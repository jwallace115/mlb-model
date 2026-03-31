#!/usr/bin/env python3
"""
V3 Phase 2 — Actual-Lineup Ceiling Test.
Does lineup-level granularity add signal beyond team-level averages?
"""

import json, os
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
V3 = BASE.parent
SIM = V3.parent.parent / "sim" / "data"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# =====================================================================
# STEP 0 — SOURCE AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — AUDIT")
print("=" * 60)

lu_env = pd.read_parquet(V3 / "actual_lineup_environment_table.parquet")
lu_env["game_date"] = pd.to_datetime(lu_env["game_date"])
v2_off = pd.read_parquet(V3.parent / "opponent_adjusted_engine_v2" / "offense_expectation_table.parquet")
v2_off["date"] = pd.to_datetime(v2_off["date"])
gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])

audit = [
    "# Source Audit — Phase 2 Ceiling Test", "",
    f"| File | Rows |",
    f"|------|------|",
    f"| actual_lineup_environment_table.parquet | {len(lu_env)} |",
    f"| V2 offense_expectation_table.parquet | {len(v2_off)} |",
    f"| game_table.parquet | {len(gt)} |",
    f"| bet_results.parquet | {len(br)} |",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")

# =====================================================================
# STEP 1 — TEAM-LEVEL BASELINE
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — TEAM-LEVEL BASELINE")
print("=" * 60)

# V2 has team_k_rate, team_bb_rate, team_contact_rate (rolling 20g)
# Need to add team_iso. Build from boxscore team batting.
print("  Building team-level ISO from boxscores...")
BOXSCORE_DIR = SIM / "cache" / "boxscores"
bat_rows = []
for fname in os.listdir(BOXSCORE_DIR):
    game_pk = int(fname.replace(".json", ""))
    try:
        with open(BOXSCORE_DIR / fname) as f:
            box = json.load(f)
    except Exception:
        continue
    for side in ["home", "away"]:
        td = box.get("teams", {}).get(side, {})
        team = td.get("team", {}).get("abbreviation", "")
        bat = td.get("teamStats", {}).get("batting", {})
        if not bat:
            continue
        ab = int(bat.get("atBats", 0))
        h = int(bat.get("hits", 0))
        tb = int(bat.get("totalBases", 0))
        iso = (tb - h) / max(ab, 1)
        bat_rows.append({"game_pk": game_pk, "side": side, "team": team, "iso": iso})

tb_df = pd.DataFrame(bat_rows)
tb_df = tb_df.merge(gt[["game_pk", "date", "season"]], on="game_pk", how="left")
tb_df = tb_df.dropna(subset=["date"]).sort_values(["team", "date"])

def _rolling_iso(grp):
    grp = grp.sort_values("date").copy()
    grp["team_iso_last20"] = grp["iso"].shift(1).rolling(20, min_periods=10).mean()
    return grp

tb_df = tb_df.groupby("team", group_keys=False).apply(_rolling_iso)

# Merge V2 offense + ISO into team baseline
team_base = v2_off[["game_pk", "side", "team", "date", "season",
                     "team_k_rate", "team_bb_rate", "team_contact_rate"]].copy()
team_base = team_base.merge(
    tb_df[["game_pk", "side", "team_iso_last20"]],
    on=["game_pk", "side"], how="left"
)
# Rename V2 rolling columns for clarity
team_base.rename(columns={
    "team_k_rate": "team_k_rate_last20",
    "team_bb_rate": "team_bb_rate_last20",
    "team_contact_rate": "team_contact_rate_last20",
}, inplace=True)

team_base.to_parquet(BASE / "team_level_offense_baseline.parquet", index=False)
t2425 = team_base[team_base.season.isin([2024, 2025])]
print(f"  Saved: {len(team_base)} rows")
for c in ["team_k_rate_last20", "team_bb_rate_last20", "team_contact_rate_last20", "team_iso_last20"]:
    print(f"    {c}: {t2425[c].notna().mean():.1%}")

# =====================================================================
# STEP 2 — COMPARISON DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — COMPARISON DATASET")
print("=" * 60)

# Start from V3 foundation
v3_ds = pd.read_parquet(V3 / "v3_lineup_foundation_dataset.parquet")
v3_ds["game_date"] = pd.to_datetime(v3_ds["game_date"])

# Add team-level baselines
for side, prefix in [("home", "home"), ("away", "away")]:
    tb_side = team_base[team_base["side"] == side][[
        "game_pk", "team_k_rate_last20", "team_bb_rate_last20",
        "team_contact_rate_last20", "team_iso_last20"
    ]].rename(columns={
        "team_k_rate_last20": f"{prefix}_team_k_rate_last20",
        "team_bb_rate_last20": f"{prefix}_team_bb_rate_last20",
        "team_contact_rate_last20": f"{prefix}_team_contact_rate_last20",
        "team_iso_last20": f"{prefix}_team_iso_last20",
    })
    v3_ds = v3_ds.merge(tb_side, on="game_pk", how="left")

# Market error
v3_ds["market_error"] = v3_ds["actual_total"] - v3_ds["closing_total"]
v3_ds["actual_result_over"] = (v3_ds["actual_total"] > v3_ds["closing_total"]).astype(float)
v3_ds.loc[v3_ds["actual_total"] == v3_ds["closing_total"], "actual_result_over"] = np.nan
v3_ds["actual_result_under"] = (v3_ds["actual_total"] < v3_ds["closing_total"]).astype(float)
v3_ds.loc[v3_ds["actual_total"] == v3_ds["closing_total"], "actual_result_under"] = np.nan
v3_ds["implied_over"] = 0.50
v3_ds["implied_under"] = 0.50

v3_ds.to_parquet(BASE / "v3_phase2_comparison_dataset.parquet", index=False)

lineup_cols = [c for c in v3_ds.columns if "lineup_" in c and "last20" in c]
team_cols = [c for c in v3_ds.columns if "team_" in c and "last20" in c]
both_avail = v3_ds[lineup_cols + team_cols].notna().all(axis=1).sum()
total = len(v3_ds)
print(f"  Total games: {total}")
print(f"  Full lineup+team coverage: {both_avail} ({100*both_avail/total:.1f}%)")

# Focus on 2024-2025 with closing lines for evaluation
eval_df = v3_ds[v3_ds["closing_total"].notna()].copy()
eval_np = eval_df[eval_df["actual_result_over"].notna()].copy()
print(f"  Evaluation (with closing): {len(eval_df)}, non-push: {len(eval_np)}")

# =====================================================================
# STEP 3 — CORRELATION / DIFFERENCE TEST
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — LINEUP vs TEAM CORRELATION")
print("=" * 60)

corr_rows = []
PAIRS = [
    ("contact_rate_last20", "lineup_contact_rate_last20", "team_contact_rate_last20"),
    ("k_rate_last20", "lineup_k_rate_last20", "team_k_rate_last20"),
    ("bb_rate_last20", "lineup_bb_rate_last20", "team_bb_rate_last20"),
    ("iso_last20", "lineup_iso_last20", "team_iso_last20"),
]

for family, lu_suffix, tm_suffix in PAIRS:
    for side in ["home", "away"]:
        lu_col = f"{side}_{lu_suffix}"
        tm_col = f"{side}_{tm_suffix}"
        valid = eval_df[[lu_col, tm_col]].dropna()
        if len(valid) < 100:
            continue
        r, _ = stats.pearsonr(valid[lu_col], valid[tm_col])
        diff = (valid[lu_col] - valid[tm_col]).abs()
        corr_rows.append({
            "family": family, "side": side,
            "correlation": r, "mean_abs_diff": diff.mean(),
            "p90_abs_diff": diff.quantile(0.90),
        })
        print(f"  {side} {family}: r={r:.4f}, mean_diff={diff.mean():.5f}, p90_diff={diff.quantile(0.90):.5f}")

corr_df = pd.DataFrame(corr_rows)
corr_df.to_parquet(BASE / "correlation_comparison.parquet", index=False)

# =====================================================================
# STEP 4 — INCREMENTAL VALUE TEST
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — INCREMENTAL VALUE")
print("=" * 60)

incr_rows = []

for family, lu_suffix, tm_suffix in PAIRS:
    for side in ["home", "away"]:
        lu_col = f"{side}_{lu_suffix}"
        tm_col = f"{side}_{tm_suffix}"
        valid = eval_df[[lu_col, tm_col, "market_error"]].dropna()
        if len(valid) < 200:
            continue

        # A: team only
        X_a = sm.add_constant(valid[tm_col])
        m_a = sm.OLS(valid["market_error"], X_a).fit()

        # B: lineup only
        X_b = sm.add_constant(valid[lu_col])
        m_b = sm.OLS(valid["market_error"], X_b).fit()

        # C: both
        X_c = sm.add_constant(valid[[tm_col, lu_col]])
        m_c = sm.OLS(valid["market_error"], X_c).fit()

        lu_p_in_c = m_c.pvalues[lu_col]
        tm_p_in_c = m_c.pvalues[tm_col]

        if lu_p_in_c < 0.10:
            verdict = "ADDS_VALUE"
        elif lu_p_in_c < 0.25:
            verdict = "WEAK"
        else:
            verdict = "REDUNDANT"

        incr_rows.append({
            "family": family, "side": side,
            "team_r2": m_a.rsquared, "team_p": m_a.pvalues.iloc[1],
            "lineup_r2": m_b.rsquared, "lineup_p": m_b.pvalues.iloc[1],
            "both_r2": m_c.rsquared,
            "lineup_p_in_combined": lu_p_in_c,
            "team_p_in_combined": tm_p_in_c,
            "verdict": verdict,
        })

        print(f"  {side} {family}: team_R²={m_a.rsquared:.6f}, lineup_R²={m_b.rsquared:.6f}, "
              f"both_R²={m_c.rsquared:.6f}, lineup_p_comb={lu_p_in_c:.4f} → {verdict}")

incr_df = pd.DataFrame(incr_rows)
incr_df.to_parquet(BASE / "incremental_models.parquet", index=False)

# =====================================================================
# STEP 5 — STRUCTURAL FEATURES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — STRUCTURAL FEATURES")
print("=" * 60)

struct_rows = []
for side in ["home", "away"]:
    for struct_col, baseline_col in [
        (f"{side}_top4_iso_last20", f"{side}_team_iso_last20"),
        (f"{side}_bottom3_k_rate_last20", f"{side}_team_k_rate_last20"),
    ]:
        if struct_col not in eval_df.columns or baseline_col not in eval_df.columns:
            continue
        valid = eval_df[[struct_col, baseline_col, "market_error"]].dropna()
        if len(valid) < 200:
            continue

        # Standalone
        X_s = sm.add_constant(valid[struct_col])
        m_s = sm.OLS(valid["market_error"], X_s).fit()

        # Incremental
        X_i = sm.add_constant(valid[[baseline_col, struct_col]])
        m_i = sm.OLS(valid["market_error"], X_i).fit()

        struct_rows.append({
            "feature": struct_col,
            "standalone_r2": m_s.rsquared,
            "standalone_p": m_s.pvalues[struct_col],
            "incremental_p": m_i.pvalues[struct_col],
            "incremental_r2": m_i.rsquared,
        })
        print(f"  {struct_col}: standalone_p={m_s.pvalues[struct_col]:.4f}, "
              f"incremental_p={m_i.pvalues[struct_col]:.4f}")

struct_df = pd.DataFrame(struct_rows)
struct_df.to_parquet(BASE / "structural_feature_tests.parquet", index=False)

# =====================================================================
# STEP 6 — TAIL TESTS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — TAIL TESTS")
print("=" * 60)

# Test the strongest lineup features
test_features = [
    ("home_lineup_iso_last20", "HIGH"),
    ("away_lineup_iso_last20", "HIGH"),
    ("home_lineup_k_rate_last20", "LOW"),
    ("away_lineup_k_rate_last20", "LOW"),
    ("home_top4_iso_last20", "HIGH"),
    ("away_top4_iso_last20", "HIGH"),
]

tail_rows = []
for feat, direction in test_features:
    if feat not in eval_np.columns:
        continue
    valid = eval_np[feat].notna()
    sub = eval_np[valid]
    if len(sub) < 200:
        continue

    for label, lo_pct, hi_pct in [("top_10", 90, 100), ("top_20", 80, 100),
                                    ("bot_10", 0, 10), ("bot_20", 0, 20)]:
        if lo_pct == 0:
            thresh = sub[feat].quantile(hi_pct / 100)
            mask = sub[feat] <= thresh
        else:
            thresh = sub[feat].quantile(lo_pct / 100)
            mask = sub[feat] > thresh

        n = mask.sum()
        if n < 40:
            continue

        over_r = sub.loc[mask, "actual_result_over"].mean()
        under_r = sub.loc[mask, "actual_result_under"].mean()
        me = eval_df.loc[sub.loc[mask].index.intersection(eval_df.index), "market_error"].mean()

        # Year split
        yr_data = {}
        for yr in [2024, 2025]:
            yr_m = mask & (sub["season"] == yr)
            yn = yr_m.sum()
            if yn >= 20:
                yw_over = sub.loc[yr_m, "actual_result_over"].sum()
                yr_data[yr] = roi_110(yw_over, yn - yw_over)

        # Best-side ROI
        w_over = sub.loc[mask, "actual_result_over"].sum()
        roi_over = roi_110(w_over, n - w_over)
        w_under = sub.loc[mask, "actual_result_under"].sum()
        roi_under = roi_110(w_under, n - w_under)

        tail_rows.append({
            "feature": feat, "bucket": label, "N": n,
            "over_rate": over_r, "under_rate": under_r,
            "mean_market_error": me,
            "roi_over": roi_over, "roi_under": roi_under,
            "roi_2024_over": yr_data.get(2024, np.nan),
            "roi_2025_over": yr_data.get(2025, np.nan),
        })

tail_df = pd.DataFrame(tail_rows)
tail_df.to_parquet(BASE / "tail_bucket_tests.parquet", index=False)

# Print notable tails
for _, r in tail_df.sort_values("roi_over", ascending=False).head(10).iterrows():
    r24 = f"{r.roi_2024_over:+.1f}" if not np.isnan(r.roi_2024_over) else "N/A"
    r25 = f"{r.roi_2025_over:+.1f}" if not np.isnan(r.roi_2025_over) else "N/A"
    print(f"  {r.feature} {r.bucket}: N={r.N}, over%={r.over_rate:.3f}, "
          f"ROI_over={r.roi_over:+.1f}%, 2024={r24}, 2025={r25}")

# =====================================================================
# STEP 7 — SEASON STABILITY
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — SEASON STABILITY")
print("=" * 60)

stab_rows = []
for feat in ["home_lineup_iso_last20", "away_lineup_iso_last20",
             "home_lineup_k_rate_last20", "away_lineup_k_rate_last20"]:
    if feat not in eval_df.columns:
        continue
    for yr in [2024, 2025]:
        yr_df = eval_df[eval_df.season == yr]
        valid = yr_df[feat].notna()
        if valid.sum() < 100:
            continue
        X = sm.add_constant(yr_df.loc[valid, feat])
        y = yr_df.loc[valid, "market_error"]
        m = sm.OLS(y, X).fit()
        stab_rows.append({
            "feature": feat, "year": yr,
            "coef": m.params[feat], "p": m.pvalues[feat],
        })
        print(f"  {feat} {yr}: coef={m.params[feat]:+.4f}, p={m.pvalues[feat]:.4f}")

# =====================================================================
# STEP 8 — MARKET AWARENESS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 8 — MARKET AWARENESS")
print("=" * 60)

for feat in ["home_lineup_iso_last20", "away_lineup_iso_last20",
             "home_top4_iso_last20", "away_top4_iso_last20"]:
    if feat not in eval_df.columns:
        continue
    valid = eval_df[feat].notna() & eval_df["closing_total"].notna()
    if valid.sum() < 200:
        continue
    r, _ = stats.pearsonr(eval_df.loc[valid, feat], eval_df.loc[valid, "closing_total"])
    p90 = eval_df.loc[valid, feat].quantile(0.90)
    fav = eval_df.loc[valid & (eval_df[feat] > p90), "closing_total"].mean()
    rest = eval_df.loc[valid & (eval_df[feat] <= p90), "closing_total"].mean()
    print(f"  {feat}: r={r:.4f}, top10_close={fav:.2f}, rest_close={rest:.2f}, diff={fav-rest:+.2f}")

# =====================================================================
# STEP 9 — V2 UPGRADE TEST
# =====================================================================
print("\n" + "=" * 60)
print("STEP 9 — V2 OPPONENT-ADJUSTED UPGRADE")
print("=" * 60)

# Test: does lineup_k_rate vs team_k_rate improve pitcher K-rate adjustment?
# adj_k = pitcher_k_rate - opponent_k_rate
# Compare: opponent = team_k_rate vs opponent = lineup_k_rate
# Against market_error

# We need pitcher K rates. Use feature_table sp_k_pct
ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
ft24 = ft[ft.season.isin([2024, 2025])][["game_pk", "home_sp_k_pct", "away_sp_k_pct"]].copy()

v2_test = eval_df.merge(ft24, on="game_pk", how="left")

# Team-adjusted K: pitcher_k - team_opponent_k
v2_test["adj_k_team_home"] = v2_test["home_sp_k_pct"] - v2_test["away_team_k_rate_last20"]
v2_test["adj_k_team_away"] = v2_test["away_sp_k_pct"] - v2_test["home_team_k_rate_last20"]
v2_test["adj_k_team_combined"] = (v2_test["adj_k_team_home"] + v2_test["adj_k_team_away"]) / 2

# Lineup-adjusted K: pitcher_k - lineup_opponent_k
v2_test["adj_k_lineup_home"] = v2_test["home_sp_k_pct"] - v2_test["away_lineup_k_rate_last20"]
v2_test["adj_k_lineup_away"] = v2_test["away_sp_k_pct"] - v2_test["home_lineup_k_rate_last20"]
v2_test["adj_k_lineup_combined"] = (v2_test["adj_k_lineup_home"] + v2_test["adj_k_lineup_away"]) / 2

for label, col in [("team-adjusted", "adj_k_team_combined"),
                     ("lineup-adjusted", "adj_k_lineup_combined")]:
    valid = v2_test[col].notna() & v2_test["market_error"].notna()
    X = sm.add_constant(v2_test.loc[valid, col])
    y = v2_test.loc[valid, "market_error"]
    m = sm.OLS(y, X).fit()
    print(f"  {label}: coef={m.params[col]:+.5f}, p={m.pvalues[col]:.4f}, R²={m.rsquared:.6f}")

# Both in one model
valid = (v2_test["adj_k_team_combined"].notna() &
         v2_test["adj_k_lineup_combined"].notna() &
         v2_test["market_error"].notna())
X = sm.add_constant(v2_test.loc[valid, ["adj_k_team_combined", "adj_k_lineup_combined"]])
y = v2_test.loc[valid, "market_error"]
m = sm.OLS(y, X).fit()
print(f"  Combined: team_p={m.pvalues['adj_k_team_combined']:.4f}, "
      f"lineup_p={m.pvalues['adj_k_lineup_combined']:.4f}, R²={m.rsquared:.6f}")

# =====================================================================
# STEP 10 — FINAL REPORT
# =====================================================================
print("\n" + "=" * 60)
print("STEP 10 — REPORT")
print("=" * 60)

R = []
R.append("# V3 Phase 2 — Actual-Lineup Ceiling Test Report")
R.append("")
R.append(f"Dataset: {len(eval_df)} games (2024-2025 with closing lines)")
R.append(f"Non-push: {len(eval_np)}")
R.append("")

R.append("## Q1: Do lineup features differ from team baselines?")
R.append("")
R.append("| Family | Side | Correlation | Mean Diff | p90 Diff |")
R.append("|--------|------|------------|-----------|----------|")
for _, r in corr_df.iterrows():
    R.append(f"| {r.family} | {r.side} | {r.correlation:.4f} | {r.mean_abs_diff:.5f} | {r.p90_abs_diff:.5f} |")
R.append("")

avg_corr = corr_df["correlation"].mean()
R.append(f"Average correlation: {avg_corr:.4f}")
if avg_corr > 0.90:
    R.append("**Lineup and team features are very similar** (r > 0.90). Limited room for differentiation.")
elif avg_corr > 0.75:
    R.append("**Moderate differentiation** (r ~ 0.75-0.90). Some lineup composition information beyond team average.")
else:
    R.append("**Substantial differentiation** (r < 0.75). Lineups carry meaningful unique information.")
R.append("")

R.append("## Q2: Do lineup features add signal beyond team?")
R.append("")
R.append("| Family | Side | Team R² | Lineup R² | Both R² | Lineup p (combined) | Verdict |")
R.append("|--------|------|---------|-----------|---------|--------------------|---------| ")
for _, r in incr_df.iterrows():
    R.append(f"| {r.family} | {r.side} | {r.team_r2:.6f} | {r.lineup_r2:.6f} | "
             f"{r.both_r2:.6f} | {r.lineup_p_in_combined:.4f} | **{r.verdict}** |")
R.append("")

n_adds = (incr_df.verdict == "ADDS_VALUE").sum()
n_weak = (incr_df.verdict == "WEAK").sum()
n_redun = (incr_df.verdict == "REDUNDANT").sum()
R.append(f"ADDS_VALUE: {n_adds}/{len(incr_df)}, WEAK: {n_weak}, REDUNDANT: {n_redun}")
R.append("")

R.append("## Q3: Which lineup metrics matter most?")
R.append("")
best = incr_df.sort_values("lineup_p_in_combined")
for _, r in best.head(5).iterrows():
    R.append(f"- {r.side} {r.family}: lineup_p={r.lineup_p_in_combined:.4f} ({r.verdict})")
R.append("")

R.append("## Q4: Structural features useful?")
R.append("")
R.append("| Feature | Standalone p | Incremental p |")
R.append("|---------|-------------|--------------|")
for _, r in struct_df.iterrows():
    R.append(f"| {r.feature} | {r.standalone_p:.4f} | {r.incremental_p:.4f} |")
R.append("")

R.append("## Tail Tests (top results)")
R.append("")
R.append("| Feature | Bucket | N | Over% | ROI Over | 2024 | 2025 |")
R.append("|---------|--------|---|-------|----------|------|------|")
for _, r in tail_df.sort_values("roi_over", ascending=False).head(8).iterrows():
    r24 = f"{r.roi_2024_over:+.1f}%" if not np.isnan(r.roi_2024_over) else "N/A"
    r25 = f"{r.roi_2025_over:+.1f}%" if not np.isnan(r.roi_2025_over) else "N/A"
    R.append(f"| {r.feature} | {r.bucket} | {r.N} | {r.over_rate:.3f} | {r.roi_over:+.1f}% | {r24} | {r25} |")
R.append("")

R.append("## Q5: Proceed to Phase 3?")
R.append("")

R.append("## Q6: V2 Opponent-Adjusted Upgrade")
R.append("")
R.append("Lineup-adjusted K rate vs team-adjusted K rate against market_error:")
R.append("(see console output for exact numbers)")
R.append("")

# Verdict
R.append("## Final Verdict")
R.append("")

if n_adds >= 3:
    verdict = "ADVANCE to Phase 3 projected-lineup engine"
    R.append(f"**{verdict}**")
    R.append(f"Lineup features add incremental value in {n_adds}/{len(incr_df)} family-side tests.")
elif n_adds >= 1 or n_weak >= 3:
    verdict = "INVESTIGATE further"
    R.append(f"**{verdict}**")
    R.append(f"Some evidence of lineup value ({n_adds} ADDS_VALUE, {n_weak} WEAK) but not broad enough.")
else:
    verdict = "SHELVE V3 concept"
    R.append(f"**{verdict}**")
    R.append("Lineup-level features are largely redundant with team-level averages.")

R.append("")
R.append("### Top 5 Lineup Features Worth Carrying Forward")
for i, (_, r) in enumerate(best.head(5).iterrows()):
    R.append(f"{i+1}. {r.side}_{r.family} (p={r.lineup_p_in_combined:.4f})")

R.append("")
R.append("### Clearly Redundant Features")
for _, r in incr_df[incr_df.verdict == "REDUNDANT"].iterrows():
    R.append(f"- {r.side}_{r.family}")

R.append("")
R.append("### Biggest Phase 3 Gaps")
R.append("1. Statcast batter-level metrics (hard_hit, barrel, pull, launch_angle)")
R.append("2. Batter handedness for platoon splits")
R.append("3. Projected lineup engine (currently using actual lineups)")

out = BASE / "v3_phase2_ceiling_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"  Saved: {out}")
print(f"  Verdict: {verdict}")
