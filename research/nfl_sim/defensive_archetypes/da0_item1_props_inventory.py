#!/usr/bin/env python3
"""DA-0 Item 1: Prop archive inventory + name resolution.

Reads every parquet under data/odds_archive/nfl/props/season=*/,
reassigns to NFL season, writes inventory + name resolution tables.
"""
import glob
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "nfl_sim" / "defensive_archetypes"

# ── Load all props ──
print("Loading props files...")
frames = []
for f in sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=*/month=*/data_*.parquet"))):
    df = pd.read_parquet(f)
    df["_source_file"] = os.path.basename(f)
    df["_source_dir"] = str(Path(f).parent.relative_to(ROOT))
    frames.append(df)
# Manual / scratch files (2026)
for f in sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2026/manual/*.parquet"))):
    df = pd.read_parquet(f)
    df["_source_file"] = os.path.basename(f)
    df["_source_dir"] = "season=2026/manual"
    frames.append(df)

all_props = pd.concat(frames, ignore_index=True)
print(f"Total rows loaded: {len(all_props):,}")

# ── Assign NFL season by commence_time (Sep-Feb → the September year) ──
all_props["_ct"] = pd.to_datetime(all_props["commence_time"], utc=True, errors="coerce")
all_props["_ct_month"] = all_props["_ct"].dt.month
all_props["_ct_year"] = all_props["_ct"].dt.year
# NFL season: if month >= 9 → year; if month <= 2 → year - 1
all_props["nfl_season"] = np.where(
    all_props["_ct_month"] >= 3,
    np.where(all_props["_ct_month"] >= 9, all_props["_ct_year"], np.nan),
    all_props["_ct_year"] - 1)
# Handle March-August: these shouldn't exist for NFL but assign to prior season if Jan-Feb
# and to current year if Sep+
all_props["nfl_season"] = all_props["nfl_season"].fillna(all_props["_ct_year"])
all_props["nfl_season"] = all_props["nfl_season"].astype(int)

# Count reassigned rows
all_props["_folder_season"] = all_props["_source_dir"].str.extract(r"season=(\d+)").astype(int)
reassigned = (all_props["nfl_season"] != all_props["_folder_season"]).sum()
print(f"Rows reassigned to a different NFL season: {reassigned:,}")

# ── Parse last_update and commence_time for timing ──
all_props["_lu"] = pd.to_datetime(all_props["last_update"], utc=True, errors="coerce")
all_props["_hours_before_kick"] = (all_props["_ct"] - all_props["_lu"]).dt.total_seconds() / 3600
all_props["_inplay"] = all_props["_lu"] >= all_props["_ct"]
all_props["_player_game"] = all_props["event_id"].astype(str) + "|" + all_props["player_name"].astype(str)

# ── Inventory per (nfl_season, market_key, bookmaker) ──
print("Building inventory...")
inv_rows = []
for (season, mk, bk), g in all_props.groupby(["nfl_season", "market_key", "bookmaker"]):
    h = g["_hours_before_kick"].dropna()
    inv_rows.append({
        "nfl_season": season, "market_key": mk, "bookmaker": bk,
        "n_rows": len(g),
        "n_events": g["event_id"].nunique(),
        "n_player_games": g["_player_game"].nunique(),
        "hours_before_kick_p10": round(h.quantile(0.1), 2) if len(h) else None,
        "hours_before_kick_p50": round(h.quantile(0.5), 2) if len(h) else None,
        "hours_before_kick_p90": round(h.quantile(0.9), 2) if len(h) else None,
        "share_inplay_or_after": round(g["_inplay"].mean(), 4),
        "n_distinct_pull_batch": g["pull_batch"].nunique() if "pull_batch" in g.columns else 0,
    })

inv = pd.DataFrame(inv_rows)
inv.to_parquet(OUT / "da0_props_inventory.parquet", index=False)
print(f"Inventory: {len(inv)} rows → da0_props_inventory.parquet")

# ── Per-event span of last_update ──
per_event = all_props.groupby(["nfl_season", "event_id"]).agg(
    lu_min=("_lu", "min"), lu_max=("_lu", "max")).dropna()
per_event["span_hours"] = (per_event["lu_max"] - per_event["lu_min"]).dt.total_seconds() / 3600
span_summary = per_event.groupby(per_event.index.get_level_values(0))["span_hours"].agg(
    span_p50=lambda x: x.quantile(0.5), span_p90=lambda x: x.quantile(0.9))
print("\nPer-event last_update span (hours):")
print(span_summary.to_string())

# ── Season-level: events vs nflverse schedule ──
print("\nLoading nflverse schedules...")
try:
    import nflreadpy
    for season in sorted(all_props["nfl_season"].unique()):
        sched = nflreadpy.load_schedules([int(season)])
        if hasattr(sched, "to_pandas"):
            sched = sched.to_pandas()
        reg = sched[sched["game_type"] == "REG"]
        post = sched[sched["game_type"] != "REG"]
        prop_events = all_props[all_props["nfl_season"] == season]["event_id"].nunique()
        print(f"  {season}: schedule REG={len(reg)} POST={len(post)}  prop events={prop_events}")
        # Weeks with zero coverage
        prop_weeks = set()
        season_props = all_props[all_props["nfl_season"] == season]
        if "week" in sched.columns:
            # Map events to weeks via commence_time matching
            for w in sorted(reg["week"].unique()):
                wg = reg[reg["week"] == w]
                # Check if any prop event matches a game in this week (by team pair)
                week_teams = set(zip(wg["home_team"], wg["away_team"]))
                has_coverage = False
                for _, r in season_props.drop_duplicates("event_id").iterrows():
                    if (r["home_team"], r["away_team"]) in week_teams or \
                       (r["away_team"], r["home_team"]) in week_teams:
                        has_coverage = True
                        break
                if has_coverage:
                    prop_weeks.add(w)
            all_weeks = set(reg["week"].unique())
            missing = sorted(all_weeks - prop_weeks)
            if missing:
                print(f"    weeks with zero prop coverage: {missing}")
            else:
                print(f"    all {len(all_weeks)} weeks covered")
except Exception as e:
    print(f"  nflverse schedule load failed: {e}")

# ── 2026 snapshot_tag breakdown ──
s26 = all_props[all_props["nfl_season"] == 2026]
if "snapshot_tag" in s26.columns:
    print("\n2026 rows/events by snapshot_tag:")
    for tag, g in s26.groupby("snapshot_tag", dropna=False):
        print(f"  {tag}: {len(g):,} rows, {g['event_id'].nunique()} events")

# ── Books per season ──
print("\nBooks per season:")
for season, g in all_props.groupby("nfl_season"):
    books = sorted(g["bookmaker"].unique())
    print(f"  {season}: {len(books)} books — {', '.join(books[:8])}" +
          (f" +{len(books)-8} more" if len(books) > 8 else ""))

# ── Snapshots per event (prove single-snapshot claim) ──
print("\nSnapshots per event (historical seasons):")
for season in [2023, 2024, 2025]:
    sg = all_props[all_props["nfl_season"] == season]
    snaps_per_event = sg.groupby("event_id")["pull_batch"].nunique()
    print(f"  {season}: p50={snaps_per_event.quantile(0.5):.0f} p90={snaps_per_event.quantile(0.9):.0f} "
          f"max={snaps_per_event.max()} mean={snaps_per_event.mean():.1f}")

# ══════════════════════════════════════════════════════════════════════
# NAME RESOLUTION
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("NAME RESOLUTION")
print("=" * 60)


def normalize_name(name):
    """Normalize: lowercase, strip diacritics, remove Jr/Sr/II/III/IV, punctuation."""
    if not name or pd.isna(name):
        return ""
    s = str(name).strip()
    # Remove diacritics
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    # Remove suffixes
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    # Remove punctuation except spaces
    s = re.sub(r"[^a-z\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Build roster lookup: (normalized_name, team) → gsis_id
print("Loading nflreadpy rosters...")
roster_frames = []
try:
    import nflreadpy
    for season in range(2021, 2027):
        try:
            r = nflreadpy.load_rosters([season])
            if hasattr(r, "to_pandas"):
                r = r.to_pandas()
            r["_season"] = season
            roster_frames.append(r)
        except Exception:
            pass
except Exception as e:
    print(f"  roster load failed: {e}")

if roster_frames:
    rosters = pd.concat(roster_frames, ignore_index=True)
    rosters["_norm_name"] = rosters["full_name"].apply(normalize_name)
    # Build lookup: (norm_name, team, season) → gsis_id
    roster_lookup = {}
    ambiguous = {}
    for _, r in rosters.iterrows():
        key = (r["_norm_name"], r.get("team", ""), int(r["_season"]))
        if key in roster_lookup and roster_lookup[key] != r.get("gsis_id"):
            ambiguous[key] = (roster_lookup[key], r.get("gsis_id"))
        roster_lookup[key] = r.get("gsis_id")
    print(f"Roster lookup: {len(roster_lookup):,} entries, {len(ambiguous)} ambiguous")

# Resolve prop player names
# We need to map the prop team names to nflverse abbreviations
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
    # Alternate names
    "Oakland Raiders": "LV", "Washington Football Team": "WAS", "Washington Redskins": "WAS",
}

# Build per-row resolution
print("Resolving names...")
all_props["_norm_name"] = all_props["player_name"].apply(normalize_name)
all_props["_home_abbr"] = all_props["home_team"].map(TEAM_MAP)
all_props["_away_abbr"] = all_props["away_team"].map(TEAM_MAP)

resolved = []
for idx, r in all_props.iterrows():
    nn = r["_norm_name"]
    if not nn:
        resolved.append(None)
        continue
    season = int(r["nfl_season"])
    # Try both teams
    gsis = roster_lookup.get((nn, r.get("_home_abbr", ""), season))
    if not gsis:
        gsis = roster_lookup.get((nn, r.get("_away_abbr", ""), season))
    if not gsis:
        # Try without team
        matches = [(k, v) for k, v in roster_lookup.items() if k[0] == nn and k[2] == season]
        if len(matches) == 1:
            gsis = matches[0][1]
    resolved.append(gsis)

all_props["gsis_id"] = resolved
all_props["_resolved"] = all_props["gsis_id"].notna()

# Resolution rate per season per market
print("\nResolution rate per season × market:")
res_rates = all_props.groupby(["nfl_season", "market_key"]).agg(
    n_rows=("_resolved", "count"),
    n_resolved=("_resolved", "sum"),
    rate=("_resolved", "mean")).reset_index()
res_rates["rate"] = (res_rates["rate"] * 100).round(1)

for season in sorted(res_rates["nfl_season"].unique()):
    s = res_rates[res_rates["nfl_season"] == season]
    print(f"\n  {season}:")
    for _, r in s.iterrows():
        print(f"    {r['market_key']:30s} {r['n_resolved']:>7,}/{r['n_rows']:>7,}  {r['rate']:5.1f}%")

# Top 30 unresolved names
unres = all_props[~all_props["_resolved"] & all_props["_norm_name"].str.len().gt(0)]
top_unres = unres.groupby("player_name").size().sort_values(ascending=False).head(30)
print("\nTop 30 unresolved names:")
for name, count in top_unres.items():
    print(f"  {name:40s} {count:>6,}")

# Ambiguous matches
if ambiguous:
    print(f"\nAmbiguous matches (one name → two ids): {len(ambiguous)}")
    for k, v in list(ambiguous.items())[:10]:
        print(f"  {k} → {v}")

# Player-game counts for yardage/reception markets
print("\nPlayer-game counts for key markets (two-way only):")
two_way = all_props[all_props["under_price"].notna()]
for mk in ["player_receptions", "player_reception_yds", "player_rush_yds",
            "player_rush_attempts", "player_pass_yds", "player_pass_attempts",
            "player_pass_completions", "player_pass_tds", "player_pass_interceptions"]:
    for season in sorted(two_way["nfl_season"].unique()):
        sg = two_way[(two_way["nfl_season"] == season) & (two_way["market_key"] == mk)]
        pg = sg["_player_game"].nunique()
        if pg > 0:
            print(f"  {season} {mk:35s} {pg:>7,} player-games")

# Resolution check
overall_rate = all_props["_resolved"].mean()
print(f"\nOverall resolution rate: {overall_rate*100:.1f}%")
if overall_rate < 0.50:
    print("HALT: resolution < 50%")
    sys.exit(1)

# Write name resolution table
nr_out = all_props[["nfl_season", "event_id", "market_key", "player_name", "_norm_name",
                     "home_team", "away_team", "gsis_id", "_resolved"]].copy()
nr_out.columns = ["nfl_season", "event_id", "market_key", "player_name", "norm_name",
                   "home_team", "away_team", "gsis_id", "resolved"]
# Deduplicate to player-game level
nr_dedup = nr_out.drop_duplicates(subset=["nfl_season", "event_id", "player_name", "market_key"])
nr_dedup.to_parquet(OUT / "da0_name_resolution.parquet", index=False)
print(f"\nName resolution: {len(nr_dedup):,} rows → da0_name_resolution.parquet")

print("\nDONE")
