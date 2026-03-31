"""
Phase V2.2-A2: Injury and suspension data from API-Football.

Pulls /injuries?fixture={id} for all fixtures in the crosswalk.
Caches responses. Extracts injured/suspended players per team.

Output: soccer/data/injuries_raw.parquet
"""

import json
import logging
import os
import time

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache", "api_football")

CANONICAL_PATH  = os.path.join(DATA_DIR, "soccer_canonical.parquet")
CROSSWALK_PATH  = os.path.join(DATA_DIR, "api_football_crosswalk.parquet")
OUTPUT_PATH     = os.path.join(DATA_DIR, "injuries_raw.parquet")

API_BASE      = "https://v3.football.api-sports.io"
REQUEST_DELAY = 0.52   # ~1.9 req/sec to stay under 2/sec limit
DAILY_CAP     = 70_000
SEP = "═" * 72

os.makedirs(CACHE_DIR, exist_ok=True)


def load_api_key() -> str:
    env_path = os.path.join(os.path.dirname(BASE_DIR), ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(BASE_DIR, "..", ".env")
    with open(env_path) as f:
        for line in f:
            if line.startswith("API_FOOTBALL_KEY="):
                return line.strip().split("=", 1)[1]
    raise ValueError("API_FOOTBALL_KEY not found in .env")


class APIFootballClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers["x-apisports-key"] = api_key
        self.calls_this_session = 0
        self.quota_remaining    = None

    def get(self, endpoint: str, params: dict) -> dict:
        # Check cache
        param_str  = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
        slug       = endpoint.lstrip("/").replace("/", "_")
        cache_file = os.path.join(CACHE_DIR, f"{slug}_{param_str}.json")

        if os.path.exists(cache_file):
            with open(cache_file) as f:
                return json.load(f)

        if self.quota_remaining is not None and self.quota_remaining <= 10:
            logger.error("API quota nearly exhausted, stopping.")
            return {"response": [], "results": 0, "errors": ["quota_exhausted"]}

        url  = f"{API_BASE}/{endpoint.lstrip('/')}"
        last_exc = None

        for attempt in range(3):
            try:
                time.sleep(REQUEST_DELAY)
                resp = self.session.get(url, params=params, timeout=20)
                self.calls_this_session += 1

                self.quota_remaining = int(resp.headers.get("x-ratelimit-requests-remaining", -1))

                if resp.status_code in (429, 503, 502, 504):
                    wait = 10 * (attempt + 1)
                    logger.warning(f"HTTP {resp.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                with open(cache_file, "w") as f:
                    json.dump(data, f)

                return data

            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(10 * (attempt + 1))

        logger.error(f"All retries exhausted for {endpoint} {params}: {last_exc}")
        return {"response": [], "results": 0, "errors": [str(last_exc)]}


def parse_injuries(fixture_id: int, game_id: str, data: dict,
                   home_team_id: int, away_team_id: int) -> list[dict]:
    """Parse /injuries response into flat rows."""
    rows = []
    for entry in data.get("response", []):
        player  = entry.get("player", {})
        team    = entry.get("team",   {})
        fixture = entry.get("fixture", {})

        team_id   = team.get("id")
        if team_id == home_team_id:
            team_side = "home"
        elif team_id == away_team_id:
            team_side = "away"
        else:
            team_side = "unknown"

        rows.append({
            "game_id":     game_id,
            "fixture_id":  fixture_id,
            "player_id":   player.get("id"),
            "player_name": player.get("name"),
            "team_id":     team_id,
            "team_name":   team.get("name"),
            "team_side":   team_side,
            "reason":      player.get("reason"),   # e.g. "Knee Injury", "Suspended"
            "type":        player.get("type"),     # e.g. "Injury", "Suspension"
        })
    return rows


def main():
    print(f"\n{SEP}")
    print("  PHASE V2.2-A2: INJURIES BACKFILL (API-Football)")
    print(SEP)

    api_key = load_api_key()
    client  = APIFootballClient(api_key)

    crosswalk = pd.read_parquet(CROSSWALK_PATH)
    canon     = pd.read_parquet(CANONICAL_PATH)
    logger.info(f"Fixtures to process: {len(crosswalk):,}")

    # Build team_id lookup from cached fixture JSONs
    import glob
    team_id_map = {}  # fixture_id → (home_team_id, away_team_id)
    for fpath in glob.glob(os.path.join(CACHE_DIR, "fixtures_league*.json")):
        with open(fpath) as f:
            d = json.load(f)
        for g in d.get("response", []):
            fid = g["fixture"]["id"]
            home_id = g.get("teams", {}).get("home", {}).get("id")
            away_id = g.get("teams", {}).get("away", {}).get("id")
            if home_id and away_id:
                team_id_map[fid] = (home_id, away_id)

    logger.info(f"Team IDs loaded from fixture JSONs: {len(team_id_map):,}")

    all_rows = []
    empty_count  = 0
    cached_count = 0
    fetched_count = 0

    for i, (_, cw_row) in enumerate(crosswalk.iterrows()):
        game_id    = cw_row["game_id"]
        fixture_id = int(cw_row["fixture_id"])

        home_id, away_id = team_id_map.get(fixture_id, (None, None))

        data = client.get("injuries", {"fixture": fixture_id})

        # Check if this was from cache
        param_str  = f"fixture{fixture_id}"
        cache_file = os.path.join(CACHE_DIR, f"injuries_{param_str}.json")
        was_cached = os.path.exists(cache_file) and client.calls_this_session == 0

        if data.get("results", 0) == 0:
            empty_count += 1
        else:
            rows = parse_injuries(fixture_id, game_id, data, home_id, away_id)
            all_rows.extend(rows)

        if (i + 1) % 100 == 0:
            logger.info(f"  {i+1}/{len(crosswalk)} processed  "
                        f"calls_this_session={client.calls_this_session}  "
                        f"quota={client.quota_remaining}  "
                        f"injury_rows={len(all_rows)}  empty={empty_count}")

    logger.info(f"Complete: {len(all_rows):,} injury rows from {len(crosswalk):,} fixtures")
    logger.info(f"Empty responses: {empty_count:,} ({empty_count/len(crosswalk):.1%})")

    if all_rows:
        out = pd.DataFrame(all_rows)
    else:
        logger.warning("No injury data found — creating empty DataFrame")
        out = pd.DataFrame(columns=[
            "game_id", "fixture_id", "player_id", "player_name",
            "team_id", "team_name", "team_side", "reason", "type"
        ])

    out.to_parquet(OUTPUT_PATH, index=False)
    logger.info(f"Saved: {OUTPUT_PATH}  ({len(out):,} rows)")

    # ── Audit ──────────────────────────────────────────────────────────────────
    print(f"\n  AUDIT")
    print(f"  Total injury rows:   {len(out):,}")
    if len(out) > 0:
        games_with_injuries = out["game_id"].nunique()
        print(f"  Games with data:     {games_with_injuries:,} / {len(crosswalk):,} "
              f"({games_with_injuries/len(crosswalk):.1%})")
        if "type" in out.columns:
            print(f"  Type breakdown:\n{out['type'].value_counts().to_string()}")
    else:
        print(f"  NOTE: API-Football injury endpoint returned 0 records.")
        print(f"  This is common for historical fixtures — injury list feature")
        print(f"  will use fallback (0) for all games.")
    print(f"\n  Total API calls: {client.calls_this_session}")
    print(f"  Quota remaining: {client.quota_remaining}")
    print(f"\n  Saved → {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
