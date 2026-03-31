"""
V2.2b Challenger Calibration Layer
===================================
Replaces isotonic calibration with Platt scaling + league offsets.
Fit on VALIDATE (2023-24), evaluated on OOS (2024-25).
"""

import json
import os
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent  # mlb-model/
PRED_PATH = ROOT / "soccer/data/soccer_v2_2_predictions.parquet"
CAN_PATH = ROOT / "soccer/data/soccer_canonical.parquet"
ODDS_PATH = ROOT / "soccer/data/odds_historical.parquet"
OUT_DIR = ROOT / "soccer/models/v2_2b"

ACTIVE = ["EPL", "BUN", "SEA", "LG1"]

# ── Load data ──────────────────────────────────────────────────────────────
pred = pd.read_parquet(PRED_PATH)
can = pd.read_parquet(CAN_PATH)[["game_id", "over_price", "under_price", "closing_total_line"]]
odds = pd.read_parquet(ODDS_PATH)[["game_id", "ref_over_close", "ref_under_close"]]

pred = pred[pred["league_id"].isin(ACTIVE)].copy()
pred = pred.merge(can, on="game_id", how="left")
pred = pred.merge(odds, on="game_id", how="left")

val = pred[pred["split"] == "validate"].copy()
oos = pred[pred["split"] == "oos"].copy()

print(f"Validate set: {len(val)} games  |  OOS set: {len(oos)} games")
print(f"Leagues: {sorted(val['league_id'].unique())}")
print()

# ── PART A: Platt scaling on VALIDATE ──────────────────────────────────────
def safe_logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))

logit_raw_val = safe_logit(val["ridge_raw_p"].values)
platt = LogisticRegression(C=1e10, solver="lbfgs", max_iter=1000)
platt.fit(logit_raw_val.reshape(-1, 1), val["actual_over_2_5"].values.astype(int))

os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT_DIR / "platt_calibrator.pkl", "wb") as f:
    pickle.dump(platt, f)

print(f"Platt coefficients: slope={platt.coef_[0][0]:.4f}, intercept={platt.intercept_[0]:.4f}")

# Apply Platt to validate set
val["platt_p"] = platt.predict_proba(logit_raw_val.reshape(-1, 1))[:, 1]

# ── PART B: League-specific intercept on VALIDATE ──────────────────────────
league_offsets = {}
for lg in ACTIVE:
    mask = val["league_id"] == lg
    actual_rate = val.loc[mask, "actual_over_2_5"].mean()
    pred_rate = val.loc[mask, "platt_p"].mean()
    league_offsets[lg] = round(float(actual_rate - pred_rate), 6)

print(f"\nLeague offsets (validate): {json.dumps(league_offsets, indent=2)}")

with open(OUT_DIR / "league_calibration.json", "w") as f:
    json.dump(league_offsets, f, indent=2)

# Apply offsets to validate (for reference)
val["v2_2b_cal_p"] = val["platt_p"] + val["league_id"].map(league_offsets)
val["v2_2b_cal_p"] = val["v2_2b_cal_p"].clip(0.01, 0.99)

# ── PART C: Apply V2.2b to OOS ────────────────────────────────────────────
logit_raw_oos = safe_logit(oos["ridge_raw_p"].values)
oos["platt_p"] = platt.predict_proba(logit_raw_oos.reshape(-1, 1))[:, 1]
oos["v2_2b_cal_p"] = oos["platt_p"] + oos["league_id"].map(league_offsets)
oos["v2_2b_cal_p"] = oos["v2_2b_cal_p"].clip(0.01, 0.99)

print(f"\nOOS v2_2b_cal_p range: {oos['v2_2b_cal_p'].min():.4f} – {oos['v2_2b_cal_p'].max():.4f}")
print(f"OOS ridge_cal_p range: {oos['ridge_cal_p'].min():.4f} – {oos['ridge_cal_p'].max():.4f}")

# ═══════════════════════════════════════════════════════════════════════════
# PART D: DIAGNOSTICS ON OOS
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 80)
print("DIAGNOSTIC 1: CALIBRATION CURVE (OOS)")
print("=" * 80)

bins = [0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 1.0]
labels = ["<0.40", "0.40-0.45", "0.45-0.50", "0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65+"]
oos["cal_bin"] = pd.cut(oos["v2_2b_cal_p"], bins=bins, labels=labels, include_lowest=True)

print(f"\n{'Bucket':<12} {'N':>5} {'Avg Pred':>10} {'Actual':>10} {'Gap (pp)':>10}")
print("-" * 50)
for label in labels:
    mask = oos["cal_bin"] == label
    n = mask.sum()
    if n == 0:
        continue
    avg_pred = oos.loc[mask, "v2_2b_cal_p"].mean()
    actual = oos.loc[mask, "actual_over_2_5"].mean()
    gap = (actual - avg_pred) * 100
    print(f"{label:<12} {n:>5} {avg_pred:>10.4f} {actual:>10.4f} {gap:>+10.1f}")

# Platt slope on OOS (measure, not retrain)
logit_cal_oos = safe_logit(oos["v2_2b_cal_p"].values)
platt_oos = LogisticRegression(C=1e10, solver="lbfgs", max_iter=1000)
platt_oos.fit(logit_cal_oos.reshape(-1, 1), oos["actual_over_2_5"].values.astype(int))
cal_slope = platt_oos.coef_[0][0]

# Brier score
brier = np.mean((oos["v2_2b_cal_p"] - oos["actual_over_2_5"]) ** 2)
overall_bias = (oos["actual_over_2_5"].mean() - oos["v2_2b_cal_p"].mean()) * 100

# V2.2 comparison brier
brier_v22 = np.mean((oos["ridge_cal_p"] - oos["actual_over_2_5"]) ** 2)
logit_cal_v22 = safe_logit(oos["ridge_cal_p"].values)
platt_v22 = LogisticRegression(C=1e10, solver="lbfgs", max_iter=1000)
platt_v22.fit(logit_cal_v22.reshape(-1, 1), oos["actual_over_2_5"].values.astype(int))
cal_slope_v22 = platt_v22.coef_[0][0]
bias_v22 = (oos["actual_over_2_5"].mean() - oos["ridge_cal_p"].mean()) * 100

print(f"\nCalibration slope (OOS): {cal_slope:.4f}  (V2.2: {cal_slope_v22:.4f})")
print(f"Overall bias (pp):       {overall_bias:+.1f}  (V2.2: {bias_v22:+.1f})")
print(f"Brier score:             {brier:.4f}  (V2.2: {brier_v22:.4f})")

# ──────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("DIAGNOSTIC 2: EDGE CALIBRATION (OOS)")
print("=" * 80)

oos["edge"] = oos["v2_2b_cal_p"] - oos["market_fair_p_over_2_5"]
oos["market_error"] = oos["actual_over_2_5"] - oos["market_fair_p_over_2_5"]

edge_bins = [-1, -0.06, -0.03, 0.00, 0.03, 0.06, 0.10, 1]
edge_labels = ["≤-0.06", "-0.06 to -0.03", "-0.03 to 0.00", "0.00 to 0.03", "0.03 to 0.06", "0.06 to 0.10", "0.10+"]
oos["edge_bin"] = pd.cut(oos["edge"], bins=edge_bins, labels=edge_labels, include_lowest=True)

print(f"\n{'Bucket':<18} {'N':>5} {'Avg Edge':>10} {'Actual O2.5':>12} {'Avg Mkt Err':>12}")
print("-" * 60)
bucket_ranks = []
bucket_errors = []
for i, label in enumerate(edge_labels):
    mask = oos["edge_bin"] == label
    n = mask.sum()
    if n == 0:
        continue
    avg_edge = oos.loc[mask, "edge"].mean()
    actual_rate = oos.loc[mask, "actual_over_2_5"].mean()
    avg_mkt_err = oos.loc[mask, "market_error"].mean()
    print(f"{label:<18} {n:>5} {avg_edge:>+10.4f} {actual_rate:>12.4f} {avg_mkt_err:>+12.4f}")
    bucket_ranks.append(i)
    bucket_errors.append(avg_mkt_err)

if len(bucket_ranks) >= 3:
    spearman, sp_pval = stats.spearmanr(bucket_ranks, bucket_errors)
    print(f"\nSpearman (bucket rank vs avg market error): {spearman:.3f}  (p={sp_pval:.3f})")

# ──────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("DIAGNOSTIC 3: CLOSING LINE TEST (OOS)")
print("=" * 80)

# Active bets: |edge| >= 0.06
oos["bet_side"] = np.where(oos["edge"] >= 0.06, "OVER", np.where(oos["edge"] <= -0.06, "UNDER", "NONE"))
active_bets = oos[oos["bet_side"] != "NONE"].copy()

# Assign odds
active_bets["odds"] = np.where(
    active_bets["bet_side"] == "OVER",
    active_bets["over_price"],
    active_bets["under_price"],
)
# Drop rows without odds
active_bets = active_bets.dropna(subset=["odds"])

# Win flag
active_bets["won"] = np.where(
    active_bets["bet_side"] == "OVER",
    active_bets["actual_over_2_5"] == 1,
    active_bets["actual_over_2_5"] == 0,
)

# Profit at actual odds
active_bets["profit_actual"] = np.where(active_bets["won"], active_bets["odds"] - 1, -1)
# Profit at -110 (1.909)
active_bets["profit_110"] = np.where(active_bets["won"], 1.909 - 1, -1)

# Tiers
def assign_tier(edge):
    ae = abs(edge)
    if ae >= 0.10:
        return "HIGH"
    elif ae >= 0.08:
        return "MEDIUM"
    else:
        return "LOW"

active_bets["tier"] = active_bets["edge"].abs().apply(lambda x: "HIGH" if x >= 0.10 else ("MEDIUM" if x >= 0.08 else "LOW"))

def report_group(df, label):
    n = len(df)
    if n == 0:
        print(f"  {label:<25} N=0")
        return 0
    hit = df["won"].mean() * 100
    roi_actual = df["profit_actual"].mean() * 100
    roi_110 = df["profit_110"].mean() * 100
    avg_odds = df["odds"].mean()
    be = 1 / avg_odds * 100 if avg_odds > 0 else 0
    print(f"  {label:<25} N={n:>4}  Hit={hit:>5.1f}%  ROI@actual={roi_actual:>+6.1f}%  ROI@-110={roi_110:>+6.1f}%  AvgOdds={avg_odds:.3f}  BE={be:.1f}%")
    return roi_actual

print("\nOverall:")
report_group(active_bets, "ALL ACTIVE")

print("\nBy Tier:")
tier_rois = {}
for t in ["LOW", "MEDIUM", "HIGH"]:
    roi = report_group(active_bets[active_bets["tier"] == t], t)
    tier_rois[t] = roi

print("\nBy League:")
league_rois = {}
for lg in sorted(ACTIVE):
    roi = report_group(active_bets[active_bets["league_id"] == lg], lg)
    league_rois[lg] = roi

print("\nSpecial combos:")
med_mask = active_bets["tier"] == "MEDIUM"
med_roi = report_group(active_bets[med_mask], "MEDIUM-only")

bun_med = active_bets[(active_bets["league_id"] == "BUN") & (active_bets["tier"] == "MEDIUM")]
bun_med_roi = report_group(bun_med, "BUN+MEDIUM")

print("\nHit rate vs break-even by league and tier:")
print(f"  {'League':<8} {'Tier':<10} {'N':>5} {'Hit%':>8} {'BE%':>8} {'Delta':>8}")
print("  " + "-" * 45)
for lg in sorted(ACTIVE):
    for t in ["LOW", "MEDIUM", "HIGH"]:
        sub = active_bets[(active_bets["league_id"] == lg) & (active_bets["tier"] == t)]
        if len(sub) < 3:
            continue
        hit = sub["won"].mean() * 100
        avg_odds = sub["odds"].mean()
        be = 1 / avg_odds * 100 if avg_odds > 0 else 0
        delta = hit - be
        print(f"  {lg:<8} {t:<10} {len(sub):>5} {hit:>8.1f} {be:>8.1f} {delta:>+8.1f}")

# ──────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("DIAGNOSTIC 4: EDGE OVERSTATEMENT (OOS)")
print("=" * 80)

over_bets = active_bets[active_bets["bet_side"] == "OVER"].copy()
if len(over_bets) > 0:
    claimed_edge = (over_bets["v2_2b_cal_p"] - over_bets["market_fair_p_over_2_5"]).mean()
    actual_edge = (over_bets["actual_over_2_5"] - over_bets["market_fair_p_over_2_5"]).mean()
    overstatement = claimed_edge / actual_edge if actual_edge != 0 else float("inf")
    print(f"\nOVER bets only (N={len(over_bets)}):")
    print(f"  Mean claimed edge: {claimed_edge:.4f}")
    print(f"  Mean actual edge:  {actual_edge:.4f}")
    print(f"  Overstatement ratio: {overstatement:.1f}x")
else:
    claimed_edge = actual_edge = 0
    overstatement = float("inf")
    print("  No OVER bets found.")

# Also compute for V2.2 (using ridge_cal_p)
oos_v22 = oos.copy()
oos_v22["edge_v22"] = oos_v22["ridge_cal_p"] - oos_v22["market_fair_p_over_2_5"]
oos_v22["bet_side_v22"] = np.where(oos_v22["edge_v22"] >= 0.06, "OVER", np.where(oos_v22["edge_v22"] <= -0.06, "UNDER", "NONE"))
over_v22 = oos_v22[oos_v22["bet_side_v22"] == "OVER"]
if len(over_v22) > 0:
    claimed_v22 = (over_v22["ridge_cal_p"] - over_v22["market_fair_p_over_2_5"]).mean()
    actual_v22 = (over_v22["actual_over_2_5"] - over_v22["market_fair_p_over_2_5"]).mean()
    overstatement_v22 = claimed_v22 / actual_v22 if actual_v22 != 0 else float("inf")
else:
    overstatement_v22 = float("inf")

# ═══════════════════════════════════════════════════════════════════════════
# PART E: V2.2 COMPARISON (compute V2.2 ROIs with same methodology)
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 80)
print("V2.2 BASELINE (for comparison)")
print("=" * 80)

oos_v22["odds_v22"] = np.where(
    oos_v22["bet_side_v22"] == "OVER", oos_v22["over_price"],
    np.where(oos_v22["bet_side_v22"] == "UNDER", oos_v22["under_price"], np.nan)
)
active_v22 = oos_v22[oos_v22["bet_side_v22"] != "NONE"].dropna(subset=["odds_v22"]).copy()
active_v22["won_v22"] = np.where(
    active_v22["bet_side_v22"] == "OVER",
    active_v22["actual_over_2_5"] == 1,
    active_v22["actual_over_2_5"] == 0,
)
active_v22["profit_v22"] = np.where(active_v22["won_v22"], active_v22["odds_v22"] - 1, -1)
active_v22["tier_v22"] = active_v22["edge_v22"].abs().apply(lambda x: "HIGH" if x >= 0.10 else ("MEDIUM" if x >= 0.08 else "LOW"))

def roi_of(df, col="profit_v22"):
    return df[col].mean() * 100 if len(df) > 0 else 0

v22_overall_roi = roi_of(active_v22)
v22_league_rois = {lg: roi_of(active_v22[active_v22["league_id"] == lg]) for lg in ACTIVE}
v22_med_roi = roi_of(active_v22[active_v22["tier_v22"] == "MEDIUM"])

print(f"V2.2 Overall ROI@actual:  {v22_overall_roi:+.1f}%  (N={len(active_v22)})")
for lg in sorted(ACTIVE):
    n = len(active_v22[active_v22["league_id"] == lg])
    print(f"  {lg}: {v22_league_rois[lg]:+.1f}%  (N={n})")
print(f"  MEDIUM-only: {v22_med_roi:+.1f}%")

# ═══════════════════════════════════════════════════════════════════════════
# PART E: COMPARISON TABLE
# ═══════════════════════════════════════════════════════════════════════════

overall_roi = active_bets["profit_actual"].mean() * 100 if len(active_bets) > 0 else 0

print("\n" + "=" * 80)
print("COMPARISON TABLE")
print("=" * 80)
print()
print(f"{'Metric':<30} {'V2.2':>12} {'V2.2b':>12}")
print("-" * 56)
print(f"{'Calibration slope':<30} {cal_slope_v22:>12.2f} {cal_slope:>12.2f}")
print(f"{'Overall bias (pp)':<30} {bias_v22:>+12.1f} {overall_bias:>+12.1f}")
print(f"{'Brier score':<30} {brier_v22:>12.4f} {brier:>12.4f}")
print(f"{'BUN ROI @ actual':<30} {v22_league_rois.get('BUN', 0):>+12.1f}% {league_rois.get('BUN', 0):>+12.1f}%")
print(f"{'EPL ROI @ actual':<30} {v22_league_rois.get('EPL', 0):>+12.1f}% {league_rois.get('EPL', 0):>+12.1f}%")
print(f"{'LG1 ROI @ actual':<30} {v22_league_rois.get('LG1', 0):>+12.1f}% {league_rois.get('LG1', 0):>+12.1f}%")
print(f"{'SEA ROI @ actual':<30} {v22_league_rois.get('SEA', 0):>+12.1f}% {league_rois.get('SEA', 0):>+12.1f}%")
print(f"{'Overall ROI @ actual':<30} {v22_overall_roi:>+12.1f}% {overall_roi:>+12.1f}%")
print(f"{'MEDIUM-only ROI @ actual':<30} {v22_med_roi:>+12.1f}% {med_roi:>+12.1f}%")
print(f"{'Edge overstatement':<30} {overstatement_v22:>12.1f}x {overstatement:>12.1f}x")

# ═══════════════════════════════════════════════════════════════════════════
# PART F: DECISION GATE
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 80)
print("DECISION GATE")
print("=" * 80)

g1 = cal_slope >= 0.85
g2 = abs(overall_bias) < 1.5
g3 = overstatement < 2.0
g4a = overall_roi >= 0
g4b = (league_rois.get("BUN", 0) > 0) and (league_rois.get("EPL", 0) - v22_league_rois.get("EPL", 0) >= 3.0)
g4 = g4a or g4b

print(f"\n  Gate 1: Calibration slope >= 0.85      {'PASS' if g1 else 'FAIL'}  ({cal_slope:.2f})")
print(f"  Gate 2: Overall bias < 1.5pp           {'PASS' if g2 else 'FAIL'}  ({abs(overall_bias):.1f}pp)")
print(f"  Gate 3: Edge overstatement < 2x        {'PASS' if g3 else 'FAIL'}  ({overstatement:.1f}x)")
print(f"  Gate 4a: Overall ROI >= 0%             {'PASS' if g4a else 'FAIL'}  ({overall_roi:+.1f}%)")
print(f"  Gate 4b: BUN+ & EPL narrows >=3pp      {'PASS' if g4b else 'FAIL'}  (BUN={league_rois.get('BUN',0):+.1f}%, EPL delta={league_rois.get('EPL',0) - v22_league_rois.get('EPL',0):+.1f}pp)")
print(f"  Gate 4: (4a OR 4b)                     {'PASS' if g4 else 'FAIL'}")

verdict = "PROMOTE V2.2b" if (g1 and g2 and g3 and g4) else "KEEP V2.2"
print(f"\n  >>> VERDICT: {verdict} <<<")
print()
