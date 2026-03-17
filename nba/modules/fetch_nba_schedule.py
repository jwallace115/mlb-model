"""
NBA schedule fetcher — today's games via ScoreboardV2.

Returns list of dicts:
  {game_id, home_team, away_team, game_time_et, game_time_utc, status}

Only returns games with status "scheduled" or "pregame" — ignores completed
or in-progress games. Intended for the 7 AM morning card (before tip-off).
"""

import logging
import time
from datetime import date
from typing import Optional

import pandas as pd

from nba.config import NBA_API_TIMEOUT, SEASON_TYPE_REGULAR, SEASON_TYPE_PLAYOFF
from nba.modules.fetch_games import _call_with_retry, _norm_team


def _season_type_from_game_id(gid: str) -> str:
    """
    Derive season_type from NBA game_id format.
    Game IDs are 10 digits: 00 + 2-digit-year + 2-digit-type + 5-digit-seq.
    Type codes: 01=Preseason, 02=Regular Season, 03=All-Star, 04=Playoffs, 05=Play-In.
    """
    try:
        if len(gid) >= 6 and gid[4:6] == "04":
            return SEASON_TYPE_PLAYOFF
    except Exception:
        pass
    return SEASON_TYPE_REGULAR

logger = logging.getLogger(__name__)


def fetch_today_schedule(game_date: Optional[str] = None) -> list[dict]:
    """
    Fetch NBA schedule for game_date (YYYY-MM-DD, default today).
    Returns list of game dicts for scheduled/pregame games only.
    """
    if game_date is None:
        game_date = date.today().isoformat()

    date_str = pd.Timestamp(game_date).strftime("%m/%d/%Y")

    try:
        from nba_api.stats.endpoints import scoreboardv2
        board = _call_with_retry(
            scoreboardv2.ScoreboardV2,
            game_date=date_str,
            day_offset=0,
            league_id="00",
            timeout=NBA_API_TIMEOUT,
        )
        time.sleep(0.6)

        # GameHeader is index 0
        try:
            header = board.game_header.get_data_frame()
        except AttributeError:
            header = board.get_data_frames()[0]

        # LineScore is index 1 — gives team abbreviations
        try:
            ls = board.line_score.get_data_frame()
        except AttributeError:
            ls = board.get_data_frames()[1]

    except Exception as e:
        logger.warning(f"ScoreboardV2 failed for {game_date}: {e}")
        return []

    if header.empty:
        logger.info(f"No games found for {game_date}")
        return []

    # Build game_id → {home_team, away_team} from line_score
    team_map: dict[str, dict] = {}
    for _, row in ls.iterrows():
        gid   = str(row.get("GAME_ID", "")).strip()
        abbr  = _norm_team(str(row.get("TEAM_ABBREVIATION", "")))
        loc   = str(row.get("TEAM_CITY_NAME", "")) or ""
        # LineScore HOME/AWAY determined by order; use GAME_SEQUENCE if available
        # Fall back to tracking home as first seen, away as second
        if gid not in team_map:
            team_map[gid] = {"home_team": abbr, "away_team": None}
        else:
            team_map[gid]["away_team"] = abbr

    games = []
    seen_ids: set[str] = set()
    for _, row in header.iterrows():
        gid    = str(row.get("GAME_ID", "")).strip()
        if gid in seen_ids:
            continue
        seen_ids.add(gid)
        status = str(row.get("GAME_STATUS_TEXT", "")).strip().lower()

        # Only include upcoming games (not completed or in-progress)
        # Status codes: 1 = not started, 2 = in progress, 3 = final
        status_id = int(row.get("GAME_STATUS_ID", 0) or 0)
        if status_id >= 2:
            logger.debug(f"Skipping game {gid} (status_id={status_id}): {status}")
            continue

        teams = team_map.get(gid, {})
        home  = teams.get("home_team") or _norm_team(str(row.get("HOME_TEAM_ID", "")))
        away  = teams.get("away_team") or _norm_team(str(row.get("VISITOR_TEAM_ID", "")))

        # Game time — ScoreboardV2 gives ET time in GAME_STATUS_TEXT for scheduled games
        # e.g. "7:30 pm ET"
        game_time_et = status if "pm" in status or "am" in status else "TBD"
        game_time_utc = str(row.get("GAME_DATE_EST", "")).strip()

        games.append({
            "game_id":      gid,
            "home_team":    home,
            "away_team":    away,
            "game_time_et": game_time_et,
            "game_time_utc": game_time_utc,
            "game_date":    game_date,
            "season_type":  _season_type_from_game_id(gid),
        })

    logger.info(f"Schedule for {game_date}: {len(games)} upcoming games")
    return games
