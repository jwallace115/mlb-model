"""
Phase 2.5 Robustness Audit - 5 tests
RESEARCH ONLY - no live files modified.
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss
from scipy.stats import norm
import warnings
warnings.filterwarnings("ignore")

# -- Reconstruct Phase 2 dataset (same logic as build_baseline.py) --
ft = pd.read_parquet("sim/data/feature_table.parquet")
odds_raw = pd.read_parquet("mlb_sim/data/mlb_odds_closing_canonical.parquet")

ft = ft[ft["season"].isin([2022, 2023, 2024, 2025])].copy()

# De-vig DK ML
odds_dk = odds_raw[odds_raw["book_key"] == "draftkings"].copy()
total = odds_dk["ml_home_implied"] + odds_dk["ml_away_implied"]
odds_dk["p_home_ml"] = odds_dk["ml_home_implied"] / total
odds_dk["p_away_ml"] = odds_dk["ml_away_implied"] / total

odds_game = odds_dk[["game_pk", "p_home_ml", "p_away_ml", "total_line",
                      "ml_home_price", "ml_away_price"]].copy()
odds_game = odds_game.drop_duplicates(subset="game_pk", keep="first")

df = ft[["game_pk", "date", "season", "home_team", "away_team",
         "home_score", "away_score", "actual_total",
         "home_sp_xfip", "away_sp_xfip",
         "home_wrc_plus", "away_wrc_plus",
         "home_bp_xfip", "away_bp_xfip",
         "park_factor_runs", "temperature", "wind_factor_effective",
         "umpire_over_rate", "home_rest_days", "away_rest_days"]].copy()

df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
df["actual_margin"] = df["home_score"] - df["away_score"]
df = df[df["home_score"] != df["away_score"]].copy()

df["game_pk"] = df["game_pk"].astype(str)
odds_game["game_pk"] = odds_game["game_pk"].astype(str)
df = df.merge(odds_game, on="game_pk", how="left")

df["sp_xfip_diff"] = df["home_sp_xfip"] - df["away_sp_xfip"]
df["wrc_diff"] = df["home_wrc_plus"] - df["away_wrc_plus"]
df["bp_xfip_diff"] = df["home_bp_xfip"] - df["away_bp_xfip"]
df["rest_diff"] = df["home_rest_days"] - df["away_rest_days"]

ALL_FEATURES = [
    "sp_xfip_diff", "wrc_diff", "bp_xfip_diff", "park_factor_runs",
    "temperature", "wind_factor_effective", "umpire_over_rate",
    "rest_diff", "total_line",
]

df_model = df.dropna(subset=ALL_FEATURES + ["p_home_ml", "home_win"]).copy()

train = df_model[df_model["season"].isin([2022, 2023])].copy()
val   = df_model[df_model["season"] == 2024].copy()
oos   = df_model[df_model["season"] == 2025].copy()

print(f"Dataset: train={len(train)}, val={len(val)}, oos={len(oos)}")

# -- Helper: train logistic and return predictions --
def train_logistic(train_df, val_df, oos_df, features):
    sc = StandardScaler()
    X_tr = sc.fit_transform(train_df[features])
    X_va = sc.transform(val_df[features])
    X_oo = sc.transform(oos_df[features])
    m = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
    m.fit(X_tr, train_df["home_win"].values)
    return (m.predict_proba(X_tr)[:,1],
            m.predict_proba(X_va)[:,1],
            m.predict_proba(X_oo)[:,1],
            dict(zip(features, m.coef_[0])))

# -- Baseline Model A (reproduce) --
p_tr, p_va, p_oo, coefs = train_logistic(train, val, oos, ALL_FEATURES)
train["prob_a"] = p_tr
val["prob_a"] = p_va
oos["prob_a"] = p_oo

baseline_brier_oos = brier_score_loss(oos["home_win"], oos["prob_a"])
market_brier_oos   = brier_score_loss(oos["home_win"], oos["p_home_ml"])
baseline_delta     = baseline_brier_oos - market_brier_oos
print(f"\nBaseline Model A OOS Brier: {baseline_brier_oos:.6f}")
print(f"Market ML OOS Brier:        {market_brier_oos:.6f}")
print(f"Baseline delta:             {baseline_delta:+.6f}")

report = []
def R(s=""):
    print(s)
    report.append(str(s))

R("=" * 70)
R("ROBUSTNESS AUDIT -- PHASE 2.5")
R("=" * 70)

# ===================================================================
# TEST 1: Market Feature Leakage
# ===================================================================
R("\n## TEST 1: Market Feature Leakage\n")

market_features = ["total_line"]  # closing total is market-derived
nonmarket_features = [f for f in ALL_FEATURES if f not in market_features]
R(f"Market-derived features removed: {market_features}")
R(f"Remaining features ({len(nonmarket_features)}): {nonmarket_features}")

p_tr1, p_va1, p_oo1, coefs1 = train_logistic(train, val, oos, nonmarket_features)

brier_nomarket_val = brier_score_loss(val["home_win"], p_va1)
brier_nomarket_oos = brier_score_loss(oos["home_win"], p_oo1)
market_brier_val   = brier_score_loss(val["home_win"], val["p_home_ml"])
delta_nomarket_val = brier_nomarket_val - market_brier_val
delta_nomarket_oos = brier_nomarket_oos - market_brier_oos

R(f"\nWith total_line removed:")
R(f"  Val Brier:  {brier_nomarket_val:.6f} (market: {market_brier_val:.6f}, delta: {delta_nomarket_val:+.6f})")
R(f"  OOS Brier:  {brier_nomarket_oos:.6f} (market: {market_brier_oos:.6f}, delta: {delta_nomarket_oos:+.6f})")
R(f"\nBaseline delta (with total_line):   {baseline_delta:+.6f}")
R(f"No-market delta (without total_line): {delta_nomarket_oos:+.6f}")
survives = delta_nomarket_oos < 0
R(f"Does -0.0020 survive? {'YES' if survives else 'NO'} (delta={delta_nomarket_oos:+.6f})")

R(f"\nCoefficients (no-market model):")
for feat, c in sorted(coefs1.items(), key=lambda x: abs(x[1]), reverse=True):
    R(f"  {feat:30s}: {c:+.4f}")

# ===================================================================
# TEST 2: Total Band Concentration
# ===================================================================
R("\n## TEST 2: Total Band Concentration\n")

bands = [
    ("7.0-8.5", (oos["total_line"] >= 7.0) & (oos["total_line"] < 8.5)),
    ("8.5-9.0", (oos["total_line"] >= 8.5) & (oos["total_line"] < 9.0)),
    ("9.0-9.5", (oos["total_line"] >= 9.0) & (oos["total_line"] < 9.5)),
    ("9.5-10.0", (oos["total_line"] >= 9.5) & (oos["total_line"] < 10.0)),
    ("10.0-10.5", (oos["total_line"] >= 10.0) & (oos["total_line"] < 10.5)),
    ("10.5+", oos["total_line"] >= 10.5),
]

R(f"{'Band':>12} {'N':>5} {'Model Brier':>12} {'Market Brier':>13} {'Delta':>10}")
R("-" * 55)
for name, mask in bands:
    sub = oos[mask]
    if len(sub) < 10:
        R(f"{name:>12} {len(sub):>5}   (too few)")
        continue
    mb = brier_score_loss(sub["home_win"], sub["prob_a"])
    mkb = brier_score_loss(sub["home_win"], sub["p_home_ml"])
    d = mb - mkb
    R(f"{name:>12} {len(sub):>5} {mb:>12.6f} {mkb:>13.6f} {d:>+10.6f}")

# ===================================================================
# TEST 3: Season-by-Season Stability
# ===================================================================
R("\n## TEST 3: Season-by-Season Stability\n")

R("--- Train 2022-2023, test each season ---")

for yr, split_df in [(2022, train[train["season"]==2022]),
                      (2023, train[train["season"]==2023]),
                      (2024, val), (2025, oos)]:
    if len(split_df) < 50:
        continue
    mb = brier_score_loss(split_df["home_win"], split_df["prob_a"])
    mkb = brier_score_loss(split_df["home_win"], split_df["p_home_ml"])
    d = mb - mkb
    label = "train" if yr in [2022,2023] else ("val" if yr==2024 else "OOS")
    R(f"  {yr} ({label:5s}): N={len(split_df):>5}  Model={mb:.6f}  Market={mkb:.6f}  Delta={d:+.6f}")

# Retrain on 2023-2024, test on 2025
R("\n--- Retrain on 2023-2024, test on 2025 ---")
train_alt = df_model[df_model["season"].isin([2023, 2024])].copy()
oos_alt   = df_model[df_model["season"] == 2025].copy()

_, _, p_oo_alt, coefs_alt = train_logistic(train_alt, oos_alt, oos_alt, ALL_FEATURES)
brier_alt = brier_score_loss(oos_alt["home_win"], p_oo_alt)
delta_alt = brier_alt - market_brier_oos
R(f"  Train 2023-2024 -> OOS 2025: Model={brier_alt:.6f}  Market={market_brier_oos:.6f}  Delta={delta_alt:+.6f}")

# High-total subset
R("\n--- High-total subset (total > 9.0) ---")
oo_hi = oos[oos["total_line"] > 9.0]
if len(oo_hi) > 20:
    mb = brier_score_loss(oo_hi["home_win"], oo_hi["prob_a"])
    mkb = brier_score_loss(oo_hi["home_win"], oo_hi["p_home_ml"])
    R(f"  Train 22-23 -> OOS 25 (total>9.0): N={len(oo_hi)}  Model={mb:.6f}  Market={mkb:.6f}  Delta={mb-mkb:+.6f}")

# Alt train high-total
oo_alt_hi = oos_alt[oos_alt["total_line"] > 9.0]
if len(oo_alt_hi) > 20:
    mb2 = brier_score_loss(oo_alt_hi["home_win"], p_oo_alt[oos_alt["total_line"].values > 9.0])
    mkb2 = brier_score_loss(oo_alt_hi["home_win"], oo_alt_hi["p_home_ml"])
    R(f"  Train 23-24 -> OOS 25 (total>9.0): N={len(oo_alt_hi)}  Model={mb2:.6f}  Market={mkb2:.6f}  Delta={mb2-mkb2:+.6f}")

# ===================================================================
# TEST 4: Home-Undervaluation Directional Robustness
# ===================================================================
R("\n## TEST 4: Home-Undervaluation Directional Robustness\n")

oos["disagreement"] = oos["prob_a"] - oos["p_home_ml"]

# For per-season analysis, predict all years using train-fitted model
sc_fixed = StandardScaler()
sc_fixed.fit(train[ALL_FEATURES])
m_fixed = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")
m_fixed.fit(sc_fixed.transform(train[ALL_FEATURES]), train["home_win"].values)

all_data = df_model.copy()
X_all = sc_fixed.transform(all_data[ALL_FEATURES])
all_data["prob_a"] = m_fixed.predict_proba(X_all)[:,1]
all_data["disagreement"] = all_data["prob_a"] - all_data["p_home_ml"]

R("--- Per-season home win rate in top quartile (model says home undervalued) ---")

R(f"\n{'Year':>6} {'N_top25':>8} {'HW_rate':>8} {'Model_p':>8} {'Market_p':>8}")
for yr in [2022, 2023, 2024, 2025]:
    sub = all_data[all_data["season"] == yr]
    q75_yr = sub["disagreement"].quantile(0.75)
    top = sub[sub["disagreement"] > q75_yr]
    R(f"{yr:>6} {len(top):>8} {top['home_win'].mean():>8.3f} {top['prob_a'].mean():>8.3f} {top['p_home_ml'].mean():>8.3f}")

# Threshold sensitivity (OOS only)
R("\n--- Threshold sensitivity (OOS 2025) ---")
R(f"{'Threshold':>12} {'N':>5} {'HW_rate':>8} {'Model_p':>8} {'Market_p':>8} {'Mkt_err':>8}")
for pct_label, pct in [("Top 30%", 0.70), ("Top 25%", 0.75), ("Top 20%", 0.80), ("Top 10%", 0.90)]:
    q = oos["disagreement"].quantile(pct)
    top = oos[oos["disagreement"] > q]
    hw = top["home_win"].mean()
    mp = top["prob_a"].mean()
    mkp = top["p_home_ml"].mean()
    mkt_err = abs(hw - mkp)
    R(f"{pct_label:>12} {len(top):>5} {hw:>8.3f} {mp:>8.3f} {mkp:>8.3f} {mkt_err:>8.3f}")

# Synthetic flat-price ROI at -110
R("\n--- Synthetic flat-price ROI at -110 (PROXY ONLY) ---")
R("Assumes all bets placed at -110 (implied 52.38%)")
for pct_label, pct in [("Top 30%", 0.70), ("Top 25%", 0.75), ("Top 20%", 0.80), ("Top 10%", 0.90)]:
    q = oos["disagreement"].quantile(pct)
    top = oos[oos["disagreement"] > q]
    wins = top["home_win"].sum()
    losses = len(top) - wins
    profit = wins * (100.0/110.0) - losses * 1.0
    roi = profit / len(top) * 100
    R(f"  {pct_label}: {len(top)} bets, {int(wins)}W-{int(losses)}L, ROI={roi:+.1f}%")

# ===================================================================
# TEST 5: Price Band Stability
# ===================================================================
R("\n## TEST 5: Price Band Stability\n")

R(f"{'Band':>35} {'N':>5} {'Model Brier':>12} {'Market Brier':>13} {'Delta':>10}")
R("-" * 78)

price_bands = [
    ("Heavy fav (>0.60 or <0.40)", (oos["p_home_ml"] > 0.60) | (oos["p_home_ml"] < 0.40)),
    ("Moderate (0.52-0.60 / 0.40-0.48)",
     ((oos["p_home_ml"] >= 0.52) & (oos["p_home_ml"] <= 0.60)) |
     ((oos["p_home_ml"] >= 0.40) & (oos["p_home_ml"] <= 0.48))),
    ("Pick'em (0.48-0.52)",
     (oos["p_home_ml"] >= 0.48) & (oos["p_home_ml"] <= 0.52)),
]

for name, mask in price_bands:
    sub = oos[mask]
    if len(sub) < 10:
        R(f"{name:>35} {len(sub):>5}   (too few)")
        continue
    mb = brier_score_loss(sub["home_win"], sub["prob_a"])
    mkb = brier_score_loss(sub["home_win"], sub["p_home_ml"])
    d = mb - mkb
    R(f"{name:>35} {len(sub):>5} {mb:>12.6f} {mkb:>13.6f} {d:>+10.6f}")

# ===================================================================
# SUMMARY VERDICT
# ===================================================================
R("\n" + "=" * 70)
R("SUMMARY VERDICT")
R("=" * 70)

R(f"\n{'Test':>40} {'Result':>15} {'Status':>10}")
R("-" * 68)

# Test 1 verdict
t1_status = "ROBUST" if delta_nomarket_oos < 0 else "ARTIFACT"
R(f"{'T1: Market Leakage':>40} {'survives' if survives else 'fails':>15} {t1_status:>10}")

# Test 2 verdict
band_results = []
for name, mask in bands:
    sub = oos[mask]
    if len(sub) >= 10:
        mb = brier_score_loss(sub["home_win"], sub["prob_a"])
        mkb = brier_score_loss(sub["home_win"], sub["p_home_ml"])
        band_results.append((name, len(sub), mb - mkb))

neg_bands = sum(1 for _, _, d in band_results if d < 0)
t2_status = "ROBUST" if neg_bands >= len(band_results)//2 + 1 else ("PARTIAL" if neg_bands >= 2 else "ARTIFACT")
R(f"{'T2: Total Band Concentration':>40} {str(neg_bands)+'/'+str(len(band_results))+' bands neg':>15} {t2_status:>10}")

# Test 3 verdict
t3_status = "ROBUST" if delta_alt < 0 else "PARTIAL"
R(f"{'T3: Season Stability':>40} {'alt delta='+str(round(delta_alt,4)):>15} {t3_status:>10}")

# Test 4 verdict
yr_results = []
for yr in [2022, 2023, 2024, 2025]:
    sub = all_data[all_data["season"] == yr]
    q75_yr = sub["disagreement"].quantile(0.75)
    top = sub[sub["disagreement"] > q75_yr]
    yr_results.append(top["home_win"].mean())
consistent = all(r > 0.55 for r in yr_results)
t4_status = "ROBUST" if consistent else "PARTIAL"
R(f"{'T4: Home Underval Direction':>40} {'all>55%' if consistent else 'mixed':>15} {t4_status:>10}")

# Test 5 verdict
pb_results = []
for name, mask in price_bands:
    sub = oos[mask]
    if len(sub) >= 10:
        mb = brier_score_loss(sub["home_win"], sub["prob_a"])
        mkb = brier_score_loss(sub["home_win"], sub["p_home_ml"])
        pb_results.append((name, mb - mkb))
neg_pb = sum(1 for _, d in pb_results if d < 0)
t5_status = "ROBUST" if neg_pb == len(pb_results) else ("PARTIAL" if neg_pb >= 1 else "ARTIFACT")
R(f"{'T5: Price Band Stability':>40} {str(neg_pb)+'/'+str(len(pb_results))+' bands neg':>15} {t5_status:>10}")

# Overall
statuses = [t1_status, t2_status, t3_status, t4_status, t5_status]
robust_count = statuses.count("ROBUST")
artifact_count = statuses.count("ARTIFACT")
if robust_count >= 4:
    overall = "ROBUST"
elif artifact_count >= 3:
    overall = "ARTIFACT"
else:
    overall = "PARTIAL"

R(f"\n{'OVERALL VERDICT':>40} {'':>15} {overall:>10}")
R(f"\nRobust: {robust_count}/5, Partial: {statuses.count('PARTIAL')}/5, Artifact: {artifact_count}/5")

# Save report lines for appending
with open("research/mlb_side_engine/_audit_output.txt", "w") as f:
    f.write("\n".join(report))

print("\n\nDone. Output saved to _audit_output.txt")
