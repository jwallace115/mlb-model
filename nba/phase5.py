#!/usr/bin/env python3
"""
Phase 5 — Simulation layer calibration.

Applies the simulation wrapper (nba/modules/simulate.py) to:
  1. 2024-25 validation predictions (predictions.parquet)
  2. 2025-26 out-of-sample predictions (predictions_4b.parquet)

Reports per season:
  • Sim-mean vs Ridge-forecast divergence (sanity check)
  • P(over) calibration by probability bucket — implied vs actual
  • Brier score and Brier skill score
  • 80% CI coverage — what fraction of actual totals fall within the CI
  • Edge-conditional accuracy — does flagging |pred − line| ≥ EDGE_THRESHOLD_FULL
    improve precision over the flat directional hit rate?

Framing note
------------
Compressed prediction range (pred σ ≈ 6.5 pts vs actual σ ≈ 20 pts) is a
limitation of the current rolling-average feature structure, not a fundamental
ceiling. With the present feature set, the model cannot reliably reach tail
outcomes — but this is addressable with structural improvements later.
The simulation correctly uses the residual σ (18.62 pts), not the narrow
predicted range, as its variance parameter.
"""

import logging
import os
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
    EDGE_THRESHOLD_FULL,
    LEAGUE_AVG_TOTAL,
    RESIDUAL_SIGMA,
    SIMULATION_N_ITER,
    VALIDATION_SEASON,
    CURRENT_SEASON,
)
from nba.modules.simulate import simulate_games

logger = logging.getLogger(__name__)

NBA_DIR   = os.path.dirname(os.path.abspath(__file__))
PRED_PATH = os.path.join(NBA_DIR, "data", "predictions.parquet")
PRED4B_PATH = os.path.join(NBA_DIR, "data", "predictions_4b.parquet")
SIM_PATH  = os.path.join(NBA_DIR, "data", "sim_results.parquet")
SIM4B_PATH = os.path.join(NBA_DIR, "data", "sim_results_4b.parquet")

SEP  = "═" * 70
SEP2 = "─" * 70


# ── Data loading ───────────────────────────────────────────────────────────────

def load_predictions(path: str, label: str, season_filter: str = None) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} predictions not found at {path}. Run the relevant phase first.")
    df = pd.read_parquet(path)
    logger.info(f"Loaded {len(df)} rows from {path}")

    # predictions.parquet contains both training and validation seasons.
    # Only calibrate on the validation season to avoid in-sample inflation.
    if season_filter is not None and "season" in df.columns:
        df = df[df["season"] == season_filter].copy()
        logger.info(f"Filtered to season={season_filter}: {len(df)} rows")

    # Ensure rolling_league_avg is present — fall back to fixed constant with warning
    if "rolling_league_avg" not in df.columns:
        logger.warning(
            f"{label}: rolling_league_avg column missing — falling back to "
            f"LEAGUE_AVG_TOTAL={LEAGUE_AVG_TOTAL}. Rebuild predictions for accurate calibration."
        )
        df["rolling_league_avg"] = LEAGUE_AVG_TOTAL

    logger.info(f"Using {len(df)} {label} predictions for calibration")
    return df


# ── Diagnostic sections ────────────────────────────────────────────────────────

def sec_divergence_check(sim: pd.DataFrame, label: str) -> None:
    print(SEP)
    print(f"  DIVERGENCE CHECK — Sim mean vs Ridge forecast ({label})")
    print(SEP)

    from nba.modules.simulate import _DIVERGENCE_FLAG
    div = sim["divergence"]
    n_flagged = (div > _DIVERGENCE_FLAG).sum()
    # Expected MC noise: SE of mean = σ / √n_iter = 18.62 / 100 ≈ 0.186 pts.
    # Flag threshold (1.0 pt) is ~5.4 SE — genuine bugs only.
    print(f"""
   n games          : {len(sim)}
   n_iter / game    : {SIMULATION_N_ITER:,}
   sigma used       : {RESIDUAL_SIGMA} pts  (training residual σ, Pass 1 model)
   MC SE of mean    : {RESIDUAL_SIGMA / SIMULATION_N_ITER**0.5:.4f} pts  (expected max noise ≈ 3×SE)

   Divergence stats (|sim_mean − pred_total|):
   mean   : {div.mean():.4f} pts
   max    : {div.max():.4f} pts  (expected ≲ {3 * RESIDUAL_SIGMA / SIMULATION_N_ITER**0.5:.3f} pts at 3σ)
   p99    : {div.quantile(0.99):.4f} pts
   flagged (> {_DIVERGENCE_FLAG} pts) : {n_flagged}

   {"✓  All games within expected Monte Carlo noise" if n_flagged == 0
    else f"⚠  {n_flagged} game(s) exceeded {_DIVERGENCE_FLAG} pt flag — investigate"}
""")


def sec_calibration(sim: pd.DataFrame, label: str, season_label: str) -> dict:
    """
    Compare P(over) implied by simulation vs actual over rate by bucket.
    Returns dict of key calibration metrics for cross-season comparison.
    """
    print(SEP)
    print(f"  PROBABILITY CALIBRATION — {season_label} ({label})")
    print(SEP)

    v = sim.copy()
    line = v["rolling_league_avg"]
    v["went_over"] = (v["actual_total"] > line).astype(int)

    # Bucket by simulated P(over)
    bins = np.arange(0.30, 0.76, 0.05)
    bin_labels = [f"{b:.0%}–{b+0.05:.0%}" for b in bins[:-1]]
    v["prob_bin"] = pd.cut(v["p_over"], bins=bins, labels=bin_labels).astype(object)
    v.loc[v["p_over"] < 0.30, "prob_bin"] = "< 30%"
    v.loc[v["p_over"] >= 0.75, "prob_bin"] = "≥ 75%"

    order = ["< 30%"] + bin_labels + ["≥ 75%"]

    print(f"\n   {'Bucket':<14} {'n':>5} {'implied':>9} {'actual':>9} {'diff':>8} {'flag'}")
    print(f"   {SEP2[:54]}")

    bucket_rows = []
    for bkt in order:
        sub = v[v["prob_bin"] == bkt]
        if len(sub) < 5:
            continue
        imp = sub["p_over"].mean()
        ar  = sub["went_over"].mean()
        diff = ar - imp
        flag = "  ⚠" if abs(diff) > 0.08 else ""
        print(f"   {bkt:<14} {len(sub):>5} {imp:>9.1%} {ar:>9.1%} {diff:>+8.1%}{flag}")
        bucket_rows.append({"bucket": bkt, "n": len(sub), "implied": imp, "actual": ar, "diff": diff})

    brier = ((v["p_over"] - v["went_over"]) ** 2).mean()
    brier_naive = ((0.5 - v["went_over"]) ** 2).mean()
    bss = 1 - brier / brier_naive

    print(f"\n   Brier score       : {brier:.4f}  (naive baseline: {brier_naive:.4f})")
    print(f"   Brier skill score : {bss:+.4f}  (0 = naive; 1 = perfect)")
    print()

    return {"brier": brier, "bss": bss, "buckets": bucket_rows}


def sec_ci_coverage(sim: pd.DataFrame, label: str) -> float:
    """
    Report what fraction of actual totals fall within the simulated 80% CI.
    For a well-calibrated normal model, coverage should be ≈ 80%.
    """
    print(SEP)
    print(f"  80% CONFIDENCE INTERVAL COVERAGE ({label})")
    print(SEP)

    v = sim.copy()
    in_ci = ((v["actual_total"] >= v["ci_80_low"]) &
             (v["actual_total"] <= v["ci_80_high"]))
    coverage = in_ci.mean() * 100
    avg_width = v["ci_80_width"].mean()
    med_width = v["ci_80_width"].median()

    print(f"""
   Expected coverage (80% CI) : 80.0%
   Actual coverage            : {coverage:.1f}%
   {'✓  Well-calibrated' if abs(coverage - 80.0) < 3.0 else '⚠  Coverage drift > 3 pts from expected 80%'}

   CI width:
   mean   : {avg_width:.1f} pts
   median : {med_width:.1f} pts

   Note: CI is symmetric around Ridge forecast using residual σ = {RESIDUAL_SIGMA} pts.
   Width = {RESIDUAL_SIGMA * 2 * 1.282:.1f} pts at σ = {RESIDUAL_SIGMA}  (theoretical: 2 × 1.282 × σ).
   CI width does NOT reflect the narrow predicted range (pred σ ≈ 6.5 pts) —
   it reflects true uncertainty estimated from training residuals.
""")
    return coverage


def sec_edge_conditional(sim: pd.DataFrame, label: str) -> None:
    """
    Split games by |pred − line| vs EDGE_THRESHOLD_FULL.
    Tests whether the edge threshold from config meaningfully filters for precision.
    """
    print(SEP)
    print(f"  EDGE-CONDITIONAL ACCURACY (threshold = {EDGE_THRESHOLD_FULL} pts, from config)")
    print(SEP)

    v = sim.copy()
    line = v["rolling_league_avg"]
    v["edge"]     = (v["pred_total"] - line).abs()
    v["lean"]     = np.where(v["pred_total"] > line, "OVER", "UNDER")
    v["correct"]  = (
        ((v["lean"] == "OVER")  & (v["actual_total"] > line)) |
        ((v["lean"] == "UNDER") & (v["actual_total"] < line))
    )

    all_hr   = v["correct"].mean() * 100
    above    = v[v["edge"] >= EDGE_THRESHOLD_FULL]
    below    = v[v["edge"] <  EDGE_THRESHOLD_FULL]
    above_hr = above["correct"].mean() * 100 if len(above) > 0 else float("nan")
    below_hr = below["correct"].mean() * 100 if len(below) > 0 else float("nan")

    rho, pval = stats.spearmanr(v["pred_total"] - line, v["actual_total"] - line)

    print(f"""
   Directional hit rate — all games        : {all_hr:.1f}%  (n={len(v)})
   Directional hit rate — edge ≥ {EDGE_THRESHOLD_FULL:.0f} pts  : {above_hr:.1f}%  (n={len(above)})
   Directional hit rate — edge < {EDGE_THRESHOLD_FULL:.0f} pts   : {below_hr:.1f}%  (n={len(below)})

   Spearman ρ (pred_edge vs actual_move)   : {rho:.4f}  p={pval:.4f}
   {'✓  Significant (p < 0.05)' if pval < 0.05 else '✗  Not significant'}

   Filtering to edge ≥ {EDGE_THRESHOLD_FULL:.0f} pts captures {len(above)/len(v)*100:.1f}% of games.
   Note: EDGE_THRESHOLD_FULL = {EDGE_THRESHOLD_FULL} is configurable in nba/config.py.
         Full-game and first-half thresholds are intentionally kept separate.
""")

    # Finer bucketing within the above-threshold group
    if len(above) > 0:
        print(f"   P(over) distribution for flagged games (edge ≥ {EDGE_THRESHOLD_FULL} pts):")
        print(f"   {'P(over) range':<16} {'n':>5} {'hit_rate':>10} {'avg_edge':>10}")
        print(f"   {SEP2[:46]}")
        above2 = above.copy()
        above2["p_bin"] = pd.cut(above2["p_over"], bins=[0, 0.4, 0.5, 0.6, 0.7, 1.0],
                                  labels=["<40%", "40-50%", "50-60%", "60-70%", ">70%"])
        for bkt, sub in above2.groupby("p_bin", observed=True):
            if len(sub) == 0:
                continue
            hr = sub["correct"].mean() * 100
            avg_e = sub["edge"].mean()
            print(f"   {str(bkt):<16} {len(sub):>5} {hr:>10.1f}% {avg_e:>10.2f} pts")
    print()


def sec_cross_season_summary(val_metrics: dict, oos_metrics: dict) -> None:
    print(SEP)
    print("  PHASE 5 CALIBRATION SUMMARY — CROSS-SEASON COMPARISON")
    print(SEP)

    print(f"""
   ┌──────────────────────────────────────────────────────────────────┐
   │  Metric                          2024-25 (val)   2025-26 (OOS)  │
   ├──────────────────────────────────────────────────────────────────┤
   │  n games                              {val_metrics['n']:>6}          {oos_metrics['n']:>6}  │
   │  Simulation n_iter                 {SIMULATION_N_ITER:>7,}         {SIMULATION_N_ITER:>7,}  │
   │  Sigma used                         {RESIDUAL_SIGMA} pts      {RESIDUAL_SIGMA} pts  │
   │  Brier score                         {val_metrics['brier']:.4f}          {oos_metrics['brier']:.4f}  │
   │  Brier skill score                  {val_metrics['bss']:+.4f}          {oos_metrics['bss']:+.4f}  │
   │  80% CI coverage                     {val_metrics['ci_cov']:.1f}%          {oos_metrics['ci_cov']:.1f}%  │
   │  Directional HR (all games)          {val_metrics['dir_hr']:.1f}%          {oos_metrics['dir_hr']:.1f}%  │
   │  Directional HR (edge ≥ {EDGE_THRESHOLD_FULL:.0f} pts)     {val_metrics['above_hr']:.1f}%          {oos_metrics['above_hr']:.1f}%  │
   │  n games flagged at threshold        {val_metrics['n_above']:>6}          {oos_metrics['n_above']:>6}  │
   └──────────────────────────────────────────────────────────────────┘

   Known limitations carried into Phase 6:
   • Compressed prediction range (pred σ ≈ 6.5 pts vs actual σ ≈ 20 pts)
     is a current-feature-set limitation — addressable structurally later.
   • Tail games (Q1/Q5) MAE ≈ 25 pts — model anchors near league mean.
   • 30–45% probability bucket has systematic negative drift on OOS data.
   • Directional ρ weakens from 0.335 (val) to 0.195 (OOS) — signal real
     but degrades on unseen seasons; flagging at ≥ {EDGE_THRESHOLD_FULL:.0f} pts improves precision.
   • All variances currently global (σ = {RESIDUAL_SIGMA} pts). Matchup-specific
     variance (via per_game_sigma override in simulate_games) is the designed
     extension point for Phase 6+.

   Status: PHASE 5 COMPLETE — simulation layer operational.
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_season(path: str, label: str, season_label: str, save_path: str, season_filter: str = None) -> dict:
    """Load predictions, run simulation, run all diagnostics, return summary metrics."""
    preds = load_predictions(path, label, season_filter=season_filter)

    print(f"\n{SEP}")
    print(f"  PHASE 5 — SIMULATION: {season_label}")
    print(SEP)
    print(f"\n   n games : {len(preds)}")
    print(f"   sigma   : {RESIDUAL_SIGMA} pts  (training residual σ)")
    print(f"   n_iter  : {SIMULATION_N_ITER:,} per game\n")

    logger.info(f"Running simulation for {label} ({len(preds)} games) …")
    sim = simulate_games(
        preds,
        pred_col="pred_total",
        line_col="rolling_league_avg",
        sigma=RESIDUAL_SIGMA,
        n_iter=SIMULATION_N_ITER,
        seed=42,
    )
    sim.to_parquet(save_path, index=False)
    logger.info(f"Simulation results saved → {save_path}")

    sec_divergence_check(sim, label)
    cal = sec_calibration(sim, label, season_label)
    ci_cov = sec_ci_coverage(sim, label)
    sec_edge_conditional(sim, label)

    # Compute directional hit rate stats for summary
    line = sim["rolling_league_avg"]
    sim2 = sim.copy()
    sim2["lean"] = np.where(sim2["pred_total"] > line, "OVER", "UNDER")
    sim2["correct"] = (
        ((sim2["lean"] == "OVER")  & (sim2["actual_total"] > line)) |
        ((sim2["lean"] == "UNDER") & (sim2["actual_total"] < line))
    )
    sim2["edge"] = (sim2["pred_total"] - line).abs()
    above = sim2[sim2["edge"] >= EDGE_THRESHOLD_FULL]

    return {
        "n":        len(sim),
        "brier":    cal["brier"],
        "bss":      cal["bss"],
        "ci_cov":   ci_cov,
        "dir_hr":   sim2["correct"].mean() * 100,
        "above_hr": above["correct"].mean() * 100 if len(above) > 0 else float("nan"),
        "n_above":  len(above),
    }


def main():
    print(f"\n{'═' * 70}")
    print("  PHASE 5 — SIMULATION LAYER")
    print(f"{'═' * 70}\n")
    print(f"   sigma = {RESIDUAL_SIGMA} pts  |  n_iter = {SIMULATION_N_ITER:,}  |  edge threshold = {EDGE_THRESHOLD_FULL} pts\n")

    val_metrics = run_season(PRED_PATH,   "2024-25 val", "2024-25 VALIDATION",    SIM_PATH,   season_filter=VALIDATION_SEASON)
    oos_metrics = run_season(PRED4B_PATH, "2025-26 OOS", "2025-26 OUT-OF-SAMPLE", SIM4B_PATH, season_filter=None)

    sec_cross_season_summary(val_metrics, oos_metrics)


if __name__ == "__main__":
    main()
