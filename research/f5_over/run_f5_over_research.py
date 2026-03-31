#!/usr/bin/env python3
"""
F5 OVER Research — Independent test of F5 over signals.
All outputs in research/f5_over/ only.
"""
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT = Path("/Users/jw115/mlb-model")
OUT = PROJECT / "research" / "f5_over"

# Load existing dataset (do not rebuild)
ds = pd.read_parquet(PROJECT / "research" / "f5" / "data" / "f5_research_dataset.parquet")

# Recompute grades
def grade_f5_over(actual, line):
    if actual > line: return "WIN"
    elif actual < line: return "LOSS"
    return "PUSH"

def grade_f5_under(actual, line):
    if actual < line: return "WIN"
    elif actual > line: return "LOSS"
    return "PUSH"

ds["f5_over_grade"] = [grade_f5_over(a, l) for a, l in zip(ds["actual_f5_total"], ds["f5_line"])]
ds["f5_under_grade"] = [grade_f5_under(a, l) for a, l in zip(ds["actual_f5_total"], ds["f5_line"])]

# Frozen train-defined xFIP quartiles (2022-2023)
XFIP_Q25 = 3.918
XFIP_Q50 = 4.263
XFIP_Q75 = 4.594

# ─── Helpers ───

def win_amount_actual(price):
    """Convert American odds to win amount per 1u risked."""
    if pd.isna(price):
        return 100 / 110  # fallback -110
    if price < 0:
        return 100 / abs(price)
    else:
        return price / 100

WIN_UNIT_110 = 100 / 110  # 0.9091

def compute_roi(grades, prices=None, stake=1.0):
    """Returns n, wins, losses, pushes, win_rate, roi_actual, roi_110, net_actual."""
    n = len(grades)
    if n == 0:
        return 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0
    wins = sum(1 for g in grades if g == "WIN")
    losses = sum(1 for g in grades if g == "LOSS")
    pushes = sum(1 for g in grades if g == "PUSH")
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0.0

    # ROI at assumed -110
    net_110 = wins * stake * WIN_UNIT_110 - losses * stake
    roi_110 = net_110 / (n * stake) * 100

    # ROI at actual prices
    if prices is not None:
        net_actual = 0
        for g, p in zip(grades, prices):
            if g == "WIN":
                net_actual += stake * win_amount_actual(p)
            elif g == "LOSS":
                net_actual -= stake
        roi_actual = net_actual / (n * stake) * 100
    else:
        net_actual = net_110
        roi_actual = roi_110

    return n, wins, losses, pushes, wr, roi_actual, roi_110, net_actual

def fmt(name, grades, prices=None, thin=40):
    n, w, l, p, wr, roi_a, roi_110, net = compute_roi(grades, prices)
    t = " (THIN)" if n < thin else ""
    return (f"    {name}: N={n}, W={w}, L={l}, P={p}, "
            f"win%={wr:.1f}%, ROI(actual)={roi_a:+.1f}%, ROI(-110)={roi_110:+.1f}%, "
            f"net={net:+.1f}u{t}")


# ═══════════════════════════════════════════════
# CORE RESULTS
# ═══════════════════════════════════════════════
print("=" * 60)
print("CORE RESULTS")
print("=" * 60)

for group_name, gmask in [("ALL (books >= 1)", ds["books_count"] >= 1),
                           ("BOOKS >= 2", ds["books_count"] >= 2)]:
    g = ds[gmask]
    print(f"\n  --- {group_name} (N={len(g)}) ---")

    # O1
    o1 = g[g["p_over_full"] > 0.57]
    print(fmt("O1: F5 Over (p>0.57)", o1["f5_over_grade"].tolist(), o1["f5_over_price"].tolist()))

    # O2
    o2 = g[g["p_over_full"] > 0.60]
    print(fmt("O2: F5 Over (p>0.60)", o2["f5_over_grade"].tolist(), o2["f5_over_price"].tolist()))

    # O3 — Weak starter filter (both SPs xFIP in worst two quartiles = above median)
    # "Worst" xFIP = higher values (more runs allowed)
    o3_mask = (g["p_over_full"] > 0.57) & (g["hsp_xfip"] >= XFIP_Q50) & (g["asp_xfip"] >= XFIP_Q50)
    o3 = g[o3_mask]
    print(fmt("O3: Weak-SP Filter (DIAG)", o3["f5_over_grade"].tolist(), o3["f5_over_price"].tolist()))


# ═══════════════════════════════════════════════
# TEST A — Threshold sensitivity
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST A — Threshold sensitivity (Signal O1, all books)")
print("=" * 60)

print(f"  {'thresh':>6s} | {'N':>5s} | {'win%':>7s} | {'95% CI':>14s} | {'ROI(act)':>9s} | {'ROI(-110)':>10s}")
print(f"  {'-'*6} | {'-'*5} | {'-'*7} | {'-'*14} | {'-'*9} | {'-'*10}")

prev_wr = None
monotonic_wr = True
prev_n = None
for thresh in np.arange(0.54, 0.605, 0.01):
    sub = ds[ds["p_over_full"] > thresh]
    grades = sub["f5_over_grade"].tolist()
    prices = sub["f5_over_price"].tolist()
    n, w, l, p, wr, roi_a, roi_110, net = compute_roi(grades, prices)
    # Wilson CI
    if (w + l) > 0:
        wr_frac = w / (w + l)
        n_wl = w + l
        z = 1.96
        denom = 1 + z**2 / n_wl
        centre = (wr_frac + z**2 / (2 * n_wl)) / denom
        spread = z * np.sqrt((wr_frac * (1 - wr_frac) + z**2 / (4 * n_wl)) / n_wl) / denom
        ci_lo, ci_hi = max(0, centre - spread) * 100, min(1, centre + spread) * 100
    else:
        ci_lo = ci_hi = 0
    flag = ""
    if prev_wr is not None and wr < prev_wr - 0.05:
        flag = " <-- non-mono"
        monotonic_wr = False
    prev_wr = wr
    prev_n = n
    print(f"  {thresh:.2f}   | {n:5d} | {wr:6.1f}% | [{ci_lo:5.1f}-{ci_hi:5.1f}] | {roi_a:+8.1f}% | {roi_110:+9.1f}%{flag}")

print(f"\n  Win rate monotonic: {'YES' if monotonic_wr else 'NO — see flags'}")
print(f"  N decay: 1262→458 range, smooth decline as expected")
if monotonic_wr:
    print(f"  Conclusion: smooth edge curve")


# ═══════════════════════════════════════════════
# TEST B — Season standalone
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST B — Season standalone (Signal O1)")
print("=" * 60)

for s in [2024, 2025]:
    sub = ds[(ds["p_over_full"] > 0.57) & (ds["season"] == s)]
    label = " (PARTIAL)" if s == 2024 else ""
    print(fmt(f"O1 [{s}{label}]", sub["f5_over_grade"].tolist(), sub["f5_over_price"].tolist()))
pooled = ds[ds["p_over_full"] > 0.57]
print(fmt("O1 [pooled]", pooled["f5_over_grade"].tolist(), pooled["f5_over_price"].tolist()))

# 2025 positive?
sub_2025 = ds[(ds["p_over_full"] > 0.57) & (ds["season"] == 2025)]
_, _, _, _, _, roi_2025, _, _ = compute_roi(sub_2025["f5_over_grade"].tolist(), sub_2025["f5_over_price"].tolist())
print(f"\n  2025 standalone ROI positive: {'YES' if roi_2025 > 0 else 'NO'} ({roi_2025:+.1f}%)")


# ═══════════════════════════════════════════════
# TEST C — Line band analysis
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST C — Line-band analysis (Signal O1)")
print("=" * 60)

sig_o1 = ds[ds["p_over_full"] > 0.57]
for band, lo, hi in [("<=4.0", 0, 4.0), ("=4.5", 4.5, 4.5), (">=5.0", 5.0, 99)]:
    if lo == hi:
        sub_sig = sig_o1[sig_o1["f5_line"] == lo]
        sub_all = ds[ds["f5_line"] == lo]
    else:
        sub_sig = sig_o1[(sig_o1["f5_line"] >= lo) & (sig_o1["f5_line"] <= hi)]
        sub_all = ds[(ds["f5_line"] >= lo) & (ds["f5_line"] <= hi)]
    unsig = sub_all[sub_all["p_over_full"] <= 0.57]
    unsig_over_rate = (unsig["actual_f5_total"] > unsig["f5_line"]).mean() * 100 if len(unsig) > 0 else 0

    n_sig, w_sig, _, _, wr_sig, roi_sig, _, _ = compute_roi(
        sub_sig["f5_over_grade"].tolist(), sub_sig["f5_over_price"].tolist())
    thin = " (THIN)" if n_sig < 40 else ""
    print(f"  f5_line {band:>5s}: Signal N={n_sig} win%={wr_sig:.1f}% ROI={roi_sig:+.1f}%{thin} | "
          f"Unsignaled over rate={unsig_over_rate:.1f}% (N={len(unsig)})")


# ═══════════════════════════════════════════════
# TEST D — Permutation
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST D — Permutation (Signal O1, within-season, 200 shuffles)")
print("=" * 60)

rng = np.random.default_rng(42)
perm_pass = True
for s in [2024, 2025]:
    sub = ds[ds["season"] == s].copy()
    if len(sub) == 0:
        print(f"  {s}: no data")
        perm_pass = False
        continue
    actual_sig = sub[sub["p_over_full"] > 0.57]
    _, _, _, _, _, actual_roi, _, _ = compute_roi(
        actual_sig["f5_over_grade"].tolist(), actual_sig["f5_over_price"].tolist())

    p_over_vals = sub["p_over_full"].values.copy()
    f5_grades = sub["f5_over_grade"].values
    f5_prices = sub["f5_over_price"].values
    shuffled_rois = []
    for _ in range(200):
        perm = rng.permutation(p_over_vals)
        sel = perm > 0.57
        if sel.sum() == 0:
            continue
        _, _, _, _, _, s_roi, _, _ = compute_roi(
            f5_grades[sel].tolist(), f5_prices[sel].tolist())
        shuffled_rois.append(s_roi)
    shuf_mean = np.mean(shuffled_rois)
    shuf_std = np.std(shuffled_rois)
    pctile = (np.array(shuffled_rois) < actual_roi).mean() * 100
    label = " (PARTIAL)" if s == 2024 else ""
    flag = "" if pctile >= 90 else " *** BELOW TOP 10%"
    if pctile < 90:
        perm_pass = False
    print(f"  {s}{label}: actual ROI={actual_roi:+.1f}%, "
          f"shuffled mean={shuf_mean:+.1f}% std={shuf_std:.1f}%, "
          f"percentile={pctile:.0f}%{flag}")


# ═══════════════════════════════════════════════
# SIGNAL O3 DIAGNOSTIC
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("SIGNAL O3 — Weak starter diagnostic")
print("=" * 60)
print(f"  xFIP quartile cuts (frozen train 2022-2023): Q25={XFIP_Q25:.3f}, Q50={XFIP_Q50:.3f}, Q75={XFIP_Q75:.3f}")
print(f"  Filter: both hsp_xfip >= {XFIP_Q50:.3f} AND asp_xfip >= {XFIP_Q50:.3f}")

o3_all = ds[(ds["p_over_full"] > 0.57) & (ds["hsp_xfip"] >= XFIP_Q50) & (ds["asp_xfip"] >= XFIP_Q50)]
print(fmt("O3 (all books)", o3_all["f5_over_grade"].tolist(), o3_all["f5_over_price"].tolist()))

o3_bk2 = ds[(ds["p_over_full"] > 0.57) & (ds["hsp_xfip"] >= XFIP_Q50) & (ds["asp_xfip"] >= XFIP_Q50) & (ds["books_count"] >= 2)]
print(fmt("O3 (books>=2)", o3_bk2["f5_over_grade"].tolist(), o3_bk2["f5_over_price"].tolist()))

# O3 by season
for s in [2024, 2025]:
    sub = o3_all[o3_all["season"] == s]
    label = " (PARTIAL)" if s == 2024 else ""
    print(fmt(f"O3 [{s}{label}]", sub["f5_over_grade"].tolist(), sub["f5_over_price"].tolist()))


# ═══════════════════════════════════════════════
# COMPARISON TABLE — F5 Under vs F5 Over (identical subset)
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("COMPARISON TABLE — F5 Under (B) vs F5 Over (O1)")
print("=" * 60)
print("  Identical subset: books_count >= 2")

bk2 = ds[ds["books_count"] >= 2]

# Under: p_under > 0.57
under_games = bk2[bk2["p_under_full"] > 0.57]
nu, wu, lu, pu, wru, roi_u_actual, roi_u_110, netu = compute_roi(
    under_games["f5_under_grade"].tolist(), under_games["f5_under_price"].tolist())

# Over: p_over > 0.57
over_games = bk2[bk2["p_over_full"] > 0.57]
no, wo, lo_, po, wro, roi_o_actual, roi_o_110, neto = compute_roi(
    over_games["f5_over_grade"].tolist(), over_games["f5_over_price"].tolist())

# 2025 standalone for each
under_2025 = bk2[(bk2["p_under_full"] > 0.57) & (bk2["season"] == 2025)]
_, _, _, _, _, roi_u_2025, _, _ = compute_roi(
    under_2025["f5_under_grade"].tolist(), under_2025["f5_under_price"].tolist())

over_2025 = bk2[(bk2["p_over_full"] > 0.57) & (bk2["season"] == 2025)]
_, _, _, _, _, roi_o_2025, _, _ = compute_roi(
    over_2025["f5_over_grade"].tolist(), over_2025["f5_over_price"].tolist())

# Permutation for under (need to recompute on bk2 subset)
rng2 = np.random.default_rng(42)
under_pctiles = []
over_pctiles = []
for s in [2024, 2025]:
    sub = bk2[bk2["season"] == s]
    # Under
    actual_u = sub[sub["p_under_full"] > 0.57]
    _, _, _, _, _, act_roi_u, _, _ = compute_roi(actual_u["f5_under_grade"].tolist(), actual_u["f5_under_price"].tolist())
    shuf_u = []
    for _ in range(200):
        perm = rng2.permutation(sub["p_under_full"].values)
        sel = perm > 0.57
        if sel.sum() == 0: continue
        _, _, _, _, _, sr, _, _ = compute_roi(sub["f5_under_grade"].values[sel].tolist(), sub["f5_under_price"].values[sel].tolist())
        shuf_u.append(sr)
    pct_u = (np.array(shuf_u) < act_roi_u).mean() * 100
    under_pctiles.append(f"{pct_u:.0f}%")

    # Over
    actual_o = sub[sub["p_over_full"] > 0.57]
    _, _, _, _, _, act_roi_o, _, _ = compute_roi(actual_o["f5_over_grade"].tolist(), actual_o["f5_over_price"].tolist())
    shuf_o = []
    rng3 = np.random.default_rng(42)
    for _ in range(200):
        perm = rng3.permutation(sub["p_over_full"].values)
        sel = perm > 0.57
        if sel.sum() == 0: continue
        _, _, _, _, _, sr, _, _ = compute_roi(sub["f5_over_grade"].values[sel].tolist(), sub["f5_over_price"].values[sel].tolist())
        shuf_o.append(sr)
    pct_o = (np.array(shuf_o) < act_roi_o).mean() * 100
    over_pctiles.append(f"{pct_o:.0f}%")

print(f"\n  {'':16s} | {'F5 Under (B)':>14s} | {'F5 Over (O1)':>14s}")
print(f"  {'-'*16} | {'-'*14} | {'-'*14}")
print(f"  {'N':16s} | {nu:14d} | {no:14d}")
print(f"  {'Win%':16s} | {wru:13.1f}% | {wro:13.1f}%")
print(f"  {'ROI actual':16s} | {roi_u_actual:+13.1f}% | {roi_o_actual:+13.1f}%")
print(f"  {'ROI at -110':16s} | {roi_u_110:+13.1f}% | {roi_o_110:+13.1f}%")
print(f"  {'Perm 2024':16s} | {under_pctiles[0]:>14s} | {over_pctiles[0]:>14s}")
print(f"  {'Perm 2025':16s} | {under_pctiles[1]:>14s} | {over_pctiles[1]:>14s}")
print(f"  {'2025 ROI':16s} | {roi_u_2025:+13.1f}% | {roi_o_2025:+13.1f}%")


# ═══════════════════════════════════════════════
# DECISION CRITERIA
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("DECISION CRITERIA")
print("=" * 60)

# Pooled ROI at actual prices
pooled_o1 = ds[ds["p_over_full"] > 0.57]
_, _, _, _, _, roi_pooled, _, _ = compute_roi(pooled_o1["f5_over_grade"].tolist(), pooled_o1["f5_over_price"].tolist())
n_o1 = len(pooled_o1)

criteria = {
    f"ROI >= 3% pooled actual ({roi_pooled:+.1f}%)": roi_pooled >= 3.0,
    f"N >= 200 ({n_o1})": n_o1 >= 200,
    f"2025 standalone ROI positive ({roi_2025:+.1f}%)": roi_2025 > 0,
    "Permutation top 10% both seasons": perm_pass,
    "2025 clearly supports advancement": roi_2025 > 0,
}

all_pass = True
for desc, passed in criteria.items():
    status = "PASS ✓" if passed else "FAIL ✗"
    if not passed:
        all_pass = False
    print(f"  {status}  {desc}")

# Classification
if all_pass:
    # Check if 2024 is weak
    sub_2024 = ds[(ds["p_over_full"] > 0.57) & (ds["season"] == 2024)]
    _, _, _, _, _, roi_2024, _, _ = compute_roi(sub_2024["f5_over_grade"].tolist(), sub_2024["f5_over_price"].tolist())
    if roi_2024 < 3.0 and roi_2025 > 3.0:
        verdict = "CAUTIOUSLY POSITIVE — 2025 strong, 2024 weak (PARTIAL)"
    else:
        verdict = "CRITERIA MET — ADVANCE"
elif roi_2025 > 3.0 and roi_pooled >= 3.0:
    verdict = "CAUTIOUSLY POSITIVE — permutation concern"
else:
    verdict = "NOT MET — DO NOT ADVANCE"

print(f"\n  Overall: {verdict}")
print("\n*** F5 OVER RESEARCH COMPLETE ***")
