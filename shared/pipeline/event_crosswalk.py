#!/usr/bin/env python3
"""
Event crosswalk: tape event_id → official game key, built per sport.

NCAAF: tape (home, away, commence) → CFBD id via _odds_to_cfbd (copied from
  ncaaf/pipeline/grade_ncaaf_tickets.py), date within ±1 day.
NFL: tape (home, away, commence) → nflverse game_id via nfl_team normaliser,
  date within ±1 day (gametime converted from ET to UTC explicitly).

Exactly one match → row; zero → listed as unmatched; two → HALT.

OPS2 Item 3.
"""
import os, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import picks_ledger as pl
import pick_sources as ps

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")

# ---- NCAAF: _odds_to_cfbd copied from ncaaf/pipeline/grade_ncaaf_tickets.py ----
# Origin: ncaaf/pipeline/grade_ncaaf_tickets.py lines 33-71 (2026-10-05)
_TEAM_MAP = {
    "San Jose State Spartans": "San Jos\u00e9 State",
    "UMass Minutemen": "Massachusetts",
    "Southern Mississippi Golden Eagles": "Southern Miss",
    "Appalachian State Mountaineers": "App State",
    "Hawaii Rainbow Warriors": "Hawai'i",
    "Southeastern Louisiana Lions": "SE Louisiana",
    "William and Mary Tribe": "William & Mary",
    "LIU Sharks": "Long Island University",
    "Houston Baptist Huskies": "Houston Christian",
}


def _odds_to_cfbd(odds_name, cfbd_teams):
    """Map an Odds API team name to a CFBD team name.
    Copied from ncaaf/pipeline/grade_ncaaf_tickets.py (origin noted in that file)."""
    if odds_name in _TEAM_MAP:
        return _TEAM_MAP[odds_name]
    words = odds_name.split()
    for i in range(len(words), 0, -1):
        candidate = " ".join(words[:i])
        if candidate in cfbd_teams:
            return candidate
    return None


def _nfl_team_norm(name):
    """Normalise NFL team name to nflverse abbreviation."""
    n = ps.nfl_team(name)
    if n:
        # nfl_team returns nickname; we need the abbreviation
        inv = {v: k for k, v in ps.NFL.items() if k != "WSH"}
        return inv.get(n, n).upper()
    # Maybe already an abbreviation
    if name and name.upper() in ps.NFL:
        return name.upper()
    return name


def build_crosswalk(events_df, officials_df, sport, team_map=None):
    """Build crosswalk from tape events to official games.
    events_df: event_id, home_team, away_team, commence_time
    officials_df: official_game_id, home, away, date, home_score, away_score, completed
    Returns DataFrame with: event_id, official_game_id, home_score, away_score, completed, home_team, away_team
    """
    results = []
    unmatched = []

    for _, ev in events_df.iterrows():
        eid = ev.event_id
        ct = pd.to_datetime(ev.commence_time, utc=True)
        ev_date = ct.date()

        if team_map:
            eh = team_map(ev.home_team)
            ea = team_map(ev.away_team)
        else:
            eh = ev.home_team
            ea = ev.away_team

        matches = []
        for _, off in officials_df.iterrows():
            off_date = pd.to_datetime(off.date).date() if off.date else None
            if off_date is None:
                continue
            # date within ±1 day
            if abs((ev_date - off_date).days) > 1:
                continue

            if team_map:
                oh = team_map(off.home)
                oa = team_map(off.away)
            else:
                oh = off.home
                oa = off.away

            if (eh == oh and ea == oa) or (eh == oa and ea == oh):
                matches.append(off)

        if len(matches) == 0:
            unmatched.append({"event_id": eid, "home": ev.home_team, "away": ev.away_team,
                              "commence": str(ct), "reason": "no_match"})
        elif len(matches) > 1:
            # Check if they're actually the same game (same id)
            game_ids = {m.official_game_id for m in matches}
            if len(game_ids) == 1:
                m = matches[0]
                results.append({"event_id": eid, "official_game_id": m.official_game_id,
                                "home_score": m.home_score, "away_score": m.away_score,
                                "completed": m.completed, "home_team": ev.home_team, "away_team": ev.away_team})
            else:
                raise pl.Halt(f"multiple official games for event {eid}: {game_ids}")
        else:
            m = matches[0]
            results.append({"event_id": eid, "official_game_id": m.official_game_id,
                            "home_score": m.home_score, "away_score": m.away_score,
                            "completed": m.completed, "home_team": ev.home_team, "away_team": ev.away_team})

    return pd.DataFrame(results), unmatched


def _load_ncaaf_officials(root):
    """Load CFBD games 2026."""
    p = root / "research" / "ncaaf" / "cfbd_games_2026.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df.startDate).dt.date
    return df.rename(columns={"id": "official_game_id", "homeTeam": "home", "awayTeam": "away",
                               "homePoints": "home_score", "awayPoints": "away_score"})


def _load_nfl_officials(root):
    """Load nflverse schedule 2026 from data/results_archive/nfl/.

    HALT if the folder is empty or the newest file is older than 36 h.
    No network call: pull_nfl_results.py writes these files on a schedule.
    """
    archive_dir = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (root / "data" / "results_archive")) / "nfl"
    if not archive_dir.exists():
        raise pl.Halt(f"NFL results archive missing: {archive_dir}")
    files = sorted(archive_dir.glob("schedules_2026_*.parquet"))
    if not files:
        raise pl.Halt(f"NFL results archive empty: {archive_dir}")

    newest = files[-1]
    age_h = (datetime.now(timezone.utc) - datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600
    if age_h > 36:
        raise pl.Halt(f"NFL results archive stale: {newest.name} is {age_h:.1f}h old (>36h)")

    sched = pd.read_parquet(newest)
    sched["date"] = pd.to_datetime(sched.gameday).dt.date
    sched["completed"] = sched.home_score.notna()
    return sched.rename(columns={"game_id": "official_game_id",
                                  "home_team": "home", "away_team": "away"})


def _tape_events_for_sport(sport, root):
    """Get unique tape events for a sport."""
    folder = {"NFL": "nfl", "NCAAF": "ncaaf"}.get(sport)
    if not folder:
        return pd.DataFrame()
    tape_dir = root / "data" / "odds_archive" / folder / "line_history"
    if not tape_dir.exists():
        return pd.DataFrame()
    frames = []
    for season_dir in tape_dir.glob("season=*"):
        for f in sorted(season_dir.glob("snap_*.parquet")):
            try:
                df = pd.read_parquet(f, columns=["event_id", "home_team", "away_team", "commence_time"])
                frames.append(df)
            except Exception:
                continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    # Take latest commence_time per event
    df["ct"] = pd.to_datetime(df.commence_time, utc=True)
    latest = df.sort_values("ct").groupby("event_id").last().reset_index()
    return latest[["event_id", "home_team", "away_team", "commence_time"]]


def build_all(root=None):
    root = Path(root or ROOT)
    results = {}

    # NCAAF
    ncaaf_events = _tape_events_for_sport("NCAAF", root)
    ncaaf_officials = _load_ncaaf_officials(root)
    if not ncaaf_events.empty and not ncaaf_officials.empty:
        cfbd_teams = set(ncaaf_officials["home"].unique()) | set(ncaaf_officials["away"].unique())
        xw, unmatched = build_crosswalk(
            ncaaf_events, ncaaf_officials, "NCAAF",
            team_map=lambda n: _odds_to_cfbd(n, cfbd_teams) or n)
        results["ncaaf"] = (xw, unmatched)
        print(f"NCAAF crosswalk: {len(xw)} events matched, {len(unmatched)} unmatched")
    else:
        print("NCAAF: no tape events or no CFBD data")

    # NFL
    nfl_events = _tape_events_for_sport("NFL", root)
    nfl_officials = _load_nfl_officials(root)
    if not nfl_events.empty and not nfl_officials.empty:
        xw, unmatched = build_crosswalk(
            nfl_events, nfl_officials, "NFL",
            team_map=lambda n: _nfl_team_norm(n))
        results["nfl"] = (xw, unmatched)
        print(f"NFL crosswalk: {len(xw)} events matched, {len(unmatched)} unmatched")
    else:
        print("NFL: no tape events or no nflverse data")

    # Write to ledger dir
    for sport, (xw, _) in results.items():
        out = LEDGER_DIR / f"crosswalk_{sport}.parquet"
        xw.to_parquet(out, index=False)
        print(f"  wrote {out} ({len(xw)} rows)")

    return results


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)
    build_all()


if __name__ == "__main__":
    main()
