"""
Props odds module — fetch pitcher K and batter TB lines.

Primary source  : DraftKings public sportsbook API
Fallback source : The Odds API (pitcher_strikeouts / batter_total_bases)

Returns dict keyed by player name.lower():
    {
        "k":  float | None,   # strikeout total line
        "tb": float | None,   # total bases line
    }
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# DraftKings MLB event group — regular season (may need updating each season)
DK_MLB_EVENT_GROUP = 84240
DK_API_URL = (
    f"https://sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups"
    f"/{DK_MLB_EVENT_GROUP}/categories/{{category_id}}/subcategories/{{subcategory_id}}"
)
# Fallback: simpler full event group endpoint (works without category ids)
DK_FULL_URL = (
    f"https://sportsbook-nash.draftkings.com/api/v2/eventgroup/{DK_MLB_EVENT_GROUP}/full"
)

# The Odds API
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb/events"
ODDS_API_PROP_MARKETS = "pitcher_strikeouts,batter_total_bases"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _norm_name(raw: str) -> str:
    """Normalise a player name: strip HTML entities, collapse whitespace."""
    s = re.sub(r"<[^>]+>", "", raw or "")
    return " ".join(s.split()).strip()


# ── DraftKings scraper ────────────────────────────────────────────────────────────

def _fetch_dk_props(home_team: str, away_team: str) -> dict:
    """
    Scrape DraftKings public API for the matching MLB game.
    Returns {player_name.lower(): {"k": float|None, "tb": float|None}}.
    """
    result: dict[str, dict] = {}
    try:
        resp = requests.get(DK_FULL_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.debug(f"DK full endpoint failed: {e}")
        return result

    # Navigate to events list
    events = (
        data.get("eventGroup", {})
            .get("offerCategories", [])
    )
    # Alternatively the response may be structured differently; try both shapes
    raw_events = (
        data.get("events")
        or data.get("eventGroup", {}).get("events")
        or []
    )

    # Find the game matching home/away teams (case-insensitive substring match)
    ht = home_team.lower()
    at = away_team.lower()

    target_event_id = None
    for ev in raw_events:
        name = (ev.get("name") or "").lower()
        teams = [t.lower() for t in (ev.get("teamNames") or [])]
        if (ht in name or any(ht in t for t in teams)) and \
           (at in name or any(at in t for t in teams)):
            target_event_id = ev.get("id") or ev.get("eventId")
            break

    if target_event_id is None:
        logger.debug(f"DK: could not find event for {away_team}@{home_team}")
        return result

    # Find offers for this event
    offers = (
        data.get("eventGroup", {})
            .get("offers", [])
    ) or []
    # Some response shapes nest offers under each event
    event_offers = []
    for ev in raw_events:
        if (ev.get("id") or ev.get("eventId")) == target_event_id:
            event_offers = ev.get("offers") or ev.get("displayGroups") or []
            break

    all_offers = list(offers) + list(event_offers)

    # Parse K and TB markets
    for offer in all_offers:
        label = (offer.get("label") or offer.get("name") or "").lower()
        is_k  = "strikeout" in label
        is_tb = "total base" in label

        if not (is_k or is_tb):
            continue

        outcomes = offer.get("outcomes") or []
        for oc in outcomes:
            player = _norm_name(oc.get("participant") or oc.get("label") or "")
            if not player:
                continue
            key   = player.lower()
            line  = _safe_float(oc.get("line") or oc.get("handicap") or oc.get("points"))
            if line is None:
                continue

            if key not in result:
                result[key] = {"k": None, "tb": None}
            if is_k:
                result[key]["k"] = line
            elif is_tb:
                result[key]["tb"] = line

    logger.info(f"DK props: {len(result)} players for {away_team}@{home_team}")
    return result


# ── The Odds API fallback ─────────────────────────────────────────────────────────

def _fetch_odds_api_props(
    home_team: str,
    away_team: str,
    game_date: str,
    odds_api_key: Optional[str],
) -> dict:
    """Fetch props from The Odds API (requires key; player props tier)."""
    if not odds_api_key:
        return {}

    result: dict[str, dict] = {}
    try:
        # Step 1: find event id
        resp = requests.get(
            f"{ODDS_API_BASE}",
            params={
                "apiKey":      odds_api_key,
                "sport":       "baseball_mlb",
                "dateFormat":  "iso",
                "commenceTimeFrom": f"{game_date}T00:00:00Z",
                "commenceTimeTo":   f"{game_date}T23:59:59Z",
            },
            timeout=15,
        )
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        logger.debug(f"Odds API event list failed: {e}")
        return result

    ht = home_team.lower()
    at = away_team.lower()
    event_id = None
    for ev in events:
        if (ht in (ev.get("home_team") or "").lower() or
                ht in (ev.get("away_team") or "").lower()):
            if (at in (ev.get("home_team") or "").lower() or
                    at in (ev.get("away_team") or "").lower()):
                event_id = ev.get("id")
                break

    if not event_id:
        return result

    # Step 2: fetch player prop markets for this event
    try:
        resp2 = requests.get(
            f"{ODDS_API_BASE}/{event_id}/odds",
            params={
                "apiKey":  odds_api_key,
                "markets": ODDS_API_PROP_MARKETS,
                "regions": "us",
                "oddsFormat": "american",
            },
            timeout=15,
        )
        resp2.raise_for_status()
        ev_data = resp2.json()
    except Exception as e:
        logger.debug(f"Odds API props fetch failed: {e}")
        return result

    bookmakers = ev_data.get("bookmakers") or []
    for bk in bookmakers:
        for mkt in (bk.get("markets") or []):
            mkt_key = mkt.get("key") or ""
            is_k    = "strikeout" in mkt_key
            is_tb   = "total_base" in mkt_key
            if not (is_k or is_tb):
                continue
            for outcome in (mkt.get("outcomes") or []):
                player = _norm_name(outcome.get("description") or outcome.get("name") or "")
                if not player:
                    continue
                pt   = _safe_float(outcome.get("point"))
                name = (outcome.get("name") or "").lower()
                if pt is None or name not in ("over", "under"):
                    continue
                key = player.lower()
                if key not in result:
                    result[key] = {"k": None, "tb": None}
                # Use the "over" line as the standard line
                if name == "over":
                    if is_k:
                        result[key]["k"]  = pt
                    elif is_tb:
                        result[key]["tb"] = pt

    logger.info(f"Odds API props: {len(result)} players for {away_team}@{home_team}")
    return result


# ── Public entry point ────────────────────────────────────────────────────────────

def fetch_props_lines(
    home_team: str,
    away_team: str,
    game_date: str,
    odds_api_key: Optional[str] = None,
) -> dict:
    """
    Fetch player prop lines for a single game.

    Tries DraftKings first; if it returns nothing falls back to The Odds API.

    Returns
    -------
    dict  — keyed by player_name.lower():
            {"k": float|None, "tb": float|None}
    """
    lines = _fetch_dk_props(home_team, away_team)
    if not lines and odds_api_key:
        lines = _fetch_odds_api_props(home_team, away_team, game_date, odds_api_key)
    return lines
