"""
MLB Totals Model — Central Configuration
========================================
Adjust MODEL_WEIGHTS to re-tune the model as the season progresses.
All park factors and stadium metadata live here for easy maintenance.
"""

# ---------------------------------------------------------------------------
# Model weights — must sum to 1.0 within each group
# ---------------------------------------------------------------------------
MODEL_WEIGHTS = {
    # Starting pitcher component (how much SP quality drives expected runs)
    "sp_quality": 0.35,
    # Team offense component
    "offense": 0.30,
    # Park factor component
    "park": 0.15,
    # Weather (wind + temperature combined)
    "weather": 0.08,
    # Umpire tendency
    "umpire": 0.07,
    # Bullpen fatigue (full game only; F5 uses 0 for this slot)
    "bullpen": 0.05,
}

# F5 weight overrides — bullpen is irrelevant, redistribute to SP/offense
F5_WEIGHTS = {
    "sp_quality": 0.40,
    "offense":    0.32,
    "park":       0.14,
    "weather":    0.08,
    "umpire":     0.06,
    "bullpen":    0.00,
}

# ---------------------------------------------------------------------------
# League baseline constants (2024 MLB averages)
# ---------------------------------------------------------------------------
LEAGUE_AVG_RUNS_PER_TEAM = 4.50   # runs per team per 9-inning game
LEAGUE_AVG_ERA            = 4.25   # ERA / xFIP baseline for starters
LEAGUE_AVG_BULLPEN_ERA    = 4.10   # ERA baseline for relievers
LEAGUE_AVG_WRC_PLUS       = 100    # by definition
LEAGUE_AVG_K_RATE         = 0.224  # 22.4% strikeout rate league-wide
LEAGUE_AVG_BB_RATE        = 0.085  # 8.5% walk rate league-wide

# F5 run fraction: starters typically allow ~55% of total game runs in 5 inn.
F5_RUN_FRACTION = 0.56

# Bullpen fatigue scaling: 1 inning of relief = this fraction of "fatigue unit"
BULLPEN_FATIGUE_PER_INNING = 0.08
# Max fatigue factor multiplier on RA9 (if every reliever threw 3+ innings)
BULLPEN_MAX_FATIGUE_MULTIPLIER = 1.30

# Wind effect on runs: fraction of run adjustment per mph (blowing out)
WIND_RUNS_PER_MPH = 0.0025

# Temperature baseline (°F); each degree above/below adjusts runs by factor
TEMP_BASELINE_F   = 72.0
TEMP_RUNS_PER_DEG = 0.002   # +0.2% per degree above baseline

# ---------------------------------------------------------------------------
# Stadium data
# Each entry: name, latitude, longitude,
#             cf_bearing  (compass degrees FROM home plate TO center field),
#             park_factor (2024 runs park factor, 100 = neutral)
# ---------------------------------------------------------------------------
STADIUMS = {
    # ---- American League East ----
    "BOS": {
        "name": "Fenway Park",
        "lat": 42.3467, "lon": -71.0972,
        "cf_bearing": 55,
        "park_factor": 104,
    },
    "NYY": {
        "name": "Yankee Stadium",
        "lat": 40.8296, "lon": -73.9262,
        "cf_bearing": 40,
        "park_factor": 103,
    },
    "TBR": {
        "name": "Tropicana Field",
        "lat": 27.7683, "lon": -82.6534,
        "cf_bearing": 5,
        "park_factor": 97,
        "dome": True,
    },
    "TOR": {
        "name": "Rogers Centre",
        "lat": 43.6414, "lon": -79.3894,
        "cf_bearing": 350,
        "park_factor": 105,
        "retractable_roof": True,
    },
    "BAL": {
        "name": "Camden Yards",
        "lat": 39.2840, "lon": -76.6218,
        "cf_bearing": 50,
        "park_factor": 106,
    },
    # ---- American League Central ----
    "CHW": {
        "name": "Guaranteed Rate Field",
        "lat": 41.8300, "lon": -87.6338,
        "cf_bearing": 5,
        "park_factor": 100,
    },
    "CLE": {
        "name": "Progressive Field",
        "lat": 41.4962, "lon": -81.6852,
        "cf_bearing": 350,
        "park_factor": 98,
    },
    "DET": {
        "name": "Comerica Park",
        "lat": 42.3390, "lon": -83.0485,
        "cf_bearing": 10,
        "park_factor": 99,
    },
    "KCR": {
        "name": "Kauffman Stadium",
        "lat": 39.0517, "lon": -94.4803,
        "cf_bearing": 5,
        "park_factor": 100,
    },
    "MIN": {
        "name": "Target Field",
        "lat": 44.9817, "lon": -93.2781,
        "cf_bearing": 345,
        "park_factor": 99,
    },
    # ---- American League West ----
    "HOU": {
        "name": "Minute Maid Park",
        "lat": 29.7573, "lon": -95.3555,
        "cf_bearing": 0,
        "park_factor": 100,
        "retractable_roof": True,
    },
    "LAA": {
        "name": "Angel Stadium",
        "lat": 33.8003, "lon": -117.8827,
        "cf_bearing": 0,
        "park_factor": 97,
    },
    "OAK": {
        "name": "Oakland Coliseum",
        "lat": 37.7516, "lon": -122.2005,
        "cf_bearing": 330,
        "park_factor": 95,
    },
    "SEA": {
        "name": "T-Mobile Park",
        "lat": 47.5914, "lon": -122.3325,
        "cf_bearing": 30,
        "park_factor": 94,
    },
    "TEX": {
        "name": "Globe Life Field",
        "lat": 32.7473, "lon": -97.0842,
        "cf_bearing": 355,
        "park_factor": 107,
        "retractable_roof": True,
    },
    # ---- National League East ----
    "ATL": {
        "name": "Truist Park",
        "lat": 33.8908, "lon": -84.4678,
        "cf_bearing": 5,
        "park_factor": 102,
    },
    "MIA": {
        "name": "loanDepot Park",
        "lat": 25.7781, "lon": -80.2197,
        "cf_bearing": 350,
        "park_factor": 98,
        "retractable_roof": True,
    },
    "NYM": {
        "name": "Citi Field",
        "lat": 40.7571, "lon": -73.8458,
        "cf_bearing": 15,
        "park_factor": 94,
    },
    "PHI": {
        "name": "Citizens Bank Park",
        "lat": 39.9061, "lon": -75.1665,
        "cf_bearing": 5,
        "park_factor": 104,
    },
    "WSN": {
        "name": "Nationals Park",
        "lat": 38.8730, "lon": -77.0074,
        "cf_bearing": 10,
        "park_factor": 101,
    },
    # ---- National League Central ----
    "CHC": {
        "name": "Wrigley Field",
        "lat": 41.9484, "lon": -87.6553,
        "cf_bearing": 90,
        "park_factor": 103,
    },
    "CIN": {
        "name": "Great American Ball Park",
        "lat": 39.0979, "lon": -84.5082,
        "cf_bearing": 30,
        "park_factor": 107,
    },
    "MIL": {
        "name": "American Family Field",
        "lat": 43.0280, "lon": -87.9712,
        "cf_bearing": 0,
        "park_factor": 102,
        "retractable_roof": True,
    },
    "PIT": {
        "name": "PNC Park",
        "lat": 40.4468, "lon": -80.0057,
        "cf_bearing": 340,
        "park_factor": 101,
    },
    "STL": {
        "name": "Busch Stadium",
        "lat": 38.6226, "lon": -90.1928,
        "cf_bearing": 10,
        "park_factor": 97,
    },
    # ---- National League West ----
    "ARI": {
        "name": "Chase Field",
        "lat": 33.4453, "lon": -112.0667,
        "cf_bearing": 345,
        "park_factor": 98,
        "retractable_roof": True,
    },
    "COL": {
        "name": "Coors Field",
        "lat": 39.7559, "lon": -104.9942,
        "cf_bearing": 340,
        "park_factor": 117,
    },
    "LAD": {
        "name": "Dodger Stadium",
        "lat": 34.0739, "lon": -118.2400,
        "cf_bearing": 25,
        "park_factor": 95,
    },
    "SDP": {
        "name": "Petco Park",
        "lat": 32.7076, "lon": -117.1570,
        "cf_bearing": 310,
        "park_factor": 95,
    },
    "SFG": {
        "name": "Oracle Park",
        "lat": 37.7786, "lon": -122.3893,
        "cf_bearing": 60,
        "park_factor": 96,
    },
}

# ---------------------------------------------------------------------------
# Team ID → abbreviation mapping (MLB Stats API numeric IDs)
# ---------------------------------------------------------------------------
TEAM_ID_TO_ABB = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS", 112: "CHC",
    113: "CIN", 114: "CLE", 115: "COL", 116: "DET", 117: "HOU",
    118: "KCR", 119: "LAD", 120: "WSN", 121: "NYM", 133: "OAK",
    134: "PIT", 135: "SDP", 136: "SEA", 137: "SFG", 138: "STL",
    139: "TBR", 140: "TEX", 141: "TOR", 142: "MIN", 143: "PHI",
    144: "ATL", 145: "CHW", 146: "MIA", 147: "NYY", 158: "MIL",
}
ABB_TO_TEAM_ID = {v: k for k, v in TEAM_ID_TO_ABB.items()}

# FanGraphs team name → abbreviation (for matching wRC+ data)
FANGRAPHS_TEAM_MAP = {
    "Angels": "LAA", "Diamondbacks": "ARI", "Orioles": "BAL",
    "Red Sox": "BOS", "Cubs": "CHC", "Reds": "CIN",
    "Guardians": "CLE", "Rockies": "COL", "Tigers": "DET",
    "Astros": "HOU", "Royals": "KCR", "Dodgers": "LAD",
    "Nationals": "WSN", "Mets": "NYM", "Athletics": "OAK",
    "Pirates": "PIT", "Padres": "SDP", "Mariners": "SEA",
    "Giants": "SFG", "Cardinals": "STL", "Rays": "TBR",
    "Rangers": "TEX", "Blue Jays": "TOR", "Twins": "MIN",
    "Phillies": "PHI", "Braves": "ATL", "White Sox": "CHW",
    "Marlins": "MIA", "Yankees": "NYY", "Brewers": "MIL",
}

# ---------------------------------------------------------------------------
# The Odds API
# https://the-odds-api.com  — free tier: ~500 requests/month
# Set ODDS_API_KEY in your .env file or shell environment — never hardcode.
# ---------------------------------------------------------------------------
import os as _os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_os.path.join(_os.path.dirname(__file__), ".env"))
except ImportError:
    pass
ODDS_API_KEY  = _os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Bookmakers to pull from (must be valid Odds API keys)
ODDS_BOOKMAKERS = ["draftkings", "fanduel"]

# Minimum edge (proj - line, in runs) to flag as a value play
EDGE_MIN_RUNS = 0.5

# Team name as returned by The Odds API → our abbreviation
ODDS_API_TEAM_MAP = {
    "Los Angeles Angels":       "LAA",
    "Arizona Diamondbacks":     "ARI",
    "Baltimore Orioles":        "BAL",
    "Boston Red Sox":           "BOS",
    "Chicago Cubs":             "CHC",
    "Cincinnati Reds":          "CIN",
    "Cleveland Guardians":      "CLE",
    "Colorado Rockies":         "COL",
    "Detroit Tigers":           "DET",
    "Houston Astros":           "HOU",
    "Kansas City Royals":       "KCR",
    "Los Angeles Dodgers":      "LAD",
    "Washington Nationals":     "WSN",
    "New York Mets":            "NYM",
    "Oakland Athletics":        "OAK",
    "Athletics":                "OAK",
    "Pittsburgh Pirates":       "PIT",
    "San Diego Padres":         "SDP",
    "Seattle Mariners":         "SEA",
    "San Francisco Giants":     "SFG",
    "St. Louis Cardinals":      "STL",
    "Tampa Bay Rays":           "TBR",
    "Texas Rangers":            "TEX",
    "Toronto Blue Jays":        "TOR",
    "Minnesota Twins":          "MIN",
    "Philadelphia Phillies":    "PHI",
    "Atlanta Braves":           "ATL",
    "Chicago White Sox":        "CHW",
    "Miami Marlins":            "MIA",
    "New York Yankees":         "NYY",
    "Milwaukee Brewers":        "MIL",
}

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
MLB_STATS_API = "https://statsapi.mlb.com/api/v1"
OPEN_METEO_API = "https://api.open-meteo.com/v1/forecast"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
import os
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
LOGS_DIR  = os.path.join(BASE_DIR, "logs")
DB_PATH   = os.path.join(DATA_DIR, "mlb_model.db")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,  exist_ok=True)
