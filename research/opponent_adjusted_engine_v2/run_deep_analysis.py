#!/usr/bin/env python3
"""
V2 Deep Analysis — ADJ_CONTACT and ADJ_HH
Tests 1-8 + final verdict.
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

# ── Load data ─────────────────────────────────────────────────────────
df = pd.read_parquet(BASE / "signal_scanner_input.parquet")
df["game_date"] = pd.to_datetime(df["game_date"])
df["is_push"] = df["is_push"].astype(bool)
df_np = df[~df["is_push"]].copy()

print(f"Dataset: {len(df)} games, {len(df_np)} non-push")

# Signal definitions
SIGNALS = {
    "ADJ_CONTACT": {
        "col": "combined_adj_contact_rate_last3",
        "direction": "HIGH",  # top = UNDER favorable (scanner: top_10 = +8.0% ROI)
        "hypothesis": "Higher adjusted contact suppression → UNDER",
    },
    "ADJ_HH": {
        "col": "combined_adj_hard_hit_last3",
        "direction": "LOW",   # bot_20 was best V1 interaction in scanner
        "hypothesis": "Lower adjusted hard-hit suppression → UNDER (counterintuitive, needs validation)",
    },
}

# V1 trigger
df["v1_under"] = (df["p_under"] > 0.57).astype(int)
df_np["v1_under"] = (df_np["p_under"] > 0.57).astype(int)

R = []  # Report lines
R.append("# V2 Deep Analysis — ADJ_CONTACT and ADJ_HH")
R.append("")
R.append(f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append(f"V1 baseline (p_under>0.57): N={df_np['v1_under'].sum()}")
R.append("")
R.append("## Signal Definitions")
R.append("")
R.append("| Signal | Field | Direction | Hypothesis |")
R.append("|--------|-------|-----------|-----------|")
for name, meta in SIGNALS.items():
    R.append(f"| {name} | {meta['col']} | {meta['direction']} tail → UNDER | {meta['hypothesis']} |")
R.append("")

for sig_name, meta in SIGNALS.items():
    col = meta["col"]
    direction = meta["direction"]  # HIGH or LOW
    print(f"\n{'='*60}")
    print(f"SIGNAL: {sig_name} ({col})")
    print(f"{'='*60}")

    R.append(f"---")
    R.append(f"## {sig_name}: {col}")
    R.append("")

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
        X = sm.add_constant(yr_df[col])
        y = yr_df["market_residual"]
        m = sm.OLS(y, X).fit()
        coef = m.params[col]
        pval = m.pvalues[col]
        r2 = m.rsquared
        yr_coefs[yr] = coef
        R.append(f"| {yr} | {coef:+.5f} | {pval:.4f} | {r2:.6f} |")
        print(f"  {yr}: coef={coef:+.5f}, p={pval:.4f}")

    stable = yr_coefs[2024] * yr_coefs[2025] > 0
    R.append(f"\nVerdict: **{'STABLE' if stable else 'MIXED'}** — "
             f"{'same sign both years' if stable else 'sign reversal'}")
    R.append("")

    # ── TEST 2 — DECILE STRUCTURE ────────────────────────────────
    R.append("### Test 2 — Decile Structure")
    R.append("")
    subset = df[valid].copy()
    subset_np = df_np[valid_np].copy()
    subset["decile"] = pd.qcut(subset[col], 10, labels=False, duplicates="drop")
    subset_np["decile"] = pd.qcut(subset_np[col], 10, labels=False, duplicates="drop")

    R.append("| Decile | N | Mean | Resid | Under% | ROI |")
    R.append("|--------|---|------|-------|--------|-----|")
    decile_resids = []
    for dec in sorted(subset["decile"].unique()):
        d = subset[subset["decile"] == dec]
        d_np = subset_np[subset_np["decile"] == dec]
        n = len(d_np)
        mean_val = d[col].mean()
        resid = d["market_residual"].mean()
        ur = d_np["went_under"].mean() if n > 0 else np.nan
        w = d_np["went_under"].sum()
        roi = roi_110(w, n - w) if n > 0 else np.nan
        decile_resids.append(resid)
        R.append(f"| {dec} | {n} | {mean_val:.4f} | {resid:+.4f} | {ur:.3f} | {roi:+.1f}% |")

    # Check monotonicity
    increasing = all(decile_resids[i] <= decile_resids[i+1] for i in range(len(decile_resids)-1))
    decreasing = all(decile_resids[i] >= decile_resids[i+1] for i in range(len(decile_resids)-1))
    if increasing or decreasing:
        gradient = "monotonic"
    else:
        # Check if just tails
        d0_r = decile_resids[0]
        d9_r = decile_resids[-1]
        mid_r = np.mean(decile_resids[3:7])
        if abs(d9_r - d0_r) > 0.03 and abs(mid_r) < 0.01:
            gradient = "tail-only"
        else:
            gradient = "noisy"
    R.append(f"\nGradient: **{gradient}**")
    R.append("")

    # ── TEST 3 — THRESHOLD SENSITIVITY ───────────────────────────
    R.append("### Test 3 — Threshold Sensitivity")
    R.append("")
    R.append("| Threshold | N | Under% | Resid | ROI | 2024 ROI | 2025 ROI |")
    R.append("|-----------|---|--------|-------|-----|----------|----------|")

    for label, lo_pct, hi_pct in [
        ("top_10", 90, 100), ("top_20", 80, 100), ("top_30", 70, 100),
        ("bot_10", 0, 10), ("bot_20", 0, 20), ("bot_30", 0, 30),
    ]:
        lo_val = np.nanpercentile(df.loc[valid, col], lo_pct)
        hi_val = np.nanpercentile(df.loc[valid, col], hi_pct)
        if lo_pct == 0:
            mask_np = valid_np & (df_np[col] <= hi_val)
            mask_all = valid & (df[col] <= hi_val)
        else:
            mask_np = valid_np & (df_np[col] > lo_val)
            mask_all = valid & (df[col] > lo_val)

        n = mask_np.sum()
        if n < 40:
            R.append(f"| {label} | {n} | N/A | N/A | N/A | N/A | N/A |")
            continue

        ur = df_np.loc[mask_np, "went_under"].mean()
        resid = ur - 0.50
        w = df_np.loc[mask_np, "went_under"].sum()
        roi = roi_110(w, n - w)

        # By year
        yr_rois = {}
        for yr in [2024, 2025]:
            yr_np = df_np[(df_np["season"] == yr)]
            yr_mask = mask_np & (df_np["season"] == yr)
            yn = yr_mask.sum()
            if yn < 10:
                yr_rois[yr] = "N/A"
            else:
                yw = yr_np.loc[yr_mask, "went_under"].sum()
                yr_rois[yr] = f"{roi_110(yw, yn - yw):+.1f}%"

        R.append(f"| {label} | {n} | {ur:.3f} | {resid:+.3f} | {roi:+.1f}% | "
                 f"{yr_rois[2024]} | {yr_rois[2025]} |")

    R.append("")

    # ── TEST 4 — ROBUSTNESS CONTROLS ────────────────────────────
    R.append("### Test 4 — Robustness Controls")
    R.append("")
    controls = [col, "home_sp_xfip", "away_sp_xfip", "closing_total", "park_factor_runs"]
    # No CSW in dataset — note it
    R.append("Note: home_sp_csw_pct not available in dataset (CSW proxy not in game_level table).")
    R.append("Controls used: home_sp_xfip, away_sp_xfip, closing_total, park_factor_runs")
    R.append("")

    df_ols = df[valid].dropna(subset=controls + ["market_residual"]).copy()
    X = sm.add_constant(df_ols[controls])
    y = df_ols["market_residual"]
    m = sm.OLS(y, X).fit()
    sig_coef = m.params[col]
    sig_p = m.pvalues[col]
    robust = "ROBUST" if sig_p < 0.10 else "NOT ROBUST"
    R.append(f"- Signal coefficient: {sig_coef:+.5f}")
    R.append(f"- Signal p-value: {sig_p:.4f}")
    R.append(f"- Verdict: **{robust}**")
    R.append("")
    print(f"  Robustness: coef={sig_coef:+.5f}, p={sig_p:.4f} → {robust}")

    # ── TEST 5 — INDEPENDENCE FROM S12/P09 ───────────────────────
    R.append("### Test 5 — Independence from S12/P09")
    R.append("")
    R.append("S12 and P09 fields are not directly available in the V2 engine dataset.")
    R.append("S12 uses production CSW (FanGraphs/Savant) which differs from boxscore strike%.")
    R.append("P09 requires pitcher-level Statcast hard-hit lookups not joined here.")
    R.append("")
    R.append("Proxy check: correlation with closing_total and xFIP (which S12/P09 partially capture)")
    R.append("")
    for ctrl in ["closing_total", "home_sp_xfip", "away_sp_xfip"]:
        v = df[valid & df[ctrl].notna()]
        r_c, p_c = stats.pearsonr(v[col], v[ctrl])
        R.append(f"- corr({sig_name}, {ctrl}): r={r_c:.4f}")
    R.append("")
    R.append("S12/P09 direct test: SKIPPED (field mismatch — would require production CSW/Statcast join)")
    R.append("")

    # ── TEST 6 — V1 INTERACTION (walk-forward) ───────────────────
    R.append("### Test 6 — V1 Interaction (walk-forward safe)")
    R.append("")

    WARMUP = 50  # V1 UNDER games before activating
    PCTILE = 80 if direction == "HIGH" else 20  # top 20% or bottom 20%

    # Expanding threshold per season
    df_wf = df.sort_values("game_date").copy()
    df_wf["wf_threshold"] = np.nan

    for yr in [2024, 2025]:
        yr_mask = df_wf["season"] == yr
        yr_v1 = df_wf[yr_mask & (df_wf["v1_under"] == 1) & df_wf[col].notna()]

        # Walk forward through V1 UNDER games
        for i, (idx, row) in enumerate(yr_v1.iterrows()):
            if i < WARMUP:
                continue  # warmup
            prior = yr_v1.iloc[:i]
            if direction == "HIGH":
                thresh = prior[col].quantile(0.80)
            else:
                thresh = prior[col].quantile(0.20)
            df_wf.at[idx, "wf_threshold"] = thresh

    # Apply threshold
    if direction == "HIGH":
        df_wf["sig_active"] = (df_wf[col] >= df_wf["wf_threshold"]).astype(int)
    else:
        df_wf["sig_active"] = (df_wf[col] <= df_wf["wf_threshold"]).astype(int)
    df_wf.loc[df_wf["wf_threshold"].isna(), "sig_active"] = 0

    df_wf_np = df_wf[~df_wf["is_push"]].copy()

    # Frozen 2024 threshold for 2025 sensitivity
    v1_2024 = df[(df["season"] == 2024) & (df["v1_under"] == 1) & df[col].notna()]
    if direction == "HIGH":
        frozen_thresh = v1_2024[col].quantile(0.80)
    else:
        frozen_thresh = v1_2024[col].quantile(0.20)

    if direction == "HIGH":
        df_wf["sig_frozen"] = ((df_wf[col] >= frozen_thresh) & df_wf[col].notna()).astype(int)
    else:
        df_wf["sig_frozen"] = ((df_wf[col] <= frozen_thresh) & df_wf[col].notna()).astype(int)
    df_wf_np["sig_frozen"] = df_wf.loc[df_wf_np.index, "sig_frozen"]
    df_wf_np["sig_active"] = df_wf.loc[df_wf_np.index, "sig_active"]

    R.append(f"Warmup: first {WARMUP} V1 UNDER games per season excluded")
    R.append(f"Threshold: {direction} 20% ({f'p80' if direction == 'HIGH' else 'p20'}), expanding within season")
    R.append(f"Frozen 2024 threshold: {frozen_thresh:.5f}")
    R.append("")

    # Cohort results
    R.append("| Cohort | N | Under% | Resid | ROI | 2024 ROI | 2025 ROI |")
    R.append("|--------|---|--------|-------|-----|----------|----------|")

    cohorts = {
        "A: V1 alone": lambda d: d["v1_under"] == 1,
        f"B: V1 + {sig_name} (expanding)": lambda d: (d["v1_under"] == 1) & (d["sig_active"] == 1),
        f"B2: V1 + {sig_name} (frozen)": lambda d: (d["v1_under"] == 1) & (d["sig_frozen"] == 1),
    }

    for clabel, cfn in cohorts.items():
        for yr_label, yr_np_src, yr_all_src in [
            ("pooled", df_wf_np, df_wf),
            ("2024", df_wf_np[df_wf_np["season"] == 2024], df_wf[df_wf["season"] == 2024]),
            ("2025", df_wf_np[df_wf_np["season"] == 2025], df_wf[df_wf["season"] == 2025]),
        ]:
            mask = cfn(yr_np_src)
            n = mask.sum()
            if n < 10:
                if yr_label == "pooled":
                    R.append(f"| {clabel} | {n} | N/A | N/A | N/A | N/A | N/A |")
                continue
            ur = yr_np_src.loc[mask, "went_under"].mean()
            resid = ur - 0.50
            w = yr_np_src.loc[mask, "went_under"].sum()
            roi = roi_110(w, n - w)

            if yr_label == "pooled":
                # Also compute per-year ROIs
                yr_rois = {}
                for yr in [2024, 2025]:
                    yr_m = mask & (yr_np_src["season"] == yr)
                    yn = yr_m.sum()
                    if yn < 10:
                        yr_rois[yr] = "N/A"
                    else:
                        yw = yr_np_src.loc[yr_m, "went_under"].sum()
                        yr_rois[yr] = f"{roi_110(yw, yn - yw):+.1f}%"

                R.append(f"| {clabel} | {n} | {ur:.3f} | {resid:+.3f} | {roi:+.1f}% | "
                         f"{yr_rois[2024]} | {yr_rois[2025]} |")
                print(f"  {clabel}: N={n}, under%={ur:.3f}, ROI={roi:+.1f}%")

    R.append("")

    # ── TEST 7 — PERMUTATION (2025) ──────────────────────────────
    R.append("### Test 7 — Permutation (2025)")
    R.append("")

    v1_2025_np = df_wf_np[(df_wf_np["season"] == 2025) & (df_wf_np["v1_under"] == 1)]
    flagged = v1_2025_np["sig_active"] == 1
    n_flagged = flagged.sum()

    if n_flagged >= 10:
        obs_w = v1_2025_np.loc[flagged, "went_under"].sum()
        obs_roi = roi_110(obs_w, n_flagged - obs_w)
        obs_ur = v1_2025_np.loc[flagged, "went_under"].mean()

        N_PERM = 200
        outcomes = v1_2025_np["went_under"].values.copy()
        perm_rois = []
        for _ in range(N_PERM):
            np.random.shuffle(outcomes)
            w = outcomes[:n_flagged].sum()
            perm_rois.append(roi_110(w, n_flagged - w))
        perm_rois = np.array(perm_rois)
        pctile = (perm_rois <= obs_roi).mean() * 100

        R.append(f"- N flagged: {n_flagged}")
        R.append(f"- Observed: under%={obs_ur:.3f}, ROI={obs_roi:+.1f}%")
        R.append(f"- Permutation ({N_PERM} shuffles): median={np.median(perm_rois):+.1f}%, "
                 f"p5={np.percentile(perm_rois, 5):+.1f}%, p95={np.percentile(perm_rois, 95):+.1f}%")
        R.append(f"- Percentile: {pctile:.1f}%")
        R.append(f"- {'PASS' if pctile >= 85 else 'MARGINAL' if pctile >= 75 else 'FAIL'}")
        print(f"  Permutation: obs ROI={obs_roi:+.1f}%, pctile={pctile:.0f}%")
    else:
        R.append(f"- N flagged: {n_flagged} (too few for permutation)")
        pctile = np.nan
    R.append("")

    # ── TEST 8 — AVAILABILITY BIAS ───────────────────────────────
    R.append("### Test 8 — Availability Bias")
    R.append("")
    v1_np_all = df_np[df_np["v1_under"] == 1]
    avail = v1_np_all[col].notna()
    unavail = ~avail

    R.append("| Group | N | Under% | Avg Close | ROI |")
    R.append("|-------|---|--------|-----------|-----|")
    for lbl, mask in [("Available", avail), ("Unavailable", unavail)]:
        n = mask.sum()
        if n == 0: continue
        ur = v1_np_all.loc[mask, "went_under"].mean()
        avg_cl = df.loc[v1_np_all.loc[mask].index.intersection(df.index), "closing_total"].mean()
        w = v1_np_all.loc[mask, "went_under"].sum()
        roi = roi_110(w, n - w)
        R.append(f"| {lbl} | {n} | {ur:.3f} | {avg_cl:.2f} | {roi:+.1f}% |")

    bias = abs(v1_np_all.loc[avail, "went_under"].mean() -
               v1_np_all.loc[unavail, "went_under"].mean()) if unavail.sum() > 0 else 0
    R.append(f"\nAvailability bias: {bias:.3f} ({'CLEAN' if bias < 0.03 else 'WARNING'})")
    R.append("")


# =====================================================================
# FINAL VERDICT
# =====================================================================
R.append("---")
R.append("## Final Verdict")
R.append("")

# Collect key metrics for each signal
for sig_name, meta in SIGNALS.items():
    col = meta["col"]
    R.append(f"### {sig_name}")
    R.append("")

    # Gather evidence
    valid = df[col].notna()

    # Robustness
    controls_list = [col, "home_sp_xfip", "away_sp_xfip", "closing_total", "park_factor_runs"]
    df_ols = df[valid].dropna(subset=controls_list + ["market_residual"])
    X = sm.add_constant(df_ols[controls_list])
    y = df_ols["market_residual"]
    m = sm.OLS(y, X).fit()
    robust_p = m.pvalues[col]

    # Year coefs
    yr_signs = []
    for yr in [2024, 2025]:
        yr_df = df[(df["season"] == yr) & valid]
        X2 = sm.add_constant(yr_df[col])
        y2 = yr_df["market_residual"]
        m2 = sm.OLS(y2, X2).fit()
        yr_signs.append(m2.params[col])

    stable = yr_signs[0] * yr_signs[1] > 0

    # V1 interaction (pooled walk-forward expanding)
    v1_mask = df_wf_np["v1_under"] == 1
    sig_mask = (df_wf_np["v1_under"] == 1) & (df_wf_np["sig_active"] == 1)
    v1_n = v1_mask.sum()
    v1_roi = roi_110(df_wf_np.loc[v1_mask, "went_under"].sum(),
                     v1_n - df_wf_np.loc[v1_mask, "went_under"].sum())
    sig_n = sig_mask.sum()
    if sig_n > 0:
        sig_roi = roi_110(df_wf_np.loc[sig_mask, "went_under"].sum(),
                          sig_n - df_wf_np.loc[sig_mask, "went_under"].sum())
        lift = sig_roi - v1_roi
    else:
        sig_roi = np.nan
        lift = np.nan

    # Determine verdict
    if (robust_p < 0.10 and stable and not np.isnan(lift) and lift > 3 and sig_n >= 75):
        verdict = "ADVANCE"
        role = "V1 amplifier"
    elif (not np.isnan(lift) and lift > 0 and sig_n >= 50):
        verdict = "INVESTIGATE"
        role = "V1 amplifier candidate (needs 2026 validation)"
    else:
        verdict = "SHELVE"
        role = "scanner ingredient only"

    # Independence
    r_close, _ = stats.pearsonr(df.loc[valid & df["closing_total"].notna(), col],
                                 df.loc[valid & df["closing_total"].notna(), "closing_total"])
    indep = "independent" if abs(r_close) < 0.15 else "partially correlated" if abs(r_close) < 0.30 else "priced"

    R.append(f"| Criterion | Result |")
    R.append(f"|-----------|--------|")
    R.append(f"| Robustness (p after controls) | {robust_p:.4f} {'ROBUST' if robust_p < 0.10 else 'NOT ROBUST'} |")
    R.append(f"| Year stability | {'STABLE' if stable else 'MIXED'} ({yr_signs[0]:+.4f} / {yr_signs[1]:+.4f}) |")
    R.append(f"| V1 interaction lift | {lift:+.1f}pp (N={sig_n}) |" if not np.isnan(lift) else f"| V1 interaction lift | N/A |")
    R.append(f"| Market independence | {indep} (r={r_close:.3f}) |")
    R.append(f"| Permutation 2025 | {'see above'} |")
    R.append(f"| Availability bias | {'see above'} |")
    R.append("")
    R.append(f"**Verdict: {verdict}**")
    R.append(f"- Best role: {role}")
    R.append(f"- Independent from S12/P09: {indep} with closing_total; direct S12/P09 test skipped (field mismatch)")
    R.append(f"- Minimum viable N for live use: 100 qualifying V1+signal games per season")
    R.append("")

# Save
out = BASE / "v2_deep_analysis.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"\nSaved: {out}")
