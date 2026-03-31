#!/usr/bin/env python3
"""
Statcast Interaction Family Scanner — Five Families.
Tests extension×command, contact×GB, spin×contact, OAA, tempo.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent.parent / "sim" / "data"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# ── Load base data ────────────────────────────────────────────────────
sc = pd.read_parquet(BASE.parent.parent / "statcast_enrichment" /
                     "pitcher_statcast_per_start_starters_only.parquet")
sc["game_date"] = pd.to_datetime(sc["game_date"])

ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])

br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])

sim_v1 = pd.read_parquet(SIM / "phase5_sim_results.parquet")
sim_v1["date"] = pd.to_datetime(sim_v1["date"])

bu = pd.read_parquet(SIM / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])
starters_bu = bu[bu["is_starter"]][["game_pk", "pitcher_id", "team"]].copy()

gt = pd.read_parquet(SIM / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])

# ── Build rolling 5-start features per pitcher ────────────────────────
print("Building pitcher rolling features...")
sc_s = sc.sort_values(["pitcher_id", "game_date"])
for col in ["extension", "hard_hit_rate", "barrel_rate", "whiff_rate",
            "zone_rate", "zone_contact_rate", "chase_rate",
            "spin_rate_ff", "avg_launch_angle"]:
    sc_s[f"{col}_r5"] = sc_s.groupby("pitcher_id")[col].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# Season baseline spin (for spin loss)
sc_s["spin_ff_season"] = sc_s.groupby(["pitcher_id", sc_s.game_date.dt.year])["spin_rate_ff"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).mean())
sc_s["spin_loss"] = (sc_s["spin_ff_season"] - sc_s["spin_rate_ff_r5"]).clip(lower=0)

# CSW proxy = zone_rate * (1 - zone_contact_rate) + whiff_rate (simplified)
sc_s["csw_proxy_r5"] = sc_s["zone_rate_r5"] * (1 - sc_s["zone_contact_rate_r5"]) + sc_s["whiff_rate_r5"]

# ── Build pitcher HH/extension lookup per game ───────────────────────
# Match each game_pk to home/away pitcher stats
sc_game = sc_s.merge(starters_bu, on=["game_pk", "pitcher_id"], how="left")
sc_game = sc_game.merge(gt[["game_pk", "home_team", "away_team"]], on="game_pk", how="left")
sc_game["side"] = np.where(sc_game["team"] == sc_game["home_team"], "home", "away")

# ── Build game-level eval dataset ─────────────────────────────────────
print("Building game-level dataset...")
df = ft[ft["season"].isin([2024, 2025])].copy()
df = df.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
              on="game_pk", how="inner")
df.rename(columns={"close_total": "closing_total"}, inplace=True)
df = df.merge(sim_v1[["game_pk", "p_under"]], on="game_pk", how="left")

df["is_push"] = (df["actual_total"] == df["closing_total"])
df["went_under"] = (df["actual_total"] < df["closing_total"]).astype(int)
df["market_residual_under"] = df["went_under"] - 0.50
df["v1_under"] = (df["p_under"] > 0.57).astype(int)

# Join pitcher rolling features
roll_cols = [c for c in sc_s.columns if c.endswith("_r5") or c == "spin_loss" or c == "csw_proxy_r5"]
for side in ["home", "away"]:
    side_data = sc_game[sc_game["side"] == side][["game_pk"] + roll_cols].copy()
    side_data.columns = ["game_pk"] + [f"{side}_sp_{c}" for c in roll_cols]
    df = df.merge(side_data, on="game_pk", how="left")

# Combined features
for col in roll_cols:
    h_col = f"home_sp_{col}"
    a_col = f"away_sp_{col}"
    if h_col in df.columns and a_col in df.columns:
        df[f"combined_{col}"] = (df[h_col] + df[a_col]) / 2

# Lineup contact from V2 offense
v2_off = pd.read_parquet(BASE.parent.parent / "opponent_adjusted_engine_v2" / "offense_expectation_table.parquet")
v2_off["date"] = pd.to_datetime(v2_off["date"])
for side, prefix in [("home", "home"), ("away", "away")]:
    ct = v2_off[v2_off["side"] == side][["game_pk", "team_contact_rate"]].rename(
        columns={"team_contact_rate": f"{prefix}_lineup_contact"})
    df = df.merge(ct, on="game_pk", how="left")
df["combined_lineup_contact"] = (df["home_lineup_contact"] + df["away_lineup_contact"]) / 2

df_np = df[~df["is_push"]].copy()
print(f"Dataset: {len(df)} games, {len(df_np)} non-push")

# =====================================================================
# FAMILY TESTING FRAMEWORK
# =====================================================================

def test_family(name, signal_col, direction, df_full, df_nonpush):
    """Run full gate sequence on a signal. Returns results dict."""
    valid = df_full[signal_col].notna()
    valid_np = df_nonpush[signal_col].notna()
    sub = df_nonpush[valid_np].copy()
    sub_all = df_full[valid].copy()

    n_total = len(sub)
    if n_total < 500:
        return {"name": name, "verdict": "INSUFFICIENT_DATA", "n": n_total}

    result = {"name": name, "signal": signal_col, "direction": direction, "n": n_total}

    # Gate 1: Season stability
    yr_coefs = {}
    for yr in [2024, 2025]:
        yr_df = sub_all[sub_all["season"] == yr]
        v = yr_df[signal_col].dropna()
        if len(v) < 200: continue
        X = sm.add_constant(yr_df.loc[v.index, signal_col])
        y = yr_df.loc[v.index, "market_residual_under"]
        m = sm.OLS(y, X).fit()
        yr_coefs[yr] = m.params[signal_col]

    if len(yr_coefs) < 2:
        result["gate1"] = "FAIL_INSUF"
        result["verdict"] = "SHELVE"
        return result

    if direction == "UNDER":
        stable = yr_coefs[2024] > 0 and yr_coefs[2025] > 0
    else:
        stable = yr_coefs[2024] < 0 and yr_coefs[2025] < 0

    result["gate1"] = "PASS" if stable else "FAIL"
    result["coef_2024"] = yr_coefs[2024]
    result["coef_2025"] = yr_coefs[2025]

    if not stable:
        result["verdict"] = "SHELVE"
        return result

    # Gate 2: Robustness
    controls = [signal_col, "closing_total", "home_sp_xfip", "away_sp_xfip",
                "park_factor_runs", "temperature"]
    ctrl_df = sub_all.dropna(subset=[c for c in controls if c in sub_all.columns] + ["market_residual_under"])
    ctrl_cols = [c for c in controls if c in ctrl_df.columns]
    X = sm.add_constant(ctrl_df[ctrl_cols])
    y = ctrl_df["market_residual_under"]
    m = sm.OLS(y, X).fit()
    result["robust_p"] = m.pvalues[signal_col]
    result["gate2"] = "PASS" if m.pvalues[signal_col] < 0.10 else "FAIL"

    if result["gate2"] == "FAIL":
        result["verdict"] = "SHELVE"
        return result

    # Gate 2.5: Availability bias
    v1_all = df_nonpush[df_nonpush["v1_under"] == 1]
    avail = v1_all[signal_col].notna()
    if avail.sum() > 50 and (~avail).sum() > 20:
        bias = abs(v1_all.loc[avail, "went_under"].mean() - v1_all.loc[~avail, "went_under"].mean())
        result["avail_bias"] = bias
    else:
        result["avail_bias"] = 0.0

    # Gate 3: Walk-forward
    WARMUP = 50
    wf_results = {}
    for yr in [2024, 2025]:
        yr_np = sub[sub["season"] == yr]
        if len(yr_np) < 100: continue
        # Expanding threshold
        yr_sorted = yr_np.sort_values("date" if "date" in yr_np.columns else "game_date")
        thresholds = []
        for i in range(len(yr_sorted)):
            if i < WARMUP:
                thresholds.append(np.nan)
            else:
                prior = yr_sorted.iloc[:i]
                if direction == "UNDER":
                    thresholds.append(prior[signal_col].quantile(0.80))
                else:
                    thresholds.append(prior[signal_col].quantile(0.20))
        yr_sorted["wf_thresh"] = thresholds

        if direction == "UNDER":
            flagged = yr_sorted[signal_col] >= yr_sorted["wf_thresh"]
        else:
            flagged = yr_sorted[signal_col] <= yr_sorted["wf_thresh"]

        flagged = flagged & yr_sorted["wf_thresh"].notna()
        n_f = flagged.sum()
        if n_f < 20:
            wf_results[yr] = np.nan
            continue
        ur = yr_sorted.loc[flagged, "went_under"].mean()
        w = yr_sorted.loc[flagged, "went_under"].sum()
        wf_results[yr] = roi_110(w, n_f - w) if direction == "UNDER" else roi_110(n_f - w, w)

    result["wf_2024"] = wf_results.get(2024, np.nan)
    result["wf_2025"] = wf_results.get(2025, np.nan)

    both_positive = (not np.isnan(result["wf_2024"]) and result["wf_2024"] > 0 and
                     not np.isnan(result["wf_2025"]) and result["wf_2025"] > 0)
    result["gate3"] = "PASS" if both_positive else "FAIL"

    if not both_positive:
        result["verdict"] = "SHELVE"
        return result

    # Gate 4: Permutation (2025)
    yr_np = sub[sub["season"] == 2025]
    if direction == "UNDER":
        p80 = yr_np[signal_col].quantile(0.80)
        flagged = yr_np[signal_col] >= p80
    else:
        p20 = yr_np[signal_col].quantile(0.20)
        flagged = yr_np[signal_col] <= p20
    n_f = flagged.sum()
    if n_f >= 20:
        obs_w = yr_np.loc[flagged, "went_under"].sum()
        obs_roi = roi_110(obs_w, n_f - obs_w) if direction == "UNDER" else roi_110(n_f - obs_w, obs_w)
        outcomes = yr_np["went_under"].values.copy()
        perm_rois = []
        for _ in range(200):
            np.random.shuffle(outcomes)
            w = outcomes[:n_f].sum()
            perm_rois.append(roi_110(w, n_f - w) if direction == "UNDER" else roi_110(n_f - w, w))
        pctile = (np.array(perm_rois) <= obs_roi).mean() * 100
        result["perm_pctile"] = pctile
        result["gate4"] = "PASS" if pctile >= 85 else "FAIL"
    else:
        result["perm_pctile"] = np.nan
        result["gate4"] = "FAIL_INSUF"

    # Gate 5: Market independence
    corr_valid = valid & df_full["closing_total"].notna()
    r_corr, _ = stats.pearsonr(df_full.loc[corr_valid, signal_col],
                                df_full.loc[corr_valid, "closing_total"])
    result["market_corr"] = r_corr
    result["gate5"] = "PASS" if abs(r_corr) < 0.30 else "FAIL"

    # Gate 6: V1 amplification
    v1_sub = sub[sub["v1_under"] == 1]
    v1_base_ur = v1_sub["went_under"].mean() if len(v1_sub) > 50 else np.nan
    if direction == "UNDER":
        p80_v1 = v1_sub[signal_col].quantile(0.80)
        v1_flagged = v1_sub[signal_col] >= p80_v1
    else:
        p20_v1 = v1_sub[signal_col].quantile(0.20)
        v1_flagged = v1_sub[signal_col] <= p20_v1
    v1_amp_ur = v1_sub.loc[v1_flagged, "went_under"].mean() if v1_flagged.sum() > 20 else np.nan
    result["v1_base_ur"] = v1_base_ur
    result["v1_amp_ur"] = v1_amp_ur
    result["v1_lift"] = (v1_amp_ur - v1_base_ur) if not np.isnan(v1_amp_ur) and not np.isnan(v1_base_ur) else np.nan
    result["gate6"] = "PASS" if not np.isnan(result["v1_lift"]) and result["v1_lift"] > 0 else "FAIL"

    # Tail ROI by year
    for yr in [2024, 2025]:
        yr_np = sub[sub["season"] == yr]
        if direction == "UNDER":
            p80 = yr_np[signal_col].quantile(0.80)
            mask = yr_np[signal_col] >= p80
        else:
            p20 = yr_np[signal_col].quantile(0.20)
            mask = yr_np[signal_col] <= p20
        n = mask.sum()
        if n >= 20:
            w = yr_np.loc[mask, "went_under"].sum()
            result[f"tail_roi_{yr}"] = roi_110(w, n - w) if direction == "UNDER" else roi_110(n - w, w)
            result[f"tail_n_{yr}"] = n
            result[f"tail_ur_{yr}"] = yr_np.loc[mask, "went_under"].mean()

    # Final verdict
    gates = [result.get(f"gate{g}") for g in [1, 2, 3, 4, 5, 6]]
    passes = sum(1 for g in gates if g == "PASS")
    if passes == 6:
        result["verdict"] = "SHADOW"
    elif passes >= 4:
        result["verdict"] = "INVESTIGATE"
    else:
        result["verdict"] = "SHELVE"

    return result


# =====================================================================
# RUN ALL FAMILIES
# =====================================================================

all_results = []

# Build all interaction columns BEFORE creating df_np
# FAMILY 1
df["F1_extension_x_csw"] = df["combined_extension_r5"] * df["combined_csw_proxy_r5"]
# FAMILY 2
df["combined_gb_proxy_r5"] = -1 * df["combined_avg_launch_angle_r5"]
df["F2_suppression"] = (1 - df["combined_hard_hit_rate_r5"]) * df["combined_gb_proxy_r5"]
# FAMILY 3
df["combined_spin_loss"] = (df["home_sp_spin_loss"] + df["away_sp_spin_loss"]) / 2
df["F3_spinloss_x_contact"] = df["combined_spin_loss"] * df["combined_lineup_contact"]
df["actual_result_over"] = (df["actual_total"] > df["closing_total"]).astype(int)
df["market_residual_over"] = df["actual_result_over"] - 0.50

# Recreate df_np with all columns
df_np = df[~df["is_push"]].copy()

# FAMILY 1: Extension × Command
print("\n=== FAMILY 1: Extension × Command ===")
r1a = test_family("F1a: extension standalone", "combined_extension_r5", "UNDER", df, df_np)
r1b = test_family("F1b: extension × CSW", "F1_extension_x_csw", "UNDER", df, df_np)
all_results.extend([r1a, r1b])
for r in [r1a, r1b]:
    print(f"  {r['name']}: G1={r.get('gate1','?')} G2={r.get('gate2','?')} G3={r.get('gate3','?')} → {r['verdict']}")

# FAMILY 2: Contact Suppression × Low Launch Angle (GB proxy)
print("\n=== FAMILY 2: Contact × Groundball (launch angle proxy) ===")
r2 = test_family("F2: (1-HH) × GB_proxy", "F2_suppression", "UNDER", df, df_np)
all_results.append(r2)
print(f"  {r2['name']}: G1={r2.get('gate1','?')} G2={r2.get('gate2','?')} G3={r2.get('gate3','?')} → {r2['verdict']}")

# FAMILY 3: Spin Loss × Lineup Contact
print("\n=== FAMILY 3: Spin Loss × Lineup Contact ===")
r3 = test_family("F3: spin_loss × contact (UNDER tail check)", "F3_spinloss_x_contact", "UNDER", df, df_np)
# Also check OVER tail manually
v = df_np["F3_spinloss_x_contact"].dropna()
if len(v) > 200:
    p80 = v.quantile(0.80)
    mask = df_np["F3_spinloss_x_contact"] >= p80
    over_rate = df_np.loc[mask, "actual_result_over"].mean()
    n = mask.sum()
    w_over = df_np.loc[mask, "actual_result_over"].sum()
    over_roi = roi_110(w_over, n - w_over)
    print(f"  OVER tail (top 20%): N={n}, over%={over_rate:.3f}, OVER_ROI={over_roi:+.1f}%")
    r3["over_tail_rate"] = over_rate
    r3["over_tail_roi"] = over_roi
all_results.append(r3)
print(f"  {r3['name']}: G1={r3.get('gate1','?')} G2={r3.get('gate2','?')} G3={r3.get('gate3','?')} → {r3['verdict']}")

# FAMILY 4: OAA Defense — INSUFFICIENT DATA
print("\n=== FAMILY 4: OAA Defense ===")
r4 = {"name": "F4: OAA × contact suppression", "verdict": "SHELVE", "reason": "INSUFFICIENT_DATA — team OAA not available locally"}
all_results.append(r4)
print(f"  {r4['name']}: {r4['reason']}")

# FAMILY 5: Pitch Tempo — INSUFFICIENT DATA
print("\n=== FAMILY 5: Pitch Tempo ===")
r5 = {"name": "F5: pitch tempo × CSW", "verdict": "SHELVE", "reason": "INSUFFICIENT_DATA — pitch tempo not available locally"}
all_results.append(r5)
print(f"  {r5['name']}: {r5['reason']}")

# =====================================================================
# SAVE RESULTS
# =====================================================================

# Save per-family parquets (signal values for games where data exists)
for col, fname in [
    ("combined_extension_r5", "family1_extension_x_command.parquet"),
    ("F2_suppression", "family2_contact_x_groundball.parquet"),
    ("F3_spinloss_x_contact", "family3_spinloss_x_lineup.parquet"),
]:
    if col in df.columns:
        save_cols = ["game_pk", "date", "season", "home_team", "away_team",
                     "closing_total", "actual_total", "went_under", "market_residual_under",
                     "p_under", "v1_under", col]
        df[[c for c in save_cols if c in df.columns]].to_parquet(BASE / fname, index=False)

# Empty files for F4/F5
pd.DataFrame().to_parquet(BASE / "family4_oaa_defense.parquet", index=False)
pd.DataFrame().to_parquet(BASE / "family5_pitch_tempo.parquet", index=False)

# =====================================================================
# WRITE REPORT
# =====================================================================
print("\n=== WRITING REPORT ===")

R = []
R.append("# Statcast Interaction Family Scanner — Report")
R.append("")
R.append(f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append("")

R.append("## Summary Table")
R.append("")
R.append("| Family | Signal | G1 Stable | G2 Robust | G3 WF | G4 Perm | G5 Mkt | G6 V1 | Verdict |")
R.append("|--------|--------|-----------|-----------|-------|---------|--------|-------|---------|")
for r in all_results:
    g1 = r.get("gate1", "N/A")
    g2 = r.get("gate2", "N/A")
    g3 = r.get("gate3", "N/A")
    g4 = r.get("gate4", "N/A")
    g5 = r.get("gate5", "N/A")
    g6 = r.get("gate6", "N/A")
    R.append(f"| {r['name']} | {r.get('signal', 'N/A')} | {g1} | {g2} | {g3} | {g4} | {g5} | {g6} | **{r['verdict']}** |")
R.append("")

# Detailed per-family
for r in all_results:
    R.append(f"## {r['name']}")
    R.append("")
    if r["verdict"] in ("INSUFFICIENT_DATA", "SHELVE") and "reason" in r:
        R.append(f"**{r['verdict']}**: {r.get('reason', 'failed gates')}")
        R.append("")
        continue

    R.append(f"- Direction: {r.get('direction', '?')}")
    R.append(f"- N: {r.get('n', '?')}")
    R.append(f"- Gate 1 (stability): {r.get('gate1')} — 2024={r.get('coef_2024', 'N/A'):.5f}, 2025={r.get('coef_2025', 'N/A'):.5f}"
             if r.get("coef_2024") is not None else f"- Gate 1: {r.get('gate1')}")
    R.append(f"- Gate 2 (robustness): {r.get('gate2')} — p={r.get('robust_p', 'N/A'):.4f}"
             if r.get("robust_p") is not None else f"- Gate 2: {r.get('gate2')}")
    R.append(f"- Gate 3 (walk-forward): {r.get('gate3')} — 2024={r.get('wf_2024', 'N/A')}, 2025={r.get('wf_2025', 'N/A')}"
             if r.get("wf_2024") is not None else f"- Gate 3: {r.get('gate3')}")

    if r.get("gate3") == "PASS":
        R.append(f"- Gate 4 (permutation): {r.get('gate4')} — {r.get('perm_pctile', 'N/A'):.0f}th pctile"
                 if r.get("perm_pctile") is not None else f"- Gate 4: {r.get('gate4')}")
        R.append(f"- Gate 5 (market): {r.get('gate5')} — r={r.get('market_corr', 'N/A'):.4f}"
                 if r.get("market_corr") is not None else f"- Gate 5: {r.get('gate5')}")
        R.append(f"- Gate 6 (V1 amp): {r.get('gate6')} — V1 base={r.get('v1_base_ur', 'N/A'):.3f}, "
                 f"V1+sig={r.get('v1_amp_ur', 'N/A'):.3f}, lift={r.get('v1_lift', 'N/A'):.3f}"
                 if r.get("v1_lift") is not None else f"- Gate 6: {r.get('gate6')}")

    # Tail ROI
    for yr in [2024, 2025]:
        if f"tail_roi_{yr}" in r:
            R.append(f"- {yr} tail: N={r[f'tail_n_{yr}']}, under%={r[f'tail_ur_{yr}']:.3f}, ROI={r[f'tail_roi_{yr}']:+.1f}%")

    R.append(f"- **Verdict: {r['verdict']}**")
    R.append("")

R.append("## Conclusion")
R.append("")
shadows = [r for r in all_results if r["verdict"] == "SHADOW"]
investigates = [r for r in all_results if r["verdict"] == "INVESTIGATE"]
shelved = [r for r in all_results if r["verdict"] == "SHELVE"]

if shadows:
    R.append(f"**SHADOW candidates: {len(shadows)}**")
    for s in shadows:
        R.append(f"- {s['name']}")
elif investigates:
    R.append(f"**INVESTIGATE candidates: {len(investigates)}** (passed some but not all gates)")
    for s in investigates:
        R.append(f"- {s['name']}")
else:
    R.append("**No signals passed sufficient gates for SHADOW or INVESTIGATE.**")
    R.append("All five families SHELVED. The existing S12/P09 overlays appear to capture")
    R.append("the available Statcast interaction signal space adequately.")

R.append("")
R.append(f"Shelved: {len(shelved)} families")
R.append("")

out = BASE / "statcast_interactions_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"Saved: {out}")
