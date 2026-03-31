"""
NBA injury report fetcher.

Primary: ESPN injury API (free, no auth required).
Fallback: Return empty list with warning (does not crash the daily run).

Returns list of dicts:
  {team, player, status, description}

Only Out and Doubtful players are returned — Questionable is ignored
because injury impact on game totals is ambiguous at question mark status.

ORtg adjustment is applied in run_nba.py using:
  INJURY_PPP_REDUCTION per Out/Doubtful rotation player (MPG ≥ INJURY_MIN_MPG)
  capped at INJURY_MAX_REDUCTION
"""

import logging
from typing import Optional

import requests

from nba.config import INJURY_MIN_MPG

logger = logging.getLogger(__name__)

_ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"

# ESPN team abbr → our canonical abbreviation
_ESPN_TEAM_MAP = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "CHA": "CHA",
    "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN",
    "DET": "DET", "GSW": "GSW", "HOU": "HOU", "IND": "IND",
    "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA",
    "MIL": "MIL", "MIN": "MIN", "NOP": "NOP", "NYK": "NYK",
    "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHX": "PHX",
    "POR": "POR", "SAC": "SAC", "SAS": "SAS", "TOR": "TOR",
    "UTA": "UTA", "WAS": "WAS",
    # Alternate ESPN codes
    "NO":  "NOP", "GS":  "GSW", "SA":  "SAS", "NY":  "NYK",
}

_ACTIONABLE_STATUSES = {"out", "doubtful"}


def fetch_injuries() -> list[dict]:
    """
    Fetch today's NBA injury report from ESPN.
    Returns list of {team, player, status, description} for Out/Doubtful players.
    Falls back to empty list on any error.
    """
    try:
        resp = requests.get(_ESPN_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"ESPN injury API failed: {e} — running without injury adjustments")
        return []

    result = []
    for team_entry in (data if isinstance(data, list) else []):
        team_abbr_raw = (
            team_entry.get("team", {}).get("abbreviation", "")
            if isinstance(team_entry.get("team"), dict)
            else ""
        )
        team = _ESPN_TEAM_MAP.get(team_abbr_raw.upper(), team_abbr_raw.upper())

        for injury in (team_entry.get("injuries") or []):
            status_raw = (injury.get("status") or "").lower()
            if status_raw not in _ACTIONABLE_STATUSES:
                continue
            athlete = injury.get("athlete") or {}
            player  = athlete.get("displayName") or athlete.get("shortName") or "Unknown"
            desc    = injury.get("longComment") or injury.get("shortComment") or ""
            result.append({
                "team":        team,
                "player":      player,
                "status":      status_raw,
                "description": desc,
            })

    logger.info(f"Injury report: {len(result)} Out/Doubtful players across NBA")
    return result
