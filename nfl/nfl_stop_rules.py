#!/usr/bin/env python3
"""
NFL stop rules — same pattern as MLB, NBA, Soccer.

State file: nfl/data/nfl_stop_rule_state.json

Tier suspension: live signals in tier >= 15 AND ROI < -10%
Full model suspension: total live signals >= 30 AND overall ROI < -12%

Live only: market_snapshot_status = "live"
Sticky — manual reset only.
"""

import json
import os
import sys

import pandas as pd

NFL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(NFL_DIR, "data")
DECISIONS_PATH = os.path.join(DATA_DIR, "nfl_decisions.parquet")
STATE_PATH = os.path.join(DATA_DIR, "nfl_stop_rule_state.json")

TIER_MIN_N = 15
TIER_ROI_THRESHOLD = -0.10
OVERALL_MIN_N = 30
OVERALL_ROI_THRESHOLD = -0.12

WIN_PER_UNIT = 100.0 / 110.0


def _roi(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    return (wins * WIN_PER_UNIT - losses) / n


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {
        "model_suspended": False,
        "suspended_tiers": [],
        "overall_n": 0,
        "overall_roi": None,
        "tier_stats": {},
    }


def save_state(state: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def evaluate() -> dict:
    state = load_state()

    if not os.path.exists(DECISIONS_PATH):
        return state

    try:
        dec = pd.read_parquet(DECISIONS_PATH)
    except Exception:
        return state

    live = dec[dec.get("market_snapshot_status", pd.Series()) == "live"]
    graded = live[live["result"].isin(["WIN", "LOSS", "PUSH"])] if "result" in live.columns else pd.DataFrame()

    if graded.empty:
        return state

    # Overall
    w = int((graded["result"] == "WIN").sum())
    l = int((graded["result"] == "LOSS").sum())
    roi = _roi(w, l)
    n = w + l

    state["overall_n"] = n
    state["overall_roi"] = roi

    if n >= OVERALL_MIN_N and roi is not None and roi < OVERALL_ROI_THRESHOLD:
        state["model_suspended"] = True

    # Per tier
    suspended = list(state.get("suspended_tiers", []))
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        sub = graded[graded["confidence_tier"] == tier]
        tw = int((sub["result"] == "WIN").sum())
        tl = int((sub["result"] == "LOSS").sum())
        tn = tw + tl
        troi = _roi(tw, tl)
        state["tier_stats"][tier] = {"n": tn, "roi": troi}

        if tn >= TIER_MIN_N and troi is not None and troi < TIER_ROI_THRESHOLD:
            if tier not in suspended:
                suspended.append(tier)

    state["suspended_tiers"] = suspended
    save_state(state)
    return state


def reset(tier: str | None = None):
    state = load_state()
    if tier is None or tier == "--all":
        state["model_suspended"] = False
        state["suspended_tiers"] = []
    else:
        tier = tier.upper()
        state["suspended_tiers"] = [t for t in state.get("suspended_tiers", []) if t != tier]
    save_state(state)
    print(f"Reset: {state}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        tier_arg = sys.argv[2] if len(sys.argv) > 2 else "--all"
        reset(tier_arg)
    else:
        state = evaluate()
        print(json.dumps(state, indent=2))
