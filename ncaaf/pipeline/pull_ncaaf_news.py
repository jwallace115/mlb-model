#!/usr/bin/env python3
"""
N03: Pull NCAAF news from ESPN for teams on the board.

No API key. Zero credits. Endpoint:
  site.api.espn.com/apis/site/v2/sports/football/college-football/news?team={id}&limit=20

Output: data/news_archive/ncaaf/season=2026/ (append-only, raw JSON)
"""

import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
NEWS_DIR = ROOT / "data" / "news_archive" / "ncaaf"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
TEAM_MAP_PATH = ROOT / "ncaaf" / "pipeline" / "espn_team_map.json"


def build_espn_team_map(board_teams):
    """Build Odds API name -> ESPN team id map.

    Fetches the ESPN teams endpoint and matches against the board's team names.
    Returns (map_dict, unmatched_list, match_rate).
    """
    r = requests.get(f"{ESPN_BASE}/teams", params={"limit": 900}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"ESPN teams endpoint: HTTP {r.status_code}")

    espn_teams = []
    for item in r.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
        t = item.get("team", {})
        espn_teams.append({
            "id": t.get("id"),
            "displayName": t.get("displayName", ""),
            "abbreviation": t.get("abbreviation", ""),
            "location": t.get("location", ""),
            "nickname": t.get("nickname", ""),
            "slug": t.get("slug", ""),
        })

    # Match: try displayName first, then location + nickname
    espn_by_name = {}
    for t in espn_teams:
        espn_by_name[t["displayName"].lower()] = t["id"]
        full = f"{t['location']} {t['nickname']}".strip().lower()
        if full:
            espn_by_name[full] = t["id"]

    team_map = {}
    unmatched = []
    for name in board_teams:
        key = name.lower().strip()
        if key in espn_by_name:
            team_map[name] = int(espn_by_name[key])
        else:
            # Try partial match
            matched = False
            for espn_key, eid in espn_by_name.items():
                if key in espn_key or espn_key in key:
                    team_map[name] = int(eid)
                    matched = True
                    break
            if not matched:
                unmatched.append(name)

    match_rate = len(team_map) / len(board_teams) if board_teams else 0
    return team_map, unmatched, match_rate


def pull_news(team_map, build_time=None, season=2026):
    """Pull news for each mapped team. Returns list of article dicts."""
    if build_time is None:
        build_time = datetime.now(timezone.utc)
    build_dt = pd.Timestamp(build_time, tz="UTC") if isinstance(build_time, str) else build_time

    all_articles = []
    for team_name, espn_id in sorted(team_map.items()):
        r = requests.get(f"{ESPN_BASE}/news",
                         params={"team": espn_id, "limit": 20}, timeout=30)
        if r.status_code != 200:
            print(f"  {team_name} (id={espn_id}): HTTP {r.status_code}")
            time.sleep(1)
            continue

        articles = r.json().get("articles", [])
        eligible = []
        for a in articles:
            pub = a.get("published", "")
            pub_dt = pd.Timestamp(pub, tz="UTC") if pub else None
            if pub_dt and pub_dt < build_dt:
                eligible.append({
                    "team_name": team_name,
                    "espn_id": espn_id,
                    "headline": a.get("headline", ""),
                    "description": a.get("description", ""),
                    "published": pub,
                    "pull_time": build_dt.isoformat(),
                })
        all_articles.extend(eligible)
        print(f"  {team_name}: {len(eligible)}/{len(articles)} articles eligible")
        time.sleep(1)

    return all_articles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--build-time", help="ISO8601 UTC")
    args = parser.parse_args()

    bt = args.build_time or datetime.now(timezone.utc).isoformat()

    # Get board teams from the latest tape
    from ncaaf.pipeline.build_ncaaf_board import load_tape
    tape = load_tape(args.season, build_time=bt)
    if tape.empty:
        print("No tape data"); sys.exit(0)
    board_teams = sorted(set(tape["home_team"].unique()) | set(tape["away_team"].unique()))
    print(f"Board teams: {len(board_teams)}")

    # Build/load team map
    if TEAM_MAP_PATH.exists():
        with open(TEAM_MAP_PATH) as f:
            team_map = json.load(f)
        # Check all board teams are mapped
        unmapped = [t for t in board_teams if t not in team_map]
        if unmapped:
            print(f"Unmapped teams, rebuilding map: {unmapped}")
            team_map, unmatched, rate = build_espn_team_map(board_teams)
        else:
            unmatched = []
            rate = 1.0
    else:
        team_map, unmatched, rate = build_espn_team_map(board_teams)

    print(f"Match rate: {rate*100:.1f}% ({len(team_map)}/{len(board_teams)})")
    if unmatched:
        print(f"HALT: unmatched teams: {unmatched}")
        sys.exit(1)

    # Save the map
    with open(TEAM_MAP_PATH, "w") as f:
        json.dump(team_map, f, indent=2, sort_keys=True)
    print(f"Team map: {TEAM_MAP_PATH}")

    # Pull news
    print(f"\nPulling news (build_time={bt})...")
    articles = pull_news(team_map, build_time=bt, season=args.season)

    # Save
    out_dir = NEWS_DIR / f"season={args.season}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    out_path = out_dir / f"news_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(articles, f, indent=2)
    print(f"\nSaved {len(articles)} articles to {out_path}")


if __name__ == "__main__":
    main()
