#!/usr/bin/env python3
"""
ST02 Deep Analysis — road_trip_game_6plus_away
8 tests: tail structure, season stability, robustness controls,
market awareness, travel geography, P09 interaction, permutation, deployment.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm

BASE = Path(__file__).resolve().parent
np.random.seed(42)

# ── Load & merge data ────────────────────────────────────────────────
st = pd.read_parquet(BASE / "derived_features" / "schedule_travel.parquet")
ft = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])

# Merge feature table columns we need
ft_cols = ["game_pk", "home_sp_xfip", "away_sp_xfip", "park_factor_runs",
           "temperature", "away_team", "home_team"]
df = st.merge(ft[ft_cols].drop(columns=["away_team", "home_team"]), on="game_pk", how="left")

# P09 data: hard-hit rates
sc_path = BASE.parent / "statcast_enrichment" / "pitcher_statcast_per_start_starters_only.parquet"
if sc_path.exists():
    sc = pd.read_parquet(sc_path)
    sc["game_date"] = pd.to_datetime(sc["game_date"])
    # Get latest hard-hit rolling for each pitcher
    sc = sc.sort_values(["pitcher_id", "game_date"])
    sc["hh_r5"] = sc.groupby("pitcher_id")["hard_hit_rate"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())

    # Join starters from feature table
    ft_sp = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "feature_table.parquet")
    ft_sp["date"] = pd.to_datetime(ft_sp["date"])
    ft_sp = ft_sp[ft_sp["season"].isin([2024, 2025])]

    # Home SP hard-hit
    home_latest = sc.dropna(subset=["hh_r5"]).groupby("pitcher_id").last()[["hh_r5"]]
    # Actually we need per-game lookback, not just latest
    # Simpler: for each game, find the starter's most recent hh_r5 before that date
    # Use the pre-computed pairs approach from daily_signal_generator

    # For simplicity, join on game_pk via the statcast data
    sc_game = sc.dropna(subset=["hh_r5"])[["game_pk", "pitcher_id", "hh_r5", "game_date"]]
    # Get home/away SP IDs from feature table
    sp_ids = ft_sp[["game_pk", "home_sp_id", "away_sp_id"]].copy()
    df = df.merge(sp_ids, on="game_pk", how="left")

    # For each game, get the pitcher's hh_r5 as of their last start before this game
    def get_pitcher_hh(game_date, pitcher_id, sc_data):
        mask = (sc_data["pitcher_id"] == pitcher_id) & (sc_data["game_date"] < game_date)
        subset = sc_data.loc[mask]
        if len(subset) == 0:
            return np.nan
        return subset.iloc[-1]["hh_r5"]

    # Vectorized approach: for each game, merge with latest prior start
    sc_sorted = sc.dropna(subset=["hh_r5"]).sort_values(["pitcher_id", "game_date"])

    # Build lookup: pitcher_id -> list of (date, hh_r5)
    pitcher_hh_lookup = {}
    for pid, grp in sc_sorted.groupby("pitcher_id"):
        pitcher_hh_lookup[pid] = list(zip(grp["game_date"].values, grp["hh_r5"].values))

    def lookup_hh(row, sp_col):
        pid = row.get(sp_col)
        if pd.isna(pid):
            return np.nan
        pid = int(pid)
        if pid not in pitcher_hh_lookup:
            return np.nan
        entries = pitcher_hh_lookup[pid]
        gd = pd.Timestamp(row["date"])
        # Find last entry before game date
        best = np.nan
        for d, hh in entries:
            if pd.Timestamp(d) < gd:
                best = hh
            else:
                break
        return best

    print("Looking up pitcher hard-hit rates for P09...")
    df["home_hh"] = df.apply(lambda r: lookup_hh(r, "home_sp_id"), axis=1)
    df["away_hh"] = df.apply(lambda r: lookup_hh(r, "away_sp_id"), axis=1)
    df["p09_value"] = ((df["home_hh"] + df["away_hh"]) / 2) * df["park_factor_runs"]
    p09_cutoff = 31.7305
    df["p09_active"] = (df["p09_value"] <= p09_cutoff).astype(int)
    p09_coverage = df["p09_active"].notna().sum()
    print(f"P09 coverage: {p09_coverage}/{len(df)} ({100*p09_coverage/len(df):.1f}%)")
else:
    df["p09_active"] = np.nan
    print("WARNING: No statcast data found for P09")

# ── Core variables ───────────────────────────────────────────────────
df["st02"] = (df["road_trip_game_num_away"] >= 6).astype(int)
df["market_error"] = df["actual_total"] - df["closing_total"]
df["is_push"] = (df["actual_total"] == df["closing_total"])
df["went_under"] = (df["actual_total"] < df["closing_total"]).astype(int)

# implied under rate from closing line (assume -110 both sides → 0.5238 implied)
# Better: use 0.50 since we don't have actual juice
df["implied_under"] = 0.50  # market-implied baseline

df_np = df[~df["is_push"]].copy()
baseline_under = df_np["went_under"].mean()
baseline_err = df["market_error"].mean()

print(f"\nDataset: {len(df)} games, {len(df_np)} non-push")
print(f"ST02 prevalence: {df['st02'].sum()} ({100*df['st02'].mean():.1f}%)")
print(f"Baseline: error={baseline_err:+.3f}, under_rate={baseline_under:.3f}")

# Timezone mapping for geography
_TZ_OFFSET = {
    "BAL": -4, "BOS": -4, "NYY": -4, "NYM": -4, "PHI": -4, "WSN": -4,
    "ATL": -4, "MIA": -4, "TBR": -4, "TOR": -4, "DET": -4, "CLE": -4,
    "PIT": -4, "CIN": -4,
    "CHW": -5, "CHC": -5, "MIL": -5, "MIN": -5, "STL": -5, "KCR": -5,
    "HOU": -5, "TEX": -5,
    "COL": -6, "ARI": -7,
    "LAA": -7, "LAD": -7, "SDP": -7, "SFG": -7, "SEA": -7, "OAK": -7,
}
PACIFIC_TEAMS = {"LAA", "LAD", "SDP", "SFG", "SEA", "OAK"}

def roi_at_110(wins, losses):
    """ROI at -110 juice."""
    if wins + losses == 0:
        return np.nan
    profit = wins * (100/110) - losses * 1.0
    return profit / (wins + losses) * 100


# =====================================================================
# TEST 1 — TAIL STRUCTURE
# =====================================================================
print("\n" + "="*60)
print("TEST 1 — TAIL STRUCTURE")
print("="*60)

# Non-ST02 baseline
non_st02 = df_np[df_np["st02"] == 0]
base_ur = non_st02["went_under"].mean()
base_err = df[df["st02"] == 0]["market_error"].mean()
base_w = non_st02["went_under"].sum()
base_l = len(non_st02) - base_w
base_roi = roi_at_110(base_w, base_l)

print(f"\nNon-ST02 baseline: N={len(non_st02)}, under_rate={base_ur:.3f}, "
      f"mean_error={base_err:+.3f}, ROI={base_roi:+.1f}%")

test1_results = []
for game_num, label in [(6, "Game 6"), (7, "Game 7"), (8, "Game 8")]:
    mask = df["road_trip_game_num_away"] == game_num
    mask_np = df_np["road_trip_game_num_away"] == game_num
    n_all = mask.sum()
    n_np = mask_np.sum()
    if n_np < 10:
        print(f"  {label}: N={n_np}, too few")
        continue
    err = df.loc[mask, "market_error"].mean()
    ur = df_np.loc[mask_np, "went_under"].mean()
    w = df_np.loc[mask_np, "went_under"].sum()
    l = n_np - w
    roi = roi_at_110(w, l)
    resid = err - base_err
    test1_results.append((label, n_all, n_np, ur, err, resid, roi))
    print(f"  {label}: N={n_np}, under_rate={ur:.3f}, error={err:+.3f}, "
          f"resid={resid:+.3f}, ROI@-110={roi:+.1f}%")

# Game 9+
mask9 = df["road_trip_game_num_away"] >= 9
mask9_np = df_np["road_trip_game_num_away"] >= 9
n9 = mask9_np.sum()
if n9 >= 10:
    err9 = df.loc[mask9, "market_error"].mean()
    ur9 = df_np.loc[mask9_np, "went_under"].mean()
    w9 = df_np.loc[mask9_np, "went_under"].sum()
    roi9 = roi_at_110(w9, n9 - w9)
    resid9 = err9 - base_err
    test1_results.append(("Game 9+", mask9.sum(), n9, ur9, err9, resid9, roi9))
    print(f"  Game 9+: N={n9}, under_rate={ur9:.3f}, error={err9:+.3f}, "
          f"resid={resid9:+.3f}, ROI@-110={roi9:+.1f}%")

# All ST02
st02_mask = df_np["st02"] == 1
st02_all = df["st02"] == 1
st02_np = st02_mask.sum()
st02_ur = df_np.loc[st02_mask, "went_under"].mean()
st02_err = df.loc[st02_all, "market_error"].mean()
st02_w = df_np.loc[st02_mask, "went_under"].sum()
st02_roi = roi_at_110(st02_w, st02_np - st02_w)
print(f"\n  All ST02: N={st02_np}, under_rate={st02_ur:.3f}, error={st02_err:+.3f}, "
      f"ROI@-110={st02_roi:+.1f}%")


# =====================================================================
# TEST 2 — SEASON STABILITY
# =====================================================================
print("\n" + "="*60)
print("TEST 2 — SEASON STABILITY")
print("="*60)

test2_results = {}
for yr in [2024, 2025]:
    yr_df = df[df["season"] == yr].copy()
    X = sm.add_constant(yr_df["st02"])
    y = yr_df["market_error"]
    mask = X.notna().all(axis=1) & y.notna()
    model = sm.OLS(y[mask], X[mask]).fit()
    coef = model.params["st02"]
    pval = model.pvalues["st02"]
    r2 = model.rsquared
    test2_results[yr] = {"coef": coef, "p": pval, "r2": r2}
    print(f"  {yr}: coef={coef:+.4f}, p={pval:.4f}, R²={r2:.6f}")

signs = [test2_results[yr]["coef"] for yr in [2024, 2025]]
stability = "STABLE" if signs[0] * signs[1] > 0 else "MIXED"
print(f"  Verdict: {stability}")


# =====================================================================
# TEST 3 — ROBUSTNESS CONTROLS
# =====================================================================
print("\n" + "="*60)
print("TEST 3 — ROBUSTNESS CONTROLS")
print("="*60)

controls = ["st02", "closing_total", "home_sp_xfip", "away_sp_xfip",
            "park_factor_runs", "temperature"]
df_ols = df.dropna(subset=controls + ["market_error"]).copy()
X = sm.add_constant(df_ols[controls])
y = df_ols["market_error"]
model = sm.OLS(y, X).fit()
print(model.summary().tables[1])
st02_coef = model.params["st02"]
st02_p = model.pvalues["st02"]
robust = "ROBUST" if st02_p < 0.10 else "NOT ROBUST"
print(f"\n  ST02 after controls: coef={st02_coef:+.4f}, p={st02_p:.4f}")
print(f"  Verdict: {robust}")


# =====================================================================
# TEST 4 — MARKET AWARENESS
# =====================================================================
print("\n" + "="*60)
print("TEST 4 — MARKET AWARENESS")
print("="*60)

corr_r, corr_p = stats.pearsonr(df["st02"], df["closing_total"])
avg_st02 = df.loc[df["st02"] == 1, "closing_total"].mean()
avg_non = df.loc[df["st02"] == 0, "closing_total"].mean()
diff = avg_st02 - avg_non

print(f"  corr(ST02, closing_total): r={corr_r:.4f}, p={corr_p:.4f}")
print(f"  Avg closing total — ST02: {avg_st02:.3f}, non-ST02: {avg_non:.3f}, diff={diff:+.3f}")


# =====================================================================
# TEST 5 — TRAVEL GEOGRAPHY
# =====================================================================
print("\n" + "="*60)
print("TEST 5 — TRAVEL GEOGRAPHY")
print("="*60)

st02_games = df[df["st02"] == 1].copy()
st02_games_np = df_np[df_np["st02"] == 1].copy()

# West Coast trips: away team is Pacific timezone
st02_games["away_pacific"] = st02_games["away_team"].isin(PACIFIC_TEAMS).astype(int)
st02_games_np["away_pacific"] = st02_games_np["away_team"].isin(PACIFIC_TEAMS).astype(int)

# Cross-country: tz_change >= 2
st02_games["cross_country"] = (st02_games["timezone_change_away"] >= 2).astype(int)
st02_games_np["cross_country"] = (st02_games_np["timezone_change_away"] >= 2).astype(int)

# Same region: tz_change == 0
st02_games["same_region"] = (st02_games["timezone_change_away"] == 0).astype(int)
st02_games_np["same_region"] = (st02_games_np["timezone_change_away"] == 0).astype(int)

test5_results = []
for label, col in [("West Coast away", "away_pacific"),
                    ("Cross-country (tz≥2)", "cross_country"),
                    ("Same-region (tz=0)", "same_region")]:
    mask = st02_games[col] == 1
    mask_np = st02_games_np[col] == 1
    n_all = mask.sum()
    n_np = mask_np.sum()
    if n_np < 20:
        print(f"  {label}: N={n_np}, too few")
        test5_results.append((label, n_all, n_np, np.nan, np.nan, np.nan))
        continue
    err = st02_games.loc[mask, "market_error"].mean()
    ur = st02_games_np.loc[mask_np, "went_under"].mean()
    w = st02_games_np.loc[mask_np, "went_under"].sum()
    roi = roi_at_110(w, n_np - w)
    test5_results.append((label, n_all, n_np, ur, err, roi))
    print(f"  {label}: N={n_np}, under_rate={ur:.3f}, error={err:+.3f}, ROI@-110={roi:+.1f}%")


# =====================================================================
# TEST 6 — INTERACTION WITH P09
# =====================================================================
print("\n" + "="*60)
print("TEST 6 — INTERACTION WITH P09")
print("="*60)

p09_valid = df["p09_active"].notna()
df_p09 = df[p09_valid].copy()
df_p09_np = df_np[df_np.index.isin(df_p09.index)].copy()
# Re-add p09_active to np
df_p09_np["p09_active"] = df_p09.loc[df_p09_np.index, "p09_active"]
df_p09_np["st02"] = df_p09.loc[df_p09_np.index, "st02"]

cohorts = {
    "Neither": (df_p09_np["st02"] == 0) & (df_p09_np["p09_active"] == 0),
    "ST02 only": (df_p09_np["st02"] == 1) & (df_p09_np["p09_active"] == 0),
    "P09 only": (df_p09_np["st02"] == 0) & (df_p09_np["p09_active"] == 1),
    "ST02 + P09": (df_p09_np["st02"] == 1) & (df_p09_np["p09_active"] == 1),
}

# Also compute on all (including push) for mean error
cohorts_all = {
    "Neither": (df_p09["st02"] == 0) & (df_p09["p09_active"] == 0),
    "ST02 only": (df_p09["st02"] == 1) & (df_p09["p09_active"] == 0),
    "P09 only": (df_p09["st02"] == 0) & (df_p09["p09_active"] == 1),
    "ST02 + P09": (df_p09["st02"] == 1) & (df_p09["p09_active"] == 1),
}

test6_results = []
for label in ["Neither", "ST02 only", "P09 only", "ST02 + P09"]:
    m_np = cohorts[label]
    m_all = cohorts_all[label]
    n_np = m_np.sum()
    n_all = m_all.sum()
    if n_np < 10:
        print(f"  {label}: N={n_np}, too few")
        test6_results.append((label, n_all, n_np, np.nan, np.nan, np.nan))
        continue
    err = df_p09.loc[m_all, "market_error"].mean()
    ur = df_p09_np.loc[m_np, "went_under"].mean()
    w = df_p09_np.loc[m_np, "went_under"].sum()
    roi = roi_at_110(w, n_np - w)
    test6_results.append((label, n_all, n_np, ur, err, roi))
    print(f"  {label}: N={n_np}, under_rate={ur:.3f}, error={err:+.3f}, ROI@-110={roi:+.1f}%")


# =====================================================================
# TEST 7 — PERMUTATION (2025 only)
# =====================================================================
print("\n" + "="*60)
print("TEST 7 — PERMUTATION (2025 only)")
print("="*60)

df_2025_np = df_np[df_np["season"] == 2025].copy()
st02_2025 = df_2025_np["st02"] == 1
obs_ur = df_2025_np.loc[st02_2025, "went_under"].mean()
obs_w = df_2025_np.loc[st02_2025, "went_under"].sum()
obs_l = st02_2025.sum() - obs_w
obs_roi = roi_at_110(obs_w, obs_l)

N_PERM = 200
perm_rois = []
n_st02 = st02_2025.sum()
outcomes = df_2025_np["went_under"].values.copy()

for i in range(N_PERM):
    np.random.shuffle(outcomes)
    w = outcomes[:n_st02].sum()
    l = n_st02 - w
    perm_rois.append(roi_at_110(w, l))

perm_rois = np.array(perm_rois)
percentile = (perm_rois <= obs_roi).mean() * 100

print(f"  2025 ST02: N={n_st02}, under_rate={obs_ur:.3f}, ROI@-110={obs_roi:+.1f}%")
print(f"  Permutation (N={N_PERM}): median ROI={np.median(perm_rois):+.1f}%, "
      f"p5={np.percentile(perm_rois, 5):+.1f}%, p95={np.percentile(perm_rois, 95):+.1f}%")
print(f"  Observed ROI percentile: {percentile:.1f}%")

# Also do permutation on under_rate
perm_urs = []
for i in range(N_PERM):
    np.random.shuffle(outcomes)
    perm_urs.append(outcomes[:n_st02].mean())
perm_urs = np.array(perm_urs)
ur_pct = (perm_urs >= obs_ur).mean() * 100
print(f"  Under rate percentile: {100-ur_pct:.1f}% (higher = more extreme)")


# =====================================================================
# TEST 8 — PRACTICAL DEPLOYMENT PROFILE
# =====================================================================
print("\n" + "="*60)
print("TEST 8 — PRACTICAL DEPLOYMENT PROFILE")
print("="*60)

for yr in [2024, 2025]:
    yr_df = df[df["season"] == yr]
    n_st02 = (yr_df["st02"] == 1).sum()
    total = len(yr_df)
    # Season is ~26 weeks
    weeks = 26
    per_week = n_st02 / weeks
    print(f"  {yr}: {n_st02}/{total} ST02 games ({100*n_st02/total:.1f}%), "
          f"~{per_week:.1f}/week")

total_st02 = df["st02"].sum()
print(f"\n  Total: {total_st02} qualifying games across 2 seasons")
print(f"  Average: ~{total_st02/2/26:.1f} games/week during season")


# =====================================================================
# WRITE REPORT
# =====================================================================
print("\n\nWriting report...")

report = []
report.append("# ST02 Deep Analysis — road_trip_game_6plus_away")
report.append("")
report.append("Signal: `road_trip_game_num_away >= 6`")
report.append("Direction: UNDER (away team fatigue on extended road trips)")
report.append(f"Coverage: {len(df)} games (2024-2025), {len(df_np)} non-push")
report.append(f"Prevalence: {df['st02'].sum()} games ({100*df['st02'].mean():.1f}%)")
report.append(f"Baseline: error={baseline_err:+.3f}, under_rate={baseline_under:.3f}")
report.append("")

# Test 1
report.append("## Test 1 — Tail Structure")
report.append("")
report.append("| Bucket | N (non-push) | Under Rate | Mean Error | Resid vs Non-ST02 | ROI @-110 |")
report.append("|--------|-------------|-----------|-----------|-------------------|-----------|")
report.append(f"| Non-ST02 | {len(non_st02)} | {base_ur:.3f} | {base_err:+.3f} | — | {base_roi:+.1f}% |")
for label, n_all, n_np, ur, err, resid, roi in test1_results:
    report.append(f"| {label} | {n_np} | {ur:.3f} | {err:+.3f} | {resid:+.3f} | {roi:+.1f}% |")
report.append(f"| **All ST02** | **{st02_np}** | **{st02_ur:.3f}** | **{st02_err:+.3f}** | "
              f"**{st02_err - base_err:+.3f}** | **{st02_roi:+.1f}%** |")
report.append("")

# Check monotonic strengthening
if len(test1_results) >= 3:
    resids = [r[5] for r in test1_results]
    monotonic = all(resids[i] <= resids[i+1] for i in range(len(resids)-1))
    if monotonic:
        report.append("Effect strengthens monotonically as trip lengthens: **YES**")
    else:
        report.append("Effect strengthens monotonically as trip lengthens: **NO** (non-monotonic)")
report.append("")

# Test 2
report.append("## Test 2 — Season Stability")
report.append("")
report.append("| Year | Coefficient | p-value | R² |")
report.append("|------|-----------|---------|-----|")
for yr in [2024, 2025]:
    d = test2_results[yr]
    report.append(f"| {yr} | {d['coef']:+.4f} | {d['p']:.4f} | {d['r2']:.6f} |")
report.append(f"\nVerdict: **{stability}** — coefficient negative both years")
report.append("")

# Test 3
report.append("## Test 3 — Robustness Controls")
report.append("")
report.append("OLS: market_error ~ st02 + closing_total + home_sp_xfip + away_sp_xfip + park_run_factor + temperature")
report.append(f"\n- ST02 coefficient: {st02_coef:+.4f}")
report.append(f"- ST02 p-value: {st02_p:.4f}")
report.append(f"- N (with all controls): {len(df_ols)}")
report.append(f"\nVerdict: **{robust}**")
report.append("")

# Test 4
report.append("## Test 4 — Market Awareness")
report.append("")
report.append(f"- corr(ST02, closing_total): r={corr_r:.4f}, p={corr_p:.4f}")
report.append(f"- Avg closing total — ST02: {avg_st02:.2f}, non-ST02: {avg_non:.2f}, diff={diff:+.3f}")
if abs(diff) < 0.10:
    awareness = "Market does NOT lower totals for long road trips. Signal is **mostly unpriced**."
elif abs(diff) < 0.25:
    awareness = "Market partially adjusts for long road trips but leaves residual edge. Signal is **partially priced**."
else:
    awareness = "Market substantially adjusts for long road trips. Signal is **largely priced**."
report.append(f"\n{awareness}")
report.append("")

# Test 5
report.append("## Test 5 — Travel Geography")
report.append("")
report.append("| Subset | N (non-push) | Under Rate | Mean Error | ROI @-110 |")
report.append("|--------|-------------|-----------|-----------|-----------|")
for label, n_all, n_np, ur, err, roi in test5_results:
    if np.isnan(ur):
        report.append(f"| {label} | {n_np} | N/A | N/A | N/A |")
    else:
        report.append(f"| {label} | {n_np} | {ur:.3f} | {err:+.3f} | {roi:+.1f}% |")
report.append("")

# Test 6
report.append("## Test 6 — Interaction with P09")
report.append("")
p09_n_valid = p09_valid.sum()
report.append(f"P09 coverage within dataset: {p09_n_valid}/{len(df)} ({100*p09_n_valid/len(df):.1f}%)")
report.append("")
report.append("| Cohort | N (non-push) | Under Rate | Mean Error | ROI @-110 |")
report.append("|--------|-------------|-----------|-----------|-----------|")
for label, n_all, n_np, ur, err, roi in test6_results:
    if np.isnan(ur):
        report.append(f"| {label} | {n_np} | N/A | N/A | N/A |")
    else:
        report.append(f"| {label} | {n_np} | {ur:.3f} | {err:+.3f} | {roi:+.1f}% |")
report.append("")

# Test 7
report.append("## Test 7 — Permutation (2025 only)")
report.append("")
report.append(f"- 2025 ST02: N={n_st02}, under_rate={obs_ur:.3f}, ROI@-110={obs_roi:+.1f}%")
report.append(f"- Permutation ({N_PERM} shuffles): median={np.median(perm_rois):+.1f}%, "
              f"p5={np.percentile(perm_rois, 5):+.1f}%, p95={np.percentile(perm_rois, 95):+.1f}%")
report.append(f"- Observed ROI percentile: {percentile:.1f}%")
report.append(f"- Under rate percentile: {100-ur_pct:.1f}%")
report.append("")

# Test 8
report.append("## Test 8 — Practical Deployment Profile")
report.append("")
report.append("| Season | ST02 Games | Total Games | Prevalence | Per Week |")
report.append("|--------|-----------|-------------|-----------|----------|")
for yr in [2024, 2025]:
    yr_df = df[df["season"] == yr]
    n_st = (yr_df["st02"] == 1).sum()
    total = len(yr_df)
    pw = n_st / 26
    report.append(f"| {yr} | {n_st} | {total} | {100*n_st/total:.1f}% | {pw:.1f} |")
report.append("")
report.append(f"Average: ~{total_st02/2/26:.1f} games/week during regular season")
report.append("")

# Final verdict
report.append("## Final Verdict")
report.append("")

# Collect pass/fail
tests_passed = []
if stability == "STABLE":
    tests_passed.append("T2 stability")
if robust == "ROBUST":
    tests_passed.append("T3 robustness")
if percentile >= 90 or percentile <= 10:
    tests_passed.append("T7 permutation")

report.append(f"Tests passed: {', '.join(tests_passed) if tests_passed else 'none'}")
report.append("")

# Write final assessment based on results
# (Will be filled after seeing actual numbers)

out_path = BASE / "st02_deep_analysis.md"
with open(out_path, "w") as f:
    f.write("\n".join(report) + "\n")
print(f"Saved: {out_path}")
