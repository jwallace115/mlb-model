#!/usr/bin/env python3
"""
Phase 5H diagnostic runner — collect per-decision / per-snap data
from the sim engine for downstream analysis.

Outputs (parquet):
  research/nfl_sim/diag_5h_4th.parquet     — per 4th-down decision
  research/nfl_sim/diag_5h_3rd.parquet     — per 3rd-down snap
  research/nfl_sim/diag_5h_late.parquet    — per snap in Q4 <=300s trailing/tied <=8

Usage:
  python3 nfl/sim/run_diag_5h.py [--n-games 1087] [--n-sims 500]
  python3 nfl/sim/run_diag_5h.py --verify   # byte-identity check only
"""

import argparse, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.seed_util import stable_seed

PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "research" / "nfl_sim"


def load_reg_season_games(seasons=(2021, 2022, 2023, 2024)):
    """Load all regular-season games for the given seasons."""
    frames = []
    for s in seasons:
        p = PBP_DIR / f"pbp_{s}.parquet"
        df = pd.read_parquet(p, columns=["game_id", "season", "week",
                                          "home_team", "away_team",
                                          "home_score", "away_score"])
        games = df.drop_duplicates("game_id").query("week <= 18")
        frames.append(games)
    return pd.concat(frames, ignore_index=True)


def verify_byte_identity():
    """Run 3 games x N=2000 with flag ON vs OFF, same seeds.
    Print whether all output columns are identical."""
    import nfl.sim.engine as eng
    eng._load_tables()
    team_r, tend, sit, kicker, league = eng._load_ratings()

    games_df = load_reg_season_games(seasons=(2023,))
    sample = games_df.head(3)

    print(f"Byte-identity check: {len(sample)} games, N=2000")
    all_ok = True

    for _, g in sample.iterrows():
        seed = stable_seed((g["game_id"], 42))

        # --- Run with flags OFF ---
        eng._DIAG_5H = None
        eng._DIAG_5H_3RD = None
        eng._DIAG_5H_LATE = None
        r_off = eng.simulate_game(
            g["home_team"], g["away_team"], int(g["season"]), int(g["week"]),
            n_sims=2000, seed=seed,
            team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
        )

        # --- Run with flags ON ---
        eng._DIAG_5H = []
        eng._DIAG_5H_3RD = []
        eng._DIAG_5H_LATE = []
        r_on = eng.simulate_game(
            g["home_team"], g["away_team"], int(g["season"]), int(g["week"]),
            n_sims=2000, seed=seed,
            team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
        )

        # Compare all columns
        mismatches = []
        for col in r_off.columns:
            if not np.array_equal(r_off[col].values, r_on[col].values):
                mismatches.append(col)

        game_id = g["game_id"]
        n4 = len(eng._DIAG_5H)
        n3 = len(eng._DIAG_5H_3RD)
        nL = len(eng._DIAG_5H_LATE)
        if mismatches:
            print(f"  {game_id}: MISMATCH in {mismatches}")
            all_ok = False
        else:
            print(f"  {game_id}: IDENTICAL  (4th={n4}, 3rd={n3}, late={nL})")

    # Reset flags
    eng._DIAG_5H = None
    eng._DIAG_5H_3RD = None
    eng._DIAG_5H_LATE = None

    if all_ok:
        print("\nByte-identity: PASS — flag ON produces identical output to flag OFF")
    else:
        print("\nByte-identity: FAIL — output differs with flag ON")
    return all_ok


def run_collection(n_games, n_sims):
    """Run all games with diagnostics enabled, save parquets."""
    import nfl.sim.engine as eng
    eng._load_tables()
    team_r, tend, sit, kicker, league = eng._load_ratings()

    games_df = load_reg_season_games()
    if n_games < len(games_df):
        games_df = games_df.head(n_games)

    print(f"Collecting diagnostics: {len(games_df)} games, N={n_sims} sims/game")

    eng._DIAG_5H = []
    eng._DIAG_5H_3RD = []
    eng._DIAG_5H_LATE = []

    t0 = time.time()
    for idx, (_, g) in enumerate(games_df.iterrows()):
        seed = stable_seed((g["game_id"], 42))
        eng.simulate_game(
            g["home_team"], g["away_team"], int(g["season"]), int(g["week"]),
            n_sims=n_sims, seed=seed,
            team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
        )
        if (idx + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = elapsed / (idx + 1)
            eta = rate * (len(games_df) - idx - 1)
            print(f"  {idx+1}/{len(games_df)} games, "
                  f"{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining, "
                  f"4th={len(eng._DIAG_5H)}, 3rd={len(eng._DIAG_5H_3RD)}, "
                  f"late={len(eng._DIAG_5H_LATE)}")

    elapsed = time.time() - t0
    print(f"\nDone: {len(games_df)} games in {elapsed:.1f}s "
          f"({elapsed/len(games_df):.2f}s/game)")
    print(f"  4th-down decisions: {len(eng._DIAG_5H):,}")
    print(f"  3rd-down snaps:     {len(eng._DIAG_5H_3RD):,}")
    print(f"  Late-game snaps:    {len(eng._DIAG_5H_LATE):,}")

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if eng._DIAG_5H:
        df_4th = pd.DataFrame(eng._DIAG_5H)
        df_4th.to_parquet(OUT_DIR / "diag_5h_4th.parquet", index=False)
        print(f"  Saved {OUT_DIR / 'diag_5h_4th.parquet'} ({len(df_4th):,} rows)")

    if eng._DIAG_5H_3RD:
        df_3rd = pd.DataFrame(eng._DIAG_5H_3RD)
        df_3rd.to_parquet(OUT_DIR / "diag_5h_3rd.parquet", index=False)
        print(f"  Saved {OUT_DIR / 'diag_5h_3rd.parquet'} ({len(df_3rd):,} rows)")

    if eng._DIAG_5H_LATE:
        df_late = pd.DataFrame(eng._DIAG_5H_LATE)
        df_late.to_parquet(OUT_DIR / "diag_5h_late.parquet", index=False)
        print(f"  Saved {OUT_DIR / 'diag_5h_late.parquet'} ({len(df_late):,} rows)")

    # Reset flags
    eng._DIAG_5H = None
    eng._DIAG_5H_3RD = None
    eng._DIAG_5H_LATE = None


def main():
    parser = argparse.ArgumentParser(description="5H diagnostic collection")
    parser.add_argument("--n-games", type=int, default=1087,
                        help="Number of games to process (default: 1087)")
    parser.add_argument("--n-sims", type=int, default=500,
                        help="Sims per game (default: 500)")
    parser.add_argument("--verify", action="store_true",
                        help="Run byte-identity check only")
    args = parser.parse_args()

    if args.verify:
        ok = verify_byte_identity()
        sys.exit(0 if ok else 1)

    run_collection(args.n_games, args.n_sims)


if __name__ == "__main__":
    main()
