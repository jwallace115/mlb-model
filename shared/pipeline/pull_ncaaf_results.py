#!/usr/bin/env python3
"""
Pull CFBD games (2026) and write to data/results_archive/ncaaf/.

HALT (non-zero) on: empty frame, <500 rows, no completed game in the last 10 days.
Output: data/results_archive/ncaaf/cfbd_games_2026_<UTC>.parquet (timestamped, append-only).

On the VM this runs daily at 09:40Z via cron, before the 10:10Z crosswalk + grader.
On the Mac, RESULTS_ARCHIVE_DIR overrides the output directory so that dry-run
writes never appear in git status.

Zero Odds API credits. CFBD API is rate-limited, not credit-metered.

OPS-R1 Item 2, P53.
"""
import hashlib
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

CFBD_KEY = os.getenv("CFBD_API_KEY", "")
KEY_FP = hashlib.sha256(CFBD_KEY.strip().encode()).hexdigest()[:8] if CFBD_KEY else "UNSET"
CFBD_BASE = "https://api.collegefootballdata.com"
CFBD_HEADERS = {"Authorization": f"Bearer {CFBD_KEY}", "Accept": "application/json"}

RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (ROOT / "data" / "results_archive"))

KEEP_COLS = [
    "id", "season", "week", "seasonType", "startDate", "completed",
    "homeTeam", "awayTeam", "homePoints", "awayPoints", "neutralSite",
]


def cfbd_get(endpoint, params=None):
    url = f"{CFBD_BASE}/{endpoint.lstrip('/')}"
    r = requests.get(url, headers=CFBD_HEADERS, params=params or {}, timeout=30)
    if r.status_code != 200:
        print(f"HALT: CFBD {endpoint} -> HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


def pull(season=2026):
    print(f"CFBD key fingerprint: {KEY_FP}")
    if not CFBD_KEY:
        print("HALT: CFBD_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    games = cfbd_get("/games", {"year": season, "seasonType": "regular"})
    post = cfbd_get("/games", {"year": season, "seasonType": "postseason"})
    all_games = games + post

    df = pd.DataFrame(all_games)
    if df.empty:
        print("HALT: CFBD returned empty games list", file=sys.stderr)
        sys.exit(1)

    # Keep only the columns we need
    for c in KEEP_COLS:
        if c not in df.columns:
            print(f"HALT: CFBD response missing column {c}", file=sys.stderr)
            sys.exit(1)
    df = df[KEEP_COLS].copy()

    if len(df) < 500:
        print(f"HALT: CFBD returned only {len(df)} rows (expected >=500)", file=sys.stderr)
        sys.exit(1)

    # Check for recent completed games
    completed = df[df["completed"] == True]
    if completed.empty:
        print("HALT: no completed games in CFBD data", file=sys.stderr)
        sys.exit(1)

    # Check that at least one game completed in the last 10 days
    now = datetime.now(timezone.utc)
    completed_dates = pd.to_datetime(completed["startDate"], utc=True)
    recent = completed_dates[completed_dates >= (now - timedelta(days=10))]
    if recent.empty:
        print(f"HALT: no completed game in the last 10 days "
              f"(latest: {completed_dates.max().isoformat()})", file=sys.stderr)
        sys.exit(1)

    out_dir = RESULTS_DIR / "ncaaf"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"cfbd_games_2026_{ts}.parquet"
    df.to_parquet(out_path, index=False)
    n_completed = (df["completed"] == True).sum()
    print(f"wrote {out_path} ({len(df)} rows, {n_completed} completed)")
    return out_path


if __name__ == "__main__":
    pull()
