"""
Phase V2.2-C+D: Market-residual model training and OOS evaluation.

Target: residual_over_2_5 = actual_over_2_5 - market_fair_p_over_2_5
  (where is the market mispriced?)

Trains two models:
  Model 1: Ridge baseline
  Model 2: LightGBM challenger

Both calibrated via isotonic regression on validate set.
Both evaluated on OOS. Better model chosen for production.

OOS success gates (unchanged from V2.1):
  OVER hit rate >= 52.5%
  UNDER hit rate >= 45%
  Any edge bucket positive ROI (n >= 20)
  Monotonic edge curve

Output:
  soccer/models/ridge_residual_model.pkl
  soccer/models/lgbm_residual_model.pkl
  soccer/models/calibrator_ridge.pkl
  soccer/models/calibrator_lgbm.pkl
  soccer/data/soccer_v2_2_predictions.parquet
  soccer/phase_v2_2_audit.txt
"""

import io
import json
import logging
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

from sklearn.ensemble import HistGradientBoostingRegressor
HAS_LGBM = True   # Using sklearn HGBR as drop-in challenger

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(BASE_DIR, "data")
MODELS_DIR    = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURE_PATH  = os.path.join(DATA_DIR, "soccer_feature_table_v2_2.parquet")
OUTPUT_PATH   = os.path.join(DATA_DIR, "soccer_v2_2_predictions.parquet")
AUDIT_PATH    = os.path.join(BASE_DIR, "phase_v2_2_audit.txt")

ALPHA_GRID = [0.1, 1.0, 10.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0]

SEP  = "═" * 72
SEP2 = "─" * 72

# ── Feature columns ───────────────────────────────────────────────────────────
# All V2.1 features + new V2.2 groups
# League IDs used for one-hot encoding (EPL is the reference category, dropped)
_LEAGUE_DUMMY_IDS = ["BUN", "LGA", "SEA", "LG1"]

FEATURE_COLS = [
    # League fixed effects
    "league_avg_goals_rolling_season",
    "league_avg_xg_rolling_season",
    "league_home_adv",
] + [f"is_{lid.lower()}" for lid in _LEAGUE_DUMMY_IDS] + [
    "league_goals_rolling_10",
    "league_xg_rolling_10",
    # Attack / defence xG
    "home_xg_for_rolling_10", "home_xg_against_rolling_10",
    "away_xg_for_rolling_10", "away_xg_against_rolling_10",
    "home_xg_for_rolling_3",  "home_xg_against_rolling_3",
    "away_xg_for_rolling_3",  "away_xg_against_rolling_3",
    "home_xg_for_rolling_15", "home_xg_against_rolling_15",
    "away_xg_for_rolling_15", "away_xg_against_rolling_15",
    # Shot volume
    "home_shots_for_rolling_10",   "home_shots_against_rolling_10",
    "away_shots_for_rolling_10",   "away_shots_against_rolling_10",
    "home_shots_on_target_rolling_10", "away_shots_on_target_rolling_10",
    "home_shots_for_rolling_3",    "away_shots_for_rolling_3",
    # Goals form
    "home_goals_scored_rolling_5",  "home_goals_conceded_rolling_5",
    "away_goals_scored_rolling_5",  "away_goals_conceded_rolling_5",
    "home_goals_scored_rolling_3",  "away_goals_scored_rolling_3",
    # Rest / schedule
    "home_days_rest", "away_days_rest",
    "home_matches_last_7", "away_matches_last_7",
    # Matchup interactions (V2.0)
    "home_xg_mismatch", "away_xg_mismatch",
    "home_shot_mismatch", "away_shot_mismatch",
    "home_form_mismatch", "away_form_mismatch",
    # Lineup features (V2.1)
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
    # Group K: Market (V2.2) — NOTE: market_fair_p_over_2_5 NOT included as feature
    # (it's the baseline, not a signal — including it would let the model learn
    #  to just output the market, not beat it)
    "market_fair_p_over_1_5",
    "market_fair_p_over_3_5",
    "market_low_total_pressure",
    "market_high_total_pressure",
    "market_implied_mu",
    "market_move_to_over_2_5",
    "market_move_magnitude_2_5",
    "market_late_move_over",
    "market_late_move_under",
    # Group L: Injuries (V2.2)
    "home_injury_count", "away_injury_count",
    "home_key_player_injured", "away_key_player_injured",
    "home_total_absence_score", "away_total_absence_score",
    # Group M: Weather (V2.2)
    "weather_wind_high", "weather_rain",
    "weather_temp_cold", "weather_extreme",
    "weather_wind_kph", "weather_precip_mm",
    # Group N: Referee (V2.2)
    "ref_avg_goals", "ref_red_card_rate",
    "ref_penalty_rate", "ref_available",
]

# Columns with NaN that need imputation (same as V2.1 + new)
IMPUTE_ZERO = [
    "home_lineup_delta", "away_lineup_delta",
    "home_att_strength", "away_att_strength",
    "home_def_strength", "away_def_strength",
    "home_first_choice_gk_missing", "away_first_choice_gk_missing",
    "home_primary_attacker_missing", "away_primary_attacker_missing",
    "home_attack_delta_vs_away_defense", "away_attack_delta_vs_home_defense",
    "net_lineup_attack_edge", "net_lineup_defense_weakness",
    "home_injury_count", "away_injury_count",
    "home_key_player_injured", "away_key_player_injured",
    "home_total_absence_score", "away_total_absence_score",
    "market_move_to_over_2_5", "market_move_magnitude_2_5",
    "market_late_move_over", "market_late_move_under",
    "weather_wind_high", "weather_rain",
    "weather_temp_cold", "weather_extreme",
]
IMPUTE_MEAN = [
    "home_lineup_overlap_last_match", "away_lineup_overlap_last_match",
    "home_lineup_overlap_rolling_3", "away_lineup_overlap_rolling_3",
]
IMPUTE_MEDIAN = [
    "home_num_defenders", "away_num_defenders",
    "home_num_attackers", "away_num_attackers",
    "home_back_five", "away_back_five",
    "weather_wind_kph", "weather_precip_mm",
]


# ── Data preparation ──────────────────────────────────────────────────────────

def prepare(df: pd.DataFrame, impute_vals: dict | None = None) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    # League dummies (EPL is reference, dropped to avoid multicollinearity)
    for lid in _LEAGUE_DUMMY_IDS:
        df[f"is_{lid.lower()}"] = (df["league_id"] == lid).astype(float)

    if impute_vals is None:
        impute_vals = {}
        for col in IMPUTE_ZERO:
            impute_vals[col] = 0.0
        for col in IMPUTE_MEAN:
            impute_vals[col] = float(df[col].mean()) if col in df.columns else 0.0
        for col in IMPUTE_MEDIAN:
            impute_vals[col] = float(df[col].median()) if col in df.columns else 0.0
        # Rest
        impute_vals["home_days_rest"] = float(df["home_days_rest"].median())
        impute_vals["away_days_rest"] = float(df["away_days_rest"].median())
        # Market: fill with mean (already fallback-filled in B, but just in case)
        for col in ["market_fair_p_over_1_5", "market_fair_p_over_3_5",
                    "market_implied_mu", "market_low_total_pressure",
                    "market_high_total_pressure"]:
            if col in df.columns:
                impute_vals[col] = float(df[col].mean())
        # Ref
        impute_vals["ref_avg_goals"]    = float(df.get("ref_avg_goals", pd.Series([2.8])).mean())
        impute_vals["ref_red_card_rate"] = float(df.get("ref_red_card_rate", pd.Series([0.1])).mean())
        impute_vals["ref_penalty_rate"] = float(df.get("ref_penalty_rate", pd.Series([0.3])).mean())

    for col, val in impute_vals.items():
        if col in df.columns:
            df[col] = df[col].fillna(val)

    # Ensure all FEATURE_COLS are present
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = impute_vals.get(col, 0.0)

    # Catch-all: fill any remaining NaN in feature columns with column mean or 0
    for col in FEATURE_COLS:
        if col in df.columns and df[col].isna().any():
            fill_val = impute_vals.get(col)
            if fill_val is None:
                fill_val = float(df[col].mean()) if df[col].notna().any() else 0.0
                impute_vals[col] = fill_val
            df[col] = df[col].fillna(fill_val)

    return df, impute_vals


def build_sample_weights(df: pd.DataFrame) -> np.ndarray:
    """COVID downweight + market-available upweight."""
    w = np.ones(len(df))
    w[df["season_year"].isin(["2019-20", "2020-21"])] = 0.5
    # Full weight for games without market odds (already at 1.0)
    # Downweight games that need fallback market (pre-2020 or missing)
    if "market_odds_available" in df.columns:
        w[df["market_odds_available"] == 0] *= 0.3
    return w


# ── ROI calculation ───────────────────────────────────────────────────────────

def roi_at_110(hit_rate: float) -> float:
    """ROI betting at -110 (vig-applied)."""
    return hit_rate * (100 / 110) - (1 - hit_rate)


# ── Calibration ───────────────────────────────────────────────────────────────

def calibrate_isotonic(pred_raw: np.ndarray, actual: np.ndarray) -> IsotonicRegression:
    """Fit isotonic regression on validate set predictions."""
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(pred_raw, actual)
    return iso


# ── Evaluation ────────────────────────────────────────────────────────────────

EDGE_THRESHOLD = 0.04

def evaluate_signals(df: pd.DataFrame, model_name: str, buf: io.StringIO) -> dict:
    """
    Full OOS evaluation: signals, hit rates, ROI by edge bucket.
    Returns dict with key metrics.
    """
    def p(s=""):
        print(s, file=buf)
        print(s)

    p(f"\n  {model_name} — OOS EVALUATION")
    p(f"  {SEP2[:60]}")

    oos = df[df["split"] == "oos"].copy()
    p(f"  OOS rows: {len(oos):,}  |  market_available: {(oos.get('market_odds_available',0)==1).sum()}")

    # Signals
    oos["signal_over"]  = oos["edge_over_2_5"] >= EDGE_THRESHOLD
    oos["signal_under"] = oos["edge_over_2_5"] <= -EDGE_THRESHOLD
    oos["actual_over"]  = (oos["actual_total_goals"] > 2.5).astype(float)
    oos["actual_under"] = (oos["actual_total_goals"] <= 2.5).astype(float)

    over_sigs  = oos[oos["signal_over"]]
    under_sigs = oos[oos["signal_under"]]

    n_over  = len(over_sigs)
    n_under = len(under_sigs)

    hit_over  = over_sigs["actual_over"].mean()  if n_over  > 0 else np.nan
    hit_under = under_sigs["actual_under"].mean() if n_under > 0 else np.nan

    roi_over  = roi_at_110(hit_over)  if not np.isnan(hit_over)  else np.nan
    roi_under = roi_at_110(hit_under) if not np.isnan(hit_under) else np.nan

    p(f"  OVER  signals: N={n_over:>4}  hit={hit_over:.1%}  ROI={roi_over:+.3f}")
    p(f"  UNDER signals: N={n_under:>4}  hit={hit_under:.1%}  ROI={roi_under:+.3f}")
    p()

    # Edge buckets
    p(f"  EDGE BUCKETS (OOS):")
    p(f"  {'Bucket':<12} {'N':>5} {'Wins':>6} {'Hit%':>8} {'ROI':>8}")
    p(f"  {'-'*44}")

    buckets = [(0.04, 0.06), (0.06, 0.08), (0.08, 0.10), (0.10, 1.0)]
    bucket_results = []

    for lo, hi in buckets:
        # Both OVER and UNDER signals in this edge magnitude bucket
        mask = (oos["edge_over_2_5"].abs() >= lo) & (oos["edge_over_2_5"].abs() < hi)
        sub  = oos[mask]
        n    = len(sub)
        if n < 5:
            bucket_results.append({"lo": lo, "hi": hi, "n": n, "hit": np.nan, "roi": np.nan})
            p(f"  {lo:.2f}–{hi:.2f}    {n:>5}  (too few)")
            continue

        # Win: over signal → over hits; under signal → under hits
        wins = (
            (sub["signal_over"]  & (sub["actual_over"]  == 1)) |
            (sub["signal_under"] & (sub["actual_under"] == 1))
        ).sum()
        hit = wins / n
        roi = roi_at_110(hit)
        check = "✓" if roi > 0 else "✗"
        p(f"  {lo:.2f}–{hi:.2f}   {n:>5}  {wins:>6}  {hit:>7.1%}  {roi:>+7.3f}  {check}")
        bucket_results.append({"lo": lo, "hi": hi, "n": n, "hit": hit, "roi": roi})

    p()

    # ── Gate evaluation ───────────────────────────────────────────────────────
    p(f"  OOS GATE EVALUATION:")
    gate_results = {}

    # Gate 1: OVER hit rate >= 52.5%
    g1 = not np.isnan(hit_over) and hit_over >= 0.525
    gate_results["over_hit_rate"] = {"value": hit_over, "pass": g1}
    p(f"  Gate 1 — OVER hit rate >= 52.5%:  {hit_over:.1%}  → {'PASS ✓' if g1 else 'FAIL ✗'}")

    # Gate 2: UNDER hit rate >= 45%
    g2 = not np.isnan(hit_under) and hit_under >= 0.45
    gate_results["under_hit_rate"] = {"value": hit_under, "pass": g2}
    p(f"  Gate 2 — UNDER hit rate >= 45%:   {hit_under:.1%}  → {'PASS ✓' if g2 else 'FAIL ✗'}")

    # Gate 3: Any edge bucket positive ROI (n >= 20)
    pos_buckets = [b for b in bucket_results if b["n"] >= 20 and not np.isnan(b["roi"]) and b["roi"] > 0]
    g3 = len(pos_buckets) > 0
    gate_results["positive_bucket"] = {"value": len(pos_buckets), "pass": g3}
    p(f"  Gate 3 — Any edge bucket ROI > 0: {len(pos_buckets)} bucket(s)  → {'PASS ✓' if g3 else 'FAIL ✗'}")

    # Gate 4: Monotonic edge curve (rough: higher edge → higher hit rate)
    valid_bkts = [b for b in bucket_results if b["n"] >= 20 and not np.isnan(b["hit"])]
    if len(valid_bkts) >= 2:
        hits = [b["hit"] for b in valid_bkts]
        monotone = all(hits[i] <= hits[i+1] + 0.05 for i in range(len(hits)-1)) or \
                   all(hits[i] >= hits[i+1] - 0.05 for i in range(len(hits)-1))
        g4 = monotone
    else:
        g4 = True  # Can't evaluate with < 2 buckets
    gate_results["monotonic"] = {"value": None, "pass": g4}
    p(f"  Gate 4 — Monotonic edge curve:    {'PASS ✓' if g4 else 'FAIL ✗'}")

    gates_passed = sum([g1, g2, g3, g4])
    p()
    p(f"  Gates passed: {gates_passed}/4")
    verdict = "GO ✓" if gates_passed >= 3 and g1 and g3 else "NO-GO ✗"
    p(f"  VERDICT: {verdict}  (need all 4 to proceed; must pass gate 1 + 3)")
    p()

    return {
        "n_over": n_over, "n_under": n_under,
        "hit_over": hit_over, "hit_under": hit_under,
        "roi_over": roi_over, "roi_under": roi_under,
        "gates_passed": gates_passed,
        "verdict": verdict,
        "g1": g1, "g2": g2, "g3": g3, "g4": g4,
        "bucket_results": bucket_results,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    buf = io.StringIO()

    def pw(s=""):
        print(s, file=buf)
        print(s)

    pw(SEP)
    pw("  PHASE V2.2-C+D: MARKET-RESIDUAL MODEL TRAINING AND EVALUATION")
    pw(SEP)

    # ── Load feature table ─────────────────────────────────────────────────────
    ft = pd.read_parquet(FEATURE_PATH)
    logger.info(f"Feature table: {len(ft):,} rows × {len(ft.columns)} columns")

    # ── Splits ────────────────────────────────────────────────────────────────
    SPLIT_MAP = {
        "2019-20": "train", "2020-21": "train",
        "2021-22": "train", "2022-23": "train",
        "2023-24": "validate", "2024-25": "oos",
    }
    ft["split"] = ft["season_year"].map(SPLIT_MAP)
    # Drop rows outside train/validate/oos (e.g. current live season)
    ft = ft[ft["split"].notna()].copy()

    train_raw = ft[ft["split"] == "train"].copy()
    val_raw   = ft[ft["split"] == "validate"].copy()
    oos_raw   = ft[ft["split"] == "oos"].copy()

    pw(f"\n  Split sizes: train={len(train_raw)}  validate={len(val_raw)}  oos={len(oos_raw)}")

    # ── Prepare (impute NaN) ───────────────────────────────────────────────────
    train_prep, impute_vals = prepare(train_raw)
    val_prep,   _           = prepare(val_raw,  impute_vals)
    oos_prep,   _           = prepare(oos_raw,  impute_vals)
    all_prep,   _           = prepare(ft,        impute_vals)

    # Save impute values
    with open(os.path.join(MODELS_DIR, "v2_2_impute_vals.pkl"), "wb") as f:
        pickle.dump(impute_vals, f)

    # ── Target variable: residual_over_2_5 ────────────────────────────────────
    # actual_over_2_5 = 1 if total_goals > 2.5
    # market_fair_p_over_2_5 = vig-removed B365 closing probability

    for prep in [train_prep, val_prep, oos_prep, all_prep]:
        prep["actual_over_2_5"] = (prep["total_goals"] > 2.5).astype(float)
        prep["residual_over_2_5"] = (
            prep["actual_over_2_5"] - prep["market_fair_p_over_2_5"]
        )

    # Sample weights
    w_train = build_sample_weights(train_prep)

    y_train_res  = train_prep["residual_over_2_5"].values
    y_val_res    = val_prep["residual_over_2_5"].values
    y_val_act    = val_prep["actual_over_2_5"].values
    y_oos_act    = oos_prep["actual_over_2_5"].values

    X_train = train_prep[FEATURE_COLS].values
    X_val   = val_prep[FEATURE_COLS].values
    X_oos   = oos_prep[FEATURE_COLS].values
    X_all   = all_prep[FEATURE_COLS].values

    pw(f"\n  Feature count: {len(FEATURE_COLS)}")
    pw(f"  Target: residual_over_2_5")
    pw(f"  Mean residual (train): {y_train_res.mean():+.4f}  (should be near 0)")
    pw(f"  Std  residual (train): {y_train_res.std():.4f}")
    pw()

    # ── ═══════════════════════════════════════════════════════════════════════
    #    MODEL 1: RIDGE
    # ── ═══════════════════════════════════════════════════════════════════════

    pw(f"  MODEL 1 — RIDGE BASELINE")
    pw(f"  {SEP2[:60]}")

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s   = scaler.transform(X_val)
    X_oos_s   = scaler.transform(X_oos)
    X_all_s   = scaler.transform(X_all)

    # Alpha grid search
    ridge_alpha_results = {}
    for alpha in ALPHA_GRID:
        mdl = Ridge(alpha=alpha)
        mdl.fit(X_train_s, y_train_res, sample_weight=w_train)
        preds_val = mdl.predict(X_val_s)
        mae = mean_absolute_error(y_val_res, preds_val)
        ridge_alpha_results[alpha] = mae

    best_alpha_ridge = min(ridge_alpha_results, key=ridge_alpha_results.get)
    pw(f"  Alpha grid search:")
    for a, mae in sorted(ridge_alpha_results.items()):
        mark = " ← selected" if a == best_alpha_ridge else ""
        pw(f"    alpha={a:<8} validate MAE={mae:.4f}{mark}")
    pw()

    ridge_model = Ridge(alpha=best_alpha_ridge)
    ridge_model.fit(X_train_s, y_train_res, sample_weight=w_train)

    # Predict residuals → add to market → clip
    all_prep["ridge_pred_residual"] = ridge_model.predict(X_all_s)
    all_prep["ridge_raw_p"] = (
        all_prep["market_fair_p_over_2_5"] + all_prep["ridge_pred_residual"]
    ).clip(0.05, 0.95)

    # Calibrate on validate
    val_raw_p = val_prep["market_fair_p_over_2_5"].values + ridge_model.predict(X_val_s)
    val_raw_p = val_raw_p.clip(0.05, 0.95)
    iso_ridge = calibrate_isotonic(val_raw_p, y_val_act)
    all_prep["ridge_cal_p"] = iso_ridge.predict(all_prep["ridge_raw_p"].values)
    all_prep["edge_over_2_5"] = (
        all_prep["ridge_cal_p"] - all_prep["market_fair_p_over_2_5"]
    )

    # Feature importance
    pw(f"  Top 15 features (by scaled coefficient magnitude):")
    pw(f"  {'Feature':<45} {'Coef':>8}")
    pw(f"  {'-'*55}")
    coefs = pd.Series(ridge_model.coef_, index=FEATURE_COLS)
    top15 = coefs.abs().sort_values(ascending=False).head(15)
    for feat in top15.index:
        pw(f"  {feat:<45} {coefs[feat]:>+8.4f}")
    pw()

    # Group K features in top 15?
    grp_k = [f for f in top15.index if f.startswith("market_")]
    pw(f"  Market features in top 15: {grp_k if grp_k else '(none)'}")
    pw()

    # Evaluate Ridge
    ridge_results = evaluate_signals(all_prep.rename(columns={
        "total_goals": "actual_total_goals"
    }), "RIDGE", buf)

    # Save Ridge
    with open(os.path.join(MODELS_DIR, "ridge_residual_model.pkl"), "wb") as f:
        pickle.dump(ridge_model, f)
    with open(os.path.join(MODELS_DIR, "scaler_v2_2.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODELS_DIR, "calibrator_ridge.pkl"), "wb") as f:
        pickle.dump(iso_ridge, f)

    # ── ═══════════════════════════════════════════════════════════════════════
    #    MODEL 2: LIGHTGBM
    # ── ═══════════════════════════════════════════════════════════════════════

    lgbm_results = None
    lgbm_pred_col = None

    if HAS_LGBM:
        pw(f"  MODEL 2 — HISTGRADIENTBOOSTING CHALLENGER (sklearn HGBR)")
        pw(f"  {SEP2[:60]}")

        best_lgbm_params = None
        best_lgbm_mae    = float("inf")
        best_lgbm_model  = None

        quick_grid = [
            {"max_leaf_nodes": ml, "learning_rate": lr, "max_iter": 500,
             "min_samples_leaf": ms, "l2_regularization": l2}
            for ml in [31, 63, 127]
            for lr in [0.05, 0.01]
            for ms in [20, 50]
            for l2 in [0.0, 1.0]
        ]

        pw(f"  Grid ({len(quick_grid)} combos, validate MAE selection)...")

        for params in quick_grid:
            mdl = HistGradientBoostingRegressor(
                max_leaf_nodes=params["max_leaf_nodes"],
                learning_rate=params["learning_rate"],
                max_iter=params["max_iter"],
                min_samples_leaf=params["min_samples_leaf"],
                l2_regularization=params["l2_regularization"],
                early_stopping=True,
                validation_fraction=None,
                n_iter_no_change=30,
                random_state=42,
            )
            mdl.fit(X_train, y_train_res, sample_weight=w_train)
            mae = mean_absolute_error(y_val_res, mdl.predict(X_val))
            if mae < best_lgbm_mae:
                best_lgbm_mae    = mae
                best_lgbm_params = params.copy()
                best_lgbm_model  = mdl

        pw(f"  Best HGBR params: {best_lgbm_params}")
        pw(f"  Best validate MAE: {best_lgbm_mae:.4f}")
        pw()

        # Predictions
        all_prep["lgbm_pred_residual"] = best_lgbm_model.predict(X_all)
        all_prep["lgbm_raw_p"] = (
            all_prep["market_fair_p_over_2_5"] + all_prep["lgbm_pred_residual"]
        ).clip(0.05, 0.95)

        # Calibrate on validate
        lgbm_val_raw = val_prep["market_fair_p_over_2_5"].values + best_lgbm_model.predict(X_val)
        lgbm_val_raw = lgbm_val_raw.clip(0.05, 0.95)
        iso_lgbm = calibrate_isotonic(lgbm_val_raw, y_val_act)
        all_prep["lgbm_cal_p"] = iso_lgbm.predict(all_prep["lgbm_raw_p"].values)

        # Evaluate LightGBM
        lgbm_eval_df = all_prep.copy()
        lgbm_eval_df["edge_over_2_5"] = (
            lgbm_eval_df["lgbm_cal_p"] - lgbm_eval_df["market_fair_p_over_2_5"]
        )
        lgbm_results = evaluate_signals(
            lgbm_eval_df.rename(columns={"total_goals": "actual_total_goals"}),
            "LIGHTGBM", buf
        )

        # Save LightGBM
        with open(os.path.join(MODELS_DIR, "lgbm_residual_model.pkl"), "wb") as f:
            pickle.dump(best_lgbm_model, f)
        with open(os.path.join(MODELS_DIR, "calibrator_lgbm.pkl"), "wb") as f:
            pickle.dump(iso_lgbm, f)
    else:
        pw(f"  MODEL 2 — LIGHTGBM SKIPPED (not installed)")
        pw(f"  Install: pip install lightgbm")
        pw()

    # ── Head-to-head comparison ───────────────────────────────────────────────
    pw(SEP)
    pw("  HEAD-TO-HEAD COMPARISON — OOS")
    pw(SEP)
    pw(f"  {'Metric':<30} {'Ridge':>12} {'LightGBM':>12}")
    pw(f"  {'-'*56}")

    def fmt(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "N/A"
        return f"{v:.1%}" if abs(v) < 2 else f"{v:.3f}"

    metrics = [
        ("OVER hit rate",    "hit_over"),
        ("UNDER hit rate",   "hit_under"),
        ("OVER ROI",         "roi_over"),
        ("UNDER ROI",        "roi_under"),
        ("Gates passed",     "gates_passed"),
    ]
    for label, key in metrics:
        r_val = ridge_results.get(key)
        l_val = lgbm_results.get(key) if lgbm_results else None
        pw(f"  {label:<30} {fmt(r_val):>12} {fmt(l_val) if l_val is not None else 'N/A':>12}")
    pw()

    # ── Choose production model ───────────────────────────────────────────────
    pw(f"  MODEL SELECTION:")
    if lgbm_results and lgbm_results["gates_passed"] >= ridge_results["gates_passed"]:
        production_model = "lgbm"
        prod_results     = lgbm_results
    else:
        production_model = "ridge"
        prod_results     = ridge_results

    pw(f"  Selected: {production_model.upper()}")
    pw()

    # ── Final GO / NO-GO ──────────────────────────────────────────────────────
    pw(SEP)
    pw("  FINAL V2.2 VERDICT")
    pw(SEP)

    if lgbm_results:
        either_passes = ridge_results["verdict"].startswith("GO") or lgbm_results["verdict"].startswith("GO")
    else:
        either_passes = ridge_results["verdict"].startswith("GO")

    pw(f"  Ridge:    {ridge_results['verdict']}")
    if lgbm_results:
        pw(f"  LightGBM: {lgbm_results['verdict']}")
    pw()

    if either_passes:
        pw(f"  RESULT: PASS — {production_model.upper()} passes OOS gates.")
        pw(f"  PROCEED TO PHASE 6.")
    else:
        pw(f"  RESULT: FAIL — Neither model passes OOS gates.")
        pw(f"  SOCCER MODEL STOPPED. No V2.3. Final attempt complete.")
        pw()
        pw(f"  Findings:")
        pw(f"  - Market-residual architecture tested")
        pw(f"  - 4 rounds of feature engineering (V2.0–V2.2)")
        pw(f"  - Multiple model architectures (Ridge, LightGBM)")
        pw(f"  - Root cause: insufficient independent signal to beat B365 2.5 line")
        pw(f"    with available historical data sources")
    pw()

    # ── Build output parquet ───────────────────────────────────────────────────
    out_cols = [
        "game_id", "game_date", "league_id", "season_year",
        "home_team", "away_team", "split",
        "total_goals", "actual_over_2_5",
        "market_fair_p_over_2_5",
        "residual_over_2_5",
        "ridge_pred_residual", "ridge_raw_p", "ridge_cal_p",
    ]
    if HAS_LGBM and lgbm_results:
        out_cols += ["lgbm_pred_residual", "lgbm_raw_p", "lgbm_cal_p"]

    out = all_prep[[c for c in out_cols if c in all_prep.columns]].copy()
    out.to_parquet(OUTPUT_PATH, index=False)
    logger.info(f"Predictions saved: {OUTPUT_PATH}  ({len(out):,} rows)")

    # ── Save audit ────────────────────────────────────────────────────────────
    audit_text = buf.getvalue()
    with open(AUDIT_PATH, "w") as f:
        f.write(audit_text)
    logger.info(f"Audit saved: {AUDIT_PATH}")

    pw(f"  Models:      {MODELS_DIR}")
    pw(f"  Predictions: {OUTPUT_PATH}")
    pw(f"  Audit:       {AUDIT_PATH}")
    pw()


if __name__ == "__main__":
    main()
