#!/usr/bin/env python3
"""
NBA Player Props Historical Backfill
Collects 2023-24 through 2025-26 player prop lines, normalizes, joins outcomes.
Same architecture as MLB Props P2.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROPS_DIR = PROJECT_ROOT / "nba" / "props"
RAW_DIR = PROPS_DIR / "raw"
PROC_DIR = PROPS_DIR / "processed"
LOGS_FILE = PROJECT_ROOT / "nba" / "model_c" / "player_game_logs.parquet"

for d in [RAW_DIR, PROC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba"

MARKETS = "player_points,player_rebounds,player_assists,player_threes"

PROP_TYPE_MAP = {
    "player_points": "POINTS",
    "player_rebounds": "REBOUNDS",
    "player_assists": "ASSISTS",
    "player_threes": "THREES",
}

# NBA season date ranges (regular season + playoffs)
SEASON_RANGES = {
    "2023-24": ("2023-10-24", "2024-06-20"),
    "2024-25": ("2024-10-22", "2025-06-20"),
    "2025-26": ("2025-10-21", "2026-03-19"),  # to current date
}

SEASON_SPLIT = {
    "2023-24": "TRAIN",
    "2024-25": "VALIDATION",
    "2025-26": "OOS",
}

# NBA team name mapping (Odds API → abbreviation)
TEAM_MAP = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "LA Clippers": "LAC",
    "Los Angeles Lakers": "LAL", "LA Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}


def _determine_season(date_str):
    """Map a date to NBA season label."""
    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    # NBA seasons span Oct-June; use October as boundary
    if dt.month >= 10:
        return f"{dt.year}-{str(dt.year+1)[2:]}"
    else:
        return f"{dt.year-1}-{str(dt.year)[2:]}"


# ══════════════════════════════════════════════════════════════
# STEP 1 — EVENT COLLECTION
# ══════════════════════════════════════════════════════════════

def collect_events():
    cache_file = RAW_DIR / "events.parquet"
    if cache_file.exists():
        existing = pd.read_parquet(cache_file)
        print(f"Events cache: {len(existing):,} events")
        return existing

    print("STEP 1 — Collecting NBA events...")
    all_events = []

    for season, (start, end) in SEASON_RANGES.items():
        dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        # Don't go past today
        today = datetime.now()
        if end_dt > today:
            end_dt = today

        while dt <= end_dt:
            date_str = dt.strftime("%Y-%m-%dT12:00:00Z")
            try:
                r = requests.get(f"{BASE_URL}/events",
                                  params={"apiKey": API_KEY, "date": date_str}, timeout=30)
                if r.status_code == 200:
                    for e in r.json().get("data", []):
                        all_events.append({
                            "event_id": e["id"],
                            "commence_time": e.get("commence_time", ""),
                            "home_team": e.get("home_team", ""),
                            "away_team": e.get("away_team", ""),
                            "date": dt.strftime("%Y-%m-%d"),
                            "season": season,
                        })
            except Exception as ex:
                print(f"  {dt.strftime('%Y-%m-%d')}: {ex}")

            dt += timedelta(days=1)
            time.sleep(0.12)

            if len(all_events) % 500 == 0 and all_events:
                print(f"  {len(all_events)} events ({season})...")

    df = pd.DataFrame(all_events)
    df.to_parquet(cache_file, index=False)
    print(f"  Events: {len(df):,}")
    return df


# ══════════════════════════════════════════════════════════════
# STEP 2 — ODDS COLLECTION
# ══════════════════════════════════════════════════════════════

def collect_odds(events_df):
    cache_file = RAW_DIR / "odds_raw.parquet"

    collected_ids = set()
    existing_rows = []
    if cache_file.exists():
        existing = pd.read_parquet(cache_file)
        collected_ids = set(existing["event_id"].unique())
        existing_rows = existing.to_dict("records")
        print(f"Resuming: {len(collected_ids)} events already done")

    remaining = events_df[~events_df["event_id"].isin(collected_ids)]
    print(f"STEP 2 — Collecting odds for {len(remaining)} events...")

    all_rows = list(existing_rows)
    batch = 0
    errors = 0

    for _, event in remaining.iterrows():
        eid = event["event_id"]
        date = event["date"]
        query_date = f"{date}T12:00:00Z"

        try:
            r = requests.get(
                f"{BASE_URL}/events/{eid}/odds",
                params={"apiKey": API_KEY, "date": query_date, "regions": "us",
                        "markets": MARKETS, "oddsFormat": "american"},
                timeout=30)

            if r.status_code == 200:
                data = r.json()
                ts = data.get("timestamp", "")
                for bk in data.get("data", {}).get("bookmakers", []):
                    for mkt in bk.get("markets", []):
                        player_lines = {}
                        for o in mkt.get("outcomes", []):
                            player = o.get("description", "Unknown")
                            player_lines.setdefault(player, {})[o["name"]] = {
                                "point": o.get("point"), "price": o.get("price")}

                        for player, sides in player_lines.items():
                            over = sides.get("Over", {})
                            under = sides.get("Under", {})
                            line = over.get("point") or under.get("point")
                            if line is None:
                                continue
                            all_rows.append({
                                "event_id": eid, "game_date": date,
                                "season": event["season"],
                                "home_team": event["home_team"],
                                "away_team": event["away_team"],
                                "market": mkt["key"],
                                "player_name": player,
                                "line": float(line),
                                "over_odds": over.get("price"),
                                "under_odds": under.get("price"),
                                "bookmaker": bk["key"],
                                "snapshot_timestamp": ts,
                                "pull_timestamp": datetime.now().isoformat(),
                            })
            elif r.status_code == 422:
                pass
            else:
                errors += 1
                if errors <= 10:
                    print(f"  Event {eid}: status {r.status_code}")
        except Exception as ex:
            errors += 1
            if errors <= 10:
                print(f"  Event {eid}: {ex}")

        batch += 1
        time.sleep(0.18)

        if batch % 200 == 0:
            pd.DataFrame(all_rows).to_parquet(cache_file, index=False)
            credits = r.headers.get("x-requests-remaining", "?") if 'r' in dir() else "?"
            print(f"  Checkpoint: {batch}/{len(remaining)}, "
                  f"{len(all_rows):,} rows, credits={credits}")

    df = pd.DataFrame(all_rows)
    if len(df) > 0:
        df.to_parquet(cache_file, index=False)
    print(f"  Total rows: {len(df):,}, errors: {errors}")
    return df


# ══════════════════════════════════════════════════════════════
# STEP 3 — PLAYER NORMALIZATION
# ══════════════════════════════════════════════════════════════

def normalize_players(odds_df):
    print("\nSTEP 3 — Player normalization...")

    logs = pd.read_parquet(LOGS_FILE)
    # Build name → ID lookup
    name_to_id = logs.groupby("PLAYER_NAME")["PLAYER_ID"].first().to_dict()

    def _norm(name):
        name = name.strip()
        for sfx in [" Jr.", " Sr.", " III", " II", " IV"]:
            name = name.replace(sfx, "")
        return name.strip()

    norm_lookup = {}
    for name, pid in name_to_id.items():
        norm_lookup[name.lower()] = pid
        norm_lookup[_norm(name).lower()] = pid

    raw_names = odds_df["player_name"].unique()
    mapping = {}
    unmatched = []

    for raw in raw_names:
        if raw in name_to_id:
            mapping[raw] = name_to_id[raw]
        elif raw.lower() in norm_lookup:
            mapping[raw] = norm_lookup[raw.lower()]
        elif _norm(raw).lower() in norm_lookup:
            mapping[raw] = norm_lookup[_norm(raw).lower()]
        else:
            # Try last name
            last = raw.split()[-1].lower() if raw.split() else ""
            found = False
            for full_name, pid in name_to_id.items():
                if full_name.lower().endswith(last) and last and len(last) > 2:
                    mapping[raw] = pid
                    found = True
                    break
            if not found:
                unmatched.append(raw)

    odds_df["player_id"] = odds_df["player_name"].map(mapping)
    matched = odds_df["player_id"].notna().sum()
    print(f"  Matched: {len(mapping)} players, {matched:,}/{len(odds_df):,} rows ({matched/len(odds_df)*100:.1f}%)")
    print(f"  Unmatched: {len(unmatched)}")
    if unmatched:
        print(f"  Sample: {unmatched[:15]}")

    pd.DataFrame([{"raw_name": k, "player_id": v} for k, v in mapping.items()]).to_parquet(
        PROC_DIR / "player_mapping.parquet", index=False)

    return odds_df


# ══════════════════════════════════════════════════════════════
# STEP 4 — PROP NORMALIZATION
# ══════════════════════════════════════════════════════════════

def normalize_props(odds_df):
    print("\nSTEP 4 — Prop normalization...")
    odds_df["prop_type"] = odds_df["market"].map(PROP_TYPE_MAP)
    odds_df["dataset_split"] = odds_df["season"].map(SEASON_SPLIT)

    props = odds_df[[
        "player_id", "player_name", "event_id", "game_date", "season",
        "home_team", "away_team", "prop_type", "line", "over_odds",
        "under_odds", "bookmaker", "snapshot_timestamp", "dataset_split",
    ]].copy()

    props.to_parquet(PROC_DIR / "props_lines.parquet", index=False)
    print(f"  Normalized: {len(props):,} rows")
    return props


# ══════════════════════════════════════════════════════════════
# STEP 5 — OUTCOME JOIN
# ══════════════════════════════════════════════════════════════

def join_outcomes(props_df):
    print("\nSTEP 5 — Outcome join...")

    logs = pd.read_parquet(LOGS_FILE)
    logs["PTS"] = pd.to_numeric(logs["PTS"], errors="coerce")
    logs["REB"] = pd.to_numeric(logs["REB"], errors="coerce")
    logs["AST"] = pd.to_numeric(logs["AST"], errors="coerce")
    logs["FG3M"] = pd.to_numeric(logs["FG3M"], errors="coerce")

    actuals = logs[["PLAYER_ID", "GAME_ID", "PTS", "REB", "AST", "FG3M"]].copy()
    actuals = actuals.rename(columns={
        "PLAYER_ID": "player_id",
        "GAME_ID": "game_id",
        "PTS": "actual_POINTS",
        "REB": "actual_REBOUNDS",
        "AST": "actual_ASSISTS",
        "FG3M": "actual_THREES",
    })

    # Map event_id → game_id
    # NBA game_ids are like '0022300001'; event_ids are Odds API UUIDs
    # Join via date + team matching
    events = pd.read_parquet(RAW_DIR / "events.parquet")
    events["home_abbr"] = events["home_team"].map(TEAM_MAP)
    events["away_abbr"] = events["away_team"].map(TEAM_MAP)

    # Build game_id from logs: group by date + team
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"]).dt.strftime("%Y-%m-%d")
    game_lookup = logs[["GAME_ID", "GAME_DATE", "TEAM_ABBREVIATION"]].drop_duplicates()

    # For each event, find matching game_id via date + home team
    event_game = events.merge(
        game_lookup.rename(columns={"TEAM_ABBREVIATION": "home_abbr_log", "GAME_DATE": "date_log",
                                     "GAME_ID": "game_id"}),
        left_on=["date", "home_abbr"],
        right_on=["date_log", "home_abbr_log"],
        how="left"
    )
    event_to_game = event_game[["event_id", "game_id"]].dropna(subset=["game_id"]).drop_duplicates(subset="event_id")
    print(f"  Event → game_id mapping: {len(event_to_game)}/{len(events)} "
          f"({len(event_to_game)/len(events)*100:.1f}%)")

    # Add game_id to props
    props_df = props_df.merge(event_to_game, on="event_id", how="left")

    # Join actuals
    props_df = props_df.merge(actuals, on=["player_id", "game_id"], how="left")

    # Map actual column
    def get_actual(row):
        pt = row.get("prop_type", "")
        return row.get(f"actual_{pt}", np.nan)

    props_df["actual_value"] = props_df.apply(get_actual, axis=1)

    props_df["over_hit"] = np.where(props_df["actual_value"].notna(),
                                     (props_df["actual_value"] > props_df["line"]).astype(int), np.nan)
    props_df["under_hit"] = np.where(props_df["actual_value"].notna(),
                                      (props_df["actual_value"] < props_df["line"]).astype(int), np.nan)
    props_df["push"] = np.where(props_df["actual_value"].notna(),
                                 (props_df["actual_value"] == props_df["line"]).astype(int), np.nan)

    matched = props_df["actual_value"].notna().sum()
    print(f"  Outcomes: {matched:,}/{len(props_df):,} ({matched/len(props_df)*100:.1f}%)")

    result_cols = ["event_id", "game_id", "game_date", "season", "dataset_split",
                    "player_id", "player_name", "prop_type", "line",
                    "over_odds", "under_odds", "bookmaker",
                    "actual_value", "over_hit", "under_hit", "push"]
    result_cols = [c for c in result_cols if c in props_df.columns]
    results = props_df[result_cols]

    results.to_parquet(PROC_DIR / "props_results.parquet", index=False)
    return results


# ══════════════════════════════════════════════════════════════
# STEP 6 — MARKET VIEW
# ══════════════════════════════════════════════════════════════

def build_market_view(results_df):
    print("\nSTEP 6 — Market view...")

    grouped = results_df.groupby(
        ["event_id", "game_date", "season", "dataset_split",
         "player_id", "player_name", "prop_type"]
    )

    rows = []
    for key, group in grouped:
        event_id, game_date, season, split, player_id, player_name, prop_type = key
        lines = group["line"].dropna()
        if len(lines) == 0:
            continue

        rows.append({
            "event_id": event_id, "game_date": game_date,
            "season": season, "dataset_split": split,
            "player_id": player_id, "player_name": player_name,
            "prop_type": prop_type,
            "consensus_line": round(lines.median(), 1),
            "line_std": round(lines.std(), 2) if len(lines) > 1 else 0.0,
            "best_over_line": lines.min(),
            "best_under_line": lines.max(),
            "n_books": group["bookmaker"].nunique(),
            "actual_value": group["actual_value"].iloc[0],
            "over_hit": group["over_hit"].iloc[0],
            "under_hit": group["under_hit"].iloc[0],
        })

    mv = pd.DataFrame(rows)
    mv.to_parquet(PROC_DIR / "props_market_view.parquet", index=False)
    print(f"  Market view: {len(mv):,} unique player-prop-games")
    return mv


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    log("=" * 70)
    log("NBA PLAYER PROPS — HISTORICAL BACKFILL")
    log("=" * 70)
    log(f"Player game logs: {LOGS_FILE}")
    log()

    events_df = collect_events()
    log(f"\nSECTION 0 — COLLECTION SUMMARY")
    log(f"  Events: {len(events_df):,}")
    log(f"  By season: {events_df['season'].value_counts().sort_index().to_dict()}")
    log()

    odds_df = collect_odds(events_df)
    log(f"  Raw odds: {len(odds_df):,}")
    if len(odds_df) > 0:
        log(f"  Markets: {odds_df['market'].value_counts().to_dict()}")
        log(f"  Books: {odds_df['bookmaker'].nunique()}")
    log()

    if len(odds_df) == 0:
        log("NO ODDS DATA. Stopping.")
        with open(PROPS_DIR / "p2_summary.txt", "w") as f:
            f.write("\n".join(lines))
        return

    odds_df = normalize_players(odds_df)
    props_df = normalize_props(odds_df)
    results_df = join_outcomes(props_df)
    mv = build_market_view(results_df)

    log()
    log("=" * 70)
    log("SECTION 1 — DATA QUALITY")
    log("=" * 70)
    log()
    log(f"Player mapping: {results_df['player_id'].notna().mean()*100:.1f}%")
    log(f"Outcome join: {results_df['actual_value'].notna().sum():,}/{len(results_df):,} "
        f"({results_df['actual_value'].notna().mean()*100:.1f}%)")
    dupes = results_df.duplicated(subset=["event_id", "player_id", "prop_type", "bookmaker"]).sum()
    log(f"Duplicates: {dupes}")
    log()

    log("Line ranges:")
    for pt in sorted(results_df["prop_type"].dropna().unique()):
        sub = results_df[results_df["prop_type"] == pt]["line"]
        log(f"  {pt:<12s}: min={sub.min():.1f}, max={sub.max():.1f}, median={sub.median():.1f}")
    log()

    log("=" * 70)
    log("SECTION 2 — MARKET STRUCTURE")
    log("=" * 70)
    log()
    log(f"Unique player-prop-games: {len(mv):,}")
    ppg = mv.groupby("event_id").size()
    log(f"Props per game: median={ppg.median():.0f}, mean={ppg.mean():.1f}")
    log(f"Books per prop: median={mv['n_books'].median():.0f}, mean={mv['n_books'].mean():.1f}")
    log()
    log("Props by type:")
    for pt in sorted(mv["prop_type"].unique()):
        log(f"  {pt:<12s}: {(mv['prop_type']==pt).sum():>7,}")
    log()

    log("=" * 70)
    log("SECTION 3 — FINAL DATASET SHAPE")
    log("=" * 70)
    log()
    log(f"Total market view: {len(mv):,}")
    for split in ["TRAIN", "VALIDATION", "OOS"]:
        n = (mv["dataset_split"] == split).sum()
        log(f"  {split}: {n:,}")
    with_outcome = mv["actual_value"].notna().sum()
    log(f"With outcomes: {with_outcome:,}/{len(mv):,} ({with_outcome/len(mv)*100:.1f}%)")
    log()

    log("=" * 70)
    log("SECTION 4 — READINESS CHECK")
    log("=" * 70)
    log()
    if len(mv) > 10000 and with_outcome > 5000:
        log("STATUS: READY FOR MODELING")
        log(f"  {len(mv):,} player-prop-games with market lines")
        log(f"  {with_outcome:,} with graded outcomes")
        log(f"  4 prop types, {mv['n_books'].median():.0f} median books per prop")
        log(f"  Train/Validation/OOS split tagged")
    else:
        log("STATUS: INSUFFICIENT DATA")
    log()

    with open(PROPS_DIR / "p2_summary.txt", "w") as f:
        f.write("\n".join(lines))

    log("=" * 70)
    log("Files saved:")
    for f in ["raw/events.parquet", "raw/odds_raw.parquet",
              "processed/player_mapping.parquet", "processed/props_lines.parquet",
              "processed/props_results.parquet", "processed/props_market_view.parquet",
              "p2_summary.txt"]:
        log(f"  nba/props/{f}")
    log("=" * 70)


if __name__ == "__main__":
    main()
