#!/usr/bin/env python3
"""
Phase 3: Ridge Baseline Models.

Two separate Ridge models:
  Model A: target = home_goals
  Model B: target = away_goals

Train on split=="train" with sample weights.
StandardScaler fit on train only.
Alpha tuned by MAE on validate set.

Usage:
    python3 -m soccer.phase3_train_ridge
"""

import io
import logging
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error

from soccer.config import DATA_DIR

logger = logging.getLogger(__name__)

FEATURE_TABLE_PATH   = os.path.join(DATA_DIR, "soccer_feature_table_v2_1.parquet")
MODEL_OUTPUTS_PATH   = os.path.join(DATA_DIR, "soccer_model_outputs.parquet")
MODELS_DIR           = os.path.join(os.path.dirname(DATA_DIR), "models")
AUDIT_PATH           = os.path.join(os.path.dirname(DATA_DIR), "phase3_model_audit.txt")

ALPHA_GRID = [0.1, 1.0, 10.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0]

SEP  = "═" * 72
SEP2 = "─" * 72

# ── Feature columns ───────────────────────────────────────────────────────────
# All xG features are normalized versions (from phase2 normalize_xg step).
# league_id encoded as is_bundesliga binary (0=EPL, 1=BUN).

FEATURE_COLS = [
    # League fixed effects
    "league_avg_goals_rolling_season",
    "league_avg_xg_rolling_season",
    "league_home_adv",
    "is_bundesliga",
    # Fix 3: league rolling-10 scoring environment
    "league_goals_rolling_10",
    "league_xg_rolling_10",
    # Fix 1: market total line anchor
    "market_total_line",
    # Attack / defence xG (home/away split, rolling 10, normalized)
    "home_xg_for_rolling_10",
    "home_xg_against_rolling_10",
    "away_xg_for_rolling_10",
    "away_xg_against_rolling_10",
    # Shot volume (rolling 10, home/away split)
    "home_shots_for_rolling_10",
    "home_shots_against_rolling_10",
    "away_shots_for_rolling_10",
    "away_shots_against_rolling_10",
    "home_shots_on_target_rolling_10",
    "away_shots_on_target_rolling_10",
    # Recent goals form (rolling 5, home/away split)
    "home_goals_scored_rolling_5",
    "home_goals_conceded_rolling_5",
    "away_goals_scored_rolling_5",
    "away_goals_conceded_rolling_5",
    # Fix 2: short window (3) — recent form
    "home_xg_for_rolling_3",
    "home_xg_against_rolling_3",
    "away_xg_for_rolling_3",
    "away_xg_against_rolling_3",
    "home_shots_for_rolling_3",
    "away_shots_for_rolling_3",
    "home_goals_scored_rolling_3",
    "away_goals_scored_rolling_3",
    # Fix 2: long window (15) — stable baseline
    "home_xg_for_rolling_15",
    "home_xg_against_rolling_15",
    "away_xg_for_rolling_15",
    "away_xg_against_rolling_15",
    # Rest / schedule congestion
    "home_days_rest",
    "away_days_rest",
    "home_matches_last_7",
    "away_matches_last_7",
    # Matchup interaction features
    "home_xg_mismatch",
    "away_xg_mismatch",
    "home_shot_mismatch",
    "away_shot_mismatch",
    "home_form_mismatch",
    "away_form_mismatch",
    # V2.1 lineup features
    "home_lineup_delta",
    "away_lineup_delta",
    "home_att_strength",
    "away_att_strength",
    "home_def_strength",
    "away_def_strength",
    "home_first_choice_gk_missing",
    "away_first_choice_gk_missing",
    "home_primary_attacker_missing",
    "away_primary_attacker_missing",
    "home_lineup_overlap_last_match",
    "away_lineup_overlap_last_match",
    "home_lineup_overlap_rolling_3",
    "away_lineup_overlap_rolling_3",
    "home_num_defenders",
    "away_num_defenders",
    "home_num_attackers",
    "away_num_attackers",
    "home_back_five",
    "away_back_five",
    "home_attack_delta_vs_away_defense",
    "away_attack_delta_vs_home_defense",
    "net_lineup_attack_edge",
    "net_lineup_defense_weakness",
]

# Lineup cols that need NaN imputation (first games have no prior history)
LINEUP_IMPUTE_ZERO = [
    "home_lineup_delta", "away_lineup_delta",
    "home_att_strength", "away_att_strength",
    "home_def_strength", "away_def_strength",
    "home_first_choice_gk_missing", "away_first_choice_gk_missing",
    "home_primary_attacker_missing", "away_primary_attacker_missing",
    "home_attack_delta_vs_away_defense", "away_attack_delta_vs_home_defense",
    "net_lineup_attack_edge", "net_lineup_defense_weakness",
]
LINEUP_IMPUTE_MEAN = [
    "home_lineup_overlap_last_match", "away_lineup_overlap_last_match",
    "home_lineup_overlap_rolling_3", "away_lineup_overlap_rolling_3",
]
LINEUP_IMPUTE_MEDIAN = [
    "home_num_defenders", "away_num_defenders",
    "home_num_attackers", "away_num_attackers",
    "home_back_five", "away_back_five",
]


# ── Data preparation ──────────────────────────────────────────────────────────

def prepare(df: pd.DataFrame, rest_medians: dict | None = None,
            lineup_impute: dict | None = None):
    """
    Add is_bundesliga flag. Impute days_rest and lineup NaNs.
    rest_medians:   dict with keys 'home_days_rest', 'away_days_rest'.
    lineup_impute:  dict of {col: fill_value} for lineup features.
    If None for either, compute from df (train set usage).
    Returns (df_prepared, rest_medians_used, lineup_impute_used).
    """
    df = df.copy()
    df["is_bundesliga"] = (df["league_id"] == "BUN").astype(float)

    if rest_medians is None:
        rest_medians = {
            "home_days_rest": df["home_days_rest"].median(),
            "away_days_rest": df["away_days_rest"].median(),
        }

    df["home_days_rest"] = df["home_days_rest"].fillna(rest_medians["home_days_rest"])
    df["away_days_rest"] = df["away_days_rest"].fillna(rest_medians["away_days_rest"])

    # Lineup NaN imputation (leakage-safe: values from train set only)
    if lineup_impute is None:
        lineup_impute = {}
        for col in LINEUP_IMPUTE_ZERO:
            lineup_impute[col] = 0.0
        for col in LINEUP_IMPUTE_MEAN:
            lineup_impute[col] = float(df[col].mean()) if col in df.columns else 0.0
        for col in LINEUP_IMPUTE_MEDIAN:
            lineup_impute[col] = float(df[col].median()) if col in df.columns else 0.0

    for col, fill in lineup_impute.items():
        if col in df.columns:
            df[col] = df[col].fillna(fill)

    return df, rest_medians, lineup_impute


# ── Alpha search ──────────────────────────────────────────────────────────────

def tune_alpha(
    X_train, y_train, w_train,
    X_val,   y_val,
    target_name: str,
    scaler: StandardScaler,
) -> tuple[float, dict]:
    """
    Grid search over ALPHA_GRID. Select alpha minimising MAE on validate set.
    Returns (best_alpha, results_dict).
    """
    results = {}
    for alpha in ALPHA_GRID:
        model = Ridge(alpha=alpha)
        model.fit(X_train, y_train, sample_weight=w_train)
        preds_val = model.predict(X_val)
        mae_val   = mean_absolute_error(y_val, preds_val)
        results[alpha] = mae_val

    best_alpha = min(results, key=results.get)
    return best_alpha, results


# ── Train final model ─────────────────────────────────────────────────────────

def train_model(X_train, y_train, w_train, alpha: float) -> Ridge:
    model = Ridge(alpha=alpha)
    model.fit(X_train, y_train, sample_weight=w_train)
    return model


# ── Diagnostics ───────────────────────────────────────────────────────────────

def diagnostics(
    df: pd.DataFrame,
    pred_home: np.ndarray,
    pred_away: np.ndarray,
    buf: io.StringIO,
) -> None:
    """
    Write full Phase 3 audit to buf. Checks all 6 diagnostic sections.
    """
    def p(s=""):
        print(s, file=buf)
        print(s)

    pred_total = pred_home + pred_away
    df = df.copy()
    df["pred_home"]  = pred_home
    df["pred_away"]  = pred_away
    df["pred_total"] = pred_total
    df["res_home"]   = pred_home  - df["home_goals"]
    df["res_away"]   = pred_away  - df["away_goals"]
    df["res_total"]  = pred_total - df["total_goals"]

    # ── 1. MAE by split ───────────────────────────────────────────────────────
    p(SEP)
    p("  PHASE 3 MODEL AUDIT")
    p(SEP)
    p()
    p("  DIAGNOSTIC 1: MAE by split")
    p(f"  {SEP2[:60]}")
    p(f"  {'Split':<12} {'MAE home':>10} {'MAE away':>10} {'MAE total':>10}")
    p(f"  {'-'*46}")

    mae_results = {}
    for split in ["train", "validate", "oos"]:
        sub = df[df["split"] == split]
        if sub.empty:
            continue
        mh = mean_absolute_error(sub["home_goals"],  sub["pred_home"])
        ma = mean_absolute_error(sub["away_goals"],  sub["pred_away"])
        mt = mean_absolute_error(sub["total_goals"], sub["pred_total"])
        mae_results[split] = {"home": mh, "away": ma, "total": mt}
        p(f"  {split:<12} {mh:>10.4f} {ma:>10.4f} {mt:>10.4f}")

    p()
    # Overfitting flag
    if "train" in mae_results and "validate" in mae_results:
        for tgt in ["home", "away", "total"]:
            gap = mae_results["validate"][tgt] - mae_results["train"][tgt]
            flag = "FAIL (overfit)" if gap > 0.15 else "PASS"
            p(f"  Overfit check MAE_{tgt}: val−train = {gap:+.4f}  →  {flag}")
    p()

    # ── 2. Mean calibration by split ─────────────────────────────────────────
    p("  DIAGNOSTIC 2: Mean calibration by split")
    p(f"  {SEP2[:60]}")
    p(f"  {'Split':<12} {'pred_home':>10} {'act_home':>10} {'drift_h':>8}  "
      f"{'pred_away':>10} {'act_away':>9} {'drift_a':>8}  "
      f"{'pred_tot':>9} {'act_tot':>8} {'drift_t':>8}")
    p(f"  {'-'*90}")
    for split in ["train", "validate", "oos"]:
        sub = df[df["split"] == split]
        if sub.empty:
            continue
        ph = sub["pred_home"].mean();  ah = sub["home_goals"].mean()
        pa = sub["pred_away"].mean();  aa = sub["away_goals"].mean()
        pt = sub["pred_total"].mean(); at = sub["total_goals"].mean()
        dh = ph - ah;  da = pa - aa;  dt = pt - at
        p(f"  {split:<12} {ph:>10.4f} {ah:>10.4f} {dh:>+8.4f}  "
          f"{pa:>10.4f} {aa:>9.4f} {da:>+8.4f}  "
          f"{pt:>9.4f} {at:>8.4f} {dt:>+8.4f}")

    p()
    val = df[df["split"] == "validate"]
    for label, col_pred, col_act in [
        ("home",  "pred_home",  "home_goals"),
        ("away",  "pred_away",  "away_goals"),
        ("total", "pred_total", "total_goals"),
    ]:
        drift = abs(val[col_pred].mean() - val[col_act].mean())
        flag  = "FAIL (mean drift > 0.15)" if drift > 0.15 else "PASS"
        p(f"  Mean drift {label} on validate: {drift:.4f}  →  {flag}")
    p()

    # ── 3. League-specific calibration (validate only) ────────────────────────
    p("  DIAGNOSTIC 3: League-specific calibration (validate set)")
    p(f"  {SEP2[:60]}")
    p(f"  {'League':<8} {'pred_tot':>9} {'act_tot':>8} {'drift':>8}  check")
    p(f"  {'-'*42}")
    for lid in ["EPL", "BUN"]:
        sub = df[(df["split"] == "validate") & (df["league_id"] == lid)]
        if sub.empty:
            continue
        pt = sub["pred_total"].mean();  at = sub["total_goals"].mean()
        drift = abs(pt - at)
        flag  = "FAIL (>0.15)" if drift > 0.15 else "PASS"
        p(f"  {lid:<8} {pt:>9.4f} {at:>8.4f} {drift:>+8.4f}  {flag}")
    p()

    # ── 4. Prediction range / quintile calibration (validate) ─────────────────
    p("  DIAGNOSTIC 4: Prediction range — validate set")
    p(f"  {SEP2[:60]}")
    pcts = [0, 10, 25, 50, 75, 90, 100]
    p(f"  {'Pct':<6} {'pred_total':>12} {'actual_total':>14}")
    p(f"  {'-'*36}")
    for pct in pcts:
        pv = np.percentile(val["pred_total"], pct)
        av = np.percentile(val["total_goals"], pct)
        p(f"  {pct:<6} {pv:>12.3f} {av:>14.3f}")
    pred_range   = np.percentile(val["pred_total"], 90) - np.percentile(val["pred_total"], 10)
    actual_range = np.percentile(val["total_goals"], 90) - np.percentile(val["total_goals"], 10)
    compression  = 1.0 - (pred_range / actual_range) if actual_range > 0 else 0
    flag = "FAIL (>30% compression)" if compression > 0.30 else "PASS"
    p()
    p(f"  10–90 range (pred):   {pred_range:.3f}")
    p(f"  10–90 range (actual): {actual_range:.3f}")
    p(f"  Compression:          {compression:.1%}  →  {flag}")
    p()

    # ── 5. Residual check ─────────────────────────────────────────────────────
    p("  DIAGNOSTIC 5: Residuals (pred − actual)")
    p(f"  {SEP2[:60]}")
    p(f"  {'Split':<12} {'mean_res_home':>14} {'std_res_home':>13} "
      f"{'mean_res_away':>14} {'std_res_away':>13} "
      f"{'mean_res_total':>15} {'std_res_total':>13}")
    p(f"  {'-'*90}")
    for split in ["train", "validate", "oos"]:
        sub = df[df["split"] == split]
        if sub.empty:
            continue
        mrh = sub["res_home"].mean();  srh = sub["res_home"].std()
        mra = sub["res_away"].mean();  sra = sub["res_away"].std()
        mrt = sub["res_total"].mean(); srt = sub["res_total"].std()
        p(f"  {split:<12} {mrh:>+14.4f} {srh:>13.4f} "
          f"{mra:>+14.4f} {sra:>13.4f} "
          f"{mrt:>+15.4f} {srt:>13.4f}")
    p()
    for split in ["validate", "oos"]:
        sub = df[df["split"] == split]
        if sub.empty:
            continue
        mrt = abs(sub["res_total"].mean())
        flag = "FAIL (>0.15)" if mrt > 0.15 else "PASS"
        p(f"  Mean total residual |{split}|: {mrt:.4f}  →  {flag}")
    p()

    # ── 6. Feature importance (informational) ────────────────────────────────
    # Reported by caller


def print_feature_importance(
    model_home: Ridge,
    model_away: Ridge,
    scaler: StandardScaler,
    buf: io.StringIO,
) -> None:
    def p(s=""):
        print(s, file=buf)
        print(s)

    p(f"  DIAGNOSTIC 6: Top 10 features by scaled coefficient magnitude")
    p(f"  {SEP2[:60]}")

    for name, model in [("Model A (home_goals)", model_home), ("Model B (away_goals)", model_away)]:
        coefs = pd.Series(model.coef_, index=FEATURE_COLS)
        top10 = coefs.abs().sort_values(ascending=False).head(10)
        p(f"  {name}:")
        p(f"    {'Feature':<45} {'Coef':>8}")
        p(f"    {'-'*55}")
        for feat, absv in top10.items():
            coef = coefs[feat]
            p(f"    {feat:<45} {coef:>+8.4f}")
        p()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DATA_DIR), exist_ok=True)

    # ── Load feature table ────────────────────────────────────────────────────
    ft = pd.read_parquet(FEATURE_TABLE_PATH)
    logger.info(f"Feature table: {len(ft):,} rows")

    # Confirm xG features are normalized (not raw)
    logger.info(f"home_xg_for_rolling_10 sample mean: {ft['home_xg_for_rolling_10'].mean():.4f} "
                f"(raw would be ~1.5–2.0; normalized ~same range but league-adjusted)")

    # ── Prepare (encode league, impute rest) ─────────────────────────────────
    train_raw = ft[ft["split"] == "train"].copy()
    val_raw   = ft[ft["split"] == "validate"].copy()
    oos_raw   = ft[ft["split"] == "oos"].copy()

    # Compute rest medians + lineup impute values from train only
    train_prep, rest_medians, lineup_impute = prepare(train_raw)
    val_prep,   _, _  = prepare(val_raw,  rest_medians, lineup_impute)
    oos_prep,   _, _  = prepare(oos_raw,  rest_medians, lineup_impute)
    all_prep,   _, _  = prepare(ft,       rest_medians, lineup_impute)

    X_train = train_prep[FEATURE_COLS].values
    X_val   = val_prep[FEATURE_COLS].values
    X_oos   = oos_prep[FEATURE_COLS].values
    X_all   = all_prep[FEATURE_COLS].values

    y_train_home  = train_prep["home_goals"].values
    y_train_away  = train_prep["away_goals"].values
    w_train       = train_prep["sample_weight"].values

    y_val_home    = val_prep["home_goals"].values
    y_val_away    = val_prep["away_goals"].values

    # ── Scaler: fit on train only ─────────────────────────────────────────────
    scaler_home = StandardScaler()
    scaler_away = StandardScaler()

    X_train_sh = scaler_home.fit_transform(X_train)
    X_train_sa = scaler_away.fit_transform(X_train)

    X_val_sh   = scaler_home.transform(X_val)
    X_val_sa   = scaler_away.transform(X_val)

    X_oos_sh   = scaler_home.transform(X_oos)
    X_oos_sa   = scaler_away.transform(X_oos)

    X_all_sh   = scaler_home.transform(X_all)
    X_all_sa   = scaler_away.transform(X_all)

    logger.info("Scalers fit on train set only.")

    # ── Alpha grid search — Model A (home) ────────────────────────────────────
    best_alpha_home, alpha_results_home = tune_alpha(
        X_train_sh, y_train_home, w_train,
        X_val_sh,   y_val_home,
        "home_goals", scaler_home,
    )
    logger.info(f"Model A best alpha: {best_alpha_home}  (validate MAE: {alpha_results_home[best_alpha_home]:.4f})")

    # ── Alpha grid search — Model B (away) ────────────────────────────────────
    best_alpha_away, alpha_results_away = tune_alpha(
        X_train_sa, y_train_away, w_train,
        X_val_sa,   y_val_away,
        "away_goals", scaler_away,
    )
    logger.info(f"Model B best alpha: {best_alpha_away}  (validate MAE: {alpha_results_away[best_alpha_away]:.4f})")

    # ── Train final models ────────────────────────────────────────────────────
    model_home = train_model(X_train_sh, y_train_home, w_train, best_alpha_home)
    model_away = train_model(X_train_sa, y_train_away, w_train, best_alpha_away)

    # ── Predictions on all splits ─────────────────────────────────────────────
    pred_home_all = model_home.predict(X_all_sh)
    pred_away_all = model_away.predict(X_all_sa)

    # ── Mean calibration offsets (computed from validate set only) ────────────
    # offset = mean(actual) - mean(predicted) on validate
    # Applied additively to all predictions — models not refitted.
    val_mask      = all_prep["split"] == "validate"
    pred_home_val = pred_home_all[val_mask.values]
    pred_away_val = pred_away_all[val_mask.values]
    act_home_val  = val_prep["home_goals"].values
    act_away_val  = val_prep["away_goals"].values

    calibration_factor = 0.5

    offset_home = calibration_factor * float(act_home_val.mean() - pred_home_val.mean())
    offset_away = calibration_factor * float(act_away_val.mean() - pred_away_val.mean())

    logger.info(f"Calibration factor: {calibration_factor}  "
                f"offset_home: {offset_home:+.4f}  offset_away: {offset_away:+.4f}")

    pred_home_cal = pred_home_all + offset_home
    pred_away_cal = pred_away_all + offset_away

    # Persist offsets + factor for live inference pipeline
    offsets = {
        "calibration_factor": calibration_factor,
        "offset_home":        offset_home,
        "offset_away":        offset_away,
    }
    with open(os.path.join(MODELS_DIR, "calibration_offsets.pkl"), "wb") as f:
        pickle.dump(offsets, f)

    # ── Build model outputs DataFrame ────────────────────────────────────────
    outputs = all_prep[[
        "game_id", "game_date", "league_id",
        "home_team", "away_team",
        "split", "sample_weight",
        "home_goals", "away_goals", "total_goals",
    ]].copy()

    outputs["lambda_home"]             = pred_home_all
    outputs["lambda_away"]             = pred_away_all
    outputs["lambda_total"]            = pred_home_all + pred_away_all
    outputs["lambda_home_calibrated"]  = pred_home_cal
    outputs["lambda_away_calibrated"]  = pred_away_cal
    outputs["lambda_total_calibrated"] = pred_home_cal + pred_away_cal
    outputs = outputs.rename(columns={
        "home_goals":  "actual_home_goals",
        "away_goals":  "actual_away_goals",
        "total_goals": "actual_total_goals",
    })

    # ── Diagnostics ───────────────────────────────────────────────────────────
    buf = io.StringIO()

    def pbuf(s=""):
        print(s, file=buf)

    pbuf(SEP)
    pbuf("  PHASE 3 MODEL AUDIT")
    pbuf(SEP)
    pbuf()
    pbuf("  MODEL CONFIGURATION")
    pbuf(f"  {SEP2[:60]}")
    pbuf(f"  Features:          {len(FEATURE_COLS)}")
    pbuf(f"  Train rows:        {len(train_prep):,}")
    pbuf(f"  Validate rows:     {len(val_prep):,}")
    pbuf(f"  OOS rows:          {len(oos_prep):,}")
    pbuf()
    pbuf(f"  Alpha grid search results — Model A (home_goals):")
    for a, mae in sorted(alpha_results_home.items()):
        mark = " ← selected" if a == best_alpha_home else ""
        pbuf(f"    alpha={a:<8} validate MAE = {mae:.4f}{mark}")
    pbuf()
    pbuf(f"  Alpha grid search results — Model B (away_goals):")
    for a, mae in sorted(alpha_results_away.items()):
        mark = " ← selected" if a == best_alpha_away else ""
        pbuf(f"    alpha={a:<8} validate MAE = {mae:.4f}{mark}")
    pbuf()
    pbuf(f"  Selected: Model A alpha = {best_alpha_home}  |  Model B alpha = {best_alpha_away}")
    pbuf()
    pbuf(f"  FIX 2 — CALIBRATION OFFSETS (halved, computed from validate set)")
    pbuf(f"  {SEP2[:60]}")
    pbuf(f"  calibration_factor       = {calibration_factor}")
    pbuf(f"  validate_offset_home_raw = {offset_home/calibration_factor:+.4f}  (full validate gap)")
    pbuf(f"  validate_offset_away_raw = {offset_away/calibration_factor:+.4f}  (full validate gap)")
    pbuf(f"  offset_home applied      = {offset_home:+.4f}  (factor × raw)")
    pbuf(f"  offset_away applied      = {offset_away:+.4f}  (factor × raw)")
    pbuf(f"  Applied additively to all predictions. Models not refitted.")
    pbuf(f"  Saved: soccer/models/calibration_offsets.pkl  (includes calibration_factor)")
    pbuf()

    # Diagnostics operate on CALIBRATED predictions
    diag_df = outputs.rename(columns={
        "actual_home_goals": "home_goals",
        "actual_away_goals": "away_goals",
        "actual_total_goals": "total_goals",
        "lambda_home_calibrated":  "pred_home",
        "lambda_away_calibrated":  "pred_away",
        "lambda_total_calibrated": "pred_total",
    })
    diag_df["res_total"] = diag_df["pred_total"] - diag_df["total_goals"]
    diag_df["res_home"]  = diag_df["pred_home"]  - diag_df["home_goals"]
    diag_df["res_away"]  = diag_df["pred_away"]  - diag_df["away_goals"]

    def pw(s=""):
        pbuf(s)
        print(s)

    val = diag_df[diag_df["split"] == "validate"]

    # ── Diag 1: MAE ──────────────────────────────────────────────────────────
    pw(f"  DIAGNOSTIC 1: MAE by split")
    pw(f"  {SEP2[:60]}")
    pw(f"  {'Split':<12} {'MAE home':>10} {'MAE away':>10} {'MAE total':>10}")
    pw(f"  {'-'*46}")
    mae_results = {}
    for split in ["train", "validate", "oos"]:
        sub = diag_df[diag_df["split"] == split]
        if sub.empty: continue
        mh = mean_absolute_error(sub["home_goals"], sub["pred_home"])
        ma = mean_absolute_error(sub["away_goals"], sub["pred_away"])
        mt = mean_absolute_error(sub["total_goals"], sub["pred_total"])
        mae_results[split] = {"home": mh, "away": ma, "total": mt}
        pw(f"  {split:<12} {mh:>10.4f} {ma:>10.4f} {mt:>10.4f}")
    pw()
    if "train" in mae_results and "validate" in mae_results:
        for tgt in ["home", "away", "total"]:
            gap  = mae_results["validate"][tgt] - mae_results["train"][tgt]
            flag = "FAIL (overfit)" if gap > 0.15 else "PASS"
            pw(f"  Overfit check MAE_{tgt}: val−train = {gap:+.4f}  →  {flag}")
    pw()

    # ── Diag 2: Mean calibration ─────────────────────────────────────────────
    pw(f"  DIAGNOSTIC 2: Mean calibration by split")
    pw(f"  {SEP2[:60]}")
    pw(f"  {'Split':<12} {'pred_h':>8} {'act_h':>7} {'drift_h':>8}  "
       f"{'pred_a':>8} {'act_a':>7} {'drift_a':>8}  "
       f"{'pred_t':>8} {'act_t':>7} {'drift_t':>8}")
    pw(f"  {'-'*82}")
    for split in ["train", "validate", "oos"]:
        sub = diag_df[diag_df["split"] == split]
        if sub.empty: continue
        ph = sub["pred_home"].mean();  ah = sub["home_goals"].mean()
        pa = sub["pred_away"].mean();  aa = sub["away_goals"].mean()
        pt = sub["pred_total"].mean(); at = sub["total_goals"].mean()
        pw(f"  {split:<12} {ph:>8.4f} {ah:>7.4f} {(ph-ah):>+8.4f}  "
           f"{pa:>8.4f} {aa:>7.4f} {(pa-aa):>+8.4f}  "
           f"{pt:>8.4f} {at:>7.4f} {(pt-at):>+8.4f}")
    pw()
    thresholds = {"home": 0.12, "away": 0.12, "total": 0.12}
    for label, col_p, col_a in [("home","pred_home","home_goals"),("away","pred_away","away_goals"),("total","pred_total","total_goals")]:
        drift = abs(val[col_p].mean() - val[col_a].mean())
        thr   = thresholds[label]
        flag  = f"FAIL (>{thr})" if drift > thr else "PASS"
        pw(f"  Mean drift {label} on validate: {drift:.4f}  (threshold ±{thr})  →  {flag}")
    pw()

    # ── Diag 3: League calibration ────────────────────────────────────────────
    pw(f"  DIAGNOSTIC 3: League-specific calibration (validate set)")
    pw(f"  {SEP2[:60]}")
    pw(f"  {'League':<8} {'pred_h':>8} {'act_h':>7} {'d_h':>6}  "
       f"{'pred_a':>8} {'act_a':>7} {'d_a':>6}  "
       f"{'pred_t':>8} {'act_t':>7} {'drift_t':>8}  check")
    pw(f"  {'-'*76}")
    for lid in ["EPL", "BUN"]:
        sub = diag_df[(diag_df["split"] == "validate") & (diag_df["league_id"] == lid)]
        if sub.empty: continue
        ph = sub["pred_home"].mean();  ah = sub["home_goals"].mean()
        pa = sub["pred_away"].mean();  aa = sub["away_goals"].mean()
        pt = sub["pred_total"].mean(); at = sub["total_goals"].mean()
        drift_t = abs(pt - at)
        flag = "FAIL (>0.15)" if drift_t > 0.15 else "PASS"
        pw(f"  {lid:<8} {ph:>8.4f} {ah:>7.4f} {(ph-ah):>+6.4f}  "
           f"{pa:>8.4f} {aa:>7.4f} {(pa-aa):>+6.4f}  "
           f"{pt:>8.4f} {at:>7.4f} {drift_t:>+8.4f}  {flag}")
    pw()

    # ── Diag 4: Prediction range ──────────────────────────────────────────────
    pw(f"  DIAGNOSTIC 4: Prediction range distribution (validate set)")
    pw(f"  {SEP2[:60]}")
    pcts = [0, 10, 25, 50, 75, 90, 100]
    pw(f"  {'Pct':<6} {'pred_total':>12} {'actual_total':>14}")
    pw(f"  {'-'*36}")
    for pct in pcts:
        pv = np.percentile(val["pred_total"], pct)
        av = np.percentile(val["actual_total_goals"] if "actual_total_goals" in val.columns else val["total_goals"], pct)
        pw(f"  {pct:<6} {pv:>12.3f} {av:>14.3f}")
    pred_range   = np.percentile(val["pred_total"], 90) - np.percentile(val["pred_total"], 10)
    actual_range = np.percentile(val["total_goals"], 90) - np.percentile(val["total_goals"], 10)
    compression  = 1.0 - (pred_range / actual_range) if actual_range > 0 else 0
    flag = "FAIL (>30% compression)" if compression > 0.30 else "PASS"
    pw()
    pw(f"  10–90 pred range:   {pred_range:.3f}")
    pw(f"  10–90 actual range: {actual_range:.3f}")
    pw(f"  Compression:        {compression:.1%}  →  {flag}")
    pw()

    # ── Diag 5: Residuals ────────────────────────────────────────────────────
    pw(f"  DIAGNOSTIC 5: Residuals (pred − actual)")
    pw(f"  {SEP2[:60]}")
    pw(f"  {'Split':<12} {'mean_res_h':>12} {'std_h':>8} {'mean_res_a':>12} {'std_a':>8} {'mean_res_t':>12} {'std_t':>8}")
    pw(f"  {'-'*76}")
    for split in ["train", "validate", "oos"]:
        sub = diag_df[diag_df["split"] == split]
        if sub.empty: continue
        pw(f"  {split:<12} {sub['res_home'].mean():>+12.4f} {sub['res_home'].std():>8.4f} "
           f"{sub['res_away'].mean():>+12.4f} {sub['res_away'].std():>8.4f} "
           f"{sub['res_total'].mean():>+12.4f} {sub['res_total'].std():>8.4f}")
    pw()
    for split in ["validate", "oos"]:
        sub = diag_df[diag_df["split"] == split]
        if sub.empty: continue
        mrt = abs(sub["res_total"].mean())
        flag = "FAIL (>0.12)" if mrt > 0.12 else "PASS"
        pw(f"  Mean |total residual| on {split}: {mrt:.4f}  (threshold ±0.12)  →  {flag}")
    pw()

    # ── Diag 6: Feature importance ────────────────────────────────────────────
    pw(f"  DIAGNOSTIC 6: Top 15 features by scaled coefficient magnitude")
    pw(f"  {SEP2[:60]}")
    for name, model in [("Model A (home_goals)", model_home), ("Model B (away_goals)", model_away)]:
        coefs = pd.Series(model.coef_, index=FEATURE_COLS)
        top15 = coefs.abs().sort_values(ascending=False).head(15)
        pw(f"  {name}  [alpha={best_alpha_home if 'home' in name else best_alpha_away}]:")
        pw(f"    {'Feature':<45} {'Coef':>8}")
        pw(f"    {'-'*55}")
        for feat in top15.index:
            pw(f"    {feat:<45} {coefs[feat]:>+8.4f}")
        # Separately: any lineup features in top 15?
        lineup_feats_in_top = [f for f in top15.index if any(
            f.startswith(p) for p in ["home_lineup", "away_lineup", "home_att_s", "away_att_s",
                                       "home_def_s", "away_def_s", "home_first_choice", "away_first_choice",
                                       "home_primary", "away_primary", "home_num_", "away_num_",
                                       "home_back", "away_back", "net_lineup", "home_attack_delta", "away_attack_delta"]
        )]
        if lineup_feats_in_top:
            pw(f"    *** Lineup features in top 15: {lineup_feats_in_top}")
        else:
            pw(f"    (no lineup features in top 15)")
        pw()

    audit_text = buf.getvalue()

    # ── Save audit ────────────────────────────────────────────────────────────
    with open(AUDIT_PATH, "w") as f:
        f.write(audit_text)
    logger.info(f"Audit saved → {AUDIT_PATH}")

    # ── Save models ───────────────────────────────────────────────────────────
    with open(os.path.join(MODELS_DIR, "ridge_home_model.pkl"), "wb") as f:
        pickle.dump(model_home, f)
    with open(os.path.join(MODELS_DIR, "ridge_away_model.pkl"), "wb") as f:
        pickle.dump(model_away, f)
    with open(os.path.join(MODELS_DIR, "scaler_home.pkl"), "wb") as f:
        pickle.dump(scaler_home, f)
    with open(os.path.join(MODELS_DIR, "scaler_away.pkl"), "wb") as f:
        pickle.dump(scaler_away, f)

    # Also save rest medians + lineup impute for inference
    with open(os.path.join(MODELS_DIR, "rest_medians.pkl"), "wb") as f:
        pickle.dump(rest_medians, f)
    with open(os.path.join(MODELS_DIR, "lineup_impute.pkl"), "wb") as f:
        pickle.dump(lineup_impute, f)

    logger.info("Models and scalers saved.")

    # ── Save model outputs ────────────────────────────────────────────────────
    outputs.to_parquet(MODEL_OUTPUTS_PATH, index=False)
    logger.info(f"Model outputs → {MODEL_OUTPUTS_PATH}  ({len(outputs):,} rows)")

    print(f"\n  Models saved: {MODELS_DIR}")
    print(f"  Outputs:      {MODEL_OUTPUTS_PATH}")
    print(f"  Audit:        {AUDIT_PATH}\n")


if __name__ == "__main__":
    main()
