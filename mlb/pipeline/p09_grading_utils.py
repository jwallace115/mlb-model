#!/usr/bin/env python3
"""
P09 Shadow Grading Utility
============================
Grades fired P09 UNDER shadow signals after MLB games reach final status.
Reads mlb/logs/p09_shadow_2026.json, grades eligible rows, writes back.

Shadow-only. No live betting. No promotion. No V1 dependency.

Usage:
  python3 mlb/pipeline/p09_grading_utils.py --dry-run
  python3 mlb/pipeline/p09_grading_utils.py --date 2026-05-10 --dry-run
  python3 mlb/pipeline/p09_grading_utils.py                    # production grade
  python3 mlb/pipeline/p09_grading_utils.py --force             # re-grade already graded
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("p09_grading")

SHADOW_LOG = PROJECT_ROOT / "mlb" / "logs" / "p09_shadow_2026.json"
FINAL_STATUS_CODES = {"F"}


def _load_shadow_log():
    """Load P09 shadow log."""
    if not SHADOW_LOG.exists():
        return None
    try:
        return json.loads(SHADOW_LOG.read_text())
    except Exception:
        return []


def _save_shadow_log(entries):
    """Save P09 shadow log."""
    SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
    SHADOW_LOG.write_text(json.dumps(entries, indent=2, default=str))


def _get_final_score(game_pk, sleep_secs=0.3):
    """
    Fetch final score from MLB Stats API linescore.
    Returns (away_score, home_score, status_str) or (None, None, error_str).
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        time.sleep(sleep_secs)
    except Exception as e:
        return None, None, f"API_ERROR:{str(e)[:40]}"

    data = resp.json()
    status_code = data.get("gameData", {}).get("status", {}).get("statusCode", "")
    if status_code not in FINAL_STATUS_CODES:
        return None, None, f"NOT_FINAL:{status_code}"

    linescore = data.get("liveData", {}).get("linescore", {})
    teams = linescore.get("teams", {})
    away_runs = teams.get("away", {}).get("runs")
    home_runs = teams.get("home", {}).get("runs")

    if away_runs is None or home_runs is None:
        return None, None, "MISSING_RUN_DATA"

    return int(away_runs), int(home_runs), "OK"


def _get_schedule_status(game_date_str, home_team, away_team, sleep_secs=0.3):
    """
    Check game status via schedule API. Returns (game_pk, status_code) or (None, None).
    """
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": game_date_str,
        "fields": "dates,date,games,gamePk,teams,home,away,team,name,status,statusCode",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        time.sleep(sleep_secs)
    except Exception:
        return None, None

    _ABB_TO_FULL = {
        "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves",
        "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox",
        "CHC": "Chicago Cubs", "CHW": "Chicago White Sox",
        "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians",
        "COL": "Colorado Rockies", "DET": "Detroit Tigers",
        "HOU": "Houston Astros", "KCR": "Kansas City Royals",
        "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
        "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers",
        "MIN": "Minnesota Twins", "NYM": "New York Mets",
        "NYY": "New York Yankees", "OAK": "Athletics",
        "PHI": "Philadelphia Phillies", "PIT": "Pittsburgh Pirates",
        "SDP": "San Diego Padres", "SFG": "San Francisco Giants",
        "SEA": "Seattle Mariners", "STL": "St. Louis Cardinals",
        "TBR": "Tampa Bay Rays", "TEX": "Texas Rangers",
        "TOR": "Toronto Blue Jays", "WSN": "Washington Nationals",
    }

    home_full = _ABB_TO_FULL.get(home_team, home_team).lower().replace(" ", "")
    away_full = _ABB_TO_FULL.get(away_team, away_team).lower().replace(" ", "")

    for date_block in resp.json().get("dates", []):
        for game in date_block.get("games", []):
            g_home = game["teams"]["home"]["team"]["name"].lower().replace(" ", "")
            g_away = game["teams"]["away"]["team"]["name"].lower().replace(" ", "")
            if g_home == home_full and g_away == away_full:
                return game["gamePk"], game.get("status", {}).get("statusCode", "")

    return None, None


def compute_profit(result, price_under):
    """
    Compute profit in units for a 1-unit risk UNDER bet.
    result: "WIN" / "LOSS" / "PUSH"
    price_under: American odds integer
    """
    if price_under is None or result is None:
        return None
    if result == "WIN":
        if price_under > 0:
            return round(price_under / 100, 4)
        else:
            return round(100 / abs(price_under), 4)
    elif result == "LOSS":
        return -1.0
    elif result == "PUSH":
        return 0.0
    return None


def grade_entry(entry, force=False, sleep_secs=0.3):
    """
    Grade one P09 shadow log entry. Returns (entry, grading_status).

    Grading-status precedence (first match wins):
    1. DRAFTKINGS_MISSING → NO_DRAFTKINGS_MARKET
    2. signal_fired=false → NO_SIGNAL
    3. selected_side=null → NO_SELECTED_SIDE
    4. market_total=null → MARKET_TOTAL_MISSING
    5. game not final → GAME_NOT_FINAL
    6. final score lookup failed → FINAL_SCORE_MISSING
    7. price_under=null → PRICE_UNDER_MISSING
    8. all pass → GRADED
    """
    # Already graded (skip unless force)
    if entry.get("graded") is True and not force:
        return entry, "ALREADY_GRADED"

    # 1. DraftKings missing
    if entry.get("market_status") == "DRAFTKINGS_MISSING":
        entry["grading_status"] = "NO_DRAFTKINGS_MARKET"
        return entry, "NO_DRAFTKINGS_MARKET"

    # 2. No signal fired
    if not entry.get("signal_fired"):
        entry["grading_status"] = "NO_SIGNAL"
        return entry, "NO_SIGNAL"

    # 3. No selected side
    if entry.get("selected_side") is None:
        entry["grading_status"] = "NO_SELECTED_SIDE"
        return entry, "NO_SELECTED_SIDE"

    # 4. Market total missing
    if entry.get("market_total") is None:
        entry["grading_status"] = "MARKET_TOTAL_MISSING"
        return entry, "MARKET_TOTAL_MISSING"

    game_date = entry.get("date", "")
    home_team = entry.get("home_team", "")
    away_team = entry.get("away_team", "")

    # Don't grade future games
    try:
        game_dt = datetime.strptime(game_date, "%Y-%m-%d").date()
        if game_dt >= date.today():
            entry["grading_status"] = "GAME_NOT_FINAL"
            return entry, "GAME_NOT_FINAL"
    except ValueError:
        entry["grading_status"] = "GAME_NOT_FINAL"
        return entry, "GAME_NOT_FINAL"

    # 5. Check game final status + get score
    game_pk = entry.get("game_id")

    # Try direct game_pk first if it looks like an MLB game_pk
    away_score, home_score, fetch_status = None, None, None
    if game_pk and game_pk.isdigit():
        away_score, home_score, fetch_status = _get_final_score(int(game_pk), sleep_secs)

    # Fallback: schedule lookup
    if fetch_status is None or (fetch_status and fetch_status.startswith("NOT_FINAL")):
        sched_pk, sched_status = _get_schedule_status(game_date, home_team, away_team, sleep_secs)
        if sched_pk and sched_status in FINAL_STATUS_CODES:
            away_score, home_score, fetch_status = _get_final_score(sched_pk, sleep_secs)
            if fetch_status == "OK":
                game_pk = str(sched_pk)
        elif sched_status and sched_status not in FINAL_STATUS_CODES:
            entry["grading_status"] = "GAME_NOT_FINAL"
            return entry, "GAME_NOT_FINAL"

    if fetch_status != "OK":
        entry["grading_status"] = "FINAL_SCORE_MISSING"
        return entry, "FINAL_SCORE_MISSING"

    # 7. Price under missing
    price_under = entry.get("price_under")
    if price_under is None:
        entry["grading_status"] = "PRICE_UNDER_MISSING"
        entry["actual_total"] = away_score + home_score
        entry["away_score"] = away_score
        entry["home_score"] = home_score
        return entry, "PRICE_UNDER_MISSING"

    # 8. All checks pass — grade
    actual_total = away_score + home_score
    market_total = entry["market_total"]

    if actual_total < market_total:
        result = "WIN"
    elif actual_total > market_total:
        result = "LOSS"
    else:
        result = "PUSH"

    profit_units = compute_profit(result, price_under)
    now = datetime.now(timezone.utc).isoformat()

    entry["graded"] = True
    entry["graded_at"] = now
    entry["updated_at"] = now
    entry["actual_total"] = actual_total
    entry["away_score"] = away_score
    entry["home_score"] = home_score
    entry["result"] = result
    entry["selected_price"] = price_under
    entry["profit_units"] = profit_units
    entry["grading_source"] = "mlb_statsapi_linescore"
    entry["grading_status"] = "GRADED"

    return entry, "GRADED"


def main():
    parser = argparse.ArgumentParser(description="P09 Shadow Grading Utility")
    parser.add_argument("--date", default=None,
                        help="Only grade rows for this date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be graded without modifying the log")
    parser.add_argument("--force", action="store_true",
                        help="Re-grade already graded rows")
    args = parser.parse_args()

    logger.info(f"P09 Grading Utility ({'DRY-RUN' if args.dry_run else 'PRODUCTION'})")

    entries = _load_shadow_log()
    if entries is None:
        print("P09 shadow log not found; nothing to grade.")
        return

    logger.info(f"Loaded {len(entries)} rows from shadow log")

    # Stats
    stats = {
        "total": len(entries),
        "fired": 0,
        "eligible": 0,
        "graded_now": 0,
        "already_graded": 0,
        "no_signal": 0,
        "game_not_final": 0,
        "dk_missing": 0,
        "price_missing": 0,
        "score_missing": 0,
        "no_selected_side": 0,
        "market_total_missing": 0,
    }

    for i, entry in enumerate(entries):
        # Date filter
        if args.date and entry.get("date") != args.date:
            continue

        if entry.get("signal_fired"):
            stats["fired"] += 1

        if (entry.get("signal_fired") and
                entry.get("selected_side") == "UNDER" and
                entry.get("market_total") is not None and
                entry.get("market_status") != "DRAFTKINGS_MISSING" and
                entry.get("price_under") is not None and
                not entry.get("graded")):
            stats["eligible"] += 1

        graded_entry, status = grade_entry(entry, force=args.force, sleep_secs=0.3)

        if status == "GRADED":
            stats["graded_now"] += 1
            if not args.dry_run:
                entries[i] = graded_entry
            logger.info(
                f"  {entry.get('away_team')}@{entry.get('home_team')} {entry.get('date')}: "
                f"actual={graded_entry.get('actual_total')} market={entry.get('market_total')} "
                f"result={graded_entry.get('result')} profit={graded_entry.get('profit_units')}"
            )
        elif status == "ALREADY_GRADED":
            stats["already_graded"] += 1
        elif status == "NO_SIGNAL":
            stats["no_signal"] += 1
        elif status == "GAME_NOT_FINAL":
            stats["game_not_final"] += 1
        elif status == "NO_DRAFTKINGS_MARKET":
            stats["dk_missing"] += 1
        elif status == "PRICE_UNDER_MISSING":
            stats["price_missing"] += 1
        elif status == "FINAL_SCORE_MISSING":
            stats["score_missing"] += 1
        elif status == "NO_SELECTED_SIDE":
            stats["no_selected_side"] += 1
        elif status == "MARKET_TOTAL_MISSING":
            stats["market_total_missing"] += 1

    if not args.dry_run and stats["graded_now"] > 0:
        _save_shadow_log(entries)
        logger.info(f"Saved {len(entries)} rows to shadow log")

    # Summary
    print(f"\n=== P09 GRADING {'DRY-RUN' if args.dry_run else 'RESULT'} ===\n")
    print(f"Rows loaded:           {stats['total']}")
    print(f"Fired rows:            {stats['fired']}")
    print(f"Eligible rows:         {stats['eligible']}")
    print(f"Graded now:            {stats['graded_now']}")
    print(f"Already graded:        {stats['already_graded']}")
    print(f"Skip — no signal:      {stats['no_signal']}")
    print(f"Skip — game not final: {stats['game_not_final']}")
    print(f"Skip — DK missing:     {stats['dk_missing']}")
    print(f"Skip — price missing:  {stats['price_missing']}")
    print(f"Skip — score missing:  {stats['score_missing']}")
    print(f"Skip — no side:        {stats['no_selected_side']}")
    print(f"Skip — no market:      {stats['market_total_missing']}")

    if args.dry_run:
        print("\nDry-run: no changes written to shadow log.")


if __name__ == "__main__":
    main()
