#!/usr/bin/env python3
"""
Deep analysis on OV043 (bullpen_overuse) and OV001 (bb_x_hard_hit).
Tests 1-9 + final verdict.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# ── Load dataset ──────────────────────────────────────────────────────
df = pd.read_parquet(BASE / "over_wave1_dataset.parquet")
df["date"] = pd.to_datetime(df["date"])
df_np = df[~df["is_push"]].copy()
df["v1_over_lean"] = (df["p_under"] < 0.45).astype(int)
df_np["v1_over_lean"] = (df_np["p_under"] < 0.45).astype(int)

# Also load feature_table for controls
ft = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
ft_ctrl = ft[ft["season"].isin([2024, 2025])][["game_pk", "home_sp_xfip", "away_sp_xfip", "park_factor_runs"]].copy()
df = df.merge(ft_ctrl, on="game_pk", how="left")
df_np = df[~df["is_push"]].copy()
df_np["v1_over_lean"] = (df_np["p_under"] < 0.45).astype(int)

SIGS = {
    "OV043": "bullpen_overuse (combined BP IP last 3d)",
    "OV001": "bb_x_hard_hit (avg SP BB% × SP HH%)",
}

print(f"Dataset: {len(df)} games, {len(df_np)} non-push")
v1_over = df_np[df_np["v1_over_lean"] == 1]
v1_w = v1_over["actual_result_over"].sum()
v1_roi = roi_110(v1_w, len(v1_over) - v1_w)
print(f"V1 OVER-lean: N={len(v1_over)}, over%={v1_over.actual_result_over.mean():.3f}, ROI={v1_roi:+.1f}%")

R = []
R.append("# Deep Analysis — OV043 and OV001")
R.append("")
R.append(f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append(f"V1 OVER-lean (p_under<0.45): N={len(v1_over)}, over%={v1_over.actual_result_over.mean():.3f}, ROI={v1_roi:+.1f}%")
R.append("")

for sig, sig_desc in SIGS.items():
    print(f"\n{'='*60}")
    print(f"SIGNAL: {sig} — {sig_desc}")
    print(f"{'='*60}")

    R.append(f"---")
    R.append(f"## {sig}: {sig_desc}")
    R.append("")

    col = sig
    valid = df[col].notna()
    valid_np = df_np[col].notna()

    # ── TEST 1 — SEASON STABILITY ────────────────────────────────
    R.append("### Test 1 — Season Stability")
    R.append("")
    R.append("| Year | Coefficient | p-value | R² |")
    R.append("|------|-----------|---------|-----|")
    yr_coefs = {}
    for yr in [2024, 2025]:
        yr_df = df[(df["season"] == yr) & valid]
        if yr_df[col].std() < 1e-10:
            yr_coefs[yr] = {"coef": 0, "p": 1.0}
            R.append(f"| {yr} | 0 | 1.0 | 0 |")
            continue
        X = sm.add_constant(yr_df[col])
        y = yr_df["market_residual_over"]
        m = sm.OLS(y, X).fit()
        yr_coefs[yr] = {"coef": m.params[col], "p": m.pvalues[col], "r2": m.rsquared}
        R.append(f"| {yr} | {m.params[col]:+.5f} | {m.pvalues[col]:.4f} | {m.rsquared:.6f} |")
        print(f"  {yr}: coef={m.params[col]:+.5f}, p={m.pvalues[col]:.4f}")

    stable = yr_coefs.get(2024, {}).get("coef", 0) * yr_coefs.get(2025, {}).get("coef", 0) > 0
    R.append(f"\nVerdict: **{'STABLE' if stable else 'MIXED'}**")
    R.append("")

    # ── TEST 2 — DECILE STRUCTURE ────────────────────────────────
    R.append("### Test 2 — Decile Structure")
    R.append("")
    sub = df_np[valid_np].copy()
    sub["decile"] = pd.qcut(sub[col], 10, labels=False, duplicates="drop")

    R.append("| Decile | N | Mean | Resid | Over% | ROI |")
    R.append("|--------|---|------|-------|-------|-----|")
    dec_resids = []
    for dec in sorted(sub["decile"].unique()):
        d = sub[sub["decile"] == dec]
        n = len(d)
        mean_v = d[col].mean()
        resid = d["market_residual_over"].mean()
        over_r = d["actual_result_over"].mean()
        w = d["actual_result_over"].sum()
        roi = roi_110(w, n - w)
        dec_resids.append(resid)
        R.append(f"| {dec} | {n} | {mean_v:.4f} | {resid:+.4f} | {over_r:.3f} | {roi:+.1f}% |")

    # Gradient assessment
    top3_avg = np.mean(dec_resids[-3:])
    bot3_avg = np.mean(dec_resids[:3])
    mid_avg = np.mean(dec_resids[3:7])
    if top3_avg > mid_avg > bot3_avg:
        gradient = "monotonic"
    elif top3_avg > bot3_avg and abs(mid_avg) < 0.01:
        gradient = "tail-only"
    else:
        gradient = "noisy"
    R.append(f"\nGradient: **{gradient}** (top3 avg={top3_avg:+.4f}, mid={mid_avg:+.4f}, bot3={bot3_avg:+.4f})")
    R.append("")

    # ── TEST 3 — THRESHOLD SENSITIVITY ───────────────────────────
    R.append("### Test 3 — Threshold Sensitivity")
    R.append("")

    # Standalone
    R.append("**Standalone:**")
    R.append("| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |")
    R.append("|-----------|---|-------|-------|-----|----------|----------|")
    for label, pctile in [("top_10", 90), ("top_20", 80), ("top_30", 70)]:
        thresh = df_np.loc[valid_np, col].quantile(pctile / 100)
        mask = valid_np & (df_np[col] > thresh)
        n = mask.sum()
        if n < 20: continue
        over_r = df_np.loc[mask, "actual_result_over"].mean()
        resid = over_r - 0.50
        w = df_np.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)
        yr_rois = {}
        for yr in [2024, 2025]:
            yr_m = mask & (df_np["season"] == yr)
            yn = yr_m.sum()
            if yn < 10: yr_rois[yr] = "N/A"
            else:
                yw = df_np.loc[yr_m, "actual_result_over"].sum()
                yr_rois[yr] = f"{roi_110(yw, yn - yw):+.1f}%"
        R.append(f"| {label} | {n} | {over_r:.3f} | {resid:+.3f} | {roi:+.1f}% | {yr_rois[2024]} | {yr_rois[2025]} |")
    R.append("")

    # V1 interaction
    R.append("**V1 OVER-lean interaction:**")
    R.append("| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |")
    R.append("|-----------|---|-------|-------|-----|----------|----------|")
    v1_sub = df_np[(df_np["v1_over_lean"] == 1) & valid_np]
    for label, pctile in [("top_10", 90), ("top_20", 80), ("top_30", 70)]:
        thresh = v1_sub[col].quantile(pctile / 100)
        mask = v1_sub[col] > thresh
        n = mask.sum()
        if n < 10: continue
        over_r = v1_sub.loc[mask, "actual_result_over"].mean()
        resid = over_r - 0.50
        w = v1_sub.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)
        yr_rois = {}
        for yr in [2024, 2025]:
            yr_m = mask & (v1_sub["season"] == yr)
            yn = yr_m.sum()
            if yn < 10: yr_rois[yr] = "N/A"
            else:
                yw = v1_sub.loc[yr_m, "actual_result_over"].sum()
                yr_rois[yr] = f"{roi_110(yw, yn - yw):+.1f}%"
        R.append(f"| {label} | {n} | {over_r:.3f} | {resid:+.3f} | {roi:+.1f}% | {yr_rois[2024]} | {yr_rois[2025]} |")
    R.append("")

    # ── TEST 4 — ROBUSTNESS CONTROLS ────────────────────────────
    R.append("### Test 4 — Robustness Controls")
    R.append("")
    controls = [col, "closing_total", "home_sp_xfip", "away_sp_xfip", "park_factor_runs"]
    df_ols = df[valid].dropna(subset=controls + ["market_residual_over"])
    if len(df_ols) > 100:
        X = sm.add_constant(df_ols[controls])
        y = df_ols["market_residual_over"]
        m = sm.OLS(y, X).fit()
        sig_coef = m.params[col]
        sig_p = m.pvalues[col]
        robust = "ROBUST" if sig_p < 0.10 else "NOT ROBUST"
        R.append(f"- Coefficient: {sig_coef:+.5f}")
        R.append(f"- p-value: {sig_p:.4f}")
        R.append(f"- Verdict: **{robust}**")
        print(f"  Robustness: coef={sig_coef:+.5f}, p={sig_p:.4f} → {robust}")
    else:
        R.append("- Insufficient data for controls")
        robust = "N/A"
    R.append("")

    # ── TEST 5 — MARKET AWARENESS ────────────────────────────────
    R.append("### Test 5 — Market Awareness")
    R.append("")
    corr_mask = valid & df["closing_total"].notna()
    r_corr, _ = stats.pearsonr(df.loc[corr_mask, col], df.loc[corr_mask, "closing_total"])
    R.append(f"- corr(signal, closing_total): r={r_corr:.4f}")

    # Compare closing total in top 20% vs rest
    p80 = df.loc[valid, col].quantile(0.80)
    top20_cl = df.loc[valid & (df[col] > p80), "closing_total"].mean()
    rest_cl = df.loc[valid & (df[col] <= p80), "closing_total"].mean()
    diff = top20_cl - rest_cl
    R.append(f"- Avg closing total — top 20%: {top20_cl:.2f}, rest: {rest_cl:.2f}, diff: {diff:+.2f}")
    if abs(diff) < 0.15:
        awareness = "Market **mostly misses** this signal"
    elif abs(diff) < 0.30:
        awareness = "Market **partially prices** this signal"
    else:
        awareness = "Market **substantially prices** this signal"
    R.append(f"- {awareness}")
    R.append("")

# ── TEST 6 — V1 INTERACTION WALK-FORWARD ─────────────────────────
R.append("---")
R.append("## Test 6 — V1 Interaction (Walk-Forward)")
R.append("")

WARMUP = 50

# Build walk-forward thresholds for both signals
df_wf = df.sort_values("date").copy()
df_wf["v1_over_lean"] = (df_wf["p_under"] < 0.45).astype(int)

for sig in ["OV043", "OV001"]:
    df_wf[f"{sig}_wf_thresh10"] = np.nan
    df_wf[f"{sig}_wf_thresh20"] = np.nan
    df_wf[f"{sig}_wf_thresh30"] = np.nan

    for yr in [2024, 2025]:
        yr_mask = (df_wf["season"] == yr) & (df_wf["v1_over_lean"] == 1) & df_wf[sig].notna()
        yr_v1 = df_wf[yr_mask].copy()
        for i, (idx, row) in enumerate(yr_v1.iterrows()):
            if i < WARMUP:
                continue
            prior = yr_v1.iloc[:i]
            df_wf.at[idx, f"{sig}_wf_thresh10"] = prior[sig].quantile(0.90)
            df_wf.at[idx, f"{sig}_wf_thresh20"] = prior[sig].quantile(0.80)
            df_wf.at[idx, f"{sig}_wf_thresh30"] = prior[sig].quantile(0.70)

for sig in ["OV043", "OV001"]:
    df_wf[f"{sig}_wf_top10"] = ((df_wf[sig] > df_wf[f"{sig}_wf_thresh10"]) &
                                  df_wf[f"{sig}_wf_thresh10"].notna()).astype(int)
    df_wf[f"{sig}_wf_top20"] = ((df_wf[sig] > df_wf[f"{sig}_wf_thresh20"]) &
                                  df_wf[f"{sig}_wf_thresh20"].notna()).astype(int)
    df_wf[f"{sig}_wf_top30"] = ((df_wf[sig] > df_wf[f"{sig}_wf_thresh30"]) &
                                  df_wf[f"{sig}_wf_thresh30"].notna()).astype(int)

# Combined: both in top 20%
df_wf["both_wf_top20"] = ((df_wf["OV043_wf_top20"] == 1) & (df_wf["OV001_wf_top20"] == 1)).astype(int)

df_wf_np = df_wf[~df_wf["is_push"]].copy()

R.append(f"Warmup: first {WARMUP} V1 OVER-lean games per season")
R.append("")
R.append("| Cohort | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |")
R.append("|--------|---|-------|-------|-----|----------|----------|")

cohorts = {
    "A: V1 OVER-lean alone": lambda d: d["v1_over_lean"] == 1,
    "B: V1 + OV043 top10": lambda d: (d["v1_over_lean"] == 1) & (d["OV043_wf_top10"] == 1),
    "C: V1 + OV043 top20": lambda d: (d["v1_over_lean"] == 1) & (d["OV043_wf_top20"] == 1),
    "D: V1 + OV043 top30": lambda d: (d["v1_over_lean"] == 1) & (d["OV043_wf_top30"] == 1),
    "E: V1 + OV001 top10": lambda d: (d["v1_over_lean"] == 1) & (d["OV001_wf_top10"] == 1),
    "F: V1 + OV001 top20": lambda d: (d["v1_over_lean"] == 1) & (d["OV001_wf_top20"] == 1),
    "G: V1 + OV001 top30": lambda d: (d["v1_over_lean"] == 1) & (d["OV001_wf_top30"] == 1),
    "H: V1 + OV043+OV001 top20": lambda d: (d["v1_over_lean"] == 1) & (d["both_wf_top20"] == 1),
}

for clabel, cfn in cohorts.items():
    mask = cfn(df_wf_np)
    n = mask.sum()
    if n < 10:
        R.append(f"| {clabel} | {n} | N/A | N/A | N/A | N/A | N/A |")
        continue
    over_r = df_wf_np.loc[mask, "actual_result_over"].mean()
    resid = over_r - 0.50
    w = df_wf_np.loc[mask, "actual_result_over"].sum()
    roi = roi_110(w, n - w)
    yr_rois = {}
    for yr in [2024, 2025]:
        yr_m = mask & (df_wf_np["season"] == yr)
        yn = yr_m.sum()
        if yn < 10: yr_rois[yr] = "N/A"
        else:
            yw = df_wf_np.loc[yr_m, "actual_result_over"].sum()
            yr_rois[yr] = f"{roi_110(yw, yn - yw):+.1f}%"
    R.append(f"| {clabel} | {n} | {over_r:.3f} | {resid:+.3f} | {roi:+.1f}% | {yr_rois[2024]} | {yr_rois[2025]} |")
    print(f"  {clabel}: N={n}, over%={over_r:.3f}, ROI={roi:+.1f}%")

R.append("")

# ── TEST 7 — INDEPENDENCE ────────────────────────────────────────
R.append("---")
R.append("## Test 7 — Independence")
R.append("")

both_valid = df["OV043"].notna() & df["OV001"].notna()
r_inter, p_inter = stats.pearsonr(df.loc[both_valid, "OV043"], df.loc[both_valid, "OV001"])
R.append(f"- corr(OV043, OV001): r={r_inter:.4f}, p={p_inter:.4f}")
if abs(r_inter) > 0.60:
    R.append("- **REDUNDANT** (r > 0.60)")
elif abs(r_inter) > 0.30:
    R.append("- Partially correlated")
else:
    R.append("- **INDEPENDENT** (r < 0.30)")

# Joint OLS
df_joint = df[both_valid].dropna(subset=["market_residual_over"])
X = sm.add_constant(df_joint[["OV043", "OV001"]])
y = df_joint["market_residual_over"]
m = sm.OLS(y, X).fit()
R.append(f"- Joint OLS: OV043 coef={m.params['OV043']:+.5f} (p={m.pvalues['OV043']:.4f}), "
         f"OV001 coef={m.params['OV001']:+.5f} (p={m.pvalues['OV001']:.4f})")
R.append(f"- R²={m.rsquared:.6f}")
both_sig = m.pvalues["OV043"] < 0.10 and m.pvalues["OV001"] < 0.10
R.append(f"- Both carry independent info: **{'YES' if both_sig else 'NO'}**")
R.append("")
print(f"  Independence: r={r_inter:.4f}, OV043_p={m.pvalues['OV043']:.4f}, OV001_p={m.pvalues['OV001']:.4f}")

# ── TEST 8 — PERMUTATION (2025) ──────────────────────────────────
R.append("---")
R.append("## Test 8 — Permutation (2025)")
R.append("")

for sig in ["OV043", "OV001"]:
    yr_np = df_wf_np[(df_wf_np["season"] == 2025) & (df_wf_np["v1_over_lean"] == 1)]
    flag_col = f"{sig}_wf_top20"
    flagged = yr_np[flag_col] == 1
    n_f = flagged.sum()

    if n_f < 10:
        R.append(f"- {sig}: N={n_f}, too few")
        continue

    obs_w = yr_np.loc[flagged, "actual_result_over"].sum()
    obs_roi = roi_110(obs_w, n_f - obs_w)
    obs_or = yr_np.loc[flagged, "actual_result_over"].mean()

    outcomes = yr_np["actual_result_over"].values.copy()
    perm_rois = []
    for _ in range(200):
        np.random.shuffle(outcomes)
        w = outcomes[:n_f].sum()
        perm_rois.append(roi_110(w, n_f - w))
    perm_rois = np.array(perm_rois)
    pctile = (perm_rois <= obs_roi).mean() * 100

    R.append(f"**{sig}** (top 20%, walk-forward):")
    R.append(f"- N={n_f}, obs over%={obs_or:.3f}, obs ROI={obs_roi:+.1f}%")
    R.append(f"- Permutation: median={np.median(perm_rois):+.1f}%, "
             f"p5={np.percentile(perm_rois, 5):+.1f}%, p95={np.percentile(perm_rois, 95):+.1f}%")
    R.append(f"- Percentile: {pctile:.0f}% ({'PASS' if pctile >= 85 else 'MARGINAL' if pctile >= 75 else 'FAIL'})")
    R.append("")
    print(f"  Perm {sig}: obs ROI={obs_roi:+.1f}%, pctile={pctile:.0f}%")

# ── TEST 9 — AVAILABILITY BIAS ───────────────────────────────────
R.append("---")
R.append("## Test 9 — Availability Bias")
R.append("")

for sig in ["OV043", "OV001"]:
    R.append(f"**{sig}:**")
    v1_np_all = df_np[df_np["v1_over_lean"] == 1]
    avail = v1_np_all[sig].notna()
    unavail = ~avail
    R.append("| Group | N | Over% | Avg Close | ROI |")
    R.append("|-------|---|-------|-----------|-----|")
    for lbl, mask in [("Available", avail), ("Unavailable", unavail)]:
        n = mask.sum()
        if n == 0: continue
        over_r = v1_np_all.loc[mask, "actual_result_over"].mean()
        w = v1_np_all.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)
        avg_cl = df.loc[v1_np_all.loc[mask].index.intersection(df.index), "closing_total"].mean()
        R.append(f"| {lbl} | {n} | {over_r:.3f} | {avg_cl:.2f} | {roi:+.1f}% |")
    bias = abs(v1_np_all.loc[avail, "actual_result_over"].mean() -
               v1_np_all.loc[unavail, "actual_result_over"].mean()) if unavail.sum() > 0 else 0
    R.append(f"\nBias: {bias:.3f} ({'CLEAN' if bias < 0.03 else 'WARNING'})")
    R.append("")

# =====================================================================
# FINAL VERDICT
# =====================================================================
R.append("---")
R.append("## Final Verdict")
R.append("")

for sig in ["OV043", "OV001"]:
    R.append(f"### {sig}: {SIGS[sig]}")
    R.append("")

    # Gather key metrics
    sr = [s for s in [{"signal": sig}]][0]  # placeholder

    # Walk-forward V1 interaction — get top 20% cohort
    wf_mask = (df_wf_np["v1_over_lean"] == 1) & (df_wf_np[f"{sig}_wf_top20"] == 1)
    wf_n = wf_mask.sum()
    if wf_n > 0:
        wf_or = df_wf_np.loc[wf_mask, "actual_result_over"].mean()
        wf_w = df_wf_np.loc[wf_mask, "actual_result_over"].sum()
        wf_roi = roi_110(wf_w, wf_n - wf_w)
        # V1 baseline
        v1_mask = df_wf_np["v1_over_lean"] == 1
        v1_n_wf = v1_mask.sum()
        v1_w_wf = df_wf_np.loc[v1_mask, "actual_result_over"].sum()
        v1_roi_wf = roi_110(v1_w_wf, v1_n_wf - v1_w_wf)
        lift = wf_roi - v1_roi_wf
    else:
        wf_roi = lift = np.nan

    # Year check
    for yr in [2024, 2025]:
        yr_m = wf_mask & (df_wf_np["season"] == yr)
        yn = yr_m.sum()
        if yn >= 10:
            yw = df_wf_np.loc[yr_m, "actual_result_over"].sum()
            yr_roi = roi_110(yw, yn - yw)

    R.append(f"| Criterion | Result |")
    R.append(f"|-----------|--------|")
    R.append(f"| Season stability | {'STABLE' if stable else 'MIXED'} |")
    R.append(f"| Walk-forward V1 top20 ROI | {wf_roi:+.1f}% (N={wf_n}) |" if not np.isnan(wf_roi) else "| WF ROI | N/A |")
    R.append(f"| V1 lift | {lift:+.1f}pp |" if not np.isnan(lift) else "| V1 lift | N/A |")
    R.append(f"| Market awareness | r={r_corr:.3f} |")
    R.append("")

    # Verdict
    if not np.isnan(lift) and lift > 3 and wf_n >= 75:
        verdict = "ADVANCE"
        role = "V1 OVER-lean amplifier"
    elif not np.isnan(lift) and lift > 0 and wf_n >= 50:
        verdict = "INVESTIGATE"
        role = "V1 amplifier candidate (needs 2026 validation)"
    else:
        verdict = "SHELVE"
        role = "No deployment value"

    R.append(f"**Verdict: {verdict}**")
    R.append(f"- Role: {role}")
    R.append(f"- Viable cohort: ~{wf_n//2} games/season in V1+{sig} top20")
    R.append("")

# Combined assessment
R.append("### Combined OV043 + OV001")
R.append("")
both_mask = (df_wf_np["v1_over_lean"] == 1) & (df_wf_np["both_wf_top20"] == 1)
both_n = both_mask.sum()
if both_n >= 10:
    both_or = df_wf_np.loc[both_mask, "actual_result_over"].mean()
    both_w = df_wf_np.loc[both_mask, "actual_result_over"].sum()
    both_roi = roi_110(both_w, both_n - both_w)
    R.append(f"- V1 + both top20: N={both_n}, over%={both_or:.3f}, ROI={both_roi:+.1f}%")
    R.append(f"- Independence: r={r_inter:.4f} ({'independent' if abs(r_inter) < 0.30 else 'correlated'})")
else:
    R.append(f"- V1 + both top20: N={both_n}, too few for assessment")
R.append("")

# Save
out = BASE / "ov043_ov001_deep_analysis.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"\nSaved: {out}")
