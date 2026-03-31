"""
phase3_ridge_baseline_v2.py — Tightened Phase 3 Ridge Regression Baseline

Changes from v1:
  1. Primary evaluation protocol: train=2022+2023, validate=2024.
     LOYO (leave-one-year-out) cross-validation kept as a supplemental diagnostic.
  2. Alpha grid expanded to [0.01 … 1000] to prevent hitting the ceiling.
  3. Honest feature labels in all output: team offense features are Savant
     xwOBA-derived proxies, NOT FanGraphs wRC+.  Pitcher quality features are
     Savant xERA-derived proxies, NOT FanGraphs xFIP.

Output:
  sim/data/phase3_ridge_model_v2.pkl    — final model (train = 2022+2023)
  sim/data/phase3_backtest_report_v2.txt
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

SIM_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SIM_DIR)
sys.path.insert(0, PROJECT_DIR)

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("phase3v2")

FEATURE_TABLE_PATH = os.path.join(SIM_DIR, "data", "feature_table.parquet")
MODEL_PATH         = os.path.join(SIM_DIR, "data", "phase3_ridge_model_v2.pkl")
REPORT_PATH        = os.path.join(SIM_DIR, "data", "phase3_backtest_report_v2.txt")

TRAIN_YEARS    = [2022, 2023]
VALIDATE_YEAR  = 2024
LOYO_YEARS     = [2022, 2023, 2024]    # supplemental LOYO diagnostic only

# Extended alpha grid — previous ceiling was 100 (maxed out).
ALPHAS = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0,
          50.0, 100.0, 200.0, 500.0, 1000.0]

# ---------------------------------------------------------------------------
# Feature set — HONEST labels used in all report output
# ---------------------------------------------------------------------------

SP_FEATURES = [
    "home_sp_xfip",   "away_sp_xfip",   # Savant xERA proxy — NOT FanGraphs xFIP
    "home_sp_k_pct",  "away_sp_k_pct",  # MLB Stats API K/BF — valid
    "home_sp_bb_pct", "away_sp_bb_pct", # MLB Stats API BB/BF — valid
    "home_sp_avg_ip", "away_sp_avg_ip", # MLB Stats API IP/GS — valid
]
OFFENSE_FEATURES = [
    "home_wrc_plus",  # Savant xwOBA proxy — NOT FanGraphs wRC+
    "away_wrc_plus",  # Savant xwOBA proxy — NOT FanGraphs wRC+
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

# Display labels for reports — honest about data sources
FEATURE_LABELS = {
    "home_sp_xfip":          "home_sp_xera_proxy   [Savant]",
    "away_sp_xfip":          "away_sp_xera_proxy   [Savant]",
    "home_sp_k_pct":         "home_sp_k_pct        [MLB Stats]",
    "away_sp_k_pct":         "away_sp_k_pct        [MLB Stats]",
    "home_sp_bb_pct":        "home_sp_bb_pct       [MLB Stats]",
    "away_sp_bb_pct":        "away_sp_bb_pct       [MLB Stats]",
    "home_sp_avg_ip":        "home_sp_avg_ip       [MLB Stats]",
    "away_sp_avg_ip":        "away_sp_avg_ip       [MLB Stats]",
    "home_wrc_plus":         "home_xwoba_proxy     [Savant]",
    "away_wrc_plus":         "away_xwoba_proxy     [Savant]",
    "park_factor_runs":      "park_factor_runs     [config]",
    "park_factor_hr":        "park_factor_hr       [config]",
    "temperature":           "temperature          [Open-Meteo]",
    "wind_factor_effective": "wind_factor_eff      [Open-Meteo+config]",
    "umpire_over_rate":      "umpire_over_rate     [static table]",
    "home_rest_days":        "home_rest_days       [MLB Stats]",
    "away_rest_days":        "away_rest_days       [MLB Stats]",
    "doubleheader_flag":     "doubleheader_flag    [MLB Stats]",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_and_prepare(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} cols")

    missing = [c for c in ALL_FEATURES + [TARGET, "season"] if c not in df.columns]
    if missing:
        logger.error(f"Missing columns: {missing}")
        sys.exit(1)

    df = df.dropna(subset=[TARGET])
    df["doubleheader_flag"] = df["doubleheader_flag"].astype(int)

    for col in ALL_FEATURES:
        n = df[col].isna().sum()
        if n:
            med = df[col].median()
            df[col] = df[col].fillna(med)
            logger.info(f"  Filled {n} nulls in {col} → median {med:.3f}")

    return df


# ---------------------------------------------------------------------------
# Model fitting helpers
# ---------------------------------------------------------------------------

def make_pipeline(alphas=ALPHAS, cv=5) -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  RidgeCV(alphas=alphas, cv=cv)),
    ])


def fit_eval(X_tr, y_tr, X_te, y_te, label: str) -> tuple[Pipeline, dict]:
    pipe = make_pipeline()
    pipe.fit(X_tr, y_tr)
    alpha = pipe.named_steps["ridge"].alpha_

    pred_tr = pipe.predict(X_tr)
    pred_te = pipe.predict(X_te)

    metrics = {
        "label":        label,
        "alpha":        alpha,
        "train_mae":    mean_absolute_error(y_tr, pred_tr),
        "train_rmse":   np.sqrt(mean_squared_error(y_tr, pred_tr)),
        "val_mae":      mean_absolute_error(y_te, pred_te),
        "val_rmse":     np.sqrt(mean_squared_error(y_te, pred_te)),
        "val_r":        np.corrcoef(y_te, pred_te)[0, 1],
        "val_bias":     (y_te - pred_te).mean(),
        "pred_val":     pred_te,
        "actual_val":   y_te,
    }
    logger.info(f"  [{label}] alpha={alpha:.1f}  "
                f"train MAE={metrics['train_mae']:.4f}  "
                f"val MAE={metrics['val_mae']:.4f}  "
                f"r={metrics['val_r']:.4f}")
    return pipe, metrics


# ---------------------------------------------------------------------------
# LOYO supplemental diagnostic
# ---------------------------------------------------------------------------

def loyo_cv(df: pd.DataFrame) -> pd.DataFrame:
    result_dfs = []
    for held_year in LOYO_YEARS:
        tr = df["season"] != held_year
        te = df["season"] == held_year
        X_tr = df.loc[tr, ALL_FEATURES].values
        y_tr = df.loc[tr, TARGET].values
        X_te = df.loc[te, ALL_FEATURES].values

        pipe = make_pipeline()
        pipe.fit(X_tr, y_tr)
        alpha = pipe.named_steps["ridge"].alpha_
        preds = pipe.predict(X_te)

        fold_df = df.loc[te, ["game_pk", "date", "season", "home_team",
                               "away_team", TARGET, "actual_f5_total"]].copy()
        fold_df["pred_total"] = preds
        fold_df["residual"]   = fold_df[TARGET] - preds
        fold_df["alpha"]      = alpha
        result_dfs.append(fold_df)
        logger.info(f"  LOYO {held_year}: alpha={alpha:.1f}  "
                    f"MAE={mean_absolute_error(y_tr[~tr.values[:len(y_tr)]] if False else fold_df[TARGET].values, preds):.4f}")

    return pd.concat(result_dfs, ignore_index=True).sort_values("date")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(primary: dict, loyo_df: pd.DataFrame,
                 final_pipe: Pipeline) -> list[str]:
    lines: list[str] = []

    def L(s=""):
        lines.append(s)

    L("=" * 72)
    L("PHASE 3 RIDGE REGRESSION — TIGHTENED BACKTEST (v2)")
    L("=" * 72)
    L()
    L("DATA SOURCES (honest labeling):")
    L("  Pitcher quality : Savant xERA proxy  (NOT FanGraphs xFIP/SIERA)")
    L("  Team offense    : Savant xwOBA proxy (NOT FanGraphs wRC+)")
    L("  K%, BB%, avg_IP : MLB Stats API season totals")
    L("  Weather         : Open-Meteo archive API")
    L("  Park factors    : Static config (2024 run park factors)")
    L("  Umpires         : Static rating table")
    L()

    # ── Primary split ──────────────────────────────────────────────────────
    L("─" * 72)
    L(f"PRIMARY EVALUATION  |  Train: {TRAIN_YEARS}  →  Validate: {VALIDATE_YEAR}")
    L("─" * 72)
    L(f"  Best alpha (RidgeCV internal): {primary['alpha']:.1f}")
    L()
    L(f"  {'Split':<12}  {'N':>5}  {'MAE':>8}  {'RMSE':>8}  {'r':>7}  {'Bias':>7}")
    L(f"  {'─'*12}  {'─'*5}  {'─'*8}  {'─'*8}  {'─'*7}  {'─'*7}")
    n_tr = sum(1 for yr in TRAIN_YEARS
               for _ in range(1))   # approximate
    L(f"  {'Train '+str(TRAIN_YEARS):<12}  {'—':>5}  {primary['train_mae']:>8.4f}  "
      f"{primary['train_rmse']:>8.4f}  {'—':>7}  {'—':>7}")
    L(f"  {'Validate '+str(VALIDATE_YEAR):<12}  {len(primary['actual_val']):>5,}  "
      f"{primary['val_mae']:>8.4f}  {primary['val_rmse']:>8.4f}  "
      f"{primary['val_r']:>7.4f}  {primary['val_bias']:>+7.4f}")

    # Pred distribution
    actual = primary["actual_val"]
    pred   = primary["pred_val"]
    L()
    L(f"  Prediction distribution (2024 validation):")
    L(f"    {'':20}  {'Pred':>8}  {'Actual':>8}")
    L(f"    {'Mean':20}  {pred.mean():>8.3f}  {actual.mean():>8.3f}")
    L(f"    {'Std':20}  {pred.std():>8.3f}  {actual.std():>8.3f}")
    L(f"    {'Range':20}  {pred.min():>5.2f}–{pred.max():>5.2f}  "
      f"{int(actual.min())}–{int(actual.max())}")

    # ── LOYO supplemental ──────────────────────────────────────────────────
    L()
    L("─" * 72)
    L("SUPPLEMENTAL: Leave-One-Year-Out Cross-Validation")
    L("─" * 72)
    L(f"  {'Year':<6}  {'N':>5}  {'MAE':>8}  {'RMSE':>8}  {'r':>7}  {'Alpha':>7}")
    L(f"  {'─'*6}  {'─'*5}  {'─'*8}  {'─'*8}  {'─'*7}  {'─'*7}")
    for yr in LOYO_YEARS:
        s   = loyo_df[loyo_df["season"] == yr]
        a   = s[TARGET].values
        p   = s["pred_total"].values
        alpha = s["alpha"].iloc[0]
        L(f"  {int(yr):<6}  {len(s):>5,}  "
          f"{mean_absolute_error(a,p):>8.4f}  "
          f"{np.sqrt(mean_squared_error(a,p)):>8.4f}  "
          f"{np.corrcoef(a,p)[0,1]:>7.4f}  "
          f"{alpha:>7.1f}")
    all_a = loyo_df[TARGET].values
    all_p = loyo_df["pred_total"].values
    L(f"  {'LOYO avg':<6}  {len(loyo_df):>5,}  "
      f"{mean_absolute_error(all_a,all_p):>8.4f}  "
      f"{np.sqrt(mean_squared_error(all_a,all_p)):>8.4f}  "
      f"{np.corrcoef(all_a,all_p)[0,1]:>7.4f}  {'—':>7}")

    # ── Coefficients ───────────────────────────────────────────────────────
    L()
    L("─" * 72)
    L("FEATURE COEFFICIENTS  (final model trained on 2022+2023+2024)")
    L("─" * 72)
    scaler = final_pipe.named_steps["scaler"]
    ridge  = final_pipe.named_steps["ridge"]
    raw    = ridge.coef_ / scaler.scale_

    rows = sorted(zip(ALL_FEATURES, ridge.coef_, raw),
                  key=lambda x: abs(x[1]), reverse=True)
    L(f"  {'Feature (data source)':<46}  {'Coef_std':>9}  {'Coef_raw':>9}")
    L(f"  {'─'*46}  {'─'*9}  {'─'*9}")
    for feat, c_std, c_raw in rows:
        label = FEATURE_LABELS.get(feat, feat)
        L(f"  {label:<46}  {c_std:>+9.4f}  {c_raw:>+9.4f}")

    L()
    L("=" * 72)
    L("NOTE: alpha maxed at 100 in v1; v2 grid extended to 1000.")
    if final_pipe.named_steps["ridge"].alpha_ >= 900:
        L("WARNING: alpha still at grid maximum (1000) — model wants more shrinkage.")
        L("         Consider narrowing feature set or extending grid further.")
    else:
        L(f"OK: alpha settled at {final_pipe.named_steps['ridge'].alpha_:.1f} "
          f"(below grid maximum of 1000) — grid is now sufficient.")

    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    df = load_and_prepare(FEATURE_TABLE_PATH)

    # Filter to train+validate years only (2025 excluded from Phase 3)
    df_3yr = df[df["season"].isin(TRAIN_YEARS + [VALIDATE_YEAR])].copy()
    logger.info(f"Phase 3 dataset: {len(df_3yr):,} games "
                f"(seasons {sorted(df_3yr['season'].unique().tolist())})")

    # Primary split
    tr_mask = df_3yr["season"].isin(TRAIN_YEARS)
    te_mask = df_3yr["season"] == VALIDATE_YEAR

    X_tr = df_3yr.loc[tr_mask, ALL_FEATURES].values
    y_tr = df_3yr.loc[tr_mask, TARGET].values
    X_te = df_3yr.loc[te_mask, ALL_FEATURES].values
    y_te = df_3yr.loc[te_mask, TARGET].values

    logger.info(f"Primary split: train={tr_mask.sum():,} games  "
                f"validate={te_mask.sum():,} games")
    logger.info("Fitting primary train/validate model...")
    primary_pipe, primary_metrics = fit_eval(X_tr, y_tr, X_te, y_te,
                                             label=f"{TRAIN_YEARS}→{VALIDATE_YEAR}")

    # LOYO supplemental
    logger.info("Running LOYO supplemental cross-validation...")
    loyo_df = loyo_cv(df_3yr)

    # Final model on all 3 years
    logger.info("Fitting final model on all 3 seasons (2022+2023+2024)...")
    final_pipe = make_pipeline()
    final_pipe.fit(df_3yr[ALL_FEATURES].values, df_3yr[TARGET].values)
    final_alpha = final_pipe.named_steps["ridge"].alpha_
    logger.info(f"Final model alpha: {final_alpha:.1f}  "
                f"intercept: {final_pipe.named_steps['ridge'].intercept_:.3f}")

    # Save model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({
            "pipeline":     primary_pipe,   # trained on 2022+2023 only
            "final_pipe":   final_pipe,     # trained on all 3 seasons
            "features":     ALL_FEATURES,
            "feature_labels": FEATURE_LABELS,
            "target":       TARGET,
            "train_years":  TRAIN_YEARS,
            "validate_year": VALIDATE_YEAR,
            "primary_metrics": {k: v for k, v in primary_metrics.items()
                                if k not in ("pred_val", "actual_val")},
        }, f)
    logger.info(f"Saved model: {MODEL_PATH}")

    # Build and print report
    lines = build_report(primary_metrics, loyo_df, final_pipe)
    report_text = "\n".join(lines)
    print(report_text)
    with open(REPORT_PATH, "w") as f:
        f.write(report_text)
    logger.info(f"Saved report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
