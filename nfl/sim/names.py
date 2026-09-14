#!/usr/bin/env python3
"""
NFL Sim — Player name -> player_id resolver.

Matches props-archive player names to nflverse gsis_id via rosters_weekly.
Normalises both sides: lowercase, strip accents, strip punctuation,
strip suffixes (Jr, Sr, II, III, IV, V), collapse whitespace.

Match order:
  1. Exact full-name match on a candidate team
  2. Unique first-initial + last-name match on a candidate team
  3. Unique full-name match league-wide
  4. Unresolved
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent

# Full team name -> abbreviation (verified against props archive 2024 + 2026)
FULL_TO_ABBR = {
    'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL',
    'Baltimore Ravens': 'BAL', 'Buffalo Bills': 'BUF',
    'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE',
    'Dallas Cowboys': 'DAL', 'Denver Broncos': 'DEN',
    'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND',
    'Jacksonville Jaguars': 'JAX', 'Kansas City Chiefs': 'KC',
    'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LA', 'Miami Dolphins': 'MIA',
    'Minnesota Vikings': 'MIN', 'New England Patriots': 'NE',
    'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI',
    'Pittsburgh Steelers': 'PIT', 'San Francisco 49ers': 'SF',
    'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS',
}

_SUFFIX_RE = re.compile(
    r'\s+(jr\.?|sr\.?|ii|iii|iv|v)$', re.IGNORECASE
)
_TEAM_PARENS_RE = re.compile(r'\s*\([A-Z]{2,4}\)\s*$')
_PUNCT_RE = re.compile(r'[.\'\-,]')
_MULTI_SPACE = re.compile(r'\s+')

# Nickname / alias table — props name -> canonical roster name
_ALIASES = {
    'hollywood brown': 'marquise brown',
    'robbie chosen': 'robbie anderson',
    'chosen anderson': 'robbie anderson',
    'scotty miller': 'scott miller',
    'gabriel davis': 'gabe davis',
    'drew ogletree': 'andrew ogletree',
}

# Names that are not players (D/ST, placeholder, etc.)
_NON_PLAYER_RE = re.compile(
    r'(d/st|defense$|defense/special|no touchdown)', re.IGNORECASE
)


def is_player_name(name: str) -> bool:
    """Return False for D/ST, defense, or placeholder entries."""
    if not name or not isinstance(name, str):
        return False
    return not bool(_NON_PLAYER_RE.search(name))


def _normalise(name: str) -> str:
    """Lowercase, strip accents, strip punctuation, strip suffixes, collapse whitespace."""
    if not name or not isinstance(name, str):
        return ""
    # Strip " (TEAM)" suffix (e.g. "Lamar Jackson (BAL)")
    s = _TEAM_PARENS_RE.sub('', name)
    # NFD decompose then strip combining marks (accents)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower().strip()
    # Strip suffixes
    s = _SUFFIX_RE.sub('', s)
    # Strip punctuation (periods, apostrophes, hyphens)
    s = _PUNCT_RE.sub('', s)
    # Collapse whitespace
    s = _MULTI_SPACE.sub(' ', s).strip()
    return s


def _build_roster_lookup(roster_df, season, week):
    """Build lookup dicts from rosters_weekly for a given season/week.

    Returns:
      by_team: {team_abbr: {normalised_name: gsis_id}}
      by_fi_last_team: {team_abbr: {(first_initial, last): [gsis_id]}}
      by_name_league: {normalised_name: [gsis_id]}
    """
    # Filter to season/week (use max available week <= target)
    rw = roster_df[roster_df['season'] == season].copy()
    if rw.empty:
        return {}, {}, {}
    available_weeks = sorted(rw['week'].unique())
    target_week = max(w for w in available_weeks if w <= week) if any(w <= week for w in available_weeks) else available_weeks[0]
    rw = rw[rw['week'] == target_week]

    by_team = {}
    by_fi_last_team = {}
    by_name_league = {}

    for _, row in rw.iterrows():
        name = row.get('full_name', '')
        gsis_id = row.get('gsis_id', '')
        team = row.get('team', '')
        if not name or not gsis_id or not team:
            continue

        norm = _normalise(name)
        if not norm:
            continue

        # By team
        by_team.setdefault(team, {})[norm] = gsis_id

        # First initial + last name by team
        parts = norm.split()
        if len(parts) >= 2:
            fi = parts[0][0]
            last = parts[-1]
            by_fi_last_team.setdefault(team, {}).setdefault((fi, last), []).append(gsis_id)

        # League-wide
        by_name_league.setdefault(norm, []).append(gsis_id)

    return by_team, by_fi_last_team, by_name_league


def resolve_player(name, season, week, team_candidates,
                   by_team, by_fi_last_team, by_name_league):
    """Resolve a player name to (gsis_id, method).

    team_candidates: list of team abbreviations (e.g. ['KC', 'DEN'])

    Returns:
      (gsis_id, method) where method is 'exact_team', 'fi_last_team',
      'exact_league', or 'unresolved'.
    """
    norm = _normalise(name)
    if not norm:
        return (None, 'unresolved')

    # Check aliases
    names_to_try = [norm]
    if norm in _ALIASES:
        names_to_try.append(_normalise(_ALIASES[norm]))

    # 1. Exact full-name match on a candidate team
    for n in names_to_try:
        for team in team_candidates:
            team_map = by_team.get(team, {})
            if n in team_map:
                return (team_map[n], 'exact_team')

    # 2. Unique first-initial + last-name match on a candidate team
    for n in names_to_try:
        parts = n.split()
        if len(parts) >= 2:
            fi = parts[0][0]
            last = parts[-1]
            for team in team_candidates:
                fi_map = by_fi_last_team.get(team, {})
                candidates = fi_map.get((fi, last), [])
                if len(candidates) == 1:
                    return (candidates[0], 'fi_last_team')

    # 3. Unique full-name match league-wide
    for n in names_to_try:
        league_matches = by_name_league.get(n, [])
        unique_ids = list(set(league_matches))
        if len(unique_ids) == 1:
            return (unique_ids[0], 'exact_league')

    return (None, 'unresolved')


def get_team_candidates(home_team_full, away_team_full):
    """Convert full team names to abbreviation list for matching."""
    teams = []
    for full in [home_team_full, away_team_full]:
        abbr = FULL_TO_ABBR.get(full)
        if abbr:
            teams.append(abbr)
        else:
            # Try matching by last word
            teams.append(full)
    return teams


def load_roster():
    """Load rosters_weekly from disk."""
    return pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / "rosters_weekly.parquet")
