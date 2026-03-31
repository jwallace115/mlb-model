"""
NBA Opening Line Backfill
Pull historical opening totals from The Odds API for all games
in nba_historical_closing_lines.parquet.
"""

import os
import sys
import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

PARQUET_PATH = Path(__file__).parent / "data" / "nba_historical_closing_lines.parquet"
CACHE_DIR = Path(__file__).parent / "data" / "cache" / "nba_opening_lines"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("ODDS_API_KEY")
if not API_KEY:
    print("ERROR: ODDS_API_KEY not set in environment")
    sys.exit(1)

BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/odds"

# NBA team name mapping: Odds API name -> our abbreviation
TEAM_MAP = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "LA Clippers": "LAC",
    "LA Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}


def check_credits():
    """Check remaining API credits."""
    r = requests.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": API_KEY})
    remaining = int(r.headers.get("x-requests-remaining", 0))
    used = int(r.headers.get("x-requests-used", 0))
    return remaining, used


def fetch_historical_odds(query_date_str):
    """
    Fetch historical odds snapshot for a given ISO date string.
    Returns parsed JSON and updates credit info.
    Caches results to avoid re-fetching on reruns.
    """
    # Cache by the full query timestamp to distinguish different query strategies
    safe_name = query_date_str.replace(":", "-")
    cache_file = CACHE_DIR / f"opening_{safe_name}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            data = json.load(f)
        return data, None  # None means we used cache, no credit cost

    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "totals",
        "oddsFormat": "american",
        "date": query_date_str,
    }

    r = requests.get(BASE_URL, params=params)

    if r.status_code == 422:
        # No data available for this date
        return None, r.headers.get("x-requests-remaining")

    if r.status_code == 429:
        print("  RATE LIMITED — sleeping 60s")
        time.sleep(60)
        return fetch_historical_odds(query_date_str)

    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
        return None, r.headers.get("x-requests-remaining")

    data = r.json()
    remaining = r.headers.get("x-requests-remaining")

    # Cache the response
    with open(cache_file, "w") as f:
        json.dump(data, f)

    return data, remaining


def extract_totals_from_snapshot(data):
    """
    Extract totals from an API response.
    Returns dict of (home_abbr, away_abbr) -> total_points
    """
    if not data or "data" not in data:
        return {}

    results = {}
    for game in data["data"]:
        home = TEAM_MAP.get(game.get("home_team", ""))
        away = TEAM_MAP.get(game.get("away_team", ""))
        if not home or not away:
            continue

        # Get the first bookmaker with totals
        total = None
        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] == "totals":
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == "Over":
                            total = outcome["point"]
                            break
                    if total is not None:
                        break
            if total is not None:
                break

        if total is not None:
            results[(home, away)] = total

    return results


def main():
    print("=" * 60)
    print("NBA Opening Line Backfill")
    print("=" * 60)

    # Check credits
    remaining, used = check_credits()
    print(f"Credits: {remaining:,} remaining, {used:,} used")

    # Load existing data
    df = pd.read_parquet(PARQUET_PATH)
    print(f"Games in file: {len(df):,}")
    print(f"Unique dates: {df['date'].nunique()}")

    # Group by date
    dates = sorted(df["date"].unique())
    estimated_credits = len(dates) * 10
    print(f"Estimated credit cost: {estimated_credits:,} (10 per date × {len(dates)} dates)")

    if remaining < estimated_credits:
        print(f"WARNING: May not have enough credits. Will pause at 5,000 remaining.")

    # Process each date
    opening_totals = {}  # game_id -> opening_total
    api_calls = 0
    cache_hits = 0
    not_found = []
    credits_remaining = remaining

    for i, game_date in enumerate(dates):
        # Query date = game_date at 10:00 UTC (6am ET) to get early-morning opening lines
        # NBA lines are typically posted early morning of game day
        dt = datetime.strptime(game_date, "%Y-%m-%d")
        query_str = dt.strftime("%Y-%m-%dT10:00:00Z")

        # Check credit threshold
        if credits_remaining is not None and int(credits_remaining) < 5000:
            print(f"\n⚠ CREDIT THRESHOLD: {credits_remaining} remaining. Pausing.")
            break

        # Fetch
        data, new_remaining = fetch_historical_odds(query_str)

        if new_remaining is not None:
            credits_remaining = new_remaining
            api_calls += 1
        else:
            if data is not None:
                cache_hits += 1

        # Extract totals
        totals_map = extract_totals_from_snapshot(data) if data else {}

        # Match to our games on this date
        games_on_date = df[df["date"] == game_date]
        for _, row in games_on_date.iterrows():
            key = (row["home_team"], row["away_team"])
            if key in totals_map:
                opening_totals[row["game_id"]] = totals_map[key]
            else:
                not_found.append(row["game_id"])

        # Progress
        if (i + 1) % 50 == 0 or i == len(dates) - 1:
            matched = len(opening_totals)
            total_games = len(df[df["date"].isin(dates[: i + 1])])
            print(
                f"  [{i+1}/{len(dates)}] API calls: {api_calls}, "
                f"cache hits: {cache_hits}, matched: {matched}/{total_games}, "
                f"credits remaining: {credits_remaining}"
            )

        # Small delay to avoid rate limiting
        if new_remaining is not None:
            time.sleep(0.3)

    # Add opening_total column
    df["opening_total"] = df["game_id"].map(opening_totals)

    # Save
    df.to_parquet(PARQUET_PATH, index=False)

    # Report
    matched = df["opening_total"].notna().sum()
    total = len(df)
    coverage = matched / total * 100

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total games:      {total:,}")
    print(f"Opening lines:    {matched:,}")
    print(f"Coverage:          {coverage:.1f}%")
    print(f"Not found:         {len(not_found):,}")
    print(f"API calls:         {api_calls}")
    print(f"Cache hits:        {cache_hits}")
    print(f"Credits remaining: {credits_remaining}")

    if not_found:
        print(f"\nFirst 20 unmatched game_ids:")
        for gid in not_found[:20]:
            row = df[df["game_id"] == gid].iloc[0]
            print(f"  {gid}  {row['date']}  {row['away_team']}@{row['home_team']}")

    # Summary stats
    has_both = df.dropna(subset=["opening_total", "close_total"])
    if len(has_both) > 0:
        diff = has_both["close_total"] - has_both["opening_total"]
        print(f"\nOpening vs Closing (n={len(has_both):,}):")
        print(f"  Mean movement:   {diff.mean():+.2f}")
        print(f"  Median movement: {diff.median():+.2f}")
        print(f"  Std movement:    {diff.std():.2f}")
        print(f"  Max move up:     {diff.max():+.1f}")
        print(f"  Max move down:   {diff.min():+.1f}")


if __name__ == "__main__":
    main()
