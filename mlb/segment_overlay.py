#!/usr/bin/env python3
"""
MLB Segment Overlay — Phase 4 live integration.

Applies frozen segment-based confidence boost to OVER signals.
Reads config from mlb/config_segment_overlay.json.

Overlay rule:
  If model signals OVER AND (Segment A OR Segment B):
    promote WATCHLIST → BET tier

Segments:
  A: calm wind + pitcher umpire
  B: low total (<8.0) + warm/hot temperature

No UNDER suppression. No threshold changes.
"""

import json
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

MLB_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MLB_DIR / "config_segment_overlay.json"
STOP_RULES_PATH = MLB_DIR / "data" / "mlb_overlay_stop_rules.json"

# Umpire classification from 2022-2023 discovery data
# Pre-computed thresholds (frozen)
_UMPIRE_CACHE = {}
_UMPIRE_THRESHOLDS = None


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.warning(f"Overlay config not found: {CONFIG_PATH}")
        return {}
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    if not cfg.get("overlay_active"):
        return {}
    if not cfg.get("frozen"):
        logger.error("Overlay config is not frozen — refusing to run")
        return {}
    return cfg


def load_umpire_classification() -> dict:
    """Load umpire bucket classification from game_table 2022-2023 data."""
    global _UMPIRE_CACHE, _UMPIRE_THRESHOLDS

    if _UMPIRE_CACHE:
        return _UMPIRE_CACHE

    gt_path = Path(__file__).resolve().parent.parent / "sim" / "data" / "game_table.parquet"
    if not gt_path.exists():
        return {}

    gt = pd.read_parquet(gt_path)
    disc = gt[gt["season"].isin([2022, 2023])]

    league_avg = disc["umpire_over_rate"].mean()
    league_std = disc["umpire_over_rate"].std()
    ump_hi = league_avg + 0.5 * league_std
    ump_lo = league_avg - 0.5 * league_std
    _UMPIRE_THRESHOLDS = {"avg": league_avg, "std": league_std, "hi": ump_hi, "lo": ump_lo}

    umps = disc.groupby("umpire_name").agg(
        n=("game_pk", "count"),
        rate=("umpire_over_rate", "mean"),
    ).reset_index()

    for _, u in umps.iterrows():
        if u["n"] < 30:
            _UMPIRE_CACHE[u["umpire_name"]] = "neutral_ump"
        elif u["rate"] > ump_hi:
            _UMPIRE_CACHE[u["umpire_name"]] = "hitter_ump"
        elif u["rate"] < ump_lo:
            _UMPIRE_CACHE[u["umpire_name"]] = "pitcher_ump"
        else:
            _UMPIRE_CACHE[u["umpire_name"]] = "neutral_ump"

    return _UMPIRE_CACHE


def classify_game(game: dict) -> dict:
    """Evaluate segment flags for a single game.

    Returns dict with segment_A, segment_B, overlay_flag, overlay_reason.
    """
    ump_map = load_umpire_classification()

    # Wind bucket
    ws = game.get("wind_speed", 0) or 0
    wind_bucket = "calm" if ws < 5 else ("moderate" if ws < 15 else "strong")

    # Umpire bucket
    ump_name = game.get("umpire_name", "")
    umpire_bucket = ump_map.get(ump_name, "neutral_ump")

    # Temperature bucket
    temp = game.get("temperature", 72) or 72
    if temp < 50:
        temp_bucket = "cold"
    elif temp < 65:
        temp_bucket = "cool"
    elif temp < 80:
        temp_bucket = "warm"
    else:
        temp_bucket = "hot"

    # Close total
    close_total = game.get("close_total") or game.get("decision_line") or game.get("line")

    # Segment A: calm wind + pitcher ump
    seg_a = (wind_bucket == "calm") and (umpire_bucket == "pitcher_ump")

    # Segment B: low total + warm/hot
    seg_b = (close_total is not None and close_total < 8.0) and (temp_bucket in ("warm", "hot"))

    overlay_flag = seg_a or seg_b
    reasons = []
    if seg_a:
        reasons.append("segment_A")
    if seg_b:
        reasons.append("segment_B")

    return {
        "segment_A_flag": seg_a,
        "segment_B_flag": seg_b,
        "overlay_flag": overlay_flag,
        "overlay_reason": "+".join(reasons) if reasons else "none",
        "wind_bucket": wind_bucket,
        "umpire_bucket": umpire_bucket,
        "temp_bucket": temp_bucket,
    }


def apply_overlay(tier: str, bet_side: str, overlay_flag: bool, cfg: dict | None = None) -> tuple[str, bool]:
    """Apply overlay promotion. Returns (final_tier, overlay_applied).

    Only promotes WATCHLIST OVER → BET OVER.
    """
    if cfg is None:
        cfg = load_config()

    if not cfg.get("overlay_active"):
        return tier, False

    # Only apply to OVER signals
    if "over" not in tier.lower() and bet_side.lower() != "over":
        return tier, False

    # Only promote WATCHLIST
    if "WATCHLIST" not in tier.upper():
        return tier, False

    if not overlay_flag:
        return tier, False

    # Check stop rules
    stop = load_stop_rules()
    if stop.get("overlay_suspended"):
        return tier, False

    # Promote
    new_tier = tier.replace("WATCHLIST", "BET")
    return new_tier, True


def load_stop_rules() -> dict:
    if STOP_RULES_PATH.exists():
        with open(STOP_RULES_PATH) as f:
            return json.load(f)
    return {
        "overlay_suspended": False,
        "suspended_segments": [],
        "segment_stats": {},
    }


def save_stop_rules(state: dict):
    STOP_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STOP_RULES_PATH, "w") as f:
        json.dump(state, f, indent=2)


def evaluate_stop_rules(results_df: pd.DataFrame | None = None) -> dict:
    """Evaluate overlay stop rules on live data."""
    state = load_stop_rules()

    if results_df is None or results_df.empty:
        return state

    live = results_df[results_df.get("overlay_applied", pd.Series(dtype=bool)) == True]
    if live.empty:
        return state

    WIN = 100.0 / 110.0
    cfg = load_config()

    suspended = list(state.get("suspended_segments", []))

    for seg_key, seg_cfg in cfg.get("segments", {}).items():
        seg_name = seg_cfg["name"]
        col = f"overlay_{seg_name}" if f"overlay_{seg_name}" in live.columns else None

        if col is None:
            # Try segment_A_flag / segment_B_flag
            flag_col = "segment_A_flag" if "A" in seg_key else "segment_B_flag"
            if flag_col not in live.columns:
                continue
            sub = live[live[flag_col] == True]
        else:
            sub = live[live[col] == True]

        graded = sub[sub["result"].isin(["WIN", "LOSS"])]
        n = len(graded)
        if n == 0:
            continue

        w = int((graded["result"] == "WIN").sum())
        l = n - w
        roi = (w * WIN - l) / n

        state["segment_stats"][seg_name] = {"n": n, "w": w, "l": l, "roi": round(roi, 4)}

        min_n = seg_cfg.get("stop_min_n", 30)
        threshold = seg_cfg.get("stop_roi_threshold", -0.10)

        if n >= min_n and roi < threshold and seg_name not in suspended:
            suspended.append(seg_name)
            logger.warning(f"Overlay segment {seg_name} SUSPENDED: n={n}, ROI={roi:.1%}")

    # Global
    all_graded = live[live["result"].isin(["WIN", "LOSS"])]
    total_n = len(all_graded)
    if total_n >= 75:
        total_w = int((all_graded["result"] == "WIN").sum())
        total_roi = (total_w * WIN - (total_n - total_w)) / total_n
        if total_roi < -0.12:
            state["overlay_suspended"] = True
            logger.warning(f"Overlay globally SUSPENDED: n={total_n}, ROI={total_roi:.1%}")

    state["suspended_segments"] = suspended
    save_stop_rules(state)
    return state


def reset_stop_rules(segment: str | None = None):
    state = load_stop_rules()
    if segment is None:
        state["overlay_suspended"] = False
        state["suspended_segments"] = []
    else:
        state["suspended_segments"] = [s for s in state.get("suspended_segments", []) if s != segment]
    save_stop_rules(state)
