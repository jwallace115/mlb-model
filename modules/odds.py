"""
Odds module — fetches MLB totals lines from The Odds API.

Pulls full-game and F5 totals from DraftKings and FanDuel.
Cached once per day to conserve free-tier API quota (~500 req/month).

Returned structure per game:
  {
    "home_team":   "NYY",
    "away_team":   "TOR",
    "full": {
      "draftkings": {"line": 8.5, "over": -110, "under": -110},
      "fanduel":    {"line": 8.5, "over": -112, "under": -108},
      "consensus":  8.5,        # simple average of available lines
      "best_over":  {"book": "fanduel",  "line": 8.5, "odds": -108},
      "best_under": {"book": "fanduel",  "line": 8.5, "odds": -108},
    },
    "f5": { ... same shape, or None if unavailable },
  }
"""

import json
import logging
import os
from datetime import date
from typing import Optional

import requests

from config import (
    ODDS_API_KEY, ODDS_API_BASE, ODDS_BOOKMAKERS,
    ODDS_API_TEAM_MAP, CACHE_DIR,
)

logger = logging.getLogger(__name__)

_CACHE_FULL = os.path.join(CACHE_DIR, f"odds_full_{date.today().isoformat()}.json")
_CACHE_F5   = os.path.join(CACHE_DIR, f"odds_f5_{date.today().isoformat()}.json")

MLB_SPORT    = "baseball_mlb"
F5_SPORT     = "baseball_mlb"          # same sport key
FULL_MARKET  = "totals"
F5_MARKET    = "totals_1st5_innings"   # Odds API additional market key


def _load_cache(path: str) -> Optional[list]:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cache(path: str, data: list) -> None:
    with open(path, "w") as f:
        json.dump(data, f)


def _fetch_odds(market: str) -> list:
    """Raw fetch from The Odds API for one market. Returns list of game dicts."""
    url = f"{ODDS_API_BASE}/sports/{MLB_SPORT}/odds/"
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
        # Log remaining quota from response headers
        remaining = resp.headers.get("x-requests-remaining", "?")
        used      = resp.headers.get("x-requests-used", "?")
        logger.info(f"Odds API [{market}]: {resp.status_code} | quota used={used} remaining={remaining}")
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 422:
            logger.warning(f"Market '{market}' not available (422) — F5 lines may not be offered today")
        else:
            logger.error(f"Odds API error for market={market}: {e}")
        return []
    except Exception as e:
        logger.error(f"Odds API request failed for market={market}: {e}")
        return []


def _parse_book_line(market_outcomes: list) -> Optional[dict]:
    """Extract over/under line and odds from a single bookmaker's market outcomes."""
    over  = next((o for o in market_outcomes if o["name"] == "Over"),  None)
    under = next((o for o in market_outcomes if o["name"] == "Under"), None)
    if not over or not under:
        return None
    # Sanity-check: both sides should have the same point
    line = over.get("point") or under.get("point")
    if line is None:
        return None
    return {
        "line":  float(line),
        "over":  int(over["price"]),
        "under": int(under["price"]),
    }


def _best_odds(book_lines: dict, side: str) -> Optional[dict]:
    """Return the book offering the best odds for 'over' or 'under'."""
    best = None
    for book, data in book_lines.items():
        if data is None:
            continue
        odds = data[side]
        # Higher American odds = better payout
        if best is None or odds > best["odds"]:
            best = {"book": book, "line": data["line"], "odds": odds}
    return best


def _build_game_lines(raw_games: list, market_key: str) -> dict:
    """
    Convert raw Odds API response into a lookup dict:
      (home_abb, away_abb) → {draftkings: ..., fanduel: ..., consensus: ..., best_over: ..., best_under: ...}
    """
    result = {}

    for game in raw_games:
        home_name = game.get("home_team", "")
        away_name = game.get("away_team", "")
        home_abb  = ODDS_API_TEAM_MAP.get(home_name)
        away_abb  = ODDS_API_TEAM_MAP.get(away_name)

        if not home_abb or not away_abb:
            logger.debug(f"Unmapped team: home='{home_name}' away='{away_name}'")
            continue

        book_lines = {}
        for bookmaker in game.get("bookmakers", []):
            bk_key  = bookmaker["key"]
            markets = bookmaker.get("markets", [])
            market  = next((m for m in markets if m["key"] == market_key), None)
            if not market:
                continue
            parsed = _parse_book_line(market.get("outcomes", []))
            if parsed:
                book_lines[bk_key] = parsed

        if not book_lines:
            continue

        lines = [v["line"] for v in book_lines.values() if v]
        consensus = round(sum(lines) / len(lines), 1) if lines else None

        result[(home_abb, away_abb)] = {
            **book_lines,
            "consensus":  consensus,
            "best_over":  _best_odds(book_lines, "over"),
            "best_under": _best_odds(book_lines, "under"),
        }

    return result


def fetch_all_lines() -> dict:
    """
    Fetch both full-game and F5 totals. Returns a merged dict keyed by
    (home_abb, away_abb) → {"full": {...}, "f5": {...}}.
    Cached per day to preserve quota.
    """
    # --- Full game ---
    raw_full = _load_cache(_CACHE_FULL)
    if raw_full is None:
        raw_full = _fetch_odds(FULL_MARKET)
        if raw_full:
            _save_cache(_CACHE_FULL, raw_full)

    # --- F5 ---
    raw_f5 = _load_cache(_CACHE_F5)
    if raw_f5 is None:
        raw_f5 = _fetch_odds(F5_MARKET)
        if raw_f5:
            _save_cache(_CACHE_F5, raw_f5)

    full_lines = _build_game_lines(raw_full or [], FULL_MARKET)
    f5_lines   = _build_game_lines(raw_f5   or [], F5_MARKET)

    # Merge by game key
    all_keys = set(full_lines) | set(f5_lines)
    merged = {}
    for key in all_keys:
        merged[key] = {
            "home_team": key[0],
            "away_team": key[1],
            "full": full_lines.get(key),
            "f5":   f5_lines.get(key),
        }

    logger.info(f"Lines loaded: {len(merged)} games | "
                f"full={len(full_lines)} f5={len(f5_lines)}")
    return merged


def get_game_lines(home_abb: str, away_abb: str, all_lines: dict) -> dict:
    """
    Return lines for a specific game. Falls back gracefully if not found.
    """
    return all_lines.get((home_abb, away_abb), {"full": None, "f5": None})


def edge_summary(proj_total: float, line_data: Optional[dict]) -> dict:
    """
    Compute model edge vs market consensus line.
    Returns {"edge": float, "lean": str, "consensus": float, "value": bool}
    """
    if not line_data or line_data.get("consensus") is None:
        return {"edge": None, "lean": None, "consensus": None, "value": False}

    consensus = line_data["consensus"]
    edge      = round(proj_total - consensus, 2)   # positive = proj is OVER
    lean      = "OVER" if edge > 0 else "UNDER" if edge < 0 else "PUSH"
    value     = abs(edge) >= 0.5                    # configurable via EDGE_MIN_RUNS

    return {
        "edge":      edge,
        "lean":      lean,
        "consensus": consensus,
        "value":     value,
    }
