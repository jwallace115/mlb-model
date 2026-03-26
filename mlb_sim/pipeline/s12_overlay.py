#!/usr/bin/env python3
"""
S12 Overlay — Under Amplifier for V1 Full-Game Totals.

S12 = (home_csw + away_csw)/2 - 5*(home_xfip + away_xfip)/2

When S12 >= frozen top-20% cutoff AND V1 fires an UNDER signal,
stake is amplified by 1.25x.

Does NOT create new bets, lower thresholds, or apply to OVER.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("s12_overlay")

BASE = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE / "pipeline" / "s12_overlay_config.json"

# Frozen cutoff from 2024 research
_DEFAULT_CONFIG = {
    "s12_cutoff_top20": 8.4468,
    "overlay_status": "ACTIVE",
    "overlay_version": "1.0",
    "stake_amplifier": 1.25,
    "deployment_note": "S12 under amplifier — 2024-derived cutoff, conservative 1.25x stake boost",
}


def _load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return _DEFAULT_CONFIG


def compute_s12(home_sp, away_sp):
    """
    Compute S12 combined pitcher score.

    Args:
        home_sp: dict with 'csw_pct' and 'xfip' keys
        away_sp: dict with 'csw_pct' and 'xfip' keys

    Returns:
        float S12 value, or None if inputs missing
    """
    h_csw = home_sp.get("csw_pct") if home_sp else None
    a_csw = away_sp.get("csw_pct") if away_sp else None
    h_xfip = home_sp.get("xfip") if home_sp else None
    a_xfip = away_sp.get("xfip") if away_sp else None

    if h_xfip is None or a_xfip is None:
        return None

    # Use 27.0 (league median) as CSW fallback
    h_csw = h_csw if h_csw is not None else 27.0
    a_csw = a_csw if a_csw is not None else 27.0

    return (h_csw + a_csw) / 2 - 5 * ((h_xfip + a_xfip) / 2)


def evaluate_overlay(s12_value, base_stake):
    """
    Evaluate S12 overlay for a V1 UNDER signal.

    Args:
        s12_value: float S12 score (or None)
        base_stake: float original V1 stake

    Returns:
        dict with overlay fields:
            s12_value, s12_cutoff, s12_overlay_active,
            base_stake, final_stake, overlay_delta_units,
            overlay_version
    """
    cfg = _load_config()
    cutoff = cfg["s12_cutoff_top20"]
    status = cfg["overlay_status"]
    amplifier = cfg["stake_amplifier"]
    version = cfg["overlay_version"]

    result = {
        "s12_value": round(s12_value, 3) if s12_value is not None else None,
        "s12_cutoff": cutoff,
        "s12_overlay_active": 0,
        "base_stake": base_stake,
        "final_stake": base_stake,
        "overlay_delta_units": 0.0,
        "overlay_version": version,
    }

    if s12_value is None:
        return result

    if status != "ACTIVE":
        return result

    if s12_value >= cutoff:
        final = round(base_stake * amplifier, 2)
        result["s12_overlay_active"] = 1
        result["final_stake"] = final
        result["overlay_delta_units"] = round(final - base_stake, 2)
        logger.info(f"  S12 overlay ACTIVE: s12={s12_value:.2f} >= {cutoff:.2f}, "
                    f"stake {base_stake}u → {final}u")

    return result


def apply_overlay_to_signal(sig, home_sp, away_sp):
    """
    Apply S12 overlay to a V1 signal dict in place.
    Only applies to UNDER signals.

    Args:
        sig: dict — the V1 signal (modified in place)
        home_sp: dict with pitcher metrics
        away_sp: dict with pitcher metrics

    Returns:
        sig (same dict, with overlay fields added)
    """
    # Only apply to UNDER
    if sig.get("signal_side") != "UNDER":
        sig.update({
            "s12_value": None, "s12_cutoff": None, "s12_overlay_active": 0,
            "base_stake": sig.get("stake_units"), "final_stake": sig.get("stake_units"),
            "overlay_delta_units": 0.0, "overlay_version": _load_config()["overlay_version"],
        })
        return sig

    s12 = compute_s12(home_sp, away_sp)
    overlay = evaluate_overlay(s12, sig["stake_units"])

    sig["stake_units"] = overlay["final_stake"]  # update actual stake
    sig.update(overlay)

    return sig
