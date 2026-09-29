#!/usr/bin/env python3
"""
Fit expected-goals logistic regression on 2021-22 + 2022-23 shots ONLY, then freeze.

Features: distance, angle, shot_type (one-hot), rebound, rush, strength_group (even/PP/PK/3v3).
Output: nhl/data/sim/xg_v1.json with coefficients, feature defs, training table sha256.

Reports calibration by decile on fit seasons and 2023-24 (OOS).
"""
import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
OUT_PATH = ROOT / "nhl" / "data" / "sim" / "xg_v1.json"

FIT_SEASONS = [2021, 2022]  # 2021-22 + 2022-23
VALIDATE_SEASON = 2023      # 2023-24
REPORT_SEASONS = [2021, 2022, 2023, 2024, 2025]

STRENGTH_GROUPS = {
    "5v5": "even", "4v4": "even", "3v3": "3v3",
    "5v4": "PP", "5v3": "PP", "4v3": "PP",
    "4v5": "PK", "3v5": "PK", "3v4": "PK",
}


def load_shots(season):
    path = EVENTS_DIR / f"season={season}" / "shots.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    # Non-empty-net unblocked attempts only
    df = df[~df["empty_net"]].copy()
    return df


def featurise(df):
    """Build feature matrix from shots dataframe."""
    df = df.copy()
    df["strength_group"] = df["strength"].map(STRENGTH_GROUPS).fillna("other")

    # One-hot shot type
    shot_types = ["wrist", "slap", "snap", "backhand", "tip-in", "deflected", "wrap-around", "cradle"]
    for st in shot_types:
        df[f"st_{st}"] = (df["shot_type"] == st).astype(int)

    # Strength group dummies
    for sg in ["PP", "PK", "3v3"]:
        df[f"sg_{sg}"] = (df["strength_group"] == sg).astype(int)

    feature_cols = (
        ["distance", "angle", "rebound", "rush"]
        + [f"st_{st}" for st in shot_types]
        + [f"sg_{sg}" for sg in ["PP", "PK", "3v3"]]
    )
    X = df[feature_cols].fillna(0).values.astype(float)
    y = df["is_goal"].values.astype(int)
    return X, y, feature_cols, df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Load fit data
    fit_dfs = []
    for s in FIT_SEASONS:
        df = load_shots(s)
        if df.empty:
            print(f"HALT: no shots for season {s}")
            sys.exit(1)
        fit_dfs.append(df)
    fit_df = pd.concat(fit_dfs, ignore_index=True)
    print(f"Fit data: {len(fit_df)} non-empty-net shots from seasons {FIT_SEASONS}")
    print(f"  goals: {fit_df['is_goal'].sum()} ({fit_df['is_goal'].mean():.3%})")

    X_fit, y_fit, feature_cols, fit_enriched = featurise(fit_df)

    # Training table sha256
    table_hash = hashlib.sha256(pd.util.hash_pandas_object(fit_enriched[feature_cols + ["is_goal"]]).values.tobytes()).hexdigest()

    # Fit
    model = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    model.fit(X_fit, y_fit)

    # Training metrics
    p_fit = model.predict_proba(X_fit)[:, 1]
    auc_fit = roc_auc_score(y_fit, p_fit)
    ll_fit = log_loss(y_fit, p_fit)
    xg_sum_fit = p_fit.sum()
    goals_fit = y_fit.sum()
    print(f"\nFit AUC: {auc_fit:.4f}, log-loss: {ll_fit:.4f}")
    print(f"sum(xG)/goals: {xg_sum_fit:.0f}/{goals_fit} = {xg_sum_fit/goals_fit:.3f}")

    # NULL CONTROL: shuffled labels -> AUC ~0.50
    rng = np.random.RandomState(42)
    y_shuf = rng.permutation(y_fit)
    model_null = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    model_null.fit(X_fit, y_shuf)
    p_null = model_null.predict_proba(X_fit)[:, 1]
    auc_null = roc_auc_score(y_shuf, p_null)
    print(f"\nNULL CONTROL (shuffled labels): AUC = {auc_null:.4f} (expected ~0.50)")

    # Calibration by decile (fit)
    print(f"\nCalibration by decile (fit seasons):")
    print_calibration(p_fit, y_fit)

    # Validate on 2023-24
    val_df = load_shots(VALIDATE_SEASON)
    if not val_df.empty:
        X_val, y_val, _, val_enriched = featurise(val_df)
        p_val = model.predict_proba(X_val)[:, 1]
        auc_val = roc_auc_score(y_val, p_val)
        ll_val = log_loss(y_val, p_val)
        xg_sum_val = p_val.sum()
        goals_val = y_val.sum()
        slope = compute_calibration_slope(p_val, y_val)
        print(f"\nValidation (2023-24): AUC={auc_val:.4f}, log-loss={ll_val:.4f}")
        print(f"  sum(xG)/goals: {xg_sum_val:.0f}/{goals_val} = {xg_sum_val/goals_val:.3f}")
        print(f"  calibration slope: {slope:.3f}")
        print(f"\nCalibration by decile (2023-24):")
        print_calibration(p_val, y_val)

    # Report all seasons
    print(f"\nsum(xG)/goals by season:")
    for s in REPORT_SEASONS:
        sdf = load_shots(s)
        if sdf.empty:
            print(f"  {s}: no data")
            continue
        X_s, y_s, _, _ = featurise(sdf)
        p_s = model.predict_proba(X_s)[:, 1]
        print(f"  {s}: xG={p_s.sum():.0f} goals={y_s.sum()} ratio={p_s.sum()/y_s.sum():.3f} "
              f"AUC={roc_auc_score(y_s, p_s):.4f}")

    if args.dry_run:
        print("--dry-run: not saving model")
        return

    # Save
    coefs = {feature_cols[j]: float(model.coef_[0][j]) for j in range(len(feature_cols))}
    out = {
        "model": "logistic_regression_xg_v1",
        "fit_seasons": FIT_SEASONS,
        "features": feature_cols,
        "coefficients": coefs,
        "intercept": float(model.intercept_[0]),
        "training_table_sha256": table_hash,
        "training_shots": len(fit_df),
        "training_goals": int(fit_df["is_goal"].sum()),
        "fit_auc": round(auc_fit, 4),
        "null_auc": round(auc_null, 4),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nSaved: {OUT_PATH}")
    print(f"sha256: {hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()}")


def print_calibration(p, y):
    df = pd.DataFrame({"p": p, "y": y})
    df["decile"] = pd.qcut(df["p"], 10, labels=False, duplicates="drop")
    cal = df.groupby("decile").agg(mean_p=("p", "mean"), mean_y=("y", "mean"), n=("y", "count"))
    for _, r in cal.iterrows():
        print(f"  decile {int(r.name)}: predicted={r.mean_p:.4f} actual={r.mean_y:.4f} n={int(r.n)}")


def compute_calibration_slope(p, y):
    """Calibration slope: regress y on logit(p). Slope ~1 = well calibrated."""
    from sklearn.linear_model import LogisticRegression
    logit_p = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    lr = LogisticRegression(max_iter=1000, solver="lbfgs")
    lr.fit(logit_p.reshape(-1, 1), y)
    return float(lr.coef_[0][0])


if __name__ == "__main__":
    main()
