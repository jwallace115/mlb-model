"""
Shared YRFI grading utilities.
Used by yrfi_grade_backfill.py and yrfi_shadow_daily.py.
"""

import json
import time
from datetime import date, datetime

import requests

FINAL_STATUS_CODES = {"F"}

_TEAM_ABB_TO_FULL = {
    "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs", "CHW": "Chicago White Sox",
    "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies", "DET": "Detroit Tigers",
    "HOU": "Houston Astros", "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins", "NYM": "New York Mets",
    "NYY": "New York Yankees", "OAK": "Athletics",
    "PHI": "Philadelphia Phillies", "PIT": "Pittsburgh Pirates",
    "SDP": "San Diego Padres", "SFG": "San Francisco Giants",
    "SEA": "Seattle Mariners", "STL": "St. Louis Cardinals",
    "TBR": "Tampa Bay Rays", "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays", "WSN": "Washington Nationals",
}


def add_note(entry, note):
    """Add note to entry without duplicating."""
    notes = entry.get("notes", [])
    if note not in notes:
        notes.append(note)
    entry["notes"] = notes


def _normalize(name):
    return name.lower().strip().replace(" ", "").replace(".", "")


def get_schedule_for_date(game_date_str, sleep_secs=0.3):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": game_date_str,
        "fields": "dates,date,games,gamePk,teams,home,away,team,name,status,statusCode",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    time.sleep(sleep_secs)
    games = []
    for date_block in resp.json().get("dates", []):
        for game in date_block.get("games", []):
            games.append({
                "game_pk": game["gamePk"],
                "home_team": game["teams"]["home"]["team"]["name"],
                "away_team": game["teams"]["away"]["team"]["name"],
                "status_code": game.get("status", {}).get("statusCode", ""),
            })
    return games


def find_game_pk(game_date, home_team, away_team, sleep_secs=0.3):
    """Find game_pk by team name matching. Accepts abbreviations or full names."""
    games = get_schedule_for_date(game_date, sleep_secs)

    # Expand abbreviations to full names for matching
    home_full = _TEAM_ABB_TO_FULL.get(home_team, home_team)
    away_full = _TEAM_ABB_TO_FULL.get(away_team, away_team)
    home_norm = _normalize(home_full)
    away_norm = _normalize(away_full)

    for g in games:
        g_home = _normalize(g["home_team"])
        g_away = _normalize(g["away_team"])
        if g_home == home_norm and g_away == away_norm:
            return g["game_pk"], g["status_code"]
        if (home_norm in g_home or g_home in home_norm) and \
           (away_norm in g_away or g_away in away_norm):
            return g["game_pk"], g["status_code"]
    return None, None


def get_first_inning_runs(game_pk, sleep_secs=0.3):
    """Fetch linescore, return (away_1st, home_1st, status)."""
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    time.sleep(sleep_secs)
    innings = resp.json().get("innings", [])
    if not innings:
        return None, None, "NO_INNINGS_DATA"
    first = innings[0]
    away = first.get("away", {}).get("runs")
    home = first.get("home", {}).get("runs")
    if away is None or home is None:
        return None, None, "MISSING_RUN_DATA"
    return int(away), int(home), "OK"


def compute_profit(result_yrfi, fd_yrfi_price):
    if fd_yrfi_price is None:
        return None
    if result_yrfi == 1:
        if fd_yrfi_price > 0:
            return round(fd_yrfi_price / 100, 4)
        else:
            return round(100 / abs(fd_yrfi_price), 4)
    elif result_yrfi == 0:
        return -1.0
    return None


def grade_entry(entry, sleep_secs=0.3):
    """Grade one shadow log entry. Never overwrites result_graded=True."""
    if entry.get("result_graded") is True:
        return entry

    game_date = entry.get("game_date")
    home_team = entry.get("home_team")
    away_team = entry.get("away_team")

    if not all([game_date, home_team, away_team]):
        add_note(entry, "GRADE_SKIP_MISSING_FIELDS")
        return entry

    try:
        game_dt = datetime.strptime(game_date, "%Y-%m-%d").date()
        if game_dt >= date.today():
            add_note(entry, "GRADE_PENDING_FUTURE_GAME")
            return entry
    except ValueError:
        add_note(entry, "GRADE_SKIP_BAD_DATE")
        return entry

    try:
        game_pk, status_code = find_game_pk(
            game_date, home_team, away_team, sleep_secs)
    except Exception as e:
        add_note(entry, f"GRADE_SKIP_API_ERROR_{str(e)[:40]}")
        return entry

    if game_pk is None:
        add_note(entry, "GRADE_SKIP_GAME_PK_NOT_FOUND")
        return entry

    if status_code not in FINAL_STATUS_CODES:
        add_note(entry, f"GRADE_PENDING_STATUS_{status_code}")
        return entry

    try:
        away_1st, home_1st, status = get_first_inning_runs(game_pk, sleep_secs)
    except Exception as e:
        add_note(entry, f"GRADE_SKIP_LINESCORE_ERROR_{str(e)[:40]}")
        return entry

    if status != "OK":
        add_note(entry, f"GRADE_SKIP_{status}")
        return entry

    total_1st = away_1st + home_1st
    result_yrfi = 1 if total_1st > 0 else 0
    fd_price = entry.get("fd_yrfi_price")
    profit = compute_profit(result_yrfi, fd_price)

    entry["away_1st_runs"] = away_1st
    entry["home_1st_runs"] = home_1st
    entry["total_1st_runs"] = total_1st
    entry["result_yrfi"] = result_yrfi
    entry["result_graded"] = True
    entry["graded_date"] = date.today().isoformat()
    entry["yrfi_profit_units"] = profit
    return entry
