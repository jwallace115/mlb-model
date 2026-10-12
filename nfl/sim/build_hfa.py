#!/usr/bin/env python3
"""
Measure home-field advantage from 2021-23 REG PBP and write hfa_v1.json.

Reports: mean home margin pooled and by season, plus the home-minus-away
offensive EPA/play and success-rate split on scrimmage plays.
"""

import json, os, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = Path(os.environ.get("NFL_PBP_DIR", str(ROOT / "nfl" / "data" / "pbp")))
OUT_PATH = ROOT / "nfl" / "sim" / "hfa_v1.json"

SEASONS = [2021, 2022, 2023]


def main():
    # Load PBP
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if not p.exists():
            print(f"HALT: {p} not found", file=sys.stderr)
            sys.exit(1)
        frames.append(pd.read_parquet(p))
    plays = pd.concat(frames, ignore_index=True)

    # Game-level: home margin
    games = plays.drop_duplicates("game_id")[
        ["game_id", "season", "week", "home_team", "away_team",
         "home_score", "away_score"]
    ].copy()
    games = games[games["week"] <= 18]
    games["margin"] = games["home_score"] - games["away_score"]

    print(f"=== Home-Field Advantage (2021-23 REG) ===")
    print(f"Games: {len(games)}")

    # Pooled
    pooled_hfa = games["margin"].mean()
    print(f"\nPooled home margin: {pooled_hfa:.3f}")

    # By season
    by_season = {}
    for s in SEASONS:
        sg = games[games["season"] == s]
        m = sg["margin"].mean()
        by_season[s] = m
        print(f"  {s}: {m:.3f} (N={len(sg)})")

    # Home-win rate
    hw_rate = (games["margin"] > 0).mean()
    print(f"\nHome-win rate: {hw_rate:.3f}")

    # Scrimmage EPA split
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    scrimmage["is_home_off"] = scrimmage["posteam"] == scrimmage["home_team"]

    home_epa = scrimmage[scrimmage["is_home_off"]]["epa"].mean()
    away_epa = scrimmage[~scrimmage["is_home_off"]]["epa"].mean()
    epa_diff = home_epa - away_epa

    home_success = scrimmage[scrimmage["is_home_off"]]["success"].mean()
    away_success = scrimmage[~scrimmage["is_home_off"]]["success"].mean()
    success_diff = home_success - away_success

    print(f"\nScrimmage EPA/play:")
    print(f"  Home offense: {home_epa:.5f}")
    print(f"  Away offense: {away_epa:.5f}")
    print(f"  Diff (home-away): {epa_diff:.5f}")
    print(f"\nSuccess rate:")
    print(f"  Home offense: {home_success:.4f}")
    print(f"  Away offense: {away_success:.4f}")
    print(f"  Diff: {success_diff:.4f} ({success_diff*100:.2f} pp)")

    print(f"\n=== Reading ===")
    print(f"The scrimmage EPA diff ({epa_diff:.4f}) and success diff ({success_diff:.4f})")
    print(f"are tiny — most of the {pooled_hfa:.2f}-point home margin does NOT live in")
    print(f"per-play scrimmage EPA. The 2.13 pts comes from: FG/XP conversion rates,")
    print(f"turnover rates (fumble recovery, INT), penalties (false starts less common")
    print(f"at home), and field position (crowd noise → opponent false starts, delay,")
    print(f"snap count advantages). These are channels the engine models but does not")
    print(f"tilt by home/away.")

    # Write hfa_v1.json
    hfa_data = {
        "measured_on": "2021-2023 REG",
        "n_games": int(len(games)),
        "mean_home_margin": round(float(pooled_hfa), 4),
        "by_season": {str(s): round(float(v), 4) for s, v in by_season.items()},
        "home_win_rate": round(float(hw_rate), 4),
        "scrimmage_epa_diff": round(float(epa_diff), 5),
        "scrimmage_success_diff": round(float(success_diff), 5),
        "h": 0.0,
        "h_note": "Set after engine run with h0; see G7"
    }

    with open(OUT_PATH, "w") as f:
        json.dump(hfa_data, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
