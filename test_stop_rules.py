#!/usr/bin/env python3
"""
Mock tests for MLB and NBA stop rules.
Injects synthetic state, verifies behavior, then restores original state.

Usage:
    python test_stop_rules.py
"""

import json
import os
import sys
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.abspath(__file__))
_MLB_STATE = os.path.join(_REPO, "data", "mlb_stop_rule_state.json")
_NBA_STATE = os.path.join(_REPO, "nba", "data", "nba_stop_rule_state.json")

_PASS = 0
_FAIL = 0


def _check(label: str, condition: bool) -> None:
    global _PASS, _FAIL
    if condition:
        print(f"  [PASS] {label}")
        _PASS += 1
    else:
        print(f"  [FAIL] {label}", file=sys.stderr)
        _FAIL += 1


def _load(path: str) -> dict | None:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _write(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _clear(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def _suspended_state(trigger: str = "full_model", roi: float = -14.0, n: int = 45) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "suspended": True,
        "trigger": trigger,
        "triggered_at": now,
        "roi": roi,
        "n": n,
        "suspension_log": [{"event": "TRIGGERED", "trigger": trigger,
                            "roi": roi, "n": n, "timestamp": now}],
    }


def _clean_state() -> dict:
    return {
        "suspended": False,
        "trigger": None,
        "triggered_at": None,
        "roi": None,
        "n": None,
        "suspension_log": [],
    }


# ── save originals ─────────────────────────────────────────────────────────────
_orig_mlb = _load(_MLB_STATE)
_orig_nba = _load(_NBA_STATE)


def _restore() -> None:
    if _orig_mlb is not None:
        _write(_MLB_STATE, _orig_mlb)
    else:
        _clear(_MLB_STATE)

    if _orig_nba is not None:
        _write(_NBA_STATE, _orig_nba)
    else:
        _clear(_NBA_STATE)
    print("\n[test_stop_rules] State restored.")


# ── MLB tests ─────────────────────────────────────────────────────────────────

print("\n── MLB Stop Rule Tests ──────────────────────────────────────")

# Test 1: no state file → evaluate returns not suspended
print("\nTest 1: no state file → not suspended")
_clear(_MLB_STATE)
from mlb_stop_rules import evaluate_mlb_stop_rules, get_mlb_stop_rule_status
status = evaluate_mlb_stop_rules()
_check("suspended=False with no state file", status["suspended"] is False)
_check("trigger is None", status["trigger"] is None)

# Test 2: pre-inject suspended state → sticky
print("\nTest 2: pre-inject suspended → sticky (no re-evaluation clears)")
_write(_MLB_STATE, _suspended_state("full_model", roi=-14.0, n=45))
import importlib, mlb_stop_rules
importlib.reload(mlb_stop_rules)
from mlb_stop_rules import evaluate_mlb_stop_rules, get_mlb_stop_rule_status
status2 = evaluate_mlb_stop_rules()
_check("suspended=True (sticky)", status2["suspended"] is True)
_check("trigger preserved", status2["trigger"] == "full_model")
_check("roi preserved", status2["roi"] == -14.0)

# Test 3: get_mlb_stop_rule_status reads without evaluating
print("\nTest 3: get_mlb_stop_rule_status reads state")
_write(_MLB_STATE, _suspended_state("tier_HIGH", roi=-11.5, n=22))
importlib.reload(mlb_stop_rules)
from mlb_stop_rules import get_mlb_stop_rule_status
status3 = get_mlb_stop_rule_status()
_check("suspended=True from state file", status3["suspended"] is True)
_check("trigger=tier_HIGH", status3["trigger"] == "tier_HIGH")

# Test 4: reset script clears state
print("\nTest 4: reset script clears suspension")
_write(_MLB_STATE, _suspended_state("full_model", roi=-13.0, n=55))
import mlb_reset_stop_rules
mlb_reset_stop_rules.reset(reason="mock test reset")
state4 = _load(_MLB_STATE)
_check("suspended=False after reset", state4["suspended"] is False)
_check("trigger cleared", state4["trigger"] is None)
_check("suspension_log has TRIGGERED + RESET", len(state4["suspension_log"]) == 2)
_check("log[1].event == RESET", state4["suspension_log"][1]["event"] == "RESET")
_check("reset reason logged", "mock test reset" in state4["suspension_log"][1]["reason"])

# Test 5: reset on non-suspended state is a no-op
print("\nTest 5: reset on non-suspended state → no-op")
_write(_MLB_STATE, _clean_state())
mlb_reset_stop_rules.reset(reason="no-op test")
state5 = _load(_MLB_STATE)
_check("still not suspended", state5["suspended"] is False)
_check("suspension_log still empty", len(state5["suspension_log"]) == 0)


# ── NBA tests ─────────────────────────────────────────────────────────────────

print("\n── NBA Stop Rule Tests ──────────────────────────────────────")

# Test 6: no state file → not suspended
print("\nTest 6: no state file → not suspended")
_clear(_NBA_STATE)
import nba_stop_rules
importlib.reload(nba_stop_rules)
from nba_stop_rules import evaluate_nba_stop_rules, get_nba_stop_rule_status
status6 = evaluate_nba_stop_rules()
_check("suspended=False with no state file", status6["suspended"] is False)

# Test 7: pre-inject suspended state → sticky
print("\nTest 7: pre-inject suspended → sticky")
_write(_NBA_STATE, _suspended_state("tier_MEDIUM", roi=-10.8, n=26))
importlib.reload(nba_stop_rules)
from nba_stop_rules import evaluate_nba_stop_rules
status7 = evaluate_nba_stop_rules()
_check("suspended=True (sticky)", status7["suspended"] is True)
_check("trigger=tier_MEDIUM", status7["trigger"] == "tier_MEDIUM")

# Test 8: get_nba_stop_rule_status
print("\nTest 8: get_nba_stop_rule_status reads state")
_write(_NBA_STATE, _suspended_state("full_model", roi=-13.0, n=52))
importlib.reload(nba_stop_rules)
from nba_stop_rules import get_nba_stop_rule_status
status8 = get_nba_stop_rule_status()
_check("suspended=True from state", status8["suspended"] is True)
_check("n=52", status8["n"] == 52)

# Test 9: NBA reset script
print("\nTest 9: NBA reset script clears suspension")
_write(_NBA_STATE, _suspended_state("full_model", roi=-13.0, n=52))
import nba_reset_stop_rules
nba_reset_stop_rules.reset(reason="nba mock test")
state9 = _load(_NBA_STATE)
_check("suspended=False after reset", state9["suspended"] is False)
_check("log has TRIGGERED + RESET", len(state9["suspension_log"]) == 2)
_check("log[1].event == RESET", state9["suspension_log"][1]["event"] == "RESET")


# ── restore and summary ───────────────────────────────────────────────────────
_restore()

print(f"\n{'='*50}")
print(f"Results: {_PASS} passed, {_FAIL} failed")
if _FAIL > 0:
    sys.exit(1)
else:
    print("All tests passed.")
