#!/usr/bin/env python3
"""
YRFI/NRFI Full Research — 2024 train, 2025 holdout.
All output in research/yrfi/ only.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "yrfi"
WIN_110 = 100 / 110


# ── Helpers ──────────────────────────────────────────────────────────────────

def american_to_prob(price):
    if pd.isna(price): return np.nan
    p = float(price)
    return abs(p) / (abs(p) + 100) if p < 0 else 100 / (p + 100)


def american_to_win(price):
    """Net units won per 1u risked at American odds."""
    if pd.isna(price): return WIN_110
    p = float(price)
    return 100 / abs(p) if p < 0 else p / 100


def compute_roi(results, prices, stake=1.0):
    """results: array of 0/1 (win/loss). prices: American odds."""
    n = len(results)
    if n == 0:
        return 0, 0, 0, 0, 0, 0
    wins = int(results.sum())
    losses = n - wins
    wr = wins / n * 100

    # Actual price ROI
    net_actual = sum(stake * american_to_win(p) if r == 1 else -stake
                     for r, p in zip(results, prices))
    roi_actual = net_actual / (n * stake) * 100

    # -110 ROI
    net_110 = wins * stake * WIN_110 - losses * stake
    roi_110 = net_110 / (n * stake) * 100

    return n, wins, losses, wr, roi_actual, roi_110


def fmt(name, n, wr, roi_a, roi_110, act_rate, imp_rate, thin=40):
    t = " (THIN)" if n < thin else ""
    resid = act_rate - imp_rate
    return (f"    {name}: N={n}, rate={act_rate:.3f}, implied={imp_rate:.3f}, "
            f"resid={resid:+.3f}, ROI_actual={roi_a:+.1f}%, ROI_110={roi_110:+.1f}%{t}")


# ── SETUP ────────────────────────────────────────────────────────────────────

print("=" * 60)
print("YRFI RESEARCH — SETUP")
print("=" * 60)

lines = pd.read_parquet(OUT / "data" / "yrfi_lines_historical.parquet")
lines = lines[lines["pull_status"] == "ok"].copy()
lines["game_id"] = lines["game_id"].astype(str)

actuals = pd.read_parquet(OUT / "data" / "yrfi_actuals.parquet")
actuals = actuals[actuals["actuals_status"] == "ok"].copy()
actuals["game_id"] = actuals["game_id"].astype(str)

# Sim inputs
si24 = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_historical_2022_2024.parquet")
si24 = si24[si24["season"] == 2024]
si25 = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_2025.parquet")
si = pd.concat([si24, si25], ignore_index=True)
si["game_id"] = si["game_pk"].astype(str)

si_home = si[si["is_home"] == 1][["game_id", "sp_csw_pct", "sp_xfip", "sp_whiff_pct"]].rename(
    columns={"sp_csw_pct": "home_csw", "sp_xfip": "home_xfip", "sp_whiff_pct": "home_whiff"})
si_away = si[si["is_home"] == 0][["game_id", "sp_csw_pct", "sp_xfip", "sp_whiff_pct"]].rename(
    columns={"sp_csw_pct": "away_csw", "sp_xfip": "away_xfip", "sp_whiff_pct": "away_whiff"})

# BB% from pitcher game logs
pgl = pd.read_parquet(PROJECT / "mlb" / "data" / "pitcher_game_logs.parquet")
pgl_s = pgl[pgl["starter_flag"] == 1].copy()
pgl_s["game_id"] = pgl_s["game_pk"].astype(str)
pgl_s = pgl_s[pgl_s["season"].isin([2024, 2025])].sort_values(["player_id", "game_date"])

pgl_s["cum_bb"] = pgl_s.groupby(["player_id", "season"])["walks"].transform(
    lambda x: x.shift(1).expanding().sum())
pgl_s["cum_bf"] = pgl_s.groupby(["player_id", "season"])["batters_faced"].transform(
    lambda x: x.shift(1).expanding().sum())
pgl_s["bb_pct"] = (pgl_s["cum_bb"] / pgl_s["cum_bf"] * 100).clip(2, 20)

# Debug home_away values
print(f"  pgl_s home_away values: {pgl_s['home_away'].value_counts().to_dict()}")

# Try both possible key formats
for ha_val in ["home", "Home", "H", 1]:
    n = (pgl_s["home_away"] == ha_val).sum()
    if n > 0:
        print(f"  home_away == '{ha_val}': {n}")

# Use actual values
home_val = pgl_s[pgl_s["home_away"].isin(["home", "Home", "H", 1])]["home_away"].iloc[0] if len(pgl_s) > 0 else None
away_val = pgl_s[pgl_s["home_away"].isin(["away", "Away", "A", 0])]["home_away"].iloc[0] if len(pgl_s) > 0 else None
print(f"  Using home_away: home='{home_val}', away='{away_val}'")

if home_val is not None:
    bb_home = pgl_s[pgl_s["home_away"] == home_val][["game_id", "bb_pct"]].rename(
        columns={"bb_pct": "home_bb_pct"}).drop_duplicates("game_id")
    bb_away = pgl_s[pgl_s["home_away"] == away_val][["game_id", "bb_pct"]].rename(
        columns={"bb_pct": "away_bb_pct"}).drop_duplicates("game_id")
    print(f"  BB% home rows: {len(bb_home)}, away rows: {len(bb_away)}")
else:
    bb_home = pd.DataFrame(columns=["game_id", "home_bb_pct"])
    bb_away = pd.DataFrame(columns=["game_id", "away_bb_pct"])
    print("  BB% join FAILED — no matching home_away values")

# Join
df = lines.merge(actuals, on="game_id", how="inner", suffixes=("", "_a"))
df = df.merge(si_home, on="game_id", how="left")
df = df.merge(si_away, on="game_id", how="left")
df = df.merge(bb_home, on="game_id", how="left")
df = df.merge(bb_away, on="game_id", how="left")

df["season"] = df["date"].str[:4].astype(int)
df = df[df["season"].isin([2024, 2025])].copy()

# Compute probabilities
df["implied_yrfi"] = df["yrfi_over_price"].apply(american_to_prob)
df["implied_nrfi"] = df["nrfi_under_price"].apply(american_to_prob)
df["nrfi_result"] = 1 - df["yrfi_result"]
df["market_residual_yrfi"] = df["yrfi_result"] - df["implied_yrfi"]
df["market_residual_nrfi"] = df["nrfi_result"] - df["implied_nrfi"]

print(f"\n  Total joined: {len(df)}")
for yr in [2024, 2025]:
    print(f"  {yr}: {(df['season']==yr).sum()}")

bb_ok = df["home_bb_pct"].notna().sum()
print(f"\n  Null counts:")
print(f"    home_csw: {df['home_csw'].isna().sum()}/{len(df)}")
print(f"    away_csw: {df['away_csw'].isna().sum()}/{len(df)}")
print(f"    home_xfip: {df['home_xfip'].isna().sum()}/{len(df)}")
print(f"    away_xfip: {df['away_xfip'].isna().sum()}/{len(df)}")
print(f"    home_bb_pct: {df['home_bb_pct'].isna().sum()}/{len(df)}")
print(f"    away_bb_pct: {df['away_bb_pct'].isna().sum()}/{len(df)}")
print(f"  Actual YRFI rate: {df['yrfi_result'].mean():.4f}")
print(f"  Implied YRFI rate: {df['implied_yrfi'].mean():.4f}")

# Pitcher score (quartile cuts from 2024 only)
df["pitcher_score"] = (
    (df["home_csw"].fillna(27) + df["away_csw"].fillna(27)) / 2
    - 5 * ((df["home_xfip"].fillna(4.25) + df["away_xfip"].fillna(4.25)) / 2)
)
q4_cut = df[df["season"] == 2024]["pitcher_score"].quantile(0.75)
print(f"  Pitcher score Q4 cutpoint (from 2024): {q4_cut:.3f}")

# ── PRICE CALIBRATION ────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("PRICE CALIBRATION CURVE")
print("=" * 60)
bins = [-999, -140, -120, -105, 104, 120, 999]
labels = ["<=-140", "-139:-120", "-119:-105", "-104:+104", "+105:+120", ">=+121"]
df["price_bin"] = pd.cut(df["yrfi_over_price"], bins=bins, labels=labels, include_lowest=True)
print(f"  {'Bin':>12s} {'N':>5s} {'Imp':>7s} {'Act':>7s} {'Resid':>7s}")
for b in labels:
    sub = df[df["price_bin"] == b]
    if len(sub) == 0: continue
    print(f"  {b:>12s} {len(sub):5d} {sub['implied_yrfi'].mean():7.4f} "
          f"{sub['yrfi_result'].mean():7.4f} {sub['market_residual_yrfi'].mean():+6.4f}")


# ── PHASE 2: CORE BACKTEST ──────────────────────────────────────────────────

def run_signal(name, mask, side, price_col, df_in):
    """Run a signal and return results dict."""
    sub = df_in[mask]
    n = len(sub)
    if n == 0:
        return {"n": 0}

    if side == "YRFI":
        results = sub["yrfi_result"].values
        prices = sub["yrfi_over_price"].values
        act_rate = sub["yrfi_result"].mean()
        imp_rate = sub["implied_yrfi"].mean()
    else:
        results = sub["nrfi_result"].values
        prices = sub["nrfi_under_price"].values
        act_rate = sub["nrfi_result"].mean()
        imp_rate = sub["implied_nrfi"].mean()

    n, w, l, wr, roi_a, roi_110 = compute_roi(results, prices)
    return {"n": n, "w": w, "wr": wr, "roi_a": roi_a, "roi_110": roi_110,
            "act": act_rate, "imp": imp_rate, "resid": act_rate - imp_rate}


print("\n" + "=" * 60)
print("PHASE 2 — CORE BACKTEST")
print("=" * 60)

# Signal definitions
signals = {
    "A: Weak YRFI (xFIP>=4.5)": ("YRFI", (df["home_xfip"] >= 4.5) & (df["away_xfip"] >= 4.5)),
    "A+: Weak YRFI (xFIP>=4.8)": ("YRFI", (df["home_xfip"] >= 4.8) & (df["away_xfip"] >= 4.8)),
    "A++: Weak YRFI (xFIP>=5.0)": ("YRFI", (df["home_xfip"] >= 5.0) & (df["away_xfip"] >= 5.0)),
    "B: Elite NRFI (CSW>=28)": ("NRFI", (df["home_csw"] >= 28) & (df["away_csw"] >= 28)),
    "B+: Elite NRFI (CSW>=30)": ("NRFI", (df["home_csw"] >= 30) & (df["away_csw"] >= 30)),
    "C: Score Q4 NRFI": ("NRFI", df["pitcher_score"] >= q4_cut),
    "E: Market NRFI >0.57 (CTL)": ("NRFI", df["implied_nrfi"] > 0.57),
}

if bb_ok > 100:
    signals["D: High BB% YRFI (>=9)"] = ("YRFI", (df["home_bb_pct"] >= 9) & (df["away_bb_pct"] >= 9))
    signals["D-: High BB% YRFI (>=8)"] = ("YRFI", (df["home_bb_pct"] >= 8) & (df["away_bb_pct"] >= 8))

for group_name, books_min in [("ALL BOOKS", 1), ("BOOKS >= 3", 3)]:
    g = df[df["books_count"] >= books_min]
    print(f"\n  --- {group_name} (N={len(g)}) ---")

    for sig_name, (side, base_mask) in signals.items():
        mask = base_mask & (df["books_count"] >= books_min)
        price_col = "yrfi_over_price" if side == "YRFI" else "nrfi_under_price"

        parts = []
        for yr_label, yr_filter in [("2024", df["season"] == 2024),
                                     ("2025", df["season"] == 2025),
                                     ("pooled", pd.Series(True, index=df.index))]:
            r = run_signal(sig_name, mask & yr_filter, side, price_col, df)
            if r["n"] > 0:
                thin = " (THIN)" if r["n"] < 40 else ""
                parts.append(f'{yr_label}: N={r["n"]} rate={r["act"]:.3f} imp={r["imp"]:.3f} '
                             f'resid={r["resid"]:+.3f} ROI_act={r["roi_a"]:+.1f}% '
                             f'ROI_110={r["roi_110"]:+.1f}%{thin}')
            else:
                parts.append(f"{yr_label}: N=0")

        print(f"    {sig_name}")
        for p in parts:
            print(f"      {p}")


# ── PHASE 3: DIAGNOSTICS ────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 3 — DIAGNOSTICS")
print("=" * 60)

# 3A — Price band interaction
print("\n  3A — Price band interaction")
for sig_name, (side, base_mask) in [("A: Weak YRFI", ("YRFI", (df["home_xfip"] >= 4.5) & (df["away_xfip"] >= 4.5))),
                                     ("B: Elite NRFI", ("NRFI", (df["home_csw"] >= 28) & (df["away_csw"] >= 28)))]:
    print(f"    {sig_name}:")
    for band, lo, hi in [("favorite", -999, -120), ("near-even", -119, 104), ("underdog", 105, 999)]:
        if side == "YRFI":
            pmask = (df["yrfi_over_price"] >= lo) & (df["yrfi_over_price"] <= hi)
        else:
            pmask = (df["nrfi_under_price"] >= lo) & (df["nrfi_under_price"] <= hi)
        r = run_signal("", base_mask & pmask, side, "", df)
        if r["n"] > 0:
            thin = " (THIN)" if r["n"] < 40 else ""
            print(f"      {band}: N={r['n']} rate={r['act']:.3f} imp={r['imp']:.3f} "
                  f"resid={r['resid']:+.3f} ROI_110={r['roi_110']:+.1f}%{thin}")

# 3B — Park effects
print("\n  3B — Park effects")
from config import STADIUMS
park_factors = {abb: s["park_factor"] for abb, s in STADIUMS.items()}
df["park_rf"] = df["home_team"].map(park_factors).fillna(100)
df["park_tier"] = pd.cut(df["park_rf"], bins=[0, 98, 103, 999], labels=["low", "mid", "high"])

for sig_name, (side, base_mask) in [("A: Weak YRFI", ("YRFI", (df["home_xfip"] >= 4.5) & (df["away_xfip"] >= 4.5))),
                                     ("B: Elite NRFI", ("NRFI", (df["home_csw"] >= 28) & (df["away_csw"] >= 28)))]:
    print(f"    {sig_name}:")
    for tier in ["low", "mid", "high"]:
        r = run_signal("", base_mask & (df["park_tier"] == tier), side, "", df)
        if r["n"] > 0:
            thin = " (THIN)" if r["n"] < 40 else ""
            print(f"      park={tier}: N={r['n']} rate={r['act']:.3f} imp={r['imp']:.3f} "
                  f"resid={r['resid']:+.3f}{thin}")

# 3D — Temporal stability (2024 only)
print("\n  3D — Temporal stability (2024)")
df_24 = df[df["season"] == 2024].copy()
df_24["half"] = np.where(df_24["date"] < "2024-07-01", "H1", "H2")

for sig_name, (side, base_mask) in [("A: Weak YRFI", ("YRFI", (df["home_xfip"] >= 4.5) & (df["away_xfip"] >= 4.5))),
                                     ("B: Elite NRFI", ("NRFI", (df["home_csw"] >= 28) & (df["away_csw"] >= 28)))]:
    print(f"    {sig_name}:")
    mask_24 = base_mask & (df["season"] == 2024)
    for h in ["H1", "H2"]:
        hmask = mask_24 & (df_24.reindex(df.index, fill_value="").eq(h) if False else df["date"].apply(
            lambda d: "H1" if d < "2024-07-01" else "H2") == h)
        r = run_signal("", hmask, side, "", df)
        if r["n"] > 0:
            thin = " (THIN)" if r["n"] < 40 else ""
            print(f"      {h}: N={r['n']} rate={r['act']:.3f} ROI_110={r['roi_110']:+.1f}%{thin}")

# 3E — Permutation (2025 only)
print("\n  3E — Permutation (2025 only, 200 shuffles)")
rng = np.random.default_rng(42)
df_25 = df[df["season"] == 2025].copy()

for sig_name, (side, base_mask) in [("A: Weak YRFI", ("YRFI", (df["home_xfip"] >= 4.5) & (df["away_xfip"] >= 4.5))),
                                     ("B: Elite NRFI", ("NRFI", (df["home_csw"] >= 28) & (df["away_csw"] >= 28)))]:
    mask_25 = base_mask & (df["season"] == 2025)
    r = run_signal("", mask_25, side, "", df)
    if r["n"] == 0:
        print(f"    {sig_name}: N=0 in 2025")
        continue

    actual_roi = r["roi_110"]
    result_col = "yrfi_result" if side == "YRFI" else "nrfi_result"
    outcomes_25 = df_25[result_col].values.copy()

    shuffled_rois = []
    for _ in range(200):
        perm = rng.permutation(outcomes_25)
        # Apply same mask indices
        sel = mask_25[df["season"] == 2025].values
        if sel.sum() == 0:
            continue
        w = perm[sel].sum()
        l = sel.sum() - w
        sr = (w * WIN_110 - l) / sel.sum() * 100
        shuffled_rois.append(sr)

    pctile = (np.array(shuffled_rois) < actual_roi).mean() * 100
    flag = "" if pctile >= 90 else " *** BELOW TOP 10%"
    print(f"    {sig_name}: actual ROI_110={actual_roi:+.1f}%, shuffled mean={np.mean(shuffled_rois):+.1f}%, "
          f"percentile={pctile:.0f}%{flag}")


# ── DECISION CRITERIA ────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("DECISION CRITERIA")
print("=" * 60)

for sig_name, (side, base_mask) in signals.items():
    if "CTL" in sig_name:
        continue
    price_col = "yrfi_over_price" if side == "YRFI" else "nrfi_under_price"

    r_pool = run_signal("", base_mask, side, price_col, df)
    r_2025 = run_signal("", base_mask & (df["season"] == 2025), side, price_col, df)

    if r_pool["n"] == 0:
        print(f"  {sig_name}: N=0 — SKIP")
        continue

    c1 = r_pool["roi_a"] >= 2.0
    c2 = r_pool["n"] >= 150
    c3 = r_2025["n"] > 0 and r_2025["roi_a"] > 0
    # c4 (permutation) and c5 (not mixed) evaluated above

    status = "PASS" if (c1 and c2 and c3) else "FAIL"
    print(f"  {sig_name}:")
    print(f"    ROI >= 2% pooled actual: {r_pool['roi_a']:+.1f}% {'✓' if c1 else '✗'}")
    print(f"    N >= 150: {r_pool['n']} {'✓' if c2 else '✗'}")
    print(f"    2025 ROI positive: {r_2025['roi_a']:+.1f}% {'✓' if c3 else '✗'}")
    print(f"    Preliminary: {status}")

print("\n*** YRFI RESEARCH COMPLETE ***")
