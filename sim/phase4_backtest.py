"""
phase4_backtest.py — Full Phase 4 Backtest Report

Uses the Phase 3 v2 model (trained on 2022+2023) and evaluates on:
  • 2024 validation set (the primary held-out season)
  • 2025 true OOS      (never seen during any training step)

Diagnostics:
  1. Primary metrics: MAE, RMSE, r, bias (2024 vs 2025, side-by-side)
  2. Directional hit rate (model lean vs actual outcome, relative to proxy line)
  3. Edge bucket monotonicity table — the key signal-vs-noise diagnostic
  4. Calibration by prediction decile
  5. Performance segmented by: starter quality, weather, umpire tendency,
     SP depth (proxy for bullpen reliance)
  6. Market review flags: |edge| ≥ 2.5 = review, ≥ 4.0 = extreme anomaly

PROXY LINE NOTE: Without historical market totals, the season mean (~8.86 runs)
is used as the proxy "posted line" for all edge / directional calculations.
Edge = model_prediction − proxy_line.  This understates the model's true edge
vs the actual posted total, but provides a consistent apples-to-apples
diagnostic across 2024 and 2025.

Usage:
    python sim/phase4_backtest.py           # requires feature_table.parquet with 2025
    python sim/phase4_backtest.py --no-2025 # 2024 validation only
"""

import argparse
import logging
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")

SIM_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SIM_DIR)
sys.path.insert(0, PROJECT_DIR)

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("phase4")

FEATURE_TABLE_PATH = os.path.join(SIM_DIR, "data", "feature_table.parquet")
MODEL_PATH         = os.path.join(SIM_DIR, "data", "phase3_ridge_model_v2.pkl")
REPORT_PATH        = os.path.join(SIM_DIR, "data", "phase4_backtest_report.txt")

TRAIN_YEARS    = [2022, 2023]
VALIDATE_YEAR  = 2024
OOS_YEAR       = 2025

# Proxy "posted line" — league average runs per game over 2022-2024
PROXY_LINE = 8.86   # updated each season; used for all edge calculations

# Review / anomaly thresholds (from build spec)
REVIEW_THRESH  = 2.5
EXTREME_THRESH = 4.0


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_model() -> dict:
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    return bundle


def load_features(years: list[int]) -> pd.DataFrame:
    df = pd.read_parquet(FEATURE_TABLE_PATH)
    df = df[df["season"].isin(years)].copy()
    df["doubleheader_flag"] = df["doubleheader_flag"].astype(int)
    for col in bundle_features({}):
        pass    # placeholder
    return df


def bundle_features(bundle: dict) -> list[str]:
    return bundle.get("features", [])


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict(df: pd.DataFrame, pipe, features: list[str]) -> np.ndarray:
    X = df[features].copy()
    for col in features:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())
    return pipe.predict(X.values)


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

def core_metrics(actual: np.ndarray, pred: np.ndarray, label: str) -> dict:
    resid = actual - pred
    return {
        "label":    label,
        "n":        len(actual),
        "mae":      mean_absolute_error(actual, pred),
        "rmse":     np.sqrt(mean_squared_error(actual, pred)),
        "r":        np.corrcoef(actual, pred)[0, 1],
        "bias":     resid.mean(),
        "pred_std": pred.std(),
        "act_std":  actual.std(),
        "pred_min": pred.min(),
        "pred_max": pred.max(),
    }


# ---------------------------------------------------------------------------
# Directional hit rate
# ---------------------------------------------------------------------------

def directional_hit_rate(actual: np.ndarray, pred: np.ndarray,
                          line: float = PROXY_LINE) -> dict:
    """
    Lean = sign of (pred - line).
    Hit  = actual is on the same side of line as the lean.
    Games right at line (pred == line) are excluded (no lean).
    """
    mask_over  = pred > line
    mask_under = pred < line
    mask_lean  = mask_over | mask_under     # has a clear lean

    actual_over  = actual > line
    actual_under = actual <= line

    hits_over  = (mask_over  & actual_over).sum()
    hits_under = (mask_under & actual_under).sum()
    total_lean = mask_lean.sum()
    total_hits = hits_over + hits_under

    hit_rate = total_hits / total_lean if total_lean > 0 else 0.0

    return {
        "n_lean":       total_lean,
        "n_no_lean":    len(pred) - total_lean,
        "lean_over":    mask_over.sum(),
        "lean_under":   mask_under.sum(),
        "hits":         total_hits,
        "hit_rate":     hit_rate,
        "hit_over":     hits_over / mask_over.sum() if mask_over.sum() > 0 else 0.0,
        "hit_under":    hits_under / mask_under.sum() if mask_under.sum() > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Edge bucket monotonicity
# ---------------------------------------------------------------------------

def edge_bucket_table(actual: np.ndarray, pred: np.ndarray,
                       line: float = PROXY_LINE) -> pd.DataFrame:
    """
    Group games by |edge| = |pred - line| and compute directional hit rate
    per bucket.  Monotonic increase = model has real signal.
    """
    edge        = pred - line
    abs_edge    = np.abs(edge)
    actual_over = actual > line

    bins   = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, np.inf]
    labels = ["0.0–0.5", "0.5–1.0", "1.0–1.5", "1.5–2.0",
              "2.0–2.5", "2.5–3.0", "3.0–4.0", "4.0+"]

    rows = []
    for lo, hi, lbl in zip(bins[:-1], bins[1:], labels):
        mask = (abs_edge >= lo) & (abs_edge < hi)
        n = mask.sum()
        if n == 0:
            continue
        lean_over  = edge[mask] > 0
        lean_under = edge[mask] < 0
        act_over   = actual_over[mask]
        hits = ((lean_over & act_over) | (lean_under & ~act_over)).sum()
        avg_pred   = pred[mask].mean()
        avg_actual = actual[mask].mean()
        rows.append({
            "edge_bucket":  lbl,
            "n":            n,
            "hit_rate":     hits / n,
            "avg_pred":     avg_pred,
            "avg_actual":   avg_actual,
            "avg_abs_edge": abs_edge[mask].mean(),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Calibration by prediction decile
# ---------------------------------------------------------------------------

def calibration_table(actual: np.ndarray, pred: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame({"actual": actual, "pred": pred})
    df["decile"] = pd.qcut(df["pred"], q=10, labels=False, duplicates="drop")
    rows = []
    for d, grp in df.groupby("decile"):
        rows.append({
            "decile":       int(d) + 1,
            "n":            len(grp),
            "pred_range":   f"{grp['pred'].min():.2f}–{grp['pred'].max():.2f}",
            "pred_mean":    grp["pred"].mean(),
            "actual_mean":  grp["actual"].mean(),
            "pct_over_8":   (grp["actual"] > 8).mean(),
            "pct_over_9":   (grp["actual"] > 9).mean(),
            "pct_over_10":  (grp["actual"] > 10).mean(),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Segmented performance
# ---------------------------------------------------------------------------

def segment_performance(df_eval: pd.DataFrame, pred: np.ndarray,
                         actual: np.ndarray) -> dict[str, pd.DataFrame]:
    dfe = df_eval.copy()
    dfe["pred"]    = pred
    dfe["actual"]  = actual
    dfe["abs_err"] = (actual - pred).__abs__()
    dfe["edge"]    = pred - PROXY_LINE
    dfe["hit"]     = ((dfe["edge"] > 0) & (actual > PROXY_LINE)) | \
                     ((dfe["edge"] < 0) & (actual <= PROXY_LINE))

    results = {}

    # ── Starter quality ─────────────────────────────────────────────────
    dfe["sp_avg_xera"] = (dfe["home_sp_xfip"] + dfe["away_sp_xfip"]) / 2
    dfe["sp_tier"] = pd.cut(
        dfe["sp_avg_xera"],
        bins=[-np.inf, 3.80, 4.50, np.inf],
        labels=["Elite (<3.80)", "Average (3.80–4.50)", "Poor (>4.50)"]
    )
    results["starter_quality"] = (
        dfe.groupby("sp_tier", observed=True)
        .agg(n=("abs_err", "count"),
             mae=("abs_err", "mean"),
             hit_rate=("hit", "mean"),
             avg_pred=("pred", "mean"),
             avg_actual=("actual", "mean"))
        .reset_index()
    )

    # ── Weather ─────────────────────────────────────────────────────────
    # Temperature bucket (outdoor games only; dome+retractable neutralized)
    dfe["temp_bucket"] = "Dome/Indoor"
    outdoor = dfe["roof_status"] == "open"
    dfe.loc[outdoor & (dfe["temperature"] < 55), "temp_bucket"] = "Cold (<55°F)"
    dfe.loc[outdoor & (dfe["temperature"] >= 55) & (dfe["temperature"] < 75),
            "temp_bucket"] = "Neutral (55-75°F)"
    dfe.loc[outdoor & (dfe["temperature"] >= 75), "temp_bucket"] = "Hot (>75°F)"

    results["temperature"] = (
        dfe.groupby("temp_bucket")
        .agg(n=("abs_err", "count"),
             mae=("abs_err", "mean"),
             hit_rate=("hit", "mean"),
             avg_pred=("pred", "mean"),
             avg_actual=("actual", "mean"))
        .reset_index()
    )

    # Wind bucket (outdoor only)
    dfe["wind_bucket"] = "Dome/Retractable"
    dfe.loc[outdoor & (dfe["wind_factor_effective"] < -3), "wind_bucket"] = "Wind In (<-3)"
    dfe.loc[outdoor & (dfe["wind_factor_effective"].abs() <= 3), "wind_bucket"] = "Calm (±3)"
    dfe.loc[outdoor & (dfe["wind_factor_effective"] > 3), "wind_bucket"] = "Wind Out (>+3)"

    results["wind"] = (
        dfe.groupby("wind_bucket")
        .agg(n=("abs_err", "count"),
             mae=("abs_err", "mean"),
             hit_rate=("hit", "mean"),
             avg_pred=("pred", "mean"),
             avg_actual=("actual", "mean"))
        .reset_index()
    )

    # ── Umpire tendency ──────────────────────────────────────────────────
    # umpire_over_rate is a multiplier centered at 1.0 (league avg):
    #   < 0.990 = under-caller (~11% of games), > 1.005 = over-caller (~12%)
    dfe["ump_tier"] = pd.cut(
        dfe["umpire_over_rate"],
        bins=[-np.inf, 0.990, 1.005, np.inf],
        labels=["Under-caller (<0.990)", "Neutral (0.990–1.005)", "Over-caller (>1.005)"]
    )
    results["umpire"] = (
        dfe.groupby("ump_tier", observed=True)
        .agg(n=("abs_err", "count"),
             mae=("abs_err", "mean"),
             hit_rate=("hit", "mean"),
             avg_pred=("pred", "mean"),
             avg_actual=("actual", "mean"))
        .reset_index()
    )

    # ── SP depth (proxy for bullpen reliance) ────────────────────────────
    sp_avg_ip = (dfe["home_sp_avg_ip"] + dfe["away_sp_avg_ip"]) / 2
    dfe["sp_depth"] = pd.cut(
        sp_avg_ip,
        bins=[-np.inf, 5.0, 6.0, np.inf],
        labels=["Short (<5.0 IP)", "Normal (5.0–6.0)", "Deep (>6.0 IP)"]
    )
    results["sp_depth"] = (
        dfe.groupby("sp_depth", observed=True)
        .agg(n=("abs_err", "count"),
             mae=("abs_err", "mean"),
             hit_rate=("hit", "mean"),
             avg_pred=("pred", "mean"),
             avg_actual=("actual", "mean"))
        .reset_index()
    )

    return results


# ---------------------------------------------------------------------------
# Market review flags
# ---------------------------------------------------------------------------

def market_flag_table(actual: np.ndarray, pred: np.ndarray,
                       line: float = PROXY_LINE) -> pd.DataFrame:
    edge    = pred - line
    abs_e   = np.abs(edge)

    bins   = [-np.inf, REVIEW_THRESH, EXTREME_THRESH, np.inf]
    labels = [f"No flag (< {REVIEW_THRESH})",
              f"Review ({REVIEW_THRESH}–{EXTREME_THRESH})",
              f"Extreme anomaly (≥ {EXTREME_THRESH})"]

    buckets = pd.cut(abs_e, bins=bins, labels=labels)
    actual_over = actual > line

    rows = []
    for lbl in labels:
        mask = buckets == lbl
        n = mask.sum()
        if n == 0:
            rows.append({"tier": lbl, "n": 0, "pct_of_games": 0.0,
                          "hit_rate": np.nan, "avg_actual": np.nan, "avg_pred": np.nan})
            continue
        lean_over  = edge[mask] > 0
        lean_under = edge[mask] < 0
        act_over   = actual_over[mask]
        hits = ((lean_over & act_over) | (lean_under & ~act_over)).sum()
        rows.append({
            "tier":          lbl,
            "n":             n,
            "pct_of_games":  n / len(actual) * 100,
            "hit_rate":      hits / n,
            "avg_pred":      pred[mask].mean(),
            "avg_actual":    actual[mask].mean(),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_report(results_2024: dict, results_2025: dict | None) -> list[str]:
    lines: list[str] = []

    def L(s=""):
        lines.append(s)
        print(s)

    L("=" * 76)
    L("PHASE 4 BACKTEST REPORT")
    L("=" * 76)
    L("Model: Ridge (alpha=500, train=2022+2023) — Phase 3 v2")
    L(f"Proxy line: {PROXY_LINE} runs (league season mean 2022–2024)")
    L("NOTE: Edge = model_pred − proxy_line.  Without market lines this")
    L("      understates true edge vs posted totals but is consistent.")
    L()

    years_to_show = [2024]
    if results_2025:
        years_to_show.append(2025)

    # ── 1. Primary metrics ─────────────────────────────────────────────────
    L("─" * 76)
    L("1. PRIMARY METRICS")
    L("─" * 76)
    L(f"  {'Metric':<18}  {'2024 Validate':>16}  {'2025 OOS':>16}")
    L(f"  {'─'*18}  {'─'*16}  {'─'*16}")
    for key, label in [("n","N (games)"),("mae","MAE"),("rmse","RMSE"),
                        ("r","Pearson r"),("bias","Bias"),
                        ("pred_std","Pred std"),("act_std","Actual std")]:
        v24 = results_2024["metrics"][key]
        v25 = results_2025["metrics"][key] if results_2025 else "—"
        fmt = lambda v: f"{v:,.4f}" if isinstance(v, float) and key not in ("n",) else (f"{int(v):,}" if key == "n" else str(v))
        L(f"  {label:<18}  {fmt(v24):>16}  {fmt(v25) if v25 != '—' else '—':>16}")

    # ── 2. Directional hit rate ────────────────────────────────────────────
    L()
    L("─" * 76)
    L("2. DIRECTIONAL HIT RATE  (lean vs actual, relative to proxy line 8.86)")
    L("─" * 76)
    for yr, res in [(2024, results_2024)] + ([(2025, results_2025)] if results_2025 else []):
        dhr = res["directional"]
        L(f"  {yr}:")
        L(f"    Games with lean:  {dhr['n_lean']:,} ({dhr['n_lean']/results_2024['metrics']['n']*100:.0f}%)")
        L(f"    Lean over:        {dhr['lean_over']:,}  hit {dhr['hit_over']:.1%}")
        L(f"    Lean under:       {dhr['lean_under']:,}  hit {dhr['hit_under']:.1%}")
        L(f"    Combined:         {dhr['hit_rate']:.1%}  (random baseline = 50.0%)")

    # ── 3. Edge bucket monotonicity ────────────────────────────────────────
    L()
    L("─" * 76)
    L("3. EDGE BUCKET MONOTONICITY  (most important diagnostic)")
    L("   Monotonic hit-rate increase with edge size = model has real signal")
    L("─" * 76)
    for yr, res in [(2024, results_2024)] + ([(2025, results_2025)] if results_2025 else []):
        L(f"  {yr}:")
        ebt = res["edge_buckets"]
        L(f"  {'|Edge| bucket':<12}  {'N':>5}  {'Hit%':>7}  {'Avg_Pred':>9}  {'Avg_Act':>9}")
        L(f"  {'─'*12}  {'─'*5}  {'─'*7}  {'─'*9}  {'─'*9}")
        for _, row in ebt.iterrows():
            L(f"  {row['edge_bucket']:<12}  {row['n']:>5,}  {row['hit_rate']:>7.1%}  "
              f"{row['avg_pred']:>9.3f}  {row['avg_actual']:>9.3f}")
        # Monotonicity check
        rates = ebt["hit_rate"].values
        is_mono = all(rates[i] <= rates[i+1] + 0.03 for i in range(len(rates)-1))
        L(f"  → {'MONOTONIC ✓' if is_mono else 'NON-MONOTONIC ⚠'}")
        L()

    # ── 4. Calibration by prediction decile ───────────────────────────────
    L("─" * 76)
    L("4. CALIBRATION BY PREDICTION DECILE")
    L("─" * 76)
    for yr, res in [(2024, results_2024)] + ([(2025, results_2025)] if results_2025 else []):
        L(f"  {yr}:")
        cal = res["calibration"]
        L(f"  {'Decile':<7}  {'Pred range':<14}  {'Pred mean':>10}  {'Act mean':>10}  "
          f"{'%>8':>6}  {'%>9':>6}  {'%>10':>6}")
        L(f"  {'─'*7}  {'─'*14}  {'─'*10}  {'─'*10}  {'─'*6}  {'─'*6}  {'─'*6}")
        for _, row in cal.iterrows():
            L(f"  {row['decile']:<7}  {row['pred_range']:<14}  {row['pred_mean']:>10.3f}  "
              f"{row['actual_mean']:>10.3f}  {row['pct_over_8']:>6.1%}  "
              f"{row['pct_over_9']:>6.1%}  {row['pct_over_10']:>6.1%}")
        L()

    # ── 5. Segmented performance ───────────────────────────────────────────
    L("─" * 76)
    L("5. SEGMENTED PERFORMANCE")
    L("─" * 76)

    segments = [
        ("starter_quality", "Starter Quality Tier"),
        ("temperature",     "Temperature Bucket"),
        ("wind",            "Wind Bucket"),
        ("umpire",          "Umpire Tendency"),
        ("sp_depth",        "SP Depth (bullpen reliance proxy)"),
    ]

    for seg_key, seg_label in segments:
        L(f"  {seg_label}:")
        for yr, res in [(2024, results_2024)] + ([(2025, results_2025)] if results_2025 else []):
            seg_df = res["segments"].get(seg_key)
            if seg_df is None or seg_df.empty:
                continue
            first_col = seg_df.columns[0]
            L(f"  {yr:>4}  {'Tier':<30}  {'N':>5}  {'MAE':>7}  {'Hit%':>7}  {'Pred':>6}  {'Actual':>6}")
            L(f"        {'─'*30}  {'─'*5}  {'─'*7}  {'─'*7}  {'─'*6}  {'─'*6}")
            for _, row in seg_df.iterrows():
                tier_val = str(row[first_col])
                L(f"        {tier_val:<30}  {int(row['n']):>5,}  {row['mae']:>7.4f}  "
                  f"{row['hit_rate']:>7.1%}  {row['avg_pred']:>6.3f}  {row['avg_actual']:>6.3f}")
        L()

    # ── 6. Market review flags ─────────────────────────────────────────────
    L("─" * 76)
    L("6. MARKET REVIEW FLAGS")
    L(f"   Review ≥ {REVIEW_THRESH} run edge  |  Extreme anomaly ≥ {EXTREME_THRESH} run edge")
    L("─" * 76)
    for yr, res in [(2024, results_2024)] + ([(2025, results_2025)] if results_2025 else []):
        L(f"  {yr}:")
        mft = res["market_flags"]
        L(f"  {'Tier':<35}  {'N':>5}  {'% games':>8}  {'Hit%':>7}  {'AvgPred':>8}  {'AvgAct':>7}")
        L(f"  {'─'*35}  {'─'*5}  {'─'*8}  {'─'*7}  {'─'*8}  {'─'*7}")
        for _, row in mft.iterrows():
            hit_str = f"{row['hit_rate']:.1%}" if not pd.isna(row['hit_rate']) else "—"
            pred_str = f"{row['avg_pred']:.3f}" if not pd.isna(row['avg_pred']) else "—"
            act_str = f"{row['avg_actual']:.3f}" if not pd.isna(row['avg_actual']) else "—"
            L(f"  {row['tier']:<35}  {int(row['n']):>5,}  {row['pct_of_games']:>7.1f}%  "
              f"{hit_str:>7}  {pred_str:>8}  {act_str:>7}")
        L()

    L("=" * 76)
    L("DATA QUALITY LIMITATIONS:")
    L("  • Pitcher quality = Savant xERA proxy (NOT FanGraphs xFIP)")
    L("  • Offense = Savant xwOBA proxy (NOT FanGraphs wRC+)")
    L("  • Full-season stats used for mid-season games (mild data leakage)")
    L("  • Bullpen quality = league average for all teams (no FanGraphs GS data)")
    L("  • Proxy line = league season mean (not actual market totals)")

    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-2025", action="store_true",
                        help="Skip 2025 OOS (run 2024 validation only)")
    args = parser.parse_args()

    # Load model
    logger.info("Loading Phase 3 v2 model...")
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)

    pipe     = bundle["pipeline"]   # trained on 2022+2023
    features = bundle["features"]

    # Load feature table
    logger.info("Loading feature table...")
    df_all = pd.read_parquet(FEATURE_TABLE_PATH)
    df_all["doubleheader_flag"] = df_all["doubleheader_flag"].astype(int)
    for col in features:
        if col in df_all.columns and df_all[col].isna().any():
            df_all[col] = df_all[col].fillna(df_all[col].median())

    available_years = sorted(df_all["season"].unique())
    logger.info(f"Available seasons: {available_years}")

    def run_eval(year: int, label: str) -> dict | None:
        df_yr = df_all[df_all["season"] == year]
        if df_yr.empty:
            logger.warning(f"No data for {year}")
            return None

        actual = df_yr["actual_total"].values.astype(float)
        pred   = pipe.predict(df_yr[features].values)

        logger.info(f"[{label}] n={len(df_yr):,}  "
                    f"MAE={mean_absolute_error(actual,pred):.4f}  "
                    f"r={np.corrcoef(actual,pred)[0,1]:.4f}")

        segs = segment_performance(df_yr, pred, actual)

        return {
            "metrics":      core_metrics(actual, pred, label),
            "directional":  directional_hit_rate(actual, pred),
            "edge_buckets": edge_bucket_table(actual, pred),
            "calibration":  calibration_table(actual, pred),
            "segments":     segs,
            "market_flags": market_flag_table(actual, pred),
            "pred":         pred,
            "actual":       actual,
        }

    # 2024 validation
    logger.info("Evaluating 2024 validation set...")
    results_2024 = run_eval(VALIDATE_YEAR, "2024 Validate")
    if results_2024 is None:
        logger.error("2024 data not found in feature table")
        sys.exit(1)

    # 2025 OOS
    results_2025 = None
    if not args.no_2025:
        if OOS_YEAR not in available_years:
            logger.warning(f"2025 not in feature table ({available_years}). "
                           "Build 2025 data first: python sim/phase1_build_game_table.py --seasons 2025 "
                           "then python sim/phase2_build_features.py")
        else:
            logger.info("Evaluating 2025 true OOS...")
            results_2025 = run_eval(OOS_YEAR, "2025 OOS")

    # Render
    lines = render_report(results_2024, results_2025)

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))
    logger.info(f"Saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
