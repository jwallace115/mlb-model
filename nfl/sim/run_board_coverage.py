#!/usr/bin/env python3
"""5J: Board coverage report — compares candidates vs picks_log.

Usage: python3 nfl/sim/run_board_coverage.py --week 2

Reads the newest nfl_prop_candidates parquet for the given week and
picks_log.parquet, prints coverage per market and per-row miss reasons.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
BOARD_DIR = ROOT / "nfl" / "data" / "board"
SIM_OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs"

MARKET_KEY_MAP = {
    'player_receptions': 'receptions',
    'player_reception_yds': 'rec_yds',
    'player_rush_yds': 'rush_yds',
    'player_rush_attempts': 'rush_attempts',
    'player_rush_attempts_alternate': 'rush_attempts',
    'player_anytime_td': 'anytime_td',
    'player_pass_completions': 'pass_completions',
    'player_pass_attempts': 'pass_attempts',
    'player_pass_yds': 'pass_yds',
    'player_pass_tds': 'pass_tds',
    'player_pass_interceptions': 'pass_interceptions',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    week_dir = BOARD_DIR / f"week={args.season}_{args.week:02d}"
    if not week_dir.exists():
        print(f"No board directory: {week_dir}")
        return

    # Newest candidates file
    cand_files = sorted(week_dir.glob("nfl_prop_candidates_*.parquet"))
    if not cand_files:
        print(f"No candidates parquet in {week_dir}")
        return
    cands = pd.read_parquet(cand_files[-1])
    print(f"Candidates: {cand_files[-1].name} ({len(cands)} rows)")

    # Two-way rows only
    two_way = cands[cands["two_way"] == True].copy()
    print(f"Two-way rows: {len(two_way)}")

    # Picks log
    picks_dir = SIM_OUT_DIR / f"week={args.season}_{args.week:02d}"
    picks_path = picks_dir / "picks_log.parquet"
    if not picks_path.exists():
        print(f"No picks_log.parquet at {picks_path}")
        return
    picks = pd.read_parquet(picks_path)
    print(f"Picks log: {len(picks)} legs")

    # Normalize names for join
    def _norm(s):
        return str(s).strip().lower().replace(".", "").replace("'", "")

    picks["_pname"] = picks["player_name"].apply(_norm)
    picks["_family"] = picks["family"]
    picks["_line"] = picks["line"]

    # Coverage per market
    print(f"\n{'market':30s} {'two_way':>8s} {'in_sim':>7s} {'at_line':>8s}")
    print("-" * 60)
    for mk in sorted(two_way["market_key"].unique()):
        family = MARKET_KEY_MAP.get(mk, mk)
        mk_rows = two_way[two_way["market_key"] == mk]
        n_tw = len(mk_rows)

        n_in_sim = 0
        n_at_line = 0
        for _, r in mk_rows.iterrows():
            pn = _norm(r["player_name"])
            # Is this player in the sim universe for this family?
            player_legs = picks[(picks["_pname"] == pn) & (picks["_family"] == family)]
            if len(player_legs) > 0:
                n_in_sim += 1
                # Is there a leg at this specific line?
                at_line = player_legs[abs(player_legs["_line"] - r["line"]) < 0.01]
                if len(at_line) > 0:
                    n_at_line += 1

        print(f"  {mk:28s} {n_tw:8d} {n_in_sim:7d} {n_at_line:8d}")


if __name__ == "__main__":
    main()
