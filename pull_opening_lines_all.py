#!/usr/bin/env python3
"""
Universal Opening Line Capture — 2:05 AM ET Nightly
=====================================================
Pulls opening totals lines from The Odds API for all active sports
and saves tagged snapshots. Designed to run 5 minutes after results_tracker.

Sports: MLB, NBA, NHL, Soccer (EPL, Bundesliga, La Liga, Serie A, Ligue 1)
"""

import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("opening_lines_all")

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
BOOKMAKERS = ["pinnacle", "draftkings", "fanduel"]

# Sport keys → output files
SPORTS = {
    "MLB": {
        "sport_key": "baseball_mlb",
        "markets": "totals",
        "output": PROJECT_ROOT / "mlb_sim" / "data" / "line_snapshots_open_2026.json",
    },
    "NBA": {
        "sport_key": "basketball_nba",
        "markets": "totals",
        "output": PROJECT_ROOT / "nba" / "data" / "nba_lines_open_2026.json",
    },
    "NHL": {
        "sport_key": "icehockey_nhl",
        "markets": "totals",
        "output": PROJECT_ROOT / "nhl" / "data" / "nhl_lines_open_2026.json",
    },
    "soccer_EPL": {
        "sport_key": "soccer_epl",
        "markets": "totals",
        "output": PROJECT_ROOT / "soccer" / "data" / "soccer_lines_open_2026.json",
    },
    "soccer_BUN": {
        "sport_key": "soccer_germany_bundesliga",
        "markets": "totals",
        "output": PROJECT_ROOT / "soccer" / "data" / "soccer_lines_open_2026.json",
    },
    "soccer_LGA": {
        "sport_key": "soccer_spain_la_liga",
        "markets": "totals",
        "output": PROJECT_ROOT / "soccer" / "data" / "soccer_lines_open_2026.json",
    },
    "soccer_SEA": {
        "sport_key": "soccer_italy_serie_a",
        "markets": "totals",
        "output": PROJECT_ROOT / "soccer" / "data" / "soccer_lines_open_2026.json",
    },
    "soccer_LG1": {
        "sport_key": "soccer_france_ligue_one",
        "markets": "totals",
        "output": PROJECT_ROOT / "soccer" / "data" / "soccer_lines_open_2026.json",
    },
}


def _load_existing(path):
    """Load existing snapshot records from file."""
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def _save(path, records):
    """Save snapshot records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(records, f, indent=2)


def _extract_totals(game, bookmakers):
    """Extract best totals line from a game's bookmaker data."""
    best_line = None
    best_over = None
    best_under = None
    best_book = None

    for bm in game.get("bookmakers", []):
        bk = bm.get("key", "")
        if bookmakers and bk not in bookmakers:
            continue
        for mkt in bm.get("markets", []):
            if mkt.get("key") != "totals":
                continue
            for outcome in mkt.get("outcomes", []):
                if outcome.get("name") == "Over":
                    line = outcome.get("point")
                    price = outcome.get("price")
                    if line is not None:
                        best_line = line
                        best_over = price
                        best_book = bk
                elif outcome.get("name") == "Under":
                    best_under = outcome.get("price")

    return best_line, best_over, best_under, best_book


def pull_sport(sport_label, sport_cfg, target_date):
    """Pull opening lines for a single sport."""
    import requests

    sport_key = sport_cfg["sport_key"]
    markets = sport_cfg["markets"]
    output_path = sport_cfg["output"]

    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": markets,
        "bookmakers": ",".join(BOOKMAKERS),
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        remaining = resp.headers.get("x-requests-remaining", "?")
        if resp.status_code == 422:
            logger.info(f"  {sport_label}: no events available (422)")
            return 0
        resp.raise_for_status()
        games = resp.json()
    except Exception as e:
        logger.warning(f"  {sport_label}: API error — {e}")
        return 0

    if not games:
        logger.info(f"  {sport_label}: no games returned")
        return 0

    # Filter to target_date and next day (early morning games)
    next_day = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
    today_games = []
    for g in games:
        ct = g.get("commence_time", "")
        if ct.startswith(target_date) or ct.startswith(next_day):
            today_games.append(g)

    if not today_games:
        logger.info(f"  {sport_label}: {len(games)} total games, 0 for {target_date}")
        return 0

    # Build snapshot records
    records = _load_existing(output_path)
    stored = 0
    ts = datetime.utcnow().isoformat() + "Z"

    for g in today_games:
        game_id = g.get("id", "")
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        commence = g.get("commence_time", "")

        # Check for duplicate
        exists = any(r.get("game_id") == game_id and r.get("snapshot_type") == "open"
                     for r in records)
        if exists:
            continue

        line, over_price, under_price, book = _extract_totals(g, BOOKMAKERS)
        if line is None:
            continue

        records.append({
            "game_id": game_id,
            "game_date": target_date,
            "sport": sport_label.split("_")[0] if "_" in sport_label else sport_label,
            "league": sport_label,
            "home_team": home,
            "away_team": away,
            "commence_time": commence,
            "snapshot_type": "open",
            "total_line": line,
            "over_price": over_price,
            "under_price": under_price,
            "book": book,
            "capture_timestamp": ts,
        })
        stored += 1

    _save(output_path, records)
    logger.info(f"  {sport_label}: {len(today_games)} games, {stored} new snapshots")
    return stored


def main():
    if not ODDS_API_KEY:
        logger.error("ODDS_API_KEY not set — aborting")
        return

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    logger.info(f"Opening line capture for {tomorrow}")

    total_stored = 0
    files_changed = set()

    for label, cfg in SPORTS.items():
        n = pull_sport(label, cfg, tomorrow)
        total_stored += n
        if n > 0:
            files_changed.add(str(cfg["output"]))

    # Check remaining quota
    import requests
    try:
        r = requests.get(f"{ODDS_API_BASE}/sports/", params={"apiKey": ODDS_API_KEY}, timeout=10)
        remaining = r.headers.get("x-requests-remaining", "?")
        logger.info(f"Odds API quota remaining: {remaining}")
    except Exception:
        pass

    logger.info(f"Total snapshots stored: {total_stored}")

    # Commit and push if anything changed
    if files_changed:
        try:
            for f in files_changed:
                subprocess.run(["git", "add", "-f", f], cwd=str(PROJECT_ROOT), check=True)
            subprocess.run(
                ["git", "commit", "-m", f"opening lines: {tomorrow}"],
                cwd=str(PROJECT_ROOT), check=True)
            subprocess.run(["git", "push", "origin", "main"],
                           cwd=str(PROJECT_ROOT), check=True)
            logger.info("Pushed opening line snapshots to GitHub")
        except Exception as e:
            logger.warning(f"Git push failed (non-fatal): {e}")
    else:
        logger.info("No new snapshots — nothing to push")


if __name__ == "__main__":
    main()
