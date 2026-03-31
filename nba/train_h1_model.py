#!/usr/bin/env python3
"""
Phase 6 — Ridge regression model for NBA first-half totals.

Architecture: identical to train_model.py (Phase 3) except:
  • Target: actual_h1_total  (not actual_total)
  • Input:  h1_features.parquet (not features.parquet)
  • Output: h1_ridge_model.pkl  (not ridge_model.pkl)

Feature set: same Pass 1 FEATURE_COLS as the full-game model.
The full-game rolling features capture team quality/style which manifests
equally in first halves. Ridge will learn H1-appropriate coefficient scales
(expect ~0.5× the full-game intercept, same feature directions).

Structural differences from full-game that Ridge will implicitly absorb:
  • No end-of-game fouling in H1 → FT rate less influential
  • H1 avg total historically ~108-112 pts vs ~227 full game
  • Pace slightly higher early — captured by same pace feature

H1-specific structural improvements (e.g. H1-pace rolling avg, lineup data)
are Phase 7+ work; this is the clean baseline.
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
    H1_FEATURES_PATH,
    RIDGE_ALPHA,
    TRAINING_SEASONS,
    VALIDATION_SEASON,
)

logger = logging.getLogger(__name__)

NBA_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(NBA_DIR, "data", "h1_ridge_model.pkl")
PRED_PATH  = os.path.join(NBA_DIR, "data", "h1_predictions.parquet")

# Same feature columns as the full-game Pass 1 model.
FEATURE_COLS = [
    "home_ortg", "away_ortg",
    "home_drtg", "away_drtg",
    "home_pace", "away_pace",
    "b2b_flag_away",
    "home_ortg_trend", "away_ortg_trend",
    "home_pace_trend", "away_pace_trend",
    "home_3pa_rate", "away_3pa_rate",
    "home_ft_rate",  "away_ft_rate",
]

TARGET = "actual_h1_total"


def load_features() -> pd.DataFrame:
    if not os.path.exists(H1_FEATURES_PATH):
        raise FileNotFoundError(
            f"h1_features.parquet not found at {H1_FEATURES_PATH}. "
            "Run: python nba/build_h1_features.py"
        )
    feat = pd.read_parquet(H1_FEATURES_PATH)
    logger.info(f"Loaded {len(feat)} rows from h1_features.parquet")
    return feat


def split_data(feat: pd.DataFrame):
    train = feat[feat["season"].isin(TRAINING_SEASONS)].copy()
    val   = feat[feat["season"] == VALIDATION_SEASON].copy()
    logger.info(f"Train: {len(train)} games ({TRAINING_SEASONS})")
    logger.info(f"Val  : {len(val)} games ({VALIDATION_SEASON})")
    return train, val


def train(train_df: pd.DataFrame):
    X = train_df[FEATURE_COLS].values
    y = train_df[TARGET].values

    scaler = StandardScaler()
    X_sc   = scaler.fit_transform(X)

    alphas = np.logspace(-1, 3, 50)
    model  = RidgeCV(alphas=alphas, cv=5, scoring="neg_mean_absolute_error")
    model.fit(X_sc, y)

    logger.info(f"RidgeCV selected alpha = {model.alpha_:.4f}  (config default = {RIDGE_ALPHA})")
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
    raw_coefs = model.coef_ / scaler.scale_
    intercept = model.intercept_ - np.dot(raw_coefs, scaler.mean_)

    print(f"\n{'Feature':<22} {'coef (raw units)':>18}  {'direction':>10}")
    print("-" * 56)
    pairs = sorted(zip(FEATURE_COLS, raw_coefs), key=lambda x: abs(x[1]), reverse=True)
    for name, c in pairs:
        direction = "↑ more pts" if c > 0 else "↓ fewer pts"
        print(f"   {name:<20} {c:>+18.4f}  {direction}")
    print(f"\n   Intercept (raw space): {intercept:.2f}")


def show_tail_mae(val: pd.DataFrame, pred: np.ndarray) -> None:
    v = val.copy()
    v["pred_h1"] = pred
    v["err"]     = v["pred_h1"] - v[TARGET]
    v["actual_q"] = pd.qcut(v[TARGET], q=5,
                             labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"])

    print(f"\n{'Quintile':<12} {'n':>5} {'act_mean':>9} {'pred_mean':>10} {'MAE':>8} {'Bias':>9}")
    print("-" * 60)
    for q in ["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"]:
        sub = v[v["actual_q"] == q]
        flag = "  ⚠ TAIL" if q in ("Q1(low)", "Q5(high)") else ""
        print(f"   {str(q):<12} {len(sub):>5} {sub[TARGET].mean():>9.2f} "
              f"{sub['pred_h1'].mean():>10.2f} {sub['err'].abs().mean():>8.2f} "
              f"{sub['err'].mean():>+9.2f}{flag}")


def main():
    feat = load_features()
    train_df, val_df = split_data(feat)

    for col in FEATURE_COLS + [TARGET]:
        n_null = feat[col].isna().sum()
        if n_null:
            raise ValueError(f"Null values in '{col}': {n_null} — fix h1 features first")

    print("\n" + "═" * 65)
    print("  PHASE 6 — H1 RIDGE REGRESSION MODEL")
    print("═" * 65)

    model, scaler = train(train_df)

    # Training residual sigma — used by simulation layer
    X_tr   = scaler.transform(train_df[FEATURE_COLS].values)
    resid  = train_df[TARGET].values - model.predict(X_tr)
    h1_sigma = float(np.std(resid))
    logger.info(f"H1 training residual σ = {h1_sigma:.4f} pts")

    print(f"\n   H1 training residual σ = {h1_sigma:.2f} pts  "
          f"(vs full-game σ = 18.62 pts)")
    print(f"\n📈 Model performance:")
    train_pred = evaluate(model, scaler, train_df, "TRAIN")
    val_pred   = evaluate(model, scaler, val_df,   "VALIDATION")

    train_mae = np.abs(train_pred - train_df[TARGET].values).mean()
    val_mae   = np.abs(val_pred   - val_df[TARGET].values).mean()
    gap = val_mae - train_mae
    if gap > 0.3:
        print(f"\n   ⚠  Val MAE {gap:.2f} pts worse than train — possible overfitting")
    else:
        print(f"\n   ✓  Train/val MAE gap = {gap:+.2f} pts (acceptable)")

    pred_vals = val_pred
    print(f"\n   Predicted H1 range (val): min={pred_vals.min():.1f}  max={pred_vals.max():.1f}  "
          f"σ={pred_vals.std():.1f}")
    print(f"   Actual H1 range   (val): min={val_df[TARGET].min():.1f}  max={val_df[TARGET].max():.1f}  "
          f"σ={val_df[TARGET].std():.1f}")

    print("\n📊 Feature coefficients:")
    show_coefficients(model, scaler)

    print("\n📊 Tail compression (H1 actual-total quintiles):")
    show_tail_mae(val_df, val_pred)

    # Save model + scaler + h1_sigma for simulation
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({
            "model":    model,
            "scaler":   scaler,
            "features": FEATURE_COLS,
            "h1_sigma": h1_sigma,
        }, f)
    print(f"\n💾 H1 model saved → {MODEL_PATH}")

    # Save predictions
    train_df = train_df.copy(); train_df["pred_h1"] = train_pred
    val_df   = val_df.copy();   val_df["pred_h1"]   = val_pred
    preds = pd.concat([train_df, val_df], ignore_index=True)
    preds["h1_error"] = preds["pred_h1"] - preds[TARGET]
    preds.to_parquet(PRED_PATH, index=False)
    print(f"💾 H1 predictions saved → {PRED_PATH}")

    print("\n" + "═" * 65)
    print("  PHASE 6 TRAINING COMPLETE")
    print("═" * 65 + "\n")


if __name__ == "__main__":
    main()
