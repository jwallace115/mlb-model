#!/usr/bin/env python3
"""
F5 Run Line Research — Full backtest.
Train: 2024, Holdout: 2025.
All output in research/f5_runline/ only.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "f5_runline"


# ── Helpers ──────────────────────────────────────────────────────────────────

def american_to_prob(price):
    if pd.isna(price): return np.nan
    p = float(price)
    return abs(p) / (abs(p) + 100) if p < 0 else 100 / (p + 100)


def american_to_win(price):
    if pd.isna(price): return 100 / 110
    p = float(price)
    return 100 / abs(p) if p < 0 else p / 100


WIN_110 = 100 / 110


def compute_roi(results, prices, push_mask):
    """results: 1=win, 0=loss. push_mask: True=push. All same length."""
    n = len(results)
    if n == 0:
        return {"n": 0, "n_nonpush": 0, "wins": 0, "wr": 0, "push_rate": 0,
                "roi_actual": 0, "roi_110": 0, "net_actual": 0}

    wins = int((results == 1).sum())
    losses = int((results == 0).sum())
    pushes = int(push_mask.sum())
    n_nonpush = wins + losses
    wr = wins / n_nonpush * 100 if n_nonpush > 0 else 0

    # Actual price ROI
    net_actual = 0
    for r, p, is_push in zip(results, prices, push_mask):
        if is_push:
            net_actual += 0
        elif r == 1:
            net_actual += american_to_win(p)
        else:
            net_actual -= 1.0
    roi_actual = net_actual / n * 100

    # -110 ROI
    net_110 = wins * WIN_110 - losses * 1.0
    roi_110 = net_110 / n * 100

    return {"n": n, "n_nonpush": n_nonpush, "wins": wins, "wr": round(wr, 1),
            "push_rate": round(pushes / n * 100, 1),
            "roi_actual": round(roi_actual, 1), "roi_110": round(roi_110, 1),
            "net_actual": round(net_actual, 2)}


def fmt_signal(name, r, imp_wr=None, thin=40):
    t = " (THIN)" if r["n"] < thin else ""
    imp_s = f" imp={imp_wr:.1f}%" if imp_wr is not None else ""
    resid_s = ""
    if imp_wr is not None and r["wr"] > 0:
        resid_s = f" resid={r['wr'] - imp_wr:+.1f}pp"
    return (f"    {name}: N={r['n']} (nonpush={r['n_nonpush']}) wr={r['wr']:.1f}%{imp_s}{resid_s} "
            f"push={r['push_rate']:.1f}% ROI_act={r['roi_actual']:+.1f}% "
            f"ROI_110={r['roi_110']:+.1f}%{t}")


# ── SETUP ────────────────────────────────────────────────────────────────────

print("=" * 60)
print("F5 RUN LINE RESEARCH — SETUP")
print("=" * 60)

lines = pd.read_parquet(OUT / "data" / "f5_runline_lines_historical.parquet")
lines = lines[lines["pull_status"] == "ok"].copy()
lines["game_id"] = lines["game_id"].astype(str)

scores = pd.read_parquet(OUT / "data" / "f5_scores.parquet")
scores = scores[scores["score_status"] == "ok"].copy()
scores["game_id"] = scores["game_id"].astype(str)

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

df = lines.merge(scores, on="game_id", how="inner", suffixes=("_l", "_s"))
df = df.merge(si_home, on="game_id", how="left")
df = df.merge(si_away, on="game_id", how="left")
df["season"] = df["date_l"].str[:4].astype(int)

print(f"  Total joined: {len(df)}")
for yr in [2024, 2025]:
    print(f"  {yr}: {(df['season']==yr).sum()}")
for col in ["home_csw", "away_csw", "home_xfip", "away_xfip", "home_whiff", "away_whiff"]:
    print(f"  {col} null: {df[col].isna().sum()}/{len(df)}")

# Derived variables
df["f5_margin"] = df["home_f5_score"] - df["away_f5_score"]
df["is_push"] = df["f5_margin"] == 0
df["f5_result"] = np.where(df["f5_margin"] > 0, 1, np.where(df["f5_margin"] < 0, 0, np.nan))
df["home_implied"] = df["home_price"].apply(american_to_prob)
df["away_implied"] = df["away_price"].apply(american_to_prob)

non_push = df[~df["is_push"]]
df["home_residual"] = np.nan
df.loc[~df["is_push"], "home_residual"] = non_push["f5_result"] - non_push["home_implied"]

print(f"\n  Push rate: {df['is_push'].mean()*100:.1f}%")
print(f"  Home win (non-push): {non_push['f5_result'].mean()*100:.1f}%")
print(f"  Mean home_implied: {df['home_implied'].mean()*100:.1f}%")

# Starter gaps
df["csw_gap"] = df["home_csw"] - df["away_csw"]
df["xfip_gap"] = df["away_xfip"] - df["home_xfip"]  # positive = home advantage
df["whiff_gap"] = df["home_whiff"] - df["away_whiff"]
df["starter_score"] = df["csw_gap"].fillna(0) * 100 + df["whiff_gap"].fillna(0) * 100 + df["xfip_gap"].fillna(0) * 2

# Q4 cutpoint from 2024 only
q4_cut = df[df["season"] == 2024]["starter_score"].quantile(0.75)
print(f"  Starter score Q4 cut (2024): {q4_cut:.2f}")


# ── PHASE 1: MARKET CALIBRATION ─────────────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 1 — MARKET CALIBRATION")
print("=" * 60)

bins = [-999, -160, -140, -120, -105, 104, 120, 999]
labels = ["<=-160", "-159:-140", "-139:-120", "-119:-105", "-104:+104", "+105:+120", ">=+121"]
df["price_bin"] = pd.cut(df["home_price"], bins=bins, labels=labels, include_lowest=True)

print(f"  {'Bin':>12s} {'N':>5s} {'Imp%':>6s} {'Act%':>6s} {'Push%':>6s} {'Resid':>7s}")
for b in labels:
    sub = df[df["price_bin"] == b]
    if len(sub) == 0: continue
    imp = sub["home_implied"].mean() * 100
    np_sub = sub[~sub["is_push"]]
    act = np_sub["f5_result"].mean() * 100 if len(np_sub) > 0 else 0
    push = sub["is_push"].mean() * 100
    resid = act - imp
    print(f"  {b:>12s} {len(sub):5d} {imp:5.1f}% {act:5.1f}% {push:5.1f}% {resid:+6.1f}pp")


# ── PHASE 2: STARTER MISMATCH SIGNALS ───────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 2 — STARTER MISMATCH SIGNALS")
print("=" * 60)

signal_defs = {
    "A: CSW gap>=4": ("home", df["csw_gap"] >= 4),
    "A_away: CSW gap<=-4": ("away", df["csw_gap"] <= -4),
    "B: xFIP gap>=1.0": ("home", df["xfip_gap"] >= 1.0),
    "B_away: xFIP gap<=-1.0": ("away", df["xfip_gap"] <= -1.0),
    "C: Whiff gap>=5": ("home", df["whiff_gap"] >= 5),
    "C_away: Whiff gap<=-5": ("away", df["whiff_gap"] <= -5),
    "D: Score Q4": ("home", df["starter_score"] >= q4_cut),
    "D_away: Score Q1": ("away", df["starter_score"] <= df[df["season"] == 2024]["starter_score"].quantile(0.25)),
}

for group_name, books_min in [("ALL BOOKS", 1), ("BOOKS >= 3", 3)]:
    g = df[df["books_count"] >= books_min]
    print(f"\n  --- {group_name} (N={len(g)}) ---")

    for sig_name, (side, base_mask) in signal_defs.items():
        for yr_label, yr_filter in [("2024", g["season"] == 2024),
                                     ("2025", g["season"] == 2025),
                                     ("pooled", pd.Series(True, index=g.index))]:
            mask = base_mask.reindex(g.index, fill_value=False) & yr_filter
            sub = g[mask]
            if len(sub) == 0:
                continue

            if side == "home":
                results = sub["f5_result"].values
                prices = sub["home_price"].values
                imp_wr = sub[~sub["is_push"]]["home_implied"].mean() * 100 if (~sub["is_push"]).sum() > 0 else 0
            else:
                results = np.where(sub["f5_margin"] > 0, 0, np.where(sub["f5_margin"] < 0, 1, np.nan))
                prices = sub["away_price"].values
                imp_wr = sub[~sub["is_push"]]["away_implied"].mean() * 100 if (~sub["is_push"]).sum() > 0 else 0

            push_mask = sub["is_push"].values
            # For ROI: replace NaN results with -1 (they're pushes, handled by push_mask)
            clean_results = np.where(np.isnan(results), -1, results)

            r = compute_roi(clean_results, prices, push_mask)
            if yr_label == "pooled":
                print(fmt_signal(f"{sig_name} [{yr_label}]", r, imp_wr))
            elif yr_label == "2025":
                print(fmt_signal(f"  {sig_name} [{yr_label}]", r, imp_wr))
            else:
                print(fmt_signal(f"  {sig_name} [{yr_label}]", r, imp_wr))


# ── PHASE 3: STARTER QUALITY DUELS ──────────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 3 — STARTER QUALITY DUELS")
print("=" * 60)

duel_defs = {
    "Elite duel (CSW>=28 both) → home": ("home",
        (df["home_csw"] >= 28) & (df["away_csw"] >= 28)),
    "Weak duel (xFIP>=4.5 both) → home": ("home",
        (df["home_xfip"] >= 4.5) & (df["away_xfip"] >= 4.5)),
    "Dominant home (h_csw>=28, a_csw<25)": ("home",
        (df["home_csw"] >= 28) & (df["away_csw"] < 25)),
    "Dominant away (a_csw>=28, h_csw<25)": ("away",
        (df["away_csw"] >= 28) & (df["home_csw"] < 25)),
}

for sig_name, (side, base_mask) in duel_defs.items():
    for yr_label, yr_filter in [("2024", df["season"] == 2024),
                                 ("2025", df["season"] == 2025),
                                 ("pooled", pd.Series(True, index=df.index))]:
        mask = base_mask & yr_filter
        sub = df[mask]
        if len(sub) == 0: continue

        if side == "home":
            results = sub["f5_result"].values
            prices = sub["home_price"].values
            imp_wr = sub[~sub["is_push"]]["home_implied"].mean() * 100 if (~sub["is_push"]).sum() > 0 else 0
        else:
            results = np.where(sub["f5_margin"] > 0, 0, np.where(sub["f5_margin"] < 0, 1, np.nan))
            prices = sub["away_price"].values
            imp_wr = sub[~sub["is_push"]]["away_implied"].mean() * 100 if (~sub["is_push"]).sum() > 0 else 0

        push_mask = sub["is_push"].values
        clean_results = np.where(np.isnan(results), -1, results)
        r = compute_roi(clean_results, prices, push_mask)
        if yr_label == "pooled":
            print(fmt_signal(f"{sig_name} [{yr_label}]", r, imp_wr))
        else:
            print(fmt_signal(f"  {sig_name} [{yr_label}]", r, imp_wr))


# ── PHASE 4: PRICE BAND INTERACTION ─────────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 4 — PRICE BAND INTERACTION")
print("=" * 60)

for sig_name, (side, base_mask) in list(signal_defs.items())[:4]:  # A, A_away, B, B_away
    print(f"  {sig_name}:")
    for band, lo, hi in [("favorite", -999, -120), ("near-even", -119, 104), ("underdog", 105, 999)]:
        if side == "home":
            pmask = (df["home_price"] >= lo) & (df["home_price"] <= hi)
        else:
            pmask = (df["away_price"] >= lo) & (df["away_price"] <= hi)
        sub = df[base_mask & pmask]
        if len(sub) == 0: continue

        if side == "home":
            results = sub["f5_result"].values
            prices = sub["home_price"].values
        else:
            results = np.where(sub["f5_margin"] > 0, 0, np.where(sub["f5_margin"] < 0, 1, np.nan))
            prices = sub["away_price"].values

        push_mask = sub["is_push"].values
        clean_results = np.where(np.isnan(results), -1, results)
        r = compute_roi(clean_results, prices, push_mask)
        thin = " (THIN)" if r["n"] < 40 else ""
        print(f"    {band}: N={r['n']} wr={r['wr']:.1f}% push={r['push_rate']:.1f}% "
              f"ROI_act={r['roi_actual']:+.1f}%{thin}")


# ── PHASE 5: TEMPORAL STABILITY ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 5 — TEMPORAL STABILITY (2024)")
print("=" * 60)

df["half"] = np.where(df["date_l"] < "2024-07-01", "H1", "H2")

for sig_name, (side, base_mask) in list(signal_defs.items())[:4]:
    mask_24 = base_mask & (df["season"] == 2024)
    sub = df[mask_24]
    if len(sub) < 20: continue

    print(f"  {sig_name}:")
    for h in ["H1", "H2"]:
        hsub = sub[sub["half"] == h]
        if len(hsub) == 0: continue

        if side == "home":
            results = hsub["f5_result"].values
            prices = hsub["home_price"].values
        else:
            results = np.where(hsub["f5_margin"] > 0, 0, np.where(hsub["f5_margin"] < 0, 1, np.nan))
            prices = hsub["away_price"].values

        push_mask = hsub["is_push"].values
        clean_results = np.where(np.isnan(results), -1, results)
        r = compute_roi(clean_results, prices, push_mask)
        thin = " (THIN)" if r["n"] < 40 else ""
        print(f"    {h}: N={r['n']} wr={r['wr']:.1f}% ROI_act={r['roi_actual']:+.1f}%{thin}")


# ── PHASE 6: PERMUTATION ────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("PHASE 6 — PERMUTATION (2025 ONLY)")
print("=" * 60)

rng = np.random.default_rng(42)
df_25 = df[df["season"] == 2025].copy()

for sig_name, (side, base_mask) in signal_defs.items():
    mask_25 = base_mask & (df["season"] == 2025)
    sub = df[mask_25]
    if len(sub) < 50:
        continue

    if side == "home":
        results = sub["f5_result"].values
        prices = sub["home_price"].values
    else:
        results = np.where(sub["f5_margin"] > 0, 0, np.where(sub["f5_margin"] < 0, 1, np.nan))
        prices = sub["away_price"].values

    push_mask = sub["is_push"].values
    clean_results = np.where(np.isnan(results), -1, results)
    actual_r = compute_roi(clean_results, prices, push_mask)

    # Permutation: shuffle f5_margin within 2025
    margins_25 = df_25["f5_margin"].values.copy()
    sel_idx = mask_25[df["season"] == 2025].values

    shuffled_rois = []
    for _ in range(200):
        perm = rng.permutation(margins_25)
        perm_results = np.where(perm > 0, 1, np.where(perm < 0, 0, -1))
        perm_push = perm == 0
        sel_r = perm_results[sel_idx]
        sel_push = perm_push[sel_idx]
        sel_prices = prices  # same prices
        sr = compute_roi(sel_r, sel_prices, sel_push)
        shuffled_rois.append(sr["roi_actual"])

    pctile = (np.array(shuffled_rois) < actual_r["roi_actual"]).mean() * 100
    flag = "" if pctile >= 90 else " *** BELOW TOP 10%"
    print(f"  {sig_name}: actual ROI={actual_r['roi_actual']:+.1f}%, "
          f"shuffled mean={np.mean(shuffled_rois):+.1f}%, pctile={pctile:.0f}%{flag}")


# ── DECISION CRITERIA ────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("DECISION CRITERIA")
print("=" * 60)

for sig_name, (side, base_mask) in {**signal_defs, **duel_defs}.items():
    for yr_label, yr_filter in [("pooled", pd.Series(True, index=df.index))]:
        mask = base_mask & yr_filter
        sub = df[mask]
        if len(sub) == 0: continue

        if side == "home":
            results = sub["f5_result"].values
            prices = sub["home_price"].values
        else:
            results = np.where(sub["f5_margin"] > 0, 0, np.where(sub["f5_margin"] < 0, 1, np.nan))
            prices = sub["away_price"].values

        push_mask = sub["is_push"].values
        clean_results = np.where(np.isnan(results), -1, results)
        r_pool = compute_roi(clean_results, prices, push_mask)

    # 2025 standalone
    mask_25 = base_mask & (df["season"] == 2025)
    sub_25 = df[mask_25]
    if len(sub_25) > 0:
        if side == "home":
            r25 = sub_25["f5_result"].values
            p25 = sub_25["home_price"].values
        else:
            r25 = np.where(sub_25["f5_margin"] > 0, 0, np.where(sub_25["f5_margin"] < 0, 1, np.nan))
            p25 = sub_25["away_price"].values
        r_2025 = compute_roi(np.where(np.isnan(r25), -1, r25), p25, sub_25["is_push"].values)
    else:
        r_2025 = {"roi_actual": -99, "n": 0}

    c1 = r_pool["roi_actual"] >= 2.0
    c2 = r_pool["n"] >= 150
    c3 = r_2025["n"] > 0 and r_2025["roi_actual"] > 0

    if r_pool["n"] < 50:
        continue

    status = "PASS" if (c1 and c2 and c3) else "FAIL"
    print(f"  {sig_name}:")
    print(f"    ROI>=2% pooled: {r_pool['roi_actual']:+.1f}% {'✓' if c1 else '✗'}")
    print(f"    N>=150: {r_pool['n']} {'✓' if c2 else '✗'}")
    print(f"    2025 ROI>0: {r_2025['roi_actual']:+.1f}% {'✓' if c3 else '✗'}")
    print(f"    → {status}")

print("\n*** F5 RUN LINE RESEARCH COMPLETE ***")
