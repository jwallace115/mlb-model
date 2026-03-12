"""
Core projection engine — combines all factors into a total runs projection.

Projection formula (multiplicative):
  For each team's expected runs scored (batting against the opposing SP):
    runs_team = BASE_RUNS
              × sp_factor          (SP xFIP/SIERA vs league avg)
              × offense_factor     (team wRC+ vs 100)
              × park_factor        (runs park factor / 100)
              × weather_factor     (wind + temp combined)
              × umpire_factor      (runs environment tendency)
              × bullpen_factor     (full game only, from bullpen fatigue)

  proj_total_full = runs_away + runs_home
  proj_total_f5   = runs_away_f5 + runs_home_f5  (SP only, ~56% of full-game total)
"""

import logging
from typing import Optional

from config import (
    MODEL_WEIGHTS, F5_WEIGHTS,
    LEAGUE_AVG_RUNS_PER_TEAM, LEAGUE_AVG_ERA,
    LEAGUE_AVG_BULLPEN_ERA, F5_RUN_FRACTION,
    STADIUMS,
)

logger = logging.getLogger(__name__)


def _sp_factor(sp_metrics: dict) -> float:
    """
    Convert pitcher xFIP/SIERA into a multiplicative factor on opponent runs.
    Higher xFIP → higher factor → more runs allowed.
    """
    xfip  = sp_metrics.get("xfip",  LEAGUE_AVG_ERA)
    siera = sp_metrics.get("siera", LEAGUE_AVG_ERA)
    # Blend xFIP and SIERA equally
    blended = (xfip + siera) / 2
    return blended / LEAGUE_AVG_ERA


def _offense_factor(offense_metrics: dict) -> float:
    """wRC+ directly as a fraction of league average."""
    wrc = offense_metrics.get("wrc_plus", 100)
    return wrc / 100.0


def _park_factor(home_team: str) -> float:
    """Stadium runs park factor, normalised to 1.0."""
    pf = STADIUMS.get(home_team, {}).get("park_factor", 100)
    return pf / 100.0


def _compute_confidence(factors_dict: dict, proj_total: float,
                        neutral_total: float) -> tuple[str, float]:
    """
    Score confidence based on how much the projection deviates from neutral
    AND whether the key factors are aligned.

    Returns (label, score_0_to_1)
    """
    deviation = abs(proj_total - neutral_total)
    # Score relative to a 1-run deviation being "high"
    score = min(deviation / 1.0, 1.0)

    # Check alignment of key directional factors
    directional = []
    for key in ("sp_factor_home", "sp_factor_away", "offense_factor_home",
                "offense_factor_away", "park_factor", "weather_wind_factor",
                "umpire_factor"):
        val = factors_dict.get(key, 1.0)
        if val > 1.0:
            directional.append(1)
        elif val < 1.0:
            directional.append(-1)

    alignment = abs(sum(directional)) / max(len(directional), 1)
    combined_score = 0.6 * score + 0.4 * alignment

    if combined_score >= 0.65:
        label = "HIGH"
    elif combined_score >= 0.35:
        label = "MEDIUM"
    else:
        label = "LOW"

    return label, round(combined_score, 3)


def project_game(
    home_team: str,
    away_team: str,
    home_sp_metrics: dict,
    away_sp_metrics: dict,
    home_offense: dict,
    away_offense: dict,
    weather: dict,
    umpire: dict,
    home_bullpen: dict,
    away_bullpen: dict,
    weights: Optional[dict] = None,
    f5_weights: Optional[dict] = None,
) -> dict:
    """
    Project the total runs for a game (full game + F5).

    All factor dicts come from their respective modules.
    Returns a dict with projected totals, factors breakdown, and confidence.
    """
    w  = weights   or MODEL_WEIGHTS
    wf = f5_weights or F5_WEIGHTS

    base = LEAGUE_AVG_RUNS_PER_TEAM  # per-team base runs (~4.50)

    # --- Component factors ---
    sp_h = _sp_factor(home_sp_metrics)  # effect on AWAY team's runs (home pitcher)
    sp_a = _sp_factor(away_sp_metrics)  # effect on HOME team's runs (away pitcher)

    off_h = _offense_factor(home_offense)
    off_a = _offense_factor(away_offense)

    pf    = _park_factor(home_team)
    wf_wnd = weather.get("wind_factor", 1.0)
    wf_tmp = weather.get("temp_factor", 1.0)
    weather_combined = wf_wnd * wf_tmp

    ump   = umpire.get("runs_factor", 1.0)

    # Bullpen: how the multiplier affects the back-end innings
    bp_h_mult = home_bullpen.get("fatigue_multiplier", 1.0)
    bp_a_mult = away_bullpen.get("fatigue_multiplier", 1.0)

    # --- Full game run estimates ---
    # Away team scores:
    #   SP innings (~5.5 inn): driven by home SP (sp_h) and away offense (off_a)
    #   Bullpen innings (~3.5 inn): driven by home bullpen fatigue (bp_h_mult)
    sp_frac   = 5.5 / 9.0
    bp_frac   = 3.5 / 9.0

    runs_away_sp  = base * sp_frac  * sp_h  * off_a * pf * weather_combined * ump
    runs_away_bp  = base * bp_frac  * (LEAGUE_AVG_BULLPEN_ERA / LEAGUE_AVG_ERA) * bp_h_mult * off_a * pf * weather_combined * ump
    runs_away     = runs_away_sp + runs_away_bp

    runs_home_sp  = base * sp_frac  * sp_a  * off_h * pf * weather_combined * ump
    runs_home_bp  = base * bp_frac  * (LEAGUE_AVG_BULLPEN_ERA / LEAGUE_AVG_ERA) * bp_a_mult * off_h * pf * weather_combined * ump
    runs_home     = runs_home_sp + runs_home_bp

    proj_full = runs_away + runs_home

    # --- F5 run estimates (SP only) ---
    runs_away_f5 = base * F5_RUN_FRACTION * sp_h  * off_a * pf * weather_combined * ump
    runs_home_f5 = base * F5_RUN_FRACTION * sp_a  * off_h * pf * weather_combined * ump
    proj_f5  = runs_away_f5 + runs_home_f5

    # --- Neutral baseline (all factors = 1.0, no park/weather/ump adjustment) ---
    neutral_full = base * 2  # 9 runs total

    # --- Confidence ---
    factors_dict = {
        "sp_factor_home":       sp_h,
        "sp_factor_away":       sp_a,
        "offense_factor_home":  off_h,
        "offense_factor_away":  off_a,
        "park_factor":          pf,
        "weather_wind_factor":  wf_wnd,
        "weather_temp_factor":  wf_tmp,
        "umpire_factor":        ump,
        "bullpen_fatigue_home": bp_h_mult,
        "bullpen_fatigue_away": bp_a_mult,
    }
    confidence_label, confidence_score = _compute_confidence(
        factors_dict, proj_full, neutral_full
    )

    # --- Over/under lean ---
    if proj_full > neutral_full + 0.3:
        lean = "OVER"
    elif proj_full < neutral_full - 0.3:
        lean = "UNDER"
    else:
        lean = "NEUTRAL"

    return {
        "home_team":         home_team,
        "away_team":         away_team,
        "proj_total_full":   round(proj_full, 2),
        "proj_total_f5":     round(proj_f5, 2),
        "neutral_baseline":  round(neutral_full, 2),
        "lean":              lean,
        "confidence":        confidence_label,
        "confidence_score":  confidence_score,
        # Per-team splits
        "runs_home":         round(runs_home, 2),
        "runs_away":         round(runs_away, 2),
        "runs_home_f5":      round(runs_home_f5, 2),
        "runs_away_f5":      round(runs_away_f5, 2),
        # Factor breakdown (for transparency / debugging)
        "factors": {
            "sp_home_xfip":         home_sp_metrics.get("xfip"),
            "sp_away_xfip":         away_sp_metrics.get("xfip"),
            "sp_home_siera":        home_sp_metrics.get("siera"),
            "sp_away_siera":        away_sp_metrics.get("siera"),
            "home_wrc_plus":        home_offense.get("wrc_plus"),
            "away_wrc_plus":        away_offense.get("wrc_plus"),
            "park_factor":          round(pf, 3),
            "wind_speed_mph":       weather.get("wind_speed_mph"),
            "wind_direction":       weather.get("wind_direction"),
            "wind_desc":            weather.get("wind_desc"),
            "temperature_f":        weather.get("temperature_f"),
            "weather_desc":         weather.get("description"),
            "wind_factor":          round(wf_wnd, 4),
            "temp_factor":          round(wf_tmp, 4),
            "umpire_name":          umpire.get("name"),
            "umpire_runs_factor":   round(ump, 4),
            "home_bp_fatigue":      home_bullpen.get("fatigue_score"),
            "away_bp_fatigue":      away_bullpen.get("fatigue_score"),
            "home_bp_innings_used": home_bullpen.get("innings_used"),
            "away_bp_innings_used": away_bullpen.get("innings_used"),
        },
    }
