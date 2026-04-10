#!/usr/bin/env python3
"""
S12 Standalone Revalidation — Clean PIT-safe data only.

S12 = avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)

CSW source: sim_inputs sp_csw_pct (rolling-5 prior starts via shift(1), PIT-safe)
xFIP source: sim_inputs sp_xfip (season-end FanGraphs — KNOWN CONTAMINATED in V1)

IMPORTANT: sp_xfip in sim_inputs comes from the feature_table which was built from
FanGraphs season-end stats. This is the same PIT contamination identified in V1.
We need to use PIT-safe xFIP from v1_clean_features instead.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

OUT = Path("/root/mlb-model/research/recovery/s12_standalone_revalidation")
OUT.mkdir(parents=True, exist_ok=True)

# ─── Phase 1: Build S12 from clean inputs ───────────────────────────────────

print("=" * 70)
print("PHASE 1: Data Assembly & PIT Safety Verification")
print("=" * 70)

# Load sim_inputs (has CSW per-start, PIT-safe via shift(1))
si_hist = pd.read_parquet("/root/mlb-model/mlb_sim/data/sim_inputs_historical_2022_2024.parquet")
si_2025 = pd.read_parquet("/root/mlb-model/mlb_sim/data/sim_inputs_2025.parquet")
si = pd.concat([si_hist, si_2025], ignore_index=True)

# Pivot to game-level
home = si[si["is_home"] == 1][["game_pk", "date", "season", "sp_csw_pct", "sp_xfip"]].rename(
    columns={"sp_csw_pct": "home_csw", "sp_xfip": "home_xfip_CONTAMINATED"})
away = si[si["is_home"] == 0][["game_pk", "sp_csw_pct", "sp_xfip"]].rename(
    columns={"sp_csw_pct": "away_csw", "sp_xfip": "away_xfip_CONTAMINATED"})

games = home.merge(away, on="game_pk", how="inner")

# Load PIT-safe xFIP from v1_clean_features
pit = pd.read_parquet("/root/mlb-model/research/recovery/v1_clean_features/baseball_features_pit_v1.parquet")
pit_xfip = pit[["game_pk", "home_sp_xfip", "away_sp_xfip"]].copy()
pit_xfip = pit_xfip.rename(columns={"home_sp_xfip": "home_xfip_pit", "away_sp_xfip": "away_xfip_pit"})

games = games.merge(pit_xfip, on="game_pk", how="left")

# Check how many have PIT xFIP
n_pit = games["home_xfip_pit"].notna().sum()
n_total = len(games)
print(f"  Games with PIT-safe xFIP: {n_pit}/{n_total}")

# Use PIT-safe xFIP where available, fall back to sim_inputs xFIP with a flag
games["home_xfip"] = games["home_xfip_pit"]
games["away_xfip"] = games["away_xfip_pit"]
games["xfip_pit_safe"] = games["home_xfip_pit"].notna() & games["away_xfip_pit"].notna()

# For games without PIT xFIP, use contaminated (flag it)
mask_no_pit = games["home_xfip"].isna()
games.loc[mask_no_pit, "home_xfip"] = games.loc[mask_no_pit, "home_xfip_CONTAMINATED"]
mask_no_pit = games["away_xfip"].isna()
games.loc[mask_no_pit, "away_xfip"] = games.loc[mask_no_pit, "away_xfip_CONTAMINATED"]

# Get actual totals from feature_table
ft = pd.read_parquet("/root/mlb-model/sim/data/feature_table.parquet")
ft_totals = ft[["game_pk", "actual_total"]].copy()
games = games.merge(ft_totals, on="game_pk", how="left")

# Get closing lines + under prices
# 2024-2025: market_snapshots
ms = pd.read_parquet("/root/mlb-model/sim/data/market_snapshots.parquet")
ms = ms.rename(columns={"game_id": "game_pk"})
ms_prices = ms[["game_pk", "close_total", "under_price"]].copy()

# 2022-2023: closing_lines (no prices, assume -110)
cl = pd.read_parquet("/root/mlb-model/sim/data/mlb_historical_closing_lines.parquet")
cl_prices = cl[["game_pk", "close_total"]].copy()
cl_prices["under_price"] = -110.0

# Combine (prefer market_snapshots for overlap)
odds = pd.concat([cl_prices, ms_prices], ignore_index=True)
odds = odds.drop_duplicates(subset=["game_pk"], keep="last")

games = games.merge(odds, on="game_pk", how="left")

# Drop games missing essential data
games_full = games.dropna(subset=["home_csw", "away_csw", "home_xfip", "away_xfip", "actual_total"]).copy()
games_pit = games_full[games_full["xfip_pit_safe"]].copy()

print(f"  Games with all inputs: {len(games_full)}")
print(f"  Games with PIT-safe xFIP: {len(games_pit)}")
print(f"  Games with closing lines: {games_full[close_total].notna().sum()}")

# Compute S12
games_full["s12"] = (games_full["home_csw"] + games_full["away_csw"]) / 2 - \
                     5 * (games_full["home_xfip"] + games_full["away_xfip"]) / 2
games_pit["s12"] = (games_pit["home_csw"] + games_pit["away_csw"]) / 2 - \
                    5 * (games_pit["home_xfip"] + games_pit["away_xfip"]) / 2

print(f"\n  S12 distribution (all):")
print(f"    mean={games_full[s12].mean():.3f}  std={games_full[s12].std():.3f}")
print(f"    25%={games_full[s12].quantile(0.25):.3f}  50%={games_full[s12].quantile(0.5):.3f}  75%={games_full[s12].quantile(0.75):.3f}")
print(f"    Top 20% cutoff: {games_full[s12].quantile(0.80):.4f}")
print(f"    Old cutoff: 8.4468")

print(f"\n  S12 distribution (PIT-safe only):")
print(f"    mean={games_pit[s12].mean():.3f}  std={games_pit[s12].std():.3f}")
print(f"    25%={games_pit[s12].quantile(0.25):.3f}  50%={games_pit[s12].quantile(0.5):.3f}  75%={games_pit[s12].quantile(0.75):.3f}")
print(f"    Top 20% cutoff: {games_pit[s12].quantile(0.80):.4f}")

# ─── Helper: ROI calculation ────────────────────────────────────────────────

def american_to_decimal(price):
    if price is None or np.isnan(price):
        return None
    if price > 0:
        return 1 + price / 100
    else:
        return 1 + 100 / abs(price)

def calc_roi(wins, losses, prices):
    """Calculate ROI from wins/losses with actual prices."""
    profit = 0
    total_wagered = 0
    for w, p in zip(wins, prices):
        dec = american_to_decimal(p) if p == p else american_to_decimal(-110)
        if dec is None:
            dec = american_to_decimal(-110)
        total_wagered += 1
        if w:
            profit += (dec - 1)
        else:
            profit -= 1
    return (profit / total_wagered * 100) if total_wagered > 0 else 0

def grade_unders(df, label=""):
    """Grade under bets. Under wins when actual < close_total."""
    has_lines = df["close_total"].notna()
    graded = df[has_lines].copy()
    graded["under_win"] = graded["actual_total"] < graded["close_total"]
    graded["push"] = graded["actual_total"] == graded["close_total"]
    # Exclude pushes
    graded = graded[~graded["push"]].copy()
    
    n = len(graded)
    wins = graded["under_win"].sum()
    wr = wins / n * 100 if n > 0 else 0
    
    # ROI at actual prices
    prices = graded["under_price"].fillna(-110).values
    profit = 0
    for i in range(n):
        dec = american_to_decimal(prices[i])
        if graded.iloc[i]["under_win"]:
            profit += (dec - 1)
        else:
            profit -= 1
    roi = profit / n * 100 if n > 0 else 0
    
    return {"label": label, "n": n, "wins": wins, "wr": wr, "roi": roi,
            "profit_units": round(profit, 2)}


# Use PIT-safe data as primary; report both
# For the main analysis, use PIT-safe only
df = games_pit.copy()
print(f"\n={chr(39)*0}"="*70")
print(f"Using PIT-safe dataset: {len(df)} games")
print(f"={chr(39)*0}"="*70")

# ─── Phase 3: Old rule test ─────────────────────────────────────────────────

print(f"\n={chr(39)*0}"="*70")
print("PHASE 3: Old Rule Test (cutoff = 8.4468, blind UNDER)")
print(f"={chr(39)*0}"="*70")

OLD_CUTOFF = 8.4468
df["s12_fire"] = df["s12"] >= OLD_CUTOFF

phase3_results = []
for season in sorted(df["season"].unique()):
    ssn = df[df["season"] == season]
    fired = ssn[ssn["s12_fire"]]
    result = grade_unders(fired, f"S12>={OLD_CUTOFF} {season}")
    phase3_results.append(result)
    print(f"  {season}: N={result[n]:>4}  WR={result[wr]:.1f}%  ROI={result[roi]:+.1f}%  units={result[profit_units]:+.1f}")

# All seasons
fired_all = df[df["s12_fire"]]
result_all = grade_unders(fired_all, f"S12>={OLD_CUTOFF} ALL")
phase3_results.append(result_all)
print(f"  ALL:  N={result_all[n]:>4}  WR={result_all[wr]:.1f}%  ROI={result_all[roi]:+.1f}%  units={result_all[profit_units]:+.1f}")

# Also show how many games fire
for season in sorted(df["season"].unique()):
    ssn = df[df["season"] == season]
    n_fire = ssn["s12_fire"].sum()
    print(f"  {season} fire rate: {n_fire}/{len(ssn)} = {n_fire/len(ssn)*100:.1f}%")

# ─── Phase 4: Rederive cutoff ───────────────────────────────────────────────

print(f"\n={chr(39)*0}"="*70")
print("PHASE 4: Threshold Ladder (train 2022-2024, OOS 2025)")
print(f"={chr(39)*0}"="*70")

train = df[df["season"].isin([2022, 2023, 2024])].copy()
oos = df[df["season"] == 2025].copy()

print(f"  Train: {len(train)} games")
print(f"  OOS:   {len(oos)} games")

thresholds = np.arange(4.0, 14.0, 0.5)
phase4_results = []

print(f"\n  {Threshold:>10} | {N_train:>8} | {WR_train:>8} | {ROI_train:>10} | {N_oos:>6} | {WR_oos:>7} | {ROI_oos:>9}")
print(f"  {-*10} | {-*8} | {-*8} | {-*10} | {-*6} | {-*7} | {-*9}")

for t in thresholds:
    train_fire = train[train["s12"] >= t]
    oos_fire = oos[oos["s12"] >= t]
    
    r_train = grade_unders(train_fire, f"train_{t}")
    r_oos = grade_unders(oos_fire, f"oos_{t}")
    
    phase4_results.append({
        "threshold": t,
        "n_train": r_train["n"], "wr_train": r_train["wr"], "roi_train": r_train["roi"],
        "n_oos": r_oos["n"], "wr_oos": r_oos["wr"], "roi_oos": r_oos["roi"],
    })
    
    print(f"  {t:>10.1f} | {r_train[n]:>8} | {r_train[wr]:>7.1f}% | {r_train[roi]:>+9.1f}% | {r_oos[n]:>6} | {r_oos[wr]:>6.1f}% | {r_oos[roi]:>+8.1f}%")

# ─── Phase 5: Stability ─────────────────────────────────────────────────────

print(f"\n={chr(39)*0}"="*70")
print("PHASE 5: Stability Analysis")
print(f"={chr(39)*0}"="*70")

# 5a: Season stability at old cutoff
print("\n  5a: Season-by-season at old cutoff (8.4468)")
for season in sorted(df["season"].unique()):
    ssn = df[df["season"] == season]
    fired = ssn[ssn["s12_fire"]]
    r = grade_unders(fired, f"{season}")
    print(f"    {season}: N={r[n]:>4}  WR={r[wr]:.1f}%  ROI={r[roi]:+.1f}%")

# 5b: Total-band dependence
print("\n  5b: Performance by closing total band (S12 >= 8.4468)")
fired_with_lines = df[df["s12_fire"] & df["close_total"].notna()].copy()
if len(fired_with_lines) > 0:
    bands = [(0, 7.5), (7.5, 8.5), (8.5, 9.5), (9.5, 15)]
    for lo, hi in bands:
        band = fired_with_lines[(fired_with_lines["close_total"] >= lo) & (fired_with_lines["close_total"] < hi)]
        r = grade_unders(band, f"[{lo},{hi})")
        print(f"    Total [{lo:.1f}, {hi:.1f}): N={r[n]:>4}  WR={r[wr]:.1f}%  ROI={r[roi]:+.1f}%")

# 5c: Price dependence
print("\n  5c: Performance by under price bucket (S12 >= 8.4468)")
fired_prices = df[df["s12_fire"] & df["under_price"].notna()].copy()
if len(fired_prices) > 0:
    price_bands = [(-200, -115), (-115, -105), (-105, -95), (-95, 200)]
    for lo, hi in price_bands:
        band = fired_prices[(fired_prices["under_price"] >= lo) & (fired_prices["under_price"] < hi)]
        r = grade_unders(band, f"price [{lo},{hi})")
        print(f"    Price [{lo}, {hi}): N={r[n]:>4}  WR={r[wr]:.1f}%  ROI={r[roi]:+.1f}%")

# ─── Phase 6: Baseline comparison ───────────────────────────────────────────

print(f"\n={chr(39)*0}"="*70")
print("PHASE 6: Baseline Comparison")
print(f"={chr(39)*0}"="*70")

# Baseline 1: Blind under all games
r_blind = grade_unders(df, "Blind UNDER all")
print(f"  Blind UNDER all:            N={r_blind[n]:>5}  WR={r_blind[wr]:.1f}%  ROI={r_blind[roi]:+.1f}%")

# Baseline 2: Blind under low totals (close_total <= 8.0)
low_total = df[df["close_total"].notna() & (df["close_total"] <= 8.0)]
r_low = grade_unders(low_total, "Blind UNDER low total (<=8.0)")
print(f"  Blind UNDER low total <=8:  N={r_low[n]:>5}  WR={r_low[wr]:.1f}%  ROI={r_low[roi]:+.1f}%")

# Baseline 3: Blind under where market leans under (under_price < -115)
mkt_under = df[df["under_price"].notna() & (df["under_price"] < -115)]
r_mkt = grade_unders(mkt_under, "Blind UNDER strong market under (<-115)")
print(f"  Blind UNDER mkt fav (<-115):N={r_mkt[n]:>5}  WR={r_mkt[wr]:.1f}%  ROI={r_mkt[roi]:+.1f}%")

# S12 signal
r_s12 = grade_unders(fired_all, f"S12>={OLD_CUTOFF}")
print(f"  S12 >= 8.4468:              N={r_s12[n]:>5}  WR={r_s12[wr]:.1f}%  ROI={r_s12[roi]:+.1f}%")

# S12 + low total intersection
s12_low = df[df["s12_fire"] & df["close_total"].notna() & (df["close_total"] <= 8.5)]
r_s12_low = grade_unders(s12_low, "S12 + low total")
print(f"  S12 + close_total<=8.5:     N={r_s12_low[n]:>5}  WR={r_s12_low[wr]:.1f}%  ROI={r_s12_low[roi]:+.1f}%")

# S12 uniqueness: games where S12 fires but close_total > 8.5
s12_high_total = df[df["s12_fire"] & df["close_total"].notna() & (df["close_total"] > 8.5)]
r_s12_high = grade_unders(s12_high_total, "S12 + high total")
print(f"  S12 + close_total>8.5:      N={r_s12_high[n]:>5}  WR={r_s12_high[wr]:.1f}%  ROI={r_s12_high[roi]:+.1f}%")

# ─── Phase 7: Verdict ───────────────────────────────────────────────────────

print(f"\n={chr(39)*0}"="*70")
print("PHASE 7: VERDICT")
print(f"={chr(39)*0}"="*70")

# Determine verdict
# Key questions:
# 1. Does S12 beat blind-under baseline?
# 2. Is it OOS profitable?
# 3. Is it stable across seasons?
# 4. Is it additive beyond obvious filters?

blind_roi = r_blind["roi"]
s12_roi = r_s12["roi"]
s12_wr = r_s12["wr"]

# OOS (2025) at best threshold from phase 4
best_oos = max(phase4_results, key=lambda x: x["roi_oos"] if x["n_oos"] >= 20 else -999)

print(f"\n  Key metrics:")
print(f"    S12 all-sample WR: {s12_wr:.1f}%  ROI: {s12_roi:+.1f}%")
print(f"    Blind UNDER ROI:   {blind_roi:+.1f}%")
print(f"    S12 edge vs blind: {s12_roi - blind_roi:+.1f}pp")
print(f"    Best OOS threshold: {best_oos[threshold]:.1f} → ROI={best_oos[roi_oos]:+.1f}% (N={best_oos[n_oos]})")

# Season stability check
season_rois = []
for season in sorted(df["season"].unique()):
    ssn = df[df["season"] == season]
    fired = ssn[ssn["s12_fire"]]
    r = grade_unders(fired, f"{season}")
    season_rois.append(r["roi"])
    
n_positive = sum(1 for r in season_rois if r > 0)
n_seasons = len(season_rois)

if s12_roi > 3.0 and best_oos["roi_oos"] > 0 and n_positive >= 3:
    verdict = "SURVIVES"
    reason = "Positive ROI in-sample and OOS, stable across most seasons"
elif s12_roi > 0 and best_oos["roi_oos"] > -3.0:
    verdict = "DIMINISHED"
    reason = "Marginal edge, not robust OOS"
elif s12_roi < -3.0 or best_oos["roi_oos"] < -5.0:
    verdict = "COLLAPSES"
    reason = "Negative ROI on clean data"
else:
    verdict = "DIMINISHED"
    reason = "Weak edge, questionable stability"

# Check if additive
if s12_roi <= blind_roi + 1.0:
    verdict = "COLLAPSES" if verdict != "DIMINISHED" else "DIMINISHED"
    reason += "; NOT additive beyond blind under"

print(f"\n  VERDICT: {verdict}")
print(f"  Reason: {reason}")
print(f"  Positive seasons: {n_positive}/{n_seasons}")
print(f"  Season ROIs: {[f{r:+.1f}% for r in season_rois]}")

# ─── Also run on FULL dataset (including non-PIT-safe xFIP) for comparison ──

print(f"\n={chr(39)*0}"="*70")
print("APPENDIX: Full dataset (includes contaminated xFIP games)")
print(f"={chr(39)*0}"="*70")

df_full = games_full.copy()
df_full["s12_fire"] = df_full["s12"] >= OLD_CUTOFF

for season in sorted(df_full["season"].unique()):
    ssn = df_full[df_full["season"] == season]
    fired = ssn[ssn["s12_fire"]]
    r = grade_unders(fired, f"{season}")
    print(f"  {season}: N={r[n]:>4}  WR={r[wr]:.1f}%  ROI={r[roi]:+.1f}%")

r_full_all = grade_unders(df_full[df_full["s12_fire"]], "ALL (full)")
print(f"  ALL:  N={r_full_all[n]:>4}  WR={r_full_all[wr]:.1f}%  ROI={r_full_all[roi]:+.1f}%")

# Contamination delta
print(f"\n  Contamination impact: PIT-safe ROI={s12_roi:+.1f}% vs Full ROI={r_full_all[roi]:+.1f}%  delta={s12_roi - r_full_all[roi]:+.1f}pp")

# ─── Write outputs ──────────────────────────────────────────────────────────

# Save phase 4 table
pd.DataFrame(phase4_results).to_csv(OUT / "phase4_threshold_ladder.csv", index=False)

# Save master summary
summary = {
    "verdict": verdict,
    "reason": reason,
    "s12_formula": "avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)",
    "old_cutoff": OLD_CUTOFF,
    "n_games_pit_safe": len(df),
    "n_games_full": len(games_full),
    "s12_all_sample_wr": round(s12_wr, 1),
    "s12_all_sample_roi": round(s12_roi, 1),
    "blind_under_roi": round(blind_roi, 1),
    "s12_edge_vs_blind": round(s12_roi - blind_roi, 1),
    "best_oos_threshold": best_oos["threshold"],
    "best_oos_roi": round(best_oos["roi_oos"], 1),
    "best_oos_n": best_oos["n_oos"],
    "season_rois": {str(s): round(r, 1) for s, r in zip(sorted(df["season"].unique()), season_rois)},
    "positive_seasons": f"{n_positive}/{n_seasons}",
    "contamination_delta_pp": round(s12_roi - r_full_all["roi"], 1),
    "pit_safety_note": "CSW is PIT-safe (shift(1) rolling). xFIP uses PIT v1_clean_features where available.",
}

with open(OUT / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n  Outputs written to {OUT}")
print(f"  FINAL VERDICT: {verdict}")
