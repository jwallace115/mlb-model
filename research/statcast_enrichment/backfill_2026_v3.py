#!/usr/bin/env python3
"""
2026 Statcast Backfill v3 — APPEND-ONLY to existing parquet.
Strategy: load existing (ground truth), union with 2026 chunk rows, write back.
PIT-SAFE: never touches chunk merging; only appends 2026 rows.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT = Path("/root/mlb-model")
OUT = PROJECT / "research" / "statcast_enrichment"
CHUNKS = OUT / "chunks"

# ── load existing parquet (ground truth) ─────────────────────────────────────
existing = pd.read_parquet(OUT / "pitcher_statcast_per_start.parquet")
pre_by_year = existing["game_date"].astype(str).str[:4].value_counts().sort_index().to_dict()
print(f"PRE-UPDATE rows: {len(existing):,}")
print(f"PRE-UPDATE by year: {pre_by_year}")
pre_total = len(existing)

# ── load all 2026 chunks ──────────────────────────────────────────────────────
chunks_2026 = sorted(CHUNKS.glob("pitcher_statcast_2026_*.parquet"))
print(f"\nFound {len(chunks_2026)} 2026 chunk files:")
rows_2026 = []
for p in chunks_2026:
    df_c = pd.read_parquet(p)
    df_c["game_pk"]    = df_c["game_pk"].astype("int64")
    df_c["pitcher_id"] = df_c["pitcher_id"].astype("int64")
    rows_2026.append(df_c)
    print(f"  {p.name}: {len(df_c)} rows, dates {df_c['game_date'].min()} to {df_c['game_date'].max()}")

if not rows_2026:
    print("ERROR: No 2026 chunk files found. Run backfill script first.")
    sys.exit(1)

df_2026 = pd.concat(rows_2026, ignore_index=True)
df_2026 = df_2026.drop_duplicates(subset=["pitcher_id", "game_date", "game_pk"])
print(f"\n2026 rows (deduplicated): {len(df_2026)}")
print(f"2026 date range: {df_2026['game_date'].min()} to {df_2026['game_date'].max()}")

# ── ensure column alignment before concat ────────────────────────────────────
existing_cols = existing.columns.tolist()
for col in existing_cols:
    if col not in df_2026.columns:
        df_2026[col] = np.nan
df_2026 = df_2026[existing_cols]  # same column order

# ── union: existing (2022-2025) + 2026 ───────────────────────────────────────
merged = pd.concat([existing, df_2026], ignore_index=True)
merged = merged.drop_duplicates(subset=["pitcher_id", "game_date", "game_pk"])

# ── PIT-SAFETY: verify 2022-2025 rows EXACTLY unchanged ──────────────────────
post_by_year = merged["game_date"].astype(str).str[:4].value_counts().sort_index().to_dict()
print(f"\nPOST-UPDATE rows: {len(merged):,}")
print(f"POST-UPDATE by year: {post_by_year}")
print("\nPIT-SAFETY CHECK (2022-2025):")
safe = True
for yr in ["2022", "2023", "2024", "2025"]:
    pre = pre_by_year.get(yr, 0)
    post = post_by_year.get(yr, 0)
    ok = (pre == post)
    status = "OK" if ok else f"CHANGED ({pre} -> {post}) *** HALT ***"
    print(f"  {yr}: {status}")
    if not ok:
        safe = False

if not safe:
    print("\nHARD STOP: 2022-2025 data changed. NOT writing parquet.")
    sys.exit(1)

rows_added = post_by_year.get("2026", 0)
print(f"\n2026 rows added: {rows_added}")
print(f"Total rows before: {pre_total:,}  |  after: {len(merged):,}  |  delta: +{len(merged)-pre_total}")

# ── write updated parquet ─────────────────────────────────────────────────────
out_path = OUT / "pitcher_statcast_per_start.parquet"
merged.to_parquet(out_path, index=False)
print(f"\nWrote: {out_path}")
print("STATUS: SUCCESS")
