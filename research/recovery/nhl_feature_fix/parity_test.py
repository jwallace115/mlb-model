#!/usr/bin/env python3
"""
Phase 3-4: Feature parity re-test + model parity re-test.

Builds a synthetic live cache from canonical CSV, then recomputes features
using the FIXED pipeline logic. Compares to canonical rebuild features.
"""
import sys, os
sys.path.insert(0, ".")

import pandas as pd
import numpy as np
import pickle
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Load canonical data
# ---------------------------------------------------------------------------
gc = pd.read_csv("nhl/nhl_games_canonical.csv")
gc["game_date"] = pd.to_datetime(gc["game_date"]).dt.date
s25 = gc[gc["season_year"] == 2025].copy()
print(f"Canonical 2025-26 games: {len(s25)}")

# Load canonical features for comparison
canon_ft = pd.read_parquet("research/recovery/nhl_rebuild/nhl_rebuild_features.parquet")
canon_25 = canon_ft[canon_ft["season_year"] == 2025].copy()
print(f"Canonical 2025-26 feature rows: {len(canon_25)}")

# ---------------------------------------------------------------------------
# Build synthetic live cache from canonical CSV
# ---------------------------------------------------------------------------
# Map canonical columns to live cache format
live_rows = []
for _, r in s25.iterrows():
    live_rows.append({
        "game_id": r["game_id"],
        "game_date": r["game_date"],
        "home_team": r["home_team"],
        "away_team": r["away_team"],
        "home_score": r["home_score"],
        "away_score": r["away_score"],
        "home_sog": r.get("home_shots_on_goal"),
        "away_sog": r.get("away_shots_on_goal"),
        "home_pp_goals": r.get("home_pp_goals"),
        "away_pp_goals": r.get("away_pp_goals"),
        "home_pp_opportunities": r.get("home_pp_opportunities"),
        "away_pp_opportunities": r.get("away_pp_opportunities"),
        "home_goalie_id": r.get("home_goalie_id"),
        "away_goalie_id": r.get("away_goalie_id"),
        "home_goalie_name": r.get("home_goalie_name"),
        "away_goalie_name": r.get("away_goalie_name"),
        "home_goalie_sa": r.get("home_goalie_sa"),
        "away_goalie_sa": r.get("away_goalie_sa"),
        "home_goalie_ga": r.get("home_goalie_ga"),
        "away_goalie_ga": r.get("away_goalie_ga"),
    })

live_df = pd.DataFrame(live_rows)
print(f"Synthetic live cache: {len(live_df)} rows, columns: {list(live_df.columns)}")

# ---------------------------------------------------------------------------
# Import fixed pipeline functions
# ---------------------------------------------------------------------------
from nhl.nhl_daily_pipeline import (
    build_live_team_features, compute_league_priors, load_feature_table,
    load_models, predict_and_calibrate
)

ft = load_feature_table()
priors = compute_league_priors(ft)

print("\nPriors computed (D2 fix):")
for k in sorted(priors.keys()):
    if "goals_scored" in k or "shots_for" in k or "goalie_sv" in k or "pp_pct" in k:
        print(f"  {k}: {priors[k]:.4f}")

# ---------------------------------------------------------------------------
# Phase 3: Feature parity — compute features for a sample of games
# ---------------------------------------------------------------------------
FEATURES_TO_CHECK = [
    "goals_scored_rolling_10", "goals_allowed_rolling_10",
    "shots_for_rolling_20", "shots_against_rolling_20",
    "pp_pct_rolling_20", "pk_pct_rolling_20",
    "pp_opp_per_game_rolling_20",
    "goalie_sv_pct_rolling_10", "goalie_vs_team_baseline",
    "goalie_fatigue",
]

# Sample games at different points in the season
sample_indices = list(range(0, len(s25), max(1, len(s25) // 50)))  # ~50 samples
if len(s25) - 1 not in sample_indices:
    sample_indices.append(len(s25) - 1)

print(f"\nComputing features for {len(sample_indices)} sample games...")

results = []
for idx in sample_indices:
    row = s25.iloc[idx]
    game_date = row["game_date"]
    home = row["home_team"]
    away = row["away_team"]
    game_id = row["game_id"]

    # Get goalie IDs from canonical data
    home_goalie_id = row.get("home_goalie_id")
    away_goalie_id = row.get("away_goalie_id")

    # Compute live features using fixed pipeline
    h_feat = build_live_team_features(home, game_date, live_df, priors, "home",
                                       today_goalie_id=home_goalie_id)
    a_feat = build_live_team_features(away, game_date, live_df, priors, "away",
                                       today_goalie_id=away_goalie_id)

    # Get canonical features for this game
    canon_row = canon_25[canon_25["game_id"] == game_id]
    if len(canon_row) == 0:
        continue
    canon_row = canon_row.iloc[0]

    for side, feat_dict in [("home", h_feat), ("away", a_feat)]:
        for f in FEATURES_TO_CHECK:
            feat_name = f"{side}_{f}"
            live_val = feat_dict.get(feat_name)
            canon_val = canon_row.get(feat_name)

            if pd.notna(live_val) and pd.notna(canon_val):
                delta = live_val - canon_val
                results.append({
                    "game_id": game_id,
                    "game_date": str(game_date),
                    "game_num": idx,
                    "side": side,
                    "feature": f,
                    "live_val": round(float(live_val), 6),
                    "canon_val": round(float(canon_val), 6),
                    "delta": round(float(delta), 6),
                    "abs_delta": round(abs(float(delta)), 6),
                })

res_df = pd.DataFrame(results)

# ---------------------------------------------------------------------------
# Feature-level summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 3: FEATURE PARITY REPORT")
print("=" * 70)

feat_summary = res_df.groupby("feature").agg(
    mean_delta=("delta", "mean"),
    std_delta=("delta", "std"),
    max_abs_delta=("abs_delta", "max"),
    mean_abs_delta=("abs_delta", "mean"),
    n=("delta", "count"),
).round(6)

print(feat_summary.to_string())

# Season progression
print("\nDelta by season stage:")
res_df["stage"] = pd.cut(res_df["game_num"], bins=[0, 20, 50, 100, 200, 500, 2000],
                          labels=["1-20", "21-50", "51-100", "101-200", "201-500", "501+"])
stage_summary = res_df.groupby("stage").agg(
    mean_abs_delta=("abs_delta", "mean"),
    max_abs_delta=("abs_delta", "max"),
    n=("delta", "count"),
).round(6)
print(stage_summary.to_string())

# Save feature comparison CSV
res_df.to_csv("research/recovery/nhl_feature_fix/feature_parity_comparison.csv", index=False)
print(f"\nFeature comparison saved: {len(res_df)} rows")

# ---------------------------------------------------------------------------
# Phase 4: Model parity — predict with both canonical and live features
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 4: MODEL PARITY REPORT")
print("=" * 70)

hpkg, apkg = load_models()
all_feats = sorted(set(hpkg["features"] + apkg["features"]))
train = ft[ft["season_year"].isin({2021, 2022})]
train_means = train[all_feats].mean()

pred_results = []
for idx in sample_indices:
    row = s25.iloc[idx]
    game_date = row["game_date"]
    home = row["home_team"]
    away = row["away_team"]
    game_id = row["game_id"]

    home_goalie_id = row.get("home_goalie_id")
    away_goalie_id = row.get("away_goalie_id")

    # Live features (fixed pipeline)
    h_feat = build_live_team_features(home, game_date, live_df, priors, "home",
                                       today_goalie_id=home_goalie_id)
    a_feat = build_live_team_features(away, game_date, live_df, priors, "away",
                                       today_goalie_id=away_goalie_id)
    feat = {**h_feat, **a_feat}
    feat["home_shot_pressure"] = feat["home_shots_for_rolling_20"] - feat["away_shots_against_rolling_20"]
    feat["away_shot_pressure"] = feat["away_shots_for_rolling_20"] - feat["home_shots_against_rolling_20"]

    # Schedule features from canonical
    feat["home_days_rest"] = row.get("home_rest_days", 3.0)
    feat["away_days_rest"] = row.get("away_rest_days", 3.0)
    feat["home_b2b"] = int(row.get("home_is_b2b", 0))
    feat["away_b2b"] = int(row.get("away_is_b2b", 0))
    feat["home_games_last_7"] = row.get("home_games_last_7", 2.5)
    feat["away_games_last_7"] = row.get("away_games_last_7", 2.5)
    feat["home_goalie_b2b"] = int(row.get("home_is_b2b", 0))
    feat["away_goalie_b2b"] = int(row.get("away_is_b2b", 0))
    feat["home_backup_flag"] = 0
    feat["away_backup_flag"] = 0

    # Live prediction
    lh_live, la_live, drift = predict_and_calibrate(feat, hpkg, apkg, live_df, game_date, train_means)
    lt_live = lh_live + la_live

    # Canonical prediction — use canonical features directly
    canon_row = canon_25[canon_25["game_id"] == game_id]
    if len(canon_row) == 0:
        continue
    canon_row = canon_row.iloc[0]

    canon_feat = {}
    for f in all_feats:
        canon_feat[f] = canon_row.get(f, train_means.get(f, 0.0))

    canon_df = pd.DataFrame([canon_feat])
    canon_df = canon_df.fillna(train_means)

    lh_canon = hpkg["model"].predict(hpkg["scaler"].transform(canon_df[hpkg["features"]].to_numpy()))[0]
    la_canon = apkg["model"].predict(apkg["scaler"].transform(canon_df[apkg["features"]].to_numpy()))[0]
    # Apply same drift
    lh_canon += drift / 2.0
    la_canon += drift / 2.0
    lt_canon = lh_canon + la_canon

    actual = row["total_goals"]

    pred_results.append({
        "game_id": game_id,
        "game_date": str(game_date),
        "game_num": idx,
        "home": home,
        "away": away,
        "actual_total": actual,
        "live_total": round(lt_live, 4),
        "canon_total": round(lt_canon, 4),
        "delta": round(lt_live - lt_canon, 4),
        "abs_delta": round(abs(lt_live - lt_canon), 4),
        "live_error": round(lt_live - actual, 4),
        "canon_error": round(lt_canon - actual, 4),
    })

pred_df = pd.DataFrame(pred_results)

print(f"\nPredictions compared: {len(pred_df)} games")
print(f"Mean delta (live - canon): {pred_df['delta'].mean():.4f}")
print(f"Std delta:                 {pred_df['delta'].std():.4f}")
print(f"Max abs delta:             {pred_df['abs_delta'].max():.4f}")
print(f"Mean abs delta:            {pred_df['abs_delta'].mean():.4f}")
print(f"Live MAE:                  {pred_df['live_error'].abs().mean():.4f}")
print(f"Canon MAE:                 {pred_df['canon_error'].abs().mean():.4f}")

# Prediction delta by season stage
print("\nPrediction delta by season stage:")
pred_df["stage"] = pd.cut(pred_df["game_num"], bins=[0, 20, 50, 100, 200, 500, 2000],
                           labels=["1-20", "21-50", "51-100", "101-200", "201-500", "501+"])
stage_pred = pred_df.groupby("stage").agg(
    mean_delta=("delta", "mean"),
    mean_abs_delta=("abs_delta", "mean"),
    max_abs_delta=("abs_delta", "max"),
    n=("delta", "count"),
).round(4)
print(stage_pred.to_string())

# Save prediction comparison
pred_df.to_csv("research/recovery/nhl_feature_fix/prediction_parity_comparison.csv", index=False)
print(f"\nPrediction comparison saved: {len(pred_df)} rows")

# ---------------------------------------------------------------------------
# Phase 5: Final verdict
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 5: FINAL VERDICT")
print("=" * 70)

mean_abs_delta = pred_df["abs_delta"].mean()
max_abs_delta = pred_df["abs_delta"].max()
mean_delta = pred_df["delta"].mean()

# Late-season delta (games 200+) — the key test since priors wash out
late = pred_df[pred_df["game_num"] >= 200]
late_mean_abs = late["abs_delta"].mean() if len(late) > 0 else 999
late_max_abs = late["abs_delta"].max() if len(late) > 0 else 999

print(f"\nOverall: mean_abs_delta={mean_abs_delta:.4f}, max_abs_delta={max_abs_delta:.4f}, mean_delta={mean_delta:.4f}")
print(f"Late-season (200+): mean_abs_delta={late_mean_abs:.4f}, max_abs_delta={late_max_abs:.4f}")

# Feature-level check
feat_max_abs = feat_summary["max_abs_delta"].max()
feat_mean_abs = feat_summary["mean_abs_delta"].mean()
print(f"Feature level: max_abs_delta={feat_max_abs:.6f}, mean_of_mean_abs={feat_mean_abs:.6f}")

# Verdict thresholds
if late_mean_abs < 0.01 and late_max_abs < 0.05:
    verdict = "READY FOR SHADOW"
    print(f"\nVERDICT: {verdict}")
    print("  All features within tolerance. Fixed pipeline matches canonical rebuild.")
elif late_mean_abs < 0.05 and late_max_abs < 0.15:
    verdict = "PARTIAL"
    print(f"\nVERDICT: {verdict}")
    print("  Most features match but residual divergence remains.")
    print("  Investigate remaining feature deltas before going live.")
else:
    verdict = "FAILED"
    print(f"\nVERDICT: {verdict}")
    print("  Significant divergence persists after fixes.")
    print("  Additional investigation required.")

# Check prior-region specifically
early = pred_df[pred_df["game_num"] < 20]
if len(early) > 0:
    early_mean_abs = early["abs_delta"].mean()
    print(f"\nEarly-season (0-20): mean_abs_delta={early_mean_abs:.4f}")
    if early_mean_abs > late_mean_abs * 3 and early_mean_abs > 0.02:
        print("  NOTE: Early-season divergence is expected from prior differences.")
        print("  D2 fix narrows but cannot eliminate all prior divergence since")
        print("  canonical uses look-ahead 2025 season stats.")

print(f"\n{'=' * 70}")
print(f"VERDICT: {verdict}")
print(f"{'=' * 70}")
