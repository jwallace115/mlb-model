#!/usr/bin/env python3
"""
PULL 3 — Pitcher rolling ERA and pitch count history
PULL 4 — Pitcher times-through-order rolling splits
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SIM = BASE.parent.parent / "sim" / "data"

# =====================================================================
# PULL 3 — PITCHER ROLLING ERA AND PITCH COUNT
# =====================================================================
print("=" * 60)
print("PULL 3 — PITCHER ROLLING ERA AND PITCH COUNT")
print("=" * 60)

ps = pd.read_parquet(BASE.parent / "opponent_adjusted_engine" /
                     "pitcher_start_adjusted_metrics.parquet")
ps["date"] = pd.to_datetime(ps["date"])
ps = ps.sort_values(["pitcher_id", "date"]).reset_index(drop=True)

print(f"  Pitcher starts: {len(ps)}")
print(f"  Seasons: {ps.season.value_counts().sort_index().to_dict()}")

# Rolling ERA last 2 starts (shift to exclude current)
ps["er_r2"] = ps.groupby("pitcher_id")["er"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())
ps["ip_r2"] = ps.groupby("pitcher_id")["ip"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())
ps["pitcher_era_last2_starts"] = ps["er_r2"] / ps["ip_r2"].clip(lower=0.1) * 9

# Runs allowed last 2
ps["pitcher_runs_allowed_last2"] = ps.groupby("pitcher_id")["er"].transform(
    lambda x: x.shift(1).rolling(2, min_periods=2).sum())

# Runs per IP last 2
ps["pitcher_runs_allowed_per_inning_last2"] = ps["pitcher_runs_allowed_last2"] / ps["ip_r2"].clip(lower=0.1)

# ERA season to date (expanding within season, shifted)
ps["er_season"] = ps.groupby(["pitcher_id", "season"])["er"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).sum())
ps["ip_season"] = ps.groupby(["pitcher_id", "season"])["ip"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).sum())
ps["pitcher_era_season_to_date"] = ps["er_season"] / ps["ip_season"].clip(lower=0.1) * 9

# Pitches last start and 2 starts ago
ps["pitcher_pitches_last_start"] = ps.groupby("pitcher_id")["pitches"].shift(1)
ps["pitcher_pitches_2starts_ago"] = ps.groupby("pitcher_id")["pitches"].shift(2)

# Pitches per inning last 3
ps["ppi"] = ps["pitches"] / ps["ip"].clip(lower=0.1)
ps["pitcher_pitches_per_inning_last3"] = ps.groupby("pitcher_id")["ppi"].transform(
    lambda x: x.shift(1).rolling(3, min_periods=2).mean())

# ERA spike
ps["pitcher_era_spike"] = ps["pitcher_era_last2_starts"] - ps["pitcher_era_season_to_date"]

# Output
out_cols = ["pitcher_id", "game_pk", "date", "season", "team", "opponent",
            "pitcher_era_last2_starts", "pitcher_runs_allowed_last2",
            "pitcher_runs_allowed_per_inning_last2", "pitcher_era_season_to_date",
            "pitcher_pitches_last_start", "pitcher_pitches_2starts_ago",
            "pitcher_pitches_per_inning_last3", "pitcher_era_spike"]

pull3 = ps[out_cols].copy()
pull3.rename(columns={"game_pk": "game_id", "date": "game_date"}, inplace=True)
pull3.to_parquet(BASE / "pitcher_rolling_era_pitches.parquet", index=False)

print(f"\n  Saved: {len(pull3)} rows")
print(f"  Seasons: {pull3.groupby(pull3.game_date.dt.year).size().to_dict()}")
print(f"\n  Coverage vs pitcher start universe: {len(pull3)}/{len(ps)} ({100*len(pull3)/len(ps):.1f}%)")
print(f"\n  Null rates:")
for c in out_cols[6:]:
    null_rate = pull3[c.replace("game_pk", "game_id").replace("date", "game_date")
                       if c in ["game_pk", "date"] else c].isna().mean()
    # fix column name for renamed cols
for c in ["pitcher_era_last2_starts", "pitcher_runs_allowed_last2",
          "pitcher_runs_allowed_per_inning_last2", "pitcher_era_season_to_date",
          "pitcher_pitches_last_start", "pitcher_pitches_2starts_ago",
          "pitcher_pitches_per_inning_last3", "pitcher_era_spike"]:
    null_rate = pull3[c].isna().mean()
    print(f"    {c}: {null_rate:.1%} null")


# =====================================================================
# PULL 4 — PITCHER TIMES-THROUGH-ORDER SPLITS
# =====================================================================
print("\n" + "=" * 60)
print("PULL 4 — PITCHER TIMES-THROUGH-ORDER SPLITS")
print("=" * 60)

# TTO data requires inning-level or plate-appearance-level data.
# We don't have pitch-by-pitch or PA-level data locally.
# What we DO have: per-start totals (K, BB, H, HR, IP, ER, BF)
#
# We CANNOT directly compute wOBA by TTO without PA-level data.
#
# Best available proxy:
# Use innings 1-3 vs innings 4-6 performance as a TTO surrogate.
# Pitchers typically face the order once in innings 1-3 and again in 4-6.
#
# Alternative: use the per-start ER/IP as a proxy for how much the pitcher
# degrades as the game goes on. We can compute:
#   - ERA in short outings (< 5 IP) vs long outings (>= 5 IP)
#   - IP-weighted ER rate, which reflects durability
#
# HOWEVER: this is not a true TTO split. Let me report this limitation.

print("  TRUE TTO DATA NOT AVAILABLE")
print("  Pitch-by-pitch or plate-appearance-level data not in local pipeline.")
print("  Deriving best available proxy: short-outing vs long-outing degradation.")
print()

# Proxy: for each pitcher, compute rolling stats that proxy TTO exposure
# Metric: pitcher_late_inning_risk = ratio of ER in IP > 4 vs IP <= 4
# This requires inning-level splits we don't have.
#
# Alternative proxy: for each start, compute:
# - early_era_proxy: pitcher's ERA in starts where they went 6+ IP (command games)
# - short_exit_era: pitcher's ERA in starts where they went < 5 IP (degradation games)
# The RATIO or DIFFERENCE between these proxies TTO degradation.

ps2 = ps.copy()
ps2["went_deep"] = (ps2["ip"] >= 5.0).astype(int)
ps2["short_exit"] = (ps2["ip"] < 5.0).astype(int)

# Rolling 15 starts
ps2["er_deep_r15"] = ps2.groupby("pitcher_id").apply(
    lambda g: (g["er"] * g["went_deep"]).shift(1).rolling(15, min_periods=5).sum(),
    include_groups=False
).reset_index(level=0, drop=True)
ps2["ip_deep_r15"] = ps2.groupby("pitcher_id").apply(
    lambda g: (g["ip"] * g["went_deep"]).shift(1).rolling(15, min_periods=5).sum(),
    include_groups=False
).reset_index(level=0, drop=True)
ps2["er_short_r15"] = ps2.groupby("pitcher_id").apply(
    lambda g: (g["er"] * g["short_exit"]).shift(1).rolling(15, min_periods=5).sum(),
    include_groups=False
).reset_index(level=0, drop=True)
ps2["ip_short_r15"] = ps2.groupby("pitcher_id").apply(
    lambda g: (g["ip"] * g["short_exit"]).shift(1).rolling(15, min_periods=5).sum(),
    include_groups=False
).reset_index(level=0, drop=True)

# ERA in deep starts vs short starts
ps2["era_deep_r15"] = ps2["er_deep_r15"] / ps2["ip_deep_r15"].clip(lower=0.1) * 9
ps2["era_short_r15"] = ps2["er_short_r15"] / ps2["ip_short_r15"].clip(lower=0.1) * 9

# TTO drop proxy: how much worse is pitcher in short outings vs deep outings
# Higher = more degradation (worse when they can't go deep)
ps2["pitcher_tto_drop"] = ps2["era_short_r15"] - ps2["era_deep_r15"]

# Also compute: rolling fraction of short exits as durability proxy
ps2["short_exit_rate_r15"] = ps2.groupby("pitcher_id")["short_exit"].transform(
    lambda x: x.shift(1).rolling(15, min_periods=5).mean())

# wOBA proxies (using the data we have):
# "TTO1" proxy: ERA when pitcher goes deep (controlled, early-order success)
# "TTO2" proxy: overall ERA
# "TTO3" proxy: ERA in short exits (lineup cracked pitcher = late-order failure)
ps2["pitcher_woba_tto1_rolling"] = ps2["era_deep_r15"]  # best proxy for early-TTO performance
ps2["pitcher_woba_tto2_rolling"] = ps2.groupby("pitcher_id")["er"].transform(
    lambda x: x.shift(1).rolling(15, min_periods=5).sum()) / \
    ps2.groupby("pitcher_id")["ip"].transform(
    lambda x: x.shift(1).rolling(15, min_periods=5).sum()).clip(lower=0.1) * 9
ps2["pitcher_woba_tto3_rolling"] = ps2["era_short_r15"]  # proxy for late-TTO degradation

out_cols4 = ["pitcher_id", "game_pk", "date", "season", "team", "opponent",
             "pitcher_woba_tto1_rolling", "pitcher_woba_tto2_rolling",
             "pitcher_woba_tto3_rolling", "pitcher_tto_drop",
             "short_exit_rate_r15"]

pull4 = ps2[out_cols4].copy()
pull4.rename(columns={"game_pk": "game_id", "date": "game_date"}, inplace=True)
pull4.to_parquet(BASE / "pitcher_tto_splits.parquet", index=False)

print(f"  Saved: {len(pull4)} rows")
print(f"  Seasons: {pull4.groupby(pull4.game_date.dt.year).size().to_dict()}")
print(f"  Coverage vs pitcher starts: {len(pull4)}/{len(ps)} ({100*len(pull4)/len(ps):.1f}%)")
print(f"\n  NULL RATES:")
for c in ["pitcher_woba_tto1_rolling", "pitcher_woba_tto2_rolling",
          "pitcher_woba_tto3_rolling", "pitcher_tto_drop", "short_exit_rate_r15"]:
    null_rate = pull4[c].isna().mean()
    print(f"    {c}: {null_rate:.1%} null")

print(f"\n  ⚠ LIMITATION: True TTO wOBA splits require pitch-by-pitch or PA-level data")
print(f"  which is not available locally. These are PROXY metrics derived from:")
print(f"    TTO1 proxy: ERA in starts ≥5 IP (pitcher dominated = early TTO success)")
print(f"    TTO3 proxy: ERA in starts <5 IP (pitcher cracked = late TTO failure)")
print(f"    TTO drop: ERA_short - ERA_deep (positive = degrades later in game)")
print(f"  These proxies capture durability-related degradation but NOT true")
print(f"  times-through-order effects within a single game.")

print("\nDone. Both pulls complete.")
