#!/usr/bin/env python3
"""
Residual Space Scan — discover structural patterns in games where
the UNDER system does NOT fire.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats as sp_stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
PULLS = BASE.parent / "data_pulls"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

def cohens_d(g1, g2):
    n1, n2 = len(g1), len(g2)
    if n1 < 2 or n2 < 2: return 0
    s = np.sqrt(((n1-1)*g1.std()**2 + (n2-1)*g2.std()**2) / (n1+n2-2))
    if s == 0: return 0
    return (g1.mean() - g2.mean()) / s

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
sc = pd.read_parquet(BASE.parent / "statcast_enrichment" /
                     "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])
ps = pd.read_parquet(BASE.parent / "opponent_adjusted_engine" /
                     "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])
lp = pd.read_parquet(PULLS / "lineup_batted_ball_profiles.parquet")
lp["date"] = pd.to_datetime(lp["date"])
rt = pd.read_parquet(PULLS / "reliever_role_tracking.parquet")
rt["date"] = pd.to_datetime(rt["date"])
era_pulls = pd.read_parquet(PULLS / "pitcher_rolling_era_pitches.parquet")
era_pulls["game_date"] = pd.to_datetime(era_pulls["game_date"])
tto_pulls = pd.read_parquet(PULLS / "pitcher_tto_splits.parquet")
tto_pulls["game_date"] = pd.to_datetime(tto_pulls["game_date"])
gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
bf = pd.read_parquet(SIM / "bullpen_features.parquet")
bf["date"] = pd.to_datetime(bf["date"])

audit = [
    "# Source Audit — Residual Space Scan", "",
    f"| File | Rows | Purpose |",
    f"|------|------|---------|",
    f"| feature_table | {len(ft)} | SP, BP, park, weather |",
    f"| bet_results | {len(br)} | Closing lines (2024-2025) |",
    f"| phase5_sim_results | {len(sim_v1)} | V1 p_under |",
    f"| pitcher_statcast_per_start | {len(sc)} | HH%, barrel%, whiff% |",
    f"| pitcher_start_adjusted_metrics | {len(ps)} | Per-start K/BB/IP/ER |",
    f"| lineup_batted_ball_profiles | {len(lp)} | Lineup contact/HH/barrel/ISO |",
    f"| reliever_role_tracking | {len(rt)} | Closer/setup usage, BP IP |",
    f"| pitcher_rolling_era_pitches | {len(era_pulls)} | ERA spike, pitch counts |",
    f"| pitcher_tto_splits | {len(tto_pulls)} | TTO degradation proxy |",
    f"| bullpen_features | {len(bf)} | BP pitches last 1/3 games |",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1 — BUILD RESIDUAL COHORT
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — BUILD RESIDUAL COHORT")
print("=" * 60)

# Build base dataset
df = ft[ft["season"].isin([2024, 2025])].copy()
df = df.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
              on="game_pk", how="inner")
df.rename(columns={"close_total": "closing_total"}, inplace=True)
df = df.merge(sim_v1[["game_pk", "p_under"]], on="game_pk", how="left")

# Reconstruct S12 trigger: need season-level CSW per pitcher
# Use strike% from pitcher starts as CSW proxy (same as V1 engine)
ps_s = ps.sort_values(["pitcher_id", "date"]).copy()
ps_s["season_csw"] = ps_s.groupby(["pitcher_id", "season"])["raw_csw_start"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).mean())

for side, prefix in [("home", "home_sp"), ("away", "away_sp")]:
    csw_join = ps_s[ps_s["side"] == side][["game_pk", "season_csw"]].rename(
        columns={"season_csw": f"{prefix}_csw"})
    df = df.merge(csw_join, on="game_pk", how="left")

# S12 = (home_csw + away_csw)/2 - 5*(home_xfip + away_xfip)/2
df["s12_score"] = ((df["home_sp_csw"] + df["away_sp_csw"]) / 2) - \
                   5 * ((df["home_sp_xfip"] + df["away_sp_xfip"]) / 2)
S12_CUTOFF = 8.4468
df["s12_trigger"] = (df["s12_score"] >= S12_CUTOFF).astype(int)

# Reconstruct P09 trigger: need pitcher hard-hit rates
sc_s = sc.sort_values(["pitcher_id", "game_date"])
sc_s["hh_r5"] = sc_s.groupby("pitcher_id")["hard_hit_rate"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Build pitcher HH lookup
pitcher_hh = {}
for pid, grp in sc_s.dropna(subset=["hh_r5"]).groupby("pitcher_id"):
    pitcher_hh[pid] = list(zip(grp["game_date"].values, grp["hh_r5"].values))

def lookup_hh(row, sp_col):
    pid = row.get(sp_col)
    if pd.isna(pid): return np.nan
    pid = int(pid)
    if pid not in pitcher_hh: return np.nan
    gd = pd.Timestamp(row["date"])
    best = np.nan
    for d, hh in pitcher_hh[pid]:
        if pd.Timestamp(d) < gd: best = hh
        else: break
    return best

print("  Computing P09 triggers...")
df["home_hh"] = df.apply(lambda r: lookup_hh(r, "home_sp_id"), axis=1)
df["away_hh"] = df.apply(lambda r: lookup_hh(r, "away_sp_id"), axis=1)
df["p09_value"] = ((df["home_hh"] + df["away_hh"]) / 2) * df["park_factor_runs"]
P09_CUTOFF = 31.7305
df["p09_trigger"] = (df["p09_value"] <= P09_CUTOFF).astype(int)

# V1 UNDER trigger
df["v1_under_trigger"] = (df["p_under"] > 0.57).astype(int)

# Under system fires when V1 + (S12 or P09)
df["under_signal"] = ((df["v1_under_trigger"] == 1) &
                       ((df["s12_trigger"] == 1) | (df["p09_trigger"] == 1))).astype(int)

# Residual space = under_signal == 0
df["residual_space"] = (df["under_signal"] == 0).astype(int)

# Targets
df["is_push"] = (df["actual_total"] == df["closing_total"])
df["actual_result_over"] = (df["actual_total"] > df["closing_total"]).astype(int)
df["market_residual"] = df["actual_total"] - df["closing_total"]

total = len(df)
residual_n = df["residual_space"].sum()
print(f"  Total games: {total}")
print(f"  Under signal fires: {total - residual_n} ({100*(total-residual_n)/total:.1f}%)")
print(f"  Residual space: {residual_n} ({100*residual_n/total:.1f}%)")

# Filter to residual
resid = df[df["residual_space"] == 1].copy()
resid_np = resid[~resid["is_push"]].copy()

# =====================================================================
# STEP 2 — OUTCOME CLASSIFICATION
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — OUTCOME CLASSIFICATION")
print("=" * 60)

resid["outcome_group"] = "NEUTRAL"
resid.loc[resid["actual_total"] >= resid["closing_total"] + 2, "outcome_group"] = "STRONG_OVER"
resid.loc[resid["actual_total"] <= resid["closing_total"] - 2, "outcome_group"] = "STRONG_UNDER"

for grp in ["STRONG_OVER", "NEUTRAL", "STRONG_UNDER"]:
    n = (resid["outcome_group"] == grp).sum()
    print(f"  {grp}: {n} ({100*n/len(resid):.1f}%)")

# =====================================================================
# STEP 3 — FEATURE POOL
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — FEATURE POOL")
print("=" * 60)

# Join all feature sources
# Pitcher ERA/pitches
for side, prefix in [("home", "home_sp"), ("away", "away_sp")]:
    era_side = era_pulls[era_pulls["team"].isin(
        resid[f"{side}_team"].unique() if f"{side}_team" in resid.columns else [])].copy()
    # Join on game_pk
    era_join = era_pulls[["game_id", "pitcher_id",
                          "pitcher_era_spike", "pitcher_pitches_per_inning_last3",
                          "pitcher_pitches_2starts_ago"]].copy()
    # Match by game_pk and side
    ps_side = ps[ps["side"] == side][["game_pk", "pitcher_id"]].copy()
    era_join = era_join.merge(ps_side.rename(columns={"game_pk": "game_id"}),
                               on=["game_id", "pitcher_id"], how="inner")
    era_join = era_join.drop(columns=["pitcher_id"]).rename(
        columns={"pitcher_era_spike": f"{prefix}_era_spike",
                 "pitcher_pitches_per_inning_last3": f"{prefix}_ppi",
                 "pitcher_pitches_2starts_ago": f"{prefix}_pitches_2ago"})
    resid = resid.merge(era_join.rename(columns={"game_id": "game_pk"}), on="game_pk", how="left")

# Lineup features
for side, prefix in [("home", "home"), ("away", "away")]:
    lp_side = lp[lp["side"] == side][
        ["game_pk", "team_lineup_contact_rate", "team_lineup_hard_hit_rate",
         "team_lineup_barrel_rate", "team_lineup_pull_pct",
         "team_lineup_avg_launch_angle", "team_lineup_iso"]].copy()
    lp_side.columns = ["game_pk"] + [f"{prefix}_lineup_{c.replace('team_lineup_', '')}"
                                       for c in lp_side.columns[1:]]
    resid = resid.merge(lp_side, on="game_pk", how="left")

# Reliever tracking
resid = resid.merge(rt[["game_pk",
                         "home_closer_pitched_last2days", "away_closer_pitched_last2days",
                         "home_top_3_relievers_ip_last3d", "away_top_3_relievers_ip_last3d",
                         "home_bullpen_high_leverage_ip_last3d", "away_bullpen_high_leverage_ip_last3d"]],
                     on="game_pk", how="left")

# Bullpen features
bf_home = bf[["game_pk", "team", "bullpen_pitches_last_3_games"]].rename(
    columns={"team": "home_team", "bullpen_pitches_last_3_games": "home_bp_pitches_3g"})
bf_away = bf[["game_pk", "team", "bullpen_pitches_last_3_games"]].rename(
    columns={"team": "away_team", "bullpen_pitches_last_3_games": "away_bp_pitches_3g"})
resid = resid.merge(bf_home, on=["game_pk", "home_team"], how="left")
resid = resid.merge(bf_away, on=["game_pk", "away_team"], how="left")

# TTO splits
for side, prefix in [("home", "home_sp"), ("away", "away_sp")]:
    tto_side = tto_pulls.copy()
    ps_side = ps[ps["side"] == side][["game_pk", "pitcher_id"]].copy()
    tto_join = tto_side[["game_id", "pitcher_id", "pitcher_tto_drop", "short_exit_rate_r15"]].merge(
        ps_side.rename(columns={"game_pk": "game_id"}), on=["game_id", "pitcher_id"], how="inner"
    ).drop(columns=["pitcher_id"]).rename(
        columns={"pitcher_tto_drop": f"{prefix}_tto_drop",
                 "short_exit_rate_r15": f"{prefix}_short_exit_rate",
                 "game_id": "game_pk"})
    resid = resid.merge(tto_join, on="game_pk", how="left")

# Build combined features
resid["combined_era_spike"] = (resid.get("home_sp_era_spike", pd.Series(dtype=float)).fillna(0) +
                                resid.get("away_sp_era_spike", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_ppi"] = (resid.get("home_sp_ppi", pd.Series(dtype=float)).fillna(0) +
                          resid.get("away_sp_ppi", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_lineup_contact"] = (resid.get("home_lineup_contact_rate", pd.Series(dtype=float)).fillna(0) +
                                     resid.get("away_lineup_contact_rate", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_lineup_hh"] = (resid.get("home_lineup_hard_hit_rate", pd.Series(dtype=float)).fillna(0) +
                                resid.get("away_lineup_hard_hit_rate", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_lineup_barrel"] = (resid.get("home_lineup_barrel_rate", pd.Series(dtype=float)).fillna(0) +
                                    resid.get("away_lineup_barrel_rate", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_lineup_iso"] = (resid.get("home_lineup_iso", pd.Series(dtype=float)).fillna(0) +
                                 resid.get("away_lineup_iso", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_lineup_bb"] = (resid.get("home_lineup_bb", pd.Series(dtype=float)) if "home_lineup_bb" in resid.columns
                                else pd.Series(0, index=resid.index))
# Use V2 offense table if lineup_bb not joined yet
if resid["combined_lineup_bb"].isna().all():
    v2_off = pd.read_parquet(BASE.parent / "opponent_adjusted_engine_v2" / "offense_expectation_table.parquet")
    v2_off["date"] = pd.to_datetime(v2_off["date"])
    for side, prefix in [("home", "home"), ("away", "away")]:
        bb_join = v2_off[v2_off["side"] == side][["game_pk", "team_bb_rate"]].rename(
            columns={"team_bb_rate": f"{prefix}_lineup_bb"})
        resid = resid.merge(bb_join, on="game_pk", how="left")
    resid["combined_lineup_bb"] = (resid["home_lineup_bb"].fillna(0) + resid["away_lineup_bb"].fillna(0)) / 2

resid["combined_bp_workload"] = resid["home_bp_pitches_3g"].fillna(0) + resid["away_bp_pitches_3g"].fillna(0)
resid["combined_bp_xfip"] = (resid["home_bp_xfip"] + resid["away_bp_xfip"]) / 2
resid["combined_closer_used"] = (resid["home_closer_pitched_last2days"].fillna(0) +
                                  resid["away_closer_pitched_last2days"].fillna(0))
resid["combined_top3_ip"] = (resid["home_top_3_relievers_ip_last3d"].fillna(0) +
                              resid["away_top_3_relievers_ip_last3d"].fillna(0))
resid["combined_tto_drop"] = (resid.get("home_sp_tto_drop", pd.Series(dtype=float)).fillna(0) +
                               resid.get("away_sp_tto_drop", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_short_exit"] = (resid.get("home_sp_short_exit_rate", pd.Series(dtype=float)).fillna(0) +
                                 resid.get("away_sp_short_exit_rate", pd.Series(dtype=float)).fillna(0)) / 2
resid["combined_bb_rate"] = (resid["home_sp_bb_pct"] + resid["away_sp_bb_pct"]) / 2
resid["combined_k_rate"] = (resid["home_sp_k_pct"] + resid["away_sp_k_pct"]) / 2
resid["combined_xfip"] = (resid["home_sp_xfip"] + resid["away_sp_xfip"]) / 2

# Feature pool (exclude S12/P09/V1 direct features)
FEATURES = [
    "combined_era_spike",
    "combined_ppi",
    "combined_lineup_contact",
    "combined_lineup_hh",
    "combined_lineup_barrel",
    "combined_lineup_iso",
    "combined_lineup_bb",
    "combined_bp_workload",
    "combined_bp_xfip",
    "combined_closer_used",
    "combined_top3_ip",
    "combined_tto_drop",
    "combined_short_exit",
    "combined_bb_rate",
    "combined_k_rate",
    "park_factor_hr",
    "temperature",
    "wind_factor_effective",
    "home_rest_days",
    "away_rest_days",
]

print(f"  Features in pool: {len(FEATURES)}")
for feat in FEATURES:
    if feat in resid.columns:
        n = resid[feat].notna().sum()
        print(f"    {feat}: {n}/{len(resid)} ({100*n/len(resid):.1f}%)")

# Save residual dataset
resid.to_parquet(BASE / "residual_dataset.parquet", index=False)

# =====================================================================
# STEP 4 — ANOMALY DETECTION
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — ANOMALY DETECTION")
print("=" * 60)

strong_over = resid[resid["outcome_group"] == "STRONG_OVER"]
neutral = resid[resid["outcome_group"] == "NEUTRAL"]
strong_under = resid[resid["outcome_group"] == "STRONG_UNDER"]

anomaly_results = []

for feat in FEATURES:
    if feat not in resid.columns:
        continue
    so = strong_over[feat].dropna()
    ne = neutral[feat].dropna()
    su = strong_under[feat].dropna()

    if len(so) < 20 or len(ne) < 20 or len(su) < 20:
        continue

    delta_over = so.mean() - ne.mean()
    delta_under = su.mean() - ne.mean()

    t_over, p_over = sp_stats.ttest_ind(so, ne)
    t_under, p_under = sp_stats.ttest_ind(su, ne)

    d_over = cohens_d(so, ne)
    d_under = cohens_d(su, ne)

    anomaly_results.append({
        "feature": feat,
        "mean_strong_over": so.mean(),
        "mean_neutral": ne.mean(),
        "mean_strong_under": su.mean(),
        "delta_over": delta_over,
        "delta_under": delta_under,
        "t_over": t_over, "p_over": p_over,
        "t_under": t_under, "p_under": p_under,
        "d_over": d_over, "d_under": d_under,
    })

    if p_over < 0.10 or p_under < 0.10:
        print(f"  {feat}: delta_over={delta_over:+.4f} (p={p_over:.4f}, d={d_over:+.3f}), "
              f"delta_under={delta_under:+.4f} (p={p_under:.4f}, d={d_under:+.3f})")

anom_df = pd.DataFrame(anomaly_results)

# =====================================================================
# STEP 5 — TAIL ANALYSIS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — TAIL ANALYSIS")
print("=" * 60)

resid_np = resid[~resid["is_push"]].copy()

tail_results = []

for feat in FEATURES:
    if feat not in resid_np.columns:
        continue
    valid = resid_np[feat].notna()
    if valid.sum() < 200:
        continue

    for label, lo_pct, hi_pct in [("top_10", 90, 100), ("bot_10", 0, 10)]:
        lo_val = np.nanpercentile(resid_np.loc[valid, feat], lo_pct)
        hi_val = np.nanpercentile(resid_np.loc[valid, feat], hi_pct)
        if lo_pct == 0:
            mask = valid & (resid_np[feat] <= hi_val)
        else:
            mask = valid & (resid_np[feat] > lo_val)

        n = mask.sum()
        if n < 40:
            continue

        over_r = resid_np.loc[mask, "actual_result_over"].mean()
        resid_val = over_r - 0.50
        w = resid_np.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)

        # Year consistency
        yr_rois = {}
        yr_consistent = True
        for yr in [2024, 2025]:
            yr_m = mask & (resid_np["season"] == yr)
            yn = yr_m.sum()
            if yn < 20:
                yr_rois[yr] = np.nan
                continue
            yw = resid_np.loc[yr_m, "actual_result_over"].sum()
            yr_rois[yr] = roi_110(yw, yn - yw)

        if not np.isnan(yr_rois.get(2024, np.nan)) and not np.isnan(yr_rois.get(2025, np.nan)):
            yr_consistent = yr_rois[2024] * yr_rois[2025] > 0  # same sign
        else:
            yr_consistent = False

        # Market correlation
        corr_mask = valid & resid_np["closing_total"].notna()
        if resid_np.loc[corr_mask, feat].std() > 1e-10:
            r_c, _ = sp_stats.pearsonr(resid_np.loc[corr_mask, feat],
                                         resid_np.loc[corr_mask, "closing_total"])
        else:
            r_c = 0.0

        tail_results.append({
            "feature": feat, "bucket": label, "N": n,
            "over_rate": over_r, "resid": resid_val, "roi": roi,
            "roi_2024": yr_rois.get(2024, np.nan),
            "roi_2025": yr_rois.get(2025, np.nan),
            "yr_consistent": yr_consistent,
            "market_corr": r_c,
        })

        flagged = roi > 4 and n >= 80 and yr_consistent
        if flagged:
            print(f"  *** FLAGGED: {feat} {label}: N={n}, over%={over_r:.3f}, "
                  f"ROI={roi:+.1f}%, 2024={yr_rois.get(2024, 'N/A')}, 2025={yr_rois.get(2025, 'N/A')}")

tail_df = pd.DataFrame(tail_results)

# =====================================================================
# STEP 6 — MARKET INDEPENDENCE
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — MARKET INDEPENDENCE")
print("=" * 60)

corr_results = []
for feat in FEATURES:
    if feat not in resid.columns:
        continue
    valid = resid[feat].notna() & resid["closing_total"].notna()
    if valid.sum() < 100:
        continue
    if resid.loc[valid, feat].std() < 1e-10:
        corr_results.append({"feature": feat, "corr": 0, "class": "CLEAN"})
        continue
    r, _ = sp_stats.pearsonr(resid.loc[valid, feat], resid.loc[valid, "closing_total"])
    cls = "CLEAN" if abs(r) < 0.15 else "PARTIAL" if abs(r) < 0.30 else "PRICED"
    corr_results.append({"feature": feat, "corr": r, "class": cls})
    if cls != "CLEAN":
        print(f"  {feat}: r={r:.4f} → {cls}")

corr_df = pd.DataFrame(corr_results)

# =====================================================================
# STEP 7 — CANDIDATE RANKING
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — CANDIDATE RANKING")
print("=" * 60)

# Merge anomaly + tail + correlation results
candidates = []
for feat in FEATURES:
    anom = anom_df[anom_df["feature"] == feat]
    tails = tail_df[tail_df["feature"] == feat]
    corr = corr_df[corr_df["feature"] == feat]

    if len(anom) == 0:
        continue

    a = anom.iloc[0]

    # Best tail
    if len(tails) > 0:
        best_tail = tails.loc[tails["roi"].idxmax()] if tails["roi"].notna().any() else None
    else:
        best_tail = None

    candidates.append({
        "feature": feat,
        "delta_over": a["delta_over"],
        "delta_under": a["delta_under"],
        "p_over": a["p_over"],
        "p_under": a["p_under"],
        "d_over": a["d_over"],
        "d_under": a["d_under"],
        "tail_bucket": best_tail["bucket"] if best_tail is not None else "N/A",
        "tail_roi": best_tail["roi"] if best_tail is not None else np.nan,
        "tail_N": best_tail["N"] if best_tail is not None else 0,
        "tail_yr_consistent": best_tail["yr_consistent"] if best_tail is not None else False,
        "market_corr": corr.iloc[0]["corr"] if len(corr) > 0 else np.nan,
        "market_class": corr.iloc[0]["class"] if len(corr) > 0 else "N/A",
    })

cand_df = pd.DataFrame(candidates)
# Score: lower p_over or p_under + lower market_corr + higher tail ROI
cand_df["score"] = (
    -np.log10(cand_df["p_over"].clip(lower=1e-10)) +
    -np.log10(cand_df["p_under"].clip(lower=1e-10)) +
    cand_df["tail_roi"].fillna(0) / 10 +
    (1 - abs(cand_df["market_corr"].fillna(0)))
)
cand_df = cand_df.sort_values("score", ascending=False)
cand_df.to_parquet(BASE / "candidate_signals.parquet", index=False)
anom_df.to_parquet(BASE / "anomaly_feature_results.parquet", index=False)

print(f"\n{'Feature':<30} {'d_over':>7} {'p_over':>8} {'d_under':>8} {'p_under':>8} {'Tail ROI':>9} {'Corr':>7}")
print("-" * 85)
for _, r in cand_df.head(15).iterrows():
    tr = f"{r.tail_roi:+.1f}%" if not np.isnan(r.tail_roi) else "N/A"
    print(f"{r.feature:<30} {r.d_over:>+7.3f} {r.p_over:>8.4f} {r.d_under:>+8.3f} {r.p_under:>8.4f} {tr:>9} {r.market_corr:>+7.3f}")


# =====================================================================
# WRITE REPORT
# =====================================================================
print("\n" + "=" * 60)
print("WRITING REPORT")
print("=" * 60)

R = []
R.append("# Residual Space Scan — Anomaly Report")
R.append("")
R.append(f"Total games: {total}")
R.append(f"Under signal fires: {total - residual_n} ({100*(total-residual_n)/total:.1f}%)")
R.append(f"Residual space: {residual_n} ({100*residual_n/total:.1f}%)")
R.append("")
R.append("## Outcome Groups (within residual space)")
R.append("")
for grp in ["STRONG_OVER", "NEUTRAL", "STRONG_UNDER"]:
    n = (resid["outcome_group"] == grp).sum()
    R.append(f"- {grp}: {n} ({100*n/len(resid):.1f}%)")
R.append("")
R.append(f"Features scanned: {len(FEATURES)}")
R.append("")

# Anomaly detection results
R.append("## Anomaly Detection (STRONG_OVER vs NEUTRAL)")
R.append("")
R.append("| Feature | Delta | Cohen's d | p-value | Direction |")
R.append("|---------|-------|----------|---------|-----------|")
for _, r in anom_df.sort_values("p_over").head(10).iterrows():
    direction = "OVER ↑" if r.delta_over > 0 else "OVER ↓"
    R.append(f"| {r.feature} | {r.delta_over:+.4f} | {r.d_over:+.3f} | {r.p_over:.4f} | {direction} |")
R.append("")

R.append("## Anomaly Detection (STRONG_UNDER vs NEUTRAL)")
R.append("")
R.append("| Feature | Delta | Cohen's d | p-value | Direction |")
R.append("|---------|-------|----------|---------|-----------|")
for _, r in anom_df.sort_values("p_under").head(10).iterrows():
    direction = "UNDER ↑" if r.delta_under < 0 else "UNDER ↓"
    R.append(f"| {r.feature} | {r.delta_under:+.4f} | {r.d_under:+.3f} | {r.p_under:.4f} | {direction} |")
R.append("")

# Tail analysis
R.append("## Tail Analysis (top/bottom 10%)")
R.append("")
R.append("| Feature | Bucket | N | Over% | ROI | 2024 | 2025 | Consistent | Mkt Corr |")
R.append("|---------|--------|---|-------|-----|------|------|-----------|----------|")
for _, r in tail_df.sort_values("roi", ascending=False).head(15).iterrows():
    r24 = f"{r.roi_2024:+.1f}%" if not np.isnan(r.roi_2024) else "N/A"
    r25 = f"{r.roi_2025:+.1f}%" if not np.isnan(r.roi_2025) else "N/A"
    R.append(f"| {r.feature} | {r.bucket} | {r.N} | {r.over_rate:.3f} | {r.roi:+.1f}% | "
             f"{r24} | {r25} | {'YES' if r.yr_consistent else 'NO'} | {r.market_corr:+.3f} |")
R.append("")

# Candidate ranking
R.append("## Candidate Signal Ranking")
R.append("")
R.append("| Rank | Feature | d_over | p_over | Tail ROI | Tail N | Yr Consistent | Mkt Class |")
R.append("|------|---------|--------|--------|----------|--------|--------------|----------|")
for i, (_, r) in enumerate(cand_df.head(10).iterrows()):
    tr = f"{r.tail_roi:+.1f}%" if not np.isnan(r.tail_roi) else "N/A"
    R.append(f"| {i+1} | {r.feature} | {r.d_over:+.3f} | {r.p_over:.4f} | {tr} | "
             f"{r.tail_N:.0f} | {'YES' if r.tail_yr_consistent else 'NO'} | {r.market_class} |")
R.append("")

# Final answers
R.append("## Final Answers")
R.append("")

# Q1: STRONG_OVER features
R.append("### Q1: What distinguishes STRONG_OVER games?")
over_sig = anom_df[anom_df.p_over < 0.10].sort_values("p_over")
if len(over_sig) > 0:
    for _, r in over_sig.iterrows():
        direction = "higher" if r.delta_over > 0 else "lower"
        R.append(f"- **{r.feature}**: {direction} in STRONG_OVER (d={r.d_over:+.3f}, p={r.p_over:.4f})")
else:
    R.append("- No features distinguish STRONG_OVER at p<0.10")
R.append("")

# Q2: STRONG_UNDER features
R.append("### Q2: What distinguishes missed STRONG_UNDER games?")
under_sig = anom_df[anom_df.p_under < 0.10].sort_values("p_under")
if len(under_sig) > 0:
    for _, r in under_sig.iterrows():
        direction = "lower" if r.delta_under < 0 else "higher"
        R.append(f"- **{r.feature}**: {direction} in STRONG_UNDER (d={r.d_under:+.3f}, p={r.p_under:.4f})")
else:
    R.append("- No features distinguish STRONG_UNDER at p<0.10")
R.append("")

# Q3: Most promising candidates
R.append("### Q3: Most promising candidates?")
flagged_tails = tail_df[(tail_df.roi > 4) & (tail_df.N >= 80) & tail_df.yr_consistent]
if len(flagged_tails) > 0:
    for _, r in flagged_tails.iterrows():
        R.append(f"- **{r.feature} ({r.bucket})**: ROI={r.roi:+.1f}%, N={r.N}, year-consistent")
else:
    R.append("- No tail passes all three gates (ROI>4%, N≥80, year-consistent)")
R.append("")

# Q4: Classification
R.append("### Q4: Signal Classification")
R.append("")
R.append("| Feature | Classification | Reason |")
R.append("|---------|---------------|--------|")

promoted = 0
for _, r in cand_df.iterrows():
    if r.p_over < 0.05 and abs(r.market_corr) < 0.25 and r.tail_yr_consistent and r.tail_roi > 3 and promoted < 5:
        cls = "**PROMOTE**"
        promoted += 1
    elif r.p_over < 0.10 or (r.tail_roi > 0 and r.tail_N >= 80):
        cls = "HOLD"
    else:
        cls = "SHELVE"
    tr = f"ROI={r.tail_roi:+.1f}%" if not np.isnan(r.tail_roi) else "no tail"
    R.append(f"| {r.feature} | {cls} | p_over={r.p_over:.4f}, {tr}, corr={r.market_class} |")
R.append("")

out = BASE / "residual_anomaly_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"Saved: {out}")
print("Done.")
