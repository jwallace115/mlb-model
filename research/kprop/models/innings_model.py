#!/usr/bin/env python3
"""
K2 — Innings Distribution Model for K Prop Research.

Multinomial logistic: predicts IP bucket probabilities per start.
Train: 2022-2023, Val: 2024, Holdout: 2025.
"""

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegressionCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, confusion_matrix

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "kprop"

# ── Load data ────────────────────────────────────────────────────────────────

pgl = pd.read_parquet(PROJECT / "mlb" / "data" / "pitcher_game_logs.parquet")
starters = pgl[pgl["starter_flag"] == 1].copy()
starters["game_pk"] = starters["game_pk"].astype(str)
starters = starters.sort_values(["player_id", "game_date"]).reset_index(drop=True)

ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)

# ── Compute features ────────────────────────────────────────────────────────

# Outs and IP bucket
starters["outs"] = (starters["innings_pitched"] * 3).round().astype(int)
starters["ip_bucket"] = pd.cut(
    starters["outs"],
    bins=[-1, 11, 14, 17, 20, 999],
    labels=[0, 1, 2, 3, 4]
).astype(int)

# Traditional starter flag
starters["traditional_starter"] = (starters["outs"] >= 12).astype(int)

# Prior-start features (strictly lagged — no leakage)
starters["pc_last1"] = starters.groupby("player_id")["pitches"].shift(1)
starters["pc_last3_avg"] = starters.groupby("player_id")["pitches"].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)
starters["ip_last1"] = starters.groupby("player_id")["innings_pitched"].shift(1)

# Season-to-date avg pitch count (prior starts only)
starters["pc_season_avg"] = starters.groupby(["player_id", "season"])["pitches"].transform(
    lambda x: x.shift(1).expanding().mean()
)

# Days rest
starters["prev_date"] = starters.groupby("player_id")["game_date"].shift(1)
starters["days_rest"] = (
    pd.to_datetime(starters["game_date"]) - pd.to_datetime(starters["prev_date"])
).dt.days
starters["days_rest"] = starters["days_rest"].clip(upper=14)

# Count starts this season (for early-season blending)
starters["season_starts"] = starters.groupby(["player_id", "season"]).cumcount()

# Prior season averages for early-season blending
prior_season_avg = starters.groupby(["player_id", "season"]).agg(
    prior_pc_avg=("pitches", "mean"),
    prior_ip_avg=("innings_pitched", "mean"),
).reset_index()
prior_season_avg["season"] = prior_season_avg["season"] + 1  # shift to next year
prior_season_avg = prior_season_avg.rename(columns={
    "prior_pc_avg": "prior_yr_pc_avg",
    "prior_ip_avg": "prior_yr_ip_avg",
})

starters = starters.merge(prior_season_avg, on=["player_id", "season"], how="left")

# Early-season blending: weight = min(season_starts, 5) / 5
starters["blend_w"] = (starters["season_starts"].clip(upper=5) / 5)
starters["pc_season_avg_blended"] = (
    starters["blend_w"] * starters["pc_season_avg"].fillna(starters["prior_yr_pc_avg"]) +
    (1 - starters["blend_w"]) * starters["prior_yr_pc_avg"].fillna(starters["pc_season_avg"])
)
starters["pc_season_avg_blended"] = starters["pc_season_avg_blended"].fillna(starters["pc_season_avg"])

# Opponent wOBA from feature table (game-level)
# For home starter: opponent is away team → away_wrc_plus as proxy
# For away starter: opponent is home team → home_wrc_plus as proxy
ft_opp = ft[["game_pk", "home_wrc_plus", "away_wrc_plus"]].copy()
starters = starters.merge(ft_opp, on="game_pk", how="left")
starters["opp_wrc"] = np.where(
    starters["home_away"] == "home",
    starters["away_wrc_plus"],
    starters["home_wrc_plus"]
)

# ── Feature matrix ───────────────────────────────────────────────────────────

FEATURES = ["pc_last1", "pc_last3_avg", "pc_season_avg_blended", "days_rest",
            "ip_last1", "opp_wrc"]

# Drop rows with missing features (first start of career, etc.)
model_df = starters.dropna(subset=FEATURES + ["ip_bucket"]).copy()

print("=" * 60)
print("PHASE K2 — INNINGS DISTRIBUTION MODEL")
print("=" * 60)

# Traditional starter filter
trad = model_df[model_df["traditional_starter"] == 1]
n_excluded = len(model_df) - len(trad)
print(f"\nTraditional starters: {len(trad)}")
print(f"Excluded (< 12 outs): {n_excluded} ({n_excluded/len(model_df)*100:.1f}%)")

# ── Empirical midpoints ─────────────────────────────────────────────────────

print("\nEmpirical bucket midpoints (from ALL starters, 2022-2023):")
train_all = model_df[model_df["season"].isin([2022, 2023])]
empirical_means = {}
for b in range(5):
    sub = train_all[train_all["ip_bucket"] == b]
    emp_mean = sub["innings_pitched"].mean()
    empirical_means[b] = round(emp_mean, 2)
    hand = [3.0, 4.5, 5.5, 6.5, 7.5][b]
    print(f"  Bucket {b}: N={len(sub):5d} empirical_mean_ip={emp_mean:.2f} (hand-set={hand:.1f})")

# ── Train/Val/Holdout split ──────────────────────────────────────────────────

# Use traditional starters for model fitting
train = trad[trad["season"].isin([2022, 2023])]
val = trad[trad["season"] == 2024]
holdout = trad[trad["season"] == 2025]

print(f"\n--- SAMPLE SIZE GATE ---")
for label, df_split in [("Train", train), ("Val", val), ("Holdout", holdout)]:
    counts = df_split["ip_bucket"].value_counts().sort_index()
    print(f"  {label}: {dict(counts)}")
    if label == "Train" and counts.min() < 150:
        print("  *** HARD STOP: bucket count < 150 ***")
        sys.exit(1)

# ── Fit model ────────────────────────────────────────────────────────────────

X_train = train[FEATURES].values
y_train = train["ip_bucket"].values
X_val = val[FEATURES].values
y_val = val["ip_bucket"].values
X_hold = holdout[FEATURES].values
y_hold = holdout["ip_bucket"].values

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_val_s = scaler.transform(X_val)
X_hold_s = scaler.transform(X_hold)

model = LogisticRegressionCV(
    Cs=10, cv=5, penalty="l2", solver="lbfgs",
    max_iter=2000, random_state=42,
)
model.fit(X_train_s, y_train)

print(f"\nBest C: {model.C_[0]:.4f}")

# ── Predictions ──────────────────────────────────────────────────────────────

# Predict on ALL data (including non-traditional starters) for downstream use
all_df = model_df.copy()
X_all = all_df[FEATURES].values
X_all_s = scaler.transform(X_all)
probs = model.predict_proba(X_all_s)
preds = model.predict(X_all_s)
classes = model.classes_  # may be [1,2,3,4] if bucket 0 excluded from train

# Map probabilities to all 5 buckets (0 through 4)
for i in range(5):
    if i in classes:
        col_idx = list(classes).index(i)
        all_df[f"p_bucket{i}"] = probs[:, col_idx]
    else:
        all_df[f"p_bucket{i}"] = 0.0  # bucket not in model

all_df["predicted_bucket"] = preds
all_df["actual_bucket"] = all_df["ip_bucket"]
all_df["expected_ip"] = sum(all_df[f"p_bucket{i}"] * empirical_means[i] for i in range(5))

# Save
out_cols = ["game_pk", "game_date", "player_id", "player_name", "season",
            "traditional_starter", "innings_pitched", "outs",
            "p_bucket0", "p_bucket1", "p_bucket2", "p_bucket3", "p_bucket4",
            "predicted_bucket", "actual_bucket", "expected_ip",
            "batters_faced", "strikeouts", "pitches"]
all_df[out_cols].to_parquet(OUT / "data" / "innings_model_results.parquet", index=False)

# Save model
with open(OUT / "models" / "innings_model.pkl", "wb") as f:
    pickle.dump({"model": model, "scaler": scaler, "features": FEATURES,
                 "empirical_means": empirical_means}, f)

# ── K2 GATE ──────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("K2 GATE")
print("=" * 60)

# 1. Train bucket counts
print("\n1. Train bucket counts:")
for b, n in train["ip_bucket"].value_counts().sort_index().items():
    print(f"   Bucket {b}: {n}")

# 2. Empirical means
print("\n2. Empirical mean IP by bucket (used as midpoints):")
for b, m in empirical_means.items():
    print(f"   Bucket {b}: {m}")

# 3. Val accuracy + confusion
y_val_pred = model.predict(X_val_s)
print(f"\n3. 2024 Val accuracy: {accuracy_score(y_val, y_val_pred):.3f}")
print(f"   Confusion matrix:")
cm = confusion_matrix(y_val, y_val_pred, labels=list(classes))
hdr = " ".join(f"Pred{c}" for c in classes)
print(f"   {'':>8} {hdr}")
for i, c in enumerate(classes):
    row = " ".join(f"{cm[i,j]:5d}" for j in range(len(classes)))
    print(f"   Act{c}: {row}")

# 4. Holdout accuracy + confusion
y_hold_pred = model.predict(X_hold_s)
print(f"\n4. 2025 Holdout accuracy: {accuracy_score(y_hold, y_hold_pred):.3f}")
cm2 = confusion_matrix(y_hold, y_hold_pred, labels=list(classes))
print(f"   {'':>8} {hdr}")
for i, c in enumerate(classes):
    row = " ".join(f"{cm2[i,j]:5d}" for j in range(len(classes)))
    print(f"   Act{c}: {row}")

# 5. Coefficients
print("\n5. Coefficient table:")
print(f"   {'Feature':>25s}", end="")
for c in classes:
    print(f"  Bucket{c:1d}", end="")
print()
for j, feat in enumerate(FEATURES):
    print(f"   {feat:>25s}", end="")
    for b in range(len(classes)):
        print(f"  {model.coef_[b, j]:+7.3f}", end="")
    print()

# 6. Expected IP calibration
print("\n6. Expected IP calibration (2024 val, traditional starters):")
val_df = all_df[(all_df["season"] == 2024) & (all_df["traditional_starter"] == 1)]
for b in range(5):
    sub = val_df[val_df["actual_bucket"] == b]
    if len(sub) > 0:
        pred_ip = sub["expected_ip"].mean()
        actual_ip = sub["innings_pitched"].mean()
        print(f"   Bucket {b}: predicted_mean_ip={pred_ip:.2f}, actual_mean_ip={actual_ip:.2f}, "
              f"diff={pred_ip - actual_ip:+.2f}, N={len(sub)}")

# 7. Excluded starts
print(f"\n7. Excluded (non-traditional) starts: {n_excluded}")
print(f"   By season: {model_df[model_df['traditional_starter']==0].groupby('season').size().to_dict()}")

# Group comparison
print("\n--- GROUP COMPARISON: traditional vs all ---")
for label, mask in [("Traditional only", all_df["traditional_starter"] == 1),
                    ("All starters", pd.Series(True, index=all_df.index))]:
    sub_val = all_df[mask & (all_df["season"] == 2024)]
    sub_hold = all_df[mask & (all_df["season"] == 2025)]
    if len(sub_val) > 0:
        acc_v = accuracy_score(sub_val["actual_bucket"], sub_val["predicted_bucket"])
        acc_h = accuracy_score(sub_hold["actual_bucket"], sub_hold["predicted_bucket"])
        print(f"  {label}: val_acc={acc_v:.3f}, holdout_acc={acc_h:.3f}, "
              f"val_N={len(sub_val)}, holdout_N={len(sub_hold)}")

print("\n*** K2 GATE COMPLETE — awaiting confirmation for K3 ***")
