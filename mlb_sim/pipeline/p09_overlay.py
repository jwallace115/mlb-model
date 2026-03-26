#!/usr/bin/env python3
"""
P09 Overlay — Contact suppression × pitcher park under amplifier.
Fires when avg hard-hit rate × park_run_factor is in the bottom 20%.

Does NOT generate standalone bets. Only amplifies existing V1 UNDER.
"""

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger("p09_overlay")

CONFIG_PATH = Path(__file__).resolve().parent / "p09_overlay_config.json"

_DEFAULT_CONFIG = {
    "p09_cutoff_bottom20": 31.7305,
    "overlay_status": "ACTIVE",
    "overlay_version": "1.0",
    "stake_rules": {"p09_only": 1.25, "s12_only": 1.25, "both": 1.5, "cap": 1.5},
}


def _load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return _DEFAULT_CONFIG


def compute_p09(home_hard_hit_rate, away_hard_hit_rate, park_run_factor):
    """
    Compute P09 = avg(home_hh, away_hh) * park_run_factor.
    Returns float or None if inputs missing.
    """
    if home_hard_hit_rate is None or away_hard_hit_rate is None or park_run_factor is None:
        return None
    return ((home_hard_hit_rate + away_hard_hit_rate) / 2) * park_run_factor


def evaluate_p09_overlay(p09_value):
    """
    Evaluate whether P09 overlay is active.
    Returns dict with p09_value, p09_cutoff, p09_overlay_active, p09_data_available.
    """
    cfg = _load_config()
    cutoff = cfg["p09_cutoff_bottom20"]
    status = cfg["overlay_status"]

    result = {
        "p09_value": round(p09_value, 3) if p09_value is not None else None,
        "p09_cutoff": cutoff,
        "p09_overlay_active": 0,
        "p09_data_available": 1 if p09_value is not None else 0,
    }

    if p09_value is None or status != "ACTIVE":
        result["p09_data_available"] = 0 if p09_value is None else 1
        return result

    if p09_value <= cutoff:
        result["p09_overlay_active"] = 1
        logger.info(f"  P09 overlay ACTIVE: p09={p09_value:.2f} <= {cutoff:.2f}")

    return result


def apply_combined_overlay(base_stake, s12_active, p09_active):
    """
    Apply combined S12 + P09 overlay stake rules.
    Returns (final_stake, combined_overlay_tier).

    Tiers:
      NONE: no overlay
      S12_ONLY: S12 active, P09 not
      P09_ONLY: P09 active, S12 not
      BOTH: both active
    """
    cfg = _load_config()
    rules = cfg.get("stake_rules", _DEFAULT_CONFIG["stake_rules"])
    cap = rules.get("cap", 1.5)

    if s12_active and p09_active:
        multiplier = rules.get("both", 1.5)
        tier = "BOTH"
    elif p09_active:
        multiplier = rules.get("p09_only", 1.25)
        tier = "P09_ONLY"
    elif s12_active:
        multiplier = rules.get("s12_only", 1.25)
        tier = "S12_ONLY"
    else:
        return base_stake, "NONE"

    multiplier = min(multiplier, cap)
    raw = base_stake * multiplier
    # Round to nearest 0.125u
    final = round(raw * 8) / 8
    return final, tier
