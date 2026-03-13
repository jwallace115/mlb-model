"""
Lineup monitor — detect SP scratches and batter scratches vs stored projections.

Uses the MLB Stats API live feed for:
  - Current probable pitchers (reliable from game announcement through game time)
  - Confirmed batting order (available ~90 min before first pitch)

All functions degrade gracefully — return empty results on any API failure.
"""

import logging
from typing import Optional

import requests

from config import MLB_STATS_API

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "mlb-model/1.0"}

# Confidence downgrade ladder for SP scratch
CONF_DOWNGRADE = {"HIGH": "MEDIUM", "MEDIUM": "LOW", "LOW": "LOW"}
CONF_SCORE_PENALTY = 0.18   # subtracted from confidence_score on SP change


# ── MLB Stats API helpers ──────────────────────────────────────────────────────

def fetch_probable_pitchers(game_pk: int) -> dict:
    """
    Return {"home": fullName_or_None, "away": fullName_or_None}
    from the live game feed's gameData.probablePitchers.
    """
    try:
        url = f"{MLB_STATS_API}.1/game/{game_pk}/feed/live"
        resp = requests.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        pp = resp.json().get("gameData", {}).get("probablePitchers", {})
        return {
            "home": (pp.get("home") or {}).get("fullName"),
            "away": (pp.get("away") or {}).get("fullName"),
        }
    except Exception as e:
        logger.debug(f"fetch_probable_pitchers({game_pk}): {e}")
        return {"home": None, "away": None}


def fetch_batting_order(game_pk: int) -> dict:
    """
    Return {"home": [fullName, ...], "away": [...]}
    from the live feed's liveData.boxscore.teams.
    Returns empty lists if lineups not yet submitted or on error.
    """
    try:
        url = f"{MLB_STATS_API}.1/game/{game_pk}/feed/live"
        resp = requests.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        data  = resp.json()
        teams = data.get("liveData", {}).get("boxscore", {}).get("teams", {})

        result = {"home": [], "away": []}
        for side in ("home", "away"):
            team_data = teams.get(side, {})
            order_ids = team_data.get("battingOrder", [])
            players   = team_data.get("players", {})
            names = []
            for pid in order_ids:
                p    = players.get(f"ID{pid}", {})
                name = p.get("person", {}).get("fullName", "")
                if name:
                    names.append(name)
            result[side] = names
        return result
    except Exception as e:
        logger.debug(f"fetch_batting_order({game_pk}): {e}")
        return {"home": [], "away": []}


# ── Change detection ──────────────────────────────────────────────────────────

def detect_sp_changes(
    game_pk: int,
    stored_home_sp: Optional[str],
    stored_away_sp: Optional[str],
) -> list[dict]:
    """
    Compare stored SP names vs current probable pitchers from the live feed.

    Returns a list of 0-2 dicts:
        {
          "side":       "home" | "away",
          "player_out": str,
          "player_in":  str,
        }
    """
    current = fetch_probable_pitchers(game_pk)
    changes = []

    for side, stored in [("home", stored_home_sp), ("away", stored_away_sp)]:
        live_name = current.get(side)
        if not live_name or not stored:
            continue
        if live_name.strip().lower() != stored.strip().lower():
            changes.append({
                "side":       side,
                "player_out": stored,
                "player_in":  live_name,
            })
            logger.info(f"SP change detected ({side}): {stored} → {live_name}")

    return changes


def detect_batter_scratches(
    game_pk:    int,
    home_team:  str,
    away_team:  str,
    top_batters: dict,   # {team_abb: [batter_dict, ...]}
) -> list[dict]:
    """
    Check whether any of our top-TB-projection batters are absent from the
    confirmed batting order.

    Returns empty list if:
      - The lineup has not been submitted yet (order lists are empty)
      - API call fails

    Returns a list of dicts:
        {
          "side":       "home" | "away",
          "team":       team_abb,
          "player_out": str,
        }
    """
    order = fetch_batting_order(game_pk)

    # Both sides empty → lineup not posted yet
    if not order["home"] and not order["away"]:
        logger.debug(f"Batting order not yet posted for game_pk={game_pk}")
        return []

    scratches = []
    for team_abb, side in [(home_team, "home"), (away_team, "away")]:
        confirmed = {n.lower() for n in order.get(side, [])}
        if not confirmed:
            continue
        for batter in top_batters.get(team_abb, []):
            bname = batter.get("name", "")
            if not bname:
                continue
            if bname.lower() not in confirmed:
                scratches.append({
                    "side":       side,
                    "team":       team_abb,
                    "player_out": bname,
                })
                logger.info(
                    f"Batter scratch detected: {bname} ({team_abb}) "
                    f"not in confirmed lineup for game_pk={game_pk}"
                )

    return scratches


# ── Confidence helpers ─────────────────────────────────────────────────────────

def downgrade_confidence(proj: dict) -> dict:
    """
    Return a copy of proj with confidence level and score reduced by one step.
    Mutates in-place and also returns for chaining.
    """
    old_conf  = proj.get("confidence", "MEDIUM")
    new_conf  = CONF_DOWNGRADE.get(old_conf, old_conf)
    old_score = proj.get("confidence_score") or 0.5
    new_score = max(0.0, old_score - CONF_SCORE_PENALTY)

    proj["confidence"]       = new_conf
    proj["confidence_score"] = round(new_score, 4)
    return proj
