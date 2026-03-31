#!/usr/bin/env python3
"""
Pull 2022 raw pitch-level Statcast data in WEEKLY windows to avoid 25K row cap.
"""
import logging
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

OUT = Path("research/statcast_enrichment/chunks")
OUT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("pull_2022_weekly")

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

KEEP_COLS = [
    "game_date", "pitcher", "player_name", "game_pk", "game_year",
    "pitch_type", "pitch_name",
    "release_speed", "release_pos_x", "release_pos_z",
    "pfx_x", "pfx_z",
    "release_spin_rate", "effective_speed",
    "description", "events", "type",
    "launch_speed", "launch_angle",
    "estimated_woba_using_speedangle",
    "zone", "plate_x", "plate_z",
    "balls", "strikes",
    "p_throws", "stand",
]

NUMERIC_COLS = [
    "release_speed", "release_pos_x", "release_pos_z", "pfx_x", "pfx_z",
    "release_spin_rate", "effective_speed", "launch_speed", "launch_angle",
    "estimated_woba_using_speedangle", "pitcher", "game_pk",
    "zone", "plate_x", "plate_z", "balls", "strikes", "game_year",
]

# Generate weekly windows: April 4 through October 5, 2022
start_date = datetime(2022, 3, 31)  # Season opened ~April 7
end_date = datetime(2022, 10, 6)

windows = []
current = start_date
while current < end_date:
    w_end = min(current + timedelta(days=6), end_date)
    windows.append((current.strftime("%Y-%m-%d"), w_end.strftime("%Y-%m-%d")))
    current = w_end + timedelta(days=1)

logger.info(f"Pulling 2022 in {len(windows)} weekly windows")

all_dfs = []
failed = []
total_rows = 0

for i, (start, end) in enumerate(windows):
    logger.info(f"[{i+1}/{len(windows)}] {start} to {end}")

    url = SAVANT_URL.format(year=2022, start=start, end=end)

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

        df = pd.read_csv(StringIO(text), dtype=str, low_memory=False)
        avail = [c for c in KEEP_COLS if c in df.columns]
        df = df[avail].copy()

        for col in NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        logger.info(f"  {len(df)} rows, {df['game_pk'].nunique() if 'game_pk' in df.columns else '?'} games")

        if len(df) >= 25000:
            logger.warning(f"  ⚠️ HIT 25K CAP — data may be truncated for this window")

        all_dfs.append(df)
        total_rows += len(df)

    except Exception as e:
        logger.warning(f"  Failed: {e}")
        failed.append(f"{start}_{end}")

    time.sleep(6)  # Polite rate limiting

# Combine and save per-month
if all_dfs:
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["pitcher", "game_pk", "game_date", "balls", "strikes",
                                                  "pitch_type", "description"], keep="first")
    logger.info(f"After dedup: {len(combined)} rows (from {total_rows} raw)")

    # Save per-month files
    combined["game_date_dt"] = pd.to_datetime(combined["game_date"])
    combined["month"] = combined["game_date_dt"].dt.month

    for month in range(4, 11):
        mdf = combined[combined["month"] == month].drop(columns=["game_date_dt", "month"])
        if len(mdf) > 0:
            out_path = OUT / f"pitcher_statcast_2022_{month:02d}_raw.parquet"
            mdf.to_parquet(out_path, index=False)
            logger.info(f"Saved {out_path}: {len(mdf)} rows, {mdf['game_pk'].nunique()} games")

    # Print coverage summary
    print("\n" + "=" * 60)
    print("2022 RAW PITCH-LEVEL PULL — COVERAGE SUMMARY")
    print("=" * 60)

    for month in range(4, 11):
        mdf = combined[combined["game_date_dt"].dt.month == month]
        n_games = mdf["game_pk"].nunique()
        print(f"  2022-{month:02d}: {len(mdf):>7} rows, {n_games:>4} games")

    print(f"\n  Total: {len(combined)} rows")
    print(f"  Unique games: {combined['game_pk'].nunique()}")
    print(f"  Unique pitchers: {combined['pitcher'].nunique()}")
    print(f"  pitch_type: {combined['pitch_type'].notna().mean()*100:.1f}%")
    print(f"  pfx_x: {combined['pfx_x'].notna().mean()*100:.1f}%")
    print(f"  pfx_z: {combined['pfx_z'].notna().mean()*100:.1f}%")
    print(f"  release_speed: {combined['release_speed'].notna().mean()*100:.1f}%")
    print(f"  release_pos_x: {combined['release_pos_x'].notna().mean()*100:.1f}%")
    print(f"  release_pos_z: {combined['release_pos_z'].notna().mean()*100:.1f}%")
    print(f"  release_spin_rate: {combined['release_spin_rate'].notna().mean()*100:.1f}%")
    print(f"  Pitch types: {sorted(combined['pitch_type'].dropna().unique())}")

    if failed:
        print(f"\n  Failed windows ({len(failed)}): {failed}")
else:
    print("No data pulled!")
