#!/usr/bin/env python3
"""
NFL Phase 8: Conditional Signal Engine.

Generates OVER signals for games matching frozen segment definitions.
Reads segment config from config_conditional_edges.json — never hardcodes conditions.
Appends to nfl_conditional_signals.parquet and grades to nfl_conditional_results.parquet.

Usage:
    python3 nfl/phase8_conditional_signals.py
    python3 nfl/phase8_conditional_signals.py --date 2026-12-15
    python3 nfl/phase8_conditional_signals.py --grade-yesterday
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NFL_DIR = Path(__file__).resolve().parent
DATA_DIR = NFL_DIR / "data"
CONFIG_PATH = NFL_DIR / "config_conditional_edges.json"
SIGNALS_PATH = DATA_DIR / "nfl_conditional_signals.parquet"
RESULTS_PATH = DATA_DIR / "nfl_conditional_results.parquet"
STOP_RULES_PATH = DATA_DIR / "nfl_conditional_stop_rules.json"
CANONICAL_PATH = DATA_DIR / "nfl_canonical.parquet"
LINE_MOVE_PATH = DATA_DIR / "nfl_line_movement.parquet"

WIN_PER_UNIT = 100.0 / 110.0
SEGMENT_MIN_N = 30
SEGMENT_ROI_THRESHOLD = -0.10
GLOBAL_MIN_N = 75
GLOBAL_ROI_THRESHOLD = -0.12


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.error(f"Config not found: {CONFIG_PATH}")
        return {}
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    if not cfg.get("frozen"):
        logger.error("Config is not frozen — refusing to run")
        return {}
    return cfg


def load_stop_rules() -> dict:
    if STOP_RULES_PATH.exists():
        with open(STOP_RULES_PATH) as f:
            return json.load(f)
    return {
        "model_suspended": False,
        "suspended_segments": [],
        "live_signals_total": 0,
    }


def save_stop_rules(state: dict):
    with open(STOP_RULES_PATH, "w") as f:
        json.dump(state, f, indent=2)


def evaluate_stop_rules() -> dict:
    state = load_stop_rules()
    if not RESULTS_PATH.exists():
        return state

    try:
        results = pd.read_parquet(RESULTS_PATH)
    except Exception:
        return state

    live = results[results.get("market_snapshot_status", pd.Series()) == "live"] if "market_snapshot_status" in results.columns else pd.DataFrame()
    graded = live[live["graded"] == True] if not live.empty and "graded" in live.columns else pd.DataFrame()

    if graded.empty:
        return state

    def _roi(df):
        w = int((df["result"] == "WIN").sum())
        l = int((df["result"] == "LOSS").sum())
        n = w + l
        return (w * WIN_PER_UNIT - l) / n if n > 0 else None

    # Per segment
    suspended = list(state.get("suspended_segments", []))
    for seg_name in graded["segment_name"].unique():
        sub = graded[graded["segment_name"] == seg_name]
        n = len(sub)
        roi = _roi(sub)
        if n >= SEGMENT_MIN_N and roi is not None and roi < SEGMENT_ROI_THRESHOLD:
            if seg_name not in suspended:
                suspended.append(seg_name)
                logger.warning(f"Segment {seg_name} SUSPENDED: n={n}, ROI={roi:.1%}")

    # Global
    total_n = len(graded)
    overall_roi = _roi(graded)
    if total_n >= GLOBAL_MIN_N and overall_roi is not None and overall_roi < GLOBAL_ROI_THRESHOLD:
        state["model_suspended"] = True
        logger.warning(f"NFL conditional model SUSPENDED: n={total_n}, ROI={overall_roi:.1%}")

    state["suspended_segments"] = suspended
    state["live_signals_total"] = total_n
    save_stop_rules(state)
    return state


def match_segment(game: dict, segment: dict) -> bool:
    """Check if a game matches a segment's conditions."""
    conditions = segment.get("conditions", {})

    for key, value in conditions.items():
        if key == "is_dome":
            if game.get("is_dome") != value:
                return False

        elif key == "closing_total_line_lt":
            line = game.get("closing_total_line")
            if line is None or line >= value:
                return False

        elif key == "week_gte":
            week = game.get("week")
            if week is None or week < value:
                return False

        elif key == "abs_line_move_lt":
            lm = game.get("line_move")
            if lm is None:
                return False  # skip if unavailable, don't assume 0
            if abs(lm) >= value:
                return False

    return True


def generate_signals(game_date: str, cfg: dict, stop_state: dict) -> list[dict]:
    """Generate conditional signals for games on game_date."""
    if not CANONICAL_PATH.exists():
        return []

    canon = pd.read_parquet(CANONICAL_PATH)
    games = canon[canon["date"] == game_date]

    if games.empty:
        logger.info(f"No games on {game_date}")
        return []

    # Try to get line movement data
    lm_data = {}
    if LINE_MOVE_PATH.exists():
        try:
            lm = pd.read_parquet(LINE_MOVE_PATH)
            for _, row in lm.iterrows():
                lm_data[row["game_id"]] = row.get("line_move")
        except Exception:
            pass

    signals = []
    now_utc = datetime.now(timezone.utc).isoformat()

    for _, game in games.iterrows():
        game_dict = game.to_dict()
        game_dict["line_move"] = lm_data.get(game_dict.get("game_id"))

        for segment in cfg.get("segments", []):
            seg_name = segment["segment_name"]

            # Check stop rules
            if stop_state.get("model_suspended"):
                continue
            if seg_name in stop_state.get("suspended_segments", []):
                continue

            if match_segment(game_dict, segment):
                sig = {
                    "date": game_date,
                    "game_id": game_dict["game_id"],
                    "home_team": game_dict["home_team"],
                    "away_team": game_dict["away_team"],
                    "segment_name": seg_name,
                    "display_name": segment["display_name"],
                    "bet_side": segment["bet_side"],
                    "closing_total_line": game_dict.get("closing_total_line"),
                    "line_move": game_dict.get("line_move"),
                    "is_dome": game_dict.get("is_dome"),
                    "week": int(game_dict.get("week", 0)),
                    "market_snapshot_status": "live",
                    "decision_line": game_dict.get("closing_total_line"),
                    "decision_line_source": "closing",
                    "decision_timestamp": now_utc,
                    "risk_note": segment.get("risk_note", "standard"),
                }
                signals.append(sig)
                logger.info(f"  Signal: {seg_name} — {game_dict['away_team']} @ {game_dict['home_team']} "
                            f"OVER {game_dict.get('closing_total_line')}")

    return signals


def append_signals(signals: list[dict]):
    if not signals:
        return
    new_df = pd.DataFrame(signals)
    if SIGNALS_PATH.exists():
        existing = pd.read_parquet(SIGNALS_PATH)
        # Deduplicate on game_id + segment_name
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["game_id", "segment_name"], keep="last")
    else:
        combined = new_df
    combined.to_parquet(SIGNALS_PATH, index=False)
    logger.info(f"Signals: {len(signals)} new, {len(combined)} total in {SIGNALS_PATH}")


def grade_signals(grade_date: str):
    """Grade signals for a specific date using canonical results."""
    if not SIGNALS_PATH.exists() or not CANONICAL_PATH.exists():
        return

    signals = pd.read_parquet(SIGNALS_PATH)
    canon = pd.read_parquet(CANONICAL_PATH)

    to_grade = signals[signals["date"] == grade_date].copy()
    if to_grade.empty:
        logger.info(f"No signals to grade for {grade_date}")
        return

    results = []
    for _, sig in to_grade.iterrows():
        game = canon[canon["game_id"] == sig["game_id"]]
        if game.empty:
            continue
        game = game.iloc[0]

        actual = game.get("total_points")
        line = sig.get("decision_line")
        if actual is None or line is None:
            continue

        if actual > line:
            result = "WIN"
            profit = WIN_PER_UNIT
        elif actual < line:
            result = "LOSS"
            profit = -1.0
        else:
            result = "PUSH"
            profit = 0.0

        res = {
            "game_id": sig["game_id"],
            "date": sig["date"],
            "segment_name": sig["segment_name"],
            "bet_side": sig["bet_side"],
            "decision_line": line,
            "actual_total": float(actual),
            "result": result,
            "profit": profit,
            "graded": True,
            "market_snapshot_status": sig.get("market_snapshot_status", "live"),
        }

        # Monitoring for no_move_low_total
        if sig["segment_name"] == "no_move_low_total":
            logger.warning(f"  ⚠️ no_move_low_total: {result} (actual={actual}, line={line}) "
                           f"— monitoring vs 82.6% baseline")

        results.append(res)

    if not results:
        return

    new_df = pd.DataFrame(results)
    if RESULTS_PATH.exists():
        existing = pd.read_parquet(RESULTS_PATH)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["game_id", "segment_name"], keep="last")
    else:
        combined = new_df
    combined.to_parquet(RESULTS_PATH, index=False)

    w = (new_df["result"] == "WIN").sum()
    l = (new_df["result"] == "LOSS").sum()
    logger.info(f"Graded {len(new_df)} signals for {grade_date}: {w}W-{l}L")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--grade-yesterday", action="store_true")
    parser.add_argument("--grade-date", default=None)
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()

    cfg = load_config()
    if not cfg:
        return

    logger.info(f"NFL conditional signals — {game_date} (config v{cfg['version']})")

    # Grade yesterday or specific date
    if args.grade_yesterday:
        gd = (date.fromisoformat(game_date) - timedelta(days=1)).isoformat()
        grade_signals(gd)
    if args.grade_date:
        grade_signals(args.grade_date)

    # Evaluate stop rules
    stop_state = evaluate_stop_rules()
    if stop_state.get("model_suspended"):
        logger.warning("NFL conditional model is SUSPENDED — no signals generated")
        print("[nfl_conditional] Model suspended — no signals")
        return

    # Generate signals
    signals = generate_signals(game_date, cfg, stop_state)
    if signals:
        append_signals(signals)
        print(f"[nfl_conditional] {len(signals)} signals for {game_date}")
    else:
        print(f"[nfl_conditional] No conditional signals for {game_date}")


if __name__ == "__main__":
    main()
