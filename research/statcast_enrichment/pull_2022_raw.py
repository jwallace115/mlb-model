#!/usr/bin/env python3
"""
Pull 2022 raw pitch-level Statcast data from Baseball Savant CSV endpoint.
Same URL pattern as phase1_repair.py. Saves raw pitches (not aggregated).
"""
import logging
import time
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path("research/statcast_enrichment/chunks")
OUT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("pull_2022_raw")

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

# Columns to retain
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

# Pull in 2-week windows to stay under Savant's row limit
import calendar

YEAR = 2022
MONTHS = list(range(4, 11))  # April through October

all_chunks = []
results = {}

for month in MONTHS:
    _, last_day = calendar.monthrange(YEAR, month)
    # Split each month into 2 halves to stay under row limits
    windows = [
        (f"{YEAR}-{month:02d}-01", f"{YEAR}-{month:02d}-15"),
        (f"{YEAR}-{month:02d}-16", f"{YEAR}-{month:02d}-{last_day}"),
    ]

    month_dfs = []
    for start, end in windows:
        url = SAVANT_URL.format(year=YEAR, start=start, end=end)
        logger.info(f"Pulling {start} to {end}...")

        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            if r.status_code != 200:
                logger.warning(f"  HTTP {r.status_code} — skipping")
                continue

            text = r.text
            if len(text) < 200 or "pitcher" not in text[:500].lower():
                logger.info(f"  Empty response ({len(text)} bytes)")
                continue

            df = pd.read_csv(StringIO(text), dtype=str, low_memory=False)
            logger.info(f"  Got {len(df)} rows")

            # Keep only columns that exist
            avail = [c for c in KEEP_COLS if c in df.columns]
            df = df[avail].copy()

            # Convert numeric columns
            for col in ["release_speed", "release_pos_x", "release_pos_z", "pfx_x", "pfx_z",
                         "release_spin_rate", "effective_speed", "launch_speed", "launch_angle",
                         "estimated_woba_using_speedangle", "pitcher", "game_pk",
                         "zone", "plate_x", "plate_z", "balls", "strikes", "game_year"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            month_dfs.append(df)
        except Exception as e:
            logger.warning(f"  Failed: {e}")

        # Polite rate limiting
        time.sleep(6)

    if month_dfs:
        month_df = pd.concat(month_dfs, ignore_index=True)
        out_path = OUT / f"pitcher_statcast_{YEAR}_{month:02d}_raw.parquet"
        month_df.to_parquet(out_path, index=False)
        logger.info(f"  Saved {out_path}: {len(month_df)} rows")
        results[month] = {"rows": len(month_df), "status": "OK"}
        all_chunks.append(month_df)
    else:
        results[month] = {"rows": 0, "status": "FAILED"}
        logger.warning(f"  Month {month:02d} FAILED — no data")

# Coverage summary
print("\n" + "=" * 60)
print("2022 RAW PITCH-LEVEL PULL — COVERAGE SUMMARY")
print("=" * 60)

total = pd.concat(all_chunks, ignore_index=True) if all_chunks else pd.DataFrame()

for m in MONTHS:
    r = results.get(m, {"rows": 0, "status": "NOT_RUN"})
    flag = "⚠️" if r["rows"] < 50000 else "✓"
    print(f"  {YEAR}-{m:02d}: {r['rows']:>7} rows  [{r['status']}] {flag}")

print(f"\n  Total rows: {len(total)}")
if len(total) > 0:
    print(f"  pitch_type populated: {total['pitch_type'].notna().mean()*100:.1f}%")
    print(f"  pfx_x populated: {total['pfx_x'].notna().mean()*100:.1f}%")
    print(f"  pfx_z populated: {total['pfx_z'].notna().mean()*100:.1f}%")
    print(f"  release_speed populated: {total['release_speed'].notna().mean()*100:.1f}%")
    print(f"  release_pos_x populated: {total['release_pos_x'].notna().mean()*100:.1f}%")
    print(f"  release_pos_z populated: {total['release_pos_z'].notna().mean()*100:.1f}%")
    print(f"  release_spin_rate populated: {total['release_spin_rate'].notna().mean()*100:.1f}%")
    print(f"  Unique pitchers: {total['pitcher'].nunique()}")
    print(f"  Unique games: {total['game_pk'].nunique()}")
    print(f"  Pitch types: {sorted(total['pitch_type'].dropna().unique())}")
