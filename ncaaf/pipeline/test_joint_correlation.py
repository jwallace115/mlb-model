#!/usr/bin/env python3
"""
N06/N09: Test joint (cover, over) correlation on held-out 2025 data.

Committed code, reproducible. Reports BOTH bin conventions side by side.
The --bins flag is REQUIRED — the caller must choose, and both are always shown.

N09 defect: the original used left-closed bins while the probe used right-closed
(pd.cut). In football, 3/7/14/21 are modal spreads, so the convention reallocates
a large mass of games across exactly the boundaries being tested.
"""

import argparse, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent

BUCKET_EDGES = [0, 3, 7, 14, 21]
BUCKET_NAMES = ["0-3", "3-7", "7-14", "14-21", "21+"]


def load_bovada(year):
    if year == 2025:
        path = ROOT / "research" / "ncaaf" / f"cfbd_betting_lines_{year}.parquet"
    else:
        path = ROOT / "research" / "ncaaf" / "cfbd_betting_lines.parquet"
    df = pd.read_parquet(path)
    bov = df[df["provider"] == "Bovada"].copy()
    if year != 2025:
        bov = bov[bov["season"] == year] if "season" in bov.columns else bov
    bov = bov[bov["spread"].notna() & bov["overUnder"].notna() &
              bov["homeScore"].notna() & bov["awayScore"].notna()]
    bov["margin"] = bov["homeScore"] - bov["awayScore"]
    bov["total"] = bov["homeScore"] + bov["awayScore"]
    bov["abs_spread"] = bov["spread"].abs()
    bov["cover"] = (bov["margin"] + bov["spread"] > 0).astype(int)
    bov["over"] = (bov["total"] > bov["overUnder"]).astype(int)
    bov = bov[(bov["margin"] + bov["spread"] != 0) & (bov["total"] != bov["overUnder"])]
    return bov


def compute_phi(df):
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
    return {"n": n, "p_cover": round(p_cover, 4), "p_over": round(p_over, 4),
            "p_indep": round(p_indep, 4), "p_joint": round(p_joint, 4),
            "delta": round(delta, 4), "phi": round(phi, 4), "t": round(t, 2)}


def bucket_games(bov, convention):
    """Assign games to buckets under the given convention.
    left-closed: [lo, hi) — 3 goes in 3-7, 7 in 7-14, 21 in 21+
    right-closed: (lo, hi] — 3 goes in 0-3, 7 in 3-7, 21 in 14-21
    """
    results = []
    for i, name in enumerate(BUCKET_NAMES):
        lo = BUCKET_EDGES[i] if i < len(BUCKET_EDGES) else BUCKET_EDGES[-1]
        hi = BUCKET_EDGES[i + 1] if i + 1 < len(BUCKET_EDGES) else 999
        if convention == "left":
            sub = bov[(bov["abs_spread"] >= lo) & (bov["abs_spread"] < hi)]
        else:  # right-closed
            if i == 0:
                sub = bov[(bov["abs_spread"] >= 0) & (bov["abs_spread"] <= lo if lo > 0 else bov["abs_spread"] <= hi)]
                # Right-closed: (lo, hi] except first bucket is [0, hi]
                sub = bov[(bov["abs_spread"] >= 0) & (bov["abs_spread"] <= hi)]
            else:
                sub = bov[(bov["abs_spread"] > lo) & (bov["abs_spread"] <= hi)]
        r = compute_phi(sub)
        r["bucket"] = name
        r["convention"] = convention
        results.append(r)
    return results


def run_test(year):
    bov = load_bovada(year)
    print(f"\n{'='*70}")
    print(f"Year {year}: N = {len(bov)}")
    print(f"{'='*70}")

    p_cover = bov["cover"].mean()
    p_over = bov["over"].mean()
    print(f"\nNULL CONTROL: P(cover)={p_cover:.4f}, P(over)={p_over:.4f}")
    if abs(p_cover - 0.50) > 0.05 or abs(p_over - 0.50) > 0.05:
        print("  *** HALT: marginals off 0.50 ***")

    pooled = compute_phi(bov)
    print(f"Pooled: N={pooled['n']}, phi={pooled['phi']}, t={pooled['t']}")

    # Report BOTH conventions
    left = bucket_games(bov, "left")
    right = bucket_games(bov, "right")

    print(f"\n{'Bucket':>8s} | {'LEFT-CLOSED':>30s} | {'RIGHT-CLOSED (probe)':>30s}")
    print(f"{'':>8s} | {'N':>5s} {'phi':>7s} {'t':>6s} | {'N':>5s} {'phi':>7s} {'t':>6s}")
    print("-" * 70)
    for l, r in zip(left, right):
        print(f"{l['bucket']:>8s} | {l['n']:>5d} {l['phi']:>7.4f} {l['t']:>6.2f} | "
              f"{r['n']:>5d} {r['phi']:>7.4f} {r['t']:>6.2f}")

    return bov, pooled, left, right


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bins", choices=["left", "right"], required=True,
                        help="Bin convention: left-closed [lo,hi) or right-closed (lo,hi]")
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()

    bov, pooled, left, right = run_test(args.year)

    primary = left if args.bins == "left" else right
    print(f"\nPrimary convention: {args.bins}-closed")
    print(f"Bin edges recorded: {BUCKET_EDGES} + 999, convention={args.bins}")
