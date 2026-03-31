#!/usr/bin/env python3
"""
Steps 5-7 — Primary Tests, Decile/Stability, Final Verdict
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

BASE = Path(__file__).resolve().parent
np.random.seed(42)

# ── Load evaluation dataset ──────────────────────────────────────────
df = pd.read_parquet(BASE / "opponent_adjusted_research_dataset.parquet")
df["date"] = pd.to_datetime(df["date"])
df_np = df[~df["is_push"]].copy()

print(f"Dataset: {len(df)} games ({len(df_np)} non-push)")
print(f"2024: {(df.season==2024).sum()}, 2025: {(df.season==2025).sum()}")

def roi_at_110(wins, losses):
    if wins + losses == 0:
        return np.nan
    return (wins * (100/110) - losses) / (wins + losses) * 100


# =====================================================================
# STEP 5 — RAW VS ADJUSTED COMPARISON
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5A — UNIVARIATE TESTS")
print("=" * 60)

# Test pairs
pairs = [
    ("combined_raw_k_rate_last3", "combined_adj_k_rate_last3", "K_rate_last3"),
    ("combined_raw_k_rate_last5", "combined_adj_k_rate_last5", "K_rate_last5"),
    ("combined_raw_bb_rate_last3", "combined_adj_bb_rate_last3", "BB_rate_last3"),
    ("combined_raw_bb_rate_last5", "combined_adj_bb_rate_last5", "BB_rate_last5"),
    ("combined_raw_strike_pct_last3", "combined_adj_strike_pct_last3", "StrikePct_last3"),
    ("combined_raw_strike_pct_last5", "combined_adj_strike_pct_last5", "StrikePct_last5"),
]

univariate_results = []

for raw_col, adj_col, label in pairs:
    print(f"\n--- {label} ---")
    for col, tag in [(raw_col, "RAW"), (adj_col, "ADJ")]:
        # OLS vs market_residual
        valid = df[col].notna() & df["market_residual"].notna()
        X = sm.add_constant(df.loc[valid, col])
        y = df.loc[valid, "market_residual"]
        model = sm.OLS(y, X).fit()
        coef = model.params.iloc[1]
        tstat = model.tvalues.iloc[1]
        pval = model.pvalues.iloc[1]
        r2 = model.rsquared
        n = valid.sum()

        # OLS vs actual_total
        y_total = df.loc[valid, "actual_total"]
        model_total = sm.OLS(y_total, X).fit()
        coef_total = model_total.params.iloc[1]
        p_total = model_total.pvalues.iloc[1]
        r2_total = model_total.rsquared

        # Logistic vs under outcome (non-push only)
        valid_np = df_np[col].notna() & df_np["actual_result_under"].notna()
        try:
            X_np = sm.add_constant(df_np.loc[valid_np, col])
            y_np = df_np.loc[valid_np, "actual_result_under"]
            logit = sm.Logit(y_np, X_np).fit(disp=0)
            logit_coef = logit.params.iloc[1]
            logit_z = logit.tvalues.iloc[1]
            logit_p = logit.pvalues.iloc[1]
        except:
            logit_coef = logit_z = logit_p = np.nan

        univariate_results.append({
            "family": label, "version": tag, "N": n,
            "resid_coef": coef, "resid_t": tstat, "resid_p": pval, "resid_r2": r2,
            "total_coef": coef_total, "total_p": p_total, "total_r2": r2_total,
            "under_coef": logit_coef, "under_z": logit_z, "under_p": logit_p,
        })

        print(f"  {tag}: N={n}, resid_coef={coef:+.5f} (p={pval:.4f}), "
              f"total_coef={coef_total:+.3f} (p={p_total:.4f}), "
              f"under_logit_z={logit_z:+.3f} (p={logit_p:.4f})")

# Step 5B — Paired comparison
print("\n" + "=" * 60)
print("STEP 5B — PAIRED COMPARISON")
print("=" * 60)

paired_results = []
for raw_col, adj_col, label in pairs:
    raw_res = [r for r in univariate_results if r["family"] == label and r["version"] == "RAW"][0]
    adj_res = [r for r in univariate_results if r["family"] == label and r["version"] == "ADJ"][0]

    # Compare significance
    sig_winner = "ADJ" if adj_res["resid_p"] < raw_res["resid_p"] else "RAW"
    # Compare effect size
    eff_winner = "ADJ" if abs(adj_res["resid_coef"]) > abs(raw_res["resid_coef"]) else "RAW"

    # Season stability — run 2024 and 2025 separately
    stability = {}
    for yr in [2024, 2025]:
        yr_df = df[df["season"] == yr]
        for col, tag in [(raw_col, "RAW"), (adj_col, "ADJ")]:
            valid = yr_df[col].notna() & yr_df["market_residual"].notna()
            if valid.sum() < 50:
                stability[(yr, tag)] = {"coef": np.nan, "p": np.nan}
                continue
            X = sm.add_constant(yr_df.loc[valid, col])
            y = yr_df.loc[valid, "market_residual"]
            model = sm.OLS(y, X).fit()
            stability[(yr, tag)] = {"coef": model.params.iloc[1], "p": model.pvalues.iloc[1]}

    raw_stable = (stability.get((2024, "RAW"), {}).get("coef", 0) *
                  stability.get((2025, "RAW"), {}).get("coef", 0) > 0)
    adj_stable = (stability.get((2024, "ADJ"), {}).get("coef", 0) *
                  stability.get((2025, "ADJ"), {}).get("coef", 0) > 0)
    stab_winner = "ADJ" if adj_stable and not raw_stable else "RAW" if raw_stable and not adj_stable else "TIE"

    # Decile separation — top vs bottom quintile spread
    for col, tag in [(raw_col, "RAW"), (adj_col, "ADJ")]:
        valid = df[col].notna() & df["market_residual"].notna()
        vals = df.loc[valid]
        p20 = vals[col].quantile(0.2)
        p80 = vals[col].quantile(0.8)
        bot_err = vals.loc[vals[col] <= p20, "market_residual"].mean()
        top_err = vals.loc[vals[col] > p80, "market_residual"].mean()
        spread = top_err - bot_err
        if tag == "RAW":
            raw_spread = spread
        else:
            adj_spread = spread

    spread_winner = "ADJ" if abs(adj_spread) > abs(raw_spread) else "RAW"

    paired_results.append({
        "family": label,
        "sig_winner": sig_winner,
        "eff_winner": eff_winner,
        "stab_winner": stab_winner,
        "spread_winner": spread_winner,
        "raw_p": raw_res["resid_p"],
        "adj_p": adj_res["resid_p"],
        "raw_coef": raw_res["resid_coef"],
        "adj_coef": adj_res["resid_coef"],
        "raw_spread": raw_spread,
        "adj_spread": adj_spread,
        "stability": stability,
    })

    overall = sum([sig_winner == "ADJ", eff_winner == "ADJ",
                   stab_winner == "ADJ", spread_winner == "ADJ"])
    print(f"  {label}: sig={sig_winner}, effect={eff_winner}, "
          f"stability={stab_winner}, spread={spread_winner} → ADJ wins {overall}/4")

# Step 5C — Combined models
print("\n" + "=" * 60)
print("STEP 5C — COMBINED MODELS")
print("=" * 60)

combined_results = []
test_pairs = [
    ("combined_raw_k_rate_last3", "combined_adj_k_rate_last3", "K_rate_last3"),
    ("combined_raw_k_rate_last5", "combined_adj_k_rate_last5", "K_rate_last5"),
    ("combined_raw_strike_pct_last3", "combined_adj_strike_pct_last3", "StrikePct_last3"),
    ("combined_raw_strike_pct_last5", "combined_adj_strike_pct_last5", "StrikePct_last5"),
]

for raw_col, adj_col, label in test_pairs:
    valid = df[raw_col].notna() & df[adj_col].notna() & df["market_residual"].notna()
    subset = df[valid].copy()
    y = subset["market_residual"]

    # Model 1: raw only
    X1 = sm.add_constant(subset[raw_col])
    m1 = sm.OLS(y, X1).fit()

    # Model 2: adj only
    X2 = sm.add_constant(subset[adj_col])
    m2 = sm.OLS(y, X2).fit()

    # Model 3: both
    X3 = sm.add_constant(subset[[raw_col, adj_col]])
    m3 = sm.OLS(y, X3).fit()

    combined_results.append({
        "family": label,
        "raw_r2": m1.rsquared, "raw_aic": m1.aic,
        "adj_r2": m2.rsquared, "adj_aic": m2.aic,
        "both_r2": m3.rsquared, "both_aic": m3.aic,
        "raw_p_in_combined": m3.pvalues[raw_col],
        "adj_p_in_combined": m3.pvalues[adj_col],
    })

    print(f"\n  {label}:")
    print(f"    Raw only:  R²={m1.rsquared:.6f}, AIC={m1.aic:.1f}")
    print(f"    Adj only:  R²={m2.rsquared:.6f}, AIC={m2.aic:.1f}")
    print(f"    Both:      R²={m3.rsquared:.6f}, AIC={m3.aic:.1f}")
    print(f"    In combined: raw_p={m3.pvalues[raw_col]:.4f}, adj_p={m3.pvalues[adj_col]:.4f}")


# =====================================================================
# STEP 6 — DECILE AND STABILITY TESTS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — DECILE AND STABILITY TESTS")
print("=" * 60)

# Find the strongest adjusted metric from Step 5
# Use the one with lowest p-value
best_adj = min(
    [r for r in univariate_results if r["version"] == "ADJ"],
    key=lambda x: x["resid_p"]
)
best_family = best_adj["family"]

# Map back to column name
family_map = {
    "K_rate_last3": "combined_adj_k_rate_last3",
    "K_rate_last5": "combined_adj_k_rate_last5",
    "BB_rate_last3": "combined_adj_bb_rate_last3",
    "BB_rate_last5": "combined_adj_bb_rate_last5",
    "StrikePct_last3": "combined_adj_strike_pct_last3",
    "StrikePct_last5": "combined_adj_strike_pct_last5",
}
best_col = family_map[best_family]
print(f"\nStrongest adjusted metric: {best_family} (p={best_adj['resid_p']:.4f})")

# Also test best raw for comparison
best_raw = min(
    [r for r in univariate_results if r["version"] == "RAW"],
    key=lambda x: x["resid_p"]
)
best_raw_family = best_raw["family"]
raw_family_map = {k.replace("adj", "raw"): v.replace("adj", "raw") for k, v in family_map.items()}
raw_family_map = {
    "K_rate_last3": "combined_raw_k_rate_last3",
    "K_rate_last5": "combined_raw_k_rate_last5",
    "BB_rate_last3": "combined_raw_bb_rate_last3",
    "BB_rate_last5": "combined_raw_bb_rate_last5",
    "StrikePct_last3": "combined_raw_strike_pct_last3",
    "StrikePct_last5": "combined_raw_strike_pct_last5",
}
best_raw_col = raw_family_map[best_raw_family]

for test_col, test_label in [(best_col, f"ADJ {best_family}"), (best_raw_col, f"RAW {best_raw_family}")]:
    print(f"\n--- {test_label}: {test_col} ---")

    # 6.1 Decile structure
    valid = df[test_col].notna() & df["market_residual"].notna()
    valid_np = df_np[test_col].notna() & df_np["actual_result_under"].notna()
    subset = df[valid].copy()
    subset_np = df_np[valid_np].copy()

    subset["decile"] = pd.qcut(subset[test_col], 10, labels=False, duplicates="drop")
    subset_np["decile"] = pd.qcut(subset_np[test_col], 10, labels=False, duplicates="drop")

    print(f"\n  Decile structure:")
    print(f"  {'Dec':>4} {'N':>5} {'Mean':>8} {'MktResid':>9} {'Under%':>7} {'ROI':>7}")
    for dec in sorted(subset["decile"].unique()):
        d_all = subset[subset["decile"] == dec]
        d_np = subset_np[subset_np["decile"] == dec]
        n = len(d_np)
        mean_val = d_all[test_col].mean()
        mean_resid = d_all["market_residual"].mean()
        under_rate = d_np["actual_result_under"].mean() if n > 0 else np.nan
        w = d_np["actual_result_under"].sum()
        roi = roi_at_110(w, n - w) if n > 0 else np.nan
        print(f"  {dec:>4d} {n:>5d} {mean_val:>8.4f} {mean_resid:>+9.4f} {under_rate:>7.3f} {roi:>+7.1f}%")

    # 6.2 Season stability
    print(f"\n  Season stability:")
    for yr in [2024, 2025]:
        yr_df = df[df["season"] == yr]
        valid_yr = yr_df[test_col].notna() & yr_df["market_residual"].notna()
        if valid_yr.sum() < 50:
            print(f"    {yr}: insufficient data")
            continue
        X = sm.add_constant(yr_df.loc[valid_yr, test_col])
        y = yr_df.loc[valid_yr, "market_residual"]
        model = sm.OLS(y, X).fit()
        print(f"    {yr}: coef={model.params.iloc[1]:+.5f}, p={model.pvalues.iloc[1]:.4f}, "
              f"sign={'POS' if model.params.iloc[1] > 0 else 'NEG'}")

    # 6.3 Market independence
    corr_valid = df[test_col].notna() & df["closing_total"].notna()
    r, p_corr = stats.pearsonr(df.loc[corr_valid, test_col], df.loc[corr_valid, "closing_total"])
    print(f"\n  Market correlation: r={r:.4f}, p={p_corr:.4f}")


# =====================================================================
# STEP 7 — FINAL VERDICT & REPORT
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — FINAL VERDICT")
print("=" * 60)

# Build report
report = []
report.append("# Opponent-Adjusted Pitcher Form — Research Report")
report.append("")
report.append("## Overview")
report.append("Tested whether opponent-adjusted recent pitcher form predicts MLB totals /")
report.append("market residuals better than raw recent pitcher form.")
report.append("")
report.append(f"Evaluation window: 2024 + 2025 ({len(df)} games, {len(df_np)} non-push)")
report.append("")

report.append("## Source Data")
report.append("- Game table: sim/data/game_table.parquet (9,715 games)")
report.append("- Boxscores: sim/data/cache/boxscores/ (9,715 JSON files)")
report.append("- Statcast: research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet")
report.append("- Closing lines: sim/data/bet_results.parquet (4,855 games)")
report.append("")

report.append("## Methodology")
report.append("```")
report.append("adj_metric_start = raw_metric_start - (opponent_rolling_20g - league_avg)")
report.append("```")
report.append("- Opponent rolling: team K/AB, BB/AB over last 20 games (excluding current)")
report.append("- Rolling form: last 3 and last 5 prior starts per pitcher")
report.append("- Combined: average of home SP + away SP rolling form")
report.append("- Strike% used as CSW proxy (strikes/pitches from boxscores)")
report.append("")

report.append("## Step 5A — Univariate Results")
report.append("")
report.append("| Family | Version | N | Resid Coef | Resid p | Total Coef | Total p | Under z | Under p |")
report.append("|--------|---------|---|-----------|---------|-----------|---------|---------|---------|")
for r in univariate_results:
    report.append(f"| {r['family']} | {r['version']} | {r['N']} | "
                  f"{r['resid_coef']:+.5f} | {r['resid_p']:.4f} | "
                  f"{r['total_coef']:+.3f} | {r['total_p']:.4f} | "
                  f"{r['under_z']:+.3f} | {r['under_p']:.4f} |")
report.append("")

report.append("## Step 5B — Paired Comparison")
report.append("")
report.append("| Family | Significance | Effect Size | Stability | Decile Spread | ADJ Wins |")
report.append("|--------|-------------|-------------|-----------|---------------|----------|")
for r in paired_results:
    wins = sum([r["sig_winner"] == "ADJ", r["eff_winner"] == "ADJ",
                r["stab_winner"] == "ADJ", r["spread_winner"] == "ADJ"])
    report.append(f"| {r['family']} | {r['sig_winner']} | {r['eff_winner']} | "
                  f"{r['stab_winner']} | {r['spread_winner']} | {wins}/4 |")

report.append("")
report.append("### Year-by-Year Stability Detail")
report.append("")
report.append("| Family | Version | 2024 Coef | 2024 p | 2025 Coef | 2025 p | Stable? |")
report.append("|--------|---------|-----------|--------|-----------|--------|---------|")
for r in paired_results:
    stab = r["stability"]
    for tag in ["RAW", "ADJ"]:
        c24 = stab.get((2024, tag), {}).get("coef", np.nan)
        p24 = stab.get((2024, tag), {}).get("p", np.nan)
        c25 = stab.get((2025, tag), {}).get("coef", np.nan)
        p25 = stab.get((2025, tag), {}).get("p", np.nan)
        stable = "YES" if (not np.isnan(c24) and not np.isnan(c25) and c24 * c25 > 0) else "NO"
        report.append(f"| {r['family']} | {tag} | {c24:+.5f} | {p24:.4f} | "
                      f"{c25:+.5f} | {p25:.4f} | {stable} |")
report.append("")

report.append("## Step 5C — Combined Models")
report.append("")
report.append("| Family | Raw R² | Adj R² | Both R² | Raw p (combined) | Adj p (combined) |")
report.append("|--------|--------|--------|---------|-----------------|-----------------|")
for r in combined_results:
    report.append(f"| {r['family']} | {r['raw_r2']:.6f} | {r['adj_r2']:.6f} | "
                  f"{r['both_r2']:.6f} | {r['raw_p_in_combined']:.4f} | {r['adj_p_in_combined']:.4f} |")
report.append("")

report.append("## Step 6 — Strongest Metric Decile Structure")
report.append("")
report.append(f"Best adjusted metric: **{best_family}** ({best_col})")
report.append(f"Best raw metric: **{best_raw_family}** ({best_raw_col})")
report.append("")

# Re-run decile for report
for test_col, test_label in [(best_col, f"ADJ {best_family}"), (best_raw_col, f"RAW {best_raw_family}")]:
    valid = df[test_col].notna() & df["market_residual"].notna()
    valid_np = df_np[test_col].notna() & df_np["actual_result_under"].notna()
    subset = df[valid].copy()
    subset_np = df_np[valid_np].copy()
    subset["decile"] = pd.qcut(subset[test_col], 10, labels=False, duplicates="drop")
    subset_np["decile"] = pd.qcut(subset_np[test_col], 10, labels=False, duplicates="drop")

    report.append(f"### {test_label}")
    report.append("")
    report.append("| Decile | N | Mean | Mkt Resid | Under% | ROI @-110 |")
    report.append("|--------|---|------|----------|--------|-----------|")
    for dec in sorted(subset["decile"].unique()):
        d_all = subset[subset["decile"] == dec]
        d_np = subset_np[subset_np["decile"] == dec]
        n = len(d_np)
        mean_val = d_all[test_col].mean()
        mean_resid = d_all["market_residual"].mean()
        under_rate = d_np["actual_result_under"].mean() if n > 0 else np.nan
        w = d_np["actual_result_under"].sum()
        roi = roi_at_110(w, n - w) if n > 0 else np.nan
        report.append(f"| {dec} | {n} | {mean_val:.4f} | {mean_resid:+.4f} | "
                      f"{under_rate:.3f} | {roi:+.1f}% |")
    report.append("")

    # Market independence
    corr_valid = df[test_col].notna() & df["closing_total"].notna()
    r_corr, p_corr = stats.pearsonr(df.loc[corr_valid, test_col], df.loc[corr_valid, "closing_total"])
    report.append(f"Market correlation: r={r_corr:.4f}, p={p_corr:.4f}")
    report.append("")

# ── Final answers ────────────────────────────────────────────────────
report.append("## Step 7 — Final Verdict")
report.append("")

# Q1: Does adjusted beat raw?
adj_wins_total = sum(1 for r in paired_results
                     if sum([r["sig_winner"] == "ADJ", r["eff_winner"] == "ADJ",
                            r["stab_winner"] == "ADJ", r["spread_winner"] == "ADJ"]) >= 3)
adj_ties = sum(1 for r in paired_results
               if sum([r["sig_winner"] == "ADJ", r["eff_winner"] == "ADJ",
                      r["stab_winner"] == "ADJ", r["spread_winner"] == "ADJ"]) == 2)

report.append("### Q1: Does opponent-adjusted recent form beat raw recent form?")
report.append("")
report.append(f"- Families where ADJ wins ≥3/4 criteria: {adj_wins_total}/{len(paired_results)}")
report.append(f"- Families where ADJ ties (2/4): {adj_ties}/{len(paired_results)}")

# Check combined model results
adj_adds_value = sum(1 for r in combined_results if r["adj_p_in_combined"] < 0.10)
report.append(f"- Combined models where adj adds sig. value (p<0.10): {adj_adds_value}/{len(combined_results)}")
report.append("")

# Determine overall answer
if adj_wins_total >= 4:
    q1_answer = "YES — adjusted form consistently outperforms raw form"
elif adj_wins_total >= 2:
    q1_answer = "MIXED — adjusted form improves some families but not all"
elif adj_adds_value >= 2:
    q1_answer = "MARGINAL — adjustment adds some value in combined models"
else:
    q1_answer = "NO — adjustment does not reliably outperform raw form"
report.append(f"**Answer: {q1_answer}**")
report.append("")

# Q2: Strongest metric family
report.append("### Q2: Strongest metric family")
report.append("")
best_p = {r["family"]: r["resid_p"] for r in univariate_results if r["version"] == "ADJ"}
for family, p in sorted(best_p.items(), key=lambda x: x[1]):
    report.append(f"- {family}: p={p:.4f}")
report.append("")

# Q3: Does adjusted add value beyond raw?
report.append("### Q3: Does adjusted metric add value beyond raw metric?")
report.append("")
for r in combined_results:
    incremental = "YES" if r["adj_p_in_combined"] < 0.10 else "NO"
    report.append(f"- {r['family']}: adj p in combined = {r['adj_p_in_combined']:.4f} → {incremental}")
report.append("")

# Q4: Strength classification
report.append("### Q4: Classification by metric family")
report.append("")
report.append("| Family | Verdict | Reason |")
report.append("|--------|---------|--------|")

for r in paired_results:
    adj_p = [x for x in univariate_results if x["family"] == r["family"] and x["version"] == "ADJ"][0]["resid_p"]
    raw_p = [x for x in univariate_results if x["family"] == r["family"] and x["version"] == "RAW"][0]["resid_p"]
    wins = sum([r["sig_winner"] == "ADJ", r["eff_winner"] == "ADJ",
                r["stab_winner"] == "ADJ", r["spread_winner"] == "ADJ"])

    # Check combined model increment
    combined_match = [c for c in combined_results if c["family"] == r["family"]]
    adj_incremental = combined_match[0]["adj_p_in_combined"] < 0.10 if combined_match else False

    if adj_p < 0.05 and wins >= 3 and adj_incremental:
        verdict = "**ADVANCE**"
        reason = f"ADJ p={adj_p:.4f}, wins {wins}/4, incremental in combined"
    elif adj_p < 0.10 and wins >= 2:
        verdict = "**INVESTIGATE**"
        reason = f"ADJ p={adj_p:.4f}, wins {wins}/4, needs more data"
    elif adj_p < raw_p and wins >= 2:
        verdict = "**INVESTIGATE**"
        reason = f"ADJ outperforms RAW (p={adj_p:.4f} vs {raw_p:.4f})"
    else:
        verdict = "**SHELVE**"
        reason = f"No consistent improvement (ADJ p={adj_p:.4f}, wins {wins}/4)"
    report.append(f"| {r['family']} | {verdict} | {reason} |")

report.append("")
report.append("### Overall Recommendation")
report.append("")

# Count verdicts
n_advance = sum(1 for line in report if "**ADVANCE**" in line and "|" in line)
n_investigate = sum(1 for line in report if "**INVESTIGATE**" in line and "|" in line)
n_shelve = sum(1 for line in report if "**SHELVE**" in line and "|" in line)

if n_advance >= 2:
    overall = "Opponent-adjusted form is a genuine improvement. Integrate into scanner catalog."
elif n_advance >= 1 or n_investigate >= 3:
    overall = "Some evidence of improvement. Worth shadow monitoring with strongest adjusted features."
elif n_investigate >= 1:
    overall = "Marginal evidence. Not worth current integration but revisit with more data."
else:
    overall = "No evidence of improvement. Adjustment adds complexity without benefit. Shelve entire concept."

report.append(overall)
report.append("")

# Save report
out_path = BASE / "opponent_adjusted_pitcher_form_report.md"
with open(out_path, "w") as f:
    f.write("\n".join(report) + "\n")
print(f"\nSaved: {out_path}")
print("\nDone.")
