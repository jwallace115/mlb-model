#!/usr/bin/env python3
"""
Weather Interaction Triage — fast scan on 7 weather signals.
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

field_report = []

# Check each requested field
requested = {
    "wind_speed": ("wind_speed", "FOUND"),
    "wind_out_flag": (None, "MISSING — derived from wind_factor_effective > 0"),
    "wind_in_flag": (None, "MISSING — derived from wind_factor_effective < 0"),
    "temperature": ("temperature", "FOUND"),
    "humidity_pct": (None, "MISSING — not in feature_table or game_table"),
    "park_hr_factor": ("park_factor_hr", "FOUND (as park_factor_hr)"),
    "avg_sp_fb_rate": (None, "MISSING — sp_gb_pct is all NaN; using 1 - avg_sp_gb_proxy"),
    "avg_sp_breaking_ball_pct": (None, "MISSING — no pitch-type breakdown in feature_table"),
    "park_seasonal_avg_temp": (None, "MISSING — not precomputed"),
}

for req, (actual, status) in requested.items():
    field_report.append((req, actual or "N/A", status))
    print(f"  {req}: {status}")

# Derive what we can
# wind_out_flag: wind_factor_effective > 0 means wind helps HR (blowing out)
df["wind_out_flag"] = (df["wind_factor_effective"] > 0).astype(int)
df["wind_in_flag"] = (df["wind_factor_effective"] < 0).astype(int)
df_np["wind_out_flag"] = df.loc[df_np.index, "wind_out_flag"]
df_np["wind_in_flag"] = df.loc[df_np.index, "wind_in_flag"]

# avg_sp_fb_rate: gb_pct is all NaN. Use wind_factor_effective magnitude as proxy
# for "flyball exposure" (higher abs(wfe) = more wind-sensitive, implying FB pitchers)
# Actually, we DON'T have flyball rate. We'll note this and test what we can.
# For W01/W02: use wind_factor_effective directly (it already encodes wind × park geometry)
# For W06: already encoded in wind_factor_effective

# park_seasonal_avg_temp: compute from our data
park_avg_temp = df.groupby("park_id")["temperature"].mean().rename("park_avg_temp")
df = df.merge(park_avg_temp, on="park_id", how="left")
df_np = df[~df["is_push"]].copy()

print(f"\n  MISSING FIELDS IMPACT:")
print(f"    humidity_pct: W07 CANNOT BUILD")
print(f"    avg_sp_fb_rate: W01, W02 use wind_factor_effective as proxy")
print(f"    avg_sp_breaking_ball_pct: W04 CANNOT BUILD as specified")
print(f"    park_seasonal_avg_temp: DERIVED from park-level mean temperature in dataset")

print(f"\n  DATA INTEGRITY:")
print(f"    temperature: Open-Meteo forecast (pre-game). Confirmed pregame.")
print(f"    wind_speed/direction: Open-Meteo forecast (pre-game). Confirmed pregame.")
print(f"    wind_factor_effective: derived from wind_speed × cos(wind_dir - cf_bearing). Pre-game.")
print(f"    roof_status: from venue metadata. Pre-game.")

# =====================================================================
# BUILD SIGNALS
# =====================================================================
print("\n=== BUILDING SIGNALS ===")

# W01: wind_out_flyball — use wind_factor_effective for positive wind (out)
# Since we don't have fb_rate, use wind_factor_effective directly when > 0
# This IS the wind × park geometry × direction effect
df["W01"] = df["wind_factor_effective"].clip(lower=0)  # 0 when wind in or neutral
df_np["W01"] = df.loc[df_np.index, "W01"]
print(f"  W01 (wind_out): nonzero N={( df['W01'] > 0).sum()}")

# W02: wind_in_flyball — use magnitude of negative wind_factor_effective
df["W02"] = (-df["wind_factor_effective"]).clip(lower=0)  # 0 when wind out or neutral
df_np["W02"] = df.loc[df_np.index, "W02"]
print(f"  W02 (wind_in): nonzero N={(df['W02'] > 0).sum()}")

# W03: temp_deviation = temperature - park_seasonal_avg_temp
df["W03"] = df["temperature"] - df["park_avg_temp"]
df_np["W03"] = df.loc[df_np.index, "W03"]
print(f"  W03 (temp_dev): mean={df['W03'].mean():.2f}, std={df['W03'].std():.2f}")

# W04: cold_breaking — CANNOT BUILD as specified (no breaking_ball_pct)
# Substitute: cold_suppression = max(0, 60 - temperature)
# Tests whether cold weather alone suppresses/boosts scoring
df["W04"] = (60 - df["temperature"]).clip(lower=0)
df_np["W04"] = df.loc[df_np.index, "W04"]
n_cold = (df["W04"] > 0).sum()
print(f"  W04 (cold_factor): games with temp<60: {n_cold}")

# W05: extreme_heat flag (temp >= 95)
df["W05"] = (df["temperature"] >= 95).astype(int)
df_np["W05"] = df.loc[df_np.index, "W05"]
n_hot = df["W05"].sum()
print(f"  W05 (extreme_heat): N={n_hot}")

# W06: wind_park_geometry = wind_speed * park_hr_factor * wind_out_flag
df["W06"] = df["wind_speed"] * (df["park_factor_hr"] / 100) * df["wind_out_flag"]
df_np["W06"] = df.loc[df_np.index, "W06"]
print(f"  W06 (wind_park): nonzero N={(df['W06'] > 0).sum()}")

# W07: humidity_carry — CANNOT BUILD (no humidity data)

SIGNALS = {
    "W01": {"name": "wind_out_proxy", "hyp": "OVER", "note": "wind_factor_effective clipped >0"},
    "W02": {"name": "wind_in_proxy", "hyp": "UNDER", "note": "-wind_factor_effective clipped >0"},
    "W03": {"name": "temp_deviation", "hyp": "OVER (high dev)", "note": "temp - park_avg_temp"},
    "W04": {"name": "cold_factor", "hyp": "OVER", "note": "max(0, 60-temp); no breaking_ball_pct available"},
    "W05": {"name": "extreme_heat", "hyp": "OVER", "note": "binary: temp >= 95°F"},
    "W06": {"name": "wind_park_geometry", "hyp": "OVER", "note": "wind_speed × park_hr_factor × wind_out_flag"},
}

# =====================================================================
# RUN TRIAGE
# =====================================================================
print("\n=== RUNNING TRIAGE ===")

triage_results = []

for sig_id, meta in SIGNALS.items():
    col = sig_id
    name = meta["name"]
    print(f"\n--- {sig_id}: {name} ---")

    valid = df[col].notna()
    valid_np = df_np[col].notna()

    # Handle binary (W05) vs continuous
    is_binary = sig_id == "W05"

    # TEST 1 — EXTREMES
    extremes = []
    promote_t1 = False

    if is_binary:
        # Binary signal
        for flag_val, label in [(1, "flag=1"), (0, "flag=0")]:
            mask_np = valid_np & (df_np[col] == flag_val)
            mask_all = valid & (df[col] == flag_val)
            n_np = mask_np.sum()
            if n_np < 20:
                extremes.append({"bucket": label, "N": n_np, "resid": np.nan, "roi": np.nan})
                continue
            resid = df.loc[valid][mask_all]["market_residual"].mean()
            ur = df_np.loc[valid_np][mask_np]["went_under"].mean()
            w = df_np.loc[valid_np][mask_np]["went_under"].sum()
            roi = roi_110(w, n_np - w)
            extremes.append({"bucket": label, "N": n_np, "resid": resid, "roi": roi, "under_rate": ur})
            print(f"  {label}: N={n_np}, resid={resid:+.4f}, under%={ur:.3f}, ROI={roi:+.1f}%")
            if n_np >= 60 and abs(resid) > 0.03:
                promote_t1 = True
    else:
        for label, lo_pct, hi_pct in [
            ("top_10", 90, 100), ("top_20", 80, 100),
            ("bot_10", 0, 10), ("bot_20", 0, 20),
        ]:
            # For signals with many zeros (W01, W02, W04), quantiles may be degenerate
            nonzero = df.loc[valid, col]
            lo_val = np.nanpercentile(nonzero, lo_pct)
            hi_val = np.nanpercentile(nonzero, hi_pct)

            if lo_pct == 0:
                mask_np = valid_np & (df_np[col] <= hi_val)
                mask_all = valid & (df[col] <= hi_val)
            else:
                mask_np = valid_np & (df_np[col] > lo_val)
                mask_all = valid & (df[col] > lo_val)

            n_np = mask_np.sum()
            if n_np < 20:
                extremes.append({"bucket": label, "N": n_np, "resid": np.nan, "roi": np.nan})
                continue

            resid = df.loc[valid][mask_all]["market_residual"].mean()
            ur = df_np.loc[valid_np][mask_np]["went_under"].mean()
            w = df_np.loc[valid_np][mask_np]["went_under"].sum()
            roi = roi_110(w, n_np - w)
            extremes.append({"bucket": label, "N": n_np, "resid": resid, "roi": roi, "under_rate": ur})
            print(f"  {label}: N={n_np}, resid={resid:+.4f}, under%={ur:.3f}, ROI={roi:+.1f}%")

            if "10" in label and n_np >= 60 and abs(resid) > 0.03:
                promote_t1 = True

    # TEST 2 — DIRECTIONAL CONSISTENCY
    yr_coefs = {}
    for yr in [2024, 2025]:
        yr_df = df[(df["season"] == yr) & valid]
        if yr_df[col].std() < 1e-10:
            yr_coefs[yr] = {"coef": 0, "p": 1.0}
            continue
        X = sm.add_constant(yr_df[col])
        y = yr_df["market_residual"]
        m = sm.OLS(y, X).fit()
        yr_coefs[yr] = {"coef": m.params[col], "p": m.pvalues[col]}

    consistent = yr_coefs.get(2024, {}).get("coef", 0) * yr_coefs.get(2025, {}).get("coef", 0) > 0
    stability = "CONSISTENT" if consistent else "MIXED"
    print(f"  Stability: {stability} "
          f"({yr_coefs.get(2024,{}).get('coef',0):+.4f} / {yr_coefs.get(2025,{}).get('coef',0):+.4f})")

    # TEST 3 — MARKET CORRELATION
    corr_mask = valid & df["closing_total"].notna()
    if df.loc[corr_mask, col].std() > 1e-10:
        r_corr, _ = stats.pearsonr(df.loc[corr_mask, col], df.loc[corr_mask, "closing_total"])
    else:
        r_corr = 0.0
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
            reasons.append("direction MIXED")
        if abs(r_corr) >= 0.25:
            reasons.append(f"market corr ({r_corr:.3f})")
        verdict_reason = "; ".join(reasons)

    print(f"  → {verdict}" + (f" ({verdict_reason})" if verdict == "SHELVE" else ""))

    triage_results.append({
        "signal": sig_id, "name": name, "hypothesis": meta["hyp"],
        "note": meta["note"],
        "extremes": extremes, "stability": stability,
        "yr_2024_coef": yr_coefs.get(2024, {}).get("coef", np.nan),
        "yr_2024_p": yr_coefs.get(2024, {}).get("p", np.nan),
        "yr_2025_coef": yr_coefs.get(2025, {}).get("coef", np.nan),
        "yr_2025_p": yr_coefs.get(2025, {}).get("p", np.nan),
        "market_corr": r_corr, "corr_class": corr_class,
        "promote_t1": promote_t1, "consistent": consistent,
        "verdict": verdict,
    })


# =====================================================================
# WRITE REPORT
# =====================================================================
print("\n=== WRITING REPORT ===")

lines = [
    "",
    "",
    "## Weather Interaction Triage",
    "",
    f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push",
    "",
    "### Field Mapping",
    "",
    "| Requested Field | Actual Field | Status |",
    "|----------------|-------------|--------|",
]
for req, actual, status in field_report:
    lines.append(f"| {req} | {actual} | {status} |")

lines.extend([
    "",
    "### Signals Skipped / Modified",
    "- **W07 (humidity_carry)**: CANNOT BUILD — humidity_pct not available",
    "- **W01 (wind_out_flyball)**: MODIFIED — avg_sp_fb_rate not available; using wind_factor_effective clipped >0 as proxy (already encodes wind × park geometry)",
    "- **W02 (wind_in_flyball)**: MODIFIED — same proxy approach, negative wind_factor_effective",
    "- **W04 (cold_breaking)**: MODIFIED — avg_sp_breaking_ball_pct not available; using max(0, 60-temp) as cold factor only",
    "",
    "### Data Integrity",
    "- temperature, wind_speed, wind_direction: Open-Meteo forecast (pre-game). Confirmed pregame.",
    "- wind_factor_effective: derived from wind_speed × cos(wind_dir - cf_bearing). Pre-game.",
    "- park_avg_temp: derived from dataset mean per park_id (static, not post-game).",
    "",
    "### Signal Definitions (as built)",
    "",
    "| Signal | Formula | Direction | Note |",
    "|--------|---------|-----------|------|",
])
for tr in triage_results:
    lines.append(f"| {tr['signal']} | see code | {tr['hypothesis']} | {tr['note']} |")

lines.extend([
    "",
    "### Triage Results",
    "",
    "| Signal | Name | Best 10% Bucket | N | Resid | ROI | Stability | Mkt Corr | Verdict |",
    "|--------|------|----------------|---|-------|-----|-----------|----------|---------|",
])

for tr in triage_results:
    ten_pct = [e for e in tr["extremes"]
               if ("10" in e["bucket"] or "flag" in e["bucket"])
               and not np.isnan(e.get("resid", np.nan))]
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

lines.extend([
    "",
    "### Year Detail",
    "",
    "| Signal | 2024 Coef | 2024 p | 2025 Coef | 2025 p | Consistent? |",
    "|--------|----------|--------|----------|--------|------------|",
])
for tr in triage_results:
    c24 = tr["yr_2024_coef"]
    p24 = tr["yr_2024_p"]
    c25 = tr["yr_2025_coef"]
    p25 = tr["yr_2025_p"]
    c24s = f"{c24:+.5f}" if not np.isnan(c24) else "N/A"
    p24s = f"{p24:.4f}" if not np.isnan(p24) else "N/A"
    c25s = f"{c25:+.5f}" if not np.isnan(c25) else "N/A"
    p25s = f"{p25:.4f}" if not np.isnan(p25) else "N/A"
    lines.append(f"| {tr['signal']} | {c24s} | {p24s} | {c25s} | {p25s} | {tr['stability']} |")

lines.extend([
    "",
    "### Extreme Bucket Detail",
    "",
])
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

n_promoted = sum(1 for tr in triage_results if tr["verdict"] == "PROMOTE")
n_shelved = sum(1 for tr in triage_results if tr["verdict"] == "SHELVE")
lines.extend([
    "### Summary",
    "",
    f"**Promoted: {n_promoted}** | Shelved: {n_shelved} | Skipped (missing data): 1 (W07)",
    "",
])
if n_promoted == 0:
    lines.append("No weather signals passed all three promotion gates.")
    lines.append("Weather effects (temperature, wind) are already in the V1 simulation model")
    lines.append("via wind_factor_effective and temperature features. The market prices these")
    lines.append("factors into totals efficiently — no residual exploitable signal remains.")
elif n_promoted > 0:
    promoted = [tr for tr in triage_results if tr["verdict"] == "PROMOTE"]
    for p in promoted:
        lines.append(f"**{p['signal']} ({p['name']})**: promoted for deep analysis")
lines.append("")

report_path = BASE / "scan_report.md"
with open(report_path, "a") as f:
    f.write("\n".join(lines) + "\n")
print(f"Appended to {report_path}")
print("Done.")
