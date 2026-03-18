#!/usr/bin/env python3
"""
Manual reset for NBA stop rules.

Appends a RESET event to the suspension_log and clears the suspension.
Does NOT delete history — the log is append-only.

Usage:
    python nba_reset_stop_rules.py [--reason "line quality improved"]
"""

import argparse
import json
import os
from datetime import datetime, timezone

_REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_REPO_DIR, "nba", "data", "nba_stop_rule_state.json")


def reset(reason: str = "") -> None:
    if os.path.exists(_STATE_PATH):
        with open(_STATE_PATH) as f:
            state = json.load(f)
    else:
        state = {
            "suspended": False,
            "trigger": None,
            "triggered_at": None,
            "roi": None,
            "n": None,
            "suspension_log": [],
        }

    now = datetime.now(timezone.utc).isoformat()

    if not state.get("suspended"):
        print("[nba_reset_stop_rules] Model is not currently suspended — nothing to reset.")
        print(f"  State: {state}")
        return

    state["suspension_log"].append({
        "event":     "RESET",
        "timestamp": now,
        "reason":    reason or "manual reset",
        "was_trigger": state.get("trigger"),
        "was_roi":     state.get("roi"),
        "was_n":       state.get("n"),
    })

    state["suspended"]    = False
    state["trigger"]      = None
    state["triggered_at"] = None
    state["roi"]          = None
    state["n"]            = None

    with open(_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"[nba_reset_stop_rules] Suspension cleared at {now}")
    print(f"  Reason: {reason or 'manual reset'}")
    print(f"  Suspension log now has {len(state['suspension_log'])} entries.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset NBA stop-rule suspension")
    parser.add_argument("--reason", default="", help="Reason for reset (logged)")
    args = parser.parse_args()
    reset(reason=args.reason)


if __name__ == "__main__":
    main()
