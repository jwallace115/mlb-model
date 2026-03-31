"""
Understat xG fetcher — Phase 1 backfill.

Source: https://understat.com/getLeagueData/{league}/{season_year}
  - GET request, returns JSON with 'dates' list of match records
  - Each match has: id, h/a team title, goals, xG {h, a}, datetime, isResult
  - No Cloudflare blocking — direct HTTP GET with browser headers works

Understat league codes:
  EPL       → "EPL"
  Bundesliga → "Bundesliga"
  La Liga    → "La_liga"
  Serie A    → "Serie_A"
  Ligue 1    → "Ligue_1"

Understat season codes:
  2019-20 season → 2019
  2023-24 season → 2023
  (year the season starts)

Team name crosswalk (Understat → football-data.co.uk):
  Built by manually comparing all teams that appear in canonical table.
  Separate crosswalks for EPL and BUN — naming conventions differ.
"""

import json
import logging
import os
import time

import pandas as pd
import requests

from soccer.config import (
    CACHE_DIR,
    SEASON_LABELS,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://understat.com/getLeagueData/{league}/{season_year}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

_REQUEST_DELAY = 1.2   # seconds between requests


# ── Understat → football-data.co.uk team name crosswalk ───────────────────────
# Keys: Understat name. Values: football-data.co.uk name.
# Only entries where names differ — exact matches are passed through unchanged.

_CROSSWALK_EPL = {
    "Manchester City":         "Man City",
    "Manchester United":       "Man United",
    "Newcastle United":        "Newcastle",
    "Nottingham Forest":       "Nott'm Forest",
    "Wolverhampton Wanderers": "Wolves",
    # Historical names (appear in older seasons)
    "Leeds":                   "Leeds",
    "Leicester":               "Leicester",
    "Norwich":                 "Norwich",
    "Watford":                 "Watford",
    "West Brom":               "West Brom",
    "West Bromwich Albion":    "West Brom",
}

_CROSSWALK_BUN = {
    "Borussia Dortmund":     "Dortmund",
    "Eintracht Frankfurt":   "Ein Frankfurt",
    "FC Cologne":            "FC Koln",
    "FC Heidenheim":         "Heidenheim",
    "Bayer Leverkusen":      "Leverkusen",
    "Borussia M.Gladbach":   "M'gladbach",
    "Mainz 05":              "Mainz",
    "RasenBallsport Leipzig": "RB Leipzig",
    "VfB Stuttgart":         "Stuttgart",
    # Historical (older seasons)
    "Arminia Bielefeld":     "Bielefeld",
    "Greuther Fuerth":       "Greuther Furth",
    "Hamburger SV":          "Hamburg",
    "Hannover 96":           "Hannover",
    "Ingolstadt 04":         "Ingolstadt",
    "Fortuna Duesseldorf":   "Fortuna Dusseldorf",
    "Paderborn 07":          "Paderborn",
    "FC Schalke 04":         "Schalke 04",
    "SpVgg Greuther Furth":  "Greuther Furth",
    "1. FC Nuremberg":       "Nuernberg",
    "1. FC Nurnberg":        "Nuernberg",
    "Hertha Berlin":         "Hertha",
    "St. Pauli":             "St Pauli",
}

_CROSSWALK_LGA = {
    "Athletic Club":     "Ath Bilbao",
    "Atletico Madrid":   "Ath Madrid",
    "Celta Vigo":        "Celta",
    "Espanyol":          "Espanol",
    "Rayo Vallecano":    "Vallecano",
    "Real Betis":        "Betis",
    "Real Sociedad":     "Sociedad",
    "Real Valladolid":   "Valladolid",
    # Historical
    "Deportivo Alaves":  "Alaves",
    "SD Huesca":         "Huesca",
    "SD Eibar":          "Eibar",
}

_CROSSWALK_SEA = {
    "AC Milan":          "Milan",
    "Hellas Verona":     "Verona",
    "AS Roma":           "Roma",
    "Inter":             "Inter",
    "Internazionale":    "Inter",
    # Historical
    "Benevento":         "Benevento",
    "Chievo":            "Chievo",
    "SPAL 2013":         "Spal",
    "Parma Calcio 1913": "Parma",
}

_CROSSWALK_LG1 = {
    "Paris Saint Germain": "Paris SG",
    "Saint-Etienne":     "St Etienne",
    "Clermont Foot":     "Clermont",
    "Stade Brestois 29": "Brest",
    "Stade Rennais":     "Rennes",
    # Historical
    "AS Saint-Etienne":  "St Etienne",
    "Stade de Reims":    "Reims",
    "AS Monaco":         "Monaco",
    "RC Strasbourg Alsace": "Strasbourg",
    "FC Metz":           "Metz",
    "Dijon FCO":         "Dijon",
    "Nimes Olympique":   "Nimes",
    "RC Lens":           "Lens",
    "FC Nantes":         "Nantes",
    "Amiens SC":         "Amiens",
}

_CROSSWALK = {
    "EPL": _CROSSWALK_EPL,
    "BUN": _CROSSWALK_BUN,
    "LGA": _CROSSWALK_LGA,
    "SEA": _CROSSWALK_SEA,
    "LG1": _CROSSWALK_LG1,
}

# Understat league code for each league_id
_US_LEAGUE_CODE = {
    "EPL": "EPL",
    "BUN": "Bundesliga",
    "LGA": "La_liga",
    "SEA": "Serie_A",
    "LG1": "Ligue_1",
}

# fd-code season (e.g. "2324") → understat season year (int, e.g. 2023)
def _fd_season_to_us_year(fd_season: str) -> int:
    """Convert "2324" → 2023, "2425" → 2024, "1920" → 2019"""
    return 2000 + int(fd_season[:2])


# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path(league_id: str, season: str) -> str:
    return os.path.join(CACHE_DIR, f"xg_{league_id}_{season}.json")


def _fetch_raw(league_id: str, season: str, force_refresh: bool = False) -> list | None:
    """
    Fetch raw match list from Understat for one league × season.
    Returns list of match dicts or None on failure.
    Caches JSON to disk.
    """
    cache = _cache_path(league_id, season)
    if not force_refresh and os.path.exists(cache):
        try:
            with open(cache) as f:
                data = json.load(f)
            logger.debug(f"xG cache hit: {league_id} {season} ({len(data)} matches)")
            return data
        except Exception:
            pass

    us_league = _US_LEAGUE_CODE.get(league_id)
    if us_league is None:
        logger.warning(f"No Understat league code for {league_id}")
        return None

    us_year = _fd_season_to_us_year(season)
    url = _BASE_URL.format(league=us_league, season_year=us_year)
    referer = f"https://understat.com/league/{us_league}/{us_year}"

    try:
        resp = requests.get(
            url,
            headers={**_HEADERS, "Referer": referer},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        matches = payload.get("dates", [])
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w") as f:
            json.dump(matches, f)
        logger.info(
            f"Understat xG fetched: {league_id} {season} → "
            f"{len(matches)} matches, "
            f"{sum(1 for m in matches if m.get('xG', {}).get('h'))} with xG"
        )
        time.sleep(_REQUEST_DELAY)
        return matches
    except Exception as e:
        logger.warning(f"Understat fetch failed for {league_id} {season}: {e}")
        return None


# ── Parse to DataFrame ────────────────────────────────────────────────────────

def _apply_crosswalk(name: str, league_id: str) -> str:
    cw = _CROSSWALK.get(league_id, {})
    return cw.get(name, name)


def _parse_matches(matches: list, league_id: str, season: str) -> pd.DataFrame:
    """
    Parse raw Understat match list into a join-ready DataFrame.
    Columns: game_date, home_team_fd, away_team_fd, home_xg_raw, away_xg_raw
    home_team_fd / away_team_fd are normalised to football-data.co.uk names.
    """
    rows = []
    for m in matches:
        if not m.get("isResult"):
            continue
        xg = m.get("xG", {})
        h_xg = xg.get("h")
        a_xg = xg.get("a")
        if h_xg is None or a_xg is None:
            continue

        h_name = m["h"]["title"]
        a_name = m["a"]["title"]
        dt_str = m.get("datetime", "")
        game_date = dt_str[:10] if dt_str else None

        rows.append({
            "game_date":    game_date,
            "home_team_fd": _apply_crosswalk(h_name, league_id),
            "away_team_fd": _apply_crosswalk(a_name, league_id),
            "home_xg_raw":  float(h_xg),
            "away_xg_raw":  float(a_xg),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.debug(f"Parsed xG {league_id} {season}: {len(df)} rows")
    return df


def fetch_xg_season(league_id: str, season: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch and parse xG for one league × season.
    Returns DataFrame with columns:
        game_date, home_team_fd, away_team_fd, home_xg_raw, away_xg_raw
    Returns empty DataFrame on failure.
    """
    matches = _fetch_raw(league_id, season, force_refresh=force_refresh)
    if matches is None:
        return pd.DataFrame()
    return _parse_matches(matches, league_id, season)


def fetch_xg_all(
    league_ids: list[str] | None = None,
    seasons:    list[str] | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch xG for all league × season combos.
    Returns concatenated DataFrame.
    """
    from soccer.config import ALL_SEASONS, LEAGUES

    if league_ids is None:
        league_ids = list(LEAGUES.keys())
    if seasons is None:
        seasons = ALL_SEASONS

    frames = []
    for lid in league_ids:
        for s in seasons:
            df = fetch_xg_season(lid, s, force_refresh=force_refresh)
            if not df.empty:
                df["league_id"]  = lid
                df["season_year"] = SEASON_LABELS.get(s, s)
                frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
