#!/usr/bin/env python3
"""
Pull historical MLB TB prop closing odds from The Odds API.
Saves incrementally every 50 events.
"""

import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from config import ODDS_API_KEY, ODDS_API_BASE, ODDS_API_TEAM_MAP

BASE = Path(__file__).resolve().parent
API_BASE = ODDS_API_BASE
SPORT = "baseball_mlb"
MARKET = "batter_total_bases"
BOOKS = "fanduel,draftkings"


def pull_events_for_date(date_str):
    """Pull historical events for a given date."""
    url = f"{API_BASE}/historical/sports/{SPORT}/events"
    params = {
        "apiKey": ODDS_API_KEY,
        "date": f"{date_str}T12:00:00Z",
    }
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        return [], resp.headers.get("x-requests-remaining", "?")
    data = resp.json()
    events = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(events, list):
        return events, resp.headers.get("x-requests-remaining", "?")
    return [], resp.headers.get("x-requests-remaining", "?")


def pull_event_tb_odds(event_id, game_date_str):
    """Pull TB prop odds for a single event near game time."""
    # Use 11 PM ET (3 AM UTC next day) as closing proxy
    close_time = f"{game_date_str}T23:00:00Z"
    url = f"{API_BASE}/historical/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": MARKET,
        "bookmakers": BOOKS,
        "oddsFormat": "american",
        "date": close_time,
    }
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")

    if resp.status_code != 200:
        return [], remaining

    data = resp.json()
    inner = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(inner, dict):
        return [], remaining

    records = []
    for bm in inner.get("bookmakers", []):
        book = bm.get("key", "")
        for mkt in bm.get("markets", []):
            if mkt.get("key") != MARKET:
                continue
            outcomes = mkt.get("outcomes", [])
            # Group by player+line
            player_lines = {}
            for o in outcomes:
                player = o.get("description", "")
                name = o.get("name", "")  # Over or Under
                point = o.get("point")
                price = o.get("price")
                key = (player, point)
                if key not in player_lines:
                    player_lines[key] = {"player": player, "line": point, "book": book}
                if name == "Over":
                    player_lines[key]["over_odds"] = price
                elif name == "Under":
                    player_lines[key]["under_odds"] = price

            for (player, line), rec in player_lines.items():
                if "over_odds" in rec:
                    records.append(rec)

    return records, remaining


def american_to_implied(odds):
    """Convert American odds to implied probability."""
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def run_season(year):
    """Pull all TB props for a season."""
    print(f"\n{'='*60}")
    print(f"PULLING {year} SEASON")
    print(f"{'='*60}")

    # Generate game dates (April through October)
    start = date(year, 3, 20)
    end = date(year, 10, 5)
    all_dates = []
    d = start
    while d <= end:
        all_dates.append(d.isoformat())
        d += timedelta(days=1)

    all_records = []
    events_seen = set()
    total_events = 0
    total_api_calls = 0

    for i, date_str in enumerate(all_dates):
        events, remaining = pull_events_for_date(date_str)
        total_api_calls += 1

        # Filter to real MLB games (not All-Star, not spring training)
        real_games = [e for e in events if e.get("id") not in events_seen
                      and "All-Star" not in (e.get("home_team") or "")
                      and "All-Star" not in (e.get("away_team") or "")]

        for event in real_games:
            eid = event["id"]
            if eid in events_seen:
                continue
            events_seen.add(eid)
            total_events += 1

            home = ODDS_API_TEAM_MAP.get(event.get("home_team", ""), event.get("home_team", ""))
            away = ODDS_API_TEAM_MAP.get(event.get("away_team", ""), event.get("away_team", ""))
            commence = event.get("commence_time", "")
            game_date = commence[:10] if commence else date_str

            # Pull TB odds
            tb_records, remaining = pull_event_tb_odds(eid, game_date)
            total_api_calls += 1

            for rec in tb_records:
                rec["event_id"] = eid
                rec["game_date"] = game_date
                rec["season"] = year
                rec["home_team"] = home
                rec["away_team"] = away
                rec["implied_over"] = american_to_implied(rec.get("over_odds"))
                rec["implied_under"] = american_to_implied(rec.get("under_odds"))
                all_records.append(rec)

            # Rate limit
            time.sleep(0.15)

        # Progress
        if (i + 1) % 7 == 0 or i == len(all_dates) - 1:
            print(f"  {date_str}: {total_events} events, {len(all_records)} TB records, "
                  f"credits remaining={remaining}")

        # Save incrementally every 50 events
        if total_events > 0 and total_events % 50 == 0:
            df = pd.DataFrame(all_records)
            df.to_parquet(BASE / f"tb_props_raw_{year}.parquet", index=False)

    # Final save
    df = pd.DataFrame(all_records)
    if len(df) > 0:
        df.to_parquet(BASE / f"tb_props_raw_{year}.parquet", index=False)
    print(f"\n{year} complete: {total_events} events, {len(all_records)} TB records, "
          f"{total_api_calls} API calls")
    return df


if __name__ == "__main__":
    for year in [2024, 2025]:
        run_season(year)
    print("\nDone.")
