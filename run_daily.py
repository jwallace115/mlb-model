#!/usr/bin/env python3
"""
Daily Morning Card — 7 AM runner.
Runs MLB model first, then NBA model.
Results logging for NBA runs at the start of the NBA section.

Usage:
  python run_daily.py                 # today's card
  python run_daily.py 2025-12-15      # specific date
  python run_daily.py --no-odds       # skip all Odds API calls
  python run_daily.py --no-mlb        # NBA only
  python run_daily.py --no-nba        # MLB only
  python run_daily.py --skip-results  # skip NBA results grading
"""

import argparse
import logging
import os
import sys
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

BANNER = "═" * 68


def run_mlb(game_date: str, use_odds: bool) -> None:
    print(f"\n{BANNER}")
    print("  MLB MORNING CARD")
    print(BANNER)
    try:
        import runpy

        argv_backup = sys.argv[:]
        sys.argv = ["run_model.py", game_date]
        if not use_odds:
            sys.argv.append("--no-odds")
        try:
            runpy.run_path(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_model.py"),
                run_name="__main__",
            )
        finally:
            sys.argv = argv_backup

    except SystemExit:
        pass  # run_model.py calls sys.exit() — swallow it
    except Exception as e:
        logger.error(f"MLB runner failed: {e}", exc_info=True)
        print(f"\n  ⚠  MLB runner failed: {e}\n")


def run_nba(game_date: str, use_odds: bool, skip_results: bool) -> None:
    print(f"\n{BANNER}")
    print("  NBA MORNING CARD")
    print(BANNER)
    try:
        from nba.run_nba import run as nba_run
        nba_run(
            game_date=game_date,
            use_odds=use_odds,
            skip_results=skip_results,
        )
    except Exception as e:
        logger.error(f"NBA runner failed: {e}", exc_info=True)
        print(f"\n  ⚠  NBA runner failed: {e}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily MLB + NBA morning card")
    parser.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--no-odds",       action="store_true", help="Skip all Odds API calls")
    parser.add_argument("--no-mlb",        action="store_true", help="Skip MLB section")
    parser.add_argument("--no-nba",        action="store_true", help="Skip NBA section")
    parser.add_argument("--skip-results",  action="store_true", help="Skip NBA results grading")
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()
    use_odds  = not args.no_odds

    print(f"\n{'═'*68}")
    print(f"  DAILY CARD — {game_date}")
    print(f"{'═'*68}")

    if not args.no_mlb:
        run_mlb(game_date, use_odds)

    if not args.no_nba:
        run_nba(game_date, use_odds, args.skip_results)

    print(f"\n{'═'*68}")
    print("  Daily card complete.")
    print(f"{'═'*68}\n")


if __name__ == "__main__":
    main()
