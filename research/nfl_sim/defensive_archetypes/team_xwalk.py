"""Canonical team abbreviation crosswalk across nflverse + Odds API.

One canonical key per franchise-season. Handles:
  JAX/JAC, LA/LAR, LV/OAK, WSH/WAS, SD/LAC, STL/LA by season.
"""
# The canonical form is the nflverse schedule abbreviation for the season.
# Any alias encountered in props/pbp/rosters is mapped to that canonical form.

_ALIASES = {
    # Jacksonville: nflverse uses JAX
    "JAC": "JAX",
    # LA Rams: nflverse uses LA; Odds API uses "Los Angeles Rams" -> LAR in some years
    "LAR": "LA",
    "STL": "LA",  # pre-2016 (St. Louis)
    # Raiders: nflverse uses LV from 2020, OAK before
    "OAK": "LV",   # mapped to LV for all seasons (franchise identity)
    # Washington: nflverse uses WAS; some sources use WSH
    "WSH": "WAS",
    # Chargers: nflverse uses LAC from 2017, SD before
    "SD": "LAC",
}

# Full-name → canonical abbreviation (Odds API names)
_FULL_TO_CANON = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
    # Historical names
    "Oakland Raiders": "LV", "Washington Football Team": "WAS",
    "Washington Redskins": "WAS", "San Diego Chargers": "LAC",
    "St. Louis Rams": "LA",
}


def canon(team, season=None):
    """Map any team identifier to the canonical abbreviation.

    Accepts: 2-3 letter abbreviation, or full name.
    """
    if not team:
        return None
    t = str(team).strip()
    # Full name first
    if t in _FULL_TO_CANON:
        return _FULL_TO_CANON[t]
    # Abbreviation alias
    t_upper = t.upper()
    if t_upper in _ALIASES:
        return _ALIASES[t_upper]
    # Already canonical
    if len(t_upper) <= 3:
        return t_upper
    return None


def canon_pair(home, away, season=None):
    """Return (canonical_home, canonical_away)."""
    return canon(home, season), canon(away, season)
