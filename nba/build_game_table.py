#!/usr/bin/env python3
"""
Phase 1 — Build canonical NBA game table and run data quality audit.

Usage:
    python nba/build_game_table.py                  # build all historical seasons
    python nba/build_game_table.py --force-refresh  # re-pull from API even if cached
    python nba/build_game_table.py --seasons 2024-25  # specific season only
"""

import argparse
import logging
import os
import sys

# Allow running from repo root: python nba/build_game_table.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

from nba.config import ALL_HISTORICAL_SEASONS
from nba.modules.fetch_games import audit_game_table, build_game_table


def main():
    parser = argparse.ArgumentParser(description="Build NBA game table (Phase 1)")
    parser.add_argument(
        "--seasons", nargs="+", default=None,
        help="Season(s) to fetch, e.g. 2022-23 2023-24 2024-25"
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Re-pull all seasons from NBA API even if cached"
    )
    args = parser.parse_args()

    seasons = args.seasons or ALL_HISTORICAL_SEASONS
    print(f"\nBuilding NBA game table for seasons: {', '.join(seasons)}")

    df = build_game_table(seasons=seasons, force_refresh=args.force_refresh)

    if df.empty:
        print("ERROR: No games loaded. Check API connectivity.")
        sys.exit(1)

    print(f"\nTotal rows in game table: {len(df)}")
    audit_game_table(df)


if __name__ == "__main__":
    main()
