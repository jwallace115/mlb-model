#!/usr/bin/env python3
"""
Lineup Protection ISO Mechanism Follow-up.
Tests whether the observed ISO/power effect is a real pitch-attack mechanism
or lineup-quality clustering noise.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
STUDY = BASE.parent
np.random.seed(42)

# =====================================================================
# STEP 0 — AUDIT
# =====================================================================
print("=" * 60)
print("STEP 0 — AUDIT")
print("=" * 60)

pa = pd.read_parquet(STUDY / "protection_pa_dataset.parquet")
pa["game_date"] = pd.to_datetime(pa["game_date"])

audit = [
    "# Source Audit — ISO Mechanism Follow-up", "",
    f"## Data Available",
    f"- protection_pa_dataset.parquet: {len(pa)} batter-games",
    f"- Statcast per-start (pitcher): zone_rate, whiff_rate, hard_hit_rate, barrel_rate",
    "",
    "## CRITICAL LIMITATION",
    "**No batter-level pitch attack data available locally.**",
    "- zone_rate: PITCHER-GAME level only (not per-batter or per-PA)",
    "- first_pitch_strike: NOT available",
    "- fastball_rate: NOT available",
    "- hard_hit / barrel: PITCHER-GAME level only (not per-batter)",
    "",
    "## What We CAN Test",
    "- Batter-game K rate, BB rate, ISO, contact rate, wOBA as outcomes",
    "- Extra-base-hit rate (2B+3B+HR) / PA as damage proxy",
    "- HR rate as isolated power proxy",
    "- Pitcher-game aggregate Statcast (zone_rate, whiff_rate, hard_hit_allowed)",
    "  as environmental context (not per-batter causal)",
    "",
    "## Design Implication",
    "Cannot directly test: 'does protector change zone rate to THIS batter?'",
    "CAN test: 'does protector change batter outcomes in ways consistent with",
    "attack-mechanism hypothesis vs clustering hypothesis?'",
]
with open(BASE / "source_audit.md", "w") as f:
    f.write("\n".join(audit) + "\n")
print("  Saved source_audit.md")

# =====================================================================
# STEP 1 — BUILD MECHANISM DATASET
# =====================================================================
print("\n" + "=" * 60)
print("STEP 1 — BUILD DATASET")
print("=" * 60)

# Load on-deck and batter features
ondeck_feat = pd.read_parquet(STUDY / "ondeck_hitter_features.parquet")
batter_feat = pd.read_parquet(STUDY / "current_batter_pitcher_controls.parquet")

# The features were saved without index alignment — they match pa by row position
for col in ondeck_feat.columns:
    pa[col] = ondeck_feat[col].values
for col in batter_feat.columns:
    pa[col] = batter_feat[col].values

# Add pitcher controls (already in pa from original study)
# opp_pitcher_bb_r5 and opp_pitcher_k_r5 were added in original study

# Compute additional outcome variables
pa["xbh_rate"] = (pa["doubles"] + pa["triples"] + pa["hr"]) / pa["pa"].clip(lower=1)
pa["hr_rate"] = pa["hr"] / pa["pa"].clip(lower=1)
pa["walk_flag_game"] = (pa["bb"] > 0).astype(int)  # any walk in game

# Add pitcher-level Statcast (game-level aggregate, NOT per-batter)
sc = pd.read_parquet(STUDY.parent / "statcast_enrichment" /
                     "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])
# Merge pitcher's game-level zone_rate, whiff_rate, hard_hit_rate
# For each batter, the opposing pitcher's game stats are the environmental context
bu = pd.read_parquet(STUDY.parent.parent / "sim" / "data" / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
starters = bu[bu["is_starter"]][["game_pk", "pitcher_id", "team"]].copy()

# Match: for home batters, the opposing pitcher is the away starter
sc_game = sc[["game_pk", "pitcher_id", "zone_rate", "whiff_rate",
              "hard_hit_rate", "barrel_rate"]].copy()
sc_game = sc_game.merge(starters[["game_pk", "pitcher_id", "team"]],
                        on=["game_pk", "pitcher_id"], how="left")

# For home batters → away pitcher stats; for away batters → home pitcher stats
gt = pd.read_parquet(STUDY.parent.parent / "sim" / "data" / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
sc_game = sc_game.merge(gt[["game_pk", "home_team", "away_team"]], on="game_pk", how="left")
sc_game["pitcher_side"] = np.where(sc_game["team"] == sc_game["home_team"], "home", "away")

# Away pitcher stats → for home batters
away_pitcher_sc = sc_game[sc_game["pitcher_side"] == "away"][
    ["game_pk", "zone_rate", "whiff_rate", "hard_hit_rate", "barrel_rate"]].rename(
    columns={"zone_rate": "opp_pitcher_zone_rate", "whiff_rate": "opp_pitcher_whiff_rate",
             "hard_hit_rate": "opp_pitcher_hh_rate", "barrel_rate": "opp_pitcher_barrel_rate"})
away_pitcher_sc["_batter_side"] = "home"

home_pitcher_sc = sc_game[sc_game["pitcher_side"] == "home"][
    ["game_pk", "zone_rate", "whiff_rate", "hard_hit_rate", "barrel_rate"]].rename(
    columns={"zone_rate": "opp_pitcher_zone_rate", "whiff_rate": "opp_pitcher_whiff_rate",
             "hard_hit_rate": "opp_pitcher_hh_rate", "barrel_rate": "opp_pitcher_barrel_rate"})
home_pitcher_sc["_batter_side"] = "away"

opp_sc = pd.concat([away_pitcher_sc, home_pitcher_sc])

for side in ["home", "away"]:
    mask = pa["home_away"] == side
    idx = pa.loc[mask].index
    merged = pa.loc[mask, ["game_pk"]].merge(
        opp_sc[opp_sc["_batter_side"] == side].drop(columns=["_batter_side"]),
        on="game_pk", how="left")
    for col in ["opp_pitcher_zone_rate", "opp_pitcher_whiff_rate",
                "opp_pitcher_hh_rate", "opp_pitcher_barrel_rate"]:
        pa.loc[idx, col] = merged[col].values

# Protector type (re-derive)
pa["protector_type"] = "average"
pa.loc[(pa["ondeck_iso_last20"] > pa["ondeck_iso_last20"].quantile(0.75)) &
       (pa["ondeck_k_rate_last20"] < pa["ondeck_k_rate_last20"].quantile(0.50)),
       "protector_type"] = "elite_damage"
pa.loc[(pa["ondeck_iso_last20"] > pa["ondeck_iso_last20"].quantile(0.75)) &
       (pa["ondeck_k_rate_last20"] >= pa["ondeck_k_rate_last20"].quantile(0.50)),
       "protector_type"] = "high_k_power"
pa.loc[(pa["ondeck_iso_last20"] <= pa["ondeck_iso_last20"].quantile(0.25)),
       "protector_type"] = "weak"
pa.loc[(pa["ondeck_contact_rate_last20"] > pa["ondeck_contact_rate_last20"].quantile(0.75)) &
       (pa["ondeck_iso_last20"] <= pa["ondeck_iso_last20"].quantile(0.50)),
       "protector_type"] = "contact_only"

pa.to_parquet(BASE / "iso_mechanism_dataset.parquet", index=False)

sc_cov = pa["opp_pitcher_zone_rate"].notna().mean()
print(f"  Dataset: {len(pa)} batter-games")
print(f"  Pitcher Statcast coverage (game-level): {sc_cov:.1%}")
print(f"  On-deck features coverage: {pa['ondeck_woba_proxy_last20'].notna().mean():.1%}")

# =====================================================================
# STEP 2 — ATTACK CHANNEL TEST (indirect via pitcher game aggregate)
# =====================================================================
print("\n" + "=" * 60)
print("STEP 2 — ATTACK CHANNEL TEST")
print("=" * 60)

# We cannot test per-batter attack changes directly.
# Instead test: in games where the overall lineup has better protection,
# does the pitcher's aggregate zone_rate / whiff_rate change?
#
# This is weaker than per-PA but it's the best we can do.

# For each game-team, compute average protector quality across all slots
lineup_prot = pa.groupby(["game_pk", "team"]).agg(
    avg_ondeck_woba=("ondeck_woba_proxy_last20", "mean"),
    avg_ondeck_iso=("ondeck_iso_last20", "mean"),
    avg_batter_woba=("batter_woba_proxy_last20", "mean"),
).reset_index()

# Join opposing pitcher's game-level Statcast
lineup_prot = lineup_prot.merge(
    pa[["game_pk", "team", "opp_pitcher_zone_rate", "opp_pitcher_whiff_rate",
        "opp_pitcher_hh_rate", "opp_pitcher_barrel_rate"]].drop_duplicates(subset=["game_pk", "team"]),
    on=["game_pk", "team"], how="left"
)

model_results = []

# Test: pitcher zone_rate ~ lineup avg protector quality + lineup batter quality
for outcome, label in [
    ("opp_pitcher_zone_rate", "Pitcher Zone Rate"),
    ("opp_pitcher_whiff_rate", "Pitcher Whiff Rate"),
    ("opp_pitcher_hh_rate", "Pitcher Hard-Hit Allowed"),
    ("opp_pitcher_barrel_rate", "Pitcher Barrel Allowed"),
]:
    valid = lineup_prot[["avg_ondeck_woba", "avg_batter_woba", outcome]].dropna()
    if len(valid) < 500:
        continue
    X = sm.add_constant(valid[["avg_ondeck_woba", "avg_batter_woba"]])
    y = valid[outcome]
    m = sm.OLS(y, X).fit()
    coef = m.params["avg_ondeck_woba"]
    p = m.pvalues["avg_ondeck_woba"]
    model_results.append({
        "test": "attack_channel", "outcome": label,
        "ondeck_var": "avg_ondeck_woba",
        "coef": coef, "p": p, "r2": m.rsquared, "N": len(valid),
    })
    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
    print(f"  {label}: ondeck_woba_coef={coef:+.5f} (p={p:.4f}){sig}")

# =====================================================================
# STEP 3 — DAMAGE CHANNEL TEST
# =====================================================================
print("\n" + "=" * 60)
print("STEP 3 — DAMAGE CHANNEL TEST")
print("=" * 60)

# Test batter-game outcomes controlling for protector quality
# These are the actual batter outcomes, not pitcher aggregates
controls = ["ondeck_woba_proxy_last20", "batter_woba_proxy_last20",
            "opp_pitcher_zone_rate", "opp_pitcher_whiff_rate"]

for outcome, label in [
    ("iso", "ISO"),
    ("xbh_rate", "Extra-Base-Hit Rate"),
    ("hr_rate", "HR Rate"),
    ("contact_rate", "Contact Rate"),
    ("woba_proxy", "wOBA Proxy"),
]:
    valid = pa[controls + [outcome, "pa"]].dropna()
    valid = valid[valid["pa"] >= 3]
    if len(valid) < 1000:
        continue
    X = sm.add_constant(valid[controls])
    y = valid[outcome]
    m = sm.OLS(y, X).fit()
    coef = m.params["ondeck_woba_proxy_last20"]
    p = m.pvalues["ondeck_woba_proxy_last20"]
    model_results.append({
        "test": "damage_channel", "outcome": label,
        "ondeck_var": "ondeck_woba",
        "coef": coef, "p": p, "r2": m.rsquared, "N": len(valid),
    })
    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
    print(f"  {label}: ondeck_woba_coef={coef:+.5f} (p={p:.4f}){sig}")

    # Also with pitcher Statcast controls if available
    env_controls = controls + ["opp_pitcher_zone_rate", "opp_pitcher_hh_rate"]
    valid2 = pa[env_controls + [outcome, "pa"]].dropna()
    valid2 = valid2[valid2["pa"] >= 3]
    if len(valid2) > 1000:
        X2 = sm.add_constant(valid2[env_controls])
        y2 = valid2[outcome]
        m2 = sm.OLS(y2, X2).fit()
        coef2 = m2.params["ondeck_woba_proxy_last20"]
        p2 = m2.pvalues["ondeck_woba_proxy_last20"]
        model_results.append({
            "test": "damage_with_env", "outcome": label,
            "ondeck_var": "ondeck_woba (+ pitcher env)",
            "coef": coef2, "p": p2, "r2": m2.rsquared, "N": len(valid2),
        })
        print(f"    + pitcher env: coef={coef2:+.5f} (p={p2:.4f})")

# =====================================================================
# STEP 4 — CLUSTERING / CONFOUND CHECK
# =====================================================================
print("\n" + "=" * 60)
print("STEP 4 — CLUSTERING CHECK")
print("=" * 60)

valid = pa[["batter_woba_proxy_last20", "ondeck_woba_proxy_last20",
            "batter_iso_last20", "ondeck_iso_last20"]].dropna()

r_woba, _ = stats.pearsonr(valid["batter_woba_proxy_last20"], valid["ondeck_woba_proxy_last20"])
r_iso, _ = stats.pearsonr(valid["batter_iso_last20"], valid["ondeck_iso_last20"])
print(f"  corr(batter_woba, ondeck_woba): r={r_woba:.4f}")
print(f"  corr(batter_iso, ondeck_iso): r={r_iso:.4f}")

# Residualized protector quality
valid_res = pa[["ondeck_woba_proxy_last20", "batter_woba_proxy_last20",
                "batting_order_slot", "opp_pitcher_zone_rate", "opp_pitcher_whiff_rate",
                "iso", "walk_rate", "pa"]].dropna()
valid_res = valid_res[valid_res["pa"] >= 3]

# Residualize ondeck against batter quality + slot
X_resid = sm.add_constant(valid_res[["batter_woba_proxy_last20", "batting_order_slot"]])
y_resid = valid_res["ondeck_woba_proxy_last20"]
m_resid = sm.OLS(y_resid, X_resid).fit()
valid_res["residual_ondeck_woba"] = m_resid.resid

# Re-test with residualized protector
for outcome, label in [("iso", "ISO (residualized)"), ("walk_rate", "Walk Rate (residualized)")]:
    X = sm.add_constant(valid_res[["residual_ondeck_woba", "batter_woba_proxy_last20",
                                    "opp_pitcher_zone_rate", "opp_pitcher_whiff_rate"]])
    y = valid_res[outcome]
    m = sm.OLS(y, X).fit()
    coef = m.params["residual_ondeck_woba"]
    p = m.pvalues["residual_ondeck_woba"]
    model_results.append({
        "test": "residualized", "outcome": label,
        "ondeck_var": "residual_ondeck_woba",
        "coef": coef, "p": p, "r2": m.rsquared, "N": len(valid_res),
    })
    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
    print(f"  {label}: residual_ondeck_coef={coef:+.5f} (p={p:.4f}){sig}")

# =====================================================================
# STEP 5 — PROTECTOR-TYPE EFFECTS
# =====================================================================
print("\n" + "=" * 60)
print("STEP 5 — PROTECTOR-TYPE EFFECTS")
print("=" * 60)

valid_pt = pa[["protector_type", "batter_woba_proxy_last20",
               "iso", "walk_rate", "xbh_rate", "hr_rate", "contact_rate", "pa",
               "opp_pitcher_zone_rate", "opp_pitcher_hh_rate"]].dropna(
    subset=["protector_type", "batter_woba_proxy_last20", "iso", "pa"])
valid_pt = valid_pt[valid_pt["pa"] >= 3]

ptype_results = []
weak_baseline = valid_pt[valid_pt["protector_type"] == "weak"]

for ptype in ["elite_damage", "high_k_power", "contact_only", "average", "weak"]:
    sub = valid_pt[valid_pt["protector_type"] == ptype]
    if len(sub) < 200:
        continue
    row = {"protector_type": ptype, "N": len(sub)}
    for metric in ["iso", "walk_rate", "xbh_rate", "hr_rate", "contact_rate"]:
        row[f"{metric}_mean"] = sub[metric].mean()
        row[f"{metric}_delta"] = sub[metric].mean() - weak_baseline[metric].mean()
    # Pitcher env if available
    for env_metric in ["opp_pitcher_zone_rate", "opp_pitcher_hh_rate"]:
        if sub[env_metric].notna().sum() > 100:
            row[f"{env_metric}_mean"] = sub[env_metric].dropna().mean()
            row[f"{env_metric}_delta"] = sub[env_metric].dropna().mean() - weak_baseline[env_metric].dropna().mean()
    ptype_results.append(row)
    print(f"  {ptype}: ISO_delta={row.get('iso_delta',0):+.4f}, "
          f"walk_delta={row.get('walk_rate_delta',0):+.4f}, "
          f"xbh_delta={row.get('xbh_rate_delta',0):+.4f}")

ptype_df = pd.DataFrame(ptype_results)
ptype_df.to_parquet(BASE / "protector_type_effects.parquet", index=False)

# =====================================================================
# SAVE RESULTS + WRITE REPORT
# =====================================================================
mr_df = pd.DataFrame(model_results)
mr_df.to_parquet(BASE / "iso_mechanism_model_results.parquet", index=False)

print("\n" + "=" * 60)
print("WRITING REPORT")
print("=" * 60)

R = []
R.append("# ISO Mechanism Follow-up — Report")
R.append("")
R.append(f"Dataset: {len(pa)} batter-games (2022-2025)")
R.append("")

R.append("## Critical Data Limitation")
R.append("")
R.append("**No batter-level pitch attack data available locally.**")
R.append("Zone rate, first-pitch strike, fastball rate all require pitch-by-pitch data.")
R.append("Only pitcher-game-aggregate Statcast is available (zone_rate, whiff_rate per start).")
R.append("This means we CANNOT directly test 'does protector change attack on THIS batter.'")
R.append("We CAN test indirect effects through batter outcomes and pitcher game aggregates.")
R.append("")

R.append("## Step 2 — Attack Channel (Pitcher Game Aggregate)")
R.append("")
R.append("Does lineup-average protector quality change the opposing pitcher's game aggregate?")
R.append("")
R.append("| Outcome | Ondeck Coef | p-value | Direction |")
R.append("|---------|-----------|---------|-----------|")
for _, r in mr_df[mr_df.test == "attack_channel"].iterrows():
    direction = "+" if r.coef > 0 else "-"
    R.append(f"| {r.outcome} | {r.coef:+.5f} | {r.p:.4f} | {direction} |")
R.append("")

R.append("## Step 3 — Damage Channel (Batter Outcomes)")
R.append("")
R.append("Does better protector quality increase batter ISO/power/wOBA?")
R.append("")
R.append("| Outcome | Test | Ondeck Coef | p-value | R² | N |")
R.append("|---------|------|-----------|---------|-----|---|")
for _, r in mr_df[mr_df.test.isin(["damage_channel", "damage_with_env"])].iterrows():
    R.append(f"| {r.outcome} | {r.ondeck_var} | {r.coef:+.5f} | {r.p:.4f} | {r.r2:.6f} | {r.N:.0f} |")
R.append("")

R.append("## Step 4 — Clustering Check")
R.append("")
R.append(f"- corr(batter_woba, ondeck_woba): r={r_woba:.4f}")
R.append(f"- corr(batter_iso, ondeck_iso): r={r_iso:.4f}")
R.append("")

if abs(r_woba) > 0.30:
    R.append("**WARNING: substantial clustering** — batter and protector quality are correlated.")
    R.append("Residualization is critical for valid inference.")
elif abs(r_woba) > 0.15:
    R.append("Moderate clustering present. Residualized tests needed for confirmation.")
else:
    R.append("Minimal clustering. Raw and residualized results should be similar.")
R.append("")

R.append("### Residualized Protector Tests")
R.append("")
R.append("| Outcome | Residual Ondeck Coef | p-value |")
R.append("|---------|---------------------|---------|")
for _, r in mr_df[mr_df.test == "residualized"].iterrows():
    R.append(f"| {r.outcome} | {r.coef:+.5f} | {r.p:.4f} |")
R.append("")

R.append("## Step 5 — Protector Type Effects")
R.append("")
R.append("| Protector Type | N | ISO Δ | Walk Δ | XBH Δ | HR Δ |")
R.append("|---------------|---|-------|--------|-------|------|")
for _, r in ptype_df.iterrows():
    R.append(f"| {r.protector_type} | {r.N:.0f} | {r.get('iso_delta',0):+.4f} | "
             f"{r.get('walk_rate_delta',0):+.4f} | {r.get('xbh_rate_delta',0):+.4f} | "
             f"{r.get('hr_rate_delta',0):+.4f} |")
R.append("")

# Final interpretation
R.append("## Final Interpretation")
R.append("")

# Check if residualized ISO effect survives
resid_iso = mr_df[(mr_df.test == "residualized") & (mr_df.outcome.str.contains("ISO"))]
resid_walk = mr_df[(mr_df.test == "residualized") & (mr_df.outcome.str.contains("Walk"))]

iso_survives = len(resid_iso) > 0 and resid_iso.iloc[0]["p"] < 0.05
walk_survives = len(resid_walk) > 0 and resid_walk.iloc[0]["p"] < 0.05

if iso_survives:
    R.append("**ISO effect SURVIVES residualization** — evidence of real protection mechanism.")
elif walk_survives:
    R.append("**Walk effect survives but ISO does not** — protection mainly through walk mechanism.")
else:
    R.append("**Effects do NOT survive residualization** — likely lineup clustering noise.")

R.append("")
R.append("### Q1: Does protector quality change pitch attack behavior?")
attack_sig = mr_df[(mr_df.test == "attack_channel") & (mr_df.p < 0.10)]
if len(attack_sig) > 0:
    R.append("CANNOT DEFINITIVELY ANSWER — no per-batter attack data available.")
    R.append("Pitcher-game-aggregate test shows:")
    for _, r in attack_sig.iterrows():
        R.append(f"  - {r.outcome}: {r.coef:+.5f} (p={r.p:.4f})")
else:
    R.append("No significant effect on pitcher game aggregates. Attack channel NOT confirmed.")

R.append("")
R.append("### Q2: Is the ISO effect real or clustering?")
if iso_survives:
    R.append(f"ISO effect real after residualization (p={resid_iso.iloc[0]['p']:.4f}).")
else:
    R.append("ISO effect likely driven by lineup quality clustering — does not survive residualization.")

R.append("")
R.append("### Q3: Large enough for totals?")
elite_delta = ptype_df[ptype_df.protector_type == "elite_damage"]
if len(elite_delta) > 0:
    iso_d = elite_delta.iloc[0].get("iso_delta", 0)
    R.append(f"Elite protector ISO delta vs weak: {iso_d:+.4f}")
    if abs(iso_d) < 0.005:
        R.append("**Negligible for totals** — less than 1 extra-base-hit per 200 PA difference.")
    elif abs(iso_d) < 0.015:
        R.append("**Small but detectable** — may matter at player prop level.")
    else:
        R.append("**Meaningful** — worth investigating for simulation refinement.")

R.append("")
R.append("## Final Verdict")
R.append("")

if iso_survives and abs(iso_d) > 0.01:
    verdict = "INVESTIGATE"
    R.append(f"**{verdict}**")
    R.append("Real protection mechanism detected at ISO level, survives residualization.")
    R.append("Next step: acquire pitch-level data to test attack channel directly.")
elif walk_survives:
    verdict = "ARCHIVE"
    R.append(f"**{verdict}**")
    R.append("Walk effect real but ISO effect is clustering noise.")
    R.append("Archive for future player prop research (walk totals).")
else:
    verdict = "ARCHIVE"
    R.append(f"**{verdict}**")
    R.append("Protection effects do not survive proper clustering controls.")
    R.append("The original study's ISO finding was driven by lineup quality correlation,")
    R.append("not a true pitch-attack mechanism. Archive — no further investigation needed.")

R.append("")

out = BASE / "iso_mechanism_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"  Saved: {out}")
print(f"  Verdict: {verdict}")
