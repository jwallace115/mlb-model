"""
Core projection engine — combines all factors into a total runs projection.

Projection formula (multiplicative):
  For each team's expected runs scored (batting against the opposing SP):
    runs_team = BASE_RUNS
              x sp_factor          (SP xFIP/SIERA vs league avg, regressed)
              x offense_factor     (team wRC+ vs 100)
              x park_factor        (runs park factor / 100)
              x weather_factor     (wind + temp combined)
              x umpire_factor      (runs environment tendency)
              x bullpen_factor     (full game only, from bullpen fatigue)

  SP innings per start are pulled from the pitcher's season average (dynamic).
  Fallback: 5.5 innings if no data is available.

  proj_total_full = runs_away + runs_home
  proj_total_f5   = runs_away_f5 + runs_home_f5  (SP only, capped at 5.0 inn)
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

DEFAULT_SP_IP    = 5.5   # fallback when no season data is available
LEAGUE_AVG_FB_PCT = 0.35  # league-average fly ball rate for pitchers


def _sp_factor(sp_metrics: dict) -> float:
    """
    Convert pitcher xFIP/SIERA into a multiplicative factor on opponent runs.
    Higher xFIP -> higher factor -> more runs allowed.
    Stats are already regressed+blended when they arrive from get_pitcher_metrics().
    """
    xfip  = sp_metrics.get("xfip",  LEAGUE_AVG_ERA)
    siera = sp_metrics.get("siera", LEAGUE_AVG_ERA)
    blended = (xfip + siera) / 2
    return blended / LEAGUE_AVG_ERA


def _sp_ip(sp_metrics: dict) -> float:
    """
    Return the SP's season-average innings per start.
    Clamped to [4.0, 7.0]; falls back to DEFAULT_SP_IP if unavailable.
    """
    avg = sp_metrics.get("avg_ip_per_start")
    if avg is None or avg <= 0:
        return DEFAULT_SP_IP
    return max(4.0, min(float(avg), 7.0))


def _offense_factor(offense_metrics: dict) -> float:
    wrc = offense_metrics.get("wrc_plus", 100)
    return wrc / 100.0


def _park_factor(home_team: str) -> float:
    pf = STADIUMS.get(home_team, {}).get("park_factor", 100)
    return pf / 100.0


def _compute_confidence(factors_dict: dict, proj_total: float,
                        neutral_total: float) -> tuple[str, float]:
    deviation = abs(proj_total - neutral_total)
    score = min(deviation / 2.5, 1.0)

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

    if combined_score >= 0.72:
        label = "HIGH"
    elif combined_score >= 0.45:
        label = "MEDIUM"
    else:
        label = "LOW"

    # Require at least 1.5 run deviation from neutral for HIGH confidence
    if label == "HIGH" and deviation < 1.5:
        label = "MEDIUM"

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
    SP innings are pulled dynamically from pitcher metrics.
    """
    w  = weights   or MODEL_WEIGHTS
    wf = f5_weights or F5_WEIGHTS

    base = LEAGUE_AVG_RUNS_PER_TEAM   # per-team base runs (~4.50)

    # --- Component factors ---
    sp_h = _sp_factor(home_sp_metrics)   # effect on AWAY team's runs (home pitcher)
    sp_a = _sp_factor(away_sp_metrics)   # effect on HOME team's runs (away pitcher)

    off_h = _offense_factor(home_offense)
    off_a = _offense_factor(away_offense)

    pf     = _park_factor(home_team)
    wf_wnd = weather.get("wind_factor", 1.0)
    wf_tmp = weather.get("temp_factor", 1.0)

    # Wind × flyball interaction: pitchers who allow more flyballs are more wind-sensitive.
    # away team scores against HOME SP → use home SP's fb_pct to scale wind for away runs.
    # home team scores against AWAY SP → use away SP's fb_pct to scale wind for home runs.
    home_fb_pct = home_sp_metrics.get("fb_pct") or LEAGUE_AVG_FB_PCT
    away_fb_pct = away_sp_metrics.get("fb_pct") or LEAGUE_AVG_FB_PCT
    away_wind_adj = 1.0 + (wf_wnd - 1.0) * (home_fb_pct / LEAGUE_AVG_FB_PCT)
    home_wind_adj = 1.0 + (wf_wnd - 1.0) * (away_fb_pct / LEAGUE_AVG_FB_PCT)
    # Cap: ±15% max from wind×flyball to avoid runaway adjustments
    away_wind_adj = max(0.85, min(away_wind_adj, 1.15))
    home_wind_adj = max(0.85, min(home_wind_adj, 1.15))
    away_weather_combined = away_wind_adj * wf_tmp   # for away runs (vs home SP)
    home_weather_combined = home_wind_adj * wf_tmp   # for home runs (vs away SP)

    ump        = umpire.get("runs_factor", 1.0)

    bp_h_mult  = home_bullpen.get("fatigue_multiplier", 1.0)
    bp_a_mult  = away_bullpen.get("fatigue_multiplier", 1.0)

    # --- Dynamic SP innings ---
    # home_sp_ip: innings the HOME pitcher is expected to throw (affects away team's runs)
    # away_sp_ip: innings the AWAY pitcher is expected to throw (affects home team's runs)
    home_sp_ip = _sp_ip(home_sp_metrics)
    away_sp_ip = _sp_ip(away_sp_metrics)

    home_sp_frac = home_sp_ip / 9.0
    home_bp_frac = 1.0 - home_sp_frac
    away_sp_frac = away_sp_ip / 9.0
    away_bp_frac = 1.0 - away_sp_frac

    # --- Full game run estimates ---
    # Away team scores: home SP pitches home_sp_ip innings, home BP pitches home_bp_frac
    runs_away_sp = base * home_sp_frac * sp_h  * off_a * pf * away_weather_combined * ump
    runs_away_bp = base * home_bp_frac * (LEAGUE_AVG_BULLPEN_ERA / LEAGUE_AVG_ERA) * bp_h_mult * off_a * pf * away_weather_combined * ump
    runs_away    = runs_away_sp + runs_away_bp

    # Home team scores: away SP pitches away_sp_ip innings, away BP pitches away_bp_frac
    runs_home_sp = base * away_sp_frac * sp_a  * off_h * pf * home_weather_combined * ump
    runs_home_bp = base * away_bp_frac * (LEAGUE_AVG_BULLPEN_ERA / LEAGUE_AVG_ERA) * bp_a_mult * off_h * pf * home_weather_combined * ump
    runs_home    = runs_home_sp + runs_home_bp

    proj_full = runs_away + runs_home

    # --- F5 run estimates ---
    # Each SP's contribution to F5 is capped at 5 innings.
    # If SP averages < 5 IP, they may be pulled before F5 ends (conservative estimate).
    home_f5_frac = min(home_sp_ip, 5.0) / 9.0
    away_f5_frac = min(away_sp_ip, 5.0) / 9.0

    runs_away_f5 = base * home_f5_frac * sp_h  * off_a * pf * away_weather_combined * ump
    runs_home_f5 = base * away_f5_frac * sp_a  * off_h * pf * home_weather_combined * ump
    proj_f5      = runs_away_f5 + runs_home_f5

    # --- Neutral baseline ---
    neutral_full = base * 2   # 9 runs total, all factors = 1.0

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
        "home_wind_adj":        home_wind_adj,
        "away_wind_adj":        away_wind_adj,
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
        "runs_home":         round(runs_home, 2),
        "runs_away":         round(runs_away, 2),
        "runs_home_f5":      round(runs_home_f5, 2),
        "runs_away_f5":      round(runs_away_f5, 2),
        "home_sp_ip":        round(home_sp_ip, 2),
        "away_sp_ip":        round(away_sp_ip, 2),
        "factors": {
            "sp_home_xfip":         home_sp_metrics.get("xfip"),
            "sp_away_xfip":         away_sp_metrics.get("xfip"),
            "sp_home_siera":        home_sp_metrics.get("siera"),
            "sp_away_siera":        away_sp_metrics.get("siera"),
            "sp_home_ip_per_start": round(home_sp_ip, 2),
            "sp_away_ip_per_start": round(away_sp_ip, 2),
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
            "home_wind_adj":        round(home_wind_adj, 4),
            "away_wind_adj":        round(away_wind_adj, 4),
            "home_sp_fb_pct":       home_fb_pct,
            "away_sp_fb_pct":       away_fb_pct,
            "umpire_name":          umpire.get("name"),
            "umpire_runs_factor":   round(ump, 4),
            "home_bp_fatigue":      home_bullpen.get("fatigue_score"),
            "away_bp_fatigue":      away_bullpen.get("fatigue_score"),
            "home_bp_innings_used": home_bullpen.get("innings_used"),
            "away_bp_innings_used": away_bullpen.get("innings_used"),
            "home_bp_xfip":         home_bullpen.get("team_xfip"),
            "away_bp_xfip":         away_bullpen.get("team_xfip"),
            "home_tier1_red":       home_bullpen.get("tier1_red_arms", 0),
            "away_tier1_red":       away_bullpen.get("tier1_red_arms", 0),
        },
    }
