#!/usr/bin/env python3
"""
Phase 6 — H1 out-of-sample test (2025-26) + H1 simulation layer.

Pipeline
--------
1. Build 2025-26 game features via phase4b.build_2526_features()
2. Fetch 2025-26 H1 scores via fetch_halftime_season(CURRENT_SEASON)
3. Merge H1 scores and compute rolling_h1_league_avg for 2025-26
   (prior = 2024-25 actual H1 mean from h1_features.parquet)
4. Apply h1_ridge_model.pkl — NO retraining
5. Run full H1 diagnostic suite (same as backtest_h1.py)
6. Run H1 simulation using h1_sigma from the model bundle
7. Load 2024-25 val (h1_predictions.parquet) and run identical simulation
8. Cross-season comparison table: 2024-25 val vs 2025-26 OOS

Framing
-------
• H1 residual σ (h1_sigma, ≈13 pts) is used for simulation — NOT 18.62.
• Compressed prediction range is a feature-set limitation, not a ceiling.
• All comparisons are apples-to-apples: same diagnostic code, same dataset
  membership criteria (season label), separate metrics per season.
"""

import logging
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd
from scipy import stats

from nba.config import (
    CURRENT_SEASON,
    H1_FEATURES_PATH,
    LEAGUE_AVG_H1_TOTAL,
    PRIOR_SEASON_WEIGHT,
    SEASON_BLEND_END,
    SEASON_BLEND_START,
    SIMULATION_N_ITER,
    VALIDATION_SEASON,
)
from nba.modules.fetch_halftime import fetch_halftime_season
from nba.modules.simulate import _DIVERGENCE_FLAG, simulate_games
from nba.phase4b import build_2526_features

logger = logging.getLogger(__name__)

NBA_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(NBA_DIR, "data", "h1_ridge_model.pkl")
PRED_PATH  = os.path.join(NBA_DIR, "data", "h1_predictions.parquet")
OOS_PATH   = os.path.join(NBA_DIR, "data", "h1_predictions_6b.parquet")
SIM_VAL_PATH = os.path.join(NBA_DIR, "data", "h1_sim_val.parquet")
SIM_OOS_PATH = os.path.join(NBA_DIR, "data", "h1_sim_oos.parquet")

SEP  = "═" * 68
SEP2 = "─" * 68

FEATURE_COLS = [
    "home_ortg", "away_ortg",
    "home_drtg", "away_drtg",
    "home_pace", "away_pace",
    "b2b_flag_away",
    "home_ortg_trend", "away_ortg_trend",
    "home_pace_trend", "away_pace_trend",
    "home_3pa_rate", "away_3pa_rate",
    "home_ft_rate",  "away_ft_rate",
]


# ── Build 2025-26 H1 features ─────────────────────────────────────────────────

def build_h1_2526_features(model_bundle: dict) -> pd.DataFrame:
    """
    Build first-half features for 2025-26 completed games:
      1. Full-game features from phase4b.build_2526_features()
      2. Fetch H1 scores for CURRENT_SEASON
      3. Merge, compute rolling_h1_league_avg (prior = 2024-25 H1 mean)
      4. Apply h1_ridge_model to produce pred_h1
    Returns DataFrame ready for H1 diagnostics.
    """
    logger.info("Building 2025-26 full-game features …")
    feat = build_2526_features()
    feat["date"] = pd.to_datetime(feat["date"])

    logger.info(f"Fetching 2025-26 H1 scores …")
    # Pass feat as games_df — CURRENT_SEASON not in games.parquet (historical only)
    h1_df = fetch_halftime_season(CURRENT_SEASON, games_df=feat)
    if h1_df.empty:
        raise RuntimeError(f"No H1 data returned for {CURRENT_SEASON}. Check API connectivity.")
    logger.info(f"  {len(h1_df)} H1 game rows for {CURRENT_SEASON}")

    # Drop H1 entries where ScoreboardV2 returned 0 for both Q1+Q2 (API data gap)
    n_zero = (h1_df["actual_h1_total"] < 80).sum()
    if n_zero:
        logger.warning(
            f"Dropping {n_zero} H1 rows with actual_h1_total < 80 pts "
            f"(ScoreboardV2 returned null Q1/Q2 — API data gap)"
        )
        h1_df = h1_df[h1_df["actual_h1_total"] >= 80].copy()

    # Inner join — only keep games that have both features and H1 scores
    merged = feat.merge(
        h1_df[["game_id", "home_h1", "away_h1", "actual_h1_total"]],
        on="game_id",
        how="inner",
    )
    n_dropped = len(feat) - len(merged)
    if n_dropped:
        logger.warning(f"Dropped {n_dropped} games with missing H1 data (API gaps)")
    logger.info(f"Merged: {len(merged)} 2025-26 games with H1 scores")

    # Rolling H1 league avg for 2025-26 (no leakage)
    # Prior = 2024-25 actual H1 mean from h1_features.parquet
    if os.path.exists(H1_FEATURES_PATH):
        hist_h1 = pd.read_parquet(H1_FEATURES_PATH)
        prior_h1_mean = hist_h1[hist_h1["season"] == VALIDATION_SEASON]["actual_h1_total"].mean()
        logger.info(f"Prior H1 mean (2024-25): {prior_h1_mean:.2f} pts")
    else:
        prior_h1_mean = LEAGUE_AVG_H1_TOTAL
        logger.warning(f"h1_features.parquet not found — falling back to LEAGUE_AVG_H1_TOTAL={LEAGUE_AVG_H1_TOTAL}")

    merged = merged.sort_values("date").reset_index(drop=True)
    rla_vals = []
    for i in range(len(merged)):
        past = merged.iloc[:i]["actual_h1_total"]
        n_past = len(past)
        cur_mean = past.mean() if n_past > 0 else prior_h1_mean
        if n_past >= SEASON_BLEND_END:
            blended = cur_mean
        elif n_past <= SEASON_BLEND_START:
            blended = PRIOR_SEASON_WEIGHT * prior_h1_mean + (1 - PRIOR_SEASON_WEIGHT) * cur_mean
        else:
            t = (n_past - SEASON_BLEND_START) / (SEASON_BLEND_END - SEASON_BLEND_START)
            w = PRIOR_SEASON_WEIGHT * (1 - t)
            blended = w * prior_h1_mean + (1 - w) * cur_mean
        rla_vals.append(round(blended, 2))
    merged["rolling_h1_league_avg"] = rla_vals

    # Apply H1 Ridge model
    model   = model_bundle["model"]
    scaler  = model_bundle["scaler"]
    X = scaler.transform(merged[FEATURE_COLS].values)
    merged["pred_h1"] = model.predict(X)
    merged["abs_err"] = (merged["pred_h1"] - merged["actual_h1_total"]).abs()

    merged["season"] = CURRENT_SEASON
    return merged


# ── Diagnostic sections (H1-specific) ─────────────────────────────────────────

def sec_accuracy(df: pd.DataFrame, label: str) -> None:
    print(SEP)
    print(f"  1. H1 ACCURACY — {label}")
    print(SEP)
    err = df["pred_h1"] - df["actual_h1_total"]
    print(f"""
   n games       : {len(df)}
   MAE           : {err.abs().mean():.2f} pts
   Median |err|  : {err.abs().median():.2f} pts
   RMSE          : {np.sqrt((err**2).mean()):.2f} pts
   Bias          : {err.mean():+.2f} pts  {'(model over-projects)' if err.mean() > 0 else '(model under-projects)'}
   90th pct err  : {err.abs().quantile(0.90):.2f} pts
""")
    early = df[df["date"].dt.month.isin([10, 11, 12])]
    late  = df[~df["date"].dt.month.isin([10, 11, 12])]
    if len(early):
        print(f"   Early season (Oct–Dec):  n={len(early):>4}  MAE={early['abs_err'].mean():.2f}  "
              f"bias={(early['pred_h1'] - early['actual_h1_total']).mean():+.2f}")
    if len(late):
        print(f"   Late season  (Jan–Apr):  n={len(late):>4}  MAE={late['abs_err'].mean():.2f}  "
              f"bias={(late['pred_h1'] - late['actual_h1_total']).mean():+.2f}")
    print()


def sec_directional(df: pd.DataFrame, label: str) -> None:
    print(SEP)
    print(f"  2. H1 OVER/UNDER DIRECTIONAL HIT RATE — {label}")
    print(SEP)

    v = df.copy()
    rla = v["rolling_h1_league_avg"]

    over_pred  = (v["actual_h1_total"] > v["pred_h1"]).sum()
    under_pred = (v["actual_h1_total"] < v["pred_h1"]).sum()
    over_rate  = over_pred / (over_pred + under_pred) * 100

    v["lean"]    = np.where(v["pred_h1"] > rla, "OVER", "UNDER")
    v["correct"] = (
        ((v["lean"] == "OVER")  & (v["actual_h1_total"] > rla)) |
        ((v["lean"] == "UNDER") & (v["actual_h1_total"] < rla))
    )
    dir_hr = v["correct"].mean() * 100

    print(f"""
   Over rate (pred as line)             : {over_rate:.1f}%
   Directional hit rate (vs H1 avg)     : {dir_hr:.1f}%
   OVER  lean: n={v[v['lean']=='OVER'].shape[0]:>3}  hit={(v[v['lean']=='OVER']['correct'].mean()*100):.1f}%
   UNDER lean: n={v[v['lean']=='UNDER'].shape[0]:>3}  hit={(v[v['lean']=='UNDER']['correct'].mean()*100):.1f}%
""")

    v["edge"] = (v["pred_h1"] - rla).abs()
    bins   = [0, 1, 2, 3, 4, 100]
    labels = ["0-1 pts", "1-2 pts", "2-3 pts", "3-4 pts", "4+ pts"]
    v["edge_bin"] = pd.cut(v["edge"], bins=bins, labels=labels)
    print(f"   Hit rate by |proj − H1_avg| (confidence proxy):")
    print(f"   {'Bucket':<12} {'n':>5} {'hit_rate':>10} {'avg_actual_move':>16}")
    print(f"   {SEP2[:48]}")
    for lbl in labels:
        sub = v[v["edge_bin"] == lbl]
        if len(sub) == 0:
            continue
        hr      = sub["correct"].mean() * 100
        avg_mov = (sub["actual_h1_total"] - sub["rolling_h1_league_avg"]).mean()
        print(f"   {lbl:<12} {len(sub):>5} {hr:>10.1f}% {avg_mov:>+16.2f} pts")
    print()


def sec_edge_distribution(df: pd.DataFrame, label: str) -> float:
    print(SEP)
    print(f"  3. H1 EDGE DISTRIBUTION VS ACTUAL OUTCOMES — {label}")
    print(SEP)

    v = df.copy()
    rla = v["rolling_h1_league_avg"]
    v["edge"]        = v["pred_h1"] - rla
    v["actual_move"] = v["actual_h1_total"] - rla
    v["abs_err"]     = (v["pred_h1"] - v["actual_h1_total"]).abs()

    bins   = [-99, -4, -2, -1, 1, 2, 4, 99]
    labels = ["≤ −4", "−4 to −2", "−2 to −1", "−1 to +1", "+1 to +2", "+2 to +4", "≥ +4"]
    v["edge_bin"] = pd.cut(v["edge"], bins=bins, labels=labels)

    print(f"\n   {'Bucket':<14} {'n':>5} {'avg_pred':>9} {'avg_act':>8} "
          f"{'avg_move':>10} {'over%':>7} {'MAE':>7}")
    print(f"   {SEP2[:68]}")
    prev_over = None
    for lbl in labels:
        sub = v[v["edge_bin"] == lbl]
        if len(sub) == 0:
            continue
        over_pct = (sub["actual_h1_total"] > sub["rolling_h1_league_avg"]).mean() * 100
        flag = ""
        if prev_over is not None and over_pct < prev_over - 3:
            flag = "  ⚠ break"
        prev_over = over_pct
        print(f"   {lbl:<14} {len(sub):>5} {sub['pred_h1'].mean():>9.2f} "
              f"{sub['actual_h1_total'].mean():>8.2f} {sub['actual_move'].mean():>+10.2f} "
              f"{over_pct:>7.1f}% {sub['abs_err'].mean():>7.2f}{flag}")

    rho, pval = stats.spearmanr(v["edge"], v["actual_move"])
    print(f"\n   Spearman ρ (H1 edge vs H1 actual_move) = {rho:.4f}  p={pval:.4f}")
    verdict = "SIGNIFICANT ✓" if pval < 0.05 else "NOT SIGNIFICANT ✗"
    print(f"   {verdict}")
    print()
    return rho


def sec_tail_compression(df: pd.DataFrame, label: str) -> None:
    print(SEP)
    print(f"  4. H1 TAIL COMPRESSION — {label}")
    print(SEP)

    v = df.copy()
    v["actual_q"] = pd.qcut(v["actual_h1_total"], q=5,
                             labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"])
    pred_std = v["pred_h1"].std()
    act_std  = v["actual_h1_total"].std()

    print(f"""
   Predicted H1 range: min={v['pred_h1'].min():.1f}  max={v['pred_h1'].max():.1f}  σ={pred_std:.1f}
   Actual H1 range  : min={v['actual_h1_total'].min():.1f}  max={v['actual_h1_total'].max():.1f}  σ={act_std:.1f}
""")
    print(f"   {'Quintile':<12} {'n':>5} {'act_mean':>9} {'pred_mean':>10} {'MAE':>8} {'Bias':>9}")
    print(f"   {SEP2[:60]}")
    for q in ["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"]:
        sub = v[v["actual_q"] == q]
        err = sub["pred_h1"] - sub["actual_h1_total"]
        flag = "  ⚠ TAIL" if q in ("Q1(low)", "Q5(high)") else ""
        print(f"   {str(q):<12} {len(sub):>5} {sub['actual_h1_total'].mean():>9.2f} "
              f"{sub['pred_h1'].mean():>10.2f} {err.abs().mean():>8.2f} {err.mean():>+9.2f}{flag}")
    print()


# ── H1 simulation diagnostics ─────────────────────────────────────────────────

def run_h1_simulation(df: pd.DataFrame, h1_sigma: float, save_path: str, label: str) -> pd.DataFrame:
    """Run Monte Carlo simulation on H1 predictions and save results."""
    print(f"\n   Running H1 simulation ({len(df)} games, σ={h1_sigma:.2f} pts, {SIMULATION_N_ITER:,} iter) …")
    sim = simulate_games(
        df,
        pred_col="pred_h1",
        line_col="rolling_h1_league_avg",
        sigma=h1_sigma,
        n_iter=SIMULATION_N_ITER,
        seed=42,
    )
    sim.to_parquet(save_path, index=False)
    logger.info(f"H1 simulation saved → {save_path}")
    return sim


def sec_sim_divergence(sim: pd.DataFrame, h1_sigma: float, label: str) -> None:
    print(SEP)
    print(f"  5. H1 SIMULATION DIVERGENCE CHECK — {label}")
    print(SEP)

    div = sim["divergence"]
    n_flagged = (div > _DIVERGENCE_FLAG).sum()
    se = h1_sigma / SIMULATION_N_ITER**0.5

    print(f"""
   n games          : {len(sim)}
   n_iter / game    : {SIMULATION_N_ITER:,}
   H1 sigma used    : {h1_sigma:.2f} pts  (H1 training residual σ)
   MC SE of mean    : {se:.4f} pts  (expected max noise ≈ 3×SE)

   Divergence stats (|sim_mean − pred_h1|):
   mean   : {div.mean():.4f} pts
   max    : {div.max():.4f} pts  (expected ≲ {3 * se:.3f} pts at 3σ)
   p99    : {div.quantile(0.99):.4f} pts
   flagged (> {_DIVERGENCE_FLAG} pts) : {n_flagged}

   {"✓  All games within expected Monte Carlo noise" if n_flagged == 0
    else f"⚠  {n_flagged} game(s) exceeded {_DIVERGENCE_FLAG} pt flag — investigate"}
""")


def sec_sim_calibration(sim: pd.DataFrame, h1_sigma: float, label: str) -> dict:
    print(SEP)
    print(f"  6. H1 PROBABILITY CALIBRATION — {label}")
    print(SEP)

    v = sim.copy()
    line = v["rolling_h1_league_avg"]
    v["went_over"] = (v["actual_h1_total"] > line).astype(int)

    bins = np.arange(0.30, 0.76, 0.05)
    bin_labels = [f"{b:.0%}–{b+0.05:.0%}" for b in bins[:-1]]
    v["prob_bin"] = pd.cut(v["p_over"], bins=bins, labels=bin_labels).astype(object)
    v.loc[v["p_over"] < 0.30, "prob_bin"] = "< 30%"
    v.loc[v["p_over"] >= 0.75, "prob_bin"] = "≥ 75%"
    order = ["< 30%"] + bin_labels + ["≥ 75%"]

    print(f"\n   {'Bucket':<14} {'n':>5} {'implied':>9} {'actual':>9} {'diff':>8}")
    print(f"   {SEP2[:50]}")
    for bkt in order:
        sub = v[v["prob_bin"] == bkt]
        if len(sub) < 5:
            continue
        imp  = sub["p_over"].mean()
        ar   = sub["went_over"].mean()
        diff = ar - imp
        flag = "  ⚠" if abs(diff) > 0.08 else ""
        print(f"   {bkt:<14} {len(sub):>5} {imp:>9.1%} {ar:>9.1%} {diff:>+8.1%}{flag}")

    brier       = ((v["p_over"] - v["went_over"]) ** 2).mean()
    brier_naive = ((0.5 - v["went_over"]) ** 2).mean()
    bss         = 1 - brier / brier_naive
    print(f"\n   Brier score       : {brier:.4f}  (naive: {brier_naive:.4f})")
    print(f"   Brier skill score : {bss:+.4f}  (0 = naive; 1 = perfect)")
    print()
    return {"brier": brier, "bss": bss}


def sec_sim_ci_coverage(sim: pd.DataFrame, h1_sigma: float, label: str) -> float:
    print(SEP)
    print(f"  7. H1 80% CI COVERAGE — {label}")
    print(SEP)

    v = sim.copy()
    in_ci = (
        (v["actual_h1_total"] >= v["ci_80_low"]) &
        (v["actual_h1_total"] <= v["ci_80_high"])
    )
    coverage  = in_ci.mean() * 100
    avg_width = v["ci_80_width"].mean()

    print(f"""
   Expected coverage (80% CI) : 80.0%
   Actual coverage            : {coverage:.1f}%
   {'✓  Well-calibrated' if abs(coverage - 80.0) < 3.0 else '⚠  Coverage drift > 3 pts from expected 80%'}

   CI mean width : {avg_width:.1f} pts
   Theoretical   : {h1_sigma * 2 * 1.282:.1f} pts  (2 × 1.282 × {h1_sigma:.2f})

   Note: CI uses H1 residual σ = {h1_sigma:.2f} pts, NOT full-game σ = 18.62 pts.
""")
    return coverage


# ── Cross-season summary ──────────────────────────────────────────────────────

def sec_cross_season_summary(
    val_df: pd.DataFrame, oos_df: pd.DataFrame,
    val_sim: pd.DataFrame, oos_sim: pd.DataFrame,
    h1_sigma: float,
    val_rho: float, oos_rho: float,
    val_cal: dict, oos_cal: dict,
    val_cov: float, oos_cov: float,
) -> None:
    print(SEP)
    print("  PHASE 6 SUMMARY — H1 CROSS-SEASON COMPARISON")
    print(SEP)

    def _metrics(df, sim, label):
        err  = df["pred_h1"] - df["actual_h1_total"]
        rla  = df["rolling_h1_league_avg"]
        lean = np.where(df["pred_h1"] > rla, "OVER", "UNDER")
        correct = (
            ((lean == "OVER")  & (df["actual_h1_total"] > rla)) |
            ((lean == "UNDER") & (df["actual_h1_total"] < rla))
        )
        return {
            "n":    len(df),
            "mae":  err.abs().mean(),
            "rmse": np.sqrt((err**2).mean()),
            "bias": err.mean(),
            "hr":   correct.mean() * 100,
        }

    vm = _metrics(val_df, val_sim, "val")
    om = _metrics(oos_df, oos_sim, "oos")

    print(f"""
   ┌──────────────────────────────────────────────────────────────────┐
   │  Metric                          2024-25 (val)   2025-26 (OOS)  │
   ├──────────────────────────────────────────────────────────────────┤
   │  n games                              {vm['n']:>6}          {om['n']:>6}  │
   │  H1 training σ (simulation)           {h1_sigma:.2f} pts      {h1_sigma:.2f} pts  │
   │  MAE                                  {vm['mae']:>5.2f} pts      {om['mae']:>5.2f} pts  │
   │  RMSE                                 {vm['rmse']:>5.2f} pts      {om['rmse']:>5.2f} pts  │
   │  Bias                                {vm['bias']:>+6.2f} pts     {om['bias']:>+6.2f} pts  │
   │  Directional HR (vs H1 avg)           {vm['hr']:>5.1f}%          {om['hr']:>5.1f}%  │
   │  Spearman ρ (H1 edge monotonicity)   {val_rho:>6.3f}          {oos_rho:>6.3f}  │
   │  Brier skill score                   {val_cal['bss']:>+6.4f}         {oos_cal['bss']:>+6.4f}  │
   │  80% CI coverage                      {val_cov:>5.1f}%          {oos_cov:>5.1f}%  │
   └──────────────────────────────────────────────────────────────────┘

   Known limitations carried forward:
   • Compressed H1 prediction range (feature-set limitation, not ceiling).
   • Tail games (Q1/Q5) MAE elevated — model anchors near H1 league mean.
   • H1 sigma ({h1_sigma:.2f} pts) correctly differs from full-game σ (18.62 pts).
   • EDGE_THRESHOLD_HALF in config.py is a placeholder — calibrate separately.

   Status: PHASE 6 COMPLETE — H1 model and simulation layer operational.
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'═' * 68}")
    print("  PHASE 6 — H1 OUT-OF-SAMPLE TEST + SIMULATION")
    print(f"{'═' * 68}\n")

    # Load model bundle
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"h1_ridge_model.pkl not found. Run: python nba/train_h1_model.py"
        )
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    h1_sigma = bundle.get("h1_sigma", 13.0)
    print(f"   H1 model loaded | h1_sigma = {h1_sigma:.2f} pts\n")

    # ── 2025-26 OOS ──────────────────────────────────────────────────────────
    print(SEP)
    print("  BUILDING 2025-26 H1 FEATURES")
    print(SEP)
    oos_df = build_h1_2526_features(bundle)
    print(f"\n   2025-26 H1 games : {len(oos_df)}")
    print(f"   H1 avg (OOS)     : {oos_df['actual_h1_total'].mean():.2f} pts")
    print(f"   Rolling H1 avg   : {oos_df['rolling_h1_league_avg'].mean():.2f} pts (mean)\n")

    oos_df.to_parquet(OOS_PATH, index=False)
    logger.info(f"2025-26 H1 predictions saved → {OOS_PATH}")

    # OOS diagnostics
    print(f"\n{'═' * 68}")
    print("  2025-26 OUT-OF-SAMPLE DIAGNOSTICS")
    print(f"{'═' * 68}")
    sec_accuracy(oos_df, "2025-26 OUT-OF-SAMPLE")
    sec_directional(oos_df, "2025-26 OUT-OF-SAMPLE")
    oos_rho = sec_edge_distribution(oos_df, "2025-26 OUT-OF-SAMPLE")
    sec_tail_compression(oos_df, "2025-26 OUT-OF-SAMPLE")

    # OOS simulation
    oos_sim = run_h1_simulation(oos_df, h1_sigma, SIM_OOS_PATH, "2025-26 OOS")
    sec_sim_divergence(oos_sim, h1_sigma, "2025-26 OUT-OF-SAMPLE")
    oos_cal = sec_sim_calibration(oos_sim, h1_sigma, "2025-26 OUT-OF-SAMPLE")
    oos_cov = sec_sim_ci_coverage(oos_sim, h1_sigma, "2025-26 OUT-OF-SAMPLE")

    # ── 2024-25 Validation ────────────────────────────────────────────────────
    if not os.path.exists(PRED_PATH):
        raise FileNotFoundError(
            f"h1_predictions.parquet not found. Run: python nba/train_h1_model.py"
        )
    print(f"\n{'═' * 68}")
    print("  2024-25 VALIDATION DIAGNOSTICS  (apples-to-apples)")
    print(f"{'═' * 68}")

    preds = pd.read_parquet(PRED_PATH)
    val_df = preds[preds["season"] == VALIDATION_SEASON].copy()
    val_df["date"] = pd.to_datetime(val_df["date"])
    val_df["abs_err"] = (val_df["pred_h1"] - val_df["actual_h1_total"]).abs()
    print(f"\n   2024-25 val games : {len(val_df)}\n")

    sec_accuracy(val_df, "2024-25 VALIDATION")
    sec_directional(val_df, "2024-25 VALIDATION")
    val_rho = sec_edge_distribution(val_df, "2024-25 VALIDATION")
    sec_tail_compression(val_df, "2024-25 VALIDATION")

    val_sim = run_h1_simulation(val_df, h1_sigma, SIM_VAL_PATH, "2024-25 val")
    sec_sim_divergence(val_sim, h1_sigma, "2024-25 VALIDATION")
    val_cal = sec_sim_calibration(val_sim, h1_sigma, "2024-25 VALIDATION")
    val_cov = sec_sim_ci_coverage(val_sim, h1_sigma, "2024-25 VALIDATION")

    # ── Cross-season summary ──────────────────────────────────────────────────
    sec_cross_season_summary(
        val_df, oos_df,
        val_sim, oos_sim,
        h1_sigma,
        val_rho, oos_rho,
        val_cal, oos_cal,
        val_cov, oos_cov,
    )


if __name__ == "__main__":
    main()
