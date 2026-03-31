#!/usr/bin/env python3
"""
MLB Simulation Engine — Phase S2: Starter Path Model
=====================================================
Classifies each start into 3 path buckets based on pregame inputs.
The path bucket drives variance routing in the run distribution engine.

Path buckets (defined in outs, not decimal IP):
  Path 0 — Early Exit:  < 15 outs recorded
  Path 1 — Normal:      15 to 20 outs recorded (inclusive)
  Path 2 — Deep:        > 20 outs recorded

CSW ROLE: path-probability input, NOT a mean-runs feature.
CSW shifts the probability of Path 0 (early exit).

Training: 2022-2023 | OOS evaluation: 2024
"""

import os
import sys
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegressionCV, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, brier_score_loss

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIM_DATA = Path(__file__).resolve().parent.parent / "data"
EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
MODEL_DIR = Path(__file__).resolve().parent
EVAL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Path bucket definitions (in outs)
PATH_0_MAX_OUTS = 14   # < 15 outs = early exit
PATH_1_MAX_OUTS = 20   # 15–20 outs = normal
# > 20 outs = deep

# Features for path model
# sp_siera dropped — confirmed identical to sp_xfip (pipeline alias)
FEATURES = [
    "sp_csw_pct",
    "sp_whiff_pct",
    "sp_fstrike_pct",
    "sp_xfip",
    "days_rest",
    "sp_recent_pc",
    "opp_lineup_woba",
    "park_factor",
    "weather_run_modifier",
]


def ip_to_outs(ip_val):
    """Convert IP notation (e.g., 5.2 = 5 innings + 2 outs) to total outs."""
    if pd.isna(ip_val):
        return np.nan
    whole = int(ip_val)
    frac = round((ip_val - whole) * 10)
    return whole * 3 + frac


def outs_to_ip_display(outs):
    """Convert total outs to IP display notation."""
    innings = outs // 3
    remainder = outs % 3
    return f"{innings}.{remainder}"


def assign_path(outs):
    """Assign path bucket from outs recorded."""
    if pd.isna(outs):
        return np.nan
    if outs < 15:
        return 0
    elif outs <= 20:
        return 1
    else:
        return 2


def build_and_evaluate():
    """Build starter path model on 2022-2023, evaluate on 2024."""

    # ── Load S1 feature table ────────────────────────────────────────────────
    sim_path = SIM_DATA / "sim_inputs_historical_2022_2024.parquet"
    if not sim_path.exists():
        print(f"ERROR: {sim_path} not found. Run build_sim_inputs.py first.")
        sys.exit(1)

    df = pd.read_parquet(sim_path)
    print(f"Loaded: {len(df)} starter-rows")

    # ── Compute outs recorded and assign path buckets ────────────────────────
    df["outs_recorded"] = df["actual_ip"].apply(ip_to_outs)
    df["actual_path"] = df["outs_recorded"].apply(assign_path)

    # Drop rows with missing actual path (no game log data)
    df = df.dropna(subset=["actual_path"])
    df["actual_path"] = df["actual_path"].astype(int)
    print(f"After dropping missing actual_path: {len(df)} rows")

    # ── Split train/OOS ──────────────────────────────────────────────────────
    train = df[df["season"].isin([2022, 2023])].copy()
    oos = df[df["season"] == 2024].copy()
    print(f"Train: {len(train)} | OOS: {len(oos)}")

    # ── SAMPLE SIZE GATE ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SAMPLE SIZE GATE")
    print("=" * 60)
    train_counts = train["actual_path"].value_counts().sort_index()
    print(f"\nTrain set path bucket counts:")
    for path, count in train_counts.items():
        label = {0: "Early Exit (<15 outs)", 1: "Normal (15-20 outs)", 2: "Deep (>20 outs)"}[path]
        status = "PASS" if count >= 150 else "*** FAIL ***"
        print(f"  Path {path} — {label}: {count} ({status})")

    if (train_counts < 150).any():
        print("\n*** SAMPLE SIZE GATE FAILED — stopping ***")
        sys.exit(1)
    print("\nGate: PASS")

    # ── Prepare features ─────────────────────────────────────────────────────
    # Drop rows with missing features
    train_clean = train.dropna(subset=FEATURES).copy()
    oos_clean = oos.dropna(subset=FEATURES).copy()
    print(f"\nAfter feature dropna: Train={len(train_clean)} OOS={len(oos_clean)}")

    X_train = train_clean[FEATURES].values
    y_train = train_clean["actual_path"].values
    X_oos = oos_clean[FEATURES].values
    y_oos = oos_clean["actual_path"].values

    # Standardize on train set; apply same scaler to OOS
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_oos_s = scaler.transform(X_oos)

    # ── Tune regularization on train via CV ──────────────────────────────────
    print("\nTuning regularization (5-fold CV on train)...")
    cv_model = LogisticRegressionCV(
        Cs=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0],
        cv=5,
        penalty="l2",
        solver="lbfgs",
        max_iter=2000,
        random_state=42,
    )
    cv_model.fit(X_train_s, y_train)
    best_C = cv_model.C_[0]
    print(f"Best C: {best_C}")

    # ── Fit final model on full train with best C ────────────────────────────
    model = LogisticRegression(
        C=best_C,
        penalty="l2",
        solver="lbfgs",
        max_iter=2000,
        random_state=42,
    )
    model.fit(X_train_s, y_train)

    # ── Predict on OOS ───────────────────────────────────────────────────────
    probs_oos = model.predict_proba(X_oos_s)
    preds_oos = model.predict(X_oos_s)

    oos_clean["p_path0"] = probs_oos[:, 0]
    oos_clean["p_path1"] = probs_oos[:, 1]
    oos_clean["p_path2"] = probs_oos[:, 2]
    oos_clean["predicted_path"] = preds_oos
    oos_clean["correct"] = (preds_oos == y_oos).astype(int)

    # ── Save model and OOS results ───────────────────────────────────────────
    model_bundle = {
        "model": model,
        "scaler": scaler,
        "features": FEATURES,
        "best_C": best_C,
        "train_seasons": [2022, 2023],
    }
    model_path = MODEL_DIR / "starter_path_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_bundle, f)
    print(f"\nModel saved: {model_path}")

    oos_output = oos_clean[["game_pk", "date", "sp_name", "sp_id", "team_id",
                             "p_path0", "p_path1", "p_path2",
                             "predicted_path", "actual_path", "correct"]].copy()
    oos_path = EVAL_DIR / "starter_path_oos_2024.parquet"
    oos_output.to_parquet(oos_path, index=False)
    print(f"OOS results saved: {oos_path} ({len(oos_output)} rows)")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE S2 GATE DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("PHASE S2 GATE DIAGNOSTICS")
    print("=" * 60)

    # 1. Train set path bucket counts
    print("\n1. TRAIN SET PATH BUCKET COUNTS")
    for path in [0, 1, 2]:
        label = {0: "Early Exit (<15 outs)", 1: "Normal (15-20)", 2: "Deep (>20)"}[path]
        n = (y_train == path).sum()
        pct = n / len(y_train) * 100
        print(f"   Path {path} — {label}: {n} ({pct:.1f}%)")

    # 2. OOS hard-class accuracy
    accuracy = oos_clean["correct"].mean() * 100
    print(f"\n2. OOS HARD-CLASS ACCURACY: {accuracy:.1f}%")

    # 3. OOS confusion matrix
    print(f"\n3. OOS CONFUSION MATRIX (rows=actual, cols=predicted)")
    cm = confusion_matrix(y_oos, preds_oos, labels=[0, 1, 2])
    print(f"{'':>15} | {'Pred 0':>8} | {'Pred 1':>8} | {'Pred 2':>8} | {'Total':>8}")
    print("-" * 58)
    labels = {0: "Actual 0 (EE)", 1: "Actual 1 (N)", 2: "Actual 2 (D)"}
    for i in [0, 1, 2]:
        row_total = cm[i].sum()
        print(f"{labels[i]:>15} | {cm[i][0]:>8} | {cm[i][1]:>8} | {cm[i][2]:>8} | {row_total:>8}")

    # 4. Coefficient table
    print(f"\n4. COEFFICIENT TABLE")
    print(f"{'Feature':<25} | {'Path 0 (EE)':>12} | {'Path 1 (N)':>12} | {'Path 2 (D)':>12}")
    print("-" * 70)
    for j, feat in enumerate(FEATURES):
        c0 = model.coef_[0][j]
        c1 = model.coef_[1][j]
        c2 = model.coef_[2][j]
        print(f"{feat:<25} | {c0:>+12.4f} | {c1:>+12.4f} | {c2:>+12.4f}")
    print(f"{'intercept':<25} | {model.intercept_[0]:>+12.4f} | {model.intercept_[1]:>+12.4f} | {model.intercept_[2]:>+12.4f}")

    # 5. CSW quartile table (OOS only)
    print(f"\n5. CSW QUARTILE TABLE (OOS only)")
    print("   CSW quartile cut points defined on 2022-2023 train set:")
    csw_train = train_clean["sp_csw_pct"]
    q_cuts = csw_train.quantile([0.25, 0.50, 0.75]).values
    print(f"   Q25={q_cuts[0]:.2f}, Q50={q_cuts[1]:.2f}, Q75={q_cuts[2]:.2f}")

    def assign_csw_q(v):
        if pd.isna(v): return np.nan
        if v <= q_cuts[0]: return "Q1 (low)"
        if v <= q_cuts[1]: return "Q2"
        if v <= q_cuts[2]: return "Q3"
        return "Q4 (high)"

    oos_clean["csw_quartile"] = oos_clean["sp_csw_pct"].apply(assign_csw_q)

    print(f"\n   {'CSW Quartile':<15} | {'N':>6} | {'Actual P0 rate':>15} | {'Mean pred p_path0':>18} | {'Delta':>8}")
    print("   " + "-" * 72)
    for q in ["Q1 (low)", "Q2", "Q3", "Q4 (high)"]:
        sub = oos_clean[oos_clean["csw_quartile"] == q]
        if len(sub) == 0:
            continue
        actual_p0_rate = (sub["actual_path"] == 0).mean() * 100
        mean_pred_p0 = sub["p_path0"].mean() * 100
        delta = actual_p0_rate - mean_pred_p0
        print(f"   {q:<15} | {len(sub):>6} | {actual_p0_rate:>14.1f}% | {mean_pred_p0:>17.1f}% | {delta:>+7.1f}%")

    # 6. Probabilistic Path 0 diagnostics (OOS)
    print(f"\n6. PROBABILISTIC PATH 0 DIAGNOSTICS (OOS)")
    p0_actual = (y_oos == 0).astype(int)
    p0_pred = oos_clean["p_path0"].values

    avg_p0_for_actual_p0 = p0_pred[p0_actual == 1].mean()
    avg_p0_for_non_p0 = p0_pred[p0_actual == 0].mean()
    brier = brier_score_loss(p0_actual, p0_pred)

    print(f"   Avg predicted p_path0 for actual Path 0 starts: {avg_p0_for_actual_p0:.4f}")
    print(f"   Avg predicted p_path0 for actual non-Path 0:    {avg_p0_for_non_p0:.4f}")
    print(f"   Separation: {avg_p0_for_actual_p0 - avg_p0_for_non_p0:.4f}")
    print(f"   Brier score (Path 0 vs not): {brier:.4f}")

    print(f"\n*** PHASE S2 COMPLETE — awaiting confirmation to proceed to S3 ***")


if __name__ == "__main__":
    build_and_evaluate()
