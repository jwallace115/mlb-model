#!/usr/bin/env python3
"""
Phase 5A-5 STEP 4: Conditional drive analysis from PBP 2021-2024.
Builds actual-side tables for comparison with sim drive log.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]


def load_pbp():
    frames = []
    for s in SEASONS:
        frames.append(pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet"))
    return pd.concat(frames, ignore_index=True).query("week <= 18").copy()


def build_actual_drives(df):
    """Build drive-level table from PBP including kneels."""
    scrim = df[df["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])].copy()
    drives = scrim.groupby(["game_id", "fixed_drive"]).agg(
        posteam=("posteam", "first"),
        start_yl=("yardline_100", "first"),
        start_qtr=("qtr", "first"),
        plays=("play_id", "size"),
        yards=("yards_gained", "sum"),
        result=("fixed_drive_result", "last"),
        season=("season", "first"),
        score_diff=("score_differential", "first"),
    ).reset_index()
    return drives


def _start_bucket(yl):
    """Bucket yardline for drive-start analysis."""
    if yl <= 20: return "opp_rz"
    elif yl <= 40: return "opp_40"
    elif yl <= 60: return "midfield"
    elif yl <= 80: return "own_40"
    else: return "own_20"


def _score_state(sd):
    if sd <= -9: return "trail9+"
    elif sd <= -1: return "trail1-8"
    elif sd == 0: return "tied"
    elif sd <= 8: return "lead1-8"
    else: return "lead9+"


def step4_actual(df):
    """Conditional drive analysis tables from PBP."""
    drives = build_actual_drives(df)
    n_games = df["game_id"].nunique()
    print(f"\n{'='*70}")
    print(f"STEP 4 ACTUAL: Conditional Drive Analysis (2021-2024)")
    print(f"Drives: {len(drives)}, Games: {n_games}")
    print(f"{'='*70}")

    drives["start_bucket"] = drives["start_yl"].apply(_start_bucket)
    drives["score_state"] = drives["score_diff"].apply(_score_state)

    # 4a: yards per drive and result distribution by start_bucket × score_state
    print(f"\n--- 4a: Yards/drive and result by start_bucket × score_state ---")
    for ss in ["trail9+", "trail1-8", "tied", "lead1-8", "lead9+"]:
        grp = drives[drives["score_state"] == ss]
        print(f"\n  {ss} ({len(grp)} drives):")
        for sb in ["own_20", "own_40", "midfield", "opp_40", "opp_rz"]:
            sub = grp[grp["start_bucket"] == sb]
            if len(sub) < 20: continue
            td_rate = (sub["result"] == "Touchdown").mean()
            fg_rate = (sub["result"] == "Field goal").mean()
            punt_rate = (sub["result"] == "Punt").mean()
            yds = sub["yards"].mean()
            print(f"    {sb:12s}: n={len(sub):5d} yds={yds:5.1f} TD={td_rate:.3f} FG={fg_rate:.3f} punt={punt_rate:.3f}")

    # 4c: Where long-field drives END (own 1-40 starts)
    print(f"\n--- 4c: Where drives starting own_1-40 END ---")
    long = drives[drives["start_yl"] > 60].copy()  # own 1-40 = yl 61-99
    print(f"  Drives starting own 1-40 (yl > 60): {len(long)}")

    # End yardline from PBP — use the last play's yardline_100
    scrim = df[df["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])].copy()
    drive_ends = scrim.groupby(["game_id", "fixed_drive"]).agg(
        end_yl=("yardline_100", "last"),
        end_down=("down", "last"),
        end_dist=("ydstogo", "last"),
        result=("fixed_drive_result", "last"),
    ).reset_index()

    long_merged = long.merge(drive_ends[["game_id", "fixed_drive", "end_yl", "end_down", "end_dist"]],
                              on=["game_id", "fixed_drive"], how="left")

    # Distribution of end yardline by result
    for result in ["Touchdown", "Field goal", "Punt", "Turnover", "Turnover on downs"]:
        sub = long_merged[long_merged["result"] == result]
        if len(sub) < 10: continue
        print(f"\n  Result: {result} (n={len(sub)})")
        print(f"    End yl: mean={sub['end_yl'].mean():.1f} p25={sub['end_yl'].quantile(0.25):.0f} p50={sub['end_yl'].median():.0f} p75={sub['end_yl'].quantile(0.75):.0f}")
        if result in ["Punt", "Turnover on downs"]:
            # Bucket the end yardline
            for lo, hi, label in [(1, 20, "opp_rz"), (21, 40, "opp_40"), (41, 60, "midfield"), (61, 80, "own_40"), (81, 99, "own_20")]:
                ct = len(sub[(sub["end_yl"] >= lo) & (sub["end_yl"] <= hi)])
                print(f"      {label}: {ct} ({ct/len(sub)*100:.1f}%)")

    # 4d: Plays per first down and yards by down
    print(f"\n--- 4d: Yards by down (all scrimmage plays) ---")
    scrim_plays = df[df["play_type"].isin(["pass", "run"])].copy()
    for d in [1, 2, 3, 4]:
        dp = scrim_plays[scrim_plays["down"] == d]
        yds = dp["yards_gained"].mean()
        n = len(dp)
        sr = (dp["yards_gained"] >= dp["ydstogo"]).mean() if d < 4 else 0
        print(f"  Down {d}: n={n:6d} mean_yds={yds:5.2f} conversion_rate={sr:.3f}")

    # Series conversion rate by start yardline bucket
    print(f"\n--- 4b: Series conversion rate by start yardline ---")
    # A series = a set of downs. New first down or TD = conversion.
    # first_down == 1 or touchdown == 1 on any play in the series
    # Approximate: count first_down events per drive
    scrim_plays["first_down_any"] = (scrim_plays["first_down"] == 1) | (scrim_plays["touchdown"] == 1)
    fd_per_drive = scrim_plays.groupby(["game_id", "fixed_drive"]).agg(
        n_first_downs=("first_down_any", "sum"),
        n_plays=("play_id", "size"),
        start_yl=("yardline_100", "first"),
    ).reset_index()
    fd_per_drive["start_bucket"] = fd_per_drive["start_yl"].apply(_start_bucket)
    fd_per_drive["plays_per_fd"] = fd_per_drive["n_plays"] / fd_per_drive["n_first_downs"].clip(1)

    for sb in ["own_20", "own_40", "midfield", "opp_40", "opp_rz"]:
        sub = fd_per_drive[fd_per_drive["start_bucket"] == sb]
        print(f"  {sb:12s}: n={len(sub):5d} mean_FD/drive={sub['n_first_downs'].mean():.2f} "
              f"plays/FD={sub['plays_per_fd'].mean():.2f}")


if __name__ == "__main__":
    print("Loading PBP data...")
    df = load_pbp()
    print(f"Loaded {len(df):,} plays")
    step4_actual(df)
