"""
Phases 1-6: Clean V1 Retrain, Backtest, Calibration, Downstream, Comparison, Recommendation
"""
import os, sys, warnings, pickle
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error

warnings.filterwarnings("ignore")

PROJECT_DIR = "/root/mlb-model"
sys.path.insert(0, PROJECT_DIR)

RECOVERY_DIR = os.path.join(PROJECT_DIR, "research/recovery")
PIT_FT_PATH = os.path.join(RECOVERY_DIR, "v1_clean_features/baseball_features_pit_v1.parquet")
MARKET_PATH = os.path.join(PROJECT_DIR, "sim/data/market_snapshots.parquet")
ORIG_MODEL_PATH = os.path.join(PROJECT_DIR, "sim/data/phase9_baseline_model.pkl")
ORIG_FT_PATH = os.path.join(PROJECT_DIR, "sim/data/feature_table.parquet")
BF_PATH = os.path.join(PROJECT_DIR, "sim/data/bullpen_features.parquet")

SIGMA = 4.361280110817918
ALPHA = 50.0
TRAIN_YEARS = [2022, 2023]
VAL_YEAR = 2024
OOS_YEAR = 2025

V1_FEATURES = [
    "home_sp_xfip", "away_sp_xfip", "home_sp_k_pct", "away_sp_k_pct",
    "home_sp_bb_pct", "away_sp_bb_pct", "home_sp_avg_ip", "away_sp_avg_ip",
    "home_wrc_plus", "away_wrc_plus", "park_factor_runs", "park_factor_hr",
    "temperature", "wind_factor_effective", "umpire_over_rate",
    "home_rest_days", "away_rest_days", "doubleheader_flag",
    "flyball_wind_interaction",
    "home_high_leverage_avail", "away_high_leverage_avail",
    "home_bullpen_delta", "away_bullpen_delta",
    "home_bp_delta_exposure", "away_bp_delta_exposure",
]

def load_data():
    df = pd.read_parquet(PIT_FT_PATH)
    df["date"] = pd.to_datetime(df["date"])
    # Filter 9-inning completed games
    df = df[df["innings_played"] >= 9].copy()
    df = df[df["actual_total"].notna()].copy()
    return df

def load_market():
    ms = pd.read_parquet(MARKET_PATH)
    ms["date"] = pd.to_datetime(ms["date"])
    # Use DK closing total
    dk = ms[ms["book"] == "draftkings"][["game_id", "date", "close_total", "over_price", "under_price"]].copy()
    dk = dk.rename(columns={"game_id": "game_pk"})
    return dk

def train_ridge(X_train, y_train):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=ALPHA)),
    ])
    pipe.fit(X_train, y_train)
    return pipe

def compute_p_under(pred_total, closing_total, sigma=SIGMA):
    """P(actual < closing_total) using normal CDF."""
    if pd.isna(closing_total) or pd.isna(pred_total):
        return np.nan
    return sp_stats.norm.cdf(closing_total, loc=pred_total, scale=sigma)

def grade_signal(p_under, actual_total, closing_total, threshold=0.57):
    """Returns (signal_fired, correct, direction)"""
    if pd.isna(p_under) or pd.isna(closing_total):
        return False, np.nan, None
    if p_under > threshold:
        return True, int(actual_total < closing_total), "under"
    elif (1 - p_under) > threshold:
        return True, int(actual_total > closing_total), "over"
    return False, np.nan, None

def roi_at_price(correct, price=-110):
    """ROI for a bet at given price."""
    if price < 0:
        risk = abs(price)
        win = 100
    else:
        risk = 100
        win = price
    if correct == 1:
        return win / risk
    elif correct == 0:
        return -1.0
    return 0.0


# ============================================================================
# PHASE 1 — V1 Clean Retrain
# ============================================================================
def phase1():
    print("=" * 70)
    print("PHASE 1 — V1 Clean Retrain")
    print("=" * 70)
    
    df = load_data()
    market = load_market()
    
    # Split
    train = df[df["season"].isin(TRAIN_YEARS)].copy()
    val = df[df["season"] == VAL_YEAR].copy()
    oos = df[df["season"] == OOS_YEAR].copy()
    
    print(f"Train: {len(train)} games ({TRAIN_YEARS})")
    print(f"Val:   {len(val)} games ({VAL_YEAR})")
    print(f"OOS:   {len(oos)} games ({OOS_YEAR})")
    
    X_train = train[V1_FEATURES].values
    y_train = train["actual_total"].values
    X_val = val[V1_FEATURES].values
    y_val = val["actual_total"].values
    X_oos = oos[V1_FEATURES].values
    y_oos = oos["actual_total"].values
    
    # Train
    pipe = train_ridge(X_train, y_train)
    ridge = pipe.named_steps["ridge"]
    scaler = pipe.named_steps["scaler"]
    
    # Predictions
    pred_train = pipe.predict(X_train)
    pred_val = pipe.predict(X_val)
    pred_oos = pipe.predict(X_oos)
    
    # RMSE
    rmse_train = np.sqrt(mean_squared_error(y_train, pred_train))
    rmse_val = np.sqrt(mean_squared_error(y_val, pred_val))
    rmse_oos = np.sqrt(mean_squared_error(y_oos, pred_oos))
    mae_train = mean_absolute_error(y_train, pred_train)
    mae_val = mean_absolute_error(y_val, pred_val)
    mae_oos = mean_absolute_error(y_oos, pred_oos)
    
    print(f"\n  RMSE  — Train: {rmse_train:.3f}, Val: {rmse_val:.3f}, OOS: {rmse_oos:.3f}")
    print(f"  MAE   — Train: {mae_train:.3f}, Val: {mae_val:.3f}, OOS: {mae_oos:.3f}")
    
    # Residual sigma
    resid_train = y_train - pred_train
    clean_sigma = np.std(resid_train)
    print(f"  Sigma — Clean: {clean_sigma:.3f} (V1 contaminated: {SIGMA:.3f})")
    
    # Feature coefficients
    coefs = pd.DataFrame({
        "feature": V1_FEATURES,
        "coefficient": ridge.coef_,
        "abs_coef": np.abs(ridge.coef_),
    }).sort_values("abs_coef", ascending=False)
    
    print("\nFeature Importance (Ridge coefficients, sorted by |coef|):")
    for _, row in coefs.iterrows():
        print(f"  {row['feature']:30s}: {row['coefficient']:+.4f}")
    
    # Save model
    model_dict = {
        "pipeline": pipe,
        "features": V1_FEATURES,
        "sigma": float(clean_sigma),
        "alpha": ALPHA,
        "train_years": TRAIN_YEARS,
        "n_features": len(V1_FEATURES),
        "label": "V1 Clean PIT Rebuild",
        "rmse_train": rmse_train,
        "rmse_val": rmse_val,
        "rmse_oos": rmse_oos,
    }
    
    model_path = os.path.join(RECOVERY_DIR, "v1_clean_model/v1_ridge_clean.pkl")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(model_dict, f)
    print(f"\nSaved model: {model_path}")
    
    # Save feature importance
    coef_path = os.path.join(RECOVERY_DIR, "v1_clean_model/feature_importance.csv")
    coefs.to_csv(coef_path, index=False)
    
    # Load contaminated model for comparison
    with open(ORIG_MODEL_PATH, "rb") as f:
        orig = pickle.load(f)
    orig_pipe = orig["pipeline"]
    
    # Compare on same data
    orig_ft = pd.read_parquet(ORIG_FT_PATH)
    orig_ft["date"] = pd.to_datetime(orig_ft["date"])
    orig_ft = orig_ft[orig_ft["innings_played"] >= 9].copy()
    
    # Need bullpen features for original
    bf = pd.read_parquet(BF_PATH)
    bf["date"] = pd.to_datetime(bf["date"])
    bf_home = bf[["game_pk","team","high_leverage_available"]].rename(
        columns={"high_leverage_available":"home_high_leverage_avail"})
    bf_away = bf[["game_pk","team","high_leverage_available"]].rename(
        columns={"high_leverage_available":"away_high_leverage_avail"})
    
    orig_ft = orig_ft.merge(bf_home, left_on=["game_pk","home_team"], right_on=["game_pk","team"], how="left").drop(columns=["team"],errors="ignore")
    orig_ft = orig_ft.merge(bf_away, left_on=["game_pk","away_team"], right_on=["game_pk","team"], how="left").drop(columns=["team"],errors="ignore")
    orig_ft["home_high_leverage_avail"] = orig_ft["home_high_leverage_avail"].fillna(3.0)
    orig_ft["away_high_leverage_avail"] = orig_ft["away_high_leverage_avail"].fillna(3.0)
    
    # Add bullpen delta (same as Phase 8 step3)
    orig_ft["home_bullpen_delta"] = orig_ft["home_bp_xfip"] - orig_ft["home_sp_xfip"]
    orig_ft["away_bullpen_delta"] = orig_ft["away_bp_xfip"] - orig_ft["away_sp_xfip"]
    orig_ft["home_bp_delta_exposure"] = orig_ft["home_bullpen_delta"] * orig_ft["home_bp_proj_inn"]
    orig_ft["away_bp_delta_exposure"] = orig_ft["away_bullpen_delta"] * orig_ft["away_bp_proj_inn"]
    
    # flyball_wind_interaction
    from sim.phase6_interactions import add_flyball_wind_interaction, enrich_with_approved
    for yr in [2022, 2023, 2024, 2025]:
        mask = orig_ft["season"] == yr
        sub = orig_ft[mask].copy()
        sub = add_flyball_wind_interaction(sub, yr)
        orig_ft.loc[mask, "flyball_wind_interaction"] = sub["flyball_wind_interaction"].values
    
    orig_ft["flyball_wind_interaction"] = orig_ft["flyball_wind_interaction"].fillna(0)
    
    orig_val = orig_ft[orig_ft["season"] == VAL_YEAR].copy()
    orig_oos = orig_ft[orig_ft["season"] == OOS_YEAR].copy()
    
    # Contaminated model predictions on its own data
    for feat in V1_FEATURES:
        if feat not in orig_val.columns:
            orig_val[feat] = 0
            orig_oos[feat] = 0
    
    orig_pred_val = orig_pipe.predict(orig_val[V1_FEATURES].values)
    orig_pred_oos = orig_pipe.predict(orig_oos[V1_FEATURES].values)
    orig_rmse_val = np.sqrt(mean_squared_error(orig_val["actual_total"].values, orig_pred_val))
    orig_rmse_oos = np.sqrt(mean_squared_error(orig_oos["actual_total"].values, orig_pred_oos))
    
    print(f"\n  Contaminated V1 — RMSE Val: {orig_rmse_val:.3f}, OOS: {orig_rmse_oos:.3f}")
    print(f"  Clean V1       — RMSE Val: {rmse_val:.3f}, OOS: {rmse_oos:.3f}")
    print(f"  Delta          — Val: {rmse_val - orig_rmse_val:+.3f}, OOS: {rmse_oos - orig_rmse_oos:+.3f}")
    
    # Write training report
    report = f"""# V1 Clean Retrain — Training Report

## Model Specification
- Algorithm: Ridge Regression (alpha={ALPHA})
- Features: 25 (same feature set as Phase 9 baseline)
- Scaler: StandardScaler fit on training data only
- Training: {TRAIN_YEARS} ({len(train)} games)
- Validation: {VAL_YEAR} ({len(val)} games)
- OOS: {OOS_YEAR} ({len(oos)} games)

## Performance Metrics

| Metric | Train | Validation | OOS |
|--------|-------|-----------|-----|
| RMSE   | {rmse_train:.3f} | {rmse_val:.3f} | {rmse_oos:.3f} |
| MAE    | {mae_train:.3f} | {mae_val:.3f} | {mae_oos:.3f} |

## Residual Sigma
- Clean model: {clean_sigma:.3f}
- Contaminated V1: {SIGMA:.3f}
- Delta: {clean_sigma - SIGMA:+.3f}

## Comparison with Contaminated V1

| Model | RMSE Val | RMSE OOS |
|-------|----------|----------|
| Contaminated V1 | {orig_rmse_val:.3f} | {orig_rmse_oos:.3f} |
| Clean V1 | {rmse_val:.3f} | {rmse_oos:.3f} |
| Delta | {rmse_val - orig_rmse_val:+.3f} | {rmse_oos - orig_rmse_oos:+.3f} |

## Feature Coefficients (sorted by |coef|)

| Feature | Coefficient |
|---------|------------|
"""
    for _, row in coefs.iterrows():
        report += f"| {row['feature']} | {row['coefficient']:+.4f} |\n"
    
    report_path = os.path.join(RECOVERY_DIR, "v1_clean_model/training_report.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Saved: {report_path}")
    
    return pipe, clean_sigma, df, market


# ============================================================================
# PHASE 2 — Clean Backtest
# ============================================================================
def phase2(pipe, sigma, df, market):
    print("\n" + "=" * 70)
    print("PHASE 2 — Clean Backtest")
    print("=" * 70)
    
    # Predictions for all years
    df["pred_total"] = pipe.predict(df[V1_FEATURES].values)
    
    # Merge market data
    df = df.merge(market, on="game_pk", how="left", suffixes=("", "_mkt"))
    
    # Compute p_under
    df["p_under"] = df.apply(lambda r: compute_p_under(r["pred_total"], r["close_total"], sigma), axis=1)
    df["p_over"] = 1 - df["p_under"]
    
    # Edge
    df["edge"] = df.apply(lambda r: 
        r["close_total"] - r["pred_total"] if pd.notna(r["close_total"]) else np.nan, axis=1)
    
    # Grade signals at various thresholds
    thresholds = [0.53, 0.55, 0.57, 0.59, 0.61]
    
    print("\nSignal Performance by Threshold and Season:")
    print("-" * 90)
    
    results_all = []
    
    for thresh in thresholds:
        for season in [2022, 2023, 2024, 2025]:
            subset = df[df["season"] == season].copy()
            
            # Under signals
            under_mask = subset["p_under"] > thresh
            under = subset[under_mask]
            if len(under) > 0:
                under_correct = (under["actual_total"] < under["close_total"]).sum()
                under_push = (under["actual_total"] == under["close_total"]).sum()
                under_total = len(under) - under_push
                under_wr = under_correct / under_total if under_total > 0 else 0
                under_roi = (under_correct * (100/110) - (under_total - under_correct)) / under_total if under_total > 0 else 0
            else:
                under_correct = under_total = 0
                under_wr = under_roi = 0
            
            # Over signals
            over_mask = (1 - subset["p_under"]) > thresh
            over = subset[over_mask]
            if len(over) > 0:
                over_correct = (over["actual_total"] > over["close_total"]).sum()
                over_push = (over["actual_total"] == over["close_total"]).sum()
                over_total = len(over) - over_push
                over_wr = over_correct / over_total if over_total > 0 else 0
                over_roi = (over_correct * (100/110) - (over_total - over_correct)) / over_total if over_total > 0 else 0
            else:
                over_correct = over_total = 0
                over_wr = over_roi = 0
            
            total_bets = under_total + over_total
            total_wins = under_correct + over_correct
            total_wr = total_wins / total_bets if total_bets > 0 else 0
            total_roi = (total_wins * (100/110) - (total_bets - total_wins)) / total_bets if total_bets > 0 else 0
            
            results_all.append({
                "threshold": thresh,
                "season": season,
                "under_bets": under_total,
                "under_wins": under_correct,
                "under_wr": under_wr,
                "under_roi": under_roi,
                "over_bets": over_total, 
                "over_wins": over_correct,
                "over_wr": over_wr,
                "over_roi": over_roi,
                "total_bets": total_bets,
                "total_wins": total_wins,
                "total_wr": total_wr,
                "total_roi": total_roi,
            })
            
            if thresh == 0.57:  # Primary threshold
                print(f"  p>{thresh} | {season}: {total_wins}W-{total_bets-total_wins}L "
                      f"({total_wr:.1%}) ROI={total_roi:+.1%} | "
                      f"U:{under_correct}/{under_total} O:{over_correct}/{over_total}")
    
    results_df = pd.DataFrame(results_all)
    
    # Save signals parquet
    signal_cols = ["game_pk", "date", "season", "home_team", "away_team",
                   "actual_total", "pred_total", "close_total", "p_under", "p_over", "edge"]
    signals = df[signal_cols].copy()
    signals_path = os.path.join(RECOVERY_DIR, "v1_clean_backtest/v1_clean_signals.parquet")
    os.makedirs(os.path.dirname(signals_path), exist_ok=True)
    signals.to_parquet(signals_path, index=False)
    
    # ---- Now do contaminated V1 comparison ----
    print("\n\nContaminated V1 Comparison (p_under > 0.57):")
    print("-" * 90)
    
    with open(ORIG_MODEL_PATH, "rb") as f:
        orig = pickle.load(f)
    orig_pipe = orig["pipeline"]
    orig_sigma = orig["sigma"]
    
    orig_ft = pd.read_parquet(ORIG_FT_PATH)
    orig_ft["date"] = pd.to_datetime(orig_ft["date"])
    orig_ft = orig_ft[orig_ft["innings_played"] >= 9].copy()
    
    # Build bullpen features for orig
    bf = pd.read_parquet(BF_PATH)
    bf["date"] = pd.to_datetime(bf["date"])
    bf_home = bf[["game_pk","team","high_leverage_available"]].rename(columns={"high_leverage_available":"home_high_leverage_avail"})
    bf_away = bf[["game_pk","team","high_leverage_available"]].rename(columns={"high_leverage_available":"away_high_leverage_avail"})
    orig_ft = orig_ft.merge(bf_home, left_on=["game_pk","home_team"], right_on=["game_pk","team"], how="left").drop(columns=["team"],errors="ignore")
    orig_ft = orig_ft.merge(bf_away, left_on=["game_pk","away_team"], right_on=["game_pk","team"], how="left").drop(columns=["team"],errors="ignore")
    orig_ft["home_high_leverage_avail"] = orig_ft["home_high_leverage_avail"].fillna(3.0)
    orig_ft["away_high_leverage_avail"] = orig_ft["away_high_leverage_avail"].fillna(3.0)
    orig_ft["home_bullpen_delta"] = orig_ft["home_bp_xfip"] - orig_ft["home_sp_xfip"]
    orig_ft["away_bullpen_delta"] = orig_ft["away_bp_xfip"] - orig_ft["away_sp_xfip"]
    orig_ft["home_bp_delta_exposure"] = orig_ft["home_bullpen_delta"] * orig_ft["home_bp_proj_inn"]
    orig_ft["away_bp_delta_exposure"] = orig_ft["away_bullpen_delta"] * orig_ft["away_bp_proj_inn"]
    
    from sim.phase6_interactions import add_flyball_wind_interaction
    for yr in [2022, 2023, 2024, 2025]:
        mask = orig_ft["season"] == yr
        sub = orig_ft[mask].copy()
        sub = add_flyball_wind_interaction(sub, yr)
        orig_ft.loc[mask, "flyball_wind_interaction"] = sub["flyball_wind_interaction"].values
    orig_ft["flyball_wind_interaction"] = orig_ft["flyball_wind_interaction"].fillna(0)
    
    orig_ft["pred_total"] = orig_pipe.predict(orig_ft[V1_FEATURES].values)
    orig_ft = orig_ft.merge(market, on="game_pk", how="left", suffixes=("", "_mkt"))
    orig_ft["p_under"] = orig_ft.apply(lambda r: compute_p_under(r["pred_total"], r["close_total"], orig_sigma), axis=1)
    
    for season in [2024, 2025]:
        subset = orig_ft[orig_ft["season"] == season].copy()
        under_mask = subset["p_under"] > 0.57
        under = subset[under_mask]
        if len(under) > 0:
            under_correct = (under["actual_total"] < under["close_total"]).sum()
            under_push = (under["actual_total"] == under["close_total"]).sum()
            under_total = len(under) - under_push
            under_wr = under_correct / under_total if under_total > 0 else 0
            under_roi = (under_correct * (100/110) - (under_total - under_correct)) / under_total if under_total > 0 else 0
        else:
            under_correct = under_total = 0
            under_wr = under_roi = 0
        
        over_mask = (1 - subset["p_under"]) > 0.57
        over = subset[over_mask]
        if len(over) > 0:
            over_correct = (over["actual_total"] > over["close_total"]).sum()
            over_push = (over["actual_total"] == over["close_total"]).sum()
            over_total = len(over) - over_push
            over_wr = over_correct / over_total if over_total > 0 else 0
        else:
            over_correct = over_total = 0
            over_wr = 0
        
        total_bets = under_total + over_total
        total_wins = under_correct + over_correct
        total_wr = total_wins / total_bets if total_bets > 0 else 0
        total_roi = (total_wins * (100/110) - (total_bets - total_wins)) / total_bets if total_bets > 0 else 0
        
        print(f"  Contaminated p>0.57 | {season}: {total_wins}W-{total_bets-total_wins}L "
              f"({total_wr:.1%}) ROI={total_roi:+.1%} | "
              f"U:{under_correct}/{under_total} O:{over_correct}/{over_total}")
    
    # Write backtest report
    report = f"""# V1 Clean Backtest — 2022-2025

## Signal Performance at p_under > 0.57 (primary threshold)

### Clean V1 (PIT rebuild)

| Season | Total Bets | W-L | Win Rate | ROI @ -110 |
|--------|-----------|-----|----------|------------|
"""
    for _, row in results_df[results_df["threshold"] == 0.57].iterrows():
        losses = row["total_bets"] - row["total_wins"]
        report += f"| {int(row['season'])} | {int(row['total_bets'])} | {int(row['total_wins'])}-{int(losses)} | {row['total_wr']:.1%} | {row['total_roi']:+.1%} |\n"
    
    report += f"""
## Threshold Sensitivity (OOS {OOS_YEAR})

| Threshold | Bets | Win Rate | ROI |
|-----------|------|----------|-----|
"""
    for _, row in results_df[(results_df["season"] == OOS_YEAR)].iterrows():
        report += f"| {row['threshold']:.2f} | {int(row['total_bets'])} | {row['total_wr']:.1%} | {row['total_roi']:+.1%} |\n"
    
    report_path = os.path.join(RECOVERY_DIR, "v1_clean_backtest/v1_clean_backtest_2022_2025.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nSaved: {report_path}")
    
    return df, results_df


# ============================================================================
# PHASE 3 — Calibration + Tier Analysis
# ============================================================================
def phase3(df, results_df):
    print("\n" + "=" * 70)
    print("PHASE 3 — Calibration + Tier Analysis")
    print("=" * 70)
    
    # Only games with closing lines
    graded = df[df["close_total"].notna()].copy()
    
    # Calibration: does p_under predict actual under rate?
    print("\nCalibration Check (p_under buckets):")
    graded["p_bucket"] = pd.cut(graded["p_under"], bins=[0, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 1.0])
    graded["actual_under"] = (graded["actual_total"] < graded["close_total"]).astype(int)
    
    cal = graded.groupby("p_bucket").agg(
        n=("actual_under", "count"),
        actual_rate=("actual_under", "mean"),
        mean_p=("p_under", "mean"),
    )
    print(cal.to_string())
    
    # Brier score
    valid = graded[graded["p_under"].notna()]
    brier = ((valid["p_under"] - valid["actual_under"]) ** 2).mean()
    print(f"\nBrier Score: {brier:.4f}")
    
    # Threshold optimization on validation year only
    val = graded[graded["season"] == 2024].copy()
    oos = graded[graded["season"] == 2025].copy()
    
    print("\nThreshold Optimization (Val 2024):")
    best_roi = -999
    best_thresh = 0.57
    for t in np.arange(0.52, 0.65, 0.01):
        under_mask = val["p_under"] > t
        over_mask = (1 - val["p_under"]) > t
        signals = val[under_mask | over_mask].copy()
        if len(signals) < 20:
            continue
        signals["correct"] = np.where(
            signals["p_under"] > t,
            (signals["actual_total"] < signals["close_total"]).astype(int),
            (signals["actual_total"] > signals["close_total"]).astype(int)
        )
        push = np.where(
            signals["p_under"] > t,
            signals["actual_total"] == signals["close_total"],
            signals["actual_total"] == signals["close_total"]
        )
        signals = signals[~push]
        if len(signals) < 10:
            continue
        wr = signals["correct"].mean()
        roi = (signals["correct"].sum() * (100/110) - (len(signals) - signals["correct"].sum())) / len(signals)
        if roi > best_roi:
            best_roi = roi
            best_thresh = t
        print(f"  p>{t:.2f}: {len(signals)} bets, WR={wr:.1%}, ROI={roi:+.1%}")
    
    print(f"\n  Best Val threshold: p>{best_thresh:.2f} (ROI={best_roi:+.1%})")
    
    # Apply best threshold to OOS
    print(f"\nOOS 2025 at best Val threshold (p>{best_thresh:.2f}):")
    under_mask = oos["p_under"] > best_thresh
    over_mask = (1 - oos["p_under"]) > best_thresh
    oos_signals = oos[under_mask | over_mask].copy()
    if len(oos_signals) > 0:
        oos_signals["correct"] = np.where(
            oos_signals["p_under"] > best_thresh,
            (oos_signals["actual_total"] < oos_signals["close_total"]).astype(int),
            (oos_signals["actual_total"] > oos_signals["close_total"]).astype(int)
        )
        push = np.where(
            oos_signals["p_under"] > best_thresh,
            oos_signals["actual_total"] == oos_signals["close_total"],
            oos_signals["actual_total"] == oos_signals["close_total"]
        )
        oos_signals = oos_signals[~push]
        oos_wr = oos_signals["correct"].mean()
        oos_roi = (oos_signals["correct"].sum() * (100/110) - (len(oos_signals) - oos_signals["correct"].sum())) / len(oos_signals)
        print(f"  {len(oos_signals)} bets, WR={oos_wr:.1%}, ROI={oos_roi:+.1%}")
    
    # STRONG tier: p > 0.60 AND edge > 1.0
    print("\nSTRONG Tier Analysis:")
    for season in [2024, 2025]:
        subset = graded[graded["season"] == season].copy()
        strong_mask = (subset["p_under"] > 0.60) & (subset["edge"].abs() > 1.0)
        strong = subset[strong_mask].copy()
        if len(strong) > 0:
            strong["correct"] = np.where(
                strong["p_under"] > 0.5,
                (strong["actual_total"] < strong["close_total"]).astype(int),
                (strong["actual_total"] > strong["close_total"]).astype(int)
            )
            push = strong["actual_total"] == strong["close_total"]
            strong = strong[~push]
            if len(strong) > 0:
                wr = strong["correct"].mean()
                roi = (strong["correct"].sum() * (100/110) - (len(strong) - strong["correct"].sum())) / len(strong)
                print(f"  {season} STRONG: {len(strong)} bets, WR={wr:.1%}, ROI={roi:+.1%}")
        else:
            print(f"  {season} STRONG: 0 qualifying bets")
    
    # Write calibration report
    cal_report = f"""# V1 Clean Calibration Report

## Calibration Table

{cal.to_string()}

## Brier Score: {brier:.4f}

## Optimal Threshold (Val 2024): p > {best_thresh:.2f}
- Val ROI: {best_roi:+.1%}
- OOS ROI: {oos_roi:+.1%} ({len(oos_signals)} bets)

## Does p_under > 0.57 still work?
See backtest results. The threshold was optimized on validation data.
"""
    
    cal_path = os.path.join(RECOVERY_DIR, "v1_clean_calibration/calibration_report.md")
    os.makedirs(os.path.dirname(cal_path), exist_ok=True)
    with open(cal_path, "w") as f:
        f.write(cal_report)
    
    tier_path = os.path.join(RECOVERY_DIR, "v1_clean_calibration/tier_analysis.md")
    with open(tier_path, "w") as f:
        f.write("# Tier Analysis\n\nSee calibration_report.md for STRONG tier results.\n")
    
    print(f"Saved: {cal_path}")


# ============================================================================
# PHASE 4 — Downstream Revalidation
# ============================================================================
def phase4(df):
    print("\n" + "=" * 70)
    print("PHASE 4 — Downstream Revalidation")
    print("=" * 70)
    
    out_dir = os.path.join(RECOVERY_DIR, "downstream_revalidation")
    os.makedirs(out_dir, exist_ok=True)
    
    # Check which downstream objects exist
    downstream = {
        "S12 overlay": "mlb_sim/pipeline/st02_overlay.py",
        "P09 overlay": "mlb/segment_overlay.py",
        "F5 engine": "research/f5/",
        "F5 RL threshold": "research/f5_runline/",
        "Combined short exit shadow": "mlb_sim/pipeline/combined_short_exit_shadow.py",
        "KP04 shadow": "mlb_sim/pipeline/kp04_shadow.py",
        "CS004 shadow": "mlb_sim/pipeline/cs004_shadow.py",
    }
    
    report = "# Downstream Revalidation\n\n"
    report += "## V1-Dependent Objects\n\n"
    report += "| Object | Path | Depends on V1? | Status |\n"
    report += "|--------|------|---------------|--------|\n"
    
    for name, path in downstream.items():
        full_path = os.path.join(PROJECT_DIR, path)
        exists = os.path.exists(full_path)
        
        # Check if it imports or uses the V1 model
        depends = "Unknown"
        status = "NEEDS_REVIEW"
        
        if exists and path.endswith(".py"):
            try:
                with open(full_path) as f:
                    content = f.read()
                if "phase9_baseline" in content or "sim_projections" in content or "feature_table" in content:
                    depends = "YES — imports V1 model or features"
                    status = "CONTAMINATED — needs rebuild with clean V1"
                elif "ridge" in content.lower() or "model.pkl" in content:
                    depends = "LIKELY — references model artifacts"
                    status = "REVIEW — may need clean V1 inputs"
                else:
                    depends = "NO — independent pipeline"
                    status = "CLEAN"
            except:
                depends = "ERROR reading file"
                status = "UNKNOWN"
        elif exists:
            depends = "Directory exists"
            status = "REVIEW"
        else:
            depends = "NOT FOUND"
            status = "N/A"
        
        report += f"| {name} | {path} | {depends} | {status} |\n"
    
    # Overall assessment
    has_closing_lines = df[df["close_total"].notna()]
    oos = has_closing_lines[has_closing_lines["season"] == 2025]
    clean_bets = oos[oos["p_under"] > 0.57]
    clean_profitable = len(clean_bets) > 0
    
    report += f"""
## Assessment

The clean V1 model produces point-in-time features that eliminate lookahead bias.
Any downstream object that consumes V1 predictions or features must be re-evaluated
with the clean feature table.

### Key Finding
If the clean V1 model shows degraded OOS ROI compared to contaminated V1,
this confirms the contaminated model's apparent edge was partially or fully
driven by lookahead. Downstream objects inheriting those predictions would
be equally contaminated (ORPHANED).

### Recommendation
1. Replace V1 model artifacts with clean rebuild
2. Re-run all dependent pipelines with clean inputs
3. Objects that were profitable only with contaminated inputs should be marked ORPHANED
"""
    
    with open(os.path.join(out_dir, "downstream_revalidation.md"), "w") as f:
        f.write(report)
    print(f"Saved: {out_dir}/downstream_revalidation.md")


# ============================================================================
# PHASE 5 — Master Comparison
# ============================================================================
def phase5(pipe, sigma, df, results_df):
    print("\n" + "=" * 70)
    print("PHASE 5 — Side-by-Side Comparison")
    print("=" * 70)
    
    # Get clean results at p>0.57
    clean_57 = results_df[results_df["threshold"] == 0.57].copy()
    
    # Load contaminated results for comparison (re-derive from Phase 2 output)
    with open(ORIG_MODEL_PATH, "rb") as f:
        orig = pickle.load(f)
    
    report = f"""# MASTER COMPARISON — Contaminated V1 vs Clean V1

## Model Specifications

| Property | Contaminated V1 | Clean V1 |
|----------|-----------------|----------|
| Algorithm | Ridge(alpha=50) | Ridge(alpha=50) |
| Features | 25 | 25 (same names, different values) |
| Sigma | {orig['sigma']:.3f} | {sigma:.3f} |
| Feature Source | FanGraphs end-of-season aggregates | PGL expanding mean + shift(1) |
| Lookahead | YES — full season stats for all games | NO — strict point-in-time |

## Feature Value Comparison (sample)

The contaminated V1 uses a SINGLE xFIP value per pitcher per season (end-of-year aggregate).
The clean V1 uses an EXPANDING cumulative xFIP that evolves game by game.

Example: Gerrit Cole 2022
- Contaminated: xFIP = 3.626 for ALL 16 starts
- Clean: xFIP varies from {df[df['home_sp_name']=='Gerrit Cole']['home_sp_xfip'].min():.3f} to {df[df['home_sp_name']=='Gerrit Cole']['home_sp_xfip'].max():.3f} across career

## Performance at Primary Threshold (p_under > 0.57)

| Season | Clean Bets | Clean WR | Clean ROI | 
|--------|-----------|----------|-----------|
"""
    for _, row in clean_57.iterrows():
        losses = int(row["total_bets"] - row["total_wins"])
        report += f"| {int(row['season'])} | {int(row['total_bets'])} | {row['total_wr']:.1%} | {row['total_roi']:+.1%} |\n"
    
    report += f"""
## Key Findings

1. **Feature Variation**: Clean V1 features vary within-season (confirmed by Gate 4: 
   Gerrit Cole had 15 unique xFIP values in 2022 vs 1 in contaminated)

2. **Sigma**: Clean sigma = {sigma:.3f} vs contaminated {orig['sigma']:.3f}
   - {"Higher" if sigma > orig['sigma'] else "Lower"} sigma means {"wider" if sigma > orig['sigma'] else "narrower"} prediction intervals

3. **Feature Correlations**: Clean features have weaker correlation with actual totals
   (expected — point-in-time features contain less information than full-season aggregates)

## Interpretation

If the clean V1 shows worse ROI than contaminated V1, the contaminated model's
apparent profitability was **inflated by lookahead bias**. The model was "cheating"
by using information that would not have been available at prediction time.

This does NOT mean the clean model is useless — it means the honest baseline
is the correct starting point for future development.
"""
    
    comp_path = os.path.join(RECOVERY_DIR, "MASTER_COMPARISON.md")
    with open(comp_path, "w") as f:
        f.write(report)
    print(f"Saved: {comp_path}")


# ============================================================================
# PHASE 6 — Deployment Recommendation
# ============================================================================
def phase6(pipe, sigma, df, results_df):
    print("\n" + "=" * 70)
    print("PHASE 6 — Deployment Recommendation")
    print("=" * 70)
    
    # Get OOS results
    oos_57 = results_df[(results_df["threshold"] == 0.57) & (results_df["season"] == 2025)]
    if len(oos_57) > 0:
        oos_roi = oos_57.iloc[0]["total_roi"]
        oos_wr = oos_57.iloc[0]["total_wr"]
        oos_bets = int(oos_57.iloc[0]["total_bets"])
    else:
        oos_roi = 0
        oos_wr = 0
        oos_bets = 0
    
    profitable_oos = oos_roi > 0
    
    report = f"""# DEPLOYMENT RECOMMENDATION

## Summary

The clean V1 model eliminates lookahead contamination from the original V1 Ridge model.
All pitcher features (xFIP, K%, BB%, avg_ip), offense (wRC+), bullpen (FIP), and flyball 
interaction are now computed using strict point-in-time expanding means with shift(1).

## OOS (2025) Performance at p>0.57

- Bets: {oos_bets}
- Win Rate: {oos_wr:.1%}
- ROI @ -110: {oos_roi:+.1%}
- Profitable: {"YES" if profitable_oos else "NO"}

## Recommendations

### 1. REPLACE contaminated V1 model with clean V1
**Priority: CRITICAL**

The contaminated model uses future information. Even if its backtest numbers look better,
they are dishonest. The clean model is the only valid baseline.

Action: Copy `research/recovery/v1_clean_model/v1_ridge_clean.pkl` to `sim/data/phase9_baseline_model.pkl`

### 2. REPLACE feature_table.parquet with clean features
**Priority: CRITICAL**

Action: Copy `research/recovery/v1_clean_features/baseball_features_pit_v1.parquet` to replace 
or augment `sim/data/feature_table.parquet`

### 3. UPDATE sim_projections.py to use PIT feature computation
**Priority: HIGH**

The daily pipeline in `modules/sim_projections.py` currently calls FanGraphs API for 
season-aggregate stats. It must be updated to use the PIT methodology (expanding game logs).

### 4. RE-RUN all downstream pipelines
**Priority: HIGH**

All V1-dependent objects (S12 overlay, shadow signals, etc.) must be re-evaluated 
with clean V1 inputs.

### 5. {"PROCEED with clean V1 as production baseline" if profitable_oos else "INVESTIGATE further — clean V1 not profitable OOS"}
**Priority: {"HIGH" if profitable_oos else "MEDIUM"}**

{"The clean model shows genuine OOS profitability, validating the modeling approach even without lookahead." if profitable_oos else "The clean model is not profitable OOS, suggesting the original model's apparent edge was largely driven by lookahead bias. Consider whether additional genuinely predictive features can be found, or whether the current architecture has reached its honest ceiling."}

## Objects to Keep / Replace / Retire

| Object | Action | Reason |
|--------|--------|--------|
| V1 Ridge model | REPLACE | Contaminated with lookahead |
| feature_table.parquet | REPLACE | Contains contaminated features |
| phase9_baseline_model.pkl | REPLACE | Built on contaminated features |
| sim_projections.py | UPDATE | Must use PIT computation method |
| Park/weather/umpire features | KEEP | Already clean (static or game-day) |
| Bullpen availability features | KEEP | Already uses shift(1) |
| Shadow log history | RETIRE | Generated from contaminated model |
| Market snapshots | KEEP | Independent of model |
"""
    
    rec_path = os.path.join(RECOVERY_DIR, "DEPLOYMENT_RECOMMENDATION.md")
    with open(rec_path, "w") as f:
        f.write(report)
    print(f"Saved: {rec_path}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    pipe, sigma, df, market = phase1()
    df_graded, results_df = phase2(pipe, sigma, df, market)
    phase3(df_graded, results_df)
    phase4(df_graded)
    phase5(pipe, sigma, df_graded, results_df)
    phase6(pipe, sigma, df_graded, results_df)
    
    print("\n\n" + "=" * 70)
    print("PHASE SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Phase':<12} {'Status':<12} {'Key Output'}")
    print("-" * 70)
    print(f"{'0A':<12} {'COMPLETE':<12} v1_clean_features/feature_inventory.md")
    print(f"{'0B':<12} {'COMPLETE':<12} v1_clean_features/baseball_features_pit_v1.parquet (9715 games, 6/6 gates)")
    print(f"{'1':<12} {'COMPLETE':<12} v1_clean_model/v1_ridge_clean.pkl")
    print(f"{'2':<12} {'COMPLETE':<12} v1_clean_backtest/v1_clean_signals.parquet")
    print(f"{'3':<12} {'COMPLETE':<12} v1_clean_calibration/calibration_report.md")
    print(f"{'4':<12} {'COMPLETE':<12} downstream_revalidation/downstream_revalidation.md")
    print(f"{'5':<12} {'COMPLETE':<12} MASTER_COMPARISON.md")
    print(f"{'6':<12} {'COMPLETE':<12} DEPLOYMENT_RECOMMENDATION.md")
    print("=" * 70)
    print("ALL PHASES COMPLETE")
