"""
Offense module — fetches team wRC+ from FanGraphs API.

Aggregates individual batter data (PA-weighted wRC+) per team.
wRC+: 100 = league average, >100 = above average offense.
"""

import logging
import os
import json
import re
from collections import defaultdict
from datetime import date
from typing import Optional

import pandas as pd
import requests

from config import CACHE_DIR, LEAGUE_AVG_WRC_PLUS

logger = logging.getLogger(__name__)

_CACHE_FILE = os.path.join(CACHE_DIR, f"offense_{date.today().isoformat()}.json")

FANGRAPHS_BATTING_URL = "https://www.fangraphs.com/api/leaders/major-league/data"

# FanGraphs uses different abbreviations for some teams; normalise here
_FG_ABB_MAP = {
    "ATH": "OAK",   # Oakland Athletics (sometimes shown as ATH)
    "KCR": "KCR",
    "SDP": "SDP",
    "SFG": "SFG",
    "TBR": "TBR",
    "WSN": "WSN",
}

# Abbreviations to skip (multi-team players)
_SKIP_ABBS = {"2 Tms", "3 Tms", "4 Tms", "- - -"}


def _load_cache() -> dict:
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(data: dict) -> None:
    with open(_CACHE_FILE, "w") as f:
        json.dump(data, f)


def _fetch_fangraphs_batting(year: int) -> dict:
    """
    Pull FanGraphs individual batting (qual=10 PA) and aggregate to team level.
    Returns team_abb → {wrc_plus, ops}.
    """
    params = {
        "age": 0, "pos": "all", "stats": "bat", "lg": "all",
        "qual": 10, "season": year, "season1": year, "ind": 0,
        "team": 0, "pageitems": 2000, "pagenum": 1, "type": 8,
    }
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Referer": "https://www.fangraphs.com/leaders/major-league",
    }

    try:
        resp = requests.get(FANGRAPHS_BATTING_URL, params=params,
                            headers=headers, timeout=30)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    except Exception as e:
        logger.error(f"FanGraphs batting fetch failed: {e}")
        return {}

    # PA-weighted aggregation per team
    team_agg: dict = defaultdict(lambda: {
        "wrc_sum": 0.0, "pa_sum": 0.0, "ops_list": []
    })

    for row in rows:
        fg_abb = (row.get("TeamNameAbb") or "").strip()
        if not fg_abb or fg_abb in _SKIP_ABBS:
            continue

        abb    = _FG_ABB_MAP.get(fg_abb, fg_abb)
        wrc    = row.get("wRC+") or 0.0
        pa     = row.get("PA")   or 0.0
        ops    = row.get("OPS")  or 0.0

        try:
            wrc = float(wrc)
            pa  = float(pa)
            ops = float(ops)
        except (TypeError, ValueError):
            continue

        if pa <= 0:
            continue

        team_agg[abb]["wrc_sum"]  += wrc * pa
        team_agg[abb]["pa_sum"]   += pa
        team_agg[abb]["ops_list"].append(ops)

    db: dict = {}
    for abb, agg in team_agg.items():
        pa_sum = agg["pa_sum"]
        if pa_sum > 0:
            wrc_plus = agg["wrc_sum"] / pa_sum
        else:
            wrc_plus = LEAGUE_AVG_WRC_PLUS

        ops_list = agg["ops_list"]
        avg_ops  = sum(ops_list) / len(ops_list) if ops_list else 0.750

        db[abb] = {
            "wrc_plus": round(wrc_plus, 1),
            "ops":      round(avg_ops, 3),
        }

    logger.info(f"FanGraphs batting: loaded {len(db)} teams")
    return db


def _fetch_savant_team_offense(year: int) -> dict:
    """
    Fallback: pull individual batter xwOBA from Savant and aggregate by team.
    Converts team xwOBA → wRC+ proxy: (xwOBA / league_avg) * 100.
    Uses MLB Stats API to map player_id → current team.
    """
    LEAGUE_AVG_XWOBA = 0.318  # 2024-2025 MLB average

    try:
        from io import StringIO
        url = (
            f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
            f"?type=batter&year={year}&position=&team=&min=50&csv=true"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
    except Exception as e:
        logger.error(f"Savant batter CSV failed: {e}")
        return {}

    # Fetch player → team mapping from MLB Stats API
    player_team: dict = {}
    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/sports/1/players",
            params={"season": year}, timeout=20
        )
        resp.raise_for_status()
        from config import TEAM_ID_TO_ABB
        for p in resp.json().get("people", []):
            pid = str(p.get("id", ""))
            tid = p.get("currentTeam", {}).get("id")
            if pid and tid:
                abb = TEAM_ID_TO_ABB.get(tid, "")
                if abb:
                    player_team[pid] = abb
    except Exception as e:
        logger.warning(f"Player-team mapping failed: {e}")

    # PA-weighted xwOBA per team
    team_agg: dict = defaultdict(lambda: {"xwoba_sum": 0.0, "pa_sum": 0.0})
    for _, row in df.iterrows():
        pid   = str(int(row.get("player_id", 0) or 0))
        xwoba = row.get("est_woba")
        pa    = row.get("pa")
        team  = player_team.get(pid)
        if not team or pd.isna(xwoba) or pd.isna(pa) or float(pa) <= 0:
            continue
        team_agg[team]["xwoba_sum"] += float(xwoba) * float(pa)
        team_agg[team]["pa_sum"]    += float(pa)

    db: dict = {}
    for abb, agg in team_agg.items():
        if agg["pa_sum"] > 0:
            team_xwoba = agg["xwoba_sum"] / agg["pa_sum"]
            wrc_proxy  = (team_xwoba / LEAGUE_AVG_XWOBA) * 100
            db[abb] = {
                "wrc_plus": round(wrc_proxy, 1),
                "ops":      round(team_xwoba * 3.2, 3),
            }

    logger.info(f"Savant xwOBA fallback: loaded {len(db)} teams")
    return db


def build_offense_db(year: Optional[int] = None) -> dict:
    """
    Returns dict: team_abbr → {wrc_plus, ops}.
    Falls back to prior year if current year has no data (pre-season).
    """
    if year is None:
        year = date.today().year

    cache = _load_cache()
    if cache:
        return cache

    # Try FanGraphs first; fall back to Savant xwOBA if blocked/unavailable.
    db: dict = {}
    for attempt_year in [year, year - 1]:
        logger.info(f"Fetching team offense (FanGraphs) for {attempt_year}...")
        db = _fetch_fangraphs_batting(attempt_year)
        if db:
            break

    if not db:
        for attempt_year in [year, year - 1]:
            logger.info(f"Falling back to Savant xwOBA for {attempt_year}...")
            db = _fetch_savant_team_offense(attempt_year)
            if db:
                break

    if db:
        _save_cache(db)
        logger.info(f"Cached offense data for {len(db)} teams")
    else:
        logger.warning("Offense DB empty — league average will be used")

    return db


def get_team_offense(team_abb: str, offense_db: dict) -> dict:
    """Return offensive metrics for *team_abb*, falling back to league average."""
    default = {"wrc_plus": LEAGUE_AVG_WRC_PLUS, "ops": 0.750}

    if team_abb in offense_db:
        return offense_db[team_abb]

    logger.debug(f"Team offense not found: {team_abb} — using league average")
    return default
