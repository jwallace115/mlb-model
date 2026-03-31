#!/usr/bin/env python3
"""
F5 Research — Full backtest pipeline.

Steps:
  1. Derive p_under from existing frozen S3 sim results
  2. Build joined F5 research dataset
  3-6. Run all pre-registered signals and diagnostics

All outputs in research/f5/data/ only. No production files modified.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "f5" / "data"
OUT.mkdir(parents=True, exist_ok=True)

# Frozen thresholds
F5_RUN_FRACTION = 0.56
WIN_UNIT = 100 / 110  # ~0.9091
CSW_Q50 = 27.03  # from calibration_params.json
CSW_Q75 = 29.294

# ─────────────────────────────────────────────
# STEP 1 — Derive p_under from frozen S3 outputs
# ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — DERIVE p_under FROM FROZEN S3 RESULTS")
print("=" * 60)

sr24 = pd.read_parquet(PROJECT / "mlb_sim" / "eval" / "sim_results_oos_2024.parquet")
sr25 = pd.read_parquet(PROJECT / "mlb_sim" / "eval" / "sim_results_2025.parquet")

# Compute p_under = 1 - p_over_line (frozen S3 definition: p_under = P(total <= line))
sr24["p_under_full"] = 1.0 - sr24["p_over_line"]
sr24["p_over_full"] = sr24["p_over_line"]
sr24["season"] = 2024

sr25["p_under_full"] = 1.0 - sr25["p_over_line"]
sr25["p_over_full"] = sr25["p_over_line"]
if "season" not in sr25.columns:
    sr25["season"] = 2025

# Unify columns
keep = ["game_pk", "date", "home_team", "away_team", "p_under_full",
        "p_over_full", "closing_line", "m3_projection", "season",
        "sim_mean_total", "sim_std_total"]
v1 = pd.concat([sr24[keep], sr25[keep]], ignore_index=True)
v1["game_id"] = v1["game_pk"].astype(str)

v1.to_parquet(OUT / "v1_probabilities_2024_2025.parquet", index=False)

# Sanity checks
print(f"  Total games: {len(v1)}")
for s in [2024, 2025]:
    sub = v1[v1["season"] == s]
    print(f"  {s}: N={len(sub)}, p_under mean={sub['p_under_full'].mean():.4f}, "
          f"std={sub['p_under_full'].std():.4f}")
    print(f"    >0.57: {(sub['p_under_full'] > 0.57).sum()} "
          f"({(sub['p_under_full'] > 0.57).mean()*100:.1f}%)")
    print(f"    >0.60: {(sub['p_under_full'] > 0.60).sum()} "
          f"({(sub['p_under_full'] > 0.60).mean()*100:.1f}%)")

# ─────────────────────────────────────────────
# STEP 2 — Build F5 research dataset
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — BUILD F5 RESEARCH DATASET")
print("=" * 60)

# F5 lines
f5 = pd.read_parquet(PROJECT / "research" / "team_totals" / "data" / "f5_lines_historical.parquet")
f5_ok = f5[f5["pull_status"] == "ok"].copy()
f5_ok["game_id"] = f5_ok["game_id"].astype(str)
f5_keep = ["game_id", "f5_line", "f5_over_price", "f5_under_price",
           "primary_book", "books_count"]
f5_ok = f5_ok[f5_keep]

# Feature table (actuals)
ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_id"] = ft["game_pk"].astype(str)
ft_keep = ["game_id", "actual_f5_total", "actual_total", "home_score", "away_score"]
ft_sub = ft[ft_keep].copy()

# S3 team projections
s3 = pd.read_parquet(PROJECT / "research" / "team_totals" / "data" / "s3_team_projections.parquet")
s3["game_id"] = s3["game_id"].astype(str)
s3_keep = ["game_id", "mu_home", "mu_away", "std_home", "std_away",
           "run_gap", "suppressed_team", "suppressed_mu", "favored_mu",
           "p_path0_home", "p_path0_away",
           "hsp_xfip", "asp_xfip", "hsp_csw", "asp_csw"]
s3_sub = s3[s3_keep].copy()

# Starter CSW from sim_inputs (pivot home/away per game)
si_hist = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_historical_2022_2024.parquet")
si_25 = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_2025.parquet")
si = pd.concat([si_hist[si_hist["season"].isin([2024])], si_25], ignore_index=True)
si["game_id"] = si["game_pk"].astype(str)

# Pivot to game-level: home and away CSW
si_home = si[si["is_home"] == 1][["game_id", "sp_csw_pct", "sp_xfip", "sp_whiff_pct"]].rename(
    columns={"sp_csw_pct": "home_csw_si", "sp_xfip": "home_xfip_si", "sp_whiff_pct": "home_whiff_si"})
si_away = si[si["is_home"] == 0][["game_id", "sp_csw_pct", "sp_xfip", "sp_whiff_pct"]].rename(
    columns={"sp_csw_pct": "away_csw_si", "sp_xfip": "away_xfip_si", "sp_whiff_pct": "away_whiff_si"})

# Join all
df = v1.merge(f5_ok, on="game_id", how="inner")
print(f"  v1 ∩ f5: {len(df)}")
df = df.merge(ft_sub, on="game_id", how="inner")
print(f"  + ft: {len(df)}")
df = df.merge(s3_sub, on="game_id", how="inner")
print(f"  + s3: {len(df)}")
df = df.merge(si_home, on="game_id", how="left")
df = df.merge(si_away, on="game_id", how="left")
print(f"  + si (starter metrics): {len(df)}")

# Usable subset: all required fields present
usable_mask = (
    df["p_under_full"].notna() &
    df["f5_line"].notna() &
    df["actual_f5_total"].notna() &
    df["actual_total"].notna() &
    df["closing_line"].notna() &
    df["mu_home"].notna()
)
ds = df[usable_mask].copy().reset_index(drop=True)

# Compute derived fields
ds["s3_implied_f5"] = (ds["mu_home"] + ds["mu_away"]) * F5_RUN_FRACTION
ds["pricing_error"] = ds["f5_line"] - ds["s3_implied_f5"]

# Determine suppressing pitcher CSW
# Suppressing pitcher = the SP whose team is FACING the suppressed team
# i.e. the dominant SP that creates the run_gap
ds["suppressing_csw"] = np.where(
    ds["suppressed_team"] == ds["away_team"],  # away team is suppressed
    ds["hsp_csw"],  # home SP is the suppressing pitcher (uses s3 data)
    ds["asp_csw"]   # away SP is the suppressing pitcher
)
# Also from sim_inputs for backup
ds["suppressing_csw_si"] = np.where(
    ds["suppressed_team"] == ds["away_team"],
    ds["home_csw_si"],
    ds["away_csw_si"]
)
# Use s3 CSW first, fall back to sim_inputs
ds["suppressing_csw_final"] = ds["suppressing_csw"].fillna(ds["suppressing_csw_si"])

ds.to_parquet(OUT / "f5_research_dataset.parquet", index=False)

print(f"\n  USABLE DATASET:")
for s in [2024, 2025]:
    n = len(ds[ds["season"] == s])
    label = "PARTIAL — 77.7% F5 coverage" if s == 2024 else ""
    print(f"    {s}: {n} games {label}")
print(f"    Total: {len(ds)}")


# ─────────────────────────────────────────────
# GRADING FUNCTIONS
# ─────────────────────────────────────────────
def grade_f5(row):
    """Grade F5 under: WIN if actual < line, LOSS if actual > line, PUSH if ==."""
    actual = row["actual_f5_total"]
    line = row["f5_line"]
    if actual < line:
        return "WIN"
    elif actual > line:
        return "LOSS"
    else:
        return "PUSH"

def grade_full(row):
    """Grade full-game under at closing_line."""
    actual = row["actual_total"]
    line = row["closing_line"]
    if actual < line:
        return "WIN"
    elif actual > line:
        return "LOSS"
    else:
        return "PUSH"

def compute_roi(results, stake=1.0):
    """Compute ROI from list of WIN/LOSS/PUSH."""
    n = len(results)
    if n == 0:
        return 0, 0, 0, 0, 0, 0
    wins = sum(1 for r in results if r == "WIN")
    losses = sum(1 for r in results if r == "LOSS")
    pushes = sum(1 for r in results if r == "PUSH")
    net = wins * stake * WIN_UNIT - losses * stake
    roi = net / (n * stake) * 100
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    return n, wins, losses, pushes, wr, roi, net

def fmt_signal(name, results, stake=1.0, thin_threshold=40, extra=""):
    """Format signal result line."""
    n, w, l, p, wr, roi, net = compute_roi(results, stake)
    thin = " (THIN)" if n < thin_threshold else ""
    return (f"    {name}: N={n}, W={w}, L={l}, P={p}, "
            f"win%={wr:.1f}%, ROI={roi:+.1f}%, net={net:+.1f}u{thin}{extra}")


# ─────────────────────────────────────────────
# STEP 3-4 — CORE BACKTEST
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEPS 3-4 — CORE BACKTEST")
print("=" * 60)

# Pre-grade all rows
ds["f5_grade"] = ds.apply(grade_f5, axis=1)
ds["full_grade"] = ds.apply(grade_full, axis=1)

for group_name, group_mask in [("ALL (books_count >= 1)", ds["books_count"] >= 1),
                                ("BOOKS >= 2", ds["books_count"] >= 2)]:
    g = ds[group_mask]
    print(f"\n  --- {group_name} (N={len(g)}) ---")

    # Signal A — Game under baseline
    sig_a = g[g["p_under_full"] > 0.57]
    print(fmt_signal("A: Game Under (p>0.57)", sig_a["full_grade"].tolist()))

    sig_a60 = g[g["p_under_full"] > 0.60]
    print(fmt_signal("A: Game Under (p>0.60)", sig_a60["full_grade"].tolist()))

    # Signal B — F5 under
    sig_b = g[g["p_under_full"] > 0.57]
    print(fmt_signal("B: F5 Under (p>0.57)", sig_b["f5_grade"].tolist()))

    # Signal C — High-confidence F5 under
    sig_c = g[g["p_under_full"] > 0.60]
    print(fmt_signal("C: F5 Under (p>0.60)", sig_c["f5_grade"].tolist()))

    # Signal C by season
    for s in [2024, 2025]:
        sub = sig_c[sig_c["season"] == s]
        label = " (PARTIAL)" if s == 2024 else ""
        print(fmt_signal(f"   C [{s}{label}]", sub["f5_grade"].tolist()))

    # Signal D — CSW-filtered F5 under (DIAGNOSTIC)
    sig_d = g[(g["p_under_full"] > 0.57) & (g["suppressing_csw_final"] >= CSW_Q50)]
    print(fmt_signal("D: CSW-filtered F5 Under (DIAG)", sig_d["f5_grade"].tolist()))

    # Signal E — Combined game + F5 (DIAGNOSTIC)
    sig_e = g[g["p_under_full"] > 0.57].copy()
    if len(sig_e) > 0:
        e_full = sig_e["full_grade"].tolist()
        e_f5 = sig_e["f5_grade"].tolist()
        n_e = len(sig_e)
        # Each game: 2u risked (1u full + 1u F5)
        net_e = 0
        both_w = both_l = f5w_gl = f5l_gw = any_push = 0
        for fg, f5g in zip(e_full, e_f5):
            leg1 = WIN_UNIT if fg == "WIN" else (-1.0 if fg == "LOSS" else 0)
            leg2 = WIN_UNIT if f5g == "WIN" else (-1.0 if f5g == "LOSS" else 0)
            net_e += leg1 + leg2
            if fg == "WIN" and f5g == "WIN": both_w += 1
            elif fg == "LOSS" and f5g == "LOSS": both_l += 1
            elif f5g == "WIN" and fg == "LOSS": f5w_gl += 1
            elif f5g == "LOSS" and fg == "WIN": f5l_gw += 1
            if fg == "PUSH" or f5g == "PUSH": any_push += 1
        roi_e = net_e / (n_e * 2) * 100
        thin = " (THIN)" if n_e < 40 else ""
        print(f"    E: Combined (DIAG): N={n_e}, ROI={roi_e:+.1f}% (2u), "
              f"net={net_e:+.1f}u, both_w={both_w}, both_l={both_l}{thin}")


# ─────────────────────────────────────────────
# STEP 5 — DIAGNOSTIC TESTS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5 — DIAGNOSTIC TESTS")
print("=" * 60)

# 5A — Threshold sensitivity
print("\n  5A — Threshold sensitivity (Signal B, all books)")
print(f"    {'thresh':>6} {'N':>5} {'win%':>7} {'95% CI':>14} {'ROI':>8}")
for thresh in np.arange(0.54, 0.61, 0.01):
    sub = ds[ds["p_under_full"] > thresh]
    results = sub["f5_grade"].tolist()
    n, w, l, p, wr, roi, net = compute_roi(results)
    # Wilson CI
    if (w + l) > 0:
        wr_frac = w / (w + l)
        n_wl = w + l
        z = 1.96
        denom = 1 + z**2 / n_wl
        centre = (wr_frac + z**2 / (2 * n_wl)) / denom
        spread = z * np.sqrt((wr_frac * (1 - wr_frac) + z**2 / (4 * n_wl)) / n_wl) / denom
        ci_lo, ci_hi = max(0, centre - spread) * 100, min(1, centre + spread) * 100
    else:
        ci_lo, ci_hi = 0, 0
    thin = " *" if n < 40 else ""
    print(f"    {thresh:.2f}  {n:5d} {wr:6.1f}% [{ci_lo:5.1f}-{ci_hi:5.1f}] {roi:+7.1f}%{thin}")

# 5B — Temporal split
print("\n  5B — Temporal split (Signal B, p>0.57)")
sig_b_all = ds[ds["p_under_full"] > 0.57].copy()
for s in [2024, 2025]:
    sub = sig_b_all[sig_b_all["season"] == s].copy()
    if len(sub) == 0:
        print(f"    {s}: no games")
        continue
    sub = sub.sort_values("date")
    mid = len(sub) // 2
    h1 = sub.iloc[:mid]
    h2 = sub.iloc[mid:]
    _, _, _, _, wr1, roi1, net1 = compute_roi(h1["f5_grade"].tolist())
    _, _, _, _, wr2, roi2, net2 = compute_roi(h2["f5_grade"].tolist())
    total_net = net1 + net2
    conc = ""
    if total_net != 0:
        pct1 = abs(net1 / total_net) * 100 if total_net != 0 else 0
        pct2 = abs(net2 / total_net) * 100 if total_net != 0 else 0
        if max(pct1, pct2) > 70:
            conc = " (HALF CONCENTRATED)"
    label = " (PARTIAL)" if s == 2024 else ""
    print(f"    {s}{label}: H1 N={len(h1)} ROI={roi1:+.1f}% net={net1:+.1f}u | "
          f"H2 N={len(h2)} ROI={roi2:+.1f}% net={net2:+.1f}u{conc}")

# 5C — Season standalone
print("\n  5C — Season standalone")
for sig_name, thresh in [("B (p>0.57)", 0.57), ("C (p>0.60)", 0.60)]:
    for s in [2024, 2025]:
        sub = ds[(ds["p_under_full"] > thresh) & (ds["season"] == s)]
        label = " PARTIAL" if s == 2024 else ""
        print(fmt_signal(f"Signal {sig_name} [{s}{label}]", sub["f5_grade"].tolist()))
    pooled = ds[ds["p_under_full"] > thresh]
    print(fmt_signal(f"Signal {sig_name} [pooled]", pooled["f5_grade"].tolist()))

# 5D — CSW quartile analysis
print("\n  5D — CSW quartile analysis (Signal B, suppressing pitcher)")
sig_b_csw = ds[(ds["p_under_full"] > 0.57) & ds["suppressing_csw_final"].notna()].copy()
if len(sig_b_csw) > 0:
    # Use train-defined quartile cuts
    q25 = 2 * CSW_Q50 - CSW_Q75  # approximate Q25 from Q50 and Q75
    cuts = [0, q25, CSW_Q50, CSW_Q75, 100]
    labels = ["Q1 (low)", "Q2", "Q3", f"Q4 (≥{CSW_Q75:.1f})"]
    sig_b_csw["csw_q"] = pd.cut(sig_b_csw["suppressing_csw_final"], bins=cuts, labels=labels, include_lowest=True)
    for q in labels:
        sub = sig_b_csw[sig_b_csw["csw_q"] == q]
        print(fmt_signal(f"  {q}", sub["f5_grade"].tolist()))

# 5E — Line-band analysis
print("\n  5E — Line-band analysis (Signal B)")
sig_b_all_bk = ds[ds["p_under_full"] > 0.57]
for band_name, lo, hi in [("≤4.0", 0, 4.0), ("4.5", 4.5, 4.5), ("≥5.0", 5.0, 99)]:
    if lo == hi:
        sub_sig = sig_b_all_bk[sig_b_all_bk["f5_line"] == lo]
        sub_all = ds[ds["f5_line"] == lo]
    else:
        sub_sig = sig_b_all_bk[(sig_b_all_bk["f5_line"] >= lo) & (sig_b_all_bk["f5_line"] <= hi)]
        sub_all = ds[(ds["f5_line"] >= lo) & (ds["f5_line"] <= hi)]
    # Unsignaled baseline under rate
    unsig = sub_all[sub_all["p_under_full"] <= 0.57]
    unsig_under = (unsig["actual_f5_total"] < unsig["f5_line"]).mean() * 100 if len(unsig) > 0 else 0
    n_sig, w_sig, l_sig, p_sig, wr_sig, roi_sig, _ = compute_roi(sub_sig["f5_grade"].tolist())
    thin = " (THIN)" if n_sig < 40 else ""
    print(f"    f5_line {band_name}: Signal N={n_sig} win%={wr_sig:.1f}% ROI={roi_sig:+.1f}%{thin} | "
          f"Unsignaled under rate={unsig_under:.1f}% (N={len(unsig)})")

# 5F — Permutation sanity check (within-season)
print("\n  5F — Permutation test (Signal B, within-season, 200 shuffles)")
rng = np.random.default_rng(42)
for s in [2024, 2025]:
    sub = ds[ds["season"] == s].copy()
    if len(sub) == 0:
        print(f"    {s}: no data")
        continue
    # Actual ROI
    actual_sig = sub[sub["p_under_full"] > 0.57]
    _, _, _, _, _, actual_roi, _ = compute_roi(actual_sig["f5_grade"].tolist())

    # Permutation
    shuffled_rois = []
    p_under_vals = sub["p_under_full"].values.copy()
    f5_grades = sub["f5_grade"].values
    for _ in range(200):
        perm = rng.permutation(p_under_vals)
        sel = perm > 0.57
        if sel.sum() == 0:
            continue
        selected_grades = f5_grades[sel]
        _, _, _, _, _, s_roi, _ = compute_roi(selected_grades.tolist())
        shuffled_rois.append(s_roi)
    shuf_mean = np.mean(shuffled_rois)
    shuf_std = np.std(shuffled_rois)
    pctile = (np.array(shuffled_rois) < actual_roi).mean() * 100
    label = " (PARTIAL)" if s == 2024 else ""
    flag = "" if pctile >= 90 else " *** BELOW TOP 10%"
    print(f"    {s}{label}: actual ROI={actual_roi:+.1f}%, "
          f"shuffled mean={shuf_mean:+.1f}% std={shuf_std:.1f}%, "
          f"percentile={pctile:.0f}%{flag}")

# 5G — F5 vs full-game outcome relationship
print("\n  5G — F5 vs full-game outcome relationship (Signal B)")
sig_b_g = ds[ds["p_under_full"] > 0.57].copy()
n_total = len(sig_b_g)
both_w = ((sig_b_g["f5_grade"] == "WIN") & (sig_b_g["full_grade"] == "WIN")).sum()
both_l = ((sig_b_g["f5_grade"] == "LOSS") & (sig_b_g["full_grade"] == "LOSS")).sum()
f5w_gl = ((sig_b_g["f5_grade"] == "WIN") & (sig_b_g["full_grade"] == "LOSS")).sum()
f5l_gw = ((sig_b_g["f5_grade"] == "LOSS") & (sig_b_g["full_grade"] == "WIN")).sum()
any_push = n_total - both_w - both_l - f5w_gl - f5l_gw
non_push = both_w + both_l + f5w_gl + f5l_gw

print(f"    Both WIN:       {both_w:4d} ({both_w/n_total*100:5.1f}%)")
print(f"    Both LOSS:      {both_l:4d} ({both_l/n_total*100:5.1f}%)")
print(f"    F5 WIN/G LOSS:  {f5w_gl:4d} ({f5w_gl/n_total*100:5.1f}%)")
print(f"    F5 LOSS/G WIN:  {f5l_gw:4d} ({f5l_gw/n_total*100:5.1f}%)")
print(f"    Any PUSH:       {any_push:4d} ({any_push/n_total*100:5.1f}%)")
if non_push > 0:
    agree = (both_w + both_l) / non_push * 100
    indep = (f5w_gl + f5l_gw) / non_push * 100
    note = ""
    if agree > 80:
        note = " → highly correlated with game under"
    elif agree < 65:
        note = " → genuine diversification"
    else:
        note = " → moderate correlation"
    print(f"    Agreement rate:  {agree:.1f}%{note}")
    print(f"    Independent rate: {indep:.1f}%")


# ─────────────────────────────────────────────
# STEP 6 — ROUNDING ARTIFACT CONTROLS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6 — ROUNDING ARTIFACT CONTROLS")
print("=" * 60)

# Control A — Pricing error (DIAGNOSTIC APPROXIMATE)
print("\n  Control A — Pricing error (DIAGNOSTIC APPROXIMATE)")
print(f"    s3_implied_f5 = (mu_home + mu_away) * {F5_RUN_FRACTION}")
pe_all = ds["pricing_error"]
pe_sig = ds[ds["p_under_full"] > 0.57]["pricing_error"]
print(f"    All games: mean={pe_all.mean():+.3f}, median={pe_all.median():+.3f}, %pos={((pe_all>0).mean()*100):.1f}%")
print(f"    Signal B:  mean={pe_sig.mean():+.3f}, median={pe_sig.median():+.3f}, %pos={((pe_sig>0).mean()*100):.1f}%")

# Control B — Implied probability baseline
print("\n  Control B — Implied probability baseline (bin width=0.25)")
# Bin all games by s3_implied_f5
ds["f5_bin"] = (ds["s3_implied_f5"] / 0.25).round() * 0.25
# Historical under rate per bin (all games)
bin_rates = ds.groupby("f5_bin").apply(
    lambda x: pd.Series({
        "n_all": len(x),
        "under_rate": (x["actual_f5_total"] < x["f5_line"]).mean()
    })
).reset_index()
# For signal B games
sig_b_bins = ds[ds["p_under_full"] > 0.57].copy()
sig_b_bins = sig_b_bins.merge(bin_rates[["f5_bin", "under_rate"]], on="f5_bin", how="left")
implied_baseline = sig_b_bins["under_rate"].mean()
actual_win_rate = (sig_b_bins["f5_grade"] == "WIN").sum() / ((sig_b_bins["f5_grade"] == "WIN").sum() + (sig_b_bins["f5_grade"] == "LOSS").sum())
print(f"    Signal B actual win rate: {actual_win_rate*100:.1f}%")
print(f"    Implied baseline (bin-weighted): {implied_baseline*100:.1f}%")
if actual_win_rate > implied_baseline:
    print(f"    Signal B exceeds baseline by {(actual_win_rate - implied_baseline)*100:+.1f}pp ✓")
else:
    print(f"    Signal B DOES NOT exceed baseline ({(actual_win_rate - implied_baseline)*100:+.1f}pp) ✗")

# Control C — Half-line sensitivity
print("\n  Control C — Half-line sensitivity")
sig_b_hl = ds[ds["p_under_full"] > 0.57].copy()
for desc, mask in [(".0 lines", sig_b_hl["f5_line"] == sig_b_hl["f5_line"].round()),
                    (".5 lines", sig_b_hl["f5_line"] != sig_b_hl["f5_line"].round())]:
    # More robust: check if line ends in .5 vs .0
    pass

# Actually check properly
sig_b_hl["line_type"] = np.where(
    (sig_b_hl["f5_line"] * 2) == (sig_b_hl["f5_line"] * 2).astype(int),
    np.where(sig_b_hl["f5_line"] == sig_b_hl["f5_line"].astype(int), ".0 line", ".5 line"),
    "other"
)
for lt in [".0 line", ".5 line"]:
    sub = sig_b_hl[sig_b_hl["line_type"] == lt]
    print(fmt_signal(f"  {lt}", sub["f5_grade"].tolist()))


# ─────────────────────────────────────────────
# SIDE-BY-SIDE SUMMARY
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("SIDE-BY-SIDE: SIGNAL A vs B vs C")
print("=" * 60)

print(f"\n  {'':20s} | {'A: Game Under':>14s} | {'B: F5 Under':>14s} | {'C: F5 p>0.60':>14s}")
print(f"  {'-'*20} | {'-'*14} | {'-'*14} | {'-'*14}")

sig_a = ds[ds["p_under_full"] > 0.57]
sig_c = ds[ds["p_under_full"] > 0.60]

for label, subset in [("All books", ds), ("Books >= 2", ds[ds["books_count"] >= 2])]:
    a = subset[subset["p_under_full"] > 0.57]
    b = subset[subset["p_under_full"] > 0.57]
    c = subset[subset["p_under_full"] > 0.60]

    na, _, _, _, wra, roia, neta = compute_roi(a["full_grade"].tolist())
    nb, _, _, _, wrb, roib, netb = compute_roi(b["f5_grade"].tolist())
    nc, _, _, _, wrc, roic, netc = compute_roi(c["f5_grade"].tolist())

    print(f"  {label:20s} |                |                |")
    print(f"  {'  N':20s} | {na:14d} | {nb:14d} | {nc:14d}")
    print(f"  {'  Win%':20s} | {wra:13.1f}% | {wrb:13.1f}% | {wrc:13.1f}%")
    print(f"  {'  ROI':20s} | {roia:+13.1f}% | {roib:+13.1f}% | {roic:+13.1f}%")
    print(f"  {'  Net units':20s} | {neta:+13.1f}u | {netb:+13.1f}u | {netc:+13.1f}u")
    print()


# ─────────────────────────────────────────────
# DECISION CRITERIA
# ─────────────────────────────────────────────
print("=" * 60)
print("DECISION CRITERIA")
print("=" * 60)

# Signal B pooled
_, _, _, _, _, roi_b_pooled, _ = compute_roi(ds[ds["p_under_full"] > 0.57]["f5_grade"].tolist())
n_b = len(ds[ds["p_under_full"] > 0.57])

# 2025 standalone
sub_2025 = ds[(ds["p_under_full"] > 0.57) & (ds["season"] == 2025)]
_, _, _, _, _, roi_b_2025, _ = compute_roi(sub_2025["f5_grade"].tolist())

# Season divergence
sub_2024 = ds[(ds["p_under_full"] > 0.57) & (ds["season"] == 2024)]
_, _, _, _, _, roi_b_2024, _ = compute_roi(sub_2024["f5_grade"].tolist())
mixed = abs(roi_b_2024 - roi_b_2025) > 15  # material divergence

# Permutation (already computed above, re-check)
# Re-run for final reporting
perm_pass = True
for s in [2024, 2025]:
    sub = ds[ds["season"] == s]
    if len(sub) == 0:
        perm_pass = False
        continue
    actual_sig = sub[sub["p_under_full"] > 0.57]
    _, _, _, _, _, actual_roi, _ = compute_roi(actual_sig["f5_grade"].tolist())
    p_under_vals = sub["p_under_full"].values.copy()
    f5_grades = sub["f5_grade"].values
    shuffled_rois = []
    rng2 = np.random.default_rng(42)
    for _ in range(200):
        perm = rng2.permutation(p_under_vals)
        sel = perm > 0.57
        if sel.sum() == 0:
            continue
        _, _, _, _, _, s_roi, _ = compute_roi(f5_grades[sel].tolist())
        shuffled_rois.append(s_roi)
    pctile = (np.array(shuffled_rois) < actual_roi).mean() * 100
    if pctile < 90:
        perm_pass = False

# Rounding
rounding_clean = actual_win_rate > implied_baseline

criteria = {
    f"ROI >= 3% pooled ({roi_b_pooled:+.1f}%)": roi_b_pooled >= 3.0,
    f"N >= 200 ({n_b})": n_b >= 200,
    f"2025 standalone ROI positive ({roi_b_2025:+.1f}%)": roi_b_2025 > 0,
    "Permutation top 10% both seasons": perm_pass,
    "Rounding controls clean": rounding_clean,
    f"Not MIXED across seasons": not mixed,
}

all_pass = True
for desc, passed in criteria.items():
    status = "PASS ✓" if passed else "FAIL ✗"
    if not passed:
        all_pass = False
    print(f"  {status}  {desc}")

print(f"\n  Overall: {'CRITERIA MET — ADVANCE' if all_pass else 'NOT MET — DO NOT ADVANCE'}")
print("\n*** F5 RESEARCH COMPLETE ***")
