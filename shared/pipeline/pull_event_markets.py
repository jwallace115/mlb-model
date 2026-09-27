#!/usr/bin/env python3
"""
MULTI-BOOK EVENT MARKETS — every market the API has for a game.

Generalises the NFL props puller to any sport. Discovers what markets each book
offers, then pulls odds for the union of Hard Rock + Pinnacle markets (minus the
three featured markets the tape already captures).

Cost model: each market requested = 1 credit per region-equivalent per event.
10 books = 1 region-equivalent, so cost = events x markets.

Usage:
  python3 shared/pipeline/pull_event_markets.py --sport icehockey_nhl --window-hours 24 --tag open
  python3 shared/pipeline/pull_event_markets.py --sport americanfootball_nfl --window-hours 168 --tag open --exclude-prefix player_
  python3 shared/pipeline/pull_event_markets.py --sport icehockey_nhl --window-hours 24 --tag open --dry-run
"""

import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"
BASE = "https://api.the-odds-api.com/v4"

# Same 10-book list as the tape (1 region-equivalent).
BOOKS = ["hardrockbet_fl", "pinnacle", "draftkings", "fanduel", "betmgm",
         "betonlineag", "bovada", "betrivers", "williamhill_us", "lowvig"]

# Featured markets the tape already captures — exclude from event-market pulls.
TAPE_MARKETS = {"h2h", "spreads", "totals"}

HALT_THRESHOLD = 3000

# Import folder/season helpers from the tape module.
from shared.pipeline.multi_book_open_capture import FOLDER_MAP, _folder, _season


def _scrub(text):
    t = str(text)
    if KEY:
        t = t.replace(KEY, "<APIKEY-REDACTED>")
    return re.sub(r"(apiKey=)[^&\s'\"]+", r"\1<APIKEY-REDACTED>", t)


def _utc(ts):
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_events(sport):
    """Get upcoming events (free, no credits)."""
    r = requests.get(f"{BASE}/sports/{sport}/events",
                     params={"apiKey": KEY}, timeout=30)
    remaining = int(r.headers.get("x-requests-remaining", 0))
    print(f"events: HTTP {r.status_code}  x-requests-remaining={remaining}")
    return (r.json() if r.status_code == 200 else []), remaining


def filter_window(events, now, window_hours):
    """Keep only events that start within [now, now + window_hours] and haven't started."""
    window_end = now + timedelta(hours=window_hours)
    out = []
    for e in events:
        ct = e.get("commence_time", "")
        try:
            ct_dt = _utc(ct)
        except (ValueError, AttributeError):
            continue
        if now < ct_dt <= window_end:
            out.append(e)
    return out


def discover_markets(sport, event_id):
    """Call GET /v4/sports/{sport}/events/{id}/markets with all books to discover
    available market keys. Returns {book: [market_keys]} and the response headers.
    Cost: 1 credit per call."""
    r = requests.get(
        f"{BASE}/sports/{sport}/events/{event_id}/markets",
        params={"apiKey": KEY, "bookmakers": ",".join(BOOKS)},
        timeout=30)
    used = r.headers.get("x-requests-last", "0")
    rem = r.headers.get("x-requests-remaining", "?")
    print(f"  discovery {event_id[:12]}...: HTTP {r.status_code}  "
          f"x-requests-last={used}  remaining={rem}")
    if r.status_code != 200:
        print(f"    ERROR: {_scrub(r.text[:200])}")
        return {}, used, rem
    data = r.json()
    book_markets = {}
    for bm in data.get("bookmakers", []):
        book = bm.get("key", "")
        keys = [m.get("key", "") for m in bm.get("markets", [])]
        book_markets[book] = keys
    return book_markets, used, rem


def compute_market_set(book_markets, exclude_prefixes):
    """Union of Hard Rock + Pinnacle market keys, minus tape markets and excluded prefixes."""
    hr = set(book_markets.get("hardrockbet_fl", []))
    pin = set(book_markets.get("pinnacle", []))
    union = hr | pin
    # Remove tape markets
    union -= TAPE_MARKETS
    # Remove excluded prefixes
    if exclude_prefixes:
        union = {m for m in union
                 if not any(m.startswith(p) for p in exclude_prefixes)}
    return sorted(union)


def pull_event_odds(sport, event_id, markets):
    """Pull odds for specific markets on one event. Returns (data_dict, used, rem)."""
    r = requests.get(
        f"{BASE}/sports/{sport}/events/{event_id}/odds",
        params={"apiKey": KEY, "bookmakers": ",".join(BOOKS),
                "markets": ",".join(markets), "oddsFormat": "american"},
        timeout=30)
    used = r.headers.get("x-requests-last", "0")
    rem = r.headers.get("x-requests-remaining", "?")
    if r.status_code == 422:
        return None, used, rem
    if r.status_code != 200:
        print(f"    ERROR: {_scrub(r.text[:200])}")
        return None, used, rem
    return r.json(), used, rem


def flatten_event(data, sport, snap_iso, tag):
    """Flatten one event's odds response into rows."""
    rows = []
    if not data:
        return rows
    eid = data.get("id", "")
    commence = data.get("commence_time", "")
    home = data.get("home_team", "")
    away = data.get("away_team", "")
    for bm in data.get("bookmakers", []):
        book = bm.get("key", "")
        lu = bm.get("last_update", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            for oc in mkt.get("outcomes", []):
                rows.append({
                    "snapshot_utc": snap_iso,
                    "sport": sport,
                    "event_id": eid,
                    "commence_time": commence,
                    "home_team": home,
                    "away_team": away,
                    "bookmaker": book,
                    "book_last_update": lu,
                    "market": mk,
                    "outcome_name": oc.get("name", ""),
                    "description": oc.get("description", ""),
                    "point": oc.get("point"),
                    "price": oc.get("price"),
                    "tag": tag,
                })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Pull event-level markets for any sport")
    parser.add_argument("--sport", required=True, help="API sport key (e.g. icehockey_nhl)")
    parser.add_argument("--window-hours", type=int, required=True)
    parser.add_argument("--tag", choices=["open", "mid", "close"], required=True)
    parser.add_argument("--floor", type=int, default=HALT_THRESHOLD,
                        help=f"credit floor (default {HALT_THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--markets", nargs="*", default=None,
                        help="Explicit market list; default: DISCOVERED from Hard Rock + Pinnacle")
    parser.add_argument("--exclude-prefix", action="append", default=[],
                        help="Exclude markets starting with this prefix (repeatable)")
    args = parser.parse_args()

    print(f"key fingerprint {KEY_FP}")
    if not KEY:
        print("HALT: ODDS_API_KEY not set")
        sys.exit(1)

    if args.sport not in FOLDER_MAP:
        print(f"HALT: unknown sport {args.sport} (add to FOLDER_MAP)")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    snap_iso = now.isoformat()

    # ── Get events (free) ──
    all_events, remaining = get_events(args.sport)
    window = filter_window(all_events, now, args.window_hours)

    print(f"events in window (next {args.window_hours}h): {len(window)}")
    for e in window:
        print(f"  {e.get('away_team', '?')[:20]:<20s} @ {e.get('home_team', '?')[:20]:<20s}  {e.get('commence_time', '?')}")

    if not window:
        print("No events in window")
        sys.exit(0)

    # ── Discovery: learn what markets each book offers ──
    if args.markets is not None:
        market_set = args.markets
        print(f"using explicit markets: {market_set}")
    else:
        print(f"\n--- DISCOVERY (first event) ---")
        first = window[0]
        book_markets, disc_used, disc_rem = discover_markets(args.sport, first["id"])
        remaining = int(disc_rem) if disc_rem != "?" else remaining

        print(f"\nMarkets per book:")
        for book in BOOKS:
            keys = book_markets.get(book, [])
            print(f"  {book:<20s}: {', '.join(sorted(keys)) if keys else '(none)'}")

        market_set = compute_market_set(book_markets, args.exclude_prefix)
        print(f"\nDiscovered market set ({len(market_set)}): {', '.join(market_set)}")
        if not market_set:
            print("HALT: no markets discovered (after exclusions)")
            sys.exit(0)

    # ── Cost pre-check ──
    n_markets = len(market_set)
    cost_per_event = n_markets  # 1 credit per market per region-equivalent
    total_cost = len(window) * cost_per_event
    after = remaining - total_cost
    print(f"\ncost pre-check: {len(window)} events x {n_markets} markets = {total_cost} credits")
    print(f"  remaining now: {remaining}  after: {after}  floor: {args.floor}")
    if after < args.floor:
        print(f"HALT: remaining {remaining} - cost {total_cost} = {after} < {args.floor}")
        sys.exit(1)

    if args.dry_run:
        print("--dry-run: stopping before paid calls")
        sys.exit(0)

    # ── Pull odds for each event ──
    all_rows = []
    credits_used = 0

    for i, event in enumerate(window):
        eid = event["id"]
        commence = event.get("commence_time", "")

        # Skip already-started events
        try:
            if _utc(commence) <= now:
                print(f"  [{i+1}/{len(window)}] {eid[:12]}... SKIPPED (already started)")
                continue
        except (ValueError, AttributeError):
            pass

        data, used, rem = pull_event_odds(args.sport, eid, market_set)
        credits_used += int(used)
        print(f"  [{i+1}/{len(window)}] {event.get('away_team','?')[:12]}@{event.get('home_team','?')[:12]}: "
              f"HTTP {'200' if data else 'err'}  x-requests-last={used}  remaining={rem}")

        if data:
            rows = flatten_event(data, args.sport, snap_iso, args.tag)
            all_rows.extend(rows)

        time.sleep(0.5)

    # ── Save ──
    if all_rows:
        df = pd.DataFrame(all_rows)
        folder = _folder(args.sport)
        season = _season(args.sport, now)
        out_dir = ROOT / "data" / "odds_archive" / folder / "event_markets" / f"season={season}"
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"snap_{now.strftime('%Y%m%dT%H%M%SZ')}.parquet"
        path = out_dir / fname
        df.to_parquet(path, index=False)
        print(f"\nSaved {len(df)} rows -> {path}")

        # Summary: rows by book x market
        print("\nRows by bookmaker x market:")
        pivot = df.groupby(["bookmaker", "market"]).size().unstack(fill_value=0)
        print(pivot.to_string())
    else:
        print("\nNo rows to save")

    print(f"\ncredits used: {credits_used}  tag: {args.tag}  events: {len(window)}")


if __name__ == "__main__":
    main()
