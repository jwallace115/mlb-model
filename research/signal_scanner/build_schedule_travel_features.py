#!/usr/bin/env python3
"""
Task 2 — Schedule / Travel Features

Computes per-game rest, road-trip, home-stand, timezone change,
and days-since-travel features from game_table.

Output: research/signal_scanner/derived_features/schedule_travel.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ── Timezone offsets (UTC hours, summer approximation) ────────────────
# For timezone_change we just need the magnitude of shift, not exact DST.
_TZ_OFFSET = {
    "America/New_York": -4, "America/Toronto": -4, "America/Detroit": -4,
    "America/Chicago": -5, "America/Denver": -6, "America/Phoenix": -7,
    "America/Los_Angeles": -7,
}

_TEAM_TZ = {
    "BAL": "America/New_York",  "BOS": "America/New_York",
    "NYY": "America/New_York",  "NYM": "America/New_York",
    "PHI": "America/New_York",  "WSN": "America/New_York",
    "ATL": "America/New_York",  "MIA": "America/New_York",
    "TBR": "America/New_York",  "TOR": "America/Toronto",
    "DET": "America/Detroit",   "CLE": "America/New_York",
    "PIT": "America/New_York",  "CIN": "America/New_York",
    "CHW": "America/Chicago",   "CHC": "America/Chicago",
    "MIL": "America/Chicago",   "MIN": "America/Chicago",
    "STL": "America/Chicago",   "KCR": "America/Chicago",
    "HOU": "America/Chicago",   "TEX": "America/Chicago",
    "COL": "America/Denver",
    "ARI": "America/Phoenix",
    "LAA": "America/Los_Angeles", "LAD": "America/Los_Angeles",
    "SDP": "America/Los_Angeles", "SFG": "America/Los_Angeles",
    "SEA": "America/Los_Angeles", "OAK": "America/Los_Angeles",
}


def _tz_offset(team):
    tz = _TEAM_TZ.get(team)
    return _TZ_OFFSET.get(tz, -5)  # default Central


# ── Load data ─────────────────────────────────────────────────────────
ft = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "feature_table.parquet")
ft["date"] = pd.to_datetime(ft["date"])

gt = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])

br = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "bet_results.parquet")
br["date"] = pd.to_datetime(br["date"])

# ── Build scanner dataset ────────────────────────────────────────────
scanner = ft[ft["season"].isin([2024, 2025])].copy()
scanner = scanner.merge(br[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"}),
                        on="game_pk", how="inner")
scanner.rename(columns={"close_total": "closing_total"}, inplace=True)
print(f"Scanner dataset: {len(scanner)} games")

# ── Build full schedule (all years for lookback) ─────────────────────
# Create team-centric schedule: one row per team per game
games = gt[["game_pk", "date", "home_team", "away_team", "venue_name"]].copy()

home_sched = games.rename(columns={"home_team": "team", "away_team": "opponent"}).copy()
home_sched["is_home"] = True

away_sched = games.rename(columns={"away_team": "team", "home_team": "opponent"}).copy()
away_sched["is_home"] = False

sched = pd.concat([home_sched, away_sched], ignore_index=True)
sched = sched.sort_values(["team", "date", "game_pk"]).reset_index(drop=True)

# ── Days rest (already in game_table, but let's verify and use those) ─
# game_table has home_rest_days and away_rest_days — use directly
# But we need to compute additional features from the schedule

# ── Road trip / Home stand game numbers ──────────────────────────────
def compute_streak_features(group):
    """For a team's schedule, compute road trip game # and home stand game #."""
    group = group.sort_values("date").copy()
    is_home = group["is_home"].values

    road_trip_num = np.zeros(len(group), dtype=int)
    home_stand_num = np.zeros(len(group), dtype=int)

    road_count = 0
    home_count = 0

    for i in range(len(group)):
        if is_home[i]:
            home_count += 1
            road_count = 0
            home_stand_num[i] = home_count
        else:
            road_count += 1
            home_count = 0
            road_trip_num[i] = road_count

    group["road_trip_game_num"] = road_trip_num
    group["home_stand_game_num"] = home_stand_num
    return group


print("Computing road trip / home stand sequences...")
sched = sched.groupby("team", group_keys=False).apply(compute_streak_features)

# ── Timezone change ──────────────────────────────────────────────────
# For each game, the "city timezone" is the home team's timezone
# (since the game is played at the home team's city)
sched["game_tz_offset"] = sched.apply(
    lambda r: _tz_offset(r["team"]) if r["is_home"] else _tz_offset(r["opponent"]),
    axis=1
)

def compute_tz_change(group):
    """Compute timezone change from previous game's city."""
    group = group.sort_values("date").copy()
    prev_tz = group["game_tz_offset"].shift(1)
    group["timezone_change"] = (group["game_tz_offset"] - prev_tz).abs()
    return group

sched = sched.groupby("team", group_keys=False).apply(compute_tz_change)

# ── Days since travel (city change) ──────────────────────────────────
# "City" is approximated by the home_team of the game venue
sched["game_city"] = sched.apply(
    lambda r: r["team"] if r["is_home"] else r["opponent"], axis=1
)

def compute_days_since_travel(group):
    group = group.sort_values("date").copy()
    cities = group["game_city"].values
    dates = group["date"].values
    days_since = np.full(len(group), np.nan)

    for i in range(1, len(group)):
        if cities[i] != cities[i-1]:
            days_since[i] = 0  # traveled today
        else:
            # Find last city change
            for j in range(i-1, -1, -1):
                if cities[j] != cities[i]:
                    days_since[i] = (pd.Timestamp(dates[i]) - pd.Timestamp(dates[j])).days
                    break
            else:
                days_since[i] = np.nan  # never changed (season start)

    group["days_since_travel"] = days_since
    return group


print("Computing days-since-travel...")
sched = sched.groupby("team", group_keys=False).apply(compute_days_since_travel)

# ── Filter to 2024-2025 and separate home/away ──────────────────────
sched_2425 = sched[sched["date"].dt.year.isin([2024, 2025])].copy()

# Home features: for the home team
home_feats = sched_2425[sched_2425["is_home"]][
    ["game_pk", "team", "date", "home_stand_game_num"]
].rename(columns={"team": "home_team", "home_stand_game_num": "home_stand_game_num_home"})

# Away features: for the away team
away_feats = sched_2425[~sched_2425["is_home"]][
    ["game_pk", "team", "date", "road_trip_game_num", "timezone_change", "days_since_travel"]
].rename(columns={
    "team": "away_team",
    "road_trip_game_num": "road_trip_game_num_away",
    "timezone_change": "timezone_change_away",
    "days_since_travel": "days_since_travel_away",
})

# ── Join to scanner ──────────────────────────────────────────────────
result = scanner.copy()

# Rest days already in feature table
result.rename(columns={
    "home_rest_days": "days_rest_home",
    "away_rest_days": "days_rest_away",
}, inplace=True)

result = result.merge(home_feats[["game_pk", "home_stand_game_num_home"]],
                      on="game_pk", how="left")
result = result.merge(away_feats[["game_pk", "road_trip_game_num_away",
                                   "timezone_change_away", "days_since_travel_away"]],
                      on="game_pk", how="left")

# ── Coverage report ──────────────────────────────────────────────────
total = len(result)
for col in ["days_rest_home", "days_rest_away", "home_stand_game_num_home",
            "road_trip_game_num_away", "timezone_change_away", "days_since_travel_away"]:
    n = result[col].notna().sum()
    print(f"  {col}: {n}/{total} ({100*n/total:.1f}%)")

out_cols = ["game_pk", "date", "season", "home_team", "away_team", "actual_total", "closing_total",
            "days_rest_home", "days_rest_away",
            "road_trip_game_num_away", "home_stand_game_num_home",
            "timezone_change_away", "days_since_travel_away"]
out = result[out_cols].copy()

print(f"\n{'='*50}")
print(f"Total rows:  {total}")
all_joined = out.dropna(subset=["road_trip_game_num_away", "timezone_change_away"])
print(f"Rows joined: {len(all_joined)} ({100*len(all_joined)/total:.1f}%)")

out_path = BASE / "derived_features" / "schedule_travel.parquet"
out.to_parquet(out_path, index=False)
print(f"\nSaved: {out_path}")
print(f"Shape: {out.shape}")

# Quick stats
print("\n── Feature distributions ──")
for col in ["days_rest_home", "days_rest_away", "road_trip_game_num_away",
            "home_stand_game_num_home", "timezone_change_away", "days_since_travel_away"]:
    s = out[col].dropna()
    print(f"  {col}: mean={s.mean():.2f}, median={s.median():.1f}, max={s.max():.0f}, N={len(s)}")
