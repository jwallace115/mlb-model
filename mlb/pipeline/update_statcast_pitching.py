#!/usr/bin/env python3
"""
Incremental Statcast Pitch Data Updater
========================================
Pulls pitch-level data from Baseball Savant CSV endpoint for recent games
and saves to mlb/props/data/statcast_chunk_YYYY-MM-01.parquet files.

Runs weekly (Sunday 4am UTC) so KP04 shadow has fresh breaking-ball usage data.
Idempotent — deduplicates by (game_pk, pitcher, at_bat_number, pitch_number).

Usage:
  python3 mlb/pipeline/update_statcast_pitching.py
"""

import calendar
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SC_DIR = PROJECT_ROOT / "mlb" / "props" / "data"
SC_DIR.mkdir(parents=True, exist_ok=True)

SAVANT_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv?"
    "all=true&hfPT=&hfAB=&hfGT=R%7C&hfPR=&hfZ=&hfStadium=&hfBBL=&hfNewZones=&hfPull=&hfC="
    "&hfSea={year}%7C"
    "&hfSit=&player_type=pitcher&hfOuts=&hfOpponent=&pitcher_throws=&batter_stands="
    "&hfSA=&game_date_gt={start}&game_date_lt={end}"
    "&hfMo=&hfTeam=&home_road=&hfRO=&position=&hfInfield=&hfOutfield=&hfInn=&hfBBT=&hfFlag="
    "&metric_1=&group_by=name&min_pitches=0&min_results=0&min_pas=0"
    "&sort_col=pitches&player_event_sort=api_p_release_speed"
    "&sort_order=desc&type=details&player_id=&csv=true"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# Dedup key columns
DEDUP_COLS = ["game_pk", "pitcher", "at_bat_number", "pitch_number"]


def find_max_date():
    """Find the latest game_date across all existing chunks for current year."""
    current_year = date.today().year
    chunks = sorted(SC_DIR.glob("statcast_chunk_*.parquet"))
    max_dt = None
    for f in chunks:
        if str(current_year) not in f.stem:
            continue
        try:
            df = pd.read_parquet(f, columns=["game_date"])
            chunk_max = df["game_date"].max()
            if pd.notna(chunk_max):
                if max_dt is None or chunk_max > max_dt:
                    max_dt = chunk_max
        except Exception:
            continue
    return max_dt


def pull_window(year, start, end):
    """Pull a date window from Savant. Returns DataFrame or None."""
    url = SAVANT_URL.format(year=year, start=start, end=end)
    try:
        r = requests.get(url, headers=HEADERS, timeout=180)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} for {start} to {end}")
            return None

        text = r.text
        if len(text) < 200 or "pitcher" not in text[:500].lower():
            print(f"  Empty response for {start} to {end} ({len(text)} bytes)")
            return None

        df = pd.read_csv(StringIO(text), low_memory=False)
        # Filter to regular season only
        if "game_type" in df.columns:
            df = df[df["game_type"] == "R"]
        print(f"  {start} to {end}: {len(df)} pitches")
        return df
    except Exception as e:
        print(f"  Error pulling {start} to {end}: {e}")
        return None


def main():
    print(f"Statcast Pitch Data Updater — {datetime.now(timezone.utc).isoformat()}")

    current_year = date.today().year
    max_dt = find_max_date()

    if max_dt is not None:
        # Start from the day after max_date
        scan_start = pd.Timestamp(max_dt).date() + timedelta(days=1)
        print(f"  Existing {current_year} data through: {max_dt.date()}")
    else:
        # No current-year data — start from season opening
        scan_start = date(current_year, 3, 20)
        print(f"  No {current_year} data — starting from {scan_start}")

    # Pull through yesterday (today's games may still be in progress)
    scan_end = date.today() - timedelta(days=1)

    if scan_start > scan_end:
        print(f"  Already up to date (max={max_dt.date() if max_dt else 'none'}, yesterday={scan_end})")
        return

    print(f"  Pulling: {scan_start} to {scan_end}")

    # Group by month for chunk file naming
    months = {}
    d = scan_start
    while d <= scan_end:
        key = (d.year, d.month)
        if key not in months:
            months[key] = {"start": d, "end": d}
        months[key]["end"] = d
        d += timedelta(days=1)

    total_new = 0
    total_pitchers = set()

    for (year, month), rng in sorted(months.items()):
        chunk_path = SC_DIR / f"statcast_chunk_{year}-{month:02d}-01.parquet"
        print(f"\n  Month {year}-{month:02d}:")

        # Load existing chunk if any
        existing = None
        if chunk_path.exists():
            try:
                existing = pd.read_parquet(chunk_path)
                print(f"    Existing chunk: {len(existing)} rows")
            except Exception:
                existing = None

        # Pull in 2-week windows to stay under Savant row limits
        _, last_day = calendar.monthrange(year, month)
        month_start = max(rng["start"], date(year, month, 1))
        month_end = min(rng["end"], date(year, month, last_day))

        windows = []
        ws = month_start
        while ws <= month_end:
            we = min(ws + timedelta(days=13), month_end)
            windows.append((ws.isoformat(), we.isoformat()))
            ws = we + timedelta(days=1)

        new_dfs = []
        for start, end in windows:
            df = pull_window(year, start, end)
            if df is not None and len(df) > 0:
                new_dfs.append(df)
            time.sleep(6)  # polite rate limiting

        if not new_dfs:
            print(f"    No new data for {year}-{month:02d}")
            continue

        new_data = pd.concat(new_dfs, ignore_index=True)

        # Merge with existing
        if existing is not None:
            combined = pd.concat([existing, new_data], ignore_index=True)
        else:
            combined = new_data

        # Dedup
        avail_dedup = [c for c in DEDUP_COLS if c in combined.columns]
        if avail_dedup:
            before = len(combined)
            combined = combined.drop_duplicates(subset=avail_dedup, keep="last")
            dupes = before - len(combined)
            if dupes > 0:
                print(f"    Deduped: {dupes} duplicate rows removed")

        # Ensure game_date is datetime
        if "game_date" in combined.columns:
            combined["game_date"] = pd.to_datetime(combined["game_date"])

        combined.to_parquet(chunk_path, index=False)

        n_new = len(combined) - (len(existing) if existing is not None else 0)
        pitchers = set(combined["pitcher"].dropna().unique()) if "pitcher" in combined.columns else set()
        total_new += n_new
        total_pitchers |= pitchers
        print(f"    Saved: {len(combined)} total rows ({n_new} new), {len(pitchers)} pitchers")

    print(f"\n  Summary: {total_new} new rows, {len(total_pitchers)} unique pitchers")

    # Auto-push
    subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
                     "Statcast pitch data incremental update"],
                    capture_output=True)


if __name__ == "__main__":
    main()
