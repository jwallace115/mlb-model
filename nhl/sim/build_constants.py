#!/usr/bin/env python3
"""
Measure league constants from 2021-22 + 2022-23 event tables.

Output: nhl/data/sim/constants_v1.json — every constant has n and a derivation.
Also computes 2023-24 values as validate_drift (reported, never used in the engine).
"""
import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
OUT_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v1.json"
MANIFEST = ROOT / "research" / "nhl_sim" / "constants_v1_manifest.md"

FIT_SEASONS = [2021, 2022]
VAL_SEASON = 2023
GAMES_PER_SEASON = 1312

STRENGTH_GROUPS = {
    "5v5": "even", "4v4": "even", "3v3": "3v3",
    "5v4": "PP", "5v3": "PP", "4v3": "PP",
    "4v5": "PK", "3v5": "PK", "3v4": "PK",
}


def load(season, table):
    path = EVENTS_DIR / f"season={season}" / f"{table}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def compute_constants(seasons):
    shots_list = [load(s, "shots") for s in seasons]
    pens_list = [load(s, "penalties") for s in seasons]
    state_list = [load(s, "state_time") for s in seasons]

    shots = pd.concat(shots_list, ignore_index=True)
    pens = pd.concat(pens_list, ignore_index=True)
    state = pd.concat(state_list, ignore_index=True)

    n_games = shots["game_id"].nunique()
    constants = {}

    # ── Attempt rate per 60 by strength state ──
    shots["sg"] = shots["strength"].map(STRENGTH_GROUPS).fillna("other")
    state["sg"] = state.apply(lambda r: STRENGTH_GROUPS.get(
        f"{r['home_skaters']}v{r['away_skaters']}", "other"), axis=1)
    for sg in ["even", "PP", "PK", "3v3"]:
        sg_shots = len(shots[shots["sg"] == sg])
        sg_seconds = state[state["sg"] == sg]["duration"].sum()
        rate = sg_shots / sg_seconds * 3600 if sg_seconds > 0 else 0
        constants[f"attempt_rate_per_60_{sg}"] = {
            "value": round(rate, 2), "n_shots": sg_shots,
            "n_seconds": round(sg_seconds), "n_games": n_games,
            "derivation": f"unblocked attempts in {sg} / seconds in {sg} * 3600"
        }

    # ── Goals per xG by strength state (placeholder — uses raw goal rate for now) ──
    for sg in ["even", "PP", "PK", "3v3"]:
        sg_s = shots[shots["sg"] == sg]
        goals = sg_s["is_goal"].sum()
        n = len(sg_s)
        rate = goals / n if n > 0 else 0
        constants[f"goal_rate_{sg}"] = {
            "value": round(rate, 4), "goals": int(goals), "shots": n,
            "derivation": f"goals / unblocked attempts in {sg}"
        }

    # ── Penalties per 60 per team ──
    total_game_seconds = n_games * 3600  # approximate
    n_pens = len(pens)
    pen_rate = n_pens / (total_game_seconds / 3600) * 60 if total_game_seconds > 0 else 0
    # Per team: divide by 2 (two teams per game)
    constants["penalties_per_60_per_team"] = {
        "value": round(pen_rate / 2, 2), "n_penalties": n_pens, "n_games": n_games,
        "derivation": "total penalties / (games * 60 min) / 2 teams"
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

    # ── PP goal rate (goals per 60 of PP time) ──
    pp_shots = shots[shots["sg"] == "PP"]
    pp_goals = pp_shots["is_goal"].sum()
    pp_seconds = state[state["sg"] == "PP"]["duration"].sum()
    pp_g_per_60 = pp_goals / pp_seconds * 3600 if pp_seconds > 0 else 0
    constants["pp_goals_per_60"] = {
        "value": round(pp_g_per_60, 2), "goals": int(pp_goals),
        "pp_seconds": round(pp_seconds),
        "derivation": "PP goals / PP seconds * 3600"
    }

    # ── Score effects on attempt rate ──
    for score_diff in range(-3, 4):
        for period in [1, 2, 3]:
            mask = (shots["score_diff"] == score_diff) & (shots["period"] == period) & (shots["sg"] == "even")
            n = len(shots[mask])
            base_mask = (shots["score_diff"] == 0) & (shots["period"] == period) & (shots["sg"] == "even")
            base = len(shots[base_mask])
            mult = n / base if base > 0 else 1.0
            constants[f"score_effect_attempts_sd{score_diff}_p{period}"] = {
                "value": round(mult, 3), "n": n, "n_base": base,
                "derivation": f"attempts at score_diff={score_diff} period {period} / attempts at tied"
            }

    # ── Pulled goalie hazard ──
    # Simplified: count empty-net situations by score diff and seconds remaining
    en_shots = shots[(shots["empty_net"]) & (shots["period"] == 3)]
    for sd in [-1, -2, -3]:
        mask = en_shots["score_diff"] == sd
        n_en = len(en_shots[mask])
        constants[f"pull_en_shots_sd{sd}"] = {
            "value": n_en, "n": n_en, "n_games": n_games,
            "derivation": f"empty-net shots against at score_diff={sd} in 3rd period"
        }

    # ── Home ice ──
    home_attempts = len(shots[shots["shooting_team"] == "home"])
    away_attempts = len(shots[shots["shooting_team"] == "away"])
    total = home_attempts + away_attempts
    home_share = home_attempts / total if total else 0.5
    constants["home_attempt_share"] = {
        "value": round(home_share, 4),
        "home": home_attempts, "away": away_attempts,
        "derivation": "home unblocked attempts / total"
    }

    home_goals = shots[(shots["shooting_team"] == "home") & (shots["is_goal"])].shape[0]
    away_goals = shots[(shots["shooting_team"] == "away") & (shots["is_goal"])].shape[0]
    home_goal_rate = home_goals / home_attempts if home_attempts else 0
    away_goal_rate = away_goals / away_attempts if away_attempts else 0
    constants["home_goal_rate_mult"] = {
        "value": round(home_goal_rate / away_goal_rate, 4) if away_goal_rate else 1.0,
        "home_rate": round(home_goal_rate, 5), "away_rate": round(away_goal_rate, 5),
        "derivation": "home goal rate / away goal rate on unblocked attempts"
    }

    # ── OT stats ──
    ot_shots = shots[shots["period"] == 4]
    ot_goals = ot_shots["is_goal"].sum()
    n_ot_shots = len(ot_shots)
    constants["ot_goal_rate"] = {
        "value": round(ot_goals / n_ot_shots, 4) if n_ot_shots else 0,
        "goals": int(ot_goals), "shots": n_ot_shots,
        "derivation": "OT goals / OT unblocked attempts"
    }

    # ── Shootout (from boxsores, rough) ──
    # Count games that went to SO
    box_dir = ROOT / "nhl" / "cache"
    so_games = 0
    ot_games = 0
    for s in seasons:
        for i in range(1, GAMES_PER_SEASON + 1):
            gid = f"{s}02{i:04d}"
            bp = box_dir / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
            if outcome == "SO":
                so_games += 1
            if outcome in ("OT", "SO"):
                ot_games += 1
    constants["ot_share"] = {
        "value": round(ot_games / n_games, 4) if n_games else 0,
        "ot_games": ot_games, "n_games": n_games,
        "derivation": "games going to OT / total games"
    }
    constants["so_share_of_ot"] = {
        "value": round(so_games / ot_games, 4) if ot_games else 0,
        "so_games": so_games, "ot_games": ot_games,
        "derivation": "shootout games / OT games"
    }

    return constants, n_games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Computing constants from seasons {FIT_SEASONS}...")
    constants, n_games = compute_constants(FIT_SEASONS)

    print(f"\n{'='*60}")
    print(f"LEAGUE CONSTANTS (fitted on {FIT_SEASONS}, {n_games} games)")
    print(f"{'='*60}")
    for k, v in constants.items():
        if isinstance(v, dict) and "value" in v:
            print(f"  {k}: {v['value']} (n={v.get('n', v.get('n_games', '?'))})")

    # Key pre-registered values
    print(f"\nPRE-REGISTERED CHECKS:")
    ppg60 = constants.get("pp_goals_per_60", {}).get("value", 0)
    print(f"  PP goals per 60: {ppg60} (expected 6-8)")
    ha = constants.get("home_attempt_share", {}).get("value", 0)
    print(f"  Home attempt share: {ha:.4f} (expected 50.5-52.0%)")

    # Validate drift on 2023-24
    print(f"\nValidation drift (2023-24):")
    val_constants, val_n = compute_constants([VAL_SEASON])
    for k in ["pp_goals_per_60", "home_attempt_share", "ot_share"]:
        fit_v = constants.get(k, {}).get("value", "?")
        val_v = val_constants.get(k, {}).get("value", "?")
        print(f"  {k}: fit={fit_v}, val={val_v}")

    if args.dry_run:
        print("--dry-run: not saving"); return

    # Save
    out = {
        "fit_seasons": FIT_SEASONS,
        "n_games": n_games,
        "constants": constants,
        "validate_drift": {k: val_constants.get(k, {}).get("value") for k in constants},
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")

    sha = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    print(f"\nSaved: {OUT_PATH}")
    print(f"sha256: {sha}")

    # Write manifest
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(f"# constants_v1 manifest\n\nsha256: {sha}\nfit_seasons: {FIT_SEASONS}\nn_games: {n_games}\n")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
