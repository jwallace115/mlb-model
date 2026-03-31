#!/usr/bin/env python3
"""
Phase 6 — Build first-half features table.

Merges H1 scores (home_h1, away_h1, actual_h1_total) onto the existing
features.parquet game rows, then adds rolling_h1_league_avg using the same
70/30 blending logic as the full-game model.

Output: nba/data/h1_features.parquet

Run once; re-run to refresh H1 data for new seasons.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import pandas as pd

from nba.config import (
    ALL_HISTORICAL_SEASONS,
    FEATURES_PATH,
    H1_FEATURES_PATH,
    LEAGUE_AVG_H1_TOTAL,
    PRIOR_SEASON_WEIGHT,
    SEASON_BLEND_END,
    SEASON_BLEND_START,
)
from nba.modules.fetch_halftime import fetch_halftime_season

logger = logging.getLogger(__name__)


def _prior_season_key(season: str, all_seasons: list) -> str:
    idx = all_seasons.index(season) if season in all_seasons else -1
    return all_seasons[idx - 1] if idx > 0 else ""


def _rolling_h1_league_avg(feat: pd.DataFrame) -> pd.Series:
    """
    Compute per-game rolling H1 league average with no leakage.
    Same 70/30 blending logic as full-game rolling_league_avg.
    Prior for the first season falls back to LEAGUE_AVG_H1_TOTAL.
    """
    feat = feat.sort_values(["season", "date"]).reset_index(drop=True)
    all_seasons = sorted(feat["season"].unique())

    # Pre-compute prior-season H1 means
    prior_h1: dict = {}
    for s in all_seasons:
        idx = feat["season"] == s
        prior_h1[s] = feat.loc[idx, "actual_h1_total"].mean()

    result = []
    for season, group in feat.groupby("season", sort=True):
        prior_key = _prior_season_key(season, all_seasons)
        prior_mean = prior_h1.get(prior_key, LEAGUE_AVG_H1_TOTAL)

        for i, (_, row) in enumerate(group.iterrows()):
            past = group.iloc[:i]["actual_h1_total"]
            n_past = len(past)
            cur_mean = past.mean() if n_past > 0 else prior_mean

            if n_past >= SEASON_BLEND_END:
                blended = cur_mean
            elif n_past <= SEASON_BLEND_START:
                blended = PRIOR_SEASON_WEIGHT * prior_mean + (1 - PRIOR_SEASON_WEIGHT) * cur_mean
            else:
                t = (n_past - SEASON_BLEND_START) / (SEASON_BLEND_END - SEASON_BLEND_START)
                w = PRIOR_SEASON_WEIGHT * (1 - t)
                blended = w * prior_mean + (1 - w) * cur_mean
            result.append((group.index[i], round(blended, 2)))

    idx_vals, rla_vals = zip(*result) if result else ([], [])
    return pd.Series(dict(zip(idx_vals, rla_vals)))


def build_h1_features() -> pd.DataFrame:
    if not os.path.exists(FEATURES_PATH):
        raise FileNotFoundError(
            f"features.parquet not found at {FEATURES_PATH}. Run build_features.py first."
        )

    feat = pd.read_parquet(FEATURES_PATH)
    logger.info(f"Loaded {len(feat)} game rows from features.parquet")

    # Fetch H1 scores for all historical seasons
    h1_frames = []
    for season in ALL_HISTORICAL_SEASONS:
        df = fetch_halftime_season(season)
        if not df.empty:
            h1_frames.append(df)
        else:
            logger.warning(f"No H1 data returned for {season}")

    if not h1_frames:
        raise RuntimeError("No H1 data fetched — check API connectivity.")

    h1_all = pd.concat(h1_frames, ignore_index=True)
    logger.info(f"H1 data: {len(h1_all)} game rows across {len(h1_frames)} seasons")

    # Merge — inner join: only keep games with both features and H1 scores
    feat_h1 = feat.merge(
        h1_all[["game_id", "home_h1", "away_h1", "actual_h1_total"]],
        on="game_id",
        how="inner",
    )
    n_dropped = len(feat) - len(feat_h1)
    if n_dropped:
        logger.warning(f"Dropped {n_dropped} games with missing H1 data (API gaps)")
    logger.info(f"Merged H1 features: {len(feat_h1)} games")

    # Naive H1 projection (~47% of full-game naive; Ridge will learn true ratio)
    feat_h1["proj_h1_naive"] = (feat_h1["proj_total_naive"] * 0.47).round(2)

    # Rolling H1 league average (same blending logic as full-game)
    feat_h1["date"] = pd.to_datetime(feat_h1["date"])
    feat_h1 = feat_h1.sort_values(["season", "date"]).reset_index(drop=True)
    feat_h1["rolling_h1_league_avg"] = _rolling_h1_league_avg(feat_h1)

    # Sanity check
    for season in feat_h1["season"].unique():
        sg = feat_h1[feat_h1["season"] == season]
        logger.info(
            f"  {season}: {len(sg)} games | "
            f"H1 avg={sg['actual_h1_total'].mean():.1f} | "
            f"roll_avg range={sg['rolling_h1_league_avg'].min():.1f}–{sg['rolling_h1_league_avg'].max():.1f}"
        )

    feat_h1.to_parquet(H1_FEATURES_PATH, index=False)
    logger.info(f"H1 features saved: {len(feat_h1)} rows → {H1_FEATURES_PATH}")
    return feat_h1


if __name__ == "__main__":
    build_h1_features()
    print("\nH1 features built successfully.")
