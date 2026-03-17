"""
NBA Model — central configuration.
All thresholds and season parameters live here — nothing hardcoded in logic.
"""

import os

# ── Directories ───────────────────────────────────────────────────────────────
NBA_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(NBA_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
GAMES_PATH      = os.path.join(DATA_DIR, "games.parquet")
BOX_STATS_PATH  = os.path.join(DATA_DIR, "box_stats.parquet")
FEATURES_PATH   = os.path.join(DATA_DIR, "features.parquet")
H1_FEATURES_PATH = os.path.join(DATA_DIR, "h1_features.parquet")

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

# ── Simulation (Phase 5) ──────────────────────────────────────────────────────
SIMULATION_N_ITER    = 10_000  # Monte Carlo draws per game
RESIDUAL_SIGMA       = 18.62   # training residual std dev (2022-24, Pass 1 model)
                                # Used as default variance; can be overridden per game.

# ── Playoff mode (Phase 8) ─────────────────────────────────────────────────────
# Playoff sigma calibrated from 2025 shadow run (84 games, bref source).
# Empirical error std = 20.20 pts — HIGHER than regular season (18.62), not lower.
# Wider variance reflects extreme defensive schemes + series-specific outliers.
# Shadow run: 56% within ±15.5 (target 68%) → updated to 20.2 for correct coverage.
RESIDUAL_SIGMA_PLAYOFF   = 20.2     # playoff residual std dev (calibrated 2025-03-17)
PLAYOFF_MODE_VERSION     = "v1_2026_04"  # bump on logic changes for audit trail
PLAYOFF_SERIES_BLEND_CAP = 5        # series games at which w_playoff saturates at 1.0
# Execution rules — thresholds for calling a game actionable.
# These live here so they can be tuned independently of model logic.
# Full-game and first-half thresholds are kept separate because the
# OOS edge-bucket analysis showed different reliability profiles.
EDGE_THRESHOLD_FULL  = 6.0    # |pred − rolling_avg| ≥ this to flag full-game play
EDGE_THRESHOLD_HALF  = None   # placeholder — to be calibrated when F5 data added

# ── Confidence tiers ──────────────────────────────────────────────────────────
# HIGH:   both conditions met + no active injury flag
# MEDIUM: edge + probability conditions only
# LOW:    probability only
CONF_HIGH   = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW    = "LOW"

# ── League averages (calibrated from 2022-25 rolling data) ───────────────────
# ORtg/DRtg from rolling windows are lower than raw season averages because
# rolling 15-game windows include early-season regression toward the mean.
# 115.0 is the raw NBA season average; 112.0 is what the rolling feature
# distributions actually produce. Using 115.0 in the naive formula inflates
# the DRtg multiplier and creates a -7 pt systematic bias.
LEAGUE_AVG_PACE  = 101.4    # actual mean pace in rolling feature data
LEAGUE_AVG_ORTG  = 112.0    # actual mean ORtg in rolling feature data
LEAGUE_AVG_DRTG  = 112.0    # actual mean DRtg in rolling feature data
LEAGUE_AVG_TOTAL    = 228.5  # actual mean game total 2022-25
LEAGUE_AVG_H1_TOTAL = 108.5  # fallback H1 prior for first season (historical NBA avg)

# ── Phase 7 — Live / Odds API ─────────────────────────────────────────────────
import os as _os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), ".env"))
except ImportError:
    pass
ODDS_API_KEY  = _os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_BOOKMAKERS = ["draftkings", "fanduel"]

# ── NBA Results tracker paths ──────────────────────────────────────────────────
NBA_PROJECTIONS_PATH      = _os.path.join(DATA_DIR, "nba_daily_projections.parquet")
NBA_RESULTS_LOG_PATH      = _os.path.join(DATA_DIR, "nba_results_log.parquet")
NBA_MARKET_SNAPSHOTS_PATH = os.path.join(DATA_DIR, "nba_market_snapshots.parquet")

# ── The Odds API: NBA team name → abbreviation ────────────────────────────────
NBA_ODDS_TEAM_MAP = {
    "Atlanta Hawks":           "ATL",
    "Boston Celtics":          "BOS",
    "Brooklyn Nets":           "BKN",
    "Charlotte Hornets":       "CHA",
    "Chicago Bulls":           "CHI",
    "Cleveland Cavaliers":     "CLE",
    "Dallas Mavericks":        "DAL",
    "Denver Nuggets":          "DEN",
    "Detroit Pistons":         "DET",
    "Golden State Warriors":   "GSW",
    "Houston Rockets":         "HOU",
    "Indiana Pacers":          "IND",
    "Los Angeles Clippers":    "LAC",
    "Los Angeles Lakers":      "LAL",
    "Memphis Grizzlies":       "MEM",
    "Miami Heat":              "MIA",
    "Milwaukee Bucks":         "MIL",
    "Minnesota Timberwolves":  "MIN",
    "New Orleans Pelicans":    "NOP",
    "New York Knicks":         "NYK",
    "Oklahoma City Thunder":   "OKC",
    "Orlando Magic":           "ORL",
    "Philadelphia 76ers":      "PHI",
    "Phoenix Suns":            "PHX",
    "Portland Trail Blazers":  "POR",
    "Sacramento Kings":        "SAC",
    "San Antonio Spurs":       "SAS",
    "Toronto Raptors":         "TOR",
    "Utah Jazz":               "UTA",
    "Washington Wizards":      "WAS",
}
