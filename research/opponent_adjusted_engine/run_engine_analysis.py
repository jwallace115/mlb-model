#!/usr/bin/env python3
"""
Steps 5–9: Model build, comparisons, feature families, interaction readiness, verdict.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
np.random.seed(42)

df = pd.read_parquet(BASE / "game_level_engine_dataset.parquet")
df["date"] = pd.to_datetime(df["date"])
df_np = df[~df["is_push"]].copy()
print(f"Dataset: {len(df)} games ({len(df_np)} non-push)")

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# =====================================================================
# STEP 5 — BUILD THREE ENGINE MODELS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — ENGINE MODELS")
print("=" * 60)

# Feature sets
RAW_FEATS = [
    "combined_raw_k_rate_last3", "combined_raw_k_rate_last5",
    "combined_raw_bb_rate_last3", "combined_raw_bb_rate_last5",
    "combined_raw_csw_last3", "combined_raw_csw_last5",
]
ADJ_FEATS = [
    "combined_adj_k_rate_last3", "combined_adj_k_rate_last5",
    "combined_adj_bb_rate_last3", "combined_adj_bb_rate_last5",
    "combined_adj_csw_last3", "combined_adj_csw_last5",
]
COMBINED_FEATS = RAW_FEATS + ADJ_FEATS

# Also test hard-hit/barrel variants
RAW_EXTENDED = RAW_FEATS + [
    "combined_raw_hard_hit_last3", "combined_raw_hard_hit_last5",
    "combined_raw_barrel_last3", "combined_raw_barrel_last5",
]
ADJ_EXTENDED = ADJ_FEATS + [
    "combined_adj_hard_hit_last3", "combined_adj_hard_hit_last5",
    "combined_adj_barrel_last3", "combined_adj_barrel_last5",
]
COMBINED_EXTENDED = RAW_EXTENDED + ADJ_EXTENDED

models_summary = []

def run_model(name, features, target, df_in, model_type="ols"):
    """Run model and return summary dict."""
    valid = df_in[features + [target]].dropna()
    if len(valid) < 100:
        return {"name": name, "N": len(valid), "r2": np.nan, "mae": np.nan}

    X = valid[features].values
    y = valid[target].values

    if model_type == "ols":
        X_const = sm.add_constant(X)
        model = sm.OLS(y, X_const).fit()
        preds = model.predict(X_const)
        return {
            "name": name, "N": len(valid), "r2": model.rsquared,
            "adj_r2": model.rsquared_adj,
            "mae": mean_absolute_error(y, preds),
            "aic": model.aic,
            "sig_features": sum(model.pvalues[1:] < 0.10),
            "total_features": len(features),
        }
    elif model_type == "ridge":
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X)
        model = Ridge(alpha=10.0)
        model.fit(X_s, y)
        preds = model.predict(X_s)
        r2 = 1 - np.sum((y - preds)**2) / np.sum((y - y.mean())**2)
        return {
            "name": name, "N": len(valid), "r2": r2,
            "mae": mean_absolute_error(y, preds),
        }


# Target 1: market_residual (continuous)
print("\n--- Target: market_residual ---")
for name, feats in [("A_RAW", RAW_FEATS), ("B_ADJ", ADJ_FEATS), ("C_COMBINED", COMBINED_FEATS),
                     ("A_RAW_ext", RAW_EXTENDED), ("B_ADJ_ext", ADJ_EXTENDED), ("C_COMB_ext", COMBINED_EXTENDED)]:
    res = run_model(name, feats, "market_residual", df)
    models_summary.append({**res, "target": "market_residual"})
    print(f"  {name}: N={res['N']}, R²={res['r2']:.6f}, adj_R²={res.get('adj_r2', 0):.6f}, "
          f"sig_feats={res.get('sig_features', '?')}/{res.get('total_features', '?')}")

# Target 2: actual_result_under (binary — use OLS for comparability, then logistic for confirmation)
print("\n--- Target: actual_result_under ---")
for name, feats in [("A_RAW", RAW_FEATS), ("B_ADJ", ADJ_FEATS), ("C_COMBINED", COMBINED_FEATS)]:
    res = run_model(name, feats, "actual_result_under", df_np)
    models_summary.append({**res, "target": "actual_result_under"})
    print(f"  {name}: N={res['N']}, R²={res['r2']:.6f}, sig_feats={res.get('sig_features', '?')}")

# Target 3: full_game_total_runs
print("\n--- Target: actual_total ---")
for name, feats in [("A_RAW", RAW_FEATS), ("B_ADJ", ADJ_FEATS), ("C_COMBINED", COMBINED_FEATS)]:
    res = run_model(name, feats, "actual_total", df)
    models_summary.append({**res, "target": "actual_total"})
    print(f"  {name}: N={res['N']}, R²={res['r2']:.6f}, MAE={res['mae']:.3f}")

# =====================================================================
# STEP 6 — MODEL COMPARISONS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — MODEL COMPARISONS")
print("=" * 60)

# 6.1 — Season stability
print("\n--- 6.1 Season Stability (market_residual) ---")
stability_rows = []
for name, feats in [("A_RAW", RAW_FEATS), ("B_ADJ", ADJ_FEATS), ("C_COMBINED", COMBINED_FEATS)]:
    for yr in [2024, 2025]:
        yr_df = df[df["season"] == yr]
        res = run_model(f"{name}_{yr}", feats, "market_residual", yr_df)
        stability_rows.append({"model": name, "year": yr, **res})
        print(f"  {name} {yr}: R²={res['r2']:.6f}, sig_feats={res.get('sig_features', '?')}")

# 6.2 — Market independence
print("\n--- 6.2 Market Independence ---")
market_corr_rows = []
for name, feats in [("A_RAW", RAW_FEATS), ("B_ADJ", ADJ_FEATS)]:
    valid = df[feats + ["closing_total"]].dropna()
    X = valid[feats].values
    y_resid = df.loc[valid.index, "market_residual"].values

    # Build model score
    X_const = sm.add_constant(X)
    model = sm.OLS(y_resid, X_const).fit()
    score = model.predict(X_const)

    r_market, p_market = stats.pearsonr(score, valid["closing_total"].values)
    market_corr_rows.append({"model": name, "score_market_corr": r_market, "p": p_market})
    print(f"  {name} score vs closing_total: r={r_market:.4f}, p={p_market:.4f}")

    # Also check individual feature correlations with closing_total
    for feat in feats:
        r_f, _ = stats.pearsonr(valid[feat], valid["closing_total"])
        if abs(r_f) > 0.20:
            print(f"    {feat} vs closing_total: r={r_f:.4f}")

# 6.3 — Decile structure for each engine
print("\n--- 6.3 Decile Structure ---")
decile_tables = {}
for name, feats in [("A_RAW", RAW_FEATS), ("B_ADJ", ADJ_FEATS), ("C_COMBINED", COMBINED_FEATS)]:
    valid = df[feats + ["market_residual", "closing_total"]].dropna()
    valid_np_idx = valid.index.intersection(df_np.index)
    valid_np = df_np.loc[valid_np_idx].copy()

    # Build model score
    X = sm.add_constant(valid[feats])
    y = valid["market_residual"]
    model = sm.OLS(y, X).fit()
    valid["score"] = model.predict(X)
    valid_np["score"] = valid.loc[valid_np_idx, "score"]

    # Decile on score
    valid["decile"] = pd.qcut(valid["score"], 10, labels=False, duplicates="drop")
    valid_np["decile"] = pd.qcut(valid_np["score"], 10, labels=False, duplicates="drop")

    print(f"\n  {name} decile structure:")
    print(f"  {'Dec':>4} {'N':>5} {'Score':>8} {'Resid':>8} {'Under%':>7} {'ROI':>7}")
    rows = []
    for dec in sorted(valid["decile"].unique()):
        d = valid[valid["decile"] == dec]
        d_np = valid_np[valid_np["decile"] == dec]
        n = len(d_np)
        mean_score = d["score"].mean()
        mean_resid = d["market_residual"].mean()
        under_rate = d_np["actual_result_under"].mean() if n > 0 else np.nan
        w = d_np["actual_result_under"].sum() if n > 0 else 0
        roi = roi_110(w, n - w) if n > 0 else np.nan
        rows.append({"decile": dec, "N": n, "mean_score": mean_score,
                      "mean_resid": mean_resid, "under_rate": under_rate, "roi": roi})
        print(f"  {dec:>4d} {n:>5d} {mean_score:>8.4f} {mean_resid:>+8.4f} {under_rate:>7.3f} {roi:>+7.1f}%")

    decile_tables[name] = rows

    # Tail spread: D9 - D0
    d0 = [r for r in rows if r["decile"] == 0][0]
    d9 = [r for r in rows if r["decile"] == max(r["decile"] for r in rows)][0]
    spread = d9["under_rate"] - d0["under_rate"]
    roi_spread = d9["roi"] - d0["roi"]
    print(f"  Tail spread: under_rate D9-D0={spread:+.3f}, ROI D9-D0={roi_spread:+.1f}pp")


# =====================================================================
# STEP 7 — FEATURE FAMILY COMPARISON
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — FEATURE FAMILY COMPARISON")
print("=" * 60)

families = [
    ("K_rate_last3", "combined_raw_k_rate_last3", "combined_adj_k_rate_last3"),
    ("K_rate_last5", "combined_raw_k_rate_last5", "combined_adj_k_rate_last5"),
    ("BB_rate_last3", "combined_raw_bb_rate_last3", "combined_adj_bb_rate_last3"),
    ("BB_rate_last5", "combined_raw_bb_rate_last5", "combined_adj_bb_rate_last5"),
    ("CSW_last3", "combined_raw_csw_last3", "combined_adj_csw_last3"),
    ("CSW_last5", "combined_raw_csw_last5", "combined_adj_csw_last5"),
    ("HardHit_last3", "combined_raw_hard_hit_last3", "combined_adj_hard_hit_last3"),
    ("HardHit_last5", "combined_raw_hard_hit_last5", "combined_adj_hard_hit_last5"),
    ("Barrel_last3", "combined_raw_barrel_last3", "combined_adj_barrel_last3"),
    ("Barrel_last5", "combined_raw_barrel_last5", "combined_adj_barrel_last5"),
]

family_results = []

for fam_name, raw_col, adj_col in families:
    # Univariate OLS vs market_residual
    results = {}
    for col, tag in [(raw_col, "RAW"), (adj_col, "ADJ")]:
        valid = df[[col, "market_residual"]].dropna()
        if len(valid) < 100:
            results[tag] = {"coef": np.nan, "p": np.nan, "r2": np.nan}
            continue
        X = sm.add_constant(valid[col])
        y = valid["market_residual"]
        m = sm.OLS(y, X).fit()
        results[tag] = {"coef": m.params.iloc[1], "p": m.pvalues.iloc[1], "r2": m.rsquared}

    # Combined model: raw + adj together
    valid = df[[raw_col, adj_col, "market_residual"]].dropna()
    if len(valid) > 100:
        X = sm.add_constant(valid[[raw_col, adj_col]])
        y = valid["market_residual"]
        m_both = sm.OLS(y, X).fit()
        raw_p_comb = m_both.pvalues[raw_col]
        adj_p_comb = m_both.pvalues[adj_col]
        r2_both = m_both.rsquared
    else:
        raw_p_comb = adj_p_comb = r2_both = np.nan

    # Season stability
    stable_raw = True
    stable_adj = True
    yr_detail = {}
    for yr in [2024, 2025]:
        yr_df = df[df["season"] == yr]
        for col, tag in [(raw_col, "RAW"), (adj_col, "ADJ")]:
            v = yr_df[[col, "market_residual"]].dropna()
            if len(v) < 50:
                yr_detail[(yr, tag)] = {"coef": np.nan, "p": np.nan}
                continue
            X = sm.add_constant(v[col])
            y = v["market_residual"]
            m = sm.OLS(y, X).fit()
            yr_detail[(yr, tag)] = {"coef": m.params.iloc[1], "p": m.pvalues.iloc[1]}

    c24r = yr_detail.get((2024, "RAW"), {}).get("coef", 0)
    c25r = yr_detail.get((2025, "RAW"), {}).get("coef", 0)
    c24a = yr_detail.get((2024, "ADJ"), {}).get("coef", 0)
    c25a = yr_detail.get((2025, "ADJ"), {}).get("coef", 0)
    stable_raw = (c24r * c25r > 0) if (c24r != 0 and c25r != 0) else False
    stable_adj = (c24a * c25a > 0) if (c24a != 0 and c25a != 0) else False

    # Quintile spread (tail vs broad)
    for col, tag in [(raw_col, "RAW"), (adj_col, "ADJ")]:
        v = df[[col, "market_residual"]].dropna()
        if len(v) < 100:
            continue
        p20 = v[col].quantile(0.2)
        p80 = v[col].quantile(0.8)
        bot = v.loc[v[col] <= p20, "market_residual"].mean()
        top = v.loc[v[col] > p80, "market_residual"].mean()
        if tag == "RAW":
            raw_spread = top - bot
        else:
            adj_spread = top - bot

    # Determine winners
    adj_beats_raw = results["ADJ"]["p"] < results["RAW"]["p"]
    adj_adds_value = adj_p_comb < 0.10 if not np.isnan(adj_p_comb) else False
    broad = abs(adj_spread) > 0.03 if not np.isnan(locals().get("adj_spread", np.nan)) else False

    family_results.append({
        "family": fam_name,
        "raw_coef": results["RAW"]["coef"], "raw_p": results["RAW"]["p"],
        "adj_coef": results["ADJ"]["coef"], "adj_p": results["ADJ"]["p"],
        "adj_beats_raw": adj_beats_raw,
        "adj_adds_value": adj_adds_value,
        "adj_p_in_combined": adj_p_comb,
        "raw_p_in_combined": raw_p_comb,
        "r2_both": r2_both,
        "stable_raw": stable_raw, "stable_adj": stable_adj,
        "raw_spread": raw_spread if 'raw_spread' in dir() else np.nan,
        "adj_spread": adj_spread if 'adj_spread' in dir() else np.nan,
        "yr_detail": yr_detail,
    })

    print(f"  {fam_name:20s} RAW p={results['RAW']['p']:.4f} ADJ p={results['ADJ']['p']:.4f} "
          f"adj_beats={adj_beats_raw} adds_value={adj_adds_value} "
          f"stable_r={stable_raw} stable_a={stable_adj}")

# =====================================================================
# STEP 8 — INTERACTION READINESS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 8 — INTERACTION READINESS")
print("=" * 60)

# Identify families that survived (adj_p < 0.10 OR adj_beats_raw with adj_p < 0.20)
survivors = [f for f in family_results if f["adj_p"] < 0.10 or (f["adj_beats_raw"] and f["adj_p"] < 0.20)]
print(f"  Surviving families: {len(survivors)}")
for s in survivors:
    print(f"    {s['family']}: adj_p={s['adj_p']:.4f}, adds_value={s['adj_adds_value']}")

# Check correlation with existing S12 (combined_pitcher_score) and P09
# S12 proxy: combined CSW and xFIP are already in the model
# Just check correlations between surviving adj features and existing signals
if survivors:
    print("\n  Correlation with existing features:")
    for s in survivors:
        adj_col = f"combined_adj_{s['family'].lower().replace('_last', '_last')}"
        # Fix column name mapping
        fam_map = {
            "K_rate_last3": "combined_adj_k_rate_last3",
            "K_rate_last5": "combined_adj_k_rate_last5",
            "CSW_last3": "combined_adj_csw_last3",
            "CSW_last5": "combined_adj_csw_last5",
            "HardHit_last3": "combined_adj_hard_hit_last3",
            "HardHit_last5": "combined_adj_hard_hit_last5",
        }
        adj_col = fam_map.get(s["family"])
        if adj_col is None or adj_col not in df.columns:
            continue

        # vs xFIP gap
        for ctrl in ["home_sp_xfip", "closing_total"]:
            if ctrl in df.columns:
                v = df[[adj_col, ctrl]].dropna()
                r, p = stats.pearsonr(v[adj_col], v[ctrl])
                print(f"    {s['family']} vs {ctrl}: r={r:.4f}")


# =====================================================================
# STEP 9 — FINAL VERDICT & REPORT
# =====================================================================
print("\n" + "=" * 60)
print("STEP 9 — FINAL VERDICT")
print("=" * 60)

# Build report
R = []
R.append("# Opponent-Adjusted Pitcher Form Engine — v1 Report")
R.append("")
R.append("## Overview")
R.append("Full independent engine testing whether opponent-adjusted recent pitcher form")
R.append("predicts MLB totals / market residuals better than raw recent form.")
R.append("")
R.append(f"Evaluation: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append("")

R.append("## Methodology")
R.append("```")
R.append("adj_metric = raw_metric - (opponent_rolling_20g - league_avg)")
R.append("```")
R.append("- Team offense: K_rate, BB_rate, runs/game rolling 20 games (pregame)")
R.append("- Hard-hit/barrel: adjusted via opponent runs quality proxy")
R.append("- Rolling form: last 3 and last 5 prior starts")
R.append("- Combined: avg(home_SP, away_SP) rolling form")
R.append("")

# Step 5 — Model comparison
R.append("## Step 5 — Engine Model Comparison")
R.append("")
R.append("### Target: market_residual")
R.append("")
R.append("| Model | Features | N | R² | Adj R² | Sig Features | AIC |")
R.append("|-------|----------|---|-----|--------|-------------|-----|")
for m in models_summary:
    if m["target"] == "market_residual":
        R.append(f"| {m['name']} | {m.get('total_features', '?')} | {m['N']} | "
                 f"{m['r2']:.6f} | {m.get('adj_r2', 0):.6f} | "
                 f"{m.get('sig_features', '?')} | {m.get('aic', 0):.0f} |")
R.append("")

R.append("### Target: actual_result_under")
R.append("")
R.append("| Model | N | R² | Sig Features |")
R.append("|-------|---|-----|-------------|")
for m in models_summary:
    if m["target"] == "actual_result_under":
        R.append(f"| {m['name']} | {m['N']} | {m['r2']:.6f} | {m.get('sig_features', '?')} |")
R.append("")

R.append("### Target: actual_total")
R.append("")
R.append("| Model | N | R² | MAE |")
R.append("|-------|---|-----|-----|")
for m in models_summary:
    if m["target"] == "actual_total":
        R.append(f"| {m['name']} | {m['N']} | {m['r2']:.6f} | {m['mae']:.3f} |")
R.append("")

# Step 6 — Decile tables
R.append("## Step 6 — Decile Structure")
R.append("")
for name, rows in decile_tables.items():
    R.append(f"### {name}")
    R.append("")
    R.append("| Decile | N | Score | Resid | Under% | ROI @-110 |")
    R.append("|--------|---|-------|-------|--------|-----------|")
    for row in rows:
        R.append(f"| {row['decile']} | {row['N']} | {row['mean_score']:.4f} | "
                 f"{row['mean_resid']:+.4f} | {row['under_rate']:.3f} | {row['roi']:+.1f}% |")
    d0 = rows[0]
    d9 = rows[-1]
    spread_ur = d9["under_rate"] - d0["under_rate"]
    spread_roi = d9["roi"] - d0["roi"]
    R.append(f"\nTail spread: D9-D0 under_rate={spread_ur:+.3f}, ROI={spread_roi:+.1f}pp")
    R.append("")

# Season stability
R.append("### Season Stability")
R.append("")
R.append("| Model | Year | R² | Sig Features |")
R.append("|-------|------|-----|-------------|")
for row in stability_rows:
    R.append(f"| {row['model']} | {row['year']} | {row['r2']:.6f} | {row.get('sig_features', '?')} |")
R.append("")

# Market independence
R.append("### Market Independence")
R.append("")
R.append("| Model | Score vs closing_total r | p |")
R.append("|-------|------------------------|---|")
for row in market_corr_rows:
    R.append(f"| {row['model']} | {row['score_market_corr']:.4f} | {row['p']:.4f} |")
R.append("")

# Step 7 — Feature families
R.append("## Step 7 — Feature Family Comparison")
R.append("")
R.append("| Family | Raw p | Adj p | Adj beats raw? | Adj adds value? | Stable raw | Stable adj |")
R.append("|--------|-------|-------|---------------|----------------|-----------|-----------|")
for f in family_results:
    R.append(f"| {f['family']} | {f['raw_p']:.4f} | {f['adj_p']:.4f} | "
             f"{'YES' if f['adj_beats_raw'] else 'NO'} | "
             f"{'YES' if f['adj_adds_value'] else 'NO'} | "
             f"{'YES' if f['stable_raw'] else 'NO'} | "
             f"{'YES' if f['stable_adj'] else 'NO'} |")
R.append("")

# Year detail for surviving families
R.append("### Year Detail (surviving families)")
R.append("")
for f in family_results:
    if f["adj_p"] < 0.15:
        R.append(f"**{f['family']}**")
        R.append("| Year | Version | Coef | p |")
        R.append("|------|---------|------|---|")
        for yr in [2024, 2025]:
            for tag in ["RAW", "ADJ"]:
                d = f["yr_detail"].get((yr, tag), {})
                c = d.get("coef", np.nan)
                p = d.get("p", np.nan)
                R.append(f"| {yr} | {tag} | {c:+.5f} | {p:.4f} |")
        R.append("")

# Step 8 — Interaction readiness
R.append("## Step 8 — Interaction Readiness")
R.append("")
if survivors:
    R.append(f"Surviving families: {len(survivors)}")
    R.append("")
    for s in survivors:
        R.append(f"- **{s['family']}**: adj_p={s['adj_p']:.4f}, adds_value={s['adj_adds_value']}")
    R.append("")
    R.append("### Best Interaction Candidates")
    R.append("")
    R.append("1. **adj_k_rate_last3**: Best standalone significance. Test as interaction with S12 (command)")
    R.append("   because S12 uses CSW×xFIP — opponent-adjusted K rate captures a different dimension")
    R.append("   (form recency vs. season-level skill).")
    R.append("")
    R.append("2. **adj_csw_last3**: If significant, test with P09 (contact suppression × park)")
    R.append("   because adjusted CSW isolates pitcher dominance from opponent weakness.")
    R.append("")
    R.append("3. Hard-hit families: NOT recommended for interaction testing unless individually significant.")
else:
    R.append("No families survived for interaction testing.")
R.append("")

# Step 9 — Final verdict
R.append("## Step 9 — Final Verdict")
R.append("")

# Count results
n_adj_beats = sum(1 for f in family_results if f["adj_beats_raw"])
n_adj_adds = sum(1 for f in family_results if f["adj_adds_value"])
n_adj_sig = sum(1 for f in family_results if f["adj_p"] < 0.05)
n_adj_marginal = sum(1 for f in family_results if f["adj_p"] < 0.10)

R.append("### Scorecard")
R.append("")
R.append(f"- Families where ADJ beats RAW on significance: {n_adj_beats}/{len(family_results)}")
R.append(f"- Families where ADJ is individually significant (p<0.05): {n_adj_sig}/{len(family_results)}")
R.append(f"- Families where ADJ is marginal (p<0.10): {n_adj_marginal}/{len(family_results)}")
R.append(f"- Families where ADJ adds value beyond RAW in combined model: {n_adj_adds}/{len(family_results)}")
R.append("")

# Answers
R.append("### Q1: Does the full opponent-adjusted engine concept work?")
# Check if B_ADJ model beats A_RAW on market_residual
raw_r2 = [m for m in models_summary if m["name"] == "A_RAW" and m["target"] == "market_residual"][0]["r2"]
adj_r2 = [m for m in models_summary if m["name"] == "B_ADJ" and m["target"] == "market_residual"][0]["r2"]
comb_r2 = [m for m in models_summary if m["name"] == "C_COMBINED" and m["target"] == "market_residual"][0]["r2"]
R.append(f"- RAW engine R²: {raw_r2:.6f}")
R.append(f"- ADJ engine R²: {adj_r2:.6f}")
R.append(f"- COMBINED engine R²: {comb_r2:.6f}")
if adj_r2 > raw_r2 * 1.2:
    R.append("- **YES** — adjusted engine outperforms raw by >20% relative R²")
elif adj_r2 > raw_r2:
    R.append("- **MARGINAL** — adjusted engine slightly outperforms raw")
else:
    R.append("- **NO** — adjusted engine does not outperform raw")
R.append("")

R.append("### Q2: Does adjusted engine beat raw?")
if adj_r2 > raw_r2 and n_adj_beats >= 5:
    R.append("- **YES** across most families")
elif adj_r2 > raw_r2 and n_adj_beats >= 3:
    R.append("- **PARTIALLY** — better in some families, not all")
else:
    R.append("- **NO** — not consistently better")
R.append("")

R.append("### Q3: Does combined engine beat both?")
if comb_r2 > max(raw_r2, adj_r2) * 1.1:
    R.append("- **YES** — meaningful information in both raw and adjusted")
elif comb_r2 > max(raw_r2, adj_r2):
    R.append("- **MARGINAL** — slight improvement from combining")
else:
    R.append("- **NO** — no benefit from combining")
R.append("")

R.append("### Q4: Which adjusted feature families matter most?")
sorted_fams = sorted(family_results, key=lambda x: x["adj_p"])
for f in sorted_fams[:5]:
    tag = "**SIGNIFICANT**" if f["adj_p"] < 0.05 else "marginal" if f["adj_p"] < 0.10 else "not sig"
    R.append(f"- {f['family']}: adj_p={f['adj_p']:.4f} ({tag})")
R.append("")

R.append("### Q5: Broad enough for further development?")
if n_adj_sig >= 3:
    R.append("- **YES** — multiple significant families justify continued work")
elif n_adj_sig >= 1 and n_adj_marginal >= 3:
    R.append("- **CONDITIONAL** — one strong family, others marginal. Worth targeted follow-up.")
elif n_adj_sig >= 1:
    R.append("- **NARROW** — only one family shows promise. Not broad enough for full engine.")
else:
    R.append("- **NO** — insufficient evidence across families")
R.append("")

# Final classification
R.append("### Final Project Verdict")
R.append("")
if n_adj_sig >= 2 and adj_r2 > raw_r2:
    verdict = "ADVANCE"
    next_step = "scanner feature family integration + interaction testing with S12/P09"
elif n_adj_sig >= 1 and n_adj_adds >= 1:
    verdict = "INVESTIGATE"
    next_step = "add adj_k_rate_last3 to scanner catalog; shadow monitor in 2026; test S12 interaction"
elif n_adj_marginal >= 2:
    verdict = "INVESTIGATE"
    next_step = "scanner feature family only; revisit with 2026 data"
else:
    verdict = "SHELVE"
    next_step = "no further work"

R.append(f"**{verdict}**")
R.append("")
R.append(f"Recommended next step: {next_step}")
R.append("")

# Save
out_path = BASE / "opponent_adjusted_engine_report.md"
with open(out_path, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"\nSaved: {out_path}")

# Also save comparison tables
pd.DataFrame(models_summary).to_parquet(BASE / "model_comparison.parquet", index=False)
pd.DataFrame(family_results).to_parquet(BASE / "family_comparison.parquet", index=False)
pd.DataFrame(stability_rows).to_parquet(BASE / "stability_comparison.parquet", index=False)
print("Saved model/family/stability comparison tables.")
