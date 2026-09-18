#!/usr/bin/env python3
"""
N06: Test joint (cover, over) correlation on held-out 2025 data.

Committed code, not hand-run — so the result is reproducible (D63, D72).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent


def load_bovada(year):
    """Load Bovada lines for a year, compute cover/over indicators."""
    if year == 2025:
        path = ROOT / "research" / "ncaaf" / f"cfbd_betting_lines_{year}.parquet"
    else:
        path = ROOT / "research" / "ncaaf" / "cfbd_betting_lines.parquet"

    df = pd.read_parquet(path)
    bov = df[df["provider"] == "Bovada"].copy()

    if year != 2025:
        bov = bov[bov["season"] == year] if "season" in bov.columns else bov

    # Filter to complete rows
    bov = bov[bov["spread"].notna() & bov["overUnder"].notna() &
              bov["homeScore"].notna() & bov["awayScore"].notna()]

    bov["margin"] = bov["homeScore"] - bov["awayScore"]
    bov["total"] = bov["homeScore"] + bov["awayScore"]
    bov["abs_spread"] = bov["spread"].abs()

    # Cover: home covers if margin + spread > 0 (spread is negative for home fav)
    bov["cover"] = (bov["margin"] + bov["spread"] > 0).astype(int)
    bov["over"] = (bov["total"] > bov["overUnder"]).astype(int)

    # Drop pushes on either leg
    bov = bov[(bov["margin"] + bov["spread"] != 0) & (bov["total"] != bov["overUnder"])]

    return bov


def compute_phi(df):
    """Compute phi correlation between cover and over."""
    n = len(df)
    if n < 10:
        return {"n": n, "phi": np.nan, "t": np.nan}

    p_cover = df["cover"].mean()
    p_over = df["over"].mean()
    p_joint = ((df["cover"] == 1) & (df["over"] == 1)).mean()
    p_indep = p_cover * p_over
    delta = p_joint - p_indep

    denom = np.sqrt(p_cover * (1 - p_cover) * p_over * (1 - p_over))
    phi = delta / denom if denom > 0 else 0
    t = phi * np.sqrt(n) if n > 1 else 0

    return {
        "n": n, "p_cover": round(p_cover, 4), "p_over": round(p_over, 4),
        "p_indep": round(p_indep, 4), "p_joint": round(p_joint, 4),
        "delta": round(delta, 4), "phi": round(phi, 4), "t": round(t, 2),
    }


def run_test(year):
    """Run the bucketed correlation test for a single year."""
    bov = load_bovada(year)
    print(f"\n{'='*60}")
    print(f"Year {year}: N = {len(bov)}")
    print(f"{'='*60}")

    # Null control
    p_cover = bov["cover"].mean()
    p_over = bov["over"].mean()
    print(f"\nNULL CONTROL:")
    print(f"  P(home cover) = {p_cover:.4f}  (expect ~0.50)")
    print(f"  P(over)       = {p_over:.4f}  (expect ~0.50)")
    if abs(p_cover - 0.50) > 0.05 or abs(p_over - 0.50) > 0.05:
        print(f"  *** HALT: marginals off 0.50 by more than 5pp ***")

    # Pooled
    pooled = compute_phi(bov)
    print(f"\nPooled: N={pooled['n']}, phi={pooled['phi']}, t={pooled['t']}")

    # By bucket
    buckets = [(0, 3, "0-3"), (3, 7, "3-7"), (7, 14, "7-14"),
               (14, 21, "14-21"), (21, 999, "21+")]

    print(f"\n{'Bucket':>8s} {'N':>5s} {'P(cov)':>7s} {'P(ov)':>7s} {'Indep':>7s} {'Obs':>7s} {'Delta':>7s} {'Phi':>7s} {'t':>6s}")
    results = []
    for lo, hi, name in buckets:
        sub = bov[(bov["abs_spread"] >= lo) & (bov["abs_spread"] < hi)]
        r = compute_phi(sub)
        r["bucket"] = name
        results.append(r)
        print(f"{name:>8s} {r['n']:>5d} {r.get('p_cover',0):>7.4f} {r.get('p_over',0):>7.4f} "
              f"{r.get('p_indep',0):>7.4f} {r.get('p_joint',0):>7.4f} {r.get('delta',0):>+7.4f} "
              f"{r.get('phi',0):>7.4f} {r.get('t',0):>6.2f}")

    return bov, pooled, results


if __name__ == "__main__":
    # Run on 2025 (held out)
    bov25, pooled25, results25 = run_test(2025)

    # Verdict
    print(f"\n{'='*60}")
    print("VERDICT")
    print(f"{'='*60}")

    r21 = next((r for r in results25 if r["bucket"] == "21+"), {})
    r14 = next((r for r in results25 if r["bucket"] == "14-21"), {})
    r03 = next((r for r in results25 if r["bucket"] == "0-3"), {})
    r37 = next((r for r in results25 if r["bucket"] == "3-7"), {})
    r714 = next((r for r in results25 if r["bucket"] == "7-14"), {})

    pred1 = r21.get("phi", 0) > 0 and r21.get("phi", 0) >= 0.05
    pred2 = r14.get("phi", 0) > 0
    pred3 = all(abs(r.get("t", 0)) < 2 for r in [r03, r37, r714])

    print(f"  Prediction 1 (21+ positive phi ~0.10-0.25): phi={r21.get('phi')}, {'HELD' if pred1 else 'DID NOT HOLD'}")
    print(f"  Prediction 2 (14-21 positive but smaller):  phi={r14.get('phi')}, {'HELD' if pred2 else 'DID NOT HOLD'}")
    print(f"  Prediction 3 (0-3,3-7,7-14 flat |t|<2):    t={r03.get('t')},{r37.get('t')},{r714.get('t')}, {'HELD' if pred3 else 'DID NOT HOLD'}")
