"""
Line movement tracker — logs opening and closing totals to data/line_movement.csv.

Called from push_results.py (opening line) and refresh.py (closing line).
Builds a validation dataset over the season for edge analysis.

CSV columns:
  date, game_id, home_team, away_team,
  open_total, model_projection, model_edge,
  close_total, line_move, final_model_edge
"""

import csv
import logging
import os
from datetime import date
from typing import Optional

from config import DATA_DIR

logger = logging.getLogger(__name__)

LINE_CSV = os.path.join(DATA_DIR, "line_movement.csv")
COLUMNS  = [
    "date", "game_id", "home_team", "away_team",
    "open_total", "model_projection", "model_edge",
    "close_total", "line_move", "final_model_edge",
]


def _read_csv() -> list[dict]:
    if not os.path.exists(LINE_CSV):
        return []
    try:
        with open(LINE_CSV, newline="") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        logger.warning(f"line_movement.csv read error: {e}")
        return []


def _write_csv(rows: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(LINE_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        logger.warning(f"line_movement.csv write error: {e}")


def log_opening_lines(game_date: str, results: list[dict]) -> None:
    """
    Called after the morning model run.
    Appends one row per game with the opening line and model projection.
    Does not overwrite existing rows for the same game.
    """
    existing = _read_csv()
    existing_ids = {r["game_id"] for r in existing}

    new_rows = []
    for r in results:
        game       = r.get("game", {})
        proj       = r.get("projection", {})
        odds       = r.get("odds", {})
        full_lines = (odds or {}).get("full") or {}

        game_id    = str(game.get("game_pk", ""))
        if game_id in existing_ids:
            continue   # already logged (refresh re-run guard)

        open_total   = full_lines.get("consensus")
        model_proj   = proj.get("proj_total_full")
        model_edge   = (
            round(float(model_proj) - float(open_total), 2)
            if open_total is not None and model_proj is not None
            else None
        )

        new_rows.append({
            "date":             game_date,
            "game_id":          game_id,
            "home_team":        game.get("home_team", ""),
            "away_team":        game.get("away_team", ""),
            "open_total":       open_total if open_total is not None else "",
            "model_projection": model_proj if model_proj is not None else "",
            "model_edge":       model_edge if model_edge is not None else "",
            "close_total":      "",
            "line_move":        "",
            "final_model_edge": "",
        })

    if new_rows:
        _write_csv(existing + new_rows)
        logger.info(f"[line_tracker] Logged opening lines for {len(new_rows)} games on {game_date}")
    else:
        logger.info(f"[line_tracker] No new opening lines to log for {game_date}")


def update_closing_lines(game_date: str, results: list[dict]) -> None:
    """
    Called from refresh.py after the pre-game refresh.
    Updates close_total, line_move, and final_model_edge for today's games.
    """
    existing = _read_csv()
    if not existing:
        logger.warning("[line_tracker] No existing rows to update with closing lines.")
        return

    row_by_id = {r["game_id"]: r for r in existing}
    updated   = 0

    for r in results:
        game       = r.get("game", {})
        proj       = r.get("projection", {})
        odds       = r.get("odds", {})
        full_lines = (odds or {}).get("full") or {}

        game_id     = str(game.get("game_pk", ""))
        close_total = full_lines.get("consensus")
        model_proj  = proj.get("proj_total_full")

        if game_id not in row_by_id:
            continue

        row = row_by_id[game_id]

        # Compute line movement
        try:
            open_total = float(row["open_total"]) if row.get("open_total") else None
        except (ValueError, TypeError):
            open_total = None

        line_move = (
            round(float(close_total) - open_total, 1)
            if close_total is not None and open_total is not None
            else None
        )
        final_edge = (
            round(float(model_proj) - float(close_total), 2)
            if close_total is not None and model_proj is not None
            else None
        )

        row["close_total"]      = close_total if close_total is not None else ""
        row["line_move"]        = line_move   if line_move   is not None else ""
        row["final_model_edge"] = final_edge  if final_edge  is not None else ""
        updated += 1

    _write_csv(existing)
    logger.info(f"[line_tracker] Updated closing lines for {updated} games on {game_date}")
