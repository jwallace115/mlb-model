#!/usr/bin/env python3
"""
Pull NHL historical odds from the Odds API.

Subcommands:
  lines    — h2h, spreads, totals for 2022-23 .. 2025-26 (featured snapshot endpoint)
  threeway — h2h_3_way for 2024-25 (per-event endpoint)
  props    — player props for 2024-25 (per-event endpoint)

Cost model (historical): 10 x markets x regions per call.
  bookmakers= with <= 10 books = 1 region-equivalent.
  lines: 10 x 3 x 1 = 30 per snapshot.
  threeway per event: 10 x 1 x 1 = 10.
  props per event: 10 x (number of markets) x 1.

Resume rule: an output file that already exists is skipped (never overwritten).
"""

import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"
BASE = "https://api.the-odds-api.com/v4"
RESERVE = 20_000

BOOKS = ["pinnacle", "hardrockbet_fl", "draftkings", "fanduel", "betmgm",
         "williamhill_us", "betrivers", "bovada", "betonlineag", "lowvig"]
BOOKS_STR = ",".join(BOOKS)

# NHL season date ranges (start_year: (first_game_approx, last_game_approx))
SEASONS = {
    2022: (date(2022, 10, 7), date(2023, 6, 15)),
    2023: (date(2023, 10, 10), date(2024, 6, 25)),
    2024: (date(2024, 10, 4), date(2025, 6, 25)),
    2025: (date(2025, 10, 4), date(2026, 6, 25)),
}

LINE_MARKETS = "h2h,spreads,totals"
LINE_COST_PER_SNAP = 30   # 10 x 3 markets x 1 region


def _scrub(text):
    t = str(text)
    if KEY:
        t = t.replace(KEY, "<APIKEY-REDACTED>")
    return re.sub(r"(apiKey=)[^&\s'\"]+", r"\1<APIKEY-REDACTED>", t)


def _check_reserve(remaining, next_cost):
    if remaining - next_cost < RESERVE:
        print(f"HALT: remaining {remaining} - next_cost {next_cost} = {remaining - next_cost} < RESERVE {RESERVE}")
        sys.exit(1)


def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def flatten_snapshot(data, requested_utc):
    """One row per outcome. Keeps team names on h2h/spreads, player names on props."""
    rows = []
    snapshot_utc = data.get("timestamp", data.get("previous_timestamp", requested_utc))
    games = data.get("data", [])
    if not isinstance(games, list):
        return rows
    for g in games:
        commence = g.get("commence_time", "")
        # Drop in-play: snapshot_utc >= commence_time
        try:
            if _parse_utc(snapshot_utc) >= _parse_utc(commence):
                continue
        except (ValueError, TypeError):
            pass
        eid = g.get("id", "")
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        for bm in g.get("bookmakers", []):
            book = bm.get("key", "")
            for mkt in bm.get("markets", []):
                mk = mkt.get("key", "")
                for oc in mkt.get("outcomes", []):
                    rows.append({
                        "snapshot_utc": snapshot_utc,
                        "requested_utc": requested_utc,
                        "event_id": eid,
                        "commence_time": commence,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker": book,
                        "market": mk,
                        "outcome_name": oc.get("name", ""),
                        "description": oc.get("description", ""),
                        "point": oc.get("point"),
                        "price": oc.get("price"),
                    })
    return rows


def flatten_event(data, requested_utc):
    """One row per outcome for a single-event response."""
    rows = []
    if not data:
        return rows
    snapshot_utc = data.get("timestamp", data.get("previous_timestamp", requested_utc))
    # Event-level response has the event at top level
    ev = data.get("data", data)
    if not isinstance(ev, dict):
        return rows
    commence = ev.get("commence_time", "")
    try:
        if _parse_utc(snapshot_utc) >= _parse_utc(commence):
            return rows
    except (ValueError, TypeError):
        pass
    eid = ev.get("id", "")
    home = ev.get("home_team", "")
    away = ev.get("away_team", "")
    for bm in ev.get("bookmakers", []):
        book = bm.get("key", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            for oc in mkt.get("outcomes", []):
                rows.append({
                    "snapshot_utc": snapshot_utc,
                    "requested_utc": requested_utc,
                    "event_id": eid,
                    "commence_time": commence,
                    "home_team": home,
                    "away_team": away,
                    "bookmaker": book,
                    "market": mk,
                    "outcome_name": oc.get("name", ""),
                    "description": oc.get("description", ""),
                    "point": oc.get("point"),
                    "price": oc.get("price"),
                })
    return rows


# ─── LINES subcommand ───────────────────────────────────────────────────

def _to_z(dt):
    """Format a UTC datetime as ISO with Z suffix (required by the historical API)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_times_for_date(d):
    """Return the snapshot request timestamps for a game date.
    Always: 22:45Z (covers 7-7:30pm ET games).
    Conditional: 01:45Z next day if any game starts >= 01:30Z (late West Coast).
    We don't know the actual start times here, so we include 22:45Z always
    and 01:45Z always (cheap to skip if no games)."""
    dt = datetime(d.year, d.month, d.day, 22, 45, tzinfo=timezone.utc)
    late = datetime(d.year, d.month, d.day, 1, 45, tzinfo=timezone.utc) + timedelta(days=1)
    return [dt, late]


def _lines_plan(season):
    """Return list of (snapshot_datetime_Z, output_path) for a season."""
    start, end = SEASONS[season]
    plan = []
    out_dir = ROOT / "data" / "odds_archive" / "nhl" / "history" / "lines" / f"season={season}"
    d = start
    while d <= end:
        for snap in _snapshot_times_for_date(d):
            fname = f"snap_{snap.strftime('%Y%m%dT%H%M%SZ')}.parquet"
            plan.append((_to_z(snap), out_dir / fname))
        d += timedelta(days=1)
    return plan


def cmd_lines(args):
    seasons = [int(s) for s in args.season.split(",")]
    all_plans = []
    for s in seasons:
        if s not in SEASONS:
            print(f"HALT: unknown season {s}")
            sys.exit(1)
        all_plans.extend([(s, ts, p) for ts, p in _lines_plan(s)])

    # Skip already-done
    todo = [(s, ts, p) for s, ts, p in all_plans if not p.exists()]
    skip = len(all_plans) - len(todo)
    total_credits = len(todo) * LINE_COST_PER_SNAP

    print(f"LINES plan: {len(all_plans)} snapshots total, {skip} already done, {len(todo)} to pull")
    print(f"  estimated credits: {len(todo)} x {LINE_COST_PER_SNAP} = {total_credits}")
    for s in seasons:
        n = sum(1 for ss, _, _ in todo if ss == s)
        print(f"  season {s}: {n} snapshots to pull")

    if args.dry_run:
        print("--dry-run: stopping")
        return

    if not KEY:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    credits_used = 0
    remaining = int(args.cap) if args.cap else 999999

    for i, (season, ts, path) in enumerate(todo):
        if path.exists():
            continue
        _check_reserve(remaining, LINE_COST_PER_SNAP)

        r = requests.get(f"{BASE}/historical/sports/icehockey_nhl/odds",
                         params={"apiKey": KEY, "markets": LINE_MARKETS,
                                 "bookmakers": BOOKS_STR, "oddsFormat": "american",
                                 "date": ts},
                         timeout=45)
        used = int(r.headers.get("x-requests-last", "0"))
        remaining = int(r.headers.get("x-requests-remaining", "0"))
        credits_used += used

        if r.status_code != 200:
            print(f"  [{i+1}/{len(todo)}] {ts}: HTTP {r.status_code} ({_scrub(r.text[:100])})")
            time.sleep(0.5)
            continue

        data = r.json()
        rows = flatten_snapshot(data, ts)
        if rows:
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(path, index=False)

        n_games = len(set(row["event_id"] for row in rows)) if rows else 0
        print(f"  [{i+1}/{len(todo)}] {ts}: {len(rows)} rows, {n_games} games, "
              f"used={used} rem={remaining}")
        time.sleep(0.5)

    print(f"\nLINES done: {credits_used} credits used, {remaining} remaining")


# ─── THREEWAY subcommand ────────────────────────────────────────────────

def cmd_threeway(args):
    season = int(args.season)
    if season not in SEASONS:
        print(f"HALT: unknown season {season}"); sys.exit(1)
    start, end = SEASONS[season]
    out_base = ROOT / "data" / "odds_archive" / "nhl" / "history" / "threeway" / f"season={season}"

    # Build date list
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)

    print(f"THREEWAY plan: season {season}, {len(dates)} dates")
    print(f"  estimated: ~1,312 events x 10 + {len(dates)} event-list calls")

    if args.dry_run:
        print("--dry-run: stopping"); return
    if not KEY:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    credits_used = 0
    remaining = int(args.cap) if args.cap else 999999
    events_covered = 0

    for di, game_date in enumerate(dates):
        out_path = out_base / f"date={game_date.isoformat()}.parquet"
        if out_path.exists():
            continue

        _check_reserve(remaining, 11)  # 1 for events + 10 for first event

        # Get events for this date
        date_str = f"{game_date.isoformat()}T12:00:00Z"
        r = requests.get(f"{BASE}/historical/sports/icehockey_nhl/events",
                         params={"apiKey": KEY, "date": date_str}, timeout=30)
        used = int(r.headers.get("x-requests-last", "0"))
        remaining = int(r.headers.get("x-requests-remaining", "0"))
        credits_used += used

        if r.status_code != 200:
            print(f"  [{di+1}/{len(dates)}] {game_date}: events HTTP {r.status_code}")
            time.sleep(0.5)
            continue

        resp_data = r.json()
        events = resp_data.get("data", resp_data)
        if not isinstance(events, list):
            events = []

        # Filter to events on this date
        day_events = []
        for e in events:
            ct = e.get("commence_time", "")
            try:
                ct_date = _parse_utc(ct).date()
                if ct_date == game_date or ct_date == game_date + timedelta(days=1):
                    day_events.append(e)
            except (ValueError, TypeError):
                pass

        if not day_events:
            time.sleep(0.3)
            continue

        all_rows = []
        for ei, event in enumerate(day_events):
            eid = event["id"]
            commence = event.get("commence_time", "")
            # Request 10 min before commence (Z format required)
            try:
                req_time = _to_z(_parse_utc(commence) - timedelta(minutes=10))
            except (ValueError, TypeError):
                continue

            _check_reserve(remaining, 10)

            r2 = requests.get(f"{BASE}/historical/sports/icehockey_nhl/events/{eid}/odds",
                              params={"apiKey": KEY, "bookmakers": BOOKS_STR,
                                      "markets": "h2h_3_way", "oddsFormat": "american",
                                      "date": req_time},
                              timeout=30)
            used2 = int(r2.headers.get("x-requests-last", "0"))
            remaining = int(r2.headers.get("x-requests-remaining", "0"))
            credits_used += used2

            if r2.status_code in (200,):
                rows = flatten_event(r2.json(), req_time)
                all_rows.extend(rows)
            time.sleep(0.5)

        if all_rows:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(all_rows).to_parquet(out_path, index=False)
            events_covered += len(day_events)

        print(f"  [{di+1}/{len(dates)}] {game_date}: {len(day_events)} events, "
              f"{len(all_rows)} rows, rem={remaining}")

    print(f"\nTHREEWAY done: {events_covered} events, {credits_used} credits, {remaining} remaining")


# ─── PROPS subcommand ────────────────────────────────────────────────────

PROP_MARKETS = "player_points,player_assists,player_shots_on_goal,player_goal_scorer_anytime"


def cmd_props(args):
    season = int(args.season)
    if season not in SEASONS:
        print(f"HALT: unknown season {season}"); sys.exit(1)
    start, end = SEASONS[season]
    out_base = ROOT / "data" / "odds_archive" / "nhl" / "history" / "props" / f"season={season}"

    n_markets = len(PROP_MARKETS.split(","))
    cost_per_event = 10 * n_markets  # historical: 10 x markets x 1 region

    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)

    print(f"PROPS plan: season {season}, {len(dates)} dates")
    print(f"  markets: {PROP_MARKETS}")
    print(f"  cost per event: 10 x {n_markets} = {cost_per_event}")
    print(f"  estimated: ~1,312 events x {cost_per_event} + {len(dates)} event-list calls")

    if args.dry_run:
        print("--dry-run: stopping"); return
    if not KEY:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    credits_used = 0
    remaining = int(args.cap) if args.cap else 999999
    events_covered = 0

    for di, game_date in enumerate(dates):
        month = game_date.month
        out_path = out_base / f"month={month:02d}" / f"date={game_date.isoformat()}.parquet"
        if out_path.exists():
            continue

        _check_reserve(remaining, cost_per_event + 1)

        date_str = f"{game_date.isoformat()}T12:00:00Z"
        r = requests.get(f"{BASE}/historical/sports/icehockey_nhl/events",
                         params={"apiKey": KEY, "date": date_str}, timeout=30)
        used = int(r.headers.get("x-requests-last", "0"))
        remaining = int(r.headers.get("x-requests-remaining", "0"))
        credits_used += used

        if r.status_code != 200:
            print(f"  [{di+1}/{len(dates)}] {game_date}: events HTTP {r.status_code}")
            time.sleep(0.5)
            continue

        resp_data = r.json()
        events = resp_data.get("data", resp_data)
        if not isinstance(events, list):
            events = []

        day_events = []
        for e in events:
            ct = e.get("commence_time", "")
            try:
                ct_date = _parse_utc(ct).date()
                if ct_date == game_date or ct_date == game_date + timedelta(days=1):
                    day_events.append(e)
            except (ValueError, TypeError):
                pass

        if not day_events:
            time.sleep(0.3)
            continue

        all_rows = []
        for event in day_events:
            eid = event["id"]
            commence = event.get("commence_time", "")
            try:
                req_time = _to_z(_parse_utc(commence) - timedelta(minutes=10))
            except (ValueError, TypeError):
                continue

            _check_reserve(remaining, cost_per_event)

            r2 = requests.get(f"{BASE}/historical/sports/icehockey_nhl/events/{eid}/odds",
                              params={"apiKey": KEY, "bookmakers": BOOKS_STR,
                                      "markets": PROP_MARKETS, "oddsFormat": "american",
                                      "date": req_time},
                              timeout=30)
            used2 = int(r2.headers.get("x-requests-last", "0"))
            remaining = int(r2.headers.get("x-requests-remaining", "0"))
            credits_used += used2

            if r2.status_code == 200:
                rows = flatten_event(r2.json(), req_time)
                all_rows.extend(rows)
            time.sleep(0.5)

        if all_rows:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(all_rows).to_parquet(out_path, index=False)
            events_covered += len(day_events)

        print(f"  [{di+1}/{len(dates)}] {game_date}: {len(day_events)} events, "
              f"{len(all_rows)} rows, rem={remaining}")

    print(f"\nPROPS done: {events_covered} events, {credits_used} credits, {remaining} remaining")


def main():
    print(f"key fingerprint {KEY_FP}")
    ap = argparse.ArgumentParser(description="Pull NHL historical odds")
    ap.add_argument("cmd", choices=["lines", "threeway", "props"])
    ap.add_argument("--season", required=True, help="start year(s), comma-separated for lines")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cap", type=int, default=None, help="credit cap for this run")
    args = ap.parse_args()

    if not KEY and not args.dry_run:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    if args.cmd == "lines":
        cmd_lines(args)
    elif args.cmd == "threeway":
        cmd_threeway(args)
    elif args.cmd == "props":
        cmd_props(args)


if __name__ == "__main__":
    main()
