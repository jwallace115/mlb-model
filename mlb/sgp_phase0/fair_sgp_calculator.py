#!/usr/bin/env python3
"""
SGP Phase 0 — Fair SGP price calculator using STRUCTURAL_CONTAINMENT.
Fair price = TB leg standalone (hits leg is logically redundant).
"""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("sgp_fair")

BASE_DIR = Path(__file__).resolve().parent
LEG_DIR = BASE_DIR / "leg_prices"
FAIR_DIR = BASE_DIR / "fair_prices"
FAIR_DIR.mkdir(parents=True, exist_ok=True)


def implied_to_american(prob):
    """Convert implied probability to American odds."""
    if prob >= 0.5:
        return round(-(prob / (1 - prob)) * 100)
    else:
        return round(((1 - prob) / prob) * 100)


def compute_fair(game_date=None):
    """Compute fair SGP prices for a date."""
    if game_date is None:
        # Find most recent leg_prices file
        files = sorted(LEG_DIR.glob("leg_prices_*.parquet"))
        if not files:
            logger.error("No leg price files found")
            return pd.DataFrame()
        game_date = files[-1].stem.replace("leg_prices_", "").replace("_", "-")

    leg_path = LEG_DIR / f"leg_prices_{game_date.replace('-','_')}.parquet"
    if not leg_path.exists():
        logger.error(f"No leg prices for {game_date}")
        return pd.DataFrame()

    df = pd.read_parquet(leg_path)
    logger.info(f"Loaded {len(df)} leg price rows for {game_date}")

    # STRUCTURAL_CONTAINMENT: fair price = TB leg price
    # Pair A: fair = TB O1.5 price. Pair B: fair = TB O2.5 price.
    df["fair_prob_method"] = "STRUCTURAL_CONTAINMENT"
    df["fair_combined_prob"] = df["leg2_implied_prob"]  # TB leg implied prob
    df["fair_american_odds"] = df["leg2_price"]  # TB leg price directly

    # Placeholders for manual logging
    df["book_sgp_price"] = None
    df["book_sgp_implied_prob"] = None
    df["same_book_tb_price"] = None
    df["same_book_tb_implied_prob"] = None
    df["same_book_comparison"] = False
    df["reference_book_mismatch"] = None
    df["decimal_odds_book"] = None
    df["edge"] = None
    df["excess_hold"] = None
    df["ev_per_unit"] = None

    # Save
    out_path = FAIR_DIR / f"fair_sgp_{game_date.replace('-','_')}.parquet"
    df.to_parquet(out_path, index=False)
    logger.info(f"Saved: {out_path}")

    # Print summary
    for pt in ["A", "B"]:
        sub = df[df["pair_type"] == pt]
        if len(sub) > 0:
            avg_fair = sub["fair_combined_prob"].mean()
            avg_odds = sub["fair_american_odds"].mean()
            logger.info(f"  Pair {pt}: {len(sub)} rows, avg fair prob={avg_fair:.3f}, avg fair odds={avg_odds:+.0f}")

    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    compute_fair(args.date)
