#!/usr/bin/env python3
"""
Run Volatility Score — Full research model.
Steps 0-7: audit, build features, composite scores, test, stability, V1 independence, permutation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
V2OFF = BASE.parent / "opponent_adjusted_engine_v2"
STATCAST = BASE.parent / "statcast_enrichment"
V1ENG = BASE.parent / "opponent_adjusted_engine"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# =====================================================================
# STEP 0 — SOURCE AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — SOURCE AUDIT")
print("=" * 60)

ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])
sim_v1 = pd.read_parquet(SIM / "phase5_sim_results.parquet")
sim_v1["date"] = pd.to_datetime(sim_v1["date"])
sc = pd.read_parquet(STATCAST / "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])
bf = pd.read_parquet(SIM / "bullpen_features.parquet")
bf["date"] = pd.to_datetime(bf["date"])
v2_off = pd.read_parquet(V2OFF / "offense_expectation_table.parquet")
v2_off["date"] = pd.to_datetime(v2_off["date"])
ps = pd.read_parquet(V1ENG / "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])

audit = [
    "# Source Audit — Run Volatility Model",
    "",
    f"| File | Rows | Purpose |",
    f"|------|------|---------|",
    f"| sim/data/feature_table.parquet | {len(ft)} | SP xFIP/K%/BB%, BP xFIP, park, weather |",
    f"| sim/data/bet_results.parquet | {len(br)} | Closing lines, outcomes |",
    f"| sim/data/phase5_sim_results.parquet | {len(sim_v1)} | V1 p_under |",
    f"| research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | {len(sc)} | HH%, barrel%, whiff% per start |",
    f"| sim/data/bullpen_features.parquet | {len(bf)} | BP pitches last 1/3 games |",
    f"| research/opponent_adjusted_engine_v2/offense_expectation_table.parquet | {len(v2_off)} | Team contact/BB/runs rolling |",
    f"| research/opponent_adjusted_engine/pitcher_start_adjusted_metrics.parquet | {len(ps)} | Pitcher K/BB/IP/ER per start |",
    "",
    "## Feature availability",
    "- SP bb_pct, k_pct, xfip: YES (feature_table)",
    "- SP hard_hit, barrel, whiff: YES (Statcast per-start, ~92% coverage)",
    "- BP xfip: YES (feature_table)",
    "- BP workload: YES (bullpen_features — pitches last 3 games)",
    "- Lineup contact_rate, bb_rate: YES (V2 offense table)",
    "- Park factors, temperature, wind: YES (feature_table)",
    "- SP fb_rate/gb_rate: NOT AVAILABLE (all NaN)",
    "- Strand rate, ISO, BABIP: NOT AVAILABLE directly",
    "- Will use proxies where feasible",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1 — BUILD VARIANCE TARGET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — VARIANCE TARGET")
print("=" * 60)

df = ft[ft["season"].isin([2024, 2025])].copy()
df = df.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
              on="game_pk", how="inner")
df.rename(columns={"close_total": "closing_total"}, inplace=True)
df = df.merge(sim_v1[["game_pk", "p_under", "p_over"]], on="game_pk", how="left")

df["market_residual_runs"] = df["actual_total"] - df["closing_total"]
df["over_flag"] = (df["actual_total"] > df["closing_total"]).astype(int)
df["is_push"] = (df["actual_total"] == df["closing_total"])
df["absolute_deviation"] = np.abs(df["actual_total"] - df["closing_total"])

print(f"  Games: {len(df)}")
print(f"  Over rate: {df[~df.is_push]['over_flag'].mean():.3f}")
print(f"  Mean abs deviation: {df['absolute_deviation'].mean():.2f}")

# =====================================================================
# STEP 2 — BUILD VOLATILITY FEATURES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — VOLATILITY FEATURES")
print("=" * 60)

# ── Pitcher volatility (from feature_table) ──────────────────────────
df["combined_bb_rate"] = (df["home_sp_bb_pct"] + df["away_sp_bb_pct"]) / 2
df["combined_k_rate"] = (df["home_sp_k_pct"] + df["away_sp_k_pct"]) / 2
df["combined_xfip"] = (df["home_sp_xfip"] + df["away_sp_xfip"]) / 2

# ── Pitcher Statcast per-start rolling (hard-hit, whiff, barrel) ─────
# Build rolling 5-start means per pitcher, then join home/away
sc_sorted = sc.sort_values(["pitcher_id", "game_date"])
for col in ["hard_hit_rate", "barrel_rate", "whiff_rate"]:
    sc_sorted[f"{col}_r5"] = sc_sorted.groupby("pitcher_id")[col].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Latest per-pitcher lookback
def build_pitcher_lookback(sc_data, ft_data, sp_id_col, prefix):
    """For each game, find the pitcher's most recent rolling stat."""
    # Build lookup dict: pitcher_id -> sorted list of (date, stat_dict)
    lookup = {}
    for pid, grp in sc_data.dropna(subset=["hard_hit_rate_r5"]).groupby("pitcher_id"):
        lookup[pid] = list(zip(
            grp["game_date"].values,
            grp["hard_hit_rate_r5"].values,
            grp["barrel_rate_r5"].values,
            grp["whiff_rate_r5"].values,
        ))

    hh_vals, br_vals, wh_vals = [], [], []
    for _, row in ft_data.iterrows():
        pid = row.get(sp_id_col)
        gd = pd.Timestamp(row["date"])
        if pd.isna(pid) or int(pid) not in lookup:
            hh_vals.append(np.nan); br_vals.append(np.nan); wh_vals.append(np.nan)
            continue
        entries = lookup[int(pid)]
        best_hh = best_br = best_wh = np.nan
        for d, hh, barr, wh in entries:
            if pd.Timestamp(d) < gd:
                best_hh, best_br, best_wh = hh, barr, wh
            else:
                break
        hh_vals.append(best_hh); br_vals.append(best_br); wh_vals.append(best_wh)

    ft_data[f"{prefix}_hard_hit_r5"] = hh_vals
    ft_data[f"{prefix}_barrel_r5"] = br_vals
    ft_data[f"{prefix}_whiff_r5"] = wh_vals

print("  Building pitcher Statcast lookbacks...")
build_pitcher_lookback(sc_sorted, df, "home_sp_id", "home_sp")
build_pitcher_lookback(sc_sorted, df, "away_sp_id", "away_sp")

df["combined_hard_hit"] = (df["home_sp_hard_hit_r5"] + df["away_sp_hard_hit_r5"]) / 2
df["combined_barrel"] = (df["home_sp_barrel_r5"] + df["away_sp_barrel_r5"]) / 2
df["combined_whiff"] = (df["home_sp_whiff_r5"] + df["away_sp_whiff_r5"]) / 2

# Interaction: bb × hard_hit
df["bb_x_hard_hit"] = df["combined_bb_rate"] * df["combined_hard_hit"]

# ── Pitcher ERA recent form (from pitcher starts) ───────────��────────
ps_sorted = ps.sort_values(["pitcher_id", "date"])
ps_sorted["era_r3"] = ps_sorted.groupby("pitcher_id").apply(
    lambda g: g["er"].shift(1).rolling(3, min_periods=2).sum() /
              g["ip"].shift(1).rolling(3, min_periods=2).sum() * 9,
    include_groups=False
).reset_index(level=0, drop=True)
ps_sorted["era_season"] = ps_sorted.groupby(["pitcher_id", "season"]).apply(
    lambda g: g["er"].shift(1).expanding(min_periods=3).sum() /
              g["ip"].shift(1).expanding(min_periods=3).sum() * 9,
    include_groups=False
).reset_index(level=[0,1], drop=True)

# ERA spike = recent - season (positive = deteriorating)
ps_sorted["era_spike"] = ps_sorted["era_r3"] - ps_sorted["era_season"]

# Join to games
for side, sp_col, prefix in [("home", "home_sp_id", "home_sp"),
                               ("away", "away_sp_id", "away_sp")]:
    side_ps = ps_sorted[ps_sorted["side"] == side][["game_pk", "era_spike", "era_r3"]].copy()
    side_ps.columns = ["game_pk", f"{prefix}_era_spike", f"{prefix}_era_r3"]
    df = df.merge(side_ps, on="game_pk", how="left")

df["combined_era_spike"] = (df["home_sp_era_spike"].fillna(0) + df["away_sp_era_spike"].fillna(0)) / 2

# ── Bullpen volatility ─────────────────────────────────────────────��─
df["combined_bp_xfip"] = (df["home_bp_xfip"] + df["away_bp_xfip"]) / 2

# BP workload from bullpen_features
bf_home = bf.rename(columns={"team": "home_team",
                               "bullpen_pitches_last_3_games": "home_bp_pitches_3g"})[
    ["game_pk", "home_team", "home_bp_pitches_3g"]]
bf_away = bf.rename(columns={"team": "away_team",
                               "bullpen_pitches_last_3_games": "away_bp_pitches_3g"})[
    ["game_pk", "away_team", "away_bp_pitches_3g"]]
df = df.merge(bf_home, on=["game_pk", "home_team"], how="left")
df = df.merge(bf_away, on=["game_pk", "away_team"], how="left")
df["combined_bp_workload"] = (df["home_bp_pitches_3g"].fillna(0) + df["away_bp_pitches_3g"].fillna(0)) / 2

# ── Contact environment (from V2 offense table) ─────────────────────
# Home team offense → home lineup facing away pitcher
home_off = v2_off[v2_off["side"] == "home"][
    ["game_pk", "team_contact_rate", "team_bb_rate", "team_runs_per_game"]].rename(
    columns={"team_contact_rate": "home_lineup_contact",
             "team_bb_rate": "home_lineup_bb",
             "team_runs_per_game": "home_lineup_runs"})
away_off = v2_off[v2_off["side"] == "away"][
    ["game_pk", "team_contact_rate", "team_bb_rate", "team_runs_per_game"]].rename(
    columns={"team_contact_rate": "away_lineup_contact",
             "team_bb_rate": "away_lineup_bb",
             "team_runs_per_game": "away_lineup_runs"})
df = df.merge(home_off, on="game_pk", how="left")
df = df.merge(away_off, on="game_pk", how="left")

df["combined_lineup_contact"] = (df["home_lineup_contact"] + df["away_lineup_contact"]) / 2
df["combined_lineup_bb"] = (df["home_lineup_bb"] + df["away_lineup_bb"]) / 2

# contact × bb interaction (patient + contact = long innings)
df["contact_x_bb"] = df["combined_lineup_contact"] * df["combined_lineup_bb"]

# ── Park × environment ───────────────────────────────────────────────
df["park_hr_factor_scaled"] = df["park_factor_hr"] / 100

# wind_factor_effective already in dataset (positive = out = more HR)
# Temperature effect
df["temp_factor"] = (df["temperature"] - 70) / 10  # centered at 70°F

# ── Starter short outing risk ────────────────────────────────────────
# avg IP last 5 starts
ps_ip = ps_sorted.copy()
ps_ip["ip_r5"] = ps_ip.groupby("pitcher_id")["ip"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())
for side, sp_col, prefix in [("home", "home_sp_id", "home_sp"),
                               ("away", "away_sp_id", "away_sp")]:
    side_ip = ps_ip[ps_ip["side"] == side][["game_pk", "ip_r5"]].copy()
    side_ip.columns = ["game_pk", f"{prefix}_ip_r5"]
    df = df.merge(side_ip, on="game_pk", how="left")

df["combined_short_starter_risk"] = (
    (5 - df["home_sp_ip_r5"].fillna(5)).clip(lower=0) +
    (5 - df["away_sp_ip_r5"].fillna(5)).clip(lower=0)
) / 2

# Short starter × weak bullpen interaction
df["short_starter_x_bp"] = df["combined_short_starter_risk"] * df["combined_bp_xfip"]

# ── Feature summary ──────────────────────────────────────────────────
FEATURES = [
    "combined_bb_rate",
    "combined_hard_hit",
    "bb_x_hard_hit",
    "combined_whiff",       # low whiff = more contact = more variance (inverted)
    "combined_barrel",
    "combined_era_spike",
    "combined_bp_xfip",
    "combined_bp_workload",
    "combined_lineup_contact",
    "combined_lineup_bb",
    "contact_x_bb",
    "park_hr_factor_scaled",
    "wind_factor_effective",
    "temp_factor",
    "combined_short_starter_risk",
    "short_starter_x_bp",
]

print("  Feature coverage (2024+2025):")
for feat in FEATURES:
    n = df[feat].notna().sum()
    print(f"    {feat}: {n}/{len(df)} ({100*n/len(df):.1f}%)")

# =====================================================================
# STEP 3 — COMPOSITE SCORES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — COMPOSITE VOLATILITY SCORES")
print("=" * 60)

# Use games with all features available
df_model = df.dropna(subset=FEATURES + ["absolute_deviation"]).copy()
print(f"  Games with all features: {len(df_model)}/{len(df)}")

# Split for z-score fitting
df_2024 = df_model[df_model["season"] == 2024]
df_2025 = df_model[df_model["season"] == 2025]

# MODEL A — Equal-weight z-score composite
# Fit scaler on 2024, apply to both
scaler = StandardScaler()
scaler.fit(df_2024[FEATURES])

# Invert whiff (low whiff = more variance)
# Actually, build composite where HIGH = more variance:
# High bb, high hard_hit, high barrel, high era_spike, high bp_xfip, high bp_workload,
# high lineup_contact, high lineup_bb, high park_hr, high wind_out, high temp, high short_starter
# LOW whiff = more variance → invert
INVERT = ["combined_whiff"]  # negate these before summing

z_scores = pd.DataFrame(scaler.transform(df_model[FEATURES]), columns=FEATURES, index=df_model.index)
for col in INVERT:
    z_scores[col] = -z_scores[col]

df_model["vol_score_A"] = z_scores.sum(axis=1)

# MODEL B — OLS-weighted
X = sm.add_constant(df_model[FEATURES])
y = df_model["absolute_deviation"]
ols_model = sm.OLS(y, X).fit()
df_model["vol_score_B"] = ols_model.predict(X)

print(f"\n  MODEL A (equal-weight z-score):")
print(f"    R² vs abs_deviation: {df_model['vol_score_A'].corr(df_model['absolute_deviation'])**2:.4f}")
print(f"  MODEL B (OLS-weighted):")
print(f"    R² vs abs_deviation: {ols_model.rsquared:.4f}")
print(f"    Adj R²: {ols_model.rsquared_adj:.4f}")
print(f"    Sig features (p<0.10): {sum(ols_model.pvalues[1:] < 0.10)}/{len(FEATURES)}")

# Print OLS coefficients
print(f"\n  OLS coefficients:")
for feat in FEATURES:
    coef = ols_model.params[feat]
    pval = ols_model.pvalues[feat]
    sig = "*" if pval < 0.10 else " "
    print(f"    {feat:35s}: {coef:+.4f} (p={pval:.4f}){sig}")

# Also score the full dataset (for games with missing features, score is NaN)
z_full = pd.DataFrame(scaler.transform(df[FEATURES].fillna(df_2024[FEATURES].mean())),
                       columns=FEATURES, index=df.index)
for col in INVERT:
    z_full[col] = -z_full[col]
df["vol_score_A"] = z_full.sum(axis=1)
# Only set for games with all features
df.loc[~df.index.isin(df_model.index), "vol_score_A"] = np.nan
df["vol_score_B"] = np.nan
df.loc[df_model.index, "vol_score_B"] = df_model["vol_score_B"]

# ── Decile comparison ────────────────────────────────────────────────
df_np = df[~df["is_push"]].copy()

for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    valid = df_model[score_col].notna()
    valid_np = df_np[score_col].notna()
    sub = df_np[valid_np].copy()
    sub["decile"] = pd.qcut(sub[score_col], 10, labels=False, duplicates="drop")

    print(f"\n  {model_name} decile structure:")
    print(f"  {'Dec':>4} {'N':>5} {'Score':>8} {'Over%':>7} {'ROI':>7}")
    for dec in sorted(sub["decile"].unique()):
        d = sub[sub["decile"] == dec]
        n = len(d)
        mean_s = d[score_col].mean()
        over_rate = d["over_flag"].mean()
        w = d["over_flag"].sum()
        roi = roi_110(w, n - w)
        print(f"  {dec:>4d} {n:>5d} {mean_s:>8.2f} {over_rate:>7.3f} {roi:>+7.1f}%")

# =====================================================================
# STEP 4 — TEST OVER PREDICTION
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — OVER PREDICTION TESTS")
print("=" * 60)

# Use MODEL A and MODEL B
for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    valid_np = df_np[score_col].notna()
    sub = df_np[valid_np].copy()

    print(f"\n  --- {model_name} ---")
    for label, lo_pct in [("top_10", 90), ("top_20", 80), ("top_30", 70)]:
        thresh = sub[score_col].quantile(lo_pct / 100)
        mask = sub[score_col] > thresh
        n = mask.sum()
        over_rate = sub.loc[mask, "over_flag"].mean()
        w = sub.loc[mask, "over_flag"].sum()
        roi = roi_110(w, n - w)
        print(f"  {label}: N={n}, over%={over_rate:.3f}, ROI={roi:+.1f}%")

    # Split by closing total
    for cl_label, cl_lo, cl_hi in [("close>=8.5", 8.5, 99), ("close<=7.5", 0, 7.5)]:
        cl_mask = valid_np & (df_np["closing_total"] >= cl_lo) & (df_np["closing_total"] <= cl_hi)
        cl_sub = df_np[cl_mask].copy()
        if len(cl_sub) < 50:
            continue
        thresh = cl_sub[score_col].quantile(0.80)
        mask = cl_sub[score_col] > thresh
        n = mask.sum()
        if n < 20:
            continue
        over_rate = cl_sub.loc[mask, "over_flag"].mean()
        w = cl_sub.loc[mask, "over_flag"].sum()
        roi = roi_110(w, n - w)
        print(f"  top_20 + {cl_label}: N={n}, over%={over_rate:.3f}, ROI={roi:+.1f}%")

# =====================================================================
# STEP 5 — SEASON STABILITY
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — SEASON STABILITY")
print("=" * 60)

for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    print(f"\n  --- {model_name} ---")
    for yr in [2024, 2025]:
        yr_np = df_np[(df_np["season"] == yr) & df_np[score_col].notna()]
        if len(yr_np) < 100:
            print(f"  {yr}: insufficient data")
            continue
        thresh = yr_np[score_col].quantile(0.80)
        mask = yr_np[score_col] > thresh
        n = mask.sum()
        over_rate = yr_np.loc[mask, "over_flag"].mean()
        w = yr_np.loc[mask, "over_flag"].sum()
        roi = roi_110(w, n - w)
        print(f"  {yr}: top_20 N={n}, over%={over_rate:.3f}, ROI={roi:+.1f}%")

# =====================================================================
# STEP 6 — INDEPENDENCE FROM V1
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — V1 INDEPENDENCE")
print("=" * 60)

for score_col, model_name in [("vol_score_A", "MODEL_A"), ("vol_score_B", "MODEL_B")]:
    valid = df[score_col].notna() & df["p_under"].notna()
    r_corr, p_corr = stats.pearsonr(df.loc[valid, score_col], df.loc[valid, "p_under"])
    print(f"  {model_name} vs V1 p_under: r={r_corr:.4f}, p={p_corr:.4f}")

# V1 OVER lean = p_under < 0.45
print("\n  V1 OVER lean (p_under < 0.45) + volatility top 20%:")
v1_over = df_np[(df_np["p_under"] < 0.45) & df_np["vol_score_A"].notna()]
print(f"  V1 OVER alone: N={len(v1_over)}, over%={v1_over['over_flag'].mean():.3f}, "
      f"ROI={roi_110(v1_over['over_flag'].sum(), len(v1_over) - v1_over['over_flag'].sum()):+.1f}%")

if len(v1_over) > 50:
    thresh = v1_over["vol_score_A"].quantile(0.80)
    mask = v1_over["vol_score_A"] > thresh
    n = mask.sum()
    if n > 10:
        over_rate = v1_over.loc[mask, "over_flag"].mean()
        w = v1_over.loc[mask, "over_flag"].sum()
        roi = roi_110(w, n - w)
        print(f"  V1 OVER + vol top20: N={n}, over%={over_rate:.3f}, ROI={roi:+.1f}%")

# =====================================================================
# STEP 7 — PERMUTATION (2025)
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — PERMUTATION (2025)")
print("=" * 60)

for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    yr_np = df_np[(df_np["season"] == 2025) & df_np[score_col].notna()]
    thresh = yr_np[score_col].quantile(0.80)
    flagged = yr_np[score_col] > thresh
    n_flagged = flagged.sum()

    if n_flagged < 20:
        print(f"  {model_name}: N={n_flagged}, too few")
        continue

    obs_w = yr_np.loc[flagged, "over_flag"].sum()
    obs_roi = roi_110(obs_w, n_flagged - obs_w)

    N_PERM = 200
    outcomes = yr_np["over_flag"].values.copy()
    perm_rois = []
    for _ in range(N_PERM):
        np.random.shuffle(outcomes)
        w = outcomes[:n_flagged].sum()
        perm_rois.append(roi_110(w, n_flagged - w))
    perm_rois = np.array(perm_rois)
    pctile = (perm_rois <= obs_roi).mean() * 100

    print(f"  {model_name}: N={n_flagged}, obs ROI={obs_roi:+.1f}%, "
          f"perm median={np.median(perm_rois):+.1f}%, pctile={pctile:.0f}%")

# =====================================================================
# WRITE REPORT
# =====================================================================
print("\n" + "=" * 60)
print("WRITING REPORT")
print("=" * 60)

# Gather key results
df_np_valid_A = df_np[df_np["vol_score_A"].notna()]
df_np_valid_B = df_np[df_np["vol_score_B"].notna()]

R = []
R.append("# Run Volatility Score — Research Report")
R.append("")
R.append("## Concept")
R.append("Model game-level run scoring VARIANCE, not mean.")
R.append("High-variance environments favor OVER due to right-skewed run distributions.")
R.append("")
R.append(f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append(f"Games with all features: {len(df_model)}")
R.append("")

R.append("## Features ({} total)".format(len(FEATURES)))
R.append("")
R.append("| Feature | Domain | Coverage |")
R.append("|---------|--------|----------|")
for feat in FEATURES:
    n = df[feat].notna().sum()
    domain = "pitcher" if "bb_rate" in feat or "hard_hit" in feat or "whiff" in feat or "barrel" in feat or "era" in feat or "xfip" in feat else \
             "bullpen" if "bp_" in feat else \
             "lineup" if "lineup" in feat or "contact" in feat else \
             "park" if "park" in feat or "wind" in feat or "temp" in feat else "interaction"
    R.append(f"| {feat} | {domain} | {100*n/len(df):.1f}% |")
R.append("")

R.append("## Model Comparison")
R.append("")
R.append("| Model | R² vs |deviation| | Method |")
R.append("|-------|-------------------|--------|")
corr_A = df_model["vol_score_A"].corr(df_model["absolute_deviation"])**2
R.append(f"| A (equal-weight) | {corr_A:.4f} | z-score sum |")
R.append(f"| B (OLS-weighted) | {ols_model.rsquared:.4f} | OLS regression |")
R.append("")

R.append("### OLS Significant Features (p<0.10)")
R.append("")
R.append("| Feature | Coefficient | p-value |")
R.append("|---------|------------|---------|")
for feat in FEATURES:
    if ols_model.pvalues[feat] < 0.10:
        R.append(f"| {feat} | {ols_model.params[feat]:+.4f} | {ols_model.pvalues[feat]:.4f} |")
R.append("")

# Decile tables
for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    valid_np = df_np[score_col].notna()
    sub = df_np[valid_np].copy()
    sub["decile"] = pd.qcut(sub[score_col], 10, labels=False, duplicates="drop")

    R.append(f"### {model_name} Decile Structure")
    R.append("")
    R.append("| Decile | N | Score | Over% | ROI |")
    R.append("|--------|---|-------|-------|-----|")
    for dec in sorted(sub["decile"].unique()):
        d = sub[sub["decile"] == dec]
        n = len(d)
        ms = d[score_col].mean()
        over_r = d["over_flag"].mean()
        w = d["over_flag"].sum()
        roi = roi_110(w, n - w)
        R.append(f"| {dec} | {n} | {ms:.2f} | {over_r:.3f} | {roi:+.1f}% |")
    d0 = sub[sub["decile"] == 0]["over_flag"].mean()
    d9 = sub[sub["decile"] == sub["decile"].max()]["over_flag"].mean()
    R.append(f"\nTail spread: D0={d0:.3f} → D9={d9:.3f} ({d9-d0:+.3f})")
    R.append("")

# Step 4 — OVER prediction
R.append("## OVER Prediction")
R.append("")
for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    R.append(f"### {model_name}")
    R.append("")
    R.append("| Threshold | N | Over% | ROI |")
    R.append("|-----------|---|-------|-----|")
    valid_np = df_np[score_col].notna()
    sub = df_np[valid_np]
    for label, lo_pct in [("top_10", 90), ("top_20", 80), ("top_30", 70)]:
        thresh = sub[score_col].quantile(lo_pct / 100)
        mask = sub[score_col] > thresh
        n = mask.sum()
        over_r = sub.loc[mask, "over_flag"].mean()
        w = sub.loc[mask, "over_flag"].sum()
        roi = roi_110(w, n - w)
        R.append(f"| {label} | {n} | {over_r:.3f} | {roi:+.1f}% |")
    R.append("")

# Step 5 — Stability
R.append("## Season Stability (top 20%)")
R.append("")
R.append("| Model | Year | N | Over% | ROI |")
R.append("|-------|------|---|-------|-----|")
for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    for yr in [2024, 2025]:
        yr_np = df_np[(df_np["season"] == yr) & df_np[score_col].notna()]
        if len(yr_np) < 100: continue
        thresh = yr_np[score_col].quantile(0.80)
        mask = yr_np[score_col] > thresh
        n = mask.sum()
        over_r = yr_np.loc[mask, "over_flag"].mean()
        w = yr_np.loc[mask, "over_flag"].sum()
        roi = roi_110(w, n - w)
        R.append(f"| {model_name} | {yr} | {n} | {over_r:.3f} | {roi:+.1f}% |")
R.append("")

# Step 6 — V1 independence
R.append("## V1 Independence")
R.append("")
for score_col, mn in [("vol_score_A", "A"), ("vol_score_B", "B")]:
    valid = df[score_col].notna() & df["p_under"].notna()
    r_c, _ = stats.pearsonr(df.loc[valid, score_col], df.loc[valid, "p_under"])
    R.append(f"- {mn} vs V1 p_under: r={r_c:.4f}")
R.append("")

# Step 7 — Permutation
R.append("## Permutation (2025 top 20%)")
R.append("")
for model_name, score_col in [("MODEL_A", "vol_score_A"), ("MODEL_B", "vol_score_B")]:
    yr_np = df_np[(df_np["season"] == 2025) & df_np[score_col].notna()]
    thresh = yr_np[score_col].quantile(0.80)
    flagged = yr_np[score_col] > thresh
    n_f = flagged.sum()
    if n_f < 20: continue
    obs_w = yr_np.loc[flagged, "over_flag"].sum()
    obs_roi = roi_110(obs_w, n_f - obs_w)
    outcomes = yr_np["over_flag"].values.copy()
    perm_rois = []
    for _ in range(200):
        np.random.shuffle(outcomes)
        w = outcomes[:n_f].sum()
        perm_rois.append(roi_110(w, n_f - w))
    perm_rois = np.array(perm_rois)
    pctile = (perm_rois <= obs_roi).mean() * 100
    R.append(f"- {model_name}: obs ROI={obs_roi:+.1f}%, pctile={pctile:.0f}%")
R.append("")

# Final verdict
R.append("## Final Verdict")
R.append("")

# Determine based on results
# Check if top_20 over% > 0.52 and stable
out = BASE / "run_volatility_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")

# Re-open to append verdict after seeing numbers
print(f"Saved initial report to {out}")
print("\nKey results for verdict:")

# Print summary for verdict
for mn, sc_col in [("A", "vol_score_A"), ("B", "vol_score_B")]:
    valid_np = df_np[sc_col].notna()
    sub = df_np[valid_np]
    thresh = sub[sc_col].quantile(0.80)
    mask = sub[sc_col] > thresh
    n = mask.sum()
    over_r = sub.loc[mask, "over_flag"].mean()
    w = sub.loc[mask, "over_flag"].sum()
    roi = roi_110(w, n - w)
    print(f"  {mn} top_20: N={n}, over%={over_r:.3f}, ROI={roi:+.1f}%")

    for yr in [2024, 2025]:
        yr_np = df_np[(df_np["season"] == yr) & df_np[sc_col].notna()]
        if len(yr_np) < 100: continue
        th = yr_np[sc_col].quantile(0.80)
        m = yr_np[sc_col] > th
        yn = m.sum()
        yo = yr_np.loc[m, "over_flag"].mean()
        yw = yr_np.loc[m, "over_flag"].sum()
        yr_roi = roi_110(yw, yn - yw)
        print(f"    {yr}: N={yn}, over%={yo:.3f}, ROI={yr_roi:+.1f}%")
