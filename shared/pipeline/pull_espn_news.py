#!/usr/bin/env python3
"""
WO10 Item 2a: Pull NFL or NCAAF news from ESPN (per-team endpoint).

No API key. Zero credits.
  NFL:   site.api.espn.com/apis/site/v2/sports/football/nfl/news?team={id}&limit=20
  NCAAF: site.api.espn.com/apis/site/v2/sports/football/college-football/news?team={id}&limit=20

Output (raw JSON, append-only):
  data/news_archive/nfl/season=2026/news_<UTC>.json
  data/news_archive/ncaaf/season=2026/news_<UTC>.json

Freshness check: newest article must be published within 72 hours, else HALT.
"""

import argparse, json, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent

ESPN_BASES = {
    "nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
    "ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football",
}

NFL_TEAM_MAP = ROOT / "nfl" / "pipeline" / "espn_team_map.json"
NCAAF_TEAM_MAP = ROOT / "ncaaf" / "pipeline" / "espn_team_map.json"

FRESHNESS_HOURS = 72


def load_team_ids(sport):
    if sport == "nfl":
        with open(NFL_TEAM_MAP) as f:
            m = json.load(f)
        return {name: info["id"] for name, info in m.items()}
    else:
        # NCAAF: read from board artifact (N14 rule)
        board_dir = ROOT / "ncaaf" / "data" / "board"
        board_files = sorted(board_dir.rglob("ncaaf_board.parquet"))
        if not board_files:
            print("HALT: no board artifact found for NCAAF team list")
            sys.exit(1)
        board_df = pd.read_parquet(board_files[-1])
        board_teams = sorted(
            set(board_df["home_team"].unique()) | set(board_df["away_team"].unique())
        )
        with open(NCAAF_TEAM_MAP) as f:
            ncaaf_map = json.load(f)
        team_ids = {}
        unmapped = []
        for t in board_teams:
            if t in ncaaf_map:
                team_ids[t] = int(ncaaf_map[t])
            else:
                unmapped.append(t)
        if unmapped:
            print(f"HALT: {len(unmapped)} unmapped NCAAF teams: {unmapped[:5]}")
            sys.exit(1)
        return team_ids


def pull_news(sport, team_ids, season):
    now = datetime.now(timezone.utc)
    ts_label = now.strftime("%Y%m%dT%H%MZ")
    base = ESPN_BASES[sport]

    all_articles = []
    newest_pub = None
    errors = 0

    for team_name, espn_id in sorted(team_ids.items()):
        try:
            r = requests.get(
                f"{base}/news",
                params={"team": espn_id, "limit": 20},
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"  {team_name} (id={espn_id}): request error {e}")
            errors += 1
            time.sleep(0.5)
            continue

        if r.status_code != 200:
            print(f"  {team_name} (id={espn_id}): HTTP {r.status_code}")
            errors += 1
            time.sleep(0.5)
            continue

        articles = r.json().get("articles", [])
        for a in articles:
            pub = a.get("published", "")
            a["_team_name"] = team_name
            a["_espn_id"] = espn_id
            a["_pull_time"] = now.isoformat()
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if newest_pub is None or pub_dt > newest_pub:
                        newest_pub = pub_dt
                except (ValueError, TypeError):
                    pass
        all_articles.extend(articles)
        time.sleep(0.5)

    print(f"  teams queried: {len(team_ids)}, errors: {errors}, "
          f"articles: {len(all_articles)}")

    # Freshness check
    if newest_pub is None:
        print(f"HALT: no article has a parseable published timestamp")
        sys.exit(1)

    age_hours = (now - newest_pub).total_seconds() / 3600
    print(f"  newest article: {newest_pub.isoformat()} (age: {age_hours:.1f}h)")
    if age_hours > FRESHNESS_HOURS:
        print(f"HALT: newest article is {age_hours:.1f}h old (threshold: {FRESHNESS_HOURS}h)")
        sys.exit(1)

    # Save
    out_dir = ROOT / "data" / "news_archive" / sport / f"season={season}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"news_{ts_label}.json"

    with open(out_path, "w") as f:
        json.dump(all_articles, f)

    size_kb = out_path.stat().st_size / 1024
    print(f"  saved {len(all_articles)} articles to {out_path} ({size_kb:.0f} KB)")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", required=True, choices=["nfl", "ncaaf"])
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    print(f"pull_espn_news --sport {args.sport} --season {args.season}")
    team_ids = load_team_ids(args.sport)
    print(f"  teams: {len(team_ids)}")

    t0 = time.time()
    pull_news(args.sport, team_ids, args.season)
    elapsed = time.time() - t0
    print(f"  elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
