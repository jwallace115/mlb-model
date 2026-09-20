#!/usr/bin/env python3
"""
WO10b Item 3b: Capture health check — reads files only, no network.

For each feed, finds the newest file by parsing the UTC timestamp in its
FILENAME (not st_mtime, which resets on clone/rebase). For props, reads
pull_timestamp inside the parquet. For hash-skipped feeds, reads the last
line of _pulls.jsonl.

Exits non-zero if ANY feed is stale, naming it.
Can be run from any host with a clone of the repo.
"""

import argparse, json, gzip, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent

# Pattern: captures YYYYMMDDTHHMMZ or YYYYMMDDTHHMMSSZ from filenames
TS_PATTERN = re.compile(r"(\d{8}T\d{4,6}Z)")


def _parse_filename_ts(filename):
    """Extract tz-aware UTC datetime from filename timestamp."""
    m = TS_PATTERN.search(filename)
    if not m:
        return None
    ts_str = m.group(1)
    if len(ts_str) == 16:  # YYYYMMDDTHHMMSSZ
        return datetime.strptime(ts_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return datetime.strptime(ts_str, "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)


def _newest_file_age(pattern_dir, glob_pattern, now):
    """Find newest file by filename timestamp. Returns (age_hours, path) or (None, None)."""
    p = Path(pattern_dir)
    if not p.exists():
        return None, None
    files = list(p.glob(glob_pattern))
    if not files:
        return None, None

    best_ts = None
    best_path = None
    for f in files:
        ts = _parse_filename_ts(f.name)
        if ts is not None and (best_ts is None or ts > best_ts):
            best_ts = ts
            best_path = f

    if best_ts is None:
        return None, None
    age = (now - best_ts).total_seconds() / 3600
    return age, best_path


# N40: infer feed from `file` key for lines without explicit `feed`
_FILE_TO_FEED = {
    "depth_charts.parquet": "nflverse_depth",
    "injuries.parquet": "nflverse_injuries",
    "rosters_weekly.parquet": "nflverse_rosters",
}


def _infer_feed(entry):
    """Return the feed name from an explicit field or from the file key."""
    feed = entry.get("feed")
    if feed:
        return feed
    fname = entry.get("file", "")
    if fname in _FILE_TO_FEED:
        return _FILE_TO_FEED[fname]
    # Depth .json.gz files without explicit feed -> espn_depth
    if fname.startswith("depth_") and fname.endswith(".json.gz"):
        return "espn_depth"
    # N41: before N41 the ESPN puller logged {"utc","sha256","status"} — no `feed`, no `file` —
    # and every nflverse line carries `file`. So a bare line is ESPN's, in whichever log it
    # sits. Without this an "unchanged" ESPN pull left no pulse and a quiet day read STALE.
    if not fname:
        return "espn_legacy"
    return None


def _newest_pulls_age(pulls_path, now):
    """Get newest timestamp from _pulls.jsonl (for hash-skipped feeds).
    DEPRECATED in favor of _newest_pulls_age_by_feed; kept for compatibility."""
    if not pulls_path.exists():
        return None
    last_line = None
    with open(pulls_path) as f:
        for line in f:
            line = line.strip()
            if line:
                last_line = line
    if not last_line:
        return None
    entry = json.loads(last_line)
    ts_str = entry.get("utc", "")
    ts = _parse_filename_ts(ts_str)
    if ts is None:
        return None
    return (now - ts).total_seconds() / 3600


def _newest_pulls_age_by_feed(pulls_path, feed_name, now):
    """N40: Get newest timestamp from _pulls.jsonl for a SPECIFIC feed only."""
    if not pulls_path.exists():
        return None
    best_ts = None
    with open(pulls_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entry_feed = _infer_feed(entry)
            if entry_feed == "espn_legacy" and feed_name.startswith("espn_"):
                entry_feed = feed_name
            if entry_feed != feed_name:
                continue
            ts_str = entry.get("utc", "")
            ts = _parse_filename_ts(ts_str)
            if ts is not None and (best_ts is None or ts > best_ts):
                best_ts = ts
    if best_ts is None:
        return None
    return (now - best_ts).total_seconds() / 3600


def _newest_feed_age(pattern_dir, glob_pattern, now, pulls_jsonl_path=None,
                     feed_name=None):
    """Newest age from either filename timestamps or _pulls.jsonl, whichever is newer."""
    file_age, file_path = _newest_file_age(pattern_dir, glob_pattern, now)
    pulls_age = None
    if pulls_jsonl_path:
        if feed_name:
            pulls_age = _newest_pulls_age_by_feed(pulls_jsonl_path, feed_name, now)
        else:
            pulls_age = _newest_pulls_age(pulls_jsonl_path, now)

    if file_age is not None and pulls_age is not None:
        if pulls_age < file_age:
            return pulls_age, file_path  # hash-skip was more recent
        return file_age, file_path
    if file_age is not None:
        return file_age, file_path
    if pulls_age is not None:
        return pulls_age, None
    return None, None


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
        df = pd.read_parquet(f, columns=["pull_timestamp"])
        ts = pd.to_datetime(df["pull_timestamp"], utc=True).max()
        if ts is pd.NaT:
            print(f"  ERROR reading {f.name}: no valid pull_timestamp")
            sys.exit(1)
        if newest_ts is None or ts > newest_ts:
            newest_ts = ts
    if newest_ts is None:
        return None, None
    # Ensure tz-aware
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

    # Paths for _pulls.jsonl (hash-skipped feeds)
    injury_pulls = data_root / "data" / "injury_archive" / "nfl" / "season=2026" / "_pulls.jsonl"
    depth_pulls = data_root / "data" / "depth_archive" / "nfl" / "season=2026" / "_pulls.jsonl"

    # N40: each feed has an optional feed_name to filter _pulls.jsonl
    feeds = [
        ("nfl_lines", data_root / "data" / "odds_archive" / "nfl" / "line_history", "**/*.parquet", line_max, None, None),
        ("ncaaf_lines", data_root / "data" / "odds_archive" / "ncaaf" / "line_history", "**/*.parquet", line_max, None, None),
        ("kalshi_nfl", data_root / "data" / "odds_archive" / "kalshi" / "nfl", "**/*.parquet", kalshi_max, None, None),
        ("kalshi_ncaaf", data_root / "data" / "odds_archive" / "kalshi" / "ncaaf", "**/*.parquet", kalshi_max, None, None),
        ("nfl_news", data_root / "data" / "news_archive" / "nfl", "**/*.json*", news_max, None, None),
        ("ncaaf_news", data_root / "data" / "news_archive" / "ncaaf", "**/*.json*", news_max, None, None),
        ("nfl_injuries", data_root / "data" / "injury_archive" / "nfl", "**/*.json*", status_max, injury_pulls, "espn_injuries"),
        ("nfl_depth", data_root / "data" / "depth_archive" / "nfl", "**/depth_*.json*", status_max, depth_pulls, "espn_depth"),
        ("nflverse_inputs", data_root / "data" / "depth_archive" / "nfl", "**/nflverse_*.parquet", nflverse_max, depth_pulls, "nflverse_depth"),
    ]

    # Props: check the props archive parquet
    props_dir = data_root / "data" / "odds_archive" / "nfl" / "props"

    stale = []
    for name, fdir, pattern, max_age, pulls_path, feed_name in feeds:
        age, path = _newest_feed_age(fdir, pattern, now, pulls_jsonl_path=pulls_path,
                                     feed_name=feed_name)
        if age is None:
            print(f"  STALE  {name}: no files found")
            stale.append(name)
        elif age > max_age:
            label = path.name if path else "(hash-skip)"
            print(f"  STALE  {name}: {age:.1f}h old (max {max_age:.1f}h) — {label}")
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
