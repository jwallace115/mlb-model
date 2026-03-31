#!/usr/bin/env python3
"""
MLB Opening Lines Pull — 10PM Nightly
======================================
Pulls tomorrow's MLB totals lines from The Odds API and stores as OPEN snapshots.
Designed to run via launchd at 10:00 PM nightly.
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("pull_opening_lines")


def main():
    from config import ODDS_API_KEY, ODDS_API_BASE, ODDS_BOOKMAKERS
    import requests

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    logger.info(f"Pulling opening lines for {tomorrow}")

    url = f"{ODDS_API_BASE}/sports/baseball_mlb/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "totals",
        "bookmakers": ",".join(ODDS_BOOKMAKERS),
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info(f"API response: {resp.status_code} | quota remaining={remaining}")
        resp.raise_for_status()
        games = resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch lines: {e}")
        return

    if not games:
        logger.info("No games returned — season may not be active or no lines posted yet.")
        return

    # Filter to tomorrow's games only
    tomorrow_games = []
    for g in games:
        commence = g.get("commence_time", "")
        if commence.startswith(tomorrow):
            tomorrow_games.append(g)

    # Also include games that start after midnight (early morning ET = same slate)
    day_after = (date.today() + timedelta(days=2)).isoformat()
    for g in games:
        commence = g.get("commence_time", "")
        # Games starting between midnight and 6AM ET on day_after are part of tomorrow's slate
        if commence.startswith(day_after) and commence[11:13] < "10":  # before 10 UTC = before 6AM ET
            tomorrow_games.append(g)

    logger.info(f"Total games from API: {len(games)}, tomorrow's slate: {len(tomorrow_games)}")

    if not tomorrow_games:
        logger.info(f"No lines available for {tomorrow} yet. Will retry at 7AM.")
        return

    from mlb_sim.pipeline.line_snapshot_store import store_snapshots_from_odds_response
    stored, skipped, no_line = store_snapshots_from_odds_response(
        tomorrow_games, "OPEN", tomorrow)

    logger.info(f"Opening lines: stored={stored}, skipped={skipped}, no_line={no_line}")

    # Push snapshot to GitHub so Streamlit site reflects opening lines
    if stored > 0:
        try:
            import subprocess
            snap_file = str(PROJECT_ROOT / "mlb_sim" / "data" / "line_snapshots_2026.json")
            subprocess.run(["git", "add", snap_file], cwd=str(PROJECT_ROOT), check=True)
            subprocess.run(
                ["git", "commit", "-m", f"chore: opening line snapshot {tomorrow}"],
                cwd=str(PROJECT_ROOT), check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=str(PROJECT_ROOT), check=True)
            logger.info("Pushed opening line snapshot to GitHub.")
        except Exception as e:
            logger.warning(f"Git push failed (non-fatal): {e}")


if __name__ == "__main__":
    main()
