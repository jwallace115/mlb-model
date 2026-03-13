"""
MLB transaction wire — fetch and filter same-day IL/roster moves.

Relevant for the model:
  - IL placements (player suddenly unavailable)
  - Activations from IL (player returning)
  - Recalls from minors (roster depth move)
  - Options to minors (player unavailable)
  - Designations for assignment (DFA)

Filters to MLB-level teams only (ignores all minor-league-only transactions).
Tags each transaction with the affected today's game if any.

Degrades gracefully — returns [] on any API failure.
"""

import logging
from typing import Optional

import requests

from config import MLB_STATS_API, TEAM_ID_TO_ABB

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "mlb-model/1.0"}

# MLB team IDs — anything outside this set is a minor-league transaction
_MLB_TEAM_IDS = set(TEAM_ID_TO_ABB.keys())

# TypeCodes to surface (description text used to filter within each code)
_RELEVANT_TYPE_CODES = {"SC", "CU", "OPT", "DES", "SE", "TR", "ASG"}

# Keywords in description that make a transaction worth surfacing
_RELEVANT_KEYWORDS = (
    " IL ",      "10-Day",   "15-Day",   "60-Day",
    "Injured",   "paternity","bereavement",
    "placed",    "activated","recalled", "recalled from",
    "optioned",  "designated for assignment", "selected",
    "traded",    "acquired", "rehab",
)

# TypeCodes that are always relevant regardless of description
_ALWAYS_SHOW = {"DES", "TR"}

# Brief human-readable label by typeCode
_TYPE_LABELS = {
    "SC":  "Status Change",
    "CU":  "Recalled",
    "OPT": "Optioned",
    "DES": "DFA",
    "SE":  "Selected",
    "TR":  "Trade",
    "ASG": "Rehab Assignment",
}


def _is_mlb_relevant(txn: dict) -> bool:
    """True if this transaction involves at least one MLB-level team."""
    to_id   = (txn.get("toTeam")   or {}).get("id")
    from_id = (txn.get("fromTeam") or {}).get("id")
    return bool(
        (to_id   and to_id   in _MLB_TEAM_IDS) or
        (from_id and from_id in _MLB_TEAM_IDS)
    )


def _is_model_relevant(txn: dict) -> bool:
    """True if the description or type code indicates a roster impact."""
    tc   = txn.get("typeCode", "")
    desc = txn.get("description", "").lower()
    if tc in _ALWAYS_SHOW:
        return True
    if tc not in _RELEVANT_TYPE_CODES:
        return False
    return any(kw.lower() in desc for kw in _RELEVANT_KEYWORDS)


def _mlb_team_abb(team_id: Optional[int]) -> Optional[str]:
    if team_id is None:
        return None
    return TEAM_ID_TO_ABB.get(team_id)


def fetch_transactions(game_date: str) -> list[dict]:
    """
    Fetch all transactions for game_date from MLB Stats API.
    Returns raw list; empty list on error.
    """
    try:
        url  = f"{MLB_STATS_API}/transactions"
        resp = requests.get(
            url,
            params={"startDate": game_date, "endDate": game_date},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        txns = resp.json().get("transactions", [])
        logger.info(f"Fetched {len(txns)} raw transactions for {game_date}")
        return txns
    except Exception as e:
        logger.warning(f"fetch_transactions({game_date}) failed: {e}")
        return []


def filter_to_model_relevant(
    transactions: list[dict],
    games: list[dict],
) -> list[dict]:
    """
    Keep only MLB-level, model-relevant transactions and annotate each
    with which of today's games (if any) it affects.

    Parameters
    ----------
    transactions : raw list from fetch_transactions()
    games        : list of game dicts from fetch_schedule() — must have
                   home_team_id, away_team_id, home_team, away_team, game_pk

    Returns
    -------
    List of cleaned transaction dicts:
        {
          transaction_id,
          player_name, player_id,
          team_name, team_id, team_abb,
          type_code, type_label, description,
          affects_game_pk,   # None if player's team not in today's slate
          affects_team,      # abbreviation
          affects_matchup,   # "MIL @ CLE" or None
        }
    """
    # Build team_id → game lookup for today's slate
    team_id_to_game: dict[int, dict] = {}
    for g in games:
        for key in ("home_team_id", "away_team_id"):
            tid = g.get(key)
            if tid:
                team_id_to_game[tid] = g

    result = []
    for txn in transactions:
        if not _is_mlb_relevant(txn):
            continue
        if not _is_model_relevant(txn):
            continue

        to_id   = (txn.get("toTeam")   or {}).get("id")
        from_id = (txn.get("fromTeam") or {}).get("id")

        # The "primary" MLB team for this transaction
        mlb_team_id   = from_id if from_id in _MLB_TEAM_IDS else to_id
        mlb_team_name = (
            (txn.get("fromTeam") or {}).get("name") if from_id in _MLB_TEAM_IDS
            else (txn.get("toTeam") or {}).get("name")
        )
        team_abb  = _mlb_team_abb(mlb_team_id)

        # Does this team play today?
        affected_game = team_id_to_game.get(mlb_team_id)

        tc    = txn.get("typeCode", "")
        label = _TYPE_LABELS.get(tc, txn.get("typeDesc", tc))

        result.append({
            "transaction_id": txn.get("id"),
            "player_name":    (txn.get("person") or {}).get("fullName"),
            "player_id":      (txn.get("person") or {}).get("id"),
            "team_name":      mlb_team_name,
            "team_id":        mlb_team_id,
            "team_abb":       team_abb,
            "type_code":      tc,
            "type_label":     label,
            "description":    txn.get("description", ""),
            "affects_game_pk": affected_game["game_pk"] if affected_game else None,
            "affects_team":    team_abb if affected_game else None,
            "affects_matchup": (
                f"{affected_game['away_team']} @ {affected_game['home_team']}"
                if affected_game else None
            ),
        })

    logger.info(
        f"Filtered to {len(result)} model-relevant transactions "
        f"({sum(1 for r in result if r['affects_game_pk'])} affect today's games)"
    )
    return result
