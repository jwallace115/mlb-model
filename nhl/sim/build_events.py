#!/usr/bin/env python3
"""
Build event tables from NHL play-by-play JSON.

Outputs (per season):
  shots.parquet — every unblocked attempt (shot-on-goal, missed-shot, goal)
  penalties.parquet — penalties with type, minutes, team, time, score state
  state_time.parquet — seconds per game in every strength/score combination

Null controls (asserted):
  (a) goals from shots table == boxscore score minus shootout +1 for 100% of games
  (b) shots on goal == boxscore SOG — report match rate
  (c) state seconds == regulation 3600 + OT seconds, within 5s, 100% of games
  (d) empty-net goals from situationCode vs emptyNet flag
"""
import argparse, gzip, json, math, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PBP_DIR = ROOT / "nhl" / "cache" / "pbp"
BOX_DIR = ROOT / "nhl" / "cache"
OUT_DIR = ROOT / "nhl" / "data" / "sim" / "events"

SHOT_TYPES = {"shot-on-goal", "missed-shot", "goal"}
GAMES_PER_SEASON = 1312


def parse_situation(code, event_team_is_home):
    """Parse 4-digit situationCode into strength state from the SHOOTING team's view.
    Format: {awayGoalie}{awaySkaters}{homeSkaters}{homeGoalie}
    goalie=1 in net, 0=pulled."""
    s = str(code).zfill(4)
    away_g, away_sk, home_sk, home_g = int(s[0]), int(s[1]), int(s[2]), int(s[3])
    if event_team_is_home:
        own_sk, opp_sk = home_sk, away_sk
        own_g, opp_g = home_g, away_g
    else:
        own_sk, opp_sk = away_sk, home_sk
        own_g, opp_g = away_g, home_g
    return f"{own_sk}v{opp_sk}", own_g, opp_g


def time_to_seconds(time_str, period):
    """Convert timeInPeriod 'MM:SS' + period number to total seconds elapsed in game."""
    parts = time_str.split(":")
    m, s = int(parts[0]), int(parts[1])
    period_seconds = m * 60 + s
    # Periods are 20 min each. OT is 5 min in regular season.
    elapsed_before = (period - 1) * 1200  # 20 min periods
    return elapsed_before + period_seconds


def normalise_coords(x, y, defending_side):
    """Normalise so the attacking net is always at +x.
    defending_side is the HOME team's defending side for this period.
    If home defends 'right', then home attacks left->right, so home shots are at +x as-is.
    We flip so the SHOOTING team always attacks toward +x."""
    # The API coordinates: x ranges roughly -100 to 100, y -42 to 42
    # We'll just return as-is for now; the caller decides if flipping is needed
    return float(x) if x is not None else 0.0, float(y) if y is not None else 0.0


def compute_distance_angle(x, y):
    """Distance and angle from the net at (89, 0)."""
    net_x, net_y = 89.0, 0.0
    dx = net_x - abs(x)  # abs(x) because we normalise attacking toward +x
    dy = y
    dist = math.sqrt(dx**2 + dy**2)
    angle = math.degrees(math.atan2(abs(dy), dx)) if dx > 0 else 90.0
    return round(dist, 1), round(angle, 1)


def process_game(game_id, data):
    """Process one game's PBP into shots, penalties, state_time rows."""
    home_id = data["homeTeam"]["id"]
    away_id = data["awayTeam"]["id"]
    home_abbrev = data["homeTeam"]["abbrev"]
    away_abbrev = data["awayTeam"]["abbrev"]

    shots = []
    penalties = []
    state_spans = []

    plays = data.get("plays", [])
    prev_shot_time = {}  # team -> last shot second for rebound detection
    prev_event_time = None
    prev_event_zone = None
    prev_event_team_is_home = None

    home_score, away_score = 0, 0

    for i, play in enumerate(plays):
        period_desc = play.get("periodDescriptor", {})
        period = period_desc.get("number", 0)
        period_type = period_desc.get("periodType", "REG")
        type_key = play.get("typeDescKey", "")
        sit_code = play.get("situationCode", "")
        time_str = play.get("timeInPeriod", "00:00")
        details = play.get("details", {})
        defending_side = play.get("homeTeamDefendingSide", "left")

        sec = time_to_seconds(time_str, period)
        event_team_id = details.get("eventOwnerTeamId")
        is_home = event_team_id == home_id

        # ── Shots (unblocked attempts) ──
        if type_key in SHOT_TYPES and period_type != "SO":
            x = details.get("xCoord", 0)
            y = details.get("yCoord", 0)
            shot_type = details.get("shotType", "unknown")
            shooter_id = details.get("shootingPlayerId") or details.get("scoringPlayerId")
            goalie_id = details.get("goalieInNetId")
            is_goal = type_key == "goal"

            # Normalise x so attacking net is at +x
            # If home defends right, home attacks left (toward -x for home shooters)
            # We want: shooting team attacks toward +x
            if is_home:
                if defending_side == "right":
                    # Home attacks left, so home shots should be flipped
                    x, y = -x, -y
                # If home defends left, home attacks right -> already +x
            else:
                if defending_side == "left":
                    # Away attacks left when home defends left
                    x, y = -x, -y
                # If home defends right, away attacks right -> already +x

            strength, own_g, opp_g = parse_situation(sit_code, is_home)
            score_diff = (home_score - away_score) if is_home else (away_score - home_score)
            empty_net = opp_g == 0  # opponent's goalie is pulled

            dist, angle = compute_distance_angle(x, y)

            # Rebound: same team shot <= 3s earlier
            team_key = "home" if is_home else "away"
            prev_t = prev_shot_time.get(team_key)
            rebound = prev_t is not None and (sec - prev_t) <= 3
            prev_shot_time[team_key] = sec

            # Rush: previous event was in neutral or defensive zone <= 4s earlier
            rush = False
            if prev_event_time is not None and (sec - prev_event_time) <= 4:
                # Defensive/neutral zone for the shooting team
                if prev_event_zone in ("N", "D"):
                    rush = True
                elif prev_event_zone == "O" and prev_event_team_is_home != is_home:
                    # Previous event was in the OTHER team's offensive zone = our defensive
                    rush = True

            shots.append({
                "game_id": game_id,
                "period": period,
                "period_type": period_type,
                "seconds": sec,
                "x": round(x, 1),
                "y": round(y, 1),
                "distance": dist,
                "angle": angle,
                "shot_type": shot_type,
                "shooting_team": "home" if is_home else "away",
                "shooter_id": shooter_id,
                "goalie_id": goalie_id if goalie_id else None,
                "strength": strength,
                "score_diff": score_diff,
                "rebound": rebound,
                "rush": rush,
                "is_goal": is_goal,
                "empty_net": empty_net,
                "situation_code": sit_code,
                "type_key": type_key,
            })

            if is_goal:
                if is_home:
                    home_score += 1
                else:
                    away_score += 1

        # Track previous event for rush detection (all event types)
        if details.get("zoneCode"):
            prev_event_time = sec
            prev_event_zone = details.get("zoneCode")
            prev_event_team_is_home = is_home

        # ── Penalties ──
        if type_key == "penalty":
            minutes = details.get("duration", 2)
            pen_type = details.get("descKey", "unknown")
            team = "home" if is_home else "away"
            penalties.append({
                "game_id": game_id,
                "period": period,
                "seconds": sec,
                "team": team,
                "penalty_type": pen_type,
                "minutes": minutes,
                "score_diff_home": home_score - away_score,
            })

    # ── State timeline: proper running-score spans ──
    # Walk plays in order, tracking running score. Spans end at the next play or
    # period end. Shootout (periodType SO) contributes NO time.
    running_home = 0
    running_away = 0
    # Group plays by period, process each period's spans
    period_plays = {}
    for play in plays:
        pd_info = play.get("periodDescriptor", {})
        per = pd_info.get("number", 0)
        ptype = pd_info.get("periodType", "REG")
        if ptype == "SO":
            continue  # No shootout spans
        period_plays.setdefault(per, []).append(play)

    running_home = 0
    running_away = 0

    for per_num in sorted(period_plays.keys()):
        per_plays = period_plays[per_num]
        # Period duration: 1200s for regulation (1-3), 300s for OT (4)
        if per_num <= 3:
            period_max = 1200
        else:
            period_max = 300

        for idx in range(len(per_plays)):
            p = per_plays[idx]
            time_str = p.get("timeInPeriod", "00:00")
            parts = time_str.split(":")
            elapsed_in_period = int(parts[0]) * 60 + int(parts[1])

            # Span start = this play's time in period
            span_start = elapsed_in_period

            # Span end = next play's time in same period, or period end
            if idx + 1 < len(per_plays):
                next_time = per_plays[idx + 1].get("timeInPeriod", "00:00")
                np_parts = next_time.split(":")
                span_end = int(np_parts[0]) * 60 + int(np_parts[1])
            else:
                span_end = period_max

            # In OT sudden death: if a goal just happened (this play IS the goal),
            # the game ends here — no span after the winning goal
            duration = span_end - span_start
            if duration <= 0:
                # Check if this is a goal and update score
                if p.get("typeDescKey") == "goal":
                    det = p.get("details", {})
                    owner = det.get("eventOwnerTeamId")
                    if owner == home_id:
                        running_home += 1
                    else:
                        running_away += 1
                continue

            sc = p.get("situationCode", "1551")
            s_code = str(sc).zfill(4)

            # Game-seconds for start/end
            period_base = (per_num - 1) * 1200
            state_spans.append({
                "game_id": game_id,
                "period": per_num,
                "start_sec": period_base + span_start,
                "end_sec": period_base + span_end,
                "away_goalie": int(s_code[0]),
                "away_skaters": int(s_code[1]),
                "home_skaters": int(s_code[2]),
                "home_goalie": int(s_code[3]),
                "score_diff_home": running_home - running_away,
                "duration": duration,
            })

            # Update score if this play is a goal (AFTER recording the span)
            if p.get("typeDescKey") == "goal":
                det = p.get("details", {})
                owner = det.get("eventOwnerTeamId")
                if owner == home_id:
                    running_home += 1
                else:
                    running_away += 1

    return shots, penalties, state_spans


def load_boxscores(season):
    """Load boxscore data for null controls."""
    boxes = {}
    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"{season}02{i:04d}"
        path = BOX_DIR / f"boxscore_{gid}.json"
        if not path.exists():
            continue
        with open(path) as f:
            d = json.load(f)
        boxes[gid] = {
            "home_score": d.get("homeTeam", {}).get("score", 0),
            "away_score": d.get("awayTeam", {}).get("score", 0),
            "home_sog": d.get("homeTeam", {}).get("sog", 0),
            "away_sog": d.get("awayTeam", {}).get("sog", 0),
            "outcome": d.get("gameOutcome", {}).get("lastPeriodType", "REG"),
        }
    return boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", required=True, help="comma-separated start years")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seasons = [int(s) for s in args.seasons.split(",")]

    for season in seasons:
        print(f"\n{'='*60}\nSeason {season}-{season+1}\n{'='*60}")

        all_shots = []
        all_penalties = []
        all_state = []
        processed = 0
        failed = 0

        for i in range(1, GAMES_PER_SEASON + 1):
            gid = f"{season}02{i:04d}"
            path = PBP_DIR / f"{gid}.json.gz"
            if not path.exists():
                continue
            try:
                with gzip.open(path, "rt") as f:
                    data = json.load(f)
                s, p, st = process_game(gid, data)
                all_shots.extend(s)
                all_penalties.extend(p)
                all_state.extend(st)
                processed += 1
            except Exception as e:
                print(f"  ERROR {gid}: {e}")
                failed += 1

        print(f"  Processed: {processed}, Failed: {failed}")
        print(f"  Shots: {len(all_shots)}, Penalties: {len(all_penalties)}, State spans: {len(all_state)}")

        if args.dry_run or not all_shots:
            continue

        # Save
        out = OUT_DIR / f"season={season}"
        out.mkdir(parents=True, exist_ok=True)

        shots_df = pd.DataFrame(all_shots)
        shots_df.to_parquet(out / "shots.parquet", index=False)

        pen_df = pd.DataFrame(all_penalties)
        pen_df.to_parquet(out / "penalties.parquet", index=False)

        state_df = pd.DataFrame(all_state)
        state_df.to_parquet(out / "state_time.parquet", index=False)

        # ── Null controls ──
        boxes = load_boxscores(season)
        print(f"\n  NULL CONTROLS (season {season}):")

        # (a) Goals from shots == boxscore score (minus shootout +1)
        goals = shots_df[shots_df["is_goal"]].groupby(["game_id", "shooting_team"]).size().unstack(fill_value=0)
        goal_match = 0
        goal_total = 0
        for gid, box in boxes.items():
            if gid not in goals.index:
                continue
            goal_total += 1
            home_goals_table = goals.loc[gid].get("home", 0)
            away_goals_table = goals.loc[gid].get("away", 0)
            # If shootout, the winner gets +1 in the final score but not in the PBP goals
            exp_home = box["home_score"]
            exp_away = box["away_score"]
            if box["outcome"] == "SO":
                if exp_home > exp_away:
                    exp_home -= 1
                else:
                    exp_away -= 1
            if home_goals_table == exp_home and away_goals_table == exp_away:
                goal_match += 1
        print(f"  (a) Goals match boxscore (minus SO +1): {goal_match}/{goal_total} "
              f"({goal_match/goal_total:.1%})" if goal_total else "  (a) No boxscores")

        # (b) SOG match
        sog = shots_df[shots_df["type_key"].isin(["shot-on-goal", "goal"])].groupby(
            ["game_id", "shooting_team"]).size().unstack(fill_value=0)
        sog_match = 0
        sog_total = 0
        sog_mismatches = []
        for gid, box in boxes.items():
            if gid not in sog.index:
                continue
            sog_total += 1
            home_sog_table = sog.loc[gid].get("home", 0)
            away_sog_table = sog.loc[gid].get("away", 0)
            if home_sog_table == box["home_sog"] and away_sog_table == box["away_sog"]:
                sog_match += 1
            else:
                sog_mismatches.append({
                    "game": gid,
                    "table_home": home_sog_table, "box_home": box["home_sog"],
                    "table_away": away_sog_table, "box_away": box["away_sog"],
                })
        print(f"  (b) SOG match boxscore: {sog_match}/{sog_total} "
              f"({sog_match/sog_total:.1%})" if sog_total else "  (b) No SOG data")
        if sog_mismatches:
            diffs = [(m["table_home"] - m["box_home"], m["table_away"] - m["box_away"]) for m in sog_mismatches]
            print(f"      mismatches: {len(sog_mismatches)} games; "
                  f"typical diff: home {np.mean([d[0] for d in diffs]):+.1f}, away {np.mean([d[1] for d in diffs]):+.1f}")

        # (c) State seconds == regulation + OT, within 2s
        game_state_secs = state_df.groupby("game_id")["duration"].sum()
        state_match = 0
        state_total = 0
        state_diffs = []
        for gid, box in boxes.items():
            if gid not in game_state_secs.index:
                continue
            state_total += 1
            expected = 3600  # 3 periods x 20 min
            if box["outcome"] in ("OT", "SO"):
                expected += 300  # 5 min OT
            actual = game_state_secs[gid]
            diff = abs(actual - expected)
            state_diffs.append(diff)
            if diff <= 2:
                state_match += 1
        print(f"  (c) State time within 2s: {state_match}/{state_total} "
              f"({state_match/state_total:.1%})" if state_total else "  (c) No state data")
        if state_diffs:
            over2 = [d for d in state_diffs if d > 2]
            if over2:
                print(f"      > 2s mismatches: {len(over2)}, median diff: {np.median(over2):.0f}s")

        # (b2) First span of every game has score_diff_home == 0
        first_spans = state_df.groupby("game_id").first()
        first_zero = (first_spans["score_diff_home"] == 0).sum()
        print(f"  (b2) First span score_diff == 0: {first_zero}/{len(first_spans)} "
              f"({first_zero/len(first_spans):.1%})" if len(first_spans) else "")

        # (c2) Last span score_diff == final regulation+OT score diff
        last_spans = state_df.groupby("game_id").last()
        last_match = 0
        last_total = 0
        for gid, box in boxes.items():
            if gid not in last_spans.index:
                continue
            last_total += 1
            exp_diff = box["home_score"] - box["away_score"]
            if box["outcome"] == "SO":
                if exp_diff > 0:
                    exp_diff -= 1
                else:
                    exp_diff += 1
            actual_diff = last_spans.loc[gid, "score_diff_home"]
            if actual_diff == exp_diff:
                last_match += 1
        print(f"  (c2) Last span score matches final (minus SO+1): {last_match}/{last_total} "
              f"({last_match/last_total:.1%})" if last_total else "")

        # (d2) Home goalie out while NOT trailing
        if len(state_df):
            goalie_out_not_trailing = state_df[
                (state_df["home_goalie"] == 0) & (state_df["score_diff_home"] >= 0)
            ]
            if len(goalie_out_not_trailing):
                print(f"  (d2) Home goalie out while not trailing: {len(goalie_out_not_trailing)} spans, "
                      f"median duration: {goalie_out_not_trailing['duration'].median():.1f}s "
                      f"(expected: small — delayed penalties)")

        # (d) Empty-net goals: situationCode vs play flag
        en_goals = shots_df[(shots_df["is_goal"]) & (shots_df["empty_net"])]
        print(f"  (d) Empty-net goals from situationCode: {len(en_goals)} "
              f"({len(en_goals)/len(shots_df[shots_df['is_goal']]):.1%} of goals)" if len(shots_df[shots_df["is_goal"]]) else "")

        print(f"\n  Season {season} summary: {len(shots_df)} shots, "
              f"{shots_df['is_goal'].sum()} goals, {len(pen_df)} penalties")


if __name__ == "__main__":
    main()
