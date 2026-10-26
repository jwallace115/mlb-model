#!/usr/bin/env python3
"""DA-0 Item 2: Defensive data inventory.

nflreadpy only, read-only. Checks load_participation, load_ftn_charting,
and on-disk pbp for defensive fields availability.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "nfl_sim" / "defensive_archetypes"

rows = []

# ── load_participation ──
print("=== load_participation ===")
try:
    import nflreadpy
    for season in range(2016, 2027):
        try:
            df = nflreadpy.load_participation([season])
            if hasattr(df, "to_pandas"):
                df = df.to_pandas()
            if df.empty:
                continue
            print(f"  {season}: {len(df):,} rows, {len(df.columns)} cols")
            # Key defensive fields
            for col in ["defense_man_zone_type", "defense_coverage_type", "defense_personnel",
                         "number_of_pass_rushers", "defenders_in_box", "offense_formation"]:
                if col in df.columns:
                    nonnull = df[col].notna().mean()
                    # By week bucket
                    if "week" in df.columns:
                        for wmin, wmax, label in [(1, 3, "1-3"), (4, 9, "4-9"), (10, 99, "10+")]:
                            wk = df[(df.week >= wmin) & (df.week <= wmax)]
                            wk_rate = wk[col].notna().mean() if len(wk) else 0
                            rows.append({"source": "participation", "season": season,
                                         "field": col, "week_bucket": label,
                                         "nonnull_share": round(wk_rate, 4),
                                         "n_rows": len(wk)})
                    rows.append({"source": "participation", "season": season,
                                 "field": col, "week_bucket": "all",
                                 "nonnull_share": round(nonnull, 4),
                                 "n_rows": len(df)})
                    print(f"    {col}: {nonnull:.1%} non-null")
                else:
                    print(f"    {col}: NOT PRESENT")
            # Defenses with >= 100 labelled pass plays by week 4
            if "defense_man_zone_type" in df.columns and "week" in df.columns:
                early = df[(df.week <= 4) & df["defense_man_zone_type"].notna()]
                if "defteam" in df.columns:
                    teams_100 = (early.groupby("defteam").size() >= 100).sum()
                    print(f"    defenses with >=100 labelled pass plays by wk4: {teams_100}")
        except Exception as e:
            if "404" not in str(e) and "not found" not in str(e).lower():
                print(f"  {season}: {e}")
except Exception as e:
    print(f"  load_participation failed: {e}")

# ── load_ftn_charting ──
print("\n=== load_ftn_charting ===")
try:
    import nflreadpy
    for season in range(2016, 2027):
        try:
            df = nflreadpy.load_ftn_charting([season])
            if hasattr(df, "to_pandas"):
                df = df.to_pandas()
            if df.empty:
                continue
            print(f"  {season}: {len(df):,} rows, {len(df.columns)} cols")
            for col in ["n_blitzers", "n_pass_rushers", "is_motion", "is_play_action",
                         "is_rpo", "is_screen"]:
                if col in df.columns:
                    nonnull = df[col].notna().mean()
                    if "week" in df.columns:
                        for wmin, wmax, label in [(1, 3, "1-3"), (4, 9, "4-9"), (10, 99, "10+")]:
                            wk = df[(df.week >= wmin) & (df.week <= wmax)]
                            wk_rate = wk[col].notna().mean() if len(wk) else 0
                            rows.append({"source": "ftn_charting", "season": season,
                                         "field": col, "week_bucket": label,
                                         "nonnull_share": round(wk_rate, 4),
                                         "n_rows": len(wk)})
                    rows.append({"source": "ftn_charting", "season": season,
                                 "field": col, "week_bucket": "all",
                                 "nonnull_share": round(nonnull, 4),
                                 "n_rows": len(df)})
                    print(f"    {col}: {nonnull:.1%} non-null")
                else:
                    print(f"    {col}: NOT PRESENT")
        except Exception as e:
            if "404" not in str(e) and "not found" not in str(e).lower():
                print(f"  {season}: {e}")
except Exception as e:
    print(f"  load_ftn_charting failed: {e}")

# ── PBP on disk (2021-2024) ──
print("\n=== PBP on disk ===")
pbp_dir = ROOT / "nfl" / "data" / "pbp"
for season in range(2021, 2026):
    pbp_files = sorted(pbp_dir.glob(f"play_by_play_{season}*.parquet"))
    if not pbp_files:
        print(f"  {season}: no PBP files")
        continue
    df = pd.read_parquet(pbp_files[-1])
    pass_plays = df[df["play_type"] == "pass"]
    print(f"  {season}: {len(df):,} plays, {len(pass_plays):,} pass plays")
    # Receiver position via rosters for positional funnels
    for col in ["receiver_player_id", "receiver_player_name", "posteam", "defteam",
                 "air_yards", "yards_after_catch", "complete_pass", "interception",
                 "qb_scramble", "rush_attempt"]:
        if col in df.columns:
            nonnull = pass_plays[col].notna().mean() if len(pass_plays) else 0
            rows.append({"source": "pbp", "season": season,
                         "field": col, "week_bucket": "all",
                         "nonnull_share": round(nonnull, 4),
                         "n_rows": len(pass_plays)})
    # Explosive plays allowed (20+ yds)
    explosive = pass_plays[pass_plays["yards_gained"] >= 20] if "yards_gained" in pass_plays.columns else pd.DataFrame()
    print(f"    explosive pass plays (20+ yds): {len(explosive):,}")

# No publication receipt — nflreadpy does not expose server timestamps
print("\nNote: no publication receipt from nflreadpy (the OPS-ON-1 lesson: do not claim freshness)")

inv = pd.DataFrame(rows)
inv.to_parquet(OUT / "da0_defense_inventory.parquet", index=False)
print(f"\nDefense inventory: {len(inv)} rows → da0_defense_inventory.parquet")
print("DONE")
