#!/usr/bin/env python3
"""
NRFI Daily Selector — Frozen V1
================================
Selects top 3 NRFI candidates from today's MLB slate.

Frozen rules (do not modify without full revalidation):
  QUALIFY:     F5 closing total <= 4.0
  DISQUALIFY:  night game AND F5 = 4.0 exactly
  RANK:        F5 total ascending -> start time ascending -> matchup alphabetical
  CARD:        Top 3

object_id: mlb_nrfi_selector_v1_20260411
ruleset_version: frozen_v1
"""

import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TRACKER_PATH = PROJECT_ROOT / "mlb" / "logs" / "nrfi_selector_v1_2026.json"
F5_PATH = PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_lines_2026.parquet"

OBJECT_ID = "mlb_nrfi_selector_v1_20260411"
RULESET_VERSION = "frozen_v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("nrfi_selector")


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_f5_lines(game_date: str) -> dict:
    """Load canonical F5 closing totals for the given date.

    Returns dict: game_id (str) -> f5_total (float).
    """
    if not F5_PATH.exists():
        logger.warning("F5 file not found: %s", F5_PATH)
        return {}
    f5 = pd.read_parquet(F5_PATH)
    today = f5[(f5["date"] == game_date) & (f5["is_canonical"] == True)]
    out = {}
    for _, r in today.iterrows():
        gid = str(r["game_id"])
        val = r.get("f5_total")
        if pd.notna(val):
            out[gid] = float(val)
    logger.info("Loaded %d canonical F5 lines for %s", len(out), game_date)
    return out


def load_schedule(game_date: str) -> list[dict]:
    """Load today's MLB schedule from the Stats API.

    Returns list of dicts with game_pk, teams, time, day/night.
    """
    from shared.retry_utils import retry_request
    url = "https://statsapi.mlb.com/api/v1/schedule"

    def _fetch_schedule():
        resp = requests.get(url, params={"sportId": 1, "date": game_date, "hydrate": "team"},
                            timeout=15)
        resp.raise_for_status()
        return resp.json()

    data = retry_request(_fetch_schedule, max_retries=2, base_wait=15, label="MLB schedule")
    raw_games = data.get("dates", [{}])[0].get("games", [])
    games = []
    for g in raw_games:
        home = g["teams"]["home"]["team"]
        away = g["teams"]["away"]["team"]
        game_time_utc = g.get("gameDate", "")
        # Parse hour from UTC time for sorting
        hour_utc = 0
        if len(game_time_utc) >= 16:
            try:
                hour_utc = int(game_time_utc[11:13]) * 60 + int(game_time_utc[14:16])
            except ValueError:
                pass
        games.append({
            "game_pk": str(g["gamePk"]),
            "home_team_api": home.get("abbreviation", "?"),
            "away_team_api": away.get("abbreviation", "?"),
            "home_team_name": home.get("name", "?"),
            "away_team_name": away.get("name", "?"),
            "game_time_utc": game_time_utc,
            "sort_minutes_utc": hour_utc,
            "day_night": g.get("dayNight", "unknown"),
            "is_night": g.get("dayNight", "").lower() == "night",
            "status": g.get("status", {}).get("detailedState", ""),
        })
    logger.info("Loaded %d games from schedule for %s", len(games), game_date)
    return games


def fetch_first_inning(game_pk: str) -> dict | None:
    """Fetch first-inning runs from the live feed.

    Returns {"away_runs": int, "home_runs": int, "nrfi": bool} or None.
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        innings = r.json().get("liveData", {}).get("linescore", {}).get("innings", [])
        if not innings:
            return None
        i1 = innings[0]
        ar = i1.get("away", {}).get("runs", 0)
        hr = i1.get("home", {}).get("runs", 0)
        return {"away_runs": ar, "home_runs": hr, "nrfi": ar == 0 and hr == 0}
    except Exception as e:
        logger.warning("Failed to fetch linescore for %s: %s", game_pk, e)
        return None


# ---------------------------------------------------------------------------
# Selector engine
# ---------------------------------------------------------------------------

def run_selector(game_date: str | None = None) -> list[dict]:
    """Run the frozen NRFI selector for a given date."""
    game_date = game_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # Load inputs
    f5_map = load_f5_lines(game_date)
    schedule = load_schedule(game_date)

    if not schedule:
        print(f"No games scheduled for {game_date}")
        return []

    if not f5_map:
        print(f"No F5 lines available for {game_date} — cannot run selector")
        return []

    # Merge F5 into schedule; use F5 team names where available
    f5_df = pd.read_parquet(F5_PATH)
    f5_today = f5_df[(f5_df["date"] == game_date) & (f5_df["is_canonical"] == True)]
    f5_teams = {}
    for _, r in f5_today.iterrows():
        f5_teams[str(r["game_id"])] = {
            "home_team": r["home_team"],
            "away_team": r["away_team"],
        }

    # Build candidate list
    candidates = []
    for g in schedule:
        gpk = g["game_pk"]
        f5 = f5_map.get(gpk)

        # Use F5 team abbreviations if available (consistent with model)
        teams = f5_teams.get(gpk, {})
        home = teams.get("home_team", g["home_team_api"])
        away = teams.get("away_team", g["away_team_api"])
        matchup = f"{away} @ {home}"

        candidates.append({
            "game_pk": gpk,
            "home_team": home,
            "away_team": away,
            "matchup": matchup,
            "game_time_utc": g["game_time_utc"],
            "sort_minutes_utc": g["sort_minutes_utc"],
            "day_night": g["day_night"],
            "is_night": g["is_night"],
            "f5_total": f5,
            "qualified": f5 is not None and f5 <= 4.0,
            "disqualified": False,
            "disqualifier_reason": None,
            "status": g["status"],
        })

    # Apply disqualifier: night AND F5 = 4.0 exactly
    for c in candidates:
        if c["qualified"] and c["is_night"] and c["f5_total"] == 4.0:
            c["qualified"] = False
            c["disqualified"] = True
            c["disqualifier_reason"] = "night_and_f5_4.0"

    # Rank qualified candidates: F5 asc -> time asc -> matchup alpha
    qualified = [c for c in candidates if c["qualified"]]
    qualified.sort(key=lambda x: (x["f5_total"], x["sort_minutes_utc"], x["matchup"]))

    for i, c in enumerate(qualified):
        c["selector_rank"] = i + 1
        c["selected_top3"] = i < 3
        c["selected_top4"] = i < 4

    # Output
    top3 = [c for c in qualified if c["selected_top3"]]
    alt = qualified[3] if len(qualified) > 3 else None
    not_qual = [c for c in candidates if not c["qualified"] and not c["disqualified"]]
    disqual = [c for c in candidates if c["disqualified"]]

    print()
    print("=" * 55)
    print(f"  NRFI SELECTOR v1 — {game_date}")
    print("=" * 55)
    print(f"  Slate:         {len(schedule)} games")
    print(f"  F5 lines:      {len(f5_map)} available")
    print(f"  Qualified:     {len(qualified)}")
    print(f"  Disqualified:  {len(disqual)}")
    print(f"  No F5/above:   {len(not_qual)}")
    print()
    if top3:
        print("  TOP 3 NRFI CARD:")
        for c in top3:
            dn = "D" if not c["is_night"] else "N"
            print(f"    #{c['selector_rank']:d}  {c['matchup']:<18s}  F5={c['f5_total']:.1f}  [{dn}]")
    else:
        print("  NO QUALIFYING GAMES")
    if alt:
        dn = "D" if not alt["is_night"] else "N"
        print(f"\n  ALT  {alt['matchup']:<18s}  F5={alt['f5_total']:.1f}  [{dn}]")
    if disqual:
        print(f"\n  DISQUALIFIED:")
        for c in disqual:
            print(f"    {c['matchup']:<18s}  F5={c['f5_total']:.1f}  reason={c['disqualifier_reason']}")
    print()

    # Log to tracker
    _log_to_tracker(game_date, candidates, now)

    return qualified


# ---------------------------------------------------------------------------
# Tracker I/O
# ---------------------------------------------------------------------------

def _load_tracker() -> dict:
    """Load or initialize the tracker file."""
    default = {
        "object_id": OBJECT_ID,
        "ruleset_version": RULESET_VERSION,
        "start_date": "2026-04-11",
        "selections": [],
    }
    if TRACKER_PATH.exists():
        try:
            return json.loads(TRACKER_PATH.read_text())
        except Exception:
            pass
    return default


def _save_tracker(tracker: dict) -> None:
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_PATH.write_text(json.dumps(tracker, indent=2, default=str))


def _log_to_tracker(game_date: str, candidates: list[dict], now: str) -> None:
    """Append today's selection to tracker JSON (idempotent per date)."""
    tracker = _load_tracker()

    # Dedup by date
    existing_dates = {s["run_date"] for s in tracker.get("selections", [])}
    if game_date in existing_dates:
        logger.info("Date %s already in tracker — skipping", game_date)
        return

    for c in candidates:
        tracker["selections"].append({
            "run_date": game_date,
            "game_pk": c["game_pk"],
            "home_team": c["home_team"],
            "away_team": c["away_team"],
            "matchup": c["matchup"],
            "game_time_utc": c["game_time_utc"],
            "day_night": c["day_night"],
            "is_night": c["is_night"],
            "f5_total": c["f5_total"],
            "qualified": c["qualified"],
            "disqualified": c.get("disqualified", False),
            "disqualifier_reason": c.get("disqualifier_reason"),
            "selector_rank": c.get("selector_rank"),
            "selected_top3": c.get("selected_top3", False),
            "selected_top4": c.get("selected_top4", False),
            "nrfi_result": None,
            "first_inning_away": None,
            "first_inning_home": None,
            "win_loss": None,
            "object_id": OBJECT_ID,
            "ruleset_version": RULESET_VERSION,
            "logged_at": now,
        })

    _save_tracker(tracker)
    logger.info("Logged %d candidates for %s", len(candidates), game_date)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def grade_selector(game_date: str | None = None) -> None:
    """Grade prior NRFI selections using MLB API linescore.

    If game_date is provided, grades that date only.
    Otherwise grades all ungraded dates before today.
    """
    tracker = _load_tracker()
    today = date.today().isoformat()

    to_grade = []
    for s in tracker["selections"]:
        if s.get("nrfi_result") is not None:
            continue
        if game_date:
            if s["run_date"] == game_date:
                to_grade.append(s)
        else:
            if s["run_date"] < today:
                to_grade.append(s)

    if not to_grade:
        print("Nothing to grade.")
        return

    # Group by game_pk to avoid duplicate API calls
    seen = {}
    for s in to_grade:
        gpk = s["game_pk"]
        if gpk not in seen:
            result = fetch_first_inning(gpk)
            seen[gpk] = result

        result = seen[gpk]
        if result is not None:
            s["first_inning_away"] = result["away_runs"]
            s["first_inning_home"] = result["home_runs"]
            s["nrfi_result"] = result["nrfi"]
            if s.get("selected_top3"):
                s["win_loss"] = "W" if result["nrfi"] else "L"

    _save_tracker(tracker)

    # Print grading summary
    graded_top3 = [s for s in tracker["selections"]
                   if s.get("selected_top3") and s.get("nrfi_result") is not None]
    wins = sum(1 for s in graded_top3 if s["win_loss"] == "W")
    losses = sum(1 for s in graded_top3 if s["win_loss"] == "L")

    dates_graded = sorted(set(s["run_date"] for s in to_grade if s.get("nrfi_result") is not None))

    print()
    print("=" * 55)
    print("  NRFI GRADING REPORT")
    print("=" * 55)
    for d in dates_graded:
        day_sel = [s for s in tracker["selections"]
                   if s["run_date"] == d and s.get("selected_top3") and s.get("nrfi_result") is not None]
        day_w = sum(1 for s in day_sel if s["win_loss"] == "W")
        day_l = sum(1 for s in day_sel if s["win_loss"] == "L")
        print(f"\n  {d}  ({day_w}-{day_l})")
        for s in day_sel:
            res = "NRFI" if s["nrfi_result"] else f"YRFI ({s['first_inning_away']}-{s['first_inning_home']})"
            print(f"    #{s.get('selector_rank','?')}  {s['matchup']:<18s}  F5={s['f5_total']:.1f}  {res}  {s['win_loss']}")

    print(f"\n  SEASON RECORD (top-3): {wins}-{losses}")
    if wins + losses > 0:
        print(f"  Hit rate: {wins/(wins+losses)*100:.1f}%")
    print()


# ---------------------------------------------------------------------------
# Season summary
# ---------------------------------------------------------------------------

def print_summary() -> None:
    """Print cumulative season summary from tracker."""
    tracker = _load_tracker()
    sel = tracker["selections"]
    graded_top3 = [s for s in sel if s.get("selected_top3") and s.get("nrfi_result") is not None]
    wins = sum(1 for s in graded_top3 if s["win_loss"] == "W")
    losses = sum(1 for s in graded_top3 if s["win_loss"] == "L")
    dates = sorted(set(s["run_date"] for s in sel))

    print()
    print("=" * 55)
    print("  NRFI SELECTOR v1 — SEASON SUMMARY")
    print("=" * 55)
    print(f"  Dates logged:  {len(dates)}")
    print(f"  Graded picks:  {len(graded_top3)}")
    print(f"  Record:        {wins}-{losses}")
    if wins + losses > 0:
        print(f"  Hit rate:      {wins/(wins+losses)*100:.1f}%")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NRFI Daily Selector (Frozen V1)")
    parser.add_argument("--date", default=None, help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--grade", action="store_true", help="Grade prior selections")
    parser.add_argument("--summary", action="store_true", help="Print season summary")
    args = parser.parse_args()

    if args.summary:
        print_summary()
    elif args.grade:
        grade_selector(args.date)
    else:
        run_selector(args.date)
