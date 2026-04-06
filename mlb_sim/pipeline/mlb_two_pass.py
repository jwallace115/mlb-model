#!/usr/bin/env python3
"""
MLB Two-Pass Daily Workflow
============================
Executes the MLB pipeline in two modes:

  prelim  — 2:00 AM: grade, refresh caches, capture early lines, preliminary signals
  confirm — 7:00 AM: verify grading completeness, re-refresh, official signals, push

Usage:
  python mlb_sim/pipeline/mlb_two_pass.py --mode prelim
  python mlb_sim/pipeline/mlb_two_pass.py --mode confirm
"""

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("mlb_two_pass")


def _update_last_run(key):
    p = PROJECT_ROOT / "shared" / "last_updated.json"
    d = json.load(open(p)) if p.exists() else {}
    d[key] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(p, "w") as f:
        json.dump(d, f, indent=2)


def _yesterday(game_date: str) -> str:
    return (datetime.strptime(game_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def _tomorrow(game_date: str) -> str:
    return (datetime.strptime(game_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


# =====================================================================
# GRADING
# =====================================================================

def grade_yesterday_games(game_date: str) -> dict:
    """Grade yesterday's completed games. Returns {expected, graded, missing}."""
    yesterday = _yesterday(game_date)
    logger.info(f"Grading yesterday ({yesterday})...")

    try:
        from push_results import grade_yesterday
        grade_yesterday(game_date)
    except Exception as e:
        logger.warning(f"Grading failed: {e}")

    # Check completeness
    db_path = PROJECT_ROOT / "data" / "mlb_model.db"
    if not db_path.exists():
        return {"expected": 0, "graded": 0, "missing": []}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Count games scheduled yesterday
    scheduled = conn.execute(
        "SELECT game_pk, home_team, away_team FROM projections WHERE game_date = ?",
        (yesterday,)
    ).fetchall()

    # Count graded
    graded = conn.execute(
        "SELECT game_pk FROM results WHERE game_date = ? AND actual_total IS NOT NULL",
        (yesterday,)
    ).fetchall()
    graded_pks = {r["game_pk"] for r in graded}

    missing = []
    for s in scheduled:
        if s["game_pk"] not in graded_pks:
            missing.append(f"{s['away_team']}@{s['home_team']} (pk={s['game_pk']})")

    conn.close()

    result = {
        "expected": len(scheduled),
        "graded": len(graded),
        "missing": missing,
    }

    if missing:
        logger.warning(f"West coast / delayed games not yet final: {len(missing)} missing")
        for m in missing:
            logger.warning(f"  MISSING: {m}")
    else:
        logger.info(f"All {result['graded']} games graded successfully")

    return result


# =====================================================================
# CACHE QUALITY
# =====================================================================

def check_cache_quality(game_date: str) -> dict:
    """Check offense and pitcher cache quality for today."""
    from config import CACHE_DIR

    report = {}

    # Offense cache
    off_path = os.path.join(CACHE_DIR, f"offense_v2_{game_date}.json")
    if os.path.exists(off_path):
        with open(off_path) as f:
            off = json.load(f)
        report["offense_teams"] = len(off)
        report["offense_path"] = off_path
        report["offense_valid"] = len(off) >= 25
    else:
        report["offense_teams"] = 0
        report["offense_valid"] = False

    # Pitcher cache
    pit_path = os.path.join(CACHE_DIR, f"pitchers_v2_{game_date}.json")
    if os.path.exists(pit_path):
        with open(pit_path) as f:
            pit = json.load(f)
        report["pitcher_count"] = len(pit)
        # Check how many have K%
        k_pct_count = sum(1 for v in pit.values() if v.get("k_pct") is not None)
        report["pitcher_with_kpct"] = k_pct_count
    else:
        report["pitcher_count"] = 0
        report["pitcher_with_kpct"] = 0

    return report


def invalidate_stale_cache(game_date: str) -> None:
    """Remove today's caches if they contain incomplete data, forcing re-fetch."""
    from config import CACHE_DIR

    off_path = os.path.join(CACHE_DIR, f"offense_v2_{game_date}.json")
    if os.path.exists(off_path):
        with open(off_path) as f:
            off = json.load(f)
        if len(off) < 25:
            backup = off_path.replace(".json", "_invalidated.json")
            os.rename(off_path, backup)
            logger.info(f"Invalidated offense cache ({len(off)} teams < 25): {off_path}")


# =====================================================================
# 2AM PRELIMINARY PASS
# =====================================================================

def run_prelim(game_date: str) -> None:
    """
    2:00 AM preliminary pass.
    Grades, refreshes caches, captures early lines, generates preliminary signals.
    """
    _update_last_run("mlb_prelim")
    logger.info(f"{'='*60}")
    logger.info(f"PRELIM 2AM PASS — {game_date}")
    logger.info(f"{'='*60}")

    # Step 1: Grade yesterday (some west coast games may still be missing)
    grade_result = grade_yesterday_games(game_date)
    logger.info(f"Grading: {grade_result['graded']}/{grade_result['expected']} games "
                f"({len(grade_result['missing'])} missing)")

    # Step 2: Invalidate any stale/poisoned caches from prior runs
    invalidate_stale_cache(game_date)

    # Step 3: Capture opening lines for today
    try:
        from mlb_sim.pipeline.line_snapshot_store import store_snapshots_from_odds_response
        from config import ODDS_API_KEY, ODDS_API_BASE, ODDS_BOOKMAKERS
        import requests

        url = f"{ODDS_API_BASE}/sports/baseball_mlb/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "totals",
            "bookmakers": ",".join(ODDS_BOOKMAKERS),
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        games = resp.json()

        # Store as OPEN for today
        stored, skipped, no_line = store_snapshots_from_odds_response(games, "OPEN", game_date)
        logger.info(f"Opening lines: stored={stored}, skipped={skipped}, no_line={no_line}")

        # Also store as 2AM snapshot
        store_snapshots_from_odds_response(games, "2AM", game_date)
    except Exception as e:
        logger.warning(f"Line capture failed (non-fatal): {e}")

    # Step 4: Refresh feature caches (offense, pitcher) — these write to per-day cache files
    try:
        from modules.pitchers import build_pitcher_db
        pitcher_db = build_pitcher_db()
        logger.info(f"Pitcher DB refreshed: {len(pitcher_db)} entries")
    except Exception as e:
        logger.warning(f"Pitcher DB refresh failed: {e}")

    try:
        from modules.offense import build_offense_db
        offense_db = build_offense_db()
        logger.info(f"Offense DB refreshed: {len(offense_db)} teams")
    except Exception as e:
        logger.warning(f"Offense DB refresh failed: {e}")

    # Step 5: Cache quality check
    cache_quality = check_cache_quality(game_date)
    logger.info(f"Cache quality: offense={cache_quality['offense_teams']} teams "
                f"({'OK' if cache_quality['offense_valid'] else 'INCOMPLETE'}), "
                f"pitchers={cache_quality['pitcher_count']}")

    # Step 6: Run preliminary model + signals (no push)
    try:
        from run_model import run as run_model_fn
        results = run_model_fn(game_date=game_date, quiet=True, use_odds=True)
        logger.info(f"Preliminary model: {len(results)} games projected")
    except Exception as e:
        logger.warning(f"Preliminary model run failed: {e}")

    # Step 7: Run V1 signal generator
    try:
        from mlb_sim.pipeline.daily_signal_generator import run_daily as sim_daily
        from modules.schedule import fetch_schedule
        schedule = fetch_schedule(game_date)
        sim_signals = sim_daily(game_date_str=game_date, schedule=schedule,
                                 pitcher_db=pitcher_db if 'pitcher_db' in dir() else {})
        logger.info(f"Preliminary V1 signals: {len(sim_signals or [])}")
    except Exception as e:
        logger.warning(f"Preliminary signal generation failed: {e}")

    # Step 8: Tag preliminary signals with signal_status = "PRELIMINARY"
    try:
        sig_json_path = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.json"
        if sig_json_path.exists():
            with open(sig_json_path) as f:
                all_sigs = json.load(f)
            for s in all_sigs:
                if s.get("date") == game_date and s.get("resolved") != 1:
                    s["signal_status"] = "PRELIMINARY"
            with open(sig_json_path, "w") as f:
                json.dump(all_sigs, f, indent=2)
            logger.info("Tagged today's signals as PRELIMINARY")
    except Exception as e:
        logger.warning(f"Signal tagging failed (non-fatal): {e}")

    # Step 9: Push preliminary signals + overnight results to GitHub
    try:
        prelim_files = [
            str(PROJECT_ROOT / "mlb_sim" / "data" / "line_snapshots_2026.json"),
            str(PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.json"),
            str(PROJECT_ROOT / "mlb_sim" / "logs" / "f5_signals_2026.json"),
            str(PROJECT_ROOT / "results.json"),
            str(PROJECT_ROOT / "season_stats.json"),
            str(PROJECT_ROOT / "nba_results.json"),
            str(PROJECT_ROOT / "nhl_results.json"),
            str(PROJECT_ROOT / "soccer_results.json"),
        ]
        for f in prelim_files:
            if os.path.exists(f):
                subprocess.run(["git", "add", "-f", f], cwd=str(PROJECT_ROOT), check=True)
        # Also add performance tracker if it exists
        perf_path = str(PROJECT_ROOT / "mlb_sim" / "logs" / "rolling_performance_2026.json")
        if os.path.exists(perf_path):
            subprocess.run(["git", "add", "-f", perf_path], cwd=str(PROJECT_ROOT), check=True)

        subprocess.run(["git", "commit", "-m", f"prelim: {game_date} signals + overnight results"],
                       cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(PROJECT_ROOT), check=True)
        logger.info("Pushed preliminary signals + overnight results")
    except Exception as e:
        logger.warning(f"Git push failed (non-fatal): {e}")

    logger.info("PRELIM 2AM PASS COMPLETE")


# =====================================================================
# 7AM CONFIRMATION PASS
# =====================================================================

def run_confirm(game_date: str) -> None:
    """
    7:00 AM confirmation pass.
    Verifies grading completeness, re-refreshes, generates official signals, pushes.
    """
    _update_last_run("mlb_confirm")
    logger.info(f"{'='*60}")
    logger.info(f"CONFIRM 7AM PASS — {game_date}")
    logger.info(f"{'='*60}")

    # Step 1: West coast finalization check — re-grade if needed
    grade_result = grade_yesterday_games(game_date)

    if grade_result["missing"]:
        logger.warning(f"STILL MISSING {len(grade_result['missing'])} games after re-grade:")
        for m in grade_result["missing"]:
            logger.warning(f"  {m}")
        logger.warning("Proceeding with available data — missing games will be graded at 11:30 PM")

    # Step 2: Check cache quality from 2AM run
    cache_quality = check_cache_quality(game_date)
    logger.info(f"Pre-existing cache: offense={cache_quality['offense_teams']} teams, "
                f"pitchers={cache_quality['pitcher_count']}")

    # Step 3: If cache is incomplete, invalidate and re-fetch
    if not cache_quality["offense_valid"]:
        logger.warning("Offense cache incomplete — invalidating for re-fetch")
        invalidate_stale_cache(game_date)

    # Step 4: Hand off to the standard push_results.py pipeline
    # This runs: grade → stats → model → signals → other sports → push
    logger.info("Handing off to push_results.py for official run...")
    cmd = [sys.executable, str(PROJECT_ROOT / "push_results.py"), "--date", game_date]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        logger.error(f"push_results.py exited with code {result.returncode}")
    else:
        logger.info("CONFIRM 7AM PASS COMPLETE — official signals pushed")

    # Step 5: Enrich signals with line movement (open vs current)
    try:
        open_snap_path = PROJECT_ROOT / "mlb_sim" / "data" / "line_snapshots_open_2026.json"
        signals_path = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.json"

        if open_snap_path.exists() and signals_path.exists():
            with open(open_snap_path) as f:
                open_snaps = json.load(f)
            with open(signals_path) as f:
                signals = json.load(f)

            # Build lookup: (home_team, away_team, game_date) → open line
            open_lookup = {}
            for snap in open_snaps:
                if snap.get("snapshot_type") == "open" and snap.get("game_date") == game_date:
                    key = (snap.get("home_team", ""), snap.get("away_team", ""))
                    open_lookup[key] = snap.get("total_line")

            enriched = 0
            for sig in signals:
                if sig.get("date") != game_date:
                    continue
                key = (sig.get("home_team", ""), sig.get("away_team", ""))
                open_line = open_lookup.get(key)
                current_line = sig.get("line_at_signal_time")
                if open_line is not None and current_line is not None:
                    sig["open_line"] = open_line
                    sig["line_movement"] = round(current_line - open_line, 1)
                    enriched += 1

            if enriched > 0:
                with open(signals_path, "w") as f:
                    json.dump(signals, f, indent=2)
                logger.info(f"Line movement enriched: {enriched} signals "
                            f"(positive = line moved up, negative = line moved down)")
            else:
                logger.info("Line movement: no open snapshots matched today's signals")
        else:
            logger.info("Line movement: snapshot or signal file not found — skipping")
    except Exception as e:
        logger.warning(f"Line movement enrichment failed (non-fatal): {e}")

    # Step 6: Tag signals as CONFIRMED (overrides PRELIMINARY from 2 AM)
    try:
        sig_json_path = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.json"
        if sig_json_path.exists():
            with open(sig_json_path) as f:
                all_sigs = json.load(f)
            for s in all_sigs:
                if s.get("date") == game_date and s.get("resolved") != 1:
                    s["signal_status"] = "CONFIRMED"
            with open(sig_json_path, "w") as f:
                json.dump(all_sigs, f, indent=2)
            logger.info("Tagged today's signals as CONFIRMED")
    except Exception as e:
        logger.warning(f"Signal status tagging failed (non-fatal): {e}")

    # Step 7: Post-run cache quality verification
    final_cache = check_cache_quality(game_date)
    logger.info(f"Final cache: offense={final_cache['offense_teams']} teams, "
                f"pitchers={final_cache['pitcher_count']} "
                f"(with K%: {final_cache['pitcher_with_kpct']})")


# =====================================================================
# ENTRY POINT
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="MLB Two-Pass Daily Workflow")
    parser.add_argument("--mode", required=True, choices=["prelim", "confirm"],
                        help="Run mode: prelim (2AM) or confirm (7AM)")
    parser.add_argument("--date", default=None,
                        help="Game date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()

    if args.mode == "prelim":
        run_prelim(game_date)
    elif args.mode == "confirm":
        run_confirm(game_date)


if __name__ == "__main__":
    main()
