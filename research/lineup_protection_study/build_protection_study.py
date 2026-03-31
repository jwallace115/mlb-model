#!/usr/bin/env python3
"""
Lineup Protection Study — existence test, sensitivity, protector types.
Uses batter-game-level data (no PA-level or pitch-level data available locally).
"""

import json, os
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
V3 = BASE.parent / "mlb_v3_lineup_model"
np.random.seed(42)

# =====================================================================
# STEP 0 — SOURCE AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — AUDIT")
print("=" * 60)

lu = pd.read_parquet(V3 / "historical_lineups_long.parquet")
lu["game_date"] = pd.to_datetime(lu["game_date"])
gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])

audit = [
    "# Source Audit — Lineup Protection Study", "",
    "## Data Availability", "",
    f"| Source | Rows | Grain | Available |",
    f"|--------|------|-------|-----------|",
    f"| historical_lineups_long.parquet | {len(lu)} | batter × game | YES |",
    f"| game_table.parquet | {len(gt)} | game | YES |",
    f"| Statcast pitch-level | — | pitch | **NO** (only pitcher-aggregate per start) |",
    f"| PA-level logs | — | plate appearance | **NO** (only batter-game totals) |",
    "",
    "## Key Limitation",
    "No plate-appearance-level or pitch-level data exists locally.",
    "Study uses BATTER-GAME-LEVEL outcomes (K rate, BB rate, ISO per game).",
    "Cannot test: zone rate, first-pitch strike, fastball rate, per-PA sequencing.",
    "",
    "## Fields Available Per Batter-Game",
    "AB, H, 2B, 3B, HR, K, BB, HBP, PA, total_bases, batting_order_slot",
    "Player ID, team, opponent, home/away, position",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1 — BUILD PROTECTION STUDY DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — PROTECTION DATASET")
print("=" * 60)

# For each batter-game, identify the on-deck hitter (next batting order slot)
# Slot 9 wraps to slot 1
df = lu.copy()

# Build on-deck lookup: for each game+team, map slot -> player_id
ondeck_map = df.copy()
ondeck_map["ondeck_slot"] = ondeck_map["batting_order_slot"] % 9 + 1  # next slot (9->1)
ondeck_map = ondeck_map.rename(columns={"player_id": "batter_id_lookup",
                                         "batting_order_slot": "source_slot"})

# Join: for each batter, find who bats in the next slot
df = df.merge(
    ondeck_map[["game_pk", "team", "ondeck_slot", "batter_id_lookup"]].rename(
        columns={"ondeck_slot": "batting_order_slot",
                 "batter_id_lookup": "on_deck_batter_id"}),
    on=["game_pk", "team", "batting_order_slot"],
    how="left"
)

# Per-game rates
df["walk_rate"] = df["bb"] / df["pa"].clip(lower=1)
df["k_rate"] = df["k"] / df["pa"].clip(lower=1)
df["iso"] = (df["total_bases"] - df["h"]) / df["ab"].clip(lower=1)
df["contact_rate"] = df["h"] / df["ab"].clip(lower=1)
df["woba_proxy"] = (0.69*df["bb"] + 0.72*df["hbp"] + 0.89*df["h"] +
                    0.27*df["doubles"] + 0.58*df["triples"] + 1.24*df["hr"]) / df["pa"].clip(lower=1)

# Add game context from game_table
df = df.merge(gt[["game_pk", "home_team", "away_team", "home_score", "away_score",
                   "actual_total", "temperature", "park_factor_runs"]],
              on="game_pk", how="left")

on_deck_coverage = df["on_deck_batter_id"].notna().mean()
print(f"  Dataset: {len(df)} batter-games")
print(f"  On-deck hitter identified: {on_deck_coverage:.1%}")
print(f"  Seasons: {sorted(df.season.unique())}")

df.to_parquet(BASE / "protection_pa_dataset.parquet", index=False)

# =====================================================================
# STEP 2 — ON-DECK HITTER QUALITY FEATURES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — ON-DECK FEATURES")
print("=" * 60)

# Build rolling features for ALL players, then look up on-deck
hitters = df[["player_id", "game_pk", "game_date", "season", "team",
              "walk_rate", "k_rate", "iso", "contact_rate", "woba_proxy", "pa"]].copy()
hitters = hitters.sort_values(["player_id", "game_date"]).reset_index(drop=True)

print("  Computing rolling hitter features...")
for metric in ["walk_rate", "k_rate", "iso", "contact_rate", "woba_proxy"]:
    hitters[f"{metric}_last20"] = hitters.groupby("player_id")[metric].transform(
        lambda x: x.shift(1).rolling(20, min_periods=8).mean())

# Build lookup: player_id + game_pk -> features
feature_cols = [f"{m}_last20" for m in ["walk_rate", "k_rate", "iso", "contact_rate", "woba_proxy"]]
hitter_lookup = hitters[["player_id", "game_pk"] + feature_cols].copy()

# Join on-deck features
ondeck_features = hitter_lookup.rename(columns={
    "player_id": "on_deck_batter_id",
    **{c: f"ondeck_{c}" for c in feature_cols}
})
df = df.merge(ondeck_features, on=["on_deck_batter_id", "game_pk"], how="left")

# Join current batter features
batter_features = hitter_lookup.rename(columns={
    "player_id": "player_id",
    **{c: f"batter_{c}" for c in feature_cols}
})
df = df.merge(batter_features, on=["player_id", "game_pk"], how="left")

ondeck_cov = df["ondeck_woba_proxy_last20"].notna().mean()
batter_cov = df["batter_woba_proxy_last20"].notna().mean()
print(f"  On-deck feature coverage: {ondeck_cov:.1%}")
print(f"  Batter feature coverage: {batter_cov:.1%}")

# Save feature tables
df[[c for c in df.columns if c.startswith("ondeck_")]].to_parquet(
    BASE / "ondeck_hitter_features.parquet", index=False)
df[[c for c in df.columns if c.startswith("batter_")]].to_parquet(
    BASE / "current_batter_pitcher_controls.parquet", index=False)

# =====================================================================
# STEP 3 — PITCHER CONTROLS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — PITCHER CONTROLS")
print("=" * 60)

# Pitcher quality from pitcher starts
ps = pd.read_parquet(BASE.parent / "opponent_adjusted_engine" /
                     "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])
ps = ps.sort_values(["pitcher_id", "date"])
ps["pitcher_bb_rate_r5"] = ps.groupby("pitcher_id")["raw_bb_rate_start"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())
ps["pitcher_k_rate_r5"] = ps.groupby("pitcher_id")["raw_k_rate_start"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Join pitcher quality: away pitcher for home batters, home pitcher for away batters
# Pre-initialize columns
df["opp_pitcher_bb_r5"] = np.nan
df["opp_pitcher_k_r5"] = np.nan

for side, opp_side in [("home", "away"), ("away", "home")]:
    pitcher_join = ps[ps["side"] == opp_side][["game_pk", "pitcher_bb_rate_r5", "pitcher_k_rate_r5"]].copy()
    pitcher_join.columns = ["game_pk", "_pb", "_pk"]
    mask = df["home_away"] == side
    idx = df.loc[mask].index
    merged = df.loc[mask, ["game_pk"]].merge(pitcher_join, on="game_pk", how="left")
    df.loc[idx, "opp_pitcher_bb_r5"] = merged["_pb"].values
    df.loc[idx, "opp_pitcher_k_r5"] = merged["_pk"].values

pitcher_cov = df["opp_pitcher_bb_r5"].notna().mean()
print(f"  Pitcher control coverage: {pitcher_cov:.1%}")

# =====================================================================
# STEP 4 — EXISTENCE TEST
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — EXISTENCE TEST")
print("=" * 60)

# Filter to games with all features
model_cols = ["ondeck_woba_proxy_last20", "batter_woba_proxy_last20",
              "opp_pitcher_bb_r5", "opp_pitcher_k_r5"]
valid = df[model_cols + ["walk_rate", "k_rate", "iso", "pa"]].dropna()
valid = valid[valid["pa"] >= 3]  # require ≥3 PA for stable rates
print(f"  Model-ready observations: {len(valid)}")

model_results = []

for outcome, outcome_name in [
    ("walk_rate", "Walk Rate"),
    ("k_rate", "K Rate"),
    ("iso", "ISO"),
    ("contact_rate", "Contact Rate"),
    ("woba_proxy", "wOBA Proxy"),
]:
    v = df[model_cols + [outcome, "pa", "season"]].dropna()
    v = v[v["pa"] >= 3]
    if len(v) < 1000:
        continue

    # Model: outcome ~ ondeck_quality + batter_quality + pitcher_quality
    X = sm.add_constant(v[["ondeck_woba_proxy_last20", "batter_woba_proxy_last20",
                            "opp_pitcher_bb_r5", "opp_pitcher_k_r5"]])
    y = v[outcome]
    m = sm.OLS(y, X).fit()

    ondeck_coef = m.params["ondeck_woba_proxy_last20"]
    ondeck_p = m.pvalues["ondeck_woba_proxy_last20"]
    batter_coef = m.params["batter_woba_proxy_last20"]

    model_results.append({
        "outcome": outcome_name,
        "ondeck_coef": ondeck_coef, "ondeck_p": ondeck_p,
        "batter_coef": batter_coef, "batter_p": m.pvalues["batter_woba_proxy_last20"],
        "pitcher_bb_coef": m.params["opp_pitcher_bb_r5"],
        "r2": m.rsquared, "N": len(v),
    })
    sig = "***" if ondeck_p < 0.001 else "**" if ondeck_p < 0.01 else "*" if ondeck_p < 0.05 else ""
    print(f"  {outcome_name}: ondeck_coef={ondeck_coef:+.5f} (p={ondeck_p:.4f}){sig}, "
          f"batter_coef={batter_coef:+.5f}, R²={m.rsquared:.6f}")

    # Also test with ondeck ISO specifically
    if "ondeck_iso_last20" in df.columns:
        v2 = df[["ondeck_iso_last20", "batter_woba_proxy_last20",
                  "opp_pitcher_bb_r5", "opp_pitcher_k_r5", outcome, "pa"]].dropna()
        v2 = v2[v2["pa"] >= 3]
        if len(v2) > 1000:
            X2 = sm.add_constant(v2[["ondeck_iso_last20", "batter_woba_proxy_last20",
                                      "opp_pitcher_bb_r5", "opp_pitcher_k_r5"]])
            m2 = sm.OLS(v2[outcome], X2).fit()
            model_results.append({
                "outcome": f"{outcome_name} (ondeck_iso)",
                "ondeck_coef": m2.params["ondeck_iso_last20"],
                "ondeck_p": m2.pvalues["ondeck_iso_last20"],
                "batter_coef": m2.params["batter_woba_proxy_last20"],
                "batter_p": m2.pvalues["batter_woba_proxy_last20"],
                "pitcher_bb_coef": m2.params["opp_pitcher_bb_r5"],
                "r2": m2.rsquared, "N": len(v2),
            })

mr_df = pd.DataFrame(model_results)
mr_df.to_parquet(BASE / "protection_model_results.parquet", index=False)

# =====================================================================
# STEP 5 — BATTER SENSITIVITY
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — BATTER SENSITIVITY")
print("=" * 60)

# Create batter quality buckets
v = df[model_cols + ["walk_rate", "pa", "season", "player_id"]].dropna()
v = v[v["pa"] >= 3]
v["batter_bucket"] = pd.qcut(v["batter_woba_proxy_last20"], 4,
                               labels=["weak", "average", "above_avg", "elite"])

for bucket in ["weak", "average", "above_avg", "elite"]:
    sub = v[v["batter_bucket"] == bucket]
    if len(sub) < 500:
        continue
    X = sm.add_constant(sub[["ondeck_woba_proxy_last20", "opp_pitcher_bb_r5"]])
    y = sub["walk_rate"]
    m = sm.OLS(y, X).fit()
    coef = m.params["ondeck_woba_proxy_last20"]
    p = m.pvalues["ondeck_woba_proxy_last20"]
    print(f"  {bucket} batters: ondeck→walk_rate coef={coef:+.5f} (p={p:.4f}), N={len(sub)}")

# =====================================================================
# STEP 6 — PROTECTOR-TYPE CATEGORIZATION
# =====================================================================
print("\n" + "=" * 60)
print("STEP 6 — PROTECTOR TYPES")
print("=" * 60)

v = df[["ondeck_woba_proxy_last20", "ondeck_iso_last20", "ondeck_k_rate_last20",
        "ondeck_contact_rate_last20", "batter_woba_proxy_last20",
        "opp_pitcher_bb_r5", "opp_pitcher_k_r5",
        "walk_rate", "k_rate", "iso", "pa"]].dropna()
v = v[v["pa"] >= 3]

# Protector archetypes based on ISO and K rate
v["protector_type"] = "average"
v.loc[(v["ondeck_iso_last20"] > v["ondeck_iso_last20"].quantile(0.75)) &
      (v["ondeck_k_rate_last20"] < v["ondeck_k_rate_last20"].quantile(0.50)),
      "protector_type"] = "elite_damage"
v.loc[(v["ondeck_iso_last20"] > v["ondeck_iso_last20"].quantile(0.75)) &
      (v["ondeck_k_rate_last20"] >= v["ondeck_k_rate_last20"].quantile(0.50)),
      "protector_type"] = "high_k_power"
v.loc[(v["ondeck_iso_last20"] <= v["ondeck_iso_last20"].quantile(0.25)),
      "protector_type"] = "weak"
v.loc[(v["ondeck_contact_rate_last20"] > v["ondeck_contact_rate_last20"].quantile(0.75)) &
      (v["ondeck_iso_last20"] <= v["ondeck_iso_last20"].quantile(0.50)),
      "protector_type"] = "contact_only"

print(f"  Protector type distribution:")
print(v["protector_type"].value_counts().to_string())

# Test effect by protector type
for ptype in ["elite_damage", "high_k_power", "contact_only", "weak", "average"]:
    sub = v[v["protector_type"] == ptype]
    if len(sub) < 500:
        continue
    walk_rate_mean = sub["walk_rate"].mean()
    baseline = v["walk_rate"].mean()
    diff = walk_rate_mean - baseline
    print(f"  {ptype}: walk_rate={walk_rate_mean:.4f} (Δ={diff:+.4f}), N={len(sub)}")

# OLS with protector type dummies
dummies = pd.get_dummies(v["protector_type"], drop_first=True, prefix="prot").astype(float)
X_prot = pd.concat([v[["batter_woba_proxy_last20", "opp_pitcher_bb_r5"]].reset_index(drop=True),
                     dummies.reset_index(drop=True)], axis=1)
X_prot = sm.add_constant(X_prot)
y_prot = v["walk_rate"].reset_index(drop=True)
m_prot = sm.OLS(y_prot, X_prot).fit()
print(f"\n  Protector type OLS on walk_rate:")
for col in dummies.columns:
    print(f"    {col}: coef={m_prot.params[col]:+.5f}, p={m_prot.pvalues[col]:.4f}")

# =====================================================================
# STEP 7 — PAIR EXAMPLES
# =====================================================================
print("\n" + "=" * 60)
print("STEP 7 — PAIR EXAMPLES")
print("=" * 60)

# Find high-sample batter+ondeck pairs
pairs = df.groupby(["player_id", "on_deck_batter_id"]).agg(
    games=("game_pk", "nunique"),
    total_pa=("pa", "sum"),
    avg_walk_rate=("walk_rate", "mean"),
    avg_k_rate=("k_rate", "mean"),
    avg_iso=("iso", "mean"),
    batter_name=("player_name", "first"),
).reset_index()

# Get on-deck names
ondeck_names = df[["player_id", "player_name"]].drop_duplicates().rename(
    columns={"player_id": "on_deck_batter_id", "player_name": "ondeck_name"})
pairs = pairs.merge(ondeck_names, on="on_deck_batter_id", how="left")

# Filter to meaningful samples
pairs_sig = pairs[pairs["games"] >= 30].sort_values("games", ascending=False)

# For notable hitters, compare protection scenarios
pair_lines = [
    "# Pair Examples — Lineup Protection", "",
    "**Note:** These are exploratory only. Game-level K/BB rates have high variance.",
    "Minimum 30 games required per pair.", "",
]

# Find elite hitters
elite_batters = df.groupby("player_id").agg(
    name=("player_name", "first"),
    total_pa=("pa", "sum"),
    avg_woba=("woba_proxy", "mean"),
).reset_index()
elite_batters = elite_batters[elite_batters["total_pa"] > 1000].sort_values("avg_woba", ascending=False)

for _, batter_row in elite_batters.head(5).iterrows():
    bid = batter_row["player_id"]
    bname = batter_row["name"]
    batter_pairs = pairs_sig[pairs_sig["player_id"] == bid].sort_values("avg_walk_rate", ascending=False)

    if len(batter_pairs) < 2:
        continue

    pair_lines.append(f"## {bname}")
    pair_lines.append(f"Career wOBA proxy: {batter_row['avg_woba']:.3f}")
    pair_lines.append("")
    pair_lines.append("| On-Deck Hitter | Games | Walk Rate | K Rate | ISO |")
    pair_lines.append("|---------------|-------|----------|--------|-----|")

    for _, pr in batter_pairs.head(5).iterrows():
        pair_lines.append(f"| {pr.get('ondeck_name', 'Unknown')} | {pr['games']} | "
                          f"{pr['avg_walk_rate']:.3f} | {pr['avg_k_rate']:.3f} | {pr['avg_iso']:.3f} |")
    pair_lines.append("")

with open(BASE / "pair_examples.md", "w") as f:
    f.write("\n".join(pair_lines) + "\n")

# =====================================================================
# STEP 8 + 9 — EFFECT SIZE + SIMULATION RELEVANCE
# =====================================================================
print("\n" + "=" * 60)
print("STEPS 8+9 — EFFECT SIZE & SIMULATION RELEVANCE")
print("=" * 60)

# Compute effect size: elite protector vs weak protector on walk rate
v_elite = v[v["protector_type"] == "elite_damage"]
v_weak = v[v["protector_type"] == "weak"]
if len(v_elite) > 100 and len(v_weak) > 100:
    walk_diff = v_elite["walk_rate"].mean() - v_weak["walk_rate"].mean()
    k_diff = v_elite["k_rate"].mean() - v_weak["k_rate"].mean()
    iso_diff = v_elite["iso"].mean() - v_weak["iso"].mean()
    print(f"  Elite vs Weak protector:")
    print(f"    Walk rate: {walk_diff:+.4f} ({walk_diff*100:+.2f}pp)")
    print(f"    K rate: {k_diff:+.4f} ({k_diff*100:+.2f}pp)")
    print(f"    ISO: {iso_diff:+.4f}")

# =====================================================================
# FINAL REPORT
# =====================================================================
print("\n" + "=" * 60)
print("WRITING REPORT")
print("=" * 60)

R = []
R.append("# Lineup Protection Study — Report")
R.append("")
R.append(f"Dataset: {len(df)} batter-games (2022-2025)")
R.append(f"On-deck identified: {on_deck_coverage:.1%}")
R.append(f"Model-ready (≥3 PA + all features): {len(valid)}")
R.append("")
R.append("## Data Limitation")
R.append("No plate-appearance or pitch-level data available locally.")
R.append("All analysis uses batter-GAME-level outcomes (K rate, BB rate, ISO per game).")
R.append("Cannot test: zone rate, first-pitch strike, fastball rate, per-PA sequencing.")
R.append("")

R.append("## Existence Test (Step 4)")
R.append("")
R.append("OLS: outcome ~ ondeck_woba + batter_woba + pitcher_bb_r5 + pitcher_k_r5")
R.append("")
R.append("| Outcome | Ondeck Coef | Ondeck p | Batter Coef | R² | N |")
R.append("|---------|-----------|----------|------------|-----|---|")
for _, r in mr_df.iterrows():
    R.append(f"| {r['outcome']} | {r['ondeck_coef']:+.5f} | {r['ondeck_p']:.4f} | "
             f"{r['batter_coef']:+.5f} | {r['r2']:.6f} | {r['N']:.0f} |")
R.append("")

sig_outcomes = mr_df[mr_df["ondeck_p"] < 0.05]
R.append(f"Significant at p<0.05: {len(sig_outcomes)}/{len(mr_df)} models")
R.append("")

R.append("## Batter Sensitivity (Step 5)")
R.append("")
R.append("Walk rate response to ondeck quality by batter bucket:")
R.append("(higher coefficient = more sensitive to protection)")
R.append("")

R.append("## Protector Types (Step 6)")
R.append("")
R.append("| Protector Type | N | Walk Rate | Δ vs Baseline |")
R.append("|---------------|---|----------|--------------|")
baseline_walk = v["walk_rate"].mean()
for ptype in ["elite_damage", "high_k_power", "contact_only", "weak", "average"]:
    sub = v[v["protector_type"] == ptype]
    if len(sub) > 100:
        wr = sub["walk_rate"].mean()
        R.append(f"| {ptype} | {len(sub)} | {wr:.4f} | {wr - baseline_walk:+.4f} |")
R.append("")

R.append("## Effect Size (Step 8)")
R.append("")
if len(v_elite) > 100 and len(v_weak) > 100:
    R.append(f"Elite damage protector vs weak protector:")
    R.append(f"- Walk rate: {walk_diff:+.4f} ({walk_diff*100:+.2f} percentage points)")
    R.append(f"- K rate: {k_diff:+.4f} ({k_diff*100:+.2f} percentage points)")
    R.append(f"- ISO: {iso_diff:+.4f}")
R.append("")

R.append("## Simulation Relevance (Step 9)")
R.append("")

# Determine verdict
any_sig = (mr_df["ondeck_p"] < 0.05).any()
walk_sig = mr_df[(mr_df["outcome"] == "Walk Rate") & (mr_df["ondeck_p"] < 0.05)]

R.append("## Final Verdict")
R.append("")

if len(walk_sig) > 0 and abs(walk_diff) > 0.005:
    verdict = "INVESTIGATE"
    R.append(f"**{verdict}**")
    R.append("")
    R.append("Lineup protection shows a statistically detectable effect on walk rates,")
    R.append("but the magnitude is small and measured at batter-game level (not PA level).")
    R.append("")
    R.append("### Next Steps")
    R.append("1. Acquire pitch-level or PA-level data for sharper existence test")
    R.append("2. Test zone rate and first-pitch strike as primary mechanism channels")
    R.append("3. If PA-level confirms, build protector-type adjustment table")
    R.append("4. Determine if protection effect is large enough for lineup simulation refinement")
elif any_sig:
    verdict = "INVESTIGATE"
    R.append(f"**{verdict}**")
    R.append("")
    R.append("Some statistical evidence of protection effects, but effect sizes are small")
    R.append("and cannot be validated at PA/pitch level with current data.")
else:
    verdict = "SHELVE"
    R.append(f"**{verdict}**")
    R.append("")
    R.append("No statistically significant protection effects detected at batter-game level.")

R.append("")

out = BASE / "lineup_protection_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"  Saved: {out}")
print(f"  Verdict: {verdict}")
