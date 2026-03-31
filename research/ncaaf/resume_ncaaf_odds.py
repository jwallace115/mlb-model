#!/usr/bin/env python3
"""
Resume NCAAF odds backfill — 2023 remainder + full 2024.
Continues from where Phase 1 stopped (2023-09-16).
"""

import json, os, sys, time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import ODDS_API_KEY, ODDS_API_BASE

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "odds_archive" / "ncaaf"
SPORT = "americanfootball_ncaaf"
MARKETS = "h2h,spreads,totals"
CREDIT_LIMIT = 180_000


def pull_events(date_str):
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events"
    params = {"apiKey": ODDS_API_KEY, "date": f"{date_str}T12:00:00Z"}
    resp = requests.get(url, params=params, timeout=15)
    rem = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200: return [], rem
    data = resp.json()
    events = data.get("data", data) if isinstance(data, dict) else data
    return (events if isinstance(events, list) else []), rem


def pull_odds(eid, commence):
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events/{eid}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": MARKETS,
              "oddsFormat": "american", "date": commence}
    resp = requests.get(url, params=params, timeout=15)
    rem = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code in (404, 422): return None, rem, resp.status_code
    if resp.status_code != 200: return None, rem, resp.status_code
    data = resp.json().get("data", resp.json())
    return (data if isinstance(data, dict) else None), rem, 200


def normalize(data, eid, gd, home, away, commence, ts):
    rows = []
    if not data: return rows
    for bm in data.get("bookmakers", []):
        book = bm.get("key", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            player_lines = {}
            for o in mkt.get("outcomes", []):
                desc = o.get("description", "")
                name = o.get("name", "")
                point = o.get("point")
                price = o.get("price")
                key = (desc, point)
                if key not in player_lines: player_lines[key] = {}
                if name == "Over": player_lines[key]["over_price"] = price
                elif name == "Under": player_lines[key]["under_price"] = price
                else: player_lines[key].setdefault("over_price", price)
            for (desc, point), prices in player_lines.items():
                rows.append({
                    "sport": "ncaaf", "event_id": eid, "game_date": gd,
                    "commence_time": commence, "home_team": home, "away_team": away,
                    "bookmaker": book, "market_key": mk,
                    "player_name": None, "line": point,
                    "over_price": prices.get("over_price"),
                    "under_price": prices.get("under_price"),
                    "pull_batch": "game", "pull_timestamp": ts,
                })
    return rows


def save_partition(rows, base_dir, season, month):
    if not rows: return
    part = base_dir / f"season={season}" / f"month={month:02d}"
    part.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    path = part / f"data_{season}_{month:02d}.parquet"
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(
            subset=["event_id", "bookmaker", "market_key", "line"], keep="last")
    df.to_parquet(path, index=False)


# Date ranges to pull
RANGES = [
    ("2023-09-16", "2024-01-09"),  # 2023 remainder
    ("2024-08-24", "2025-01-20"),  # full 2024
]

manifest = []
buf = []
ev_total = ev_ok = ev_404 = 0
n_rows = 0
credits_start = None

for start_str, end_str in RANGES:
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    all_dates = []
    d = start
    while d <= end:
        all_dates.append(d.isoformat())
        d += timedelta(days=1)

    print(f"\n{'='*60}")
    print(f"Pulling {start_str} to {end_str} ({len(all_dates)} dates)")
    print(f"{'='*60}")

    for i, ds in enumerate(all_dates):
        events, rem = pull_events(ds)
        if credits_start is None and rem != "?":
            credits_start = int(rem)

        if credits_start and rem != "?":
            consumed = credits_start - int(rem)
            if consumed > CREDIT_LIMIT:
                print(f"\n  CREDIT LIMIT: {consumed:,} > {CREDIT_LIMIT:,}")
                if buf:
                    pdf = pd.DataFrame(buf)
                    for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                                     pdf.game_date.str[5:7].astype(int)]):
                        save_partition(grp.to_dict("records"), ARCHIVE_ROOT / "game_markets", s, m)
                print(f"\n  STOPPED: {ev_ok} events, {n_rows} rows, ~{consumed:,} credits")
                sys.exit(0)

        for event in events:
            eid = event["id"]
            commence = event.get("commence_time", f"{ds}T23:00:00Z")
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            gd = commence[:10]
            ts = datetime.now().isoformat()
            ev_total += 1

            manifest.append({"event_id": eid, "commence_time": commence,
                              "home_team": home, "away_team": away, "date": gd})

            data, rem, status = pull_odds(eid, commence, )
            if status == 404:
                ev_404 += 1; time.sleep(0.08); continue

            ev_ok += 1
            if data:
                rows = normalize(data, eid, gd, home, away, commence, ts)
                buf.extend(rows); n_rows += len(rows)
            time.sleep(0.1)

        if (i + 1) % 7 == 0:
            print(f"  [{i+1}/{len(all_dates)}] {ds}: ev={ev_total}(ok={ev_ok},404={ev_404}), "
                  f"rows={n_rows}, credits={rem}")

        if ev_ok > 0 and ev_ok % 200 == 0 and buf:
            pdf = pd.DataFrame(buf)
            for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                             pdf.game_date.str[5:7].astype(int)]):
                save_partition(grp.to_dict("records"), ARCHIVE_ROOT / "game_markets", s, m)
            buf = []

# Final flush
if buf:
    pdf = pd.DataFrame(buf)
    for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                     pdf.game_date.str[5:7].astype(int)]):
        save_partition(grp.to_dict("records"), ARCHIVE_ROOT / "game_markets", s, m)

# Update manifest
mpath = ARCHIVE_ROOT / "manifests" / "ncaaf_event_manifest.parquet"
if mpath.exists():
    existing_m = pd.read_parquet(mpath)
    new_m = pd.DataFrame(manifest)
    combined = pd.concat([existing_m, new_m], ignore_index=True).drop_duplicates(subset="event_id", keep="last")
    combined.to_parquet(mpath, index=False)
else:
    pd.DataFrame(manifest).to_parquet(mpath, index=False)

credits_end = int(rem) if rem != "?" else 0
credits_used = (credits_start - credits_end) if credits_start else 0

print(f"\n{'='*60}")
print(f"RESUME COMPLETE: {ev_ok} events, {n_rows} rows, ~{credits_used:,} credits")
print(f"{'='*60}")
