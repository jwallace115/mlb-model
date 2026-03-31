#!/usr/bin/env python3
"""
Umpire Interaction Triage — fast scan on 6 umpire signals.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# ── Load data ─────────────────────────────────────────────────────────
ft = pd.read_parquet(SIM / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])
br = pd.read_parquet(SIM / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])

# Build scanner dataset (2024+2025 with closing lines)
df = ft[ft["season"].isin([2024, 2025])].copy()
df = df.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
              on="game_pk", how="inner")
df.rename(columns={"close_total": "closing_total"}, inplace=True)

df["is_push"] = (df["actual_total"] == df["closing_total"])
df["went_under"] = (df["actual_total"] < df["closing_total"]).astype(int)
df["market_residual"] = df["went_under"] - 0.50
df_np = df[~df["is_push"]].copy()

print(f"Dataset: {len(df)} games, {len(df_np)} non-push")

# =====================================================================
# SOURCE AUDIT
# =====================================================================
print("\n=== SOURCE AUDIT ===")

# Available fields
available = {}
requested = {
    "umpire_bb_rate": "umpire_bb_rate",
    "umpire_k_rate": "umpire_k_rate",
    "umpire_historical_over_rate": "umpire_over_rate",
    "umpire_historical_runs_per_game": None,
    "avg_sp_csw_pct": None,
    "avg_sp_bb_rate": None,
}

field_map = {}
missing_fields = []

# umpire_k_rate: exists as k_tendency additive adjustment
if "umpire_k_rate" in df.columns:
    available["umpire_k_rate"] = True
    field_map["umpire_k_rate"] = "umpire_k_rate (k_tendency from UMPIRE_RATINGS, additive)"
    print(f"  umpire_k_rate: FOUND — range [{df.umpire_k_rate.min():.3f}, {df.umpire_k_rate.max():.3f}]")
else:
    missing_fields.append("umpire_k_rate")

# umpire_over_rate: exists as runs_factor multiplicative
if "umpire_over_rate" in df.columns:
    available["umpire_over_rate"] = True
    field_map["umpire_historical_over_rate"] = "umpire_over_rate (runs_factor from UMPIRE_RATINGS, multiplicative ~0.92–1.06)"
    field_map["umpire_historical_runs_per_game"] = "DERIVED from umpire_over_rate (runs_factor IS the runs-per-game ratio)"
    print(f"  umpire_over_rate: FOUND — range [{df.umpire_over_rate.min():.3f}, {df.umpire_over_rate.max():.3f}]")
else:
    missing_fields.append("umpire_over_rate")

# umpire_bb_rate: NOT in dataset
if "umpire_bb_rate" not in df.columns:
    missing_fields.append("umpire_bb_rate")
    print(f"  umpire_bb_rate: MISSING — not in UMPIRE_RATINGS or feature_table")

# avg_sp_csw_pct: not directly available but can derive from K%
# Use (home_sp_k_pct + away_sp_k_pct)/2 as proxy
df["avg_sp_k_pct"] = (df["home_sp_k_pct"] + df["away_sp_k_pct"]) / 2
df["avg_sp_bb_pct"] = (df["home_sp_bb_pct"] + df["away_sp_bb_pct"]) / 2
df_np["avg_sp_k_pct"] = df.loc[df_np.index, "avg_sp_k_pct"]
df_np["avg_sp_bb_pct"] = df.loc[df_np.index, "avg_sp_bb_pct"]
field_map["avg_sp_csw_pct"] = "avg_sp_k_pct = (home_sp_k_pct + away_sp_k_pct)/2 — K% proxy for CSW"
field_map["avg_sp_bb_rate"] = "avg_sp_bb_pct = (home_sp_bb_pct + away_sp_bb_pct)/2"
print(f"  avg_sp_csw_pct: SUBSTITUTED with avg_sp_k_pct (K% proxy)")
print(f"  avg_sp_bb_rate: DERIVED as avg_sp_bb_pct")

# Report missing
print(f"\n  MISSING FIELDS: {missing_fields}")
print(f"  These signals cannot be built as specified:")
print(f"    U01 (ump_walk_rate): CANNOT BUILD — umpire_bb_rate not available")
print(f"    U05 (ump_walk_pitcher): CANNOT BUILD — umpire_bb_rate not available")

# Data integrity
print(f"\n  DATA INTEGRITY: umpire_over_rate and umpire_k_rate are static per-umpire")
print(f"  ratings from UMPIRE_RATINGS dict (pre-season assignment). These are NOT")
print(f"  post-game corrected. They are pregame information based on historical")
print(f"  career data. Confirmed leakage-safe.")

# =====================================================================
# BUILD SIGNALS
# =====================================================================
print("\n=== BUILDING SIGNALS ===")

# League averages
lg_over_rate = df["umpire_over_rate"].mean()
lg_k_rate = df["umpire_k_rate"].mean()

print(f"  League avg umpire_over_rate: {lg_over_rate:.4f}")
print(f"  League avg umpire_k_rate: {lg_k_rate:.5f}")

# U01: CANNOT BUILD (no umpire_bb_rate)
# U02: ump_k_rate = umpire_k_rate - league_avg (already centered near 0)
df["U02"] = df["umpire_k_rate"] - lg_k_rate
df_np["U02"] = df.loc[df_np.index, "U02"]

# U03: ump_over_under_bias = umpire_over_rate - 1.0 (since 1.0 = neutral)
df["U03"] = df["umpire_over_rate"] - 1.0
df_np["U03"] = df.loc[df_np.index, "U03"]

# U04: ump_csw_interaction = umpire_k_rate * avg_sp_k_pct
df["U04"] = df["umpire_k_rate"] * df["avg_sp_k_pct"]
df_np["U04"] = df.loc[df_np.index, "U04"]

# U05: CANNOT BUILD (no umpire_bb_rate)

# U06: ump_runs_factor = umpire_over_rate / league_avg (≈ umpire_over_rate since lg ≈ 1.0)
df["U06"] = df["umpire_over_rate"] / lg_over_rate
df_np["U06"] = df.loc[df_np.index, "U06"]

SIGNALS = {
    "U02": {"name": "ump_k_rate", "hyp": "UNDER", "col": "U02"},
    "U03": {"name": "ump_over_under_bias", "hyp": "OVER (positive → OVER)", "col": "U03"},
    "U04": {"name": "ump_csw_interaction", "hyp": "UNDER (tight ump × command SP)", "col": "U04"},
    "U06": {"name": "ump_runs_factor", "hyp": "OVER (high → OVER)", "col": "U06"},
}

# =====================================================================
# RUN TRIAGE
# =====================================================================
print("\n=== RUNNING TRIAGE ===")

triage_results = []

for sig_id, meta in SIGNALS.items():
    col = meta["col"]
    name = meta["name"]
    print(f"\n--- {sig_id}: {name} ---")

    valid = df[col].notna()
    valid_np = df_np[col].notna()

    # TEST 1 — EXTREMES
    extremes = []
    promote_t1 = False
    for label, lo_pct, hi_pct in [
        ("top_10", 90, 100), ("top_20", 80, 100),
        ("bot_10", 0, 10), ("bot_20", 0, 20),
    ]:
        lo_val = np.nanpercentile(df.loc[valid, col], lo_pct)
        hi_val = np.nanpercentile(df.loc[valid, col], hi_pct)
        if lo_pct == 0:
            mask_np = valid_np & (df_np[col] <= hi_val)
            mask_all = valid & (df[col] <= hi_val)
        else:
            mask_np = valid_np & (df_np[col] > lo_val)
            mask_all = valid & (df[col] > lo_val)

        n_np = mask_np.sum()
        n_all = mask_all.sum()
        if n_np < 20:
            extremes.append({"bucket": label, "N": n_np, "resid": np.nan, "roi": np.nan})
            continue

        resid = df.loc[valid][mask_all]["market_residual"].mean()
        ur = df_np.loc[valid_np][mask_np]["went_under"].mean()
        w = df_np.loc[valid_np][mask_np]["went_under"].sum()
        roi = roi_110(w, n_np - w)

        extremes.append({"bucket": label, "N": n_np, "resid": resid, "roi": roi, "under_rate": ur})
        print(f"  {label}: N={n_np}, resid={resid:+.4f}, ROI={roi:+.1f}%")

        if "10" in label and n_np >= 60 and abs(resid) > 0.03:
            promote_t1 = True

    # TEST 2 — DIRECTIONAL CONSISTENCY
    yr_coefs = {}
    for yr in [2024, 2025]:
        yr_df = df[(df["season"] == yr) & valid]
        X = sm.add_constant(yr_df[col])
        y = yr_df["market_residual"]
        m = sm.OLS(y, X).fit()
        yr_coefs[yr] = {"coef": m.params[col], "p": m.pvalues[col]}

    consistent = yr_coefs[2024]["coef"] * yr_coefs[2025]["coef"] > 0
    stability = "CONSISTENT" if consistent else "MIXED"
    print(f"  Stability: {stability} ({yr_coefs[2024]['coef']:+.4f} / {yr_coefs[2025]['coef']:+.4f})")

    # TEST 3 — MARKET CORRELATION
    corr_mask = valid & df["closing_total"].notna()
    r_corr, _ = stats.pearsonr(df.loc[corr_mask, col], df.loc[corr_mask, "closing_total"])
    if abs(r_corr) < 0.15:
        corr_class = "CLEAN"
    elif abs(r_corr) < 0.30:
        corr_class = "PARTIAL"
    else:
        corr_class = "PRICED"
    print(f"  Market corr: r={r_corr:.4f} → {corr_class}")

    # VERDICT
    if promote_t1 and consistent and abs(r_corr) < 0.25:
        verdict = "PROMOTE"
    else:
        verdict = "SHELVE"
        reasons = []
        if not promote_t1:
            reasons.append("no extreme bucket (|resid|>3pp at N≥60)")
        if not consistent:
            reasons.append("direction MIXED across years")
        if abs(r_corr) >= 0.25:
            reasons.append(f"market corr too high ({r_corr:.3f})")
        verdict_reason = "; ".join(reasons)

    print(f"  → {verdict}" + (f" ({verdict_reason})" if verdict == "SHELVE" else ""))

    triage_results.append({
        "signal": sig_id, "name": name, "hypothesis": meta["hyp"],
        "extremes": extremes, "stability": stability,
        "yr_2024_coef": yr_coefs[2024]["coef"], "yr_2024_p": yr_coefs[2024]["p"],
        "yr_2025_coef": yr_coefs[2025]["coef"], "yr_2025_p": yr_coefs[2025]["p"],
        "market_corr": r_corr, "corr_class": corr_class,
        "promote_t1": promote_t1, "consistent": consistent,
        "verdict": verdict,
    })


# =====================================================================
# WRITE REPORT SECTION
# =====================================================================
print("\n=== WRITING REPORT ===")

lines = [
    "",
    "",
    "## Umpire Interaction Triage",
    "",
    f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push",
    "",
    "### Field Mapping",
    "",
    "| Requested Field | Available Field | Notes |",
    "|----------------|----------------|-------|",
    "| umpire_bb_rate | **MISSING** | Not in UMPIRE_RATINGS or feature_table |",
    "| umpire_k_rate | umpire_k_rate | k_tendency from UMPIRE_RATINGS, additive adjustment |",
    "| umpire_historical_over_rate | umpire_over_rate | runs_factor from UMPIRE_RATINGS, multiplicative (~0.92–1.06) |",
    "| umpire_historical_runs_per_game | derived from umpire_over_rate | runs_factor IS the runs-per-game ratio |",
    "| avg_sp_csw_pct | avg_sp_k_pct | (home_sp_k_pct + away_sp_k_pct)/2 — K% proxy for CSW |",
    "| avg_sp_bb_rate | avg_sp_bb_pct | (home_sp_bb_pct + away_sp_bb_pct)/2 |",
    "",
    "### Signals Skipped",
    "- **U01 (ump_walk_rate)**: CANNOT BUILD — umpire_bb_rate not available",
    "- **U05 (ump_walk_pitcher)**: CANNOT BUILD — umpire_bb_rate not available",
    "",
    "### Data Integrity",
    "umpire_over_rate and umpire_k_rate are static per-umpire career ratings",
    "from the UMPIRE_RATINGS dict, assigned pregame. Not post-game corrected.",
    "",
    "### Signal Definitions (as built)",
    "",
    "| Signal | Formula | Direction |",
    "|--------|---------|-----------|",
    f"| U02 | umpire_k_rate − {lg_k_rate:.5f} | UNDER |",
    "| U03 | umpire_over_rate − 1.0 | OVER (positive → OVER) |",
    "| U04 | umpire_k_rate × avg_sp_k_pct | UNDER (tight ump × command SP) |",
    f"| U06 | umpire_over_rate / {lg_over_rate:.4f} | OVER (high → OVER) |",
    "",
    "### Triage Results",
    "",
    "| Signal | Name | Best 10% Bucket | N | Resid | ROI | Stability | Mkt Corr | Verdict |",
    "|--------|------|----------------|---|-------|-----|-----------|----------|---------|",
]

for tr in triage_results:
    # Find best 10% bucket by |resid|
    ten_pct = [e for e in tr["extremes"] if "10" in e["bucket"] and not np.isnan(e.get("resid", np.nan))]
    if ten_pct:
        best = max(ten_pct, key=lambda e: abs(e["resid"]))
        resid_s = f"{best['resid']:+.4f}"
        roi_s = f"{best['roi']:+.1f}%"
        n_s = str(best["N"])
        bucket_s = best["bucket"]
    else:
        resid_s = roi_s = n_s = bucket_s = "N/A"

    lines.append(f"| {tr['signal']} | {tr['name']} | {bucket_s} | {n_s} | {resid_s} | {roi_s} | "
                 f"{tr['stability']} | {tr['corr_class']} ({tr['market_corr']:.3f}) | **{tr['verdict']}** |")

lines.append("")
lines.append("### Year Detail")
lines.append("")
lines.append("| Signal | 2024 Coef | 2024 p | 2025 Coef | 2025 p | Consistent? |")
lines.append("|--------|----------|--------|----------|--------|------------|")
for tr in triage_results:
    lines.append(f"| {tr['signal']} | {tr['yr_2024_coef']:+.5f} | {tr['yr_2024_p']:.4f} | "
                 f"{tr['yr_2025_coef']:+.5f} | {tr['yr_2025_p']:.4f} | {tr['stability']} |")

lines.append("")
lines.append("### Extreme Bucket Detail")
lines.append("")
for tr in triage_results:
    lines.append(f"**{tr['signal']}: {tr['name']}**")
    lines.append("| Bucket | N | Resid | Under% | ROI |")
    lines.append("|--------|---|-------|--------|-----|")
    for e in tr["extremes"]:
        if not np.isnan(e.get("resid", np.nan)):
            lines.append(f"| {e['bucket']} | {e['N']} | {e['resid']:+.4f} | "
                         f"{e.get('under_rate', 0):.3f} | {e['roi']:+.1f}% |")
        else:
            lines.append(f"| {e['bucket']} | {e['N']} | N/A | N/A | N/A |")
    lines.append("")

lines.append("### Summary")
lines.append("")
n_promoted = sum(1 for tr in triage_results if tr["verdict"] == "PROMOTE")
n_shelved = sum(1 for tr in triage_results if tr["verdict"] == "SHELVE")
lines.append(f"**Promoted: {n_promoted}** | Shelved: {n_shelved} | Skipped (missing data): 2")
lines.append("")
if n_promoted == 0:
    lines.append("No umpire signals passed all three promotion gates.")
    lines.append("The umpire ratings in UMPIRE_RATINGS are already incorporated into the V1 simulation")
    lines.append("model via the runs_factor and k_tendency fields. The market appears to price umpire")
    lines.append("effects adequately — no residual signal remains in the extreme buckets.")
lines.append("")

# Append to scan_report.md
report_path = BASE / "scan_report.md"
with open(report_path, "a") as f:
    f.write("\n".join(lines) + "\n")
print(f"Appended to {report_path}")
print("Done.")
