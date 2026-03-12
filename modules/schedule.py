"""
Schedule module — pulls today's full game slate from the MLB Stats API.

Returns a list of game dicts, each containing:
  game_pk, game_date, game_time, status,
  home_team, away_team (abbreviations),
  home_team_id, away_team_id,
  home_probable_pitcher, away_probable_pitcher (name + mlbam id),
  venue_name, home_umpire (name, if available)
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

import requests

from config import MLB_STATS_API, TEAM_ID_TO_ABB

logger = logging.getLogger(__name__)

# IANA timezone per MLB home team (regular-season stadiums)
_TEAM_TZ = {
    "BAL": "America/New_York",  "BOS": "America/New_York",
    "NYY": "America/New_York",  "NYM": "America/New_York",
    "PHI": "America/New_York",  "WSN": "America/New_York",
    "ATL": "America/New_York",  "MIA": "America/New_York",
    "TBR": "America/New_York",  "TOR": "America/Toronto",
    "DET": "America/Detroit",   "CLE": "America/New_York",
    "PIT": "America/New_York",  "CIN": "America/New_York",
    "CHW": "America/Chicago",   "CHC": "America/Chicago",
    "MIL": "America/Chicago",   "MIN": "America/Chicago",
    "STL": "America/Chicago",   "KCR": "America/Chicago",
    "HOU": "America/Chicago",   "TEX": "America/Chicago",
    "COL": "America/Denver",
    "ARI": "America/Phoenix",   # no DST
    "LAA": "America/Los_Angeles", "LAD": "America/Los_Angeles",
    "SDP": "America/Los_Angeles", "SFG": "America/Los_Angeles",
    "SEA": "America/Los_Angeles", "OAK": "America/Los_Angeles",
}

# Spring Training venue keywords → IANA timezone
# Arizona (MST, no DST)
_AZ_VENUE_KEYWORDS = (
    "Camelback Ranch", "Peoria Sports Complex", "Peoria Stadium",
    "American Family Fields", "Surprise Stadium", "Goodyear Ballpark",
    "Salt River Fields", "Sloan Park", "Hohokam", "Scottsdale Stadium",
    "Tempe Diablo", "Talking Stick",
)
# Florida (Eastern — catches Central-tz teams visiting FL spring sites)
_FL_VENUE_KEYWORDS = (
    "Roger Dean", "BayCare", "Joker Marchant", "LECOM Park",
    "CACTI Park", "Lee Health", "Hammond Stadium", "CoolToday",
    "Charlotte Sports", "Ed Smith", "Spectrum Field", "FITTEAM",
    "Clover Park", "JetBlue", "TD Ballpark", "Steinbrenner",
    "Palm Beaches", "Fort Myers",
)


def _venue_tz(venue_name: str, home_abb: str) -> str:
    """Return IANA timezone string for the given venue / home team."""
    if any(kw in venue_name for kw in _AZ_VENUE_KEYWORDS):
        return "America/Phoenix"
    if any(kw in venue_name for kw in _FL_VENUE_KEYWORDS):
        return "America/New_York"
    return _TEAM_TZ.get(home_abb, "America/New_York")


def _get(endpoint: str, params: dict = None) -> dict:
    url = f"{MLB_STATS_API}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_schedule(game_date: Optional[str] = None) -> list[dict]:
    """
    Fetch all MLB games for *game_date* (YYYY-MM-DD).
    Defaults to today.
    """
    if game_date is None:
        game_date = date.today().isoformat()

    data = _get(
        "schedule",
        params={
            "sportId": 1,
            "date": game_date,
            "hydrate": "probablePitcher,officials,linescore,team",
        },
    )

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            status = game.get("status", {}).get("detailedState", "Unknown")
            # Skip postponed / cancelled games
            if status.lower() in ("postponed", "cancelled", "suspended"):
                continue

            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_id = home["team"]["id"]
            away_id = away["team"]["id"]

            home_abb = TEAM_ID_TO_ABB.get(home_id, home["team"].get("abbreviation", "UNK"))
            away_abb = TEAM_ID_TO_ABB.get(away_id, away["team"].get("abbreviation", "UNK"))

            # Probable pitchers
            def _pitcher(team_data: dict) -> dict:
                pp = team_data.get("probablePitcher", {})
                return {
                    "id":       pp.get("id"),
                    "name":     pp.get("fullName", "TBD"),
                }

            # Home plate umpire
            umpire_name = None
            for official in game.get("officials", []):
                if official.get("officialType") == "Home Plate":
                    umpire_name = official["official"]["fullName"]
                    break

            # Game time: local stadium timezone + ET reference
            venue_name_raw = game.get("venue", {}).get("name", "")
            game_time_str = game.get("gameDate", "")
            try:
                game_time_utc = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
                tz_name = _venue_tz(venue_name_raw, home_abb)
                local = game_time_utc.astimezone(ZoneInfo(tz_name))
                et    = game_time_utc.astimezone(ZoneInfo("America/New_York"))
                game_time_display    = local.strftime("%I:%M %p %Z")
                game_time_et_display = et.strftime("%I:%M %p") + " ET"
            except Exception:
                game_time_display    = game_time_str
                game_time_et_display = ""

            games.append({
                "game_pk":               game["gamePk"],
                "game_date":             game_date,
                "game_time":             game_time_display,
                "game_time_et":          game_time_et_display,
                "status":                status,
                "home_team":             home_abb,
                "away_team":             away_abb,
                "home_team_id":          home_id,
                "away_team_id":          away_id,
                "home_probable_pitcher": _pitcher(home),
                "away_probable_pitcher": _pitcher(away),
                "venue_name":            game.get("venue", {}).get("name", ""),
                "home_umpire":           umpire_name,
            })

    logger.info(f"Fetched {len(games)} games for {game_date}")
    return games


def fetch_recent_games_for_team(team_id: int, start_date: str, end_date: str) -> list[dict]:
    """
    Return completed games for *team_id* between start_date and end_date.
    Used by the bullpen module to find recent game PKs.
    """
    data = _get(
        "schedule",
        params={
            "sportId": 1,
            "teamId": team_id,
            "startDate": start_date,
            "endDate": end_date,
            "hydrate": "team",
        },
    )

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            status = game.get("status", {}).get("detailedState", "")
            if "final" in status.lower() or "completed" in status.lower():
                games.append({
                    "game_pk":   game["gamePk"],
                    "game_date": date_block["date"],
                })
    return games
