#!/usr/bin/env python3
"""
Phase 3 Lite — LT01 and LT02 signal tests.
Lineup K-rate replacement and contact×whiff interaction.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, brier_score_loss

OUT = Path("research/mlb_v3_lineup_model/phase3_lite")

# ======================================================================
# LOAD & JOIN DATA
# ======================================================================
ft = pd.read_parquet("sim/data/feature_table.parquet")
lineup = pd.read_parquet("research/mlb_v3_lineup_model/v3_lineup_foundation_dataset.parquet")

# Join on game_pk
df = ft.merge(lineup[["game_pk",
                       "home_lineup_k_rate_last20", "away_lineup_k_rate_last20",
                       "home_lineup_contact_rate_last20", "away_lineup_contact_rate_last20",
                       "home_lineup_size", "away_lineup_size"]],
              on="game_pk", how="left")

print(f"Feature table: {len(ft)} rows")
print(f"After lineup join: {len(df)} rows")
print(f"Lineup K rate coverage: {df['home_lineup_k_rate_last20'].notna().mean()*100:.1f}%")

# UNDER outcome: actual_total < closing_total (from market snapshots)
# Need closing lines — join from market_snapshots or bet_results
ms = pd.read_parquet("sim/data/market_snapshots.parquet")
ms["game_pk"] = ms["game_id"].astype(int)
cl_hist = pd.read_parquet("sim/data/mlb_historical_closing_lines.parquet")

# Combine closing lines
lines = pd.concat([
    cl_hist[["game_pk", "close_total"]],
    ms[["game_pk", "close_total"]],
], ignore_index=True).drop_duplicates("game_pk", keep="last")

df = df.merge(lines, on="game_pk", how="left")
df = df[df["close_total"].notna() & df["actual_total"].notna()].copy()

# Exclude pushes (match production convention)
df["went_under"] = (df["actual_total"] < df["close_total"]).astype(int)
df["is_push"] = (df["actual_total"] == df["close_total"]).astype(int)
df = df[df["is_push"] == 0].copy()

print(f"Games with lines (no pushes): {len(df)}")
for s in sorted(df["season"].unique()):
    print(f"  {s}: {len(df[df['season'] == s])}")
print(f"Baseline under rate: {df['went_under'].mean():.4f}")

# ======================================================================
# V1 BASELINE FEATURE SET
# ======================================================================
# Phase 9 baseline features (25 features from the production model)
# Extract from feature_table — these are the columns used by the Ridge model
V1_FEATURES = [
    "home_sp_xfip", "home_sp_k_pct", "home_sp_bb_pct", "home_sp_avg_ip",
    "away_sp_xfip", "away_sp_k_pct", "away_sp_bb_pct", "away_sp_avg_ip",
    "home_wrc_plus", "away_wrc_plus",
    "park_factor_runs",
    "temperature", "wind_speed", "wind_factor_effective",
    "umpire_over_rate",
    "home_rest_days", "away_rest_days",
    "doubleheader_flag",
    "home_bp_xfip", "home_bp_proj_inn", "home_bp_interaction",
    "away_bp_xfip", "away_bp_proj_inn", "away_bp_interaction",
]

# Check which V1 features are available
available_v1 = [f for f in V1_FEATURES if f in df.columns]
missing_v1 = [f for f in V1_FEATURES if f not in df.columns]
print(f"\nV1 features available: {len(available_v1)}/{len(V1_FEATURES)}")
if missing_v1:
    print(f"  Missing: {missing_v1}")

# ======================================================================
# HELPER: train Ridge, evaluate
# ======================================================================
RIDGE_ALPHA = 50  # Match Phase 9 baseline

def train_and_eval(train_df, val_df, features, label="model"):
    """Train Ridge on train_df, evaluate on val_df. Returns metrics dict."""
    # Drop rows with any NaN in features
    train_clean = train_df.dropna(subset=features + ["went_under"])
    val_clean = val_df.dropna(subset=features + ["went_under"])

    if len(train_clean) < 100 or len(val_clean) < 50:
        return {"N_train": len(train_clean), "N_val": len(val_clean),
                "AUC": None, "Brier": None, "UR_57": None, "UR_60": None,
                "coverage": len(val_clean) / len(val_df) if len(val_df) > 0 else 0}

    X_train = train_clean[features].values.astype(float)
    y_train = train_clean["went_under"].values
    X_val = val_clean[features].values.astype(float)
    y_val = val_clean["went_under"].values

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)

    model = Ridge(alpha=RIDGE_ALPHA)
    model.fit(X_train_s, y_train)

    pred = model.predict(X_val_s)
    # Clip to valid probability range
    pred_clipped = np.clip(pred, 0.01, 0.99)

    auc = roc_auc_score(y_val, pred_clipped)
    brier = brier_score_loss(y_val, pred_clipped)

    # Under rate at thresholds
    ur_57 = y_val[pred_clipped > 0.57].mean() if (pred_clipped > 0.57).sum() > 0 else None
    ur_60 = y_val[pred_clipped > 0.60].mean() if (pred_clipped > 0.60).sum() > 0 else None
    n_57 = int((pred_clipped > 0.57).sum())
    n_60 = int((pred_clipped > 0.60).sum())

    coverage = len(val_clean) / len(val_df) if len(val_df) > 0 else 0

    return {
        "N_train": len(train_clean), "N_val": len(val_clean),
        "AUC": round(auc, 5), "Brier": round(brier, 5),
        "UR_57": round(ur_57, 4) if ur_57 is not None else None,
        "UR_60": round(ur_60, 4) if ur_60 is not None else None,
        "N_57": n_57, "N_60": n_60,
        "coverage": round(coverage, 4),
        "coefs": dict(zip(features, model.coef_.tolist())),
    }


# ======================================================================
# BASELINE: V1 features, train 2022-2024, validate 2025
# ======================================================================
print("\n" + "=" * 70)
print("BASELINE MODEL (V1 features)")
print("=" * 70)

train_2224 = df[df["season"].isin([2022, 2023, 2024])]
val_2025 = df[df["season"] == 2025]

baseline = train_and_eval(train_2224, val_2025, available_v1, "baseline")
print(f"  Train: {baseline['N_train']}, Val: {baseline['N_val']}")
print(f"  AUC: {baseline['AUC']}")
print(f"  Brier: {baseline['Brier']}")
print(f"  UR@0.57: {baseline['UR_57']} (N={baseline['N_57']})")
print(f"  UR@0.60: {baseline['UR_60']} (N={baseline['N_60']})")
print(f"  Coverage: {baseline['coverage']*100:.1f}%")

# ======================================================================
# LT01: Replace team K-rate proxy with lineup K-rate
# ======================================================================
print("\n" + "=" * 70)
print("LT01: LINEUP K-RATE REPLACEMENT")
print("=" * 70)

# V1 doesn't have an explicit "team_k_rate" — the closest proxy is wRC+
# which captures offensive quality broadly. The lineup K-rate is more specific.
# For LT01: ADD lineup K-rate features alongside existing V1 features
# (since V1 doesn't have a direct K-rate to replace, we add the lineup version)
# This is conservative — adding rather than replacing avoids breaking existing signal.

lt01_features = available_v1 + ["home_lineup_k_rate_last20", "away_lineup_k_rate_last20"]

# Check lineup coverage in val
val_lineup_coverage = val_2025["home_lineup_k_rate_last20"].notna().mean()
print(f"  Lineup K-rate coverage (2025 val): {val_lineup_coverage*100:.1f}%")

lt01_main = train_and_eval(train_2224, val_2025, lt01_features, "lt01")
print(f"  Train: {lt01_main['N_train']}, Val: {lt01_main['N_val']}")
print(f"  AUC: {lt01_main['AUC']}")
print(f"  Brier: {lt01_main['Brier']}")
print(f"  UR@0.57: {lt01_main['UR_57']} (N={lt01_main['N_57']})")
print(f"  UR@0.60: {lt01_main['UR_60']} (N={lt01_main['N_60']})")
print(f"  Coverage: {lt01_main['coverage']*100:.1f}%")

# Deltas
d_auc_lt01 = round(lt01_main["AUC"] - baseline["AUC"], 5) if lt01_main["AUC"] and baseline["AUC"] else None
d_brier_lt01 = round(lt01_main["Brier"] - baseline["Brier"], 5) if lt01_main["Brier"] and baseline["Brier"] else None
d_ur57_lt01 = round(lt01_main["UR_57"] - baseline["UR_57"], 4) if lt01_main["UR_57"] and baseline["UR_57"] else None
d_ur60_lt01 = round(lt01_main["UR_60"] - baseline["UR_60"], 4) if lt01_main["UR_60"] and baseline["UR_60"] else None

print(f"\n  delta_AUC: {d_auc_lt01}")
print(f"  delta_Brier: {d_brier_lt01}")
print(f"  delta_UR_57: {d_ur57_lt01}")
print(f"  delta_UR_60: {d_ur60_lt01}")

# Coefficient signs
if lt01_main.get("coefs"):
    hk = lt01_main["coefs"].get("home_lineup_k_rate_last20", 0)
    ak = lt01_main["coefs"].get("away_lineup_k_rate_last20", 0)
    print(f"  Coef home_lineup_k_rate: {hk:.4f} (expect negative = higher K = fewer runs)")
    print(f"  Coef away_lineup_k_rate: {ak:.4f} (expect negative)")

# ======================================================================
# LT02: CONTACT × WHIFF INTERACTION
# ======================================================================
print("\n" + "=" * 70)
print("LT02: CONTACT × WHIFF INTERACTION")
print("=" * 70)

# Compute interaction: sp_k_pct * opposing lineup_contact_rate
# For home pitcher vs away lineup: home_sp_k_pct * away_lineup_contact_rate
# For away pitcher vs home lineup: away_sp_k_pct * home_lineup_contact_rate
df["home_sp_kpct_x_away_contact"] = df["home_sp_k_pct"] * df["away_lineup_contact_rate_last20"]
df["away_sp_kpct_x_home_contact"] = df["away_sp_k_pct"] * df["home_lineup_contact_rate_last20"]

lt02_features = available_v1 + ["home_sp_kpct_x_away_contact", "away_sp_kpct_x_home_contact"]

# Rebuild train/val with interaction features
train_2224 = df[df["season"].isin([2022, 2023, 2024])]
val_2025 = df[df["season"] == 2025]

lt02_contact_cov = val_2025["home_sp_kpct_x_away_contact"].notna().mean()
print(f"  Interaction coverage (2025 val): {lt02_contact_cov*100:.1f}%")

lt02_main = train_and_eval(train_2224, val_2025, lt02_features, "lt02")
print(f"  Train: {lt02_main['N_train']}, Val: {lt02_main['N_val']}")
print(f"  AUC: {lt02_main['AUC']}")
print(f"  Brier: {lt02_main['Brier']}")
print(f"  UR@0.57: {lt02_main['UR_57']} (N={lt02_main['N_57']})")
print(f"  UR@0.60: {lt02_main['UR_60']} (N={lt02_main['N_60']})")
print(f"  Coverage: {lt02_main['coverage']*100:.1f}%")

d_auc_lt02 = round(lt02_main["AUC"] - baseline["AUC"], 5) if lt02_main["AUC"] and baseline["AUC"] else None
d_brier_lt02 = round(lt02_main["Brier"] - baseline["Brier"], 5) if lt02_main["Brier"] and baseline["Brier"] else None
d_ur57_lt02 = round(lt02_main["UR_57"] - baseline["UR_57"], 4) if lt02_main["UR_57"] and baseline["UR_57"] else None
d_ur60_lt02 = round(lt02_main["UR_60"] - baseline["UR_60"], 4) if lt02_main["UR_60"] and baseline["UR_60"] else None

print(f"\n  delta_AUC: {d_auc_lt02}")
print(f"  delta_Brier: {d_brier_lt02}")
print(f"  delta_UR_57: {d_ur57_lt02}")
print(f"  delta_UR_60: {d_ur60_lt02}")

# Coefficient direction check
if lt02_main.get("coefs"):
    hc = lt02_main["coefs"].get("home_sp_kpct_x_away_contact", 0)
    ac = lt02_main["coefs"].get("away_sp_kpct_x_home_contact", 0)
    # Higher sp_k_pct * lower contact = more suppression = lower total
    # The interaction of high_whiff * low_contact should predict UNDER
    # Since target is went_under (1=under), coefficient should be POSITIVE
    # (higher interaction → more likely under)
    # BUT: contact_rate is the complement — high contact = less suppression
    # So sp_k_pct * contact_rate: high K pitcher vs high contact lineup = mixed
    # Actually: the interaction is sp_k_pct * lineup_contact_rate
    # If pitcher has high K% and lineup has LOW contact → total suppressed
    # sp_k_pct high × contact low → product is LOW → predicts UNDER
    # So coefficient should be NEGATIVE (lower product → higher p_under)
    print(f"  Coef home_sp_kpct_x_away_contact: {hc:.4f} (expect negative)")
    print(f"  Coef away_sp_kpct_x_home_contact: {ac:.4f} (expect negative)")
    lt02_coef_correct = (hc < 0) or (ac < 0)
    print(f"  Direction correct: {lt02_coef_correct}")

# ======================================================================
# YEAR STABILITY CHECK
# ======================================================================
print("\n" + "=" * 70)
print("YEAR STABILITY CHECK")
print("=" * 70)

stability_configs = [
    ("2022→2023", [2022], 2023),
    ("2022-23→2024", [2022, 2023], 2024),
    ("2022-24→2025", [2022, 2023, 2024], 2025),
]

lt01_stability = []
lt02_stability = []

for label, train_years, val_year in stability_configs:
    tr = df[df["season"].isin(train_years)]
    vl = df[df["season"] == val_year]

    b = train_and_eval(tr, vl, available_v1, f"base_{label}")
    a1 = train_and_eval(tr, vl, lt01_features, f"lt01_{label}")
    a2 = train_and_eval(tr, vl, lt02_features, f"lt02_{label}")

    d1_auc = round(a1["AUC"] - b["AUC"], 5) if a1["AUC"] and b["AUC"] else None
    d1_ur57 = round(a1["UR_57"] - b["UR_57"], 4) if a1["UR_57"] and b["UR_57"] else None
    d2_auc = round(a2["AUC"] - b["AUC"], 5) if a2["AUC"] and b["AUC"] else None
    d2_ur57 = round(a2["UR_57"] - b["UR_57"], 4) if a2["UR_57"] and b["UR_57"] else None

    lt01_stability.append({"window": label, "d_AUC": d1_auc, "d_UR_57": d1_ur57,
                            "base_AUC": b["AUC"], "aug_AUC": a1["AUC"],
                            "base_UR57": b["UR_57"], "aug_UR57": a1["UR_57"]})
    lt02_stability.append({"window": label, "d_AUC": d2_auc, "d_UR_57": d2_ur57,
                            "base_AUC": b["AUC"], "aug_AUC": a2["AUC"],
                            "base_UR57": b["UR_57"], "aug_UR57": a2["UR_57"]})

    print(f"\n  {label}:")
    print(f"    Baseline: AUC={b['AUC']}, UR@57={b['UR_57']}")
    print(f"    LT01:     AUC={a1['AUC']} (d={d1_auc}), UR@57={a1['UR_57']} (d={d1_ur57})")
    print(f"    LT02:     AUC={a2['AUC']} (d={d2_auc}), UR@57={a2['UR_57']} (d={d2_ur57})")

# Count positive improvements
lt01_pos_auc = sum(1 for s in lt01_stability if s["d_AUC"] is not None and s["d_AUC"] > 0)
lt01_pos_ur = sum(1 for s in lt01_stability if s["d_UR_57"] is not None and s["d_UR_57"] > 0)
lt02_pos_auc = sum(1 for s in lt02_stability if s["d_AUC"] is not None and s["d_AUC"] > 0)
lt02_pos_ur = sum(1 for s in lt02_stability if s["d_UR_57"] is not None and s["d_UR_57"] > 0)

lt01_year_stable = lt01_pos_auc >= 2 or lt01_pos_ur >= 2
lt02_year_stable = lt02_pos_auc >= 2 or lt02_pos_ur >= 2

print(f"\n  LT01 year stability: {lt01_pos_auc}/3 AUC positive, {lt01_pos_ur}/3 UR positive → {'PASS' if lt01_year_stable else 'FAIL'}")
print(f"  LT02 year stability: {lt02_pos_auc}/3 AUC positive, {lt02_pos_ur}/3 UR positive → {'PASS' if lt02_year_stable else 'FAIL'}")

# ======================================================================
# PASS GATES
# ======================================================================
print("\n" + "=" * 70)
print("PASS GATES")
print("=" * 70)

def check_gates(name, coverage, d_auc, d_ur57, year_stable, coef_correct=None):
    gates = {}
    gates["coverage_70"] = coverage >= 0.70
    gates["d_auc_positive"] = d_auc is not None and d_auc > 0
    gates["d_ur57_positive"] = d_ur57 is not None and d_ur57 > 0
    gates["year_stable"] = year_stable
    if coef_correct is not None:
        gates["coef_direction"] = coef_correct

    all_pass = all(gates.values())
    verdict = "INTEGRATE" if all_pass else "SHELVE"

    print(f"\n  {name}:")
    for g, v in gates.items():
        print(f"    {g}: {'PASS' if v else 'FAIL'}")
    print(f"    VERDICT: {verdict}")
    return verdict, gates

lt01_verdict, lt01_gates = check_gates(
    "LT01", lt01_main["coverage"], d_auc_lt01, d_ur57_lt01, lt01_year_stable)

lt02_coef_ok = lt02_main.get("coefs", {}).get("home_sp_kpct_x_away_contact", 0) < 0 or \
               lt02_main.get("coefs", {}).get("away_sp_kpct_x_home_contact", 0) < 0
lt02_verdict, lt02_gates = check_gates(
    "LT02", lt02_main["coverage"], d_auc_lt02, d_ur57_lt02, lt02_year_stable, lt02_coef_ok)

# ======================================================================
# SAVE RESULTS
# ======================================================================
lt01_output = {
    "signal_id": "LT01",
    "name": "lineup_adjusted_k_rate_feature_upgrade",
    "lineup_source": "reconstructed_actual_lineups",
    "baseline": {k: v for k, v in baseline.items() if k != "coefs"},
    "augmented": {k: v for k, v in lt01_main.items() if k != "coefs"},
    "deltas": {"AUC": d_auc_lt01, "Brier": d_brier_lt01, "UR_57": d_ur57_lt01, "UR_60": d_ur60_lt01},
    "year_stability": lt01_stability,
    "year_stable": lt01_year_stable,
    "gates": {k: bool(v) for k, v in lt01_gates.items()},
    "verdict": lt01_verdict,
    "features_added": ["home_lineup_k_rate_last20", "away_lineup_k_rate_last20"],
    "coefs": {k: round(v, 6) for k, v in (lt01_main.get("coefs") or {}).items()
              if "lineup_k_rate" in k},
}

lt02_output = {
    "signal_id": "LT02",
    "name": "lineup_contact_x_pitcher_whiff_interaction",
    "lineup_source": "reconstructed_actual_lineups",
    "baseline": {k: v for k, v in baseline.items() if k != "coefs"},
    "augmented": {k: v for k, v in lt02_main.items() if k != "coefs"},
    "deltas": {"AUC": d_auc_lt02, "Brier": d_brier_lt02, "UR_57": d_ur57_lt02, "UR_60": d_ur60_lt02},
    "year_stability": lt02_stability,
    "year_stable": lt02_year_stable,
    "gates": {k: bool(v) for k, v in lt02_gates.items()},
    "verdict": lt02_verdict,
    "features_added": ["home_sp_kpct_x_away_contact", "away_sp_kpct_x_home_contact"],
    "coefs": {k: round(v, 6) for k, v in (lt02_main.get("coefs") or {}).items()
              if "kpct_x" in k},
    "coef_direction_correct": lt02_coef_ok,
}

with open(OUT / "lt01_results.json", "w") as f:
    json.dump(lt01_output, f, indent=2, default=str)
with open(OUT / "lt02_results.json", "w") as f:
    json.dump(lt02_output, f, indent=2, default=str)

# Summary markdown
summary = f"""# Phase 3 Lite — LT01 & LT02 Results

**Date:** 2026-03-29
**Lineup source:** reconstructed_actual_lineups (actual boxscore starters, not projected)

## Summary Table

| Feature | Coverage | delta_AUC | delta_Brier | delta_UR_57 | delta_UR_60 | Year Stable | Verdict |
|---------|----------|-----------|-------------|-------------|-------------|-------------|---------|
| LT01 (lineup K-rate) | {lt01_main['coverage']*100:.1f}% | {d_auc_lt01 if d_auc_lt01 is not None else 'N/A':+.5f} | {d_brier_lt01 if d_brier_lt01 is not None else 'N/A':+.5f} | {d_ur57_lt01 if d_ur57_lt01 is not None else 'N/A':+.4f} | {d_ur60_lt01 if d_ur60_lt01 is not None else 'N/A':+.4f} | {'Yes' if lt01_year_stable else 'No'} | **{lt01_verdict}** |
| LT02 (contact x whiff) | {lt02_main['coverage']*100:.1f}% | {d_auc_lt02 if d_auc_lt02 is not None else 'N/A':+.5f} | {d_brier_lt02 if d_brier_lt02 is not None else 'N/A':+.5f} | {d_ur57_lt02 if d_ur57_lt02 is not None else 'N/A':+.4f} | {d_ur60_lt02 if d_ur60_lt02 is not None else 'N/A':+.4f} | {'Yes' if lt02_year_stable else 'No'} | **{lt02_verdict}** |

## Baseline (V1 Ridge, train 2022-24, validate 2025)
- AUC: {baseline['AUC']}
- Brier: {baseline['Brier']}
- UR@0.57: {baseline['UR_57']} (N={baseline['N_57']})
- UR@0.60: {baseline['UR_60']} (N={baseline['N_60']})

## Year Stability

### LT01
| Window | Base AUC | Aug AUC | delta_AUC | Base UR57 | Aug UR57 | delta_UR57 |
|--------|----------|---------|-----------|-----------|----------|------------|
"""
for s in lt01_stability:
    summary += f"| {s['window']} | {s['base_AUC']} | {s['aug_AUC']} | {s['d_AUC']} | {s['base_UR57']} | {s['aug_UR57']} | {s['d_UR_57']} |\n"

summary += f"""
### LT02
| Window | Base AUC | Aug AUC | delta_AUC | Base UR57 | Aug UR57 | delta_UR57 |
|--------|----------|---------|-----------|-----------|----------|------------|
"""
for s in lt02_stability:
    summary += f"| {s['window']} | {s['base_AUC']} | {s['aug_AUC']} | {s['d_AUC']} | {s['base_UR57']} | {s['aug_UR57']} | {s['d_UR_57']} |\n"

summary += f"""
## Pass Gates

### LT01
"""
for g, v in lt01_gates.items():
    summary += f"- {g}: {'PASS' if v else 'FAIL'}\n"
summary += f"- **VERDICT: {lt01_verdict}**\n"

summary += f"""
### LT02
"""
for g, v in lt02_gates.items():
    summary += f"- {g}: {'PASS' if v else 'FAIL'}\n"
summary += f"- **VERDICT: {lt02_verdict}**\n"

with open(OUT / "summary.md", "w") as f:
    f.write(summary)

# ======================================================================
# FINAL SUMMARY
# ======================================================================
print(f"\n{'='*100}")
print("FINAL SUMMARY TABLE")
print(f"{'='*100}")
print(f"{'feature':<25} {'coverage':>10} {'d_AUC':>10} {'d_Brier':>10} {'d_UR_57':>10} {'d_UR_60':>10} {'yr_stable':>10} {'verdict':>10}")
print("-" * 100)
print(f"{'LT01 (lineup K-rate)':<25} {lt01_main['coverage']*100:>9.1f}% {d_auc_lt01:>+10.5f} {d_brier_lt01:>+10.5f} {d_ur57_lt01 if d_ur57_lt01 is not None else 'N/A':>10} {d_ur60_lt01 if d_ur60_lt01 is not None else 'N/A':>10} {'Yes' if lt01_year_stable else 'No':>10} {lt01_verdict:>10}")
print(f"{'LT02 (contact x whiff)':<25} {lt02_main['coverage']*100:>9.1f}% {d_auc_lt02:>+10.5f} {d_brier_lt02:>+10.5f} {d_ur57_lt02 if d_ur57_lt02 is not None else 'N/A':>10} {d_ur60_lt02 if d_ur60_lt02 is not None else 'N/A':>10} {'Yes' if lt02_year_stable else 'No':>10} {lt02_verdict:>10}")

print(f"\n{'='*100}")
print("OUTPUT FILES:")
print(f"  research/mlb_v3_lineup_model/phase3_lite/hypothesis_registry.json")
print(f"  research/mlb_v3_lineup_model/phase3_lite/lt01_results.json")
print(f"  research/mlb_v3_lineup_model/phase3_lite/lt02_results.json")
print(f"  research/mlb_v3_lineup_model/phase3_lite/summary.md")
print(f"  research/mlb_v3_lineup_model/phase3_lite/run_phase3_lite.py")
print(f"{'='*100}")
