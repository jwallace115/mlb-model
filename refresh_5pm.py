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
from datetime import date, datetime, timezone

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

    # Step 1b: F5 data collection — "close" pull (5 PM trigger)
    try:
        from modules.schedule import fetch_schedule
        from mlb_sim_f5.data.collect_f5_lines import run_daily as f5_daily
        mlb_games = fetch_schedule(game_date)
        f5_daily(game_date, "close", mlb_games)
        print("[refresh_5pm] F5 close pull complete.")
    except Exception as e:
        print(f"[refresh_5pm] F5 collection failed (non-fatal): {e}", file=sys.stderr)

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

    # Step 2 (CLV): Write pregame snapshot for NBA — overwrite any prior pregame entry
    try:
        import pandas as pd
        _nba_proj_path = os.path.join(REPO_DIR, "nba", "data", "nba_daily_projections.parquet")
        _nba_snap_path = os.path.join(REPO_DIR, "nba", "data", "nba_market_snapshots.parquet")
        if os.path.exists(_nba_proj_path):
            _projs = pd.read_parquet(_nba_proj_path)
            _today_projs = _projs[_projs["game_date"] == game_date]
            if not _today_projs.empty:
                _snap_time = datetime.now(timezone.utc).isoformat()
                _pregame_rows = []
                for _, _pg in _today_projs.iterrows():
                    _pregame_rows.append({
                        "game_id":           _pg.get("game_id"),
                        "game_date":         game_date,
                        "snapshot_type":     "pregame",
                        "snapshot_time_utc": _snap_time,
                        "line":              _pg.get("line"),
                        "price":             -110.0,
                        "source":            "odds_api" if _pg.get("line") is not None else "no_line",
                    })
                _pregame_df = pd.DataFrame(_pregame_rows)
                if os.path.exists(_nba_snap_path):
                    _existing_snaps = pd.read_parquet(_nba_snap_path)
                    # Drop any prior pregame entries for this game_date (overwrite)
                    _existing_snaps = _existing_snaps[
                        ~((_existing_snaps["game_date"] == game_date) &
                          (_existing_snaps["snapshot_type"] == "pregame"))
                    ]
                    _combined_snaps = pd.concat([_existing_snaps, _pregame_df], ignore_index=True)
                else:
                    _combined_snaps = _pregame_df
                _combined_snaps.to_parquet(_nba_snap_path, index=False)
                print(f"[refresh_5pm] NBA pregame snapshot written ({len(_pregame_df)} games)")
    except Exception as e:
        print(f"[refresh_5pm] NBA pregame snapshot failed (non-fatal): {e}", file=sys.stderr)

    # Step 2b: NHL pipeline refresh + serialize JSON
    print(f"[refresh_5pm] Running NHL pipeline for {game_date} ...")

    # NHL CLV: capture morning lines BEFORE the subprocess overwrites closing_total
    try:
        import pandas as _pd
        _nhl_dec_path  = os.path.join(REPO_DIR, "nhl", "nhl_decisions.parquet")
        _nhl_snap_path = os.path.join(REPO_DIR, "nhl", "nhl_clv_snapshots.parquet")
        if os.path.exists(_nhl_dec_path):
            _nhl_dec = _pd.read_parquet(_nhl_dec_path)
            _nhl_live = _nhl_dec[
                (_nhl_dec["split"] == "live") &
                (_nhl_dec["game_date"].astype(str) == game_date)
            ]
            if not _nhl_live.empty:
                _nhl_snap_time = datetime.now(timezone.utc).isoformat()
                _nhl_morning_rows = []
                for _, _nr in _nhl_live.iterrows():
                    _nhl_morning_rows.append({
                        "game_id":           _nr.get("game_id"),
                        "game_date":         game_date,
                        "snapshot_type":     "morning",
                        "snapshot_time_utc": _nhl_snap_time,
                        "line":              _nr.get("closing_total"),
                        "price":             None,
                        "source":            "nhl_decisions",
                    })
                _nhl_morning_df = _pd.DataFrame(_nhl_morning_rows)
                if os.path.exists(_nhl_snap_path):
                    _nhl_existing = _pd.read_parquet(_nhl_snap_path)
                    # Only write if no morning snapshot for this game_date yet
                    _already = (
                        (_nhl_existing["game_date"].astype(str) == game_date) &
                        (_nhl_existing["snapshot_type"] == "morning")
                    ).any()
                    if not _already:
                        _nhl_combined = _pd.concat([_nhl_existing, _nhl_morning_df], ignore_index=True)
                        _nhl_combined.to_parquet(_nhl_snap_path, index=False)
                        print(f"[refresh_5pm] NHL morning snapshot written ({len(_nhl_morning_df)} rows)")
                    else:
                        print(f"[refresh_5pm] NHL morning snapshot already exists for {game_date} — skipping")
                else:
                    _nhl_morning_df.to_parquet(_nhl_snap_path, index=False)
                    print(f"[refresh_5pm] NHL morning snapshot written ({len(_nhl_morning_df)} rows)")
    except Exception as e:
        print(f"[refresh_5pm] NHL morning snapshot failed (non-fatal): {e}", file=sys.stderr)

    try:
        import subprocess as _sp
        _sp.run(
            [sys.executable, "nhl/nhl_daily_pipeline.py", "--date", game_date],
            cwd=REPO_DIR, check=False,
        )
    except Exception as e:
        print(f"[refresh_5pm] NHL pipeline failed (non-fatal): {e}", file=sys.stderr)

    # NHL CLV: capture pregame (post-pipeline) lines — overwrite any prior pregame entry
    try:
        import pandas as _pd2
        _nhl_dec_path2  = os.path.join(REPO_DIR, "nhl", "nhl_decisions.parquet")
        _nhl_snap_path2 = os.path.join(REPO_DIR, "nhl", "nhl_clv_snapshots.parquet")
        if os.path.exists(_nhl_dec_path2):
            _nhl_dec2 = _pd2.read_parquet(_nhl_dec_path2)
            _nhl_live2 = _nhl_dec2[
                (_nhl_dec2["split"] == "live") &
                (_nhl_dec2["game_date"].astype(str) == game_date)
            ]
            if not _nhl_live2.empty:
                _nhl_snap_time2 = datetime.now(timezone.utc).isoformat()
                _nhl_pregame_rows = []
                for _, _nr2 in _nhl_live2.iterrows():
                    _nhl_pregame_rows.append({
                        "game_id":           _nr2.get("game_id"),
                        "game_date":         game_date,
                        "snapshot_type":     "pregame",
                        "snapshot_time_utc": _nhl_snap_time2,
                        "line":              _nr2.get("closing_total"),
                        "price":             None,
                        "source":            "nhl_decisions",
                    })
                _nhl_pregame_df = _pd2.DataFrame(_nhl_pregame_rows)
                if os.path.exists(_nhl_snap_path2):
                    _nhl_existing2 = _pd2.read_parquet(_nhl_snap_path2)
                    # Drop any prior pregame entries for this game_date (overwrite)
                    _nhl_existing2 = _nhl_existing2[
                        ~((_nhl_existing2["game_date"].astype(str) == game_date) &
                          (_nhl_existing2["snapshot_type"] == "pregame"))
                    ]
                    _nhl_combined2 = _pd2.concat([_nhl_existing2, _nhl_pregame_df], ignore_index=True)
                else:
                    _nhl_combined2 = _nhl_pregame_df
                _nhl_combined2.to_parquet(_nhl_snap_path2, index=False)
                print(f"[refresh_5pm] NHL pregame snapshot written ({len(_nhl_pregame_df)} rows)")
    except Exception as e:
        print(f"[refresh_5pm] NHL pregame snapshot failed (non-fatal): {e}", file=sys.stderr)

    try:
        from push_nhl import write_nhl_json
        write_nhl_json(game_date)
        push_files.append("nhl_results.json")
    except Exception as e:
        print(f"[refresh_5pm] NHL JSON write failed (non-fatal): {e}", file=sys.stderr)

    # Step 2c: Soccer lineup refresh — re-fetch lineups (often announced by 5pm)
    print(f"[refresh_5pm] Running Soccer lineup refresh for {game_date} ...")
    try:
        import subprocess as _sp2
        _sp2.run(
            [sys.executable, "soccer/soccer_daily_pipeline.py", "--refresh-lineups", "--date", game_date],
            cwd=REPO_DIR, check=False,
        )
    except Exception as e:
        print(f"[refresh_5pm] Soccer refresh failed (non-fatal): {e}", file=sys.stderr)
    try:
        from push_soccer import write_soccer_json
        write_soccer_json(game_date)
        push_files.append("soccer_results.json")
    except Exception as e:
        print(f"[refresh_5pm] Soccer JSON write failed (non-fatal): {e}", file=sys.stderr)

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
