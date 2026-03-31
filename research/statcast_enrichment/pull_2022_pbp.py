#!/usr/bin/env python3
"""
Pull 2022 Statcast pitch-level data with ALL columns (no KEEP_COLS filter).
Weekly windows to avoid 25K row cap. Same endpoint as phase1_repair.py.
"""
import logging
import time
import calendar
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

OUT = Path("research/statcast_enrichment/chunks")
OUT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("pull_2022_pbp")

SAVANT_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv?"
    "all=true&hfPT=&hfAB=&hfGT=R%7C&hfPR=&hfZ=&hfStadium=&hfBBL=&hfNewZones=&hfPull=&hfC=&hfSea={year}%7C"
    "&hfSit=&player_type=pitcher&hfOuts=&hfOpponent=&pitcher_throws=&batter_stands="
    "&hfSA=&game_date_gt={start}&game_date_lt={end}"
    "&hfMo=&hfTeam=&home_road=&hfRO=&position=&hfInfield=&hfOutfield=&hfInn=&hfBBT=&hfFlag="
    "&metric_1=&group_by=name&min_pitches=0&min_results=0&min_pas=0&sort_col=pitches&player_event_sort=api_p_release_speed"
    "&sort_order=desc&type=details&player_id=&csv=true"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

YEAR = 2022
start_date = datetime(2022, 3, 31)
end_date = datetime(2022, 10, 6)

windows = []
current = start_date
while current < end_date:
    w_end = min(current + timedelta(days=6), end_date)
    windows.append((current.strftime("%Y-%m-%d"), w_end.strftime("%Y-%m-%d")))
    current = w_end + timedelta(days=1)

logger.info(f"Pulling 2022 PBP in {len(windows)} weekly windows (ALL columns)")

all_dfs = []
failed = []

for i, (start, end) in enumerate(windows):
    logger.info(f"[{i+1}/{len(windows)}] {start} to {end}")
    url = SAVANT_URL.format(year=YEAR, start=start, end=end)

    try:
        r = requests.get(url, headers=HEADERS, timeout=120)
        if r.status_code != 200:
            logger.warning(f"  HTTP {r.status_code}")
            failed.append(f"{start}_{end}")
            time.sleep(6)
            continue

        text = r.text
        if len(text) < 200 or "pitcher" not in text[:500].lower():
            logger.info(f"  Empty ({len(text)} bytes)")
            time.sleep(6)
            continue

        # Parse ALL columns — no filter
        df = pd.read_csv(StringIO(text), dtype=str, low_memory=False)
        logger.info(f"  {len(df)} rows, {len(df.columns)} columns")

        if len(df) >= 25000:
            logger.warning(f"  HIT 25K CAP")

        all_dfs.append(df)
    except Exception as e:
        logger.warning(f"  Failed: {e}")
        failed.append(f"{start}_{end}")

    time.sleep(6)

if not all_dfs:
    logger.error("No data pulled!")
    exit(1)

combined = pd.concat(all_dfs, ignore_index=True)

# Convert key numeric columns
numeric_cols = ["pitcher", "batter", "game_pk", "game_year",
                "on_1b", "on_2b", "on_3b", "outs_when_up",
                "inning", "at_bat_number", "pitch_number",
                "home_score", "away_score", "bat_score", "fld_score",
                "post_home_score", "post_away_score", "post_bat_score",
                "release_speed", "launch_speed", "launch_angle",
                "release_pos_x", "release_pos_z", "pfx_x", "pfx_z",
                "release_spin_rate", "plate_x", "plate_z",
                "hc_x", "hc_y", "zone", "balls", "strikes"]
for col in numeric_cols:
    if col in combined.columns:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

# Dedup
dedup_cols = ["pitcher", "game_pk", "game_date", "at_bat_number", "pitch_number"]
avail_dedup = [c for c in dedup_cols if c in combined.columns]
before = len(combined)
combined = combined.drop_duplicates(subset=avail_dedup, keep="first")
logger.info(f"Dedup: {before} -> {len(combined)} rows")

# Save per-month
if "game_date" in combined.columns:
    combined["game_date_dt"] = pd.to_datetime(combined["game_date"])
    combined["month"] = combined["game_date_dt"].dt.month

    for month in range(4, 11):
        mdf = combined[combined["month"] == month].drop(columns=["game_date_dt", "month"], errors="ignore")
        if len(mdf) > 0:
            out_path = OUT / f"pbp_2022_{month:02d}_raw.parquet"
            mdf.to_parquet(out_path, index=False)
            logger.info(f"Saved {out_path}: {len(mdf)} rows, {mdf['game_pk'].nunique()} games")

print(f"\nTotal rows: {len(combined)}")
print(f"Total columns: {len(combined.columns)}")
print(f"Unique games: {combined['game_pk'].nunique()}")
if failed:
    print(f"Failed windows: {failed}")

# Check PBP columns
pbp_cols = ["on_1b", "on_2b", "on_3b", "outs_when_up", "events", "inning",
            "inning_topbot", "home_score", "away_score", "post_home_score",
            "post_away_score", "at_bat_number", "pitch_number"]
print(f"\nPBP column presence:")
for col in pbp_cols:
    present = col in combined.columns
    cov = combined[col].notna().mean() * 100 if present else 0
    print(f"  {col}: {'YES' if present else 'NO'} ({cov:.1f}% populated)")
