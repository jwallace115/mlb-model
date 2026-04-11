"""
NRFI Phase 5 — Small Engine Build vs Frozen Selector
=====================================================
Train=2023, Val=2024, OOS=2025
Engines A-D vs frozen V1 selector (F5 ascending, disqualify night@4.0)
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

OUT = Path("/root/mlb-model/research/recovery/nrfi_phase5_small_engine")

# ── PHASE 0: Load data ──────────────────────────────────────────────
sel = pd.read_parquet("/root/mlb-model/research/recovery/nrfi_phase4/nrfi_phase4_selector_table.parquet")

# Rename target
sel["nrfi_result"] = sel["nrfi"].astype(int)

# Derive tt_dispersion and tt_min if missing
if "tt_dispersion" not in sel.columns:
    if "home_total_line" in sel.columns and "away_total_line" in sel.columns:
        sel["tt_min"] = sel[["home_total_line","away_total_line"]].min(axis=1)
        sel["tt_dispersion"] = (sel["home_total_line"] - sel["away_total_line"]).abs()
    else:
        sel["tt_min"] = np.nan
        sel["tt_dispersion"] = np.nan

# Use closing_total as FG_total proxy
sel["total_line"] = sel["closing_total"]

print("="*70)
print("NRFI PHASE 5 — SMALL ENGINE BUILD")
print("="*70)

# ── PHASE 1: Temporal split ──────────────────────────────────────────
# F5 data starts 2023, so: Train=2023, Val=2024, OOS=2025
# Require f5_total_best and nrfi_result
base = sel[sel["f5_total_best"].notna() & sel["nrfi_result"].notna()].copy()

train = base[base["season"] == 2023].copy()
val   = base[base["season"] == 2024].copy()
oos   = base[base["season"] == 2025].copy()

print(f"\nTemporal Split:")
print(f"  Train (2023): {len(train)} games")
print(f"  Val   (2024): {len(val)} games")
print(f"  OOS   (2025): {len(oos)} games")
print(f"  NRFI base rate: Train={train['nrfi_result'].mean():.3f}, Val={val['nrfi_result'].mean():.3f}, OOS={oos['nrfi_result'].mean():.3f}")

# ── PHASE 2: Feature coverage check ─────────────────────────────────
allowed_features = [
    "f5_total_best", "total_line", "tt_max", "tt_dispersion",
    "is_day_game", "park_factor_runs", "temperature", "wind_speed",
    "umpire_over_rate", "both_sp_1st_nrfi_rate"
]

print(f"\nFeature coverage (train):")
for f in allowed_features:
    if f in train.columns:
        cov = train[f].notna().mean()
        print(f"  {f}: {cov:.1%}")
    else:
        print(f"  {f}: MISSING")

# ── PHASE 3: Engine definitions ─────────────────────────────────────
engine_specs = {
    "A_market": ["f5_total_best", "total_line"],
    "B_market_day": ["f5_total_best", "total_line", "is_day_game"],
    "C_full": ["f5_total_best", "total_line", "is_day_game", "temperature", "wind_speed", "park_factor_runs", "umpire_over_rate"],
}

# Add tt_max and tt_dispersion to A and B if coverage > 50%
for eng in ["A_market", "B_market_day"]:
    for f in ["tt_max", "tt_dispersion"]:
        if f in train.columns and train[f].notna().mean() > 0.5:
            engine_specs[eng].append(f)

# Add tt features to C too
for f in ["tt_max", "tt_dispersion"]:
    if f in train.columns and train[f].notna().mean() > 0.5:
        if f not in engine_specs["C_full"]:
            engine_specs["C_full"].append(f)

# Add SP NRFI rate to C if coverage is OK
if "both_sp_1st_nrfi_rate" in train.columns and train["both_sp_1st_nrfi_rate"].notna().mean() > 0.5:
    engine_specs["C_full"].append("both_sp_1st_nrfi_rate")

print("\nEngine feature sets:")
for name, feats in engine_specs.items():
    print(f"  {name}: {feats}")

# ── PHASE 4: Train engines ──────────────────────────────────────────
models = {}
scalers = {}

for name, feats in engine_specs.items():
    # Filter to rows where all features are available
    mask_train = train[feats].notna().all(axis=1)
    mask_val = val[feats].notna().all(axis=1)
    mask_oos = oos[feats].notna().all(axis=1)
    
    X_tr = train.loc[mask_train, feats].values
    y_tr = train.loc[mask_train, "nrfi_result"].values
    
    sc = StandardScaler()
    X_scaled = sc.fit_transform(X_tr)
    
    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(X_scaled, y_tr)
    
    models[name] = model
    scalers[name] = sc
    
    print(f"\nEngine {name}:")
    print(f"  Train games: {mask_train.sum()} (of {len(train)})")
    print(f"  Val   games: {mask_val.sum()} (of {len(val)})")
    print(f"  OOS   games: {mask_oos.sum()} (of {len(oos)})")
    coefs = dict(zip(feats, model.coef_[0]))
    print(f"  Coefficients: { {k: f'{v:.4f}' for k,v in coefs.items()} }")
    print(f"  Intercept: {model.intercept_[0]:.4f}")

# ── Engine D: Rules score (no fitting) ──────────────────────────────
# Fixed weights derived from Phase 4 findings, set on train intuition only
def rules_score(row):
    """Lower score = more likely NRFI. Rank ascending."""
    score = 0.0
    # F5 total is primary (lower = better)
    if pd.notna(row.get("f5_total_best")):
        score += row["f5_total_best"] * 10  # dominant
    else:
        score += 50  # penalty for missing
    # Day game bonus
    if row.get("is_day_game") == 1:
        score -= 1.0
    # Cold game bonus (< 65F)
    if pd.notna(row.get("temperature")) and row["temperature"] < 65:
        score -= 0.5
    # Low total bonus
    if pd.notna(row.get("total_line")) and row["total_line"] <= 8.5:
        score -= 0.5
    # Park factor penalty (high = more runs)
    if pd.notna(row.get("park_factor_runs")) and row["park_factor_runs"] > 1.05:
        score += 0.5
    # Umpire under bonus
    if pd.notna(row.get("umpire_over_rate")) and row["umpire_over_rate"] < 0.48:
        score -= 0.3
    return score

print("\nEngine D_rules: Fixed-weight scoring (no fit)")
print("  Weights: F5*10 (primary), day=-1, cold=-0.5, low_total=-0.5, high_park=+0.5, under_ump=-0.3")

# ── PHASE 5: Generate predictions ───────────────────────────────────
for split_name, df in [("train", train), ("val", val), ("oos", oos)]:
    for eng_name, feats in engine_specs.items():
        mask = df[feats].notna().all(axis=1)
        prob = np.full(len(df), np.nan)
        if mask.sum() > 0:
            X = df.loc[mask, feats].values
            X_sc = scalers[eng_name].transform(X)
            prob[mask.values] = models[eng_name].predict_proba(X_sc)[:, 1]
        df[f"prob_{eng_name}"] = prob
    
    # Engine D
    df["score_D_rules"] = df.apply(rules_score, axis=1)
    # Convert to pseudo-prob (just for ranking, invert so higher=better NRFI)
    d_scores = df["score_D_rules"].values
    d_min, d_max = np.nanmin(d_scores), np.nanmax(d_scores)
    df["prob_D_rules"] = 1 - (d_scores - d_min) / (d_max - d_min + 1e-9)

# ── PHASE 6: Top-3 Card Evaluation ──────────────────────────────────

def evaluate_top3(df, prob_col, label, ascending_rank=False, disqualify_night_f5_4=False):
    """
    Evaluate top-3 card construction.
    ascending_rank: if True, rank by prob ascending (for rules score where lower=better)
    disqualify_night_f5_4: if True, remove night games at F5=4.0 (frozen selector rule)
    """
    results = []
    for date, slate in df.groupby("date"):
        qualified = slate[slate["f5_total_best"] <= 4.0].copy()
        if disqualify_night_f5_4:
            qualified = qualified[~((qualified["is_day_game"] == 0) & (qualified["f5_total_best"] == 4.0))]
        qualified = qualified.dropna(subset=[prob_col])
        if len(qualified) < 3:
            continue
        if ascending_rank:
            qualified = qualified.sort_values(prob_col, ascending=True)
        else:
            qualified = qualified.sort_values(prob_col, ascending=False)  # highest prob first
        top3 = qualified.head(3)
        legs_hit = top3["nrfi_result"].sum()
        card_hit = int(legs_hit == 3)
        results.append({
            "date": date, "legs_hit": legs_hit, "card_hit": card_hit,
            "n_qualified": len(qualified)
        })
    
    res_df = pd.DataFrame(results)
    if len(res_df) == 0:
        return 0.0, 0.0, 0
    leg_rate = res_df["legs_hit"].sum() / (len(res_df) * 3)
    card_rate = res_df["card_hit"].mean()
    return leg_rate, card_rate, len(res_df)


def frozen_selector_top3(df):
    """Frozen V1 selector: F5 ascending, disqualify night at F5=4.0."""
    results = []
    for date, slate in df.groupby("date"):
        qualified = slate[slate["f5_total_best"] <= 4.0].copy()
        # Disqualify night at F5=4.0
        qualified = qualified[~((qualified["is_day_game"] == 0) & (qualified["f5_total_best"] == 4.0))]
        if len(qualified) < 3:
            continue
        qualified = qualified.sort_values("f5_total_best", ascending=True)
        top3 = qualified.head(3)
        legs_hit = top3["nrfi_result"].sum()
        card_hit = int(legs_hit == 3)
        results.append({
            "date": date, "legs_hit": legs_hit, "card_hit": card_hit,
            "n_qualified": len(qualified)
        })
    
    res_df = pd.DataFrame(results)
    if len(res_df) == 0:
        return 0.0, 0.0, 0
    leg_rate = res_df["legs_hit"].sum() / (len(res_df) * 3)
    card_rate = res_df["card_hit"].mean()
    return leg_rate, card_rate, len(res_df)


# Evaluate all methods on all splits
print("\n" + "="*70)
print("TOP-3 CARD RESULTS")
print("="*70)

all_results = []

for split_name, df in [("Train_2023", train), ("Val_2024", val), ("OOS_2025", oos)]:
    print(f"\n--- {split_name} ---")
    
    # Frozen selector
    leg, card, n = frozen_selector_top3(df)
    print(f"  Frozen V1:   Leg={leg:.1%}  Card={card:.1%}  Slates={n}")
    all_results.append({"split": split_name, "method": "Frozen_V1", "leg_pct": leg, "card_pct": card, "slates": n})
    
    # Engines A-C (rank by predicted NRFI prob descending, apply F5<=4.0 gate)
    for eng_name in list(engine_specs.keys()):
        prob_col = f"prob_{eng_name}"
        leg, card, n = evaluate_top3(df, prob_col, eng_name)
        print(f"  Engine {eng_name}: Leg={leg:.1%}  Card={card:.1%}  Slates={n}")
        all_results.append({"split": split_name, "method": f"Engine_{eng_name}", "leg_pct": leg, "card_pct": card, "slates": n})
    
    # Engine D (rules score — lower is better NRFI, so rank ascending)
    leg, card, n = evaluate_top3(df, "score_D_rules", "D_rules", ascending_rank=True)
    print(f"  Engine D_rules: Leg={leg:.1%}  Card={card:.1%}  Slates={n}")
    all_results.append({"split": split_name, "method": "Engine_D_rules", "leg_pct": leg, "card_pct": card, "slates": n})

    # Engine variants with night disqualifier (same as frozen)
    for eng_name in list(engine_specs.keys()):
        prob_col = f"prob_{eng_name}"
        leg, card, n = evaluate_top3(df, prob_col, eng_name, disqualify_night_f5_4=True)
        all_results.append({"split": split_name, "method": f"Engine_{eng_name}+DQ", "leg_pct": leg, "card_pct": card, "slates": n})
    
    leg, card, n = evaluate_top3(df, "score_D_rules", "D_rules+DQ", ascending_rank=True, disqualify_night_f5_4=True)
    all_results.append({"split": split_name, "method": "Engine_D_rules+DQ", "leg_pct": leg, "card_pct": card, "slates": n})

results_df = pd.DataFrame(all_results)

# ── Print full comparison table ──────────────────────────────────────
print("\n" + "="*70)
print("FULL COMPARISON TABLE")
print("="*70)

pivot = results_df.pivot_table(index="method", columns="split", values=["leg_pct","card_pct","slates"], aggfunc="first")
# Reorder splits
for metric in ["leg_pct", "card_pct", "slates"]:
    for sp in ["Train_2023", "Val_2024", "OOS_2025"]:
        col = (metric, sp)
        if col in pivot.columns:
            if metric in ["leg_pct","card_pct"]:
                pivot[col] = pivot[col].map(lambda x: f"{x:.1%}" if pd.notna(x) else "")
            else:
                pivot[col] = pivot[col].map(lambda x: f"{int(x)}" if pd.notna(x) else "")

print(pivot.to_string())

# ── PHASE 7: Pick best engine for OOS ───────────────────────────────
print("\n" + "="*70)
print("VALIDATION SELECTION")
print("="*70)

val_results = results_df[results_df["split"] == "Val_2024"].copy()
val_results = val_results.sort_values("card_pct", ascending=False)
print("\nVal 2024 ranked by card rate:")
for _, r in val_results.iterrows():
    print(f"  {r['method']:25s}  Leg={r['leg_pct']:.1%}  Card={r['card_pct']:.1%}  Slates={r['slates']}")

best_val = val_results.iloc[0]
second_val = val_results.iloc[1] if len(val_results) > 1 else None

# Check if top two are within 2pp
if second_val is not None and abs(best_val["card_pct"] - second_val["card_pct"]) < 0.02:
    # Pick simpler
    complexity = {
        "Frozen_V1": 0, "Engine_D_rules": 1, "Engine_D_rules+DQ": 1,
        "Engine_A_market": 2, "Engine_A_market+DQ": 2,
        "Engine_B_market_day": 3, "Engine_B_market_day+DQ": 3,
        "Engine_C_full": 4, "Engine_C_full+DQ": 4,
    }
    c1 = complexity.get(best_val["method"], 99)
    c2 = complexity.get(second_val["method"], 99)
    chosen = best_val["method"] if c1 <= c2 else second_val["method"]
    print(f"\nTop two within 2pp — choosing simpler: {chosen}")
else:
    chosen = best_val["method"]
    print(f"\nChosen for OOS: {chosen} (best val card rate)")

# ── PHASE 8: OOS comparison ─────────────────────────────────────────
print("\n" + "="*70)
print("OOS COMPARISON (2025)")
print("="*70)

oos_frozen = results_df[(results_df["split"]=="OOS_2025") & (results_df["method"]=="Frozen_V1")].iloc[0]
oos_chosen = results_df[(results_df["split"]=="OOS_2025") & (results_df["method"]==chosen)].iloc[0]

print(f"\n  Frozen V1:    Leg={oos_frozen['leg_pct']:.1%}  Card={oos_frozen['card_pct']:.1%}  Slates={oos_frozen['slates']}")
print(f"  {chosen}: Leg={oos_chosen['leg_pct']:.1%}  Card={oos_chosen['card_pct']:.1%}  Slates={oos_chosen['slates']}")

delta_card = oos_chosen["card_pct"] - oos_frozen["card_pct"]
delta_leg = oos_chosen["leg_pct"] - oos_frozen["leg_pct"]
print(f"\n  Delta card: {delta_card:+.1%}")
print(f"  Delta leg:  {delta_leg:+.1%}")

# ── PHASE 9: Diagnostic — overlap with frozen selector ───────────────
print("\n" + "="*70)
print("DIAGNOSTIC: ENGINE vs FROZEN SELECTOR OVERLAP")
print("="*70)

# Check how often the engine's top-3 matches the frozen selector's top-3
overlap_results = []
for date, slate in oos.groupby("date"):
    qualified = slate[slate["f5_total_best"] <= 4.0].copy()
    qual_dq = qualified[~((qualified["is_day_game"]==0) & (qualified["f5_total_best"]==4.0))]
    
    if len(qual_dq) < 3:
        continue
    
    # Frozen top 3
    frozen_top3 = set(qual_dq.sort_values("f5_total_best").head(3)["game_pk"].values)
    
    # Best engine top 3
    if "prob_" in chosen or "Engine_" in chosen:
        eng_key = chosen.replace("Engine_","").replace("+DQ","")
        prob_col = f"prob_{eng_key}" if f"prob_{eng_key}" in qualified.columns else f"score_{eng_key}"
        use_asc = "D_rules" in chosen
        use_dq = "+DQ" in chosen
        
        q2 = qual_dq if use_dq else qualified
        q2 = q2.dropna(subset=[prob_col])
        if len(q2) < 3:
            continue
        if use_asc:
            engine_top3 = set(q2.sort_values(prob_col, ascending=True).head(3)["game_pk"].values)
        else:
            engine_top3 = set(q2.sort_values(prob_col, ascending=False).head(3)["game_pk"].values)
    else:
        engine_top3 = frozen_top3  # Frozen_V1 chosen
    
    overlap = len(frozen_top3 & engine_top3)
    overlap_results.append({"date": date, "overlap": overlap})

if overlap_results:
    ov_df = pd.DataFrame(overlap_results)
    print(f"\nOOS 2025: {len(ov_df)} slates compared")
    print(f"  Mean overlap: {ov_df['overlap'].mean():.2f} / 3 legs")
    for i in range(4):
        pct = (ov_df["overlap"]==i).mean()
        print(f"  {i}/3 overlap: {pct:.1%}")

# ── PHASE 10: Decision ──────────────────────────────────────────────
print("\n" + "="*70)
print("DECISION")
print("="*70)

if chosen == "Frozen_V1":
    verdict = "SELECTOR REMAINS BEST"
    explanation = "No engine beat the frozen V1 selector on validation. Selector remains recommended."
elif delta_card > 0.03:
    verdict = "SMALL ENGINE BEATS SELECTOR"
    explanation = f"{chosen} outperforms frozen selector by {delta_card:+.1%} card rate on OOS 2025."
elif delta_card > 0:
    verdict = "MARGINAL ENGINE IMPROVEMENT"
    explanation = f"{chosen} shows +{delta_card:.1%} card rate on OOS but below 3pp threshold for switching."
elif delta_card > -0.02:
    verdict = "INCONCLUSIVE"
    explanation = f"{chosen} performed within 2pp of frozen selector on OOS. Insufficient evidence to switch."
else:
    verdict = "SELECTOR REMAINS BEST"
    explanation = f"{chosen} underperformed frozen selector by {delta_card:.1%} on OOS. Frozen V1 stays."

print(f"\n  VERDICT: {verdict}")
print(f"  {explanation}")

# ── Save outputs ─────────────────────────────────────────────────────
results_df.to_csv(OUT / "NRFI_PHASE5_FINAL_TABLE.csv", index=False)

# Build summary MD
md_lines = []
md_lines.append("# NRFI Phase 5 — Small Engine Build vs Frozen Selector\n")
md_lines.append(f"**Date:** 2026-04-11")
md_lines.append(f"**Scope:** Logistic regression engines (A-D) vs frozen V1 selector")
md_lines.append(f"**Split:** Train=2023, Val=2024, OOS=2025\n")
md_lines.append("---\n")
md_lines.append(f"## Verdict: **{verdict}**\n")
md_lines.append(f"{explanation}\n")
md_lines.append("---\n")

md_lines.append("## Temporal Split\n")
md_lines.append(f"| Split | Season | Games | NRFI Rate |")
md_lines.append(f"|-------|--------|-------|-----------|")
md_lines.append(f"| Train | 2023 | {len(train)} | {train['nrfi_result'].mean():.1%} |")
md_lines.append(f"| Val | 2024 | {len(val)} | {val['nrfi_result'].mean():.1%} |")
md_lines.append(f"| OOS | 2025 | {len(oos)} | {oos['nrfi_result'].mean():.1%} |")
md_lines.append(f"\n**Note:** F5 data starts 2023 (2022 has 0% coverage). 2026 excluded (in-season).\n")

md_lines.append("## Engine Definitions\n")
md_lines.append("| Engine | Type | Features |")
md_lines.append("|--------|------|----------|")
for name, feats in engine_specs.items():
    md_lines.append(f"| {name} | LogReg(C=1) | {', '.join(feats)} |")
md_lines.append(f"| D_rules | Fixed-weight | F5*10, day=-1, cold=-0.5, low_total=-0.5, high_park=+0.5, under_ump=-0.3 |")
md_lines.append(f"| +DQ variants | Same + disqualify night@F5=4.0 | (applied as filter) |\n")

md_lines.append("## Top-3 Card Results\n")
md_lines.append("| Method | Train Leg% | Train Card% | Val Leg% | Val Card% | OOS Leg% | OOS Card% |")
md_lines.append("|--------|-----------|------------|---------|----------|---------|----------|")

# Only show main methods (no +DQ variants cluttering)
main_methods = ["Frozen_V1"] + [f"Engine_{n}" for n in engine_specs.keys()] + ["Engine_D_rules"]
dq_methods = [f"Engine_{n}+DQ" for n in engine_specs.keys()] + ["Engine_D_rules+DQ"]

for method in main_methods + dq_methods:
    row_parts = [method]
    for sp in ["Train_2023", "Val_2024", "OOS_2025"]:
        match = results_df[(results_df["method"]==method) & (results_df["split"]==sp)]
        if len(match) > 0:
            r = match.iloc[0]
            row_parts.append(f"{r['leg_pct']:.1%}")
            row_parts.append(f"{r['card_pct']:.1%}")
        else:
            row_parts.append("")
            row_parts.append("")
    md_lines.append("| " + " | ".join(row_parts) + " |")

md_lines.append("")

md_lines.append("## Validation Selection\n")
md_lines.append(f"**Chosen engine:** {chosen}")
md_lines.append(f"**Reason:** {'Best card rate on validation' if chosen == val_results.iloc[0]['method'] else 'Simpler model within 2pp of best'}\n")

md_lines.append("## OOS Comparison\n")
md_lines.append(f"| Method | Leg% | Card% | Slates |")
md_lines.append(f"|--------|------|-------|--------|")
md_lines.append(f"| Frozen V1 | {oos_frozen['leg_pct']:.1%} | {oos_frozen['card_pct']:.1%} | {oos_frozen['slates']} |")
md_lines.append(f"| {chosen} | {oos_chosen['leg_pct']:.1%} | {oos_chosen['card_pct']:.1%} | {oos_chosen['slates']} |")
md_lines.append(f"\n**Delta card rate:** {delta_card:+.1%}")
md_lines.append(f"**Delta leg rate:** {delta_leg:+.1%}\n")

if overlap_results:
    ov_df = pd.DataFrame(overlap_results)
    md_lines.append("## Diagnostic: Top-3 Overlap (OOS)\n")
    md_lines.append(f"Mean overlap with frozen selector: {ov_df['overlap'].mean():.2f} / 3 legs\n")
    md_lines.append("| Overlap | Pct of Slates |")
    md_lines.append("|---------|---------------|")
    for i in range(4):
        pct = (ov_df["overlap"]==i).mean()
        md_lines.append(f"| {i}/3 | {pct:.1%} |")
    md_lines.append("")

md_lines.append("## Coefficients (chosen engine)\n")
if chosen != "Frozen_V1" and "D_rules" not in chosen:
    eng_key = chosen.replace("Engine_","").replace("+DQ","")
    if eng_key in engine_specs:
        feats = engine_specs[eng_key]
        coefs = dict(zip(feats, models[eng_key].coef_[0]))
        md_lines.append("| Feature | Coefficient |")
        md_lines.append("|---------|-------------|")
        for f, c in coefs.items():
            md_lines.append(f"| {f} | {c:.4f} |")
        md_lines.append(f"| intercept | {models[eng_key].intercept_[0]:.4f} |")
elif "D_rules" in chosen:
    md_lines.append("Rules engine uses fixed weights (no fitted coefficients).")
else:
    md_lines.append("Frozen V1 has no coefficients — pure F5 sort.")

md_lines.append(f"\n---\n")
md_lines.append(f"## Decision: **{verdict}**\n")
md_lines.append(f"{explanation}\n")

md_lines.append("## Files Produced\n")
md_lines.append("| File | Description |")
md_lines.append("|------|-------------|")
md_lines.append("| `nrfi_phase5_engine.py` | Full analysis script |")
md_lines.append("| `NRFI_PHASE5_FINAL_TABLE.csv` | All methods x splits comparison |")
md_lines.append("| `NRFI_PHASE5_EXEC_SUMMARY.md` | This file |")

with open(OUT / "NRFI_PHASE5_EXEC_SUMMARY.md", "w") as f:
    f.write("\n".join(md_lines))

print(f"\nFiles written to {OUT}")
print("Done.")
