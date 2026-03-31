"""
Soccer model configuration.

Leagues: EPL (E0), Bundesliga (D1), La Liga (SP1), Serie A (I1), Ligue 1 (F1).
One shared Ridge model with league fixed effects.
Two separate Ridge models: Model A → home_goals, Model B → away_goals.
New leagues deployed only if they pass OOS gates independently.
"""

import os

# ── Paths ─────────────────────────────────────────────────────────────────────

SOCCER_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR          = os.path.join(SOCCER_DIR, "data")
CACHE_DIR         = os.path.join(SOCCER_DIR, "data", "cache")
CANONICAL_PATH    = os.path.join(DATA_DIR, "soccer_canonical.parquet")
MODEL_OUTPUTS_PATH    = os.path.join(DATA_DIR, "soccer_model_outputs.parquet")
MARKET_SNAPSHOTS_PATH = os.path.join(DATA_DIR, "soccer_market_snapshots.parquet")
DECISIONS_PATH        = os.path.join(DATA_DIR, "soccer_decisions.parquet")
RESULTS_PATH          = os.path.join(DATA_DIR, "soccer_results.parquet")

# ── League definitions ────────────────────────────────────────────────────────

# league_id → football-data.co.uk division code + display name
LEAGUES = {
    "EPL": {
        "fd_code":      "E0",
        "display_name": "English Premier League",
        "country":      "England",
    },
    "BUN": {
        "fd_code":      "D1",
        "display_name": "Bundesliga",
        "country":      "Germany",
    },
    "LGA": {
        "fd_code":      "SP1",
        "display_name": "La Liga",
        "country":      "Spain",
    },
    "SEA": {
        "fd_code":      "I1",
        "display_name": "Serie A",
        "country":      "Italy",
    },
    "LG1": {
        "fd_code":      "F1",
        "display_name": "Ligue 1",
        "country":      "France",
    },
}

# Deployment status per league — only "active" leagues generate live signals.
# Set by OOS gate evaluation; "active" means the league passed all gates.
LEAGUE_DEPLOYMENT = {
    "EPL": "active",
    "BUN": "active",
    "LGA": "excluded_oos_gate",   # non-monotonic edge curve; hit=72.4% but edge buckets inverted
    "SEA": "active",              # passes OOS gates; small sample (N=9) — monitor closely
    "LG1": "active",              # passes OOS gates after intercept calibration (delta=+0.003)
}

# League metadata for display (emoji, short name)
LEAGUE_META = {
    "EPL": ("\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F", "EPL"),
    "BUN": ("\U0001F1E9\U0001F1EA", "Bundesliga"),
    "LGA": ("\U0001F1EA\U0001F1F8", "La Liga"),
    "SEA": ("\U0001F1EE\U0001F1F9", "Serie A"),
    "LG1": ("\U0001F1EB\U0001F1F7", "Ligue 1"),
}

# ── Season range ──────────────────────────────────────────────────────────────

# football-data.co.uk uses "YYYY" two-digit year codes, e.g. "2324" for 2023-24
# Training: 2019-20 through 2022-23 (covid seasons 2019-20 + 2020-21 get weight 0.5)
# Validate: 2023-24
# OOS:      2024-25

TRAIN_SEASONS    = ["1920", "2021", "2122", "2223"]
VALIDATE_SEASON  = "2324"
OOS_SEASON       = "2425"
CURRENT_SEASON   = "2526"       # live season for daily refresh

COVID_SEASONS    = {"1920", "2021"}     # downweighted to 0.5 in model training
COVID_WEIGHT     = 0.5

# Human-readable labels for audit / display
SEASON_LABELS = {
    "1920": "2019-20",
    "2021": "2020-21",
    "2122": "2021-22",
    "2223": "2022-23",
    "2324": "2023-24",
    "2425": "2024-25",
}

ALL_SEASONS = TRAIN_SEASONS + [VALIDATE_SEASON, OOS_SEASON]

# ── football-data.co.uk URL template ─────────────────────────────────────────

FD_BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"

# ── Shrinkage / rolling windows ───────────────────────────────────────────────

ROLLING_WINDOW     = 10   # games for team rolling features (attack / defence)
MIN_GAMES_FULL_WEIGHT = ROLLING_WINDOW   # n_games needed for w = 1.0

# Universal early-season shrinkage: w = min(n, window) / window
# Applied to ALL teams — including promoted clubs with no prior history in league

# ── Model hyperparameters (set at Phase 2 training time) ─────────────────────

# Placeholders — will be overwritten by Phase 2 CV
RIDGE_ALPHA_HOME = 1.0
RIDGE_ALPHA_AWAY = 1.0

# ── Poisson simulation ───────────────────────────────────────────────────────

SIMULATION_ITERATIONS = 50_000
MAX_GOALS_PER_TEAM    = 10      # truncate Poisson at P(X > MAX) ≈ 0

# ── Market / edge thresholds ─────────────────────────────────────────────────

EDGE_THRESHOLD_PROVISIONAL = 0.04   # Phase 1 provisional (soccer markets are efficient)
EDGE_THRESHOLD_LIVE        = 0.04   # will tune after Phase 2 OOS validation

# ── Canonical schema column order ────────────────────────────────────────────

CANONICAL_COLUMNS = [
    "game_id",
    "game_date",
    "season_year",
    "league_id",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "regulation_total_90",
    "official_bet_total",
    "went_to_et",
    "went_to_penalties",
    "home_xg_raw",
    "away_xg_raw",
    "xg_source",
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "closing_total_line",
    "over_price",
    "under_price",
    "market_available",
]

# ── Audit gate thresholds ────────────────────────────────────────────────────

# These are checked in phase1_build_canonical.py
AUDIT_MIN_ROWS_PER_SEASON = {
    "EPL": 300,   # 380 expected
    "BUN": 250,   # 306 expected
    "LGA": 300,   # 380 expected
    "SEA": 300,   # 380 expected
    "LG1": 250,   # 306-380 expected (18 teams some years)
}
AUDIT_MIN_EPL_ROWS_PER_SEASON    = 300    # kept for backward compat
AUDIT_MIN_BUN_ROWS_PER_SEASON    = 250
AUDIT_MAX_NULL_SCORE_RATE        = 0.01   # <1% null scores acceptable
AUDIT_MIN_MARKET_COVERAGE        = 0.80   # >80% rows should have closing_total_line
AUDIT_MIN_SHOTS_COVERAGE         = 0.90   # >90% rows should have HS/AS/HST/AST
