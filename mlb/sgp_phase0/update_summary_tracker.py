#!/usr/bin/env python3
"""
SGP Phase 0 — Rebuild summary tracker from sgp_manual_log.json.
Called automatically after each log_sgp_price.py entry.
"""
import json
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("sgp_tracker")

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "sgp_manual_log.json"
TRACKER_PATH = BASE_DIR / "summary_tracker.parquet"

SCHEMA_COLS = [
    "date", "book", "player_name", "player_team", "pair_type",
    "fair_combined_prob", "fair_american_odds",
    "book_sgp_price", "book_sgp_implied_prob",
    "same_book_tb_price", "same_book_tb_implied_prob",
    "same_book_comparison", "reference_book_mismatch",
    "excess_hold", "ev_per_unit", "result",
]


def rebuild():
    """Rebuild summary_tracker.parquet from sgp_manual_log.json."""
    if not LOG_PATH.exists():
        df = pd.DataFrame(columns=SCHEMA_COLS)
        df.to_parquet(TRACKER_PATH, index=False)
        logger.info(f"Created empty tracker: {TRACKER_PATH}")
        return df

    try:
        entries = json.loads(LOG_PATH.read_text())
    except Exception:
        entries = []

    if not entries:
        df = pd.DataFrame(columns=SCHEMA_COLS)
        df.to_parquet(TRACKER_PATH, index=False)
        logger.info(f"Tracker rebuilt: 0 rows")
        return df

    rows = []
    for e in entries:
        rows.append({
            "date": e.get("date"),
            "book": e.get("book"),
            "player_name": e.get("player"),
            "player_team": "",
            "pair_type": e.get("pair"),
            "fair_combined_prob": e.get("fair_combined_prob"),
            "fair_american_odds": e.get("fair_american_odds"),
            "book_sgp_price": e.get("book_sgp_price"),
            "book_sgp_implied_prob": e.get("book_sgp_implied_prob"),
            "same_book_tb_price": e.get("same_book_tb_price"),
            "same_book_tb_implied_prob": e.get("same_book_tb_implied_prob"),
            "same_book_comparison": e.get("same_book_comparison", False),
            "reference_book_mismatch": e.get("reference_book_mismatch", False),
            "excess_hold": e.get("excess_hold"),
            "ev_per_unit": e.get("ev_per_unit"),
            "result": e.get("result"),
        })

    df = pd.DataFrame(rows)
    df.to_parquet(TRACKER_PATH, index=False)

    n = len(df)
    avg_eh = df["excess_hold"].mean() * 100 if df["excess_hold"].notna().any() else 0
    n_sb = df["same_book_comparison"].sum()
    logger.info(f"Tracker rebuilt: {n} rows, avg excess hold={avg_eh:+.1f}pp, same-book={n_sb}")

    return df


if __name__ == "__main__":
    rebuild()
