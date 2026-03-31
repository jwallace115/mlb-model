#!/usr/bin/env python3
"""
CS004 Shadow — Bullpen collapse tail risk tracker.

SHADOW ONLY — does not affect live picks, bet sizing, or overlay activation.

Computes bullpen_tail_score for each game and logs to shadow file.
Called from run_model.py after V1 signals are generated.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("cs004_shadow")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
DATA_PATH = Path(__file__).resolve().parent.parent.parent / "mlb" / "data" / "pitcher_game_logs.parquet"

# Frozen threshold from 2022-2023 top-20% (computed in test_batch_1)
FROZEN_THRESHOLD = 6.2667

# ── Bullpen tail score cache (built once per pipeline run) ────────────
_bp_cache = {}   # team → latest tail_score


def _build_bp_cache():
    """
    Build per-team bullpen tail score from pitcher_game_logs.parquet.

    For each team, compute rolling 10-game:
      - mean variance of runs_allowed per reliever appearance
      - max runs_allowed in any single appearance
      - tail_score = var + max

    Uses shift(1) to exclude the current game (pregame safe).
    Requires minimum 8 cumulative appearances in the 10-game window.

    Returns dict: team → {tail_score, high_tail}.
    """
    global _bp_cache
    if _bp_cache:
        return _bp_cache

    try:
        if not DATA_PATH.exists():
            logger.warning("pitcher_game_logs.parquet not found — CS004 shadow disabled")
            return {}

        pl = pd.read_parquet(DATA_PATH)
        rlv = pl[pl["starter_flag"] == 0].copy()
        rlv = rlv.sort_values(["team", "game_date", "game_pk"])

        # Per team-game: aggregate reliever stats
        team_bp = rlv.groupby(["game_pk", "team"]).agg(
            bp_runs_var=("runs_allowed", "var"),
            bp_runs_max=("runs_allowed", "max"),
            bp_appearances=("player_id", "count"),
        ).reset_index()

        # Need game_date for ordering — get from pitcher logs
        game_dates = pl.drop_duplicates("game_pk")[["game_pk", "game_date", "season"]]
        team_bp = team_bp.merge(game_dates, on="game_pk", how="left")
        team_bp["game_date"] = pd.to_datetime(team_bp["game_date"])
        team_bp = team_bp.sort_values(["team", "game_date", "game_pk"])

        # Rolling 10-game stats with shift(1) for pregame safety
        team_bp["bp_var_r10"] = team_bp.groupby("team")["bp_runs_var"].transform(
            lambda x: x.shift(1).rolling(10, min_periods=8).mean()
        )
        team_bp["bp_max_r10"] = team_bp.groupby("team")["bp_runs_max"].transform(
            lambda x: x.shift(1).rolling(10, min_periods=8).max()
        )
        team_bp["tail_score"] = team_bp["bp_var_r10"].fillna(0) + team_bp["bp_max_r10"].fillna(0)

        # Minimum 8 appearances in window
        team_bp["cum_app_r10"] = team_bp.groupby("team")["bp_appearances"].transform(
            lambda x: x.shift(1).rolling(10, min_periods=1).sum()
        )
        team_bp.loc[team_bp["cum_app_r10"] < 8, "tail_score"] = np.nan

        # Keep latest per team
        latest = (
            team_bp.dropna(subset=["tail_score"])
            .sort_values(["team", "game_date", "game_pk"])
            .groupby("team")
            .last()
            .reset_index()
        )

        _bp_cache = {}
        for _, row in latest.iterrows():
            _bp_cache[row["team"]] = {
                "tail_score": round(float(row["tail_score"]), 4),
                "high_tail": bool(row["tail_score"] >= FROZEN_THRESHOLD),
            }

        logger.info(f"CS004 bullpen cache built: {len(_bp_cache)} teams, "
                     f"threshold={FROZEN_THRESHOLD:.4f}")
        return _bp_cache

    except Exception as e:
        logger.warning(f"Failed to build CS004 bullpen cache: {e}")
        return {}


def get_team_tail_score(team):
    """Look up a team's latest bullpen tail score. Returns dict or None."""
    if not _bp_cache:
        _build_bp_cache()
    return _bp_cache.get(team)


def compute_cs004(home_team, away_team):
    """
    Compute CS004 for a game.

    Returns dict with home/away tail scores, combined score, and favorable zone flag.
    """
    home = get_team_tail_score(home_team) or {}
    away = get_team_tail_score(away_team) or {}

    h_ts = home.get("tail_score")
    a_ts = away.get("tail_score")

    if h_ts is not None and a_ts is not None:
        combined = max(h_ts, a_ts)
        favorable = combined >= FROZEN_THRESHOLD
    elif h_ts is not None:
        combined = h_ts
        favorable = h_ts >= FROZEN_THRESHOLD
    elif a_ts is not None:
        combined = a_ts
        favorable = a_ts >= FROZEN_THRESHOLD
    else:
        combined = None
        favorable = False

    return {
        "home_bullpen_tail_score": h_ts,
        "away_bullpen_tail_score": a_ts,
        "combined_tail_score": round(combined, 4) if combined is not None else None,
        "cs004_favorable_zone": favorable,
    }


def _read_st02_flag(game_id, season):
    """
    Read the ST02 flag for a game from shadow_signals_{season}.json.
    Returns True/False/None.
    """
    try:
        st02_path = LOG_DIR / f"shadow_signals_{season}.json"
        if not st02_path.exists():
            return None
        with open(st02_path) as f:
            records = json.load(f)
        for r in records:
            if r.get("game_id") == game_id and r.get("signal_name", "").startswith("ST02"):
                return bool(r.get("favorable_zone_flag", False))
        return None
    except Exception:
        return None


def log_cs004_record(game_id, date, home_team, away_team,
                     cs004_result, v1_direction_context,
                     closing_total=None):
    """
    Append a CS004 shadow record to the JSON log.
    Deduplicates by game_id.
    """
    season = int(str(date)[:4])
    log_path = LOG_DIR / f"cs004_shadow_{season}.json"

    # Read ST02 flag for conflict detection
    st02_flag = _read_st02_flag(game_id, season)
    cs004_zone = cs004_result.get("cs004_favorable_zone", False)
    conflict = bool(st02_flag and cs004_zone)

    record = {
        "game_id": game_id,
        "date": str(date),
        "home_team": home_team,
        "away_team": away_team,
        "home_bullpen_tail_score": cs004_result.get("home_bullpen_tail_score"),
        "away_bullpen_tail_score": cs004_result.get("away_bullpen_tail_score"),
        "combined_tail_score": cs004_result.get("combined_tail_score"),
        "cs004_favorable_zone": cs004_zone,
        "st02_flag": st02_flag,
        "st02_cs004_conflict": conflict,
        "v1_direction_context": v1_direction_context,
        "closing_total": closing_total,
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

    if cs004_zone:
        conflict_note = " ⚠ ST02 CONFLICT" if conflict else ""
        logger.info(f"  CS004 shadow: {away_team}@{home_team} — "
                     f"tail={cs004_result['combined_tail_score']:.3f} "
                     f"FAVORABLE ZONE (V1={v1_direction_context}){conflict_note}")

    return record
