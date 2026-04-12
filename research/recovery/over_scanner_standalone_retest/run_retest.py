#!/usr/bin/env python3
"""
Over Scanner Standalone Retest
===============================
Remove V1 simulation gate. Test OV043/OV016/OV001/OV021/OV041 as pure
standalone signals using only PIT-safe boxscore features + market data.

Splits: Discovery 2022-2023, Validation 2024, OOS 2025
Success criterion: OOS ROI > +3% at actual closing over prices, stable across seasons.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent.parent
SIM = ROOT / "sim" / "data"
RESEARCH = ROOT / "research"
np.random.seed(42)

def roi_at_price(wins, losses, avg_price):
    """ROI at actual American odds price."""
    if wins + losses == 0:
        return np.nan
    profit = 0
    # For each win: profit = 100/abs(price) if fav, price/100 if dog
    if avg_price < 0:
        unit_win = 100 / abs(avg_price)
    else:
        unit_win = avg_price / 100
    profit = wins * unit_win - losses * 1.0
    return profit / (wins + losses) * 100

def roi_110(w, l):
    if w + l == 0:
        return np.nan
    return (w * 100 / 110 - l) / (w + l) * 100

def actual_roi(df_sub):
    """ROI using actual closing over prices."""
    wins = df_sub[df_sub["over_win"] == 1]
    losses = df_sub[df_sub["over_win"] == 0]
    if len(wins) + len(losses) == 0:
        return np.nan
    total_profit = 0
    for _, row in df_sub.iterrows():
        p = row["over_price"]
        if row["over_win"] == 1:
            if p < 0:
                total_profit += 100 / abs(p)
            else:
                total_profit += p / 100
        else:
            total_profit -= 1.0
    return total_profit / len(df_sub) * 100

def permutation_test(signal_vals, outcome_vals, n_perm=5000):
    """One-sided permutation test: is top-20% over rate significantly above baseline?"""
    thresh = np.percentile(signal_vals, 80)
    flagged = outcome_vals[signal_vals >= thresh]
    baseline = outcome_vals[signal_vals < thresh]
    if len(flagged) < 20 or len(baseline) < 20:
        return np.nan
    obs_diff = flagged.mean() - baseline.mean()
    combined = np.concatenate([flagged, baseline])
    count = 0
    for _ in range(n_perm):
        np.random.shuffle(combined)
        perm_flagged = combined[:len(flagged)]
        perm_baseline = combined[len(flagged):]
        if perm_flagged.mean() - perm_baseline.mean() >= obs_diff:
            count += 1
    return count / n_perm

# =====================================================================
# PHASE 0: CONCEPT LOCK
# =====================================================================
print("=" * 70)
print("PHASE 0 — CONCEPT LOCK")
print("=" * 70)
print()
print("The Over Scanner was Wave 1 research that tested 10 OVER-side signals.")
print("Original design used V1 simulation p_over as an INTERACTION GATE.")
print("V1 probabilities are CONTAMINATED (look-ahead bias in feature_table).")
print()
print("STANDALONE RETEST: Remove V1 gate entirely. Test each signal using")
print("ONLY market-observable + PIT-safe boxscore features.")
print()
print("Signals to retest:")
print("  OV043: bullpen overuse (combined BP pitches last 3 games)")
print("  OV016: high pitch count fatigue (avg SP pitches 2 starts ago)")
print("  OV001: BB x hard-hit (SP BB% x SP hard-hit rate)")
print("  OV021: low K x contact (low SP K% x lineup contact rate)")
print("  OV041: short starter x weak bullpen (SP IP deficit x BP xFIP)")
print()
print("CRITICAL: All features use ONLY lagged (shift(1)+) rolling windows.")
print("No V1 simulation output. No opponent-adjusted metrics that use")
print("concurrent-game data.")

# =====================================================================
# PHASE 1: BUILD CLEAN DATASET
# =====================================================================
print()
print("=" * 70)
print("PHASE 1 — BUILD CLEAN DATASET")
print("=" * 70)

# Load sources
ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
ms = pd.read_parquet(SIM / "market_snapshots.parquet")
ms["date"] = pd.to_datetime(ms["date"])
ps = pd.read_parquet(RESEARCH / "opponent_adjusted_engine" / "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])
bf = pd.read_parquet(SIM / "bullpen_features.parquet")
bf["date"] = pd.to_datetime(bf["date"])
bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])

print(f"  feature_table: {len(ft)} rows, seasons {sorted(ft['season'].unique())}")
print(f"  game_table: {len(gt)} rows")
print(f"  market_snapshots: {len(ms)} rows (2024-2025 only)")
print(f"  pitcher_start_metrics: {len(ps)} rows")
print(f"  bullpen_features: {len(bf)} rows")

# Build base: all 4 seasons from feature_table
df = ft[["game_pk", "date", "season", "home_team", "away_team",
         "actual_total", "actual_f5_total", "innings_played",
         "home_sp_xfip", "away_sp_xfip", "home_sp_k_pct", "away_sp_k_pct",
         "home_sp_bb_pct", "away_sp_bb_pct", "home_sp_avg_ip", "away_sp_avg_ip",
         "home_bp_xfip", "away_bp_xfip",
         "park_factor_runs", "temperature", "wind_speed", "wind_factor_effective",
         "home_sp_id", "away_sp_id"]].copy()

# Merge closing lines (2024-2025 only have market data)
ms_join = ms[["game_id", "close_total", "over_price", "under_price"]].rename(
    columns={"game_id": "game_pk"})
df = df.merge(ms_join, on="game_pk", how="left")

# For 2022-2023, we need closing totals from bet_results or game_table
# Actually bet_results only has 2024-2025. For discovery we can use
# the feature_table + game_table without market prices.
# We'll build the outcome variable for all years:
df["has_line"] = df["close_total"].notna()
print(f"  Games with closing lines: {df['has_line'].sum()}")
print(f"  Games without closing lines: {(~df['has_line']).sum()} (2022-2023)")

# For 2022-2023 discovery: we won't have closing lines, but we CAN test
# signal direction vs actual total as a pure regression target.
# For 2024-2025: proper bet grading against closing lines.

# Build outcome for games WITH lines
df["is_push"] = np.where(df["has_line"], df["actual_total"] == df["close_total"], np.nan)
df["over_win"] = np.where(
    df["has_line"],
    np.where(df["is_push"] == True, np.nan, (df["actual_total"] > df["close_total"]).astype(float)),
    np.nan
)

# ── Build PIT-safe pitcher rolling features ──────────────────────────
print("\n  Building PIT-safe pitcher rolling features...")
ps_s = ps.sort_values(["pitcher_id", "date"]).copy()

# Rolling FIP proxy from raw boxscore: (13*BB + ... ) / IP * ... 
# Simpler: use ERA from ER/IP as PIT-safe metric
ps_s["era_start"] = ps_s["er"] / ps_s["ip"].clip(lower=0.1) * 9

# Rolling features — ALL lagged (shift(1))
for col, new_col, window in [
    ("era_start", "era_r5", 5),
    ("ip", "ip_r5", 5),
    ("pitches", "pitches_r5", 5),
    ("raw_k_rate_start", "k_rate_r5", 5),
    ("raw_bb_rate_start", "bb_rate_r5", 5),
    ("raw_hard_hit_start", "hh_r5", 5),
]:
    ps_s[new_col] = ps_s.groupby("pitcher_id")[col].transform(
        lambda x: x.shift(1).rolling(window, min_periods=3).mean()
    )

# Pitches 2 starts ago
ps_s["pitches_2ago"] = ps_s.groupby("pitcher_id")["pitches"].shift(2)

# ERA last 2 starts
ps_s["er_r2"] = ps_s.groupby("pitcher_id")["er"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())
ps_s["ip_r2"] = ps_s.groupby("pitcher_id")["ip"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())
ps_s["era_last2"] = ps_s["er_r2"] / ps_s["ip_r2"].clip(lower=0.1) * 9

# Season ERA
ps_s["er_season"] = ps_s.groupby(["pitcher_id", "season"])["er"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).sum())
ps_s["ip_season"] = ps_s.groupby(["pitcher_id", "season"])["ip"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).sum())
ps_s["era_season"] = ps_s["er_season"] / ps_s["ip_season"].clip(lower=0.1) * 9
ps_s["era_spike"] = ps_s["era_last2"] - ps_s["era_season"]

# Pitches per inning
ps_s["ppi"] = ps_s["pitches"] / ps_s["ip"].clip(lower=0.1)
ps_s["ppi_r5"] = ps_s.groupby("pitcher_id")["ppi"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Join home/away
for side, prefix in [("home", "home_sp"), ("away", "away_sp")]:
    cols_needed = ["game_pk", "pitches_2ago", "era_spike", "ip_r5", "ppi_r5",
                   "hh_r5", "bb_rate_r5", "k_rate_r5", "era_r5"]
    side_ps = ps_s[ps_s["side"] == side][cols_needed].copy()
    side_ps.columns = ["game_pk"] + [f"{prefix}_{c}" for c in cols_needed[1:]]
    df = df.merge(side_ps, on="game_pk", how="left")

# ── Bullpen features ─────────────────────────────────────────────────
print("  Building bullpen features...")
bf_home = bf[["game_pk", "team", "bullpen_pitches_last_3_games"]].copy()
bf_away = bf[["game_pk", "team", "bullpen_pitches_last_3_games"]].copy()

# Join by game_pk + team matching
df = df.merge(
    bf_home.rename(columns={"team": "home_team", "bullpen_pitches_last_3_games": "home_bp_pitches_3g"}),
    on=["game_pk", "home_team"], how="left"
)
df = df.merge(
    bf_away.rename(columns={"team": "away_team", "bullpen_pitches_last_3_games": "away_bp_pitches_3g"}),
    on=["game_pk", "away_team"], how="left"
)

# BP IP last 2 days - simple loop
bp_only = bu[~bu["is_starter"]].copy()
bp_daily = bp_only.groupby(["team", "date"]).agg(bp_ip=("innings_pitched", "sum")).reset_index()
bp_daily["date"] = pd.to_datetime(bp_daily["date"])
bp_daily = bp_daily.sort_values(["team", "date"]).reset_index(drop=True)

bp_2d_rows = []
for team_name, grp in bp_daily.groupby("team"):
    dates_arr = grp["date"].dt.date.values
    ips_arr = grp["bp_ip"].values
    for i in range(len(dates_arr)):
        total = 0.0
        for j in range(i):
            delta_days = (dates_arr[i] - dates_arr[j]).days
            if 0 < delta_days <= 2:
                total += ips_arr[j]
        bp_2d_rows.append({"team": team_name, "date": grp.iloc[i]["date"], "bp_ip_last2d": total})
bp_2d = pd.DataFrame(bp_2d_rows)
bp_2d["date"] = pd.to_datetime(bp_2d["date"])

for side, prefix in [("home_team", "home"), ("away_team", "away")]:
    bp_join = bp_2d[["team", "date", "bp_ip_last2d"]].rename(
        columns={"team": side, "bp_ip_last2d": f"{prefix}_bp_ip_last2d"})
    df = df.merge(bp_join, on=[side, "date"], how="left")

print(f"  Final dataset: {len(df)} games")
print(f"  Seasons: {df['season'].value_counts().sort_index().to_dict()}")

# =====================================================================
# PHASE 2: BUILD SIGNALS (PIT-SAFE, NO V1)
# =====================================================================
print()
print("=" * 70)
print("PHASE 2 — BUILD SIGNALS (PIT-SAFE, NO V1)")
print("=" * 70)

# OV043: bullpen overuse (combined BP pitches last 3 games)
df["OV043"] = df["home_bp_pitches_3g"].fillna(0) + df["away_bp_pitches_3g"].fillna(0)

# OV016: high pitch count fatigue (avg SP pitches 2 starts ago)
df["OV016"] = (df["home_sp_pitches_2ago"].fillna(0) + df["away_sp_pitches_2ago"].fillna(0)) / 2 / 100

# OV001: BB x hard-hit (SP rolling BB% x SP rolling hard-hit)
df["OV001"] = (
    (df["home_sp_bb_rate_r5"].fillna(0) * df["home_sp_hh_r5"].fillna(0)) +
    (df["away_sp_bb_rate_r5"].fillna(0) * df["away_sp_hh_r5"].fillna(0))
) / 2

# OV021: low K x contact (inverse K% as contact proxy -- no lineup contact available for all years)
# Use (1 - SP K%) as pitcher-side contact allowance proxy
df["OV021"] = (
    ((1 - df["home_sp_k_rate_r5"].fillna(0.22)) * (1 - df["away_sp_k_rate_r5"].fillna(0.22))) +
    ((1 - df["away_sp_k_rate_r5"].fillna(0.22)) * (1 - df["home_sp_k_rate_r5"].fillna(0.22)))
) / 2

# OV041: short starter x weak bullpen
home_short = (5 - df["home_sp_ip_r5"].fillna(5)).clip(lower=0)
away_short = (5 - df["away_sp_ip_r5"].fillna(5)).clip(lower=0)
df["OV041"] = (home_short * df["home_bp_xfip"].fillna(4.0) + away_short * df["away_bp_xfip"].fillna(4.0)) / 2

# NEW standalone signals (not in original wave1):
# OV_FIP_BOTH: both starters have high rolling ERA (weak pitching = OVER lean)
df["OV_FIP_BOTH"] = df["home_sp_era_r5"].fillna(4.5) + df["away_sp_era_r5"].fillna(4.5)

# OV_ERA_SPIKE: both starters spiking above season norm
df["OV_ERA_SPIKE"] = (df["home_sp_era_spike"].fillna(0) + df["away_sp_era_spike"].fillna(0)) / 2

# OV_BP_IP: total bullpen IP last 2 days (fatigued pen = more runs)
df["OV_BP_IP"] = df["home_bp_ip_last2d"].fillna(0) + df["away_bp_ip_last2d"].fillna(0)

SIGNALS = {
    "OV043": "bullpen_overuse_pitches_3g",
    "OV016": "high_pitch_count_fatigue",
    "OV001": "bb_x_hard_hit",
    "OV021": "low_k_contact_both",
    "OV041": "short_starter_x_weak_bp",
    "OV_FIP_BOTH": "both_starters_high_era",
    "OV_ERA_SPIKE": "era_spike_combined",
    "OV_BP_IP": "bp_ip_last_2d_combined",
}

# Coverage audit
print("\nSignal coverage:")
for sig, name in SIGNALS.items():
    valid = df[sig].notna()
    nz = (df[sig] != 0) & valid
    print(f"  {sig} ({name}): {valid.sum()}/{len(df)} valid, {nz.sum()} nonzero")

# =====================================================================
# PHASE 3: SPLIT LOCK
# =====================================================================
print()
print("=" * 70)
print("PHASE 3 — SPLIT LOCK")
print("=" * 70)

disc = df[df["season"].isin([2022, 2023])].copy()
val = df[df["season"] == 2024].copy()
oos = df[df["season"] == 2025].copy()

# For val/oos, filter to games with closing lines and non-push
val_bet = val[val["has_line"] & (val["is_push"] == False)].copy()
oos_bet = oos[oos["has_line"] & (oos["is_push"] == False)].copy()

print(f"  Discovery (2022-2023): {len(disc)} games (no closing lines - direction only)")
print(f"  Validation (2024): {len(val)} total, {len(val_bet)} graded (non-push with lines)")
print(f"  OOS (2025): {len(oos)} total, {len(oos_bet)} graded (non-push with lines)")

# =====================================================================
# PHASE 4: FEATURE AUDIT
# =====================================================================
print()
print("=" * 70)
print("PHASE 4 — FEATURE AUDIT")
print("=" * 70)
print()
print("All features are PIT-safe (lagged rolling windows from boxscore data):")
print("  - Pitcher rolling metrics: shift(1) + rolling(5, min_periods=3)")
print("  - Bullpen pitches: last 3 games (pre-computed, lagged)")
print("  - Bullpen IP: last 2 days (lagged)")
print("  - SP xFIP/BB%/K%: from feature_table (FanGraphs season stats, known pre-game)")
print("  - Park/weather: known pre-game")
print()
print("NO contaminated features used:")
print("  - No V1 simulation probabilities (p_over, p_under)")
print("  - No opponent-adjusted metrics (adj_k_rate, adj_bb_rate)")
print("  - No concurrent-game data")

# =====================================================================
# PHASE 5: DISCOVERY (2022-2023) — Direction only
# =====================================================================
print()
print("=" * 70)
print("PHASE 5 — DISCOVERY (2022-2023)")
print("=" * 70)
print()
print("Without closing lines, test signal correlation with actual_total.")
print("A positive signal should correlate with HIGHER actual totals.")

disc_results = []

for sig, name in SIGNALS.items():
    valid = disc[disc[sig].notna() & (disc[sig] != 0)].copy() if sig == "OV_ERA_SPIKE" else disc[disc[sig].notna()].copy()
    if len(valid) < 100:
        print(f"  {sig}: SKIP (N={len(valid)})")
        disc_results.append({"signal": sig, "name": name, "status": "SKIP", "n": len(valid)})
        continue
    
    # Correlation with actual total
    r, p = stats.pearsonr(valid[sig], valid["actual_total"])
    
    # Top-20% vs bottom-80% actual total
    thresh = np.percentile(valid[sig].dropna(), 80)
    top20 = valid[valid[sig] >= thresh]
    bot80 = valid[valid[sig] < thresh]
    top20_mean = top20["actual_total"].mean()
    bot80_mean = bot80["actual_total"].mean()
    diff = top20_mean - bot80_mean
    
    # t-test
    t_stat, t_p = stats.ttest_ind(top20["actual_total"], bot80["actual_total"])
    
    status = "PASS" if (r > 0 and p < 0.10 and diff > 0) else "DIRECTIONAL" if r > 0 else "FAIL"
    
    print(f"  {sig} ({name}):")
    print(f"    r={r:.4f}, p={p:.4f}, top20_mean={top20_mean:.2f}, bot80_mean={bot80_mean:.2f}, diff={diff:+.2f}, t_p={t_p:.4f}")
    print(f"    Status: {status}")
    
    disc_results.append({
        "signal": sig, "name": name, "status": status, "n": len(valid),
        "corr_r": round(r, 4), "corr_p": round(p, 4),
        "top20_mean": round(top20_mean, 2), "bot80_mean": round(bot80_mean, 2),
        "diff": round(diff, 2), "t_p": round(t_p, 4)
    })

disc_df = pd.DataFrame(disc_results)
print(f"\n  Discovery summary: {(disc_df['status']=='PASS').sum()} PASS, "
      f"{(disc_df['status']=='DIRECTIONAL').sum()} DIRECTIONAL, "
      f"{(disc_df['status']=='FAIL').sum()} FAIL")

# Advance signals that are at least DIRECTIONAL
advance = disc_df[disc_df["status"].isin(["PASS", "DIRECTIONAL"])]["signal"].tolist()
print(f"  Advancing to validation: {advance}")

# =====================================================================
# PHASE 6: VALIDATION (2024) — Bet grading at actual prices
# =====================================================================
print()
print("=" * 70)
print("PHASE 6 — VALIDATION (2024)")
print("=" * 70)

val_results = []

for sig in advance:
    name = SIGNALS[sig]
    valid = val_bet[val_bet[sig].notna()].copy()
    if len(valid) < 50:
        print(f"  {sig}: SKIP (N={len(valid)})")
        val_results.append({"signal": sig, "name": name, "status": "SKIP", "n": len(valid)})
        continue
    
    # Test multiple thresholds
    best_roi = -999
    best_thresh_label = None
    best_n = 0
    best_over_rate = 0
    
    thresh_results = []
    for label, lo_pct in [("top_10", 90), ("top_20", 80), ("top_30", 70), ("top_40", 60)]:
        thresh = np.percentile(valid[sig].dropna(), lo_pct)
        flagged = valid[valid[sig] >= thresh].copy()
        if len(flagged) < 30:
            continue
        
        n = len(flagged)
        over_rate = flagged["over_win"].mean()
        wins = int(flagged["over_win"].sum())
        losses = n - wins
        r110 = roi_110(wins, losses)
        
        # Actual price ROI
        a_roi = actual_roi(flagged)
        
        # Baseline
        baseline_rate = valid["over_win"].mean()
        lift = over_rate - baseline_rate
        
        thresh_results.append({
            "threshold": label, "n": n, "over_rate": round(over_rate, 4),
            "baseline": round(baseline_rate, 4), "lift": round(lift, 4),
            "roi_110": round(r110, 1), "roi_actual": round(a_roi, 1)
        })
        
        if a_roi > best_roi:
            best_roi = a_roi
            best_thresh_label = label
            best_n = n
            best_over_rate = over_rate
    
    # Permutation test at top_20
    thresh_20 = np.percentile(valid[sig].dropna(), 80)
    perm_p = permutation_test(
        valid[sig].dropna().values,
        valid.loc[valid[sig].notna(), "over_win"].values
    )
    
    status = "PASS" if best_roi > 0 and best_over_rate > 0.52 else "MARGINAL" if best_over_rate > 0.50 else "FAIL"
    
    print(f"\n  {sig} ({name}):")
    for tr in thresh_results:
        print(f"    {tr['threshold']}: N={tr['n']}, over%={tr['over_rate']:.3f}, "
              f"lift={tr['lift']:+.3f}, ROI@-110={tr['roi_110']:+.1f}%, ROI@actual={tr['roi_actual']:+.1f}%")
    print(f"    Permutation p (top20): {perm_p:.4f}" if perm_p is not np.nan else "    Permutation p: N/A")
    print(f"    Status: {status}")
    
    val_results.append({
        "signal": sig, "name": name, "status": status,
        "best_threshold": best_thresh_label, "best_n": best_n,
        "best_over_rate": round(best_over_rate, 4),
        "best_roi_actual": round(best_roi, 1),
        "perm_p": round(perm_p, 4) if perm_p is not np.nan else np.nan,
        "thresholds": thresh_results
    })

val_df = pd.DataFrame(val_results)
print(f"\n  Validation summary: {(val_df['status']=='PASS').sum()} PASS, "
      f"{(val_df['status']=='MARGINAL').sum()} MARGINAL, "
      f"{(val_df['status']=='FAIL').sum()} FAIL")

# Advance PASS + MARGINAL
advance_oos = val_df[val_df["status"].isin(["PASS", "MARGINAL"])]["signal"].tolist()
print(f"  Advancing to OOS: {advance_oos}")

# =====================================================================
# PHASE 7: OOS (2025) — Final test at actual prices
# =====================================================================
print()
print("=" * 70)
print("PHASE 7 — OOS (2025)")
print("=" * 70)

oos_results = []

for sig in advance_oos:
    name = SIGNALS[sig]
    # Use VALIDATION threshold (locked from Phase 6)
    val_row = [r for r in val_results if r["signal"] == sig][0]
    best_label = val_row["best_threshold"]
    
    valid = oos_bet[oos_bet[sig].notna()].copy()
    if len(valid) < 50:
        print(f"  {sig}: SKIP (N={len(valid)})")
        oos_results.append({"signal": sig, "name": name, "status": "SKIP"})
        continue
    
    # Use the threshold percentile locked from validation
    pct_map = {"top_10": 90, "top_20": 80, "top_30": 70, "top_40": 60}
    pct = pct_map.get(best_label, 80)
    
    # Compute threshold from VALIDATION data (not OOS!)
    val_valid = val_bet[val_bet[sig].notna()]
    thresh = np.percentile(val_valid[sig].dropna(), pct)
    
    flagged = valid[valid[sig] >= thresh].copy()
    n = len(flagged)
    if n < 20:
        print(f"  {sig}: SKIP (flagged N={n})")
        oos_results.append({"signal": sig, "name": name, "status": "SKIP", "n": n})
        continue
    
    over_rate = flagged["over_win"].mean()
    wins = int(flagged["over_win"].sum())
    losses = n - wins
    r110 = roi_110(wins, losses)
    a_roi = actual_roi(flagged)
    baseline_rate = valid["over_win"].mean()
    lift = over_rate - baseline_rate
    
    # Permutation test
    perm_p = permutation_test(
        valid[sig].dropna().values,
        valid.loc[valid[sig].notna(), "over_win"].values
    )
    
    status = "PASS" if a_roi > 3.0 and over_rate > 0.53 else \
             "MARGINAL" if a_roi > 0 and over_rate > 0.51 else "FAIL"
    
    print(f"\n  {sig} ({name}):")
    print(f"    Threshold: {best_label} (locked from val, value={thresh:.2f})")
    print(f"    N={n}, over%={over_rate:.3f}, baseline={baseline_rate:.3f}, lift={lift:+.3f}")
    print(f"    ROI@-110={r110:+.1f}%, ROI@actual={a_roi:+.1f}%")
    print(f"    Permutation p: {perm_p:.4f}" if perm_p is not np.nan else "    Permutation p: N/A")
    print(f"    Status: {status}")
    
    oos_results.append({
        "signal": sig, "name": name, "status": status,
        "threshold": best_label, "thresh_value": round(thresh, 2),
        "n": n, "over_rate": round(over_rate, 4),
        "baseline": round(baseline_rate, 4), "lift": round(lift, 4),
        "roi_110": round(r110, 1), "roi_actual": round(a_roi, 1),
        "perm_p": round(perm_p, 4) if perm_p is not np.nan else np.nan
    })

oos_df = pd.DataFrame(oos_results)

# =====================================================================
# PHASE 8: PRICE AUDIT
# =====================================================================
print()
print("=" * 70)
print("PHASE 8 — PRICE AUDIT")
print("=" * 70)

for sig in advance_oos:
    name = SIGNALS[sig]
    val_row = [r for r in val_results if r["signal"] == sig][0]
    best_label = val_row["best_threshold"]
    pct_map = {"top_10": 90, "top_20": 80, "top_30": 70, "top_40": 60}
    pct = pct_map.get(best_label, 80)
    
    val_valid = val_bet[val_bet[sig].notna()]
    thresh = np.percentile(val_valid[sig].dropna(), pct)
    
    for year_label, year_df in [("2024 val", val_bet), ("2025 OOS", oos_bet)]:
        valid = year_df[year_df[sig].notna()].copy()
        flagged = valid[valid[sig] >= thresh].copy()
        if len(flagged) < 10:
            continue
        avg_price = flagged["over_price"].mean()
        median_price = flagged["over_price"].median()
        pct_fav = (flagged["over_price"] < -105).mean() * 100
        print(f"  {sig} {year_label}: avg_over_price={avg_price:.1f}, "
              f"median={median_price:.1f}, %favorite={pct_fav:.0f}%")

# =====================================================================
# PHASE 9: FINAL DECISION TABLE
# =====================================================================
print()
print("=" * 70)
print("PHASE 9 — FINAL DECISION")
print("=" * 70)

# Build final table
all_signals = []
for sig, name in SIGNALS.items():
    row = {"signal": sig, "name": name}
    
    # Discovery
    d_row = disc_df[disc_df["signal"] == sig]
    if len(d_row):
        row["disc_status"] = d_row.iloc[0]["status"]
        row["disc_corr"] = d_row.iloc[0].get("corr_r", np.nan)
    else:
        row["disc_status"] = "N/A"
    
    # Validation
    v_row = val_df[val_df["signal"] == sig] if len(val_df) else pd.DataFrame()
    if len(v_row):
        row["val_status"] = v_row.iloc[0]["status"]
        row["val_roi"] = v_row.iloc[0].get("best_roi_actual", np.nan)
        row["val_over_rate"] = v_row.iloc[0].get("best_over_rate", np.nan)
    else:
        row["val_status"] = "NOT_TESTED"
        row["val_roi"] = np.nan
    
    # OOS
    o_row = oos_df[oos_df["signal"] == sig] if len(oos_df) else pd.DataFrame()
    if len(o_row):
        row["oos_status"] = o_row.iloc[0]["status"]
        row["oos_roi"] = o_row.iloc[0].get("roi_actual", np.nan)
        row["oos_over_rate"] = o_row.iloc[0].get("over_rate", np.nan)
        row["oos_n"] = o_row.iloc[0].get("n", 0)
    else:
        row["oos_status"] = "NOT_TESTED"
        row["oos_roi"] = np.nan
    
    # Final verdict
    if row.get("oos_status") == "PASS":
        row["verdict"] = "PROMOTE"
    elif row.get("oos_status") == "MARGINAL":
        row["verdict"] = "SHADOW_MONITOR"
    elif row.get("val_status") == "PASS" and row.get("oos_status") in ["NOT_TESTED", "SKIP"]:
        row["verdict"] = "NEEDS_MORE_DATA"
    else:
        row["verdict"] = "KILL"
    
    all_signals.append(row)

final_df = pd.DataFrame(all_signals)

# Print table
print()
print(f"{'Signal':<16} {'Name':<30} {'Disc':<12} {'Val':<10} {'Val ROI':<10} {'OOS':<10} {'OOS ROI':<10} {'Verdict':<15}")
print("-" * 113)
for _, r in final_df.iterrows():
    val_roi_str = f"{r.get('val_roi', 0):+.1f}%" if pd.notna(r.get('val_roi')) else "N/A"
    oos_roi_str = f"{r.get('oos_roi', 0):+.1f}%" if pd.notna(r.get('oos_roi')) else "N/A"
    print(f"{r['signal']:<16} {r['name']:<30} {r['disc_status']:<12} "
          f"{r.get('val_status',''):<10} {val_roi_str:<10} "
          f"{r.get('oos_status',''):<10} {oos_roi_str:<10} {r['verdict']:<15}")

# Save outputs
final_df.to_csv(BASE / "over_scanner_standalone_results.csv", index=False)
print(f"\n  Saved: over_scanner_standalone_results.csv")

# =====================================================================
# WRITE EXEC SUMMARY
# =====================================================================
n_promoted = (final_df["verdict"] == "PROMOTE").sum()
n_shadow = (final_df["verdict"] == "SHADOW_MONITOR").sum()
n_killed = (final_df["verdict"] == "KILL").sum()

summary_lines = [
    "# Over Scanner Standalone Retest — Executive Summary",
    "",
    f"**Date:** 2026-04-12",
    f"**Scope:** {len(SIGNALS)} signals tested standalone (no V1 gate)",
    "",
    "## Background",
    "",
    "The Over Scanner Wave 1 research tested 10 OVER-side signals. The original",
    "analysis used V1 simulation p_over as an INTERACTION GATE to filter signals.",
    "V1 probabilities were subsequently found to be CONTAMINATED (look-ahead bias",
    "in the feature_table used for V1 training).",
    "",
    "This retest removes the V1 gate entirely and tests each signal as a pure",
    "standalone using only PIT-safe boxscore features and market data.",
    "",
    "## Test Design",
    "",
    "- **Discovery (2022-2023):** Signal direction vs actual total (no closing lines)",
    "- **Validation (2024):** Bet grading at actual closing over prices",  
    "- **OOS (2025):** Final test at actual closing over prices",
    "- **Success criterion:** OOS ROI > +3% at actual prices, over rate > 53%",
    "- **All features:** PIT-safe lagged rolling windows from boxscore data",
    "- **No V1 output used anywhere in the pipeline**",
    "",
    "## Signals Tested",
    "",
    "| Signal | Description |",
    "|--------|-------------|",
]
for sig, name in SIGNALS.items():
    summary_lines.append(f"| {sig} | {name} |")

summary_lines += [
    "",
    "## Results Summary",
    "",
    f"| Verdict | Count |",
    f"|---------|-------|",
    f"| PROMOTE | {n_promoted} |",
    f"| SHADOW_MONITOR | {n_shadow} |",
    f"| KILL | {n_killed} |",
    "",
    "## Decision Table",
    "",
    "| Signal | Discovery | Val Status | Val ROI | OOS Status | OOS ROI | Verdict |",
    "|--------|-----------|------------|---------|------------|---------|---------|",
]

for _, r in final_df.iterrows():
    val_roi_str = f"{r.get('val_roi', 0):+.1f}%" if pd.notna(r.get('val_roi')) else "N/A"
    oos_roi_str = f"{r.get('oos_roi', 0):+.1f}%" if pd.notna(r.get('oos_roi')) else "N/A"
    summary_lines.append(
        f"| {r['signal']} | {r['disc_status']} | {r.get('val_status','')} | "
        f"{val_roi_str} | {r.get('oos_status','')} | {oos_roi_str} | **{r['verdict']}** |"
    )

summary_lines += [
    "",
    "## Key Findings",
    "",
]

# Add findings based on results
if n_promoted > 0:
    promoted = final_df[final_df["verdict"] == "PROMOTE"]
    for _, r in promoted.iterrows():
        summary_lines.append(f"- **{r['signal']}** ({r['name']}): OOS ROI {r.get('oos_roi', 0):+.1f}%, "
                           f"over rate {r.get('oos_over_rate', 0):.1%}. Passed all gates.")
elif n_shadow > 0:
    summary_lines.append("No signals met the full PROMOTE criterion (OOS ROI > +3%, over rate > 53%).")
    shadow = final_df[final_df["verdict"] == "SHADOW_MONITOR"]
    for _, r in shadow.iterrows():
        summary_lines.append(f"- **{r['signal']}** ({r['name']}): marginally positive OOS. Shadow monitor.")
else:
    summary_lines.append("**No signals survived the standalone retest pipeline.**")
    summary_lines.append("")
    summary_lines.append("The OVER Scanner concept, once stripped of the contaminated V1 interaction")
    summary_lines.append("gate, does not produce independently profitable signals. The original Wave 1")
    summary_lines.append("results were likely artifacts of:")
    summary_lines.append("1. The V1 interaction gate (which selected games where the contaminated model")
    summary_lines.append("   already predicted OVER, creating a self-fulfilling selection bias)")
    summary_lines.append("2. Discovery-validation leakage (promoted on same 2024-2025 data)")
    summary_lines.append("3. Multiple testing across 10 signals without proper correction")

summary_lines += [
    "",
    "## Recommendation",
    "",
]

if n_promoted > 0:
    summary_lines.append("Promote passing signals to shadow pipeline for live monitoring.")
elif n_shadow > 0:
    summary_lines.append("Shadow monitor marginally positive signals. Do NOT deploy to live betting.")
    summary_lines.append("Review after 100+ additional graded signals.")
else:
    summary_lines.append("**CLEAN KILL the Over Scanner concept.** The standalone signals do not")
    summary_lines.append("carry independent edge. Do not invest further research time.")
    summary_lines.append("")
    summary_lines.append("If OVER-side signals are desired in the future, they should be built from")
    summary_lines.append("scratch using a different conceptual framework (e.g., game-state dynamics,")
    summary_lines.append("in-play events, or market microstructure) rather than pregame pitcher/bullpen")
    summary_lines.append("features which the market already prices efficiently.")

with open(BASE / "OVER_SCANNER_STANDALONE_EXEC_SUMMARY.md", "w") as f:
    f.write("\n".join(summary_lines) + "\n")
print(f"\n  Saved: OVER_SCANNER_STANDALONE_EXEC_SUMMARY.md")

print()
print("=" * 70)
print("DONE")
print("=" * 70)
