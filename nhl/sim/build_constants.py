#!/usr/bin/env python3
"""
Measure league constants v2 from 2021-22 + 2022-23 event tables (S7 timeline).

Output: nhl/data/sim/constants_v2.json. v1 withdrawn.
Every entry has n, numerator, denominator and its units.
2023-24 values as validate_drift (reported, never used).
"""
import argparse, gzip, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
PBP_DIR = ROOT / "nhl" / "cache" / "pbp"
BOX_DIR = ROOT / "nhl" / "cache"
OUT_V2 = ROOT / "nhl" / "data" / "sim" / "constants_v2.json"
MANIFEST = ROOT / "research" / "nhl_sim" / "constants_v1_manifest.md"

FIT_SEASONS = [2021, 2022]
VAL_SEASON = 2023
GAMES_PER_SEASON = 1312


def load(season, table):
    path = EVENTS_DIR / f"season={season}" / f"{table}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def strength_from_home_view(home_sk, away_sk):
    """Strength state from the HOME team's perspective."""
    return f"{home_sk}v{away_sk}"


def compute_constants(seasons):
    shots_list = [load(s, "shots") for s in seasons]
    pens_list = [load(s, "penalties") for s in seasons]
    state_list = [load(s, "state_time") for s in seasons]

    shots = pd.concat(shots_list, ignore_index=True)
    pens = pd.concat(pens_list, ignore_index=True)
    state = pd.concat(state_list, ignore_index=True)

    n_games = shots["game_id"].nunique()
    constants = {}

    # ── Strength state seconds (from the GAME's perspective, not a team's) ──
    # State is {home_sk}v{away_sk}. For per-team rates, we need to know which team
    # is shooting. Home shooting at 5v4 = home PP; away shooting at 5v4 = away PK.

    # Per-team, per-strength: split shots by shooting_team and their strength
    STRENGTH_STATES = ["5v5", "5v4", "4v5", "4v4", "3v3", "6v5", "5v6"]

    # State seconds: from the HOME team's perspective
    state["strength_home"] = state.apply(
        lambda r: f"{r['home_skaters']}v{r['away_skaters']}", axis=1)

    for st in STRENGTH_STATES:
        st_secs = state[state["strength_home"] == st]["duration"].sum()
        # Home team's attempts in this state
        home_shots_in_state = shots[(shots["strength"] == st) & (shots["shooting_team"] == "home")]
        # Away team: if home state is 5v4, away sees 4v5
        # But shots["strength"] is already from the SHOOTING team's view
        # So away shooting in state where home is 5v4 means away is at 4v5
        # We need to map: home state 5v4 -> away state 4v5
        away_st = f"{st.split('v')[1]}v{st.split('v')[0]}"
        away_shots_in_state = shots[(shots["strength"] == away_st) & (shots["shooting_team"] == "away")]

        total_attempts = len(home_shots_in_state) + len(away_shots_in_state)
        total_goals = home_shots_in_state["is_goal"].sum() + away_shots_in_state["is_goal"].sum()

        rate_per_60_per_team = total_attempts / st_secs * 3600 / 2 if st_secs > 0 else 0
        goal_per_attempt = total_goals / total_attempts if total_attempts > 0 else 0

        constants[f"attempt_rate_per_60_per_team_{st}"] = {
            "value": round(rate_per_60_per_team, 2),
            "numerator": total_attempts, "denominator": round(st_secs),
            "units": "attempts / (seconds * 2 teams) * 3600",
            "derivation": f"both teams' unblocked attempts in {st} / seconds in {st} / 2 * 3600"
        }
        constants[f"xg_per_attempt_{st}"] = {
            "value": round(goal_per_attempt, 4),
            "numerator": int(total_goals), "denominator": total_attempts,
            "units": "goals / attempts",
            "derivation": f"goals / unblocked attempts in {st}"
        }

    # ── Score effects on attempt rate (5v5 only) ──
    ev_5v5 = shots[shots["strength"] == "5v5"]
    ev_5v5_state = state[state["strength_home"] == "5v5"]

    for sd in range(-3, 4):
        for period in [1, 2, 3]:
            # Attempts at this score diff (from shooter's view) in this period
            attempts_sd = len(ev_5v5[(ev_5v5["score_diff"] == sd) & (ev_5v5["period"] == period)])
            secs_sd = ev_5v5_state[(ev_5v5_state["score_diff_home"] == sd) & (ev_5v5_state["period"] == period)]["duration"].sum() + \
                      ev_5v5_state[(ev_5v5_state["score_diff_home"] == -sd) & (ev_5v5_state["period"] == period)]["duration"].sum()
            rate_sd = attempts_sd / secs_sd * 3600 if secs_sd > 0 else 0

            # Tied baseline
            attempts_0 = len(ev_5v5[(ev_5v5["score_diff"] == 0) & (ev_5v5["period"] == period)])
            secs_0 = ev_5v5_state[(ev_5v5_state["score_diff_home"] == 0) & (ev_5v5_state["period"] == period)]["duration"].sum() * 2
            rate_0 = attempts_0 / secs_0 * 3600 if secs_0 > 0 else 0

            mult = rate_sd / rate_0 if rate_0 > 0 else 1.0

            constants[f"score_effect_attempt_mult_sd{sd}_p{period}"] = {
                "value": round(mult, 3),
                "rate": round(rate_sd, 1), "base_rate": round(rate_0, 1),
                "n_attempts": attempts_sd, "n_seconds": round(secs_sd),
                "derivation": f"attempts/60 at sd={sd} p{period} / attempts/60 at tied p{period} (5v5)"
            }

            # xG per attempt score effect
            goals_sd = ev_5v5[(ev_5v5["score_diff"] == sd) & (ev_5v5["period"] == period)]["is_goal"].sum()
            xg_sd = goals_sd / attempts_sd if attempts_sd > 0 else 0
            goals_0 = ev_5v5[(ev_5v5["score_diff"] == 0) & (ev_5v5["period"] == period)]["is_goal"].sum()
            xg_0 = goals_0 / attempts_0 if attempts_0 > 0 else 0
            xg_mult = xg_sd / xg_0 if xg_0 > 0 else 1.0

            constants[f"score_effect_xg_mult_sd{sd}_p{period}"] = {
                "value": round(xg_mult, 3),
                "n_goals": int(goals_sd), "n_attempts": attempts_sd,
                "derivation": f"goals/attempt at sd={sd} p{period} / goals/attempt at tied p{period} (5v5)"
            }

    # ── Penalties per team per 60 ──
    total_game_seconds = n_games * 3600
    n_pens = len(pens)
    pen_per_team_per_game = n_pens / n_games / 2
    constants["penalties_per_team_per_game"] = {
        "value": round(pen_per_team_per_game, 2),
        "numerator": n_pens, "denominator": n_games * 2,
        "units": "penalties / team-games",
        "derivation": "total penalties / (games * 2 teams)"
    }

    # Minor/double-minor/major shares
    minors = len(pens[pens["minutes"] == 2])
    doubles = len(pens[pens["minutes"] == 4])
    majors = len(pens[pens["minutes"] == 5])
    constants["penalty_shares"] = {
        "minor_2min": round(minors / n_pens, 3) if n_pens else 0,
        "double_minor_4min": round(doubles / n_pens, 3) if n_pens else 0,
        "major_5min": round(majors / n_pens, 3) if n_pens else 0,
        "n": n_pens,
        "derivation": "count by duration / total penalties"
    }

    # ── PP goals per 60 ──
    pp_shots = shots[shots["strength"].isin(["5v4", "5v3", "4v3"])]
    pp_goals = int(pp_shots["is_goal"].sum())
    # PP time = seconds at 5v4 + 4v5 + ... (both teams' PP)
    pp_states = ["5v4", "5v3", "4v3"]
    pk_states = ["4v5", "3v5", "3v4"]
    pp_secs = sum(state[state["strength_home"] == s]["duration"].sum() for s in pp_states + pk_states)
    pp_g_per_60 = pp_goals / pp_secs * 3600 if pp_secs > 0 else 0
    constants["pp_goals_per_60"] = {
        "value": round(pp_g_per_60, 2),
        "numerator": pp_goals, "denominator": round(pp_secs),
        "units": "goals / seconds * 3600",
        "derivation": "PP goals (both teams) / total PP seconds (both teams) * 3600"
    }

    # ── Pulled goalie hazard ──
    # Detect goalie-out transitions from the S7 timeline: spans where goalie=0
    # that follow a span where goalie=1, by score diff in 3rd period last 5 min
    pull_events = []
    for gid in state["game_id"].unique():
        g_state = state[state["game_id"] == gid].sort_values("start_sec")
        for idx in range(1, len(g_state)):
            prev = g_state.iloc[idx - 1]
            curr = g_state.iloc[idx]
            if curr["period"] != 3:
                continue
            # Home pull: home_goalie goes from 1 to 0
            if prev["home_goalie"] == 1 and curr["home_goalie"] == 0 and curr["score_diff_home"] < 0:
                sec_remaining = 3600 - curr["start_sec"]
                pull_events.append({"team": "home", "score_diff": curr["score_diff_home"],
                                    "sec_remaining": sec_remaining, "game_id": gid})
            # Away pull: away_goalie goes from 1 to 0
            if prev["away_goalie"] == 1 and curr["away_goalie"] == 0 and curr["score_diff_home"] > 0:
                sec_remaining = 3600 - curr["start_sec"]
                pull_events.append({"team": "away", "score_diff": -curr["score_diff_home"],
                                    "sec_remaining": sec_remaining, "game_id": gid})

    pull_df = pd.DataFrame(pull_events)
    if len(pull_df):
        for sd in [-1, -2, -3]:
            sd_pulls = pull_df[pull_df["score_diff"] == sd]
            if len(sd_pulls) == 0:
                continue
            last_3min = (sd_pulls["sec_remaining"] <= 180).sum()
            pct = last_3min / len(sd_pulls)
            # 30-second bins for last 5 min
            bins = {}
            for _, r in sd_pulls.iterrows():
                if r["sec_remaining"] <= 300:
                    b = int(r["sec_remaining"] // 30) * 30
                    bins[b] = bins.get(b, 0) + 1
            constants[f"pull_hazard_sd{sd}"] = {
                "total_pulls": len(sd_pulls),
                "in_last_3min": int(last_3min),
                "pct_last_3min": round(pct, 3),
                "bins_30s": dict(sorted(bins.items())),
                "derivation": f"goalie-out transitions at score_diff={sd} in 3rd period"
            }

    # ── Empty-net rates ──
    en_for_leader = shots[(shots["strength"] == "5v6") & (shots["score_diff"] > 0)]
    en_against_trailer = shots[(shots["strength"] == "6v5")]  # trailing team shooting
    en_secs = state[(state["home_goalie"] == 0) | (state["away_goalie"] == 0)]
    en_total_secs = en_secs["duration"].sum()

    constants["en_attempts_per_60_leader"] = {
        "value": round(len(en_for_leader) / en_total_secs * 3600, 1) if en_total_secs else 0,
        "n": len(en_for_leader), "seconds": round(en_total_secs),
        "derivation": "leading team shots at empty net / empty-net seconds * 3600"
    }
    constants["en_goal_rate_leader"] = {
        "value": round(en_for_leader["is_goal"].mean(), 3) if len(en_for_leader) else 0,
        "goals": int(en_for_leader["is_goal"].sum()), "attempts": len(en_for_leader),
        "derivation": "goals / attempts when shooting at empty net"
    }

    # ── OT stats ──
    ot_shots = shots[shots["period"] == 4]
    ot_secs = state[state["period"] == 4]["duration"].sum()
    ot_rate_per_60 = len(ot_shots) / ot_secs * 3600 / 2 if ot_secs else 0
    ot_goals = int(ot_shots["is_goal"].sum())
    ot_xg_per_att = ot_goals / len(ot_shots) if len(ot_shots) else 0

    # Count OT vs SO outcomes
    box_dir = BOX_DIR
    ot_decided = 0
    so_decided = 0
    reg_games = 0
    for s in seasons:
        for i in range(1, GAMES_PER_SEASON + 1):
            bp = box_dir / f"boxscore_{s}02{i:04d}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
            if outcome == "OT":
                ot_decided += 1
            elif outcome == "SO":
                so_decided += 1
            else:
                reg_games += 1

    total_ot_games = ot_decided + so_decided
    ot_share = ot_decided / total_ot_games if total_ot_games else 0
    constants["ot_per_60_per_team"] = {
        "value": round(ot_rate_per_60, 1), "attempts": len(ot_shots), "seconds": round(ot_secs),
        "derivation": "OT attempts / OT seconds / 2 teams * 3600"
    }
    constants["ot_xg_per_attempt"] = {
        "value": round(ot_xg_per_att, 4), "goals": ot_goals, "attempts": len(ot_shots),
        "derivation": "OT goals / OT attempts"
    }
    constants["ot_decided_share"] = {
        "value": round(ot_share, 3), "ot_decided": ot_decided, "so_decided": so_decided,
        "total_ot_games": total_ot_games,
        "derivation": "games decided in OT / total OT+SO games"
    }

    # ── Shootout ──
    so_goals = 0
    so_attempts = 0
    so_past_r3 = 0
    so_total = 0
    for s in seasons:
        for i in range(1, GAMES_PER_SEASON + 1):
            gid = f"{s}02{i:04d}"
            path = PBP_DIR / f"{gid}.json.gz"
            if not path.exists():
                continue
            with gzip.open(path, "rt") as f:
                data = json.load(f)
            so_plays = [p for p in data.get("plays", [])
                        if p.get("periodDescriptor", {}).get("periodType") == "SO"]
            if not so_plays:
                continue
            so_total += 1
            for p in so_plays:
                tk = p.get("typeDescKey", "")
                if tk in ("shot-on-goal", "goal", "missed-shot"):
                    so_attempts += 1
                    if tk == "goal":
                        so_goals += 1
            # Past round 3: more than 6 attempts (3 per team)
            attempt_plays = [p for p in so_plays if p.get("typeDescKey") in ("shot-on-goal", "goal", "missed-shot")]
            if len(attempt_plays) > 6:
                so_past_r3 += 1

    so_conversion = so_goals / so_attempts if so_attempts else 0
    constants["shootout_conversion"] = {
        "value": round(so_conversion, 3), "goals": so_goals, "attempts": so_attempts,
        "derivation": "shootout goals / shootout attempts"
    }
    constants["shootout_past_r3_share"] = {
        "value": round(so_past_r3 / so_total, 3) if so_total else 0,
        "past_r3": so_past_r3, "total": so_total,
        "derivation": "shootouts with > 6 attempts / total shootouts"
    }

    # ── Home ice ──
    home_att = len(shots[shots["shooting_team"] == "home"])
    away_att = len(shots[shots["shooting_team"] == "away"])
    home_share = home_att / (home_att + away_att)
    constants["home_attempt_share"] = {
        "value": round(home_share, 4),
        "home": home_att, "away": away_att,
        "derivation": "home unblocked attempts / total"
    }

    home_goals = shots[(shots["shooting_team"] == "home") & (shots["is_goal"])].shape[0]
    away_goals = shots[(shots["shooting_team"] == "away") & (shots["is_goal"])].shape[0]
    home_gr = home_goals / home_att if home_att else 0
    away_gr = away_goals / away_att if away_att else 0
    constants["home_xg_per_attempt_mult"] = {
        "value": round(home_gr / away_gr, 4) if away_gr else 1.0,
        "home_rate": round(home_gr, 5), "away_rate": round(away_gr, 5),
        "derivation": "home goals/attempt / away goals/attempt"
    }

    return constants, n_games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Computing constants v2 from seasons {FIT_SEASONS}...")
    constants, n_games = compute_constants(FIT_SEASONS)

    print(f"\n{'='*60}")
    print(f"CONSTANTS V2 (fitted on {FIT_SEASONS}, {n_games} games)")
    print(f"{'='*60}")

    # Print key values
    for k in sorted(constants):
        v = constants[k]
        if isinstance(v, dict) and "value" in v:
            print(f"  {k}: {v['value']}")

    # Pre-registered checks
    print(f"\n{'='*60}")
    print("PRE-REGISTERED CHECKS")
    print(f"{'='*60}")

    pen = constants.get("penalties_per_team_per_game", {}).get("value", 0)
    print(f"  Penalties per team per game: {pen} (expected 2.8-4.5)")

    trailing_1_p3 = constants.get("score_effect_attempt_mult_sd-1_p3", {}).get("value", 0)
    leading_1_p3 = constants.get("score_effect_attempt_mult_sd1_p3", {}).get("value", 0)
    print(f"  Trailing by 1, 3rd period attempt mult: {trailing_1_p3} (expected > 1.05)")
    print(f"  Leading by 1, 3rd period attempt mult: {leading_1_p3} (expected < 0.95)")

    pull_m1 = constants.get("pull_hazard_sd-1", {})
    if pull_m1:
        print(f"  Pull at -1, % in last 3:00: {pull_m1.get('pct_last_3min', 0):.1%} "
              f"(expected > 80%, n={pull_m1.get('total_pulls', 0)})")

    so_conv = constants.get("shootout_conversion", {}).get("value", 0)
    print(f"  Shootout conversion: {so_conv:.1%} (expected 28-35%)")

    ot_dec = constants.get("ot_decided_share", {}).get("value", 0)
    print(f"  OT decided share: {ot_dec:.1%} (expected 55-75%)")

    # Validation drift
    print(f"\nComputing 2023-24 for validate_drift...")
    val_constants, val_n = compute_constants([VAL_SEASON])
    drift = {}
    for k in constants:
        fit_v = constants.get(k, {})
        val_v = val_constants.get(k, {})
        if isinstance(fit_v, dict) and "value" in fit_v and isinstance(val_v, dict) and "value" in val_v:
            drift[k] = {"fit": fit_v["value"], "val": val_v["value"]}

    if args.dry_run:
        print("--dry-run: not saving"); return

    # Save
    out = {
        "version": 2,
        "fit_seasons": FIT_SEASONS,
        "n_games": n_games,
        "constants": constants,
        "validate_drift": drift,
    }
    OUT_V2.parent.mkdir(parents=True, exist_ok=True)
    OUT_V2.write_text(json.dumps(out, indent=2) + "\n")

    sha = hashlib.sha256(OUT_V2.read_bytes()).hexdigest()
    print(f"\nSaved: {OUT_V2}")
    print(f"sha256: {sha}")

    # Update manifest (v1 withdrawn, v2 active)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        f"# constants manifest\n\n"
        f"## v1 (WITHDRAWN — defects #1,3,4,5 from verification)\n\n"
        f"## v2 (active)\nsha256: {sha}\nfit_seasons: {FIT_SEASONS}\nn_games: {n_games}\n"
    )
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
