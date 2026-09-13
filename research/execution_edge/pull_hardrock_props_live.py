#!/usr/bin/env python3
"""
One-off: pull Hard Rock NFL player props for today's games via the Odds API.

Uses bookmakers=hardrockbet_fl (NOT regions=us; Hard Rock is in us2).
Reuses the 17-column schema from run_multi_sport_backfill.py.
"""

import hashlib, json, os, sys, time
from datetime import datetime, timezone
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

MARKETS_A = "player_pass_yds,player_pass_tds,player_pass_attempts,player_pass_completions,player_pass_interceptions,player_rush_yds,player_rush_attempts,player_reception_yds,player_receptions,player_anytime_td"
MARKETS_B = "player_pass_yds_alternate,player_rush_yds_alternate,player_reception_yds_alternate,player_receptions_alternate,player_rush_attempts_alternate"

COMMENCE_MIN = "2026-09-13T16:00:00Z"
COMMENCE_MAX = "2026-09-15T04:00:00Z"

ARCHIVE_ROOT = ROOT / "data" / "odds_archive" / "nfl"
PROPS_DIR = ARCHIVE_ROOT / "props"


def american_to_implied(odds):
    if odds is None:
        return None
    if odds > 0:
        return round(100 / (odds + 100), 4)
    return round(abs(odds) / (abs(odds) + 100), 4)


def normalize(data, eid, game_date, home, away, commence, batch_label, ts):
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
                    player_lines[key].setdefault("over_name", name)
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
                })
    return rows


def save_partition(rows, base_dir, season, month):
    if not rows:
        return
    part = base_dir / f"season={season}" / f"month={month:02d}"
    part.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    path = part / f"data_{season}_{month:02d}.parquet"
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(
            subset=["event_id", "bookmaker", "market_key", "player_name", "line"],
            keep="last")
    df.to_parquet(path, index=False)
    return path


def main():
    print(f"key fingerprint {KEY_FP}")
    if not KEY:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    snap_tag = now.strftime("%Y%m%dT%H%MZ")

    # ── Get events ──
    r = requests.get(f"{BASE}/sports/americanfootball_nfl/events",
                     params={"apiKey": KEY}, timeout=30)
    print(f"events: HTTP {r.status_code}  (free, no credits)")
    events = r.json()

    # Filter to today's window
    today = []
    for e in events:
        ct = e.get("commence_time", "")
        if COMMENCE_MIN <= ct <= COMMENCE_MAX:
            today.append(e)
    print(f"events in window: {len(today)}")
    for e in today:
        print(f"  {e['away_team'][:15]:<15s} @ {e['home_team'][:15]:<15s}  {e['commence_time']}")

    if not today:
        print("No events in window"); sys.exit(0)

    # ── Check credits before starting ──
    test_r = requests.get(f"{BASE}/sports/americanfootball_nfl/odds",
                          params={"apiKey": KEY, "bookmakers": "pinnacle",
                                  "markets": "h2h", "oddsFormat": "american"},
                          timeout=30)
    remaining = int(test_r.headers.get("x-requests-remaining", 0))
    print(f"pre-check: x-requests-remaining = {remaining}")
    if remaining < 3000:
        print(f"HALT: remaining {remaining} < 3000"); sys.exit(1)

    # ── Pull props for each event ──
    raw_dir = ARCHIVE_ROOT / "props" / "raw_live" / f"hardrock_{snap_tag}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    dropped_markets = set()
    credits_used_total = 0

    for i, event in enumerate(today):
        eid = event["id"]
        commence = event["commence_time"]
        home = event["home_team"]
        away = event["away_team"]
        game_date = commence[:10]

        print(f"\n[{i+1}/{len(today)}] {away} @ {home} ({eid[:12]}...)")

        resp = requests.get(
            f"{BASE}/sports/americanfootball_nfl/events/{eid}/odds",
            params={"apiKey": KEY, "bookmakers": "hardrockbet_fl",
                    "markets": MARKETS_A, "oddsFormat": "american"},
            timeout=30)

        used = resp.headers.get("x-requests-last", "?")
        remaining = resp.headers.get("x-requests-remaining", "?")
        credits_used_total += int(used) if used != "?" else 0
        print(f"  batch_a: HTTP {resp.status_code}  used={used}  remaining={remaining}")

        if resp.status_code == 422:
            print(f"  422 — Hard Rock may not offer props for this event")
            (raw_dir / f"{eid}.json").write_text(json.dumps({"status": 422, "batch": "a"}))
            time.sleep(0.2)
            continue
        elif resp.status_code != 200:
            print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
            time.sleep(0.2)
            continue

        data = resp.json()
        (raw_dir / f"{eid}.json").write_text(json.dumps(data, indent=2))

        # Check which markets were returned vs requested
        returned_markets = set()
        for bm in data.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                returned_markets.add(mkt.get("key", ""))
        requested = set(MARKETS_A.split(","))
        missing = requested - returned_markets
        if missing:
            dropped_markets.update(missing)
            print(f"  markets not returned: {missing}")

        rows = normalize(data, eid, game_date, home, away, commence,
                         "live_hardrock", ts)
        all_rows.extend(rows)
        print(f"  {len(rows)} prop lines")

        time.sleep(0.2)

    print(f"\n=== Batch A complete: {len(all_rows)} rows, {credits_used_total} credits ===")

    # ── Optional batch B (alt lines) if credits > 10,000 ──
    remaining_now = int(remaining) if remaining != "?" else 0
    if remaining_now > 10000:
        print(f"\nremaining {remaining_now} > 10,000 — running alt-lines batch B")
        for i, event in enumerate(today):
            eid = event["id"]
            commence = event["commence_time"]
            home = event["home_team"]
            away = event["away_team"]
            game_date = commence[:10]

            resp = requests.get(
                f"{BASE}/sports/americanfootball_nfl/events/{eid}/odds",
                params={"apiKey": KEY, "bookmakers": "hardrockbet_fl",
                        "markets": MARKETS_B, "oddsFormat": "american"},
                timeout=30)

            used = resp.headers.get("x-requests-last", "?")
            remaining = resp.headers.get("x-requests-remaining", "?")
            credits_used_total += int(used) if used != "?" else 0

            if resp.status_code == 200:
                data = resp.json()
                # Append to existing raw JSON
                raw_path = raw_dir / f"{eid}.json"
                if raw_path.exists():
                    existing = json.loads(raw_path.read_text())
                    if isinstance(existing, dict) and "bookmakers" in existing:
                        for bm in data.get("bookmakers", []):
                            existing["bookmakers"].append(bm)
                        raw_path.write_text(json.dumps(existing, indent=2))
                    else:
                        (raw_dir / f"{eid}_alt.json").write_text(json.dumps(data, indent=2))
                else:
                    (raw_dir / f"{eid}_alt.json").write_text(json.dumps(data, indent=2))

                rows = normalize(data, eid, game_date, home, away, commence,
                                 "live_hardrock_alt", ts)
                all_rows.extend(rows)
                print(f"  [{i+1}] alt: {len(rows)} lines  remaining={remaining}")
            elif resp.status_code == 422:
                print(f"  [{i+1}] alt: 422 (not offered)")
            else:
                print(f"  [{i+1}] alt: HTTP {resp.status_code}")

            time.sleep(0.2)

        print(f"\n=== Batch B complete: total {len(all_rows)} rows, {credits_used_total} credits ===")
    else:
        print(f"\nremaining {remaining_now} <= 10,000 — skipping alt-lines batch B")

    # ── Save to partition ──
    if all_rows:
        path = save_partition(all_rows, PROPS_DIR, 2026, 9)
        print(f"\nSaved to {path}  ({len(all_rows)} rows)")
    else:
        print("\nNo rows to save")

    # ── Print selected players ──
    if all_rows:
        df = pd.DataFrame(all_rows)
        targets = ["Emeka Egbuka", "Chase Brown", "Trey McBride",
                    "Jahmyr Gibbs", "Bijan Robinson",
                    "Colston Loveland", "Kenneth Gainwell"]
        print(f"\n{'='*80}")
        print("SELECTED PLAYER PROPS (Hard Rock)")
        print(f"{'='*80}")
        for name in targets:
            pf = df[df["player_name"] == name]
            if pf.empty:
                print(f"\n  {name}: NOT FOUND")
                continue
            game = pf.iloc[0]
            print(f"\n  {name}  ({game['away_team']} @ {game['home_team']})")
            for _, row in pf.sort_values("market_key").iterrows():
                o = f"{int(row['over_price']):+d}" if pd.notna(row['over_price']) else "—"
                u = f"{int(row['under_price']):+d}" if pd.notna(row['under_price']) else "—"
                line = f"{row['line']}" if pd.notna(row['line']) else "—"
                print(f"    {row['market_key']:<35s}  {line:>6s}  O {o:>5s}  U {u:>5s}")

    print(f"\nDONE. Total credits used: {credits_used_total}  remaining: {remaining}")
    if dropped_markets:
        print(f"Markets not returned by HR: {sorted(dropped_markets)}")


if __name__ == "__main__":
    main()
