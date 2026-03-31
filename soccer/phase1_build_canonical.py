#!/usr/bin/env python3
"""
Phase 1: Build Soccer Canonical Game Table.

Fetches all EPL + Bundesliga seasons from football-data.co.uk,
assembles the canonical table, runs audit gates, and saves to
soccer/data/soccer_canonical.parquet.

Usage:
    python3 -m soccer.phase1_build_canonical          # full rebuild
    python3 -m soccer.phase1_build_canonical --fresh  # force re-download

Audit gates (all must pass before table is considered Phase 1 complete):
    1. Row counts per league per season ≥ minimums
    2. Null score rate < 1%
    3. Shot coverage > 90%
    4. Market coverage > 80%  [xG = PENDING — documented]
    5. game_id uniqueness: 0 duplicates
    6. game_date parse success rate > 99%
    7. Score sanity: home_score + away_score == regulation_total_90

Exits with code 1 if any audit gate fails.
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

from soccer.config import (
    ALL_SEASONS,
    AUDIT_MAX_NULL_SCORE_RATE,
    AUDIT_MIN_BUN_ROWS_PER_SEASON,
    AUDIT_MIN_EPL_ROWS_PER_SEASON,
    AUDIT_MIN_MARKET_COVERAGE,
    AUDIT_MIN_SHOTS_COVERAGE,
    CANONICAL_COLUMNS,
    CANONICAL_PATH,
    DATA_DIR,
    LEAGUES,
    SEASON_LABELS,
    VALIDATE_SEASON,
    OOS_SEASON,
    TRAIN_SEASONS,
)
from soccer.modules.fetch_football_data import fetch_all_seasons

logger = logging.getLogger(__name__)

SEP  = "═" * 72
SEP2 = "─" * 72


# ── Audit gates ───────────────────────────────────────────────────────────────

def run_audit(df: pd.DataFrame) -> bool:
    """
    Run all Phase 1 audit gates. Prints a report.
    Returns True if all gates pass.
    """
    failures = []

    print(f"\n{SEP}")
    print("  SOCCER PHASE 1 AUDIT REPORT")
    print(SEP)
    print(f"  Total rows: {len(df):,}")
    print(f"  Leagues:    {sorted(df['league_id'].unique())}")
    print(f"  Seasons:    {sorted(df['season_year'].unique())}")
    print()

    # ── Gate 1: Row counts per league per season ──────────────────────────────
    print("  Gate 1: Row counts per league × season")
    print(f"  {SEP2[:60]}")
    g1_pass = True
    for lid in sorted(df["league_id"].unique()):
        min_rows = (
            AUDIT_MIN_EPL_ROWS_PER_SEASON if lid == "EPL"
            else AUDIT_MIN_BUN_ROWS_PER_SEASON
        )
        for season in sorted(df[df["league_id"] == lid]["season_year"].unique()):
            n = len(df[(df["league_id"] == lid) & (df["season_year"] == season)])
            ok = "✓" if n >= min_rows else "✗"
            if n < min_rows:
                g1_pass = False
                failures.append(f"Gate 1: {lid} {season} has {n} rows (min {min_rows})")
            print(f"    {ok} {lid} {season:<10} {n:>4} rows  (min {min_rows})")
    print()

    # ── Gate 2: Null score rate ───────────────────────────────────────────────
    null_scores = df["home_score"].isna() | df["away_score"].isna()
    null_rate = null_scores.mean()
    g2_pass = null_rate <= AUDIT_MAX_NULL_SCORE_RATE
    ok2 = "✓" if g2_pass else "✗"
    print(f"  Gate 2: Null score rate    {ok2}  {null_rate:.3%} (max {AUDIT_MAX_NULL_SCORE_RATE:.0%})")
    if not g2_pass:
        failures.append(f"Gate 2: null score rate {null_rate:.3%} exceeds {AUDIT_MAX_NULL_SCORE_RATE:.0%}")

    # ── Gate 3: Shot coverage ─────────────────────────────────────────────────
    has_shots = (
        df["home_shots"].notna() &
        df["away_shots"].notna() &
        df["home_shots_on_target"].notna() &
        df["away_shots_on_target"].notna()
    )
    shot_cov = has_shots.mean()
    g3_pass = shot_cov >= AUDIT_MIN_SHOTS_COVERAGE
    ok3 = "✓" if g3_pass else "✗"
    print(f"  Gate 3: Shot coverage      {ok3}  {shot_cov:.1%} (min {AUDIT_MIN_SHOTS_COVERAGE:.0%})")
    if not g3_pass:
        failures.append(f"Gate 3: shot coverage {shot_cov:.1%} < {AUDIT_MIN_SHOTS_COVERAGE:.0%}")

    # ── Gate 4: Market coverage (B365>2.5 / B365<2.5) ─────────────────────────
    mkt_cov = df["market_available"].mean() if "market_available" in df.columns else 0.0
    g4_pass = mkt_cov >= AUDIT_MIN_MARKET_COVERAGE
    ok4 = "✓" if g4_pass else "✗"
    print(f"  Gate 4: Market coverage    {ok4}  {mkt_cov:.1%} (min {AUDIT_MIN_MARKET_COVERAGE:.0%})")
    if not g4_pass:
        failures.append(f"Gate 4: market coverage {mkt_cov:.1%} < {AUDIT_MIN_MARKET_COVERAGE:.0%}")

    # xG coverage (documented as PENDING — not a blocking gate in Phase 1)
    xg_cov = df["home_xg_raw"].notna().mean()
    print(f"  Gate 4x: xG coverage       ⚠  {xg_cov:.1%}  PENDING — requires API-Football backfill")

    # ── Gate 5: game_id uniqueness ────────────────────────────────────────────
    n_dups = df["game_id"].duplicated().sum()
    g5_pass = n_dups == 0
    ok5 = "✓" if g5_pass else "✗"
    print(f"  Gate 5: game_id duplicates {ok5}  {n_dups} (must be 0)")
    if not g5_pass:
        failures.append(f"Gate 5: {n_dups} duplicate game_ids")

    # ── Gate 6: game_date parse rate ─────────────────────────────────────────
    bad_dates = (df["game_date"] == "NaT") | df["game_date"].isna()
    date_fail_rate = bad_dates.mean()
    g6_pass = date_fail_rate < 0.01
    ok6 = "✓" if g6_pass else "✗"
    print(f"  Gate 6: Date parse failures{ok6}  {bad_dates.sum()} rows ({date_fail_rate:.3%})")
    if not g6_pass:
        failures.append(f"Gate 6: {bad_dates.sum()} date parse failures ({date_fail_rate:.3%})")

    # ── Gate 7: Score sanity ──────────────────────────────────────────────────
    score_sum = df["home_score"] + df["away_score"]
    mismatch = (score_sum != df["regulation_total_90"]).sum()
    g7_pass = mismatch == 0
    ok7 = "✓" if g7_pass else "✗"
    print(f"  Gate 7: regulation_total_90{ok7}  {mismatch} mismatches (must be 0)")
    if not g7_pass:
        failures.append(f"Gate 7: {mismatch} regulation_total_90 mismatches")

    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    all_pass = len(failures) == 0
    if all_pass:
        print(f"  ✓ All gates passed. Phase 1 canonical table is valid.")
    else:
        print(f"  ✗ {len(failures)} gate(s) FAILED:")
        for f in failures:
            print(f"      • {f}")
    print()

    # ── Split summary ─────────────────────────────────────────────────────────
    print(f"  Split summary:")
    train_label = f"{SEASON_LABELS[TRAIN_SEASONS[0]]}–{SEASON_LABELS[TRAIN_SEASONS[-1]]}"
    val_label   = SEASON_LABELS[VALIDATE_SEASON]
    oos_label   = SEASON_LABELS[OOS_SEASON]

    train_seasons_set = {SEASON_LABELS[s] for s in TRAIN_SEASONS}
    n_train = len(df[df["season_year"].isin(train_seasons_set)])
    n_val   = len(df[df["season_year"] == val_label])
    n_oos   = len(df[df["season_year"] == oos_label])

    print(f"    Train   ({train_label}): {n_train:>5} rows")
    print(f"    Validate ({val_label}):  {n_val:>5} rows")
    n_oos_label = f"2024-25 (OOS — partial as of 2026-03-16)" if n_oos < 380 else f"2024-25 full season"
    print(f"    OOS      ({n_oos_label}): {n_oos:>5} rows")
    print()

    return all_pass


# ── Assemble canonical table ──────────────────────────────────────────────────

def build_canonical(force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch all seasons, normalise to canonical schema, run audit, save parquet.
    Returns the canonical DataFrame.
    """
    logger.info("Fetching all seasons from football-data.co.uk...")
    df = fetch_all_seasons(force_refresh=force_refresh)

    if df.empty:
        logger.error("No data fetched — cannot build canonical table")
        return df

    # Ensure all canonical columns exist (fill missing with None)
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Cast bool columns
    df["went_to_et"]        = df["went_to_et"].astype(bool)
    df["went_to_penalties"] = df["went_to_penalties"].astype(bool)
    df["market_available"]  = df["market_available"].fillna(False).astype(bool)

    # Reorder to canonical column order
    df = df[CANONICAL_COLUMNS].copy()

    logger.info(f"Canonical table: {len(df):,} rows, {len(df.columns)} columns")

    return df


def save_canonical(df: pd.DataFrame) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_parquet(CANONICAL_PATH, index=False)
    logger.info(f"Saved canonical table → {CANONICAL_PATH}")


# ── Print sample rows ─────────────────────────────────────────────────────────

def print_sample(df: pd.DataFrame, n: int = 5) -> None:
    print(f"\n  Sample rows (first {n} EPL 2024-25):")
    sample = df[(df["league_id"] == "EPL") & (df["season_year"] == "2024-25")].head(n)
    if sample.empty:
        sample = df.head(n)
    display_cols = [
        "game_date", "league_id", "home_team", "away_team",
        "home_score", "away_score", "regulation_total_90",
        "home_shots", "closing_total_line", "market_available",
    ]
    print(sample[[c for c in display_cols if c in sample.columns]].to_string(index=False))
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 1: Build soccer canonical table")
    parser.add_argument("--fresh", action="store_true", help="Force re-download (ignore cache)")
    args = parser.parse_args()

    df = build_canonical(force_refresh=args.fresh)
    if df.empty:
        sys.exit(1)

    audit_passed = run_audit(df)
    print_sample(df)

    save_canonical(df)

    if not audit_passed:
        logger.error("Audit gates failed — canonical table saved but marked INVALID")
        sys.exit(1)

    print(f"  Canonical table saved: {CANONICAL_PATH}")
    print(f"  Rows: {len(df):,}  Columns: {len(df.columns)}\n")


if __name__ == "__main__":
    main()
