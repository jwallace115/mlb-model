#!/usr/bin/env python3
"""
NFL Derivative Market Historical Backfill
==========================================
Pulls Q1 and H1 odds for all 2025 NFL season games from The Odds API historical endpoint.
Stores in existing archive partition convention.

Markets: totals_q1, spreads_q1, h2h_q1, totals_h1, spreads_h1, h2h_h1

Usage:
  python3 nfl/research_derivatives/pull_derivative_odds.py
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Load API key
def _load_key():
    for line in (PROJECT_ROOT / ".env").read_text().splitlines():
        if line.startswith("ODDS_API_KEY="):
            return line.split("=", 1)[1].strip()
    return os.environ.get("ODDS_API_KEY", "")

API_KEY = _load_key()
BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "odds_archive" / "nfl" / "game_markets"
CACHE_DIR = PROJECT_ROOT / "nfl" / "research_derivatives" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DERIVATIVE_MARKETS_Q1 = "totals_q1,spreads_q1,h2h_q1"
DERIVATIVE_MARKETS_H1 = "totals_h1,spreads_h1,h2h_h1"

# NFL 2025 season: Sep 2025 through Feb 2026
SCAN_START = date(2025, 9, 1)
SCAN_END = date(2026, 2, 15)


def american_to_implied(odds):
    if odds is None:
        return None
    if odds > 0:
        return round(100 / (odds + 100), 4)
    return round(abs(odds) / (abs(odds) + 100), 4)


def pull_events(date_str):
    cache_file = CACHE_DIR / f"events_{date_str}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text()), "cached"
    url = f"{BASE}/historical/sports/{SPORT}/events"
    params = {"apiKey": API_KEY, "date": f"{date_str}T12:00:00Z"}
    resp = requests.get(url, params=params, timeout=15)
    rem = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200:
        return [], rem
    data = resp.json()
    events = data.get("data", data) if isinstance(data, dict) else data
    events = events if isinstance(events, list) else []
    cache_file.write_text(json.dumps(events))
    return events, rem


def pull_odds(event_id, commence, markets_str, batch_label):
    cache_file = CACHE_DIR / f"odds_{event_id}_{batch_label}.json"
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        return data, "cached", 200
    url = f"{BASE}/historical/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY, "regions": "us", "markets": markets_str,
        "oddsFormat": "american", "date": commence,
    }
    resp = requests.get(url, params=params, timeout=15)
    rem = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code in (404, 422):
        return None, rem, resp.status_code
    if resp.status_code != 200:
        return None, rem, resp.status_code
    data = resp.json().get("data", resp.json())
    cache_file.write_text(json.dumps(data))
    return (data if isinstance(data, dict) else None), rem, 200


def normalize(data, event_id, game_date, home, away, commence, batch_label):
    rows = []
    if not data:
        return rows
    for bm in data.get("bookmakers", []):
        book = bm.get("key", "")
        lu = bm.get("last_update", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            lu_m = mkt.get("last_update", lu)
            player_lines = {}
            for o in mkt.get("outcomes", []):
                desc = o.get("description", "")
                name = o.get("name", "")
                point = o.get("point")
                price = o.get("price")
                key = (desc, point)
                if key not in player_lines:
                    player_lines[key] = {}
                if name == "Over":
                    player_lines[key]["over_price"] = price
                elif name == "Under":
                    player_lines[key]["under_price"] = price
                else:
                    player_lines[key].setdefault("over_price", price)
                    player_lines[key].setdefault("over_name", name)
            for (desc, point), prices in player_lines.items():
                rows.append({
                    "sport": "nfl", "event_id": event_id, "game_date": game_date,
                    "commence_time": commence, "home_team": home, "away_team": away,
                    "bookmaker": book, "market_key": mk, "last_update": lu_m,
                    "player_name": None,
                    "line": point,
                    "over_price": prices.get("over_price"),
                    "under_price": prices.get("under_price"),
                    "implied_over": american_to_implied(prices.get("over_price")),
                    "implied_under": american_to_implied(prices.get("under_price")),
                    "pull_batch": batch_label,
                    "pull_timestamp": datetime.now().isoformat(),
                })
    return rows


def save_partition(rows):
    if not rows:
        return
    df = pd.DataFrame(rows)
    for (season, month), grp in df.groupby([
        df["game_date"].str[:4].astype(int),
        df["game_date"].str[5:7].astype(int),
    ]):
        part = ARCHIVE_DIR / f"season={season}" / f"month={month:02d}"
        part.mkdir(parents=True, exist_ok=True)
        path = part / f"data_{season}_{month:02d}.parquet"
        if path.exists():
            existing = pd.read_parquet(path)
            combined = pd.concat([existing, grp], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=["event_id", "bookmaker", "market_key", "line"], keep="last"
            )
        else:
            combined = grp
        combined.to_parquet(path, index=False)


def main():
    print("NFL Derivative Market Backfill")
    print(f"Markets: Q1 ({DERIVATIVE_MARKETS_Q1}), H1 ({DERIVATIVE_MARKETS_H1})")
    print(f"Scan: {SCAN_START} to {SCAN_END}")

    all_rows = []
    events_total = 0
    events_ok = 0
    events_404 = 0

    d = SCAN_START
    dates = []
    while d <= SCAN_END:
        dates.append(d.isoformat())
        d += timedelta(days=1)

    for i, ds in enumerate(dates):
        events, rem = pull_events(ds)
        real = [e for e in events if "All-Star" not in (e.get("home_team") or "")]

        for ev in real:
            eid = ev["id"]
            commence = ev.get("commence_time", f"{ds}T17:00:00Z")
            home = ev.get("home_team", "")
            away = ev.get("away_team", "")
            gd = commence[:10]
            events_total += 1

            # Q1 batch
            data_q1, rem_q1, st_q1 = pull_odds(eid, commence, DERIVATIVE_MARKETS_Q1, "q1")
            if st_q1 == 404:
                events_404 += 1
                time.sleep(0.08)
                continue
            events_ok += 1
            if data_q1:
                rows = normalize(data_q1, eid, gd, home, away, commence, "q1")
                all_rows.extend(rows)

            # H1 batch
            data_h1, rem_h1, st_h1 = pull_odds(eid, commence, DERIVATIVE_MARKETS_H1, "h1")
            if data_h1:
                rows = normalize(data_h1, eid, gd, home, away, commence, "h1")
                all_rows.extend(rows)

            time.sleep(0.1)

        if (i + 1) % 7 == 0 and events_total > 0:
            print(f"  [{i+1}/{len(dates)}] {ds}: events={events_total} "
                  f"(ok={events_ok}, 404={events_404}), rows={len(all_rows)}, credits={rem_q1}")

    # Save
    save_partition(all_rows)

    # Summary
    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    print(f"\n{'='*60}")
    print(f"BACKFILL COMPLETE")
    print(f"{'='*60}")
    print(f"Events scanned: {events_total}")
    print(f"Events with data: {events_ok}")
    print(f"Events expired (404): {events_404}")
    print(f"Total rows: {len(all_rows)}")
    if len(df) > 0:
        print(f"Unique games: {df['event_id'].nunique()}")
        print(f"Unique bookmakers: {df['bookmaker'].nunique()}")
        print(f"\nBy market_key:")
        print(df.groupby("market_key").agg(
            rows=("event_id", "count"),
            games=("event_id", "nunique"),
            books=("bookmaker", "nunique"),
        ).to_string())


if __name__ == "__main__":
    main()
