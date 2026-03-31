"""
phase3_ridge_baseline.py — Ridge regression baseline for MLB totals.

Loads feature_table.parquet, selects the Phase 3 feature set (excluding
collinear/zero-variance columns documented in Phase 2), fits a RidgeCV model
with leave-one-year-out cross-validation, and produces a backtest report.

Feature set (Phase 3 V1):
  SP quality (per side):      xfip
  SP shape  (per side):       k_pct, bb_pct, avg_ip
  Offense   (per side):       wrc_plus  (platoon-split)
  Park + environment:         park_factor_runs, park_factor_hr, temperature
  Wind:                       wind_factor_effective
  Umpire:                     umpire_over_rate
  Rest / schedule:            home_rest_days, away_rest_days, doubleheader_flag

Excluded (collinear or zero-variance in Phase 2):
  siera     — perfect r=1.00 with xfip (Savant xERA proxy for both)
  bp_interaction — r=0.995 with avg_ip (bullpen quality = league avg)
  k_pct     — r≈0.71 with xfip; kept despite moderate collinearity
  tto_flag  — redundant with avg_ip

Target: actual_total (full-game runs, integer)

Output:
  sim/data/phase3_ridge_model.pkl    — fitted Ridge + preprocessing pipeline
  sim/data/phase3_backtest_report.txt
"""

import logging
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

SIM_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SIM_DIR)
sys.path.insert(0, PROJECT_DIR)

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("phase3")

FEATURE_TABLE_PATH = os.path.join(SIM_DIR, "data", "feature_table.parquet")
MODEL_PATH         = os.path.join(SIM_DIR, "data", "phase3_ridge_model.pkl")
REPORT_PATH        = os.path.join(SIM_DIR, "data", "phase3_backtest_report.txt")

SEASONS = [2022, 2023, 2024]

# ---------------------------------------------------------------------------
# Feature set definition
# ---------------------------------------------------------------------------

SP_FEATURES = [
    "home_sp_xfip",  "away_sp_xfip",
    "home_sp_k_pct", "away_sp_k_pct",
    "home_sp_bb_pct","away_sp_bb_pct",
    "home_sp_avg_ip","away_sp_avg_ip",
]
OFFENSE_FEATURES = [
    "home_wrc_plus", "away_wrc_plus",
]
ENV_FEATURES = [
    "park_factor_runs",
    "park_factor_hr",
    "temperature",
    "wind_factor_effective",
    "umpire_over_rate",
    "home_rest_days",
    "away_rest_days",
    "doubleheader_flag",
]

ALL_FEATURES = SP_FEATURES + OFFENSE_FEATURES + ENV_FEATURES
TARGET = "actual_total"


# ---------------------------------------------------------------------------
# Data prep
# ---------------------------------------------------------------------------

def load_and_prepare(feature_table_path: str) -> pd.DataFrame:
    df = pd.read_parquet(feature_table_path)
    logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} cols")

    # Require all feature columns and target
    needed = ALL_FEATURES + [TARGET, "season", "date", "game_pk",
                             "actual_f5_total", "home_team", "away_team"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        logger.error(f"Missing columns: {missing}")
        sys.exit(1)

    # Drop rows where target is null (incomplete games shouldn't be in table,
    # but guard anyway)
    before = len(df)
    df = df.dropna(subset=[TARGET])
    if len(df) < before:
        logger.warning(f"Dropped {before - len(df)} rows with null actual_total")

    # Fill remaining feature nulls with column median (best conservative estimate)
    for col in ALL_FEATURES:
        if df[col].isna().any():
            med = df[col].median()
            n   = df[col].isna().sum()
            df[col] = df[col].fillna(med)
            logger.info(f"  Filled {n} nulls in {col} with median {med:.3f}")

    # Convert boolean columns to int
    df["doubleheader_flag"] = df["doubleheader_flag"].astype(int)

    return df


# ---------------------------------------------------------------------------
# Leave-one-year-out cross-validation
# ---------------------------------------------------------------------------

def loyo_cv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Leave-one-year-out CV: train on 2 seasons, predict the held-out season.
    Returns a DataFrame with predictions + actuals for all 3 seasons.
    """
    alphas = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    result_dfs = []

    for held_year in SEASONS:
        train_mask = df["season"] != held_year
        test_mask  = df["season"] == held_year

        X_train = df.loc[train_mask, ALL_FEATURES].values
        y_train = df.loc[train_mask, TARGET].values
        X_test  = df.loc[test_mask,  ALL_FEATURES].values

        # Fit ridge with internal CV over alpha on training data
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("ridge",  RidgeCV(alphas=alphas, cv=5)),
        ])
        pipe.fit(X_train, y_train)

        best_alpha = pipe.named_steps["ridge"].alpha_
        logger.info(f"  Held out {held_year}: train={train_mask.sum():,}, "
                    f"test={test_mask.sum():,}, best alpha={best_alpha:.2f}")

        preds = pipe.predict(X_test)

        fold_df = df.loc[test_mask, ["game_pk", "date", "season", "home_team",
                                      "away_team", TARGET, "actual_f5_total"]].copy()
        fold_df["pred_total"] = preds
        fold_df["residual"]   = fold_df[TARGET] - preds
        result_dfs.append(fold_df)

    return pd.concat(result_dfs, ignore_index=True).sort_values("date")


# ---------------------------------------------------------------------------
# Final model (trained on all 3 seasons)
# ---------------------------------------------------------------------------

def fit_final_model(df: pd.DataFrame) -> Pipeline:
    alphas = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    X = df[ALL_FEATURES].values
    y = df[TARGET].values

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  RidgeCV(alphas=alphas, cv=5)),
    ])
    pipe.fit(X, y)
    logger.info(f"Final model: alpha={pipe.named_steps['ridge'].alpha_:.2f}, "
                f"intercept={pipe.named_steps['ridge'].intercept_:.3f}")
    return pipe


# ---------------------------------------------------------------------------
# Backtest report
# ---------------------------------------------------------------------------

def print_backtest_report(cv_df: pd.DataFrame, pipe: Pipeline,
                          df: pd.DataFrame) -> None:
    report_lines: list[str] = []

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    actual = cv_df[TARGET].values
    pred   = cv_df["pred_total"].values
    resid  = cv_df["residual"].values

    mae  = mean_absolute_error(actual, pred)
    rmse = np.sqrt(mean_squared_error(actual, pred))
    corr = np.corrcoef(actual, pred)[0, 1]
    bias = resid.mean()

    line("=" * 70)
    line("PHASE 3 RIDGE REGRESSION — BACKTEST REPORT")
    line("=" * 70)
    line()
    line("Leave-one-year-out cross-validation (2022–2024)")
    line(f"  Games evaluated:  {len(cv_df):,}")
    line()
    line("Overall metrics:")
    line(f"  MAE:              {mae:.4f} runs")
    line(f"  RMSE:             {rmse:.4f} runs")
    line(f"  Pearson r:        {corr:.4f}")
    line(f"  Bias (mean err):  {bias:+.4f} runs")
    line()

    # Per-season metrics
    line("─" * 70)
    line("Per-season metrics:")
    line(f"  {'Season':<8}  {'N':>5}  {'MAE':>7}  {'RMSE':>7}  {'r':>7}  {'Bias':>7}")
    line(f"  {'─'*8}  {'─'*5}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*7}")
    for yr in SEASONS:
        s    = cv_df[cv_df["season"] == yr]
        a    = s[TARGET].values
        p    = s["pred_total"].values
        mae_y  = mean_absolute_error(a, p)
        rmse_y = np.sqrt(mean_squared_error(a, p))
        r_y    = np.corrcoef(a, p)[0, 1]
        bias_y = (a - p).mean()
        line(f"  {int(yr):<8}  {len(s):>5,}  {mae_y:>7.4f}  {rmse_y:>7.4f}  "
             f"{r_y:>7.4f}  {bias_y:>+7.4f}")

    # Prediction distribution
    line()
    line("─" * 70)
    line("Prediction distribution:")
    line(f"  {'':20}  {'Pred':>8}  {'Actual':>8}")
    line(f"  {'Mean':20}  {pred.mean():>8.3f}  {actual.mean():>8.3f}")
    line(f"  {'Std':20}  {pred.std():>8.3f}  {actual.std():>8.3f}")
    line(f"  {'Min':20}  {pred.min():>8.3f}  {actual.min():>8.3f}")
    line(f"  {'Max':20}  {pred.max():>8.3f}  {actual.max():>8.3f}")
    line(f"  {'<7 runs':20}  {(pred < 7).sum():>8,}  {(actual < 7).sum():>8,}")
    line(f"  {'7–9 runs':20}  {((pred >= 7) & (pred < 9.5)).sum():>8,}  "
         f"{((actual >= 7) & (actual < 9.5)).sum():>8,}")
    line(f"  {'>9 runs':20}  {(pred >= 9.5).sum():>8,}  {(actual >= 9.5).sum():>8,}")

    # Feature coefficients (from final model)
    line()
    line("─" * 70)
    line("Feature coefficients (final model, standardized scale):")
    scaler = pipe.named_steps["scaler"]
    ridge  = pipe.named_steps["ridge"]
    coefs  = ridge.coef_
    # Unstandardized: coef / scale
    raw_coefs = coefs / scaler.scale_

    coef_df = pd.DataFrame({
        "feature": ALL_FEATURES,
        "coef_std":   coefs,
        "coef_raw":   raw_coefs,
    }).sort_values("coef_std", key=abs, ascending=False)

    line(f"  {'Feature':<30}  {'Coef (std)':>12}  {'Coef (raw)':>12}")
    line(f"  {'─'*30}  {'─'*12}  {'─'*12}")
    for _, row in coef_df.iterrows():
        line(f"  {row['feature']:<30}  {row['coef_std']:>+12.4f}  "
             f"{row['coef_raw']:>+12.4f}")

    # Residual analysis
    line()
    line("─" * 70)
    line("Residual analysis (actual − predicted):")
    line(f"  Mean:    {resid.mean():+.4f}")
    line(f"  Std:     {resid.std():.4f}")
    line(f"  P25:     {np.percentile(resid, 25):+.3f}")
    line(f"  P75:     {np.percentile(resid, 75):+.3f}")
    line(f"  P5:      {np.percentile(resid, 5):+.3f}")
    line(f"  P95:     {np.percentile(resid, 95):+.3f}")
    line()

    # Worst prediction errors
    line("─" * 70)
    line("10 largest prediction errors (|actual − predicted|):")
    cv_df_copy = cv_df.copy()
    cv_df_copy["abs_err"] = cv_df_copy["residual"].abs()
    worst = cv_df_copy.nlargest(10, "abs_err")
    line(f"  {'Date':<12}  {'Home':<5}  {'Away':<5}  "
         f"{'Actual':>7}  {'Pred':>7}  {'Error':>7}")
    for _, r in worst.iterrows():
        line(f"  {str(r['date'])[:10]:<12}  {r['home_team']:<5}  {r['away_team']:<5}  "
             f"{r[TARGET]:>7.1f}  {r['pred_total']:>7.3f}  {r['residual']:>+7.3f}")

    line()
    line("=" * 70)
    line()
    line("Known limitations (Phase 2 data quality):")
    line("  • Pitcher xERA from Savant (FanGraphs blocked) → xFIP = SIERA identical")
    line("  • Full-season pitcher/offense stats used for all games (mild data leakage)")
    line("  • Bullpen quality = league average (GS-based reliever ID requires FanGraphs)")
    line("  • wRC+ from Savant xwOBA proxy, not FanGraphs PA-weighted (bias possible)")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))
    logger.info(f"Report saved: {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logger.info("Loading feature table...")
    df = load_and_prepare(FEATURE_TABLE_PATH)

    logger.info(f"Feature set: {len(ALL_FEATURES)} features × {len(df):,} games")
    logger.info("Running leave-one-year-out cross-validation...")
    cv_df = loyo_cv(df)

    logger.info("Fitting final model on all 3 seasons...")
    final_pipe = fit_final_model(df)

    logger.info("Saving final model...")
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({
            "pipeline":    final_pipe,
            "features":    ALL_FEATURES,
            "target":      TARGET,
            "seasons":     SEASONS,
            "n_train":     len(df),
        }, f)
    logger.info(f"Saved: {MODEL_PATH}")

    print_backtest_report(cv_df, final_pipe, df)


if __name__ == "__main__":
    main()
