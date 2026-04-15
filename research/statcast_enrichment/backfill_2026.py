#!/usr/bin/env python3
"""
2026 Statcast Backfill — per-start pitcher aggregation.
Uses exact same _aggregate_pitcher_start logic as run_enrichment.py.
Pulls: 2026-03-20 through 2026-04-14 in weekly chunks.
Writes new chunk files, then re-merges full pitcher_statcast_per_start.parquet.
PIT-SAFE: never touches 2022-2025 chunk files; only appends to merged parquet.
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT = Path("/root/mlb-model")
OUT = PROJECT / "research" / "statcast_enrichment"
CHUNKS = OUT / "chunks"

# ── record pre-update state ──────────────────────────────────────────────────
existing = pd.read_parquet(OUT / "pitcher_statcast_per_start.parquet")
pre_by_year = existing["game_date"].astype(str).str[:4].value_counts().sort_index().to_dict()
print(f"PRE-UPDATE rows: {len(existing):,}")
print(f"PRE-UPDATE by year: {pre_by_year}")

# ── exact copy of _aggregate_pitcher_start from run_enrichment.py ─────────────
def _aggregate_pitcher_start(chunk_df):
    if chunk_df is None or len(chunk_df) == 0:
        return pd.DataFrame()
    df = chunk_df.copy()
    required = ["pitcher", "game_pk", "game_date", "player_name"]
    for c in required:
        if c not in df.columns:
            print(f"  Missing required column: {c}")
            return pd.DataFrame()

    df["is_bip"] = df["description"].isin([
        "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"
    ]).astype(int)
    df["is_hard_hit"] = ((df["launch_speed"] >= 95) & (df["is_bip"] == 1)).astype(int) if "launch_speed" in df.columns else 0

    if "launch_speed" in df.columns and "launch_angle" in df.columns:
        df["is_barrel"] = (
            (df["launch_speed"] >= 98) &
            (df["launch_angle"] >= max(26, 30 - (df["launch_speed"].clip(upper=116) - 98).clip(lower=0))) &
            (df["launch_angle"] <= min(50, 30 + (df["launch_speed"].clip(upper=116) - 98).clip(lower=0))) &
            (df["is_bip"] == 1)
        ).astype(int)
    else:
        df["is_barrel"] = 0

    df["is_in_zone"] = (df["zone"].between(1, 9)).astype(int) if "zone" in df.columns else np.nan
    df["is_outside_zone"] = (~df["zone"].between(1, 9)).astype(int) if "zone" in df.columns else np.nan
    df["is_swing"] = df["description"].isin([
        "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
        "foul_bunt", "missed_bunt", "hit_into_play", "hit_into_play_no_out",
        "hit_into_play_score"
    ]).astype(int)
    df["is_whiff"] = df["description"].isin(["swinging_strike", "swinging_strike_blocked"]).astype(int)
    df["is_contact"] = (df["is_swing"] == 1) & (df["is_whiff"] == 0)
    df["is_chase"] = ((df["is_outside_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_swing"] = ((df["is_in_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_contact"] = ((df["is_zone_swing"] == 1) & (df["is_contact"] == 1)).astype(int)

    if "release_spin_rate" in df.columns and "pitch_type" in df.columns:
        df["spin_ff"] = np.where(df["pitch_type"].isin(["FF", "SI"]), df["release_spin_rate"], np.nan)
        df["spin_sl"] = np.where(df["pitch_type"].isin(["SL", "ST", "SV"]), df["release_spin_rate"], np.nan)
    else:
        df["spin_ff"] = np.nan
        df["spin_sl"] = np.nan

    for col in ["release_extension", "release_pos_x", "release_pos_z"]:
        if col not in df.columns:
            df[col] = np.nan

    agg = df.groupby(["pitcher", "game_date", "game_pk"]).agg(
        pitcher_name=("player_name", "first"),
        total_pitches=("pitcher", "count"),
        bip=("is_bip", "sum"),
        hard_hits=("is_hard_hit", "sum"),
        barrels=("is_barrel", "sum"),
        swings=("is_swing", "sum"),
        whiffs=("is_whiff", "sum"),
        in_zone=("is_in_zone", "sum"),
        outside_zone=("is_outside_zone", "sum"),
        chases=("is_chase", "sum"),
        zone_swings=("is_zone_swing", "sum"),
        zone_contacts=("is_zone_contact", "sum"),
        avg_launch_angle=("launch_angle", "mean"),
        avg_exit_velo=("launch_speed", "mean"),
        spin_rate_ff=("spin_ff", "mean"),
        spin_rate_sl=("spin_sl", "mean"),
        extension=("release_extension", "mean"),
        release_point_x=("release_pos_x", "mean"),
        release_point_z=("release_pos_z", "mean"),
    ).reset_index()

    agg = agg.rename(columns={"pitcher": "pitcher_id"})
    agg["hard_hit_rate"] = agg["hard_hits"] / agg["bip"].clip(lower=1)
    agg["barrel_rate"]   = agg["barrels"]   / agg["bip"].clip(lower=1)
    agg["chase_rate"]    = agg["chases"]    / agg["outside_zone"].clip(lower=1)
    agg["zone_rate"]     = agg["in_zone"]   / agg["total_pitches"].clip(lower=1)
    agg["zone_contact_rate"] = agg["zone_contacts"] / agg["zone_swings"].clip(lower=1)
    agg["whiff_rate"]    = agg["whiffs"]    / agg["swings"].clip(lower=1)

    agg = agg[agg["total_pitches"] >= 30]
    return agg

# ── 2026 weekly chunks ────────────────────────────────────────────────────────
chunks_2026 = [
    {"id": "2026_03a", "start": "2026-03-20", "end": "2026-03-26"},
    {"id": "2026_03b", "start": "2026-03-27", "end": "2026-04-02"},
    {"id": "2026_04a", "start": "2026-04-03", "end": "2026-04-09"},
    {"id": "2026_04b", "start": "2026-04-10", "end": "2026-04-14"},
]

from pybaseball import statcast

new_rows_total = 0
for chunk in chunks_2026:
    cid = chunk["id"]
    chunk_path = CHUNKS / f"pitcher_statcast_{cid}.parquet"
    if chunk_path.exists():
        print(f"  {cid}: chunk already exists, loading")
        agg = pd.read_parquet(chunk_path)
        new_rows_total += len(agg)
        continue

    print(f"  Pulling {cid} ({chunk['start']} to {chunk['end']})...")
    for attempt in range(3):
        try:
            data = statcast(start_dt=chunk["start"], end_dt=chunk["end"])
            if data is None or len(data) == 0:
                print(f"    {cid}: no data returned")
                break
            print(f"    {cid}: raw pitch rows = {len(data):,}")
            agg = _aggregate_pitcher_start(data)
            if len(agg) > 0:
                agg.to_parquet(chunk_path, index=False)
                print(f"    {cid}: {len(agg)} pitcher-starts saved to {chunk_path.name}")
                new_rows_total += len(agg)
            else:
                print(f"    {cid}: 0 rows after aggregation")
            break
        except Exception as e:
            wait = [30, 90, 180][attempt]
            print(f"    Attempt {attempt+1} failed for {cid}: {e}")
            if attempt < 2:
                print(f"    Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    FAILED after 3 attempts: {cid}")
    time.sleep(5)

print(f"\nNew rows from 2026 chunks: {new_rows_total}")

# ── re-merge all chunks ───────────────────────────────────────────────────────
print("\nRe-merging all chunks...")
all_chunks = []
for p in sorted(CHUNKS.glob("pitcher_statcast_*.parquet")):
    # skip raw files
    if "_raw" in p.name:
        continue
    try:
        all_chunks.append(pd.read_parquet(p))
    except Exception as e:
        print(f"  Failed to read {p.name}: {e}")

merged = pd.concat(all_chunks, ignore_index=True)
merged = merged.drop_duplicates(subset=["pitcher_id", "game_date", "game_pk"])

# ── PIT-SAFETY: verify 2022-2025 rows unchanged ───────────────────────────────
post_by_year = merged["game_date"].astype(str).str[:4].value_counts().sort_index().to_dict()
print(f"\nPOST-UPDATE rows: {len(merged):,}")
print(f"POST-UPDATE by year: {post_by_year}")
print("\nPIT-SAFETY CHECK (2022-2025):")
safe = True
for yr in ["2022", "2023", "2024", "2025"]:
    pre = pre_by_year.get(yr, 0)
    post = post_by_year.get(yr, 0)
    status = "OK" if pre == post else f"CHANGED ({pre} -> {post}) *** HALT ***"
    print(f"  {yr}: {status}")
    if pre != post:
        safe = False

if not safe:
    print("\nHARD STOP: 2022-2025 data changed. NOT writing parquet.")
    sys.exit(1)

print(f"\n2026 rows: {post_by_year.get('2026', 0)}")

# ── write updated parquet ─────────────────────────────────────────────────────
out_path = OUT / "pitcher_statcast_per_start.parquet"
merged.to_parquet(out_path, index=False)
print(f"\nWrote: {out_path}")
print(f"Total rows: {len(merged):,}")
