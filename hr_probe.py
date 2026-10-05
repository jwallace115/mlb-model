#!/usr/bin/env python3
"""One-off probe: which Hard Rock bookmaker key carries which sport?
Writes nothing. Prints only. Never prints the API key."""
import os, requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path.home() / "mlb-model"
load_dotenv(ROOT / ".env", override=True)
KEY = os.getenv("ODDS_API_KEY", "")
if not KEY:
    raise SystemExit("HARD STOP: ODDS_API_KEY not set in .env")

BASE    = "https://api.the-odds-api.com/v4"
HR      = ["hardrockbet", "hardrockbet_fl", "hardrockbet_az", "hardrockbet_oh"]
MARKETS = ["h2h", "spreads", "totals"]
SPORTS  = ["americanfootball_ncaaf", "americanfootball_nfl",
           "icehockey_nhl", "basketball_nba", "baseball_mlb"]

print(f"probing {len(HR)} Hard Rock keys x {len(MARKETS)} markets x {len(SPORTS)} sports")
print(f"expected cost: {len(MARKETS)} markets x 1 region-equiv x {len(SPORTS)} sports = {len(MARKETS)*len(SPORTS)} credits\n")

rem = used_total = None
for sport in SPORTS:
    p = {"apiKey": KEY, "markets": ",".join(MARKETS),
         "bookmakers": ",".join(HR), "oddsFormat": "american"}
    try:
        r = requests.get(f"{BASE}/sports/{sport}/odds/", params=p, timeout=45)
    except requests.RequestException as e:
        print(f"{sport:24s} REQUEST ERROR {type(e).__name__}: {e}")
        continue
    if r.status_code != 200:
        print(f"{sport:24s} HTTP {r.status_code}: {r.text[:160]}")
        continue
    games = r.json()
    used = r.headers.get("x-requests-used")
    rem  = r.headers.get("x-requests-remaining")
    counts, evs = {}, {}
    for g in games:
        for b in g.get("bookmakers", []):
            k = b["key"]
            evs.setdefault(k, set()).add(g["id"])
            for m in b.get("markets", []):
                counts[k] = counts.get(k, 0) + len(m.get("outcomes", []))
    print(f"{sport:24s} events={len(games):3d}  used={used} rem={rem}")
    if not counts:
        print(f"{'':24s}   -> NO Hard Rock key returned anything")
    for k in HR:
        if k in counts:
            print(f"{'':24s}   -> {k:16s} {len(evs[k]):3d} events, {counts[k]:4d} outcome rows")
        else:
            print(f"{'':24s}      {k:16s} absent")

print(f"\ncredits remaining after probe: {rem}")
