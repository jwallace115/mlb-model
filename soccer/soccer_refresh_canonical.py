#!/usr/bin/env python3
"""
soccer_refresh_canonical.py — Daily canonical refresh via API-Football.

Fetches completed EPL and Bundesliga games from yesterday (or a specified
date), appends new rows to soccer_canonical.parquet.

Called from run_daily.py at 7am before signal generation.

Usage:
    python3 soccer/soccer_refresh_canonical.py
    python3 soccer/soccer_refresh_canonical.py --date 2026-03-15
    python3 soccer/soccer_refresh_canonical.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

SOCCER_DIR     = Path(__file__).resolve().parent
BASE_DIR       = SOCCER_DIR.parent
DATA_DIR       = SOCCER_DIR / "data"
CACHE_DIR      = DATA_DIR / "cache" / "refresh"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CANONICAL_PATH = DATA_DIR / "soccer_canonical.parquet"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

LEAGUES = {
    "EPL": {"id": 39, "season": 2025},
    "BUN": {"id": 78, "season": 2025},
}
SEASON_STR = "2025-26"

# Canonical column order (must match existing parquet)
CANONICAL_COLUMNS = [
    "game_id", "game_date", "season_year", "league_id",
    "home_team", "away_team", "home_score", "away_score",
    "regulation_total_90", "official_bet_total",
    "went_to_et", "went_to_penalties",
    "home_xg_raw", "away_xg_raw", "xg_source",
    "home_shots", "away_shots",
    "home_shots_on_target", "away_shots_on_target",
    "closing_total_line", "over_price", "under_price", "market_available",
]


def load_api_key() -> str:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("API_FOOTBALL_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("API_FOOTBALL_KEY", "")


def fetch_fixtures(api_key: str, league_id: int, season: int,
                   target_date: str) -> list[dict]:
    cache_file = CACHE_DIR / f"refresh_{league_id}_{target_date}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text()).get("response", [])

    headers = {"x-apisports-key": api_key}
    params  = {"date": target_date, "league": league_id, "season": season}
    try:
        time.sleep(0.6)
        resp = requests.get(
            f"{API_FOOTBALL_BASE}/fixtures",
            headers=headers, params=params, timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        cache_file.write_text(json.dumps(data))
        return data.get("response", [])
    except Exception as e:
        logger.warning(f"Failed to fetch fixtures for {league_id} {target_date}: {e}")
        return []


def get_stat(statistics: list[dict], team_name: str, stat_type: str) -> float | None:
    for s in statistics:
        if team_name.lower() in s.get("team", {}).get("name", "").lower():
            for item in s.get("statistics", []):
                if stat_type.lower() in item.get("type", "").lower():
                    v = item.get("value")
                    if v is None or v == "":
                        return None
                    try:
                        return float(str(v).replace("%", ""))
                    except Exception:
                        return None
    return None


def parse_fixture(fix: dict, league_id: str) -> dict | None:
    status = fix.get("fixture", {}).get("status", {}).get("short", "")
    if status not in ("FT", "AET", "PEN"):
        return None

    teams   = fix.get("teams", {})
    goals   = fix.get("goals", {})
    ft_info = fix.get("fixture", {})
    stats   = fix.get("statistics", [])

    home_team  = teams.get("home", {}).get("name", "")
    away_team  = teams.get("away", {}).get("name", "")
    home_score = goals.get("home")
    away_score = goals.get("away")

    if not home_team or not away_team or home_score is None or away_score is None:
        return None

    game_date_str = ft_info.get("date", "")[:10]
    went_to_et    = status in ("AET", "PEN")
    went_to_pen   = status == "PEN"

    home_xg    = get_stat(stats, home_team, "expected goals")
    away_xg    = get_stat(stats, away_team, "expected goals")
    home_shots = get_stat(stats, home_team, "total shots")
    away_shots = get_stat(stats, away_team, "total shots")
    home_sot   = get_stat(stats, home_team, "shots on goal")
    away_sot   = get_stat(stats, away_team, "shots on goal")

    game_id = (
        f"{league_id}_{SEASON_STR}_{game_date_str}_"
        f"{home_team}_{away_team}".replace(" ", "_")
    )

    return {
        "game_id":             game_id,
        "game_date":           game_date_str,
        "season_year":         SEASON_STR,
        "league_id":           league_id,
        "home_team":           home_team,
        "away_team":           away_team,
        "home_score":          int(home_score),
        "away_score":          int(away_score),
        "regulation_total_90": int(home_score) + int(away_score),
        "official_bet_total":  int(home_score) + int(away_score),
        "went_to_et":          int(went_to_et),
        "went_to_penalties":   int(went_to_pen),
        "home_xg_raw":         home_xg,
        "away_xg_raw":         away_xg,
        "xg_source":           "api_football" if home_xg is not None else None,
        "home_shots":          home_shots,
        "away_shots":          away_shots,
        "home_shots_on_target": home_sot,
        "away_shots_on_target": away_sot,
        "closing_total_line":  None,
        "over_price":          None,
        "under_price":         None,
        "market_available":    0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    default=None,
                        help="Date to fetch (YYYY-MM-DD, default: yesterday)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target_date = args.date or (date.today() - timedelta(days=1)).isoformat()
    logger.info(f"Soccer canonical refresh — {target_date}")

    api_key = load_api_key()
    if not api_key:
        logger.error("API_FOOTBALL_KEY not set")
        sys.exit(1)

    if CANONICAL_PATH.exists():
        canon = pd.read_parquet(CANONICAL_PATH)
        existing_ids = set(canon["game_id"].tolist())
    else:
        canon = pd.DataFrame()
        existing_ids = set()

    new_rows: list[dict] = []

    for league_id, info in LEAGUES.items():
        fixtures = fetch_fixtures(api_key, info["id"], info["season"], target_date)
        completed = [f for f in fixtures
                     if f.get("fixture", {}).get("status", {}).get("short", "") in ("FT", "AET", "PEN")]
        logger.info(f"[{league_id}] {len(completed)} completed fixtures on {target_date}")

        for fix in completed:
            row = parse_fixture(fix, league_id)
            if row is None:
                continue
            if row["game_id"] in existing_ids:
                continue
            new_rows.append(row)
            logger.info(f"  + {row['home_team']} {row['home_score']}-"
                        f"{row['away_score']} {row['away_team']}")

    if not new_rows:
        logger.info("No new games to add — canonical unchanged.")
        print(f"[soccer_refresh] 0 new games for {target_date}")
        return

    if args.dry_run:
        logger.info(f"DRY RUN: would add {len(new_rows)} rows")
        for r in new_rows:
            print(f"  {r['game_id']}")
        return

    new_df = pd.DataFrame(new_rows)

    if not canon.empty:
        # Align schema
        for col in CANONICAL_COLUMNS:
            if col not in new_df.columns:
                new_df[col] = None
        # Only keep columns present in canonical
        keep = [c for c in CANONICAL_COLUMNS if c in canon.columns]
        new_df = new_df[[c for c in keep if c in new_df.columns]]
        updated = pd.concat([canon, new_df], ignore_index=True)
        updated = updated.drop_duplicates(subset=["game_id"], keep="last")
        updated = updated.sort_values(["league_id", "season_year", "game_date"]).reset_index(drop=True)
    else:
        updated = new_df.sort_values(["league_id", "season_year", "game_date"]).reset_index(drop=True)

    updated.to_parquet(CANONICAL_PATH, index=False)
    logger.info(f"Added {len(new_rows)} game(s) → canonical now {len(updated):,} rows")
    print(f"[soccer_refresh] Added {len(new_rows)} new games → {CANONICAL_PATH}")


if __name__ == "__main__":
    main()
