"""
NBA odds — fetches full-game and H1 totals from The Odds API.

Sport key: basketball_nba
Full game : market = totals
H1        : market = h1_totals  (graceful 422 fallback if not available)

Cached once per day to conserve free-tier quota (~500 req/month shared with MLB).

Returned structure per game:
  {
    "home_team": "BOS",
    "away_team": "NYK",
    "full": {
      "draftkings": {"line": 224.5, "over": -110, "under": -110},
      "fanduel":    {"line": 224.5, "over": -112, "under": -108},
      "consensus":  224.5,
      "best_over":  {"book": "fanduel", "line": 224.5, "odds": -108},
      "best_under": {"book": "fanduel", "line": 224.5, "odds": -108},
    },
    "h1": { ... same shape, or None if unavailable },
  }
"""

import json
import logging
import os
from datetime import date
from typing import Optional

import requests

from nba.config import (
    CACHE_DIR,
    ODDS_API_KEY,
    ODDS_API_BASE,
    ODDS_BOOKMAKERS,
    NBA_ODDS_TEAM_MAP,
)

logger = logging.getLogger(__name__)

_TODAY = date.today().isoformat()
_CACHE_FULL = os.path.join(CACHE_DIR, f"nba_odds_full_{_TODAY}.json")
_CACHE_H1   = os.path.join(CACHE_DIR, f"nba_odds_h1_{_TODAY}.json")

NBA_SPORT    = "basketball_nba"
FULL_MARKET  = "totals"
H1_MARKET    = "h1_totals"


def _load_cache(path: str) -> Optional[list]:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cache(path: str, data: list) -> None:
    with open(path, "w") as f:
        json.dump(data, f)


def _fetch_odds(market: str) -> list:
    """Raw fetch from The Odds API for one market."""
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set — skipping NBA odds fetch")
        return []
    url = f"{ODDS_API_BASE}/sports/{NBA_SPORT}/odds/"
    params = {
        "apiKey":      ODDS_API_KEY,
        "regions":     "us",
        "markets":     market,
        "bookmakers":  ",".join(ODDS_BOOKMAKERS),
        "oddsFormat":  "american",
        "dateFormat":  "iso",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        remaining = resp.headers.get("x-requests-remaining", "?")
        used      = resp.headers.get("x-requests-used", "?")
        logger.info(f"NBA Odds API [{market}]: OK | used={used} remaining={remaining}")
        return resp.json()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 422:
            logger.info(f"NBA Odds API [{market}]: No H1 lines available today")
        else:
            logger.warning(f"NBA Odds API error [{market}]: {e}")
        return []
    except Exception as e:
        logger.warning(f"NBA Odds API fetch failed [{market}]: {e}")
        return []


def _norm_book(name: str) -> str:
    return name.lower().replace(" ", "")


def _parse_game(raw: dict, market: str) -> Optional[dict]:
    """Parse one Odds API game dict into our canonical structure."""
    home_raw = raw.get("home_team", "")
    away_raw = raw.get("away_team", "")
    home = NBA_ODDS_TEAM_MAP.get(home_raw, home_raw)
    away = NBA_ODDS_TEAM_MAP.get(away_raw, away_raw)
    if not home or not away:
        return None

    book_data = {}
    for bookmaker in (raw.get("bookmakers") or []):
        book_key = _norm_book(bookmaker.get("key", ""))
        if book_key not in ("draftkings", "fanduel"):
            continue
        for mkt in (bookmaker.get("markets") or []):
            if mkt.get("key") != market:
                continue
            outcomes = {o["name"].lower(): o for o in (mkt.get("outcomes") or [])}
            over_o  = outcomes.get("over")
            under_o = outcomes.get("under")
            if over_o and under_o:
                book_data[book_key] = {
                    "line":  over_o.get("point"),
                    "over":  over_o.get("price"),
                    "under": under_o.get("price"),
                }

    if not book_data:
        return None

    lines = [v["line"] for v in book_data.values() if v.get("line") is not None]
    consensus = round(sum(lines) / len(lines), 1) if lines else None

    def _best(side: str) -> Optional[dict]:
        best = None
        for book, d in book_data.items():
            odds = d.get(side)
            if odds is None:
                continue
            if best is None or odds > best["odds"]:
                best = {"book": book, "line": d.get("line"), "odds": odds}
        return best

    return {
        "home_team": home,
        "away_team": away,
        "market":    market,
        "books":     book_data,
        "consensus": consensus,
        "best_over":  _best("over"),
        "best_under": _best("under"),
    }


def _fetch_market(market: str, cache_path: str) -> list:
    cached = _load_cache(cache_path)
    if cached is not None:
        logger.info(f"Using cached NBA odds [{market}] ({len(cached)} games)")
        return cached

    raw_games = _fetch_odds(market)
    parsed = []
    for g in raw_games:
        p = _parse_game(g, market)
        if p:
            parsed.append(p)
    _save_cache(cache_path, parsed)
    logger.info(f"Cached {len(parsed)} NBA games [{market}]")
    return parsed


def fetch_all_nba_lines() -> dict:
    """
    Fetch full-game and H1 NBA lines.
    Returns {"full": [...], "h1": [...]} where each list has parsed game dicts.
    """
    full = _fetch_market(FULL_MARKET, _CACHE_FULL)
    h1   = _fetch_market(H1_MARKET,   _CACHE_H1)
    return {"full": full, "h1": h1}


def get_game_lines(home: str, away: str, all_lines: dict) -> dict:
    """
    Look up market lines for a specific game by home/away team abbreviation.
    Returns {"full": {...} or None, "h1": {...} or None}.
    """
    def _find(pool: list) -> Optional[dict]:
        for g in pool:
            if g.get("home_team") == home and g.get("away_team") == away:
                return g
            # Reverse check (sometimes home/away flipped)
            if g.get("home_team") == away and g.get("away_team") == home:
                return g
        return None

    return {
        "full": _find(all_lines.get("full", [])),
        "h1":   _find(all_lines.get("h1",   [])),
    }
