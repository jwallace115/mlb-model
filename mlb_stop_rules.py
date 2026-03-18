#!/usr/bin/env python3
"""
MLB Stop Rules — persistent, sticky, tier-aware suspension logic.

Tier-level:  tier n≥20 decided plays AND ROI<−10%  → suspend that tier only
Full model:  all plays n≥40 decided AND ROI<−12%   → suspend entire model

ROI formula: (W × (100/110) − L) / (W + L) × 100
  — denominator is W+L (decided only, matching MLB season_performance ROI in results_tracker.py)
  — pushes excluded from both numerator and denominator

Filter source: graded_results WHERE decision_line_source='real'
  — if column absent/null on a row, that row is excluded (safe default)

State file: data/mlb_stop_rule_state.json
  {
    "model_suspended": false,        // full-model gate
    "suspended_tiers": [],           // e.g. ["HIGH"] — tier-level gate
    "tier_details": {
      "HIGH":   {"n": null, "roi": null, "triggered_at": null},
      "MEDIUM": {"n": null, "roi": null, "triggered_at": null},
      "LOW":    {"n": null, "roi": null, "triggered_at": null}
    },
    "full_model_details": {"n": null, "roi": null, "triggered_at": null},
    "suspension_log": []
  }

Usage:
    from mlb_stop_rules import evaluate_mlb_stop_rules, get_mlb_stop_rule_status
    from mlb_stop_rules import apply_mlb_stop_rule_filter
"""

import json
import os
from datetime import datetime, timezone

import db

_REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_REPO_DIR, "data", "mlb_stop_rule_state.json")

_TIERS = ("HIGH", "MEDIUM", "LOW")

# Thresholds
_TIER_MIN_N    = 20    # decided (W+L) plays per tier
_TIER_ROI_GATE = -10.0
_FULL_MIN_N    = 40    # decided (W+L) plays total
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
            # Back-compat: ensure keys exist from older schema
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


def _roi_mlb(wins: int, losses: int) -> float | None:
    """MLB ROI: (W × (100/110) − L) / (W + L) × 100. Pushes excluded from denominator."""
    decided = wins + losses
    if decided == 0:
        return None
    return round((wins * (100.0 / 110.0) - losses) / decided * 100, 2)


def _compute_tier_metrics(rows: list[dict]) -> dict:
    """
    Returns {tier: {wins, losses, n_decided, roi}} plus "full" key.
    n_decided = W + L (pushes not counted, matching MLB season perf formula).
    """
    out = {}
    for tier in (*_TIERS, "full"):
        subset = rows if tier == "full" else [r for r in rows if r.get("confidence") == tier]
        w = sum(1 for r in subset if r.get("result") == "WIN")
        l = sum(1 for r in subset if r.get("result") == "LOSS")
        n = w + l  # decided only
        out[tier] = {"wins": w, "losses": l, "n_decided": n, "roi": _roi_mlb(w, l)}
    return out


def evaluate_mlb_stop_rules() -> dict:
    """
    Evaluate MLB stop rules against graded_results.
    Updates state file if new thresholds are breached.
    Returns stop_rule_status dict for results.json.
    """
    state = _load_state()
    changed = False

    # If full model already suspended, no further evaluation needed (sticky)
    if state.get("model_suspended"):
        return _status_dict(state)

    # Load live-graded plays
    try:
        db.init_db()
        all_rows = db.get_all_graded_results()
    except Exception:
        all_rows = []

    live_rows = [
        r for r in all_rows
        if r.get("was_a_play") == 1
        and r.get("result") in ("WIN", "LOSS", "PUSH")
        and r.get("decision_line_source") == "real"
    ]

    if not live_rows:
        return _status_dict(state)

    metrics = _compute_tier_metrics(live_rows)
    now = datetime.now(timezone.utc).isoformat()

    # Tier-level check (skip already-suspended tiers)
    already_suspended = set(state.get("suspended_tiers", []))
    for tier in _TIERS:
        if tier in already_suspended:
            continue
        m = metrics[tier]
        if m["n_decided"] >= _TIER_MIN_N and m["roi"] is not None and m["roi"] < _TIER_ROI_GATE:
            state["suspended_tiers"].append(tier)
            state["tier_details"][tier] = {
                "n": m["n_decided"], "roi": m["roi"], "triggered_at": now
            }
            state["suspension_log"].append({
                "event": "TIER_TRIGGERED", "tier": tier,
                "n": m["n_decided"], "roi": m["roi"], "timestamp": now,
            })
            print(f"[mlb_stop_rules] TIER SUSPENDED: {tier} — n={m['n_decided']}, ROI={m['roi']:.1f}%")
            changed = True

    # Full model check
    mf = metrics["full"]
    if mf["n_decided"] >= _FULL_MIN_N and mf["roi"] is not None and mf["roi"] < _FULL_ROI_GATE:
        state["model_suspended"] = True
        state["full_model_details"] = {
            "n": mf["n_decided"], "roi": mf["roi"], "triggered_at": now
        }
        state["suspension_log"].append({
            "event": "MODEL_SUSPENDED",
            "n": mf["n_decided"], "roi": mf["roi"], "timestamp": now,
        })
        print(f"[mlb_stop_rules] FULL MODEL SUSPENDED — n={mf['n_decided']}, ROI={mf['roi']:.1f}%")
        changed = True

    if changed:
        _save_state(state)

    return _status_dict(state)


def get_mlb_stop_rule_status() -> dict:
    """Read state file without evaluating. For dashboard use."""
    return _status_dict(_load_state())


def apply_mlb_stop_rule_filter(
    plays: list[dict], no_plays: list[dict], status: dict
) -> tuple[list[dict], list[dict]]:
    """
    Filter plays based on stop rule status.
    Suspended plays are moved to no_plays (preserved, not recommended).

    play["proj"]["confidence"] is the tier key.

    Returns: (active_plays, updated_no_plays)
    """
    if not status.get("suspended_tiers") and not status.get("model_suspended"):
        return plays, no_plays

    suspended_set = set(status.get("suspended_tiers", []))
    active, moved = [], []

    for p in plays:
        tier = (p.get("proj") or {}).get("confidence", "")
        if status.get("model_suspended") or tier in suspended_set:
            moved.append(p)
        else:
            active.append(p)

    return active, no_plays + moved


def _status_dict(state: dict) -> dict:
    return {
        "model_suspended":    state.get("model_suspended", False),
        "suspended_tiers":    state.get("suspended_tiers", []),
        "tier_details":       state.get("tier_details", {}),
        "full_model_details": state.get("full_model_details", {}),
    }
