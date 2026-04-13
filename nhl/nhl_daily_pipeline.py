#!/usr/bin/env python3
"""
NHL Daily Prediction Pipeline
==============================
Fetches today's NHL schedule, computes features, runs ridge models,
applies dynamic calibration + Poisson simulation, computes edges
against Odds API lines, outputs qualified signals (edge >= 0.10).

Usage:
  python3 nhl/nhl_daily_pipeline.py                   # today
  python3 nhl/nhl_daily_pipeline.py --date 2026-03-15 # specific date

Outputs: appends qualified signals to nhl/nhl_decisions.parquet
"""

import argparse
import json
import os
import pickle
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import time
import requests

# ---------------------------------------------------------------------------
NHL_DIR   = Path(__file__).parent
BASE_DIR  = NHL_DIR.parent
sys.path.insert(0, str(BASE_DIR))
CACHE_DIR = NHL_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

FT_FILE      = NHL_DIR / "nhl_feature_table.parquet"
HOME_PKL     = NHL_DIR / "ridge_home_model.pkl"
AWAY_PKL     = NHL_DIR / "ridge_away_model.pkl"
DECISIONS    = NHL_DIR / "nhl_decisions.parquet"
LIVE_CACHE   = CACHE_DIR / "nhl_live_season.parquet"  # current-season games
REBUILD_FT   = BASE_DIR / "research" / "recovery" / "nhl_rebuild" / "nhl_rebuild_features.parquet"
REBUILD_HOME = BASE_DIR / "research" / "recovery" / "nhl_final_alignment" / "model_A_home.pkl"
REBUILD_AWAY = BASE_DIR / "research" / "recovery" / "nhl_final_alignment" / "model_A_away.pkl"

NHL_API      = "https://api-web.nhle.com/v1"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

N_SIM     = 10_000
SEED      = 42
THRESHOLD = 0.12

# Validate-season fallback drift (from Phase 4.5)
VALIDATE_DRIFT = 0.0  # Aligned model (PK% corrected) -- no drift needed

# Min current-season games before using rolling (vs fallback prior)
MIN_SEASON_GAMES = 10

WIN_PER_UNIT = 100.0 / 110.0

# ---------------------------------------------------------------------------
# NHL team name → canonical abbreviation  (for Odds API full names)
# ---------------------------------------------------------------------------
ODDS_TEAM_MAP = {
    "Anaheim Ducks":            "ANA",
    "Arizona Coyotes":          "ARI",
    "Boston Bruins":            "BOS",
    "Buffalo Sabres":           "BUF",
    "Calgary Flames":           "CGY",
    "Carolina Hurricanes":      "CAR",
    "Chicago Blackhawks":       "CHI",
    "Colorado Avalanche":       "COL",
    "Columbus Blue Jackets":    "CBJ",
    "Dallas Stars":             "DAL",
    "Detroit Red Wings":        "DET",
    "Edmonton Oilers":          "EDM",
    "Florida Panthers":         "FLA",
    "Los Angeles Kings":        "LAK",
    "Minnesota Wild":           "MIN",
    "Montreal Canadiens":       "MTL",
    "Nashville Predators":      "NSH",
    "New Jersey Devils":        "NJD",
    "New York Islanders":       "NYI",
    "New York Rangers":         "NYR",
    "Ottawa Senators":          "OTT",
    "Philadelphia Flyers":      "PHI",
    "Pittsburgh Penguins":      "PIT",
    "San Jose Sharks":          "SJS",
    "Seattle Kraken":           "SEA",
    "St. Louis Blues":          "STL",
    "Tampa Bay Lightning":      "TBL",
    "Toronto Maple Leafs":      "TOR",
    "Utah Mammoth":             "UTA",   # formerly Arizona
    "Vancouver Canucks":        "VAN",
    "Vegas Golden Knights":     "VGK",
    "Washington Capitals":      "WSH",
    "Winnipeg Jets":            "WPG",
}

# Priority for Odds API bookmakers
BOOK_PRIORITY = ["draftkings", "fanduel", "betmgm", "williamhill_us"]

# ---------------------------------------------------------------------------
# Load models and feature table
# ---------------------------------------------------------------------------
def load_models():
    # Use rebuild Model A pickles for live parity
    home_pkl = REBUILD_HOME if REBUILD_HOME.exists() else HOME_PKL
    away_pkl = REBUILD_AWAY if REBUILD_AWAY.exists() else AWAY_PKL
    with open(home_pkl, "rb") as f:
        hpkg = pickle.load(f)
    with open(away_pkl, "rb") as f:
        apkg = pickle.load(f)
    print(f"  Models loaded from: {home_pkl.name}, {away_pkl.name}")
    return hpkg, apkg

def load_feature_table() -> pd.DataFrame:
    return pd.read_parquet(FT_FILE)

# ---------------------------------------------------------------------------
# Compute 2024-25 end-of-season league averages (shrinkage priors)
# ---------------------------------------------------------------------------
def compute_league_priors(ft: pd.DataFrame) -> dict:
    """Compute raw-stat league averages from 2024 canonical season for shrinkage priors.

    FIX D2: Aligns with canonical rebuild — uses raw per-game stat averages
    (not rolling feature means) from the most recent completed season.
    Falls back to canonical CSV if available, else rebuild feature table.
    """
    priors = {}

    # Try to compute from canonical game CSV (raw stats, matches rebuild exactly)
    _canonical_csv = NHL_DIR / "nhl_games_canonical.csv"
    if _canonical_csv.exists():
        gc = pd.read_csv(_canonical_csv)
        s24 = gc[gc["season_year"] == 2024]
        if len(s24) > 100:
            # Raw per-game stat averages (both home and away perspectives pooled)
            _raw_goals = pd.concat([s24["home_score"], s24["away_score"]]).mean()
            _raw_sog = pd.concat([s24["home_shots_on_goal"], s24["away_shots_on_goal"]]).dropna().mean()

            _pp_pct_arr = []
            _pk_pct_arr = []
            for _, _r in s24.iterrows():
                for _s in ("home", "away"):
                    _opp = "away" if _s == "home" else "home"
                    _ppo = _r.get(f"{_s}_pp_opportunities")
                    _ppg = _r.get(f"{_s}_pp_goals")
                    if pd.notna(_ppo) and pd.notna(_ppg):
                        _pp_pct_arr.append(_ppg / _ppo if _ppo > 0 else 0.0)
                    _opp_ppo = _r.get(f"{_opp}_pp_opportunities")
                    _opp_ppg = _r.get(f"{_opp}_pp_goals")
                    if pd.notna(_opp_ppo) and pd.notna(_opp_ppg):
                        _pk_pct_arr.append(1.0 - _opp_ppg / _opp_ppo if _opp_ppo > 0 else 1.0)
            _raw_pp_pct = float(np.mean(_pp_pct_arr)) if _pp_pct_arr else 0.21
            _raw_pk_pct = float(np.mean(_pk_pct_arr)) if _pk_pct_arr else 0.79
            _raw_pp_opp = pd.concat([s24["home_pp_opportunities"], s24["away_pp_opportunities"]]).dropna().mean()

            _sv_arr = []
            for _, _r in s24.iterrows():
                for _s in ("home", "away"):
                    _sa = _r.get(f"{_s}_goalie_sa")
                    _ga = _r.get(f"{_s}_goalie_ga")
                    if pd.notna(_sa) and _sa > 0 and pd.notna(_ga):
                        _sv_arr.append(1.0 - _ga / _sa)
            _raw_sv = float(np.mean(_sv_arr)) if _sv_arr else 0.91

            for side in ("home", "away"):
                priors[f"{side}_goals_scored_rolling_10"]    = float(_raw_goals)
                priors[f"{side}_goals_allowed_rolling_10"]   = float(_raw_goals)
                priors[f"{side}_shots_for_rolling_20"]       = float(_raw_sog)
                priors[f"{side}_shots_against_rolling_20"]   = float(_raw_sog)
                priors[f"{side}_pp_pct_rolling_20"]          = _raw_pp_pct
                priors[f"{side}_pk_pct_rolling_20"]          = _raw_pk_pct
                priors[f"{side}_pp_opp_per_game_rolling_20"] = float(_raw_pp_opp)
                priors[f"{side}_goalie_sv_pct_rolling_10"]   = _raw_sv
                priors[f"{side}_goalie_vs_team_baseline"]    = 0.0
                priors[f"{side}_goalie_fatigue"]             = 0
                priors[f"{side}_goalie_b2b"]                 = 0
                priors[f"{side}_backup_flag"]                = 0

            priors["home_shot_pressure"] = 0.0
            priors["away_shot_pressure"] = 0.0
            priors["home_days_rest"]    = 3.0
            priors["away_days_rest"]    = 3.0
            priors["home_b2b"]          = 0
            priors["away_b2b"]          = 0
            priors["home_games_last_7"] = 2.5
            priors["away_games_last_7"] = 2.5
            return priors

    # Fallback: use rebuild feature table means (old behavior, less accurate)
    if REBUILD_FT.exists():
        rft = pd.read_parquet(REBUILD_FT)
        oos = rft[rft["season_year"] == 2024]
    else:
        oos = ft[ft["season_year"] == 2024]

    for side in ("home", "away"):
        priors[f"{side}_goals_scored_rolling_10"]      = oos[f"{side}_goals_scored_rolling_10"].mean()
        priors[f"{side}_goals_allowed_rolling_10"]     = oos[f"{side}_goals_allowed_rolling_10"].mean()
        priors[f"{side}_shots_for_rolling_20"]         = oos[f"{side}_shots_for_rolling_20"].mean()
        priors[f"{side}_shots_against_rolling_20"]     = oos[f"{side}_shots_against_rolling_20"].mean()
        priors[f"{side}_pp_pct_rolling_20"]            = oos[f"{side}_pp_pct_rolling_20"].mean()
        priors[f"{side}_pk_pct_rolling_20"]            = oos[f"{side}_pk_pct_rolling_20"].mean()
        priors[f"{side}_pp_opp_per_game_rolling_20"]   = oos[f"{side}_pp_opp_per_game_rolling_20"].mean()
        priors[f"{side}_goalie_sv_pct_rolling_10"]     = oos[f"{side}_goalie_sv_pct_rolling_10"].mean()
        priors[f"{side}_goalie_vs_team_baseline"]      = 0.0
        priors[f"{side}_goalie_fatigue"]               = 0
        priors[f"{side}_goalie_b2b"]                   = 0
        priors[f"{side}_backup_flag"]                  = 0

    priors["home_shot_pressure"] = 0.0
    priors["away_shot_pressure"] = 0.0
    priors["home_days_rest"]    = 3.0
    priors["away_days_rest"]    = 3.0
    priors["home_b2b"]          = 0
    priors["away_b2b"]          = 0
    priors["home_games_last_7"] = 2.5
    priors["away_games_last_7"] = 2.5

    return priors

# ---------------------------------------------------------------------------
# Fetch NHL schedule for a date
# ---------------------------------------------------------------------------
def fetch_schedule(target_date: date) -> list[dict]:
    """Return list of game dicts for target_date."""
    from shared.retry_utils import retry_request
    url = f"{NHL_API}/schedule/{target_date.isoformat()}"
    try:
        def _fetch():
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        data = retry_request(_fetch, max_retries=3, base_wait=30, label="NHL schedule")
        for day in data.get("gameWeek", []):
            if day.get("date") == target_date.isoformat():
                return day.get("games", [])
    except Exception as e:
        print(f"  WARNING: Could not fetch schedule: {e}")
    return []

# ---------------------------------------------------------------------------
# Fetch goalie info from NHL boxscore
# ---------------------------------------------------------------------------
def fetch_goalies(game_id: int) -> dict:
    """
    Returns {'home': {'name': str, 'starter': bool, 'sa': int, 'ga': int},
             'away': ...}
    Falls back to empty dicts on error.
    """
    url = f"{NHL_API}/gamecenter/{game_id}/boxscore"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        pg = data.get("playerByGameStats", {})
        result = {}
        for side in ("homeTeam", "awayTeam"):
            key = "home" if side == "homeTeam" else "away"
            goalies = pg.get(side, {}).get("goalies", [])
            starter = next((g for g in goalies if g.get("starter")), None)
            if starter:
                result[key] = {
                    "name":    starter.get("name", {}).get("default", "Unknown"),
                    "starter": True,
                    "playerId": starter.get("playerId"),
                    "sa":      starter.get("shotsAgainst", 0) or 0,
                    "ga":      (starter.get("shotsAgainst", 0) or 0) -
                               (starter.get("saves", 0) or 0),
                }
            else:
                result[key] = {"name": "Unknown", "starter": None, "sa": 0, "ga": 0}
        return result
    except Exception:
        return {"home": {}, "away": {}}

# ---------------------------------------------------------------------------
# Extended boxscore fetch — SOG/PP/PK/SV for NHL rebuild parity
# ---------------------------------------------------------------------------
def fetch_game_boxscore_extended(game_id: int) -> dict:
    """
    Fetch full boxscore + play-by-play for a completed game.
    Returns dict with SOG, PP goals, PP opportunities, goalie SA/GA/ID.
    Extended for NHL rebuild parity — SOG/PP/PK/SV
    """
    result = {
        "home_sog": None, "away_sog": None,
        "home_pp_goals": None, "away_pp_goals": None,
        "home_pp_opportunities": None, "away_pp_opportunities": None,
        "home_goalie_id": None, "away_goalie_id": None,
        "home_goalie_name": None, "away_goalie_name": None,
        "home_goalie_sa": None, "away_goalie_sa": None,
        "home_goalie_ga": None, "away_goalie_ga": None,
    }

    # --- Boxscore: SOG, PP goals, goalie stats ---
    try:
        r = requests.get(f"{NHL_API}/gamecenter/{game_id}/boxscore", timeout=15)
        r.raise_for_status()
        data = r.json()

        # SOG from top-level team data
        result["home_sog"] = data.get("homeTeam", {}).get("sog")
        result["away_sog"] = data.get("awayTeam", {}).get("sog")

        # Team IDs for PBP penalty matching
        home_team_id = data.get("homeTeam", {}).get("id")
        away_team_id = data.get("awayTeam", {}).get("id")

        # PP goals from skater stats + goalie stats
        pg = data.get("playerByGameStats", {})
        for side_key, prefix in [("homeTeam", "home"), ("awayTeam", "away")]:
            team_stats = pg.get(side_key, {})

            # Sum PP goals from forwards + defense
            pp_goals = 0
            for pos in ("forwards", "defense"):
                for p in team_stats.get(pos, []):
                    pp_goals += p.get("powerPlayGoals", 0) or 0
            result[f"{prefix}_pp_goals"] = pp_goals

            # Starter goalie stats
            goalies = team_stats.get("goalies", [])
            starter = next((g for g in goalies if g.get("starter")), None)
            if starter:
                sa = starter.get("shotsAgainst", 0) or 0
                saves = starter.get("saves", 0) or 0
                result[f"{prefix}_goalie_id"] = starter.get("playerId")
                result[f"{prefix}_goalie_name"] = starter.get("name", {}).get("default", "Unknown")
                result[f"{prefix}_goalie_sa"] = sa
                result[f"{prefix}_goalie_ga"] = sa - saves

    except Exception as e:
        pass  # result fields stay None

    # --- Play-by-play: PP opportunities from penalty count ---
    try:
        r2 = requests.get(f"{NHL_API}/gamecenter/{game_id}/play-by-play", timeout=15)
        r2.raise_for_status()
        pbp = r2.json()
        plays = pbp.get("plays", [])

        home_penalties = 0
        away_penalties = 0
        for p in plays:
            if p.get("typeDescKey") != "penalty":
                continue
            details = p.get("details", {})
            event_owner = details.get("eventOwnerTeamId")
            dur = details.get("duration", 0)
            desc = (details.get("descKey") or "").lower()
            # Only penalties that create PP (exclude misconduct)
            if dur and dur >= 2 and "misconduct" not in desc:
                if event_owner == home_team_id:
                    home_penalties += 1  # home penalty = away PP opportunity
                elif event_owner == away_team_id:
                    away_penalties += 1  # away penalty = home PP opportunity

        result["home_pp_opportunities"] = away_penalties  # home PP opp = away penalties
        result["away_pp_opportunities"] = home_penalties  # away PP opp = home penalties

    except Exception:
        pass  # PP opportunities stay None

    return result

# ---------------------------------------------------------------------------
# Fetch current-season live game data and cache it
# ---------------------------------------------------------------------------
def load_or_refresh_live_season(target_date: date) -> pd.DataFrame:
    """
    Returns DataFrame of completed games in current season up to target_date.
    Uses cache if fresh (< 6 hours old); otherwise fetches from NHL API.

    Extended for NHL rebuild parity: fetches SOG, PP goals, PP opportunities,
    and goalie stats from boxscore + play-by-play for each completed game.
    """
    EXTENDED_COLS = [
        "game_id", "game_date", "home_team", "away_team",
        "home_score", "away_score",
        # Extended for NHL rebuild parity — SOG/PP/PK/SV
        "home_sog", "away_sog",
        "home_pp_goals", "away_pp_goals",
        "home_pp_opportunities", "away_pp_opportunities",
        "home_goalie_id", "away_goalie_id",
        "home_goalie_name", "away_goalie_name",
        "home_goalie_sa", "away_goalie_sa",
        "home_goalie_ga", "away_goalie_ga",
    ]

    refresh = True
    if LIVE_CACHE.exists():
        mtime = datetime.fromtimestamp(LIVE_CACHE.stat().st_mtime)
        if (datetime.now() - mtime).total_seconds() < 6 * 3600:
            refresh = False

    if not refresh:
        df = pd.read_parquet(LIVE_CACHE)
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
        # Check if cache has extended columns; if not, force refresh
        if "home_sog" not in df.columns:
            print("  Cache missing extended boxscore columns — forcing refresh")
            refresh = True
        else:
            return df[df["game_date"] < target_date]

    # Determine current season start (Oct 1 of the current season)
    year = target_date.year if target_date.month >= 10 else target_date.year - 1
    season_start = date(year, 10, 1)
    print(f"  Fetching 2025-26 season game data ({season_start} → {target_date})...")

    # Phase 1: collect game IDs and basic info from schedule
    game_stubs = []
    current = season_start
    while current < target_date:
        url = f"{NHL_API}/schedule/{current.isoformat()}"
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            for day in data.get("gameWeek", []):
                if day.get("date") == current.isoformat():
                    for g in day.get("games", []):
                        if g.get("gameState") == "OFF" and g.get("gameType") == 2:
                            game_stubs.append({
                                "game_id":    g["id"],
                                "game_date":  current,
                                "home_team":  g["homeTeam"]["abbrev"],
                                "away_team":  g["awayTeam"]["abbrev"],
                                "home_score": g["homeTeam"].get("score", np.nan),
                                "away_score": g["awayTeam"].get("score", np.nan),
                            })
        except Exception:
            pass
        current += timedelta(days=1)

    print(f"  Found {len(game_stubs)} completed regular-season games")

    # Phase 2: fetch extended boxscore data for each game
    rows = []
    n_fetched = 0
    for stub in game_stubs:
        gid = stub["game_id"]
        ext = fetch_game_boxscore_extended(gid)
        row = {**stub, **ext}
        rows.append(row)
        n_fetched += 1
        if n_fetched % 100 == 0:
            print(f"    Fetched boxscore {n_fetched}/{len(game_stubs)}...")
        time.sleep(0.05)  # gentle rate limit for NHL API

    df = pd.DataFrame(rows, columns=EXTENDED_COLS) if rows else pd.DataFrame(columns=EXTENDED_COLS)

    if len(df):
        df.to_parquet(LIVE_CACHE, index=False)
        print(f"  Live season cache: {len(df)} games saved (with extended boxscore)")
    else:
        print("  No current-season games found (early season or API issue)")

    return df[df["game_date"] < target_date] if len(df) else df

# ---------------------------------------------------------------------------
# Build rolling features for a team from live season data
# ---------------------------------------------------------------------------
def build_live_team_features(team: str, game_date: date,
                              live: pd.DataFrame, priors: dict,
                              side: str, today_goalie_id: int = None) -> dict:
    """
    Compute rolling features for a team entering game_date.
    Uses live season data with extended boxscore fields.
    All Model A features computed from NHL API data — no MoneyPuck fallback.
    'side' = 'home' or 'away' — used for feature naming.

    FIX D3/D4/D5: today_goalie_id enables goalie-specific filtering for
    save%, vs-team-baseline, and fatigue features.
    """
    ROLLING_SHORT = 10
    ROLLING_LONG  = 20

    # All prior games this season for this team (as home or away)
    if len(live) > 0:
        live["game_date"] = pd.to_datetime(live["game_date"]).dt.date
        team_games = live[
            ((live["home_team"] == team) | (live["away_team"] == team)) &
            (live["game_date"] < game_date)
        ].sort_values("game_date")
    else:
        team_games = pd.DataFrame()

    n = len(team_games)

    # Shrinkage weight — matches rebuild exactly
    def shrink(raw, n_obs, prior_val, window=20):
        if pd.isna(raw):
            return prior_val
        w = min(n_obs, window) / window
        return w * raw + (1 - w) * prior_val

    feat = {}

    # Build per-game arrays from team perspective
    goals_scored  = []
    goals_allowed = []
    shots_for     = []
    shots_against = []
    pp_pct_arr    = []
    pk_pct_arr    = []
    pp_opp_arr    = []
    goalie_sv_pct = []
    goalie_ids    = []

    for _, r in team_games.iterrows():
        is_home = (r["home_team"] == team)
        pfx = "home" if is_home else "away"
        opp_pfx = "away" if is_home else "home"

        goals_scored.append(r[f"{pfx}_score"])
        goals_allowed.append(r[f"{opp_pfx}_score"])

        # SOG — Extended for NHL rebuild parity
        sf = r.get(f"{pfx}_sog")
        sa = r.get(f"{opp_pfx}_sog")
        shots_for.append(sf if pd.notna(sf) else np.nan)
        shots_against.append(sa if pd.notna(sa) else np.nan)

        # PP% — pp_goals / pp_opportunities
        ppg = r.get(f"{pfx}_pp_goals")
        ppo = r.get(f"{pfx}_pp_opportunities")
        if pd.notna(ppg) and pd.notna(ppo):
            pp_pct_arr.append(ppg / ppo if ppo > 0 else 0.0)
        else:
            pp_pct_arr.append(np.nan)

        # PK% — 1 - (opp_pp_goals / opp_pp_opportunities)
        opp_ppg = r.get(f"{opp_pfx}_pp_goals")
        opp_ppo = r.get(f"{opp_pfx}_pp_opportunities")
        if pd.notna(opp_ppg) and pd.notna(opp_ppo):
            pk_pct_arr.append(1.0 - opp_ppg / opp_ppo if opp_ppo > 0 else 1.0)
        else:
            pk_pct_arr.append(np.nan)

        # PP opportunities per game
        pp_opp_arr.append(ppo if pd.notna(ppo) else np.nan)

        # Goalie save% — from goalie SA and GA
        gsa = r.get(f"{pfx}_goalie_sa")
        gga = r.get(f"{pfx}_goalie_ga")
        gid = r.get(f"{pfx}_goalie_id")
        if pd.notna(gsa) and gsa > 0 and pd.notna(gga):
            goalie_sv_pct.append(1.0 - gga / gsa)
        else:
            goalie_sv_pct.append(0.91)  # league average fallback
        goalie_ids.append(gid)

    # --- Goals rolling 10 ---
    gs_tail = [g for g in goals_scored[-ROLLING_SHORT:] if not pd.isna(g)]
    ga_tail = [g for g in goals_allowed[-ROLLING_SHORT:] if not pd.isna(g)]
    feat[f"{side}_goals_scored_rolling_10"] = shrink(
        float(np.mean(gs_tail)) if gs_tail else np.nan,
        n, priors[f"{side}_goals_scored_rolling_10"], ROLLING_SHORT)
    feat[f"{side}_goals_allowed_rolling_10"] = shrink(
        float(np.mean(ga_tail)) if ga_tail else np.nan,
        n, priors[f"{side}_goals_allowed_rolling_10"], ROLLING_SHORT)

    # --- Shots rolling 20 ---
    sf_tail = [s for s in shots_for[-ROLLING_LONG:] if not pd.isna(s)]
    sa_tail = [s for s in shots_against[-ROLLING_LONG:] if not pd.isna(s)]
    feat[f"{side}_shots_for_rolling_20"] = shrink(
        float(np.mean(sf_tail)) if sf_tail else np.nan,
        len(sf_tail), priors[f"{side}_shots_for_rolling_20"], ROLLING_LONG)
    feat[f"{side}_shots_against_rolling_20"] = shrink(
        float(np.mean(sa_tail)) if sa_tail else np.nan,
        len(sa_tail), priors[f"{side}_shots_against_rolling_20"], ROLLING_LONG)

    # --- PP% rolling 20 ---
    pp_tail = [p for p in pp_pct_arr[-ROLLING_LONG:] if not pd.isna(p)]
    feat[f"{side}_pp_pct_rolling_20"] = shrink(
        float(np.mean(pp_tail)) if pp_tail else np.nan,
        len(pp_tail), priors[f"{side}_pp_pct_rolling_20"], ROLLING_LONG)

    # --- PK% rolling 20 ---
    pk_tail = [p for p in pk_pct_arr[-ROLLING_LONG:] if not pd.isna(p)]
    feat[f"{side}_pk_pct_rolling_20"] = shrink(
        float(np.mean(pk_tail)) if pk_tail else np.nan,
        len(pk_tail), priors[f"{side}_pk_pct_rolling_20"], ROLLING_LONG)

    # --- PP opportunities per game rolling 20 ---
    ppo_tail = [p for p in pp_opp_arr[-ROLLING_LONG:] if not pd.isna(p)]
    feat[f"{side}_pp_opp_per_game_rolling_20"] = shrink(
        float(np.mean(ppo_tail)) if ppo_tail else np.nan,
        len(ppo_tail), priors[f"{side}_pp_opp_per_game_rolling_20"], ROLLING_LONG)

    # --- Goalie save% rolling 10 (goalie-specific, matching rebuild) ---
    # FIX D3: Filter to today's starting goalie's games only
    if today_goalie_id is not None:
        goalie_specific_sv = [
            sv for sv, gid in zip(goalie_sv_pct, goalie_ids)
            if gid == today_goalie_id and not pd.isna(sv)
        ]
    else:
        # Fallback: use all team games (pre-fix behavior)
        goalie_specific_sv = [s for s in goalie_sv_pct if not pd.isna(s)]

    gsv_tail = goalie_specific_sv[-ROLLING_SHORT:]
    n_goalie = len(gsv_tail)
    feat[f"{side}_goalie_sv_pct_rolling_10"] = shrink(
        float(np.mean(gsv_tail)) if gsv_tail else np.nan,
        n_goalie, priors[f"{side}_goalie_sv_pct_rolling_10"], ROLLING_SHORT)

    # --- Goalie vs team baseline ---
    # FIX D4: Compare goalie-specific mean to team-wide mean (matches canonical)
    all_sv = [s for s in goalie_sv_pct if not pd.isna(s)]
    team_all_mean = float(np.mean(all_sv)) if all_sv else 0.91
    if today_goalie_id is not None:
        goalie_all_sv = [
            sv for sv, gid in zip(goalie_sv_pct, goalie_ids)
            if gid == today_goalie_id and not pd.isna(sv)
        ]
        goalie_mean = float(np.mean(goalie_all_sv)) if goalie_all_sv else np.nan
    else:
        goalie_mean = np.nan

    if pd.notna(goalie_mean) and n_goalie >= 3:
        feat[f"{side}_goalie_vs_team_baseline"] = goalie_mean - team_all_mean
    else:
        feat[f"{side}_goalie_vs_team_baseline"] = 0.0

    return feat

# ---------------------------------------------------------------------------
# Compute full feature row for a game
# ---------------------------------------------------------------------------
def compute_game_features(home: str, away: str, game_date: date,
                           live: pd.DataFrame, priors: dict,
                           home_goalie_info: dict, away_goalie_info: dict,
                           home_b2b: bool = False, away_b2b: bool = False,
                           home_rest: float = 3.0, away_rest: float = 3.0) -> dict:
    # FIX D3: Pass today's starting goalie IDs for goalie-specific feature computation
    home_goalie_id = home_goalie_info.get("playerId") or home_goalie_info.get("goalie_id")
    away_goalie_id = away_goalie_info.get("playerId") or away_goalie_info.get("goalie_id")
    h_feat = build_live_team_features(home, game_date, live, priors, "home", today_goalie_id=home_goalie_id)
    a_feat = build_live_team_features(away, game_date, live, priors, "away", today_goalie_id=away_goalie_id)

    # Shot pressure (derived — Model A feature)
    feat = {**h_feat, **a_feat}
    feat["home_shot_pressure"] = feat["home_shots_for_rolling_20"] - feat["away_shots_against_rolling_20"]
    feat["away_shot_pressure"] = feat["away_shots_for_rolling_20"] - feat["home_shots_against_rolling_20"]

    # Goalie adjustments
    # Goalie fatigue: count recent starts in live data
    for s, team, b2b, goalie_info in [
        ("home", home, home_b2b, home_goalie_info),
        ("away", away, away_b2b, away_goalie_info),
    ]:
        feat[f"{s}_goalie_b2b"] = int(b2b)
        feat[f"{s}_backup_flag"] = int(goalie_info.get("starter") is False)

        # Goalie fatigue: goalie-specific starts in last 3 days (from live data)
        # FIX D5: Count only this goalie's starts, not all team games
        fatigue = 0
        _goalie_id = goalie_info.get("playerId") or goalie_info.get("goalie_id")
        if len(live) > 0 and _goalie_id is not None:
            live_copy = live.copy()
            live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
            three_days_ago = game_date - timedelta(days=3)
            # Filter team games in window
            team_recent = live_copy[
                ((live_copy["home_team"] == team) | (live_copy["away_team"] == team)) &
                (live_copy["game_date"] >= three_days_ago) &
                (live_copy["game_date"] < game_date)
            ]
            # Count only games where THIS goalie started
            for _, _gr in team_recent.iterrows():
                _is_home = (_gr["home_team"] == team)
                _gid_col = "home_goalie_id" if _is_home else "away_goalie_id"
                if _gr.get(_gid_col) == _goalie_id:
                    fatigue += 1
        elif len(live) > 0:
            # Fallback: count team games if goalie_id unknown
            live_copy = live.copy()
            live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
            three_days_ago = game_date - timedelta(days=3)
            recent = live_copy[
                ((live_copy["home_team"] == team) | (live_copy["away_team"] == team)) &
                (live_copy["game_date"] >= three_days_ago) &
                (live_copy["game_date"] < game_date)
            ]
            fatigue = len(recent)
        feat[f"{s}_goalie_fatigue"] = fatigue

    # Schedule features
    feat["home_days_rest"] = home_rest
    feat["away_days_rest"] = away_rest
    feat["home_b2b"] = int(home_b2b)
    feat["away_b2b"] = int(away_b2b)

    # Games in last 7 from live data
    for s, team in [("home", home), ("away", away)]:
        if len(live) > 0:
            live_copy = live.copy()
            live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
            seven_days_ago = game_date - timedelta(days=7)
            g7 = live_copy[
                ((live_copy["home_team"] == team) | (live_copy["away_team"] == team)) &
                (live_copy["game_date"] >= seven_days_ago) &
                (live_copy["game_date"] < game_date)
            ]
            feat[f"{s}_games_last_7"] = len(g7)
        else:
            feat[f"{s}_games_last_7"] = priors[f"{s}_games_last_7"]

    return feat

# ---------------------------------------------------------------------------
# Apply models + dynamic calibration
# ---------------------------------------------------------------------------
def predict_and_calibrate(feat: dict, hpkg: dict, apkg: dict,
                          live: pd.DataFrame, game_date: date,
                          train_col_means: pd.Series) -> tuple[float, float, float]:
    """
    Returns (lambda_home_cal, lambda_away_cal, seasonal_drift).
    """
    # Build DataFrames for model input
    feat_df = pd.DataFrame([feat])
    # Fill any missing columns with train means
    for col in hpkg["features"] + apkg["features"]:
        if col not in feat_df.columns:
            feat_df[col] = train_col_means.get(col, 0.0)
    feat_df = feat_df.fillna(train_col_means)

    lh_raw = hpkg["model"].predict(hpkg["scaler"].transform(feat_df[hpkg["features"]].to_numpy()))[0]
    la_raw = apkg["model"].predict(apkg["scaler"].transform(feat_df[apkg["features"]].to_numpy()))[0]
    lt_raw = lh_raw + la_raw

    # Dynamic seasonal drift
    # Determine current season year (Oct start)
    season_year = game_date.year if game_date.month >= 10 else game_date.year - 1

    # For 2025-26 season, check if we have live game data
    if len(live) > 0:
        live_copy = live.copy()
        live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
        prior_games = live_copy[live_copy["game_date"] < game_date]
        n_prior = len(prior_games)
    else:
        prior_games = pd.DataFrame()
        n_prior = 0

    if n_prior >= MIN_SEASON_GAMES and "total_goals" in prior_games.columns:
        # We'd need model predictions for those games too — complex for stub
        # Fall back to validate drift
        seasonal_drift = VALIDATE_DRIFT
    else:
        seasonal_drift = VALIDATE_DRIFT

    lh_cal = lh_raw + seasonal_drift / 2.0
    la_cal = la_raw + seasonal_drift / 2.0
    return float(lh_cal), float(la_cal), float(seasonal_drift)

# ---------------------------------------------------------------------------
# Poisson simulation
# ---------------------------------------------------------------------------
def simulate(lh_cal: float, la_cal: float, line: float,
             n_sim: int = N_SIM, seed: int = SEED) -> dict:
    rng  = np.random.default_rng(seed)
    lh   = max(0.5, min(8.0, lh_cal))
    la   = max(0.5, min(8.0, la_cal))
    sims = rng.poisson(lh, n_sim) + rng.poisson(la, n_sim)

    over_p  = float((sims > line).mean())
    under_p = float((sims < line).mean())
    push_p  = float((sims == line).mean())

    # Push correction for integer lines (from Phase 4.5)
    # Correction for 6.0: actual_push ≈ 0.1115, sim_push ≈ 0.1586
    # adj = (actual_push - sim_push) / 2 * (-1) = +0.0236 redistributed each way
    INT_LINE_CORRECTIONS = {6.0: -0.0471, 7.0: -0.0422}
    if line in INT_LINE_CORRECTIONS:
        corr  = INT_LINE_CORRECTIONS[line]
        adj   = -corr * 0.5   # positive → add to over/under, reduce push
        over_p  = max(0.0, min(1.0, over_p  + adj))
        under_p = max(0.0, min(1.0, under_p + adj))
        push_p  = max(0.0, min(1.0, push_p  - 2 * adj))

    return {"over": over_p, "under": under_p, "push": push_p,
            "lambda_home": lh_cal, "lambda_away": la_cal,
            "lambda_total": lh_cal + la_cal}

# ---------------------------------------------------------------------------
# Fetch NHL odds from Odds API
# ---------------------------------------------------------------------------
def fetch_nhl_odds(target_date: date) -> dict[tuple, dict]:
    """
    Returns {(home_abbrev, away_abbrev): {line, over_price, under_price, book}}
    for today's NHL games.
    """
    try:
        sys.path.insert(0, str(BASE_DIR))
        from config import ODDS_API_KEY
    except Exception:
        ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

    if not ODDS_API_KEY:
        print("  WARNING: ODDS_API_KEY not set — skipping odds fetch")
        return {}

    url = f"{ODDS_API_BASE}/sports/icehockey_nhl/odds"
    params = {
        "apiKey":      ODDS_API_KEY,
        "regions":     "us",
        "markets":     "totals",
        "dateFormat":  "iso",
        "oddsFormat":  "american",
        "bookmakers":  ",".join(BOOK_PRIORITY),
    }
    from shared.retry_utils import retry_request
    try:
        def _fetch_odds():
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp
        r = retry_request(_fetch_odds, max_retries=2, base_wait=15, label="NHL Odds API")
    except Exception as e:
        print(f"  WARNING: Odds API error: {e}")
        return {}

    remaining = r.headers.get("x-requests-remaining", "?")
    print(f"  Odds API credits remaining: {remaining}")

    result: dict[tuple, dict] = {}
    for game in r.json():
        home_name = game.get("home_team", "")
        away_name = game.get("away_team", "")
        home_abbrev = ODDS_TEAM_MAP.get(home_name)
        away_abbrev = ODDS_TEAM_MAP.get(away_name)
        if not home_abbrev or not away_abbrev:
            continue

        # Date filter: include today's games. Late-night ET starts (10 PM ET)
        # have UTC commence dates of tomorrow, so accept both today and tomorrow.
        # Extra games won't match schedule team names, so this is safe.
        commence = game.get("commence_time", "")[:10]
        _tomorrow = (target_date + timedelta(days=1)).isoformat()
        if commence not in (target_date.isoformat(), _tomorrow):
            continue

        # Pick best book by priority
        best = None
        for book_key in BOOK_PRIORITY:
            book = next((b for b in game.get("bookmakers", []) if b["key"] == book_key), None)
            if book:
                mkt = next((m for m in book.get("markets", []) if m["key"] == "totals"), None)
                if mkt:
                    outs = {o["name"]: o for o in mkt.get("outcomes", [])}
                    over  = outs.get("Over", {})
                    under = outs.get("Under", {})
                    if over and under:
                        best = {
                            "line":        float(over.get("point", 6.0)),
                            "over_price":  int(over.get("price", -110)),
                            "under_price": int(under.get("price", -110)),
                            "book":        book_key,
                            "commence_time": game.get("commence_time", ""),
                        }
                        break

        if best and 4.5 <= best["line"] <= 7.5:  # sanity: reject regulation-only or garbled totals
            result[(home_abbrev, away_abbrev)] = best

    return result

# ---------------------------------------------------------------------------
# Edge calculation
# ---------------------------------------------------------------------------
def american_to_implied(price: float) -> float:
    if pd.isna(price):
        return np.nan
    return abs(price) / (abs(price) + 100.0) if price < 0 else 100.0 / (100.0 + price)

def compute_edges(sim_probs: dict, over_price: float, under_price: float) -> dict:
    imp_o = american_to_implied(over_price)
    imp_u = american_to_implied(under_price)
    vig   = imp_o + imp_u
    fair_o = imp_o / vig
    fair_u = imp_u / vig
    return {
        "edge_over":   sim_probs["over"]  - fair_o,
        "edge_under":  sim_probs["under"] - fair_u,
        "fair_over":   fair_o,
        "fair_under":  fair_u,
    }

# ---------------------------------------------------------------------------
# Confidence tier
# ---------------------------------------------------------------------------
def _load_nhl_stop_rules():
    """Load NHL tier stop rules from config. Returns dict."""
    _rules_path = Path(__file__).resolve().parent / "data" / "nhl_stop_rules.json"
    try:
        if _rules_path.exists():
            import json as _json_sr
            return _json_sr.loads(_rules_path.read_text())
    except Exception:
        pass
    return {"high_tier": "active", "medium_tier": "active", "low_tier": "active"}

_NHL_STOP_RULES = _load_nhl_stop_rules()


def confidence_tier(edge: float, home_confirmed: bool, away_confirmed: bool,
                    backup_h: int, backup_a: int) -> str:
    vol_bucket = "high" if (backup_h + backup_a) >= 2 else "normal"
    # HIGH: edge >= 0.15 and not high volatility. Goalie confirmation is a display flag, not a gate.
    if edge >= 0.15 and vol_bucket != "high":
        return "HIGH"
    if edge >= 0.12:
        # Config-driven: active or shadow
        return "MEDIUM" if _NHL_STOP_RULES.get("medium_tier") == "active" else "SHADOW_MEDIUM"
    return "LOW" if _NHL_STOP_RULES.get("low_tier") == "active" else "SHADOW_LOW"

STAKE_UNITS = {"HIGH": 1.0, "MEDIUM": 0.75, "SHADOW_MEDIUM": 0.0, "LOW": 0.5, "SHADOW_LOW": 0.0}

def edge_bucket_label(edge: float) -> str:
    if edge < 0.12:
        return "0.10-0.12"
    if edge < 0.15:
        return "0.12-0.15"
    return "0.15+"

def bucket_label(line: float) -> str:
    return {5.5: "5.5", 6.0: "6.0", 6.5: "6.5"}.get(line, "other")

# ---------------------------------------------------------------------------
# Append signals to decisions parquet
# ---------------------------------------------------------------------------
def append_to_decisions(new_signals: list[dict]) -> None:
    if not new_signals:
        return
    new_df = pd.DataFrame(new_signals)
    new_df["game_date"] = pd.to_datetime(new_df["game_date"]).dt.date

    if DECISIONS.exists():
        existing = pd.read_parquet(DECISIONS)
        existing["game_date"] = pd.to_datetime(existing["game_date"]).dt.date
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["game_id", "signal_side"], keep="last")
    else:
        combined = new_df

    combined.to_parquet(DECISIONS, index=False)
    print(f"  Decisions file updated: {len(combined):,} total rows")

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(target_date: date) -> None:
    print("=" * 66)
    print(f"NHL Daily Pipeline  —  {target_date.isoformat()}")
    print("=" * 66)

    # Load models
    hpkg, apkg = load_models()
    ft = load_feature_table()

    # Train means for null fill (same as Phase 3)
    all_feats = sorted(set(hpkg["features"] + apkg["features"]))
    train = ft[ft["season_year"].isin({2021, 2022})]
    train_means = train[all_feats].mean()

    # League-average priors for current season
    priors = compute_league_priors(ft)

    # Load live season data
    print("\nLoading current-season game data...")
    live = load_or_refresh_live_season(target_date)
    if len(live) > 0:
        print(f"  Current-season games loaded: {len(live)}")
    else:
        print(f"  No current-season data — using 2024-25 league averages as priors")

    # Fetch today's schedule
    print(f"\nFetching NHL schedule for {target_date.isoformat()}...")
    games = fetch_schedule(target_date)
    if not games:
        print(f"  No games found for {target_date.isoformat()}")
        return
    print(f"  {len(games)} games scheduled")

    # Fetch odds
    print("\nFetching NHL totals from Odds API...")
    odds_map = fetch_nhl_odds(target_date)
    print(f"  {len(odds_map)} games with odds")

    # Load open line snapshot for line movement
    _nhl_open_lookup = {}
    try:
        _open_date_str = target_date.isoformat().replace("-", "_")
        _open_path = NHL_DIR / "data" / f"nhl_lines_open_{_open_date_str}.json"
        if _open_path.exists():
            import json as _json_lm
            with open(_open_path) as _f:
                for _snap in _json_lm.load(_f):
                    if _snap.get("snapshot_type") == "open":
                        _nhl_open_lookup[(_snap.get("home_team",""), _snap.get("away_team",""))] = _snap.get("total_line")
            print(f"  Open snapshot loaded: {len(_nhl_open_lookup)} games")
    except Exception as _e:
        print(f"  Open snapshot load failed (non-fatal): {_e}")

    # Process each game
    print(f"\nProcessing {len(games)} games...")
    signals = []
    processed = 0

    for g in games:
        home = g.get("homeTeam", {}).get("abbrev", "")
        away = g.get("awayTeam", {}).get("abbrev", "")
        game_id = g.get("id")
        state   = g.get("gameState", "")

        if not home or not away:
            continue

        # Get odds for this matchup
        odds = odds_map.get((home, away))
        if not odds:
            # Try reversed (Odds API may list differently)
            odds = odds_map.get((away, home))
            if not odds:
                print(f"  [{away} @ {home}] No odds — skipping")
                continue

        line       = odds["line"]
        over_price = odds["over_price"]
        under_price = odds["under_price"]

        # Fetch goalie info (game may be in pregame state)
        home_goalie_info = {}
        away_goalie_info = {}
        if state in ("FUT", "PRE", "LIVE", "CRIT", "OFF") and game_id:
            goalies = fetch_goalies(game_id)
            home_goalie_info = goalies.get("home", {})
            away_goalie_info = goalies.get("away", {})

        home_confirmed = bool(home_goalie_info.get("starter") is not None)
        away_confirmed = bool(away_goalie_info.get("starter") is not None)
        home_backup = int(home_goalie_info.get("starter") is False)
        away_backup = int(away_goalie_info.get("starter") is False)

        # Compute features
        feat = compute_game_features(
            home, away, target_date, live, priors,
            home_goalie_info, away_goalie_info,
        )

        # Predict + calibrate
        lh_cal, la_cal, drift = predict_and_calibrate(
            feat, hpkg, apkg, live, target_date, train_means
        )

        # Simulate
        sim_probs = simulate(lh_cal, la_cal, line)

        # Edges
        edges = compute_edges(sim_probs, over_price, under_price)

        processed += 1
        print(f"  [{away} @ {home}]  line={line}  λ_total={sim_probs['lambda_total']:.2f}  "
              f"edge_over={edges['edge_over']:+.3f}  edge_under={edges['edge_under']:+.3f}")

        # Qualify signals
        for side, edge_val, sim_p, fair_p in [
            ("OVER",  edges["edge_over"],  sim_probs["over"],  edges["fair_over"]),
            ("UNDER", edges["edge_under"], sim_probs["under"], edges["fair_under"]),
        ]:
            if edge_val < THRESHOLD:
                continue

            caution  = 1 if side == "OVER" and bucket_label(line) == "6.5" else 0
            tier     = confidence_tier(edge_val, home_confirmed, away_confirmed,
                                       home_backup, away_backup)
            stake    = STAKE_UNITS.get(tier, 0.75)
            ebkt     = edge_bucket_label(edge_val)
            bkt      = bucket_label(line)

            signal = {
                "game_id":                  game_id,
                "game_date":                target_date.isoformat(),
                "home_team":                home,
                "away_team":                away,
                "season_year":              target_date.year if target_date.month >= 10
                                            else target_date.year - 1,
                "split":                    "live",
                "signal_side":              side,
                "closing_total":            line,
                "closing_total_bucket":     bkt,
                "edge":                     edge_val,
                "edge_bucket":              ebkt,
                "sim_prob":                 sim_p,
                "fair_prob":                fair_p,
                "lambda_total_calibrated":  sim_probs["lambda_total"],
                "lambda_vs_line":           sim_probs["lambda_total"] - line,
                "volatility_bucket":        "low",
                "confidence_tier":          tier,
                "stake_units":              stake,
                "caution_flag":             caution,
                "backup_flag_home":         home_backup,
                "backup_flag_away":         away_backup,
                "goalie_confirmed_home":    home_confirmed,
                "goalie_confirmed_away":    away_confirmed,
                "over_price":               over_price,
                "under_price":              under_price,
                "book":                     odds.get("book", ""),
                "commence_time":            odds.get("commence_time", ""),
                "actual_total_goals_final": np.nan,
                "result":                   "UNGRADED",
                "graded":                   0,
                # ── Scoring-form features for summary generation ──────────────
                # Goals rolling 10: actual current-season data from live cache
                # xGF/xGA/PP: league-average priors (MoneyPuck not in live feed)
                "home_goals_scored_rolling_10":  feat.get("home_goals_scored_rolling_10"),
                "away_goals_scored_rolling_10":  feat.get("away_goals_scored_rolling_10"),
                "home_goals_allowed_rolling_10": feat.get("home_goals_allowed_rolling_10"),
                "away_goals_allowed_rolling_10": feat.get("away_goals_allowed_rolling_10"),
                "home_xgf_rolling_20":           feat.get("home_xgf_rolling_20"),
                "away_xgf_rolling_20":           feat.get("away_xgf_rolling_20"),
                "home_xga_rolling_20":           feat.get("home_xga_rolling_20"),
                "away_xga_rolling_20":           feat.get("away_xga_rolling_20"),
                "home_pp_pct_rolling_20":        feat.get("home_pp_pct_rolling_20"),
                "away_pp_pct_rolling_20":        feat.get("away_pp_pct_rolling_20"),
                "home_goalie_vs_team_baseline":  feat.get("home_goalie_vs_team_baseline", 0.0),
                "away_goalie_vs_team_baseline":  feat.get("away_goalie_vs_team_baseline", 0.0),
                "home_goalie_b2b":               feat.get("home_goalie_b2b", 0),
                "away_goalie_b2b":               feat.get("away_goalie_b2b", 0),
                "home_b2b":                      feat.get("home_b2b", 0),
                "away_b2b":                      feat.get("away_b2b", 0),
                # Line movement (open snapshot vs current)
                "open_total":                    _nhl_open_lookup.get((home, away)),
                "line_movement":                 round(line - _nhl_open_lookup[(home, away)], 1)
                                                 if (home, away) in _nhl_open_lookup else None,
            }
            signals.append(signal)
            print(f"    *** SIGNAL: {side}  edge={edge_val:.4f}  tier={tier}  "
                  f"{'CAUTION' if caution else ''}")

    # Summary
    print()
    print("=" * 66)
    print(f"SUMMARY  —  {target_date.isoformat()}")
    print("=" * 66)
    print(f"  Games processed: {processed}")
    print(f"  Signals generated: {len(signals)}")
    if signals:
        for s in signals:
            print(f"    {s['away_team']} @ {s['home_team']}  {s['signal_side']}  "
                  f"line={s['closing_total']}  edge={s['edge']:.4f}  "
                  f"tier={s['confidence_tier']}")

    # Write to decisions
    if signals:
        print()
        append_to_decisions(signals)
    else:
        print("  No qualified signals — nhl_decisions.parquet unchanged")
    # -- Write to aligned shadow tracker --
    _tracker_path = NHL_DIR / "logs" / "nhl_shadow_aligned_2026.json"
    if signals:
        try:
            import json as _json_trk
            if _tracker_path.exists():
                _trk = _json_trk.loads(_tracker_path.read_text())
            else:
                _trk = {
                    "model_version": "model_A_aligned_v1",
                    "object_id": "nhl_shadow_aligned_20260411",
                    "start_date": "2026-04-11",
                    "signals": []
                }
            _existing_gpks = {s.get("game_id") for s in _trk["signals"]}
            for _sig in signals:
                if _sig["game_id"] not in _existing_gpks:
                    _trk["signals"].append({
                        "game_id": _sig["game_id"],
                        "game_date": _sig["game_date"],
                        "home_team": _sig["home_team"],
                        "away_team": _sig["away_team"],
                        "signal_side": _sig["signal_side"],
                        "edge": round(_sig["edge"], 4),
                        "tier": _sig["confidence_tier"],
                        "closing_total": _sig["closing_total"],
                        "lambda_total": round(_sig["lambda_total_calibrated"], 3),
                        "drift_applied": 0.0,
                    })
                    _existing_gpks.add(_sig["game_id"])
            _tracker_path.write_text(_json_trk.dumps(_trk, indent=2))
            print(f"  Shadow tracker updated: {len(_trk['signals'])} total signals")
        except Exception as _e:
            print(f"  WARNING: Shadow tracker write failed: {_e}")


# ---------------------------------------------------------------------------
# Grade yesterday's live signals
# ---------------------------------------------------------------------------
def _sync_shadow_tracker(dec) -> None:
    """Propagate grading results from decisions parquet into shadow tracker JSON."""
    _tracker_path = NHL_DIR / "logs" / "nhl_shadow_aligned_2026.json"
    if not _tracker_path.exists():
        return
    import json as _json_sync
    _trk = _json_sync.loads(_tracker_path.read_text())
    _graded_map = {}
    for _, _r in dec[(dec["graded"] == 1) & (dec["split"] == "live")].iterrows():
        _graded_map[int(_r["game_id"])] = {
            "result": _r["result"],
            "actual_total": int(_r["actual_total_goals_final"]) if pd.notna(_r.get("actual_total_goals_final")) else None,
        }
    _synced = 0
    for _sig in _trk.get("signals", []):
        _gid = _sig.get("game_id")
        if _gid in _graded_map and _sig.get("result") in (None, "NONE", "UNGRADED"):
            _sig["result"] = _graded_map[_gid]["result"]
            _sig["actual_total"] = _graded_map[_gid]["actual_total"]
            _synced += 1
    if _synced:
        _tracker_path.write_text(_json_sync.dumps(_trk, indent=2))
        print(f"  Shadow tracker synced: {_synced} signal(s) updated with results.")
    else:
        print("  Shadow tracker: no new results to sync.")


def grade_yesterday(yesterday: date) -> None:
    """
    Fetch yesterday's final scores from NHLe API and grade any live signals
    in nhl_decisions.parquet that are still UNGRADED.

    Match key: canonical NHL API game_id (integer).  This is the primary and
    only join key.  No date+team fallback exists — if a game_id is absent from
    the score_map the signal is left ungraded and a warning is printed.

    Idempotent: rows with graded=1 are skipped unconditionally; running twice
    produces zero additional writes.
    """
    print(f"\nGrading yesterday ({yesterday.isoformat()}) ...")
    print(f"  Match key: canonical NHL API game_id (integer primary key)")

    if not DECISIONS.exists():
        print("  No decisions file — nothing to grade.")
        return

    dec = pd.read_parquet(DECISIONS)
    dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date

    # Separate yesterday's live signals into already-graded and pending
    yest_live = dec[(dec["game_date"] == yesterday) & (dec["split"] == "live")]
    already_graded = yest_live[yest_live["graded"] == 1]
    pending        = yest_live[yest_live["graded"] == 0]

    skipped_count = len(already_graded)
    if skipped_count:
        print(f"  Skipping {skipped_count} already-graded row(s) (idempotency).")

    if pending.empty:
        print(f"  Graded 0 new rows, skipped {skipped_count} already-graded rows.")
        # Still sync shadow tracker even if no new grading needed
        _sync_shadow_tracker(dec)
        return

    print(f"  {len(pending)} pending signal(s) to grade.")

    # Fetch yesterday's schedule + final scores
    url = f"{NHL_API}/schedule/{yesterday.isoformat()}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  WARNING: Could not fetch schedule: {e}")
        return

    game_dates = data.get("gameWeek", [])
    yest_str   = yesterday.isoformat()
    day_entry  = next((d for d in game_dates if d.get("date") == yest_str), None)
    if not day_entry:
        print(f"  No games found for {yest_str} in API response.")
        return

    # Build game_id → total_goals map from final scores.
    # Match key is the integer game_id returned by the NHLe API — same value
    # stored in nhl_decisions.parquet at signal-creation time.
    score_map: dict[int, int] = {}
    for g in day_entry.get("games", []):
        gid    = g.get("id")
        state  = g.get("gameState", "")
        home_s = g.get("homeTeam", {}).get("score")
        away_s = g.get("awayTeam", {}).get("score")
        if gid and state in ("OFF", "FINAL") and home_s is not None and away_s is not None:
            score_map[int(gid)] = int(home_s) + int(away_s)

    if not score_map:
        print("  No final scores available yet — try again later.")
        return

    print(f"  Final scores fetched for {len(score_map)} game(s) via game_id match.")

    # Load market snapshots for CLV computation
    _snap_path = NHL_DIR / "nhl_clv_snapshots.parquet"
    _morning_lines: dict[int, float] = {}
    _pregame_lines: dict[int, float] = {}
    if _snap_path.exists():
        _snaps = pd.read_parquet(_snap_path)
        for _, _sr in _snaps.iterrows():
            _gid = int(_sr["game_id"])
            if _sr.get("snapshot_type") == "morning":
                _morning_lines[_gid] = float(_sr["line"])
            elif _sr.get("snapshot_type") == "pregame":
                _pregame_lines[_gid] = float(_sr["line"])

    # Ensure CLV columns exist in dec before writing
    for _col in ("closing_line", "clv_raw", "clv_directional", "snapshot_source"):
        if _col not in dec.columns:
            dec[_col] = None

    # Grade each pending signal — skip any already graded (idempotency guard)
    graded_count = 0
    for idx in pending.index:
        # FIX 1: explicit idempotency — never touch a row with graded=1
        if dec.at[idx, "graded"] == 1:
            skipped_count += 1
            continue

        gid = int(dec.at[idx, "game_id"])

        # FIX 2: game_id is the sole match key; no fallback
        if gid not in score_map:
            home = dec.at[idx, "home_team"]
            away = dec.at[idx, "away_team"]
            print(f"  WARNING: game_id {gid} ({away} @ {home}) not in score_map "
                  f"— score may not be final; leaving ungraded.")
            continue

        total = score_map[gid]
        line  = dec.at[idx, "closing_total"]
        side  = dec.at[idx, "signal_side"]

        if total == line:
            result = "PUSH"
        elif side == "OVER":
            result = "WIN" if total > line else "LOSS"
        else:
            result = "WIN" if total < line else "LOSS"

        dec.at[idx, "actual_total_goals_final"] = total
        dec.at[idx, "result"] = result
        dec.at[idx, "graded"] = 1

        # ── CLV persistence ───────────────────────────────────────────────
        _line_taken  = _morning_lines.get(gid)   # 7am decision-time line
        _closing     = _pregame_lines.get(gid)   # 5pm closing line
        if _closing is not None:
            dec.at[idx, "closing_line"] = _closing
            if _line_taken is not None:
                _clv_raw = _closing - _line_taken
                _clv_dir = _clv_raw if side == "OVER" else -_clv_raw
                dec.at[idx, "clv_raw"]         = round(_clv_raw, 2)
                dec.at[idx, "clv_directional"] = round(_clv_dir, 2)
                dec.at[idx, "snapshot_source"] = "morning+pregame"
            else:
                dec.at[idx, "snapshot_source"] = "pregame_only"
        else:
            dec.at[idx, "snapshot_source"] = "missing"

        graded_count += 1

        home = dec.at[idx, "home_team"]
        away = dec.at[idx, "away_team"]
        print(f"    game_id={gid}  {away} @ {home}  {side}  "
              f"line={line}  actual={total}  → {result}")

    print(f"  Graded {graded_count} new rows, skipped {skipped_count} already-graded rows.")

    if graded_count:
        dec.to_parquet(DECISIONS, index=False)
        print(f"  Decisions file updated.")
    else:
        print("  No new rows written — file unchanged.")

    # ── Sync grading results into shadow tracker JSON ──────────────────────
    _sync_shadow_tracker(dec)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NHL Daily Prediction Pipeline")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--grade-yesterday", action="store_true",
                        help="Grade yesterday's live signals before running today's pipeline")
    args = parser.parse_args()

    if args.date:
        target = date.fromisoformat(args.date)
    else:
        target = date.today()

    if args.grade_yesterday:
        grade_yesterday(target - timedelta(days=1))

    run_pipeline(target)

    # Auto-push + timestamp
    import subprocess
    _lu = BASE_DIR / "shared" / "last_updated.json"
    _d = json.load(open(_lu)) if _lu.exists() else {}
    _d["nhl"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(_lu, "w") as f:
        json.dump(_d, f, indent=2)
    # Push handled by push_daemon.sh
    # subprocess.run(["bash", str(BASE_DIR / "shared" / "git_push.sh"), "NHL pipeline run"],
    #                capture_output=True)
