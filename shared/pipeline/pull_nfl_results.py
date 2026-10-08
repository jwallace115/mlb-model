#!/usr/bin/env python3
"""
Pull nflverse schedule (2026) and write to data/results_archive/nfl/.

HALT (non-zero) on: empty frame, <250 rows, no completed game.
Output: data/results_archive/nfl/schedules_2026_<UTC>.parquet (timestamped, append-only).

On the VM this runs daily at 09:30Z via cron, before the 10:10Z grader.
On the Mac, RESULTS_ARCHIVE_DIR overrides the output directory so that dry-run
writes never appear in git status.

OPS2b Item 1, P7.
"""
import os, sys
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (ROOT / "data" / "results_archive"))

KEEP_COLS = [
    "game_id", "season", "week", "gameday", "gametime",
    "home_team", "away_team", "home_score", "away_score", "game_type",
]


def pull(season=2026):
    sched = nflreadpy.load_schedules([season]).to_pandas()
    if sched.empty:
        print("HALT: nflverse returned empty schedule", file=sys.stderr)
        sys.exit(1)
    if len(sched) < 250:
        print(f"HALT: nflverse returned only {len(sched)} rows (expected >=250)", file=sys.stderr)
        sys.exit(1)
    if sched.home_score.notna().sum() == 0:
        print("HALT: no completed games in nflverse schedule", file=sys.stderr)
        sys.exit(1)

    sched = sched[KEEP_COLS].copy()

    out_dir = RESULTS_DIR / "nfl"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"schedules_2026_{ts}.parquet"
    sched.to_parquet(out_path, index=False)
    print(f"wrote {out_path} ({len(sched)} rows, {sched.home_score.notna().sum()} completed)")
    return out_path


if __name__ == "__main__":
    pull()
