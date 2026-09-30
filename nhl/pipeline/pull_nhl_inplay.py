#!/usr/bin/env python3
"""
E-WO1 Item 2: pull historical in-play NHL odds for 80 nights of 2023-24.
Reuses the WO2 schema but KEEPS in-play events (WO2 drops them).
"""
import gzip, hashlib, json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8]
BASE = "https://api.the-odds-api.com/v4"
FLOOR = 1600
OUT_DIR = ROOT / "data" / "odds_archive" / "nhl" / "history" / "inplay" / "season=2023"
BOX_DIR = ROOT / "nhl" / "cache"
GAMES_PER_SEASON = 1312
SEED = 20260930
N_NIGHTS = 80
N_SNAPS = 10  # T0+2:00 to T0+2:45 every 5 min


def flatten_all(data, requested_utc):
    """One row per outcome — KEEPS in-play events (unlike WO2's flatten_snapshot)."""
    rows = []
    snapshot_utc = data.get("timestamp", data.get("previous_timestamp", requested_utc))
    games = data.get("data", [])
    if not isinstance(games, list):
        return rows, snapshot_utc
    for g in games:
        eid = g.get("id", "")
        commence = g.get("commence_time", "")
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
    return rows, snapshot_utc


def select_nights():
    """Select 80 dates with >= 4 evening-slate games from 2023-24 boxscores."""
    game_dates = {}
    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"202302{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists():
            continue
        with open(bp) as f:
            d = json.load(f)
        date = d.get("gameDate", "")
        start = d.get("startTimeUTC", d.get("gameDate", ""))
        game_dates.setdefault(date, []).append(start)

    # Find dates with >= 4 games
    eligible = []
    for date, starts in sorted(game_dates.items()):
        if len(starts) >= 4:
            # Modal commence time = most common hour
            hours = [s[11:13] if len(s) > 11 else "00" for s in starts]
            modal_hour = max(set(hours), key=hours.count)
            eligible.append((date, int(modal_hour)))

    rng = np.random.RandomState(SEED)
    idx = sorted(rng.choice(len(eligible), min(N_NIGHTS, len(eligible)), replace=False))
    return [eligible[i] for i in idx]


def main():
    print(f"key fingerprint: {KEY_FP}")
    if not KEY:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    nights = select_nights()
    print(f"Selected {len(nights)} nights from 2023-24")
    for d, h in nights[:5]:
        print(f"  {d} modal_hour={h}")
    print(f"  ... ({len(nights)} total)")

    # Runtime pre-check
    n_calls = len(nights) * N_SNAPS
    est_sec = n_calls * 1.5  # ~1s request + 0.5s sleep
    print(f"\nRuntime estimate: {n_calls} calls x 1.5s = {est_sec:.0f}s = {est_sec/60:.0f} min")
    print(f"Credits estimate: {n_calls} x 20 = {n_calls * 20}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_calls = 0
    total_credits = 0
    remaining = 99999

    for ni, (date, modal_hour) in enumerate(nights):
        # T0 = modal commence time of evening slate
        # Derive from the date and modal hour
        t0 = datetime.strptime(f"{date}T{modal_hour:02d}:00:00Z", "%Y-%m-%dT%H:%M:%SZ")

        for si in range(N_SNAPS):
            offset_min = 120 + si * 5  # T0 + 2:00 to T0 + 2:45
            req_time = t0 + timedelta(minutes=offset_min)
            req_iso = req_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Output paths
            pq_path = OUT_DIR / f"snap_{req_time.strftime('%Y%m%dT%H%M%SZ')}.parquet"
            gz_path = OUT_DIR / f"snap_{req_time.strftime('%Y%m%dT%H%M%SZ')}.json.gz"

            if pq_path.exists():
                continue  # Resume-safe

            # Floor check
            if remaining < FLOOR + 20:
                print(f"\nFLOOR reached: remaining={remaining} < {FLOOR + 20}. Stopping.")
                print(f"Total: {total_calls} calls, {total_credits} credits used")
                return

            r = requests.get(f"{BASE}/historical/sports/icehockey_nhl/odds",
                             params={"apiKey": KEY, "regions": "us", "markets": "h2h,totals",
                                     "oddsFormat": "american", "date": req_iso},
                             timeout=45)
            used = int(r.headers.get("x-requests-last", "0"))
            remaining = int(r.headers.get("x-requests-remaining", "0"))
            total_calls += 1
            total_credits += used

            if total_calls == 1 and used != 20:
                print(f"STOP: first call cost {used}, expected 20. Aborting.")
                return

            if r.status_code != 200:
                print(f"  HTTP {r.status_code} at {req_iso}")
                time.sleep(0.5)
                continue

            data = r.json()
            rows, snap_utc = flatten_all(data, req_iso)

            # Save parquet
            if rows:
                pd.DataFrame(rows).to_parquet(pq_path, index=False)

            # Save raw JSON gz
            with gzip.open(gz_path, "wt") as f:
                json.dump(data, f)

            time.sleep(0.5)

        if (ni + 1) % 10 == 0:
            print(f"  [{ni+1}/{len(nights)}] calls={total_calls} credits={total_credits} remaining={remaining}")

    print(f"\nDone: {total_calls} calls, {total_credits} credits, remaining={remaining}")
    print(f"Nights: {len(nights)}, snapshots saved: {len(list(OUT_DIR.glob('*.parquet')))}")


if __name__ == "__main__":
    main()
