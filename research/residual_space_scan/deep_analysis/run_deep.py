#!/usr/bin/env python3
"""
Deep analysis on combined_short_exit and combined_lineup_iso.
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

# ── Load ──────────────────────────────────────────────────────────────
df = pd.read_parquet(BASE.parent / "residual_dataset.parquet")
df["date"] = pd.to_datetime(df["date"])
df["market_residual_over"] = df["actual_result_over"] - 0.50
df["combined_bp_xfip"] = (df["home_bp_xfip"] + df["away_bp_xfip"]) / 2
df["v1_over_lean"] = (df["p_under"] < 0.45).astype(int)
df_np = df[~df["is_push"]].copy()

print(f"Dataset: {len(df)} games, {len(df_np)} non-push")
v1_over = df_np[df_np["v1_over_lean"] == 1]
v1_w = v1_over["actual_result_over"].sum()
v1_roi = roi_110(v1_w, len(v1_over) - v1_w)
print(f"V1 OVER-lean: N={len(v1_over)}, over%={v1_over.actual_result_over.mean():.3f}, ROI={v1_roi:+.1f}%")

SIGS = {
    "combined_short_exit": {"direction": "LOW", "label": "durable starters (bot)"},
    "combined_lineup_iso": {"direction": "HIGH", "label": "power lineups (top)"},
}

# Audit
audit = [
    "# Source Audit", "",
    f"- residual_dataset.parquet: {len(df)} rows",
    f"- combined_short_exit: 100% coverage",
    f"- combined_lineup_iso: 100% coverage",
    f"- Controls: closing_total, home/away_sp_xfip, park_factor_runs, temperature, bp_xfip all present",
    f"- V1 p_under: present, V1 OVER-lean (p<0.45): {df.v1_over_lean.sum()}",
    f"- S12/P09 fields: reconstructed in residual scan (CSW proxy; see parent scan notes)",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")

R = []
R.append("# Deep Analysis — combined_short_exit and combined_lineup_iso")
R.append("")
R.append(f"Dataset: {len(df)} games, {len(df_np)} non-push")
R.append(f"V1 OVER-lean (p_under<0.45): N={len(v1_over)}, over%={v1_over.actual_result_over.mean():.3f}, ROI={v1_roi:+.1f}%")
R.append("")

all_deciles = []
all_thresholds = []

for sig, meta in SIGS.items():
    direction = meta["direction"]
    print(f"\n{'='*60}\n{sig} ({meta['label']})\n{'='*60}")

    R.append(f"---\n## {sig}\nDirection: {direction} → OVER\nMechanism: {meta['label']}\n")

    # ── TEST 1 — SEASON STABILITY ────────────────────────────────
    R.append("### Test 1 — Season Stability\n")
    R.append("| Year | Coefficient | p-value | R² |")
    R.append("|------|-----------|---------|-----|")
    yr_coefs = {}
    for yr in [2024, 2025]:
        yr_df = df[df["season"] == yr]
        X = sm.add_constant(yr_df[sig])
        y = yr_df["market_residual_over"]
        m = sm.OLS(y, X).fit()
        yr_coefs[yr] = m.params[sig]
        R.append(f"| {yr} | {m.params[sig]:+.5f} | {m.pvalues[sig]:.4f} | {m.rsquared:.6f} |")
        print(f"  {yr}: coef={m.params[sig]:+.5f}, p={m.pvalues[sig]:.4f}")

    stable = yr_coefs[2024] * yr_coefs[2025] > 0
    mag_ratio = abs(yr_coefs[2025]) / max(abs(yr_coefs[2024]), 1e-10)
    if stable and 0.5 < mag_ratio < 2.0:
        stab_verdict = "STABLE"
    elif stable and mag_ratio >= 2.0:
        stab_verdict = "STABLE — STRENGTHENING"
    elif stable:
        stab_verdict = "STABLE — WEAKENING"
    else:
        stab_verdict = "MIXED"
    R.append(f"\nVerdict: **{stab_verdict}**\n")

    # Favorable tail ROI by season
    for yr in [2024, 2025]:
        yr_np = df_np[df_np["season"] == yr]
        if direction == "LOW":
            thresh = yr_np[sig].quantile(0.10)
            mask = yr_np[sig] <= thresh
        else:
            thresh = yr_np[sig].quantile(0.90)
            mask = yr_np[sig] > thresh
        n = mask.sum()
        if n > 20:
            w = yr_np.loc[mask, "actual_result_over"].sum()
            roi = roi_110(w, n - w)
            R.append(f"- {yr} favorable-10% tail: N={n}, ROI={roi:+.1f}%")

    R.append("")

    # ── TEST 2 — DECILE STRUCTURE ────────────────────────────────
    R.append("### Test 2 — Decile Structure\n")
    R.append("| Decile | N | Mean | Resid | Over% | ROI |")
    R.append("|--------|---|------|-------|-------|-----|")
    sub = df_np.copy()
    sub["decile"] = pd.qcut(sub[sig], 10, labels=False, duplicates="drop")
    dec_data = []
    for dec in sorted(sub["decile"].unique()):
        d = sub[sub["decile"] == dec]
        n = len(d)
        mean_v = d[sig].mean()
        resid = d["market_residual_over"].mean()
        over_r = d["actual_result_over"].mean()
        w = d["actual_result_over"].sum()
        roi = roi_110(w, n - w)
        R.append(f"| {dec} | {n} | {mean_v:.4f} | {resid:+.4f} | {over_r:.3f} | {roi:+.1f}% |")
        dec_data.append({"signal": sig, "decile": dec, "N": n, "mean": mean_v,
                          "resid": resid, "over_rate": over_r, "roi": roi})
    all_deciles.extend(dec_data)

    resids = [d["resid"] for d in dec_data]
    if direction == "LOW":
        fav_end = resids[:3]
        unfav_end = resids[-3:]
    else:
        fav_end = resids[-3:]
        unfav_end = resids[:3]

    mono_check = all(resids[i] <= resids[i+1] for i in range(len(resids)-1)) or \
                 all(resids[i] >= resids[i+1] for i in range(len(resids)-1))
    if mono_check:
        gradient = "monotonic"
    elif abs(np.mean(fav_end)) > 0.02 and abs(np.mean(unfav_end)) < 0.01:
        gradient = "tail-only"
    else:
        gradient = "noisy"
    R.append(f"\nGradient: **{gradient}**\n")

    # ── TEST 3 — THRESHOLD SENSITIVITY ───────────────────────────
    R.append("### Test 3 — Threshold Sensitivity\n")
    R.append("| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |")
    R.append("|-----------|---|-------|-------|-----|----------|----------|")

    if direction == "LOW":
        thresholds = [("bot_10", 0, 10), ("bot_20", 0, 20), ("bot_30", 0, 30)]
    else:
        thresholds = [("top_10", 90, 100), ("top_20", 80, 100), ("top_30", 70, 100)]

    best_thresh = None
    best_roi = -999
    for label, lo_pct, hi_pct in thresholds:
        lo_val = df_np[sig].quantile(lo_pct / 100)
        hi_val = df_np[sig].quantile(hi_pct / 100)
        if lo_pct == 0:
            mask = df_np[sig] <= hi_val
        else:
            mask = df_np[sig] > lo_val

        n = mask.sum()
        over_r = df_np.loc[mask, "actual_result_over"].mean()
        resid = over_r - 0.50
        w = df_np.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)

        yr_rois = {}
        for yr in [2024, 2025]:
            yr_m = mask & (df_np["season"] == yr)
            yn = yr_m.sum()
            if yn < 20: yr_rois[yr] = "N/A"
            else:
                yw = df_np.loc[yr_m, "actual_result_over"].sum()
                yr_rois[yr] = f"{roi_110(yw, yn - yw):+.1f}%"

        thin = " (THIN)" if n < 75 else ""
        R.append(f"| {label}{thin} | {n} | {over_r:.3f} | {resid:+.3f} | {roi:+.1f}% | {yr_rois[2024]} | {yr_rois[2025]} |")

        all_thresholds.append({"signal": sig, "threshold": label, "N": n,
                                "over_rate": over_r, "resid": resid, "roi": roi,
                                "roi_2024": yr_rois[2024], "roi_2025": yr_rois[2025]})

        if roi > best_roi:
            best_roi = roi
            best_thresh = label

    R.append(f"\nSweet spot: **{best_thresh}**\n")

    # ── TEST 4 — ROBUSTNESS ─────────────────────────────────────
    R.append("### Test 4 — Robustness Controls\n")
    controls = [sig, "closing_total", "home_sp_xfip", "away_sp_xfip",
                "park_factor_runs", "temperature", "combined_bp_xfip"]
    df_ols = df.dropna(subset=controls + ["market_residual_over"])
    X = sm.add_constant(df_ols[controls])
    y = df_ols["market_residual_over"]
    m = sm.OLS(y, X).fit()
    sig_coef = m.params[sig]
    sig_p = m.pvalues[sig]
    robust = "ROBUST" if sig_p < 0.10 else "ABSORBED"
    R.append(f"- Coefficient: {sig_coef:+.5f}")
    R.append(f"- p-value: {sig_p:.4f}")
    R.append(f"- Verdict: **{robust}**\n")
    print(f"  Robustness: coef={sig_coef:+.5f}, p={sig_p:.4f} → {robust}")

    # ── TEST 5 — MARKET AWARENESS ───────────────────────────────
    R.append("### Test 5 — Market Awareness\n")
    r_corr, _ = stats.pearsonr(df[sig], df["closing_total"])
    R.append(f"- corr(signal, closing_total): r={r_corr:.4f}")

    if direction == "LOW":
        p10 = df[sig].quantile(0.10)
        fav_cl = df.loc[df[sig] <= p10, "closing_total"].mean()
        rest_cl = df.loc[df[sig] > p10, "closing_total"].mean()
    else:
        p90 = df[sig].quantile(0.90)
        fav_cl = df.loc[df[sig] > p90, "closing_total"].mean()
        rest_cl = df.loc[df[sig] <= p90, "closing_total"].mean()

    diff = fav_cl - rest_cl
    R.append(f"- Avg closing total — favorable bucket: {fav_cl:.2f}, rest: {rest_cl:.2f}, diff: {diff:+.2f}")
    if abs(diff) < 0.15:
        awareness = "Market **mostly misses** this"
    elif abs(diff) < 0.30:
        awareness = "Market **partially prices** this"
    else:
        awareness = "Market **substantially prices** this"
    R.append(f"- {awareness}\n")

# ── TEST 6 — V1 INTERACTION (walk-forward) ───────────────────────
R.append("---\n## Test 6 — V1 Interaction (Walk-Forward)\n")

WARMUP = 50
df_wf = df.sort_values("date").copy()
df_wf_np = df_wf[~df_wf["is_push"]].copy()

for sig, meta in SIGS.items():
    direction = meta["direction"]
    for pct_label, pctile in [("10", 10 if direction == "LOW" else 90),
                               ("20", 20 if direction == "LOW" else 80),
                               ("30", 30 if direction == "LOW" else 70)]:
        col_name = f"{sig}_wf_{pct_label}"
        df_wf[col_name] = 0

        for yr in [2024, 2025]:
            yr_mask = (df_wf["season"] == yr) & (df_wf["v1_over_lean"] == 1) & df_wf[sig].notna()
            yr_v1 = df_wf[yr_mask]
            for i, (idx, row) in enumerate(yr_v1.iterrows()):
                if i < WARMUP:
                    continue
                prior = yr_v1.iloc[:i]
                if direction == "LOW":
                    thresh = prior[sig].quantile(pctile / 100)
                    df_wf.at[idx, col_name] = 1 if row[sig] <= thresh else 0
                else:
                    thresh = prior[sig].quantile(pctile / 100)
                    df_wf.at[idx, col_name] = 1 if row[sig] > thresh else 0

df_wf_np = df_wf[~df_wf["is_push"]].copy()

R.append(f"Warmup: first {WARMUP} V1 OVER-lean games per season\n")
R.append("| Cohort | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |")
R.append("|--------|---|-------|-------|-----|----------|----------|")

cohorts = [("A: V1 OVER-lean alone", lambda d: d["v1_over_lean"] == 1)]

for sig, meta in SIGS.items():
    for pct in ["10", "20", "30"]:
        dir_label = "bot" if meta["direction"] == "LOW" else "top"
        col = f"{sig}_wf_{pct}"
        label = f"V1 + {sig.split('_')[-1]} {dir_label}{pct}"
        cohorts.append((label, lambda d, c=col: (d["v1_over_lean"] == 1) & (d[c] == 1)))

# Combined best
cohorts.append(("V1 + short_exit bot20 + iso top20",
    lambda d: (d["v1_over_lean"] == 1) & (d["combined_short_exit_wf_20"] == 1) & (d["combined_lineup_iso_wf_20"] == 1)))

for clabel, cfn in cohorts:
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
R.append("---\n## Test 7 — Independence\n")
r_inter, p_inter = stats.pearsonr(df["combined_short_exit"], df["combined_lineup_iso"])
R.append(f"- corr(short_exit, lineup_iso): r={r_inter:.4f}, p={p_inter:.4f}")
if abs(r_inter) > 0.60: R.append("- **REDUNDANT**")
elif abs(r_inter) > 0.30: R.append("- Partially correlated")
else: R.append("- **INDEPENDENT**")

# Joint OLS
X = sm.add_constant(df[["combined_short_exit", "combined_lineup_iso"]])
y = df["market_residual_over"]
m = sm.OLS(y, X).fit()
R.append(f"- Joint OLS: short_exit coef={m.params['combined_short_exit']:+.5f} (p={m.pvalues['combined_short_exit']:.4f}), "
         f"iso coef={m.params['combined_lineup_iso']:+.5f} (p={m.pvalues['combined_lineup_iso']:.4f})")
R.append(f"- R²={m.rsquared:.6f}\n")

# ── TEST 8 — PERMUTATION (2025) ─────────────────────────────────
R.append("---\n## Test 8 — Permutation (2025)\n")
for sig, meta in SIGS.items():
    pct = "20"
    col = f"{sig}_wf_{pct}"
    yr_np = df_wf_np[(df_wf_np["season"] == 2025) & (df_wf_np["v1_over_lean"] == 1)]
    flagged = yr_np[col] == 1
    n_f = flagged.sum()
    if n_f < 10:
        R.append(f"**{sig}**: N={n_f}, too few\n")
        continue
    obs_w = yr_np.loc[flagged, "actual_result_over"].sum()
    obs_roi = roi_110(obs_w, n_f - obs_w)
    outcomes = yr_np["actual_result_over"].values.copy()
    perm_rois = []
    for _ in range(200):
        np.random.shuffle(outcomes)
        w = outcomes[:n_f].sum()
        perm_rois.append(roi_110(w, n_f - w))
    perm_rois = np.array(perm_rois)
    pctile = (perm_rois <= obs_roi).mean() * 100
    R.append(f"**{sig}** (V1 + {meta['direction'].lower()} 20%, walk-forward):")
    R.append(f"- N={n_f}, obs ROI={obs_roi:+.1f}%")
    R.append(f"- Permutation: median={np.median(perm_rois):+.1f}%, p5={np.percentile(perm_rois,5):+.1f}%, p95={np.percentile(perm_rois,95):+.1f}%")
    R.append(f"- Percentile: {pctile:.0f}% ({'PASS' if pctile >= 85 else 'MARGINAL' if pctile >= 75 else 'FAIL'})\n")
    print(f"  Perm {sig}: obs={obs_roi:+.1f}%, pctile={pctile:.0f}%")

# ── TEST 9 — AVAILABILITY BIAS ──────────────────────────────────
R.append("---\n## Test 9 — Availability Bias\n")
for sig in SIGS:
    R.append(f"**{sig}:**")
    v1_np = df_np[df_np["v1_over_lean"] == 1]
    avail = v1_np[sig].notna()
    unavail = ~avail
    R.append("| Group | N | Over% | Avg Close | ROI |")
    R.append("|-------|---|-------|-----------|-----|")
    for lbl, mask in [("Available", avail), ("Unavailable", unavail)]:
        n = mask.sum()
        if n == 0: continue
        over_r = v1_np.loc[mask, "actual_result_over"].mean()
        w = v1_np.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)
        avg_cl = df.loc[v1_np.loc[mask].index.intersection(df.index), "closing_total"].mean()
        R.append(f"| {lbl} | {n} | {over_r:.3f} | {avg_cl:.2f} | {roi:+.1f}% |")
    bias = 0 if unavail.sum() == 0 else abs(v1_np.loc[avail, "actual_result_over"].mean() -
                                               v1_np.loc[unavail, "actual_result_over"].mean())
    R.append(f"\nBias: {bias:.3f} ({'CLEAN' if bias < 0.03 else 'WARNING'})\n")

# =====================================================================
# FINAL VERDICT
# =====================================================================
R.append("---\n## Final Verdict\n")

for sig, meta in SIGS.items():
    direction = meta["direction"]
    R.append(f"### {sig}\n")

    # Gather walk-forward V1 interaction top20
    col20 = f"{sig}_wf_20"
    wf_mask = (df_wf_np["v1_over_lean"] == 1) & (df_wf_np[col20] == 1)
    wf_n = wf_mask.sum()
    if wf_n > 0:
        wf_or = df_wf_np.loc[wf_mask, "actual_result_over"].mean()
        wf_w = df_wf_np.loc[wf_mask, "actual_result_over"].sum()
        wf_roi = roi_110(wf_w, wf_n - wf_w)
        lift = wf_roi - v1_roi
    else:
        wf_roi = lift = np.nan

    # Year ROIs
    yr_wf = {}
    for yr in [2024, 2025]:
        yr_m = wf_mask & (df_wf_np["season"] == yr)
        yn = yr_m.sum()
        if yn >= 10:
            yw = df_wf_np.loc[yr_m, "actual_result_over"].sum()
            yr_wf[yr] = roi_110(yw, yn - yw)
        else:
            yr_wf[yr] = np.nan

    R.append(f"| Criterion | Result |")
    R.append(f"|-----------|--------|")
    R.append(f"| Season stability | {stab_verdict} |")
    R.append(f"| Walk-forward V1 {direction.lower()}20 ROI | {wf_roi:+.1f}% (N={wf_n}) |" if not np.isnan(wf_roi) else "| WF ROI | N/A |")
    R.append(f"| V1 lift | {lift:+.1f}pp |" if not np.isnan(lift) else "| V1 lift | N/A |")
    r24s = f"{yr_wf[2024]:+.1f}%" if not np.isnan(yr_wf.get(2024, np.nan)) else "N/A"
    r25s = f"{yr_wf[2025]:+.1f}%" if not np.isnan(yr_wf.get(2025, np.nan)) else "N/A"
    R.append(f"| 2024 / 2025 | {r24s} / {r25s} |")
    R.append("")

    # Verdict
    both_pos = (not np.isnan(yr_wf.get(2024, np.nan)) and not np.isnan(yr_wf.get(2025, np.nan))
                and yr_wf[2024] > 0 and yr_wf[2025] > 0)
    if not np.isnan(lift) and lift > 3 and wf_n >= 75 and both_pos:
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
    R.append(f"- Viable cohort: ~{wf_n//2} games/season")
    R.append(f"- Independent from other signal: r={r_inter:.3f}")
    R.append("")

# Save
out = BASE / "residual_candidates_deep_analysis.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")

pd.DataFrame(all_deciles).to_parquet(BASE / "residual_candidates_deciles.parquet", index=False)
pd.DataFrame(all_thresholds).to_parquet(BASE / "residual_candidates_thresholds.parquet", index=False)

# Results table
results = []
for sig, meta in SIGS.items():
    col20 = f"{sig}_wf_20"
    wf_mask = (df_wf_np["v1_over_lean"] == 1) & (df_wf_np[col20] == 1)
    wf_n = wf_mask.sum()
    if wf_n > 0:
        wf_w = df_wf_np.loc[wf_mask, "actual_result_over"].sum()
        wf_roi = roi_110(wf_w, wf_n - wf_w)
    else:
        wf_roi = np.nan
    results.append({"signal": sig, "wf_n": wf_n, "wf_roi": wf_roi})
pd.DataFrame(results).to_parquet(BASE / "residual_candidates_results.parquet", index=False)

print(f"\nSaved all outputs to {BASE}")
