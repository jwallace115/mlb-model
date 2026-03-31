#!/usr/bin/env python3
"""
NBA Segment Overlay — Phase 3 implementation.

Applies validated segment-based confidence boost to OVER signals.
Segments from Phase 2 discovery (2022-23 + 2023-24), validated on 2024-25.

Overlay rules:
  If model signals OVER AND qualifying segment matches:
    boost confidence by +1 tier (LOW→MEDIUM, MEDIUM→HIGH)

Segments:
  A: both_fast_pace (edge >= 1.0)
  B: home_b2b_elite_offense (edge >= 1.5)

Priority: A before B. Single boost only. No stacking.
No UNDER suppression. No direction changes.
"""

import json
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

NBA_DIR = Path(__file__).resolve().parent
CONFIG_PATH = NBA_DIR / "config_segment_overlay.json"
STOP_RULES_PATH = NBA_DIR / "data" / "nba_overlay_stop_rules.json"

# Pace/ORtg thresholds from 2022-23 + 2023-24 discovery data (frozen)
_THRESHOLDS = None


def _load_thresholds() -> dict:
    global _THRESHOLDS
    if _THRESHOLDS is not None:
        return _THRESHOLDS

    ft_path = NBA_DIR / "data" / "features.parquet"
    if not ft_path.exists():
        _THRESHOLDS = {"pace_median": 100.0, "ortg_q67": 112.0}
        return _THRESHOLDS

    ft = pd.read_parquet(ft_path)
    disc = ft[ft["season"].isin(["2022-23", "2023-24"])]
    _THRESHOLDS = {
        "pace_median": float(disc["home_pace"].median()),
        "ortg_q67": float(disc["home_ortg"].quantile(0.67)),
    }
    return _THRESHOLDS


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    if not cfg.get("overlay_active"):
        return {}
    return cfg


def classify_segments(game: dict) -> dict:
    """Evaluate segment flags for a single NBA game.

    Args:
        game: dict with keys: home_pace, away_pace, b2b_flag_home,
              home_ortg, away_ortg, edge (model edge in points)

    Returns:
        dict with segment flags and overlay metadata.
    """
    thr = _load_thresholds()

    home_pace = game.get("home_pace") or 0
    away_pace = game.get("away_pace") or 0
    b2b_home = bool(game.get("b2b_flag_home") or game.get("b2b_home") or 0)
    home_ortg = game.get("home_ortg") or 0
    away_ortg = game.get("away_ortg") or 0
    edge = abs(game.get("edge") or 0)

    # Segment A: both_fast_pace (edge >= 1.0)
    seg_a = (home_pace > thr["pace_median"] and away_pace > thr["pace_median"]
             and edge >= 1.0)

    # Segment B: home_b2b + one_elite_offense (edge >= 1.5)
    # DISABLED after shadow testing (40% hit, -23.6% ROI)
    cfg = load_config()
    seg_b_cfg = cfg.get("segments", {}).get("home_b2b_elite_offense", {})
    seg_b_disabled = seg_b_cfg.get("disabled", False)
    one_elite = home_ortg > thr["ortg_q67"] or away_ortg > thr["ortg_q67"]
    seg_b = (not seg_b_disabled and b2b_home and one_elite and edge >= 1.5)

    # Priority resolution: A before B, single boost
    if seg_a:
        selected = "both_fast_pace"
    elif seg_b:
        selected = "home_b2b_elite_offense"
    else:
        selected = None

    return {
        "both_fast_pace": seg_a,
        "home_b2b_elite_offense": seg_b,
        "overlay_segment": selected,
        "overlay_flag": selected is not None,
    }


def apply_overlay(confidence: str, lean: str, segment_result: dict,
                  tier_names: tuple = ("LOW", "MEDIUM", "HIGH")) -> tuple[str, bool]:
    """Apply overlay boost. Returns (final_confidence, overlay_applied).

    Only boosts OVER signals. Single tier boost.
    """
    LOW, MEDIUM, HIGH = tier_names

    if not segment_result.get("overlay_flag"):
        return confidence, False

    # Only OVER
    if lean.upper() != "OVER":
        return confidence, False

    # Check stop rules
    stop = load_stop_rules()
    if stop.get("overlay_suspended"):
        return confidence, False
    seg = segment_result.get("overlay_segment", "")
    if seg in stop.get("suspended_segments", []):
        return confidence, False

    # Boost by +1 tier
    if confidence == LOW:
        return MEDIUM, True
    elif confidence == MEDIUM:
        return HIGH, True
    # Already HIGH — no boost
    return confidence, False


def load_stop_rules() -> dict:
    if STOP_RULES_PATH.exists():
        with open(STOP_RULES_PATH) as f:
            return json.load(f)
    return {"overlay_suspended": False, "suspended_segments": [], "segment_stats": {}}


def save_stop_rules(state: dict):
    STOP_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STOP_RULES_PATH, "w") as f:
        json.dump(state, f, indent=2)
