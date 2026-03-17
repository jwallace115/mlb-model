"""
modules/sim_projections.py — Phase 9 simulation model, wrapped in the same
interface as modules/projections.project_game().

Called by run_model.py when MODEL_MODE == "simulation".
Returns a proj dict with the same schema as project_game() so that all
downstream code (serialize_results, classify_game, push_results, dashboard)
requires no changes.

Extra keys added (ignored by downstream if not explicitly used):
    sim_sigma    float   per-game σ from Phase 9 variance model
    sim_p_over   float   P(total > line) — NaN if no line available
    sim_ci_lo    float   10th-percentile (80% CI lower bound)
    sim_ci_hi    float   90th-percentile (80% CI upper bound)
"""

import math
import pickle
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

# ── paths ─────────────────────────────────────────────────────────────────────
_ROOT        = Path(__file__).resolve().parent.parent
_SIM         = _ROOT / "sim"
_BASELINE    = _SIM / "data" / "phase9_baseline_model.pkl"
_VARIANCE    = _SIM / "data" / "phase9_variance_model.pkl"

# ── constants ─────────────────────────────────────────────────────────────────
_SQRT_2_PI   = math.sqrt(2.0 / math.pi)
_N_SIMS      = 50_000
_SEED        = 42
_F5_FRACTION = 0.56     # fraction of game total that falls in first 5 innings
_SIGMA_MIN   = 3.0
_PROJ_MIN    = 4.0
_PROJ_MAX    = 22.0

# League-average defaults (used when live pipeline hasn't populated k_pct/bb_pct yet)
_LEAGUE_K_PCT  = 0.224
_LEAGUE_BB_PCT = 0.085
_LEAGUE_FB_PCT = 0.385
_LEAGUE_AVG_IP = 5.5

# confidence mapping: |proj − 9.0| → tier
_CONF_HIGH   = 1.5
_CONF_MEDIUM = 0.75


@lru_cache(maxsize=1)
def _load_models() -> tuple[dict, dict]:
    """Load Phase 9 baseline + variance models once; cache for process lifetime."""
    if not _BASELINE.exists():
        raise FileNotFoundError(f"Phase 9 baseline not found: {_BASELINE}")
    if not _VARIANCE.exists():
        raise FileNotFoundError(f"Phase 9 variance model not found: {_VARIANCE}")
    with open(_BASELINE, "rb") as f:
        baseline = pickle.load(f)
    with open(_VARIANCE, "rb") as f:
        variance = pickle.load(f)
    return baseline, variance


def _to_float(v, default: float) -> float:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _build_feature_row(
    home: str,
    away: str,
    home_sp: dict,
    away_sp: dict,
    home_off: dict,
    away_off: dict,
    weather: dict,
    umpire: dict,
    home_bp: dict,
    away_bp: dict,
    game: dict,
) -> pd.Series:
    """
    Construct the 25-feature row that the Phase 9 pipeline expects.
    All values are pulled from the same live dicts that project_game() receives,
    so this runs on identical data — no extra API calls.
    """
    from config import STADIUMS, LEAGUE_AVG_K_RATE, LEAGUE_AVG_BB_RATE

    stadium = STADIUMS.get(home, {})

    # ── Starter features ──────────────────────────────────────────────────────
    home_xfip   = _to_float(home_sp.get("xfip"),           4.10)
    away_xfip   = _to_float(away_sp.get("xfip"),           4.10)
    home_k_pct  = _to_float(home_sp.get("k_pct"),  LEAGUE_AVG_K_RATE)
    away_k_pct  = _to_float(away_sp.get("k_pct"),  LEAGUE_AVG_K_RATE)
    home_bb_pct = _to_float(home_sp.get("bb_pct"), LEAGUE_AVG_BB_RATE)
    away_bb_pct = _to_float(away_sp.get("bb_pct"), LEAGUE_AVG_BB_RATE)
    home_avg_ip = _to_float(home_sp.get("avg_ip_per_start"), _LEAGUE_AVG_IP)
    away_avg_ip = _to_float(away_sp.get("avg_ip_per_start"), _LEAGUE_AVG_IP)
    home_fb_pct = _to_float(home_sp.get("fb_pct"), _LEAGUE_FB_PCT)
    away_fb_pct = _to_float(away_sp.get("fb_pct"), _LEAGUE_FB_PCT)

    # ── Offense ───────────────────────────────────────────────────────────────
    home_wrc = _to_float(home_off.get("wrc_plus"), 100.0)
    away_wrc = _to_float(away_off.get("wrc_plus"), 100.0)

    # ── Park ──────────────────────────────────────────────────────────────────
    pf_runs = float(stadium.get("park_factor", 100))
    pf_hr   = float(stadium.get("hr_factor",   100))

    # ── Weather ───────────────────────────────────────────────────────────────
    temperature  = _to_float(weather.get("temperature"), 72.0)
    wind_speed   = _to_float(weather.get("wind_speed"),   0.0)
    wind_dir_raw = str(weather.get("wind_direction", "")).lower()
    dome         = bool(stadium.get("dome") or
                        any(w in str(game.get("venue_name", "")).lower()
                            for w in ("tropicana", "rogers centre", "chase field",
                                      "t-mobile", "globe life", "minute maid",
                                      "american family", "toyota dome")))

    # ── wind_factor_effective: signed scalar used by Phase 9 model ────────────
    # Formula from sim/phase2_build_features.py _wind_factor():
    #   -cos(wind_dir_deg - cf_bearing_deg) × wind_speed
    # Live weather.py returns wind_direction as a text string (e.g. "Out to CF"),
    # not a compass bearing, so we approximate from the text direction.
    # Phase 9 model was trained on numeric wind_factor_effective from game_table
    # which stores wind_direction as compass degrees. We reconstruct via the
    # stadium's cf_bearing and the numeric wind degree if available in weather,
    # otherwise fall back to a signed speed approximation from text direction.
    cf_bearing = float(stadium.get("cf_bearing", 0))
    wind_dir_deg = weather.get("wind_direction_deg")   # set by weather.py if available
    if dome or wind_speed <= 0:
        wind_factor_effective = 0.0
        wind_out_flag = 0.0
    elif wind_dir_deg is not None:
        angle_rad = math.radians(float(wind_dir_deg) - cf_bearing)
        wind_factor_effective = round(-math.cos(angle_rad) * wind_speed, 2)
        wind_out_flag = 1.0 if wind_factor_effective > 3.0 else 0.0
    else:
        # Text-direction fallback: "out" words → positive, "in" words → negative
        out_words = ("out", "blowing out", "l to r", "r to l")
        in_words  = ("in", "blowing in")
        if any(w in wind_dir_raw for w in out_words):
            wind_factor_effective = wind_speed * 0.7   # ≈ 45° out angle
            wind_out_flag = 1.0 if wind_speed > 4 else 0.0
        elif any(w in wind_dir_raw for w in in_words):
            wind_factor_effective = -wind_speed * 0.7
            wind_out_flag = 0.0
        else:
            wind_factor_effective = 0.0  # crosswind
            wind_out_flag = 0.0

    # ── Flyball × wind interaction ────────────────────────────────────────────
    # Mirrors Phase 6 add_flyball_wind_interaction() logic
    # Phase 6 uses wind_factor_effective as the base; scale by fb_pct vs league avg
    avg_fb_pct = (home_fb_pct + away_fb_pct) / 2
    flyball_wind = (wind_factor_effective / max(wind_speed, 1.0) if wind_speed > 0 else 0.0) * (
        avg_fb_pct / _LEAGUE_FB_PCT
    ) * wind_speed if not dome else 0.0

    # ── Umpire ────────────────────────────────────────────────────────────────
    # umpire_over_rate and runs_factor are identical (same UMPIRE_RATINGS source)
    ump_rate = _to_float(umpire.get("runs_factor"), 1.0)

    # ── Rest / doubleheader ───────────────────────────────────────────────────
    home_rest = float(game.get("home_rest_days") or 1)
    away_rest = float(game.get("away_rest_days") or 1)
    dh_flag   = float(bool(game.get("doubleheader_flag")))

    # ── Bullpen features ──────────────────────────────────────────────────────
    home_bp_xfip     = _to_float(home_bp.get("team_xfip"),  4.10)
    away_bp_xfip     = _to_float(away_bp.get("team_xfip"),  4.10)
    home_bp_proj_inn = max(0.0, 9.0 - home_avg_ip)
    away_bp_proj_inn = max(0.0, 9.0 - away_avg_ip)

    home_bp_delta    = home_bp_xfip - home_xfip
    away_bp_delta    = away_bp_xfip - away_xfip
    home_bp_exp      = home_bp_delta * home_bp_proj_inn
    away_bp_exp      = away_bp_delta * away_bp_proj_inn

    # high_leverage_avail: 0 red arms in tier1 → closer available
    home_hl = 1.0 if _to_float(home_bp.get("tier1_red_arms"), 0) == 0 else 0.0
    away_hl = 1.0 if _to_float(away_bp.get("tier1_red_arms"), 0) == 0 else 0.0

    # ── Variance features (only for variance model) ───────────────────────────
    exp_bp_inn = home_bp_proj_inn + away_bp_proj_inn
    dome_flag  = 1.0 if dome else 0.0

    return pd.Series({
        # ── mean model features (25) ──────────────────────────────────────────
        "home_sp_xfip":             home_xfip,
        "away_sp_xfip":             away_xfip,
        "home_sp_k_pct":            home_k_pct,
        "away_sp_k_pct":            away_k_pct,
        "home_sp_bb_pct":           home_bb_pct,
        "away_sp_bb_pct":           away_bb_pct,
        "home_sp_avg_ip":           home_avg_ip,
        "away_sp_avg_ip":           away_avg_ip,
        "home_wrc_plus":            home_wrc,
        "away_wrc_plus":            away_wrc,
        "park_factor_runs":         pf_runs,
        "park_factor_hr":           pf_hr,
        "temperature":              temperature,
        "wind_factor_effective":    wind_factor_effective,
        "umpire_over_rate":         ump_rate,
        "home_rest_days":           home_rest,
        "away_rest_days":           away_rest,
        "doubleheader_flag":        dh_flag,
        "flyball_wind_interaction": flyball_wind,
        "home_high_leverage_avail": home_hl,
        "away_high_leverage_avail": away_hl,
        "home_bullpen_delta":       home_bp_delta,
        "away_bullpen_delta":       away_bp_delta,
        "home_bp_delta_exposure":   home_bp_exp,
        "away_bp_delta_exposure":   away_bp_exp,
        # ── variance model features (12) ──────────────────────────────────────
        "wind_speed":               wind_speed,   # variance model uses raw mph
        "wind_out_flag":            wind_out_flag,
        "home_sp_fb_pct":           home_fb_pct,
        "away_sp_fb_pct":           away_fb_pct,
        "expected_bullpen_innings": exp_bp_inn,
        "dome_flag":                dome_flag,
    })


def sim_project_game(
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
    game: dict,
    market_line: float | None = None,
) -> dict:
    """
    Phase 9 simulation projection — drop-in replacement for project_game().

    Returns a proj dict with the same required keys as project_game() plus
    sim-specific extras. Downstream code (serialize_results, classify_game,
    push_results, dashboard) is fully compatible.

    Required keys (same as project_game):
        proj_total_full    float
        proj_total_f5      float
        lean               "OVER" | "UNDER" | "NEUTRAL"
        confidence         "HIGH" | "MEDIUM" | "LOW"
        confidence_score   float  [0, 1]
        factors            dict   (matching expected factor keys)

    Sim-only extras (additive, ignored by older code paths):
        sim_sigma          float
        sim_p_over         float
        sim_ci_lo          float
        sim_ci_hi          float
        model_mode         "simulation"
    """
    baseline, variance_mdl = _load_models()

    row = _build_feature_row(
        home_team, away_team,
        home_sp_metrics, away_sp_metrics,
        home_offense, away_offense,
        weather, umpire, home_bullpen, away_bullpen,
        game,
    )

    # ── Mean prediction ───────────────────────────────────────────────────────
    # Pass .to_numpy() so sklearn doesn't warn about feature-name mismatch
    # (the scaler was fitted on arrays; column names add no information here)
    mean_features = baseline["features"]
    X_mean = pd.DataFrame([row[mean_features]]).to_numpy()
    proj_full = float(baseline["pipeline"].predict(X_mean)[0])
    proj_full = max(_PROJ_MIN, min(proj_full, _PROJ_MAX))

    # ── Variance prediction ───────────────────────────────────────────────────
    var_features = variance_mdl["features"]
    X_var = pd.DataFrame([row[var_features]]).to_numpy()
    pred_abs_resid = float(variance_mdl["pipeline"].predict(X_var)[0])
    sigma = max(pred_abs_resid / _SQRT_2_PI, variance_mdl["sigma_floor"])

    # ── Umpire variance adjustment (simulation only) ──────────────────────────
    # Apply sigma_mult from umpires.py when umpire is known and in the table.
    # Unknown umpires (sigma_mult absent or 1.00) → no change.
    ump_sigma_mult = _to_float(umpire.get("sigma_mult"), 1.0)
    if ump_sigma_mult != 1.0:
        sigma = sigma * ump_sigma_mult

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    rng   = np.random.default_rng(_SEED)
    draws = rng.normal(proj_full, sigma, _N_SIMS)
    line_ref = market_line if market_line is not None else proj_full
    p_over  = float((draws > line_ref).mean())
    ci_lo   = float(np.percentile(draws, 10.0))
    ci_hi   = float(np.percentile(draws, 90.0))

    # ── Lean / confidence ─────────────────────────────────────────────────────
    NEUTRAL_TOTAL = 9.0
    deviation = proj_full - NEUTRAL_TOTAL

    if abs(deviation) < 0.3:
        lean = "NEUTRAL"
    elif deviation > 0:
        lean = "OVER"
    else:
        lean = "UNDER"

    abs_dev = abs(deviation)
    if abs_dev >= _CONF_HIGH:
        conf  = "HIGH"
        score = min(abs_dev / 3.0, 1.0)
    elif abs_dev >= _CONF_MEDIUM:
        conf  = "MEDIUM"
        score = abs_dev / 3.0
    else:
        conf  = "LOW"
        score = abs_dev / 3.0

    score = round(score, 3)

    # ── Factors dict — same keys as project_game() for downstream compat ──────
    from config import STADIUMS
    stadium = STADIUMS.get(home_team, {})
    factors = {
        # keys read by serialize_results / dashboard
        "sp_home_xfip":        row["home_sp_xfip"],
        "sp_away_xfip":        row["away_sp_xfip"],
        "home_wrc_plus":       row["home_wrc_plus"],
        "away_wrc_plus":       row["away_wrc_plus"],
        "park_factor":         row["park_factor_runs"] / 100.0,
        "wind_factor":         _to_float(weather.get("wind_factor"), 1.0),
        "temp_factor":         _to_float(weather.get("temp_factor"), 1.0),
        "wind_speed_mph":      row["wind_speed"],
        "wind_direction":      weather.get("wind_direction", ""),
        "wind_desc":           weather.get("wind_desc", ""),
        "temperature_f":       row["temperature"],
        "umpire_name":         umpire.get("name", "Unknown"),
        "umpire_runs_factor":  row["umpire_over_rate"],
        "umpire_sigma_mult":   round(ump_sigma_mult, 4),
        "home_bp_fatigue":     0.0,   # rules-model concept; set to neutral
        "away_bp_fatigue":     0.0,
        "weather_desc":        weather.get("weather_desc", ""),
        # sim-specific (available to new dashboard code)
        "sim_sigma":           round(sigma, 3),
        "sim_p_over":          round(p_over, 3),
        "sim_ci_lo":           round(ci_lo, 2),
        "sim_ci_hi":           round(ci_hi, 2),
    }

    return {
        "proj_total_full":  round(proj_full, 2),
        "proj_total_f5":    round(proj_full * _F5_FRACTION, 2),
        "lean":             lean,
        "confidence":       conf,
        "confidence_score": score,
        "factors":          factors,
        # sim extras at top level for easy access
        "sim_sigma":        round(sigma, 3),
        "sim_p_over":       round(p_over, 3),
        "sim_ci_lo":        round(ci_lo, 2),
        "sim_ci_hi":        round(ci_hi, 2),
        "model_mode":       "simulation",
    }
