#!/usr/bin/env python3
"""
Task 3 — Triage Tests for Bullpen Fatigue (BF01-BF03) and Schedule/Travel (ST01-ST03)

Standard scanner triage:
  T1: Extreme buckets (top/bot 10%/20%), min N≥40
  T2: Directional stability (2024 vs 2025)
  T3: Market correlation (signal vs closing_total)

Output: appends to scan_report.md
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

BASE = Path(__file__).resolve().parent

# ── Load feature files ───────────────────────────────────────────────
bf = pd.read_parquet(BASE / "derived_features" / "bullpen_fatigue.parquet")
st = pd.read_parquet(BASE / "derived_features" / "schedule_travel.parquet")

# Merge on game_pk
df = bf.merge(st.drop(columns=["date", "season", "home_team", "away_team",
                                "actual_total", "closing_total"]),
              on="game_pk", how="inner")

print(f"Merged dataset: {len(df)} games")
print(f"2024: {(df.season==2024).sum()}, 2025: {(df.season==2025).sum()}")

# ── Construct derived signals ────────────────────────────────────────
# BF01: bullpen_ip_gap_2d = away - home (higher away fatigue → OVER)
df["BF01"] = df["bullpen_ip_last2days_away"] - df["bullpen_ip_last2days_home"]

# BF02: closer_unavailable_away = closer_used_last2days_away flag (→ OVER)
df["BF02"] = df["closer_used_last2days_away"]

# BF03: bullpen_workload_3d_home = bp_ip_last3d_home / season_avg (→ OVER)
df["BF03"] = df["bullpen_ip_last3days_home"] / df["home_season_avg_daily_bp_ip"]

# ST01: rest_gap = home - away (direction unknown)
df["ST01"] = df["days_rest_home"] - df["days_rest_away"]

# ST02: away_road_trip_game_6plus (→ UNDER)
df["ST02"] = (df["road_trip_game_num_away"] >= 6).astype(int)

# ST03: timezone_change_2plus (→ UNDER)
df["ST03"] = (df["timezone_change_away"] >= 2).astype(int)

# ── Outcome: market error (positive = actual went OVER market) ───────
df["market_error"] = df["actual_total"] - df["closing_total"]
df["is_push"] = (df["actual_total"] == df["closing_total"])
df["went_under"] = (df["actual_total"] < df["closing_total"]).astype(int)

# Non-push subset for win rates
df_np = df[~df["is_push"]].copy()

SIGNALS = {
    "BF01": {"name": "bullpen_ip_gap_2d", "hyp": "OVER", "continuous": True},
    "BF02": {"name": "closer_unavail_away", "hyp": "OVER", "continuous": False},
    "BF03": {"name": "bp_workload_3d_home", "hyp": "OVER", "continuous": True},
    "ST01": {"name": "rest_gap", "hyp": "UNKNOWN", "continuous": True},
    "ST02": {"name": "road_trip_6plus_away", "hyp": "UNDER", "continuous": False},
    "ST03": {"name": "tz_change_2plus_away", "hyp": "UNDER", "continuous": False},
}

results = []

for sig_id, meta in SIGNALS.items():
    print(f"\n{'='*60}")
    print(f"{sig_id}: {meta['name']} (hypothesis: {meta['hyp']})")
    print(f"{'='*60}")

    col = sig_id
    valid = df[col].notna()
    valid_np = df_np[col].notna()
    n_total = valid.sum()
    n_np = valid_np.sum()

    sig_vals = df.loc[valid, col]
    sig_np = df_np.loc[valid_np, col]

    # ── T3: Market correlation ───────────────────────────────────────
    corr_mask = valid & df["closing_total"].notna()
    if corr_mask.sum() > 50:
        r, p_corr = stats.pearsonr(df.loc[corr_mask, col], df.loc[corr_mask, "closing_total"])
    else:
        r, p_corr = np.nan, np.nan
    print(f"  Market corr: r={r:.4f}, p={p_corr:.4f}")

    # ── T1: Extreme buckets ──────────────────────────────────────────
    if meta["continuous"]:
        bucket_results = []
        for label, lo_pct, hi_pct in [
            ("top_10", 90, 100), ("bot_10", 0, 10),
            ("top_20", 80, 100), ("bot_20", 0, 20),
        ]:
            lo_val = np.nanpercentile(sig_vals, lo_pct)
            hi_val = np.nanpercentile(sig_vals, hi_pct)
            if lo_pct == 0:
                mask = sig_np <= hi_val
                mask_all = sig_vals <= hi_val
            else:
                mask = sig_np > lo_val
                mask_all = sig_vals > lo_val

            n_bucket = mask.sum()
            n_bucket_all = mask_all.sum()

            if n_bucket < 40:
                bucket_results.append((label, n_bucket, np.nan, np.nan))
                print(f"  {label}: N={n_bucket} < 40, SKIP")
                continue

            # Win rate for UNDER (went_under=1 means actual < closing)
            under_rate = df_np.loc[valid_np & mask, "went_under"].mean()
            over_rate = 1 - under_rate
            mean_err = df.loc[valid & mask_all, "market_error"].mean()

            bucket_results.append((label, n_bucket, under_rate, mean_err))
            print(f"  {label}: N={n_bucket}, under_rate={under_rate:.3f}, "
                  f"over_rate={over_rate:.3f}, mean_error={mean_err:+.3f}")

        # Best extreme bucket
        best_bucket = None
        best_effect = 0
        for lbl, n, ur, me in bucket_results:
            if ur is not None and not np.isnan(ur):
                effect = abs(me) if me is not None and not np.isnan(me) else 0
                if effect > best_effect:
                    best_effect = effect
                    best_bucket = (lbl, n, ur, me)
    else:
        # Binary signal — just compare flag=1 vs flag=0
        bucket_results = []
        for flag_val, label in [(1, "flag=1"), (0, "flag=0")]:
            mask = sig_np == flag_val
            mask_all = sig_vals == flag_val
            n_bucket = mask.sum()

            if n_bucket < 40:
                bucket_results.append((label, n_bucket, np.nan, np.nan))
                print(f"  {label}: N={n_bucket} < 40, SKIP")
                continue

            under_rate = df_np.loc[valid_np & mask, "went_under"].mean()
            mean_err = df.loc[valid & mask_all, "market_error"].mean()
            bucket_results.append((label, n_bucket, under_rate, mean_err))
            print(f"  {label}: N={n_bucket}, under_rate={under_rate:.3f}, mean_error={mean_err:+.3f}")

        best_bucket = None
        best_effect = 0
        for lbl, n, ur, me in bucket_results:
            if ur is not None and not np.isnan(ur):
                effect = abs(me) if me is not None and not np.isnan(me) else 0
                if effect > best_effect:
                    best_effect = effect
                    best_bucket = (lbl, n, ur, me)

    # ── T2: Directional stability (2024 vs 2025) ────────────────────
    year_results = {}
    for yr in [2024, 2025]:
        yr_mask = (df["season"] == yr) & valid
        yr_np_mask = (df_np["season"] == yr) & valid_np

        if yr_np_mask.sum() < 40:
            year_results[yr] = {"n": yr_np_mask.sum(), "mean_err": np.nan, "under_rate": np.nan}
            continue

        if meta["continuous"]:
            # Use top 20% bucket for directional check
            top20_val = np.nanpercentile(df.loc[yr_mask, col], 80)
            top_mask = (df_np.loc[yr_np_mask, col] > top20_val)
            top_mask_all = (df.loc[yr_mask, col] > top20_val)

            bot20_val = np.nanpercentile(df.loc[yr_mask, col], 20)
            bot_mask = (df_np.loc[yr_np_mask, col] <= bot20_val)
            bot_mask_all = (df.loc[yr_mask, col] <= bot20_val)

            top_err = df.loc[yr_mask][top_mask_all]["market_error"].mean()
            bot_err = df.loc[yr_mask][bot_mask_all]["market_error"].mean()

            # OLS on full year
            from scipy.stats import linregress
            x = df.loc[yr_mask, col].values
            y = df.loc[yr_mask, "market_error"].values
            finite = np.isfinite(x) & np.isfinite(y)
            if finite.sum() > 50:
                slope, intercept, r_val, p_val, se = linregress(x[finite], y[finite])
                year_results[yr] = {"n": finite.sum(), "slope": slope, "p": p_val,
                                    "top20_err": top_err, "bot20_err": bot_err}
                print(f"  {yr}: N={finite.sum()}, slope={slope:+.4f}, p={p_val:.4f}, "
                      f"top20_err={top_err:+.3f}, bot20_err={bot_err:+.3f}")
            else:
                year_results[yr] = {"n": 0}
        else:
            f1_np = (df_np.loc[yr_np_mask, col] == 1)
            f0_np = (df_np.loc[yr_np_mask, col] == 0)
            f1_all = (df.loc[yr_mask, col] == 1)
            f0_all = (df.loc[yr_mask, col] == 0)

            err_1 = df.loc[yr_mask][f1_all]["market_error"].mean() if f1_all.sum() > 0 else np.nan
            err_0 = df.loc[yr_mask][f0_all]["market_error"].mean() if f0_all.sum() > 0 else np.nan
            ur_1 = df_np.loc[yr_np_mask][f1_np]["went_under"].mean() if f1_np.sum() > 0 else np.nan
            ur_0 = df_np.loc[yr_np_mask][f0_np]["went_under"].mean() if f0_np.sum() > 0 else np.nan

            year_results[yr] = {"n_1": f1_np.sum(), "n_0": f0_np.sum(),
                                "err_1": err_1, "err_0": err_0,
                                "ur_1": ur_1, "ur_0": ur_0}
            print(f"  {yr}: flag=1 N={f1_np.sum()}, err={err_1:+.3f}, under_rate={ur_1:.3f} | "
                  f"flag=0 N={f0_np.sum()}, err={err_0:+.3f}, under_rate={ur_0:.3f}")

    # ── Stability check ──────────────────────────────────────────────
    if meta["continuous"]:
        slopes = [year_results[yr].get("slope", 0) for yr in [2024, 2025] if "slope" in year_results.get(yr, {})]
        stable = len(slopes) == 2 and (slopes[0] * slopes[1] > 0)  # same sign
    else:
        # Check if flag=1 error direction is consistent
        errs = [year_results[yr].get("err_1", 0) for yr in [2024, 2025] if "err_1" in year_results.get(yr, {})]
        stable = len(errs) == 2 and (errs[0] * errs[1] > 0)

    stability = "STABLE" if stable else "UNSTABLE"
    print(f"  Year stability: {stability}")

    results.append({
        "signal": sig_id,
        "name": meta["name"],
        "hypothesis": meta["hyp"],
        "N_total": n_total,
        "N_nonpush": n_np,
        "market_corr": round(r, 4) if not np.isnan(r) else "N/A",
        "best_bucket": best_bucket,
        "best_effect": round(best_effect, 4),
        "year_stability": stability,
        "year_results": year_results,
    })

# ── Generate report ──────────────────────────────────────────────────
print(f"\n\n{'='*60}")
print("TRIAGE SUMMARY")
print(f"{'='*60}")

report_lines = [
    "",
    "",
    "## Bullpen Fatigue + Schedule Triage",
    "",
    f"Base dataset: {len(df)} games (2024-2025), {len(df_np)} non-push",
    "",
    "### Feature Coverage",
    "| Feature | N | Coverage |",
    "|---------|---|----------|",
]

for col_name in ["bullpen_ip_last2days_home", "bullpen_ip_last2days_away",
                  "bullpen_ip_last3days_home", "bullpen_ip_last3days_away",
                  "closer_used_last2days_home", "closer_used_last2days_away",
                  "days_rest_home", "days_rest_away",
                  "road_trip_game_num_away", "timezone_change_away"]:
    n = df[col_name].notna().sum()
    report_lines.append(f"| {col_name} | {n} | {100*n/len(df):.1f}% |")

report_lines.extend([
    "",
    "### Signal Definitions",
    "| Signal | Formula | Hypothesis |",
    "|--------|---------|-----------|",
    "| BF01 | bp_ip_last2d_away − bp_ip_last2d_home | OVER (away fatigue) |",
    "| BF02 | closer_used_last2d_away flag | OVER (closer unavail) |",
    "| BF03 | bp_ip_last3d_home / season_avg_daily_bp_ip | OVER (home BP taxed) |",
    "| ST01 | days_rest_home − days_rest_away | UNKNOWN |",
    "| ST02 | road_trip_game_num_away ≥ 6 | UNDER |",
    "| ST03 | timezone_change_away ≥ 2 | UNDER |",
    "",
    "### Triage Results",
    "| Signal | Name | N | Best Bucket | Hit Rate | Mean Error | Mkt Corr | Year Stable | Verdict |",
    "|--------|------|---|-------------|----------|-----------|----------|-------------|---------|",
])

for r in results:
    bb = r["best_bucket"]
    if bb and bb[2] is not None and not np.isnan(bb[2]):
        bucket_str = bb[0]
        hr_str = f"{bb[2]:.3f}"
        me_str = f"{bb[3]:+.3f}" if bb[3] is not None and not np.isnan(bb[3]) else "N/A"
    else:
        bucket_str = "none"
        hr_str = "N/A"
        me_str = "N/A"

    # Verdict logic:
    # PROMOTE if: best_effect >= 0.10, year stable, not highly correlated with market
    effect = r["best_effect"]
    stable = r["year_stability"] == "STABLE"
    mkt_corr_val = r["market_corr"] if isinstance(r["market_corr"], float) else 0
    absorbed = abs(mkt_corr_val) > 0.3

    if effect >= 0.10 and stable and not absorbed:
        verdict = "**PROMOTE**"
    elif effect >= 0.05 and stable:
        verdict = "**MARGINAL**"
    elif effect < 0.03:
        verdict = "**SHELVE**"
    else:
        verdict = "**SHELVE**"

    report_lines.append(
        f"| {r['signal']} | {r['name']} | {r['N_nonpush']} | {bucket_str} | "
        f"{hr_str} | {me_str} | {r['market_corr']} | {r['year_stability']} | {verdict} |"
    )

    print(f"  {r['signal']} {r['name']:25s}  effect={effect:+.4f}  stable={r['year_stability']:8s}  "
          f"corr={r['market_corr']}  → {verdict}")

# ── Year detail ──────────────────────────────────────────────────────
report_lines.extend([
    "",
    "### Year-by-Year Detail",
    "",
])

for r in results:
    report_lines.append(f"**{r['signal']}: {r['name']}**")
    yr = r["year_results"]
    if r["signal"] in ["BF02", "ST02", "ST03"]:
        # Binary
        report_lines.append("| Year | Flag=1 N | Flag=1 Error | Flag=1 Under% | Flag=0 N | Flag=0 Error | Flag=0 Under% |")
        report_lines.append("|------|----------|-------------|--------------|----------|-------------|--------------|")
        for y in [2024, 2025]:
            d = yr.get(y, {})
            n1 = d.get("n_1", 0)
            n0 = d.get("n_0", 0)
            e1 = f"{d.get('err_1', 0):+.3f}" if not np.isnan(d.get("err_1", 0)) else "N/A"
            e0 = f"{d.get('err_0', 0):+.3f}" if not np.isnan(d.get("err_0", 0)) else "N/A"
            u1 = f"{d.get('ur_1', 0):.3f}" if not np.isnan(d.get("ur_1", 0)) else "N/A"
            u0 = f"{d.get('ur_0', 0):.3f}" if not np.isnan(d.get("ur_0", 0)) else "N/A"
            report_lines.append(f"| {y} | {n1} | {e1} | {u1} | {n0} | {e0} | {u0} |")
    else:
        # Continuous
        report_lines.append("| Year | N | Slope | p-value | Top20 Error | Bot20 Error |")
        report_lines.append("|------|---|-------|---------|------------|------------|")
        for y in [2024, 2025]:
            d = yr.get(y, {})
            n = d.get("n", 0)
            sl = f"{d.get('slope', 0):+.4f}" if "slope" in d else "N/A"
            pv = f"{d.get('p', 0):.4f}" if "p" in d else "N/A"
            te = f"{d.get('top20_err', 0):+.3f}" if "top20_err" in d else "N/A"
            be = f"{d.get('bot20_err', 0):+.3f}" if "bot20_err" in d else "N/A"
            report_lines.append(f"| {y} | {n} | {sl} | {pv} | {te} | {be} |")
    report_lines.append("")

# ── Write to scan_report.md ──────────────────────────────────────────
report_path = BASE / "scan_report.md"
with open(report_path, "a") as f:
    f.write("\n".join(report_lines) + "\n")

print(f"\nAppended to {report_path}")
