#!/usr/bin/env python3
"""
NBA Stop Rules — persistent, sticky, tier-aware suspension logic.

Tier-level:  tier n≥25 total plays AND ROI<−10%  → suspend that tier only
Full model:  all plays n≥50 total AND ROI<−12%   → suspend entire model

ROI formula: (W × (100/110) − L) / (W + L + P) × 100
  — denominator is W+L+P (matches push_nba.py _wlp() formula)

Filter source: nba_results_log WHERE market_snapshot_status='live'
  — if column absent/null on a row, that row is excluded (safe default)

State file: nba/data/nba_stop_rule_state.json
  {
    "model_suspended": false,
    "suspended_tiers": [],
    "tier_details": {...},
    "full_model_details": {...},
    "suspension_log": []
  }

Usage:
    from nba_stop_rules import evaluate_nba_stop_rules, get_nba_stop_rule_status
    from nba_stop_rules import apply_nba_stop_rule_filter
"""

import json
import os
from datetime import datetime, timezone

_REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_REPO_DIR, "nba", "data", "nba_stop_rule_state.json")
_LOG_PATH   = os.path.join(_REPO_DIR, "nba", "data", "nba_results_log.parquet")

_TIERS = ("HIGH", "MEDIUM", "LOW")

# Thresholds
_TIER_MIN_N    = 25    # total (W+L+P) plays per tier
_TIER_ROI_GATE = -10.0
_FULL_MIN_N    = 50    # total (W+L+P) plays
_FULL_ROI_GATE = -12.0


def _empty_state() -> dict:
    return {
        "model_suspended": False,
        "suspended_tiers": [],
        "tier_details": {
            "HIGH":   {"n": None, "roi": None, "triggered_at": None},
            "MEDIUM": {"n": None, "roi": None, "triggered_at": None},
            "LOW":    {"n": None, "roi": None, "triggered_at": None},
        },
        "full_model_details": {"n": None, "roi": None, "triggered_at": None},
        "suspension_log": [],
    }


def _load_state() -> dict:
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH) as f:
                s = json.load(f)
            s.setdefault("model_suspended", s.pop("suspended", False))
            s.setdefault("suspended_tiers", [])
            s.setdefault("tier_details", {})
            s.setdefault("full_model_details", {"n": None, "roi": None, "triggered_at": None})
            for t in _TIERS:
                s["tier_details"].setdefault(t, {"n": None, "roi": None, "triggered_at": None})
            return s
        except Exception:
            pass
    return _empty_state()


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _roi_nba(wins: int, losses: int, pushes: int) -> float | None:
    """NBA ROI: (W × (100/110) − L) / (W + L + P) × 100. Matches push_nba.py _wlp()."""
    n = wins + losses + pushes
    if n == 0:
        return None
    return round((wins * (100.0 / 110.0) - losses) / n * 100, 2)


def _load_live_rows() -> list[dict]:
    """Load nba_results_log, filter to market_snapshot_status='live' + graded plays."""
    if not os.path.exists(_LOG_PATH):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(_LOG_PATH)
    except Exception:
        return []

    if "market_snapshot_status" not in df.columns:
        return []

    df = df[df["market_snapshot_status"] == "live"]
    if "regulation_result" not in df.columns:
        return []
    df = df[df["regulation_result"].isin(["WIN", "LOSS", "PUSH"])]
    return df.to_dict(orient="records")


def _compute_tier_metrics(rows: list[dict]) -> dict:
    out = {}
    for tier in (*_TIERS, "full"):
        subset = rows if tier == "full" else [r for r in rows if r.get("confidence") == tier]
        w = sum(1 for r in subset if r.get("regulation_result") == "WIN")
        l = sum(1 for r in subset if r.get("regulation_result") == "LOSS")
        p = sum(1 for r in subset if r.get("regulation_result") == "PUSH")
        n = w + l + p
        out[tier] = {"wins": w, "losses": l, "pushes": p, "n": n, "roi": _roi_nba(w, l, p)}
    return out


def evaluate_nba_stop_rules() -> dict:
    """
    Evaluate NBA stop rules against nba_results_log.parquet.
    Returns stop_rule_status dict for nba_results.json.
    """
    state = _load_state()
    changed = False

    if state.get("model_suspended"):
        return _status_dict(state)

    live_rows = _load_live_rows()
    if not live_rows:
        return _status_dict(state)

    metrics = _compute_tier_metrics(live_rows)
    now = datetime.now(timezone.utc).isoformat()

    already_suspended = set(state.get("suspended_tiers", []))
    for tier in _TIERS:
        if tier in already_suspended:
            continue
        m = metrics[tier]
        if m["n"] >= _TIER_MIN_N and m["roi"] is not None and m["roi"] < _TIER_ROI_GATE:
            state["suspended_tiers"].append(tier)
            state["tier_details"][tier] = {
                "n": m["n"], "roi": m["roi"], "triggered_at": now
            }
            state["suspension_log"].append({
                "event": "TIER_TRIGGERED", "tier": tier,
                "n": m["n"], "roi": m["roi"], "timestamp": now,
            })
            print(f"[nba_stop_rules] TIER SUSPENDED: {tier} — n={m['n']}, ROI={m['roi']:.1f}%")
            changed = True

    mf = metrics["full"]
    if mf["n"] >= _FULL_MIN_N and mf["roi"] is not None and mf["roi"] < _FULL_ROI_GATE:
        state["model_suspended"] = True
        state["full_model_details"] = {
            "n": mf["n"], "roi": mf["roi"], "triggered_at": now
        }
        state["suspension_log"].append({
            "event": "MODEL_SUSPENDED",
            "n": mf["n"], "roi": mf["roi"], "timestamp": now,
        })
        print(f"[nba_stop_rules] FULL MODEL SUSPENDED — n={mf['n']}, ROI={mf['roi']:.1f}%")
        changed = True

    if changed:
        _save_state(state)

    return _status_dict(state)


def get_nba_stop_rule_status() -> dict:
    """Read state file without evaluating."""
    return _status_dict(_load_state())


def apply_nba_stop_rule_filter(
    plays: list[dict], no_plays: list[dict], status: dict
) -> tuple[list[dict], list[dict]]:
    """
    Filter NBA plays based on stop rule status.
    game["confidence"] is the tier key.
    Suspended plays are moved to no_plays.
    """
    if not status.get("suspended_tiers") and not status.get("model_suspended"):
        return plays, no_plays

    suspended_set = set(status.get("suspended_tiers", []))
    active, moved = [], []

    for g in plays:
        tier = g.get("confidence", "")
        if status.get("model_suspended") or tier in suspended_set:
            moved.append(g)
        else:
            active.append(g)

    return active, no_plays + moved


def _status_dict(state: dict) -> dict:
    return {
        "model_suspended":    state.get("model_suspended", False),
        "suspended_tiers":    state.get("suspended_tiers", []),
        "tier_details":       state.get("tier_details", {}),
        "full_model_details": state.get("full_model_details", {}),
    }
