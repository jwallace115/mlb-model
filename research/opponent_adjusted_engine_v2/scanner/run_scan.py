#!/usr/bin/env python3
"""
V2 Engine Signal Scanner — Parts A through D.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
np.random.seed(42)

def roi_110(w, l):
    if w + l == 0: return np.nan
    return (w * 100/110 - l) / (w + l) * 100

# ── Load data ─────────────────────────────────────────────────────────
df = pd.read_parquet(BASE.parent / "signal_scanner_input.parquet")
df["game_date"] = pd.to_datetime(df["game_date"])
df_np = df[~df["is_push"]].copy()

print(f"Dataset: {len(df)} games, {len(df_np)} non-push")
print(f"V1 under (p>0.57): {(df['p_under'] > 0.57).sum()}")

# Source check
sc = [
    "# Source Check — V2 Signal Scanner",
    "",
    f"Input: research/opponent_adjusted_engine_v2/signal_scanner_input.parquet",
    f"Games: {len(df)} (2024: {(df.season==2024).sum()}, 2025: {(df.season==2025).sum()})",
    f"Non-push: {len(df_np)}",
    f"V1 under signals: {(df['p_under'] > 0.57).sum()}",
    "",
    "All required fields present: game_id, game_date, season, closing_total,",
    "market_residual, went_under, is_push, p_under, all 7 V2 signals.",
    "",
    "V1 trigger: p_under > 0.57 (same as prior research)",
]
with open(BASE / "source_check.md", "w") as f:
    f.write("\n".join(sc) + "\n")

SIGNALS = [
    "combined_adj_k_rate_last3",
    "combined_adj_bb_rate_last3",
    "combined_adj_contact_rate_last3",
    "combined_adj_hard_hit_last3",
    "combined_adj_run_suppression_last3",
    "adj_k_x_contact_last3",
    "adj_k_x_runsup_last3",
]

# Direction expectations:
# Higher adj_k_rate → pitcher dominates → UNDER
# Higher adj_bb_rate → pitcher walks more → OVER (negative for UNDER)
# Higher adj_contact_rate → pitcher suppresses contact → UNDER
# Higher adj_hard_hit → pitcher suppresses hard contact → UNDER
# Higher adj_run_suppression → pitcher prevents runs → UNDER
# Higher adj_k_x_contact → combined dominance → UNDER
# Higher adj_k_x_runsup → combined dominance → UNDER

# =====================================================================
# PART A — STANDALONE TRIAGE
# =====================================================================
print("\n" + "=" * 60)
print("PART A — STANDALONE TRIAGE")
print("=" * 60)

standalone_results = []

for sig in SIGNALS:
    print(f"\n--- {sig} ---")
    valid = df[sig].notna()
    valid_np = df_np[sig].notna() & df_np.index.isin(df[valid].index)

    # TEST 1 — Extremes
    buckets = []
    for label, lo_pct, hi_pct in [
        ("top_10", 90, 100), ("top_20", 80, 100),
        ("bot_10", 0, 10), ("bot_20", 0, 20),
    ]:
        lo_val = np.nanpercentile(df.loc[valid, sig], lo_pct)
        hi_val = np.nanpercentile(df.loc[valid, sig], hi_pct)
        if lo_pct == 0:
            mask = df_np.loc[valid_np, sig] <= hi_val
            mask_all = df.loc[valid, sig] <= hi_val
        else:
            mask = df_np.loc[valid_np, sig] > lo_val
            mask_all = df.loc[valid, sig] > lo_val

        n_np = mask.sum()
        n_all = mask_all.sum()
        if n_np < 40:
            buckets.append({"signal": sig, "bucket": label, "N": n_np,
                           "under_rate": np.nan, "resid": np.nan, "roi": np.nan})
            continue

        ur = df_np.loc[valid_np][mask]["went_under"].mean()
        resid = ur - 0.50
        w = df_np.loc[valid_np][mask]["went_under"].sum()
        roi = roi_110(w, n_np - w)
        me = df.loc[valid][mask_all]["market_residual"].mean()
        buckets.append({"signal": sig, "bucket": label, "N": n_np,
                       "under_rate": ur, "resid": resid, "roi": roi, "mean_resid": me})
        print(f"  {label}: N={n_np}, under%={ur:.3f}, resid={resid:+.3f}, ROI={roi:+.1f}%")

    # TEST 2 — Year stability
    year_stable = True
    best_tail = None
    best_tail_dir = None
    yr_results = {}
    for yr in [2024, 2025]:
        yr_df = df[(df["season"] == yr) & valid]
        yr_np = df_np[(df_np["season"] == yr) & valid_np]
        if len(yr_np) < 100:
            yr_results[yr] = {}
            continue

        # Check top 20% and bottom 20% residuals
        p80 = yr_df[sig].quantile(0.80)
        p20 = yr_df[sig].quantile(0.20)
        top_mask = yr_np[sig] > p80
        bot_mask = yr_np[sig] <= p20
        top_ur = yr_np.loc[top_mask, "went_under"].mean() if top_mask.sum() > 20 else np.nan
        bot_ur = yr_np.loc[bot_mask, "went_under"].mean() if bot_mask.sum() > 20 else np.nan
        top_resid = (top_ur - 0.50) if not np.isnan(top_ur) else np.nan
        bot_resid = (bot_ur - 0.50) if not np.isnan(bot_ur) else np.nan

        yr_results[yr] = {"top_resid": top_resid, "bot_resid": bot_resid,
                          "top_ur": top_ur, "bot_ur": bot_ur}

    # Determine best tail and stability
    if yr_results.get(2024) and yr_results.get(2025):
        r24 = yr_results[2024]
        r25 = yr_results[2025]
        # Check if top is consistently UNDER-favorable (positive resid)
        top_stable = (not np.isnan(r24.get("top_resid", np.nan)) and
                      not np.isnan(r25.get("top_resid", np.nan)) and
                      r24["top_resid"] > 0 and r25["top_resid"] > 0)
        bot_stable = (not np.isnan(r24.get("bot_resid", np.nan)) and
                      not np.isnan(r25.get("bot_resid", np.nan)) and
                      r24["bot_resid"] > 0 and r25["bot_resid"] > 0)
        if top_stable:
            best_tail = "top"
            year_stable = True
        elif bot_stable:
            best_tail = "bottom"
            year_stable = True
        else:
            year_stable = False
            # Pick best pooled tail
            pooled_top = [b for b in buckets if b["bucket"] == "top_20"]
            pooled_bot = [b for b in buckets if b["bucket"] == "bot_20"]
            if pooled_top and pooled_bot:
                t_roi = pooled_top[0].get("roi", -999)
                b_roi = pooled_bot[0].get("roi", -999)
                best_tail = "top" if (t_roi or -999) > (b_roi or -999) else "bottom"

    stability_str = "STABLE" if year_stable else "MIXED"
    print(f"  Stability: {stability_str}, best_tail={best_tail}")
    if yr_results.get(2024) and yr_results.get(2025):
        print(f"    2024: top_resid={yr_results[2024].get('top_resid', 'N/A')}, "
              f"bot_resid={yr_results[2024].get('bot_resid', 'N/A')}")
        print(f"    2025: top_resid={yr_results[2025].get('top_resid', 'N/A')}, "
              f"bot_resid={yr_results[2025].get('bot_resid', 'N/A')}")

    # TEST 3 — Market correlation
    corr_mask = valid & df["closing_total"].notna()
    r_corr, p_corr = stats.pearsonr(df.loc[corr_mask, sig], df.loc[corr_mask, "closing_total"])
    if abs(r_corr) < 0.15:
        corr_class = "CLEAN"
    elif abs(r_corr) < 0.30:
        corr_class = "PARTIAL"
    else:
        corr_class = "PRICED"
    print(f"  Market corr: r={r_corr:.4f} → {corr_class}")

    # STANDALONE VERDICT
    best_bucket = max(buckets, key=lambda b: b.get("roi", -999) if not np.isnan(b.get("roi", -999)) else -999)
    best_roi = best_bucket.get("roi", np.nan)
    best_n = best_bucket.get("N", 0)

    if (not np.isnan(best_roi) and best_roi > 3 and year_stable and corr_class != "PRICED"):
        verdict = "PROMOTE"
    elif (not np.isnan(best_roi) and best_roi > 0 and not (corr_class == "PRICED")):
        verdict = "INVESTIGATE"
    else:
        verdict = "SHELVE"

    standalone_results.append({
        "signal": sig, "best_bucket": best_bucket["bucket"],
        "best_roi": best_roi, "best_n": best_n,
        "best_under_rate": best_bucket.get("under_rate", np.nan),
        "stability": stability_str, "market_corr": r_corr,
        "corr_class": corr_class, "standalone_verdict": verdict,
        "buckets": buckets, "yr_results": yr_results,
    })
    print(f"  → Standalone: {verdict} (best={best_bucket['bucket']}, ROI={best_roi:+.1f}%)")


# =====================================================================
# PART B — V1 INTERACTION SCAN
# =====================================================================
print("\n" + "=" * 60)
print("PART B — V1 INTERACTION SCAN")
print("=" * 60)

df["v1_under"] = (df["p_under"] > 0.57).astype(int)
df_np["v1_under"] = (df_np["p_under"] > 0.57).astype(int)

# V1 baseline
v1_np = df_np[df_np["v1_under"] == 1]
v1_all = df[df["v1_under"] == 1]
v1_ur = v1_np["went_under"].mean()
v1_w = v1_np["went_under"].sum()
v1_roi = roi_110(v1_w, len(v1_np) - v1_w)
print(f"V1 baseline: N={len(v1_np)}, under%={v1_ur:.3f}, ROI={v1_roi:+.1f}%")

interaction_results = []

for sig in SIGNALS:
    print(f"\n--- {sig} ---")
    valid = df[sig].notna()
    valid_np = df_np[sig].notna()

    for label, lo_pct, hi_pct in [
        ("top_10", 90, 100), ("top_20", 80, 100), ("top_30", 70, 100),
        ("bot_10", 0, 10), ("bot_20", 0, 20), ("bot_30", 0, 30),
    ]:
        lo_val = np.nanpercentile(df.loc[valid, sig], lo_pct)
        hi_val = np.nanpercentile(df.loc[valid, sig], hi_pct)

        for year_label, yr_np, yr_all in [
            ("pooled", df_np, df),
            ("2024", df_np[df_np["season"] == 2024], df[df["season"] == 2024]),
            ("2025", df_np[df_np["season"] == 2025], df[df["season"] == 2025]),
        ]:
            # V1 + signal bucket
            if lo_pct == 0:
                sig_mask_np = (yr_np["v1_under"] == 1) & yr_np[sig].notna() & (yr_np[sig] <= hi_val)
                sig_mask_all = (yr_all["v1_under"] == 1) & yr_all[sig].notna() & (yr_all[sig] <= hi_val)
            else:
                sig_mask_np = (yr_np["v1_under"] == 1) & yr_np[sig].notna() & (yr_np[sig] > lo_val)
                sig_mask_all = (yr_all["v1_under"] == 1) & yr_all[sig].notna() & (yr_all[sig] > lo_val)

            # V1 baseline for this year
            v1_yr_np = yr_np[yr_np["v1_under"] == 1]
            v1_yr_ur = v1_yr_np["went_under"].mean() if len(v1_yr_np) > 0 else np.nan
            v1_yr_w = v1_yr_np["went_under"].sum()
            v1_yr_roi = roi_110(v1_yr_w, len(v1_yr_np) - v1_yr_w) if len(v1_yr_np) > 0 else np.nan

            n_sig = sig_mask_np.sum()
            if n_sig < 10:
                interaction_results.append({
                    "signal": sig, "bucket": label, "year": year_label,
                    "N": n_sig, "under_rate": np.nan, "roi": np.nan,
                    "v1_roi": v1_yr_roi, "lift_roi": np.nan, "lift_ur": np.nan,
                })
                continue

            sig_ur = yr_np.loc[sig_mask_np, "went_under"].mean()
            sig_w = yr_np.loc[sig_mask_np, "went_under"].sum()
            sig_roi = roi_110(sig_w, n_sig - sig_w)
            lift_roi = sig_roi - v1_yr_roi if not np.isnan(v1_yr_roi) else np.nan
            lift_ur = sig_ur - v1_yr_ur if not np.isnan(v1_yr_ur) else np.nan

            thin = n_sig < 50
            interaction_results.append({
                "signal": sig, "bucket": label, "year": year_label,
                "N": n_sig, "under_rate": sig_ur, "roi": sig_roi,
                "v1_roi": v1_yr_roi, "lift_roi": lift_roi, "lift_ur": lift_ur,
                "thin": thin,
            })

    # Print best pooled interaction
    pooled = [r for r in interaction_results if r["signal"] == sig and r["year"] == "pooled"
              and not np.isnan(r.get("lift_roi", np.nan))]
    if pooled:
        best = max(pooled, key=lambda r: r["lift_roi"])
        print(f"  Best V1 interaction: {best['bucket']}, N={best['N']}, "
              f"ROI={best['roi']:+.1f}%, lift={best['lift_roi']:+.1f}pp"
              f"{' (THIN)' if best.get('thin') else ''}")

int_df = pd.DataFrame(interaction_results)

# =====================================================================
# PART C — LEADERBOARD
# =====================================================================
print("\n" + "=" * 60)
print("PART C — LEADERBOARD")
print("=" * 60)

leaderboard = []
for sr in standalone_results:
    sig = sr["signal"]

    # Best V1 interaction (pooled)
    pooled_ints = int_df[(int_df["signal"] == sig) & (int_df["year"] == "pooled") &
                          int_df["lift_roi"].notna()]
    if len(pooled_ints) > 0:
        best_int = pooled_ints.loc[pooled_ints["lift_roi"].idxmax()]
        int_bucket = best_int["bucket"]
        int_lift = best_int["lift_roi"]
        int_n = best_int["N"]
        int_roi = best_int["roi"]

        # Year check
        y24 = int_df[(int_df["signal"] == sig) & (int_df["bucket"] == int_bucket) &
                      (int_df["year"] == "2024")]
        y25 = int_df[(int_df["signal"] == sig) & (int_df["bucket"] == int_bucket) &
                      (int_df["year"] == "2025")]
        l24 = y24["lift_roi"].values[0] if len(y24) > 0 and not np.isnan(y24["lift_roi"].values[0]) else np.nan
        l25 = y25["lift_roi"].values[0] if len(y25) > 0 and not np.isnan(y25["lift_roi"].values[0]) else np.nan

        # Interaction candidate check
        is_candidate = (int_lift > 3 and int_n >= 50 and
                        (not np.isnan(l24) and not np.isnan(l25) and
                         (l24 >= 0 or l25 >= 0)))
    else:
        int_bucket = "none"
        int_lift = np.nan
        int_n = 0
        int_roi = np.nan
        l24 = l25 = np.nan
        is_candidate = False

    # Final recommendation
    if sr["standalone_verdict"] == "PROMOTE" or is_candidate:
        rec = "PROMOTE to deep analysis"
    elif sr["standalone_verdict"] == "INVESTIGATE" or (not np.isnan(int_lift) and int_lift > 0):
        rec = "HOLD for monitoring"
    else:
        rec = "SHELVE"

    leaderboard.append({
        "signal": sig,
        "standalone_bucket": sr["best_bucket"],
        "standalone_roi": sr["best_roi"],
        "standalone_verdict": sr["standalone_verdict"],
        "v1_int_bucket": int_bucket,
        "v1_int_roi_lift": int_lift,
        "v1_int_N": int_n,
        "v1_int_roi": int_roi if not np.isnan(int_roi) else np.nan,
        "year_stability": sr["stability"],
        "market_corr_class": sr["corr_class"],
        "int_2024_lift": l24,
        "int_2025_lift": l25,
        "recommendation": rec,
    })

# Sort by interaction lift, then standalone ROI
lb_df = pd.DataFrame(leaderboard)
lb_df = lb_df.sort_values(["v1_int_roi_lift", "standalone_roi"], ascending=[False, False])
lb_df.to_parquet(BASE / "v2_signal_leaderboard.parquet", index=False)

print(f"\n{'Signal':<40} {'Stand ROI':>10} {'V1 Lift':>8} {'V1 N':>6} {'Stable':>7} {'Corr':>8} {'Rec'}")
print("-" * 100)
for _, row in lb_df.iterrows():
    sr = f"{row['standalone_roi']:+.1f}%" if not np.isnan(row['standalone_roi']) else "N/A"
    il = f"{row['v1_int_roi_lift']:+.1f}pp" if not np.isnan(row['v1_int_roi_lift']) else "N/A"
    print(f"{row['signal']:<40} {sr:>10} {il:>8} {row['v1_int_N']:>6.0f} "
          f"{row['year_stability']:>7} {row['market_corr_class']:>8} {row['recommendation']}")


# =====================================================================
# PART D — SAFETY CHECKS
# =====================================================================
print("\n" + "=" * 60)
print("PART D — SAFETY CHECKS")
print("=" * 60)

# Top 2 interaction candidates
top2 = lb_df.head(2)
safety_lines = []

for _, row in top2.iterrows():
    sig = row["signal"]
    bucket = row["v1_int_bucket"]
    print(f"\n--- {sig} ({bucket}) ---")
    safety_lines.append(f"\n### {sig} ({bucket})")

    # 1. Availability bias
    v1_games_np = df_np[df_np["v1_under"] == 1]
    avail = v1_games_np[sig].notna()
    unavail = ~avail
    for lbl, mask in [("AVAILABLE", avail), ("UNAVAILABLE", unavail)]:
        n = mask.sum()
        if n == 0: continue
        ur = v1_games_np.loc[mask, "went_under"].mean()
        w = v1_games_np.loc[mask, "went_under"].sum()
        roi = roi_110(w, n - w)
        avg_cl = df.loc[v1_games_np.loc[mask].index.intersection(df.index), "closing_total"].mean()
        print(f"  {lbl}: N={n}, under%={ur:.3f}, ROI={roi:+.1f}%, avg_close={avg_cl:.2f}")
        safety_lines.append(f"- {lbl}: N={n}, under%={ur:.3f}, ROI={roi:+.1f}%, avg_close={avg_cl:.2f}")

    bias = abs(v1_games_np.loc[avail, "went_under"].mean() -
               v1_games_np.loc[unavail, "went_under"].mean()) if unavail.sum() > 0 else 0
    safety_lines.append(f"- Availability bias: {bias:.3f} ({'CLEAN' if bias < 0.03 else 'WARNING'})")

    # 2. Thin tail warning
    pooled_best = int_df[(int_df["signal"] == sig) & (int_df["bucket"] == bucket) &
                          (int_df["year"] == "pooled")]
    if len(pooled_best) > 0:
        n_pooled = pooled_best["N"].values[0]
        if n_pooled < 75:
            print(f"  THIN TAIL WARNING: N={n_pooled} < 75")
            safety_lines.append(f"- **THIN TAIL WARNING**: N={n_pooled} < 75")
        else:
            safety_lines.append(f"- Tail size OK: N={n_pooled}")

    # 3. Direction reversal
    y24 = int_df[(int_df["signal"] == sig) & (int_df["bucket"] == bucket) & (int_df["year"] == "2024")]
    y25 = int_df[(int_df["signal"] == sig) & (int_df["bucket"] == bucket) & (int_df["year"] == "2025")]
    l24 = y24["lift_roi"].values[0] if len(y24) > 0 else np.nan
    l25 = y25["lift_roi"].values[0] if len(y25) > 0 else np.nan
    if not np.isnan(l24) and not np.isnan(l25) and l24 * l25 < 0:
        print(f"  DIRECTION REVERSAL: 2024={l24:+.1f}pp, 2025={l25:+.1f}pp")
        safety_lines.append(f"- **DIRECTION REVERSAL**: 2024={l24:+.1f}pp, 2025={l25:+.1f}pp")
    elif not np.isnan(l24) and not np.isnan(l25):
        safety_lines.append(f"- Direction consistent: 2024={l24:+.1f}pp, 2025={l25:+.1f}pp")


# =====================================================================
# SAVE RESULTS
# =====================================================================
# Machine-readable results
scan_rows = []
for sr in standalone_results:
    for b in sr["buckets"]:
        scan_rows.append({
            "signal": b["signal"], "bucket": b["bucket"],
            "N": b["N"], "under_rate": b.get("under_rate"),
            "resid": b.get("resid"), "roi": b.get("roi"),
            "stability": sr["stability"], "market_corr": sr["market_corr"],
            "corr_class": sr["corr_class"], "standalone_verdict": sr["standalone_verdict"],
        })
pd.DataFrame(scan_rows).to_parquet(BASE / "v2_signal_scan_results.parquet", index=False)


# =====================================================================
# WRITE REPORT
# =====================================================================
print("\n" + "=" * 60)
print("WRITING REPORT")
print("=" * 60)

R = []
R.append("# V2 Opponent-Adjusted Engine — Signal Scan Report")
R.append("")
R.append(f"Dataset: {len(df)} games (2024-2025), {len(df_np)} non-push")
R.append(f"V1 baseline: N={len(v1_np)}, under%={v1_ur:.3f}, ROI={v1_roi:+.1f}%")
R.append("")

# Part A
R.append("## Part A — Standalone Triage")
R.append("")
R.append("| Signal | Best Bucket | N | Under% | ROI | Stability | Mkt Corr | Verdict |")
R.append("|--------|------------|---|--------|-----|-----------|----------|---------|")
for sr in standalone_results:
    ur = f"{sr['best_under_rate']:.3f}" if not np.isnan(sr['best_under_rate']) else "N/A"
    roi = f"{sr['best_roi']:+.1f}%" if not np.isnan(sr['best_roi']) else "N/A"
    R.append(f"| {sr['signal']} | {sr['best_bucket']} | {sr['best_n']} | "
             f"{ur} | {roi} | {sr['stability']} | {sr['corr_class']} ({sr['market_corr']:.3f}) | "
             f"**{sr['standalone_verdict']}** |")
R.append("")

# Year detail for non-shelved
R.append("### Year Detail")
R.append("")
for sr in standalone_results:
    if sr["standalone_verdict"] != "SHELVE":
        R.append(f"**{sr['signal']}**")
        yr = sr["yr_results"]
        for y in [2024, 2025]:
            if y in yr and yr[y]:
                R.append(f"- {y}: top20 resid={yr[y].get('top_resid', 'N/A')}, "
                         f"bot20 resid={yr[y].get('bot_resid', 'N/A')}")
        R.append("")

# Part B
R.append("## Part B — V1 Interaction Scan")
R.append("")
R.append(f"V1 UNDER baseline: p_under > 0.57, N={len(v1_np)}, ROI={v1_roi:+.1f}%")
R.append("")

# Top interactions per signal
R.append("### Best V1 Interactions (pooled)")
R.append("")
R.append("| Signal | Bucket | N | Under% | ROI | V1 ROI | Lift | 2024 Lift | 2025 Lift |")
R.append("|--------|--------|---|--------|-----|--------|------|----------|----------|")
for _, row in lb_df.iterrows():
    sig = row["signal"]
    bucket = row["v1_int_bucket"]
    pooled = int_df[(int_df["signal"] == sig) & (int_df["bucket"] == bucket) & (int_df["year"] == "pooled")]
    if len(pooled) > 0 and not np.isnan(pooled["roi"].values[0]):
        p = pooled.iloc[0]
        l24 = f"{row['int_2024_lift']:+.1f}pp" if not np.isnan(row['int_2024_lift']) else "N/A"
        l25 = f"{row['int_2025_lift']:+.1f}pp" if not np.isnan(row['int_2025_lift']) else "N/A"
        thin = " (THIN)" if p.get("thin", False) or p["N"] < 50 else ""
        R.append(f"| {sig} | {bucket} | {p['N']}{thin} | {p['under_rate']:.3f} | "
                 f"{p['roi']:+.1f}% | {p['v1_roi']:+.1f}% | {p['lift_roi']:+.1f}pp | {l24} | {l25} |")
R.append("")

# Part C
R.append("## Part C — Leaderboard")
R.append("")
R.append("| Rank | Signal | Standalone | V1 Lift | V1 N | Stable | Corr | Recommendation |")
R.append("|------|--------|-----------|---------|------|--------|------|---------------|")
for i, (_, row) in enumerate(lb_df.iterrows()):
    sr = f"{row['standalone_roi']:+.1f}%" if not np.isnan(row['standalone_roi']) else "N/A"
    il = f"{row['v1_int_roi_lift']:+.1f}pp" if not np.isnan(row['v1_int_roi_lift']) else "N/A"
    R.append(f"| {i+1} | {row['signal']} | {sr} | {il} | {row['v1_int_N']:.0f} | "
             f"{row['year_stability']} | {row['market_corr_class']} | **{row['recommendation']}** |")
R.append("")

# Part D
R.append("## Part D — Safety Checks")
R.append("")
for line in safety_lines:
    R.append(line)
R.append("")

# Final answers
R.append("## Final Answers")
R.append("")

# Q1
promotes = [sr for sr in standalone_results if sr["standalone_verdict"] == "PROMOTE"]
investigates = [sr for sr in standalone_results if sr["standalone_verdict"] == "INVESTIGATE"]
R.append("### Q1: Which V2 signals show standalone value?")
if promotes:
    R.append(f"- PROMOTE: {', '.join(s['signal'] for s in promotes)}")
if investigates:
    R.append(f"- INVESTIGATE: {', '.join(s['signal'] for s in investigates)}")
shelved = [sr for sr in standalone_results if sr["standalone_verdict"] == "SHELVE"]
if shelved:
    R.append(f"- SHELVE: {', '.join(s['signal'] for s in shelved)}")
R.append("")

# Q2
candidates = lb_df[lb_df["v1_int_roi_lift"] > 3]
R.append("### Q2: Which V2 signals improve V1 UNDER?")
if len(candidates) > 0:
    for _, c in candidates.iterrows():
        R.append(f"- {c['signal']} ({c['v1_int_bucket']}): +{c['v1_int_roi_lift']:.1f}pp lift, N={c['v1_int_N']:.0f}")
else:
    R.append("- No signal provides >3pp lift at N≥50")
R.append("")

# Q3
R.append("### Q3: Strongest interaction candidate?")
if len(lb_df) > 0 and not np.isnan(lb_df.iloc[0]["v1_int_roi_lift"]):
    top = lb_df.iloc[0]
    R.append(f"- **{top['signal']}** ({top['v1_int_bucket']}): "
             f"+{top['v1_int_roi_lift']:.1f}pp lift, ROI={top.get('v1_int_roi', 0):+.1f}%")
else:
    R.append("- None strong enough")
R.append("")

# Q4
R.append("### Q4: Classification")
R.append("")
R.append("| Signal | Classification | Reason |")
R.append("|--------|---------------|--------|")
for _, row in lb_df.iterrows():
    R.append(f"| {row['signal']} | **{row['recommendation']}** | "
             f"standalone={row['standalone_verdict']}, V1_lift={row['v1_int_roi_lift']:+.1f}pp, "
             f"stable={row['year_stability']}, corr={row['market_corr_class']} |"
             if not np.isnan(row['v1_int_roi_lift']) else
             f"| {row['signal']} | **{row['recommendation']}** | no interaction data |")
R.append("")

# Recommended next deep analysis
R.append("## Recommended Next Deep Analysis Candidates")
R.append("")
promoted = lb_df[lb_df["recommendation"].str.contains("PROMOTE")]
if len(promoted) > 0:
    for i, (_, row) in enumerate(promoted.head(3).iterrows()):
        R.append(f"{i+1}. **{row['signal']}** — V1 lift {row['v1_int_roi_lift']:+.1f}pp, "
                 f"standalone {row['standalone_roi']:+.1f}%, {row['year_stability']}")
else:
    held = lb_df[lb_df["recommendation"].str.contains("HOLD")]
    if len(held) > 0:
        R.append("No signals strong enough for immediate deep analysis.")
        R.append("Candidates for future monitoring:")
        for i, (_, row) in enumerate(held.head(3).iterrows()):
            il = f"{row['v1_int_roi_lift']:+.1f}pp" if not np.isnan(row['v1_int_roi_lift']) else "N/A"
            R.append(f"{i+1}. {row['signal']} — V1 lift {il}, {row['year_stability']}")
    else:
        R.append("No signals strong enough for deep analysis or monitoring.")
        R.append("The V2 engine expansion did not produce actionable signal candidates.")
R.append("")

out_path = BASE / "v2_signal_scan_report.md"
with open(out_path, "w") as f:
    f.write("\n".join(R) + "\n")
print(f"Saved: {out_path}")
print("Done.")
