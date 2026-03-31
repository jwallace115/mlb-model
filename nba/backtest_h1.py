#!/usr/bin/env python3
"""
Phase 6 — H1 backtest on 2024-25 validation set.

Same diagnostic pipeline as backtest.py (Phase 4) but for first-half totals:
  • MAE, bias, RMSE
  • Q1/Q5 actual-quintile tail MAE
  • Spearman ρ (edge vs actual H1 move)
  • Brier skill score using H1 training residual σ and rolling_h1_league_avg
  • Edge bucket monotonicity table
  • Rest-context and calendar breakdown
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

import pickle

import numpy as np
import pandas as pd
from scipy import stats

from nba.config import (
    H1_FEATURES_PATH,
    MARKET_FLAG_THRESHOLD,
    VALIDATION_SEASON,
)

logger = logging.getLogger(__name__)

NBA_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(NBA_DIR, "data", "h1_ridge_model.pkl")
PRED_PATH  = os.path.join(NBA_DIR, "data", "h1_predictions.parquet")

SEP  = "═" * 68
SEP2 = "─" * 68


def load_data():
    if not os.path.exists(PRED_PATH):
        raise FileNotFoundError(f"h1_predictions.parquet not found. Run train_h1_model.py first.")

    preds = pd.read_parquet(PRED_PATH)
    val   = preds[preds["season"] == VALIDATION_SEASON].copy()
    val["abs_err"] = (val["pred_h1"] - val["actual_h1_total"]).abs()

    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    h1_sigma = bundle.get("h1_sigma", 13.0)  # fallback

    rla_mean = val["rolling_h1_league_avg"].mean()
    print(f"Loaded: {len(val)} validation games | H1 training σ = {h1_sigma:.2f} pts")
    print(f"Rolling H1 avg (val mean): {rla_mean:.2f} pts")
    return val, h1_sigma


def sec_accuracy(val: pd.DataFrame) -> None:
    print(SEP)
    print("  1. OVERALL H1 ACCURACY — 2024-25 VALIDATION")
    print(SEP)
    err = val["pred_h1"] - val["actual_h1_total"]
    print(f"""
   n games       : {len(val)}
   MAE           : {err.abs().mean():.2f} pts
   Median |err|  : {err.abs().median():.2f} pts
   RMSE          : {np.sqrt((err**2).mean()):.2f} pts
   Bias          : {err.mean():+.2f} pts  {'(model over-projects)' if err.mean() > 0 else '(model under-projects)'}
   90th pct err  : {err.abs().quantile(0.90):.2f} pts
""")
    early = val[val["date"].dt.month.isin([10, 11, 12])]
    late  = val[~val["date"].dt.month.isin([10, 11, 12])]
    if len(early):
        print(f"   Early season (Oct–Dec):  n={len(early):>4}  MAE={early['abs_err'].mean():.2f}  "
              f"bias={( early['pred_h1'] - early['actual_h1_total']).mean():+.2f}")
    if len(late):
        print(f"   Late season  (Jan–Apr):  n={len(late):>4}  MAE={late['abs_err'].mean():.2f}  "
              f"bias={(late['pred_h1'] - late['actual_h1_total']).mean():+.2f}")
    print()


def sec_directional(val: pd.DataFrame) -> None:
    print(SEP)
    print("  2. H1 OVER/UNDER DIRECTIONAL HIT RATE")
    print(SEP)

    v = val.copy()
    rla = v["rolling_h1_league_avg"]
    err = v["pred_h1"] - v["actual_h1_total"]

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
    for label in labels:
        sub = v[v["edge_bin"] == label]
        if len(sub) == 0:
            continue
        hr      = sub["correct"].mean() * 100
        avg_mov = (sub["actual_h1_total"] - sub["rolling_h1_league_avg"]).mean()
        print(f"   {label:<12} {len(sub):>5} {hr:>10.1f}% {avg_mov:>+16.2f} pts")
    print()


def sec_calibration(val: pd.DataFrame, h1_sigma: float) -> float:
    print(SEP)
    print("  3. H1 CALIBRATION BY PROBABILITY BUCKET")
    print(SEP)

    v = val.copy()
    L = v["rolling_h1_league_avg"]
    v["p_over"]    = 1 - stats.norm.cdf((L - v["pred_h1"]) / h1_sigma)
    v["went_over"] = (v["actual_h1_total"] > L).astype(int)

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

    brier = ((v["p_over"] - v["went_over"]) ** 2).mean()
    brier_naive = ((0.5 - v["went_over"]) ** 2).mean()
    bss = 1 - brier / brier_naive
    print(f"\n   Brier score       : {brier:.4f}  (naive: {brier_naive:.4f})")
    print(f"   Brier skill score : {bss:+.4f}")
    print()
    return bss


def sec_edge_distribution(val: pd.DataFrame) -> float:
    print(SEP)
    print("  4. H1 EDGE DISTRIBUTION VS ACTUAL OUTCOMES")
    print(SEP)

    v = val.copy()
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
    for label in labels:
        sub = v[v["edge_bin"] == label]
        if len(sub) == 0:
            continue
        over_pct = (sub["actual_h1_total"] > sub["rolling_h1_league_avg"]).mean() * 100
        flag = ""
        if prev_over is not None and over_pct < prev_over - 3:
            flag = "  ⚠ break"
        prev_over = over_pct
        print(f"   {label:<14} {len(sub):>5} {sub['pred_h1'].mean():>9.2f} "
              f"{sub['actual_h1_total'].mean():>8.2f} {sub['actual_move'].mean():>+10.2f} "
              f"{over_pct:>7.1f}% {sub['abs_err'].mean():>7.2f}{flag}")

    rho, pval = stats.spearmanr(v["edge"], v["actual_move"])
    print(f"\n   Spearman ρ (H1 edge vs H1 actual_move) = {rho:.4f}  p={pval:.4f}")
    verdict = "SIGNIFICANT ✓" if pval < 0.05 else "NOT SIGNIFICANT ✗"
    print(f"   {verdict}")
    print()
    return rho


def sec_tail_compression(val: pd.DataFrame) -> None:
    print(SEP)
    print("  5. H1 TAIL COMPRESSION")
    print(SEP)

    v = val.copy()
    v["actual_q"] = pd.qcut(v["actual_h1_total"], q=5,
                             labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"])
    pred_std = (v["pred_h1"]).std()
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


def sec_calendar(val: pd.DataFrame) -> None:
    print(SEP)
    print("  6. H1 PERFORMANCE BY CALENDAR MONTH")
    print(SEP)

    v = val.copy()
    v["month"] = v["date"].dt.to_period("M")
    print(f"\n   {'Month':<10} {'n':>5} {'MAE':>8} {'Bias':>8} {'actual_avg':>11}")
    print(f"   {SEP2[:48]}")
    for m, sub in v.groupby("month"):
        err = sub["pred_h1"] - sub["actual_h1_total"]
        print(f"   {str(m):<10} {len(sub):>5} {err.abs().mean():>8.2f} "
              f"{err.mean():>+8.2f} {sub['actual_h1_total'].mean():>11.2f}")
    print()


def sec_summary(val: pd.DataFrame, h1_sigma: float, bss: float, rho: float) -> None:
    print(SEP)
    print("  H1 BACKTEST SUMMARY — 2024-25 VALIDATION")
    print(SEP)

    err     = val["pred_h1"] - val["actual_h1_total"]
    rla     = val["rolling_h1_league_avg"]
    lean    = np.where(val["pred_h1"] > rla, "OVER", "UNDER")
    correct = (
        ((lean == "OVER")  & (val["actual_h1_total"] > rla)) |
        ((lean == "UNDER") & (val["actual_h1_total"] < rla))
    )
    dir_hr = correct.mean() * 100

    print(f"""
   ┌──────────────────────────────────────────────────────┐
   │  Metric                            Value             │
   ├──────────────────────────────────────────────────────┤
   │  Validation games (2024-25)        {len(val):>5}             │
   │  MAE                               {err.abs().mean():>5.2f} pts          │
   │  RMSE                              {np.sqrt((err**2).mean()):>5.2f} pts          │
   │  Bias                              {err.mean():>+5.2f} pts          │
   │  H1 training σ                     {h1_sigma:>5.2f} pts          │
   │  Directional hit rate (vs H1 avg)  {dir_hr:>5.1f}%            │
   │  Spearman ρ (H1 edge monotonicity) {rho:>6.3f}             │
   │  Brier skill score                 {bss:>+6.4f}             │
   └──────────────────────────────────────────────────────┘

   Status: H1 BACKTEST COMPLETE
""")


def main():
    val, h1_sigma = load_data()
    val["date"] = pd.to_datetime(val["date"])

    sec_accuracy(val)
    sec_directional(val)
    bss = sec_calibration(val, h1_sigma)
    rho = sec_edge_distribution(val)
    sec_tail_compression(val)
    sec_calendar(val)
    sec_summary(val, h1_sigma, bss, rho)


if __name__ == "__main__":
    main()
