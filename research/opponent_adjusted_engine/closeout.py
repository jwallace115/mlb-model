#!/usr/bin/env python3
"""
Close out opponent-adjusted engine research phase.
Task 1: Add adj_k_rate_last3 to signal catalog
Task 2: Interaction tests with V1 / S12 / P09
Task 3: Write final status note
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SCANNER = BASE.parent / "signal_scanner"
SIM = BASE.parent.parent / "sim" / "data"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100


# =====================================================================
# TASK 1 — ADD TO SIGNAL CATALOG
# =====================================================================
print("=" * 60)
print("TASK 1 — ADD adj_k_rate_last3 TO SIGNAL CATALOG")
print("=" * 60)

cat = pd.read_parquet(SCANNER / "signal_catalog.parquet")
if "adj_k_rate_last3" in cat["signal_name"].values:
    next_id = int(cat.loc[cat["signal_name"] == "adj_k_rate_last3", "signal_id"].iloc[0])
    print(f"  adj_k_rate_last3 already in catalog as signal_id={next_id}, skipping")
else:
    next_id = int(cat["signal_id"].max()) + 1
    new_row = pd.DataFrame([{
        "signal_id": next_id,
        "signal_name": "adj_k_rate_last3",
        "domain": "pitching",
        "correlation_family": "starter_quality",
        "formula": "rolling 3-start opponent-adjusted K rate = raw_k_rate_last3 - (opp_k_rate_r20 - league_avg_k_rate)",
        "required_inputs": "pitcher_recent_form_features.parquet, offense_expectation_table.parquet",
        "direction": "UNDER",
        "priority": "HIGH",
        "data_status": "DERIVABLE",
        "variants": "adj_k_rate_last5",
    }])
    cat_updated = pd.concat([cat, new_row], ignore_index=True)
    cat_updated.to_parquet(SCANNER / "signal_catalog.parquet", index=False)
    print(f"  Added signal_id={next_id} to signal_catalog.parquet ({len(cat_updated)} total)")


# =====================================================================
# TASK 2 — INTERACTION TESTS
# =====================================================================
print("\n" + "=" * 60)
print("TASK 2 — INTERACTION TESTS")
print("=" * 60)

# Load V1 sim results (p_under)
sim = pd.read_parquet(SIM / "phase5_sim_results.parquet")
sim["date"] = pd.to_datetime(sim["date"])

# Load engine dataset (has adj_k_rate_last3 and controls)
eng = pd.read_parquet(BASE / "game_level_engine_dataset.parquet")
eng["date"] = pd.to_datetime(eng["date"])

# Load feature table for S12 and P09 computation
ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])

# Load bet results for closing lines
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])

# Load Statcast for P09 (hard-hit rates)
sc = pd.read_parquet(BASE.parent / "statcast_enrichment" /
                     "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])

# Load pitcher start metrics for CSW (strike% as S12 proxy)
ps = pd.read_parquet(BASE / "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])

# ── Build evaluation dataset ─────────────────────────────────────────
# Start from V1 sim results (2024+2025)
eval_df = sim[sim["season"].isin([2024, 2025])].copy()

# Add closing lines
eval_df = eval_df.merge(
    br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
    on="game_pk", how="inner"
)

# Add xFIP, park, SP IDs from feature table (actual_total already in sim)
eval_df = eval_df.merge(
    ft[["game_pk", "home_sp_xfip", "away_sp_xfip",
        "park_factor_runs", "home_sp_id", "away_sp_id"]],
    on="game_pk", how="left"
)

# Targets
eval_df["is_push"] = (eval_df["actual_total"] == eval_df["close_total"])
eval_df["went_under"] = (eval_df["actual_total"] < eval_df["close_total"]).astype(int)

print(f"  Evaluation dataset: {len(eval_df)} games")

# ── Compute S12 ──────────────────────────────────────────────────────
# S12 = (home_csw + away_csw)/2 - 5*(home_xfip + away_xfip)/2
# CSW = season-average strike% per pitcher (from boxscore data)
# Compute season-average strike% per pitcher up to each game date (pregame)
ps_sorted = ps.sort_values(["pitcher_id", "date"])

def compute_season_csw(grp):
    """Expanding mean of strike% within season, shifted by 1 (pregame)."""
    grp = grp.sort_values("date")
    grp["season_csw"] = grp["raw_csw_start"].shift(1).expanding(min_periods=3).mean()
    return grp

ps_csw = ps_sorted.groupby(["pitcher_id", "season"], group_keys=False).apply(compute_season_csw)

# Join home SP CSW
home_csw = ps_csw[ps_csw["side"] == "home"][["game_pk", "season_csw"]].rename(
    columns={"season_csw": "home_csw"})
away_csw = ps_csw[ps_csw["side"] == "away"][["game_pk", "season_csw"]].rename(
    columns={"season_csw": "away_csw"})

eval_df = eval_df.merge(home_csw, on="game_pk", how="left")
eval_df = eval_df.merge(away_csw, on="game_pk", how="left")

# S12 score
eval_df["s12_score"] = ((eval_df["home_csw"] + eval_df["away_csw"]) / 2) - \
                        5 * ((eval_df["home_sp_xfip"] + eval_df["away_sp_xfip"]) / 2)
s12_cutoff = 8.4468  # Frozen from production config
eval_df["s12_active"] = (eval_df["s12_score"] >= s12_cutoff).astype(int)

s12_cov = eval_df["s12_score"].notna().mean()
s12_rate = eval_df["s12_active"].mean()
print(f"  S12 coverage: {s12_cov:.1%}, active rate: {s12_rate:.1%}")

# ── Compute P09 ──────────────────────────────────────────────────────
# P09 = avg(home_hh_r5, away_hh_r5) * park_run_factor
# Build rolling 5-start hard-hit rate per pitcher (shifted)
sc_sorted = sc.sort_values(["pitcher_id", "game_date"])
sc_sorted["hh_r5"] = sc_sorted.groupby("pitcher_id")["hard_hit_rate"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Build lookup
pitcher_hh = {}
for pid, grp in sc_sorted.dropna(subset=["hh_r5"]).groupby("pitcher_id"):
    pitcher_hh[pid] = list(zip(grp["game_date"].values, grp["hh_r5"].values))

def lookup_hh(row, sp_col):
    pid = row.get(sp_col)
    if pd.isna(pid): return np.nan
    pid = int(pid)
    if pid not in pitcher_hh: return np.nan
    gd = pd.Timestamp(row["date"])
    best = np.nan
    for d, hh in pitcher_hh[pid]:
        if pd.Timestamp(d) < gd:
            best = hh
        else:
            break
    return best

print("  Computing P09 hard-hit lookups...")
eval_df["home_hh"] = eval_df.apply(lambda r: lookup_hh(r, "home_sp_id"), axis=1)
eval_df["away_hh"] = eval_df.apply(lambda r: lookup_hh(r, "away_sp_id"), axis=1)
eval_df["p09_value"] = ((eval_df["home_hh"] + eval_df["away_hh"]) / 2) * eval_df["park_factor_runs"]
p09_cutoff = 31.7305  # Frozen from production config
eval_df["p09_active"] = (eval_df["p09_value"] <= p09_cutoff).astype(int)

p09_cov = eval_df["p09_value"].notna().mean()
p09_rate = eval_df["p09_active"].mean()
print(f"  P09 coverage: {p09_cov:.1%}, active rate: {p09_rate:.1%}")

# ── Add adj_k_rate_last3 ─────────────────────────────────────────────
adj_k = eng[["game_pk", "combined_adj_k_rate_last3"]].copy()
eval_df = eval_df.merge(adj_k, on="game_pk", how="left")

adj_cov = eval_df["combined_adj_k_rate_last3"].notna().mean()
print(f"  adj_k_rate_last3 coverage: {adj_cov:.1%}")

# ── Freeze threshold from 2024 ───────────────────────────────────────
eval_2024 = eval_df[eval_df["season"] == 2024]
adj_k_threshold = eval_2024["combined_adj_k_rate_last3"].quantile(0.80)
eval_df["adj_k_top20"] = (eval_df["combined_adj_k_rate_last3"] >= adj_k_threshold).astype(int)
print(f"  adj_k_rate_last3 top-20% threshold (frozen from 2024): {adj_k_threshold:.5f}")
print(f"  2024 top-20% rate: {eval_2024['combined_adj_k_rate_last3'].ge(adj_k_threshold).mean():.1%}")
eval_2025 = eval_df[eval_df["season"] == 2025]
print(f"  2025 top-20% rate: {eval_2025['combined_adj_k_rate_last3'].ge(adj_k_threshold).mean():.1%}")

# ── V1 filter ────────────────────────────────────────────────────────
eval_df["v1_under"] = (eval_df["p_under"] > 0.57).astype(int)
print(f"  V1 p_under>0.57: {eval_df['v1_under'].mean():.1%}")

# ── Non-push subset ──────────────────────────────────────────────────
df_np = eval_df[~eval_df["is_push"]].copy()

# ── Run interaction tests ─────────────────────────────────────────────
def report_cohort(label, mask_all, mask_np, df_all, df_nonpush, year_label="pooled"):
    n_all = mask_all.sum()
    n_np = mask_np.sum()
    if n_np < 10:
        return {"label": label, "year": year_label, "N": n_np,
                "under_rate": np.nan, "resid": np.nan, "roi": np.nan, "thin": True}
    under_rate = df_nonpush.loc[mask_np, "went_under"].mean()
    resid = under_rate - 0.50
    w = df_nonpush.loc[mask_np, "went_under"].sum()
    l = n_np - w
    roi = roi_110(w, l)
    thin = n_np < 50
    return {"label": label, "year": year_label, "N": n_np,
            "under_rate": under_rate, "resid": resid, "roi": roi, "thin": thin}


tests = [
    ("Test A: V1 alone", lambda d: d["v1_under"] == 1),
    ("Test A: V1 + adj_k top20", lambda d: (d["v1_under"] == 1) & (d["adj_k_top20"] == 1)),

    ("Test B: V1 + S12", lambda d: (d["v1_under"] == 1) & (d["s12_active"] == 1)),
    ("Test B: V1 + S12 + adj_k top20", lambda d: (d["v1_under"] == 1) & (d["s12_active"] == 1) & (d["adj_k_top20"] == 1)),

    ("Test C: V1 + P09", lambda d: (d["v1_under"] == 1) & (d["p09_active"] == 1)),
    ("Test C: V1 + P09 + adj_k top20", lambda d: (d["v1_under"] == 1) & (d["p09_active"] == 1) & (d["adj_k_top20"] == 1)),
]

all_results = []

for year_label, yr_all, yr_np in [("pooled", eval_df, df_np),
                                    ("2024", eval_df[eval_df["season"] == 2024],
                                     df_np[df_np["season"] == 2024]),
                                    ("2025", eval_df[eval_df["season"] == 2025],
                                     df_np[df_np["season"] == 2025])]:
    for label, mask_fn in tests:
        mask_all = mask_fn(yr_all)
        mask_np = mask_fn(yr_np)
        res = report_cohort(label, mask_all, mask_np, yr_all, yr_np, year_label)
        all_results.append(res)

# Print results
print(f"\n{'─'*90}")
print(f"{'Label':<35} {'Year':<8} {'N':>5} {'Under%':>8} {'Resid':>8} {'ROI':>8} {'Flag':>6}")
print(f"{'─'*90}")
for r in all_results:
    if r["under_rate"] is None or np.isnan(r.get("under_rate", np.nan)):
        print(f"{r['label']:<35} {r['year']:<8} {r['N']:>5d}     N/A      N/A      N/A   THIN")
    else:
        flag = " THIN" if r["thin"] else ""
        print(f"{r['label']:<35} {r['year']:<8} {r['N']:>5d} {r['under_rate']:>8.3f} {r['resid']:>+8.3f} {r['roi']:>+8.1f}%{flag}")


# ── Compute lift ──────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print("LIFT ANALYSIS")
print(f"{'─'*60}")

def get_roi(results, label, year):
    matches = [r for r in results if r["label"] == label and r["year"] == year]
    return matches[0]["roi"] if matches and not np.isnan(matches[0].get("roi", np.nan)) else np.nan

lift_results = []
for test_label, base_label, enhanced_label in [
    ("Test A", "Test A: V1 alone", "Test A: V1 + adj_k top20"),
    ("Test B", "Test B: V1 + S12", "Test B: V1 + S12 + adj_k top20"),
    ("Test C", "Test C: V1 + P09", "Test C: V1 + P09 + adj_k top20"),
]:
    for yr in ["pooled", "2024", "2025"]:
        base_roi = get_roi(all_results, base_label, yr)
        enh_roi = get_roi(all_results, enhanced_label, yr)
        lift = enh_roi - base_roi if not (np.isnan(base_roi) or np.isnan(enh_roi)) else np.nan
        base_n = [r for r in all_results if r["label"] == base_label and r["year"] == yr]
        enh_n = [r for r in all_results if r["label"] == enhanced_label and r["year"] == yr]
        b_n = base_n[0]["N"] if base_n else 0
        e_n = enh_n[0]["N"] if enh_n else 0

        if not np.isnan(lift):
            if e_n < 50:
                verdict = "THIN"
            elif lift > 3:
                verdict = "MEANINGFUL LIFT"
            elif lift > -3:
                verdict = "NEUTRAL"
            else:
                verdict = "HARMFUL"
        else:
            verdict = "N/A"

        lift_results.append({
            "test": test_label, "year": yr,
            "base_roi": base_roi, "enh_roi": enh_roi,
            "lift": lift, "base_n": b_n, "enh_n": e_n,
            "verdict": verdict,
        })
        print(f"  {test_label} {yr}: base_ROI={base_roi:+.1f}% (N={b_n}), "
              f"enhanced_ROI={enh_roi:+.1f}% (N={e_n}), lift={lift:+.1f}pp → {verdict}"
              if not np.isnan(lift) else
              f"  {test_label} {yr}: insufficient data")


# =====================================================================
# TASK 3 — WRITE FINAL STATUS NOTE
# =====================================================================
print(f"\n{'='*60}")
print("TASK 3 — FINAL STATUS NOTE")
print(f"{'='*60}")

# Build interaction summary
def interaction_summary():
    lines = []
    for test_label in ["Test A", "Test B", "Test C"]:
        pooled = [r for r in lift_results if r["test"] == test_label and r["year"] == "pooled"]
        if pooled:
            p = pooled[0]
            lines.append(f"- {test_label}: base {p['base_roi']:+.1f}% (N={p['base_n']}) → "
                         f"enhanced {p['enh_roi']:+.1f}% (N={p['enh_n']}), "
                         f"lift={p['lift']:+.1f}pp → **{p['verdict']}**"
                         if not np.isnan(p["lift"]) else
                         f"- {test_label}: insufficient data")
    return lines

int_summary = interaction_summary()

# Determine overall interaction assessment
pooled_lifts = [r for r in lift_results if r["year"] == "pooled" and not np.isnan(r.get("lift", np.nan))]
meaningful = sum(1 for r in pooled_lifts if r["verdict"] == "MEANINGFUL LIFT")
neutral = sum(1 for r in pooled_lifts if r["verdict"] == "NEUTRAL")
harmful = sum(1 for r in pooled_lifts if r["verdict"] == "HARMFUL")
thin = sum(1 for r in pooled_lifts if r["verdict"] == "THIN")

if meaningful >= 2:
    overall_interaction = "additive — adj_k_rate_last3 provides meaningful lift in multiple validated stacks"
    best_view = "interaction amplifier"
elif meaningful >= 1 and harmful == 0:
    overall_interaction = "marginally additive — lift in one stack, neutral in others"
    best_view = "scanner ingredient (needs more data for amplifier role)"
elif harmful >= 1:
    overall_interaction = "harmful in at least one stack — do not deploy as amplifier"
    best_view = "scanner ingredient only"
elif neutral >= 2:
    overall_interaction = "neutral — does not improve validated stacks"
    best_view = "scanner ingredient only"
else:
    overall_interaction = "inconclusive — sample sizes too thin for reliable assessment"
    best_view = "scanner ingredient (insufficient data for interaction assessment)"

# Append to report
report_path = BASE / "opponent_adjusted_engine_report.md"
with open(report_path, "a") as f:
    f.write("\n\n## Phase Closeout\n\n")
    f.write("### Status: INVESTIGATE\n\n")
    f.write(f"**adj_k_rate_last3**: added to scanner catalog as signal_id={next_id}\n\n")

    f.write("### Interaction Test Results\n\n")
    f.write(f"adj_k_rate_last3 top-20% threshold: {adj_k_threshold:.5f} (frozen from 2024)\n\n")

    f.write("#### Pooled (2024+2025)\n\n")
    f.write("| Cohort | N | Under% | Resid | ROI @-110 |\n")
    f.write("|--------|---|--------|-------|----------|\n")
    for r in all_results:
        if r["year"] == "pooled" and not np.isnan(r.get("under_rate", np.nan)):
            thin_flag = " (THIN)" if r["thin"] else ""
            f.write(f"| {r['label']} | {r['N']} | {r['under_rate']:.3f} | "
                    f"{r['resid']:+.3f} | {r['roi']:+.1f}%{thin_flag} |\n")
        elif r["year"] == "pooled":
            f.write(f"| {r['label']} | {r['N']} | N/A | N/A | N/A (THIN) |\n")
    f.write("\n")

    f.write("#### 2024\n\n")
    f.write("| Cohort | N | Under% | ROI @-110 |\n")
    f.write("|--------|---|--------|----------|\n")
    for r in all_results:
        if r["year"] == "2024" and not np.isnan(r.get("under_rate", np.nan)):
            thin_flag = " (THIN)" if r["thin"] else ""
            f.write(f"| {r['label']} | {r['N']} | {r['under_rate']:.3f} | {r['roi']:+.1f}%{thin_flag} |\n")
        elif r["year"] == "2024":
            f.write(f"| {r['label']} | {r['N']} | N/A | N/A (THIN) |\n")
    f.write("\n")

    f.write("#### 2025\n\n")
    f.write("| Cohort | N | Under% | ROI @-110 |\n")
    f.write("|--------|---|--------|----------|\n")
    for r in all_results:
        if r["year"] == "2025" and not np.isnan(r.get("under_rate", np.nan)):
            thin_flag = " (THIN)" if r["thin"] else ""
            f.write(f"| {r['label']} | {r['N']} | {r['under_rate']:.3f} | {r['roi']:+.1f}%{thin_flag} |\n")
        elif r["year"] == "2025":
            f.write(f"| {r['label']} | {r['N']} | N/A | N/A (THIN) |\n")
    f.write("\n")

    f.write("#### Lift Summary\n\n")
    f.write("| Test | Base ROI | Enhanced ROI | Lift | Verdict |\n")
    f.write("|------|----------|-------------|------|--------|\n")
    for r in lift_results:
        if r["year"] == "pooled":
            if not np.isnan(r.get("lift", np.nan)):
                f.write(f"| {r['test']} | {r['base_roi']:+.1f}% (N={r['base_n']}) | "
                        f"{r['enh_roi']:+.1f}% (N={r['enh_n']}) | {r['lift']:+.1f}pp | "
                        f"**{r['verdict']}** |\n")
            else:
                f.write(f"| {r['test']} | N/A | N/A | N/A | N/A |\n")
    f.write("\n")

    f.write("### Interaction Assessment\n\n")
    f.write(f"{overall_interaction}\n\n")

    f.write("### Best View of adj_k_rate_last3\n\n")
    f.write(f"**{best_view}**\n\n")

    f.write("### Recommended Next Step\n\n")
    f.write("1. Shadow monitor adj_k_rate_last3 in 2026 alongside V1 signal log\n")
    f.write("2. Re-evaluate after 200+ qualifying games with V1+adj_k overlay\n")
    f.write("3. If 2026 confirms lift in Test A (V1 + adj_k top20), promote to overlay candidate\n")
    f.write("4. Do NOT deploy as overlay until 2026 validation\n")

print(f"  Appended closeout section to report")
print(f"  Overall interaction: {overall_interaction}")
print(f"  Best view: {best_view}")
print("\nDone.")
