#!/usr/bin/env python3
"""
KP04 Shadow — Breaking-ball pitcher x high-K lineup (K OVER).

SHADOW ONLY — passive data collection, does not affect live picks.

Logs one record per eligible start to kp04_shadow_2026.json.
Fires only after lineups are confirmed.

Frozen thresholds from safety-layer test:
  BB% >= 0.3826 (slider + sweeper + curveball combined, P75 2023)
  Lineup K% >= 0.2431 (confirmed lineup, P75 2023)
  Over odds > -150 (price floor)
  Minimum 5 prior starts for pitcher
"""

import json
import logging
import glob
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("kp04_shadow")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
DATA_PATH = Path(__file__).resolve().parent.parent.parent / "mlb" / "data" / "pitcher_game_logs.parquet"
SC_DIR = Path(__file__).resolve().parent.parent.parent / "mlb" / "props" / "data"
LINEUP_PATH = Path(__file__).resolve().parent.parent.parent / "research" / "mlb_v3_lineup_model" / "hitter_rolling_profiles.parquet"

# Frozen thresholds
BB_THRESHOLD = 0.3826
LINEUP_K_THRESHOLD = 0.2431
PRICE_FLOOR = -150
MIN_PRIOR_STARTS = 5

BB_TYPES = {"SL", "CU", "KC", "CS", "ST", "SV"}

# ── Cache ─────────────────────────────────────────────────
_bb_cache = {}  # pitcher_id → bb_pct (current season)
_lineup_k_cache = {}  # team → lineup_k_rate
_start_count_cache = {}  # pitcher_id → start_num


def _build_bb_cache():
    """Build per-pitcher breaking ball usage from Statcast for current season."""
    global _bb_cache
    if _bb_cache:
        return _bb_cache

    try:
        from datetime import date
        current_year = date.today().year

        sc_files = sorted(glob.glob(str(SC_DIR / "statcast_chunk_*.parquet")))
        if not sc_files:
            return {}

        # Load only current year chunks
        dfs = []
        for f in sc_files:
            if str(current_year) in Path(f).stem:
                chunk = pd.read_parquet(f, columns=["game_pk", "pitcher", "game_year",
                                                      "pitch_type", "game_type",
                                                      "inning", "inning_topbot",
                                                      "at_bat_number", "pitch_number"])
                chunk = chunk[chunk["game_type"] == "R"]
                dfs.append(chunk)

        if not dfs:
            logger.info("  KP04: no current-year Statcast data — using all available")
            # Fall back to last available chunk for season-to-date
            chunk = pd.read_parquet(sc_files[-1], columns=["game_pk", "pitcher", "game_year",
                                                             "pitch_type", "game_type",
                                                             "inning", "inning_topbot",
                                                             "at_bat_number", "pitch_number"])
            chunk = chunk[chunk["game_type"] == "R"]
            dfs = [chunk]

        sc = pd.concat(dfs, ignore_index=True)
        sc = sc.sort_values(["game_pk", "inning", "inning_topbot", "at_bat_number", "pitch_number"])

        # Identify starters
        first = sc.groupby(["game_pk", "inning_topbot"]).first().reset_index()
        starters = first[first["inning"] == 1][["game_pk", "inning_topbot", "pitcher"]].rename(
            columns={"pitcher": "starter_id"})
        sc_s = sc.merge(starters, on=["game_pk", "inning_topbot"])
        sc_s = sc_s[sc_s["pitcher"] == sc_s["starter_id"]].copy()

        sc_s["is_bb"] = sc_s["pitch_type"].isin(BB_TYPES).astype(int)

        # Season-to-date BB% per pitcher
        per_pitcher = sc_s.groupby("starter_id").agg(
            n_pitches=("pitch_type", "count"),
            n_bb=("is_bb", "sum"),
        ).reset_index()
        per_pitcher["bb_pct"] = per_pitcher["n_bb"] / per_pitcher["n_pitches"]

        _bb_cache = dict(zip(per_pitcher["starter_id"], per_pitcher["bb_pct"]))
        logger.info(f"KP04 BB cache: {len(_bb_cache)} pitchers")
        return _bb_cache

    except Exception as e:
        logger.warning(f"KP04 BB cache build failed: {e}")
        return {}


def _build_start_count_cache():
    """Count prior starts per pitcher in current season."""
    global _start_count_cache
    if _start_count_cache:
        return _start_count_cache

    try:
        from datetime import date
        current_year = date.today().year
        pl = pd.read_parquet(DATA_PATH)
        pl_s = pl[(pl["starter_flag"] == 1) & (pl["season"] == current_year)]
        counts = pl_s.groupby("player_id").size()
        _start_count_cache = dict(counts)
        return _start_count_cache
    except Exception:
        return {}


def compute_kp04(game_id, date_str, home_team, away_team,
                 home_pitcher_id, away_pitcher_id,
                 home_pitcher_name, away_pitcher_name,
                 k_lines=None, lineup_data=None):
    """
    Compute KP04 for both starters in a game.

    Args:
        k_lines: dict with pitcher K prop lines and odds
            {pitcher_id: {"k_line": 5.5, "over_price": -120, "under_price": 100}}
        lineup_data: dict with team lineup K rates
            {team: lineup_k_rate} — None if lineups not confirmed

    Returns: list of shadow records (0-2 per game)
    """
    if not _bb_cache:
        _build_bb_cache()
    if not _start_count_cache:
        _build_start_count_cache()

    records = []
    lineup_confirmed = lineup_data is not None

    for pitcher_id, pitcher_name, opp_team in [
        (home_pitcher_id, home_pitcher_name, away_team),
        (away_pitcher_id, away_pitcher_name, home_team),
    ]:
        if pitcher_id is None:
            continue

        pid = int(pitcher_id) if pitcher_id else None
        bb_usage = _bb_cache.get(pid)
        start_count = _start_count_cache.get(pid, 0)
        lineup_k = lineup_data.get(opp_team) if lineup_data else None

        # K prop line/odds
        kl = (k_lines or {}).get(pid, {})
        k_line = kl.get("k_line")
        over_odds = kl.get("over_price")

        # Flag determination
        kp04_flag = False
        if (bb_usage is not None and bb_usage >= BB_THRESHOLD and
            lineup_k is not None and lineup_k >= LINEUP_K_THRESHOLD and
            over_odds is not None and over_odds > PRICE_FLOOR and
            start_count >= MIN_PRIOR_STARTS):
            kp04_flag = True

        records.append({
            "game_id": game_id,
            "date": date_str,
            "pitcher_name": pitcher_name,
            "pitcher_id": pid,
            "bb_usage": round(float(bb_usage), 4) if bb_usage is not None else None,
            "lineup_k_pct": round(float(lineup_k), 4) if lineup_k is not None else None,
            "over_odds": int(over_odds) if over_odds is not None else None,
            "kp04_flag": kp04_flag,
            "lineup_confirmed": lineup_confirmed,
            "k_line": float(k_line) if k_line is not None else None,
            "opening_k_line": float(k_line) if k_line is not None else None,
            "closing_k_line": None,
            "actual_k": None,
            "result": None,
            "logged_at": datetime.now().isoformat(),
        })

    return records


def log_kp04_records(records):
    """Append records to kp04_shadow_2026.json. Dedup by (game_id, pitcher_id)."""
    if not records:
        return

    log_path = LOG_DIR / "kp04_shadow_2026.json"

    existing = []
    if log_path.exists():
        try:
            with open(log_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, Exception):
            existing = []

    # Dedup
    seen = {(r.get("game_id"), r.get("pitcher_id")) for r in existing}
    new = [r for r in records if (r.get("game_id"), r.get("pitcher_id")) not in seen]

    if new:
        existing.extend(new)
        with open(log_path, "w") as f:
            json.dump(existing, f, indent=2)

        flagged = sum(1 for r in new if r.get("kp04_flag"))
        pending = sum(1 for r in new if not r.get("lineup_confirmed"))
        logger.info(f"KP04 shadow: {len(new)} logged, {flagged} flagged"
                    f"{f', {pending} PENDING_LINEUP' if pending else ''}")
