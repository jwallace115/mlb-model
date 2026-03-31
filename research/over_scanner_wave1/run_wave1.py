#!/usr/bin/env python3
"""
OVER Scanner Wave 1 — Build dataset, triage 10 signals, V1 interaction, leaderboard.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# =====================================================================
# STEP 0 — LOAD SOURCES
# =====================================================================
print("=" * 60)
print("STEP 0 — LOAD SOURCES")
print("=" * 60)

ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])
sim_v1 = pd.read_parquet(SIM / "phase5_sim_results.parquet")
sim_v1["date"] = pd.to_datetime(sim_v1["date"])
ps = pd.read_parquet(BASE.parent / "opponent_adjusted_engine" / "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])
bf = pd.read_parquet(SIM / "bullpen_features.parquet")
bf["date"] = pd.to_datetime(bf["date"])
bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
sc = pd.read_parquet(BASE.parent / "statcast_enrichment" / "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])
v2_off = pd.read_parquet(BASE.parent / "opponent_adjusted_engine_v2" / "offense_expectation_table.parquet")
v2_off["date"] = pd.to_datetime(v2_off["date"])

# Audit
audit = [
    "# Source Audit — OVER Scanner Wave 1", "",
    f"| File | Rows | Key |",
    f"|------|------|-----|",
    f"| feature_table.parquet | {len(ft)} | SP xFIP/K%/BB%, BP xFIP, park, weather |",
    f"| bet_results.parquet | {len(br)} | Closing lines, outcomes |",
    f"| phase5_sim_results.parquet | {len(sim_v1)} | V1 p_under |",
    f"| pitcher_start_adjusted_metrics.parquet | {len(ps)} | Per-start K/BB/IP/ER/pitches |",
    f"| bullpen_features.parquet | {len(bf)} | BP pitches last 1/3 games, high_lev_avail |",
    f"| bullpen_usage.parquet | {len(bu)} | Per-reliever IP per game |",
    f"| game_table.parquet | {len(gt)} | innings_played for extra-innings |",
    f"| pitcher_statcast_per_start_starters_only.parquet | {len(sc)} | hard_hit_rate per start |",
    f"| offense_expectation_table.parquet (V2) | {len(v2_off)} | Team contact/BB rolling |",
    "",
    "## Notes",
    "- OV043: high_leverage_available is binary; using bullpen_pitches_last_3_games as workload proxy",
    "- OV051: bullpen ERA not available; using bullpen ER from boxscores via pitcher starts",
    "- OV050: prev_game_innings derived from game_table innings_played",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1+2 — BUILD WAVE 1 DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEPS 1+2 — BUILD WAVE 1 DATASET")
print("=" * 60)

# Base dataset
df = ft[ft["season"].isin([2024, 2025])].copy()
df = df.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
              on="game_pk", how="inner")
df.rename(columns={"close_total": "closing_total"}, inplace=True)
df = df.merge(sim_v1[["game_pk", "p_under", "p_over"]], on="game_pk", how="left")

df["is_push"] = (df["actual_total"] == df["closing_total"])
df["actual_result_over"] = (df["actual_total"] > df["closing_total"]).astype(int)
df["implied_over"] = 0.50
df["market_residual_over"] = df["actual_result_over"] - df["implied_over"]
df = df.sort_values("date").reset_index(drop=True)

print(f"  Base: {len(df)} games")

# ── Build pitcher rolling features ───────────────────────────────────
ps_s = ps.sort_values(["pitcher_id", "date"]).copy()
# Pitches 2 starts ago
ps_s["pitches_2ago"] = ps_s.groupby("pitcher_id")["pitches"].shift(2)
# ERA last 2 starts
ps_s["er_r2"] = ps_s.groupby("pitcher_id")["er"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())
ps_s["ip_r2"] = ps_s.groupby("pitcher_id")["ip"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())
ps_s["era_last2"] = ps_s["er_r2"] / ps_s["ip_r2"].clip(lower=0.1) * 9
# ERA season (expanding)
ps_s["er_season"] = ps_s.groupby(["pitcher_id", "season"])["er"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).sum())
ps_s["ip_season"] = ps_s.groupby(["pitcher_id", "season"])["ip"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).sum())
ps_s["era_season"] = ps_s["er_season"] / ps_s["ip_season"].clip(lower=0.1) * 9
ps_s["era_spike"] = ps_s["era_last2"] - ps_s["era_season"]
# Avg IP last 5
ps_s["ip_r5"] = ps_s.groupby("pitcher_id")["ip"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())
# Pitches per inning
ps_s["ppi"] = ps_s["pitches"] / ps_s["ip"].clip(lower=0.1)
ps_s["ppi_r5"] = ps_s.groupby("pitcher_id")["ppi"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Join home/away pitcher features
for side, prefix in [("home", "home_sp"), ("away", "away_sp")]:
    side_ps = ps_s[ps_s["side"] == side][[
        "game_pk", "pitches_2ago", "era_spike", "ip_r5", "ppi_r5",
        "raw_hard_hit_start", "raw_bb_rate_start"
    ]].copy()
    # Rolling hard-hit (last 5)
    side_ps_full = ps_s[ps_s["side"] == side].copy()
    side_ps_full["hh_r5"] = side_ps_full.groupby("pitcher_id")["raw_hard_hit_start"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    side_ps = side_ps.merge(side_ps_full[["game_pk", "hh_r5"]], on="game_pk", how="left")

    side_ps.columns = ["game_pk", f"{prefix}_pitches_2ago", f"{prefix}_era_spike",
                        f"{prefix}_ip_r5", f"{prefix}_ppi_r5",
                        f"{prefix}_raw_hh_start", f"{prefix}_raw_bb_start",
                        f"{prefix}_hh_r5"]
    df = df.merge(side_ps, on="game_pk", how="left")

# ── Bullpen features ─────────────────────────────────────────────────
# BP workload (pitches last 3 games as IP proxy)
bf_home = bf[["game_pk", "team", "bullpen_pitches_last_3_games"]].rename(
    columns={"team": "home_team", "bullpen_pitches_last_3_games": "home_bp_pitches_3g"})
bf_away = bf[["game_pk", "team", "bullpen_pitches_last_3_games"]].rename(
    columns={"team": "away_team", "bullpen_pitches_last_3_games": "away_bp_pitches_3g"})
df = df.merge(bf_home, on=["game_pk", "home_team"], how="left")
df = df.merge(bf_away, on=["game_pk", "away_team"], how="left")

# BP IP last 2 days (from bullpen_usage)
bp_only = bu[~bu["is_starter"]].copy()
bp_daily = bp_only.groupby(["team", "date"]).agg(bp_ip=("innings_pitched", "sum")).reset_index()
bp_daily = bp_daily.sort_values(["team", "date"])

def rolling_bp_ip_2d(grp):
    grp = grp.sort_values("date").copy()
    dates = grp["date"].values
    ip = grp["bp_ip"].values
    result = []
    for i, d in enumerate(dates):
        d_ts = pd.Timestamp(d)
        mask = (dates < d) & (dates >= (d_ts - pd.Timedelta(days=2)).to_numpy())
        result.append(ip[mask].sum())
    grp["bp_ip_last2d"] = result
    return grp

print("  Computing bullpen IP last 2 days...")
bp_daily = bp_daily.groupby("team", group_keys=False).apply(rolling_bp_ip_2d)

for side, prefix in [("home_team", "home"), ("away_team", "away")]:
    bp_join = bp_daily[["team", "date", "bp_ip_last2d"]].rename(
        columns={"team": side, "bp_ip_last2d": f"{prefix}_bp_ip_last2d"})
    df = df.merge(bp_join, on=[side, "date"], how="left")

# ── Previous game innings (for extra-innings signal) ─────────────────
# For each team, find their previous game's innings_played
games_long = []
for _, row in gt.iterrows():
    games_long.append({"game_pk": row["game_pk"], "date": row["date"],
                        "team": row["home_team"], "innings": row["innings_played"]})
    games_long.append({"game_pk": row["game_pk"], "date": row["date"],
                        "team": row["away_team"], "innings": row["innings_played"]})
gl = pd.DataFrame(games_long).sort_values(["team", "date"])
gl["prev_innings"] = gl.groupby("team")["innings"].shift(1)

for side, prefix in [("home_team", "home"), ("away_team", "away")]:
    prev_inn = gl[["game_pk", "team", "prev_innings"]].rename(
        columns={"team": side, "prev_innings": f"{prefix}_prev_innings"})
    # Keep only the row matching the correct team side
    df = df.merge(prev_inn, on=["game_pk", side], how="left")

# ── Lineup features (V2 offense) ────────────────────────────────────
home_off = v2_off[v2_off["side"] == "home"][
    ["game_pk", "team_contact_rate", "team_bb_rate"]].rename(
    columns={"team_contact_rate": "home_lineup_contact", "team_bb_rate": "home_lineup_bb"})
away_off = v2_off[v2_off["side"] == "away"][
    ["game_pk", "team_contact_rate", "team_bb_rate"]].rename(
    columns={"team_contact_rate": "away_lineup_contact", "team_bb_rate": "away_lineup_bb"})
df = df.merge(home_off, on="game_pk", how="left")
df = df.merge(away_off, on="game_pk", how="left")

# =====================================================================
# BUILD 10 SIGNALS
# =====================================================================
print("  Building 10 signals...")

# OV016: high_pitch_count_fatigue
df["OV016"] = ((df["home_sp_pitches_2ago"].fillna(0) + df["away_sp_pitches_2ago"].fillna(0)) / 2) / 100

# OV019: era_spike_recent
df["OV019"] = (df["home_sp_era_spike"].fillna(0) + df["away_sp_era_spike"].fillna(0)) / 2

# OV041: short_starter_x_weak_bullpen
home_short = (5 - df["home_sp_ip_r5"].fillna(5)).clip(lower=0)
away_short = (5 - df["away_sp_ip_r5"].fillna(5)).clip(lower=0)
df["OV041"] = (home_short * df["home_bp_xfip"] + away_short * df["away_bp_xfip"]) / 2

# OV043: high_leverage_bullpen_overuse (using pitches last 3 games as workload)
df["OV043"] = (df["home_bp_pitches_3g"].fillna(0) + df["away_bp_pitches_3g"].fillna(0))

# OV050: short_starter_x_extra_innings_yesterday
home_extra = (df["home_prev_innings"].fillna(9) - 9).clip(lower=0)
away_extra = (df["away_prev_innings"].fillna(9) - 9).clip(lower=0)
df["OV050"] = home_extra * home_short + away_extra * away_short

# OV051: bullpen_era_xfip_gap (xFIP only available; use xFIP - league_avg as proxy)
# Since we don't have BP ERA, use xFIP deviation from league mean as regression proxy
bp_xfip_mean = df[["home_bp_xfip", "away_bp_xfip"]].mean().mean()
df["OV051"] = ((df["home_bp_xfip"] - bp_xfip_mean) + (df["away_bp_xfip"] - bp_xfip_mean)) / 2

# OV100: combined_bullpen_workload_both (IP last 2 days)
df["OV100"] = df["home_bp_ip_last2d"].fillna(0) + df["away_bp_ip_last2d"].fillna(0)

# OV115: pitcher_pitch_count_per_ip_x_patient
# home SP pitches/inning × away lineup BB rate, and vice versa
df["OV115"] = (
    (df["home_sp_ppi_r5"].fillna(0) * df["away_lineup_bb"].fillna(0)) +
    (df["away_sp_ppi_r5"].fillna(0) * df["home_lineup_bb"].fillna(0))
) / 2

# OV001: bb_x_hard_hit
df["OV001"] = (
    (df["home_sp_bb_pct"] * df["home_sp_hh_r5"].fillna(0)) +
    (df["away_sp_bb_pct"] * df["away_sp_hh_r5"].fillna(0))
) / 2

# OV021: low_k_x_contact
df["OV021"] = (
    ((1 - df["home_sp_k_pct"]) * df["away_lineup_contact"].fillna(0)) +
    ((1 - df["away_sp_k_pct"]) * df["home_lineup_contact"].fillna(0))
) / 2

SIGNALS = ["OV016", "OV019", "OV041", "OV043", "OV050", "OV051", "OV100", "OV115", "OV001", "OV021"]
SIG_NAMES = {
    "OV016": "high_pitch_count_fatigue",
    "OV019": "era_spike_recent",
    "OV041": "short_starter_x_weak_bullpen",
    "OV043": "high_leverage_bullpen_overuse",
    "OV050": "short_starter_x_extra_innings",
    "OV051": "bullpen_xfip_deviation",
    "OV100": "combined_bullpen_workload",
    "OV115": "pitch_count_x_patient",
    "OV001": "bb_x_hard_hit",
    "OV021": "low_k_x_contact",
}

# Coverage
print(f"\n  Dataset: {len(df)} games, {(~df.is_push).sum()} non-push")
for sig in SIGNALS:
    n = df[sig].notna().sum()
    nz = (df[sig] != 0).sum() if df[sig].notna().any() else 0
    print(f"    {sig} ({SIG_NAMES[sig]}): {n}/{len(df)} ({100*n/len(df):.1f}%), nonzero={nz}")

# Save dataset
save_cols = ["game_pk", "date", "season", "home_team", "away_team",
             "closing_total", "actual_total", "implied_over", "actual_result_over",
             "market_residual_over", "is_push", "p_under", "p_over"] + SIGNALS
df[save_cols].to_parquet(BASE / "over_wave1_dataset.parquet", index=False)

df_np = df[~df["is_push"]].copy()

# =====================================================================
# STEP 3 — STANDALONE TRIAGE
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — STANDALONE TRIAGE")
print("=" * 60)

standalone_results = []

for sig in SIGNALS:
    name = SIG_NAMES[sig]
    valid = df[sig].notna() & (df[sig] != 0) if sig == "OV050" else df[sig].notna()
    valid_np = df_np[sig].notna() & (df_np[sig] != 0) if sig == "OV050" else df_np[sig].notna()
    # For OV050, most games are 0 (no extra innings yesterday) — use full distribution

    # Actually use full distribution for all signals (including zeros)
    valid = df[sig].notna()
    valid_np = df_np[sig].notna()

    extremes = []
    promote_t1 = False
    for label, lo_pct, hi_pct in [
        ("top_10", 90, 100), ("top_20", 80, 100),
        ("bot_10", 0, 10), ("bot_20", 0, 20),
    ]:
        lo_val = np.nanpercentile(df.loc[valid, sig], lo_pct)
        hi_val = np.nanpercentile(df.loc[valid, sig], hi_pct)
        if lo_pct == 0:
            mask_np = valid_np & (df_np[sig] <= hi_val)
        else:
            mask_np = valid_np & (df_np[sig] > lo_val)

        n = mask_np.sum()
        if n < 20:
            extremes.append({"bucket": label, "N": n, "over_rate": np.nan, "roi": np.nan, "resid": np.nan})
            continue
        over_r = df_np.loc[mask_np, "actual_result_over"].mean()
        resid = over_r - 0.50
        w = df_np.loc[mask_np, "actual_result_over"].sum()
        roi = roi_110(w, n - w)
        extremes.append({"bucket": label, "N": n, "over_rate": over_r, "resid": resid, "roi": roi})
        if "10" in label and n >= 60 and abs(resid) > 0.03:
            promote_t1 = True

    # Year stability
    yr_coefs = {}
    for yr in [2024, 2025]:
        yr_df = df[(df["season"] == yr) & valid]
        if yr_df[sig].std() < 1e-10:
            yr_coefs[yr] = {"coef": 0, "p": 1.0}
            continue
        X = sm.add_constant(yr_df[sig])
        y = yr_df["market_residual_over"]
        m = sm.OLS(y, X).fit()
        yr_coefs[yr] = {"coef": m.params[sig], "p": m.pvalues[sig]}

    consistent = yr_coefs.get(2024, {}).get("coef", 0) * yr_coefs.get(2025, {}).get("coef", 0) > 0
    stability = "STABLE" if consistent else "MIXED"

    # Market correlation
    corr_mask = valid & df["closing_total"].notna()
    if df.loc[corr_mask, sig].std() > 1e-10:
        r_corr, _ = stats.pearsonr(df.loc[corr_mask, sig], df.loc[corr_mask, "closing_total"])
    else:
        r_corr = 0.0
    corr_class = "CLEAN" if abs(r_corr) < 0.15 else "PARTIAL" if abs(r_corr) < 0.30 else "PRICED"

    # Verdict
    if promote_t1 and consistent and abs(r_corr) < 0.25:
        verdict = "PROMOTE"
    elif promote_t1 or (not np.isnan(extremes[0].get("roi", np.nan)) and max(e.get("roi", -999) for e in extremes) > 0):
        verdict = "INVESTIGATE"
    else:
        verdict = "SHELVE"

    standalone_results.append({
        "signal": sig, "name": name, "extremes": extremes,
        "stability": stability, "market_corr": r_corr, "corr_class": corr_class,
        "promote_t1": promote_t1, "consistent": consistent, "verdict": verdict,
        "yr_coefs": yr_coefs,
    })

    best_e = max(extremes, key=lambda e: e.get("roi", -999) if not np.isnan(e.get("roi", -999)) else -999)
    print(f"  {sig} {name}: best={best_e['bucket']} ROI={best_e.get('roi', 'N/A')}, "
          f"stable={stability}, corr={corr_class}({r_corr:.3f}) → {verdict}")


# =====================================================================
# STEP 4 — V1 OVER-LEAN INTERACTION
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — V1 OVER-LEAN INTERACTION")
print("=" * 60)

df["v1_over_lean"] = (df["p_under"] < 0.45).astype(int)
df_np["v1_over_lean"] = (df_np["p_under"] < 0.45).astype(int)

v1_over_np = df_np[df_np["v1_over_lean"] == 1]
v1_over_all = df[df["v1_over_lean"] == 1]
v1_n = len(v1_over_np)
v1_over_rate = v1_over_np["actual_result_over"].mean()
v1_w = v1_over_np["actual_result_over"].sum()
v1_roi = roi_110(v1_w, v1_n - v1_w)
print(f"  V1 OVER-lean baseline: N={v1_n}, over%={v1_over_rate:.3f}, ROI={v1_roi:+.1f}%")

interaction_results = []

for sig in SIGNALS:
    valid_np = df_np[sig].notna()
    for label, lo_pct in [("fav_10", 90), ("fav_20", 80), ("fav_30", 70)]:
        for yr_label, yr_np in [("pooled", df_np), ("2024", df_np[df_np.season==2024]),
                                 ("2025", df_np[df_np.season==2025])]:
            yr_v1 = yr_np[yr_np["v1_over_lean"] == 1]
            yr_valid = yr_v1[sig].notna()
            if yr_valid.sum() < 30:
                interaction_results.append({"signal": sig, "bucket": label, "year": yr_label,
                                            "N": 0, "over_rate": np.nan, "roi": np.nan,
                                            "v1_roi": np.nan, "lift_roi": np.nan})
                continue

            thresh = yr_v1.loc[yr_valid, sig].quantile(lo_pct / 100)
            mask = yr_valid & (yr_v1[sig] > thresh)
            n = mask.sum()
            if n < 10:
                interaction_results.append({"signal": sig, "bucket": label, "year": yr_label,
                                            "N": n, "over_rate": np.nan, "roi": np.nan,
                                            "v1_roi": np.nan, "lift_roi": np.nan})
                continue

            over_r = yr_v1.loc[mask, "actual_result_over"].mean()
            w = yr_v1.loc[mask, "actual_result_over"].sum()
            roi = roi_110(w, n - w)

            # V1 baseline for this year slice
            v1_yr_n = len(yr_v1)
            v1_yr_w = yr_v1["actual_result_over"].sum()
            v1_yr_roi = roi_110(v1_yr_w, v1_yr_n - v1_yr_w) if v1_yr_n > 0 else np.nan

            lift = roi - v1_yr_roi if not np.isnan(v1_yr_roi) else np.nan
            interaction_results.append({
                "signal": sig, "bucket": label, "year": yr_label,
                "N": n, "over_rate": over_r, "roi": roi,
                "v1_roi": v1_yr_roi, "lift_roi": lift,
                "thin": n < 50,
            })

int_df = pd.DataFrame(interaction_results)

# Print best per signal
for sig in SIGNALS:
    pooled = int_df[(int_df.signal == sig) & (int_df.year == "pooled") & int_df.lift_roi.notna()]
    if len(pooled) > 0:
        best = pooled.loc[pooled.lift_roi.idxmax()]
        print(f"  {sig}: best V1 int = {best.bucket}, N={best.N:.0f}, "
              f"ROI={best.roi:+.1f}%, lift={best.lift_roi:+.1f}pp"
              f"{' (THIN)' if best.get('thin') else ''}")


# =====================================================================
# STEP 5 — LEADERBOARD
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — LEADERBOARD")
print("=" * 60)

leaderboard = []
for sr in standalone_results:
    sig = sr["signal"]
    best_e = max(sr["extremes"], key=lambda e: e.get("roi", -999) if not np.isnan(e.get("roi", -999)) else -999)

    # Best V1 interaction
    pooled_ints = int_df[(int_df.signal == sig) & (int_df.year == "pooled") & int_df.lift_roi.notna()]
    if len(pooled_ints) > 0:
        best_int = pooled_ints.loc[pooled_ints.lift_roi.idxmax()]
        int_bucket = best_int.bucket
        int_lift = best_int.lift_roi
        int_n = best_int.N
        int_roi = best_int.roi
    else:
        int_bucket = "none"; int_lift = np.nan; int_n = 0; int_roi = np.nan

    # Year lifts
    y24 = int_df[(int_df.signal==sig) & (int_df.bucket==int_bucket) & (int_df.year=="2024")]
    y25 = int_df[(int_df.signal==sig) & (int_df.bucket==int_bucket) & (int_df.year=="2025")]
    l24 = y24.lift_roi.values[0] if len(y24) > 0 and not np.isnan(y24.lift_roi.values[0]) else np.nan
    l25 = y25.lift_roi.values[0] if len(y25) > 0 and not np.isnan(y25.lift_roi.values[0]) else np.nan

    # Recommendation
    is_candidate = (not np.isnan(int_lift) and int_lift > 3 and int_n >= 50)
    if sr["verdict"] == "PROMOTE" or is_candidate:
        rec = "PROMOTE"
    elif sr["verdict"] == "INVESTIGATE" or (not np.isnan(int_lift) and int_lift > 0):
        rec = "HOLD"
    else:
        rec = "SHELVE"

    leaderboard.append({
        "signal": sig, "name": sr["name"],
        "standalone_bucket": best_e["bucket"], "standalone_roi": best_e.get("roi", np.nan),
        "standalone_verdict": sr["verdict"],
        "v1_int_bucket": int_bucket, "v1_int_roi_lift": int_lift,
        "v1_int_N": int_n, "v1_int_roi": int_roi,
        "year_stability": sr["stability"], "market_corr_class": sr["corr_class"],
        "market_corr": sr["market_corr"],
        "int_2024_lift": l24, "int_2025_lift": l25,
        "recommendation": rec,
    })

lb_df = pd.DataFrame(leaderboard)
lb_df = lb_df.sort_values(["v1_int_roi_lift", "standalone_roi"], ascending=[False, False])
lb_df.to_parquet(BASE / "over_wave1_leaderboard.parquet", index=False)

print(f"\n{'Signal':<12} {'Name':<35} {'Stand':>7} {'V1 Lift':>8} {'V1 N':>5} {'Stable':>7} {'Corr':>8} {'Rec'}")
print("-" * 95)
for _, r in lb_df.iterrows():
    sr_s = f"{r.standalone_roi:+.1f}%" if not np.isnan(r.standalone_roi) else "N/A"
    il_s = f"{r.v1_int_roi_lift:+.1f}pp" if not np.isnan(r.v1_int_roi_lift) else "N/A"
    print(f"{r.signal:<12} {r['name']:<35} {sr_s:>7} {il_s:>8} {r.v1_int_N:>5.0f} "
          f"{r.year_stability:>7} {r.market_corr_class:>8} {r.recommendation}")


# =====================================================================
# STEP 6 — SAFETY CHECKS (top 3)
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — SAFETY CHECKS")
print("=" * 60)

safety_lines = []
for _, row in lb_df.head(3).iterrows():
    sig = row["signal"]
    print(f"\n  --- {sig} ({row['name']}) ---")
    safety_lines.append(f"\n### {sig}: {row['name']}")

    # Availability bias
    v1_np_all = df_np[df_np["v1_over_lean"] == 1]
    avail = v1_np_all[sig].notna()
    unavail = ~avail
    for lbl, mask in [("Available", avail), ("Unavailable", unavail)]:
        n = mask.sum()
        if n == 0: continue
        over_r = v1_np_all.loc[mask, "actual_result_over"].mean()
        w = v1_np_all.loc[mask, "actual_result_over"].sum()
        roi = roi_110(w, n - w)
        avg_cl = df.loc[v1_np_all.loc[mask].index.intersection(df.index), "closing_total"].mean()
        print(f"    {lbl}: N={n}, over%={over_r:.3f}, ROI={roi:+.1f}%, avg_close={avg_cl:.2f}")
        safety_lines.append(f"- {lbl}: N={n}, over%={over_r:.3f}, ROI={roi:+.1f}%")

    # Thin tail
    pooled_best = int_df[(int_df.signal==sig) & (int_df.bucket==row.v1_int_bucket) & (int_df.year=="pooled")]
    if len(pooled_best) > 0:
        n_p = pooled_best.N.values[0]
        if n_p < 75:
            safety_lines.append(f"- **THIN TAIL**: N={n_p} < 75")
        else:
            safety_lines.append(f"- Tail OK: N={n_p}")

    # Direction reversal
    l24, l25 = row.int_2024_lift, row.int_2025_lift
    if not np.isnan(l24) and not np.isnan(l25) and l24 * l25 < 0:
        safety_lines.append(f"- **REVERSAL**: 2024={l24:+.1f}pp, 2025={l25:+.1f}pp")
    elif not np.isnan(l24) and not np.isnan(l25):
        safety_lines.append(f"- Direction OK: 2024={l24:+.1f}pp, 2025={l25:+.1f}pp")


# =====================================================================
# SAVE RESULTS + WRITE REPORT
# =====================================================================
print("\n" + "=" * 60)
print("WRITING REPORT")
print("=" * 60)

# Scan results
scan_rows = []
for sr in standalone_results:
    for e in sr["extremes"]:
        scan_rows.append({
            "signal": sr["signal"], "name": sr["name"], "bucket": e["bucket"],
            "N": e["N"], "over_rate": e.get("over_rate"), "resid": e.get("resid"),
            "roi": e.get("roi"), "stability": sr["stability"],
            "market_corr": sr["market_corr"], "verdict": sr["verdict"],
        })
pd.DataFrame(scan_rows).to_parquet(BASE / "over_wave1_scan_results.parquet", index=False)

# Report
R = []
R.append("# OVER Scanner Wave 1 — Report")
R.append("")
R.append(f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append(f"V1 OVER-lean (p_under<0.45): N={v1_n}, over%={v1_over_rate:.3f}, ROI={v1_roi:+.1f}%")
R.append("")

# Standalone
R.append("## Standalone Triage")
R.append("")
R.append("| Signal | Name | Best Bucket | N | Over% | ROI | Stable | Corr | Verdict |")
R.append("|--------|------|------------|---|-------|-----|--------|------|---------|")
for sr in standalone_results:
    best_e = max(sr["extremes"], key=lambda e: e.get("roi", -999) if not np.isnan(e.get("roi", -999)) else -999)
    N = best_e["N"]
    or_s = f"{best_e.get('over_rate',0):.3f}" if not np.isnan(best_e.get("over_rate", np.nan)) else "N/A"
    roi_s = f"{best_e.get('roi',0):+.1f}%" if not np.isnan(best_e.get("roi", np.nan)) else "N/A"
    R.append(f"| {sr['signal']} | {sr['name']} | {best_e['bucket']} | {N} | {or_s} | {roi_s} | "
             f"{sr['stability']} | {sr['corr_class']}({sr['market_corr']:.3f}) | **{sr['verdict']}** |")
R.append("")

# V1 Interaction
R.append("## V1 OVER-Lean Interaction")
R.append("")
R.append("| Signal | Name | Bucket | N | Over% | ROI | V1 ROI | Lift | 2024 | 2025 |")
R.append("|--------|------|--------|---|-------|-----|--------|------|------|------|")
for _, row in lb_df.iterrows():
    pooled = int_df[(int_df.signal==row.signal) & (int_df.bucket==row.v1_int_bucket) & (int_df.year=="pooled")]
    if len(pooled) > 0 and not np.isnan(pooled.roi.values[0]):
        p = pooled.iloc[0]
        l24 = f"{row.int_2024_lift:+.1f}" if not np.isnan(row.int_2024_lift) else "N/A"
        l25 = f"{row.int_2025_lift:+.1f}" if not np.isnan(row.int_2025_lift) else "N/A"
        thin = " (THIN)" if p.get("thin", False) else ""
        R.append(f"| {row.signal} | {row['name']} | {row.v1_int_bucket} | {p.N:.0f}{thin} | "
                 f"{p.over_rate:.3f} | {p.roi:+.1f}% | {p.v1_roi:+.1f}% | {p.lift_roi:+.1f}pp | {l24} | {l25} |")
R.append("")

# Leaderboard
R.append("## Leaderboard")
R.append("")
R.append("| Rank | Signal | Standalone | V1 Lift | V1 N | Stable | Corr | Rec |")
R.append("|------|--------|-----------|---------|------|--------|------|-----|")
for i, (_, row) in enumerate(lb_df.iterrows()):
    sr_s = f"{row.standalone_roi:+.1f}%" if not np.isnan(row.standalone_roi) else "N/A"
    il_s = f"{row.v1_int_roi_lift:+.1f}pp" if not np.isnan(row.v1_int_roi_lift) else "N/A"
    R.append(f"| {i+1} | {row.signal} ({row['name']}) | {sr_s} | {il_s} | {row.v1_int_N:.0f} | "
             f"{row.year_stability} | {row.market_corr_class} | **{row.recommendation}** |")
R.append("")

# Safety
R.append("## Safety Checks")
for line in safety_lines:
    R.append(line)
R.append("")

# Final answers
R.append("## Final Answers")
R.append("")

promotes = [sr for sr in standalone_results if sr["verdict"] == "PROMOTE"]
investigates = [sr for sr in standalone_results if sr["verdict"] == "INVESTIGATE"]
shelved = [sr for sr in standalone_results if sr["verdict"] == "SHELVE"]

R.append("### Q1: Standalone value?")
if promotes:
    R.append(f"- PROMOTE: {', '.join(s['signal'] + ' ' + s['name'] for s in promotes)}")
if investigates:
    R.append(f"- INVESTIGATE: {', '.join(s['signal'] + ' ' + s['name'] for s in investigates)}")
if shelved:
    R.append(f"- SHELVE: {', '.join(s['signal'] + ' ' + s['name'] for s in shelved)}")
R.append("")

R.append("### Q2: V1 OVER-lean amplifiers?")
candidates = lb_df[lb_df.v1_int_roi_lift > 3]
if len(candidates) > 0:
    for _, c in candidates.iterrows():
        R.append(f"- {c.signal} ({c['name']}): +{c.v1_int_roi_lift:.1f}pp, N={c.v1_int_N:.0f}")
else:
    R.append("- No signal provides >3pp V1 OVER-lean lift at N≥50")
R.append("")

R.append("### Q3: Strongest interaction candidate?")
if len(lb_df) > 0 and not np.isnan(lb_df.iloc[0].v1_int_roi_lift):
    top = lb_df.iloc[0]
    R.append(f"- **{top.signal} ({top['name']})**: +{top.v1_int_roi_lift:.1f}pp lift")
else:
    R.append("- None")
R.append("")

R.append("## Recommended Next Deep Analysis Candidates")
R.append("")
promoted = lb_df[lb_df.recommendation == "PROMOTE"]
if len(promoted) > 0:
    for i, (_, r) in enumerate(promoted.head(3).iterrows()):
        R.append(f"{i+1}. **{r.signal} ({r['name']})** — V1 lift {r.v1_int_roi_lift:+.1f}pp, "
                 f"standalone {r.standalone_roi:+.1f}%, {r.year_stability}")
else:
    held = lb_df[lb_df.recommendation == "HOLD"]
    if len(held) > 0:
        R.append("No signals strong enough for immediate deep analysis.")
        R.append("Candidates for future monitoring:")
        for i, (_, r) in enumerate(held.head(3).iterrows()):
            il = f"{r.v1_int_roi_lift:+.1f}pp" if not np.isnan(r.v1_int_roi_lift) else "N/A"
            R.append(f"{i+1}. {r.signal} ({r['name']}) — V1 lift {il}, {r.year_stability}")
    else:
        R.append("No signals strong enough. All 10 Wave 1 OVER signals shelved.")
R.append("")

out = BASE / "over_wave1_scan_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"Saved: {out}")
print("Done.")
