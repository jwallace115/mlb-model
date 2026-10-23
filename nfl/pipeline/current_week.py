#!/usr/bin/env python3
"""Return the current week for NFL or NCAAF from the schedule archive.

P59: the week of the EARLIEST game whose kickoff is still in the future,
read from the newest schedule parquet. Falls back to the calendar formula
with a printed WARNING if no schedule file exists.

Usage:
  python3 nfl/pipeline/current_week.py --sport nfl
  python3 nfl/pipeline/current_week.py --sport ncaaf
  python3 nfl/pipeline/current_week.py --sport nfl --now 2026-10-20T16:07:00+00:00
"""
import argparse
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _nfl_week_from_schedule(now, root=ROOT):
    """Read the newest nflverse schedule parquet; return the week of the earliest future game."""
    sched_dir = root / "data" / "results_archive" / "nfl"
    files = sorted(sched_dir.glob("schedules_2026_*.parquet"))
    if not files:
        return None
    df = pd.read_parquet(files[-1])
    # Build kickoff UTC: gameday (YYYY-MM-DD) + gametime (HH:MM) in ET -> UTC
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    kicks = []
    for _, row in df.iterrows():
        try:
            d = date.fromisoformat(str(row["gameday"]))
            parts = str(row["gametime"]).split(":")
            h, m = int(parts[0]), int(parts[1])
            local = datetime(d.year, d.month, d.day, h, m, tzinfo=et)
            kicks.append(local.astimezone(timezone.utc))
        except (ValueError, TypeError, IndexError):
            kicks.append(None)
    df["kick_utc"] = kicks
    future = df[df["kick_utc"].map(lambda k: k is not None and k > now)]
    if future.empty:
        return None
    return int(future.loc[future["kick_utc"].idxmin(), "week"])


def _ncaaf_week_from_schedule(now, root=ROOT):
    """Read the newest CFBD games parquet; return the week of the earliest future game."""
    sched_dir = root / "data" / "results_archive" / "ncaaf"
    files = sorted(sched_dir.glob("cfbd_games_2026_*.parquet"))
    if not files:
        return None
    df = pd.read_parquet(files[-1])
    # startDate is ISO with Z suffix
    df["kick_utc"] = pd.to_datetime(df["startDate"], utc=True)
    future = df[df["kick_utc"] > now]
    if future.empty:
        return None
    return int(future.loc[future["kick_utc"].idxmin(), "week"])


def _nfl_calendar_fallback(now):
    """Calendar heuristic — the old formula, used only as a WARNING fallback."""
    season_start = date(2026, 9, 10)
    delta = (now.date() - season_start).days
    return max(1, delta // 7 + 1)


def _ncaaf_calendar_fallback(now):
    """Calendar heuristic for NCAAF."""
    aug31 = date(now.year, 8, 31)
    last_sat = aug31 - timedelta(days=(aug31.weekday() + 2) % 7)
    week0_start = last_sat - timedelta(days=2)
    delta = (now.date() - week0_start).days
    if delta < 0:
        return 0
    return delta // 7


def current_week(sport, now=None, root=ROOT):
    """Return (week, source) where source is 'schedule' or 'calendar_fallback'."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if sport == "nfl":
        week = _nfl_week_from_schedule(now, root)
        if week is not None:
            return week, "schedule"
        print(f"WARNING: no NFL schedule file found, falling back to calendar formula",
              file=sys.stderr)
        return _nfl_calendar_fallback(now), "calendar_fallback"
    elif sport == "ncaaf":
        week = _ncaaf_week_from_schedule(now, root)
        if week is not None:
            return week, "schedule"
        print(f"WARNING: no NCAAF schedule file found, falling back to calendar formula",
              file=sys.stderr)
        return _ncaaf_calendar_fallback(now), "calendar_fallback"
    else:
        raise SystemExit(f"HALT: unknown sport {sport}")


def main():
    ap = argparse.ArgumentParser(description="Current week from the schedule archive")
    ap.add_argument("--sport", required=True, choices=["nfl", "ncaaf"])
    ap.add_argument("--now", default=None, help="UTC ISO timestamp (default: now)")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    week, source = current_week(a.sport, now)
    print(week)


if __name__ == "__main__":
    main()
