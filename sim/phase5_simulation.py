"""
phase5_simulation.py — Monte Carlo probability wrapper around Ridge baseline.

Design:
  • Sim mean is anchored EXACTLY to the Ridge prediction — no adjustment.
  • Sigma is estimated from 2022+2023 training residuals only (not hardcoded).
  • 10,000 iterations per game, normally distributed noise N(0, sigma).
  • Per-game sigma is overrideable for future matchup-specific variance
    (e.g. wind-out + flyball pitcher → wider distribution).
    Default: global residual sigma from training set.
  • Output per game: proj_total, p_over, p_under, ci80_lo, ci80_hi.
  • Divergence check: flag games where sim mean diverges > 0.5 from Ridge.

Label disclaimer: The Ridge baseline has real directional signal (~54-56%
directional hit rate OOS) but is a compressed mean-regression forecast
(pred std ~0.93 vs actual std ~4.5).  The simulation adds a probability
wrapper — it does NOT fix range compression.  All outputs are labeled
accordingly.  Do not treat this as a finished sharp model.

Review flag: games where |sim_mean − proxy_line| ≥ 2.5 runs.  These hit
at 69–83% in Phase 4 but are based on the PROXY line (league season mean
≈ 8.86), NOT actual posted market totals.  Results are NOT actionable until
verified against real market lines.

Usage:
    python sim/phase5_simulation.py           # 2024 calibration + 2025 OOS
    python sim/phase5_simulation.py --no-2025 # 2024 only
    python sim/phase5_simulation.py --seed 99 # reproducible
"""

import argparse
import logging
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

warnings.filterwarnings("ignore")

SIM_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SIM_DIR)
sys.path.insert(0, PROJECT_DIR)

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("phase5")

FEATURE_TABLE_PATH = os.path.join(SIM_DIR, "data", "feature_table.parquet")
MODEL_PATH         = os.path.join(SIM_DIR, "data", "phase3_ridge_model_v2.pkl")
REPORT_PATH        = os.path.join(SIM_DIR, "data", "phase5_simulation_report.txt")
SIM_OUTPUT_PATH    = os.path.join(SIM_DIR, "data", "phase5_sim_results.parquet")

TRAIN_YEARS   = [2022, 2023]
VALIDATE_YEAR = 2024
OOS_YEAR      = 2025

PROXY_LINE        = 8.86   # league season mean 2022-2024; NOT actual posted totals
REVIEW_EDGE       = 2.5    # |sim_mean - proxy_line| threshold for review flag
N_SIMS            = 10_000
CI_LEVEL          = 0.80   # confidence interval coverage target
DIVERGE_THRESH    = 0.50   # flag if |sim_mean - ridge_pred| > this
DEFAULT_SEED      = 42


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_model() -> dict:
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def load_features(years: list[int]) -> pd.DataFrame:
    df = pd.read_parquet(FEATURE_TABLE_PATH)
    df = df[df["season"].isin(years)].copy()
    df["doubleheader_flag"] = df["doubleheader_flag"].astype(int)
    return df


# ---------------------------------------------------------------------------
# Ridge prediction
# ---------------------------------------------------------------------------

def ridge_predict(df: pd.DataFrame, pipe, features: list[str]) -> np.ndarray:
    X = df[features].copy()
    for col in features:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())
    return pipe.predict(X.values)


# ---------------------------------------------------------------------------
# Training residual sigma
# ---------------------------------------------------------------------------

def compute_train_sigma(pipe, features: list[str]) -> float:
    """
    Fit sigma from 2022+2023 training residuals.
    sigma = std(actual - ridge_pred) on training set.
    This is the empirical forecast error distribution — used as default
    per-game noise parameter in the simulation.
    """
    df_train = load_features(TRAIN_YEARS)
    actual   = df_train["actual_total"].values
    pred     = ridge_predict(df_train, pipe, features)
    resid    = actual - pred
    sigma    = resid.std(ddof=1)
    bias     = resid.mean()
    logger.info(f"Training residuals (2022+2023): sigma={sigma:.4f}, bias={bias:+.4f}, "
                f"n={len(resid):,}")
    return float(sigma), float(bias)


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------

def simulate_games(
    ridge_preds: np.ndarray,
    sigma: float,
    line: float = PROXY_LINE,
    n_sims: int = N_SIMS,
    ci_level: float = CI_LEVEL,
    rng: np.random.Generator = None,
    per_game_sigma: np.ndarray = None,
) -> pd.DataFrame:
    """
    For each game, draw n_sims samples from N(ridge_pred, sigma).
    Sim mean is anchored to ridge_pred — noise is zero-mean.

    per_game_sigma: optional array of per-game sigmas (shape = n_games).
      If None, global sigma is used for all games.
      Architecture hook for future matchup-specific variance (e.g. wind-out
      flyball starters → wider distribution).

    Returns DataFrame with one row per game.
    """
    if rng is None:
        rng = np.random.default_rng(DEFAULT_SEED)

    n_games = len(ridge_preds)
    alpha   = (1 - ci_level) / 2   # 0.10 for 80% CI

    results = []
    flagged_diverge = 0

    for i in range(n_games):
        mu    = ridge_preds[i]
        s     = per_game_sigma[i] if per_game_sigma is not None else sigma

        # 10,000 draws from N(mu, s) — noise is zero-mean so sim mean ≈ mu
        draws = rng.normal(loc=mu, scale=s, size=n_sims)

        sim_mean = draws.mean()
        p_over   = (draws > line).mean()
        p_under  = (draws <= line).mean()
        ci_lo    = np.percentile(draws, alpha * 100)
        ci_hi    = np.percentile(draws, (1 - alpha) * 100)

        # Divergence check: sim mean should be very close to ridge_pred
        # (any drift > DIVERGE_THRESH is a numerical anomaly)
        diverge_flag = abs(sim_mean - mu) > DIVERGE_THRESH
        if diverge_flag:
            flagged_diverge += 1
            logger.warning(f"Game {i}: sim_mean={sim_mean:.3f} diverges from "
                           f"ridge_pred={mu:.3f} by {abs(sim_mean - mu):.3f}")

        results.append({
            "ridge_pred":   mu,
            "sim_mean":     sim_mean,
            "sim_sigma":    s,
            "p_over":       p_over,
            "p_under":      p_under,
            "ci_lo":        ci_lo,
            "ci_hi":        ci_hi,
            "review_flag":  abs(mu - line) >= REVIEW_EDGE,
            "extreme_flag": abs(mu - line) >= 4.0,
            "diverge_flag": diverge_flag,
        })

    if flagged_diverge > 0:
        logger.warning(f"  Total divergence flags: {flagged_diverge}/{n_games}")
    else:
        logger.info(f"  No divergence flags (all sim means within {DIVERGE_THRESH} of Ridge)")

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Calibration metrics
# ---------------------------------------------------------------------------

def probability_calibration_table(
    actual: np.ndarray,
    p_over: np.ndarray,
    line: float = PROXY_LINE,
    n_bins: int = 10,
) -> pd.DataFrame:
    """
    Bin games by predicted P(over), check actual over rate in each bin.
    A well-calibrated model: predicted P = observed rate.
    """
    actual_over = (actual > line).astype(float)
    bins = np.linspace(0, 1, n_bins + 1)
    labels = [f"{bins[i]:.2f}–{bins[i+1]:.2f}" for i in range(n_bins)]

    df = pd.DataFrame({"p_over": p_over, "actual_over": actual_over})
    df["bin"] = pd.cut(df["p_over"], bins=bins, labels=labels, include_lowest=True)

    result = (
        df.groupby("bin", observed=False)
        .agg(
            n=("actual_over", "count"),
            pred_p_over=("p_over", "mean"),
            actual_over_rate=("actual_over", "mean"),
        )
        .reset_index()
    )
    result["calibration_error"] = result["pred_p_over"] - result["actual_over_rate"]
    return result


def ci_coverage(
    actual: np.ndarray,
    ci_lo: np.ndarray,
    ci_hi: np.ndarray,
) -> float:
    """Fraction of actual values falling within the CI."""
    inside = (actual >= ci_lo) & (actual <= ci_hi)
    return inside.mean()


def probability_hit_table(
    actual: np.ndarray,
    p_over: np.ndarray,
    line: float = PROXY_LINE,
    threshold: float = 0.55,
) -> dict:
    """
    Directional accuracy when P(over) or P(under) exceeds a threshold.
    Returns hit rate at various P thresholds.
    """
    actual_over = actual > line
    results = {}
    for t in [0.50, 0.52, 0.55, 0.58, 0.60]:
        lean_over  = p_over >= t
        lean_under = p_over <= (1 - t)
        any_lean   = lean_over | lean_under

        hits = ((lean_over & actual_over) | (lean_under & ~actual_over)).sum()
        n    = any_lean.sum()
        results[t] = {
            "threshold": t,
            "n_games":   n,
            "hit_rate":  hits / n if n > 0 else float("nan"),
            "coverage":  n / len(actual),
        }
    return results


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(
    label: str,
    df_eval: pd.DataFrame,
    sim_df: pd.DataFrame,
    actual: np.ndarray,
    ridge_pred: np.ndarray,
    train_sigma: float,
    train_bias: float,
    report_lines: list,
) -> None:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    p_over = sim_df["p_over"].values
    p_under = sim_df["p_under"].values
    ci_lo  = sim_df["ci_lo"].values
    ci_hi  = sim_df["ci_hi"].values
    review = sim_df["review_flag"].values

    n = len(actual)
    mae = mean_absolute_error(actual, ridge_pred)
    cov = ci_coverage(actual, ci_lo, ci_hi)
    actual_over = actual > PROXY_LINE

    line(f"\n{'─'*76}")
    line(f"  SEASON: {label}  (n={n:,})")
    line(f"{'─'*76}")

    # --- Primary metrics ---
    line(f"  Ridge MAE:        {mae:.4f}   (inherited from Phase 3 — no change)")
    line(f"  Sim sigma:        {train_sigma:.4f} runs  (from 2022+2023 training residuals)")
    line(f"  Training bias:    {train_bias:+.4f} runs  (residual mean)")
    line()

    # --- 80% CI coverage ---
    line(f"  80% CI coverage:  {cov:.1%}  (target = 80.0%)")
    line(f"    CI width (mean): {(ci_hi - ci_lo).mean():.3f} runs")
    line(f"    CI lo  (mean):   {ci_lo.mean():.3f}")
    line(f"    CI hi  (mean):   {ci_hi.mean():.3f}")
    line()

    # --- Directional hit rate by P(over) threshold ---
    line(f"  Directional hit rate by P(over/under) threshold:")
    line(f"  {'Threshold':>10}  {'N games':>8}  {'Hit%':>7}  {'Coverage':>10}")
    line(f"  {'─'*10}  {'─'*8}  {'─'*7}  {'─'*10}")
    hits_tbl = probability_hit_table(actual, p_over)
    for t, row in hits_tbl.items():
        hr = f"{row['hit_rate']:.1%}" if not np.isnan(row['hit_rate']) else "   —"
        line(f"  {t:>10.2f}  {row['n_games']:>8,}  {hr:>7}  {row['coverage']:>10.1%}")
    line()

    # --- P(over) calibration table ---
    line(f"  P(over) calibration (predicted vs actual over-rate, line={PROXY_LINE}):")
    cal = probability_calibration_table(actual, p_over)
    line(f"  {'P(over) bucket':>14}  {'N':>5}  {'Pred P':>7}  {'Actual%':>8}  {'Error':>8}")
    line(f"  {'─'*14}  {'─'*5}  {'─'*7}  {'─'*8}  {'─'*8}")
    for _, r in cal.iterrows():
        if r["n"] == 0:
            continue
        err_str = f"{r['calibration_error']:+.3f}" if not np.isnan(r["calibration_error"]) else "    —"
        line(f"  {str(r['bin']):>14}  {r['n']:>5,}  {r['pred_p_over']:>7.3f}  "
             f"{r['actual_over_rate']:>8.3f}  {err_str:>8}")
    line()

    # --- Review flag subset ---
    n_review = review.sum()
    if n_review > 0:
        actual_rev  = actual[review]
        pred_rev    = ridge_pred[review]
        p_over_rev  = p_over[review]
        cov_rev     = ci_coverage(actual_rev, ci_lo[review], ci_hi[review])
        hits_rev    = probability_hit_table(actual_rev, p_over_rev)

        line(f"  ── Review-flag games (|edge| ≥ {REVIEW_EDGE}) ──")
        line(f"  N review flags:   {n_review} ({n_review/n:.1%} of slate)")
        line(f"  Avg Ridge pred:   {pred_rev.mean():.3f}   Avg actual: {actual_rev.mean():.3f}")
        line(f"  MAE (review):     {mean_absolute_error(actual_rev, pred_rev):.4f}")
        line(f"  80% CI coverage:  {cov_rev:.1%}")
        line(f"  ⚠ Edge computed vs PROXY LINE ({PROXY_LINE}) — not actual market totals.")
        line(f"  ⚠ Verify against posted market lines before treating as actionable.")
        line()
        line(f"  Hit rate at thresholds (review-flag subset):")
        line(f"  {'Threshold':>10}  {'N':>5}  {'Hit%':>7}")
        line(f"  {'─'*10}  {'─'*5}  {'─'*7}")
        for t, row in hits_rev.items():
            hr = f"{row['hit_rate']:.1%}" if not np.isnan(row['hit_rate']) else "  —"
            line(f"  {t:>10.2f}  {row['n_games']:>5,}  {hr:>7}")
        line()
    else:
        line(f"  ── No review-flag games (|edge| ≥ {REVIEW_EDGE}) in this set ──")
        line()

    # --- Divergence check summary ---
    n_div = sim_df["diverge_flag"].sum()
    line(f"  Divergence flags: {n_div} games where |sim_mean - Ridge| > {DIVERGE_THRESH}")

    # --- Sample game outputs ---
    line()
    line(f"  Sample game outputs (10 highest |edge| games):")
    line(f"  {'Ridge':>7}  {'SimMean':>8}  {'Sigma':>6}  {'P(>)':>6}  {'P(<)':>6}  "
         f"{'CI_Lo':>6}  {'CI_Hi':>6}  {'Flag':>4}")
    line(f"  {'─'*7}  {'─'*8}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*4}")
    edges = np.abs(ridge_pred - PROXY_LINE)
    top10_idx = np.argsort(edges)[-10:][::-1]
    for i in top10_idx:
        flag = "REV" if review[i] else ""
        line(f"  {ridge_pred[i]:>7.3f}  {sim_df['sim_mean'].iloc[i]:>8.3f}  "
             f"{sim_df['sim_sigma'].iloc[i]:>6.3f}  "
             f"{p_over[i]:>6.3f}  {p_under[i]:>6.3f}  "
             f"{ci_lo[i]:>6.3f}  {ci_hi[i]:>6.3f}  {flag:>4}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-2025", action="store_true",
                        help="Skip 2025 OOS; calibrate on 2024 only")
    parser.add_argument("--seed",    type=int, default=DEFAULT_SEED,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    # ── Load model ──────────────────────────────────────────────────────────
    logger.info("Loading Phase 3 v2 model...")
    bundle   = load_model()
    pipe     = bundle["pipeline"]   # trained on 2022+2023 only
    features = bundle["features"]
    logger.info(f"  Features: {len(features)}, alpha: {pipe.named_steps['ridge'].alpha_:.1f}")

    # ── Training sigma ───────────────────────────────────────────────────────
    logger.info("Computing training residual sigma (2022+2023)...")
    train_sigma, train_bias = compute_train_sigma(pipe, features)
    logger.info(f"  sigma={train_sigma:.4f}  bias={train_bias:+.4f}")

    # ── Evaluate seasons ─────────────────────────────────────────────────────
    seasons_to_run = [VALIDATE_YEAR] if args.no_2025 else [VALIDATE_YEAR, OOS_YEAR]
    all_sim_dfs = {}

    for yr in seasons_to_run:
        label = f"{yr} {'Validate' if yr == VALIDATE_YEAR else 'OOS'}"
        logger.info(f"Simulating {label}...")

        df_yr   = load_features([yr])
        actual  = df_yr["actual_total"].values
        ridge   = ridge_predict(df_yr, pipe, features)

        sim_df  = simulate_games(
            ridge_preds   = ridge,
            sigma         = train_sigma,
            line          = PROXY_LINE,
            n_sims        = N_SIMS,
            ci_level      = CI_LEVEL,
            rng           = rng,
        )

        # Attach game-level metadata for downstream use
        sim_df["game_pk"]     = df_yr["game_pk"].values
        sim_df["date"]        = df_yr["date"].values
        sim_df["season"]      = df_yr["season"].values
        sim_df["home_team"]   = df_yr["home_team"].values
        sim_df["away_team"]   = df_yr["away_team"].values
        sim_df["actual_total"]= actual
        all_sim_dfs[yr]       = (sim_df, actual, ridge)

        cov = ci_coverage(actual, sim_df["ci_lo"].values, sim_df["ci_hi"].values)
        mae = mean_absolute_error(actual, ridge)
        logger.info(f"  [{label}] MAE={mae:.4f}  80%CI coverage={cov:.1%}  "
                    f"reviews={sim_df['review_flag'].sum()}")

    # ── Build combined output parquet ────────────────────────────────────────
    combined = pd.concat([v[0] for v in all_sim_dfs.values()], ignore_index=True)
    combined.to_parquet(SIM_OUTPUT_PATH, index=False)
    logger.info(f"Saved sim results: {SIM_OUTPUT_PATH}  ({len(combined):,} rows)")

    # ── Full calibration report ──────────────────────────────────────────────
    report_lines: list[str] = []

    def hdr(s: str):
        print(s)
        report_lines.append(s)

    hdr("=" * 76)
    hdr("PHASE 5 — MONTE CARLO SIMULATION REPORT")
    hdr("=" * 76)
    hdr("")
    hdr("BASELINE LABEL: Ridge regression (α=500, train=2022+2023).")
    hdr("  This is a strong directional baseline, NOT a finished sharp model.")
    hdr("  Pred std ~0.93 vs actual std ~4.5 — simulation adds a probability")
    hdr("  wrapper around a compressed forecast; it does NOT fix range compression.")
    hdr("")
    hdr(f"Sigma source:  training residual std (2022+2023), σ={train_sigma:.4f} runs")
    hdr(f"Sim draws:     {N_SIMS:,} per game, N(ridge_pred, σ)  [zero-mean noise]")
    hdr(f"CI level:      {CI_LEVEL:.0%}  (target coverage)")
    hdr(f"Proxy line:    {PROXY_LINE}  (league season mean — NOT actual posted totals)")
    hdr(f"Review flag:   |edge| ≥ {REVIEW_EDGE} runs vs proxy line  ← unverified against market")
    hdr("")

    for yr, (sim_df, actual, ridge) in all_sim_dfs.items():
        label = f"{yr} {'Validate' if yr == VALIDATE_YEAR else 'OOS'}"
        df_yr = load_features([yr])
        print_report(
            label      = label,
            df_eval    = df_yr,
            sim_df     = sim_df,
            actual     = actual,
            ridge_pred = ridge,
            train_sigma= train_sigma,
            train_bias = train_bias,
            report_lines = report_lines,
        )

    # ── Side-by-side summary ─────────────────────────────────────────────────
    if len(all_sim_dfs) == 2:
        hdr("")
        hdr("=" * 76)
        hdr("SIDE-BY-SIDE SUMMARY")
        hdr("=" * 76)
        hdr(f"  {'Metric':<32}  {'2024 Validate':>14}  {'2025 OOS':>14}")
        hdr(f"  {'─'*32}  {'─'*14}  {'─'*14}")

        rows_24, act_24, ridge_24 = all_sim_dfs[VALIDATE_YEAR]
        rows_25, act_25, ridge_25 = all_sim_dfs[OOS_YEAR]

        cov_24 = ci_coverage(act_24, rows_24["ci_lo"].values, rows_24["ci_hi"].values)
        cov_25 = ci_coverage(act_25, rows_25["ci_lo"].values, rows_25["ci_hi"].values)

        hits_24 = probability_hit_table(act_24, rows_24["p_over"].values)
        hits_25 = probability_hit_table(act_25, rows_25["p_over"].values)

        rev_24 = rows_24["review_flag"].values
        rev_25 = rows_25["review_flag"].values

        def sbrow(metric, v24, v25):
            s = f"  {metric:<32}  {v24:>14}  {v25:>14}"
            print(s)
            report_lines.append(s)

        sbrow("N games",
              f"{len(act_24):,}", f"{len(act_25):,}")
        sbrow("Ridge MAE",
              f"{mean_absolute_error(act_24, ridge_24):.4f}",
              f"{mean_absolute_error(act_25, ridge_25):.4f}")
        sbrow("Training sigma (shared)",
              f"{train_sigma:.4f}", f"{train_sigma:.4f}")
        sbrow("80% CI coverage",
              f"{cov_24:.1%}", f"{cov_25:.1%}")
        sbrow("CI width (mean)",
              f"{(rows_24['ci_hi']-rows_24['ci_lo']).mean():.3f} runs",
              f"{(rows_25['ci_hi']-rows_25['ci_lo']).mean():.3f} runs")
        sbrow("Hit% at P≥0.50 threshold",
              f"{hits_24[0.50]['hit_rate']:.1%}",
              f"{hits_25[0.50]['hit_rate']:.1%}")
        sbrow("Hit% at P≥0.55 threshold",
              f"{hits_24[0.55]['hit_rate']:.1%}",
              f"{hits_25[0.55]['hit_rate']:.1%}")
        sbrow("Review flags (|edge|≥2.5)",
              f"{rev_24.sum()} ({rev_24.mean():.1%})",
              f"{rev_25.sum()} ({rev_25.mean():.1%})")

        # Review hit rates
        if rev_24.sum() > 0 and rev_25.sum() > 0:
            rev_hits_24 = probability_hit_table(act_24[rev_24], rows_24["p_over"].values[rev_24])
            rev_hits_25 = probability_hit_table(act_25[rev_25], rows_25["p_over"].values[rev_25])
            sbrow("Review hit% at P≥0.50",
                  f"{rev_hits_24[0.50]['hit_rate']:.1%}",
                  f"{rev_hits_25[0.50]['hit_rate']:.1%}")

        hdr("")
        hdr("  ⚠ MODEL STATUS: Strong directional baseline. NOT a finished sharp model.")
        hdr("  ⚠ REVIEW FLAGS: Based on proxy line (8.86). NOT verified vs market totals.")
        hdr("  ⚠ CI RANGE:     Simulation adds probability bounds; does not fix pred std ~0.93.")

    hdr("")
    hdr("=" * 76)

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))
    logger.info(f"Report saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
