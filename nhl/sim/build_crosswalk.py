#!/usr/bin/env python3
"""S55 (L-WO1 Item 2): build game_id <-> event_id crosswalk.

Maps NHL game_id (from boxscores) to Odds API event_id (from historical lines)
using schedule date + team abbreviations. The NAME map (full name -> abbrev) is
moved here as the single source of truth.

Asserts 1:1 mapping in both directions; HALTs listing every duplicate or ambiguous pair.
"""
import hashlib, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BOX_DIR = ROOT / "nhl" / "cache"
LINES_DIR = ROOT / "data" / "odds_archive" / "nhl" / "history" / "lines"
CROSSWALK_DIR = ROOT / "nhl" / "data" / "sim" / "crosswalk"
MANIFEST = ROOT / "nhl" / "data" / "sim" / "ratings" / "manifest.json"
GAMES_PER_SEASON = 1312

# Single source of truth for Odds API full name -> NHL API abbreviation
NAME = {
    "Anaheim Ducks": "ANA", "Arizona Coyotes": "ARI", "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF", "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL", "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM", "Florida Panthers": "FLA", "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN", "Montréal Canadiens": "MTL", "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD", "New York Islanders": "NYI", "New York Rangers": "NYR",
    "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS", "Seattle Kraken": "SEA", "St Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA", "Utah Mammoth": "UTA",
    "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH", "Winnipeg Jets": "WPG",
}


def load_schedule(seasons):
    """Load game schedule from boxscores: game_id, date, home, away."""
    rows = []
    for s in seasons:
        for i in range(1, GAMES_PER_SEASON + 1):
            gid = f"{s}02{i:04d}"
            bp = BOX_DIR / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            rows.append({
                "game_id": gid,
                "season": s,
                "date": d.get("gameDate", ""),
                "home": d["homeTeam"]["abbrev"],
                "away": d["awayTeam"]["abbrev"],
            })
    return pd.DataFrame(rows)


def load_lines_events(season):
    """Load unique events from lines history for a season."""
    sd = LINES_DIR / f"season={season}"
    if not sd.exists():
        return pd.DataFrame()
    files = sorted(sd.glob("snap_*.parquet"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    # Get unique events
    events = df.groupby("event_id").first().reset_index()
    events["home"] = events["home_team"].map(NAME)
    events["away"] = events["away_team"].map(NAME)
    # Convert commence_time to ET date
    ct = pd.to_datetime(events["commence_time"])
    if ct.dt.tz is None:
        ct = ct.dt.tz_localize("UTC")
    events["et_date"] = ct.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    return events[["event_id", "home", "away", "et_date", "commence_time"]].copy()


def build_crosswalk(seasons):
    schedule = load_schedule(seasons)
    all_rows = []
    for season in seasons:
        sched_s = schedule[schedule["season"] == season]
        events = load_lines_events(season)
        if events.empty:
            print(f"Season {season}-{season+1}: NO LINES DATA — 0 matched, "
                  f"{len(sched_s)} unmatched games")
            continue

        # Join on (et_date, home, away)
        merged = sched_s.merge(events, left_on=["date", "home", "away"],
                               right_on=["et_date", "home", "away"], how="inner")
        unmatched_games = len(sched_s) - len(merged)
        unmatched_events = len(events) - len(merged)
        print(f"Season {season}-{season+1}: {len(merged)} matched, "
              f"{unmatched_games} unmatched games, {unmatched_events} unmatched events")

        # Check 1:1 in both directions
        dup_games = merged[merged.duplicated("game_id", keep=False)]
        dup_events = merged[merged.duplicated("event_id", keep=False)]
        errors = []
        if len(dup_games):
            errors.append(f"Duplicate game_ids:\n{dup_games[['game_id', 'event_id', 'date', 'home', 'away']]}")
        if len(dup_events):
            errors.append(f"Duplicate event_ids:\n{dup_events[['game_id', 'event_id', 'date', 'home', 'away']]}")
        if errors:
            print("HALT: mapping is NOT 1:1", file=sys.stderr)
            for e in errors:
                print(e, file=sys.stderr)
            sys.exit(1)

        all_rows.append(merged[["game_id", "event_id", "season", "et_date",
                                "home", "away", "commence_time"]])

    if not all_rows:
        print("HALT: no crosswalk rows produced", file=sys.stderr)
        sys.exit(1)

    result = pd.concat(all_rows, ignore_index=True)
    return result


def main():
    seasons = [2021, 2022, 2023, 2024, 2025]
    cw = build_crosswalk(seasons)

    CROSSWALK_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CROSSWALK_DIR / "game_event.parquet"
    cw.to_parquet(out_path, index=False)
    sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
    print(f"\nCrosswalk: {len(cw)} rows, sha256={sha[:16]}...")

    # Update manifest
    m = json.loads(MANIFEST.read_text())
    m["crosswalk_sha256"] = sha
    m["crosswalk_rows"] = len(cw)
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
    print("Manifest updated")


if __name__ == "__main__":
    main()
