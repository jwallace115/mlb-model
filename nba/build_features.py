#!/usr/bin/env python3
"""
Phase 2 — Build NBA feature table and show distributions + correlations.

Usage:
    python nba/build_features.py                   # build all (uses cache)
    python nba/build_features.py --force-refresh   # rebuild from scratch
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd

from nba.config import ALL_HISTORICAL_SEASONS, BOX_STATS_PATH
from nba.modules.fetch_box_stats import build_box_stats_table
from nba.modules.features import build_features


def show_distributions(feat: pd.DataFrame) -> None:
    print("\n" + "═" * 65)
    print("  PHASE 2 — FEATURE DISTRIBUTIONS")
    print("═" * 65)

    num_cols = [
        "home_ortg", "away_ortg", "home_drtg", "away_drtg",
        "home_pace", "away_pace",
        "days_rest_home", "days_rest_away",
        "b2b_flag_home", "b2b_flag_away",
        "games_l7_home", "games_l7_away",
        "home_games_in_season", "away_games_in_season",
        "proj_total_naive", "actual_total",
    ]

    print(f"\n{'Feature':<25} {'mean':>7} {'std':>7} {'p10':>7} {'p50':>7} {'p90':>7} {'nulls':>6}")
    print("-" * 65)
    for col in num_cols:
        if col not in feat.columns:
            continue
        s = feat[col].dropna()
        print(
            f"{col:<25} "
            f"{s.mean():>7.2f} "
            f"{s.std():>7.2f} "
            f"{s.quantile(0.10):>7.2f} "
            f"{s.quantile(0.50):>7.2f} "
            f"{s.quantile(0.90):>7.2f} "
            f"{feat[col].isna().sum():>6}"
        )

    print("\n📊 Fallback level distribution (home ORtg, by season):")
    for season in sorted(feat["season"].unique()):
        sub = feat[feat["season"] == season]
        counts = sub["home_ortg_fb"].value_counts()
        total  = len(sub)
        parts  = [f"{lvl}={n}({n*100//total}%)" for lvl, n in counts.items()]
        print(f"   {season}: {', '.join(parts)}")

    print("\n📊 Back-to-back rates:")
    print(f"   Home B2B: {feat['b2b_flag_home'].mean()*100:.1f}%")
    print(f"   Away B2B: {feat['b2b_flag_away'].mean()*100:.1f}%")
    print(f"   Both B2B: {(feat['b2b_flag_home'] & feat['b2b_flag_away']).mean()*100:.1f}%")


def show_correlations(feat: pd.DataFrame) -> None:
    print("\n" + "═" * 65)
    print("  FEATURE CORRELATIONS WITH actual_total")
    print("═" * 65)

    feature_cols = [
        "home_ortg", "away_ortg", "home_drtg", "away_drtg",
        "home_pace", "away_pace",
        "days_rest_home", "days_rest_away",
        "b2b_flag_home", "b2b_flag_away",
        "games_l7_home", "games_l7_away",
        "proj_total_naive",
    ]

    corrs = []
    for col in feature_cols:
        if col not in feat.columns:
            continue
        c = feat[["actual_total", col]].dropna().corr().iloc[0, 1]
        corrs.append((col, c))

    corrs.sort(key=lambda x: abs(x[1]), reverse=True)
    print(f"\n{'Feature':<25} {'Pearson r':>10}  {'direction':>10}")
    print("-" * 50)
    for col, r in corrs:
        direction = "↑ OVER" if r > 0 else "↓ UNDER"
        star = "**" if abs(r) >= 0.30 else "*" if abs(r) >= 0.15 else "  "
        print(f"{col:<25} {r:>10.4f}  {direction:>10} {star}")

    print("\n  ** = strong signal (|r| ≥ 0.30)  * = moderate (|r| ≥ 0.15)")

    # Naive projection MAE
    clean = feat.dropna(subset=["proj_total_naive", "actual_total"])
    mae   = (clean["proj_total_naive"] - clean["actual_total"]).abs().mean()
    bias  = (clean["proj_total_naive"] - clean["actual_total"]).mean()
    print(f"\n📈 proj_total_naive vs actual_total:")
    print(f"   MAE  = {mae:.2f} pts   (Phase 3 Ridge target: < 11)")
    print(f"   Bias = {bias:+.2f} pts  (+ means naive over-projects)")

    # By season
    print(f"\n   By season:")
    for season in sorted(clean["season"].unique()):
        sub  = clean[clean["season"] == season]
        smae = (sub["proj_total_naive"] - sub["actual_total"]).abs().mean()
        print(f"   {season}: MAE={smae:.2f} (n={len(sub)})")

    print()


def main():
    parser = argparse.ArgumentParser(description="Build NBA feature table (Phase 2)")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Rebuild box stats and features from scratch")
    args = parser.parse_args()

    # Step 1: Box stats
    print(f"\nStep 1/2 — Building box stats for {ALL_HISTORICAL_SEASONS} …")
    box = build_box_stats_table(force_refresh=args.force_refresh)
    print(f"  Box stats: {len(box)} team-game rows")

    # Step 2: Features
    print("\nStep 2/2 — Building feature table …")
    if args.force_refresh and os.path.exists(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "features.parquet")
    ):
        os.remove(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "features.parquet")
        )
    feat = build_features(force_refresh=args.force_refresh)
    print(f"  Features: {len(feat)} game rows, {feat.shape[1]} columns")

    show_distributions(feat)
    show_correlations(feat)


if __name__ == "__main__":
    main()
