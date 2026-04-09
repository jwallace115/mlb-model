#!/usr/bin/env python3
"""
Daily Team Total Line Pull — Odds API
=======================================
Pulls posted home/away team total lines for today's MLB games.
Appends to mlb_sim/data/team_totals_2026.json (never overwrites).

Runs daily at 11:30 UTC (7:30 AM ET) after the MLB confirm pass.

Usage:
  python3 mlb/pipeline/pull_team_totals.py
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pull_team_totals")

ODDS_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb"
TT_PATH = PROJECT_ROOT / "mlb_sim" / "data" / "team_totals_2026.json"


def pull_team_totals(game_date=None):
    """Pull team total lines for today's games."""
    if not ODDS_KEY:
        logger.error("ODDS_API_KEY not set")
        return []

    game_date = game_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # Get today's events
    try:
        r = requests.get(f"{ODDS_BASE}/events",
                         params={"apiKey": ODDS_KEY}, timeout=15)
        r.raise_for_status()
        events = r.json()
    except Exception as e:
        logger.error(f"Failed to fetch events: {e}")
        return []

    # Filter to today's games
    today_events = [e for e in events
                    if e.get("commence_time", "")[:10] == game_date
                    or (game_date == date.today().isoformat()
                        and e.get("commence_time", "")[:10] in
                        [game_date, (date.today()).isoformat()])]

    if not today_events:
        # Accept all events if date filtering is tricky with UTC
        today_events = events

    logger.info(f"Events found: {len(today_events)}")

    records = []
    for ev in today_events:
        eid = ev.get("id")
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        commence = ev.get("commence_time", "")

        try:
            r2 = requests.get(f"{ODDS_BASE}/events/{eid}/odds",
                              params={
                                  "apiKey": ODDS_KEY,
                                  "markets": "team_totals",
                                  "regions": "us",
                                  "oddsFormat": "american",
                              }, timeout=15)
            r2.raise_for_status()
            data = r2.json()
        except Exception as e:
            logger.warning(f"Failed to fetch odds for {away}@{home}: {e}")
            time.sleep(0.3)
            continue

        bookmakers = data.get("bookmakers", [])
        if not bookmakers:
            time.sleep(0.3)
            continue

        # Extract team totals from each book
        home_lines = []
        away_lines = []
        for bk in bookmakers:
            book = bk.get("key", "")
            for mkt in bk.get("markets", []):
                if mkt.get("key") != "team_totals":
                    continue
                for oc in mkt.get("outcomes", []):
                    desc = oc.get("description", "")
                    name = oc.get("name", "").lower()
                    point = oc.get("point")
                    price = oc.get("price")
                    if point is None:
                        continue
                    if desc == home and name == "over":
                        home_lines.append({"book": book, "line": float(point),
                                           "over_price": int(price) if price else None})
                    elif desc == home and name == "under":
                        for hl in home_lines:
                            if hl["book"] == book:
                                hl["under_price"] = int(price) if price else None
                    elif desc == away and name == "over":
                        away_lines.append({"book": book, "line": float(point),
                                           "over_price": int(price) if price else None})
                    elif desc == away and name == "under":
                        for al in away_lines:
                            if al["book"] == book:
                                al["under_price"] = int(price) if price else None

        if not home_lines and not away_lines:
            time.sleep(0.3)
            continue

        # Consensus line (median across books)
        home_consensus = round(float(sorted([h["line"] for h in home_lines])[len(home_lines) // 2]), 1) if home_lines else None
        away_consensus = round(float(sorted([a["line"] for a in away_lines])[len(away_lines) // 2]), 1) if away_lines else None

        records.append({
            "game_date": commence[:10] if commence else game_date,
            "event_id": eid,
            "home_team": home,
            "away_team": away,
            "commence_time": commence,
            "home_total_line": home_consensus,
            "away_total_line": away_consensus,
            "n_books": len(home_lines),
            "home_books": home_lines,
            "away_books": away_lines,
            "snapshot_time": now,
        })

        time.sleep(0.3)

    logger.info(f"Pulled team totals for {len(records)} games")
    return records


def save_records(records):
    """Append new records to team_totals JSON (dedup by event_id + snapshot window)."""
    existing = []
    if TT_PATH.exists():
        try:
            existing = json.loads(TT_PATH.read_text())
        except Exception:
            existing = []

    # Dedup: skip if same event_id already has a record from today
    existing_today = {r["event_id"] for r in existing
                      if r.get("game_date") == date.today().isoformat()}
    new = [r for r in records if r["event_id"] not in existing_today]

    if new:
        existing.extend(new)
        TT_PATH.parent.mkdir(parents=True, exist_ok=True)
        TT_PATH.write_text(json.dumps(existing, indent=2, default=str))
        logger.info(f"Saved {len(new)} new team total records ({len(existing)} total)")
    else:
        logger.info("No new records to save")


def main():
    logger.info(f"Team Total Pull — {datetime.now(timezone.utc).isoformat()}")
    records = pull_team_totals()
    if records:
        save_records(records)

    # Auto-push
    # Push handled by push_daemon.sh
    # subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
    #                  "Team total lines pull"], capture_output=True)


if __name__ == "__main__":
    main()
