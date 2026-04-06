#!/usr/bin/env python3
"""
Soccer OVER-Only Specialist — Daily Pipeline
============================================
Fetches today's EPL and Bundesliga fixtures, computes V2.2 features,
runs the ridge residual model, applies production filters, and writes
qualified OVER signals to soccer/data/soccer_decisions.parquet.

Optionally grades yesterday's signals.

Usage:
  python3 soccer/soccer_daily_pipeline.py                        # today
  python3 soccer/soccer_daily_pipeline.py --date 2026-03-16      # specific date
  python3 soccer/soccer_daily_pipeline.py --grade-yesterday       # grade + today
  python3 soccer/soccer_daily_pipeline.py --refresh-lineups       # re-fetch lineups only
  python3 soccer/soccer_daily_pipeline.py --no-odds               # skip Odds API

Model: Ridge residual (V2.2) — OVER 2.5 specialist
OOS performance: 56.7% hit rate, +8.3% ROI @ -110
HIGH bucket (edge >= 0.10): 61.7% hit, +17.8% ROI
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
import time
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.optimize import brentq
from scipy import stats

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SOCCER_DIR    = Path(__file__).resolve().parent
BASE_DIR      = SOCCER_DIR.parent
DATA_DIR      = SOCCER_DIR / "data"
MODELS_DIR    = SOCCER_DIR / "models"
CACHE_DIR     = DATA_DIR / "cache" / "daily"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CANONICAL_PATH = DATA_DIR / "soccer_canonical.parquet"
DECISIONS_PATH = DATA_DIR / "soccer_decisions.parquet"
FT_PATH        = DATA_DIR / "soccer_feature_table_v2_2.parquet"
REF_PATH       = DATA_DIR / "referee_features.parquet"

RIDGE_PKL      = MODELS_DIR / "ridge_residual_model.pkl"
CALIBRATOR_PKL = MODELS_DIR / "calibrator_ridge.pkl"
SCALER_PKL     = MODELS_DIR / "scaler_v2_2.pkl"
IMPUTE_PKL     = MODELS_DIR / "v2_2_impute_vals.pkl"

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
ODDS_API_BASE     = "https://api.the-odds-api.com/v4"
OPEN_METEO_URL    = "https://api.open-meteo.com/v1/forecast"

WIN_PER_UNIT = 100.0 / 110.0

# ---------------------------------------------------------------------------
# Production signal rules
# ---------------------------------------------------------------------------
MIN_EDGE               = 0.06
LATE_MONEY_SUPPRESS    = -0.03   # suppress if market_move_to_over < this
MIN_PRIOR_MATCHES      = 5       # skip game if team has < this many matches

# Live signal restriction — only BUN MEDIUM fires as active bet.
# All other qualified signals still logged but marked shadow/observational.
LIVE_ACTIVE_LEAGUES    = {"BUN"}
LIVE_ACTIVE_TIERS      = {"MEDIUM"}   # edge 0.08–0.10

# V2.2c shadow challenger — shrinkage formula on top of V2.2 output
V2_2C_ALPHA            = 0.66
V2_2C_SHADOW_LOG       = SOCCER_DIR / "logs" / "v2_2c_shadow_2026.json"

# ---------------------------------------------------------------------------
# Leagues
# ---------------------------------------------------------------------------
ALL_LEAGUES = {
    "EPL": {
        "api_football_id": 39,
        "odds_sport":      "soccer_epl",
        "season":          2025,
    },
    "BUN": {
        "api_football_id": 78,
        "odds_sport":      "soccer_germany_bundesliga",
        "season":          2025,
    },
    "LGA": {
        "api_football_id": 140,
        "odds_sport":      "soccer_spain_la_liga",
        "season":          2024,
    },
    "SEA": {
        "api_football_id": 135,
        "odds_sport":      "soccer_italy_serie_a",
        "season":          2024,
    },
    "LG1": {
        "api_football_id": 61,
        "odds_sport":      "soccer_france_ligue_one",
        "season":          2024,
    },
}

# Only active leagues generate live signals
try:
    from soccer.config import LEAGUE_DEPLOYMENT
except ImportError:
    sys.path.insert(0, str(BASE_DIR))
    from soccer.config import LEAGUE_DEPLOYMENT
LEAGUES = {k: v for k, v in ALL_LEAGUES.items() if LEAGUE_DEPLOYMENT.get(k) == "active"}

# Per-league post-model calibration (loaded from JSON)
_LEAGUE_CAL_PATH = MODELS_DIR / "league_calibration.json"
_LEAGUE_CALIBRATION: dict = {}
if _LEAGUE_CAL_PATH.exists():
    try:
        _LEAGUE_CALIBRATION = json.loads(_LEAGUE_CAL_PATH.read_text())
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Stadium coordinates for weather lookup
# ---------------------------------------------------------------------------
STADIUM_COORDS: dict[str, tuple[float, float]] = {
    # EPL
    "Arsenal":          (51.5549, -0.1083),
    "Aston Villa":      (52.5090, -1.8847),
    "Bournemouth":      (50.7352, -1.8382),
    "Brentford":        (51.4882, -0.2887),
    "Brighton":         (50.8618, -0.0830),
    "Burnley":          (53.7889, -2.2306),
    "Chelsea":          (51.4816, -0.1909),
    "Crystal Palace":   (51.3983, -0.0856),
    "Everton":          (53.4388, -2.9664),
    "Fulham":           (51.4749, -0.2217),
    "Ipswich":          (52.0543,  1.1447),
    "Leeds":            (53.7777, -1.5724),
    "Leicester":        (52.6204, -1.1423),
    "Liverpool":        (53.4308, -2.9608),
    "Luton":            (51.8842, -0.4299),
    "Man City":         (53.4831, -2.2004),
    "Man United":       (53.4631, -2.2913),
    "Newcastle":        (54.9757, -1.6215),
    "Norwich":          (52.6225,  1.3087),
    "Nott'm Forest":    (52.9399, -1.1328),
    "Nottingham":       (52.9399, -1.1328),
    "Sheffield United": (53.3703, -1.4706),
    "Southampton":      (50.9058, -1.3911),
    "Tottenham":        (51.6042, -0.0665),
    "Watford":          (51.6497, -0.4014),
    "West Brom":        (52.5090, -1.9642),
    "West Ham":         (51.5387,  0.0167),
    "Wolves":           (52.5902, -2.1304),
    "Sunderland":       (54.9142, -1.3881),
    # Bundesliga
    "Bayern Munich":    (48.2188, 11.6253),
    "Dortmund":         (51.4926,  7.4519),
    "RB Leipzig":       (51.3459, 12.3483),
    "Leverkusen":       (51.0380,  6.9836),
    "Frankfurt":        (50.0688,  8.6450),
    "Eintracht Frankfurt": (50.0688, 8.6450),
    "M'gladbach":       (51.1748,  6.3851),
    "Gladbach":         (51.1748,  6.3851),
    "Hoffenheim":       (49.2381,  8.8892),
    "Wolfsburg":        (52.4299, 10.8037),
    "Freiburg":         (48.0225,  7.8980),
    "Augsburg":         (48.3233, 10.9031),
    "Union Berlin":     (52.4576, 13.5686),
    "Hertha":           (52.5147, 13.2395),
    "Stuttgart":        (48.7928,  9.2322),
    "Werder Bremen":    (53.0665,  8.8377),
    "Mainz":            (49.9840,  8.2241),
    "Cologne":          (50.9333,  6.8750),
    "Bochum":           (51.4899,  7.2179),
    "Schalke":          (51.5543,  7.0676),
    "Bielefeld":        (51.9999,  8.5329),
    "Furth":            (49.4940, 10.9737),
    "Heidenheim":       (48.6851, 10.1507),
    "Darmstadt":        (49.8673,  8.6534),
    "Holstein Kiel":    (54.3350, 10.1390),
    "St. Pauli":        (53.5543,  9.9674),
    # Serie A
    "Atalanta":         (45.7092,  9.6811),
    "Bologna":          (44.4924, 11.3098),
    "Cagliari":         (39.1999,  9.1371),
    "Como":             (45.8069,  9.0966),
    "Empoli":           (43.7266, 10.9560),
    "Fiorentina":       (43.7808, 11.2822),
    "Genoa":            (44.4165,  8.9524),
    "Inter":            (45.4781,  9.1240),
    "Juventus":         (45.1097,  7.6413),
    "Lazio":            (41.9340, 12.4544),
    "Lecce":            (40.3544, 18.1714),
    "Milan":            (45.4781,  9.1240),
    "Monza":            (45.5847,  9.3010),
    "Napoli":           (40.8280, 14.1930),
    "Parma":            (44.7951, 10.3389),
    "Roma":             (41.9340, 12.4544),
    "Salernitana":      (40.6842, 14.7766),
    "Sassuolo":         (44.7148, 10.6472),
    "Torino":           (45.0421,  7.6499),
    "Udinese":          (46.0812, 13.2000),
    "Venezia":          (45.4386, 12.3464),
    "Verona":           (45.4353, 10.9685),
    # La Liga
    "Ath Madrid":       (40.4362, -3.5995),
    "Ath Bilbao":       (43.2643, -2.9493),
    "Barcelona":        (41.3809,  2.1228),
    "Betis":            (37.3564, -5.9819),
    "Celta":            (42.2117, -8.7389),
    "Espanol":          (41.3479,  2.0754),
    "Getafe":           (40.3256, -3.7144),
    "Girona":           (41.9616,  2.8285),
    "Las Palmas":       (28.1003,-15.4567),
    "Leganes":          (40.3569, -3.7567),
    "Mallorca":         (39.5906,  2.6307),
    "Osasuna":          (42.7966, -1.6361),
    "Real Madrid":      (40.4530, -3.6883),
    "Sevilla":          (37.3841, -5.9705),
    "Sociedad":         (43.3013, -1.9737),
    "Valencia":         (39.4745, -0.3583),
    "Vallecano":        (40.3917, -3.6589),
    "Valladolid":       (41.6444, -4.7614),
    "Villarreal":       (39.9438, -0.1035),
    # Ligue 1
    "Angers":           (47.4606, -0.5335),
    "Auxerre":          (47.7997,  3.5801),
    "Brest":            (48.4028, -4.4617),
    "Le Havre":         (49.4985,  0.1589),
    "Lens":             (50.4327,  2.8155),
    "Lille":            (50.6119,  3.1302),
    "Lyon":             (45.7653,  4.9822),
    "Marseille":        (43.2700,  5.3959),
    "Monaco":           (43.7277,  7.4156),
    "Montpellier":      (43.6221,  3.8119),
    "Nantes":           (47.2569, -1.5250),
    "Nice":             (43.7051,  7.1925),
    "Paris SG":         (48.8414,  2.2530),
    "Reims":            (49.2469,  3.9303),
    "Rennes":           (48.1075, -1.7128),
    "St Etienne":       (45.4608,  4.3903),
    "Strasbourg":       (48.5601,  7.7529),
    "Toulouse":         (43.5833,  1.4340),
}
FALLBACK_COORDS = {
    "EPL": (51.5, -0.1),
    "BUN": (51.5, 7.5),
    "LGA": (40.5, -3.7),
    "SEA": (42.5, 12.5),
    "LG1": (48.9, 2.4),
}


def get_coords(team: str, league: str) -> tuple[float, float]:
    for name, coords in STADIUM_COORDS.items():
        if name.lower() in team.lower() or team.lower() in name.lower():
            return coords
    for name, coords in STADIUM_COORDS.items():
        if any(w in team.lower() for w in name.lower().split() if len(w) > 3):
            return coords
    return FALLBACK_COORDS.get(league, (51.5, -0.1))


# ---------------------------------------------------------------------------
# Feature columns (must match training exactly)
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "league_avg_goals_rolling_season", "league_avg_xg_rolling_season",
    "league_home_adv",
    "is_bun", "is_lga", "is_sea", "is_lg1",
    "league_goals_rolling_10", "league_xg_rolling_10",
    "home_xg_for_rolling_10", "home_xg_against_rolling_10",
    "away_xg_for_rolling_10", "away_xg_against_rolling_10",
    "home_xg_for_rolling_3",  "home_xg_against_rolling_3",
    "away_xg_for_rolling_3",  "away_xg_against_rolling_3",
    "home_xg_for_rolling_15", "home_xg_against_rolling_15",
    "away_xg_for_rolling_15", "away_xg_against_rolling_15",
    "home_shots_for_rolling_10", "home_shots_against_rolling_10",
    "away_shots_for_rolling_10", "away_shots_against_rolling_10",
    "home_shots_on_target_rolling_10", "away_shots_on_target_rolling_10",
    "home_shots_for_rolling_3", "away_shots_for_rolling_3",
    "home_goals_scored_rolling_5", "home_goals_conceded_rolling_5",
    "away_goals_scored_rolling_5", "away_goals_conceded_rolling_5",
    "home_goals_scored_rolling_3", "away_goals_scored_rolling_3",
    "home_days_rest", "away_days_rest",
    "home_matches_last_7", "away_matches_last_7",
    "home_xg_mismatch", "away_xg_mismatch",
    "home_shot_mismatch", "away_shot_mismatch",
    "home_form_mismatch", "away_form_mismatch",
    "home_lineup_delta", "away_lineup_delta",
    "home_att_strength", "away_att_strength",
    "home_def_strength", "away_def_strength",
    "home_first_choice_gk_missing", "away_first_choice_gk_missing",
    "home_primary_attacker_missing", "away_primary_attacker_missing",
    "home_lineup_overlap_last_match", "away_lineup_overlap_last_match",
    "home_lineup_overlap_rolling_3", "away_lineup_overlap_rolling_3",
    "home_num_defenders", "away_num_defenders",
    "home_num_attackers", "away_num_attackers",
    "home_back_five", "away_back_five",
    "home_attack_delta_vs_away_defense", "away_attack_delta_vs_home_defense",
    "net_lineup_attack_edge", "net_lineup_defense_weakness",
    "market_fair_p_over_1_5", "market_fair_p_over_3_5",
    "market_low_total_pressure", "market_high_total_pressure",
    "market_implied_mu",
    "market_move_to_over_2_5", "market_move_magnitude_2_5",
    "market_late_move_over", "market_late_move_under",
    "home_injury_count", "away_injury_count",
    "home_key_player_injured", "away_key_player_injured",
    "home_total_absence_score", "away_total_absence_score",
    "weather_wind_high", "weather_rain",
    "weather_temp_cold", "weather_extreme",
    "weather_wind_kph", "weather_precip_mm",
    "ref_avg_goals", "ref_red_card_rate",
    "ref_penalty_rate", "ref_available",
]

# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------
def load_api_keys() -> dict[str, str]:
    env_path = BASE_DIR / ".env"
    keys: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                keys[k.strip()] = v.strip()
    for k in ("ODDS_API_KEY", "API_FOOTBALL_KEY"):
        keys.setdefault(k, os.environ.get(k, ""))
    return keys


# ---------------------------------------------------------------------------
# Poisson market math (replicate A1 logic)
# ---------------------------------------------------------------------------
def _poisson_over_prob(mu: float, threshold: float) -> float:
    k = int(threshold)
    return 1.0 - stats.poisson.cdf(k, mu)


def remove_vig(over_dec: float, under_dec: float) -> tuple[float, float]:
    if pd.isna(over_dec) or pd.isna(under_dec) or over_dec <= 1.0 or under_dec <= 1.0:
        return np.nan, np.nan
    imp_o = 1.0 / over_dec
    imp_u = 1.0 / under_dec
    total = imp_o + imp_u
    return imp_o / total, imp_u / total


def fair_p_to_mu(p: float) -> float:
    if pd.isna(p) or p <= 0 or p >= 1:
        return np.nan
    try:
        f = lambda mu: _poisson_over_prob(mu, 2.5) - p
        if f(0.5) * f(8.0) > 0:
            return float(np.clip(p * 4.5, 0.5, 8.0))
        return float(brentq(f, 0.5, 8.0, xtol=1e-4))
    except Exception:
        return np.nan


def derive_market_features(fair_p_over_2_5: float,
                            fair_p_over_2_5_open: float) -> dict:
    out = {
        "market_fair_p_over_2_5":  fair_p_over_2_5,
        "market_fair_p_under_2_5": 1.0 - fair_p_over_2_5 if not pd.isna(fair_p_over_2_5) else np.nan,
        "market_fair_p_over_1_5":  np.nan,
        "market_fair_p_over_3_5":  np.nan,
        "market_implied_mu":        np.nan,
        "market_low_total_pressure":  np.nan,
        "market_high_total_pressure": np.nan,
        "market_move_to_over_2_5":    0.0,
        "market_move_magnitude_2_5":  0.0,
        "market_late_move_over":      0.0,
        "market_late_move_under":     0.0,
        "market_odds_available":      0.0,
    }
    if pd.isna(fair_p_over_2_5):
        return out
    out["market_odds_available"] = 1.0
    mu = fair_p_to_mu(fair_p_over_2_5)
    if not pd.isna(mu):
        out["market_implied_mu"]       = mu
        out["market_fair_p_over_1_5"]  = _poisson_over_prob(mu, 1.5)
        out["market_fair_p_over_3_5"]  = _poisson_over_prob(mu, 3.5)
        out["market_low_total_pressure"]  = out["market_fair_p_over_1_5"] - fair_p_over_2_5
        out["market_high_total_pressure"] = fair_p_over_2_5 - out["market_fair_p_over_3_5"]
    if not pd.isna(fair_p_over_2_5_open):
        move = fair_p_over_2_5 - fair_p_over_2_5_open
        out["market_move_to_over_2_5"]   = move
        out["market_move_magnitude_2_5"] = abs(move)
        out["market_late_move_over"]     = 1.0 if move > 0.03 else 0.0
        out["market_late_move_under"]    = 1.0 if move < -0.03 else 0.0
    return out


# ---------------------------------------------------------------------------
# API-Football client
# ---------------------------------------------------------------------------
class APIFootballClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers["x-apisports-key"] = api_key
        self.quota = None

    def get(self, endpoint: str, params: dict, cache_key: str | None = None) -> dict:
        if cache_key:
            cache_file = CACHE_DIR / f"{cache_key}.json"
            if cache_file.exists():
                return json.loads(cache_file.read_text())

        url = f"{API_FOOTBALL_BASE}/{endpoint.lstrip('/')}"
        for attempt in range(3):
            try:
                time.sleep(0.55)
                resp = self.session.get(url, params=params, timeout=20)
                self.quota = resp.headers.get("x-ratelimit-requests-remaining")
                if resp.status_code in (429, 502, 503, 504):
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                if cache_key:
                    CACHE_DIR.joinpath(f"{cache_key}.json").write_text(
                        json.dumps(data)
                    )
                return data
            except Exception as e:
                if attempt < 2:
                    time.sleep(5)
        return {"response": [], "results": 0}


# ---------------------------------------------------------------------------
# Odds API
# ---------------------------------------------------------------------------
def fetch_odds(sport: str, odds_api_key: str) -> list[dict]:
    """Fetch current totals odds from The Odds API."""
    if not odds_api_key:
        return []
    cache_file = CACHE_DIR / f"odds_{sport}_{date.today().isoformat()}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass
    try:
        params = {
            "apiKey":  odds_api_key,
            "regions": "uk,eu",
            "markets": "totals",
            "oddsFormat": "decimal",
        }
        url = f"{ODDS_API_BASE}/sports/{sport}/odds"
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            cache_file.write_text(json.dumps(data))
            return data
        elif resp.status_code == 404:
            logger.warning(f"[odds] sport key not found: {sport}")
        else:
            logger.warning(f"[odds] HTTP {resp.status_code} for {sport}")
    except Exception as e:
        logger.warning(f"[odds] fetch failed: {e}")
    return []


def parse_odds_for_game(
    odds_data: list[dict],
    home_team: str,
    away_team: str,
) -> dict:
    """
    Find 2.5 over/under opening+closing prices for the given matchup.
    Tries multiple bookmakers; prefers bet365, betfair, pinnacle.
    """
    BOOK_PRIORITY = ["bet365", "pinnacle", "betfair", "unibet", "williamhill"]

    result = {
        "over_dec_open": np.nan, "under_dec_open": np.nan,
        "over_dec_close": np.nan, "under_dec_close": np.nan,
        "book": None,
    }

    def name_matches(a: str, b: str) -> bool:
        a, b = a.lower(), b.lower()
        return a in b or b in a or any(
            w in b for w in a.split() if len(w) > 4
        )

    for game in odds_data:
        ht = game.get("home_team", "")
        at = game.get("away_team", "")
        if not (name_matches(home_team, ht) and name_matches(away_team, at)):
            continue
        bookmakers = game.get("bookmakers", [])
        # Sort by priority
        def book_rank(b):
            k = b.get("key", "")
            for i, bk in enumerate(BOOK_PRIORITY):
                if bk in k:
                    return i
            return len(BOOK_PRIORITY)
        bookmakers.sort(key=book_rank)

        for bm in bookmakers:
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "totals":
                    continue
                outcomes = mkt.get("outcomes", [])
                for o in outcomes:
                    point = o.get("point", 0)
                    if abs(point - 2.5) > 0.01:
                        continue
                    name = o.get("name", "").lower()
                    price = o.get("price", np.nan)
                    if "over" in name:
                        result["over_dec_close"]  = price
                        result["over_dec_open"]   = price  # treat as open if only one available
                    elif "under" in name:
                        result["under_dec_close"] = price
                        result["under_dec_open"]  = price
                result["book"] = bm.get("key")
            if not pd.isna(result["over_dec_close"]):
                break
        if not pd.isna(result["over_dec_close"]):
            break
    return result


# ---------------------------------------------------------------------------
# Weather (Open-Meteo forecast)
# ---------------------------------------------------------------------------
def fetch_weather_forecast(lat: float, lon: float, target_date: str,
                           kickoff_hour_utc: int = 15) -> dict:
    cache_key = f"weather_{lat:.3f}_{lon:.3f}_{target_date}"
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass
    try:
        params = {
            "latitude":   lat,
            "longitude":  lon,
            "hourly":     "temperature_2m,windspeed_10m,precipitation",
            "start_date": target_date,
            "end_date":   target_date,
            "timezone":   "UTC",
        }
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            cache_file.write_text(json.dumps(data))
            return data
    except Exception as e:
        logger.warning(f"[weather] {e}")
    return {}


def extract_weather(data: dict, kickoff_hour: int) -> dict:
    empty = {
        "weather_wind_kph": np.nan, "weather_precip_mm": np.nan,
        "weather_temp_c": np.nan,
        "weather_wind_high": 0.0, "weather_rain": 0.0,
        "weather_temp_cold": 0.0, "weather_extreme": 0.0,
    }
    if not data or "hourly" not in data:
        return empty
    h = data["hourly"]
    times = h.get("time", [])
    if not times:
        return empty
    idx = min(range(len(times)),
              key=lambda i: abs(int(times[i].split("T")[1].split(":")[0]) - kickoff_hour))
    def g(k):
        v = h.get(k, [])
        return float(v[idx]) if idx < len(v) and v[idx] is not None else np.nan
    wind = g("windspeed_10m")
    precip = g("precipitation")
    temp = g("temperature_2m")
    wind_high = float(wind > 30) if not pd.isna(wind) else 0.0
    rain      = float(precip > 1.0) if not pd.isna(precip) else 0.0
    cold      = float(temp < 5.0)   if not pd.isna(temp)   else 0.0
    extreme   = float(wind_high or rain)
    return {
        "weather_wind_kph":   wind,
        "weather_precip_mm":  precip,
        "weather_temp_c":     temp,
        "weather_wind_high":  wind_high,
        "weather_rain":       rain,
        "weather_temp_cold":  cold,
        "weather_extreme":    extreme,
    }


# ---------------------------------------------------------------------------
# Referee features
# ---------------------------------------------------------------------------
def load_ref_defaults() -> dict:
    """Load league-average ref stats as fallback."""
    defaults = {
        "ref_avg_goals": 2.79, "ref_red_card_rate": 0.113,
        "ref_penalty_rate": 0.30, "ref_home_adv": 0.0, "ref_available": 0.0,
    }
    if REF_PATH.exists():
        try:
            rf = pd.read_parquet(REF_PATH)
            avail = rf[rf["ref_available"] == 1]
            if not avail.empty:
                defaults["ref_avg_goals"]    = float(avail["ref_avg_goals"].mean())
                defaults["ref_red_card_rate"] = float(avail["ref_red_card_rate"].mean())
                defaults["ref_penalty_rate"] = float(avail["ref_penalty_rate"].mean())
        except Exception:
            pass
    return defaults


def get_ref_features(referee_name: str | None,
                     ref_df: pd.DataFrame,
                     defaults: dict) -> dict:
    """Look up referee rolling stats. Falls back to defaults if unknown."""
    if referee_name and ref_df is not None and not ref_df.empty:
        for col in ("referee", "Referee"):
            if col in ref_df.columns:
                match = ref_df[ref_df[col].str.lower() == referee_name.lower()]
                if not match.empty:
                    row = match.iloc[-1]
                    return {
                        "ref_avg_goals":    float(row.get("ref_avg_goals", defaults["ref_avg_goals"])),
                        "ref_red_card_rate": float(row.get("ref_red_card_rate", defaults["ref_red_card_rate"])),
                        "ref_penalty_rate": float(row.get("ref_penalty_rate", defaults["ref_penalty_rate"])),
                        "ref_home_adv":     float(row.get("ref_home_adv", 0.0)),
                        "ref_available":    1.0,
                    }
                break
    return dict(defaults)


# ---------------------------------------------------------------------------
# Rolling feature computation from canonical
# ---------------------------------------------------------------------------
def _rolling_tail(series: list[float], n: int) -> float:
    vals = [v for v in series[-n:] if not pd.isna(v)]
    return float(np.mean(vals)) if vals else np.nan


def compute_team_rolling(team: str, prior_games: pd.DataFrame,
                         as_side: str,   # "home" or "away"
                         game_date: pd.Timestamp) -> dict:
    """
    Compute rolling stats for one team from prior game records.
    prior_games: rows where team played (any side), sorted by date ascending.
    as_side: "home" or "away" — determines which prefix to use in result.
    """
    pg = prior_games.sort_values("game_date")

    def col_or_nan(row, *cols):
        for c in cols:
            if c in row.index and not pd.isna(row[c]):
                return float(row[c])
        return np.nan

    # Build per-game vectors
    xg_for, xg_against, shots_for, shots_against, shots_ot, goals_scored, goals_conceded = [], [], [], [], [], [], []
    dates_list = []

    for _, r in pg.iterrows():
        is_home = (r.get("home_team") == team)
        if is_home:
            xg_f = col_or_nan(r, "home_xg_raw")
            xg_a = col_or_nan(r, "away_xg_raw")
            sf   = col_or_nan(r, "home_shots")
            sa   = col_or_nan(r, "away_shots")
            sot  = col_or_nan(r, "home_shots_on_target")
            gs   = col_or_nan(r, "home_score")
            gc   = col_or_nan(r, "away_score")
        else:
            xg_f = col_or_nan(r, "away_xg_raw")
            xg_a = col_or_nan(r, "home_xg_raw")
            sf   = col_or_nan(r, "away_shots")
            sa   = col_or_nan(r, "home_shots")
            sot  = col_or_nan(r, "away_shots_on_target")
            gs   = col_or_nan(r, "away_score")
            gc   = col_or_nan(r, "home_score")
        xg_for.append(xg_f); xg_against.append(xg_a)
        shots_for.append(sf); shots_against.append(sa)
        shots_ot.append(sot)
        goals_scored.append(gs); goals_conceded.append(gc)
        dates_list.append(pd.to_datetime(r["game_date"]))

    p = as_side

    # Last days rest
    if dates_list:
        last_date = max(dates_list)
        rest_days = (game_date - last_date).days
    else:
        rest_days = np.nan

    # Matches in last 7 days
    m_last_7 = sum(1 for d in dates_list if (game_date - d).days <= 7) if dates_list else 0

    return {
        f"{p}_xg_for_rolling_10":          _rolling_tail(xg_for,       10),
        f"{p}_xg_against_rolling_10":       _rolling_tail(xg_against,   10),
        f"{p}_xg_for_rolling_3":            _rolling_tail(xg_for,        3),
        f"{p}_xg_against_rolling_3":        _rolling_tail(xg_against,    3),
        f"{p}_xg_for_rolling_15":           _rolling_tail(xg_for,       15),
        f"{p}_xg_against_rolling_15":       _rolling_tail(xg_against,   15),
        f"{p}_shots_for_rolling_10":        _rolling_tail(shots_for,     10),
        f"{p}_shots_against_rolling_10":    _rolling_tail(shots_against, 10),
        f"{p}_shots_on_target_rolling_10":  _rolling_tail(shots_ot,      10),
        f"{p}_shots_for_rolling_3":         _rolling_tail(shots_for,      3),
        f"{p}_goals_scored_rolling_5":      _rolling_tail(goals_scored,   5),
        f"{p}_goals_conceded_rolling_5":    _rolling_tail(goals_conceded, 5),
        f"{p}_goals_scored_rolling_3":      _rolling_tail(goals_scored,   3),
        f"{p}_days_rest":                   rest_days,
        f"{p}_matches_last_7":              m_last_7,
        f"{p}_n_games_prior":               len(pg),
    }


def compute_league_rolling(canon: pd.DataFrame, league: str,
                           season: str, game_date: pd.Timestamp) -> dict:
    """League-level rolling averages from prior games this season."""
    prior = canon[
        (canon["league_id"] == league) &
        (canon["season_year"] == season) &
        (pd.to_datetime(canon["game_date"]) < game_date)
    ].copy()

    if prior.empty:
        return {
            "league_avg_goals_rolling_season": 2.65,
            "league_avg_xg_rolling_season":    2.65,
            "league_home_adv":                 0.30,
            "league_goals_rolling_10":         2.65,
            "league_xg_rolling_10":            2.65,
        }

    total_goals = prior["home_score"] + prior["away_score"]
    total_xg    = prior["home_xg_raw"].fillna(0) + prior["away_xg_raw"].fillna(0)
    home_wins   = prior[prior["home_score"] > prior["away_score"]]

    return {
        "league_avg_goals_rolling_season": float(total_goals.mean()),
        "league_avg_xg_rolling_season":    float(total_xg.mean()),
        "league_home_adv":                 float(len(home_wins) / max(len(prior), 1)),
        "league_goals_rolling_10":         float(total_goals.tail(10).mean()),
        "league_xg_rolling_10":            float(total_xg.tail(10).mean()),
    }


# ---------------------------------------------------------------------------
# Lineup features (from API-Football lineup response)
# ---------------------------------------------------------------------------
def parse_lineup_features(lineup_data: dict, home_team: str,
                           away_team: str) -> dict:
    """Parse lineup response into features. Returns zeros if not yet announced."""
    defaults = {
        "home_lineup_delta": 0.0, "away_lineup_delta": 0.0,
        "home_att_strength": 0.0, "away_att_strength": 0.0,
        "home_def_strength": 0.0, "away_def_strength": 0.0,
        "home_first_choice_gk_missing": 0.0, "away_first_choice_gk_missing": 0.0,
        "home_primary_attacker_missing": 0.0, "away_primary_attacker_missing": 0.0,
        "home_lineup_overlap_last_match": np.nan, "away_lineup_overlap_last_match": np.nan,
        "home_lineup_overlap_rolling_3": np.nan, "away_lineup_overlap_rolling_3": np.nan,
        "home_num_defenders": np.nan, "away_num_defenders": np.nan,
        "home_num_attackers": np.nan, "away_num_attackers": np.nan,
        "home_back_five": 0.0, "away_back_five": 0.0,
        "home_attack_delta_vs_away_defense": 0.0, "away_attack_delta_vs_home_defense": 0.0,
        "net_lineup_attack_edge": 0.0, "net_lineup_defense_weakness": 0.0,
        "lineup_confirmed": False,
    }
    response = lineup_data.get("response", [])
    if not response:
        return defaults

    out = dict(defaults)
    out["lineup_confirmed"] = True

    for team_data in response:
        team_name = team_data.get("team", {}).get("name", "")
        lineup    = team_data.get("startXI", [])
        if not lineup:
            continue

        positions = [p.get("player", {}).get("pos", "") for p in lineup if p.get("player")]
        n_def = sum(1 for pos in positions if pos in ("D", "CB", "LB", "RB", "WB"))
        n_att = sum(1 for pos in positions if pos in ("F", "ST", "CF", "LW", "RW"))
        formation = team_data.get("formation", "") or ""
        back5 = 1.0 if any(f in formation for f in ("5-", "3-")) else 0.0

        def side_of(t):
            if t == home_team or home_team.lower() in t.lower() or t.lower() in home_team.lower():
                return "home"
            return "away"

        side = side_of(team_name)
        out[f"{side}_num_defenders"] = float(n_def)
        out[f"{side}_num_attackers"] = float(n_att)
        out[f"{side}_back_five"]     = back5

    return out


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
def load_model() -> tuple:
    with open(RIDGE_PKL, "rb") as f:
        ridge = pickle.load(f)
    with open(CALIBRATOR_PKL, "rb") as f:
        calibrator = pickle.load(f)
    with open(SCALER_PKL, "rb") as f:
        scaler = pickle.load(f)
    with open(IMPUTE_PKL, "rb") as f:
        impute_vals = pickle.load(f)
    return ridge, calibrator, scaler, impute_vals


# ---------------------------------------------------------------------------
# V2.2c shadow challenger logging
# ---------------------------------------------------------------------------
def _log_v2_2c_shadow(sig: dict) -> None:
    """Compute V2.2c shrinkage probability and append to shadow log. Non-fatal."""
    try:
        mkt_p = sig.get("market_fair_p_over_2_5")
        cal_p = sig.get("ridge_cal_p")
        if mkt_p is None or cal_p is None:
            return
        v2_2c_p = float(np.clip(mkt_p + V2_2C_ALPHA * (cal_p - mkt_p), 0.01, 0.99))
        v2_2c_edge = v2_2c_p - mkt_p
        record = {
            "game_id":       sig.get("game_id"),
            "date":          sig.get("game_date"),
            "league":        sig.get("league_id"),
            "home_team":     sig.get("home_team"),
            "away_team":     sig.get("away_team"),
            "v2_2_edge":     round(sig.get("edge", 0), 6),
            "v2_2_p_over":   round(cal_p, 6),
            "v2_2c_edge":    round(v2_2c_edge, 6),
            "v2_2c_p_over":  round(v2_2c_p, 6),
            "market_p_over": round(mkt_p, 6),
            "closing_line":  sig.get("closing_total"),
            "actual_goals":  None,
            "result":        None,
            "logged_at":     datetime.now(timezone.utc).isoformat(),
        }
        V2_2C_SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if V2_2C_SHADOW_LOG.exists():
            try:
                existing = json.loads(V2_2C_SHADOW_LOG.read_text())
            except Exception:
                existing = []
        # Avoid duplicate game_id entries
        existing_ids = {r.get("game_id") for r in existing}
        if record["game_id"] not in existing_ids:
            existing.append(record)
            V2_2C_SHADOW_LOG.write_text(json.dumps(existing, indent=2, default=str))
            logger.info(f"    [v2.2c shadow] logged: edge={v2_2c_edge:+.4f}")
    except Exception as e:
        logger.warning(f"    [v2.2c shadow] non-fatal error: {e}")


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------
def get_confidence_tier(edge: float) -> str:
    if edge >= 0.10:
        return "HIGH"
    if edge >= 0.08:
        return "MEDIUM"
    return "LOW"


def predict_fixture(
    fixture_row: dict,
    features: dict,
    ridge, calibrator, scaler, impute_vals: dict,
) -> dict:
    """
    Run one fixture through the model. Returns dict with predictions.
    """
    # Build feature vector
    vec = {}
    for col in FEATURE_COLS:
        vec[col] = features.get(col, impute_vals.get(col, 0.0))

    # Impute remaining NaNs
    for col, val in impute_vals.items():
        if col in vec and (pd.isna(vec[col]) or vec[col] is None):
            vec[col] = val

    # Force numeric
    row_arr = np.array([float(vec.get(c, 0.0)) if not pd.isna(vec.get(c, np.nan)) else 0.0
                        for c in FEATURE_COLS], dtype=float).reshape(1, -1)

    # Scale + predict
    row_scaled         = scaler.transform(row_arr)
    pred_residual      = float(ridge.predict(row_scaled)[0])
    market_p           = features.get("market_fair_p_over_2_5", np.nan)

    if pd.isna(market_p):
        market_p = 0.567   # OOS mean as fallback

    raw_p        = float(np.clip(market_p + pred_residual, 0.05, 0.95))
    calibrated_p = float(np.clip(calibrator.predict([raw_p])[0], 0.05, 0.95))
    edge         = float(calibrated_p - market_p)

    # Market move filter
    market_move = features.get("market_move_to_over_2_5", 0.0)

    return {
        "ridge_pred_residual": pred_residual,
        "market_fair_p_over_2_5": market_p,
        "ridge_raw_p":   raw_p,
        "ridge_cal_p":   calibrated_p,
        "edge":          edge,
        "market_move_to_over_2_5": market_move,
    }


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def grade_yesterday(api_client: APIFootballClient, game_date_str: str) -> int:
    """
    Look up yesterday's API-Football results, match to ungraded decisions,
    update result = WIN/LOSS/PUSH and graded = 1.
    """
    if not DECISIONS_PATH.exists():
        return 0

    dec = pd.read_parquet(DECISIONS_PATH)
    dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)

    yesterday = (datetime.strptime(game_date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    ungraded = dec[(dec["game_date"] == yesterday) & (dec.get("graded", pd.Series(0)) == 0)]
    if ungraded.empty:
        logger.info(f"[grade] No ungraded signals for {yesterday}")
        return 0

    graded_count = 0
    for league_id, info in LEAGUES.items():
        league_sigs = ungraded[ungraded["league_id"] == league_id]
        if league_sigs.empty:
            continue
        data = api_client.get(
            "fixtures",
            {"date": yesterday, "league": info["api_football_id"], "season": info["season"]},
            cache_key=f"grade_{league_id}_{yesterday}",
        )
        results_map: dict[str, tuple[int, int]] = {}
        for fix in data.get("response", []):
            ht = fix.get("teams", {}).get("home", {}).get("name", "")
            at = fix.get("teams", {}).get("away", {}).get("name", "")
            hs = fix.get("goals", {}).get("home")
            as_ = fix.get("goals", {}).get("away")
            if hs is not None and as_ is not None:
                results_map[f"{ht}|{at}"] = (int(hs), int(as_))

        for idx, row in league_sigs.iterrows():
            best_match = None
            for key, (hs, aw) in results_map.items():
                ht, at = key.split("|")
                hn, an = row.get("home_team", ""), row.get("away_team", "")
                if (hn.lower() in ht.lower() or ht.lower() in hn.lower()) and \
                   (an.lower() in at.lower() or at.lower() in an.lower()):
                    best_match = (hs, aw)
                    break
            if best_match is None:
                continue
            total = best_match[0] + best_match[1]
            signal = row.get("signal_side", "OVER")
            line   = row.get("closing_total", 2.5)
            if total > line:
                result = "WIN" if signal == "OVER" else "LOSS"
            elif total < line:
                result = "WIN" if signal == "UNDER" else "LOSS"
            else:
                result = "PUSH"
            dec.at[idx, "result"] = result
            dec.at[idx, "actual_total_goals"] = total
            dec.at[idx, "graded"] = 1
            graded_count += 1

    dec.to_parquet(DECISIONS_PATH, index=False)
    logger.info(f"[grade] Graded {graded_count} signals for {yesterday}")
    return graded_count


# ---------------------------------------------------------------------------
# Live stop rules
# ---------------------------------------------------------------------------
STOP_TIER_MIN_N   = 25      # min graded signals before tier stop applies
STOP_TIER_ROI     = -0.08   # tier suspended if live ROI < -8%
STOP_OVERALL_MIN_N = 50     # min graded signals before overall stop applies
STOP_OVERALL_ROI  = -0.10   # model suspended if overall live ROI < -10%


def check_stop_rules() -> dict:
    """
    Read live graded decisions and evaluate hard stop rules.

    Returns:
        {
            "overall_suspended": bool,
            "suspended_tiers":   set[str],   # {"HIGH", "MEDIUM", "LOW"}
            "overall_n":         int,
            "overall_roi":       float | None,
            "tier_stats":        {"HIGH": {"n": int, "roi": float}, ...},
        }
    """
    result = {
        "overall_suspended": False,
        "suspended_tiers":   set(),
        "overall_n":         0,
        "overall_roi":       None,
        "tier_stats":        {},
    }

    if not DECISIONS_PATH.exists():
        return result

    try:
        dec = pd.read_parquet(DECISIONS_PATH)
    except Exception:
        return result

    if "split" not in dec.columns or "graded" not in dec.columns:
        return result

    graded = dec[(dec["split"] == "live") & (dec["graded"] == 1)].copy()
    if graded.empty:
        return result

    def _roi(df: pd.DataFrame) -> tuple[int, float | None]:
        n = len(df)
        if n == 0:
            return 0, None
        W = (df["result"] == "WIN").sum()
        L = (df["result"] == "LOSS").sum()
        wl = W + L
        if wl == 0:
            return n, None
        roi = (W * WIN_PER_UNIT - L) / wl
        return n, float(roi)

    # Overall
    overall_n, overall_roi = _roi(graded)
    result["overall_n"]   = overall_n
    result["overall_roi"] = overall_roi

    if overall_n >= STOP_OVERALL_MIN_N and overall_roi is not None and overall_roi < STOP_OVERALL_ROI:
        result["overall_suspended"] = True
        msg = (
            f"Soccer model suspended pending review — "
            f"overall live ROI {overall_roi:+.1%} below "
            f"{STOP_OVERALL_ROI:+.0%} threshold (n={overall_n})"
        )
        logger.warning(msg)
        print(f"  ⛔  {msg}")

    # Per tier
    for tier in ("HIGH", "MEDIUM", "LOW"):
        sub = graded[graded["confidence_tier"] == tier]
        tn, troi = _roi(sub)
        result["tier_stats"][tier] = {"n": tn, "roi": troi}
        if tn >= STOP_TIER_MIN_N and troi is not None and troi < STOP_TIER_ROI:
            result["suspended_tiers"].add(tier)
            msg = (
                f"[{tier}] suspended: live ROI {troi:+.1%} below "
                f"{STOP_TIER_ROI:+.0%} threshold (n={tn})"
            )
            logger.warning(msg)
            print(f"  ⛔  {msg}")

    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(game_date: str, use_odds: bool = True,
                 refresh_lineups_only: bool = False,
                 grade_yesterday_flag: bool = False) -> list[dict]:
    logger.info(f"Soccer daily pipeline — {game_date}")
    keys = load_api_keys()
    api_key  = keys.get("API_FOOTBALL_KEY", "")
    odds_key = keys.get("ODDS_API_KEY", "")

    if not api_key:
        logger.error("API_FOOTBALL_KEY not set — cannot fetch fixtures")
        return []

    api = APIFootballClient(api_key)

    # Grade yesterday first if requested
    if grade_yesterday_flag:
        grade_yesterday(api, game_date)

    if refresh_lineups_only:
        # Wipe lineup caches for today's games and re-fetch
        for f in CACHE_DIR.glob(f"lineups_*_{game_date}*.json"):
            f.unlink()
        logger.info("[lineup] Cleared lineup caches — will re-fetch")

    # Check live stop rules (after grading so data is fresh)
    stop_status = check_stop_rules()
    if stop_status["overall_suspended"]:
        logger.warning("[stop] Overall suspension active — no signals generated.")
        return []

    # Load canonical and ref data
    if not CANONICAL_PATH.exists():
        logger.error("soccer_canonical.parquet not found")
        return []
    canon = pd.read_parquet(CANONICAL_PATH)
    canon["game_date"] = pd.to_datetime(canon["game_date"])

    ref_df = None
    ref_defaults = load_ref_defaults()
    if REF_PATH.exists():
        try:
            ref_df = pd.read_parquet(REF_PATH)
        except Exception:
            pass

    # Load model
    try:
        ridge, calibrator, scaler, impute_vals = load_model()
    except Exception as e:
        logger.error(f"Could not load model: {e}")
        return []

    game_dt = pd.Timestamp(game_date)
    all_signals: list[dict] = []

    for league_id, league_info in LEAGUES.items():
        logger.info(f"[{league_id}] Fetching fixtures for {game_date}...")

        # Fetch today's fixtures
        fix_data = api.get(
            "fixtures",
            {"date": game_date, "league": league_info["api_football_id"],
             "season": league_info["season"]},
            cache_key=f"fixtures_{league_id}_{game_date}",
        )
        fixtures = fix_data.get("response", [])
        logger.info(f"[{league_id}] {len(fixtures)} fixtures")

        # Fetch odds (one call per sport key)
        odds_data: list[dict] = []
        if use_odds and odds_key:
            odds_data = fetch_odds(league_info["odds_sport"], odds_key)
            logger.info(f"[{league_id}] Odds API: {len(odds_data)} games")

        # Current season string (e.g. "2025-26")
        season_start_year = league_info["season"]
        season_str = f"{season_start_year}-{str(season_start_year + 1)[-2:]}"

        # League canon + current season
        league_canon = canon[canon["league_id"] == league_id].sort_values("game_date")

        # League rolling (using all available data through today)
        league_rolling = compute_league_rolling(canon, league_id, season_str, game_dt)

        for fix in fixtures:
            ft_info  = fix.get("fixture", {})
            teams    = fix.get("teams", {})
            home_team = teams.get("home", {}).get("name", "")
            away_team = teams.get("away", {}).get("name", "")
            fixture_id = ft_info.get("id")
            status     = ft_info.get("status", {}).get("short", "")

            if not home_team or not away_team:
                continue

            # Skip non-upcoming games
            if status in ("FT", "AET", "PEN", "CANC", "PST", "ABD"):
                continue

            # Parse kickoff
            kickoff_str = ft_info.get("date", "")
            kickoff_hour_utc = 15
            game_time_et = ""
            if kickoff_str:
                try:
                    ko = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
                    kickoff_hour_utc = ko.hour
                    # Convert to ET
                    from zoneinfo import ZoneInfo
                    ko_et = ko.astimezone(ZoneInfo("America/New_York"))
                    game_time_et = ko_et.strftime("%-I:%M %p ET")
                except Exception:
                    pass

            game_id = f"{league_id}_{season_str}_{game_date}_{home_team}_{away_team}".replace(" ", "_")

            # Skip if already written today
            if DECISIONS_PATH.exists():
                existing = pd.read_parquet(DECISIONS_PATH, columns=["game_id"])
                if game_id in existing["game_id"].values:
                    if not refresh_lineups_only:
                        logger.info(f"  Skip (already written): {home_team} v {away_team}")
                        continue

            logger.info(f"  [{league_id}] {away_team} @ {home_team}")

            # ── Prior games for each team ───────────────────────────────────────
            def get_prior(team: str) -> pd.DataFrame:
                mask = (
                    ((league_canon["home_team"] == team) |
                     (league_canon["away_team"] == team)) &
                    (league_canon["game_date"] < game_dt)
                )
                return league_canon[mask].sort_values("game_date")

            home_prior = get_prior(home_team)
            away_prior = get_prior(away_team)

            n_home = len(home_prior)
            n_away = len(away_prior)

            if n_home < MIN_PRIOR_MATCHES or n_away < MIN_PRIOR_MATCHES:
                logger.info(f"  Skip: insufficient history "
                            f"(home={n_home}, away={n_away}, min={MIN_PRIOR_MATCHES})")
                continue

            # ── Rolling features ────────────────────────────────────────────────
            home_rolling = compute_team_rolling(home_team, home_prior, "home", game_dt)
            away_rolling = compute_team_rolling(away_team, away_prior, "away", game_dt)

            # ── Mismatch interactions ───────────────────────────────────────────
            features: dict = {}
            features.update(league_rolling)
            for lid in ["BUN", "LGA", "SEA", "LG1"]:
                features[f"is_{lid.lower()}"] = 1.0 if league_id == lid else 0.0
            features.update(home_rolling)
            features.update(away_rolling)

            # xG mismatch: home attack vs away defense
            h_xg_for  = features.get("home_xg_for_rolling_10", np.nan)
            a_xg_agt  = features.get("away_xg_against_rolling_10", np.nan)
            a_xg_for  = features.get("away_xg_for_rolling_10", np.nan)
            h_xg_agt  = features.get("home_xg_against_rolling_10", np.nan)
            features["home_xg_mismatch"] = h_xg_for - a_xg_agt if not any(pd.isna([h_xg_for, a_xg_agt])) else 0.0
            features["away_xg_mismatch"] = a_xg_for - h_xg_agt if not any(pd.isna([a_xg_for, h_xg_agt])) else 0.0
            features["home_shot_mismatch"] = (
                features.get("home_shots_for_rolling_10", 0.0) -
                features.get("away_shots_against_rolling_10", 0.0)
            )
            features["away_shot_mismatch"] = (
                features.get("away_shots_for_rolling_10", 0.0) -
                features.get("home_shots_against_rolling_10", 0.0)
            )
            features["home_form_mismatch"] = (
                features.get("home_goals_scored_rolling_5", 0.0) -
                features.get("away_goals_conceded_rolling_5", 0.0)
            )
            features["away_form_mismatch"] = (
                features.get("away_goals_scored_rolling_5", 0.0) -
                features.get("home_goals_conceded_rolling_5", 0.0)
            )

            # ── Odds & market features ──────────────────────────────────────────
            odds_info = parse_odds_for_game(odds_data, home_team, away_team) if odds_data else {}
            fair_close, _ = remove_vig(
                odds_info.get("over_dec_close", np.nan),
                odds_info.get("under_dec_close", np.nan),
            )
            fair_open, _  = remove_vig(
                odds_info.get("over_dec_open", np.nan),
                odds_info.get("under_dec_open", np.nan),
            )
            mkt = derive_market_features(fair_close, fair_open)
            features.update(mkt)

            over_dec  = odds_info.get("over_dec_close", np.nan)
            under_dec = odds_info.get("under_dec_close", np.nan)
            closing_total = 2.5  # line is always 2.5

            # ── Lineups ─────────────────────────────────────────────────────────
            lineup_data = {}
            if fixture_id:
                raw = api.get(
                    "fixtures/lineups",
                    {"fixture": fixture_id},
                    cache_key=f"lineups_{fixture_id}_{game_date}",
                )
                lineup_data = raw
            lineup_feats = parse_lineup_features(lineup_data, home_team, away_team)
            lineup_confirmed = lineup_feats.pop("lineup_confirmed", False)
            features.update(lineup_feats)

            # ── Weather ─────────────────────────────────────────────────────────
            lat, lon = get_coords(home_team, league_id)
            wx_raw = fetch_weather_forecast(lat, lon, game_date, kickoff_hour_utc)
            wx = extract_weather(wx_raw, kickoff_hour_utc)
            features.update(wx)

            # ── Referee (EPL only, unknown for BUN) ─────────────────────────────
            referee_name = fix.get("fixture", {}).get("referee") or None
            ref_feats = get_ref_features(referee_name, ref_df, ref_defaults)
            features.update(ref_feats)

            # Injury features — zero fallback (API returns no historical data)
            for k in ("home_injury_count", "away_injury_count",
                      "home_key_player_injured", "away_key_player_injured",
                      "home_total_absence_score", "away_total_absence_score"):
                features.setdefault(k, 0.0)

            # ── Predict ─────────────────────────────────────────────────────────
            pred = predict_fixture(
                fixture_row={},
                features=features,
                ridge=ridge, calibrator=calibrator,
                scaler=scaler, impute_vals=impute_vals,
            )

            mkt_p   = pred["market_fair_p_over_2_5"]
            cal_p_raw = pred["ridge_cal_p"]
            mkt_move = pred["market_move_to_over_2_5"]

            # ── League calibration (post-model, pre-simulation) ────────────
            cal_params = _LEAGUE_CALIBRATION.get(league_id)
            if cal_params is not None:
                method = cal_params.get("method", "intercept")
                if method == "intercept":
                    cal_p = float(np.clip(cal_p_raw + cal_params["delta"], 0.05, 0.95))
                elif method == "linear":
                    cal_p = float(np.clip(
                        cal_params["a"] * cal_p_raw + cal_params["b"], 0.05, 0.95))
                else:
                    cal_p = cal_p_raw
            else:
                cal_p = cal_p_raw

            edge = cal_p - mkt_p

            model_total = mkt_p * 5.0 + 0.5   # rough implied total goals from fair_p
            try:
                mu = fair_p_to_mu(cal_p)
                model_total = float(mu) if not pd.isna(mu) else model_total
            except Exception:
                pass

            logger.info(
                f"    market_p={mkt_p:.3f} cal_p={cal_p:.3f} "
                f"edge={edge:+.3f} move={mkt_move:+.3f}"
            )

            # ── Production filters ───────────────────────────────────────────────
            signal_qualifies = (
                edge >= MIN_EDGE and
                mkt_move >= LATE_MONEY_SUPPRESS
            )

            if not signal_qualifies:
                reason = []
                if edge < MIN_EDGE:
                    reason.append(f"edge {edge:.3f} < {MIN_EDGE}")
                if mkt_move < LATE_MONEY_SUPPRESS:
                    reason.append(f"late money against ({mkt_move:+.3f})")
                logger.info(f"    No signal: {', '.join(reason)}")

            tier = get_confidence_tier(edge) if signal_qualifies else None

            # Hard stop: suppress if this tier is suspended
            if signal_qualifies and tier and tier in stop_status["suspended_tiers"]:
                logger.info(f"    No signal: [{tier}] tier suspended (live ROI below threshold)")
                signal_qualifies = False
                tier = None

            # ── Live signal restriction ─────────────────────────────────────
            # Active = BUN MEDIUM only; everything else is shadow/observational
            is_active_bet = (
                signal_qualifies
                and league_id in LIVE_ACTIVE_LEAGUES
                and tier in LIVE_ACTIVE_TIERS
            )
            signal_status = "active" if is_active_bet else (
                "shadow" if signal_qualifies else "no_signal"
            )

            sig = {
                "game_id":          game_id,
                "game_date":        game_date,
                "season_year":      season_str,
                "league_id":        league_id,
                "home_team":        home_team,
                "away_team":        away_team,
                "game_time_et":     game_time_et,
                "fixture_id":       fixture_id,
                "split":            "live",
                # Signal
                "signal_side":      "OVER" if signal_qualifies else None,
                "qualifies":        signal_qualifies,
                "signal_status":    signal_status,
                "closing_total":    closing_total,
                "edge":             edge,
                "confidence_tier":  tier,
                "model_total":      round(model_total, 2),
                # Market
                "market_fair_p_over_2_5": mkt_p,
                "ridge_cal_p_raw":  cal_p_raw,
                "ridge_cal_p":      cal_p,
                "calibration_applied": cal_params is not None,
                "market_move_to_over_2_5": mkt_move,
                "market_odds_available": float(features.get("market_odds_available", 0)),
                "over_price":       over_dec,
                "under_price":      under_dec,
                # Lineup
                "lineup_confirmed": lineup_confirmed,
                # Key features (for summaries)
                "home_xg_for_rolling_10":    features.get("home_xg_for_rolling_10"),
                "away_xg_for_rolling_10":    features.get("away_xg_for_rolling_10"),
                "home_xg_against_rolling_10": features.get("home_xg_against_rolling_10"),
                "away_xg_against_rolling_10": features.get("away_xg_against_rolling_10"),
                "home_goals_scored_rolling_5": features.get("home_goals_scored_rolling_5"),
                "away_goals_scored_rolling_5": features.get("away_goals_scored_rolling_5"),
                "weather_wind_kph":   wx.get("weather_wind_kph"),
                "weather_temp_c":     wx.get("weather_temp_c"),
                "referee":            referee_name,
                # Grading
                "result":             None,
                "actual_total_goals": None,
                "graded":             0,
            }
            all_signals.append(sig)

            # ── V2.2c shadow logging (non-fatal) ──────────────────────────
            if signal_qualifies:
                _log_v2_2c_shadow(sig)

    # ── Write decisions ──────────────────────────────────────────────────────
    if all_signals:
        new_df = pd.DataFrame(all_signals)
        qualified = new_df[new_df["qualifies"] == True].copy()

        if qualified.empty:
            logger.info("No qualified OVER signals today.")
        else:
            if DECISIONS_PATH.exists():
                existing = pd.read_parquet(DECISIONS_PATH)
                # Remove any same game_id rows (in case of re-run)
                existing = existing[~existing["game_id"].isin(qualified["game_id"])]
                combined = pd.concat([existing, qualified], ignore_index=True)
            else:
                combined = qualified

            out_cols = [c for c in qualified.columns if c != "qualifies"]
            combined = combined[[c for c in out_cols if c in combined.columns]]
            combined.to_parquet(DECISIONS_PATH, index=False)
            logger.info(f"Wrote {len(qualified)} signals to {DECISIONS_PATH}")

        # Return only qualified
        return qualified.to_dict("records") if not qualified.empty else []

    logger.info("No signals generated.")
    return []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Soccer OVER-Only Specialist pipeline")
    parser.add_argument("--date",             default=None)
    parser.add_argument("--grade-yesterday",  action="store_true")
    parser.add_argument("--refresh-lineups",  action="store_true")
    parser.add_argument("--no-odds",          action="store_true")
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()
    signals = run_pipeline(
        game_date        = game_date,
        use_odds         = not args.no_odds,
        refresh_lineups_only = args.refresh_lineups,
        grade_yesterday_flag = args.grade_yesterday,
    )

    print(f"\n{'═'*60}")
    print(f"  Soccer OVER Signals — {game_date}")
    print(f"{'═'*60}")
    if signals:
        for s in sorted(signals, key=lambda x: -(x.get("edge") or 0)):
            tier = s.get("confidence_tier", "LOW")
            edge = s.get("edge", 0)
            print(
                f"  [{tier}] {s['away_team']} @ {s['home_team']}  "
                f"edge={edge:+.3f}  move={s.get('market_move_to_over_2_5', 0):+.3f}  "
                f"lineup={'✓' if s.get('lineup_confirmed') else '?'}"
            )
    else:
        print("  No qualified OVER signals today.")

    # Stop rule status summary
    stop_status = check_stop_rules()
    roi_str = f"{stop_status['overall_roi']:+.1%}" if stop_status["overall_roi"] is not None else "N/A"
    print(f"{'─'*60}")
    print(f"  Stop Rules — live_n={stop_status['overall_n']}  overall_ROI={roi_str}")
    for tier in ("HIGH", "MEDIUM", "LOW"):
        ts = stop_status["tier_stats"].get(tier, {})
        t_roi = f"{ts['roi']:+.1%}" if ts.get("roi") is not None else "N/A"
        susp = " ⛔ SUSPENDED" if tier in stop_status["suspended_tiers"] else ""
        print(f"    {tier}: n={ts.get('n', 0)}  ROI={t_roi}{susp}")
    if stop_status["overall_suspended"]:
        print("  ⛔ OVERALL MODEL SUSPENDED (live ROI below -10%)")
    elif not stop_status["suspended_tiers"]:
        print("  ✓ All tiers active — no suspensions")
    print()

    # Auto-push + timestamp
    import subprocess
    _lu = BASE_DIR / "shared" / "last_updated.json"
    _d = json.load(open(_lu)) if _lu.exists() else {}
    _d["soccer"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(_lu, "w") as f:
        json.dump(_d, f, indent=2)
    subprocess.run(["bash", str(BASE_DIR / "shared" / "git_push.sh"), "Soccer pipeline run"],
                   capture_output=True)


if __name__ == "__main__":
    main()
