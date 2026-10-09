#!/usr/bin/env python3
"""
Pull nflverse weekly player stats (2026) and write to data/results_archive/nfl/.

HALT (non-zero) on: empty frame, <100 rows, no row with week >= 1.
Output: data/results_archive/nfl/player_stats_2026_<UTC>.parquet (timestamped, append-only).

On the VM this runs daily at 09:35Z, after the 09:30Z schedules pull and before
the 10:10Z grader.
On the Mac, RESULTS_ARCHIVE_DIR overrides the output directory so that dry-run
writes never appear in git status.

OPS6 Item 1, P45.
"""
import os, sys
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (ROOT / "data" / "results_archive"))

KEEP_COLS = [
    "player_id", "player_display_name", "player_name", "team", "opponent_team",
    "season", "week", "season_type",
    "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
    "carries", "rushing_yards", "rushing_tds",
    "receptions", "receiving_yards", "receiving_tds",
]


def pull(season=2026):
    df = nflreadpy.load_player_stats([season], summary_level="week").to_pandas()
    if df.empty:
        print("HALT: nflverse returned empty player_stats", file=sys.stderr)
        sys.exit(1)
    if len(df) < 100:
        print(f"HALT: nflverse returned only {len(df)} rows (expected >=100)", file=sys.stderr)
        sys.exit(1)
    if not (df.week >= 1).any():
        print("HALT: no row with week >= 1 in player_stats", file=sys.stderr)
        sys.exit(1)

    missing = [c for c in KEEP_COLS if c not in df.columns]
    if missing:
        print(f"HALT: missing columns in nflverse player_stats: {missing}", file=sys.stderr)
        sys.exit(1)

    df = df[KEEP_COLS].copy()

    out_dir = RESULTS_DIR / "nfl"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"player_stats_2026_{ts}.parquet"
    df.to_parquet(out_path, index=False)
    print(f"wrote {out_path} ({len(df)} rows, weeks {sorted(df.week.unique())})")
    return out_path


if __name__ == "__main__":
    pull()
