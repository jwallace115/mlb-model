"""
Bullpen fatigue module — uses MLB Stats API boxscores to measure
how much relievers have been used over the past 2 days.

Part A: Team bullpen xFIP baseline from the pitcher_db (replaces static 4.10/4.25).
Part B: Tier-1 arm availability — if 2+ of the top-3 relievers threw 30+ pitches
        in the last 48h, apply a collapse multiplier of 1.25 instead of standard fatigue.

Fatigue score: 0.0 (fully rested) -> 1.0 (heavily used)
"""

import logging
from datetime import date, timedelta
from typing import Optional

import requests

from config import MLB_STATS_API, BULLPEN_FATIGUE_PER_INNING, BULLPEN_MAX_FATIGUE_MULTIPLIER, LEAGUE_AVG_ERA

logger = logging.getLogger(__name__)

TIER1_RED_PITCHES   = 30    # pitches in 48h that marks a Tier-1 arm as RED
TIER1_COLLAPSE_MULT = 1.25  # multiplier when 2+ Tier-1 arms are RED
TIER1_RED_THRESHOLD = 2     # number of RED Tier-1 arms to trigger collapse


def _get(endpoint: str, params: dict = None) -> dict:
    url = f"{MLB_STATS_API}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _innings_from_str(ip_str) -> float:
    try:
        ip = float(ip_str)
        whole = int(ip)
        partial = ip - whole
        return whole + (partial / 3) * (10 / 3)
    except Exception:
        return 0.0


def _get_boxscore(game_pk: int) -> dict:
    try:
        return _get(f"game/{game_pk}/boxscore")
    except Exception as e:
        logger.warning(f"Boxscore fetch failed for game_pk={game_pk}: {e}")
        return {}


def _extract_reliever_data(boxscore: dict, is_home: bool) -> tuple[float, dict]:
    """
    Returns (total_reliever_innings, {player_id: pitches_thrown}).
    Excludes the starting pitcher if they threw 4+ innings.
    """
    side      = "home" if is_home else "away"
    team_data = boxscore.get("teams", {}).get(side, {})
    pitchers  = team_data.get("pitchers", [])
    players   = team_data.get("players", {})

    total_innings  = 0.0
    pitches_by_id  = {}

    for i, pid in enumerate(pitchers):
        player_key = f"ID{pid}"
        player     = players.get(player_key, {})
        stats      = player.get("stats", {}).get("pitching", {})
        ip_str     = stats.get("inningsPitched", "0")
        ip         = _innings_from_str(ip_str)
        pitches    = int(stats.get("numberOfPitches", 0) or 0)

        if i == 0 and ip >= 4.0:
            continue  # skip normal starter

        total_innings += ip
        if pitches > 0:
            pitches_by_id[str(pid)] = pitches_by_id.get(str(pid), 0) + pitches

    return total_innings, pitches_by_id


def _get_recent_game_pks(team_id: int, days: int = 2) -> list[int]:
    today      = date.today()
    start_date = (today - timedelta(days=days)).isoformat()
    end_date   = (today - timedelta(days=1)).isoformat()

    try:
        data = _get(
            "schedule",
            params={
                "sportId":   1,
                "teamId":    team_id,
                "startDate": start_date,
                "endDate":   end_date,
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


def build_team_bullpen_db(pitcher_db: dict) -> dict:
    """
    Build a team -> avg reliever xFIP map from the pitcher_db.
    Only uses pitchers with GS < 3 (relievers) and BF >= 20.
    Returns dict: team_abb -> {"avg_xfip": float, "top3_ids": list[str]}
    """
    team_data: dict = {}  # team -> list of {xfip, mlbam_id}
    seen_names: set = set()

    for key, entry in pitcher_db.items():
        if key.isdigit() or key.startswith("fg:") or key == "_meta":
            continue
        name = entry.get("name") or key
        if name in seen_names:
            continue
        seen_names.add(name)

        team = (entry.get("team") or "").upper()
        gs   = entry.get("gs")
        bf   = entry.get("bf") or 0

        # Skip: starters (gs >= 3), unknown gs (Savant fallback), thin samples
        if not team or gs is None or gs >= 3 or bf < 20:
            continue

        xfip     = entry.get("xfip", LEAGUE_AVG_ERA)
        mlbam_id = entry.get("mlbam_id")
        team_data.setdefault(team, []).append({"xfip": xfip, "mlbam_id": mlbam_id})

    result = {}
    for team, arms in team_data.items():
        if len(arms) < 2:
            continue
        arms.sort(key=lambda a: a["xfip"])
        avg_xfip = round(sum(a["xfip"] for a in arms) / len(arms), 3)
        top3_ids = [a["mlbam_id"] for a in arms[:3] if a["mlbam_id"]]
        result[team] = {"avg_xfip": avg_xfip, "top3_ids": top3_ids}

    logger.info(f"Team bullpen DB built: {len(result)} teams")
    return result


def calculate_bullpen_fatigue(
    team_id: int,
    is_home: bool,
    team_abb: str = "",
    team_bullpen_db: Optional[dict] = None,
) -> dict:
    """
    Calculate bullpen fatigue + quality for a team over the last 2 days.

    Part A: Uses team_bullpen_db for a live xFIP baseline (replaces static 4.10/4.25).
    Part B: Checks if 2+ Tier-1 arms are RED (30+ pitches in 48h) -> collapse multiplier.

    Returns:
        {
          fatigue_score, innings_used, fatigue_multiplier,
          team_xfip, tier1_red_arms, collapse_triggered, game_pks
        }
    """
    game_pks = _get_recent_game_pks(team_id, days=2)

    total_reliever_innings = 0.0
    all_pitches: dict = {}   # player_id (str) -> total pitches thrown in last 48h

    for gk in game_pks:
        box = _get_boxscore(gk)
        if not box:
            continue
        home_id       = box.get("teams", {}).get("home", {}).get("team", {}).get("id")
        this_is_home  = (home_id == team_id)
        inn, pitches  = _extract_reliever_data(box, this_is_home)
        total_reliever_innings += inn
        for pid, p in pitches.items():
            all_pitches[pid] = all_pitches.get(pid, 0) + p

    # Part A — team bullpen xFIP baseline
    team_xfip = LEAGUE_AVG_ERA  # default (league average)
    top3_ids  = []
    if team_bullpen_db and team_abb:
        team_entry = team_bullpen_db.get(team_abb.upper(), {})
        if team_entry:
            team_xfip = team_entry.get("avg_xfip", LEAGUE_AVG_ERA)
            top3_ids  = team_entry.get("top3_ids", [])

    # Part B — Tier-1 arm RED flag
    red_arms = sum(
        1 for pid in top3_ids
        if all_pitches.get(str(pid), 0) >= TIER1_RED_PITCHES
    )
    collapse_triggered = red_arms >= TIER1_RED_THRESHOLD

    # --- Fatigue score and multiplier ---
    max_expected = 6.0
    raw_score    = total_reliever_innings * BULLPEN_FATIGUE_PER_INNING
    fatigue_score = min(raw_score / max_expected, 1.0) if max_expected > 0 else 0.0

    if collapse_triggered:
        # Tier-1 collapse overrides standard fatigue
        fatigue_multiplier = TIER1_COLLAPSE_MULT
    else:
        # Standard: scale bullpen ERA relative to team's actual bullpen quality
        bp_era_ratio      = team_xfip / LEAGUE_AVG_ERA   # > 1 = worse bullpen
        standard_mult     = 1.0 + fatigue_score * (BULLPEN_MAX_FATIGUE_MULTIPLIER - 1.0)
        fatigue_multiplier = standard_mult * bp_era_ratio

    # Cap the multiplier to prevent runaway projections
    fatigue_multiplier = min(fatigue_multiplier, BULLPEN_MAX_FATIGUE_MULTIPLIER * 1.1)

    if collapse_triggered:
        logger.info(f"  [{team_abb}] BULLPEN COLLAPSE: {red_arms} Tier-1 arms RED "
                    f"(mult={fatigue_multiplier:.3f})")
    elif red_arms > 0:
        logger.info(f"  [{team_abb}] {red_arms} Tier-1 arm(s) RED but below collapse threshold")

    return {
        "fatigue_score":       round(fatigue_score, 3),
        "innings_used":        round(total_reliever_innings, 1),
        "fatigue_multiplier":  round(fatigue_multiplier, 3),
        "team_xfip":           round(team_xfip, 3),
        "tier1_red_arms":      red_arms,
        "collapse_triggered":  collapse_triggered,
        "game_pks":            game_pks,
    }
