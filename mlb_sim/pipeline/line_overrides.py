#!/usr/bin/env python3
"""
Hard Rock line override utility.

Reads/writes line_overrides_2026.json for grading with actual book lines
instead of Odds API consensus lines.

Override file is append-only with dedup by game_id + market (last write wins).
Does NOT affect signal generation, unit sizing, or any production logic.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("line_overrides")

OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "line_overrides_2026.json"


def _load_overrides():
    """Load all overrides from JSON file."""
    if not OVERRIDES_PATH.exists():
        return []
    try:
        with open(OVERRIDES_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def _save_overrides(overrides):
    """Save overrides to JSON file."""
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRIDES_PATH, "w") as f:
        json.dump(overrides, f, indent=2)


def save_override(game_id, date_str, market, odds_api_line, hard_rock_line):
    """
    Save a line override. Deduplicates by game_id + market (last write wins).

    Args:
        game_id: game identifier (str or int)
        date_str: "YYYY-MM-DD"
        market: "full_game" | "f5_total" | "f5_runline"
        odds_api_line: original Odds API line (float)
        hard_rock_line: user's actual line at Hard Rock (float)
    """
    overrides = _load_overrides()

    # Remove prior entry for same game_id + market
    key = (str(game_id), market)
    overrides = [o for o in overrides if (str(o.get("game_id")), o.get("market")) != key]

    overrides.append({
        "game_id": str(game_id),
        "date": date_str,
        "market": market,
        "odds_api_line": odds_api_line,
        "hard_rock_line": hard_rock_line,
        "entered_at": datetime.now().isoformat(),
    })

    _save_overrides(overrides)
    logger.info(f"Line override saved: game={game_id} market={market} "
                f"API={odds_api_line} → HR={hard_rock_line}")


def get_override(game_id, market):
    """
    Get override for a specific game_id + market.

    Returns: hard_rock_line (float) if override exists, else None
    """
    overrides = _load_overrides()
    for o in reversed(overrides):  # last write wins
        if str(o.get("game_id")) == str(game_id) and o.get("market") == market:
            return float(o["hard_rock_line"])
    return None


def get_all_overrides_for_date(date_str):
    """
    Get all overrides for a given date.

    Returns: dict of (game_id, market) → hard_rock_line
    """
    overrides = _load_overrides()
    result = {}
    for o in overrides:
        if o.get("date") == date_str:
            result[(str(o["game_id"]), o["market"])] = float(o["hard_rock_line"])
    return result
