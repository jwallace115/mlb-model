#!/usr/bin/env python3
"""
Shadow tracker for combined_short_exit OVER amplifier signal.

SHADOW ONLY — does not affect live picks, bet sizing, or overlay activation.

Computes combined_short_exit for each game and logs to shadow file.
Called from run_model.py after V1 signals are generated.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger("short_exit_shadow")

CONFIG_PATH = Path(__file__).resolve().parent / "combined_short_exit_shadow_config.json"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

# ── Pitcher short-exit lookup (built once per pipeline run) ──────────
_short_exit_cache = {}


def build_short_exit_lookup():
    """
    Build a dict: pitcher_mlbam_id → short_exit_r15 (rolling 15-start
    fraction of starts with IP < 5.0, using only completed starts).

    Uses bullpen_usage.parquet (starter appearances with IP) from sim/data/.
    Returns dict mapping pitcher_id → float.
    """
    global _short_exit_cache
    if _short_exit_cache:
        return _short_exit_cache

    try:
        import pandas as pd
        bu_path = Path(__file__).resolve().parent.parent.parent / "sim" / "data" / "bullpen_usage.parquet"
        if not bu_path.exists():
            logger.warning("bullpen_usage.parquet not found — short_exit shadow disabled")
            return {}

        bu = pd.read_parquet(bu_path)
        starters = bu[bu["is_starter"]].sort_values(["pitcher_id", "date"]).copy()
        starters["short_exit"] = (starters["innings_pitched"] < 5.0).astype(int)
        # Rolling 15 starts, shift(1) to exclude current game
        starters["short_exit_r15"] = starters.groupby("pitcher_id")["short_exit"].transform(
            lambda x: x.shift(1).rolling(15, min_periods=5).mean()
        )
        # Keep latest per pitcher
        latest = starters.dropna(subset=["short_exit_r15"]).groupby("pitcher_id").last()
        _short_exit_cache = latest["short_exit_r15"].to_dict()
        logger.info(f"Short-exit lookup built: {len(_short_exit_cache)} pitchers")
        return _short_exit_cache
    except Exception as e:
        logger.warning(f"Failed to build short-exit lookup: {e}")
        return {}


def get_pitcher_short_exit(pitcher_id):
    """Look up a pitcher's rolling short-exit rate. Returns float or None."""
    if not _short_exit_cache:
        build_short_exit_lookup()
    if pitcher_id is None:
        return None
    return _short_exit_cache.get(int(pitcher_id))


def _load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"status": "SHADOW", "frozen_cutoff_2024": 0.133333}


def compute_combined_short_exit(home_sp_short_exit_r15, away_sp_short_exit_r15):
    """
    Compute combined short-exit rate.
    Returns float or None if inputs missing.

    short_exit_r15 = fraction of last 15 starts where IP < 5.0
    Lower values = more durable starters.
    """
    if home_sp_short_exit_r15 is None or away_sp_short_exit_r15 is None:
        return None
    return (home_sp_short_exit_r15 + away_sp_short_exit_r15) / 2


def evaluate_shadow(combined_short_exit_value, v1_p_under):
    """
    Evaluate combined_short_exit against shadow config.
    Returns dict with shadow tracking fields.

    SHADOW ONLY — does not produce bet triggers.
    """
    cfg = _load_config()
    cutoff = cfg.get("frozen_cutoff_2024", 0.133333)
    status = cfg.get("status", "SHADOW")

    # Determine favorable zone
    favorable_zone = False
    if combined_short_exit_value is not None:
        favorable_zone = combined_short_exit_value <= cutoff

    # V1 direction context
    if v1_p_under is not None:
        if v1_p_under < 0.45:
            v1_direction = "OVER"
        elif v1_p_under > 0.57:
            v1_direction = "UNDER"
        else:
            v1_direction = "NONE"
    else:
        v1_direction = "NONE"

    return {
        "combined_short_exit_value": round(combined_short_exit_value, 6) if combined_short_exit_value is not None else None,
        "combined_short_exit_favorable_zone": favorable_zone,
        "combined_short_exit_cutoff": cutoff,
        "v1_direction_context": v1_direction,
        "shadow_status": status,
    }


def log_shadow_record(game_id, date, season, home_team, away_team,
                      combined_short_exit_value, favorable_zone,
                      v1_direction_context,
                      closing_total=None, actual_total=None,
                      actual_result_over=None, market_residual_over=None):
    """
    Append a shadow record to the JSON log.

    SHADOW ONLY — observational tracking, no live impact.
    """
    log_path = LOG_DIR / f"combined_short_exit_shadow_{season}.json"

    record = {
        "game_id": game_id,
        "date": str(date),
        "season": season,
        "home_team": home_team,
        "away_team": away_team,
        "combined_short_exit_value": combined_short_exit_value,
        "combined_short_exit_favorable_zone": favorable_zone,
        "v1_direction_context": v1_direction_context,
        "closing_total": closing_total,
        "actual_total": actual_total,
        "actual_result_over": actual_result_over,
        "over_hit": actual_result_over == 1 if actual_result_over is not None else None,
        "market_residual_over": market_residual_over,
        "logged_at": datetime.now().isoformat(),
    }

    # Load existing records
    records = []
    if log_path.exists():
        try:
            with open(log_path) as f:
                records = json.load(f)
        except (json.JSONDecodeError, Exception):
            records = []

    # Deduplicate by game_id
    records = [r for r in records if r.get("game_id") != game_id]
    records.append(record)

    with open(log_path, "w") as f:
        json.dump(records, f, indent=2)

    if favorable_zone:
        logger.info(f"  SHORT_EXIT shadow: {away_team}@{home_team} — "
                    f"value={combined_short_exit_value:.4f} <= {record.get('combined_short_exit_cutoff', 0.1333):.4f} "
                    f"FAVORABLE ZONE (V1={v1_direction_context})")

    return record


def fill_actuals(season, game_results):
    """
    Backfill actual_total and result fields for previously logged shadow records.
    game_results: dict mapping game_id -> {"actual_total": int, "closing_total": float}
    """
    log_path = LOG_DIR / f"combined_short_exit_shadow_{season}.json"
    if not log_path.exists():
        return 0

    with open(log_path) as f:
        records = json.load(f)

    filled = 0
    for r in records:
        gid = r.get("game_id")
        if gid in game_results and r.get("actual_total") is None:
            gr = game_results[gid]
            r["actual_total"] = gr["actual_total"]
            r["closing_total"] = gr.get("closing_total", r.get("closing_total"))
            if r["closing_total"] is not None:
                r["actual_result_over"] = 1 if gr["actual_total"] > r["closing_total"] else 0
                r["over_hit"] = r["actual_result_over"] == 1
                r["market_residual_over"] = r["actual_result_over"] - 0.50
            filled += 1

    with open(log_path, "w") as f:
        json.dump(records, f, indent=2)

    return filled


def grade_combined_short_exit(season: int = 2026):
    """Grade unresolved combined short exit shadow entries."""
    import pandas as pd

    log_path = LOG_DIR / f"combined_short_exit_shadow_{season}.json"
    gt_path = Path(__file__).resolve().parent.parent.parent / "sim" / "data" / "game_table.parquet"

    if not log_path.exists() or not gt_path.exists():
        return

    try:
        data = json.loads(log_path.read_text())
    except Exception:
        return

    gt = pd.read_parquet(gt_path)
    actuals = dict(zip(gt["game_pk"].astype(int), gt["actual_total"]))

    graded = 0
    for entry in data:
        if entry.get("resolved"):
            continue
        game_id = entry.get("game_id")
        closing = entry.get("closing_total")
        actual = actuals.get(int(game_id)) if game_id else None
        if actual is None or closing is None:
            continue

        entry["actual_total"] = float(actual)

        if actual > closing:
            entry["actual_result_over"] = 1
            entry["over_hit"] = True
        elif actual < closing:
            entry["actual_result_over"] = 0
            entry["over_hit"] = False
        else:
            entry["actual_result_over"] = 0
            entry["over_hit"] = False

        # Combined short exit is an OVER signal
        if entry.get("combined_short_exit_favorable_zone"):
            entry["result"] = ("WIN" if entry["over_hit"]
                               else "LOSS")
        else:
            entry["result"] = None

        entry["resolved"] = True
        graded += 1

    if graded > 0:
        log_path.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Combined short exit grader: resolved {graded} entries")
