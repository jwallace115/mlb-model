"""
V2.1 Feature Table Builder.

Steps:
  1. Build lineup features from lineups_raw.parquet + cached JSONs
  2. Run leakage audit
  3. Merge lineup features with existing soccer_feature_table.parquet
  4. Save soccer_feature_table_v2_1.parquet (original untouched)

Usage:
  python3 -m soccer.phase_v2_1_feature_table
"""

import logging
import os
import sys

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(BASE_DIR, "data")
CACHE_DIR      = os.path.join(DATA_DIR, "cache", "api_football")

CANONICAL_PATH  = os.path.join(DATA_DIR, "soccer_canonical.parquet")
LINEUPS_PATH    = os.path.join(DATA_DIR, "lineups_raw.parquet")
CROSSWALK_PATH  = os.path.join(DATA_DIR, "api_football_crosswalk.parquet")
FEATURE_V1_PATH = os.path.join(DATA_DIR, "soccer_feature_table.parquet")
FEATURE_V21_PATH = os.path.join(DATA_DIR, "soccer_feature_table_v2_1.parquet")


def main():
    SEP = "═" * 72

    print(f"\n{SEP}")
    print("  PHASE V2.1 — LINEUP FEATURE TABLE BUILD")
    print(SEP)

    # ── Step 1: Build lineup features ─────────────────────────────────────────
    print("\n  Step 1: Building lineup features...")
    from soccer.modules.build_lineup_features import (
        build_lineup_features,
        run_leakage_audit,
        LINEUP_FEATURE_COLS,
    )

    lineup_feats = build_lineup_features(
        canonical_path  = CANONICAL_PATH,
        lineups_path    = LINEUPS_PATH,
        cache_dir       = CACHE_DIR,
        crosswalk_path  = CROSSWALK_PATH,
    )
    print(f"  Lineup features built: {len(lineup_feats):,} rows × {len(lineup_feats.columns)} columns")

    # ── Step 2: Leakage audit ──────────────────────────────────────────────────
    print("\n  Step 2: Running leakage audit...")
    canonical = pd.read_parquet(CANONICAL_PATH)
    lineups_raw = pd.read_parquet(LINEUPS_PATH)
    run_leakage_audit(lineup_feats, lineups_raw, canonical)

    # ── Step 3: Merge with V1 feature table ────────────────────────────────────
    print("\n  Step 3: Merging with soccer_feature_table.parquet...")
    feat_v1 = pd.read_parquet(FEATURE_V1_PATH)
    print(f"  V1 feature table: {len(feat_v1):,} rows × {len(feat_v1.columns)} columns")

    # Only keep the lineup feature columns (plus game_id) for merge
    available_lineup_cols = [c for c in LINEUP_FEATURE_COLS if c in lineup_feats.columns]
    missing_lineup_cols   = [c for c in LINEUP_FEATURE_COLS if c not in lineup_feats.columns]

    if missing_lineup_cols:
        print(f"  WARNING: {len(missing_lineup_cols)} lineup cols not found: {missing_lineup_cols}")

    lineup_merge = lineup_feats[["game_id"] + available_lineup_cols].drop_duplicates("game_id")

    # Drop any lineup cols that already exist in V1 (avoid _x/_y conflicts)
    existing_in_v1 = [c for c in available_lineup_cols if c in feat_v1.columns]
    if existing_in_v1:
        print(f"  Dropping {len(existing_in_v1)} cols from V1 (will overwrite): {existing_in_v1}")
        feat_v1 = feat_v1.drop(columns=existing_in_v1)

    feat_v21 = feat_v1.merge(lineup_merge, on="game_id", how="left")
    print(f"  V2.1 feature table: {len(feat_v21):,} rows × {len(feat_v21.columns)} columns")

    # ── Coverage check ─────────────────────────────────────────────────────────
    print("\n  Coverage check:")
    for col in available_lineup_cols:
        null_pct = feat_v21[col].isna().mean() * 100
        flag = "  " if null_pct < 30 else ("⚠ " if null_pct < 50 else "✗ ")
        print(f"    {flag}{col:<45} {null_pct:>6.2f}% null")

    # ── New columns added ──────────────────────────────────────────────────────
    new_cols = [c for c in feat_v21.columns if c not in feat_v1.columns or c in available_lineup_cols]
    print(f"\n  New columns added to V2.1: {len(available_lineup_cols)}")
    for c in available_lineup_cols:
        print(f"    + {c}")

    # ── Step 4: Save ───────────────────────────────────────────────────────────
    print(f"\n  Step 4: Saving → {FEATURE_V21_PATH}")
    feat_v21.to_parquet(FEATURE_V21_PATH, index=False)
    print(f"  Saved: {len(feat_v21):,} rows × {len(feat_v21.columns)} columns")
    print(f"  Original soccer_feature_table.parquet untouched.")

    print(f"\n{SEP}")
    print("  V2.1 feature table complete.")
    print(f"{SEP}\n")


if __name__ == "__main__":
    main()
