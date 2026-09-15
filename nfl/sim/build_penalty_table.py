#!/usr/bin/env python3
"""
Phase 5A-4: Build empirical penalty distribution table from 2021-2024 PBP.

Only includes no-play penalties (play_type == "no_play" with penalty == 1),
which are the penalties that nullify the play and are modeled separately by
the engine. On-scrimmage accepted penalties are already reflected in the
play outcome distributions.

Output: nfl/data/sim/tables/penalty_detail.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "tables"
SEASONS = [2021, 2022, 2023, 2024]
QUANTILE_POINTS = np.linspace(0, 1, 101)


def load_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["week"] <= 18].copy()
    return df


def build_penalty_table(df):
    n_games = df["game_id"].nunique()

    # Only no-play penalties: play_type == "no_play" with penalty == 1
    nop = df[(df["play_type"] == "no_play") & (df["penalty"] == 1)].copy()
    nop["side"] = np.where(nop["penalty_team"] == nop["posteam"], "offense", "defense")
    nop = nop[nop["side"].isin(["offense", "defense"])].copy()

    n_scrim = len(df[df["play_type"].isin(["pass", "run"])])

    print(f"No-play penalties: {len(nop)}")
    print(f"Scrimmage plays: {n_scrim}")
    print(f"Games: {n_games}")
    print(f"No-play penalty rate per scrimmage play: {len(nop)/n_scrim:.4f}")

    # Classify penalty types
    def categorize(row):
        pt = row.get("penalty_type", "")
        if pd.isna(pt):
            pt = ""
        side = row["side"]

        off_5yd_types = [
            "False Start", "Delay of Game", "Illegal Shift", "Illegal Formation",
            "Illegal Motion", "Illegal Substitution", "Illegal Alignment",
            "Ineligible Downfield Pass", "Ineligible Downfield Kick",
        ]
        off_10yd_types = [
            "Offensive Holding", "Offensive Pass Interference",
            "Intentional Grounding", "Tripping",
        ]
        off_15yd_types = [
            "Unnecessary Roughness", "Unsportsmanlike Conduct", "Taunting",
            "Chop Block", "Clipping",
        ]
        def_auto_short_types = [
            "Defensive Holding", "Illegal Contact", "Illegal Use of Hands",
        ]
        def_auto_long_types = [
            "Unnecessary Roughness", "Roughing the Passer", "Face Mask",
            "Roughing the Kicker", "Running Into the Kicker",
            "Horse Collar Tackle", "Lowering the Head to Initiate Contact",
        ]
        def_noauto_types = [
            "Defensive Offside", "Neutral Zone Infraction",
            "Encroachment", "Defensive Too Many Men on Field",
            "Offside on Free Kick",
        ]

        if pt == "Defensive Pass Interference":
            return "defense_dpi"
        if side == "offense":
            if pt in off_5yd_types:
                return "offense_5yd"
            if pt in off_10yd_types:
                return "offense_10yd"
            if pt in off_15yd_types:
                return "offense_15yd"
            return "offense_other"
        else:
            if pt in def_auto_short_types:
                return "defense_auto_short"
            if pt in def_auto_long_types:
                return "defense_auto_long"
            if pt in def_noauto_types:
                return "defense_noauto"
            return "defense_other"

    nop["category"] = nop.apply(categorize, axis=1)

    result = {}
    for cat, grp in nop.groupby("category"):
        n = len(grp)
        yds = grp["penalty_yards"].dropna()
        auto_first_rate = grp["first_down_penalty"].mean() if "first_down_penalty" in grp.columns else 0.0

        entry = {
            "count": int(n),
            "per_game": round(n / n_games, 4),
            "mean_yds": round(float(yds.mean()), 1) if len(yds) else 0.0,
            "auto_first_rate": round(float(auto_first_rate), 4),
        }
        if len(yds) >= 20:
            entry["yds_q"] = np.quantile(yds.values.astype(float), QUANTILE_POINTS).tolist()

        result[cat] = entry

    total = sum(v["count"] for v in result.values())
    print(f"\nNo-play penalty categories ({total} total, {n_games} games):")
    for cat in sorted(result.keys()):
        v = result[cat]
        print(f"  {cat:25s}: {v['count']:5d} ({v['per_game']:.2f}/game) "
              f"mean_yds={v['mean_yds']:5.1f}  auto_first={v['auto_first_rate']:.3f}")

    off_total = sum(v["count"] for k, v in result.items() if k.startswith("offense"))
    def_total = sum(v["count"] for k, v in result.items() if k.startswith("defense"))
    print(f"\nOffense fraction: {off_total/total:.3f} ({off_total})")
    print(f"Defense fraction: {def_total/total:.3f} ({def_total})")

    result["_meta"] = {
        "n_games": n_games,
        "n_scrimmage": n_scrim,
        "n_no_play_pen": total,
        "p_penalty_per_scrimmage": round(total / n_scrim, 6),
    }

    # DPI by zone
    dpi = nop[nop["category"] == "defense_dpi"]
    if len(dpi) > 0:
        dpi_by_zone = {}
        for zone_name, lo, hi in [("deep", 0, 20), ("mid", 21, 50), ("shallow", 51, 100)]:
            z = dpi[(dpi["yardline_100"] >= lo) & (dpi["yardline_100"] <= hi)]
            if len(z) >= 10:
                yds_z = z["penalty_yards"].dropna()
                dpi_by_zone[zone_name] = {
                    "n": int(len(z)),
                    "mean_yds": round(float(yds_z.mean()), 1),
                    "yds_q": np.quantile(yds_z.values.astype(float), QUANTILE_POINTS).tolist(),
                }
        if "defense_dpi" in result:
            result["defense_dpi"]["by_zone"] = dpi_by_zone

    return result


def main():
    print("Loading PBP data...")
    df = load_pbp()
    print(f"Loaded {len(df):,} plays")

    result = build_penalty_table(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "penalty_detail.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=float)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
