"""
NBA Model — central configuration.
All thresholds and season parameters live here — nothing hardcoded in logic.
"""

import os

# ── Directories ───────────────────────────────────────────────────────────────
NBA_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(NBA_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
GAMES_PATH = os.path.join(DATA_DIR, "games.parquet")

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Seasons ────────────────────────────────────────────────────────────────────
# Format: "YYYY-YY"  — add future seasons here, nowhere else in the codebase.
TRAINING_SEASONS   = ["2022-23", "2023-24"]
VALIDATION_SEASON  = "2024-25"
CURRENT_SEASON     = "2025-26"

ALL_HISTORICAL_SEASONS = TRAINING_SEASONS + [VALIDATION_SEASON]

# Season type codes used by nba_api
SEASON_TYPE_REGULAR = "Regular Season"
SEASON_TYPE_PLAYOFF = "Playoffs"

# ── NBA API ────────────────────────────────────────────────────────────────────
NBA_API_TIMEOUT  = 30        # seconds per request
NBA_API_RETRIES  = 5         # max retry attempts
NBA_API_BACKOFF  = [2, 5, 10, 20, 30]   # seconds between retry attempts

# ── Feature engineering ───────────────────────────────────────────────────────
ROLLING_WINDOW       = 15    # games for rolling efficiency metrics
LOCATION_MIN_GAMES   = 5     # min same-location games before using location splits
SEASON_BLEND_START   = 15    # games into season: start blending with prior baseline
SEASON_BLEND_END     = 20    # games into season: fully on current-season data
PRIOR_SEASON_WEIGHT  = 0.70  # weight on prior-season baseline during blend window
INJURY_PPP_REDUCTION = 1.5   # pts/100 OffRtg reduction per missing rotation player
INJURY_MAX_REDUCTION = 4.5   # cap on total injury adjustment
INJURY_MIN_MPG       = 15.0  # minutes/game threshold to flag a missing player

# ── Model ─────────────────────────────────────────────────────────────────────
RIDGE_ALPHA          = 10.0  # L2 regularization strength (tunable)

# ── Live / props thresholds ───────────────────────────────────────────────────
OVER_UNDER_MIN_PROB  = 0.55  # minimum probability to flag a play
MIN_EDGE_VS_MARKET   = 1.5   # minimum point edge vs market line
MARKET_FLAG_THRESHOLD = 12.0 # log for inspection if model/market gap > this

# ── Confidence tiers ──────────────────────────────────────────────────────────
# HIGH:   both conditions met + no active injury flag
# MEDIUM: edge + probability conditions only
# LOW:    probability only
CONF_HIGH   = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW    = "LOW"

# ── League averages (rough 2024-25 baselines; updated by season_baselines.py) ─
LEAGUE_AVG_PACE  = 99.5
LEAGUE_AVG_ORTG  = 115.0
LEAGUE_AVG_DRTG  = 115.0
LEAGUE_AVG_TOTAL = 228.0
