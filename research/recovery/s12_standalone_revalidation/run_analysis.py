#!/usr/bin/env python3
"""S12 Standalone Revalidation on PIT-safe data."""
import pandas as pd
import numpy as np
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

OUT = Path("/root/mlb-model/research/recovery/s12_standalone_revalidation")
OUT.mkdir(parents=True, exist_ok=True)
SEP = "=" * 70
DASH = "-" * 6

def american_to_decimal(price):
    if price is None or np.isnan(price):
        return None
    if price > 0:
        return 1 + price / 100
    return 1 + 100 / abs(price)

def grade_unders(df, label=""):
    has_lines = df["close_total"].notna()
    graded = df[has_lines].copy()
    graded["under_win"] = graded["actual_total"] < graded["close_total"]
    graded["push"] = graded["actual_total"] == graded["close_total"]
    graded = graded[~graded["push"]].copy()
    n = len(graded)
    wins = int(graded["under_win"].sum())
    wr = wins / n * 100 if n > 0 else 0
    prices = graded["under_price"].fillna(-110).values
    profit = 0.0
    for i in range(n):
        dec = american_to_decimal(prices[i])
        if graded.iloc[i]["under_win"]:
            profit += (dec - 1)
        else:
            profit -= 1
    roi = profit / n * 100 if n > 0 else 0
    return {"label": label, "n": n, "wins": wins, "wr": wr, "roi": roi, "profit_units": round(profit, 2)}

########################################################################
print(SEP)
print("PHASE 1: Data Assembly & PIT Safety Verification")
print(SEP)

si_hist = pd.read_parquet("/root/mlb-model/mlb_sim/data/sim_inputs_historical_2022_2024.parquet")
si_2025 = pd.read_parquet("/root/mlb-model/mlb_sim/data/sim_inputs_2025.parquet")
si = pd.concat([si_hist, si_2025], ignore_index=True)

home = si[si["is_home"] == 1][["game_pk", "date", "season", "sp_csw_pct", "sp_xfip"]].rename(
    columns={"sp_csw_pct": "home_csw", "sp_xfip": "home_xfip_CONT"})
away = si[si["is_home"] == 0][["game_pk", "sp_csw_pct", "sp_xfip"]].rename(
    columns={"sp_csw_pct": "away_csw", "sp_xfip": "away_xfip_CONT"})
games = home.merge(away, on="game_pk", how="inner")
games["game_pk"] = games["game_pk"].astype(int)

pit = pd.read_parquet("/root/mlb-model/research/recovery/v1_clean_features/baseball_features_pit_v1.parquet")
pit_xfip = pit[["game_pk", "home_sp_xfip", "away_sp_xfip"]].rename(
    columns={"home_sp_xfip": "home_xfip_pit", "away_sp_xfip": "away_xfip_pit"})
games = games.merge(pit_xfip, on="game_pk", how="left")

n_pit = games["home_xfip_pit"].notna().sum()
print("  Games with PIT-safe xFIP: %d/%d" % (n_pit, len(games)))

games["home_xfip"] = games["home_xfip_pit"].fillna(games["home_xfip_CONT"])
games["away_xfip"] = games["away_xfip_pit"].fillna(games["away_xfip_CONT"])
games["xfip_pit_safe"] = games["home_xfip_pit"].notna() & games["away_xfip_pit"].notna()

ft = pd.read_parquet("/root/mlb-model/sim/data/feature_table.parquet")
games = games.merge(ft[["game_pk", "actual_total"]], on="game_pk", how="left")

ms = pd.read_parquet("/root/mlb-model/sim/data/market_snapshots.parquet")
ms = ms.rename(columns={"game_id": "game_pk"})
cl = pd.read_parquet("/root/mlb-model/sim/data/mlb_historical_closing_lines.parquet")
cl["under_price"] = -110.0

odds = pd.concat([cl[["game_pk", "close_total", "under_price"]],
                   ms[["game_pk", "close_total", "under_price"]]], ignore_index=True)
odds = odds.drop_duplicates(subset=["game_pk"], keep="last")
games = games.merge(odds, on="game_pk", how="left")

games_full = games.dropna(subset=["home_csw", "away_csw", "home_xfip", "away_xfip", "actual_total"]).copy()
games_pit = games_full[games_full["xfip_pit_safe"]].copy()

print("  Games with all inputs: %d" % len(games_full))
print("  Games with PIT-safe xFIP: %d" % len(games_pit))
print("  Games with closing lines: %d" % games_full["close_total"].notna().sum())

games_full["s12"] = (games_full["home_csw"] + games_full["away_csw"]) / 2 - \
                     5 * (games_full["home_xfip"] + games_full["away_xfip"]) / 2
games_pit["s12"] = (games_pit["home_csw"] + games_pit["away_csw"]) / 2 - \
                    5 * (games_pit["home_xfip"] + games_pit["away_xfip"]) / 2

print("\n  S12 distribution (PIT-safe):")
for q, lbl in [(0.25, "25%"), (0.50, "50%"), (0.75, "75%"), (0.80, "80%")]:
    print("    %s: %.4f" % (lbl, games_pit["s12"].quantile(q)))
print("    mean: %.4f  std: %.4f" % (games_pit["s12"].mean(), games_pit["s12"].std()))
print("    Old cutoff: 8.4468")

df = games_pit.copy()
OLD_CUTOFF = 8.4468
print("\nUsing PIT-safe dataset: %d games" % len(df))

########################################################################
print("\n" + SEP)
print("PHASE 3: Old Rule Test (cutoff = 8.4468, blind UNDER)")
print(SEP)

df["s12_fire"] = df["s12"] >= OLD_CUTOFF
phase3_results = []
for season in sorted(df["season"].unique()):
    ssn = df[df["season"] == season]
    fired = ssn[ssn["s12_fire"]]
    r = grade_unders(fired, "S12 %d" % season)
    phase3_results.append(r)
    n_fire = ssn["s12_fire"].sum()
    print("  %d: N=%4d  WR=%.1f%%  ROI=%+.1f%%  fired=%d/%d (%.1f%%)" %
          (season, r["n"], r["wr"], r["roi"], n_fire, len(ssn), n_fire/len(ssn)*100))

fired_all = df[df["s12_fire"]]
r_all = grade_unders(fired_all, "S12 ALL")
print("  ALL:  N=%4d  WR=%.1f%%  ROI=%+.1f%%  units=%+.1f" %
      (r_all["n"], r_all["wr"], r_all["roi"], r_all["profit_units"]))

########################################################################
print("\n" + SEP)
print("PHASE 4: Threshold Ladder (train 2022-2024, OOS 2025)")
print(SEP)

train = df[df["season"].isin([2022, 2023, 2024])].copy()
oos = df[df["season"] == 2025].copy()
print("  Train: %d games  OOS: %d games" % (len(train), len(oos)))

thresholds = np.arange(4.0, 14.0, 0.5)
phase4_results = []

print("\n  %6s | %5s | %6s | %7s | %5s | %6s | %7s" % 
      ("Thresh", "N_tr", "WR_tr", "ROI_tr", "N_os", "WR_os", "ROI_os"))
print("  " + " | ".join([DASH]*7))

for t in thresholds:
    r_tr = grade_unders(train[train["s12"] >= t], "tr_%.1f" % t)
    r_os = grade_unders(oos[oos["s12"] >= t], "os_%.1f" % t)
    phase4_results.append({
        "threshold": t, "n_train": r_tr["n"], "wr_train": r_tr["wr"], "roi_train": r_tr["roi"],
        "n_oos": r_os["n"], "wr_oos": r_os["wr"], "roi_oos": r_os["roi"],
    })
    print("  %6.1f | %5d | %5.1f%% | %+6.1f%% | %5d | %5.1f%% | %+6.1f%%" %
          (t, r_tr["n"], r_tr["wr"], r_tr["roi"], r_os["n"], r_os["wr"], r_os["roi"]))

########################################################################
print("\n" + SEP)
print("PHASE 5: Stability Analysis")
print(SEP)

print("\n  5a: Season stability at old cutoff")
season_rois = []
for season in sorted(df["season"].unique()):
    fired = df[(df["season"] == season) & df["s12_fire"]]
    r = grade_unders(fired, str(season))
    season_rois.append(r["roi"])
    print("    %d: N=%4d  WR=%.1f%%  ROI=%+.1f%%" % (season, r["n"], r["wr"], r["roi"]))

print("\n  5b: Performance by closing total band (S12 >= 8.4468)")
fired_wl = df[df["s12_fire"] & df["close_total"].notna()].copy()
if len(fired_wl) > 0:
    for lo, hi in [(0, 7.5), (7.5, 8.5), (8.5, 9.5), (9.5, 15)]:
        band = fired_wl[(fired_wl["close_total"] >= lo) & (fired_wl["close_total"] < hi)]
        r = grade_unders(band, "[%.1f,%.1f)" % (lo, hi))
        print("    Total [%.1f, %.1f): N=%4d  WR=%.1f%%  ROI=%+.1f%%" %
              (lo, hi, r["n"], r["wr"], r["roi"]))

print("\n  5c: Performance by under price bucket (2024-2025, actual prices)")
fired_pr = df[df["s12_fire"] & df["under_price"].notna() & (df["under_price"] != -110)].copy()
if len(fired_pr) > 0:
    for lo, hi in [(-200, -115), (-115, -105), (-105, -95), (-95, 200)]:
        band = fired_pr[(fired_pr["under_price"] >= lo) & (fired_pr["under_price"] < hi)]
        r = grade_unders(band, "price [%d,%d)" % (lo, hi))
        print("    Price [%d, %d): N=%4d  WR=%.1f%%  ROI=%+.1f%%" %
              (lo, hi, r["n"], r["wr"], r["roi"]))
else:
    print("    No actual price data for S12 fires")

########################################################################
print("\n" + SEP)
print("PHASE 6: Baseline Comparison")
print(SEP)

r_blind = grade_unders(df, "Blind UNDER all")
print("  Blind UNDER all:             N=%5d  WR=%.1f%%  ROI=%+.1f%%" %
      (r_blind["n"], r_blind["wr"], r_blind["roi"]))

low_t = df[df["close_total"].notna() & (df["close_total"] <= 8.0)]
r_low = grade_unders(low_t, "low total")
print("  Blind UNDER total<=8.0:      N=%5d  WR=%.1f%%  ROI=%+.1f%%" %
      (r_low["n"], r_low["wr"], r_low["roi"]))

mkt = df[df["under_price"].notna() & (df["under_price"] < -115)]
r_mkt = grade_unders(mkt, "mkt under")
print("  Blind UNDER mkt fav (<-115): N=%5d  WR=%.1f%%  ROI=%+.1f%%" %
      (r_mkt["n"], r_mkt["wr"], r_mkt["roi"]))

print("  S12 >= 8.4468:               N=%5d  WR=%.1f%%  ROI=%+.1f%%" %
      (r_all["n"], r_all["wr"], r_all["roi"]))

s12_low = df[df["s12_fire"] & df["close_total"].notna() & (df["close_total"] <= 8.5)]
r_s12l = grade_unders(s12_low, "S12+low")
print("  S12 + close<=8.5:            N=%5d  WR=%.1f%%  ROI=%+.1f%%" %
      (r_s12l["n"], r_s12l["wr"], r_s12l["roi"]))

s12_hi = df[df["s12_fire"] & df["close_total"].notna() & (df["close_total"] > 8.5)]
r_s12h = grade_unders(s12_hi, "S12+high")
print("  S12 + close>8.5:             N=%5d  WR=%.1f%%  ROI=%+.1f%%" %
      (r_s12h["n"], r_s12h["wr"], r_s12h["roi"]))

########################################################################
print("\n" + SEP)
print("PHASE 7: VERDICT")
print(SEP)

s12_roi = r_all["roi"]
s12_wr = r_all["wr"]
blind_roi = r_blind["roi"]

valid_oos = [r for r in phase4_results if r["n_oos"] >= 20]
if valid_oos:
    best_oos = max(valid_oos, key=lambda x: x["roi_oos"])
else:
    best_oos = max(phase4_results, key=lambda x: x["roi_oos"])

n_positive = sum(1 for r in season_rois if r > 0)
n_seasons = len(season_rois)

print("\n  Key metrics:")
print("    S12 all-sample WR:   %.1f%%  ROI: %+.1f%%" % (s12_wr, s12_roi))
print("    Blind UNDER ROI:     %+.1f%%" % blind_roi)
print("    S12 edge vs blind:   %+.1fpp" % (s12_roi - blind_roi))
print("    Best OOS threshold:  %.1f -> ROI=%+.1f%% (N=%d)" %
      (best_oos["threshold"], best_oos["roi_oos"], best_oos["n_oos"]))
print("    Positive seasons:    %d/%d" % (n_positive, n_seasons))
print("    Season ROIs:         %s" % str(["%+.1f%%" % r for r in season_rois]))

# Determine verdict
edge_vs_blind = s12_roi - blind_roi

if s12_roi > 3.0 and best_oos["roi_oos"] > 0 and n_positive >= 3:
    verdict = "SURVIVES"
    reason = "Positive ROI in-sample and OOS, stable across most seasons"
elif edge_vs_blind > 2.0 and best_oos["roi_oos"] > -3.0 and n_positive >= 2:
    verdict = "DIMINISHED"
    reason = "Some edge vs blind but not robust OOS"
elif edge_vs_blind < 1.0:
    verdict = "COLLAPSES"
    reason = "Not additive beyond blind under baseline (edge vs blind = %.1fpp)" % edge_vs_blind
elif best_oos["roi_oos"] < -5.0:
    verdict = "COLLAPSES"
    reason = "Negative OOS ROI (%.1f%%)" % best_oos["roi_oos"]
else:
    verdict = "DIMINISHED"
    reason = "Weak or unstable edge"

print("\n  VERDICT: %s" % verdict)
print("  Reason:  %s" % reason)

# Contamination check
games_full["s12_fire"] = games_full["s12"] >= OLD_CUTOFF
r_full = grade_unders(games_full[games_full["s12_fire"]], "full")
contam_delta = s12_roi - r_full["roi"]
print("\n  Contamination check:")
print("    PIT-safe ROI: %+.1f%%  Full ROI: %+.1f%%  delta: %+.1fpp" %
      (s12_roi, r_full["roi"], contam_delta))

# Save
pd.DataFrame(phase4_results).to_csv(OUT / "phase4_threshold_ladder.csv", index=False)
summary = {
    "verdict": verdict, "reason": reason,
    "s12_formula": "avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)",
    "old_cutoff": OLD_CUTOFF,
    "n_games_pit_safe": len(df), "n_games_full": len(games_full),
    "s12_all_wr": round(s12_wr, 1), "s12_all_roi": round(s12_roi, 1),
    "blind_under_roi": round(blind_roi, 1),
    "s12_edge_vs_blind_pp": round(edge_vs_blind, 1),
    "best_oos_threshold": best_oos["threshold"],
    "best_oos_roi": round(best_oos["roi_oos"], 1),
    "best_oos_n": best_oos["n_oos"],
    "season_rois": dict(zip([str(s) for s in sorted(df["season"].unique())],
                           [round(r,1) for r in season_rois])),
    "positive_seasons": "%d/%d" % (n_positive, n_seasons),
    "contamination_delta_pp": round(contam_delta, 1),
}
with open(OUT / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("\n  Outputs saved to %s" % OUT)
print("\n" + SEP)
print("FINAL VERDICT: %s" % verdict)
print(SEP)
