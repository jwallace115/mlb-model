#!/usr/bin/env python3
"""
Rebuild full 25-feature backtest dataset and compute monthly ROI.
Does NOT modify any production files.
"""
import pandas as pd
import numpy as np
import pickle
import json
import os
from scipy.stats import norm
from pathlib import Path

OUT = Path("research/diagnostics/full_feature_backtest")

# ======================================================================
# STEP 1 — Load base
# ======================================================================
print("=" * 80)
print("STEP 1 — BASE DATA + MODEL")
print("=" * 80)

ft = pd.read_parquet("sim/data/feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
gt = pd.read_parquet("sim/data/game_table.parquet")

with open("sim/data/phase9_baseline_model.pkl", "rb") as f:
    bundle = pickle.load(f)
pipeline = bundle["pipeline"]
feature_names = bundle["features"]
sigma = bundle["sigma"]
scaler = pipeline.named_steps["scaler"]
ridge = pipeline.named_steps["ridge"]

print(f"Feature table: {len(ft)} rows, seasons {sorted(ft['season'].unique())}")
print(f"Model: {len(feature_names)} features, sigma={sigma:.4f}")

# ======================================================================
# STEP 2 — flyball_wind_interaction
# ======================================================================
print(f"\n{'='*80}")
print("STEP 2 — FLYBALL_WIND_INTERACTION")
print("=" * 80)

# Build pitcher FB% lookup from cache
fb_lookup = {}  # (name_lower, season) → fb_pct
league_avg_fb = {}  # season → league_avg

for yr in [2022, 2023, 2024, 2025]:
    cache = f"sim/data/cache/fb_pct_{yr}.parquet"
    df_fb = pd.read_parquet(cache)
    avg = df_fb["fb_pct"].mean()
    league_avg_fb[yr] = avg
    for _, row in df_fb.iterrows():
        fb_lookup[(row["name_lower"], yr)] = row["fb_pct"]
    print(f"  {yr}: {len(df_fb)} pitchers, league avg FB%={avg:.3f}")

def get_fb(sp_name, season):
    if pd.isna(sp_name):
        return league_avg_fb.get(season, 0.35)
    key = (str(sp_name).lower().strip(), season)
    return fb_lookup.get(key, league_avg_fb.get(season, 0.35))

ft["home_sp_fb_pct"] = ft.apply(lambda r: get_fb(r["home_sp_name"], r["season"]), axis=1)
ft["away_sp_fb_pct"] = ft.apply(lambda r: get_fb(r["away_sp_name"], r["season"]), axis=1)

# wind_out_flag: open roof AND wind_factor_effective > 3
ft["wind_out_flag"] = (
    (ft["roof_status"] == "open") & (ft["wind_factor_effective"] > 3)
).astype(float)

ft["flyball_wind_interaction"] = (ft["home_sp_fb_pct"] + ft["away_sp_fb_pct"]) * ft["wind_out_flag"]

coverage = ft["flyball_wind_interaction"].notna().mean()
print(f"  flyball_wind_interaction coverage: {coverage*100:.1f}%")
print(f"  wind_out games: {int(ft['wind_out_flag'].sum())}")
print(f"  mean flyball_wind: {ft['flyball_wind_interaction'].mean():.4f}")

# ======================================================================
# STEP 3 — high_leverage_avail
# ======================================================================
print(f"\n{'='*80}")
print("STEP 3 — HIGH_LEVERAGE_AVAIL")
print("=" * 80)

bp = pd.read_parquet("sim/data/bullpen_features.parquet")
print(f"bullpen_features: {len(bp)} rows, cols={list(bp.columns)}")

# Pivot: home team's high_leverage_available per game
bp_h = bp.merge(
    ft[["game_pk", "home_team"]].drop_duplicates("game_pk"),
    left_on=["game_pk", "team"], right_on=["game_pk", "home_team"], how="inner"
)[["game_pk", "high_leverage_available"]].rename(
    columns={"high_leverage_available": "home_high_leverage_avail"}
).drop_duplicates("game_pk")

bp_a = bp.merge(
    ft[["game_pk", "away_team"]].drop_duplicates("game_pk"),
    left_on=["game_pk", "team"], right_on=["game_pk", "away_team"], how="inner"
)[["game_pk", "high_leverage_available"]].rename(
    columns={"high_leverage_available": "away_high_leverage_avail"}
).drop_duplicates("game_pk")

ft = ft.merge(bp_h, on="game_pk", how="left")
ft = ft.merge(bp_a, on="game_pk", how="left")

# Fill NaN with 1 (assume available if no data)
ft["home_high_leverage_avail"] = ft["home_high_leverage_avail"].fillna(1)
ft["away_high_leverage_avail"] = ft["away_high_leverage_avail"].fillna(1)

print(f"  home_high_leverage_avail coverage: {ft['home_high_leverage_avail'].notna().mean()*100:.1f}%")
print(f"  away_high_leverage_avail coverage: {ft['away_high_leverage_avail'].notna().mean()*100:.1f}%")

# ======================================================================
# STEP 4 — bullpen_delta and bp_delta_exposure
# ======================================================================
print(f"\n{'='*80}")
print("STEP 4 — BULLPEN_DELTA AND BP_DELTA_EXPOSURE")
print("=" * 80)

bu = pd.read_parquet("sim/data/bullpen_usage.parquet")
print(f"bullpen_usage: {len(bu)} rows, cols={list(bu.columns)}")

# Compute bullpen_delta per team per game:
# For each game, compute team's bullpen usage in last 3 games minus season expanding mean
# This matches the Phase 8 formula
bu_rlv = bu[bu["is_starter"] == 0].copy()  # relievers only
bu_rlv = bu_rlv.sort_values(["team", "date", "game_pk"])

# Per-team per-game: total reliever pitches
team_game_usage = bu_rlv.groupby(["game_pk", "date", "season", "team"]).agg(
    bp_pitches=("pitches_thrown", "sum"),
    bp_innings=("innings_pitched", "sum"),
).reset_index()
team_game_usage["date"] = pd.to_datetime(team_game_usage["date"])
team_game_usage = team_game_usage.sort_values(["team", "date"])

# Rolling 3-game bullpen pitches (shift 1 to avoid leakage)
# Season expanding mean (shift 1)
team_game_usage["bp_pitches_r3"] = team_game_usage.groupby(["team", "season"])[
    "bp_pitches"
].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())

team_game_usage["bp_pitches_season_avg"] = team_game_usage.groupby(["team", "season"])[
    "bp_pitches"
].transform(lambda x: x.shift(1).expanding(min_periods=3).mean())

# Delta = recent - baseline
team_game_usage["bullpen_delta"] = team_game_usage["bp_pitches_r3"] - team_game_usage["bp_pitches_season_avg"]

# bp_proj_inn from feature_table
# This is the projected bullpen innings (already in ft as home_bp_proj_inn / away_bp_proj_inn)
# bp_delta_exposure = bullpen_delta × bp_proj_inn

# Pivot to home/away
delta_h = team_game_usage.merge(
    ft[["game_pk", "home_team", "home_bp_proj_inn"]].drop_duplicates("game_pk"),
    left_on=["game_pk", "team"], right_on=["game_pk", "home_team"], how="inner"
)[["game_pk", "bullpen_delta", "home_bp_proj_inn"]].rename(
    columns={"bullpen_delta": "home_bullpen_delta"}
).drop_duplicates("game_pk")
delta_h["home_bp_delta_exposure"] = delta_h["home_bullpen_delta"] * delta_h["home_bp_proj_inn"]

delta_a = team_game_usage.merge(
    ft[["game_pk", "away_team", "away_bp_proj_inn"]].drop_duplicates("game_pk"),
    left_on=["game_pk", "team"], right_on=["game_pk", "away_team"], how="inner"
)[["game_pk", "bullpen_delta", "away_bp_proj_inn"]].rename(
    columns={"bullpen_delta": "away_bullpen_delta"}
).drop_duplicates("game_pk")
delta_a["away_bp_delta_exposure"] = delta_a["away_bullpen_delta"] * delta_a["away_bp_proj_inn"]

ft = ft.merge(delta_h[["game_pk", "home_bullpen_delta", "home_bp_delta_exposure"]], on="game_pk", how="left")
ft = ft.merge(delta_a[["game_pk", "away_bullpen_delta", "away_bp_delta_exposure"]], on="game_pk", how="left")

# Fill NaN with 0 (no data = no delta)
for col in ["home_bullpen_delta", "away_bullpen_delta", "home_bp_delta_exposure", "away_bp_delta_exposure"]:
    ft[col] = ft[col].fillna(0)

for col in ["home_bullpen_delta", "away_bullpen_delta", "home_bp_delta_exposure", "away_bp_delta_exposure"]:
    cov = ft[col].notna().mean()
    non_zero = (ft[col] != 0).mean()
    print(f"  {col}: coverage={cov*100:.1f}%, non-zero={non_zero*100:.1f}%, mean={ft[col].mean():.4f}")

# ======================================================================
# STEP 5 — Verify all 25 features
# ======================================================================
print(f"\n{'='*80}")
print("STEP 5 — FEATURE COVERAGE VERIFICATION")
print("=" * 80)

print(f"\n{'feature':<30} {'%pop':>7} {'mean':>10} {'std':>10} {'notes'}")
print("-" * 70)

all_good = True
for f_name in feature_names:
    if f_name not in ft.columns:
        print(f"{f_name:<30} {'MISSING':>7}")
        all_good = False
        continue
    pct = ft[f_name].notna().mean() * 100
    mean = ft[f_name].mean()
    std = ft[f_name].std()
    note = ""
    if pct < 90:
        note = "*** LOW COVERAGE"
        all_good = False
    # Fill remaining NaN with median
    if ft[f_name].isna().any():
        med = ft[f_name].median()
        if pd.isna(med):
            med = 0
        ft[f_name] = ft[f_name].fillna(med)
        note += f" (filled {(100-pct):.1f}% with median)"
    print(f"{f_name:<30} {pct:>6.1f}% {mean:>10.4f} {std:>10.4f} {note}")

assert ft[feature_names].isna().sum().sum() == 0, "Still have NaN after fill!"
print(f"\nAll 25 features populated: {all_good}")

# ======================================================================
# STEP 6 — Recompute p_under
# ======================================================================
print(f"\n{'='*80}")
print("STEP 6 — RECOMPUTE P_UNDER (FULL FEATURES)")
print("=" * 80)

X = ft[feature_names].values
pred_total = pipeline.predict(X)
ft["pred_total_full"] = pred_total

# Get closing lines
cl = pd.read_parquet("sim/data/mlb_historical_closing_lines.parquet")
ms = pd.read_parquet("sim/data/market_snapshots.parquet")
ms_pk = ms.rename(columns={"game_id": "game_pk"})
ms_pk["game_pk"] = ms_pk["game_pk"].astype(int)
lines = pd.concat([cl[["game_pk", "close_total"]], ms_pk[["game_pk", "close_total"]]],
                  ignore_index=True).drop_duplicates("game_pk", keep="last")

ft = ft.merge(lines, on="game_pk", how="left")
has_data = ft["close_total"].notna() & ft["actual_total"].notna()
df = ft[has_data].copy()

df["p_under_full"] = norm.cdf(df["close_total"], loc=df["pred_total_full"], scale=sigma)
df["month"] = df["date"].dt.month

# Compare to zeroed version
X_zero = df[feature_names].copy()
for col in ["flyball_wind_interaction", "home_high_leverage_avail", "away_high_leverage_avail",
            "home_bullpen_delta", "away_bullpen_delta", "home_bp_delta_exposure", "away_bp_delta_exposure"]:
    X_zero[col] = 0
pred_zero = pipeline.predict(X_zero.values)
df["p_under_zero"] = norm.cdf(df["close_total"], loc=pred_zero, scale=sigma)

print(f"\nGames with lines+actuals: {len(df)}")
print(f"\n{'metric':<30} {'zeroed':>12} {'full_features':>15} {'delta':>10}")
print("-" * 70)
print(f"{'Mean p_under':<30} {df['p_under_zero'].mean():>12.4f} {df['p_under_full'].mean():>15.4f} {df['p_under_full'].mean()-df['p_under_zero'].mean():>+10.4f}")
print(f"{'% above 0.57':<30} {(df['p_under_zero']>0.57).mean()*100:>11.1f}% {(df['p_under_full']>0.57).mean()*100:>14.1f}% {((df['p_under_full']>0.57).mean()-(df['p_under_zero']>0.57).mean())*100:>+9.1f}pp")
print(f"{'% above 0.60':<30} {(df['p_under_zero']>0.60).mean()*100:>11.1f}% {(df['p_under_full']>0.60).mean()*100:>14.1f}% {((df['p_under_full']>0.60).mean()-(df['p_under_zero']>0.60).mean())*100:>+9.1f}pp")
print(f"{'N signals (>0.57)':<30} {(df['p_under_zero']>0.57).sum():>12} {(df['p_under_full']>0.57).sum():>15} {(df['p_under_full']>0.57).sum()-(df['p_under_zero']>0.57).sum():>+10}")

# ======================================================================
# STEP 7 — Signal firing + results
# ======================================================================
print(f"\n{'='*80}")
print("STEP 7 — SIGNAL FIRING + RESULTS")
print("=" * 80)

# S12/P09 overlays: check if CSW data available
# S12 needs sp_csw_pct — not in feature_table. Overlays were deployed March 2026 only.
# For 2022-2025 backtest: overlays = NONE (they didn't exist historically)
# Unit sizes: base only (0.5u and 1.0u)

df["fires"] = df["p_under_full"] > 0.57
df["unit_size"] = np.where(df["p_under_full"] >= 0.60, "1.0u",
                  np.where(df["p_under_full"] > 0.57, "0.5u", "none"))
signals = df[df["fires"]].copy()

signals["result"] = np.where(signals["actual_total"] < signals["close_total"], "W",
                   np.where(signals["actual_total"] > signals["close_total"], "L", "P"))
signals["stake"] = np.where(signals["unit_size"] == "1.0u", 1.0, 0.5)
signals["units_wl"] = np.where(signals["result"] == "W", 0.909 * signals["stake"],
                      -1.0 * signals["stake"])

print(f"Total signals: {len(signals)}")
for s in sorted(signals["season"].unique()):
    for us in ["0.5u", "1.0u"]:
        n = len(signals[(signals["season"]==s) & (signals["unit_size"]==us)])
        if n > 0:
            print(f"  {s} {us}: {n}")

# ======================================================================
# STEP 8 — Monthly arc
# ======================================================================
print(f"\n{'='*80}")
print("STEP 8 — MONTHLY ARC BY UNIT SIZE")
print("=" * 80)

month_map = {3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct"}

print(f"\n{'month':<6} {'unit':<6} {'N':>5} {'W-L-P':<10} {'win%':>7} {'ROI':>8}")
print("-" * 46)

for m in sorted(signals["month"].unique()):
    for us in ["0.5u", "1.0u"]:
        sub = signals[(signals["month"]==m) & (signals["unit_size"]==us)]
        if len(sub) == 0: continue
        w = (sub["result"]=="W").sum()
        l = (sub["result"]=="L").sum()
        p = (sub["result"]=="P").sum()
        wr = w/(w+l)*100 if (w+l)>0 else 0
        roi = sub["units_wl"].sum() / sub["stake"].sum() * 100
        mn = month_map.get(m, f"M{m}")
        thin = " *" if len(sub) < 10 else ""
        print(f"{mn:<6} {us:<6} {len(sub):>5} {f'{w}-{l}-{p}':<10} {wr:>6.1f}% {roi:>+7.1f}%{thin}")

# Arc table
print(f"\n{'unit':<6}", end="")
for m in [3,4,5,6,7,8,9,10]:
    print(f" {month_map.get(m,'?'):>8}", end="")
print()
print("-" * 75)
for us in ["0.5u", "1.0u"]:
    print(f"{us:<6}", end="")
    for m in [3,4,5,6,7,8,9,10]:
        sub = signals[(signals["month"]==m) & (signals["unit_size"]==us)]
        if len(sub) >= 10:
            roi = sub["units_wl"].sum() / sub["stake"].sum() * 100
            print(f" {roi:>+7.1f}%", end="")
        else:
            print(f" {'—':>8}", end="")
    print()

# ======================================================================
# STEP 9 — Cross-check
# ======================================================================
print(f"\n{'='*80}")
print("STEP 9 — CROSS-CHECK VS PUBLISHED VALIDATION")
print("=" * 80)

for thresh, label, target in [(0.57, "p_under > 0.57", "+20.9%"), (0.60, "p_under > 0.60", "+23.8%")]:
    sub = df[df["p_under_full"] > thresh]
    w = (sub["actual_total"] < sub["close_total"]).sum()
    l = (sub["actual_total"] > sub["close_total"]).sum()
    p = (sub["actual_total"] == sub["close_total"]).sum()
    n = w + l + p
    wr = w/(w+l)*100 if (w+l)>0 else 0
    net = w*0.909 - (l+p)
    roi = net/n*100 if n>0 else 0
    print(f"\n  {label} (all seasons): N={n}, {w}W-{l}L-{p}P, wr={wr:.1f}%, ROI={roi:+.1f}%")
    print(f"  Published target: {target}")

    # 2024 OOS specifically
    sub24 = sub[sub["season"]==2024]
    w24 = (sub24["actual_total"] < sub24["close_total"]).sum()
    l24 = (sub24["actual_total"] > sub24["close_total"]).sum()
    p24 = (sub24["actual_total"] == sub24["close_total"]).sum()
    n24 = w24+l24+p24
    roi24 = (w24*0.909-(l24+p24))/n24*100 if n24>0 else 0
    print(f"  2024 OOS: N={n24}, {w24}W-{l24}L-{p24}P, ROI={roi24:+.1f}%")

    sub25 = sub[sub["season"]==2025]
    w25 = (sub25["actual_total"] < sub25["close_total"]).sum()
    l25 = (sub25["actual_total"] > sub25["close_total"]).sum()
    p25 = (sub25["actual_total"] == sub25["close_total"]).sum()
    n25 = w25+l25+p25
    roi25 = (w25*0.909-(l25+p25))/n25*100 if n25>0 else 0
    print(f"  2025 OOS: N={n25}, {w25}W-{l25}L-{p25}P, ROI={roi25:+.1f}%")

# ======================================================================
# STEP 10 — August deep dive
# ======================================================================
print(f"\n{'='*80}")
print("STEP 10 — AUGUST DEEP DIVE")
print("=" * 80)
print(f"\n{'season':<7} {'unit':<6} {'N':>5} {'W-L-P':<10} {'win%':>7} {'ROI':>8}")
print("-" * 44)

aug = signals[signals["month"]==8]
for us in ["0.5u", "1.0u"]:
    neg = 0
    tot = 0
    for s in sorted(aug["season"].unique()):
        sub = aug[(aug["season"]==s) & (aug["unit_size"]==us)]
        if len(sub)==0: continue
        w = (sub["result"]=="W").sum()
        l = (sub["result"]=="L").sum()
        p = (sub["result"]=="P").sum()
        wr = w/(w+l)*100 if (w+l)>0 else 0
        roi = sub["units_wl"].sum()/sub["stake"].sum()*100
        print(f"{s:<7} {us:<6} {len(sub):>5} {f'{w}-{l}-{p}':<10} {wr:>6.1f}% {roi:>+7.1f}%")
        tot += 1
        if roi < 0: neg += 1

    total_n = len(aug[aug["unit_size"]==us])
    if total_n < 10: v = "INSUFFICIENT"
    elif neg >= 3: v = "STRUCTURAL"
    elif neg >= 2: v = "CONSISTENT"
    elif neg == 1: v = "SAMPLE_NOISE"
    else: v = "POSITIVE"
    print(f"  → {us} VERDICT: {v} (neg {neg}/{tot}, total N={total_n})")

# ======================================================================
# STEP 11 — Save outputs
# ======================================================================
print(f"\n{'='*80}")
print("STEP 11 — SAVE OUTPUTS")
print("=" * 80)

signals.to_parquet(OUT / "full_feature_signals_2022_2025.parquet", index=False)
print(f"Saved: {OUT / 'full_feature_signals_2022_2025.parquet'}")
print(f"  {len(signals)} signals")

# Monthly arc parquet
arc_rows = []
for m in sorted(signals["month"].unique()):
    for us in ["0.5u", "1.0u"]:
        sub = signals[(signals["month"]==m) & (signals["unit_size"]==us)]
        if len(sub)==0: continue
        w = (sub["result"]=="W").sum()
        l = (sub["result"]=="L").sum()
        p = (sub["result"]=="P").sum()
        roi = sub["units_wl"].sum()/sub["stake"].sum()*100
        arc_rows.append({"month": m, "month_name": month_map.get(m,f"M{m}"),
                         "unit_size": us, "N": len(sub), "W": w, "L": l, "P": p,
                         "win_rate": w/(w+l)*100 if (w+l)>0 else 0, "roi": round(roi,2)})
arc_df = pd.DataFrame(arc_rows)
arc_df.to_parquet(OUT / "monthly_arc_full_features.parquet", index=False)
print(f"Saved: {OUT / 'monthly_arc_full_features.parquet'}")

# Summary markdown
with open(OUT / "monthly_arc_summary.md", "w") as f:
    f.write("# Monthly ROI Backtest — Full 25 Features (2022-2025)\n\n")
    f.write(f"**Model:** Phase 9 Ridge, 25 features, sigma={sigma:.4f}\n")
    f.write(f"**All features populated:** flyball_wind, high_leverage_avail, bullpen_delta, bp_delta_exposure\n\n")
    f.write("## Seasonal Arc\n\n")
    f.write("| Unit | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |\n")
    f.write("|------|-----|-----|-----|-----|-----|-----|-----|-----|\n")
    for us in ["0.5u", "1.0u"]:
        row = f"| {us} |"
        for m in [3,4,5,6,7,8,9,10]:
            sub = signals[(signals["month"]==m) & (signals["unit_size"]==us)]
            if len(sub) >= 10:
                roi = sub["units_wl"].sum()/sub["stake"].sum()*100
                row += f" {roi:+.1f}% |"
            else:
                row += " — |"
        f.write(row + "\n")
    f.write(f"\n## Overall\n\n")
    for us in ["0.5u", "1.0u"]:
        sub = signals[signals["unit_size"]==us]
        w = (sub["result"]=="W").sum()
        l = (sub["result"]=="L").sum()
        p = (sub["result"]=="P").sum()
        roi = sub["units_wl"].sum()/sub["stake"].sum()*100
        f.write(f"- {us}: {w}-{l}-{p}, wr={w/(w+l)*100:.1f}%, ROI={roi:+.1f}%\n")
print(f"Saved: {OUT / 'monthly_arc_summary.md'}")

print(f"\n{'='*80}")
print("OUTPUT FILES:")
print(f"  {OUT / 'full_feature_signals_2022_2025.parquet'}")
print(f"  {OUT / 'monthly_arc_full_features.parquet'}")
print(f"  {OUT / 'monthly_arc_summary.md'}")
print(f"{'='*80}")
