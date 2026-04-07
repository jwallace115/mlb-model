#!/usr/bin/env python3
"""Rebuild 2024 NFL season props from cache + pull remaining Jan-Feb 2025."""
import json, os, sys, time, requests
import pandas as pd
from pathlib import Path
from datetime import date, timedelta, datetime

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

key = ""
for line in (ROOT / ".env").read_text().splitlines():
    if line.startswith("ODDS_API_KEY="):
        key = line.split("=", 1)[1].strip()
        break

BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
CACHE = ROOT / "nfl" / "research_derivatives" / "cache" / "props_backfill"
ARCHIVE = ROOT / "data" / "odds_archive" / "nfl" / "props"
BA = "player_pass_yds,player_pass_tds,player_pass_attempts,player_pass_completions,player_pass_interceptions"
BB = "player_rush_yds,player_rush_attempts,player_reception_yds,player_receptions,player_anytime_td"

def a2i(o):
    if o is None: return None
    return round(abs(o)/(abs(o)+100), 4) if o < 0 else round(100/(o+100), 4)

# Step 1: Pull remaining dates (Jan-Feb 2025)
print("Pulling remaining 2024 season dates (Jan-Feb 2025)...")
d = date(2025, 1, 1)
end = date(2025, 2, 15)
while d <= end:
    ds = d.isoformat()
    cf = CACHE / f"events_{ds}.json"
    if not cf.exists():
        r = requests.get(f"{BASE}/historical/sports/{SPORT}/events",
                         params={"apiKey": key, "date": f"{ds}T12:00:00Z"}, timeout=15)
        events = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        events = events if isinstance(events, list) else []
        cf.write_text(json.dumps(events))
    else:
        events = json.loads(cf.read_text())

    for ev in (events if isinstance(events, list) else []):
        eid = ev["id"]
        commence = ev.get("commence_time", f"{ds}T17:00:00Z")
        for batch_name, markets in [("props_a", BA), ("props_b", BB)]:
            ocf = CACHE / f"odds_{eid}_{batch_name}.json"
            if ocf.exists():
                continue
            r2 = requests.get(f"{BASE}/historical/sports/{SPORT}/events/{eid}/odds",
                              params={"apiKey": key, "regions": "us", "markets": markets,
                                      "oddsFormat": "american", "date": commence}, timeout=15)
            if r2.status_code == 200:
                ocf.write_text(json.dumps(r2.json().get("data", r2.json())))
            time.sleep(0.12)
    d += timedelta(days=1)

print("Remaining dates pulled.")

# Step 2: Rebuild ALL 2024 season from cache
print("Rebuilding 2024 season from cache...")
event_map = {}
for f in sorted(CACHE.glob("events_*.json")):
    ds = f.stem.replace("events_", "")
    if not (ds >= "2024-09-01" and ds <= "2025-02-15"):
        continue
    for ev in json.loads(f.read_text()):
        if isinstance(ev, dict) and ev.get("id"):
            event_map[ev["id"]] = {
                "home": ev.get("home_team", ""), "away": ev.get("away_team", ""),
                "commence": ev.get("commence_time", ""), "gd": ev.get("commence_time", "")[:10],
            }

print(f"2024 season events: {len(event_map)}")

rows = []
ts = datetime.now().isoformat()
for f in sorted(CACHE.glob("odds_*.json")):
    data = json.loads(f.read_text())
    if not isinstance(data, dict):
        continue
    eid = f.stem.replace("odds_", "").rsplit("_props_", 1)[0]
    batch = "props_" + f.stem.rsplit("_props_", 1)[1] if "_props_" in f.stem else "unk"
    info = event_map.get(eid)
    if not info:
        continue
    for bm in data.get("bookmakers", []):
        bk = bm.get("key", "")
        lu = bm.get("last_update", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            lum = mkt.get("last_update", lu)
            pl = {}
            for o in mkt.get("outcomes", []):
                k = (o.get("description", ""), o.get("point"))
                if k not in pl:
                    pl[k] = {}
                if o["name"] == "Over":
                    pl[k]["op"] = o["price"]
                elif o["name"] == "Under":
                    pl[k]["up"] = o["price"]
                else:
                    pl[k].setdefault("op", o["price"])
            for (desc, pt), p in pl.items():
                rows.append({
                    "sport": "nfl", "event_id": eid, "game_date": info["gd"],
                    "commence_time": info["commence"], "home_team": info["home"],
                    "away_team": info["away"], "bookmaker": bk, "market_key": mk,
                    "last_update": lum,
                    "player_name": desc if "player_" in mk else None,
                    "line": pt, "over_price": p.get("op"), "under_price": p.get("up"),
                    "implied_over": a2i(p.get("op")), "implied_under": a2i(p.get("up")),
                    "pull_batch": batch, "pull_timestamp": ts,
                })

df = pd.DataFrame(rows)
print(f"2024 season rows: {len(df):,}, games: {df['event_id'].nunique()}")

# Save
for (y, m), g in df.groupby([
    df["game_date"].str[:4].astype(int),
    df["game_date"].str[5:7].astype(int),
]):
    p = ARCHIVE / f"season={y}" / f"month={m:02d}"
    p.mkdir(parents=True, exist_ok=True)
    fp = p / f"data_{y}_{m:02d}.parquet"
    if fp.exists():
        existing = pd.read_parquet(fp)
        combined = pd.concat([existing, g], ignore_index=True).drop_duplicates(
            subset=["event_id", "bookmaker", "market_key", "player_name", "line"], keep="last")
    else:
        combined = g
    combined.to_parquet(fp, index=False)
    print(f"  {fp}: {len(combined):,}")

print("Done.")
