#!/usr/bin/env python3
"""
5R Item 1: Measure the pace/PROE defect and K1's exposure by week bucket.

(a) From tendencies_weekly and tendencies_situational_weekly: mean pace_sec,
    proe, n_plays by season x week, and count of team-weeks on the default.
(b) From K1 rows: plays, drives, punts by week bucket (1-2 / 3-4 / 5-8 / 9+)
    sim vs real.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.calibration import engine_fingerprint

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]


def main():
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")

    # ---- (a) Tendency tables audit ----
    tend = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "tendencies_weekly.parquet")
    sit = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "tendencies_situational_weekly.parquet")

    print(f"\n{'='*80}")
    print("(a) TENDENCIES_WEEKLY: pace_sec, proe, n_plays by season x week")
    print(f"{'='*80}")
    print(f"{'season':>6s} {'week':>4s} {'pace':>6s} {'proe':>7s} {'n_plays':>8s} {'n_teams':>7s} {'default_count':>13s}")
    print("-" * 60)

    total_defaults = 0
    for s in SEASONS:
        st = tend[tend["season"] == s]
        for wk in sorted(st["week"].unique()):
            wt = st[st["week"] == wk]
            defaults = len(wt[(wt["pace_sec"] == 28.0) & (wt["n_plays"] == 0)])
            total_defaults += defaults
            if wk <= 4 or wk in [10, 18]:
                print(f"{s:6d} {wk:4d} {wt['pace_sec'].mean():6.1f} {wt['proe'].mean():7.3f} "
                      f"{wt['n_plays'].mean():8.0f} {len(wt):7d} {defaults:13d}")

    print(f"\nTotal team-weeks on default (pace==28.0, n_plays==0): {total_defaults}")

    # Check situational table for same default
    sit_w1 = sit[(sit["n_plays"] == 0)]
    print(f"\nSituational table rows with n_plays==0: {len(sit_w1)}")
    print(f"  Seasons: {sorted(sit_w1['season'].unique())}")
    # Check if situational table has a pace column
    if "pace_sec" in sit.columns:
        sit_default = sit[(sit["pace_sec"] == 28.0) & (sit["n_plays"] == 0)]
        print(f"  Situational rows with pace==28.0 and n_plays==0: {len(sit_default)}")
    else:
        print("  Situational table has no pace_sec column (only proe by bucket)")

    # ---- (b) K1 plays/drives/punts by week bucket ----
    print(f"\n{'='*80}")
    print("(b) K1 plays/drives/punts by week bucket, sim vs real")
    print(f"{'='*80}")

    k1 = pd.read_parquet(ROOT / "research" / "nfl_sim" / "phase5l_k1_after_rows.parquet")

    # Real side: PBP 2021-24 REG
    # Derivation: plays = pass + run plays per game; drives = max(fixed_drive) per game;
    # punts = count of play_type == 'punt' per game
    real_rows = []
    for s in [2021, 2022, 2023, 2024]:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        for gid, gdf in df.groupby("game_id"):
            wk = int(gdf["week"].iloc[0])
            scrim = gdf[gdf["play_type"].isin(["pass", "run"])]
            punts = (gdf["play_type"] == "punt").sum()
            drives = gdf["fixed_drive"].max() if "fixed_drive" in gdf.columns else 0
            real_rows.append({"game_id": gid, "season": s, "week": wk,
                              "real_plays": len(scrim), "real_punts": punts,
                              "real_drives": drives})
    real = pd.DataFrame(real_rows)

    # Merge K1 with real
    k1m = k1.merge(real, on=["game_id", "season", "week"], how="left")

    print(f"{'bucket':>8s} {'n':>5s} {'sim_plays':>10s} {'real_plays':>11s} {'diff':>6s} "
          f"{'sim_drives':>11s} {'real_drives':>12s} {'sim_punts':>10s} {'real_punts':>11s}")
    print("-" * 100)

    for label, wrange in [("1-2", [1, 2]), ("3-4", [3, 4]),
                           ("5-8", list(range(5, 9))), ("9+", list(range(9, 23)))]:
        sub = k1m[k1m["week"].isin(wrange)]
        if len(sub) == 0:
            continue
        print(f"{label:>8s} {len(sub):5d} {sub['plays'].mean():10.1f} {sub['real_plays'].mean():11.1f} "
              f"{sub['plays'].mean() - sub['real_plays'].mean():+6.1f} "
              f"{sub['drives'].mean():11.1f} {sub['real_drives'].mean():12.1f} "
              f"{sub['ev_punts'].mean():10.1f} {sub['real_punts'].mean():11.1f}")

    all_k1 = k1m
    print(f"{'ALL':>8s} {len(all_k1):5d} {all_k1['plays'].mean():10.1f} {all_k1['real_plays'].mean():11.1f} "
          f"{all_k1['plays'].mean() - all_k1['real_plays'].mean():+6.1f} "
          f"{all_k1['drives'].mean():11.1f} {all_k1['real_drives'].mean():12.1f} "
          f"{all_k1['ev_punts'].mean():10.1f} {all_k1['real_punts'].mean():11.1f}")

    print(f"\nFingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
