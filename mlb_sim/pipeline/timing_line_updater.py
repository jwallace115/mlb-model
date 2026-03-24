#!/usr/bin/env python3
"""
MLB Sim Engine — Timing Line Updater
=====================================
Captures full-game total at each scheduled pull time for signaled games.
Observational research layer only — does not affect signal generation.

Columns managed (added to signals_2026.parquet):
  line_at_open, line_at_midday, line_at_close,
  clv_vs_open, clv_vs_midday, clv_vs_close_pull

Fill rule: idempotent — earliest captured value preserved, never overwritten.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("timing_lines")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIGNALS_PATH = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.parquet"

TIMING_COLS = [
    "line_at_open", "line_at_midday", "line_at_close",
    "clv_vs_open", "clv_vs_midday", "clv_vs_close_pull",
]

_PULL_TYPE_TO_COL = {
    "open": "line_at_open",
    "midday": "line_at_midday",
    "close": "line_at_close",
}


def _ensure_timing_columns(df):
    """Add timing columns if not present. Initialize to null."""
    changed = False
    for col in TIMING_COLS:
        if col not in df.columns:
            df[col] = None
            changed = True
    return df, changed


def _load_signals():
    if not SIGNALS_PATH.exists():
        return None
    return pd.read_parquet(SIGNALS_PATH)


def _save_signals(df):
    df.to_parquet(SIGNALS_PATH, index=False)


def update_timing_lines(game_date_str, pull_type, all_lines=None):
    """
    Update timing line columns for all signaled games on game_date.

    Args:
        game_date_str: "YYYY-MM-DD"
        pull_type: "open" | "midday" | "close"
        all_lines: pre-fetched odds dict from modules/odds.py (optional).
                   If None, will attempt to fetch.
    """
    col = _PULL_TYPE_TO_COL.get(pull_type)
    if col is None:
        logger.warning(f"Unknown pull_type: {pull_type}")
        return

    sigs = _load_signals()
    if sigs is None or sigs.empty:
        return

    sigs, cols_added = _ensure_timing_columns(sigs)

    # Find today's signals that need this timing line
    today = sigs[sigs["date"] == game_date_str]
    if today.empty:
        if cols_added:
            _save_signals(sigs)
        return

    # Fetch lines if not provided
    if all_lines is None:
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from modules.odds import fetch_all_lines
            all_lines = fetch_all_lines(game_date_str)
        except Exception as e:
            logger.warning(f"Timing line fetch failed: {e}")
            if cols_added:
                _save_signals(sigs)
            return

    sys.path.insert(0, str(PROJECT_ROOT))
    from modules.odds import get_game_lines

    updated = 0
    for idx in today.index:
        # Idempotent: skip if already filled
        if pd.notna(sigs.at[idx, col]):
            continue

        home = sigs.at[idx, "home_team"]
        away = sigs.at[idx, "away_team"]
        game_lines = get_game_lines(home, away, all_lines)
        full_data = game_lines.get("full") or {}
        line = full_data.get("consensus")

        if line is not None:
            sigs.at[idx, col] = float(line)
            updated += 1

    if updated > 0 or cols_added:
        _save_signals(sigs)
    if updated > 0:
        logger.info(f"Timing {pull_type}: {updated} lines captured for {game_date_str}")


def backfill_from_snapshots(game_date_str, game_id, home_team, away_team):
    """
    At signal creation time, backfill line_at_open and line_at_midday
    from daily market snapshots already captured by the main pipeline.
    Does NOT make API calls — reads existing snapshot data only.
    """
    sigs = _load_signals()
    if sigs is None or sigs.empty:
        return

    sigs, _ = _ensure_timing_columns(sigs)
    gid = str(game_id)

    mask = ((sigs["game_id"].astype(str) == gid) & (sigs["date"] == game_date_str))
    if not mask.any():
        return

    # Try to read from market_snapshots (main pipeline's snapshot store)
    snap_path = PROJECT_ROOT / "data" / "cache" / f"odds_full_{game_date_str}.json"
    if not snap_path.exists():
        # Try alternative: the MLb model's daily odds cache
        import glob
        candidates = glob.glob(str(PROJECT_ROOT / "data" / "cache" / f"odds_*{game_date_str}*"))
        if candidates:
            snap_path = Path(candidates[0])
        else:
            return

    try:
        import json
        with open(snap_path) as f:
            snap_data = json.load(f)

        # Extract line for this game from cached odds
        # The cache format may vary — try common patterns
        sys.path.insert(0, str(PROJECT_ROOT))
        from modules.odds import get_game_lines
        game_lines = get_game_lines(home_team, away_team, snap_data)
        full_data = game_lines.get("full") or {}
        line = full_data.get("consensus")

        if line is not None:
            idx = sigs[mask].index[0]
            # Backfill open if not already set
            if pd.isna(sigs.at[idx, "line_at_open"]):
                sigs.at[idx, "line_at_open"] = float(line)
            _save_signals(sigs)
    except Exception as e:
        logger.debug(f"Snapshot backfill failed (non-fatal): {e}")


def compute_clv_timing(sigs=None):
    """
    Compute CLV fields for all resolved signals where timing lines exist.
    Positive CLV = closing line moved UP (good for under signals).
    """
    if sigs is None:
        sigs = _load_signals()
    if sigs is None or sigs.empty:
        return sigs

    sigs, _ = _ensure_timing_columns(sigs)

    # Only compute for resolved signals with closing_line
    resolved = sigs["closing_line"].notna()

    for ref_col, clv_col in [
        ("line_at_open", "clv_vs_open"),
        ("line_at_midday", "clv_vs_midday"),
        ("line_at_close", "clv_vs_close_pull"),
    ]:
        mask = resolved & sigs[ref_col].notna()
        sigs.loc[mask, clv_col] = (
            sigs.loc[mask, "closing_line"].astype(float) -
            sigs.loc[mask, ref_col].astype(float)
        )

    _save_signals(sigs)
    return sigs
