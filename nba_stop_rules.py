#!/usr/bin/env python3
"""
NBA Stop Rules — persistent, sticky suspension logic.

Reads from nba/data/nba_results_log.parquet WHERE market_snapshot_status = 'live'.
If that column is absent or all rows have NULL, no suspension is triggered (safe default).

State file: nba/data/nba_stop_rule_state.json
  {
    "suspended": false,
    "trigger": null,       // "tier_HIGH" | "tier_MEDIUM" | "full_model"
    "triggered_at": null,  // ISO datetime string
    "roi": null,
    "n": null,
    "suspension_log": []
  }

Usage:
    from nba_stop_rules import evaluate_nba_stop_rules, get_nba_stop_rule_status
"""

import json
import os
from datetime import datetime, timezone

_REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_REPO_DIR, "nba", "data", "nba_stop_rule_state.json")
_LOG_PATH   = os.path.join(_REPO_DIR, "nba", "data", "nba_results_log.parquet")

# Thresholds
_TIER_MIN_N    = 25
_TIER_ROI_GATE = -10.0
_FULL_MIN_N    = 50
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


def _load_live_rows() -> list[dict]:
    """
    Load nba_results_log.parquet, filter to market_snapshot_status='live'
    and regulation_result in (WIN, LOSS, PUSH).
    Returns list of dicts. Returns [] if file missing or column absent.
    """
    if not os.path.exists(_LOG_PATH):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(_LOG_PATH)
    except Exception:
        return []

    # If column absent, exclude all rows (safe default)
    if "market_snapshot_status" not in df.columns:
        return []

    df = df[df["market_snapshot_status"] == "live"]

    # Keep graded plays only
    if "regulation_result" in df.columns:
        df = df[df["regulation_result"].isin(["WIN", "LOSS", "PUSH"])]
    else:
        return []

    return df.to_dict(orient="records")


def _compute_stop_metrics(rows: list[dict]) -> dict:
    """Compute per-tier and full-model W/L/P/ROI."""
    results: dict[str, dict] = {}
    for tier in ("HIGH", "MEDIUM", "full"):
        if tier == "full":
            subset = rows
        else:
            subset = [r for r in rows if r.get("confidence") == tier]

        w = sum(1 for r in subset if r.get("regulation_result") == "WIN")
        l = sum(1 for r in subset if r.get("regulation_result") == "LOSS")
        p = sum(1 for r in subset if r.get("regulation_result") == "PUSH")
        n = w + l + p
        results[tier] = {
            "wins":   w,
            "losses": l,
            "pushes": p,
            "n":      n,
            "roi":    _roi(w, l, n),
        }
    return results


def evaluate_nba_stop_rules() -> dict:
    """
    Evaluate NBA stop rules against nba_results_log.parquet.
    If thresholds are breached and not already suspended, update state file.
    Returns stop_rule_status dict for inclusion in nba_results.json.
    """
    state = _load_state()

    # Sticky — already suspended
    if state.get("suspended"):
        return _status_dict(state)

    live_rows = _load_live_rows()
    if not live_rows:
        return _status_dict(state)

    metrics = _compute_stop_metrics(live_rows)

    # Tier thresholds
    for tier in ("HIGH", "MEDIUM"):
        m = metrics[tier]
        if m["n"] >= _TIER_MIN_N and m["roi"] is not None and m["roi"] < _TIER_ROI_GATE:
            _trigger(state, f"tier_{tier}", m["roi"], m["n"])
            _save_state(state)
            return _status_dict(state)

    # Full model threshold
    m_full = metrics["full"]
    if m_full["n"] >= _FULL_MIN_N and m_full["roi"] is not None and m_full["roi"] < _FULL_ROI_GATE:
        _trigger(state, "full_model", m_full["roi"], m_full["n"])
        _save_state(state)
        return _status_dict(state)

    return _status_dict(state)


def get_nba_stop_rule_status() -> dict:
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
        "event":     "TRIGGERED",
        "trigger":   trigger,
        "roi":       roi,
        "n":         n,
        "timestamp": now,
    })
    print(f"[nba_stop_rules] SUSPENDED — trigger={trigger}, n={n}, ROI={roi:.1f}%")


def _status_dict(state: dict) -> dict:
    return {
        "suspended":    state.get("suspended", False),
        "trigger":      state.get("trigger"),
        "triggered_at": state.get("triggered_at"),
        "roi":          state.get("roi"),
        "n":            state.get("n"),
    }
