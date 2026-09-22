#!/usr/bin/env python3
"""
5N Item 3: Diagnose where the extra ~2 drives/game come from.

Compare sim vs real (2021-24, same K1 sample), with the derivation stated
for every real number.
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SEASONS = [2021, 2022, 2023, 2024]


def load_real_drives():
    """Load drive-level stats from PBP."""
    frames = []
    for s in SEASONS:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        df = pd.read_parquet(p)
        # Filter to real drives (not NA drive number)
        plays = df[df["play_type"].isin(["pass", "run", "punt", "field_goal",
                                          "kickoff", "extra_point", "no_play"])].copy()
        # Drive-level aggregation
        drives = df.dropna(subset=["drive"]).groupby(["game_id", "drive"]).agg(
            n_plays=("play_id", "count"),
            first_qtr=("qtr", "first"),
            drive_result=("fixed_drive_result", "first"),
            start_time=("game_seconds_remaining", "max"),
            end_time=("game_seconds_remaining", "min"),
        ).reset_index()
        drives["season"] = s
        drives["clock_consumed"] = drives["start_time"] - drives["end_time"]

        # Scrimmage plays only
        scrim = df[df["play_type"].isin(["pass", "run"])]
        scrim_per_drive = scrim.groupby(["game_id", "drive"]).agg(
            scrim_plays=("play_id", "count"),
        ).reset_index()
        drives = drives.merge(scrim_per_drive, on=["game_id", "drive"], how="left")
        drives["scrim_plays"] = drives["scrim_plays"].fillna(0).astype(int)

        frames.append(drives)

    return pd.concat(frames, ignore_index=True)


def load_sim_drives():
    """Load sim results from K1 rows file."""
    rows_path = ROOT / "research" / "nfl_sim" / "phase5m_k1_after_rows.parquet"
    if not rows_path.exists():
        # Fall back to any K1 rows file
        for candidate in ["phase5m_k1_after_rows.parquet", "phase5l_k1_after_rows.parquet",
                          "phase5l_k1_item1_rows.parquet"]:
            p = ROOT / "research" / "nfl_sim" / candidate
            if p.exists():
                rows_path = p
                break
    if not rows_path.exists():
        print("No K1 rows file found. Run run_k1_table.py first.")
        return None
    return pd.read_parquet(rows_path)


def main():
    t0 = time.time()
    real = load_real_drives()
    n_games = real["game_id"].nunique()
    print(f"Real: {len(real)} drives, {n_games} games")

    # Drives per game by ending type
    ending_map = {
        "Punt": "punt", "Touchdown": "td", "Field goal": "fg",
        "Turnover": "turnover", "Turnover on downs": "downs",
        "End of half": "end_half", "Safety": "safety",
        "Opp touchdown": "opp_td",
    }
    real["end_type"] = real["drive_result"].map(ending_map).fillna("other")

    print(f"\n--- Real: drives per game by ending type ---")
    dpg = real.groupby("end_type").size() / n_games
    for et in sorted(dpg.index):
        print(f"  {et:15s}: {dpg[et]:.2f}")
    print(f"  {'TOTAL':15s}: {dpg.sum():.2f}")

    # Plays per drive
    print(f"\n--- Real: scrimmage plays per drive ---")
    overall_ppd = real["scrim_plays"].mean()
    print(f"  Overall: {overall_ppd:.2f}")
    for et in ["punt", "td", "fg", "turnover", "downs"]:
        sub = real[real["end_type"] == et]
        if len(sub) > 0:
            print(f"  {et:15s}: {sub['scrim_plays'].mean():.2f} (n={len(sub)})")

    # Clock consumed per drive by ending
    print(f"\n--- Real: seconds consumed per drive by ending ---")
    for et in ["punt", "td", "fg", "turnover"]:
        sub = real[real["end_type"] == et]
        if len(sub) > 0:
            print(f"  {et:15s}: {sub['clock_consumed'].mean():.1f}s (n={len(sub)})")

    # Sim comparison from K1
    sim_rows = load_sim_drives()
    if sim_rows is not None:
        print(f"\n--- Sim (from K1 rows): ---")
        print(f"  pts/team:    {sim_rows['sim_pts_per_team'].mean():.2f}" if 'sim_pts_per_team' in sim_rows.columns else "  (K1 rows schema varies)")
        for col in sim_rows.columns:
            if 'drives' in col.lower() or 'plays' in col.lower() or 'punts' in col.lower():
                print(f"  {col}: {sim_rows[col].mean():.2f}")

    # Summary comparison
    print(f"\n{'='*60}")
    print(f"SUMMARY: Real vs Sim comparison")
    print(f"{'='*60}")
    print(f"  Real drives/game:      {dpg.sum():.2f}")
    print(f"  Real plays/drive:      {overall_ppd:.2f}")
    print(f"  Real punt drives:      {dpg.get('punt', 0):.2f}/game, "
          f"plays/punt-drive: {real[real['end_type']=='punt']['scrim_plays'].mean():.2f}")
    print(f"  Sim drives/game:       ~23.8 (from K1)")
    print(f"  Sim punts/game:        ~8.84 (from K1)")
    print(f"\n  Excess drives: ~{23.8 - dpg.sum():.1f}/game")
    print(f"  If real plays/drive were used with sim's clock: "
          f"{23.8 * overall_ppd:.0f} plays vs sim's 130.3")
    print(f"  Real total plays/game: ~{dpg.sum() * overall_ppd:.0f} "
          f"(vs sim 130.3, real 124.5)")

    print(f"\nRuntime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
