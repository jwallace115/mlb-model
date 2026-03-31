#!/usr/bin/env python3
"""
Phase 3 — Ridge regression model for NBA game totals.

Training seasons : 2022-23, 2023-24  (TRAINING_SEASONS in config)
Validation season: 2024-25           (VALIDATION_SEASON in config)

Features
--------
  Efficiency : home_ortg, away_ortg, home_drtg, away_drtg, home_pace, away_pace
  Rest       : days_rest_home, days_rest_away, b2b_flag_home, b2b_flag_away
  Schedule   : games_l7_home, games_l7_away

Target: actual_total

Outputs
-------
  • Train MAE, validation MAE, bias
  • Feature coefficients (sorted by |coef|)
  • Segment-level validation error (pace quintile, projected-total quintile)
  • Saves trained model to nba/data/ridge_model.pkl
  • Saves predictions to nba/data/predictions.parquet
"""

import logging
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

from nba.config import (
    FEATURES_PATH,
    TRAINING_SEASONS,
    VALIDATION_SEASON,
    RIDGE_ALPHA,
)

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ridge_model.pkl")
PRED_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "predictions.parquet")

FEATURE_COLS = [
    # Core efficiency (15-game rolling, location-split with fallback)
    "home_ortg", "away_ortg",
    "home_drtg", "away_drtg",
    "home_pace", "away_pace",
    # Schedule (away b2b only — home b2b and rest features not supported by grouped data;
    # interaction terms dropped due to main-effect collinearity sign reversal)
    "b2b_flag_away",
    # Trend features (5-game vs 15-game delta, orthogonal to level features)
    "home_ortg_trend", "away_ortg_trend",
    "home_pace_trend", "away_pace_trend",
    # Pass 1 — Style features (rolling 15-game) — ACTIVE
    # These are the dominant coefficients in the model: 3PA rate and FT rate
    # capture per-possession scoring opportunities orthogonally to pace level.
    "home_3pa_rate", "away_3pa_rate",
    "home_ft_rate",  "away_ft_rate",
    #
    # Pass 2 — Pace volatility (rolling 10-game std) — DROPPED
    # Reason: RidgeCV shrunk both to exactly 0.0000. Rolling std of pace
    # encodes unpredictability, not directional level bias, so it carries
    # zero marginal signal for a point-total regression.
    # "home_pace_vol", "away_pace_vol",
    #
    # Pass 3 — Possession efficiency (rolling 15-game) — DROPPED
    # Reason: tov_rate and dreb_rate have basketball-logical signs (-47/-36
    # and -41/-25 respectively) but are heavily collinear with the existing
    # ORtg/DRtg/pace set. RidgeCV alpha jumped 494x (0.10 → 49.4) as Ridge
    # fought multicollinearity. OOS (2025-26) degraded on all four key metrics:
    # MAE +0.05, bias +0.73, directional HR -1.2%, Brier SS -0.006.
    # These features belong in a structural possession-count model (Phase 5+),
    # not as additional Ridge inputs.
    # "home_tov_rate", "away_tov_rate",
    # "home_dreb_rate", "away_dreb_rate",
]

TARGET = "actual_total"


def load_features() -> pd.DataFrame:
    if not os.path.exists(FEATURES_PATH):
        raise FileNotFoundError(
            f"features.parquet not found at {FEATURES_PATH}. "
            "Run: python nba/build_features.py"
        )
    feat = pd.read_parquet(FEATURES_PATH)
    logger.info(f"Loaded {len(feat)} rows from features.parquet")
    return feat


def split_data(feat: pd.DataFrame):
    train = feat[feat["season"].isin(TRAINING_SEASONS)].copy()
    val   = feat[feat["season"] == VALIDATION_SEASON].copy()
    logger.info(f"Train: {len(train)} games ({TRAINING_SEASONS})")
    logger.info(f"Val  : {len(val)} games ({VALIDATION_SEASON})")
    return train, val


def train(train: pd.DataFrame):
    X = train[FEATURE_COLS].values
    y = train[TARGET].values

    scaler = StandardScaler()
    X_sc   = scaler.fit_transform(X)

    # RidgeCV searches a log-spaced grid; RIDGE_ALPHA from config is the default
    # but we let CV pick the best from a wider range so Phase 3 is self-tuning.
    alphas = np.logspace(-1, 3, 50)   # 0.1 … 1000
    model  = RidgeCV(alphas=alphas, cv=5, scoring="neg_mean_absolute_error")
    model.fit(X_sc, y)

    logger.info(f"RidgeCV selected alpha = {model.alpha_:.4f} (config default = {RIDGE_ALPHA})")
    return model, scaler


def evaluate(model, scaler, df: pd.DataFrame, label: str) -> np.ndarray:
    X    = scaler.transform(df[FEATURE_COLS].values)
    y    = df[TARGET].values
    pred = model.predict(X)
    mae  = np.abs(pred - y).mean()
    bias = (pred - y).mean()
    print(f"   {label:<12}  MAE = {mae:.2f} pts   Bias = {bias:+.2f} pts   (n={len(y)})")
    return pred


def show_coefficients(model, scaler) -> None:
    # Convert scaled coefficients to original-space units for interpretability
    raw_coefs  = model.coef_ / scaler.scale_
    intercept  = model.intercept_ - np.dot(raw_coefs, scaler.mean_)

    print(f"\n{'Feature':<22} {'coef (raw units)':>18}  {'direction':>10}")
    print("-" * 56)
    pairs = sorted(zip(FEATURE_COLS, raw_coefs), key=lambda x: abs(x[1]), reverse=True)
    for name, c in pairs:
        direction = "↑ more pts" if c > 0 else "↓ fewer pts"
        print(f"   {name:<20} {c:>+18.4f}  {direction}")
    print(f"\n   Intercept (raw space): {intercept:.2f}")


def show_segment_errors(val: pd.DataFrame, pred: np.ndarray) -> None:
    v = val.copy()
    v["pred"] = pred
    v["err"]  = v["pred"] - v[TARGET]

    print("\n📊 Validation error by avg_pace quintile:")
    v["pace_q"] = pd.qcut(
        (v["home_pace"] + v["away_pace"]) / 2, q=5,
        labels=["Q1(slow)", "Q2", "Q3", "Q4", "Q5(fast)"]
    )
    pace_tbl = (
        v.groupby("pace_q", observed=True)["err"]
        .agg(n="count", mae=lambda x: x.abs().mean(), bias="mean")
    )
    print(f"{'Quintile':<12} {'n':>5} {'MAE':>8} {'Bias':>8}")
    for q, row in pace_tbl.iterrows():
        print(f"   {str(q):<12} {row['n']:>5} {row['mae']:>8.2f} {row['bias']:>+8.2f}")

    print("\n📊 Validation error by proj_total_naive quintile:")
    v["proj_q"] = pd.qcut(
        v["proj_total_naive"], q=5,
        labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"]
    )
    proj_tbl = (
        v.groupby("proj_q", observed=True)["err"]
        .agg(n="count", mae=lambda x: x.abs().mean(), bias="mean")
    )
    print(f"{'Quintile':<12} {'n':>5} {'MAE':>8} {'Bias':>8}")
    for q, row in proj_tbl.iterrows():
        print(f"   {str(q):<12} {row['n']:>5} {row['mae']:>8.2f} {row['bias']:>+8.2f}")


def main():
    feat = load_features()
    train_df, val_df = split_data(feat)

    # Verify no nulls in feature columns
    for col in FEATURE_COLS + [TARGET]:
        n_null = feat[col].isna().sum()
        if n_null:
            raise ValueError(f"Null values in '{col}': {n_null} — fix features.py first")

    print("\n" + "═" * 65)
    print("  PHASE 3 — RIDGE REGRESSION MODEL")
    print("═" * 65)

    model, scaler = train(train_df)

    print(f"\n📈 Model performance:")
    train_pred = evaluate(model, scaler, train_df, "TRAIN")
    val_pred   = evaluate(model, scaler, val_df,   "VALIDATION")

    train_mae = np.abs(train_pred - train_df[TARGET].values).mean()
    val_mae   = np.abs(val_pred   - val_df[TARGET].values).mean()
    gap = val_mae - train_mae
    if gap > 0.3:
        print(f"\n   ⚠  Validation MAE is {gap:.2f} pts worse than train — possible overfitting")
    else:
        print(f"\n   ✓  Train/val MAE gap = {gap:+.2f} pts (acceptable)")

    print("\n📊 Feature coefficients:")
    show_coefficients(model, scaler)

    show_segment_errors(val_df, val_pred)

    # Save model + scaler
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "scaler": scaler, "features": FEATURE_COLS}, f)
    print(f"\n💾 Model saved → {MODEL_PATH}")

    # Save predictions
    train_df = train_df.copy()
    val_df   = val_df.copy()
    train_df["pred_total"] = train_pred
    val_df["pred_total"]   = val_pred
    preds = pd.concat([train_df, val_df], ignore_index=True)
    preds["error"] = preds["pred_total"] - preds[TARGET]
    preds.to_parquet(PRED_PATH, index=False)
    print(f"💾 Predictions saved → {PRED_PATH}")

    print("\n" + "═" * 65)
    print("  PHASE 3 COMPLETE — proceed to Phase 4 backtest")
    print("═" * 65 + "\n")


if __name__ == "__main__":
    main()
