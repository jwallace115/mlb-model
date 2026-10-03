#!/usr/bin/env python3
"""One-off: pull Hard Rock NCAAF prices now, and compare hardrockbet vs
hardrockbet_fl on NFL. Writes hr_ncaaf_now.parquet only. Never prints the key."""
import os, requests, pandas as pd, datetime
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path.home() / "mlb-model"
load_dotenv(ROOT / ".env", override=True)
KEY = os.getenv("ODDS_API_KEY", "")
if not KEY:
    raise SystemExit("HARD STOP: ODDS_API_KEY not set in .env")

BASE = "https://api.the-odds-api.com/v4"
MK = "h2h,spreads,totals"


def get(sport, books):
    r = requests.get(f"{BASE}/sports/{sport}/odds/", timeout=45, params={
        "apiKey": KEY, "markets": MK, "bookmakers": books, "oddsFormat": "american"})
    r.raise_for_status()
    print(f"{sport}: {len(r.json())} events, rem={r.headers.get('x-requests-remaining')}")
    return r.json()


snap = datetime.datetime.now(datetime.timezone.utc).isoformat()

rows = []
for g in get("americanfootball_ncaaf", "hardrockbet"):
    for b in g.get("bookmakers", []):
        for m in b.get("markets", []):
            for o in m.get("outcomes", []):
                rows.append(dict(
                    snapshot_utc=snap, event_id=g["id"],
                    commence_time=g["commence_time"], home_team=g["home_team"],
                    away_team=g["away_team"], bookmaker=b["key"],
                    book_last_update=b.get("last_update"), market=m["key"],
                    outcome_name=o["name"], point=o.get("point"), price=o["price"]))

df = pd.DataFrame(rows)
df.to_parquet(ROOT / "hr_ncaaf_now.parquet")
print(f"wrote hr_ncaaf_now.parquet: {len(df)} rows, {df['event_id'].nunique()} events")

nfl = []
for g in get("americanfootball_nfl", "hardrockbet,hardrockbet_fl"):
    for b in g.get("bookmakers", []):
        for m in b.get("markets", []):
            for o in m.get("outcomes", []):
                nfl.append(dict(
                    g=f"{g['away_team']} @ {g['home_team']}", bk=b["key"],
                    mkt=m["key"], oc=o["name"], pt=o.get("point"), px=o["price"]))

n = pd.DataFrame(nfl)
print(f"\nNFL rows: generic={(n['bk'] == 'hardrockbet').sum()}  fl={(n['bk'] == 'hardrockbet_fl').sum()}")
w = n.pivot_table(index=["g", "mkt", "oc"], columns="bk", values=["pt", "px"], aggfunc="first")
if ("px", "hardrockbet") in w.columns and ("px", "hardrockbet_fl") in w.columns:
    both = w.dropna(subset=[("px", "hardrockbet"), ("px", "hardrockbet_fl")])
    dpx = both[("px", "hardrockbet")] != both[("px", "hardrockbet_fl")]
    dpt = both[("pt", "hardrockbet")].fillna(-999) != both[("pt", "hardrockbet_fl")].fillna(-999)
    print(f"comparable outcomes: {len(both)}  price differs: {dpx.sum()}  point differs: {dpt.sum()}")
    if dpx.sum() or dpt.sum():
        print("\n--- DIFFERENCES ---")
        print(both[dpx | dpt].to_string())
    else:
        print("\nIDENTICAL on every comparable outcome -> clean one-word swap")
else:
    print("one of the two keys returned nothing comparable")
