#!/usr/bin/env python3
"""
refresh_5pm.py — 5 PM refresh: MLB lineup/weather/umpire updates + NBA rerun.

Runs MLB refresh (lineup changes, weather, umpire confirmations) with no
internal push, then reruns the NBA model for fresh projections (injury
updates, line movement by tip time), then does a single combined git push
covering results.json and nba_results.json.

Usage:
    python refresh_5pm.py
    python refresh_5pm.py --date 2025-04-15
    python refresh_5pm.py --no-push
"""

import argparse
import os
import subprocess
import sys
from datetime import date

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def _git_push(game_date: str, files: list[str]) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}",
                  file=sys.stderr)
            return False
        return True

    for f in files:
        if not run(["git", "add", f]):
            return False

    status = subprocess.run(
        ["git", "status", "--porcelain"] + files,
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[refresh_5pm] Nothing to commit — files unchanged.")
        return True

    if not run(["git", "commit", "-m", f"refresh(5pm): {game_date}"]):
        return False
    if not run(["git", "push"]):
        return False

    print("[refresh_5pm] Pushed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser(description="5 PM MLB refresh + NBA rerun")
    parser.add_argument("--date",    default=None,        help="Game date YYYY-MM-DD")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()
    push = not args.no_push

    # Step 1: MLB refresh — lineup changes, weather, umpires (no internal push)
    print(f"[refresh_5pm] Running MLB refresh for {game_date} ...")
    try:
        from refresh import refresh_games
        refresh_games(game_date=game_date, push=False)
        print("[refresh_5pm] MLB refresh complete.")
    except Exception as e:
        print(f"[refresh_5pm] MLB refresh failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 2: NBA model rerun — fresh projections + updated odds (skip_results=True
    # because grading already ran at 7am; we only want fresh projections here)
    push_files = ["results.json"]
    print(f"[refresh_5pm] Running NBA model for {game_date} ...")
    try:
        from nba.run_nba import run as nba_run
        nba_run(game_date=game_date, use_odds=True, skip_results=True)
        print("[refresh_5pm] NBA model complete.")
    except Exception as e:
        print(f"[refresh_5pm] NBA model failed (non-fatal): {e}", file=sys.stderr)

    try:
        from push_nba import write_nba_json
        write_nba_json(game_date)
        push_files.append("nba_results.json")
    except Exception as e:
        print(f"[refresh_5pm] NBA JSON write failed (non-fatal): {e}", file=sys.stderr)

    # Step 2b: NHL pipeline refresh + serialize JSON
    print(f"[refresh_5pm] Running NHL pipeline for {game_date} ...")
    try:
        import subprocess as _sp
        _sp.run(
            [sys.executable, "nhl/nhl_daily_pipeline.py", "--date", game_date],
            cwd=REPO_DIR, check=False,
        )
    except Exception as e:
        print(f"[refresh_5pm] NHL pipeline failed (non-fatal): {e}", file=sys.stderr)
    try:
        from push_nhl import write_nhl_json
        write_nhl_json(game_date)
        push_files.append("nhl_results.json")
    except Exception as e:
        print(f"[refresh_5pm] NHL JSON write failed (non-fatal): {e}", file=sys.stderr)

    # Step 3: single combined push for all updated files
    if push:
        print(f"[refresh_5pm] Pushing {', '.join(push_files)} to GitHub ...")
        if not _git_push(game_date, push_files):
            print("[refresh_5pm] Push failed.", file=sys.stderr)
            sys.exit(1)
    else:
        print("[refresh_5pm] --no-push: skipping git push.")


if __name__ == "__main__":
    main()
