#!/usr/bin/env python3
"""
MLB Totals P1 — FG/F5 Path Mismatch Engine
Full research pipeline: Phases 1-11
"""
import pandas as pd
import numpy as np
import warnings, os, json
from pathlib import Path

warnings.filterwarnings("ignore")
np.random.seed(42)

OUT = Path("/root/mlb-model/research/recovery/mlb_totals_p1_fg_f5_path_engine")
OUT.mkdir(parents=True, exist_ok=True)

def american_to_decimal(price):
    """Convert American odds to decimal odds."""
    if pd.isna(price): return np.nan
    if price > 0:
        return 1 + price / 100
    else:
        return 1 + 100 / abs(price)

def implied_prob(price):
    """Convert American odds to implied probability (no-vig)."""
    if pd.isna(price): return np.nan
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

# ============================================================
# PHASE 1: Lock Market Inputs
# ============================================================
print("=" * 70)
print("PHASE 1: Lock Market Inputs")
print("=" * 70)

# F5 lines
f5 = pd.read_parquet("/root/mlb-model/mlb_sim_f5/data/f5_lines_historical.parquet")
print(f"F5 raw: {len(f5)} rows, cols: {list(f5.columns)}")

# Check what columns exist for canonical flag
if "is_canonical" in f5.columns:
    f5_canon = f5[f5["is_canonical"] == True][["game_id", "date", "f5_total"]].drop_duplicates(subset=["game_id"])
elif "source" in f5.columns:
    # Try to pick best source
    print(f"F5 sources: {f5['source'].value_counts().to_dict()}")
    f5_canon = f5[["game_id", "date", "f5_total"]].drop_duplicates(subset=["game_id"])
else:
    f5_canon = f5[["game_id", "date", "f5_total"]].drop_duplicates(subset=["game_id"])

print(f"F5 canonical: {len(f5_canon)} games")
print(f"F5 date range: {f5_canon['date'].min()} - {f5_canon['date'].max()}")

# Ensure date is string for year extraction
f5_canon["date_str"] = f5_canon["date"].astype(str)
print(f"F5 by year: {f5_canon['date_str'].str[:4].value_counts().sort_index().to_dict()}")

# Canonical odds (FG total + prices)
canon = pd.read_parquet("/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet")
print(f"\nCanonical odds: {len(canon)} rows, cols: {list(canon.columns)}")

# Find total line column
total_col = None
for c in ["total_line", "total", "closing_total", "fg_total"]:
    if c in canon.columns:
        total_col = c
        break
if total_col is None:
    print("Available columns:", canon.columns.tolist())
print(f"Using total column: {total_col}")
print(f"FG total coverage: {canon[total_col].notna().sum()}")

# Find price columns
over_price_col = under_price_col = None
for c in ["total_over_price", "over_price", "closing_over_price"]:
    if c in canon.columns:
        over_price_col = c
        break
for c in ["total_under_price", "under_price", "closing_under_price"]:
    if c in canon.columns:
        under_price_col = c
        break
print(f"Over price col: {over_price_col}, coverage: {canon[over_price_col].notna().sum() if over_price_col else 'N/A'}")
print(f"Under price col: {under_price_col}, coverage: {canon[under_price_col].notna().sum() if under_price_col else 'N/A'}")

# Game table (actual scores)
gt = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")
print(f"\nGame table: {len(gt)} rows, cols: {list(gt.columns)[:20]}...")
print(f"Game table date range: {gt['date'].min()} - {gt['date'].max()}")

# Check for F5 actual scores
f5_actual_col = None
for c in ["actual_f5_total", "f5_total_actual", "f5_runs", "home_f5_runs", "actual_home_f5"]:
    if c in gt.columns:
        f5_actual_col = c
        print(f"Found F5 actual col: {c}, coverage: {gt[c].notna().sum()}")
        break

# Check if we have inning-by-inning or half-game data
inning_cols = [c for c in gt.columns if "inning" in c.lower() or "f5" in c.lower() or "linescore" in c.lower()]
print(f"Inning-related columns: {inning_cols}")

# Check for home/away run columns
for c in gt.columns:
    if "run" in c.lower() or "score" in c.lower() or "total" in c.lower():
        print(f"  Score col: {c} — coverage: {gt[c].notna().sum()}")

# ============================================================
# PHASE 1b: Build actual F5 runs if not available
# ============================================================
# We need actual_f5_total. Check pitcher_game_logs for inning data
print("\n--- Checking pitcher game logs for F5 reconstruction ---")
pgl = pd.read_parquet("/root/mlb-model/mlb/data/pitcher_game_logs.parquet")
print(f"Pitcher game logs: {len(pgl)} rows")
print(f"Columns: {list(pgl.columns)[:30]}")

# Check for linescore or inning data in game_table more carefully
print(f"\nAll game_table columns:\n{gt.columns.tolist()}")

# ============================================================
# PHASE 1c: Try to get F5 actual from linescore API data or other sources
# ============================================================
# Check if actual_f5_total can be derived
has_f5_actual = False
if "home_f5_score" in gt.columns and "away_f5_score" in gt.columns:
    gt["actual_f5_total"] = gt["home_f5_score"] + gt["away_f5_score"]
    has_f5_actual = True
elif "actual_f5_total" in gt.columns:
    has_f5_actual = gt["actual_f5_total"].notna().sum() > 1000

# If not available, check the f5 data itself
if not has_f5_actual:
    print("\nChecking F5 lines file for actual scores...")
    f5_all_cols = f5.columns.tolist()
    print(f"F5 file columns: {f5_all_cols}")
    for c in f5.columns:
        if "actual" in c.lower() or "result" in c.lower() or "score" in c.lower():
            print(f"  Potential actual col: {c} — coverage: {f5[c].notna().sum()}")

# Check sim inputs for F5 actuals
print("\nChecking sim inputs...")
try:
    si = pd.read_parquet("/root/mlb-model/mlb_sim/data/sim_inputs_historical_2022_2024.parquet")
    print(f"Sim inputs: {len(si)}, cols: {list(si.columns)[:30]}")
    for c in si.columns:
        if "f5" in c.lower():
            print(f"  F5 col in sim_inputs: {c}")
except Exception as e:
    print(f"  Error: {e}")

print("\n--- Phase 1 data audit complete ---")
