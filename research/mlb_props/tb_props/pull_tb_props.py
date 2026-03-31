#!/usr/bin/env python3
"""
Pull all available historical MLB TB prop closing odds.
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
SPORT = "baseball_mlb"
MARKET = "batter_total_bases"
PREFERRED_BOOKS = ["fanduel", "draftkings", "betmgm", "betonlineag"]


def american_to_implied(odds):
    if odds is None: return None
    if odds > 0: return round(100 / (odds + 100), 4)
    return round(abs(odds) / (abs(odds) + 100), 4)


def pull_events(date_str):
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events"
    params = {"apiKey": ODDS_API_KEY, "date": f"{date_str}T12:00:00Z"}
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200:
        return [], remaining
    data = resp.json()
    events = data.get("data", data) if isinstance(data, dict) else data
    return (events if isinstance(events, list) else []), remaining


def pull_tb_odds(event_id, game_date_str):
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY, "regions": "us",
        "markets": MARKET, "oddsFormat": "american",
        "date": f"{game_date_str}T23:00:00Z",
    }
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200:
        return [], remaining, resp.status_code

    inner = resp.json().get("data", resp.json())
    if not isinstance(inner, dict):
        return [], remaining, resp.status_code

    records = []
    for bm in inner.get("bookmakers", []):
        book = bm.get("key", "")
        for mkt in bm.get("markets", []):
            if mkt.get("key") != MARKET:
                continue
            # Group outcomes by player+line
            player_lines = {}
            for o in mkt.get("outcomes", []):
                player = o.get("description", "")
                name = o.get("name", "")
                point = o.get("point")
                price = o.get("price")
                key = (player, point)
                if key not in player_lines:
                    player_lines[key] = {"player_name": player, "line": point, "book": book}
                if name == "Over":
                    player_lines[key]["over_odds"] = price
                elif name == "Under":
                    player_lines[key]["under_odds"] = price

            for rec in player_lines.values():
                if "over_odds" in rec:
                    records.append(rec)

    return records, remaining, resp.status_code


def generate_date_ranges():
    """Generate all dates in available windows."""
    ranges = []
    # April 2025
    d = date(2025, 3, 27)
    while d <= date(2025, 4, 30):
        ranges.append(d.isoformat())
        d += timedelta(days=1)
    # August-October 2025
    d = date(2025, 8, 15)
    while d <= date(2025, 10, 5):
        ranges.append(d.isoformat())
        d += timedelta(days=1)
    # March 2026
    d = date(2026, 3, 20)
    while d <= date(2026, 3, 27):
        ranges.append(d.isoformat())
        d += timedelta(days=1)
    return ranges


def main():
    all_dates = generate_date_ranges()
    print(f"Scanning {len(all_dates)} dates across available windows")

    all_records = []
    events_processed = 0
    events_with_tb = 0
    events_404 = 0
    credits_start = None

    for i, date_str in enumerate(all_dates):
        events, remaining = pull_events(date_str)
        if credits_start is None and remaining != "?":
            credits_start = int(remaining)

        # Filter to real MLB games
        real = [e for e in events if all(
            k not in (e.get("home_team") or "")
            for k in ["All-Star", "National", "American"]
        )]

        for event in real:
            eid = event["id"]
            home = ODDS_API_TEAM_MAP.get(event.get("home_team", ""), event.get("home_team", ""))
            away = ODDS_API_TEAM_MAP.get(event.get("away_team", ""), event.get("away_team", ""))
            commence = event.get("commence_time", "")
            game_date = commence[:10] if commence else date_str

            tb_recs, remaining, status = pull_tb_odds(eid, game_date)
            events_processed += 1

            if status == 404:
                events_404 += 1
                continue

            if tb_recs:
                events_with_tb += 1
                # Pick best book per player+line
                best = {}
                for rec in tb_recs:
                    key = (rec["player_name"], rec["line"])
                    if key not in best:
                        best[key] = rec
                    else:
                        # Prefer books in priority order
                        cur_rank = PREFERRED_BOOKS.index(best[key]["book"]) if best[key]["book"] in PREFERRED_BOOKS else 99
                        new_rank = PREFERRED_BOOKS.index(rec["book"]) if rec["book"] in PREFERRED_BOOKS else 99
                        if new_rank < cur_rank:
                            best[key] = rec

                for rec in best.values():
                    rec["event_id"] = eid
                    rec["game_date"] = game_date
                    rec["season"] = int(game_date[:4])
                    rec["home_team"] = home
                    rec["away_team"] = away
                    rec["implied_over"] = american_to_implied(rec.get("over_odds"))
                    rec["implied_under"] = american_to_implied(rec.get("under_odds"))
                    all_records.append(rec)

            time.sleep(0.12)

        # Progress
        if (i + 1) % 7 == 0:
            print(f"  [{i+1}/{len(all_dates)}] {date_str}: "
                  f"{events_processed} events, {events_with_tb} with TB, "
                  f"{len(all_records)} records, 404s={events_404}, credits={remaining}")

        # Save every 50 events
        if events_with_tb > 0 and events_with_tb % 50 == 0:
            pd.DataFrame(all_records).to_parquet(BASE / "tb_props_raw.parquet", index=False)

    # Final save
    df = pd.DataFrame(all_records)
    if len(df) > 0:
        df.to_parquet(BASE / "tb_props_raw.parquet", index=False)

    credits_end = int(remaining) if remaining != "?" else 0
    credits_used = (credits_start - credits_end) if credits_start else 0

    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"Events processed: {events_processed}")
    print(f"Events with TB data: {events_with_tb}")
    print(f"Events 404 (expired): {events_404}")
    print(f"Total TB prop records: {len(all_records)}")
    print(f"Credits used: ~{credits_used}")
    print(f"Credits remaining: {remaining}")


if __name__ == "__main__":
    main()
