#!/usr/bin/env python3
"""
N05: Pull CFBD season data (games + betting lines).

CollegeFootballData API, NOT the Odds API. CFBD_API_KEY in .env.
Zero Odds API credits. Rate-limited, not credit-metered.

Usage:
  python3 ncaaf/pipeline/pull_cfbd_season.py --year 2025
  python3 ncaaf/pipeline/pull_cfbd_season.py --year 2026 --schedule-only
"""

import argparse, hashlib, json, os, sys, time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

CFBD_KEY = os.getenv("CFBD_API_KEY", "")
KEY_FP = hashlib.sha256(CFBD_KEY.strip().encode()).hexdigest()[:8] if CFBD_KEY else "UNSET"
CFBD_BASE = "https://api.collegefootballdata.com"
CFBD_HEADERS = {"Authorization": f"Bearer {CFBD_KEY}", "Accept": "application/json"}
OUT_DIR = ROOT / "research" / "ncaaf"


def cfbd_get(endpoint, params=None):
    url = f"{CFBD_BASE}/{endpoint.lstrip('/')}"
    r = requests.get(url, headers=CFBD_HEADERS, params=params or {}, timeout=30)
    if r.status_code != 200:
        print(f"ERROR: {endpoint} -> HTTP {r.status_code}: {r.text[:200]}")
        sys.exit(1)
    return r.json()


def pull_season(year, schedule_only=False):
    print(f"CFBD key fingerprint: {KEY_FP}")
    if not CFBD_KEY:
        print("HALT: CFBD_API_KEY not set"); sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Games
    print(f"\nPulling games for {year}...")
    games = cfbd_get("/games", {"year": year, "seasonType": "regular"})
    post = cfbd_get("/games", {"year": year, "seasonType": "postseason"})
    all_games = games + post
    gdf = pd.DataFrame(all_games)
    gpath = OUT_DIR / f"cfbd_games_{year}.parquet"
    gdf.to_parquet(gpath, index=False)
    print(f"  Games: {len(gdf)} rows -> {gpath}")
    if "homePoints" in gdf.columns:
        scored = gdf[gdf["homePoints"].notna()]
        print(f"  With scores: {len(scored)}")
    if "homeLineScores" in gdf.columns:
        has_qtr = gdf["homeLineScores"].notna().sum()
        print(f"  With quarter scores: {has_qtr}")

    if schedule_only:
        print("--schedule-only: skipping lines")
        return

    # Betting lines
    print(f"\nPulling betting lines for {year}...")
    lines = cfbd_get("/lines", {"year": year, "seasonType": "regular"})
    post_lines = cfbd_get("/lines", {"year": year, "seasonType": "postseason"})
    all_lines = lines + post_lines

    # Flatten: each game has a 'lines' array of provider objects
    flat = []
    for game in all_lines:
        gid = game.get("id")
        season = game.get("season")
        week = game.get("week")
        home = game.get("homeTeam")
        away = game.get("awayTeam")
        home_score = game.get("homeScore")
        away_score = game.get("awayScore")
        for line in game.get("lines", []):
            flat.append({
                "id": gid, "season": season, "week": week,
                "homeTeam": home, "awayTeam": away,
                "homeScore": home_score, "awayScore": away_score,
                "provider": line.get("provider"),
                "spread": line.get("spread"),
                "spreadOpen": line.get("spreadOpen"),
                "overUnder": line.get("overUnder"),
                "overUnderOpen": line.get("overUnderOpen"),
                "homeMoneyline": line.get("homeMoneyline"),
                "awayMoneyline": line.get("awayMoneyline"),
            })

    ldf = pd.DataFrame(flat)
    lpath = OUT_DIR / f"cfbd_betting_lines_{year}.parquet"
    ldf.to_parquet(lpath, index=False)
    print(f"  Lines: {len(ldf)} rows -> {lpath}")

    # Report
    if not ldf.empty:
        print(f"\n  Provider coverage:")
        for p, g in ldf.groupby("provider"):
            has_spread = g["spread"].notna().sum()
            has_ou = g["overUnder"].notna().sum()
            has_both_scores = (g["homeScore"].notna() & g["awayScore"].notna()).sum()
            print(f"    {p}: {len(g)} rows, spread={has_spread}, overUnder={has_ou}, scores={has_both_scores}")

        # spread vs spreadOpen
        has_both = ldf[ldf["spread"].notna() & ldf["spreadOpen"].notna()]
        if len(has_both) > 0:
            diff = (has_both["spread"] != has_both["spreadOpen"]).mean()
            print(f"\n  spread != spreadOpen: {diff*100:.1f}% of {len(has_both)} rows")
        else:
            print("\n  No rows with both spread and spreadOpen")

    # 2026 venues
    if year == 2026:
        print(f"\nBuilding team-venue map from 2026 home games...")
        home_venues = gdf[gdf["venueId"].notna()][["homeTeam", "venueId"]].drop_duplicates("homeTeam")
        home_venues = home_venues.rename(columns={"homeTeam": "team", "venueId": "venue_id"})
        vpath = OUT_DIR / f"cfbd_teams_venues_{year}.parquet"
        home_venues.to_parquet(vpath, index=False)
        print(f"  Teams-venues: {len(home_venues)} -> {vpath}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--schedule-only", action="store_true")
    args = parser.parse_args()
    pull_season(args.year, schedule_only=args.schedule_only)


if __name__ == "__main__":
    main()
