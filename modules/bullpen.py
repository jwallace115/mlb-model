"""
Bullpen fatigue module — uses MLB Stats API boxscores to measure
how much relievers have been used over the past 2 days.

Fatigue score: 0.0 (fully rested) → 1.0 (heavily used)
"""

import logging
from datetime import date, timedelta
from typing import Optional

import requests

from config import MLB_STATS_API, BULLPEN_FATIGUE_PER_INNING, BULLPEN_MAX_FATIGUE_MULTIPLIER

logger = logging.getLogger(__name__)


def _get(endpoint: str, params: dict = None) -> dict:
    url = f"{MLB_STATS_API}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _innings_from_str(ip_str) -> float:
    """Convert '2.2' innings-pitched notation to decimal innings."""
    try:
        ip = float(ip_str)
        whole = int(ip)
        partial = ip - whole
        return whole + (partial / 3) * (10 / 3)  # .1 = 1/3 inn, .2 = 2/3 inn
    except Exception:
        return 0.0


def _get_boxscore(game_pk: int) -> dict:
    try:
        return _get(f"game/{game_pk}/boxscore")
    except Exception as e:
        logger.warning(f"Boxscore fetch failed for game_pk={game_pk}: {e}")
        return {}


def _extract_reliever_innings(boxscore: dict, is_home: bool) -> float:
    """Sum innings pitched by all relievers (non-starters) for one side."""
    side = "home" if is_home else "away"
    team_data = boxscore.get("teams", {}).get(side, {})
    pitchers  = team_data.get("pitchers", [])
    players   = team_data.get("players", {})

    total_innings = 0.0
    for i, pid in enumerate(pitchers):
        player_key = f"ID{pid}"
        player = players.get(player_key, {})
        stats  = player.get("stats", {}).get("pitching", {})
        ip_str = stats.get("inningsPitched", "0")
        ip = _innings_from_str(ip_str)

        if i == 0:
            # Starter: subtract their share so we only count relievers
            # Still count the starter if they threw < 4 innings (short start)
            if ip >= 4.0:
                continue  # skip normal starts

        total_innings += ip

    return total_innings


def _get_recent_game_pks(team_id: int, days: int = 2) -> list[int]:
    """Fetch game PKs for the last *days* days for a team."""
    today      = date.today()
    start_date = (today - timedelta(days=days)).isoformat()
    end_date   = (today - timedelta(days=1)).isoformat()

    try:
        data = _get(
            "schedule",
            params={
                "sportId": 1,
                "teamId": team_id,
                "startDate": start_date,
                "endDate": end_date,
            },
        )
    except Exception as e:
        logger.warning(f"Schedule fetch failed for team_id={team_id}: {e}")
        return []

    pks = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            status = game.get("status", {}).get("detailedState", "")
            if "final" in status.lower() or "completed" in status.lower():
                pks.append(game["gamePk"])
    return pks


def calculate_bullpen_fatigue(team_id: int, is_home: bool) -> dict:
    """
    Calculate bullpen fatigue score for a team over the last 2 days.

    Returns:
        {
          "fatigue_score":   0.0–1.0  (fraction of max expected bullpen usage),
          "innings_used":    float,
          "fatigue_multiplier": float  (how this scales RA9),
          "game_pks":        list[int],
        }
    """
    game_pks = _get_recent_game_pks(team_id, days=2)

    total_reliever_innings = 0.0
    for gk in game_pks:
        box = _get_boxscore(gk)
        if not box:
            continue
        # Determine which side this team is on in each game
        home_id = box.get("teams", {}).get("home", {}).get("team", {}).get("id")
        this_is_home = (home_id == team_id)
        total_reliever_innings += _extract_reliever_innings(box, this_is_home)

    # Normalise: ~6 innings of relief over 2 days = fully fatigued
    max_expected = 6.0
    raw_score    = total_reliever_innings * BULLPEN_FATIGUE_PER_INNING
    fatigue_score = min(raw_score / max_expected, 1.0) if max_expected > 0 else 0.0

    # Translate to RA9 multiplier
    fatigue_multiplier = 1.0 + fatigue_score * (BULLPEN_MAX_FATIGUE_MULTIPLIER - 1.0)

    return {
        "fatigue_score":       round(fatigue_score, 3),
        "innings_used":        round(total_reliever_innings, 1),
        "fatigue_multiplier":  round(fatigue_multiplier, 3),
        "game_pks":            game_pks,
    }
