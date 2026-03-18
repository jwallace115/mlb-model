#!/usr/bin/env python3
"""
Manual reset for NBA stop rules.

Appends a RESET event to suspension_log and clears all suspensions.
Does NOT delete history — log is append-only.

Usage:
    python nba_reset_stop_rules.py --reason "line quality improved"
    python nba_reset_stop_rules.py --status        # print current state, no change
"""

import argparse
import json
import os
from datetime import datetime, timezone

_REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_REPO_DIR, "nba", "data", "nba_stop_rule_state.json")

_TIERS = ("HIGH", "MEDIUM", "LOW")


def _load() -> dict:
    if os.path.exists(_STATE_PATH):
        with open(_STATE_PATH) as f:
            return json.load(f)
    return {}


def status() -> None:
    s = _load()
    print(f"[nba_stop_rules] model_suspended: {s.get('model_suspended', False)}")
    print(f"[nba_stop_rules] suspended_tiers: {s.get('suspended_tiers', [])}")
    print(f"[nba_stop_rules] suspension_log entries: {len(s.get('suspension_log', []))}")


def reset(reason: str = "") -> None:
    s = _load()
    now = datetime.now(timezone.utc).isoformat()

    currently_suspended = s.get("model_suspended", False) or bool(s.get("suspended_tiers", []))
    if not currently_suspended:
        print("[nba_reset_stop_rules] Nothing is currently suspended — nothing to reset.")
        return

    log = s.get("suspension_log", [])
    log.append({
        "event":               "RESET",
        "timestamp":           now,
        "reason":              reason or "manual reset",
        "was_model_suspended": s.get("model_suspended", False),
        "was_suspended_tiers": s.get("suspended_tiers", []),
    })

    from nba_stop_rules import _empty_state
    fresh = _empty_state()
    fresh["suspension_log"] = log

    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(fresh, f, indent=2)

    print(f"[nba_reset_stop_rules] All suspensions cleared at {now}")
    print(f"  Reason: {reason or 'manual reset'}")
    print(f"  Suspension log now has {len(log)} entries.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason", default="", help="Reason for reset (logged)")
    parser.add_argument("--status", action="store_true", help="Print current state only")
    args = parser.parse_args()
    if args.status:
        status()
    else:
        reset(reason=args.reason)


if __name__ == "__main__":
    main()
