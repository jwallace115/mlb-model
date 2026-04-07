#!/usr/bin/env python3
"""
NFL Historical Props Backfill — 2023 and 2024 seasons.
Pulls player props from The Odds API historical endpoint.
Uses same schema and partition convention as existing 2025 archive.
"""
import json, os, sys, time
from datetime import date, datetime, timedelta
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
    return ""

API_KEY = _load_key()
BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "odds_archive" / "nfl" / "props"
CACHE_DIR = PROJECT_ROOT / "nfl" / "research_derivatives" / "cache" / "props_backfill"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROPS_BATCH_A = "player_pass_yds,player_pass_tds,player_pass_attempts,player_pass_completions,player_pass_interceptions"
PROPS_BATCH_B = "player_rush_yds,player_rush_attempts,player_reception_yds,player_receptions,player_anytime_td"

SEASONS = [
    {"year": 2023, "start": "2023-09-01", "end": "2024-02-15"},
    {"year": 2024, "start": "2024-09-01", "end": "2025-02-15"},
]


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
    params = {"apiKey": API_KEY, "date": f"{date_str}T12:00:00Z"}
    resp = requests.get(f"{BASE}/historical/sports/{SPORT}/events",
                        params=params, timeout=15)
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
        return json.loads(cache_file.read_text()), "cached", 200
    params = {
        "apiKey": API_KEY, "regions": "us", "markets": markets_str,
        "oddsFormat": "american", "date": commence,
    }
    resp = requests.get(f"{BASE}/historical/sports/{SPORT}/events/{event_id}/odds",
                        params=params, timeout=15)
    rem = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code == 429:
        print("  Rate limited — waiting 5s...")
        time.sleep(5)
        resp = requests.get(f"{BASE}/historical/sports/{SPORT}/events/{event_id}/odds",
                            params=params, timeout=15)
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
    ts = datetime.now().isoformat()
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
            for (desc, point), prices in player_lines.items():
                rows.append({
                    "sport": "nfl", "event_id": event_id, "game_date": game_date,
                    "commence_time": commence, "home_team": home, "away_team": away,
                    "bookmaker": book, "market_key": mk, "last_update": lu_m,
                    "player_name": desc if "player_" in mk else None,
                    "line": point,
                    "over_price": prices.get("over_price"),
                    "under_price": prices.get("under_price"),
                    "implied_over": american_to_implied(prices.get("over_price")),
                    "implied_under": american_to_implied(prices.get("under_price")),
                    "pull_batch": batch_label, "pull_timestamp": ts,
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
                subset=["event_id", "bookmaker", "market_key", "player_name", "line"],
                keep="last")
        else:
            combined = grp
        combined.to_parquet(path, index=False)


def main():
    for season_cfg in SEASONS:
        year = season_cfg["year"]
        start = datetime.strptime(season_cfg["start"], "%Y-%m-%d").date()
        end = datetime.strptime(season_cfg["end"], "%Y-%m-%d").date()

        print(f"\n{'='*60}")
        print(f"NFL {year} SEASON PROPS BACKFILL")
        print(f"{'='*60}")

        dates = []
        d = start
        while d <= end:
            dates.append(d.isoformat())
            d += timedelta(days=1)

        all_rows = []
        ev_total = ev_ok = ev_404 = 0

        for i, ds in enumerate(dates):
            events, rem = pull_events(ds)
            real = [e for e in events if "All-Star" not in (e.get("home_team") or "")]

            for ev in real:
                eid = ev["id"]
                commence = ev.get("commence_time", f"{ds}T17:00:00Z")
                home = ev.get("home_team", "")
                away = ev.get("away_team", "")
                gd = commence[:10]
                ev_total += 1

                # Batch A (passing props)
                data_a, rem_a, st_a = pull_odds(eid, commence, PROPS_BATCH_A, "props_a")
                if st_a == 404:
                    ev_404 += 1
                    time.sleep(0.08)
                    continue
                ev_ok += 1
                if data_a:
                    all_rows.extend(normalize(data_a, eid, gd, home, away, commence, "props_a"))

                # Batch B (receiving/rushing/TD props)
                data_b, rem_b, st_b = pull_odds(eid, commence, PROPS_BATCH_B, "props_b")
                if data_b:
                    all_rows.extend(normalize(data_b, eid, gd, home, away, commence, "props_b"))

                time.sleep(0.1)

            if (i + 1) % 7 == 0 and ev_total > 0:
                print(f"  [{i+1}/{len(dates)}] {ds}: ev={ev_total} "
                      f"(ok={ev_ok}, 404={ev_404}), rows={len(all_rows)}, credits={rem_a}")

        # Save
        save_partition(all_rows)

        # Summary
        df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
        print(f"\n  Season {year} complete:")
        print(f"  Events: {ev_total} (ok={ev_ok}, 404={ev_404})")
        print(f"  Rows: {len(all_rows)}")
        if len(df) > 0:
            print(f"  Games: {df['event_id'].nunique()}")
            print(f"  Players: {df['player_name'].nunique()}")
            print(f"  Books: {df['bookmaker'].nunique()}")
            print(f"  Markets: {df['market_key'].nunique()}")
            by_mkt = df.groupby('market_key')['event_id'].agg(['count', 'nunique'])
            print(f"  By market:")
            for mk, row in by_mkt.iterrows():
                print(f"    {mk}: {row['count']} rows, {row['nunique']} games")

        all_rows = []  # Reset for next season

    print(f"\n{'='*60}")
    print("BACKFILL COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
