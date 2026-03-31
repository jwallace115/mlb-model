#!/usr/bin/env python3
"""
Task 1 — Bullpen Fatigue Features

Computes per-game bullpen fatigue metrics from bullpen_usage.parquet
and joins to the scanner dataset (feature_table + closing lines, 2024-2025).

Output: research/signal_scanner/derived_features/bullpen_fatigue.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ── Load source data ──────────────────────────────────────────────────
bu = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "bullpen_usage.parquet")
bu["date"] = pd.to_datetime(bu["date"])

ft = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])

br = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])

# ── Build scanner dataset (2024-2025 with closing lines) ─────────────
scanner = ft[ft["season"].isin([2024, 2025])].copy()
scanner = scanner.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
                        on="game_pk", how="inner")
scanner.rename(columns={"close_total": "closing_total"}, inplace=True)
print(f"Scanner dataset: {len(scanner)} games with closing lines")

# ── Bullpen IP per team-date ─────────────────────────────────────────
bp = bu[~bu["is_starter"]].copy()

# Aggregate: total bullpen IP per team per date
bp_daily = bp.groupby(["team", "date"]).agg(
    bullpen_ip=("innings_pitched", "sum")
).reset_index()

# ── Closer identification: most saves per team-season ────────────────
# games_finished proxy for saves (pitcher who finished winning games)
# Better: use actual saves from boxscores. games_finished is available.
# We'll define closer = pitcher with most games_finished per team-season
bp["season"] = bp["date"].dt.year
closer_candidates = bp.groupby(["team", "season", "pitcher_id"]).agg(
    total_gf=("games_finished", "sum")
).reset_index()
closer_ids = closer_candidates.sort_values("total_gf", ascending=False).drop_duplicates(
    subset=["team", "season"], keep="first"
)[["team", "season", "pitcher_id"]].rename(columns={"pitcher_id": "closer_id"})

print(f"Closers identified: {len(closer_ids)} team-seasons")
print(closer_candidates.merge(closer_ids.rename(columns={"closer_id": "pitcher_id"}))
      .sort_values("total_gf", ascending=False).head(10)
      [["team", "season", "pitcher_id", "total_gf"]].to_string(index=False))

# Tag closer appearances
bp = bp.merge(closer_ids, on=["team", "season"], how="left")
bp["is_closer"] = bp["pitcher_id"] == bp["closer_id"]

closer_daily = bp[bp["is_closer"]].groupby(["team", "date"]).size().reset_index(name="closer_appeared")
closer_daily["closer_appeared"] = 1  # just flag

# ── Rolling features per team ────────────────────────────────────────
# Sort and build rolling bullpen IP (last 2 days, last 3 days)
bp_daily = bp_daily.sort_values(["team", "date"]).reset_index(drop=True)

def rolling_bp_features(group):
    """Compute rolling bullpen IP for previous N days (not including game day)."""
    group = group.sort_values("date").copy()
    dates = group["date"].values
    bp_ip = group["bullpen_ip"].values

    ip_last2 = []
    ip_last3 = []

    for i, d in enumerate(dates):
        d_ts = pd.Timestamp(d)
        # Look back 2 days
        mask2 = (dates < d) & (dates >= (d_ts - pd.Timedelta(days=2)).to_numpy())
        mask3 = (dates < d) & (dates >= (d_ts - pd.Timedelta(days=3)).to_numpy())
        ip_last2.append(bp_ip[mask2].sum())
        ip_last3.append(bp_ip[mask3].sum())

    group["bp_ip_last2d"] = ip_last2
    group["bp_ip_last3d"] = ip_last3
    return group

print("Computing rolling bullpen IP (this takes a moment)...")
bp_daily = bp_daily.groupby("team", group_keys=False).apply(rolling_bp_features)

# ── Closer used last 2 days ─────────────────────────────────────────
# Build a team-date index of closer appearances
closer_daily = closer_daily.sort_values(["team", "date"]).reset_index(drop=True)

def rolling_closer_flag(group):
    group = group.sort_values("date").copy()
    return group  # just presence data; we'll join below

# For each game date, check if closer appeared in previous 2 days
# Build full team-date grid from bp_daily, then check closer_daily
all_team_dates = bp_daily[["team", "date"]].copy()

def check_closer_last2d(row, closer_dates_dict):
    key = row["team"]
    if key not in closer_dates_dict:
        return 0
    cd = closer_dates_dict[key]
    d = pd.Timestamp(row["date"])
    window = cd[(cd < d) & (cd >= d - pd.Timedelta(days=2))]
    return 1 if len(window) > 0 else 0

# Build dict of closer appearance dates per team
closer_dates_dict = {}
for team, grp in closer_daily.groupby("team"):
    closer_dates_dict[team] = grp["date"].values

all_team_dates["closer_used_last2d"] = all_team_dates.apply(
    lambda r: check_closer_last2d(r, closer_dates_dict), axis=1
)

bp_daily = bp_daily.merge(all_team_dates[["team", "date", "closer_used_last2d"]], on=["team", "date"], how="left")
bp_daily["closer_used_last2d"] = bp_daily["closer_used_last2d"].fillna(0).astype(int)

# ── Season average daily BP IP ───────────────────────────────────────
bp_daily["season"] = bp_daily["date"].dt.year
season_avg = bp_daily.groupby(["team", "season"]).agg(
    season_total_bp_ip=("bullpen_ip", "sum"),
    season_games=("date", "nunique")
).reset_index()
season_avg["team_avg_daily_bp_ip"] = season_avg["season_total_bp_ip"] / season_avg["season_games"]
bp_daily = bp_daily.merge(season_avg[["team", "season", "team_avg_daily_bp_ip"]], on=["team", "season"], how="left")

print(f"\nBP daily features: {len(bp_daily)} team-dates")
print(bp_daily[["team", "date", "bullpen_ip", "bp_ip_last2d", "bp_ip_last3d", "closer_used_last2d", "team_avg_daily_bp_ip"]].describe().to_string())

# ── Join to scanner dataset (home + away) ────────────────────────────
bp_home = bp_daily.rename(columns={
    "bp_ip_last2d": "bullpen_ip_last2days_home",
    "bp_ip_last3d": "bullpen_ip_last3days_home",
    "closer_used_last2d": "closer_used_last2days_home",
    "team_avg_daily_bp_ip": "home_season_avg_daily_bp_ip",
})[["team", "date", "bullpen_ip_last2days_home", "bullpen_ip_last3days_home",
    "closer_used_last2days_home", "home_season_avg_daily_bp_ip"]]

bp_away = bp_daily.rename(columns={
    "bp_ip_last2d": "bullpen_ip_last2days_away",
    "bp_ip_last3d": "bullpen_ip_last3days_away",
    "closer_used_last2d": "closer_used_last2days_away",
    "team_avg_daily_bp_ip": "away_season_avg_daily_bp_ip",
})[["team", "date", "bullpen_ip_last2days_away", "bullpen_ip_last3days_away",
    "closer_used_last2days_away", "away_season_avg_daily_bp_ip"]]

result = scanner.merge(bp_home, left_on=["home_team", "date"], right_on=["team", "date"], how="left").drop(columns=["team"])
result = result.merge(bp_away, left_on=["away_team", "date"], right_on=["team", "date"], how="left").drop(columns=["team"])

# Coverage
total = len(result)
joined_home = result["bullpen_ip_last2days_home"].notna().sum()
joined_away = result["bullpen_ip_last2days_away"].notna().sum()
both = (result["bullpen_ip_last2days_home"].notna() & result["bullpen_ip_last2days_away"].notna()).sum()

print(f"\n{'='*50}")
print(f"Total rows:     {total}")
print(f"Home joined:    {joined_home} ({100*joined_home/total:.1f}%)")
print(f"Away joined:    {joined_away} ({100*joined_away/total:.1f}%)")
print(f"Both joined:    {both} ({100*both/total:.1f}%)")

# Save
out_cols = ["game_pk", "date", "season", "home_team", "away_team", "actual_total", "closing_total",
            "bullpen_ip_last2days_home", "bullpen_ip_last2days_away",
            "bullpen_ip_last3days_home", "bullpen_ip_last3days_away",
            "closer_used_last2days_home", "closer_used_last2days_away",
            "home_season_avg_daily_bp_ip", "away_season_avg_daily_bp_ip"]
out = result[out_cols].copy()
out_path = BASE / "derived_features" / "bullpen_fatigue.parquet"
out.to_parquet(out_path, index=False)
print(f"\nSaved: {out_path}")
print(f"Shape: {out.shape}")
