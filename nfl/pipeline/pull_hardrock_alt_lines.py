#!/usr/bin/env python3
"""One-off, on-demand pull of Hard Rock ALTERNATE lines for ONE NFL game (same-game parlay cards).

Not a scheduled capture and not part of the props tape: it writes one parquet to
`_cowork_patches/alt_lines_now.parquet` (gitignored) for the reader to look at.

Cost (Odds API, live): 1 credit per market RETURNED per region-equivalent; one book = 1 region-eq.
12 alternate markets requested -> at most 12 credits. /events is free. Refuses to continue if the
first response reports fewer than 3,000 credits remaining. Runtime: 2-14 HTTP calls, < 30 s.

Usage (from the repo root, or piped over ssh to the VM which holds the paid key):
    python3 nfl/pipeline/pull_hardrock_alt_lines.py --teams "Colts,Chiefs"
    ssh root@VM 'cd /root/mlb-model && venv/bin/python3 - --teams "Colts,Chiefs"' < nfl/pipeline/pull_hardrock_alt_lines.py
"""
import argparse, hashlib, os, sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path.cwd()
load_dotenv(ROOT / ".env", override=True)
KEY = os.getenv("ODDS_API_KEY", "")
BASE = "https://api.the-odds-api.com/v4"
HALT_THRESHOLD = 3000
ALT_MARKETS = [
    "alternate_spreads", "alternate_totals", "alternate_team_totals",
    "player_pass_yds_alternate", "player_pass_attempts_alternate", "player_pass_completions_alternate",
    "player_pass_tds_alternate", "player_rush_yds_alternate", "player_rush_attempts_alternate",
    "player_reception_yds_alternate", "player_receptions_alternate", "team_totals",
]


def fetch(eid, markets):
    r = requests.get(f"{BASE}/sports/americanfootball_nfl/events/{eid}/odds",
                     params={"apiKey": KEY, "bookmakers": "hardrockbet_fl",
                             "markets": ",".join(markets), "oddsFormat": "american"}, timeout=30)
    return r, int(r.headers.get("x-requests-last", "0") or 0), r.headers.get("x-requests-remaining", "?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", required=True, help='two name fragments, e.g. "Colts,Chiefs"')
    a = ap.parse_args()
    if not KEY:
        sys.exit("HALT: ODDS_API_KEY not set")
    print(f"key fingerprint {hashlib.sha256(KEY.strip().encode()).hexdigest()[:8]}")
    frags = [t.strip().lower() for t in a.teams.split(",")]
    ev = requests.get(f"{BASE}/sports/americanfootball_nfl/events", params={"apiKey": KEY}, timeout=30).json()
    hit = [e for e in ev if all(f in (e["home_team"] + " " + e["away_team"]).lower() for f in frags)]
    if len(hit) != 1:
        sys.exit(f"HALT: {len(hit)} events match {frags}")
    e = hit[0]
    now = datetime.now(timezone.utc)
    if datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) <= now:
        sys.exit("HALT: game has kicked off - in-play prices are not for the tape or the card")
    resp, used, rem = fetch(e["id"], ALT_MARKETS)
    total = used
    payloads = []
    if resp.status_code == 200:
        payloads.append(resp.json())
    elif resp.status_code == 422:            # one bad market key rejects the whole call: go one by one
        print("422 on the combined call - retrying market by market")
        for m in ALT_MARKETS:
            r1, u1, rem = fetch(e["id"], [m])
            total += u1
            print(f"  {m}: HTTP {r1.status_code} used={u1}")
            if r1.status_code == 200:
                payloads.append(r1.json())
            if rem != "?" and int(rem) < HALT_THRESHOLD:
                sys.exit(f"HALT: {rem} credits remaining < {HALT_THRESHOLD}")
    else:
        sys.exit(f"HALT: HTTP {resp.status_code}")
    if rem != "?" and int(rem) < HALT_THRESHOLD:
        sys.exit(f"HALT: {rem} credits remaining < {HALT_THRESHOLD}")
    rows = []
    for p in payloads:
        for b in p.get("bookmakers", []):
            for m in b.get("markets", []):
                for o in m.get("outcomes", []):
                    rows.append({"pull_timestamp": now.isoformat(), "event_id": e["id"],
                                 "commence_time": e["commence_time"], "home_team": e["home_team"],
                                 "away_team": e["away_team"], "bookmaker": b["key"],
                                 "market_key": m["key"], "market_last_update": m.get("last_update"),
                                 "outcome_name": o.get("name"), "description": o.get("description"),
                                 "point": o.get("point"), "price": o.get("price")})
    df = pd.DataFrame(rows)
    out = ROOT / "_cowork_patches"
    out.mkdir(exist_ok=True)
    df.to_parquet(out / "alt_lines_now.parquet", index=False)
    print(f"{e['away_team']} @ {e['home_team']}: {len(df)} rows, "
          f"{df.market_key.nunique() if len(df) else 0} markets | credits used {total} | remaining {rem}")
    if len(df):
        print(df.market_key.value_counts().to_string())


if __name__ == "__main__":
    main()
