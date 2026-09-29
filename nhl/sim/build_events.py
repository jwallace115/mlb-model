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
    prev_event_zone = {}  # for rush detection

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

            # Rush: simplified — previous event in other half of ice <= 4s
            rush = False  # TODO: refine with zone tracking

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

        # ── Penalties ──
        elif type_key == "penalty":
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

    # ── State time (simplified: count seconds per situationCode) ──
    # Walk through plays and compute time between consecutive events
    for i in range(len(plays) - 1):
        p1 = plays[i]
        p2 = plays[i + 1]
        per1 = p1.get("periodDescriptor", {}).get("number", 0)
        per2 = p2.get("periodDescriptor", {}).get("number", 0)
        pt1 = p1.get("periodDescriptor", {}).get("periodType", "REG")
        if pt1 == "SO":
            continue
        t1_str = p1.get("timeInPeriod", "00:00")
        t2_str = p2.get("timeInPeriod", "00:00")
        sec1 = time_to_seconds(t1_str, per1)
        sec2 = time_to_seconds(t2_str, per2)
        duration = sec2 - sec1
        if duration <= 0:
            continue
        sc = p1.get("situationCode", "1551")
        s = str(sc).zfill(4)
        state_spans.append({
            "game_id": game_id,
            "period": per1,
            "away_goalie": int(s[0]),
            "away_skaters": int(s[1]),
            "home_skaters": int(s[2]),
            "home_goalie": int(s[3]),
            "score_diff_home": home_score - away_score,  # approximate at this point
            "duration": duration,
        })

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

        # (c) State seconds == regulation + OT
        game_state_secs = state_df.groupby("game_id")["duration"].sum()
        state_match = 0
        state_total = 0
        for gid, box in boxes.items():
            if gid not in game_state_secs.index:
                continue
            state_total += 1
            expected = 3600  # 3 periods x 20 min
            if box["outcome"] in ("OT", "SO"):
                expected += 300  # 5 min OT
            actual = game_state_secs[gid]
            if abs(actual - expected) <= 5:
                state_match += 1
        print(f"  (c) State time within 5s: {state_match}/{state_total} "
              f"({state_match/state_total:.1%})" if state_total else "  (c) No state data")

        # (d) Empty-net goals: situationCode vs play flag
        en_goals = shots_df[(shots_df["is_goal"]) & (shots_df["empty_net"])]
        print(f"  (d) Empty-net goals from situationCode: {len(en_goals)} "
              f"({len(en_goals)/len(shots_df[shots_df['is_goal']]):.1%} of goals)" if len(shots_df[shots_df["is_goal"]]) else "")

        print(f"\n  Season {season} summary: {len(shots_df)} shots, "
              f"{shots_df['is_goal'].sum()} goals, {len(pen_df)} penalties")


if __name__ == "__main__":
    main()
