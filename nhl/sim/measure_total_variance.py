#!/usr/bin/env python3
"""S46 generator: total-goals variance measurement.

Measures total-goals variance, P(total >= 7), and goal-diff variance from
actual game results and league-average engine simulations.

Usage:
  python3 nhl/sim/measure_total_variance.py [--n-sims 100000]
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BOX_DIR = ROOT / "nhl" / "cache"
GAMES_PER = 1312

from nhl.sim.engine import simulate, league_average_inputs


def load_actuals(seasons):
    """Load actual scores from cached boxscores for given seasons."""
    rows = []
    for season in seasons:
        for i in range(1, GAMES_PER + 1):
            gid = f"{season}02{i:04d}"
            bp = BOX_DIR / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            hs = d["homeTeam"]["score"]
            as_ = d["awayTeam"]["score"]
            rows.append({"game_id": gid, "season": season,
                         "home_score": hs, "away_score": as_,
                         "total": hs + as_, "diff": hs - as_})
    return pd.DataFrame(rows)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sims", type=int, default=100000)
    args = ap.parse_args()

    # Measurement on 2021-22 + 2022-23 (fit seasons)
    act = load_actuals([2021, 2022])
    n_games = len(act)
    print(f"Actual: {n_games} games (2021-22 + 2022-23)")

    actual_total_var = act["total"].var()
    actual_p_ge7 = (act["total"] >= 7).mean()
    actual_diff_var = act["diff"].var()

    print(f"  Total-goals variance: {actual_total_var:.3f}")
    print(f"  P(total >= 7):        {actual_p_ge7:.3f}")
    print(f"  Goal-diff variance:   {actual_diff_var:.3f}")

    # Engine: league-average, n_sims per game
    base = league_average_inputs()
    r = simulate(base, args.n_sims, seed=42)
    eng_total = r["home_score"] + r["away_score"]
    eng_diff = r["home_score"] - r["away_score"]

    eng_total_var = float(eng_total.var())
    eng_p_ge7 = float((eng_total >= 7).mean())
    eng_diff_var = float(eng_diff.var())

    print(f"\nEngine (league-avg, {args.n_sims:,} sims):")
    print(f"  Total-goals variance: {eng_total_var:.3f}")
    print(f"  P(total >= 7):        {eng_p_ge7:.3f}")
    print(f"  Goal-diff variance:   {eng_diff_var:.3f}")

    ratio = actual_total_var / eng_total_var
    print(f"\nRatio actual/engine total variance: {ratio:.3f}")
    print(f"Engine {'OVER' if eng_total_var > actual_total_var else 'UNDER'}-disperses totals")


if __name__ == "__main__":
    main()
