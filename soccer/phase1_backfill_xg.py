#!/usr/bin/env python3
"""
Phase 1 xG Backfill.

Fetches match-level xG from Understat for all EPL + Bundesliga seasons,
joins to the canonical table on (league_id, game_date, home_team, away_team),
updates home_xg_raw, away_xg_raw, and xg_source in place, then saves.

Join strategy:
  Primary key:  league_id + game_date + home_team + away_team
  Crosswalk:    Understat team names → football-data.co.uk names (in fetch_xg.py)

Reports:
  - xG coverage by league × season
  - Unmatched rows (canonical rows where xG join failed)
  - Gate 4x: overall xG coverage ≥ 70% required

Usage:
    python3 -m soccer.phase1_backfill_xg
    python3 -m soccer.phase1_backfill_xg --fresh   # re-download from Understat
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

import pandas as pd

from soccer.config import (
    CANONICAL_PATH,
    LEAGUES,
    ALL_SEASONS,
)
from soccer.modules.fetch_xg import fetch_xg_all

logger = logging.getLogger(__name__)

SEP  = "═" * 72
SEP2 = "─" * 72

XG_COVERAGE_GATE = 0.70   # Gate 4x threshold


def backfill_xg(force_refresh: bool = False) -> pd.DataFrame:
    """
    Load canonical, fetch all xG, merge, save. Returns updated canonical.
    """
    # ── Load canonical ────────────────────────────────────────────────────────
    if not os.path.exists(CANONICAL_PATH):
        logger.error(f"Canonical table not found: {CANONICAL_PATH}")
        sys.exit(1)

    canonical = pd.read_parquet(CANONICAL_PATH)
    logger.info(f"Loaded canonical: {len(canonical):,} rows")

    # ── Fetch all xG ─────────────────────────────────────────────────────────
    logger.info("Fetching xG from Understat (all leagues × seasons)...")
    xg_df = fetch_xg_all(force_refresh=force_refresh)
    logger.info(f"xG DataFrame: {len(xg_df):,} rows")

    if xg_df.empty:
        logger.error("No xG data returned — aborting backfill")
        sys.exit(1)

    # ── Merge ─────────────────────────────────────────────────────────────────
    # Join key: league_id + season_year + game_date + home_team + away_team
    xg_df = xg_df.rename(columns={
        "home_team_fd": "home_team",
        "away_team_fd": "away_team",
    })

    merged = canonical.merge(
        xg_df[["league_id", "season_year", "game_date", "home_team", "away_team",
               "home_xg_raw", "away_xg_raw"]],
        on=["league_id", "season_year", "game_date", "home_team", "away_team"],
        how="left",
        suffixes=("_old", "_new"),
    )

    # Use new xG values where available, fall back to old (None)
    if "home_xg_raw_new" in merged.columns:
        merged["home_xg_raw"] = merged["home_xg_raw_new"].combine_first(merged["home_xg_raw_old"])
        merged["away_xg_raw"] = merged["away_xg_raw_new"].combine_first(merged["away_xg_raw_old"])
        merged = merged.drop(columns=["home_xg_raw_old", "away_xg_raw_old",
                                       "home_xg_raw_new", "away_xg_raw_new"])
    # else: no collision (canonical had nulls), home/away_xg_raw already filled

    # Set xg_source
    xg_filled = merged["home_xg_raw"].notna()
    merged.loc[xg_filled, "xg_source"] = "understat"

    # Restore canonical column order
    from soccer.config import CANONICAL_COLUMNS
    merged = merged[CANONICAL_COLUMNS]

    return merged


def print_coverage_report(df: pd.DataFrame) -> bool:
    """
    Print xG coverage by league × season. Returns True if Gate 4x passes.
    """
    print(f"\n{SEP}")
    print("  xG COVERAGE REPORT — Phase 1 Gate 4x")
    print(SEP)

    gate_pass = True
    rows_below = []

    print(f"  {'League':<8} {'Season':<12} {'Rows':>6} {'xG filled':>10} {'Coverage':>10}")
    print(f"  {SEP2[:60]}")

    for (league, season), grp in df.groupby(["league_id", "season_year"]):
        n     = len(grp)
        filled = grp["home_xg_raw"].notna().sum()
        cov    = filled / n if n > 0 else 0.0
        ok     = "✓" if cov >= XG_COVERAGE_GATE else "✗"
        print(f"  {ok} {league:<8} {season:<12} {n:>6} {filled:>10} {cov:>9.1%}")
        if cov < XG_COVERAGE_GATE:
            gate_pass = False
            rows_below.append(f"{league} {season}: {cov:.1%}")

    # Overall
    n_total = len(df)
    n_filled = df["home_xg_raw"].notna().sum()
    overall_cov = n_filled / n_total if n_total > 0 else 0.0
    ok_overall = "✓" if overall_cov >= XG_COVERAGE_GATE else "✗"

    print(f"  {SEP2[:60]}")
    print(f"  {ok_overall} {'OVERALL':<8} {'(all)':<12} {n_total:>6} {n_filled:>10} {overall_cov:>9.1%}")
    print()

    if not gate_pass:
        print(f"  ✗ Gate 4x FAILED — coverage < {XG_COVERAGE_GATE:.0%} in:")
        for r in rows_below:
            print(f"      • {r}")
    else:
        print(f"  ✓ Gate 4x PASSED — xG coverage ≥ {XG_COVERAGE_GATE:.0%} in all league/seasons")

    # Show unmatched rows (non-trivial mismatches worth investigating)
    unmatched = df[df["home_xg_raw"].isna()]
    if not unmatched.empty:
        print(f"\n  Unmatched rows (no xG join): {len(unmatched)}")
        sample = unmatched[["game_date", "league_id", "season_year",
                             "home_team", "away_team"]].head(20)
        print(sample.to_string(index=False))

    print()
    return gate_pass and (overall_cov >= XG_COVERAGE_GATE)


def main():
    parser = argparse.ArgumentParser(description="Phase 1: Backfill xG into canonical table")
    parser.add_argument("--fresh", action="store_true",
                        help="Force re-download from Understat (ignore cache)")
    args = parser.parse_args()

    updated = backfill_xg(force_refresh=args.fresh)

    gate_pass = print_coverage_report(updated)

    # Save regardless — document any gaps
    updated.to_parquet(CANONICAL_PATH, index=False)
    logger.info(f"Canonical table updated with xG → {CANONICAL_PATH}")
    print(f"  Saved: {CANONICAL_PATH}  ({len(updated):,} rows, {len(updated.columns)} columns)\n")

    if not gate_pass:
        logger.error("Gate 4x failed — xG coverage below threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()
