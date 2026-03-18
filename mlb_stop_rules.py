#!/usr/bin/env python3
"""
MLB Stop Rules — persistent, sticky suspension logic.

Reads from graded_results WHERE decision_line_source = 'real'.
If that column is absent or all rows have NULL, no suspension is triggered (safe default).

State file: data/mlb_stop_rule_state.json
  {
    "suspended": false,
    "trigger": null,       // "tier_HIGH" | "tier_MEDIUM" | "full_model"
    "triggered_at": null,  // ISO datetime string
    "roi": null,
    "n": null,
    "suspension_log": []   // append-only log of all trigger + reset events
  }

Usage:
    from mlb_stop_rules import evaluate_mlb_stop_rules, get_mlb_stop_rule_status
"""

import json
import os
from datetime import datetime, timezone

import db

_REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_REPO_DIR, "data", "mlb_stop_rule_state.json")

# Thresholds
_TIER_MIN_N    = 20
_TIER_ROI_GATE = -10.0   # trigger if ROI < this (e.g. -12.5 < -10)
_FULL_MIN_N    = 40
_FULL_ROI_GATE = -12.0


def _load_state() -> dict:
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "suspended": False,
        "trigger": None,
        "triggered_at": None,
        "roi": None,
        "n": None,
        "suspension_log": [],
    }


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _roi(wins: int, losses: int, n: int) -> float | None:
    """ROI = (W × (100/110) − L) / n × 100.  n = W + L + P."""
    if n == 0:
        return None
    return round((wins * (100.0 / 110.0) - losses) / n * 100, 2)


def _compute_stop_metrics(rows: list[dict]) -> dict:
    """
    Given graded rows (already filtered to decision_line_source='real' + was_a_play=1),
    compute per-tier and full-model W/L/P/ROI.
    """
    results: dict[str, dict] = {}
    for tier in ("HIGH", "MEDIUM", "full"):
        if tier == "full":
            subset = rows
        else:
            subset = [r for r in rows if r.get("confidence") == tier]

        w = sum(1 for r in subset if r.get("result") == "WIN")
        l = sum(1 for r in subset if r.get("result") == "LOSS")
        p = sum(1 for r in subset if r.get("result") == "PUSH")
        n = w + l + p
        results[tier] = {
            "wins":   w,
            "losses": l,
            "pushes": p,
            "n":      n,
            "roi":    _roi(w, l, n),
        }
    return results


def evaluate_mlb_stop_rules() -> dict:
    """
    Evaluate MLB stop rules against graded_results.
    If thresholds are breached and not already suspended, update state file.
    Returns stop_rule_status dict for inclusion in results.json.
    """
    state = _load_state()

    # If already suspended, return current state immediately (sticky)
    if state.get("suspended"):
        return _status_dict(state)

    # Load graded results filtered to live-graded plays only
    try:
        db.init_db()
        all_rows = db.get_all_graded_results()
    except Exception:
        all_rows = []

    # Filter: must have decision_line_source = 'real'
    live_rows = [
        r for r in all_rows
        if r.get("was_a_play") == 1
        and r.get("result") in ("WIN", "LOSS", "PUSH")
        and r.get("decision_line_source") == "real"
    ]

    # If no live rows yet, nothing to evaluate
    if not live_rows:
        return _status_dict(state)

    metrics = _compute_stop_metrics(live_rows)

    # Check tier thresholds
    for tier in ("HIGH", "MEDIUM"):
        m = metrics[tier]
        if m["n"] >= _TIER_MIN_N and m["roi"] is not None and m["roi"] < _TIER_ROI_GATE:
            _trigger(state, f"tier_{tier}", m["roi"], m["n"])
            _save_state(state)
            return _status_dict(state)

    # Check full model threshold
    m_full = metrics["full"]
    if m_full["n"] >= _FULL_MIN_N and m_full["roi"] is not None and m_full["roi"] < _FULL_ROI_GATE:
        _trigger(state, "full_model", m_full["roi"], m_full["n"])
        _save_state(state)
        return _status_dict(state)

    return _status_dict(state)


def get_mlb_stop_rule_status() -> dict:
    """Read state file without evaluating. Use for dashboard reads."""
    return _status_dict(_load_state())


def _trigger(state: dict, trigger: str, roi: float, n: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    state["suspended"]    = True
    state["trigger"]      = trigger
    state["triggered_at"] = now
    state["roi"]          = roi
    state["n"]            = n
    state["suspension_log"].append({
        "event":        "TRIGGERED",
        "trigger":      trigger,
        "roi":          roi,
        "n":            n,
        "timestamp":    now,
    })
    print(f"[mlb_stop_rules] SUSPENDED — trigger={trigger}, n={n}, ROI={roi:.1f}%")


def _status_dict(state: dict) -> dict:
    return {
        "suspended":    state.get("suspended", False),
        "trigger":      state.get("trigger"),
        "triggered_at": state.get("triggered_at"),
        "roi":          state.get("roi"),
        "n":            state.get("n"),
    }
