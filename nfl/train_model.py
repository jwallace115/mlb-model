#!/usr/bin/env python3
"""
NFL Phase 1: Ridge baseline model, Normal simulation, market architecture, OOS validation.

Train: 2020-2022 regular season
Validate: 2023 regular season
OOS: 2024 regular season

Output:
  nfl/models/ridge_model.pkl
  nfl/models/scaler.pkl
  nfl/data/nfl_model_outputs.parquet
  nfl/data/nfl_decisions.parquet
"""

import io
import json
import logging
import os
import pickle
import sys

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NFL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(NFL_DIR, "data")
MODELS_DIR = os.path.join(NFL_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURE_PATH = os.path.join(DATA_DIR, "nfl_feature_table.parquet")
MODEL_OUT_PATH = os.path.join(DATA_DIR, "nfl_model_outputs.parquet")
DECISIONS_PATH = os.path.join(DATA_DIR, "nfl_decisions.parquet")

FEATURE_COLS = [
    "home_pts_scored_rolling", "home_pts_allowed_rolling",
    "away_pts_scored_rolling", "away_pts_allowed_rolling",
    "is_dome_f", "wind_for_feature", "temp_for_feature",
    "wind_bucket", "neutral_site_f",
    "home_rest_days", "away_rest_days", "rest_advantage",
    "is_short_week_home", "is_short_week_away",
]

ALPHA_GRID = [0.1, 1.0, 10.0, 50.0, 100.0, 300.0, 1000.0]

# Signal tiers
TIER_HIGH = 0.10
TIER_MEDIUM = 0.07
TIER_LOW = 0.05

SEP = "=" * 60


def vig_remove(over_odds: float, under_odds: float) -> float:
    """Vig-remove American odds to fair over probability."""
    def implied(american):
        if american is None or np.isnan(american):
            return np.nan
        if american < 0:
            return abs(american) / (abs(american) + 100)
        else:
            return 100 / (american + 100)

    p_over = implied(over_odds)
    p_under = implied(under_odds)
    if np.isnan(p_over) or np.isnan(p_under) or (p_over + p_under) <= 0:
        return np.nan
    return p_over / (p_over + p_under)


def get_tier(edge: float) -> str | None:
    if edge >= TIER_HIGH:
        return "HIGH"
    elif edge >= TIER_MEDIUM:
        return "MEDIUM"
    elif edge >= TIER_LOW:
        return "LOW"
    return None


def roi_at_110(wins, losses):
    n = wins + losses
    if n == 0:
        return None
    return (wins * (100 / 110) - losses) / n * 100


def main():
    ft = pd.read_parquet(FEATURE_PATH)
    reg = ft[ft["game_type"] == "regular"].copy()
    logger.info(f"Regular season: {len(reg)} rows")

    # Splits
    train = reg[reg["season"].between(2020, 2022)].copy()
    val = reg[reg["season"] == 2023].copy()
    oos = reg[reg["season"] == 2024].copy()

    print(f"\n{SEP}")
    print(f"  NFL PHASE 1 MODEL TRAINING")
    print(SEP)
    print(f"  Train: {len(train)} (2020-2022)")
    print(f"  Validate: {len(val)} (2023)")
    print(f"  OOS: {len(oos)} (2024)")

    # Impute NaN in features (week 1 rolling = NaN → fill with season mean)
    impute_vals = {}
    for col in FEATURE_COLS:
        if col in train.columns:
            m = float(train[col].mean()) if train[col].notna().any() else 0.0
            impute_vals[col] = m

    for df in [train, val, oos, reg]:
        for col, v in impute_vals.items():
            if col in df.columns:
                df[col] = df[col].fillna(v)

    # Target
    y_train = train["total_points"].values
    y_val = val["total_points"].values
    y_oos = oos["total_points"].values

    X_train = train[FEATURE_COLS].values
    X_val = val[FEATURE_COLS].values
    X_oos = oos[FEATURE_COLS].values

    # Scale
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_oos_s = scaler.transform(X_oos)

    # Ridge alpha search
    print(f"\n  Alpha grid search:")
    best_alpha = None
    best_mae = float("inf")
    for alpha in ALPHA_GRID:
        mdl = Ridge(alpha=alpha)
        mdl.fit(X_train_s, y_train)
        mae = mean_absolute_error(y_val, mdl.predict(X_val_s))
        mark = ""
        if mae < best_mae:
            best_mae = mae
            best_alpha = alpha
            mark = " ← selected"
        print(f"    alpha={alpha:<8} validate MAE={mae:.2f}{mark}")

    ridge = Ridge(alpha=best_alpha)
    ridge.fit(X_train_s, y_train)

    # Metrics
    train_pred = ridge.predict(X_train_s)
    val_pred = ridge.predict(X_val_s)
    oos_pred = ridge.predict(X_oos_s)

    train_mae = mean_absolute_error(y_train, train_pred)
    val_mae = mean_absolute_error(y_val, val_pred)
    oos_mae = mean_absolute_error(y_oos, oos_pred)
    train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))
    val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))
    oos_rmse = np.sqrt(mean_squared_error(y_oos, oos_pred))

    print(f"\n  Model performance:")
    print(f"    Train:    MAE={train_mae:.2f}  RMSE={train_rmse:.2f}")
    print(f"    Validate: MAE={val_mae:.2f}  RMSE={val_rmse:.2f}")
    print(f"    OOS:      MAE={oos_mae:.2f}  RMSE={oos_rmse:.2f}")

    gap = abs(train_mae - val_mae)
    print(f"    Train/Val MAE gap: {gap:.2f} {'⚠️ FLAG' if gap > 1.5 else '✅'}")

    # Bias check
    train_bias = train_pred.mean() - y_train.mean()
    oos_bias = oos_pred.mean() - y_oos.mean()
    print(f"    Train bias: {train_bias:+.2f}")
    print(f"    OOS bias:   {oos_bias:+.2f} {'⚠️ FLAG' if abs(oos_bias) > 1.5 else '✅'}")

    # Feature coefficients
    print(f"\n  Feature coefficients:")
    coefs = pd.Series(ridge.coef_, index=FEATURE_COLS)
    for feat in FEATURE_COLS:
        print(f"    {feat:<35} {coefs[feat]:>+8.3f}")

    # Sanity checks
    print(f"\n  Coefficient sanity:")
    print(f"    wind_for_feature < 0: {coefs['wind_for_feature'] < 0} {'✅' if coefs['wind_for_feature'] < 0 else '⚠️'}")
    print(f"    is_dome_f >= 0:       {coefs['is_dome_f'] >= 0} {'✅' if coefs['is_dome_f'] >= 0 else '⚠️'}")
    print(f"    home_pts_scored > 0:  {coefs['home_pts_scored_rolling'] > 0} {'✅' if coefs['home_pts_scored_rolling'] > 0 else '⚠️'}")

    # Save model
    with open(os.path.join(MODELS_DIR, "ridge_model.pkl"), "wb") as f:
        pickle.dump(ridge, f)
    with open(os.path.join(MODELS_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODELS_DIR, "impute_vals.json"), "w") as f:
        json.dump(impute_vals, f)

    # ── Simulation layer ──────────────────────────────────────────────
    # Normal distribution: sigma from training residuals
    train_resid = y_train - train_pred
    sigma = float(np.std(train_resid, ddof=1))
    print(f"\n  Residual sigma: {sigma:.2f}")
    print(f"    Range check: {'✅' if 8 <= sigma <= 18 else '⚠️ FLAG'} (expect 10-14)")

    with open(os.path.join(MODELS_DIR, "sigma.json"), "w") as f:
        json.dump({"sigma": sigma}, f)

    # ── Build model outputs for all regular season ────────────────────
    X_all = reg[FEATURE_COLS].values
    X_all_s = scaler.transform(X_all)
    reg["model_total"] = ridge.predict(X_all_s)

    # Normal simulation
    reg["model_p_over"] = reg.apply(
        lambda r: float(1 - stats.norm.cdf(r["closing_total_line"], loc=r["model_total"], scale=sigma))
        if pd.notna(r["closing_total_line"]) else np.nan,
        axis=1,
    )
    reg["model_p_under"] = 1 - reg["model_p_over"]
    reg["residual_sigma"] = sigma

    # Market implied
    reg["market_implied_p_over"] = reg.apply(
        lambda r: vig_remove(r["over_price"], r["under_price"]), axis=1
    )

    # Edge
    reg["edge"] = reg["model_p_over"] - reg["market_implied_p_over"]

    # Signal side and tier
    reg["signal_side"] = reg["edge"].apply(
        lambda e: "OVER" if e >= TIER_LOW else ("UNDER" if e <= -TIER_LOW else None)
    )
    reg["edge_abs"] = reg["edge"].abs()
    reg["confidence_tier"] = reg["edge_abs"].apply(
        lambda e: get_tier(e) if e >= TIER_LOW else None
    )

    # Result vs closing line
    reg["result"] = reg.apply(
        lambda r: (
            "WIN" if (r["signal_side"] == "OVER" and r["total_points"] > r["closing_total_line"])
            else "WIN" if (r["signal_side"] == "UNDER" and r["total_points"] < r["closing_total_line"])
            else "PUSH" if r["total_points"] == r["closing_total_line"]
            else "LOSS"
        ) if r["signal_side"] is not None and pd.notna(r["closing_total_line"]) else None,
        axis=1,
    )

    # Split label
    reg["split"] = reg["season"].map({
        2019: "excluded", 2020: "train", 2021: "train", 2022: "train",
        2023: "validate", 2024: "oos",
    })

    # CLV fields (null for historical)
    reg["decision_line"] = None
    reg["decision_timestamp"] = None
    reg["decision_line_source"] = None
    reg["clv_raw"] = None
    reg["clv_directional"] = None

    # Save model outputs
    out_cols = [
        "game_id", "date", "season", "week", "game_type", "split",
        "home_team", "away_team", "home_score", "away_score", "total_points",
        "model_total", "model_p_over", "model_p_under", "residual_sigma",
        "closing_total_line", "market_implied_p_over",
        "edge", "signal_side", "confidence_tier", "result",
        "decision_line", "decision_timestamp", "decision_line_source",
        "clv_raw", "clv_directional", "market_snapshot_status",
        "line_source",
    ]

    model_out = reg[[c for c in out_cols if c in reg.columns]].copy()
    model_out.to_parquet(MODEL_OUT_PATH, index=False)
    logger.info(f"Model outputs: {MODEL_OUT_PATH}")

    # Decisions parquet (same as model outputs for Phase 1)
    model_out.to_parquet(DECISIONS_PATH, index=False)
    logger.info(f"Decisions: {DECISIONS_PATH}")

    # ── OOS Validation ────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  OOS VALIDATION (2024 regular season)")
    print(SEP)

    oos_out = model_out[model_out["split"] == "oos"].copy()
    oos_out["edge_abs"] = oos_out["edge"].abs()
    oos_with_lines = oos_out[oos_out["line_source"] != "unavailable"]

    print(f"  OOS rows: {len(oos_out)} ({len(oos_with_lines)} with lines)")

    for tier_name, min_edge in [("ALL (>=0.05)", 0.05), ("LOW (0.05-0.07)", None),
                                 ("MEDIUM (0.07-0.10)", None), ("HIGH (>=0.10)", None)]:
        if tier_name.startswith("ALL"):
            sigs = oos_with_lines[oos_with_lines["edge_abs"] >= min_edge]
        elif "LOW" in tier_name:
            sigs = oos_with_lines[oos_with_lines["confidence_tier"] == "LOW"]
        elif "MEDIUM" in tier_name:
            sigs = oos_with_lines[oos_with_lines["confidence_tier"] == "MEDIUM"]
        else:
            sigs = oos_with_lines[oos_with_lines["confidence_tier"] == "HIGH"]

        n = len(sigs)
        if n == 0:
            print(f"\n  {tier_name}: 0 signals")
            continue

        wins = (sigs["result"] == "WIN").sum()
        losses = (sigs["result"] == "LOSS").sum()
        pushes = (sigs["result"] == "PUSH").sum()
        hit = wins / (wins + losses) if (wins + losses) > 0 else 0
        roi = roi_at_110(wins, losses)

        print(f"\n  {tier_name}: N={n}, W={wins} L={losses} P={pushes}, "
              f"hit={hit:.1%}, ROI={roi:+.1f}%")

    # Edge buckets
    print(f"\n  Edge buckets:")
    buckets = [(0.05, 0.07), (0.07, 0.10), (0.10, 1.0)]
    bucket_hits = []
    for lo, hi in buckets:
        sigs = oos_with_lines[
            (oos_with_lines["edge_abs"] >= lo) & (oos_with_lines["edge_abs"] < hi)
        ]
        n = len(sigs)
        if n < 5:
            print(f"    {lo:.2f}-{hi:.2f}: N={n} (too few)")
            continue
        wins = (sigs["result"] == "WIN").sum()
        losses = (sigs["result"] == "LOSS").sum()
        hit = wins / (wins + losses) if (wins + losses) > 0 else 0
        roi = roi_at_110(wins, losses)
        print(f"    {lo:.2f}-{hi:.2f}: N={n:>3}, hit={hit:.1%}, ROI={roi:+.1f}%")
        bucket_hits.append(hit)

    # Monotonic check
    mono = len(bucket_hits) < 2 or all(
        bucket_hits[i] <= bucket_hits[i + 1] + 0.05
        for i in range(len(bucket_hits) - 1)
    )

    # OOS gates
    all_sigs = oos_with_lines[oos_with_lines["edge_abs"] >= 0.05]
    overall_hit = (all_sigs["result"] == "WIN").sum() / max(1, (
        (all_sigs["result"] == "WIN").sum() + (all_sigs["result"] == "LOSS").sum()))

    print(f"\n  OOS GATES:")
    g1 = overall_hit >= 0.525
    print(f"    Hit rate >= 52.5%: {overall_hit:.1%} → {'PASS ✅' if g1 else 'FAIL ❌'}")
    print(f"    Monotonic curve:   {'PASS ✅' if mono else 'FAIL ❌'}")

    verdict = "PASS" if g1 and mono else "FAIL"
    print(f"\n  VERDICT: {verdict}")
    print()


if __name__ == "__main__":
    main()
