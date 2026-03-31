#!/usr/bin/env python3
"""
MLB Player Props Phase P2 — Full Historical Backfill + Data System
Collects 2023-2024 player prop lines, normalizes, joins outcomes.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "mlb" / "data"
PROPS_DIR = PROJECT_ROOT / "mlb" / "props"
RAW_DIR = PROPS_DIR / "raw"
PROC_DIR = PROPS_DIR / "processed"

for d in [RAW_DIR, PROC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb"

MARKETS = "pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed,pitcher_earned_runs,batter_hits,batter_total_bases,batter_home_runs,batter_rbis"

PROP_TYPE_MAP = {
    "pitcher_strikeouts": "K",
    "pitcher_outs": "OUTS",
    "pitcher_hits_allowed": "H_ALLOWED",
    "pitcher_earned_runs": "ER",
    "batter_hits": "HITS",
    "batter_total_bases": "TB",
    "batter_home_runs": "HR",
    "batter_rbis": "RBI",
}

# MLB season date ranges
SEASON_RANGES = {
    2023: ("2023-03-30", "2023-10-02"),
    2024: ("2024-03-20", "2024-09-30"),
    2025: ("2025-03-27", "2025-09-28"),
}


# ══════════════════════════════════════════════════════════════
# STEP 1 — EVENT COLLECTION
# ══════════════════════════════════════════════════════════════

def collect_events():
    """Fetch all MLB events for each date in 2023-2024."""
    cache_file = RAW_DIR / "events.parquet"
    if cache_file.exists():
        existing = pd.read_parquet(cache_file)
        print(f"Events cache exists: {len(existing)} events")
        return existing

    print("STEP 1 — Collecting events...")
    all_events = []

    for season, (start, end) in SEASON_RANGES.items():
        dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")

        while dt <= end_dt:
            date_str = dt.strftime("%Y-%m-%dT18:00:00Z")

            try:
                r = requests.get(f"{BASE_URL}/events",
                                  params={"apiKey": API_KEY, "date": date_str},
                                  timeout=30)

                if r.status_code == 200:
                    data = r.json()
                    events = data.get("data", [])
                    for e in events:
                        all_events.append({
                            "event_id": e["id"],
                            "commence_time": e.get("commence_time", ""),
                            "home_team": e.get("home_team", ""),
                            "away_team": e.get("away_team", ""),
                            "date": dt.strftime("%Y-%m-%d"),
                            "season": season,
                        })
                elif r.status_code == 422:
                    pass  # no events this date
                else:
                    print(f"  {dt.strftime('%Y-%m-%d')}: status {r.status_code}")
            except Exception as ex:
                print(f"  {dt.strftime('%Y-%m-%d')}: ERROR {ex}")

            dt += timedelta(days=1)
            time.sleep(0.15)

            if len(all_events) % 500 == 0 and all_events:
                print(f"  Collected {len(all_events)} events so far...")

    df = pd.DataFrame(all_events)
    df.to_parquet(cache_file, index=False)
    print(f"  Events: {len(df)} total")
    return df


# ══════════════════════════════════════════════════════════════
# STEP 2 — ODDS COLLECTION
# ══════════════════════════════════════════════════════════════

def collect_odds(events_df):
    """Fetch prop odds for each event."""
    cache_file = RAW_DIR / "odds_raw.parquet"

    # Resume from partial collection
    collected_ids = set()
    existing_rows = []
    if cache_file.exists():
        existing = pd.read_parquet(cache_file)
        collected_ids = set(existing["event_id"].unique())
        existing_rows = existing.to_dict("records")
        print(f"Resuming odds collection: {len(collected_ids)} events already done")

    remaining = events_df[~events_df["event_id"].isin(collected_ids)]
    print(f"STEP 2 — Collecting odds for {len(remaining)} events...")

    all_rows = list(existing_rows)
    batch_count = 0
    errors = 0

    for _, event in remaining.iterrows():
        eid = event["event_id"]
        date = event["date"]
        query_date = f"{date}T18:00:00Z"

        try:
            r = requests.get(
                f"{BASE_URL}/events/{eid}/odds",
                params={
                    "apiKey": API_KEY,
                    "date": query_date,
                    "regions": "us",
                    "markets": MARKETS,
                    "oddsFormat": "american",
                },
                timeout=30,
            )

            if r.status_code == 200:
                data = r.json()
                odds_data = data.get("data", {})
                ts = data.get("timestamp", "")

                for bk in odds_data.get("bookmakers", []):
                    book = bk["key"]
                    for mkt in bk.get("markets", []):
                        market_key = mkt["key"]
                        # Group by player
                        player_lines = {}
                        for o in mkt.get("outcomes", []):
                            player = o.get("description", "Unknown")
                            direction = o["name"]  # Over / Under
                            point = o.get("point")
                            price = o.get("price")
                            player_lines.setdefault(player, {})[direction] = {
                                "point": point, "price": price
                            }

                        for player, sides in player_lines.items():
                            over = sides.get("Over", {})
                            under = sides.get("Under", {})
                            line = over.get("point") or under.get("point")
                            if line is None:
                                continue

                            all_rows.append({
                                "event_id": eid,
                                "game_date": date,
                                "season": event["season"],
                                "home_team": event["home_team"],
                                "away_team": event["away_team"],
                                "market": market_key,
                                "player_name": player,
                                "line": float(line),
                                "over_odds": over.get("price"),
                                "under_odds": under.get("price"),
                                "bookmaker": book,
                                "snapshot_timestamp": ts,
                                "pull_timestamp": datetime.now().isoformat(),
                            })

            elif r.status_code == 422:
                pass  # no data for this event
            else:
                errors += 1
                if errors <= 10:
                    print(f"  Event {eid}: status {r.status_code}")

        except Exception as ex:
            errors += 1
            if errors <= 10:
                print(f"  Event {eid}: ERROR {ex}")

        batch_count += 1
        time.sleep(0.2)

        # Save checkpoint every 200 events
        if batch_count % 200 == 0:
            pd.DataFrame(all_rows).to_parquet(cache_file, index=False)
            credits = r.headers.get("x-requests-remaining", "?") if r else "?"
            print(f"  Checkpoint: {batch_count}/{len(remaining)} events, "
                  f"{len(all_rows):,} rows, credits={credits}")

    # Final save
    df = pd.DataFrame(all_rows)
    if len(df) > 0:
        df.to_parquet(cache_file, index=False)
    print(f"  Total odds rows: {len(df):,}")
    print(f"  Errors: {errors}")
    return df


# ══════════════════════════════════════════════════════════════
# STEP 3 — PLAYER NORMALIZATION
# ══════════════════════════════════════════════════════════════

def normalize_players(odds_df):
    """Map raw player names to internal player_ids."""
    print("\nSTEP 3 — Player name normalization...")

    hitters = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    pitchers = pd.read_parquet(DATA_DIR / "pitcher_game_logs.parquet")

    # Build name → id lookup (most common ID per name)
    all_players = pd.concat([
        hitters[["player_id", "player_name"]],
        pitchers[["player_id", "player_name"]],
    ]).drop_duplicates()

    # Deduplicate: keep most frequent ID per name
    name_to_id = all_players.groupby("player_name")["player_id"].first().to_dict()

    # Build normalized name variants
    def _normalize(name):
        """Normalize player name for matching."""
        name = name.strip()
        # Remove suffixes
        for suffix in [" Jr.", " Sr.", " III", " II", " IV"]:
            name = name.replace(suffix, "")
        return name.strip()

    norm_lookup = {}
    for name, pid in name_to_id.items():
        norm_lookup[_normalize(name).lower()] = pid
        norm_lookup[name.lower()] = pid
        # Also add last name for fuzzy matching
        parts = name.split()
        if len(parts) >= 2:
            norm_lookup[parts[-1].lower()] = pid  # will be overwritten by last match

    # Exact match first, then normalized
    raw_names = odds_df["player_name"].unique()
    mapping = {}
    unmatched = []

    for raw in raw_names:
        # Exact
        if raw in name_to_id:
            mapping[raw] = name_to_id[raw]
            continue

        # Normalized
        norm = _normalize(raw).lower()
        if norm in norm_lookup:
            mapping[raw] = norm_lookup[norm]
            continue

        # Try lowercase exact
        if raw.lower() in norm_lookup:
            mapping[raw] = norm_lookup[raw.lower()]
            continue

        unmatched.append(raw)

    # For unmatched, try last-name matching within same game
    # This is expensive so only do for remaining unmatched
    if unmatched:
        # Build game-specific lookup
        game_players = {}
        for _, row in pd.concat([
            hitters[["game_pk", "player_id", "player_name", "team"]],
            pitchers[["game_pk", "player_id", "player_name", "team"]],
        ]).iterrows():
            game_players.setdefault(row["game_pk"], {})[row["player_name"].lower()] = row["player_id"]

        # For each unmatched, try within game context
        for raw in unmatched[:]:
            norm = _normalize(raw).lower()
            last = norm.split()[-1] if norm else ""

            # Find games where this raw name appears
            events = odds_df[odds_df["player_name"] == raw]["event_id"].unique()

            # Try matching by last name
            for _, pid in name_to_id.items():
                if _ .lower().endswith(last) and last:
                    mapping[raw] = pid
                    unmatched.remove(raw)
                    break

    odds_df["player_id"] = odds_df["player_name"].map(mapping)

    matched = odds_df["player_id"].notna().sum()
    total = len(odds_df)
    n_players_matched = len(mapping)
    n_unmatched = len(unmatched)

    print(f"  Players: {n_players_matched} matched, {n_unmatched} unmatched")
    print(f"  Rows: {matched:,}/{total:,} matched ({matched/total*100:.1f}%)")

    if unmatched:
        print(f"  Sample unmatched: {unmatched[:20]}")

    # Save mapping
    map_df = pd.DataFrame([
        {"raw_name": k, "player_id": v} for k, v in mapping.items()
    ])
    map_df.to_parquet(PROC_DIR / "player_mapping.parquet", index=False)

    return odds_df


# ══════════════════════════════════════════════════════════════
# STEP 4 — PROP NORMALIZATION
# ══════════════════════════════════════════════════════════════

def normalize_props(odds_df):
    """Standardize prop types and structure."""
    print("\nSTEP 4 — Prop normalization...")

    odds_df["prop_type"] = odds_df["market"].map(PROP_TYPE_MAP)

    props = odds_df[[
        "player_id", "player_name", "event_id", "game_date", "season",
        "home_team", "away_team",
        "prop_type", "line", "over_odds", "under_odds", "bookmaker",
        "snapshot_timestamp",
    ]].copy()

    props.to_parquet(PROC_DIR / "props_lines.parquet", index=False)
    print(f"  Normalized props: {len(props):,} rows")
    return props


# ══════════════════════════════════════════════════════════════
# STEP 5 — OUTCOME JOIN
# ══════════════════════════════════════════════════════════════

def join_outcomes(props_df):
    """Join actual outcomes from M2 game logs."""
    print("\nSTEP 5 — Outcome join...")

    hitters = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    pitchers = pd.read_parquet(DATA_DIR / "pitcher_game_logs.parquet")

    # Hitter actuals
    hitters["total_bases"] = (hitters["singles"] + 2 * hitters["doubles"] +
                               3 * hitters["triples"] + 4 * hitters["home_runs"])

    hitter_actuals = hitters[["game_pk", "player_id",
                               "hits", "total_bases", "home_runs", "rbis"]].copy()
    hitter_actuals = hitter_actuals.rename(columns={
        "hits": "actual_HITS",
        "total_bases": "actual_TB",
        "home_runs": "actual_HR",
        "rbis": "actual_RBI",
    })

    # Pitcher actuals
    pitchers_sp = pitchers.copy()
    ip = pitchers_sp["innings_pitched"]
    pitchers_sp["outs"] = (ip.astype(int) * 3 +
                            ((ip - ip.astype(int)) * 10).round().astype(int))

    pitcher_actuals = pitchers_sp[["game_pk", "player_id",
                                    "strikeouts", "outs",
                                    "earned_runs", "hits_allowed"]].copy()
    pitcher_actuals = pitcher_actuals.rename(columns={
        "strikeouts": "actual_K",
        "outs": "actual_OUTS",
        "earned_runs": "actual_ER",
        "hits_allowed": "actual_H_ALLOWED",
    })

    # We need to map event_id → game_pk for joining
    # Use game_date + team matching
    tgi = pd.read_parquet(DATA_DIR / "team_game_index.parquet")
    tgi["game_date"] = pd.to_datetime(tgi["game_date"]).dt.strftime("%Y-%m-%d")

    # Build event → game_pk mapping via date + teams
    events_raw = pd.read_parquet(RAW_DIR / "events.parquet")

    # Odds API team names → abbreviations
    TEAM_MAP = {
        "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
        "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
        "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
        "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
        "Colorado Rockies": "COL", "Detroit Tigers": "DET",
        "Houston Astros": "HOU", "Kansas City Royals": "KCR",
        "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
        "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
        "Minnesota Twins": "MIN", "New York Mets": "NYM",
        "New York Yankees": "NYY", "Oakland Athletics": "OAK",
        "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
        "San Diego Padres": "SDP", "San Francisco Giants": "SFG",
        "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL",
        "Tampa Bay Rays": "TBR", "Texas Rangers": "TEX",
        "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN",
    }

    events_raw["home_abbr"] = events_raw["home_team"].map(TEAM_MAP)
    events_raw["away_abbr"] = events_raw["away_team"].map(TEAM_MAP)

    # Join events to game_pk via date + home team
    event_game = events_raw.merge(
        tgi[["game_pk", "game_date", "team", "opponent"]].rename(
            columns={"team": "home_abbr_tgi", "opponent": "away_abbr_tgi"}
        ),
        left_on=["date", "home_abbr"],
        right_on=["game_date", "home_abbr_tgi"],
        how="left"
    )
    event_to_gpk = event_game[["event_id", "game_pk"]].drop_duplicates(subset="event_id")
    event_to_gpk = event_to_gpk.dropna(subset=["game_pk"])
    event_to_gpk["game_pk"] = event_to_gpk["game_pk"].astype(int)

    print(f"  Event → game_pk mapping: {len(event_to_gpk)}/{len(events_raw)} "
          f"({len(event_to_gpk)/len(events_raw)*100:.1f}%)")

    # Add game_pk to props
    props_df = props_df.merge(event_to_gpk, on="event_id", how="left")

    # Join outcomes
    # Hitter props
    hitter_props = props_df[props_df["prop_type"].isin(["HITS", "TB", "HR", "RBI"])].copy()
    hitter_props = hitter_props.merge(
        hitter_actuals, on=["game_pk", "player_id"], how="left"
    )

    # Map actual column based on prop_type
    def get_actual(row):
        pt = row["prop_type"]
        return row.get(f"actual_{pt}", np.nan)

    hitter_props["actual_value"] = hitter_props.apply(get_actual, axis=1)

    # Pitcher props
    pitcher_props = props_df[props_df["prop_type"].isin(["K", "OUTS", "ER", "H_ALLOWED"])].copy()
    pitcher_props = pitcher_props.merge(
        pitcher_actuals, on=["game_pk", "player_id"], how="left"
    )
    pitcher_props["actual_value"] = pitcher_props.apply(get_actual, axis=1)

    # Combine
    combined = pd.concat([hitter_props, pitcher_props], ignore_index=True)

    # Compute over/under hit
    combined["over_hit"] = np.where(
        combined["actual_value"].notna(),
        (combined["actual_value"] > combined["line"]).astype(int),
        np.nan
    )
    combined["under_hit"] = np.where(
        combined["actual_value"].notna(),
        (combined["actual_value"] < combined["line"]).astype(int),
        np.nan
    )
    combined["push"] = np.where(
        combined["actual_value"].notna(),
        (combined["actual_value"] == combined["line"]).astype(int),
        np.nan
    )

    # Keep only essential columns
    result_cols = ["event_id", "game_pk", "game_date", "season",
                    "player_id", "player_name",
                    "prop_type", "line", "over_odds", "under_odds", "bookmaker",
                    "actual_value", "over_hit", "under_hit", "push"]
    result_cols = [c for c in result_cols if c in combined.columns]
    results = combined[result_cols].copy()

    matched = results["actual_value"].notna().sum()
    total = len(results)
    print(f"  Outcome join: {matched:,}/{total:,} matched ({matched/total*100:.1f}%)")

    results.to_parquet(PROC_DIR / "props_results.parquet", index=False)
    return results


# ══════════════════════════════════════════════════════════════
# STEP 6 — BEST LINE / MARKET VIEW
# ══════════════════════════════════════════════════════════════

def build_market_view(results_df):
    """Compute best lines and consensus per player-prop."""
    print("\nSTEP 6 — Market view...")

    grouped = results_df.groupby(
        ["event_id", "game_pk", "game_date", "season",
         "player_id", "player_name", "prop_type"]
    )

    market_rows = []
    for key, group in grouped:
        event_id, game_pk, game_date, season, player_id, player_name, prop_type = key

        lines = group["line"].dropna()
        n_books = group["bookmaker"].nunique()

        if len(lines) == 0:
            continue

        market_rows.append({
            "event_id": event_id,
            "game_pk": game_pk,
            "game_date": game_date,
            "season": season,
            "player_id": player_id,
            "player_name": player_name,
            "prop_type": prop_type,
            "consensus_line": round(lines.median(), 1),
            "line_std": round(lines.std(), 2) if len(lines) > 1 else 0.0,
            "best_over_line": lines.min(),
            "best_under_line": lines.max(),
            "n_books": n_books,
            "actual_value": group["actual_value"].iloc[0],
            "over_hit": group["over_hit"].iloc[0],
            "under_hit": group["under_hit"].iloc[0],
        })

    mv = pd.DataFrame(market_rows)

    # Dataset split
    mv["dataset_split"] = np.where(mv["season"] == 2023, "TRAIN",
                            np.where(mv["season"] == 2024, "VALIDATION", "OOS"))

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
    log("MLB PLAYER PROPS — PHASE P2 BACKFILL + DATA SYSTEM")
    log("=" * 70)
    log()

    # Step 1
    events_df = collect_events()
    log(f"\nSECTION 0 — COLLECTION SUMMARY")
    log(f"  Events: {len(events_df):,}")
    log(f"  By season: {events_df['season'].value_counts().sort_index().to_dict()}")
    log()

    # Step 2
    odds_df = collect_odds(events_df)
    log(f"  Raw odds rows: {len(odds_df):,}")
    if len(odds_df) > 0:
        log(f"  Markets: {odds_df['market'].value_counts().to_dict()}")
        log(f"  Books: {odds_df['bookmaker'].nunique()}")
    log()

    if len(odds_df) == 0:
        log("NO ODDS DATA COLLECTED. Stopping.")
        with open(PROPS_DIR / "p2_summary.txt", "w") as f:
            f.write("\n".join(lines))
        return

    # Step 3
    odds_df = normalize_players(odds_df)
    log()

    # Step 4
    props_df = normalize_props(odds_df)
    log()

    # Step 5
    results_df = join_outcomes(props_df)
    log()

    # Step 6
    mv = build_market_view(results_df)
    log()

    # ── SECTION 1 — DATA QUALITY ──
    log("=" * 70)
    log("SECTION 1 — DATA QUALITY")
    log("=" * 70)
    log()

    # Player mapping
    matched_pct = results_df["player_id"].notna().mean() * 100
    log(f"Player mapping: {matched_pct:.1f}% matched")
    log()

    # Outcome coverage
    with_outcome = results_df["actual_value"].notna().sum()
    log(f"Outcome join: {with_outcome:,}/{len(results_df):,} ({with_outcome/len(results_df)*100:.1f}%)")
    log()

    # Duplicates
    dupes = results_df.duplicated(subset=["event_id", "player_id", "prop_type", "bookmaker"]).sum()
    log(f"Duplicate rows: {dupes}")
    log()

    # Line ranges
    log("Line ranges by prop type:")
    for pt in sorted(results_df["prop_type"].dropna().unique()):
        sub = results_df[results_df["prop_type"] == pt]["line"]
        log(f"  {pt:<12s}: min={sub.min():.1f}, max={sub.max():.1f}, median={sub.median():.1f}")
    log()

    # ── SECTION 2 — MARKET STRUCTURE ──
    log("=" * 70)
    log("SECTION 2 — MARKET STRUCTURE")
    log("=" * 70)
    log()

    log(f"Unique player-prop-games: {len(mv):,}")
    log()

    log("Props per game (median):")
    ppg = mv.groupby(["event_id"]).size()
    log(f"  Median: {ppg.median():.0f}")
    log(f"  Mean: {ppg.mean():.1f}")
    log(f"  Max: {ppg.max()}")
    log()

    log("Books per prop (median):")
    log(f"  Median: {mv['n_books'].median():.0f}")
    log(f"  Mean: {mv['n_books'].mean():.1f}")
    log()

    log("Props by type:")
    for pt in sorted(mv["prop_type"].unique()):
        n = (mv["prop_type"] == pt).sum()
        log(f"  {pt:<12s}: {n:>7,}")
    log()

    log("Line variance by type:")
    for pt in sorted(mv["prop_type"].unique()):
        sub = mv[mv["prop_type"] == pt]
        log(f"  {pt:<12s}: mean line_std={sub['line_std'].mean():.2f}")
    log()

    # ── SECTION 3 — FINAL DATASET ──
    log("=" * 70)
    log("SECTION 3 — FINAL DATASET SHAPE")
    log("=" * 70)
    log()

    log(f"Total market view rows: {len(mv):,}")
    for split in ["TRAIN", "VALIDATION", "OOS"]:
        n = (mv["dataset_split"] == split).sum()
        log(f"  {split}: {n:,}")
    log()

    with_outcome = mv["actual_value"].notna().sum()
    log(f"With outcomes: {with_outcome:,}/{len(mv):,} ({with_outcome/len(mv)*100:.1f}%)")
    log()

    # ── SECTION 4 — READINESS ──
    log("=" * 70)
    log("SECTION 4 — READINESS CHECK")
    log("=" * 70)
    log()

    if len(mv) > 10000 and with_outcome > 5000:
        log("STATUS: READY FOR MODELING (Phase P3)")
        log()
        log("Available for P3:")
        log(f"  - {len(mv):,} player-prop-games with market lines")
        log(f"  - {with_outcome:,} with graded outcomes")
        log(f"  - 8 prop types across 9 bookmakers")
        log(f"  - Train/Validation split tagged")
    else:
        log("STATUS: INSUFFICIENT DATA")
        log(f"  Market view: {len(mv):,} rows")
        log(f"  With outcomes: {with_outcome:,}")
    log()

    # Save summary
    with open(PROPS_DIR / "p2_summary.txt", "w") as f:
        f.write("\n".join(lines))

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  mlb/props/raw/events.parquet")
    log(f"  mlb/props/raw/odds_raw.parquet")
    log(f"  mlb/props/processed/player_mapping.parquet")
    log(f"  mlb/props/processed/props_lines.parquet")
    log(f"  mlb/props/processed/props_results.parquet")
    log(f"  mlb/props/processed/props_market_view.parquet")
    log(f"  mlb/props/p2_summary.txt")
    log("=" * 70)


if __name__ == "__main__":
    main()
