#!/usr/bin/env python3
"""
NCAAF Historical Odds Backfill — Phases 1 & 2.
Reuses the multi-sport backfill pattern.
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

SEASONS = {
    2022: ("2022-08-27", "2023-01-10"),
    2023: ("2023-08-26", "2024-01-09"),
    2024: ("2024-08-24", "2025-01-20"),
}

GAME_MARKETS = "h2h,spreads,totals"
PROP_MARKETS_A = "player_pass_yds,player_rush_yds,player_reception_yds,player_pass_tds,player_anytime_td"


def american_to_implied(odds):
    if odds is None: return None
    if odds > 0: return round(100 / (odds + 100), 4)
    return round(abs(odds) / (abs(odds) + 100), 4)


def pull_events(date_str):
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events"
    params = {"apiKey": ODDS_API_KEY, "date": f"{date_str}T12:00:00Z"}
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code != 200: return [], remaining
    data = resp.json()
    events = data.get("data", data) if isinstance(data, dict) else data
    return (events if isinstance(events, list) else []), remaining


def pull_odds(eid, commence, markets_str):
    if not markets_str: return None, "?", 200
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT}/events/{eid}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": markets_str,
              "oddsFormat": "american", "date": commence}
    resp = requests.get(url, params=params, timeout=15)
    remaining = resp.headers.get("x-requests-remaining", "?")
    if resp.status_code in (404, 422): return None, remaining, resp.status_code
    if resp.status_code != 200: return None, remaining, resp.status_code
    data = resp.json().get("data", resp.json())
    return (data if isinstance(data, dict) else None), remaining, 200


def normalize(data, eid, game_date, home, away, commence, batch_label, ts):
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
                else:
                    player_lines[key].setdefault("over_price", price)
                    player_lines[key].setdefault("over_name", name)
            for (desc, point), prices in player_lines.items():
                rows.append({
                    "sport": "ncaaf", "event_id": eid, "game_date": game_date,
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


def run_phase(markets_str, output_dir, batch_label, phase_name, credit_limit=None):
    print(f"\n{'='*60}")
    print(f"{phase_name}")
    print(f"{'='*60}")

    manifest = []
    all_buf = []
    ev_total = ev_ok = ev_404 = 0
    n_rows = 0
    credits_start = None

    for season, (start_str, end_str) in sorted(SEASONS.items()):
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        all_dates = []
        d = start
        while d <= end:
            all_dates.append(d.isoformat())
            d += timedelta(days=1)

        print(f"\n  Season {season}: {len(all_dates)} dates ({start_str} to {end_str})")
        season_ev = 0

        for i, ds in enumerate(all_dates):
            events, rem = pull_events(ds)
            if credits_start is None and rem != "?":
                credits_start = int(rem)

            # Check credit limit
            if credit_limit and credits_start and rem != "?":
                consumed = credits_start - int(rem)
                if consumed > credit_limit:
                    print(f"\n  CREDIT LIMIT REACHED: {consumed:,} > {credit_limit:,}")
                    # Flush
                    if all_buf:
                        pdf = pd.DataFrame(all_buf)
                        for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                                         pdf.game_date.str[5:7].astype(int)]):
                            save_partition(grp.to_dict("records"), output_dir, s, m)
                    return ev_total, ev_ok, ev_404, n_rows, credits_start - int(rem)

            for event in events:
                eid = event["id"]
                commence = event.get("commence_time", f"{ds}T23:00:00Z")
                home = event.get("home_team", "")
                away = event.get("away_team", "")
                gd = commence[:10]
                s = int(gd[:4])
                month = int(gd[5:7])
                ts = datetime.now().isoformat()
                ev_total += 1; season_ev += 1

                manifest.append({"sport": "ncaaf", "event_id": eid, "commence_time": commence,
                                  "home_team": home, "away_team": away, "date": gd,
                                  "season": season})

                data, rem, status = pull_odds(eid, commence, markets_str)
                if status == 404:
                    ev_404 += 1
                    manifest[-1]["fetch_status"] = "expired"
                    time.sleep(0.08)
                    continue

                ev_ok += 1
                manifest[-1]["fetch_status"] = "success"
                if data:
                    rows = normalize(data, eid, gd, home, away, commence, batch_label, ts)
                    all_buf.extend(rows)
                    n_rows += len(rows)

                time.sleep(0.1)

            if (i + 1) % 7 == 0:
                print(f"    [{i+1}/{len(all_dates)}] {ds}: ev={ev_total}(ok={ev_ok},404={ev_404}), "
                      f"rows={n_rows}, credits={rem}")

            # Flush every 200 ok events
            if ev_ok > 0 and ev_ok % 200 == 0 and all_buf:
                pdf = pd.DataFrame(all_buf)
                for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                                 pdf.game_date.str[5:7].astype(int)]):
                    save_partition(grp.to_dict("records"), output_dir, s, m)
                all_buf = []

        print(f"  Season {season}: {season_ev} events")

    # Final flush
    if all_buf:
        pdf = pd.DataFrame(all_buf)
        for (s, m), grp in pdf.groupby([pdf.game_date.str[:4].astype(int),
                                         pdf.game_date.str[5:7].astype(int)]):
            save_partition(grp.to_dict("records"), output_dir, s, m)

    # Manifest
    if manifest:
        mdf = pd.DataFrame(manifest)
        mdf.to_parquet(ARCHIVE_ROOT / "manifests" / "ncaaf_event_manifest.parquet", index=False)

    credits_end = int(rem) if rem != "?" else 0
    credits_used = (credits_start - credits_end) if credits_start else 0

    # Pull log
    pd.DataFrame([{"sport": "ncaaf", "phase": phase_name, "events": ev_total,
                    "success": ev_ok, "expired": ev_404, "rows": n_rows,
                    "credits": credits_used}]).to_parquet(
        ARCHIVE_ROOT / "logs" / "pull_log.parquet", index=False)

    print(f"\n  {phase_name} COMPLETE: {ev_ok} events, {n_rows} rows, ~{credits_used:,} credits")
    return ev_total, ev_ok, ev_404, n_rows, credits_used


if __name__ == "__main__":
    # Phase 1: Game markets
    _, _, _, _, p1_credits = run_phase(
        GAME_MARKETS,
        ARCHIVE_ROOT / "game_markets",
        "game",
        "PHASE 1 — GAME MARKETS (h2h, spreads, totals)",
        credit_limit=200_000,
    )

    print(f"\n\nPhase 1 credits: {p1_credits:,}")

    # Phase 2: Props (only if Phase 1 < 200K)
    if p1_credits < 200_000:
        print(f"Phase 1 under 200K — proceeding to Phase 2 (props)")
        _, _, _, _, p2_credits = run_phase(
            PROP_MARKETS_A,
            ARCHIVE_ROOT / "props",
            "props",
            "PHASE 2 — PLAYER PROPS",
            credit_limit=350_000 - p1_credits,
        )
        print(f"\nPhase 2 credits: {p2_credits:,}")
        print(f"Total credits: {p1_credits + p2_credits:,}")
    else:
        print(f"Phase 1 used {p1_credits:,} credits — skipping Phase 2")
