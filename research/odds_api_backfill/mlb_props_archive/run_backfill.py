#!/usr/bin/env python3
"""
MLB Historical Odds Archive Backfill.
Pulls all player props + core game markets from April 2025 through present.
"""

import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from config import ODDS_API_KEY, ODDS_API_BASE, ODDS_API_TEAM_MAP

ARCHIVE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "odds_archive" / "mlb"
SPORT = "baseball_mlb"

BATCH_A = "batter_total_bases,batter_hits,batter_home_runs,batter_runs_scored,batter_rbis,batter_hits_runs_rbis,batter_stolen_bases"
BATCH_B = "pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed,pitcher_walks,pitcher_earned_runs"
BATCH_C = "totals,spreads,h2h,team_totals,totals_1st_5_innings,spreads_1st_5_innings,h2h_1st_5_innings"


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


def pull_batch(event_id, commence_time, markets_str):
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY, "regions": "us",
        "markets": markets_str, "oddsFormat": "american",
        "date": commence_time,
    }
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code == 404:
        return None, remaining, 404
    if resp.status_code != 200:
        return None, remaining, resp.status_code

    data = resp.json().get("data", resp.json())
    if not isinstance(data, dict):
        return None, remaining, resp.status_code
    return data, remaining, 200


def normalize_outcomes(data, event_id, game_date, home_team, away_team,
                        commence_time, batch_label, pull_ts):
    """Flatten API response into rows."""
    rows = []
    for bm in data.get("bookmakers", []):
        book = bm.get("key", "")
        last_update = bm.get("last_update", "")
        for mkt in bm.get("markets", []):
            market_key = mkt.get("key", "")
            last_update_mkt = mkt.get("last_update", last_update)

            # Group outcomes by player+line
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
                    player_lines[key]["over_name"] = name
                elif name == "Under":
                    player_lines[key]["under_price"] = price
                    player_lines[key]["under_name"] = name
                # h2h/spreads have different names
                elif point is not None:
                    player_lines[key].setdefault("over_price", price)
                    player_lines[key].setdefault("over_name", name)
                else:
                    player_lines[key].setdefault("over_price", price)
                    player_lines[key].setdefault("over_name", name)

            for (desc, point), prices in player_lines.items():
                row = {
                    "sport": "baseball_mlb",
                    "event_id": event_id,
                    "game_date": game_date,
                    "commence_time": commence_time,
                    "home_team": home_team,
                    "away_team": away_team,
                    "bookmaker": book,
                    "market_key": market_key,
                    "last_update": last_update_mkt,
                    "player_name": desc if "batter_" in market_key or "pitcher_" in market_key else None,
                    "line": point,
                    "over_price": prices.get("over_price"),
                    "under_price": prices.get("under_price"),
                    "over_name": prices.get("over_name"),
                    "under_name": prices.get("under_name"),
                    "implied_over": american_to_implied(prices.get("over_price")),
                    "implied_under": american_to_implied(prices.get("under_price")),
                    "pull_batch": batch_label,
                    "pull_timestamp": pull_ts,
                }
                rows.append(row)
    return rows


def save_partition(rows, base_dir, season, month):
    """Save rows to a partition directory."""
    if not rows:
        return
    part_dir = base_dir / f"season={season}" / f"month={month:02d}"
    part_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    path = part_dir / f"data_{season}_{month:02d}.parquet"
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(
            subset=["event_id", "bookmaker", "market_key", "player_name", "line"],
            keep="last"
        )
    df.to_parquet(path, index=False)


def main():
    # Generate date range
    start = date(2025, 3, 27)
    end = date.today()
    all_dates = []
    d = start
    while d <= end:
        all_dates.append(d.isoformat())
        d += timedelta(days=1)

    print(f"Backfill: {len(all_dates)} dates from {all_dates[0]} to {all_dates[-1]}")

    # Build manifest
    manifest_rows = []
    prop_rows_buffer = []
    game_rows_buffer = []
    pull_log = []

    events_total = 0
    events_success = 0
    events_404 = 0
    total_prop_records = 0
    total_game_records = 0
    credits_start = None

    for i, date_str in enumerate(all_dates):
        events, remaining = pull_events(date_str)
        if credits_start is None and remaining != "?":
            credits_start = int(remaining)

        # Filter
        real = [e for e in events if all(
            k not in (e.get("home_team") or "")
            for k in ["All-Star", "National", "American"]
        )]

        for event in real:
            eid = event["id"]
            commence = event.get("commence_time", f"{date_str}T23:00:00Z")
            home = ODDS_API_TEAM_MAP.get(event.get("home_team", ""), event.get("home_team", ""))
            away = ODDS_API_TEAM_MAP.get(event.get("away_team", ""), event.get("away_team", ""))
            game_date = commence[:10]
            season = int(game_date[:4])
            month = int(game_date[5:7])
            pull_ts = datetime.now().isoformat()

            events_total += 1
            manifest_rows.append({
                "event_id": eid, "commence_time": commence,
                "home_team": home, "away_team": away,
                "date": game_date, "season": season,
            })

            # Batch A: batter props
            data_a, remaining, status_a = pull_batch(eid, commence, BATCH_A)
            if status_a == 404:
                events_404 += 1
                manifest_rows[-1]["fetch_status"] = "expired"
                time.sleep(0.1)
                continue

            events_success += 1
            manifest_rows[-1]["fetch_status"] = "success"

            if data_a:
                rows_a = normalize_outcomes(data_a, eid, game_date, home, away,
                                            commence, "batter_props", pull_ts)
                prop_rows_buffer.extend(rows_a)
                total_prop_records += len(rows_a)

            # Batch B: pitcher props
            data_b, remaining, status_b = pull_batch(eid, commence, BATCH_B)
            if data_b:
                rows_b = normalize_outcomes(data_b, eid, game_date, home, away,
                                            commence, "pitcher_props", pull_ts)
                prop_rows_buffer.extend(rows_b)
                total_prop_records += len(rows_b)

            # Batch C: game markets
            data_c, remaining, status_c = pull_batch(eid, commence, BATCH_C)
            if data_c:
                rows_c = normalize_outcomes(data_c, eid, game_date, home, away,
                                            commence, "game_markets", pull_ts)
                game_rows_buffer.extend(rows_c)
                total_game_records += len(rows_c)

            time.sleep(0.12)

        # Progress every 7 days
        if (i + 1) % 7 == 0:
            print(f"  [{i+1}/{len(all_dates)}] {date_str}: "
                  f"events={events_total} (ok={events_success}, 404={events_404}), "
                  f"props={total_prop_records}, game_mkts={total_game_records}, "
                  f"credits={remaining}")

        # Save partitions every 100 events
        if events_success > 0 and events_success % 100 == 0:
            # Group by season/month and save
            if prop_rows_buffer:
                pdf = pd.DataFrame(prop_rows_buffer)
                for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                                 pdf.game_date.str[5:7].astype(int)]):
                    save_partition(grp.to_dict("records"), ARCHIVE / "props", s, m)
                prop_rows_buffer = []
            if game_rows_buffer:
                gdf = pd.DataFrame(game_rows_buffer)
                for (s, m), grp in gdf.groupby([gdf.game_date.str[:4].astype(int),
                                                  gdf.game_date.str[5:7].astype(int)]):
                    save_partition(grp.to_dict("records"), ARCHIVE / "game_markets", s, m)
                game_rows_buffer = []

    # Final flush
    if prop_rows_buffer:
        pdf = pd.DataFrame(prop_rows_buffer)
        for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                         pdf.game_date.str[5:7].astype(int)]):
            save_partition(grp.to_dict("records"), ARCHIVE / "props", s, m)
    if game_rows_buffer:
        gdf = pd.DataFrame(game_rows_buffer)
        for (s, m), grp in gdf.groupby([gdf.game_date.str[:4].astype(int),
                                          gdf.game_date.str[5:7].astype(int)]):
            save_partition(grp.to_dict("records"), ARCHIVE / "game_markets", s, m)

    # Save manifest
    mdf = pd.DataFrame(manifest_rows)
    mdf.to_parquet(ARCHIVE / "manifests" / "mlb_event_manifest_2025_2026.parquet", index=False)
    mdf.to_csv(ARCHIVE / "manifests" / "mlb_event_manifest_2025_2026.csv", index=False)

    # Pull log
    credits_end = int(remaining) if remaining != "?" else 0
    credits_used = (credits_start - credits_end) if credits_start else 0

    log_entry = {
        "pull_start": all_dates[0], "pull_end": all_dates[-1],
        "events_total": events_total, "events_success": events_success,
        "events_404": events_404,
        "prop_records": total_prop_records, "game_records": total_game_records,
        "credits_used": credits_used, "credits_remaining": credits_end,
    }
    pd.DataFrame([log_entry]).to_parquet(ARCHIVE / "logs" / "pull_log.parquet", index=False)

    print(f"\n{'='*60}")
    print(f"BACKFILL COMPLETE")
    print(f"Events: {events_total} total, {events_success} success, {events_404} expired")
    print(f"Prop records: {total_prop_records}")
    print(f"Game market records: {total_game_records}")
    print(f"Credits used: ~{credits_used}")
    print(f"Credits remaining: {credits_end}")


if __name__ == "__main__":
    main()
