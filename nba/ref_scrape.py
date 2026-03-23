#!/usr/bin/env python3
"""
NBA Referee Crew Scraper — Board 5.

Fetches referee crew assignments for today's NBA games via BoxScoreSummaryV3,
classifies each game by crew_high_count (number of top-quartile scoring refs),
and writes results to nba/data/nba_ref_assignments.csv.

Intended to run at 6:30 PM daily (refs typically announced ~90 min pre-tip).
Does NOT re-run the full model — ref assignments only.

Usage:
    python nba/ref_scrape.py                # today
    python nba/ref_scrape.py 2026-03-23     # specific date
"""

import argparse
import csv
import logging
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

NBA_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(NBA_DIR, "data", "nba_ref_assignments.csv")

# ── Top-quartile referee list ─────────────────────────────────────────────────
# From research/ref_crew_aggregates.csv: refs with >= 30 prior games whose
# avg_total_points_per_game is in the top 25%.
# Threshold: >= 230.4 pts avg (computed from 2022-25 historical data).
# This list is static for the 2025-26 season and updated between seasons.

TOP_QUARTILE_REFS = {
    "Bill Kennedy",
    "CJ Washington",
    "Jason Goldenberg",
    "JD Ralls",
    "Lauren Holtkamp",
    "Mark Lindsay",
    "Matt Kallio",
    "Matt Myers",
    "Mitchell Ervin",
    "Phenizee Ransom",
    "Robert Hussey",
    "Scott Foster",
    "Scott Twardoski",
    "Sean Corbin",
    "Sean Wright",
    "Sha'Rae Mitchell",
    "Simone Jelks",
    "Tony Brothers",
    "Zach Zarba",
}


def fetch_ref_assignments(game_date: str) -> list[dict]:
    """Fetch referee assignments for all games on game_date."""
    from nba.modules.fetch_nba_schedule import fetch_today_schedule
    from nba.modules.fetch_games import _call_with_retry

    schedule = fetch_today_schedule(game_date)
    if not schedule:
        logger.warning(f"No NBA games scheduled for {game_date}")
        return []

    logger.info(f"Fetching referee data for {len(schedule)} games on {game_date}")

    results = []
    for sched in schedule:
        gid = sched["game_id"]
        home = sched["home_team"]
        away = sched["away_team"]

        refs = []
        try:
            from nba_api.stats.endpoints import BoxScoreSummaryV2
            bs = _call_with_retry(
                BoxScoreSummaryV2,
                game_id=gid,
                timeout=15,
            )
            dfs = bs.get_data_frames()
            # Table 2 = Officials
            if len(dfs) > 2 and len(dfs[2]) > 0:
                for _, row in dfs[2].iterrows():
                    first = row.get("FIRST_NAME", "")
                    last = row.get("LAST_NAME", "")
                    if first and last:
                        refs.append(f"{first} {last}")
            time.sleep(0.7)
        except Exception as e:
            logger.warning(f"  Ref fetch failed for {gid} ({away}@{home}): {e}")

        # Sort alphabetically, pad to 3
        refs = sorted(refs)[:3]
        while len(refs) < 3:
            refs.append(None)

        # Classify
        if any(r is None for r in refs[:1]):
            # No ref data at all
            crew_high = None
            ref_signal = "UNKNOWN"
        else:
            crew_high = sum(1 for r in refs if r and r in TOP_QUARTILE_REFS)
            if crew_high >= 2:
                ref_signal = "REF_OVER"
            elif crew_high == 0:
                ref_signal = "REF_UNDER"
            else:
                ref_signal = "NONE"

        results.append({
            "game_id": gid,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "ref_1": refs[0],
            "ref_2": refs[1],
            "ref_3": refs[2],
            "crew_high_count": crew_high,
            "crew_high_exact": crew_high,
            "ref_signal": ref_signal,
        })

        status = f"✓ {crew_high} high" if crew_high is not None else "? unknown"
        logger.info(f"  {away}@{home} — refs: {refs[0] or '?'}, {refs[1] or '?'}, {refs[2] or '?'} → {status}")

    return results


def run(game_date: str = None) -> str:
    """Main entry point. Returns path to output CSV."""
    if game_date is None:
        game_date = date.today().isoformat()

    results = fetch_ref_assignments(game_date)

    if not results:
        logger.info(f"No games to process for {game_date}")
        return OUT_PATH

    # Write CSV (overwrite — one day at a time)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "game_id", "game_date", "home_team", "away_team",
            "ref_1", "ref_2", "ref_3",
            "crew_high_count", "crew_high_exact", "ref_signal",
        ])
        writer.writeheader()
        writer.writerows(results)

    # Summary
    n_with = sum(1 for r in results if r["ref_signal"] != "UNKNOWN")
    n_missing = sum(1 for r in results if r["ref_signal"] == "UNKNOWN")
    over = [r for r in results if r["ref_signal"] == "REF_OVER"]
    under = [r for r in results if r["ref_signal"] == "REF_UNDER"]

    print(f"\n[ref_scrape] {game_date} — {len(results)} games")
    print(f"  Ref data available: {n_with}")
    print(f"  Ref data missing:   {n_missing}")
    print(f"  REF_OVER signals:   {len(over)}", end="")
    if over:
        print(f" — {', '.join(r['game_id'] for r in over)}")
    else:
        print()
    print(f"  REF_UNDER signals:  {len(under)}", end="")
    if under:
        print(f" — {', '.join(r['game_id'] for r in under)}")
    else:
        print()
    print(f"  Output: {OUT_PATH}")

    return OUT_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA Referee Crew Scraper")
    parser.add_argument("date", nargs="?", default=None, help="Game date (YYYY-MM-DD)")
    args = parser.parse_args()
    run(args.date)
