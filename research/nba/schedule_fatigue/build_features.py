#!/usr/bin/env python3
"""
Phase 1 — Build nba_schedule_features.parquet
Schedule fatigue features for NBA totals research.
"""
import math
import pandas as pd
import numpy as np
from datetime import timedelta

# ── Team abbreviation to full name mapping ──────────────────────────────────
ABBREV_TO_FULL = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'Los Angeles Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards',
}

ARENA_COORDS = {
    'Atlanta Hawks': ('East', 33.757, -84.396),
    'Boston Celtics': ('East', 42.366, -71.062),
    'Brooklyn Nets': ('East', 40.683, -73.975),
    'Charlotte Hornets': ('East', 35.225, -80.839),
    'Chicago Bulls': ('East', 41.881, -87.674),
    'Cleveland Cavaliers': ('East', 41.496, -81.688),
    'Dallas Mavericks': ('West', 32.790, -96.810),
    'Denver Nuggets': ('West', 39.749, -104.999),
    'Detroit Pistons': ('East', 42.341, -83.048),
    'Golden State Warriors': ('West', 37.768, -122.388),
    'Houston Rockets': ('West', 29.751, -95.362),
    'Indiana Pacers': ('East', 39.764, -86.156),
    'Los Angeles Clippers': ('West', 33.930, -118.338),
    'Los Angeles Lakers': ('West', 34.043, -118.267),
    'Memphis Grizzlies': ('West', 35.138, -90.051),
    'Miami Heat': ('East', 25.781, -80.188),
    'Milwaukee Bucks': ('East', 43.045, -87.917),
    'Minnesota Timberwolves': ('West', 44.979, -93.276),
    'New Orleans Pelicans': ('West', 29.949, -90.082),
    'New York Knicks': ('East', 40.750, -73.994),
    'Oklahoma City Thunder': ('West', 35.463, -97.515),
    'Orlando Magic': ('East', 28.539, -81.384),
    'Philadelphia 76ers': ('East', 39.901, -75.172),
    'Phoenix Suns': ('West', 33.446, -112.071),
    'Portland Trail Blazers': ('West', 45.532, -122.667),
    'Sacramento Kings': ('West', 38.580, -121.500),
    'San Antonio Spurs': ('West', 29.427, -98.438),
    'Toronto Raptors': ('East', 43.643, -79.379),
    'Utah Jazz': ('West', 40.768, -111.901),
    'Washington Wizards': ('East', 38.898, -77.021),
}

HIGH_ALTITUDE_TEAMS = {'Denver Nuggets', 'Utah Jazz'}
HIGH_ALTITUDE_ABBREVS = {'DEN', 'UTA'}

# Conference lookup from ARENA_COORDS (by abbreviation for convenience)
TEAM_CONF = {abbr: ARENA_COORDS[full][0] for abbr, full in ABBREV_TO_FULL.items()}
TEAM_LAT = {abbr: ARENA_COORDS[full][1] for abbr, full in ABBREV_TO_FULL.items()}
TEAM_LON = {abbr: ARENA_COORDS[full][2] for abbr, full in ABBREV_TO_FULL.items()}


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles."""
    R = 3958.8  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_team_schedule_features(team_games: pd.DataFrame, team: str) -> pd.DataFrame:
    """
    For a single team, compute all schedule features looking backward only.
    team_games must be sorted by date, with columns: game_id, date, home_team, away_team, season.
    """
    records = []
    for i, row in team_games.iterrows():
        gid = row['game_id']
        gdate = row['date']
        is_home = (row['home_team'] == team)
        season = row['season']

        # Arena of current game = home team's arena
        current_arena_team = row['home_team']
        current_conf = TEAM_CONF.get(current_arena_team)

        # ── rest_days ──
        prev_games = team_games.loc[:i].iloc[:-1]  # all rows before this one
        same_season = prev_games[prev_games['season'] == season]

        if len(same_season) == 0:
            rest_days = None
            prev_game_date = None
            prev_game_home = None
            prev_game_away = None
        else:
            last = same_season.iloc[-1]
            prev_game_date = last['date']
            rest_days = (gdate - prev_game_date).days
            prev_game_home = last['home_team']
            prev_game_away = last['away_team']

        # ── games_last_5_days and games_last_4_days ──
        if len(same_season) > 0:
            cutoff_5 = gdate - timedelta(days=5)
            cutoff_4 = gdate - timedelta(days=4)
            recent = same_season[same_season['date'] >= cutoff_5]
            games_last_5 = len(recent[recent['date'] < gdate])
            recent_4 = same_season[same_season['date'] >= cutoff_4]
            games_last_4 = len(recent_4[recent_4['date'] < gdate])
        else:
            games_last_5 = 0
            games_last_4 = 0

        # ── road_trip_length ──
        if is_home:
            road_trip_length = 0
        else:
            # Count consecutive away games up to and including this one
            road_trip_length = 1
            for j in range(len(same_season) - 1, -1, -1):
                prev = same_season.iloc[j]
                if prev['home_team'] == team:
                    break  # hit a home game
                road_trip_length += 1

        # ── prev_game_was_altitude ──
        # True ONLY if team was AWAY at DEN or UTA in their most recent prior game
        prev_altitude = False
        if prev_game_home is not None:
            if prev_game_home in HIGH_ALTITUDE_ABBREVS and prev_game_away == team:
                # team was the away team at a high-altitude arena
                prev_altitude = True
            elif prev_game_home in HIGH_ALTITUDE_ABBREVS and prev_game_home != team:
                # team was the away team visiting high altitude
                prev_altitude = True
            # Simplify: team's previous game was at altitude if the home_team of that
            # game was DEN/UTA AND the team was the away team
            prev_altitude = (prev_game_home in HIGH_ALTITUDE_ABBREVS and
                             prev_game_home != team)

        # ── hours_since_prev_game ──
        if prev_game_date is not None:
            hours_since = (gdate - prev_game_date).days * 24.0
        else:
            hours_since = None

        # ── cross_country_flag ──
        cross_country = False
        if prev_game_date is not None and hours_since is not None and hours_since <= 48:
            prev_arena_team = prev_games.iloc[-1]['home_team'] if len(prev_games) > 0 else None
            if prev_arena_team is None:
                prev_arena_team = same_season.iloc[-1]['home_team']
            prev_conf = TEAM_CONF.get(prev_arena_team)
            if prev_conf and current_conf and prev_conf != current_conf:
                cross_country = True

        # ── travel_miles_est ──
        travel_miles = None
        if prev_game_date is not None and len(same_season) > 0:
            prev_arena = same_season.iloc[-1]['home_team']
            if prev_arena in TEAM_LAT and current_arena_team in TEAM_LAT:
                travel_miles = haversine_miles(
                    TEAM_LAT[prev_arena], TEAM_LON[prev_arena],
                    TEAM_LAT[current_arena_team], TEAM_LON[current_arena_team]
                )

        records.append({
            'game_id': gid,
            'team': team,
            'is_home': is_home,
            'rest_days': rest_days,
            'games_last_5': games_last_5,
            'games_last_4': games_last_4,
            'road_trip_length': road_trip_length,
            'prev_altitude_game': prev_altitude,
            'hours_since_prev': hours_since,
            'cross_country': cross_country,
            'travel_miles_est': travel_miles,
            'prev_game_date': prev_game_date,
        })

    return pd.DataFrame(records)


# ── MAIN ────────────────────────────────────────────────────────────────────
print("Loading data...")
lines = pd.read_parquet('nba/data/nba_historical_closing_lines.parquet')
feat = pd.read_parquet('nba/data/features.parquet',
                        columns=['game_id', 'actual_total', 'home_score', 'away_score'])
box = pd.read_parquet('nba/data/box_stats.parquet', columns=['game_id', 'team', 'went_ot'])
ot_flags = box.groupby('game_id')['went_ot'].any().reset_index().rename(columns={'went_ot': 'went_to_ot'})

# Build base game table
games = lines[['game_id', 'date', 'season', 'home_team', 'away_team', 'close_total']].copy()
games['date'] = pd.to_datetime(games['date'])
games = games.merge(feat[['game_id', 'actual_total']], on='game_id', how='left')
games = games.merge(ot_flags, on='game_id', how='left')
games = games.sort_values('date').reset_index(drop=True)

print(f"Games: {len(games)}")
print(f"With actual_total: {games['actual_total'].notna().sum()}")
print(f"With OT flag: {games['went_to_ot'].notna().sum()}")
print(f"OT games: {games['went_to_ot'].sum()}")

# Build team-level game log for all 30 teams
all_teams = sorted(set(games['home_team'].unique()) | set(games['away_team'].unique()))
print(f"\nComputing schedule features for {len(all_teams)} teams...")

team_features = []
for team in all_teams:
    team_games = games[
        (games['home_team'] == team) | (games['away_team'] == team)
    ].sort_values('date').reset_index(drop=True)
    tf = compute_team_schedule_features(team_games, team)
    team_features.append(tf)
    print(f"  {team}: {len(tf)} games")

all_tf = pd.concat(team_features, ignore_index=True)

# Pivot: home features and away features per game
home_tf = all_tf[all_tf['is_home']].rename(columns={
    'rest_days': 'home_rest_days',
    'games_last_5': 'home_games_last_5',
    'games_last_4': 'home_games_last_4',
    'road_trip_length': 'home_road_trip_length',
    'prev_altitude_game': 'home_prev_altitude_game',
    'hours_since_prev': 'home_hours_since_prev',
    'cross_country': 'home_cross_country',
    'travel_miles_est': 'home_travel_miles_est',
    'prev_game_date': 'home_prev_game_date',
}).drop(columns=['team', 'is_home'])

away_tf = all_tf[~all_tf['is_home']].rename(columns={
    'rest_days': 'away_rest_days',
    'games_last_5': 'away_games_last_5',
    'games_last_4': 'away_games_last_4',
    'road_trip_length': 'away_road_trip_length',
    'prev_altitude_game': 'away_prev_altitude_game',
    'hours_since_prev': 'away_hours_since_prev',
    'cross_country': 'away_cross_country',
    'travel_miles_est': 'away_travel_miles_est',
    'prev_game_date': 'away_prev_game_date',
}).drop(columns=['team', 'is_home'])

# Merge onto games
result = games.merge(home_tf, on='game_id', how='left')
result = result.merge(away_tf, on='game_id', how='left')

# Rename for output schema
result = result.rename(columns={'date': 'game_date', 'close_total': 'total'})

# Select output columns
out_cols = [
    'game_id', 'game_date', 'season', 'home_team', 'away_team', 'total', 'actual_total', 'went_to_ot',
    'home_rest_days', 'away_rest_days',
    'home_games_last_5', 'away_games_last_5',
    'home_games_last_4', 'away_games_last_4',
    'home_road_trip_length', 'away_road_trip_length',
    'home_prev_altitude_game', 'away_prev_altitude_game',
    'home_hours_since_prev', 'away_hours_since_prev',
    'home_cross_country', 'away_cross_country',
    'home_travel_miles_est', 'away_travel_miles_est',
    'home_prev_game_date', 'away_prev_game_date',
]
result = result[[c for c in out_cols if c in result.columns]]

# Save
out_path = 'nba/data/nba_schedule_features.parquet'
result.to_parquet(out_path, index=False)
print(f"\nSaved: {out_path}")
print(f"Shape: {result.shape}")

# ── Coverage summary ──
print(f"\n{'='*60}")
print("COVERAGE SUMMARY")
print(f"{'='*60}")
print(f"Total games: {len(result)}")
print(f"% with home_rest_days populated: {result['home_rest_days'].notna().mean()*100:.1f}%")
print(f"% with away_rest_days populated: {result['away_rest_days'].notna().mean()*100:.1f}%")
print(f"% with home_cross_country populated: {result['home_cross_country'].notna().mean()*100:.1f}%")
print(f"% with away_cross_country populated: {result['away_cross_country'].notna().mean()*100:.1f}%")

print(f"\nSeason breakdown:")
for season in sorted(result['season'].unique()):
    n = len(result[result['season'] == season])
    print(f"  {season}: {n} games")

print(f"\nOT handling: went_to_ot flag available. {int(result['went_to_ot'].sum())} OT games ({result['went_to_ot'].mean()*100:.1f}%) will be EXCLUDED from signal testing.")

# Travel miles stats
away_cc = result[result['away_cross_country'] == True]
home_cc = result[result['home_cross_country'] == True]
print(f"\nMedian travel miles (away_cross_country=True): {away_cc['away_travel_miles_est'].median():.0f} miles (N={len(away_cc)})")
print(f"Median travel miles (home_cross_country=True): {home_cc['home_travel_miles_est'].median():.0f} miles (N={len(home_cc)})")

# Spot checks
print(f"\n── Spot checks ──")
print(f"home_road_trip_length distribution (should all be 0): min={result['home_road_trip_length'].min()}, max={result['home_road_trip_length'].max()}")
print(f"away_road_trip_length distribution: min={result['away_road_trip_length'].min()}, max={result['away_road_trip_length'].max()}, mean={result['away_road_trip_length'].mean():.2f}")
print(f"home_prev_altitude_game True count: {result['home_prev_altitude_game'].sum()}")
print(f"away_prev_altitude_game True count: {result['away_prev_altitude_game'].sum()}")
print(f"home_games_last_5 distribution: {result['home_games_last_5'].value_counts().sort_index().to_dict()}")
print(f"away_games_last_5 distribution: {result['away_games_last_5'].value_counts().sort_index().to_dict()}")
PYEOF
