#!/usr/bin/env python3
"""
Pull Hard Rock (hardrockbet_fl) NFL player props via the Odds API.

Canonical writer for Hard Rock prop captures. Runs on the VM only.
Cost: 15 credits per event + 1 per run (events endpoint is free).

Usage:
  python3 nfl/pipeline/pull_hardrock_props.py --window-hours 168 --tag open
  python3 nfl/pipeline/pull_hardrock_props.py --window-hours 12  --tag close
  python3 nfl/pipeline/pull_hardrock_props.py --window-hours 12  --tag close --dry-run
"""

import argparse, hashlib, json, os, sys, time
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

MARKETS = (
    "player_pass_yds,player_pass_tds,player_pass_attempts,"
    "player_pass_completions,player_pass_interceptions,"
    "player_rush_yds,player_rush_attempts,"
    "player_reception_yds,player_receptions,player_anytime_td"
)

ARCHIVE_ROOT = ROOT / "data" / "odds_archive" / "nfl"
PROPS_DIR = ARCHIVE_ROOT / "props"
HALT_THRESHOLD = 3000


def american_to_implied(odds):
    if odds is None:
        return None
    if odds > 0:
        return round(100 / (odds + 100), 4)
    return round(abs(odds) / (abs(odds) + 100), 4)


def normalize(data, eid, game_date, home, away, commence, batch_label, ts,
              snapshot_tag):
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
            for (desc, point), prices in player_lines.items():
                rows.append({
                    "sport": "nfl",
                    "event_id": eid,
                    "game_date": game_date,
                    "commence_time": commence,
                    "home_team": home,
                    "away_team": away,
                    "bookmaker": book,
                    "market_key": mk,
                    "last_update": lu_m,
                    "player_name": desc if "player_" in mk else None,
                    "line": point,
                    "over_price": prices.get("over_price"),
                    "under_price": prices.get("under_price"),
                    "implied_over": american_to_implied(prices.get("over_price")),
                    "implied_under": american_to_implied(prices.get("under_price")),
                    "pull_batch": batch_label,
                    "pull_timestamp": ts,
                    "snapshot_tag": snapshot_tag,
                })
    return rows


def save_partition(rows, season, month):
    """Append rows to the season/month partition. Never overwrites."""
    if not rows:
        return None
    part = PROPS_DIR / f"season={season}" / f"month={month:02d}"
    part.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    path = part / f"data_{season}_{month:02d}.parquet"
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(path, index=False)
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Pull Hard Rock NFL player props")
    parser.add_argument("--window-hours", type=int, required=True,
                        help="Select events with commence_time within N hours")
    parser.add_argument("--tag", choices=["open", "mid", "close"], required=True,
                        help="Snapshot tag written to snapshot_tag column")
    parser.add_argument("--dry-run", action="store_true",
                        help="List events and cost without pulling")
    args = parser.parse_args()

    print(f"key fingerprint {KEY_FP}")
    if not KEY:
        print("HALT: ODDS_API_KEY not set")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    window_end = now + timedelta(hours=args.window_hours)

    # ── Get events (free, no credits) ──
    r = requests.get(f"{BASE}/sports/americanfootball_nfl/events",
                     params={"apiKey": KEY}, timeout=30)
    remaining = int(r.headers.get("x-requests-remaining", 0))
    print(f"events: HTTP {r.status_code}  x-requests-remaining={remaining}")

    events = r.json() if r.status_code == 200 else []
    window = []
    for e in events:
        ct = e.get("commence_time", "")
        try:
            ct_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if now <= ct_dt <= window_end:
            window.append(e)

    print(f"events in window (next {args.window_hours}h): {len(window)}")
    for e in window:
        print(f"  {e['away_team'][:20]:<20s} @ {e['home_team'][:20]:<20s}  {e['commence_time']}")

    if not window:
        print("No events in window")
        sys.exit(0)

    # ── Cost pre-check ──
    cost = len(window) * 15 + 1
    after = remaining - cost
    print(f"cost pre-check: {len(window)} events x 15 + 1 = {cost} credits")
    print(f"  remaining after: {after} (threshold: {HALT_THRESHOLD})")
    if after < HALT_THRESHOLD:
        print(f"HALT: remaining {remaining} - cost {cost} = {after} < {HALT_THRESHOLD}")
        sys.exit(1)

    if args.dry_run:
        print("--dry-run: stopping before paid calls")
        sys.exit(0)

    # ── Pull props ──
    batch_label = f"hardrock_{args.tag}"
    all_rows = []
    credits_used = 0

    for i, event in enumerate(window):
        eid = event["id"]
        commence = event["commence_time"]
        home = event["home_team"]
        away = event["away_team"]
        game_date = commence[:10]

        resp = requests.get(
            f"{BASE}/sports/americanfootball_nfl/events/{eid}/odds",
            params={"apiKey": KEY, "bookmakers": "hardrockbet_fl",
                    "markets": MARKETS, "oddsFormat": "american"},
            timeout=30)

        used = resp.headers.get("x-requests-last", "0")
        rem = resp.headers.get("x-requests-remaining", "?")
        credits_used += int(used)
        print(f"  [{i+1}/{len(window)}] {away[:12]}@{home[:12]}: "
              f"HTTP {resp.status_code}  used={used}  remaining={rem}")

        if resp.status_code == 422:
            time.sleep(0.2)
            continue
        if resp.status_code != 200:
            print(f"    ERROR: {resp.text[:120]}")
            time.sleep(0.2)
            continue

        data = resp.json()
        rows = normalize(data, eid, game_date, home, away, commence,
                         batch_label, ts, args.tag)
        all_rows.extend(rows)
        time.sleep(0.2)

    # ── In-play filter (1c): drop any row where pull_timestamp >= commence_time ──
    pre_filter = len(all_rows)
    all_rows = [r for r in all_rows if r["pull_timestamp"] < r["commence_time"]]
    if len(all_rows) < pre_filter:
        print(f"  in-play filter: dropped {pre_filter - len(all_rows)} rows "
              f"where pull_timestamp >= commence_time")

    # ── Save ──
    if all_rows:
        season = int(game_date[:4])
        month = int(game_date[5:7])
        path = save_partition(all_rows, season, month)
        print(f"\nSaved {len(all_rows)} rows to {path}")
    else:
        print("\nNo rows to save")

    print(f"credits used: {credits_used}  tag: {args.tag}  events: {len(window)}")


if __name__ == "__main__":
    main()
