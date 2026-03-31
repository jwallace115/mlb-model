#!/usr/bin/env python3
"""
MLB Line Snapshot Store
========================
Stores total line snapshots for ALL MLB games at each pull time.
Separate from the V1 signal pipeline — observational infrastructure only.

Snapshot labels: OPEN (10PM prior night), 7AM, 11AM, 5PM, CLOSING
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("line_snapshots")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT_PATH = PROJECT_ROOT / "mlb_sim" / "data" / "line_snapshots_2026.json"


def _load_snapshots():
    """Load existing snapshot records."""
    if not SNAPSHOT_PATH.exists():
        return []
    try:
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def _save_snapshots(records):
    """Save snapshot records."""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(records, f, indent=2)


def _record_exists(records, game_id, snapshot_label):
    """Check if a record already exists for this game + label."""
    for r in records:
        if r.get("game_id") == game_id and r.get("snapshot_label") == snapshot_label:
            return True
    return False


def _get_first_seen(records, game_id):
    """Get the first_seen_timestamp for a game, or None."""
    for r in records:
        if r.get("game_id") == game_id and r.get("first_seen_timestamp"):
            return r["first_seen_timestamp"]
    return None


def store_snapshot(game_id, game_date, home_team, away_team,
                   snapshot_label, total_line, over_price, under_price,
                   book="consensus"):
    """
    Store a single line snapshot. Idempotent — skips if record exists.

    Args:
        game_id: Odds API game ID or game_pk
        game_date: YYYY-MM-DD
        home_team: team abbreviation
        away_team: team abbreviation
        snapshot_label: OPEN | 7AM | 11AM | 5PM | CLOSING
        total_line: e.g. 8.5
        over_price: e.g. -110
        under_price: e.g. -110
        book: source book name
    """
    records = _load_snapshots()

    if _record_exists(records, game_id, snapshot_label):
        return False  # already exists, skip

    first_seen = _get_first_seen(records, game_id) or datetime.now().isoformat()

    record = {
        "game_id": game_id,
        "game_date": str(game_date),
        "home_team": home_team,
        "away_team": away_team,
        "snapshot_time": datetime.now().isoformat(),
        "first_seen_timestamp": first_seen,
        "snapshot_label": snapshot_label,
        "total_line": total_line,
        "over_price": over_price,
        "under_price": under_price,
        "book": book,
    }

    records.append(record)
    _save_snapshots(records)
    return True


def store_snapshots_from_odds_response(games_data, snapshot_label, game_date,
                                        team_map=None):
    """
    Parse Odds API response and store snapshots for all games.

    Args:
        games_data: list of game dicts from Odds API
        snapshot_label: OPEN | 7AM | 11AM | 5PM | CLOSING
        game_date: YYYY-MM-DD
        team_map: optional dict mapping Odds API team names to abbreviations

    Returns:
        (stored_count, skipped_count, no_line_count)
    """
    if team_map is None:
        from config import ODDS_API_TEAM_MAP
        team_map = ODDS_API_TEAM_MAP

    stored = 0
    skipped = 0
    no_line = 0

    for g in games_data:
        gid = g.get("id", "")
        home_full = g.get("home_team", "")
        away_full = g.get("away_team", "")
        home = team_map.get(home_full, home_full)
        away = team_map.get(away_full, away_full)

        # Find totals from first bookmaker with data
        total_line = None
        over_price = None
        under_price = None
        book = None

        for bm in g.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "totals":
                    for outcome in mkt.get("outcomes", []):
                        if outcome.get("name") == "Over":
                            over_price = outcome.get("price")
                            total_line = outcome.get("point")
                        elif outcome.get("name") == "Under":
                            under_price = outcome.get("price")
                    if total_line is not None:
                        book = bm.get("key", "unknown")
                        break
            if total_line is not None:
                break

        if total_line is None:
            no_line += 1
            continue

        result = store_snapshot(
            game_id=gid, game_date=game_date,
            home_team=home, away_team=away,
            snapshot_label=snapshot_label,
            total_line=total_line,
            over_price=over_price,
            under_price=under_price,
            book=book,
        )
        if result:
            stored += 1
        else:
            skipped += 1

    logger.info(f"Line snapshots [{snapshot_label}]: stored={stored}, skipped={skipped}, no_line={no_line}")
    return stored, skipped, no_line


def get_game_snapshots(game_id):
    """Get all snapshots for a specific game, sorted by label order."""
    records = _load_snapshots()
    label_order = {"OPEN": 0, "7AM": 1, "11AM": 2, "5PM": 3, "CLOSING": 4}
    game_recs = [r for r in records if r.get("game_id") == game_id]
    game_recs.sort(key=lambda r: label_order.get(r.get("snapshot_label", ""), 9))
    return game_recs


def compute_movement(game_id, signal_line=None):
    """
    Compute line movement for a game.

    Returns dict with:
        open_line, line_at_7am, line_at_11am, line_at_5pm, closing_line,
        open_to_7am_move, open_to_closing_move,
        signal_line, signal_to_closing_clv,
        movement_summary (string or None)
    """
    snaps = get_game_snapshots(game_id)
    if not snaps:
        return None

    result = {
        "open_line": None, "line_at_7am": None, "line_at_11am": None,
        "line_at_5pm": None, "closing_line": None,
        "open_to_7am_move": None, "open_to_closing_move": None,
        "signal_line": signal_line,
        "signal_to_closing_clv": None,
        "movement_summary": None,
    }

    for s in snaps:
        label = s.get("snapshot_label", "")
        line = s.get("total_line")
        if label == "OPEN":
            result["open_line"] = line
        elif label == "7AM":
            result["line_at_7am"] = line
        elif label == "11AM":
            result["line_at_11am"] = line
        elif label == "5PM":
            result["line_at_5pm"] = line
        elif label == "CLOSING":
            result["closing_line"] = line

    # Compute movements
    open_line = result["open_line"]
    closing = result["closing_line"] or result["line_at_5pm"] or result["line_at_11am"]

    if open_line is not None and result["line_at_7am"] is not None:
        result["open_to_7am_move"] = round(result["line_at_7am"] - open_line, 1)

    if open_line is not None and closing is not None:
        result["open_to_closing_move"] = round(closing - open_line, 1)

    if signal_line is not None and closing is not None:
        result["signal_to_closing_clv"] = round(signal_line - closing, 1)

    # Movement summary
    if open_line is not None and closing is not None:
        move = closing - open_line
        if abs(move) < 0.25:
            result["movement_summary"] = "Line hasn't moved off the open — no steam either direction."
        elif move < -0.25:
            result["movement_summary"] = (
                f"Line has ticked down {abs(move):.1f} from the open — market agrees with the under."
            )
        elif move > 0.25:
            result["movement_summary"] = (
                f"Line moved up {move:.1f} since opening, which works against us — shop for the best number."
            )
    elif open_line is not None:
        result["movement_summary"] = None  # no closing yet, no summary

    return result
