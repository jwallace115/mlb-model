#!/usr/bin/env python3
"""
NFL Daily Pipeline — Phase 1 skeleton.

NFL season: September through February.
Off-season: exits cleanly with no crash.

Usage:
    python3 nfl/nfl_daily_pipeline.py
    python3 nfl/nfl_daily_pipeline.py --date 2026-09-15
"""

import argparse
import json
import logging
import os
import pickle
import sys
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import requests
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NFL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(NFL_DIR, "data")
MODELS_DIR = os.path.join(NFL_DIR, "models")
DECISIONS_PATH = os.path.join(DATA_DIR, "nfl_decisions.parquet")

TIER_HIGH = 0.10
TIER_MEDIUM = 0.07
TIER_LOW = 0.05

FEATURE_COLS = [
    "home_pts_scored_rolling", "home_pts_allowed_rolling",
    "away_pts_scored_rolling", "away_pts_allowed_rolling",
    "is_dome_f", "wind_for_feature", "temp_for_feature",
    "wind_bucket", "neutral_site_f",
    "home_rest_days", "away_rest_days", "rest_advantage",
    "is_short_week_home", "is_short_week_away",
]


def is_nfl_season(d: date) -> bool:
    """Check if date falls within NFL season (Sep 1 - Feb 15)."""
    m = d.month
    return m >= 9 or m <= 2


def load_model():
    with open(os.path.join(MODELS_DIR, "ridge_model.pkl"), "rb") as f:
        ridge = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "impute_vals.json")) as f:
        impute_vals = json.load(f)
    with open(os.path.join(MODELS_DIR, "sigma.json")) as f:
        sigma = json.load(f)["sigma"]
    return ridge, scaler, impute_vals, sigma


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()
    d = date.fromisoformat(game_date)

    logger.info(f"NFL daily pipeline — {game_date}")

    if not is_nfl_season(d):
        logger.info("No NFL games scheduled (off-season). Exiting cleanly.")
        print("[nfl_pipeline] Off-season — no games scheduled.")
        return

    # Check if model exists
    if not os.path.exists(os.path.join(MODELS_DIR, "ridge_model.pkl")):
        logger.warning("NFL model not trained yet. Run nfl/train_model.py first.")
        return

    ridge, scaler, impute_vals, sigma = load_model()

    # Phase 1 totals model is excluded (OOS gate failed).
    # Phase 8 conditional signals run independently.
    logger.info("Phase 1 model excluded — running conditional signals only.")

    # Phase 8: Conditional signal generation
    try:
        from nfl.phase8_conditional_signals import load_config, evaluate_stop_rules, generate_signals, append_signals, grade_signals
        cfg = load_config()
        if cfg:
            # Grade yesterday
            yesterday = (d - timedelta(days=1)).isoformat()
            grade_signals(yesterday)
            # Generate today
            stop_state = evaluate_stop_rules()
            signals = generate_signals(game_date, cfg, stop_state)
            if signals:
                append_signals(signals)
                print(f"[nfl_pipeline] {len(signals)} conditional signals for {game_date}")
            else:
                print(f"[nfl_pipeline] No conditional signals for {game_date}")
        else:
            logger.warning("Conditional config not loaded — skipping Phase 8")
    except Exception as e:
        logger.warning(f"Phase 8 conditional signals failed (non-fatal): {e}")
        print(f"[nfl_pipeline] Conditional signals failed: {e}")


if __name__ == "__main__":
    main()
