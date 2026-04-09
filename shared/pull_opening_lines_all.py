#!/usr/bin/env python3
"""
Universal Line Snapshot Capture
================================
Pulls totals lines from The Odds API for MLB, NBA, NHL and saves
per-date snapshot files tagged by snapshot_type.

Usage:
  python3 shared/pull_opening_lines_all.py --snapshot_type open
  python3 shared/pull_opening_lines_all.py --snapshot_type midmorning
  python3 shared/pull_opening_lines_all.py --snapshot_type afternoon
  python3 shared/pull_opening_lines_all.py --snapshot_type preclosing
  python3 shared/pull_opening_lines_all.py --snapshot_type closing

Soccer excluded — lines posted 12-20 days ahead; polled by soccer pipeline.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("line_snapshots")

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
BOOKMAKERS = ["pinnacle", "draftkings", "fanduel"]

VALID_SNAPSHOTS = {"open", "midmorning", "afternoon", "preclosing", "closing"}

# US sports only — soccer excluded (lines posted weeks ahead)
SPORTS = {
    "MLB": {
        "sport_key": "baseball_mlb",
        "markets": "totals",
        "dir": PROJECT_ROOT / "mlb_sim" / "data",
        "prefix": "mlb_lines",
    },
    "NBA": {
        "sport_key": "basketball_nba",
        "markets": "totals",
        "dir": PROJECT_ROOT / "nba" / "data",
        "prefix": "nba_lines",
    },
    "NHL": {
        "sport_key": "icehockey_nhl",
        "markets": "totals",
        "dir": PROJECT_ROOT / "nhl" / "data",
        "prefix": "nhl_lines",
    },
}


def _output_path(cfg, snapshot_type, target_date):
    """Build output path: {dir}/{prefix}_{snapshot_type}_{date}.json"""
    d = target_date.replace("-", "_")
    return cfg["dir"] / f"{cfg['prefix']}_{snapshot_type}_{d}.json"


def _load_existing(path):
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def _save(path, records):
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


def pull_sport(sport_label, sport_cfg, snapshot_type, target_date):
    """Pull lines for a single sport and save to per-date file."""
    import requests

    sport_key = sport_cfg["sport_key"]
    markets = sport_cfg["markets"]
    output_path = _output_path(sport_cfg, snapshot_type, target_date)

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
        if resp.status_code == 422:
            logger.info(f"  {sport_label}: no events available (422)")
            return 0, None
        resp.raise_for_status()
        games = resp.json()
    except Exception as e:
        logger.warning(f"  {sport_label}: API error — {e}")
        return 0, None

    if not games:
        logger.info(f"  {sport_label}: no games returned")
        return 0, None

    # Filter to target_date and next day (early morning games)
    next_day = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
    today_games = []
    for g in games:
        ct = g.get("commence_time", "")
        if ct.startswith(target_date) or ct.startswith(next_day):
            today_games.append(g)

    if not today_games:
        logger.info(f"  {sport_label}: {len(games)} total, 0 for {target_date}")
        return 0, None

    # Build snapshot records
    records = _load_existing(output_path)
    stored = 0
    ts = datetime.now(timezone.utc).isoformat()

    for g in today_games:
        game_id = g.get("id", "")
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        commence = g.get("commence_time", "")

        # Check for duplicate (same game_id + snapshot_type)
        exists = any(r.get("game_id") == game_id and r.get("snapshot_type") == snapshot_type
                     for r in records)
        if exists:
            continue

        line, over_price, under_price, book = _extract_totals(g, BOOKMAKERS)
        if line is None:
            continue

        records.append({
            "game_id": game_id,
            "game_date": target_date,
            "sport": sport_label,
            "home_team": home,
            "away_team": away,
            "commence_time": commence,
            "snapshot_type": snapshot_type,
            "total_line": line,
            "over_price": over_price,
            "under_price": under_price,
            "book": book,
            "capture_timestamp": ts,
        })
        stored += 1

    _save(output_path, records)
    logger.info(f"  {sport_label}: {len(today_games)} games, {stored} new {snapshot_type} snapshots")
    return stored, str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Universal Line Snapshot Capture")
    parser.add_argument("--snapshot_type", required=True, choices=sorted(VALID_SNAPSHOTS),
                        help="Snapshot label: open, midmorning, afternoon, preclosing, closing")
    args = parser.parse_args()

    snapshot_type = args.snapshot_type

    if not ODDS_API_KEY:
        logger.error("ODDS_API_KEY not set — aborting")
        return

    # For 'open' snapshot, target tomorrow; for all others, target today
    if snapshot_type == "open":
        target_date = (date.today() + timedelta(days=1)).isoformat()
    else:
        target_date = date.today().isoformat()

    logger.info(f"Line snapshot capture: type={snapshot_type}, date={target_date}")

    total_stored = 0
    files_changed = set()

    for label, cfg in SPORTS.items():
        n, fpath = pull_sport(label, cfg, snapshot_type, target_date)
        total_stored += n
        if n > 0 and fpath:
            files_changed.add(fpath)

    logger.info(f"Total snapshots stored: {total_stored}")

    # Commit and push if anything changed
    if files_changed:
        try:
            for f in files_changed:
                subprocess.run(["git", "add", "-f", f], cwd=str(PROJECT_ROOT), check=True)
            subprocess.run(
                ["git", "commit", "-m", f"lines({snapshot_type}): {target_date}"],
                cwd=str(PROJECT_ROOT), check=True)
            # Push handled by push_daemon.sh
            # subprocess.run(["git", "push", "origin", "main"],
            #                cwd=str(PROJECT_ROOT), check=True)
            logger.info("Line snapshots committed — push_daemon will push")
        except Exception as e:
            logger.warning(f"Git push failed (non-fatal): {e}")
    else:
        logger.info("No new snapshots — nothing to push")


if __name__ == "__main__":
    main()
