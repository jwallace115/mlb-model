"""
game_starters.py — fetch actual starting pitchers from historical MLB boxscores.

For each game_pk, calls GET /api/v1/game/{pk}/boxscore and extracts the first
pitcher listed for each team as the game's actual starter.  Pitcher handedness
(throws) is batch-fetched from the MLB Stats API people endpoint.

Cache: sim/data/cache/starters_{year}.json — keyed by game_pk (str).
       sim/data/cache/pitcher_throws.json  — persistent cross-year throws map.

Usage:
    from sim.modules.game_starters import load_season_starters
    starters = load_season_starters(2024, game_pks)
    # Returns dict: game_pk(int) → {"home": {...}, "away": {...}}
"""

import json
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MLB_STATS_API = "https://statsapi.mlb.com/api/v1"
SIM_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")

# Rate-limit: stay comfortably within MLB Stats API free-tier limits
_REQUEST_DELAY = 0.25   # seconds between boxscore fetches
_BATCH_SIZE    = 200    # pitcher IDs per /people request


def _cache_path_starters(year: int) -> str:
    return os.path.join(SIM_CACHE_DIR, f"starters_{year}.json")


def _cache_path_throws() -> str:
    return os.path.join(SIM_CACHE_DIR, "pitcher_throws.json")


def _load_throws_cache() -> dict[str, str]:
    path = _cache_path_throws()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_throws_cache(cache: dict[str, str]) -> None:
    with open(_cache_path_throws(), "w") as f:
        json.dump(cache, f)


def _get_boxscore(game_pk: int) -> dict:
    """Fetch boxscore from MLB Stats API."""
    url = f"{MLB_STATS_API}/game/{game_pk}/boxscore"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Boxscore fetch failed game_pk={game_pk}: {e}")
        return {}


def _extract_starter(boxscore: dict, side: str) -> Optional[dict]:
    """
    Extract the first pitcher from the given side's pitching list.
    Returns dict with id, name, ip_pitched, or None if unavailable.
    """
    team_data = boxscore.get("teams", {}).get(side, {})
    pitchers  = team_data.get("pitchers", [])
    players   = team_data.get("players", {})

    if not pitchers:
        return None

    sp_id  = pitchers[0]
    player = players.get(f"ID{sp_id}", {})
    name   = player.get("person", {}).get("fullName", "")
    stats  = player.get("stats", {}).get("pitching", {})

    ip_str = stats.get("inningsPitched", "0") or "0"
    try:
        ip = float(ip_str)
    except ValueError:
        ip = 0.0

    return {
        "id":         sp_id,
        "name":       name,
        "ip_pitched": round(ip, 1),
    }


def _batch_fetch_throws(pitcher_ids: list[int],
                        existing: dict[str, str]) -> dict[str, str]:
    """
    Fetch pitchHand for all ids not already in existing cache.
    Returns updated dict: str(player_id) → "L" | "R".
    """
    missing = [i for i in pitcher_ids if str(i) not in existing]
    if not missing:
        return existing

    throws = dict(existing)
    total  = len(missing)
    logger.info(f"Fetching throws for {total} pitchers from MLB Stats API...")

    for start in range(0, total, _BATCH_SIZE):
        batch = missing[start : start + _BATCH_SIZE]
        ids_str = ",".join(str(i) for i in batch)
        try:
            resp = requests.get(
                f"{MLB_STATS_API}/people",
                params={"personIds": ids_str,
                        "fields": "people,id,pitchHand,code"},
                timeout=20,
            )
            resp.raise_for_status()
            for person in resp.json().get("people", []):
                pid = person.get("id")
                hand = (person.get("pitchHand") or {}).get("code", "R")
                if pid:
                    throws[str(pid)] = hand
        except Exception as e:
            logger.warning(f"Throws batch fetch failed (ids {batch[:3]}...): {e}")
        time.sleep(0.1)

    # Default any still-missing to "R" (league-common)
    for i in missing:
        if str(i) not in throws:
            throws[str(i)] = "R"

    return throws


def fetch_season_starters(year: int, game_pks: list[int]) -> dict[int, dict]:
    """
    Fetch actual starting pitchers for every game_pk in the list.
    Caches results to sim/data/cache/starters_{year}.json.

    Returns:
        dict[game_pk(int)] → {
            "home": {"id": int, "name": str, "ip_pitched": float, "throws": str},
            "away": {"id": int, "name": str, "ip_pitched": float, "throws": str},
        }
    """
    cache_path = _cache_path_starters(year)
    existing: dict[str, dict] = {}

    # Load any partial cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                existing = json.load(f)
            logger.info(f"Loaded {len(existing)} cached starters for {year}")
        except Exception:
            existing = {}

    cached_pks = {int(k) for k in existing}
    missing_pks = [pk for pk in game_pks if pk not in cached_pks]

    if missing_pks:
        logger.info(f"Fetching boxscores for {len(missing_pks)} games ({year})...")
        for i, pk in enumerate(missing_pks):
            if i % 100 == 0 and i > 0:
                logger.info(f"  ... {i}/{len(missing_pks)} complete, saving cache")
                with open(cache_path, "w") as f:
                    json.dump(existing, f)

            box = _get_boxscore(pk)
            if not box:
                continue

            home_sp = _extract_starter(box, "home")
            away_sp = _extract_starter(box, "away")
            if home_sp and away_sp:
                existing[str(pk)] = {"home": home_sp, "away": away_sp}

            time.sleep(_REQUEST_DELAY)

        logger.info(f"Boxscore fetch complete: {len(existing)} games cached for {year}")
        with open(cache_path, "w") as f:
            json.dump(existing, f)

    # Collect all unique pitcher IDs for throws lookup
    all_pitcher_ids: list[int] = []
    for entry in existing.values():
        for side in ("home", "away"):
            sp = entry.get(side, {})
            if sp.get("id"):
                all_pitcher_ids.append(int(sp["id"]))

    throws_cache = _load_throws_cache()
    throws_cache  = _batch_fetch_throws(all_pitcher_ids, throws_cache)
    _save_throws_cache(throws_cache)

    # Build final dict with throws attached
    result: dict[int, dict] = {}
    for pk_str, entry in existing.items():
        pk = int(pk_str)
        game_entry = {}
        for side in ("home", "away"):
            sp = entry.get(side, {})
            if sp:
                sp_id = sp.get("id")
                game_entry[side] = {
                    "id":         int(sp_id) if sp_id else None,
                    "name":       sp.get("name", ""),
                    "ip_pitched": sp.get("ip_pitched", 0.0),
                    "throws":     throws_cache.get(str(sp_id), "R") if sp_id else "R",
                }
        if "home" in game_entry and "away" in game_entry:
            result[pk] = game_entry

    logger.info(f"Season {year} starters ready: {len(result)} games")
    return result


def load_season_starters(year: int, game_pks: list[int]) -> dict[int, dict]:
    """Public entry point — alias for fetch_season_starters."""
    return fetch_season_starters(year, game_pks)
