#!/usr/bin/env python3
"""
Multi-sport historical odds archive backfill — NBA, NFL, NHL.
Reuses the MLB archive pattern with sport-specific market batches.
"""

import json, os, sys, time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from config import ODDS_API_KEY, ODDS_API_BASE

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data" / "odds_archive"

SPORTS = {
    "basketball_nba": {
        "key": "nba", "label": "NBA",
        "start": "2025-10-01", "end": date.today().isoformat(),
        "batch_a": "player_points,player_rebounds,player_assists,player_points_rebounds_assists,player_threes",
        "batch_b": "player_blocks,player_steals,player_points_assists,player_points_rebounds,player_rebounds_assists,player_double_double",
        "batch_c": "totals,spreads,h2h,team_totals",
    },
    "americanfootball_nfl": {
        "key": "nfl", "label": "NFL",
        "start": "2025-09-01", "end": "2026-02-15",
        "batch_a": "player_pass_yds,player_pass_tds,player_pass_attempts,player_pass_completions,player_pass_interceptions",
        "batch_b": "player_rush_yds,player_rush_attempts,player_reception_yds,player_receptions,player_anytime_td",
        "batch_c": "totals,spreads,h2h,team_totals",
    },
    "icehockey_nhl": {
        "key": "nhl", "label": "NHL",
        "start": "2025-10-01", "end": date.today().isoformat(),
        "batch_a": "player_points,player_goals,player_assists,player_shots_on_goal,player_power_play_points",
        "batch_b": None,  # NHL has fewer prop markets, single batch suffices
        "batch_c": "totals,spreads,h2h,team_totals",
    },
}


def american_to_implied(odds):
    if odds is None: return None
    if odds > 0: return round(100 / (odds + 100), 4)
    return round(abs(odds) / (abs(odds) + 100), 4)


def pull_events(sport_api, date_str):
    url = f"{ODDS_API_BASE}/historical/sports/{sport_api}/events"
    params = {"apiKey": ODDS_API_KEY, "date": f"{date_str}T12:00:00Z"}
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200: return [], remaining
    data = resp.json()
    events = data.get("data", data) if isinstance(data, dict) else data
    return (events if isinstance(events, list) else []), remaining


def pull_batch(sport_api, eid, commence, markets_str):
    if not markets_str: return None, "?", 200
    url = f"{ODDS_API_BASE}/historical/sports/{sport_api}/events/{eid}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": markets_str,
              "oddsFormat": "american", "date": commence}
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code in (404, 422): return None, remaining, resp.status_code
    if resp.status_code != 200: return None, remaining, resp.status_code
    data = resp.json().get("data", resp.json())
    return (data if isinstance(data, dict) else None), remaining, 200


def normalize(data, sport_key, eid, game_date, home, away, commence, batch_label, ts):
    rows = []
    if not data: return rows
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
                if key not in player_lines: player_lines[key] = {}
                if name == "Over": player_lines[key]["over_price"] = price
                elif name == "Under": player_lines[key]["under_price"] = price
                else: player_lines[key].setdefault("over_price", price); player_lines[key].setdefault("over_name", name)
            for (desc, point), prices in player_lines.items():
                rows.append({
                    "sport": sport_key, "event_id": eid, "game_date": game_date,
                    "commence_time": commence, "home_team": home, "away_team": away,
                    "bookmaker": book, "market_key": mk, "last_update": lu_m,
                    "player_name": desc if "player_" in mk or "goalie_" in mk else None,
                    "line": point,
                    "over_price": prices.get("over_price"),
                    "under_price": prices.get("under_price"),
                    "implied_over": american_to_implied(prices.get("over_price")),
                    "implied_under": american_to_implied(prices.get("under_price")),
                    "pull_batch": batch_label, "pull_timestamp": ts,
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
            subset=["event_id", "bookmaker", "market_key", "player_name", "line"], keep="last")
    df.to_parquet(path, index=False)


def run_sport(sport_api, cfg):
    label = cfg["label"]
    sport_key = cfg["key"]
    archive = ARCHIVE_ROOT / sport_key
    print(f"\n{'='*60}\n{label} BACKFILL\n{'='*60}")

    start = datetime.strptime(cfg["start"], "%Y-%m-%d").date()
    end = datetime.strptime(cfg["end"], "%Y-%m-%d").date()
    all_dates = []
    d = start
    while d <= end:
        all_dates.append(d.isoformat())
        d += timedelta(days=1)
    print(f"Scanning {len(all_dates)} dates: {all_dates[0]} to {all_dates[-1]}")

    manifest = []
    prop_buf, game_buf = [], []
    ev_total = ev_ok = ev_404 = 0
    n_props = n_game = 0
    credits_start = None

    for i, ds in enumerate(all_dates):
        events, rem = pull_events(sport_api, ds)
        if credits_start is None and rem != "?": credits_start = int(rem)
        real = [e for e in events if "All-Star" not in (e.get("home_team") or "")]

        for event in real:
            eid = event["id"]
            commence = event.get("commence_time", f"{ds}T23:00:00Z")
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            gd = commence[:10]
            season = int(gd[:4])
            month = int(gd[5:7])
            ts = datetime.now().isoformat()
            ev_total += 1
            manifest.append({"sport": sport_key, "event_id": eid, "commence_time": commence,
                              "home_team": home, "away_team": away, "date": gd, "season": season})

            # Batch A
            data_a, rem, st_a = pull_batch(sport_api, eid, commence, cfg["batch_a"])
            if st_a == 404:
                ev_404 += 1; manifest[-1]["fetch_status"] = "expired"; time.sleep(0.08); continue
            ev_ok += 1; manifest[-1]["fetch_status"] = "success"
            if data_a:
                rows = normalize(data_a, sport_key, eid, gd, home, away, commence, "props_a", ts)
                prop_buf.extend(rows); n_props += len(rows)

            # Batch B
            if cfg["batch_b"]:
                data_b, rem, _ = pull_batch(sport_api, eid, commence, cfg["batch_b"])
                if data_b:
                    rows = normalize(data_b, sport_key, eid, gd, home, away, commence, "props_b", ts)
                    prop_buf.extend(rows); n_props += len(rows)

            # Batch C (game markets)
            data_c, rem, _ = pull_batch(sport_api, eid, commence, cfg["batch_c"])
            if data_c:
                rows = normalize(data_c, sport_key, eid, gd, home, away, commence, "game", ts)
                game_buf.extend(rows); n_game += len(rows)

            time.sleep(0.1)

        if (i+1) % 7 == 0:
            print(f"  [{i+1}/{len(all_dates)}] {ds}: ev={ev_total}(ok={ev_ok},404={ev_404}), "
                  f"props={n_props}, game={n_game}, credits={rem}")

        # Save every 200 ok events
        if ev_ok > 0 and ev_ok % 200 == 0:
            if prop_buf:
                pdf = pd.DataFrame(prop_buf)
                for (s, m), g in pdf.groupby([pdf.game_date.str[:4].astype(int), pdf.game_date.str[5:7].astype(int)]):
                    save_partition(g.to_dict("records"), archive / "props", s, m)
                prop_buf = []
            if game_buf:
                gdf = pd.DataFrame(game_buf)
                for (s, m), g in gdf.groupby([gdf.game_date.str[:4].astype(int), gdf.game_date.str[5:7].astype(int)]):
                    save_partition(g.to_dict("records"), archive / "game_markets", s, m)
                game_buf = []

    # Final flush
    if prop_buf:
        pdf = pd.DataFrame(prop_buf)
        for (s, m), g in pdf.groupby([pdf.game_date.str[:4].astype(int), pdf.game_date.str[5:7].astype(int)]):
            save_partition(g.to_dict("records"), archive / "props", s, m)
    if game_buf:
        gdf = pd.DataFrame(game_buf)
        for (s, m), g in gdf.groupby([gdf.game_date.str[:4].astype(int), gdf.game_date.str[5:7].astype(int)]):
            save_partition(g.to_dict("records"), archive / "game_markets", s, m)

    # Manifest
    mdf = pd.DataFrame(manifest)
    mdf.to_parquet(archive / "manifests" / f"{sport_key}_event_manifest.parquet", index=False)
    mdf.to_csv(archive / "manifests" / f"{sport_key}_event_manifest.csv", index=False)

    credits_end = int(rem) if rem != "?" else 0
    credits_used = (credits_start - credits_end) if credits_start else 0
    pd.DataFrame([{"sport": sport_key, "events": ev_total, "success": ev_ok, "expired": ev_404,
                    "props": n_props, "game_markets": n_game, "credits": credits_used}]).to_parquet(
        archive / "logs" / "pull_log.parquet", index=False)

    print(f"\n{label} COMPLETE: {ev_ok} events, {n_props} props, {n_game} game mkts, ~{credits_used} credits")
    return {"sport": label, "events": ev_ok, "expired": ev_404, "props": n_props, "game": n_game, "credits": credits_used}


if __name__ == "__main__":
    # 2026-03-27: NBA already complete — run NFL and NHL only
    SKIP_SPORTS = {"basketball_nba"}
    results = []
    for sport_api, cfg in SPORTS.items():
        if sport_api in SKIP_SPORTS:
            print(f"\nSKIPPING {cfg['label']} (already complete)")
            continue
        r = run_sport(sport_api, cfg)
        results.append(r)
    print(f"\n{'='*60}\nALL SPORTS COMPLETE")
    for r in results:
        print(f"  {r['sport']}: {r['events']} events, {r['props']} props, {r['game']} game mkts, ~{r['credits']} credits")
