#!/usr/bin/env python3
"""
ST02 Overlay — Road-trip fatigue UNDER amplifier.

Fires when the away team is on game 6+ of a consecutive road trip.
Blocked when P09 is active (signals interfere; historical ROI -15.6% on overlap).

Does NOT generate standalone bets. Only tags existing V1 UNDER signals.
"""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("st02_overlay")

CONFIG_PATH = Path(__file__).resolve().parent / "st02_overlay_config.json"

_DEFAULT_CONFIG = {
    "road_trip_threshold": 6,
    "overlay_status": "ACTIVE",
    "overlay_version": "1.0",
}


def _load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return _DEFAULT_CONFIG


# ── Road-trip lookup (built once per pipeline run) ────────────────────

_road_trip_cache = {}


def _build_road_trip_lookup():
    """
    Build dict: game_pk → road_trip_game_num for the away team.
    Uses sim/data/game_table.parquet. Resets streak at season boundaries.
    """
    global _road_trip_cache
    if _road_trip_cache:
        return _road_trip_cache

    try:
        import pandas as pd
        gt_path = Path(__file__).resolve().parent.parent.parent / "sim" / "data" / "game_table.parquet"
        if not gt_path.exists():
            logger.warning("game_table.parquet not found — ST02 overlay disabled")
            return {}

        gt = pd.read_parquet(gt_path, columns=["game_pk", "date", "season", "home_team", "away_team"])
        gt["date"] = pd.to_datetime(gt["date"])
        gt = gt.sort_values("date")

        # Build team-game list
        rows = []
        for _, r in gt.iterrows():
            rows.append({"game_pk": r["game_pk"], "date": r["date"],
                         "season": r["season"], "team": r["away_team"], "is_away": True})
            rows.append({"game_pk": r["game_pk"], "date": r["date"],
                         "season": r["season"], "team": r["home_team"], "is_away": False})

        tg = pd.DataFrame(rows).sort_values(["team", "date", "game_pk"]).reset_index(drop=True)

        # Compute consecutive away streak, reset at season boundary
        streak = np.zeros(len(tg), dtype=int)
        prev_team, prev_season, s = None, None, 0
        for i, row in enumerate(tg.itertuples()):
            if row.team != prev_team or row.season != prev_season:
                s = 0
                prev_team = row.team
                prev_season = row.season
            s = s + 1 if row.is_away else 0
            streak[i] = s
        tg["rtgn"] = streak

        away_only = tg[tg["is_away"]]
        _road_trip_cache = dict(zip(away_only["game_pk"].astype(int), away_only["rtgn"].astype(int)))
        logger.info(f"ST02 road-trip lookup built: {len(_road_trip_cache)} games")
        return _road_trip_cache
    except Exception as e:
        logger.warning(f"Failed to build ST02 road-trip lookup: {e}")
        return {}


def compute_st02(game_id):
    """
    Look up the away team's road trip game number.
    Returns int or None.
    """
    if not _road_trip_cache:
        _build_road_trip_lookup()
    if game_id is None:
        return None
    return _road_trip_cache.get(int(game_id))


def evaluate_st02_overlay(st02_value, p09_active):
    """
    Evaluate whether ST02 overlay fires.

    ST02 fires when:
      1. road_trip_game_num >= threshold (default 6)
      2. P09 is NOT active (interference block)
      3. Config status == ACTIVE

    Returns dict with st02_value, st02_overlay_active, st02_blocked_by_p09.
    """
    cfg = _load_config()
    threshold = cfg.get("road_trip_threshold", 6)
    status = cfg.get("overlay_status", "ACTIVE")

    favorable = st02_value is not None and st02_value >= threshold
    blocked = favorable and p09_active

    result = {
        "st02_value": st02_value,
        "st02_threshold": threshold,
        "st02_favorable_zone": 1 if favorable else 0,
        "st02_overlay_active": 0,
        "st02_blocked_by_p09": 1 if blocked else 0,
    }

    if status != "ACTIVE":
        return result

    if favorable and not p09_active:
        result["st02_overlay_active"] = 1
        logger.info(f"  ST02 overlay ACTIVE: road_trip_game={st02_value} >= {threshold}")
    elif blocked:
        logger.info(f"  ST02 overlay BLOCKED by P09: road_trip_game={st02_value} (favorable but P09 active)")

    return result
