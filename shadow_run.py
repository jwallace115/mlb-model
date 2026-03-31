"""
shadow_run.py — Side-by-side comparison: rules model vs simulation (Phase 9) model.

Usage:
    # Live mode (today's games, both models run in parallel):
    python3 shadow_run.py

    # Historical demo mode (uses stored feature_table + game data):
    python3 shadow_run.py --demo --game-pk 777254

    # Historical demo, all games on a date:
    python3 shadow_run.py --demo --date 2025-07-04

    # Skip Odds API (saves quota):
    python3 shadow_run.py --no-odds

In live mode, both models receive the same live-fetched data.
In demo mode, the sim model uses feature_table.parquet; the rules model reconstructs
project_game() inputs from stored game features (no API calls needed).
"""

import argparse
import logging
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── project root on path ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
SIM  = ROOT / "sim"
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger("shadow")

# ── model paths ───────────────────────────────────────────────────────────────
BASELINE_PKL = SIM / "data" / "phase9_baseline_model.pkl"
VARIANCE_PKL = SIM / "data" / "phase9_variance_model.pkl"
M3_PKL       = ROOT / "mlb" / "model_m3" / "m3_ridge_model.pkl"  # built at first use

# ── simulation constants ───────────────────────────────────────────────────────
N_SIMS = 50_000
SEED   = 42
SQRT_2_PI = math.sqrt(2.0 / math.pi)

# ── shadow log ────────────────────────────────────────────────────────────────
SHADOW_LOG = SIM / "data" / "shadow_log.parquet"

# ── confidence thresholds (sim model) ─────────────────────────────────────────
STRONG_EDGE = 1.0    # |proj − line| ≥ this → STRONG tier
BET_EDGE    = 0.5    # |proj − line| ≥ this → BET tier
WATCHLIST   = 0.25   # ≥ this → WATCHLIST

# ── feature columns needed from feature_table (25-feature Phase 9 model) ──────
MEAN_FEATURES = [
    "home_sp_xfip", "away_sp_xfip",
    "home_sp_k_pct", "away_sp_k_pct",
    "home_sp_bb_pct", "away_sp_bb_pct",
    "home_sp_avg_ip", "away_sp_avg_ip",
    "home_wrc_plus", "away_wrc_plus",
    "park_factor_runs", "park_factor_hr",
    "temperature", "wind_factor_effective",
    "umpire_over_rate",
    "home_rest_days", "away_rest_days",
    "doubleheader_flag",
    "flyball_wind_interaction",
    "home_high_leverage_avail", "away_high_leverage_avail",
    "home_bullpen_delta", "away_bullpen_delta",
    "home_bp_delta_exposure", "away_bp_delta_exposure",
]

VARIANCE_FEATURES = [
    "wind_speed", "wind_out_flag",
    "home_sp_fb_pct", "away_sp_fb_pct",
    "home_bp_delta_exposure", "away_bp_delta_exposure",
    "temperature", "park_factor_hr",
    "home_sp_bb_pct", "away_sp_bb_pct",
    "expected_bullpen_innings", "dome_flag",
]


# =============================================================================
# Model loading
# =============================================================================

def load_models():
    """Load Phase 9 baseline + variance models from disk."""
    with open(BASELINE_PKL, "rb") as f:
        baseline = pickle.load(f)
    with open(VARIANCE_PKL, "rb") as f:
        variance = pickle.load(f)
    return baseline, variance


# ── M3 lineup-adjusted model ────────────────────────────────────────────────
# M3 adds 8 lineup features on top of the 25 Phase 9 features.
# The trained Ridge is cached to mlb/model_m3/m3_ridge_model.pkl
# on first use so subsequent shadow runs load instantly.

M3_EXTRA_FEATURES = [
    "home_lineup_woba", "away_lineup_woba",
    "home_lineup_iso", "away_lineup_iso",
    "home_lineup_k_pct", "away_lineup_k_pct",
    "home_lineup_delta", "away_lineup_delta",
]

_m3_model_cache = None

def _load_m3_model():
    """Load (or lazily build) the M3 Ridge model."""
    global _m3_model_cache
    if _m3_model_cache is not None:
        return _m3_model_cache
    if M3_PKL.exists():
        with open(M3_PKL, "rb") as f:
            _m3_model_cache = pickle.load(f)
        return _m3_model_cache
    # Build from M3 feature data if available
    m3_feat_file = ROOT / "mlb" / "model_m3" / "m3_features.parquet"
    ft_file = SIM / "data" / "feature_table.parquet"
    if not m3_feat_file.exists() or not ft_file.exists():
        return None
    log.info("Building M3 model from cached features (one-time)...")
    from sklearn.linear_model import RidgeCV
    from sklearn.pipeline import Pipeline as SKPipe
    from sklearn.preprocessing import StandardScaler as SKScaler
    ft = pd.read_parquet(ft_file)
    m3f = pd.read_parquet(m3_feat_file)
    m3_cols = [c for c in m3f.columns if "lineup" in c or c == "game_pk"]
    ft = ft.merge(m3f[m3_cols].drop_duplicates(subset="game_pk"), on="game_pk", how="left")
    for c in ft.columns:
        if "lineup_woba" in c: ft[c] = ft[c].fillna(0.310)
        elif "lineup_iso" in c: ft[c] = ft[c].fillna(0.150)
        elif "lineup_k_pct" in c: ft[c] = ft[c].fillna(0.224)
        elif "lineup_delta" in c: ft[c] = ft[c].fillna(0.0)
    # Add bullpen features
    bp_file = SIM / "data" / "bullpen_features.parquet"
    if bp_file.exists() and "home_high_leverage_avail" not in ft.columns:
        bp = pd.read_parquet(bp_file)
        for side, tc in [("home","home_team"),("away","away_team")]:
            bp_s = bp.rename(columns={"high_leverage_avail":f"{side}_high_leverage_avail",
                                       "bullpen_delta":f"{side}_bullpen_delta",
                                       "bp_delta_exposure":f"{side}_bp_delta_exposure"})
            avail = [c for c in [f"{side}_high_leverage_avail",f"{side}_bullpen_delta",
                                  f"{side}_bp_delta_exposure"] if c in bp_s.columns]
            if avail:
                ft = ft.merge(bp_s[["game_pk","team"]+avail].drop_duplicates(),
                               left_on=["game_pk",tc],right_on=["game_pk","team"],
                               how="left",suffixes=("","_bp"))
                ft.drop(columns=["team"]+[c for c in ft.columns if c.endswith("_bp")],
                         errors="ignore",inplace=True)
    if "flyball_wind_interaction" not in ft.columns:
        ft["flyball_wind_interaction"] = ft.get("wind_factor_effective",0)
    for c in ["home_high_leverage_avail","away_high_leverage_avail"]:
        if c not in ft.columns: ft[c] = 1.0
    for c in ["home_bullpen_delta","away_bullpen_delta",
               "home_bp_delta_exposure","away_bp_delta_exposure"]:
        if c not in ft.columns: ft[c] = 0.0
    all_feats = MEAN_FEATURES + M3_EXTRA_FEATURES
    all_feats = [f for f in all_feats if f in ft.columns]
    train = ft[ft["season"].isin([2022,2023])]
    X = train[all_feats].fillna(train[all_feats].median())
    y = train["actual_total"]
    pipe = SKPipe([("scaler",SKScaler()),
                    ("ridge",RidgeCV(alphas=[1,5,10,25,50,100,200,500],cv=5))])
    pipe.fit(X, y)
    m3_obj = {"pipeline": pipe, "features": all_feats}
    M3_PKL.parent.mkdir(parents=True, exist_ok=True)
    with open(M3_PKL, "wb") as f:
        pickle.dump(m3_obj, f)
    log.info(f"M3 model saved → {M3_PKL}")
    _m3_model_cache = m3_obj
    return _m3_model_cache


def m3_predict(feature_row: dict) -> float | None:
    """Predict total runs using M3 lineup-adjusted model."""
    mdl = _load_m3_model()
    if mdl is None:
        return None
    feats = mdl["features"]
    row_vals = {f: feature_row.get(f, np.nan) for f in feats}
    X = pd.DataFrame([row_vals])
    # Fill NaN with defaults
    for c in X.columns:
        if "lineup_woba" in c: X[c] = X[c].fillna(0.310)
        elif "lineup_iso" in c: X[c] = X[c].fillna(0.150)
        elif "lineup_k_pct" in c: X[c] = X[c].fillna(0.224)
        elif "lineup_delta" in c: X[c] = X[c].fillna(0.0)
        elif "wrc_plus" in c: X[c] = X[c].fillna(100)
        else: X[c] = X[c].fillna(0)
    proj = float(mdl["pipeline"].predict(X)[0])
    return round(max(4.0, min(proj, 22.0)), 3)


def _compute_m5_fields(m3_proj, sim_proj, line):
    """Compute M5 tracking fields from M3 and sim projections."""
    result = {}

    if m3_proj is not None and line is not None and not math.isnan(line):
        m3_edge = m3_proj - line
        result["m3_proj"] = m3_proj
        result["m3_edge"] = round(m3_edge, 3)
        result["m3_signal_direction"] = "OVER" if m3_edge > 0 else "UNDER"

        abs_edge = abs(m3_edge)
        if abs_edge >= 2.0:
            result["m3_edge_bucket"] = "2.0+"
        elif abs_edge >= 1.5:
            result["m3_edge_bucket"] = "1.5-2.0"
        elif abs_edge >= 1.0:
            result["m3_edge_bucket"] = "1.0-1.5"
        else:
            result["m3_edge_bucket"] = "<1.0"
    else:
        result["m3_proj"] = m3_proj if m3_proj is not None else float("nan")
        result["m3_edge"] = float("nan")
        result["m3_signal_direction"] = ""
        result["m3_edge_bucket"] = ""

    # Disagreement: M3 vs existing (sim) model
    if m3_proj is not None and not math.isnan(sim_proj):
        disagree_mag = abs(m3_proj - sim_proj)
        result["disagree_magnitude"] = round(disagree_mag, 3)

        if disagree_mag < 0.5:
            result["disagree_bucket"] = "0.0-0.5"
        elif disagree_mag < 1.0:
            result["disagree_bucket"] = "0.5-1.0"
        elif disagree_mag < 1.5:
            result["disagree_bucket"] = "1.0-1.5"
        else:
            result["disagree_bucket"] = "1.5+"

        # Direction relation
        if line is not None and not math.isnan(line):
            m3_side = "over" if m3_proj > line else "under"
            sim_side = "over" if sim_proj > line else "under"
            result["models_direction_relation"] = "SAME" if m3_side == sim_side else "OPPOSITE"
        else:
            result["models_direction_relation"] = ""
    else:
        result["disagree_magnitude"] = float("nan")
        result["disagree_bucket"] = ""
        result["models_direction_relation"] = ""

    return result


# =============================================================================
# Simulation-model prediction
# =============================================================================

def sim_predict(row: pd.Series, baseline: dict, variance: dict) -> dict:
    """
    Run Phase 9 sim model on a single game row (from feature_table).
    Returns dict with proj_total, sigma, p_over, p_under, ci_lo, ci_hi.
    """
    pipe_mean = baseline["pipeline"]
    pipe_var  = variance["pipeline"]

    # --- mean prediction ---
    X_mean = pd.DataFrame([row[MEAN_FEATURES]]).to_numpy()
    proj = float(pipe_mean.predict(X_mean)[0])

    # --- variance prediction ---
    X_var = pd.DataFrame([row[VARIANCE_FEATURES]]).to_numpy()
    pred_abs_resid = float(pipe_var.predict(X_var)[0])
    sigma = max(pred_abs_resid / SQRT_2_PI, variance["sigma_floor"])

    # --- Monte Carlo ---
    rng = np.random.default_rng(SEED)
    draws = rng.normal(proj, sigma, N_SIMS)
    p_over  = float((draws > row.get("line", proj)).mean())
    p_under = 1.0 - p_over
    ci_lo   = float(np.percentile(draws, 10.0))
    ci_hi   = float(np.percentile(draws, 90.0))

    return {
        "proj":    round(proj, 2),
        "sigma":   round(sigma, 3),
        "p_over":  round(p_over, 3),
        "p_under": round(p_under, 3),
        "ci_lo":   round(ci_lo, 2),
        "ci_hi":   round(ci_hi, 2),
    }


# =============================================================================
# Rules-model reconstruction (demo / historical mode)
# =============================================================================

def _safe(val, default):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    return val


def rules_predict_from_row(row: pd.Series) -> dict:
    """
    Reconstruct project_game() inputs from feature_table row and run rules model.
    This is used in demo mode only — live mode calls project_game() directly via
    the standard data pipeline.
    """
    from modules.projections import project_game

    home_sp = {
        "xfip":           _safe(row.get("home_sp_xfip"), 4.10),
        "siera":          _safe(row.get("home_sp_xfip"), 4.10),   # proxy: use xfip if siera absent
        "avg_ip_per_start": _safe(row.get("home_sp_avg_ip"), 5.5),
        "fb_pct":         _safe(row.get("home_sp_fb_pct"), 0.35),
        "gb_pct":         _safe(row.get("home_sp_gb_pct"), 0.45),
        "k_pct":          _safe(row.get("home_sp_k_pct"), 0.224),
        "bb_pct":         _safe(row.get("home_sp_bb_pct"), 0.085),
    }
    away_sp = {
        "xfip":           _safe(row.get("away_sp_xfip"), 4.10),
        "siera":          _safe(row.get("away_sp_xfip"), 4.10),
        "avg_ip_per_start": _safe(row.get("away_sp_avg_ip"), 5.5),
        "fb_pct":         _safe(row.get("away_sp_fb_pct"), 0.35),
        "gb_pct":         _safe(row.get("away_sp_gb_pct"), 0.45),
        "k_pct":          _safe(row.get("away_sp_k_pct"), 0.224),
        "bb_pct":         _safe(row.get("away_sp_bb_pct"), 0.085),
    }

    home_off = {"wrc_plus": _safe(row.get("home_wrc_plus"), 100)}
    away_off = {"wrc_plus": _safe(row.get("away_wrc_plus"), 100)}

    # Reconstruct weather dict from stored game conditions
    wind_spd  = _safe(row.get("wind_speed"), 0.0)
    temp      = _safe(row.get("temperature"), 72.0)
    roof      = str(row.get("roof_status", "")).lower()
    dome      = any(w in roof for w in ("closed", "retractable", "dome", "indoor"))

    from config import STADIUMS
    pf_runs = STADIUMS.get(row.get("home_team", ""), {}).get("park_factor", 100) / 100.0

    # Simplified wind factor (mirrors weather.py logic approximately)
    wind_dir = str(row.get("wind_direction", "")).lower()
    if dome or wind_spd == 0:
        wind_factor = 1.0
    else:
        out_words = ("out", "blowing out", "l to r", "r to l", "center")
        in_words  = ("in", "blowing in")
        if any(w in wind_dir for w in out_words):
            wind_factor = 1.0 + 0.004 * wind_spd
        elif any(w in wind_dir for w in in_words):
            wind_factor = 1.0 - 0.003 * wind_spd
        else:
            wind_factor = 1.0
        wind_factor = max(0.85, min(wind_factor, 1.15))

    temp_f = 1.0 if dome else max(0.90, 1.0 + (temp - 72) * 0.003)

    weather = {
        "wind_factor":    wind_factor,
        "temp_factor":    temp_f,
        "wind_speed":     wind_spd,
        "temperature":    temp,
        "dome":           dome,
    }

    # Umpire — feature_table stores umpire_over_rate; rules model uses runs_factor
    # They're equivalent (both ≈ 1.0 neutral, > 1.0 over-friendly)
    ump_rate = _safe(row.get("umpire_over_rate"), 1.0)
    umpire   = {"runs_factor": ump_rate, "name": row.get("umpire_name", "Unknown")}

    # Bullpen — rules model uses fatigue_multiplier; we don't have raw usage in feature_table.
    # Use neutral (1.0) — close enough for comparison purposes.
    # Live mode will call calculate_bullpen_fatigue() directly.
    home_bullpen = {"fatigue_multiplier": 1.0, "tier1_red_arms": 0, "collapse_triggered": False}
    away_bullpen = {"fatigue_multiplier": 1.0, "tier1_red_arms": 0, "collapse_triggered": False}

    result = project_game(
        home_team=row.get("home_team", ""),
        away_team=row.get("away_team", ""),
        home_sp_metrics=home_sp,
        away_sp_metrics=away_sp,
        home_offense=home_off,
        away_offense=away_off,
        weather=weather,
        umpire=umpire,
        home_bullpen=home_bullpen,
        away_bullpen=away_bullpen,
    )
    return result


# =============================================================================
# Tier / edge classification (sim model)
# =============================================================================

def classify_sim(proj: float, sigma: float, p_over: float, line: float | None) -> tuple[str, float]:
    """Return (tier, edge) for the sim model output."""
    if line is None:
        return ("NO LINE", 0.0)
    edge = proj - line
    abs_edge = abs(edge)
    lean = "OVER" if edge > 0 else "UNDER"
    if abs_edge >= STRONG_EDGE:
        tier = f"STRONG {lean}"
    elif abs_edge >= BET_EDGE:
        tier = f"BET {lean}"
    elif abs_edge >= WATCHLIST:
        tier = f"WATCHLIST {lean}"
    else:
        tier = "NEUTRAL"
    return tier, round(edge, 2)


def classify_rules(proj_total: float, line: float | None) -> tuple[str, float]:
    """Return (tier, edge) for the rules model output using same thresholds."""
    if line is None:
        return ("NO LINE", 0.0)
    edge = proj_total - line
    abs_edge = abs(edge)
    lean = "OVER" if edge > 0 else "UNDER"
    if abs_edge >= STRONG_EDGE:
        tier = f"STRONG {lean}"
    elif abs_edge >= BET_EDGE:
        tier = f"BET {lean}"
    elif abs_edge >= WATCHLIST:
        tier = f"WATCHLIST {lean}"
    else:
        tier = "NEUTRAL"
    return tier, round(edge, 2)


# =============================================================================
# Output formatting
# =============================================================================

BAR = "=" * 72

def _star(tier: str) -> str:
    t = tier.lower()
    if "strong" in t:  return "⭐⭐⭐"
    if "bet"    in t:  return "⭐⭐"
    if "watch"  in t:  return "⭐"
    return "   "


def print_game_card(row: pd.Series, rules_result: dict, sim_result: dict,
                    line: float | None, actual: float | None):
    home = row.get("home_team", "???")
    away = row.get("away_team", "???")
    date = str(row.get("date", ""))[:10]
    temp = row.get("temperature", float("nan"))
    wind = row.get("wind_speed", 0)
    roof = str(row.get("roof_status", "")).lower()
    dome = any(w in roof for w in ("closed", "retractable", "dome", "indoor"))

    home_sp = row.get("home_sp_name", "TBD")
    away_sp = row.get("away_sp_name", "TBD")

    rules_proj = rules_result.get("proj_total_full", float("nan"))
    sim_proj   = sim_result["proj"]
    sim_sigma  = sim_result["sigma"]
    sim_po     = sim_result["p_over"]
    sim_pu     = sim_result["p_under"]
    ci_lo      = sim_result["ci_lo"]
    ci_hi      = sim_result["ci_hi"]

    rules_tier, rules_edge = classify_rules(rules_proj, line)
    sim_tier,   sim_edge   = classify_sim(sim_proj, sim_sigma, sim_po, line)

    agree = "✓ AGREE" if (
        ("over" in rules_tier.lower()) == ("over" in sim_tier.lower())
        and "neutral" not in rules_tier.lower()
        and "neutral" not in sim_tier.lower()
        and "no line" not in rules_tier.lower()
    ) else "✗ SPLIT"
    if "neutral" in rules_tier.lower() and "neutral" in sim_tier.lower():
        agree = "— BOTH NEUTRAL"

    print()
    print(BAR)
    weather_str = f"dome" if dome else f"{temp:.0f}°F · wind {wind:.0f}mph"
    print(f"  {away} @ {home}   |   {date}   |   {weather_str}")
    print(f"  SP: {away_sp} (away) vs {home_sp} (home)")
    if line is not None:
        print(f"  Market line: {line:.1f}")
    if actual is not None:
        print(f"  Actual total: {actual:.0f}")
    print()
    print(f"  {'':30}  {'RULES':>14}   {'SIM (Phase 9)':>14}")
    print(f"  {'─'*30}  {'─'*14}   {'─'*14}")
    print(f"  {'Projected total':30}  {rules_proj:>14.2f}   {sim_proj:>14.2f}")
    print(f"  {'Sigma (uncertainty)':30}  {'4.36 (fixed)':>14}   {sim_sigma:>14.3f}")

    line_str = f"{line:.1f}" if line is not None else "---"
    print(f"  {'Closing line':30}  {line_str:>14}   {line_str:>14}")
    print(f"  {'Edge vs line':30}  {rules_edge:>+14.2f}   {sim_edge:>+14.2f}")

    print(f"  {'P(over)':30}  {'---':>14}   {sim_po:>14.3f}")
    print(f"  {'P(under)':30}  {'---':>14}   {sim_pu:>14.3f}")
    print(f"  {'80% CI':30}  {'---':>14}   {f'[{ci_lo:.1f}, {ci_hi:.1f}]':>14}")
    print()
    print(f"  {'Tier':30}  {rules_tier:>14}   {sim_tier:>14}")
    print(f"  {'Stars':30}  {_star(rules_tier):>14}   {_star(sim_tier):>14}")
    print()
    print(f"  Model agreement: {agree}")
    print(BAR)


# =============================================================================
# Shadow log — persistent A/B tracking
# =============================================================================

def _log_shadow_rows(rows: list[dict]) -> None:
    """
    Append shadow comparison rows to sim/data/shadow_log.parquet.
    Each call is idempotent by (game_id, date) — duplicate runs overwrite prior entry.

    Schema:
        game_id         int       MLB game_pk
        date            str       YYYY-MM-DD
        home_team       str
        away_team       str
        rules_proj      float     rules model projected total
        sim_proj        float     Phase 9 sim projected total
        market_line     float     closing line (NaN if unavailable)
        rules_edge      float     rules_proj − market_line
        sim_edge        float     sim_proj − market_line
        rules_tier      str       e.g. "BET OVER", "NEUTRAL"
        sim_tier        str
        agreement       bool      both models lean the same direction
        actual_total    float     filled in after games complete (NaN until then)
        rules_correct   bool      rules model correct direction vs actual (NaN until filled)
        sim_correct     bool      sim model correct direction vs actual  (NaN until filled)
    """
    if not rows:
        return

    new_df = pd.DataFrame(rows)

    if SHADOW_LOG.exists():
        existing = pd.read_parquet(SHADOW_LOG)
        # Drop rows that will be overwritten (same game_id + date)
        key = existing.set_index(["game_id", "date"]).index
        new_key = new_df.set_index(["game_id", "date"]).index
        existing = existing[~existing.set_index(["game_id", "date"]).index.isin(new_key)]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.sort_values(["date", "game_id"]).reset_index(drop=True)
    combined.to_parquet(SHADOW_LOG, index=False)
    log.info(f"Shadow log updated: {len(combined)} total rows → {SHADOW_LOG}")


def _build_log_row(game_id: int, date_str: str, home: str, away: str,
                   rules_result: dict, sim_result: dict, line: float | None,
                   game_row: pd.Series | None = None) -> dict:
    rules_proj = rules_result.get("proj_total_full", float("nan"))
    sim_proj   = sim_result["proj"]
    rules_edge = round(rules_proj - line, 3) if line is not None else float("nan")
    sim_edge   = round(sim_proj   - line, 3) if line is not None else float("nan")
    rules_tier, _ = classify_rules(rules_proj, line)
    sim_tier,   _ = classify_sim(sim_proj, sim_result["sigma"], sim_result["p_over"], line)
    agreement = (
        "over"  in rules_tier.lower() and "over"  in sim_tier.lower() or
        "under" in rules_tier.lower() and "under" in sim_tier.lower()
    ) and "neutral" not in rules_tier.lower() and "neutral" not in sim_tier.lower()

    row_dict = {
        "game_id":       int(game_id),
        "date":          date_str,
        "home_team":     home,
        "away_team":     away,
        "rules_proj":    round(float(rules_proj), 3) if not math.isnan(rules_proj) else float("nan"),
        "sim_proj":      round(float(sim_proj), 3),
        "market_line":   float(line) if line is not None else float("nan"),
        "rules_edge":    rules_edge,
        "sim_edge":      sim_edge,
        "rules_tier":    rules_tier,
        "sim_tier":      sim_tier,
        "agreement":     agreement,
        "actual_total":  float("nan"),
        "rules_correct": float("nan"),
        "sim_correct":   float("nan"),
    }

    # ── M3 projection + M5 tracking fields ──────────────────────────────────
    live_dict = game_row.to_dict() if game_row is not None else {}
    m3_proj_val = m3_predict(live_dict)
    m5_fields = _compute_m5_fields(m3_proj_val, sim_proj, line)
    row_dict.update(m5_fields)

    # Segment overlay (Phase 4)
    try:
        from mlb.segment_overlay import classify_game, apply_overlay
        if game_row is not None:
            game_ctx = {
                "wind_speed": game_row.get("wind_speed"),
                "umpire_name": game_row.get("umpire_name"),
                "temperature": game_row.get("temperature"),
                "close_total": line,
                "decision_line": line,
            }
            seg = classify_game(game_ctx)
            # Determine bet side from sim_tier
            bet_side = "over" if "over" in sim_tier.lower() else (
                "under" if "under" in sim_tier.lower() else "")
            final_tier, applied = apply_overlay(sim_tier, bet_side, seg["overlay_flag"])
            row_dict["overlay_applied"] = applied
            row_dict["overlay_segment_A"] = seg["segment_A_flag"]
            row_dict["overlay_segment_B"] = seg["segment_B_flag"]
            row_dict["original_tier"] = sim_tier
            row_dict["final_tier"] = final_tier
            row_dict["overlay_reason"] = seg["overlay_reason"]
        else:
            row_dict["overlay_applied"] = False
            row_dict["overlay_segment_A"] = False
            row_dict["overlay_segment_B"] = False
            row_dict["original_tier"] = sim_tier
            row_dict["final_tier"] = sim_tier
            row_dict["overlay_reason"] = "none"
    except ImportError:
        row_dict["overlay_applied"] = False
        row_dict["overlay_segment_A"] = False
        row_dict["overlay_segment_B"] = False
        row_dict["original_tier"] = sim_tier
        row_dict["final_tier"] = sim_tier
        row_dict["overlay_reason"] = "none"

    return row_dict


def fill_actuals(date_str: str | None = None) -> None:
    """
    Fill actual_total + rules_correct + sim_correct in shadow_log for completed games.
    Call this after results_tracker.py runs (11:30 PM launchd job) or manually.

    Usage:
        python3 shadow_run.py --fill-actuals [--date YYYY-MM-DD]
    """
    if not SHADOW_LOG.exists():
        print("No shadow log found.")
        return

    gt = pd.read_parquet(SIM / "data" / "game_table.parquet")
    log_df = pd.read_parquet(SHADOW_LOG)

    mask = log_df["actual_total"].isna()
    if date_str:
        mask &= log_df["date"] == date_str

    for idx in log_df[mask].index:
        gid  = int(log_df.at[idx, "game_id"])
        row  = gt[gt.game_pk == gid]
        if row.empty:
            continue
        actual = float(row.iloc[0]["actual_total"])
        line   = log_df.at[idx, "market_line"]

        log_df.at[idx, "actual_total"] = actual
        if not math.isnan(line):
            actual_over = actual > line
            rules_proj  = log_df.at[idx, "rules_proj"]
            sim_proj    = log_df.at[idx, "sim_proj"]
            log_df.at[idx, "rules_correct"] = float((rules_proj > line) == actual_over)
            log_df.at[idx, "sim_correct"]   = float((sim_proj   > line) == actual_over)

    log_df.to_parquet(SHADOW_LOG, index=False)
    filled = int(mask.sum())
    print(f"Filled actuals for {filled} game(s).")

    # Print running summary
    done = log_df.dropna(subset=["actual_total", "market_line"])
    if not done.empty:
        print(f"\n  Shadow log summary — {len(done)} games with results:")
        print(f"  Rules correct: {done['rules_correct'].mean():.1%}  "
              f"({'N/A' if done['rules_correct'].isna().all() else done['rules_correct'].sum():.0f}/{len(done)})")
        print(f"  Sim   correct: {done['sim_correct'].mean():.1%}  "
              f"({'N/A' if done['sim_correct'].isna().all() else done['sim_correct'].sum():.0f}/{len(done)})")
        agree_rows = done[done["agreement"] == True]
        if not agree_rows.empty:
            print(f"  Agreement games ({len(agree_rows)}): "
                  f"rules {agree_rows['rules_correct'].mean():.1%}  "
                  f"sim {agree_rows['sim_correct'].mean():.1%}")


# =============================================================================
# Demo mode — historical feature_table lookup
# =============================================================================

def run_demo(game_pk: int | None = None, date: str | None = None,
             no_odds: bool = False):
    """Run shadow comparison on a historical game using stored features."""
    print(f"\n{'━'*72}")
    print("  SHADOW RUN — DEMO MODE (historical feature_table)")
    print(f"{'━'*72}")

    # Load stored data — use load_and_merge() so derived bullpen features are present
    sys.path.insert(0, str(SIM.parent))
    from sim.phase8_step3_retrain import load_and_merge
    ft = load_and_merge()
    ms = pd.read_parquet(SIM / "data" / "market_snapshots.parquet")

    # Filter market to DraftKings or FanDuel, prefer close_total
    ms_dk = ms[ms.book.isin(["draftkings", "fanduel"])].copy()
    ms_dk = ms_dk.sort_values("book")          # draftkings first if both present
    ms_close = (
        ms_dk
        .groupby("game_id")[["close_total"]]
        .first()
        .reset_index()
        .rename(columns={"game_id": "game_pk"})
    )

    ft = ft.merge(ms_close, on="game_pk", how="left")
    ft["line"] = ft["close_total"]

    # Derive variance features not in base table
    ft["dome_flag"] = ft["roof_status"].str.lower().str.contains(
        "closed|retractable|dome|indoor", na=False
    ).astype(float)
    ft["expected_bullpen_innings"] = ft["home_bp_proj_inn"] + ft["away_bp_proj_inn"]

    # Filter to requested game(s)
    if game_pk is not None:
        games = ft[ft.game_pk == game_pk]
        if games.empty:
            print(f"  ERROR: game_pk {game_pk} not found in feature_table.")
            return
    elif date is not None:
        games = ft[ft.date == date]
        if games.empty:
            print(f"  ERROR: no games on {date} in feature_table.")
            return
    else:
        # Default: first 2025 mid-season game with a closing line
        games = ft[
            (ft.season == 2025) &
            (ft.date >= "2025-07-01") &
            ft.close_total.notna()
        ].head(1)
        if games.empty:
            print("  ERROR: no suitable default game found.")
            return

    baseline, variance = load_models()

    log_rows = []
    for _, row in games.iterrows():
        # Sim prediction
        sim_result  = sim_predict(row, baseline, variance)

        # Rules prediction (reconstructed from stored features)
        try:
            rules_result = rules_predict_from_row(row)
        except Exception as e:
            rules_result = {"proj_total_full": float("nan")}
            log.warning(f"Rules model error: {e}")

        line   = row.get("line")
        actual = row.get("actual_total")
        line   = None if (line is None or (isinstance(line, float) and math.isnan(line))) else float(line)
        actual = None if (actual is None or (isinstance(actual, float) and math.isnan(actual))) else float(actual)

        # Monte Carlo with actual line
        if line is not None:
            rng   = np.random.default_rng(SEED)
            draws = rng.normal(sim_result["proj"], sim_result["sigma"], N_SIMS)
            sim_result["p_over"]  = round(float((draws > line).mean()), 3)
            sim_result["p_under"] = round(1.0 - sim_result["p_over"], 3)

        print_game_card(row, rules_result, sim_result, line, actual)

        # Accumulate log row
        log_rows.append(_build_log_row(
            game_id=int(row["game_pk"]),
            date_str=str(row.get("date", ""))[:10],
            home=str(row.get("home_team", "")),
            away=str(row.get("away_team", "")),
            rules_result=rules_result,
            sim_result=sim_result,
            line=line,
            game_row=row,
        ))

    _log_shadow_rows(log_rows)
    n = len(log_rows)
    print(f"\n  Logged {n} game(s) → {SHADOW_LOG.relative_to(ROOT)}")
    print("  [DEMO MODE] Features sourced from feature_table.parquet (no live API calls)")
    print("  [DEMO MODE] Rules bullpen = neutral (1.0) — live mode uses calculate_bullpen_fatigue()")
    print("  [DEMO MODE] Rules siera = proxy xFIP   — live mode has separate SIERA from FanGraphs\n")


# =============================================================================
# Live mode — real API calls (Opening Day+)
# =============================================================================

def run_live(date_str: str | None = None, no_odds: bool = False):
    """
    Run shadow comparison for today's (or specified) games using live API data.
    Both models receive the same live-fetched pitcher/offense/weather/bullpen data.
    """
    print(f"\n{'━'*72}")
    print("  SHADOW RUN — LIVE MODE")
    print(f"{'━'*72}")

    from datetime import date as dt_date
    from modules.schedule   import fetch_schedule
    from modules.pitchers   import build_pitcher_db, get_pitcher_metrics
    from modules.offense    import build_offense_db, get_team_offense
    from modules.weather    import fetch_weather
    from modules.bullpen    import build_team_bullpen_db, calculate_bullpen_fatigue
    from modules.umpires    import get_umpire_rating
    from modules.projections import project_game
    from config import STADIUMS

    target_date = date_str or str(dt_date.today())
    print(f"  Date: {target_date}\n")

    games = fetch_schedule(target_date)
    if not games:
        print("  No games scheduled.")
        return

    pitcher_db = build_pitcher_db(target_date)
    offense_db = build_offense_db(target_date)
    bullpen_db = build_team_bullpen_db(pitcher_db)

    # Load sim models
    baseline, variance_mdl = load_models()

    log_rows = []
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        home_sp_id = game.get("home_sp_id")
        away_sp_id = game.get("away_sp_id")

        home_sp_m = get_pitcher_metrics(home_sp_id, pitcher_db)
        away_sp_m = get_pitcher_metrics(away_sp_id, pitcher_db)
        home_off  = get_team_offense(home, offense_db)
        away_off  = get_team_offense(away, offense_db)
        weather   = fetch_weather(game)
        umpire    = get_umpire_rating(game.get("umpire_name"))
        home_bp   = calculate_bullpen_fatigue(home, target_date)
        away_bp   = calculate_bullpen_fatigue(away, target_date)

        # ── Rules model ──────────────────────────────────────────────────────
        rules_result = project_game(
            home_team=home, away_team=away,
            home_sp_metrics=home_sp_m, away_sp_metrics=away_sp_m,
            home_offense=home_off, away_offense=away_off,
            weather=weather, umpire=umpire,
            home_bullpen=home_bp, away_bullpen=away_bp,
        )

        # ── Sim model feature construction ───────────────────────────────────
        #
        # Build the 25-feature row from the same live data.
        # NOTE: live pitchers.py does not yet return k_pct / bb_pct.
        # TODO (Phase 10 Task 4): add k_pct + bb_pct to get_pitcher_metrics().
        # Until then, sim model uses league-average defaults for those features.
        STADIUMS_DATA = STADIUMS.get(home, {})
        dome_flag = 1.0 if game.get("dome", False) else 0.0
        wind_speed = weather.get("wind_speed", 0.0)
        wind_out_flag = 1.0 if weather.get("wind_direction", "").lower() in (
            "out", "blowing out", "l to r", "r to l", "center"
        ) else 0.0

        home_bp_xfip = home_bp.get("team_xfip", 4.10)
        away_bp_xfip = away_bp.get("team_xfip", 4.10)
        home_sp_xfip = home_sp_m.get("xfip", 4.10)
        away_sp_xfip = away_sp_m.get("xfip", 4.10)
        home_sp_avg_ip = home_sp_m.get("avg_ip_per_start", 5.5)
        away_sp_avg_ip = away_sp_m.get("avg_ip_per_start", 5.5)
        home_bp_proj_inn = max(0, 9 - home_sp_avg_ip)
        away_bp_proj_inn = max(0, 9 - away_sp_avg_ip)

        home_bullpen_delta     = home_bp_xfip - home_sp_xfip
        away_bullpen_delta     = away_bp_xfip - away_sp_xfip
        home_bp_delta_exposure = home_bullpen_delta * home_bp_proj_inn
        away_bp_delta_exposure = away_bullpen_delta * away_bp_proj_inn

        home_fb_pct = home_sp_m.get("fb_pct", 0.35)
        away_fb_pct = away_sp_m.get("fb_pct", 0.35)
        league_avg_fb = 0.385
        raw_wind_factor = weather.get("wind_factor", 1.0) - 1.0
        flyball_wind_interaction = raw_wind_factor * (
            (home_fb_pct + away_fb_pct) / 2 / league_avg_fb
        )

        # high_leverage_avail: from bullpen fatigue; tier1_red_arms = 0 → available
        home_hl_avail = 1.0 if home_bp.get("tier1_red_arms", 0) == 0 else 0.0
        away_hl_avail = 1.0 if away_bp.get("tier1_red_arms", 0) == 0 else 0.0

        live_row = {
            "home_sp_xfip":             home_sp_xfip,
            "away_sp_xfip":             away_sp_xfip,
            "home_sp_k_pct":            home_sp_m.get("k_pct", 0.224),  # TODO: add to pitchers.py
            "away_sp_k_pct":            away_sp_m.get("k_pct", 0.224),
            "home_sp_bb_pct":           home_sp_m.get("bb_pct", 0.085),
            "away_sp_bb_pct":           away_sp_m.get("bb_pct", 0.085),
            "home_sp_avg_ip":           home_sp_avg_ip,
            "away_sp_avg_ip":           away_sp_avg_ip,
            "home_wrc_plus":            home_off.get("wrc_plus", 100),
            "away_wrc_plus":            away_off.get("wrc_plus", 100),
            "park_factor_runs":         STADIUMS_DATA.get("park_factor", 100),
            "park_factor_hr":           STADIUMS_DATA.get("hr_factor", 100),
            "temperature":              weather.get("temperature", 72.0),
            "wind_speed":               wind_speed,
            "umpire_over_rate":         umpire.get("runs_factor", 1.0),
            "home_rest_days":           game.get("home_rest_days", 1),
            "away_rest_days":           game.get("away_rest_days", 1),
            "doubleheader_flag":        game.get("doubleheader_flag", 0),
            "flyball_wind_interaction": flyball_wind_interaction,
            "home_high_leverage_avail": home_hl_avail,
            "away_high_leverage_avail": away_hl_avail,
            "home_bullpen_delta":       home_bullpen_delta,
            "away_bullpen_delta":       away_bullpen_delta,
            "home_bp_delta_exposure":   home_bp_delta_exposure,
            "away_bp_delta_exposure":   away_bp_delta_exposure,
            # variance features
            "wind_out_flag":            wind_out_flag,
            "home_sp_fb_pct":           home_fb_pct,
            "away_sp_fb_pct":           away_fb_pct,
            "park_factor_hr":           STADIUMS_DATA.get("hr_factor", 100),
            "expected_bullpen_innings": home_bp_proj_inn + away_bp_proj_inn,
            "dome_flag":                dome_flag,
            # metadata for card display
            "home_team":                home,
            "away_team":                away,
            "home_sp_name":             game.get("home_sp_name", "TBD"),
            "away_sp_name":             game.get("away_sp_name", "TBD"),
            "date":                     target_date,
            "temperature":              weather.get("temperature", 72.0),
            "wind_speed":               wind_speed,
            "roof_status":              game.get("roof_status", ""),
            "wind_direction":           weather.get("wind_direction", ""),
            "umpire_name":              game.get("umpire_name", "Unknown"),
        }

        sim_row = pd.Series(live_row)

        # odds line
        line = game.get("total_line")   # set by run_model.py's odds fetch

        sim_result = sim_predict(sim_row, baseline, variance_mdl)
        if line is not None:
            rng   = np.random.default_rng(SEED)
            draws = rng.normal(sim_result["proj"], sim_result["sigma"], N_SIMS)
            sim_result["p_over"]  = round(float((draws > line).mean()), 3)
            sim_result["p_under"] = round(1.0 - sim_result["p_over"], 3)

        print_game_card(sim_row, rules_result, sim_result, line, actual=None)

        log_rows.append(_build_log_row(
            game_id=int(game.get("game_pk", 0)),
            date_str=target_date,
            home=home,
            away=away,
            rules_result=rules_result,
            sim_result=sim_result,
            line=line,
            game_row=sim_row,
        ))

    _log_shadow_rows(log_rows)
    print(f"\n  Logged {len(log_rows)} game(s) → {SHADOW_LOG.relative_to(ROOT)}\n")


# =============================================================================
# CLI entry point
# =============================================================================

# =============================================================================
# Task 5 — Daily shadow checklist
# =============================================================================

def run_checklist(date_str: str | None = None) -> None:
    """
    Print a structured daily health report from the shadow log.
    Also writes to sim/reports/shadow_checklist_YYYY-MM-DD.txt for the paper trail.

    Usage:
        python3 shadow_run.py --checklist [--date YYYY-MM-DD]
    """
    import io
    from contextlib import redirect_stdout
    from datetime import date as dt_date

    target = date_str or str(dt_date.today())
    hr = "─" * 60

    # Tee output: capture into buffer AND print to terminal simultaneously
    buf = io.StringIO()

    class _Tee:
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)
        def flush(self):
            sys.__stdout__.flush()

    import sys as _sys
    orig_stdout = _sys.stdout
    _sys.stdout = _Tee()
    try:
        _run_checklist_body(target, hr)
    finally:
        _sys.stdout = orig_stdout

    # Write to dated file
    report_dir = SIM / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"shadow_checklist_{target}.txt"
    out_path.write_text(buf.getvalue())
    print(f"  Checklist saved → {out_path.relative_to(ROOT)}")


def _run_checklist_body(target: str, hr: str) -> None:
    """Inner implementation — all print() calls captured by run_checklist's tee."""

    print(f"\n{'━'*60}")
    print(f"  SHADOW CHECKLIST — {target}")
    print(f"{'━'*60}")

    if not SHADOW_LOG.exists():
        print("  ✗ No shadow log found — run shadow_run.py first.\n")
        return

    all_df = pd.read_parquet(SHADOW_LOG)
    df = all_df[all_df["date"] == target].copy()

    # ── 1. Games logged today ────────────────────────────────────────────────
    n_games = len(df)
    print(f"\n  {hr}")
    print(f"  1. GAMES LOGGED")
    print(f"  {hr}")
    print(f"     Today ({target}):  {n_games} game(s)")
    print(f"     All dates:         {len(all_df)} total rows across {all_df['date'].nunique()} date(s)")

    # ── 2. Actuals filled ────────────────────────────────────────────────────
    n_filled   = int(df["actual_total"].notna().sum())
    n_unfilled = n_games - n_filled
    print(f"\n  {hr}")
    print(f"  2. ACTUALS FILLED")
    print(f"  {hr}")
    print(f"     Filled: {n_filled}   Pending: {n_unfilled}")
    if n_unfilled > 0 and n_games > 0:
        pending = df[df["actual_total"].isna()][["home_team","away_team"]]
        for _, r in pending.iterrows():
            print(f"     • {r.away_team} @ {r.home_team}  — awaiting result")

    # ── 3. Agreement ─────────────────────────────────────────────────────────
    print(f"\n  {hr}")
    print(f"  3. MODEL AGREEMENT")
    print(f"  {hr}")
    if n_games == 0:
        print("     No games to compare.")
    else:
        agree_n = int(df["agreement"].sum()) if "agreement" in df.columns else 0
        agree_pct = agree_n / n_games * 100
        print(f"     Agree: {agree_n}/{n_games} ({agree_pct:.0f}%)")
        splits = df[~df["agreement"]][["home_team","away_team","rules_tier","sim_tier"]]
        for _, r in splits.iterrows():
            print(f"     SPLIT: {r.away_team} @ {r.home_team} | rules={r.rules_tier} | sim={r.sim_tier}")

    # ── 4. Directional hit rate ───────────────────────────────────────────────
    print(f"\n  {hr}")
    print(f"  4. DIRECTIONAL HIT RATE  (games with actuals)")
    print(f"  {hr}")
    with_results = df.dropna(subset=["actual_total", "market_line"])
    if with_results.empty:
        print("     No graded games yet — run --fill-actuals after games complete.")
    else:
        r_correct = with_results["rules_correct"].dropna()
        s_correct = with_results["sim_correct"].dropna()
        if r_correct.empty:
            print("     correct flags not populated — run --fill-actuals first.")
        else:
            r_rate = r_correct.mean()
            s_rate = s_correct.mean()
            gap    = s_rate - r_rate
            flag   = "⚠️" if gap < -0.05 else "✓"
            print(f"     Rules: {r_correct.sum():.0f}/{len(r_correct)} ({r_rate:.1%})")
            print(f"     Sim:   {s_correct.sum():.0f}/{len(s_correct)} ({s_rate:.1%})")
            print(f"     Gap (sim − rules): {gap:+.1%}  {flag}")

    # ── 5. Missing market lines ──────────────────────────────────────────────
    print(f"\n  {hr}")
    print(f"  5. MISSING MARKET LINES")
    print(f"  {hr}")
    no_line = df[df["market_line"].isna()] if n_games > 0 else pd.DataFrame()
    if no_line.empty:
        print("     None — all games have closing lines.")
    else:
        for _, r in no_line.iterrows():
            print(f"     ✗ {r.away_team} @ {r.home_team} — no market line")

    # ── 6. Missing critical features ─────────────────────────────────────────
    # Check by inspecting rules_proj=NaN (indicator of rules model failure)
    print(f"\n  {hr}")
    print(f"  6. PIPELINE ISSUES")
    print(f"  {hr}")
    issues = []
    if n_games > 0:
        bad_rules = df[df["rules_proj"].isna() | (df["rules_proj"] == 0)]
        bad_sim   = df[df["sim_proj"].isna()   | (df["sim_proj"]   == 0)]
        for _, r in bad_rules.iterrows():
            issues.append(f"  ✗ Rules model failed: {r.away_team} @ {r.home_team}")
        for _, r in bad_sim.iterrows():
            issues.append(f"  ✗ Sim model failed: {r.away_team} @ {r.home_team}")

        # Projection range sanity (< 5 or > 20 are suspicious)
        out_of_range = df[(df["rules_proj"].notna()) &
                          ((df["rules_proj"] < 5) | (df["rules_proj"] > 20))]
        for _, r in out_of_range.iterrows():
            issues.append(f"  ⚠️  Rules proj out of range: {r.away_team}@{r.home_team} = {r.rules_proj:.1f}")
        out_of_range_s = df[(df["sim_proj"].notna()) &
                            ((df["sim_proj"] < 5) | (df["sim_proj"] > 20))]
        for _, r in out_of_range_s.iterrows():
            issues.append(f"  ⚠️  Sim proj out of range: {r.away_team}@{r.home_team} = {r.sim_proj:.1f}")

    if not issues:
        print("     None — all projections in expected range.")
    else:
        for msg in issues:
            print(f"     {msg}")

    # ── 7. Overall health ────────────────────────────────────────────────────
    print(f"\n  {hr}")
    critical_failures = len(
        [i for i in issues if "✗" in i]
    ) if issues else 0
    if n_games == 0:
        status = "⚠️  NO GAMES LOGGED TODAY"
    elif critical_failures > 0:
        status = f"✗  {critical_failures} CRITICAL ISSUE(S)"
    elif no_line.shape[0] > n_games // 2:
        status = "⚠️  MOST LINES MISSING — verify Odds API"
    else:
        status = "✓  PIPELINE HEALTHY"
    print(f"  OVERALL: {status}")
    print(f"{'━'*60}\n")


# =============================================================================
# Task 6 — Strict cutover gate
# =============================================================================

def run_ready_to_cutover() -> None:
    """
    Evaluate hard criteria for MODEL_MODE flip to "simulation".
    Prints READY or NOT READY with specific reasons.

    Usage:
        python3 shadow_run.py --ready-to-cutover
    """
    print(f"\n{'━'*60}")
    print("  CUTOVER GATE EVALUATION")
    print(f"{'━'*60}\n")

    criteria = []   # (label, passed: bool, detail: str)

    if not SHADOW_LOG.exists():
        print("  ✗ No shadow log found. Run shadow_run.py first.\n")
        return

    df = pd.read_parquet(SHADOW_LOG)

    # ── Criterion 1: At least 3 full shadow slates with actuals ──────────────
    graded_dates = (
        df[df["actual_total"].notna()]
        .groupby("date")
        .filter(lambda g: g["actual_total"].notna().all())
        ["date"].unique()
    )
    n_complete_dates = len(graded_dates)
    passed = n_complete_dates >= 3
    criteria.append((
        "≥ 3 fully-graded shadow slates",
        passed,
        f"{n_complete_dates} complete date(s): {', '.join(sorted(graded_dates)) or 'none'}",
    ))

    # ── Criterion 2: Zero pipeline failures (rules_proj or sim_proj = NaN/0) ─
    bad = df[df["rules_proj"].isna() | df["sim_proj"].isna() |
             (df["rules_proj"] == 0) | (df["sim_proj"] == 0)]
    n_failures = len(bad)
    passed = n_failures == 0
    criteria.append((
        "Zero pipeline failures",
        passed,
        f"{n_failures} failure(s) detected" if n_failures else "clean",
    ))

    # ── Criterion 3: Zero critical missing-feature issues ────────────────────
    # Proxy: projections outside 5–20 run range = likely missing starter
    out_of_range = df[
        (df["rules_proj"].notna() & ((df["rules_proj"] < 5) | (df["rules_proj"] > 20))) |
        (df["sim_proj"].notna()   & ((df["sim_proj"]   < 5) | (df["sim_proj"]   > 20)))
    ]
    n_bad_range = len(out_of_range)
    passed = n_bad_range == 0
    criteria.append((
        "Zero out-of-range projections (missing starter proxy)",
        passed,
        f"{n_bad_range} game(s) with proj < 5 or > 20" if n_bad_range else "all in range",
    ))

    # ── Criterion 4: Missing market lines ≤ 20% of total ────────────────────
    n_total   = len(df)
    n_missing = int(df["market_line"].isna().sum())
    pct_miss  = n_missing / max(n_total, 1)
    passed = pct_miss <= 0.20
    criteria.append((
        "Market lines available for ≥ 80% of games",
        passed,
        f"{n_total - n_missing}/{n_total} games have lines ({100*(1-pct_miss):.0f}%)",
    ))

    # ── Criterion 5: Sim directional hit rate not > 5pp worse than rules ─────
    graded = df.dropna(subset=["actual_total", "market_line", "rules_correct", "sim_correct"])
    if graded.empty:
        passed = False
        detail = "No graded games — cannot evaluate"
    else:
        r_rate = graded["rules_correct"].mean()
        s_rate = graded["sim_correct"].mean()
        gap    = s_rate - r_rate
        passed = gap >= -0.05
        detail = (f"Sim {s_rate:.1%} vs Rules {r_rate:.1%}  (gap {gap:+.1%})"
                  + (" ✓" if passed else " — exceeds −5pp threshold"))
    criteria.append((
        "Sim hit rate not > 5pp below rules",
        passed,
        detail,
    ))

    # ── Print results ─────────────────────────────────────────────────────────
    all_pass = all(c[1] for c in criteria)
    for label, ok, detail in criteria:
        icon = "✓" if ok else "✗"
        print(f"  {icon}  {label}")
        print(f"       {detail}\n")

    print("─" * 60)
    if all_pass:
        print("\n  ✅  READY TO CUTOVER")
        print("  Run: sed -i '' 's/MODEL_MODE = \"rules\"/MODEL_MODE = \"simulation\"/' config.py")
        print("  Or edit config.py manually — it's a one-line change.\n")
    else:
        n_fail = sum(1 for c in criteria if not c[1])
        print(f"\n  🔴  NOT READY — {n_fail} criterion/criteria not met.")
        print("  Continue shadow logging until all criteria pass.\n")


# =============================================================================
# CLI entry point
# =============================================================================

def run_m3_summary() -> None:
    """
    Print M3 shadow tracking summary with M5 breakdowns:
    OVER vs UNDER, disagreement buckets, and combined views.
    """
    if not SHADOW_LOG.exists():
        print("No shadow log found.")
        return

    df = pd.read_parquet(SHADOW_LOG)

    # Filter to graded M3 plays (has m3_edge and actual_total)
    has_m3 = "m3_edge" in df.columns and "m3_signal_direction" in df.columns
    if not has_m3:
        print("No M3 tracking fields in shadow log yet.")
        print("M3 fields are added from the next shadow run forward.")
        return

    graded = df[df["actual_total"].notna() & df["m3_edge"].notna() & df["market_line"].notna()].copy()
    if graded.empty:
        print("No graded M3 plays yet. Run --fill-actuals first.")
        return

    # Compute M3 bet outcome
    graded["m3_bet_win"] = np.where(
        graded["m3_signal_direction"] == "OVER",
        graded["actual_total"] > graded["market_line"],
        graded["actual_total"] < graded["market_line"]
    ).astype(int)

    def _roi(wins, n):
        if n == 0: return float("nan")
        return (wins * (100/110) - (n - wins)) / n * 100

    def _print_row(label, sub):
        n = len(sub)
        if n == 0:
            print(f"  {label:<35s}   N=0")
            return
        w = sub["m3_bet_win"].sum()
        hr = w / n * 100
        roi = _roi(w, n)
        print(f"  {label:<35s}   N={n:>4d}  hit={hr:5.1f}%  ROI={roi:+6.1f}%")

    hr = "─" * 60

    print(f"\n{'━'*60}")
    print("  M3 SHADOW TRACKING — M5 BREAKDOWNS")
    print(f"{'━'*60}")
    print(f"  Graded M3 plays: {len(graded)}")
    print(f"  Date range: {graded['date'].min()} to {graded['date'].max()}")

    # ── A. OVER vs UNDER ──
    print(f"\n  {hr}")
    print("  A. SIGNAL DIRECTION (OVER vs UNDER)")
    print(f"  {hr}")
    _print_row("ALL M3 plays", graded)
    for direction in ["OVER", "UNDER"]:
        for min_e in [0.5, 1.0, 1.5]:
            sub = graded[(graded["m3_signal_direction"] == direction) &
                          (graded["m3_edge"].abs() >= min_e)]
            _print_row(f"{direction} edge>={min_e}", sub)

    # ── B. Disagreement buckets ──
    print(f"\n  {hr}")
    print("  B. DISAGREEMENT BUCKETS (M3 vs sim model)")
    print(f"  {hr}")
    if "disagree_bucket" in graded.columns:
        for bucket in ["0.0-0.5", "0.5-1.0", "1.0-1.5", "1.5+"]:
            sub = graded[(graded["disagree_bucket"] == bucket) &
                          (graded["m3_edge"].abs() >= 1.0)]
            _print_row(f"disagree {bucket} (edge>=1.0)", sub)
    else:
        print("  (disagree_bucket not yet populated)")

    # ── C. Combined direction × disagreement ──
    print(f"\n  {hr}")
    print("  C. DIRECTION × DISAGREEMENT (edge >= 1.0)")
    print(f"  {hr}")
    if "disagree_bucket" in graded.columns:
        for direction in ["UNDER", "OVER"]:
            for bucket in ["0.5-1.0", "1.0-1.5", "1.5+"]:
                sub = graded[
                    (graded["m3_signal_direction"] == direction) &
                    (graded["disagree_bucket"] == bucket) &
                    (graded["m3_edge"].abs() >= 1.0)
                ]
                _print_row(f"{direction} + disagree {bucket}", sub)
    else:
        print("  (disagree_bucket not yet populated)")

    # ── D. Models direction relation ──
    print(f"\n  {hr}")
    print("  D. MODELS DIRECTION RELATION (edge >= 1.0)")
    print(f"  {hr}")
    if "models_direction_relation" in graded.columns:
        for rel in ["SAME", "OPPOSITE"]:
            sub = graded[(graded["models_direction_relation"] == rel) &
                          (graded["m3_edge"].abs() >= 1.0)]
            _print_row(f"Models {rel} direction", sub)

    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Shadow run: rules vs sim model comparison")
    p.add_argument("--demo",              action="store_true", help="Demo mode (historical feature_table)")
    p.add_argument("--game-pk",           type=int,            help="Specific game_pk for demo mode")
    p.add_argument("--date",              type=str,            help="Date (YYYY-MM-DD) for demo or live mode")
    p.add_argument("--no-odds",           action="store_true", help="Skip Odds API calls")
    p.add_argument("--fill-actuals",      action="store_true", help="Fill actual_total + correct flags in shadow_log")
    p.add_argument("--summary",           action="store_true", help="Print shadow_log summary and exit")
    p.add_argument("--m3-summary",        action="store_true", help="Print M3 + M5 tracking breakdowns")
    p.add_argument("--checklist",         action="store_true", help="Daily pipeline health report")
    p.add_argument("--ready-to-cutover",  action="store_true", help="Evaluate hard cutover criteria")
    args = p.parse_args()

    if args.fill_actuals:
        fill_actuals(date_str=args.date)
    elif args.summary:
        if SHADOW_LOG.exists():
            df = pd.read_parquet(SHADOW_LOG)
            print(f"\nShadow log: {len(df)} rows, {df['date'].nunique()} dates")
            print(df[["date","home_team","away_team","rules_proj","sim_proj",
                       "market_line","rules_tier","sim_tier","agreement","actual_total"]].to_string(index=False))
        else:
            print("No shadow log found.")
    elif getattr(args, "m3_summary", False):
        run_m3_summary()
    elif args.checklist:
        run_checklist(date_str=args.date)
    elif getattr(args, "ready_to_cutover", False):
        run_ready_to_cutover()
    elif args.demo or args.game_pk:
        run_demo(game_pk=args.game_pk, date=args.date, no_odds=args.no_odds)
    else:
        run_live(date_str=args.date, no_odds=args.no_odds)
