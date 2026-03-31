#!/usr/bin/env python3
"""
CS013 Shadow — Bullpen blowup state model tracker.

SHADOW ONLY — does not affect live picks, bet sizing, or overlay activation.

Identifies games where 2+ relievers on the same team are individually
in a degraded state (trailing 5-appearance runs > 1.5x season baseline).

CS020 precision layer: acceleration/Bayesian variant computed for ALL games,
then combined with CS013 to assign signal_tier (HIGH / LOW / null).

Called from run_model.py after V1 signals are generated.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("cs013_shadow")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
DATA_PATH = Path(__file__).resolve().parent.parent.parent / "mlb" / "data" / "pitcher_game_logs.parquet"

# Frozen thresholds from Batch 3 (CS013 — unchanged)
DEGRADED_MULTIPLIER = 1.5   # trailing > 1.5x season baseline
DEGRADED_COUNT_IN_5 = 2     # 2+ degraded appearances in last 5
TEAM_THRESHOLD = 2           # 2+ degraded relievers on team
MIN_PRIOR_APPEARANCES = 5    # reliever needs 5+ prior appearances

# Frozen thresholds from Batch 4 Wave 1 (CS020 — precision refinement)
# Source: research/signal_discovery/safety_layer/test_results_log.json
# freeze_window: 2022-2023, freeze_n: 606, freeze_over_rate: 0.5974
CS020_ACCEL_CUTOFF = 0.3        # 3-game RA mean minus 10-game RA mean
CS020_BAYESIAN_SHIFT_CUTOFF = 0.2  # 3-game RA mean minus season mean
CS020_TEAM_THRESHOLD = 2        # 2+ accelerating relievers on team

# ── Cache (built once per pipeline run) ───────────────────
_team_cache = {}  # team → {"n_degraded": int}
_cs020_cache = {}  # team → {"n_accel": int, "max_accel_score": float}


def _build_cache():
    """
    Build per-team degraded reliever count from pitcher_game_logs.

    For each reliever:
      1. Compute season expanding mean of runs_allowed (shift 1)
      2. Flag appearances where runs > 1.5x season mean
      3. Count flagged appearances in rolling 5-game window (shift 1)
      4. Reliever is "degraded" if count >= 2

    Per team: count degraded relievers using latest game per reliever.
    """
    global _team_cache
    if _team_cache:
        return _team_cache

    try:
        if not DATA_PATH.exists():
            logger.warning("pitcher_game_logs.parquet not found — CS013 shadow disabled")
            return {}

        pl = pd.read_parquet(DATA_PATH)
        rlv = pl[pl["starter_flag"] == 0].sort_values(
            ["player_id", "game_date", "game_pk"]
        ).copy()

        # Season baseline per reliever (shift 1 = pregame only)
        # Grouped by (player_id, season) so baseline resets each year
        rlv["season_rpa"] = rlv.groupby(["player_id", "season"])[
            "runs_allowed"
        ].transform(lambda x: x.shift(1).expanding(min_periods=MIN_PRIOR_APPEARANCES).mean())

        # Flag individual degraded appearances
        rlv["degraded_app"] = (
            (rlv["runs_allowed"] > DEGRADED_MULTIPLIER * rlv["season_rpa"])
            & rlv["season_rpa"].notna()
        ).astype(int)

        # Count degraded in last 5 appearances WITHIN SAME SEASON (shift 1)
        # Grouped by (player_id, season) to prevent cross-season bleed
        rlv["deg_count_5"] = rlv.groupby(["player_id", "season"])[
            "degraded_app"
        ].transform(lambda x: x.shift(1).rolling(5, min_periods=3).sum())

        # Reliever is degraded if 2+ degraded apps in last 5 (same season)
        rlv["is_degraded"] = (rlv["deg_count_5"] >= DEGRADED_COUNT_IN_5).astype(int)

        # Use current year only — no fallback to prior seasons
        from datetime import date as _date
        current_year = _date.today().year

        if not (rlv["season"] == current_year).any():
            logger.info(f"  No {current_year} reliever data — all teams INSUFFICIENT_HISTORY")
            _team_cache = {"_status": "INSUFFICIENT_HISTORY"}
            return _team_cache

        recent = rlv[rlv["season"] == current_year].copy()
        latest = (
            recent.dropna(subset=["deg_count_5"])
            .sort_values(["player_id", "game_date", "game_pk"])
            .groupby(["team", "player_id"])
            .last()
            .reset_index()
        )

        if latest.empty:
            logger.info(f"  {current_year} data exists but no relievers have 5+ appearances yet")
            _team_cache = {"_status": "INSUFFICIENT_HISTORY"}
            return _team_cache

        team_counts = (
            latest.groupby("team")["is_degraded"]
            .sum()
            .reset_index()
            .rename(columns={"is_degraded": "n_degraded"})
        )

        _team_cache = {}
        for _, row in team_counts.iterrows():
            _team_cache[row["team"]] = {"n_degraded": int(row["n_degraded"])}

        logger.info(
            f"CS013 cache built: {len(_team_cache)} teams, "
            f"{sum(v['n_degraded'] >= TEAM_THRESHOLD for v in _team_cache.values())} with 2+ degraded"
        )
        return _team_cache

    except Exception as e:
        logger.warning(f"Failed to build CS013 cache: {e}")
        return {}


def _build_cs020_cache():
    """
    Build per-team accelerating reliever count from pitcher_game_logs.

    For each reliever:
      1. Compute 3-game rolling mean of runs_allowed (shift 1)
      2. Compute 10-game rolling mean of runs_allowed (shift 1)
      3. Compute season expanding mean of runs_allowed (shift 1)
      4. acceleration = ra_r3 - ra_r10 (short-term worsening)
      5. bayesian_shift = ra_r3 - season_mean (vs baseline)
      6. Flag if acceleration > 0.3 AND bayesian_shift > 0.2
      7. Per team: count flagged relievers, track max acceleration score
    """
    global _cs020_cache
    if _cs020_cache:
        return _cs020_cache

    try:
        if not DATA_PATH.exists():
            logger.warning("pitcher_game_logs.parquet not found — CS020 disabled")
            return {}

        pl = pd.read_parquet(DATA_PATH)
        rlv = pl[pl["starter_flag"] == 0].sort_values(
            ["player_id", "game_date", "game_pk"]
        ).copy()

        rlv["ra_r3"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
            lambda x: x.shift(1).rolling(3, min_periods=3).mean()
        )
        rlv["ra_r10"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
            lambda x: x.shift(1).rolling(10, min_periods=5).mean()
        )
        rlv["season_mean"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
            lambda x: x.shift(1).expanding(min_periods=5).mean()
        )

        rlv["acceleration"] = rlv["ra_r3"] - rlv["ra_r10"]
        rlv["bayesian_shift"] = rlv["ra_r3"] - rlv["season_mean"]

        rlv["accel_flag"] = (
            (rlv["acceleration"] > CS020_ACCEL_CUTOFF)
            & (rlv["bayesian_shift"] > CS020_BAYESIAN_SHIFT_CUTOFF)
            & rlv["ra_r3"].notna()
            & rlv["ra_r10"].notna()
        ).astype(int)

        # Use current year only
        from datetime import date as _date
        current_year = _date.today().year

        if not (rlv["season"] == current_year).any():
            logger.info(f"  No {current_year} reliever data — CS020 INSUFFICIENT_HISTORY")
            _cs020_cache = {"_status": "INSUFFICIENT_HISTORY"}
            return _cs020_cache

        recent = rlv[rlv["season"] == current_year].copy()
        valid = recent.dropna(subset=["acceleration", "bayesian_shift"])

        if valid.empty:
            logger.info(f"  {current_year} data exists but no relievers have enough appearances for CS020")
            _cs020_cache = {"_status": "INSUFFICIENT_HISTORY"}
            return _cs020_cache

        latest = (
            valid.sort_values(["player_id", "game_date", "game_pk"])
            .groupby(["team", "player_id"])
            .last()
            .reset_index()
        )

        team_agg = (
            latest.groupby("team")
            .agg(
                n_accel=("accel_flag", "sum"),
                max_accel_score=("acceleration", "max"),
            )
            .reset_index()
        )

        _cs020_cache = {}
        for _, row in team_agg.iterrows():
            _cs020_cache[row["team"]] = {
                "n_accel": int(row["n_accel"]),
                "max_accel_score": round(float(row["max_accel_score"]), 4),
            }

        logger.info(
            f"CS020 cache built: {len(_cs020_cache)} teams, "
            f"{sum(v['n_accel'] >= CS020_TEAM_THRESHOLD for v in _cs020_cache.values())} with 2+ accelerating"
        )
        return _cs020_cache

    except Exception as e:
        logger.warning(f"Failed to build CS020 cache: {e}")
        return {}


def compute_cs020(home_team, away_team):
    """
    Compute CS020 acceleration score and flag for a game.

    Computed for ALL games (not just CS013-flagged) to preserve
    diagnostic power for future CS020=TRUE + CS013=FALSE observation.

    Returns dict with acceleration scores and flag.
    Returns nulls if data insufficient.
    """
    if not _cs020_cache:
        _build_cs020_cache()

    if _cs020_cache.get("_status") == "INSUFFICIENT_HISTORY":
        return {
            "home_accel_relievers": None,
            "away_accel_relievers": None,
            "cs020_acceleration_score": None,
            "cs020_flag": None,
            "cs020_status": "INSUFFICIENT_HISTORY",
        }

    h = _cs020_cache.get(home_team, {})
    a = _cs020_cache.get(away_team, {})

    h_accel = h.get("n_accel", 0)
    a_accel = a.get("n_accel", 0)

    # Raw acceleration score = max of either team's max acceleration
    h_score = h.get("max_accel_score", 0.0)
    a_score = a.get("max_accel_score", 0.0)
    raw_score = round(max(h_score, a_score), 4)

    combined = max(h_accel, a_accel)
    flag = combined >= CS020_TEAM_THRESHOLD

    return {
        "home_accel_relievers": h_accel,
        "away_accel_relievers": a_accel,
        "cs020_acceleration_score": raw_score,
        "cs020_flag": flag,
        "cs020_status": "OK",
    }


def assign_signal_tier(cs013_flag, cs020_flag):
    """
    Assign signal tier based on CS013 + CS020 agreement.

    CS013=TRUE  + CS020=TRUE  → "HIGH"
    CS013=TRUE  + CS020=FALSE → "LOW"
    CS013=FALSE               → None
    Either flag is None        → None (insufficient data, do NOT default to LOW)
    """
    if cs013_flag is None or cs020_flag is None:
        return None
    if not cs013_flag:
        return None
    if cs020_flag:
        return "HIGH"
    return "LOW"


def compute_cs013(home_team, away_team):
    """
    Compute CS013 for a game.

    Returns dict with home/away degraded counts and flag.
    Returns nulls with status if current-season data is insufficient.
    """
    if not _team_cache:
        _build_cache()

    # Insufficient history — no current-season data
    if _team_cache.get("_status") == "INSUFFICIENT_HISTORY":
        return {
            "home_degraded_relievers": None,
            "away_degraded_relievers": None,
            "combined_degraded_count": None,
            "cs013_flag": None,
            "cs013_status": "INSUFFICIENT_2026_HISTORY",
        }

    h = _team_cache.get(home_team, {})
    a = _team_cache.get(away_team, {})

    h_deg = h.get("n_degraded", 0)
    a_deg = a.get("n_degraded", 0)
    combined = max(h_deg, a_deg)
    flag = combined >= TEAM_THRESHOLD

    return {
        "home_degraded_relievers": h_deg,
        "away_degraded_relievers": a_deg,
        "combined_degraded_count": combined,
        "cs013_flag": flag,
        "cs013_status": "OK",
    }


def _read_cs004_flag(game_id, season):
    """Read CS004 flag from cs004_shadow log if available."""
    try:
        cs004_path = LOG_DIR / f"cs004_shadow_{season}.json"
        if not cs004_path.exists():
            return None
        with open(cs004_path) as f:
            for r in json.load(f):
                if r.get("game_id") == game_id:
                    return bool(r.get("cs004_favorable_zone", False))
        return None
    except Exception:
        return None


def log_cs013_record(game_id, date, home_team, away_team,
                     cs013_result, v1_direction_context,
                     closing_total=None, cs020_result=None):
    """
    Append a CS013 shadow record to JSON log.
    Includes CS020 acceleration score, flag, and signal_tier.
    Deduplicates by game_id.
    """
    season = int(str(date)[:4])
    log_path = LOG_DIR / f"cs013_shadow_{season}.json"

    cs004_flag = _read_cs004_flag(game_id, season)

    # CS020 fields (null-safe)
    cs020 = cs020_result or {}
    cs020_accel_score = cs020.get("cs020_acceleration_score")
    cs020_flag = cs020.get("cs020_flag")
    tier = assign_signal_tier(cs013_result.get("cs013_flag"), cs020_flag)

    record = {
        "game_id": game_id,
        "date": str(date),
        "home_team": home_team,
        "away_team": away_team,
        "home_degraded_relievers": cs013_result["home_degraded_relievers"],
        "away_degraded_relievers": cs013_result["away_degraded_relievers"],
        "combined_degraded_count": cs013_result["combined_degraded_count"],
        "cs013_flag": cs013_result["cs013_flag"],
        "cs013_status": cs013_result.get("cs013_status", "OK"),
        "cs020_acceleration_score": cs020_accel_score,
        "cs020_flag": cs020_flag,
        "signal_tier": tier,
        "cs004_flag": cs004_flag,
        "v1_direction_context": v1_direction_context,
        "closing_total": closing_total,
        "logged_at": datetime.now().isoformat(),
    }

    records = []
    if log_path.exists():
        try:
            with open(log_path) as f:
                records = json.load(f)
        except (json.JSONDecodeError, Exception):
            records = []

    records = [r for r in records if r.get("game_id") != game_id]
    records.append(record)

    with open(log_path, "w") as f:
        json.dump(records, f, indent=2)

    if cs013_result["cs013_flag"]:
        tier_str = f" [{tier}]" if tier else ""
        logger.info(
            f"  CS013 shadow: {away_team}@{home_team} — "
            f"{cs013_result['combined_degraded_count']} degraded relievers "
            f"FLAGGED{tier_str} (V1={v1_direction_context})"
        )

    return record
