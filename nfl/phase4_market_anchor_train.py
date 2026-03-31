#!/usr/bin/env python3
"""
NFL Phase 4: Market-anchor model.

Predicts: market_residual = actual_total - closing_total_line
Architecture: Ridge regression on Phase 1 features → predicted residual
Projection: reconstructed = closing_line + predicted_residual
Simulation: Normal(reconstructed, sigma)

Does NOT overwrite Phase 1 model artifacts.
"""

import json
import logging
import os
import pickle

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

FEATURE_PATH = os.path.join(DATA_DIR, "nfl_feature_table.parquet")
ANCHOR_OUT_PATH = os.path.join(DATA_DIR, "nfl_anchor_outputs.parquet")
PHASE1_OUT_PATH = os.path.join(DATA_DIR, "nfl_model_outputs.parquet")

FEATURE_COLS = [
    "home_pts_scored_rolling", "home_pts_allowed_rolling",
    "away_pts_scored_rolling", "away_pts_allowed_rolling",
    "is_dome_f", "wind_for_feature", "temp_for_feature",
    "wind_bucket", "neutral_site_f",
    "home_rest_days", "away_rest_days", "rest_advantage",
    "is_short_week_home", "is_short_week_away",
]

ALPHA_GRID = [0.1, 1.0, 10.0, 50.0, 100.0, 300.0, 1000.0, 3000.0]

TIER_HIGH = 0.10
TIER_MEDIUM = 0.07
TIER_LOW = 0.05

SEP = "=" * 60


def vig_remove(over_odds, under_odds):
    def imp(am):
        if pd.isna(am): return np.nan
        return abs(am) / (abs(am) + 100) if am < 0 else 100 / (am + 100)
    po = imp(over_odds); pu = imp(under_odds)
    if np.isnan(po) or np.isnan(pu) or (po + pu) <= 0: return np.nan
    return po / (po + pu)


def get_tier(edge):
    if edge >= TIER_HIGH: return "HIGH"
    if edge >= TIER_MEDIUM: return "MEDIUM"
    if edge >= TIER_LOW: return "LOW"
    return None


def roi_at_110(w, l):
    n = w + l
    return (w * (100 / 110) - l) / n * 100 if n > 0 else None


def evaluate_oos(df, label):
    """Evaluate edge-based OOS performance."""
    df = df.copy()
    df["edge_abs"] = df["edge"].abs()
    df["actual_over"] = (df["total_points"] > df["closing_total_line"]).astype(int)
    df["push"] = (df["total_points"] == df["closing_total_line"]).astype(int)
    df["signal"] = df["edge"].apply(lambda e: "OVER" if e >= 0.05 else ("UNDER" if e <= -0.05 else None))

    sigs = df[df["edge_abs"] >= 0.05].copy()
    sigs_np = sigs[sigs["push"] == 0].copy()
    sigs_np["win"] = (
        ((sigs_np["signal"] == "OVER") & (sigs_np["actual_over"] == 1)) |
        ((sigs_np["signal"] == "UNDER") & (sigs_np["actual_over"] == 0))
    ).astype(int)

    w = int(sigs_np["win"].sum())
    l = len(sigs_np) - w
    hit = w / (w + l) if (w + l) > 0 else 0
    roi = roi_at_110(w, l)

    bh = []
    bucket_strs = []
    for lo, hi in [(0.05, 0.07), (0.07, 0.10), (0.10, 1.0)]:
        bm = (sigs_np["edge_abs"] >= lo) & (sigs_np["edge_abs"] < hi)
        bs = sigs_np[bm]
        if len(bs) >= 5:
            bw = int(bs["win"].sum()); bl = len(bs) - bw
            bhit = bw / (bw + bl) if (bw + bl) > 0 else 0
            bh.append(bhit)
            bucket_strs.append(f"    {lo:.2f}-{hi:.2f}: N={len(bs):>3}, hit={bhit:.1%}, ROI={roi_at_110(bw,bl):+.1f}%")
        elif len(bs) > 0:
            bucket_strs.append(f"    {lo:.2f}-{hi:.2f}: N={len(bs):>3} (too few)")

    mono = len(bh) < 2 or all(bh[i] <= bh[i + 1] + 0.05 for i in range(len(bh) - 1))
    g1 = hit >= 0.525

    tiers = {}
    for tier in ["LOW", "MEDIUM", "HIGH"]:
        if tier == "LOW": tm = (sigs["edge_abs"] >= 0.05) & (sigs["edge_abs"] < 0.07)
        elif tier == "MEDIUM": tm = (sigs["edge_abs"] >= 0.07) & (sigs["edge_abs"] < 0.10)
        else: tm = sigs["edge_abs"] >= 0.10
        tiers[tier] = int(tm.sum())

    print(f"\n  {label}:")
    print(f"    N signals:  {len(sigs)}")
    print(f"    Hit rate:   {hit:.1%} {'✅' if g1 else '❌'}")
    print(f"    ROI:        {roi:+.1f}%")
    print(f"    Monotonic:  {'PASS ✅' if mono else 'FAIL ❌'}")
    print(f"    Tiers: H={tiers['HIGH']} M={tiers['MEDIUM']} L={tiers['LOW']}")
    for bs in bucket_strs:
        print(bs)

    return {"n": len(sigs), "hit": hit, "roi": roi, "mono": mono, "g1": g1, "tiers": tiers}


def main():
    ft = pd.read_parquet(FEATURE_PATH)
    reg = ft[(ft["game_type"] == "regular") & ft["closing_total_line"].notna()].copy()
    logger.info(f"Regular season with lines: {len(reg)}")

    # Residual target
    reg["residual_target"] = reg["total_points"] - reg["closing_total_line"]

    # Splits
    train = reg[reg["season"].between(2020, 2022)].copy()
    val = reg[reg["season"] == 2023].copy()
    oos = reg[reg["season"] == 2024].copy()

    print(f"\n{SEP}")
    print(f"  NFL PHASE 4 — MARKET-ANCHOR MODEL")
    print(SEP)
    print(f"  Train: {len(train)} (2020-2022)")
    print(f"  Validate: {len(val)} (2023)")
    print(f"  OOS: {len(oos)} (2024)")

    # Impute
    impute_vals = {}
    for col in FEATURE_COLS:
        m = float(train[col].mean()) if train[col].notna().any() else 0.0
        impute_vals[col] = m

    for df in [train, val, oos, reg]:
        for col, v in impute_vals.items():
            if col in df.columns:
                df[col] = df[col].fillna(v)

    # Scale
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[FEATURE_COLS].values)
    X_val = scaler.transform(val[FEATURE_COLS].values)
    X_oos = scaler.transform(oos[FEATURE_COLS].values)

    y_train = train["residual_target"].values
    y_val = val["residual_target"].values

    # Alpha search on residual target
    print(f"\n  Alpha grid search (residual target):")
    best_alpha = None
    best_mae = float("inf")
    for alpha in ALPHA_GRID:
        mdl = Ridge(alpha=alpha)
        mdl.fit(X_train, y_train)
        mae = mean_absolute_error(y_val, mdl.predict(X_val))
        mark = ""
        if mae < best_mae:
            best_mae = mae
            best_alpha = alpha
            mark = " ← selected"
        print(f"    alpha={alpha:<8} validate MAE={mae:.4f}{mark}")

    ridge = Ridge(alpha=best_alpha)
    ridge.fit(X_train, y_train)

    # Metrics on residual
    train_pred_res = ridge.predict(X_train)
    val_pred_res = ridge.predict(X_val)
    oos_pred_res = ridge.predict(X_oos)

    print(f"\n  Residual model metrics:")
    print(f"    Train:    MAE={mean_absolute_error(y_train, train_pred_res):.2f}  "
          f"RMSE={np.sqrt(mean_squared_error(y_train, train_pred_res)):.2f}")
    print(f"    Validate: MAE={mean_absolute_error(y_val, val_pred_res):.2f}  "
          f"RMSE={np.sqrt(mean_squared_error(y_val, val_pred_res)):.2f}")
    print(f"    Mean pred residual: {train_pred_res.mean():+.3f} (should be ~0)")

    # Feature coefficients
    print(f"\n  Feature coefficients (residual model):")
    coefs = pd.Series(ridge.coef_, index=FEATURE_COLS)
    for feat in FEATURE_COLS:
        print(f"    {feat:<35} {coefs[feat]:>+8.4f}")

    # Reconstructed projection
    train["recon"] = train["closing_total_line"].values + train_pred_res
    val["recon"] = val["closing_total_line"].values + val_pred_res
    oos["recon"] = oos["closing_total_line"].values + oos_pred_res

    # Full-scale sigma (actual_total vs reconstructed)
    full_resid = train["total_points"].values - train["recon"].values
    sigma = float(np.std(full_resid, ddof=1))

    print(f"\n  Sigma (actual vs reconstructed): {sigma:.2f}")
    print(f"    Range check: {'✅' if 8 <= sigma <= 18 else '⚠️'} (expect 10-14)")

    # Bias check
    recon_mean = oos["recon"].mean()
    actual_mean = oos["total_points"].mean()
    print(f"    OOS bias: recon_mean={recon_mean:.1f}, actual_mean={actual_mean:.1f}, "
          f"gap={recon_mean - actual_mean:+.1f}")

    # ── Simulation + edges ──────────────────────────────────────────
    oos["model_p_over_anchor"] = [
        float(1 - stats.norm.cdf(cl, loc=rc, scale=sigma))
        for rc, cl in zip(oos["recon"], oos["closing_total_line"])
    ]
    oos["model_p_under_anchor"] = 1 - oos["model_p_over_anchor"]
    oos["market_implied_p_over"] = oos.apply(
        lambda r: vig_remove(r["over_price"], r["under_price"]), axis=1
    )
    oos["edge"] = oos["model_p_over_anchor"] - oos["market_implied_p_over"]

    # ── Side-by-side OOS ──────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  SIDE-BY-SIDE OOS EVALUATION (2024)")
    print(SEP)

    # Phase 1 baseline
    p1 = pd.read_parquet(PHASE1_OUT_PATH)
    p1_oos = p1[p1["split"] == "oos"].copy()
    p1_oos["edge"] = p1_oos["model_p_over"] - p1_oos["market_implied_p_over"]
    r1 = evaluate_oos(p1_oos, "Phase 1 Baseline")

    # Phase 4 anchor
    r4 = evaluate_oos(oos, "Phase 4 Market-Anchor")

    # Residual analysis
    print(f"\n  PREDICTED RESIDUAL ANALYSIS (OOS):")
    print(f"    Avg predicted residual:    {oos_pred_res.mean():+.3f}")
    print(f"    Avg |predicted residual|:  {np.abs(oos_pred_res).mean():.3f}")
    actual_res = oos["residual_target"].values
    corr_res = np.corrcoef(oos_pred_res, actual_res)[0, 1]
    print(f"    Corr(predicted, actual):   {corr_res:+.3f}")

    # ── Verdict ──────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  VERDICT")
    print(SEP)

    anchor_passes = r4["g1"] and r4["mono"]
    baseline_passes = r1["g1"] and r1["mono"]

    if anchor_passes:
        print(f"  Phase 4 Market-Anchor PASSES all gates ✅")
        print(f"  Deployment: READY (set nfl_model_mode = 'market_anchor')")
    elif r4["hit"] > r1["hit"]:
        print(f"  Phase 4 improves hit rate ({r1['hit']:.1%} → {r4['hit']:.1%})")
        print(f"  But still below 52.5% gate")
        print(f"  Deployment: excluded_oos_gate")
    elif r4["mono"] and not r1["mono"]:
        print(f"  Phase 4 improves monotonicity but not hit rate")
        print(f"  Deployment: excluded_oos_gate")
    else:
        print(f"  Phase 4 does not improve over Phase 1")
        print(f"  Deployment: excluded_oos_gate (Phase 1 baseline retained)")

    print()

    # Save model artifacts
    with open(os.path.join(MODELS_DIR, "market_anchor_model.pkl"), "wb") as f:
        pickle.dump(ridge, f)
    with open(os.path.join(MODELS_DIR, "market_anchor_scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODELS_DIR, "market_anchor_meta.json"), "w") as f:
        json.dump({
            "alpha": best_alpha,
            "sigma": sigma,
            "impute_vals": impute_vals,
            "features": FEATURE_COLS,
            "target": "actual_total - closing_total_line",
            "architecture": "market_anchor_ridge",
        }, f, indent=2)

    # Save outputs
    out = oos[["game_id", "date", "season", "week", "home_team", "away_team",
               "total_points", "closing_total_line", "recon",
               "model_p_over_anchor", "model_p_under_anchor",
               "market_implied_p_over", "edge"]].copy()
    out.columns = [c.replace("recon", "model_total_anchor") for c in out.columns]
    out.to_parquet(ANCHOR_OUT_PATH, index=False)
    logger.info(f"Saved anchor outputs: {ANCHOR_OUT_PATH}")


if __name__ == "__main__":
    main()
