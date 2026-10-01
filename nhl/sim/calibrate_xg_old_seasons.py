#!/usr/bin/env python3
"""D4: apply frozen xg_v2.json to 2010-2020 shots and report calibration by decile per season.

Does NOT refit. Uses the exact model from xg_v2.json.

Usage:
  python3 nhl/sim/calibrate_xg_old_seasons.py
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
XG_PATH = ROOT / "nhl" / "data" / "sim" / "xg_v2.json"

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
    df = df[~df["empty_net"]].copy()
    return df


def featurise(df, feature_cols):
    df = df.copy()
    df["strength_group"] = df["strength"].map(STRENGTH_GROUPS).fillna("other")
    shot_types = ["wrist", "slap", "snap", "backhand", "tip-in", "deflected", "wrap-around", "cradle"]
    for st in shot_types:
        df[f"st_{st}"] = (df["shot_type"] == st).astype(int)
    for sg in ["PP", "PK", "3v3"]:
        df[f"sg_{sg}"] = (df["strength_group"] == sg).astype(int)
    X = df[feature_cols].fillna(0).values.astype(float)
    y = df["is_goal"].values.astype(int)
    return X, y


def predict(X, coef, intercept):
    logits = X @ np.array(coef) + intercept
    return 1.0 / (1.0 + np.exp(-logits))


def calibration_by_decile(y_true, y_pred):
    df = pd.DataFrame({"p": y_pred, "y": y_true})
    df["decile"] = pd.qcut(df["p"], 10, duplicates="drop")
    t = df.groupby("decile", observed=True).agg(
        mean_pred=("p", "mean"), mean_actual=("y", "mean"), n=("y", "count"))
    return t


def main():
    with open(XG_PATH) as f:
        model = json.load(f)
    coef_dict = model["coefficients"]
    intercept = model["intercept"]
    feature_cols = model["features"]
    coef = [coef_dict[f] for f in feature_cols]
    print(f"Model: {XG_PATH.name}, {len(coef)} features, intercept={intercept:.4f}")

    seasons = list(range(2010, 2026))
    results = []

    for season in seasons:
        shots = load_shots(season)
        if shots.empty:
            continue
        X, y = featurise(shots, feature_cols)
        p = predict(X, coef, intercept)
        auc = roc_auc_score(y, p)
        ll = log_loss(y, p)
        goal_rate = y.mean()
        pred_rate = p.mean()
        results.append({
            "season": season, "n_shots": len(y), "goal_rate": goal_rate,
            "pred_rate": pred_rate, "auc": auc, "log_loss": ll,
        })
        print(f"\n  {season}-{season+1}: {len(y)} shots, goal_rate={goal_rate:.4f}, "
              f"pred_rate={pred_rate:.4f}, AUC={auc:.4f}, log_loss={ll:.4f}")
        cal = calibration_by_decile(y, p)
        for _, r in cal.iterrows():
            diff = r.mean_actual - r.mean_pred
            flag = " <--" if abs(diff) > 0.02 else ""
            print(f"    {r.name}: pred={r.mean_pred:.4f} actual={r.mean_actual:.4f} "
                  f"n={int(r.n)} diff={diff:+.4f}{flag}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    rdf = pd.DataFrame(results)
    print(rdf.round(4).to_string(index=False))

    # Verdict
    old = rdf[rdf.season < 2021]
    new = rdf[rdf.season >= 2021]
    if not old.empty:
        old_auc = old.auc.mean()
        new_auc = new.auc.mean() if not new.empty else 0
        print(f"\nMean AUC: 2010-2020 = {old_auc:.4f}, 2021-2025 = {new_auc:.4f}")
        print(f"AUC drop: {new_auc - old_auc:+.4f}")
        bad = old[old.auc < 0.70]
        if len(bad):
            print(f"Seasons with AUC < 0.70: {bad.season.tolist()} — xG refit may be needed")
        else:
            print("All 2010-2020 seasons have AUC >= 0.70 — one xG model may serve")


if __name__ == "__main__":
    main()
