#!/usr/bin/env python3
"""
Daily YRFI/NRFI Odds Pull — Odds API
======================================
Pulls FanDuel first-inning run lines (YRFI Over 0.5 / NRFI Under 0.5)
for today's MLB games using the totals_1st_1_innings market.

Uses the event-level odds endpoint (per-event query) because the batch
/odds endpoint does not support the totals_1st_1_innings market.

Output: mlb/logs/yrfi_odds_2026.json (append, dedup by game_id+pull_date+bookmaker).

Usage:
  python3 mlb/pipeline/pull_yrfi_odds_daily.py
"""

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

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pull_yrfi_odds")

ODDS_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb"
LOG_PATH = PROJECT_ROOT / "mlb" / "logs" / "yrfi_odds_2026.json"


def _load_log():
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except Exception:
            return []
    return []


def _save_log(records):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(records, indent=2, default=str))


def pull_yrfi_odds():
    if not ODDS_KEY:
        logger.error("ODDS_API_KEY not set")
        sys.exit(1)

    pull_date = date.today().isoformat()
    pull_ts = datetime.now(timezone.utc).isoformat()

    # Step 1: fetch today's MLB events (1 credit)
    try:
        r = requests.get(
            f"{ODDS_BASE}/events",
            params={"apiKey": ODDS_KEY},
            timeout=15,
        )
        r.raise_for_status()
        events = r.json()
    except Exception as e:
        logger.error(f"Failed to fetch MLB events: {e}")
        sys.exit(1)

    remaining = r.headers.get("x-requests-remaining", "?")
    logger.info(f"MLB events: {len(events)}, API credits remaining: {remaining}")

    if not events:
        logger.warning("No MLB events returned")
        return

    # Step 2: for each event, fetch first-inning odds (1 credit each)
    new_records = []

    for ev in events:
        event_id = ev.get("id", "")
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        commence = ev.get("commence_time", "")

        try:
            r2 = requests.get(
                f"{ODDS_BASE}/events/{event_id}/odds",
                params={
                    "apiKey": ODDS_KEY,
                    "markets": "totals_1st_1_innings",
                    "regions": "us",
                    "oddsFormat": "american",
                },
                timeout=15,
            )
            r2.raise_for_status()
            data = r2.json()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:
                logger.debug(f"  {away}@{home}: market not available (422)")
            else:
                logger.warning(f"  {away}@{home}: HTTP error {e}")
            time.sleep(0.3)
            continue
        except Exception as e:
            logger.warning(f"  {away}@{home}: request failed: {e}")
            time.sleep(0.3)
            continue

        bookmakers = data.get("bookmakers", [])
        if not bookmakers:
            time.sleep(0.3)
            continue

        # Extract FanDuel first; fall back to first available book
        fd_bk = next((bk for bk in bookmakers if bk.get("key") == "fanduel"), None)
        chosen_bk = fd_bk or bookmakers[0]
        book_key = chosen_bk.get("key", "")

        for mkt in chosen_bk.get("markets", []):
            if mkt.get("key") != "totals_1st_1_innings":
                continue

            outcomes = mkt.get("outcomes", [])
            yrfi_price = None
            nrfi_price = None
            yrfi_point = None
            nrfi_point = None

            for oc in outcomes:
                pt = oc.get("point")
                name = oc.get("name", "").lower()
                price = oc.get("price")
                if pt != 0.5:
                    continue
                if name == "over":
                    yrfi_price = price
                    yrfi_point = pt
                elif name == "under":
                    nrfi_price = price
                    nrfi_point = pt

            if yrfi_price is None and nrfi_price is None:
                continue

            new_records.append({
                "pull_timestamp": pull_ts,
                "pull_date": pull_date,
                "game_id": event_id,
                "commence_time": commence,
                "home_team": home,
                "away_team": away,
                "bookmaker": book_key,
                "market": "totals_1st_1_innings",
                "yrfi_price": yrfi_price,
                "nrfi_price": nrfi_price,
                "yrfi_point": yrfi_point,
                "nrfi_point": nrfi_point,
                "raw_outcomes": outcomes,
            })

        time.sleep(0.3)

    remaining_after = r2.headers.get("x-requests-remaining", "?") if 'r2' in dir() else "?"
    logger.info(f"API credits remaining after pulls: {remaining_after}")

    if not new_records:
        logger.warning("MARKET_NOT_AVAILABLE — no first-inning lines found")
        logger.info(f"  (queried {len(events)} events, none had totals_1st_1_innings)")
        return

    logger.info(f"YRFI records extracted: {len(new_records)}")

    # Load existing log and dedup
    existing = _load_log()

    # Remove same-day duplicates (replace with new pull)
    new_keys = {
        (r["game_id"], r["pull_date"], r["bookmaker"], r["market"])
        for r in new_records
    }
    existing = [r for r in existing
                if (r["game_id"], r["pull_date"], r["bookmaker"], r["market"])
                not in new_keys]

    combined = existing + new_records
    _save_log(combined)

    logger.info(f"Log saved: {len(combined)} total records ({len(new_records)} new today)")

    for rec in new_records[:3]:
        logger.info(
            f"  {rec['away_team']}@{rec['home_team']} "
            f"YRFI={rec['yrfi_price']} NRFI={rec['nrfi_price']} "
            f"book={rec['bookmaker']}"
        )


if __name__ == "__main__":
    pull_yrfi_odds()
