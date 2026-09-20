#!/usr/bin/env python3
"""
WO10 Item 4a: Capture health check — reads files only, no network.

For each feed, finds the newest file (or newest pull_timestamp in props
parquet), prints its age, and compares with a max age. Exits non-zero if
ANY feed is stale, naming it.

Can be run from any host with a clone of the repo.
"""

import argparse, json, gzip, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent


def _newest_file_age(pattern_dir, glob_pattern, now):
    """Find newest file matching pattern, return (age_hours, path) or (None, None)."""
    p = Path(pattern_dir)
    if not p.exists():
        return None, None
    files = sorted(p.glob(glob_pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None, None
    newest = files[0]
    age = (now - datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc))
    return age.total_seconds() / 3600, newest


def _newest_props_age(props_dir, now):
    """Find newest pull_timestamp in props parquet files."""
    p = Path(props_dir)
    if not p.exists():
        return None, None
    files = sorted(p.rglob("data_*.parquet"))
    if not files:
        return None, None
    newest_ts = None
    for f in files[-2:]:  # check last 2 partitions
        try:
            df = pd.read_parquet(f, columns=["pull_timestamp"])
            ts = pd.to_datetime(df["pull_timestamp"]).max()
            if newest_ts is None or ts > newest_ts:
                newest_ts = ts
        except Exception:
            continue
    if newest_ts is None:
        return None, None
    if newest_ts.tzinfo is None:
        newest_ts = newest_ts.tz_localize("UTC")
    age = (now - newest_ts).total_seconds() / 3600
    return age, files[-1]


def check_feeds(data_root=None, now=None):
    if data_root is None:
        data_root = ROOT
    if now is None:
        now = datetime.now(timezone.utc)

    # Determine if we're in the capture window (14:00-05:30 UTC)
    h = now.hour + now.minute / 60
    in_capture_window = (h >= 14) or (h < 5.5)

    # Current day of week (0=Mon, 6=Sun)
    dow = now.weekday()
    is_props_day = dow in (2, 3, 4, 5, 6)  # Wed-Sun

    line_max = 0.75 if in_capture_window else 9.0
    kalshi_max = 0.75 if in_capture_window else 9.0
    props_max = 26.0 if is_props_day else 168.0
    news_max = 7.0
    status_max = 7.0
    nflverse_max = 26.0

    feeds = [
        ("nfl_lines", data_root / "data" / "odds_archive" / "nfl" / "line_history", "**/*.parquet", line_max),
        ("ncaaf_lines", data_root / "data" / "odds_archive" / "ncaaf" / "line_history", "**/*.parquet", line_max),
        ("kalshi_nfl", data_root / "data" / "odds_archive" / "kalshi" / "nfl", "**/*.parquet", kalshi_max),
        ("kalshi_ncaaf", data_root / "data" / "odds_archive" / "kalshi" / "ncaaf", "**/*.parquet", kalshi_max),
        ("nfl_news", data_root / "data" / "news_archive" / "nfl", "**/*.json*", news_max),
        ("ncaaf_news", data_root / "data" / "news_archive" / "ncaaf", "**/*.json*", news_max),
        ("nfl_injuries", data_root / "data" / "injury_archive" / "nfl", "**/*.json", status_max),
        ("nfl_depth", data_root / "data" / "depth_archive" / "nfl", "**/depth_*.json", status_max),
        ("nflverse_inputs", data_root / "data" / "depth_archive" / "nfl", "**/nflverse_*.parquet", nflverse_max),
    ]

    # Props: check the props archive parquet
    props_dir = data_root / "data" / "odds_archive" / "nfl" / "props"

    stale = []
    for name, fdir, pattern, max_age in feeds:
        age, path = _newest_file_age(fdir, pattern, now)
        if age is None:
            print(f"  STALE  {name}: no files found")
            stale.append(name)
        elif age > max_age:
            print(f"  STALE  {name}: {age:.1f}h old (max {max_age:.1f}h) — {path.name}")
            stale.append(name)
        else:
            print(f"  OK     {name}: {age:.1f}h old (max {max_age:.1f}h)")

    # Props
    age, path = _newest_props_age(props_dir, now)
    if age is None:
        print(f"  STALE  nfl_props: no files found")
        stale.append("nfl_props")
    elif age > props_max:
        print(f"  STALE  nfl_props: {age:.1f}h old (max {props_max:.1f}h)")
        stale.append("nfl_props")
    else:
        print(f"  OK     nfl_props: {age:.1f}h old (max {props_max:.1f}h)")

    return stale


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=None,
                        help="Override root dir (for testing)")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    print(f"capture_health {now.isoformat()}")

    stale = check_feeds(data_root=args.data_root, now=now)

    if stale:
        print(f"\nFAIL: {len(stale)} stale feed(s): {', '.join(stale)}")
        sys.exit(1)
    else:
        print(f"\nOK: all feeds fresh")
        sys.exit(0)


if __name__ == "__main__":
    main()
