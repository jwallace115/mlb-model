#!/usr/bin/env python3
"""DA-0 Item 3: Settlement source — join official stats to resolved prop player-games."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "nfl_sim" / "defensive_archetypes"

import nflreadpy

# ── Load resolved prop player-games from Item 1 ──
nr = pd.read_parquet(OUT / "da0_name_resolution.parquet")
nr = nr[nr["resolved"]].copy()
print(f"Resolved prop rows: {len(nr):,}")

# ── Load official player stats ──
print("Loading official player stats...")
stats_frames = []
for season in range(2021, 2027):
    try:
        s = nflreadpy.load_player_stats(seasons=[season], summary_level="week")
        if hasattr(s, "to_pandas"):
            s = s.to_pandas()
        s["_season"] = season
        stats_frames.append(s)
        print(f"  {season}: {len(s):,} rows")
    except Exception as e:
        print(f"  {season}: {e}")

stats = pd.concat(stats_frames, ignore_index=True)
print(f"Total official stats: {len(stats):,}")
print(f"Columns: {[c for c in stats.columns if 'receptions' in c or 'receiving' in c or 'rushing' in c or 'passing' in c or 'player_id' in c or 'game_id' in c][:20]}")

# ── Load schedules for event→game_id mapping ──
print("\nLoading schedules for event mapping...")
sched_frames = []
for season in range(2021, 2027):
    try:
        s = nflreadpy.load_schedules([season])
        if hasattr(s, "to_pandas"):
            s = s.to_pandas()
        sched_frames.append(s)
    except Exception:
        pass
sched = pd.concat(sched_frames, ignore_index=True)

# Map prop events to game_id via team pairs + kickoff time
# The prop data has home_team (full name) and commence_time; schedule has home_team (abbr) and gameday+gametime
TEAM_MAP = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
    "Oakland Raiders": "LV", "Washington Football Team": "WAS",
}

nr["_home_abbr"] = nr["home_team"].map(TEAM_MAP)
nr["_away_abbr"] = nr["away_team"].map(TEAM_MAP)

# Deduplicate to unique (event_id, player) level for the join
prop_pg = nr.drop_duplicates(subset=["nfl_season", "event_id", "player_name", "market_key"]).copy()
print(f"\nUnique prop player-game-market rows: {len(prop_pg):,}")

# Map event_id → game_id via schedule
print("Mapping events to game_ids...")
event_to_game = {}
for _, r in prop_pg.drop_duplicates("event_id").iterrows():
    ha = r.get("_home_abbr", "")
    aa = r.get("_away_abbr", "")
    season = int(r["nfl_season"])
    ss = sched[(sched["season"] == season) & (sched["home_team"] == ha) & (sched["away_team"] == aa)]
    if len(ss) == 1:
        event_to_game[r["event_id"]] = ss.iloc[0].get("game_id")
    elif len(ss) > 1:
        # Multiple matches — use commence_time to disambiguate
        ct = pd.to_datetime(r.get("commence_time", ""), utc=True, errors="coerce") if r.get("commence_time") else None
        if ct is not None and "gameday" in ss.columns:
            best = None
            best_diff = float("inf")
            for _, sg in ss.iterrows():
                try:
                    gdt = pd.to_datetime(str(sg.gameday) + " " + str(sg.gametime), errors="coerce")
                    if gdt is not None:
                        diff = abs((ct - gdt.tz_localize("US/Eastern").tz_convert("UTC")).total_seconds())
                        if diff < best_diff:
                            best_diff = diff
                            best = sg.get("game_id")
                except Exception:
                    pass
            if best and best_diff < 3600:
                event_to_game[r["event_id"]] = best

prop_pg["game_id"] = prop_pg["event_id"].map(event_to_game)
mapped = prop_pg["game_id"].notna().sum()
total = len(prop_pg)
print(f"Event→game_id mapped: {mapped:,}/{total:,} ({100*mapped/total:.1f}%)")

# ── Join to official stats by (gsis_id, game_id) ──
print("\nJoining to official stats...")
# The stats use player_id (= gsis_id) and recent_team + week
# But game_id is in the stats too
stat_cols = ["player_id", "recent_team", "week", "season",
             "receptions", "receiving_yards", "carries", "rushing_yards",
             "passing_yards", "completions", "attempts", "passing_tds", "interceptions"]
stat_cols = [c for c in stat_cols if c in stats.columns]
# Add game_id if present
if "game_id" not in stats.columns:
    # Build game_id from season + week + teams
    print("  game_id not in stats — building from schedule")

stats_slim = stats[stat_cols + (["game_id"] if "game_id" in stats.columns else [])].copy()

# Join
joined = prop_pg.merge(
    stats_slim,
    left_on=["gsis_id", "game_id"],
    right_on=["player_id", "game_id"],
    how="left",
    suffixes=("", "_stat"))

joined["_joined"] = joined["player_id"].notna() if "player_id" in joined.columns else False
join_rate = joined["_joined"].mean()
print(f"Join rate overall: {join_rate*100:.1f}%")

# Per season per market
print("\nJoin rate per season × market:")
jr = joined.groupby(["nfl_season", "market_key"]).agg(
    n=("_joined", "count"),
    n_joined=("_joined", "sum"),
    rate=("_joined", "mean")).reset_index()
jr["rate"] = (jr["rate"] * 100).round(1)
for season in sorted(jr["nfl_season"].unique()):
    s = jr[jr["nfl_season"] == season]
    print(f"\n  {season}:")
    for _, r in s.iterrows():
        print(f"    {r['market_key']:35s} {r['n_joined']:>6,}/{r['n']:>6,}  {r['rate']:5.1f}%")

# ── PBP comparison sample (200 rows) ──
print("\n" + "=" * 60)
print("PBP vs OFFICIAL comparison (200-row sample)")
print("=" * 60)

# Load PBP for a season with good join rates
pbp = nflreadpy.load_pbp([2024])
if hasattr(pbp, "to_pandas"):
    pbp = pbp.to_pandas()

# Get joined rows for 2024 with receptions
sample_pool = joined[(joined["nfl_season"] == 2024) &
                      (joined["_joined"]) &
                      (joined["market_key"] == "player_receptions")].head(200)

mismatches = 0
mismatch_examples = []
for _, r in sample_pool.iterrows():
    gid = r.get("game_id", "")
    pid = r.get("gsis_id", "")
    if not gid or not pid:
        continue
    # PBP receptions: count complete_pass where receiver_player_id == pid
    game_pbp = pbp[pbp["game_id"] == gid]
    pbp_rec = len(game_pbp[(game_pbp["receiver_player_id"] == pid) &
                            (game_pbp["complete_pass"] == 1)])
    official_rec = r.get("receptions", np.nan)
    if pd.notna(official_rec) and pbp_rec != int(official_rec):
        mismatches += 1
        if len(mismatch_examples) < 10:
            mismatch_examples.append({
                "player": r["player_name"], "game_id": gid,
                "pbp_rec": pbp_rec, "official_rec": int(official_rec),
                "diff": pbp_rec - int(official_rec)})

print(f"Compared: {len(sample_pool)} rows, {mismatches} mismatches ({100*mismatches/max(len(sample_pool),1):.1f}%)")
if mismatch_examples:
    print("Examples:")
    for m in mismatch_examples:
        print(f"  {m['player']:25s} {m['game_id']}  pbp={m['pbp_rec']} official={m['official_rec']} diff={m['diff']}")

# Write settlement join
out_cols = ["nfl_season", "event_id", "game_id", "market_key", "player_name",
            "gsis_id", "_joined"]
for c in ["receptions", "receiving_yards", "carries", "rushing_yards",
           "passing_yards", "completions", "attempts", "passing_tds", "interceptions"]:
    if c in joined.columns:
        out_cols.append(c)
joined[out_cols].to_parquet(OUT / "da0_settlement_join.parquet", index=False)
print(f"\nSettlement join: {len(joined):,} rows → da0_settlement_join.parquet")
print("DONE")
