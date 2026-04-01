#!/usr/bin/env python3
"""
MLB Starting Pitcher Scratch Checker
======================================
Runs at noon, 4:30 PM, and 6:30 PM ET to detect pitcher changes
after the 7 AM confirm run. If a scratch is detected for a game with
an active signal, re-runs the simulation and updates the signal.

Usage:
  python3 mlb_sim/pipeline/mlb_scratch_checker.py
  python3 mlb_sim/pipeline/mlb_scratch_checker.py --date 2026-04-01
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("scratch_checker")

SIGNALS_JSON = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.json"
SIGNALS_PARQUET = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.parquet"


def _load_signals_json():
    if not SIGNALS_JSON.exists():
        return []
    with open(SIGNALS_JSON) as f:
        return json.load(f)


def _save_signals_json(signals):
    with open(SIGNALS_JSON, "w") as f:
        json.dump(signals, f, indent=2)


def _fetch_current_pitchers(game_date_str):
    """Fetch current probable pitchers from MLB Stats API schedule."""
    from modules.schedule import fetch_schedule
    schedule = fetch_schedule(game_date_str)
    # Build lookup: game_id → {home_sp_name, home_sp_id, away_sp_name, away_sp_id}
    pitcher_map = {}
    for g in schedule:
        gid = str(g.get("game_pk", ""))
        home_pp = g.get("home_probable_pitcher", {})
        away_pp = g.get("away_probable_pitcher", {})
        pitcher_map[gid] = {
            "home_sp_name": home_pp.get("name", "TBD"),
            "home_sp_id": home_pp.get("id"),
            "away_sp_name": away_pp.get("name", "TBD"),
            "away_sp_id": away_pp.get("id"),
        }
    return pitcher_map, schedule


def _rerun_single_game(game, pitcher_db):
    """Re-run simulation for a single game with updated pitcher data.

    Returns the new signal dict or None if no signal fires.
    """
    from mlb_sim.pipeline.daily_signal_generator import (
        _lookup_pitcher, _compute_path_probs, _get_m3_total,
        CSW_Q75, UNDER_THRESHOLD_LOW, UNDER_THRESHOLD_HIGH, N_SIMS,
    )
    from mlb_sim.pipeline.daily_signal_generator import _S2, _RP
    import numpy as np

    home = game.get("home_team", "")
    away = game.get("away_team", "")
    home_sp_info = game.get("home_probable_pitcher", {})
    away_sp_info = game.get("away_probable_pitcher", {})

    home_sp = _lookup_pitcher(home_sp_info, pitcher_db)
    away_sp = _lookup_pitcher(away_sp_info, pitcher_db)

    if home_sp is None or away_sp is None:
        logger.warning(f"  Cannot look up pitcher metrics for {away}@{home}")
        return None

    home_probs = _compute_path_probs(home_sp, game)
    away_probs = _compute_path_probs(away_sp, game)

    # Monte Carlo simulation (same as daily_signal_generator)
    rng = np.random.default_rng()
    home_runs = np.zeros(N_SIMS)
    away_runs = np.zeros(N_SIMS)
    for path, prob in home_probs.items():
        n = int(round(prob * N_SIMS))
        if n > 0 and path in _RP:
            home_runs[:n] += rng.poisson(_RP[path]["lambda"], n)
    for path, prob in away_probs.items():
        n = int(round(prob * N_SIMS))
        if n > 0 and path in _RP:
            away_runs[:n] += rng.poisson(_RP[path]["lambda"], n)

    totals = home_runs + away_runs
    line = game.get("line")
    if line is None:
        return None

    p_under = (totals < line).mean()
    p_over = (totals > line).mean()

    # Check thresholds
    if p_under >= UNDER_THRESHOLD_LOW:
        stake = 1.0 if p_under >= UNDER_THRESHOLD_HIGH else 0.5
        return {
            "signal_side": "UNDER",
            "stake_units": stake,
            "raw_p_under": round(float(p_under), 4),
            "raw_p_over": round(float(p_over), 4),
            "line_at_signal_time": line,
            "home_sp_name": home_sp_info.get("name", "TBD"),
            "away_sp_name": away_sp_info.get("name", "TBD"),
        }
    return None


def run(game_date_str=None):
    game_date_str = game_date_str or date.today().isoformat()
    ts = datetime.now(timezone.utc).isoformat()

    logger.info(f"{'='*60}")
    logger.info(f"MLB Scratch Checker — {game_date_str} at {ts[:19]}")
    logger.info(f"{'='*60}")

    # Load today's signals
    signals = _load_signals_json()
    today_signals = [s for s in signals if s.get("date") == game_date_str
                     and s.get("resolved") != 1
                     and s.get("scratch_voided") != True]

    if not today_signals:
        logger.info("No active unresolved signals for today. Exiting.")
        return

    logger.info(f"Active signals: {len(today_signals)}")

    # Fetch current pitchers
    current_pitchers, schedule = _fetch_current_pitchers(game_date_str)
    if not current_pitchers:
        logger.warning("Could not fetch current schedule. Exiting.")
        return

    # Build pitcher_db for re-simulation
    pitcher_db = None
    try:
        from modules.pitchers import build_pitcher_db
        pitcher_db = build_pitcher_db()
    except Exception as e:
        logger.warning(f"Pitcher DB build failed: {e}")

    # Build schedule lookup for re-simulation
    schedule_map = {}
    for g in schedule:
        gid = str(g.get("game_pk", ""))
        schedule_map[gid] = g

    scratches_found = 0
    voided = 0
    updated = 0
    changes = False

    for sig in signals:
        if sig.get("date") != game_date_str:
            continue
        if sig.get("resolved") == 1:
            continue
        if sig.get("scratch_voided") == True:
            continue

        gid = str(sig.get("game_id", ""))
        home = sig.get("home_team", "")
        away = sig.get("away_team", "")

        current = current_pitchers.get(gid)
        if not current:
            continue

        # Compare pitchers — check both home and away
        old_home_sp = sig.get("home_sp_name", "")
        old_away_sp = sig.get("away_sp_name", "")
        new_home_sp = current["home_sp_name"]
        new_away_sp = current["away_sp_name"]

        # If signal doesn't have pitcher names yet, store them and continue
        if not old_home_sp and not old_away_sp:
            sig["home_sp_name"] = new_home_sp
            sig["away_sp_name"] = new_away_sp
            changes = True
            continue

        home_changed = (old_home_sp and new_home_sp
                        and old_home_sp != "TBD" and new_home_sp != "TBD"
                        and old_home_sp != new_home_sp)
        away_changed = (old_away_sp and new_away_sp
                        and old_away_sp != "TBD" and new_away_sp != "TBD"
                        and old_away_sp != new_away_sp)

        if not home_changed and not away_changed:
            continue

        # SCRATCH DETECTED
        scratches_found += 1
        scratch_desc = []
        if home_changed:
            scratch_desc.append(f"{home} SP: {old_home_sp} → {new_home_sp}")
        if away_changed:
            scratch_desc.append(f"{away} SP: {old_away_sp} → {new_away_sp}")

        logger.info(f"  SCRATCH DETECTED: {away}@{home} — {'; '.join(scratch_desc)}")

        # Re-run simulation if possible
        game_data = schedule_map.get(gid)
        new_result = None
        if game_data and pitcher_db:
            try:
                # Update line from current signal
                game_data["line"] = sig.get("line_at_signal_time")
                new_result = _rerun_single_game(game_data, pitcher_db)
            except Exception as e:
                logger.warning(f"  Re-simulation failed: {e}")

        if new_result is None:
            # Signal voided — no longer qualifies after scratch
            sig["scratch_voided"] = True
            sig["scratch_detected"] = True
            sig["original_home_sp"] = old_home_sp
            sig["original_away_sp"] = old_away_sp
            sig["replacement_home_sp"] = new_home_sp if home_changed else old_home_sp
            sig["replacement_away_sp"] = new_away_sp if away_changed else old_away_sp
            sig["scratch_detected_at"] = ts
            voided += 1
            logger.info(f"  VOIDED: {away}@{home} — signal no longer qualifies after scratch")
        else:
            # Signal updated with new pitcher data
            sig["scratch_detected"] = True
            sig["original_home_sp"] = old_home_sp
            sig["original_away_sp"] = old_away_sp
            sig["replacement_home_sp"] = new_home_sp if home_changed else old_home_sp
            sig["replacement_away_sp"] = new_away_sp if away_changed else old_away_sp
            sig["scratch_detected_at"] = ts
            sig["home_sp_name"] = new_home_sp
            sig["away_sp_name"] = new_away_sp
            # Update signal strength
            sig["raw_p_under"] = new_result["raw_p_under"]
            sig["raw_p_over"] = new_result["raw_p_over"]
            sig["stake_units"] = new_result["stake_units"]
            updated += 1
            logger.info(f"  UPDATED: {away}@{home} — signal refreshed with new pitcher "
                        f"(p_under={new_result['raw_p_under']:.1%}, stake={new_result['stake_units']}u)")

        changes = True

    if not changes:
        logger.info("No scratches detected. All pitchers match confirm run.")
        return

    # Save updated signals
    _save_signals_json(signals)
    logger.info(f"\nScratch check complete: {scratches_found} scratches, "
                f"{voided} voided, {updated} updated")

    # Push to GitHub
    try:
        subprocess.run(["git", "add", "-f", str(SIGNALS_JSON)],
                       cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "commit", "-m",
                        f"scratch check: {scratches_found} scratches {game_date_str}"],
                       cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "push", "origin", "main"],
                       cwd=str(PROJECT_ROOT), check=True)
        logger.info("Pushed updated signals to GitHub")
    except Exception as e:
        logger.warning(f"Git push failed (non-fatal): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(args.date)
