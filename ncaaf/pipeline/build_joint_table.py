#!/usr/bin/env python3
"""
N07 (Branch A): Build joint outcome table from 2022-2025.

Keyed on (spread_bucket, total_bucket), holds the empirical joint
distribution of (cover, over). Restricted to |spread| >= 14 —
the buckets that survived OOS (N06).

Generator must be committed code (D63, D72).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "research" / "ncaaf_board"


def load_all_bovada():
    """Load Bovada lines for 2022-2025."""
    frames = []

    # 2022-2024 from the original file
    old_path = ROOT / "research" / "ncaaf" / "cfbd_betting_lines.parquet"
    if old_path.exists():
        old = pd.read_parquet(old_path)
        bov_old = old[old["provider"] == "Bovada"]
        frames.append(bov_old)

    # 2025 from the separate file
    new_path = ROOT / "research" / "ncaaf" / "cfbd_betting_lines_2025.parquet"
    if new_path.exists():
        new = pd.read_parquet(new_path)
        bov_new = new[new["provider"] == "Bovada"]
        frames.append(bov_new)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df[df["spread"].notna() & df["overUnder"].notna() &
            df["homeScore"].notna() & df["awayScore"].notna()]

    df["margin"] = df["homeScore"] - df["awayScore"]
    df["total"] = df["homeScore"] + df["awayScore"]
    df["abs_spread"] = df["spread"].abs()
    df["cover"] = (df["margin"] + df["spread"] > 0).astype(int)
    df["over"] = (df["total"] > df["overUnder"]).astype(int)

    # Drop pushes
    df = df[(df["margin"] + df["spread"] != 0) & (df["total"] != df["overUnder"])]

    return df


def build_table():
    df = load_all_bovada()
    print(f"Total rows (2022-2025, Bovada, complete, no pushes): {len(df)}")

    # Restrict to |spread| >= 14 — the buckets that survived OOS
    blowout = df[df["abs_spread"] >= 14].copy()
    print(f"  |spread| >= 14: {len(blowout)} games")

    if blowout.empty:
        print("No data"); return

    # Spread buckets: 14-21, 21+
    spread_buckets = [(14, 21, "14-21"), (21, 999, "21+")]
    # Total buckets based on overUnder: quartiles
    ou_q = blowout["overUnder"].quantile([0.25, 0.5, 0.75])
    total_buckets = [
        (0, ou_q.iloc[0], f"OU<{ou_q.iloc[0]:.0f}"),
        (ou_q.iloc[0], ou_q.iloc[1], f"OU_{ou_q.iloc[0]:.0f}-{ou_q.iloc[1]:.0f}"),
        (ou_q.iloc[1], ou_q.iloc[2], f"OU_{ou_q.iloc[1]:.0f}-{ou_q.iloc[2]:.0f}"),
        (ou_q.iloc[2], 999, f"OU>{ou_q.iloc[2]:.0f}"),
    ]

    rows = []
    for sp_lo, sp_hi, sp_name in spread_buckets:
        sp_mask = (blowout["abs_spread"] >= sp_lo) & (blowout["abs_spread"] < sp_hi)
        for ou_lo, ou_hi, ou_name in total_buckets:
            cell = blowout[sp_mask & (blowout["overUnder"] >= ou_lo) & (blowout["overUnder"] < ou_hi)]
            if len(cell) < 10:
                continue

            n = len(cell)
            p_cover = cell["cover"].mean()
            p_over = cell["over"].mean()
            p_cover_and_over = ((cell["cover"] == 1) & (cell["over"] == 1)).mean()
            p_cover_and_under = ((cell["cover"] == 1) & (cell["over"] == 0)).mean()
            p_miss_and_over = ((cell["cover"] == 0) & (cell["over"] == 1)).mean()
            p_miss_and_under = ((cell["cover"] == 0) & (cell["over"] == 0)).mean()

            rows.append({
                "spread_bucket": sp_name,
                "total_bucket": ou_name,
                "n": n,
                "p_cover": round(p_cover, 4),
                "p_over": round(p_over, 4),
                "p_cover_and_over": round(p_cover_and_over, 4),
                "p_cover_and_under": round(p_cover_and_under, 4),
                "p_miss_and_over": round(p_miss_and_over, 4),
                "p_miss_and_under": round(p_miss_and_under, 4),
                "p_independence": round(p_cover * p_over, 4),
                "delta": round(p_cover_and_over - p_cover * p_over, 4),
            })

    table = pd.DataFrame(rows)
    out_path = OUT_DIR / "joint_outcome_table_v1.parquet"
    table.to_parquet(out_path, index=False)
    print(f"\nJoint outcome table: {len(table)} cells -> {out_path}")
    print(table.to_string())

    # Also by spread bucket alone (the key result)
    print("\n\nBy spread bucket only:")
    for sp_lo, sp_hi, sp_name in spread_buckets:
        sp_mask = (blowout["abs_spread"] >= sp_lo) & (blowout["abs_spread"] < sp_hi)
        cell = blowout[sp_mask]
        if len(cell) < 10:
            continue
        p_c = cell["cover"].mean()
        p_o = cell["over"].mean()
        p_co = ((cell["cover"] == 1) & (cell["over"] == 1)).mean()
        delta = p_co - p_c * p_o
        phi = delta / np.sqrt(p_c * (1-p_c) * p_o * (1-p_o)) if p_c*(1-p_c)*p_o*(1-p_o) > 0 else 0
        t = phi * np.sqrt(len(cell))
        print(f"  {sp_name}: N={len(cell)}, delta={delta:+.4f}, phi={phi:.4f}, t={t:.2f}")

    # By season
    print("\nBy season (|spread| >= 14):")
    for s in sorted(blowout["season"].unique()):
        sd = blowout[blowout["season"] == s]
        if len(sd) < 10:
            continue
        p_c = sd["cover"].mean()
        p_o = sd["over"].mean()
        p_co = ((sd["cover"] == 1) & (sd["over"] == 1)).mean()
        delta = p_co - p_c * p_o
        phi = delta / np.sqrt(p_c * (1-p_c) * p_o * (1-p_o)) if p_c*(1-p_c)*p_o*(1-p_o) > 0 else 0
        t = phi * np.sqrt(len(sd))
        print(f"  {int(s)}: N={len(sd)}, phi={phi:.4f}, t={t:.2f}")


if __name__ == "__main__":
    build_table()
