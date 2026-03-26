#!/usr/bin/env python3
"""
Parlay Tracker — logs and grades 3-leg and 5-leg fun parlays.
Reads signals_2026.json for today's legs, grades against actuals.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger("parlay_tracker")

BASE = Path(__file__).resolve().parent.parent
TRACKER_PATH = BASE / "logs" / "parlay_tracker_2026.json"
SIGNALS_PATH = BASE / "logs" / "signals_2026.json"

PAYOUT_3 = 6.0   # ~6x at -110 each leg
PAYOUT_5 = 24.0  # ~24x at -110 each leg


def _load_tracker():
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH) as f:
            return json.load(f)
    return {
        "three_leg": {"parlays": [], "summary": {"total": 0, "wins": 0, "losses": 0, "pending": 0, "win_rate": 0, "net_units": 0, "payout_per_win": PAYOUT_3}},
        "five_leg": {"parlays": [], "summary": {"total": 0, "wins": 0, "losses": 0, "pending": 0, "win_rate": 0, "net_units": 0, "payout_per_win": PAYOUT_5}},
        "note": "Just for fun — not a recommended betting strategy",
    }


def _save_tracker(data):
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_PATH, "w") as f:
        json.dump(data, f, indent=2)


def log_today_parlays(game_date_str):
    """Create parlay entries for today from signals_2026.json."""
    if not SIGNALS_PATH.exists():
        return

    with open(SIGNALS_PATH) as f:
        rows = json.load(f)

    today = [r for r in rows if str(r.get("date", "")) == game_date_str]
    if len(today) < 3:
        return

    # Rank by p_under
    today.sort(key=lambda r: float(r.get("raw_p_under", 0)), reverse=True)

    tracker = _load_tracker()

    # Check if already logged today
    existing_dates_3 = {p["date"] for p in tracker["three_leg"]["parlays"]}
    existing_dates_5 = {p["date"] for p in tracker["five_leg"]["parlays"]}

    if game_date_str not in existing_dates_3:
        legs_3 = [{"game": f'{r["away_team"]}@{r["home_team"]}',
                    "bet": "FULL GAME UNDER",
                    "line": r.get("line_at_signal_time"),
                    "result": None} for r in today[:3]]
        tracker["three_leg"]["parlays"].append({
            "date": game_date_str, "type": "3-leg",
            "legs": legs_3, "result": "pending", "net_units": None,
        })
        logger.info(f"Parlay: logged 3-leg for {game_date_str}")

    if len(today) >= 5 and game_date_str not in existing_dates_5:
        legs_5 = [{"game": f'{r["away_team"]}@{r["home_team"]}',
                    "bet": "FULL GAME UNDER",
                    "line": r.get("line_at_signal_time"),
                    "result": None} for r in today[:5]]
        tracker["five_leg"]["parlays"].append({
            "date": game_date_str, "type": "5-leg",
            "legs": legs_5, "result": "pending", "net_units": None,
        })
        logger.info(f"Parlay: logged 5-leg for {game_date_str}")

    _save_tracker(tracker)


def grade_parlays():
    """Grade pending parlays using resolved signals."""
    if not SIGNALS_PATH.exists() or not TRACKER_PATH.exists():
        return

    with open(SIGNALS_PATH) as f:
        signals = json.load(f)

    # Build result map: "away@home" + date → result
    result_map = {}
    for s in signals:
        if s.get("resolved") == 1 and s.get("result"):
            key = (f'{s["away_team"]}@{s["home_team"]}', s["date"])
            result_map[key] = s["result"]

    tracker = _load_tracker()
    changed = False

    for tier_key, payout in [("three_leg", PAYOUT_3), ("five_leg", PAYOUT_5)]:
        for parlay in tracker[tier_key]["parlays"]:
            if parlay["result"] != "pending":
                continue

            all_resolved = True
            all_won = True
            for leg in parlay["legs"]:
                key = (leg["game"], parlay["date"])
                leg_result = result_map.get(key)
                if leg_result is None:
                    all_resolved = False
                    break
                leg["result"] = leg_result
                if leg_result != "WIN":
                    all_won = False

            if all_resolved:
                if all_won:
                    parlay["result"] = "WIN"
                    parlay["net_units"] = round(payout - 1, 2)  # payout minus 1u stake
                else:
                    parlay["result"] = "LOSS"
                    parlay["net_units"] = -1.0
                changed = True

        # Update summary
        resolved = [p for p in tracker[tier_key]["parlays"] if p["result"] != "pending"]
        wins = sum(1 for p in resolved if p["result"] == "WIN")
        losses = sum(1 for p in resolved if p["result"] == "LOSS")
        pending = sum(1 for p in tracker[tier_key]["parlays"] if p["result"] == "pending")
        total = wins + losses
        net = sum(p["net_units"] for p in resolved if p["net_units"] is not None)

        tracker[tier_key]["summary"] = {
            "total": total, "wins": wins, "losses": losses, "pending": pending,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "net_units": round(net, 2),
            "payout_per_win": payout,
        }

    if changed:
        _save_tracker(tracker)
        logger.info("Parlay: graded pending parlays")


def run_daily(game_date_str):
    """Full daily parlay pipeline."""
    grade_parlays()
    log_today_parlays(game_date_str)
