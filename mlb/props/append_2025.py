#!/usr/bin/env python3
"""
Append 2025 MLB season events and odds to the P2 backfill.
Run this AFTER the main build_p2.py completes its 2023-2024 run.

Usage:
    python3 mlb/props/append_2025.py
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "mlb" / "props" / "raw"
API_KEY = os.getenv("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb"
MARKETS = "pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed,pitcher_earned_runs,batter_hits,batter_total_bases,batter_home_runs,batter_rbis"

SEASON_2025 = ("2025-03-27", "2025-09-28")


def main():
    print("=" * 60)
    print("APPENDING 2025 SEASON TO P2 BACKFILL")
    print("=" * 60)

    # Load existing events
    events_file = RAW_DIR / "events.parquet"
    existing_events = pd.read_parquet(events_file)
    existing_2025 = existing_events[existing_events["season"] == 2025]
    print(f"Existing events: {len(existing_events):,} ({len(existing_2025)} from 2025)")

    # Collect 2025 events
    if len(existing_2025) == 0:
        print("\nCollecting 2025 events...")
        new_events = []
        start, end = SEASON_2025
        dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")

        while dt <= end_dt:
            date_str = dt.strftime("%Y-%m-%dT18:00:00Z")
            try:
                r = requests.get(f"{BASE_URL}/events",
                                  params={"apiKey": API_KEY, "date": date_str}, timeout=30)
                if r.status_code == 200:
                    for e in r.json().get("data", []):
                        new_events.append({
                            "event_id": e["id"],
                            "commence_time": e.get("commence_time", ""),
                            "home_team": e.get("home_team", ""),
                            "away_team": e.get("away_team", ""),
                            "date": dt.strftime("%Y-%m-%d"),
                            "season": 2025,
                        })
            except Exception as ex:
                print(f"  {dt.strftime('%Y-%m-%d')}: {ex}")

            dt += timedelta(days=1)
            time.sleep(0.15)

            if len(new_events) % 500 == 0 and new_events:
                print(f"  {len(new_events)} events...")

        new_df = pd.DataFrame(new_events)
        combined = pd.concat([existing_events, new_df], ignore_index=True)
        combined.to_parquet(events_file, index=False)
        print(f"  2025 events added: {len(new_df):,}")
    else:
        new_df = existing_2025
        print(f"  2025 events already present: {len(new_df)}")

    # Collect 2025 odds
    odds_file = RAW_DIR / "odds_raw.parquet"
    existing_odds = pd.read_parquet(odds_file)
    collected_ids = set(existing_odds["event_id"].unique())

    events_2025 = new_df if len(existing_2025) == 0 else existing_2025
    remaining = events_2025[~events_2025["event_id"].isin(collected_ids)]
    print(f"\n2025 events needing odds: {len(remaining)}")

    if len(remaining) == 0:
        print("All 2025 events already have odds. Done.")
        return

    all_rows = existing_odds.to_dict("records")
    batch = 0
    errors = 0

    for _, event in remaining.iterrows():
        eid = event["event_id"]
        date = event["date"]
        query_date = f"{date}T18:00:00Z"

        try:
            r = requests.get(
                f"{BASE_URL}/events/{eid}/odds",
                params={"apiKey": API_KEY, "date": query_date, "regions": "us",
                        "markets": MARKETS, "oddsFormat": "american"},
                timeout=30)

            if r.status_code == 200:
                data = r.json()
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
                                "event_id": eid, "game_date": date, "season": 2025,
                                "home_team": event["home_team"], "away_team": event["away_team"],
                                "market": mkt["key"], "player_name": player,
                                "line": float(line), "over_odds": over.get("price"),
                                "under_odds": under.get("price"), "bookmaker": bk["key"],
                                "snapshot_timestamp": data.get("timestamp", ""),
                                "pull_timestamp": datetime.now().isoformat(),
                            })
        except Exception as ex:
            errors += 1
            if errors <= 5:
                print(f"  {eid}: {ex}")

        batch += 1
        time.sleep(0.2)

        if batch % 200 == 0:
            pd.DataFrame(all_rows).to_parquet(odds_file, index=False)
            credits = r.headers.get("x-requests-remaining", "?") if r else "?"
            print(f"  Checkpoint: {batch}/{len(remaining)}, "
                  f"{len(all_rows):,} total rows, credits={credits}")

    pd.DataFrame(all_rows).to_parquet(odds_file, index=False)
    new_count = len(all_rows) - len(existing_odds)
    print(f"\n2025 odds appended: {new_count:,} new rows")
    print(f"Total odds: {len(all_rows):,}")
    print(f"Errors: {errors}")
    print("\nDone. Re-run build_p2.py to regenerate processed outputs with 2025 included.")


if __name__ == "__main__":
    main()
