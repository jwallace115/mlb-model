"""
Phase 9 — Heteroskedastic Variance Model
==========================================
Replaces constant σ=4.361 with a per-game σ estimated from variance drivers.

Architecture:
  1. Compute training residuals from Phase 9 baseline mean model
  2. Fit Ridge on |residuals| using variance driver features (train 2022+2023)
  3. Convert E[|residual|] predictions → σ_game via divide by sqrt(2/π)
  4. Clip σ_game to minimum 3.0 runs
  5. Evaluate: 80% CI coverage, calibration buckets, ROI/tiers vs constant σ

Variance driver candidates:
  wind_speed, wind_out_flag
  home/away_sp_flyball_pct (from flyball cache)
  home/away_bp_delta_exposure (quality gap × bullpen innings)
  temperature, park_factor_hr
  home/away_sp_bb_pct
  expected_bullpen_innings (home_bp_proj_inn + away_bp_proj_inn)

Usage:
    python3 sim/phase9_variance.py
"""

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR.parent))

from sim.phase6_interactions import (
    TRAIN_YEARS, VALIDATE_YEAR, OOS_YEAR, ALPHAS,
    add_flyball_wind_interaction,
)
from sim.phase8_step3_retrain import (
    load_and_merge, load_market, predict, train_sigma, evaluate_model,
)

REPORT_PATH      = SIM_DIR / "reports" / "phase9_variance.txt"
VARIANCE_MODEL   = SIM_DIR / "data"    / "phase9_variance_model.pkl"
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

SIGMA_MIN   = 3.0          # floor: never predict less uncertainty than this
N_SIMS      = 10_000
SEED        = 42
SQRT_2_PI   = np.sqrt(2.0 / np.pi)   # E[|X|] = σ × sqrt(2/π) for X~N(0,σ²)

# ---------------------------------------------------------------------------
# Variance driver features
# ---------------------------------------------------------------------------
VARIANCE_FEATURES = [
    "wind_speed",
    "wind_out_flag",
    "home_sp_fb_pct",       # flyball % (added by add_flyball_wind_interaction)
    "away_sp_fb_pct",
    "home_bp_delta_exposure",
    "away_bp_delta_exposure",
    "temperature",
    "park_factor_hr",
    "home_sp_bb_pct",
    "away_sp_bb_pct",
    "expected_bullpen_innings",
    "dome_flag",            # explicitly zero-variance indicator
]


# ---------------------------------------------------------------------------
# Feature engineering for variance model
# ---------------------------------------------------------------------------

def add_variance_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # wind_out_flag: open roof + effective wind > 3 (consistent with phase6)
    df["wind_out_flag"] = (
        (df["roof_status"] == "open") & (df["wind_factor_effective"] > 3)
    ).astype(float)
    # dome_flag
    df["dome_flag"] = (df["roof_status"] == "dome").astype(float)
    # total expected bullpen innings
    df["expected_bullpen_innings"] = df["home_bp_proj_inn"] + df["away_bp_proj_inn"]
    # flyball pct already added by load_and_merge (via add_flyball_wind_interaction)
    return df


# ---------------------------------------------------------------------------
# Ridge variance model
# ---------------------------------------------------------------------------

def fit_variance_model(df_train: pd.DataFrame,
                        abs_resid: np.ndarray) -> Pipeline:
    X = df_train[VARIANCE_FEATURES].copy()
    for c in VARIANCE_FEATURES:
        if X[c].isna().any():
            X[c] = X[c].fillna(X[c].median())
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  RidgeCV(alphas=ALPHAS, cv=5)),
    ])
    pipe.fit(X.values, abs_resid)
    return pipe


def predict_sigma(df: pd.DataFrame,
                   varpipe: Pipeline,
                   sigma_floor: float = SIGMA_MIN) -> np.ndarray:
    """
    Predict per-game sigma:
      1. Ridge predicts E[|residual|]
      2. Divide by sqrt(2/π) to recover σ
      3. Clip to sigma_floor
    """
    X = df[VARIANCE_FEATURES].copy()
    for c in VARIANCE_FEATURES:
        if X[c].isna().any():
            X[c] = X[c].fillna(X[c].median())
    pred_abs_resid = varpipe.predict(X.values)
    sigma_game = pred_abs_resid / SQRT_2_PI
    return np.clip(sigma_game, sigma_floor, None)


# ---------------------------------------------------------------------------
# Monte Carlo simulation with per-game sigma
# ---------------------------------------------------------------------------

def simulate_with_sigma(preds: np.ndarray,
                          sigma_arr: np.ndarray,
                          line: float,
                          n_sims: int = N_SIMS,
                          seed: int = SEED) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (p_over, ci_lo, ci_hi) arrays.
    sigma_arr can be scalar (constant) or array (per-game).
    """
    rng = np.random.default_rng(seed)
    n   = len(preds)
    if np.isscalar(sigma_arr):
        sigma_arr = np.full(n, float(sigma_arr))

    p_over = np.empty(n)
    ci_lo  = np.empty(n)
    ci_hi  = np.empty(n)
    alpha  = 0.10   # 80% CI

    for i in range(n):
        draws     = rng.normal(preds[i], sigma_arr[i], n_sims)
        p_over[i] = (draws > line).mean()
        ci_lo[i]  = np.percentile(draws, alpha * 100)
        ci_hi[i]  = np.percentile(draws, (1 - alpha) * 100)

    return p_over, ci_lo, ci_hi


# ---------------------------------------------------------------------------
# Calibration table
# ---------------------------------------------------------------------------

def calibration_table(actual: np.ndarray,
                        p_over: np.ndarray,
                        line: float,
                        n_bins: int = 10) -> pd.DataFrame:
    actual_over = (actual > line).astype(float)
    bins   = np.linspace(0, 1, n_bins + 1)
    labels = [f"{bins[i]:.2f}–{bins[i+1]:.2f}" for i in range(n_bins)]
    df = pd.DataFrame({"p_over": p_over, "actual_over": actual_over})
    df["bin"] = pd.cut(df["p_over"], bins=bins, labels=labels, include_lowest=True)
    result = (
        df.groupby("bin", observed=False)
        .agg(n=("actual_over","count"),
             pred_p=("p_over","mean"),
             actual_p=("actual_over","mean"))
        .reset_index()
    )
    result["error"] = result["pred_p"] - result["actual_p"]
    result["brier"] = ((df.groupby("bin", observed=False)
                         .apply(lambda g: ((g["p_over"] - g["actual_over"])**2).mean(),
                                include_groups=False))
                       .reset_index(name="brier")["brier"])
    return result


def ci_coverage(actual: np.ndarray,
                 ci_lo: np.ndarray,
                 ci_hi: np.ndarray) -> float:
    return float(((actual >= ci_lo) & (actual <= ci_hi)).mean())


# ---------------------------------------------------------------------------
# ROI simulation with per-game sigma
# ---------------------------------------------------------------------------

def roi_sim_sigma(preds: np.ndarray,
                   sigma_arr: np.ndarray,
                   df_eval: pd.DataFrame,
                   df_market: pd.DataFrame,
                   bet_edge: float, bet_prob: float,
                   win_unit: float) -> dict:
    from config import WIN_UNIT, BET_EDGE, BET_PROB
    bet_edge  = bet_edge  or BET_EDGE
    bet_prob  = bet_prob  or BET_PROB
    win_unit  = win_unit  or WIN_UNIT

    merged = df_eval[["game_pk","actual_total","season"]].copy()
    merged["pred"]  = preds
    merged["sigma"] = sigma_arr
    merged = merged.merge(df_market, on="game_pk", how="inner")
    merged = merged.dropna(subset=["close_total"])

    results = []
    rng = np.random.default_rng(SEED)

    for _, row in merged.iterrows():
        line   = row["close_total"]
        pred   = row["pred"]
        sig    = row["sigma"]
        actual = row["actual_total"]
        edge   = abs(pred - line)
        if edge < bet_edge:
            continue
        draws = rng.normal(pred, sig, N_SIMS)
        if pred > line:
            p_side = float((draws > line).mean())
            if p_side < bet_prob: continue
            won = actual > line
        else:
            p_side = float((draws < line).mean())
            if p_side < bet_prob: continue
            won = actual <= line
        results.append({"season": int(row["season"]), "won": bool(won)})

    if not results:
        return dict(n=0, win_pct=float("nan"), roi=float("nan"), by_year={})

    df_r  = pd.DataFrame(results)
    total = len(df_r); wins = df_r["won"].sum()
    roi   = float((wins * WIN_UNIT - (total - wins)) / total * 100)
    by_year = {}
    for yr, grp in df_r.groupby("season"):
        w = grp["won"].sum(); n = len(grp)
        by_year[int(yr)] = dict(n=n, win_pct=float(w/n),
                                 roi=float((w*WIN_UNIT-(n-w))/n*100))
    return dict(n=total, win_pct=float(wins/total), roi=roi, by_year=by_year)


def tier_sim_sigma(preds: np.ndarray, sigma_arr: np.ndarray,
                    df_eval: pd.DataFrame, df_market: pd.DataFrame) -> list[dict]:
    from config import (WATCHLIST_EDGE, BET_EDGE, STRONG_EDGE,
                        WATCHLIST_PROB, BET_PROB, STRONG_PROB, WIN_UNIT)
    merged = df_eval[["game_pk","actual_total"]].copy()
    merged["pred"]  = preds
    merged["sigma"] = sigma_arr
    merged = merged.merge(df_market, on="game_pk", how="inner")
    merged = merged.dropna(subset=["close_total"])

    rows = []
    rng  = np.random.default_rng(SEED)
    for _, row in merged.iterrows():
        line = row["close_total"]; pred = row["pred"]; sig = row["sigma"]
        actual = row["actual_total"]; edge = abs(pred - line)
        draws = rng.normal(pred, sig, N_SIMS)
        if pred > line: p_side = float((draws > line).mean()); won = actual > line
        else:           p_side = float((draws < line).mean()); won = actual <= line
        if   edge >= STRONG_EDGE and p_side >= STRONG_PROB:    tier = "STRONG"
        elif edge >= BET_EDGE    and p_side >= BET_PROB:       tier = "BET"
        elif edge >= WATCHLIST_EDGE and p_side >= WATCHLIST_PROB: tier = "WATCHLIST"
        else: continue
        rows.append({"tier": tier, "won": won})

    if not rows: return []
    df_t = pd.DataFrame(rows)
    out  = []
    for tier in ["STRONG","BET","WATCHLIST"]:
        sub = df_t[df_t["tier"]==tier]
        if not len(sub): continue
        w = sub["won"].sum(); n = len(sub)
        out.append(dict(tier=tier, n=n, win_pct=float(w/n),
                        roi=float((w*(100/110)-(n-w))/n*100)))
    return out


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def pln(lo: list, s: str = ""):
    print(s); lo.append(s)


def print_calibration_compare(cal_const: pd.DataFrame, cal_game: pd.DataFrame,
                                tag: str, lo: list):
    pln(lo)
    pln(lo, f"  Calibration — {tag}:")
    pln(lo, f"  {'Bin':>14}  {'N':>5}  "
            f"{'Pred P':>7}  {'Act% const':>10}  {'Err const':>9}  "
            f"{'Act% game':>10}  {'Err game':>9}")
    pln(lo, f"  {'─'*14}  {'─'*5}  {'─'*7}  {'─'*10}  {'─'*9}  {'─'*10}  {'─'*9}")
    for (_, rc), (_, rg) in zip(cal_const.iterrows(), cal_game.iterrows()):
        if rc["n"] == 0: continue
        pln(lo, f"  {str(rc['bin']):>14}  {rc['n']:>5}  "
                f"{rc['pred_p']:>7.3f}  {rc['actual_p']:>10.3f}  {rc['error']:>+9.3f}  "
                f"{rg['actual_p']:>10.3f}  {rg['error']:>+9.3f}")


def print_sigma_segments(df_eval: pd.DataFrame,
                          sigma_game: np.ndarray, lo: list,
                          label: str = "2025 OOS"):
    """Show top/bottom sigma games with their variance driver values."""
    df = df_eval.copy()
    df["sigma_game"] = sigma_game

    top10    = df.nlargest(10, "sigma_game")[
        ["date","home_team","away_team","sigma_game",
         "wind_speed","wind_out_flag","dome_flag",
         "temperature","home_sp_fb_pct","away_sp_fb_pct",
         "expected_bullpen_innings","park_factor_hr"]
    ]
    bot10    = df.nsmallest(10, "sigma_game")[
        ["date","home_team","away_team","sigma_game",
         "wind_speed","wind_out_flag","dome_flag",
         "temperature","home_sp_fb_pct","away_sp_fb_pct",
         "expected_bullpen_innings","park_factor_hr"]
    ]

    pln(lo)
    pln(lo, f"  Top-10 highest σ_game ({label}):")
    pln(lo, f"  {'Date':<12}  {'Home':<5}  {'Away':<5}  "
            f"{'σ_game':>7}  {'WindSpd':>7}  {'WndOut':>6}  "
            f"{'Dome':>4}  {'Temp':>5}  {'HmFB%':>5}  {'AwFB%':>5}  "
            f"{'ExpBP':>5}  {'PkHR':>5}")
    pln(lo, "  " + "─"*90)
    for _, r in top10.iterrows():
        pln(lo, f"  {str(r['date']):<12}  {r['home_team']:<5}  {r['away_team']:<5}  "
                f"{r['sigma_game']:>7.3f}  {r['wind_speed']:>7.1f}  {r['wind_out_flag']:>6.0f}  "
                f"{r['dome_flag']:>4.0f}  {r['temperature']:>5.0f}  "
                f"{r['home_sp_fb_pct']:>5.3f}  {r['away_sp_fb_pct']:>5.3f}  "
                f"{r['expected_bullpen_innings']:>5.1f}  {r['park_factor_hr']:>5.0f}")

    pln(lo)
    pln(lo, f"  Top-10 lowest σ_game ({label}) — tightest distributions:")
    pln(lo, "  " + "─"*90)
    for _, r in bot10.iterrows():
        pln(lo, f"  {str(r['date']):<12}  {r['home_team']:<5}  {r['away_team']:<5}  "
                f"{r['sigma_game']:>7.3f}  {r['wind_speed']:>7.1f}  {r['wind_out_flag']:>6.0f}  "
                f"{r['dome_flag']:>4.0f}  {r['temperature']:>5.0f}  "
                f"{r['home_sp_fb_pct']:>5.3f}  {r['away_sp_fb_pct']:>5.3f}  "
                f"{r['expected_bullpen_innings']:>5.1f}  {r['park_factor_hr']:>5.0f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    lo: list[str] = []

    def hdr(s=""):
        pln(lo, s)

    hdr("=" * 74)
    hdr("PHASE 9 — HETEROSKEDASTIC VARIANCE MODEL")
    hdr("=" * 74)
    hdr()
    hdr("  Replace constant σ=4.361 with per-game σ from variance drivers.")
    hdr(f"  σ_game = max({SIGMA_MIN:.1f}, Ridge(|residuals|) / sqrt(2/π))")
    hdr()

    # ── Load ──────────────────────────────────────────────────────────────────
    print("Loading data...", flush=True)
    df        = load_and_merge()
    df_market = load_market()

    # Phase 9 baseline features (from locked model)
    with open(SIM_DIR / "data" / "phase9_baseline_model.pkl", "rb") as f:
        bundle = pickle.load(f)
    pipe_mean = bundle["pipeline"]
    features  = bundle["features"]
    sigma_const = bundle["sigma"]
    hdr(f"  Loaded Phase 9 baseline: {len(features)} features, "
        f"α={bundle['alpha']:.0f}, σ_const={sigma_const:.4f}")
    hdr()

    # Add variance-specific features
    for yr in [2022, 2023, 2024, 2025]:
        mask = df["season"] == yr
        sub  = df[mask].copy()
        sub  = add_variance_features(sub)
        df.loc[mask, [c for c in sub.columns if c not in df.columns]] = sub[
            [c for c in sub.columns if c not in df.columns]
        ]
        # update existing columns too
        for c in ["wind_out_flag","dome_flag","expected_bullpen_innings"]:
            df.loc[mask, c] = sub[c].values

    # Impute bullpen features (first game of season NaN)
    bullpen_cols = bundle["bullpen_cols"]
    for c in bullpen_cols:
        if c in df.columns:
            med = df[df["season"].isin(TRAIN_YEARS)][c].median()
            df[c] = df[c].fillna(med)

    df_train = df[df["season"].isin(TRAIN_YEARS)].copy()
    df_24    = df[df["season"] == VALIDATE_YEAR].copy()
    df_25    = df[df["season"] == OOS_YEAR].copy()

    print(f"  Train: {len(df_train):,}  Val2024: {len(df_24):,}  OOS2025: {len(df_25):,}")

    # ── Training residuals ────────────────────────────────────────────────────
    train_preds = predict(df_train, pipe_mean, features)
    train_abs_resid = np.abs(df_train["actual_total"].values - train_preds)
    hdr(f"  Training |residual| stats: mean={train_abs_resid.mean():.3f}  "
        f"std={train_abs_resid.std():.3f}  "
        f"median={np.median(train_abs_resid):.3f}  "
        f"p90={np.percentile(train_abs_resid, 90):.3f}")
    hdr(f"  E[|residual|]/σ_const = {train_abs_resid.mean():.3f}/{sigma_const:.3f} "
        f"= {train_abs_resid.mean()/sigma_const:.3f}  (theory: {SQRT_2_PI:.3f})")
    hdr()

    # ── Fit variance model ────────────────────────────────────────────────────
    hdr("=" * 74)
    hdr("1. VARIANCE MODEL FIT (train 2022+2023)")
    hdr("=" * 74)

    pipe_var = fit_variance_model(df_train, train_abs_resid)
    alpha_v  = pipe_var.named_steps["ridge"].alpha_
    hdr(f"  α_variance = {alpha_v:.1f}")

    # Variance model R² and correlation with |residuals|
    var_pred_train = pipe_var.predict(
        df_train[VARIANCE_FEATURES].fillna(
            df_train[VARIANCE_FEATURES].median()).values
    )
    r_var_train = np.corrcoef(var_pred_train, train_abs_resid)[0, 1]
    r2_var_train = r_var_train ** 2
    hdr(f"  Variance model fit (in-sample):  r={r_var_train:.3f}  R²={r2_var_train:.4f}")
    hdr(f"  (R² measures how much of |residual| variance is explained by predictors)")
    hdr()

    # Coefficient table for variance model
    sc_v = pipe_var.named_steps["scaler"]
    r_v  = pipe_var.named_steps["ridge"]
    coef_rows = []
    for i, f in enumerate(VARIANCE_FEATURES):
        std_c = float(r_v.coef_[i])
        raw_c = float(std_c / sc_v.scale_[i])
        coef_rows.append((f, std_c, raw_c, abs(std_c)))
    coef_rows.sort(key=lambda x: -x[3])

    hdr(f"  Variance driver coefficients (sorted by |std coef|):")
    hdr(f"  {'Feature':<30}  {'Std coef':>10}  {'Raw coef':>10}  {'Interpretation'}")
    hdr(f"  {'─'*30}  {'─'*10}  {'─'*10}  {'─'*30}")
    interp = {
        "wind_speed":                "+coef → faster wind → wider outcome",
        "wind_out_flag":             "+coef → wind blowing out → wider",
        "home_sp_fb_pct":             "+coef → flyball SP → wind-sensitive",
        "away_sp_fb_pct":             "+coef → flyball SP → wind-sensitive",
        "home_bp_delta_exposure":    "+coef → more bullpen chaos → wider",
        "away_bp_delta_exposure":    "+coef → more bullpen chaos → wider",
        "temperature":               "+coef → hot → higher-scoring, wider",
        "park_factor_hr":            "+coef → HR park → more variance",
        "home_sp_bb_pct":            "+coef → wild SP → walk inflation",
        "away_sp_bb_pct":            "+coef → wild SP → walk inflation",
        "expected_bullpen_innings":  "+coef → more bullpen → more variance",
        "dome_flag":                 "−coef → dome → controlled environment",
    }
    for feat, std_c, raw_c, _ in coef_rows:
        hdr(f"  {feat:<30}  {std_c:>+10.4f}  {raw_c:>+10.4f}  {interp.get(feat,'')}")
    hdr()

    # ── Per-game sigma on all splits ──────────────────────────────────────────
    sigma_train = predict_sigma(df_train, pipe_var)
    sigma_24    = predict_sigma(df_24,    pipe_var)
    sigma_25    = predict_sigma(df_25,    pipe_var)

    hdr("=" * 74)
    hdr("2. PER-GAME σ DISTRIBUTION")
    hdr("=" * 74)
    hdr()
    for label, sig_arr, df_s in [
        ("Train 2022+2023", sigma_train, df_train),
        ("Val   2024",      sigma_24,    df_24),
        ("OOS   2025",      sigma_25,    df_25),
    ]:
        hdr(f"  {label}: mean={sig_arr.mean():.3f}  std={sig_arr.std():.3f}  "
            f"min={sig_arr.min():.3f}  p10={np.percentile(sig_arr,10):.3f}  "
            f"p50={np.percentile(sig_arr,50):.3f}  p90={np.percentile(sig_arr,90):.3f}  "
            f"max={sig_arr.max():.3f}  "
            f"at_floor={( sig_arr <= SIGMA_MIN + 0.01 ).sum()}")
    hdr()
    hdr(f"  σ_const (Phase 8) = {sigma_const:.4f} for all games")
    hdr(f"  σ_game floor      = {SIGMA_MIN:.1f}")
    hdr()

    # ── Segment analysis ─────────────────────────────────────────────────────
    hdr("=" * 74)
    hdr("3. HIGH- VS LOW-VOLATILITY GAME SEGMENTS")
    hdr("=" * 74)
    print_sigma_segments(df_25.assign(
        sigma_game=sigma_25,
        wind_out_flag=(
            (df_25["roof_status"]=="open") & (df_25["wind_factor_effective"]>3)
        ).astype(float),
        dome_flag=(df_25["roof_status"]=="dome").astype(float),
        expected_bullpen_innings=df_25["home_bp_proj_inn"]+df_25["away_bp_proj_inn"],
    ), sigma_25, lo, "2025 OOS")

    # Dome vs open-air vs wind-out segment σ comparison
    hdr()
    hdr("  σ_game by venue type (2025 OOS):")
    hdr(f"  {'Segment':<25}  {'N':>5}  {'Mean σ':>7}  {'P50 σ':>7}  {'P90 σ':>7}")
    hdr(f"  {'─'*25}  {'─'*5}  {'─'*7}  {'─'*7}  {'─'*7}")
    roof25 = df_25["roof_status"].values
    wout25 = ((df_25["roof_status"]=="open") & (df_25["wind_factor_effective"]>3)).values
    for seg_name, mask in [
        ("Dome",               roof25 == "dome"),
        ("Retractable roof",   roof25 == "retractable"),
        ("Open air, no wind",  (roof25=="open") & ~wout25),
        ("Open air, wind-out", wout25),
    ]:
        sig_seg = sigma_25[mask]
        if len(sig_seg) == 0: continue
        hdr(f"  {seg_name:<25}  {len(sig_seg):>5}  {sig_seg.mean():>7.3f}  "
            f"{np.median(sig_seg):>7.3f}  {np.percentile(sig_seg,90):>7.3f}")
    hdr()

    # ── Evaluate CI coverage ──────────────────────────────────────────────────
    hdr("=" * 74)
    hdr("4. CI COVERAGE — CONSTANT σ vs σ_GAME")
    hdr("=" * 74)
    hdr()
    hdr(f"  80% CI = [pred − 1.282σ, pred + 1.282σ]  (target coverage = 80%)")
    hdr()

    preds_24 = predict(df_24, pipe_mean, features)
    preds_25 = predict(df_25, pipe_mean, features)
    actual_24 = df_24["actual_total"].values
    actual_25 = df_25["actual_total"].values

    for season_label, preds, actual, sig_game, sig_c in [
        ("2024 Validate", preds_24, actual_24, sigma_24, sigma_const),
        ("2025 OOS",      preds_25, actual_25, sigma_25, sigma_const),
    ]:
        ci_lo_c   = preds - 1.282 * sig_c
        ci_hi_c   = preds + 1.282 * sig_c
        ci_lo_g   = preds - 1.282 * sig_game
        ci_hi_g   = preds + 1.282 * sig_game
        cov_c     = ci_coverage(actual, ci_lo_c, ci_hi_c)
        cov_g     = ci_coverage(actual, ci_lo_g, ci_hi_g)
        width_c   = (ci_hi_c - ci_lo_c).mean()
        width_g   = (ci_hi_g - ci_lo_g).mean()

        # CI by segment (2025 only)
        hdr(f"  {season_label}:")
        hdr(f"    Constant σ = {sig_c:.3f}:  coverage={cov_c:.1%}  CI width={width_c:.3f}")
        hdr(f"    σ_game:              coverage={cov_g:.1%}  CI width={width_g:.3f}  "
            f"(mean σ={sig_game.mean():.3f})")
        delta_cov = cov_g - cov_c
        hdr(f"    Δ coverage = {delta_cov:+.3%}  "
            f"{'✓ improved' if delta_cov > 0.001 else '✗ no improvement' if delta_cov < -0.001 else '≈ same'}")

    hdr()

    # ── P(over) simulation and calibration comparison ─────────────────────────
    hdr("=" * 74)
    hdr("5. CALIBRATION COMPARISON — CONSTANT σ vs σ_GAME")
    hdr("=" * 74)
    hdr()

    # Use proxy line for simulation (calibration table uses proxy to match full population)
    PROXY = 8.86
    print("Simulating constant σ P(over)...", flush=True)
    p_over_c24, _, _   = simulate_with_sigma(preds_24, sigma_const,  PROXY, seed=SEED)
    p_over_c25, _, _   = simulate_with_sigma(preds_25, sigma_const,  PROXY, seed=SEED)
    print("Simulating per-game σ P(over)...", flush=True)
    p_over_g24, _, _   = simulate_with_sigma(preds_24, sigma_24,     PROXY, seed=SEED)
    p_over_g25, _, _   = simulate_with_sigma(preds_25, sigma_25,     PROXY, seed=SEED)

    cal_c24 = calibration_table(actual_24, p_over_c24, PROXY)
    cal_g24 = calibration_table(actual_24, p_over_g24, PROXY)
    cal_c25 = calibration_table(actual_25, p_over_c25, PROXY)
    cal_g25 = calibration_table(actual_25, p_over_g25, PROXY)

    print_calibration_compare(cal_c24, cal_g24, "2024 Validate (proxy line)", lo)
    print_calibration_compare(cal_c25, cal_g25, "2025 OOS (proxy line)",      lo)

    # Brier score comparison
    hdr()
    hdr("  Brier score summary (lower = better calibrated):")
    def brier(actual, p_over, line):
        return ((p_over - (actual > line).astype(float))**2).mean()
    hdr(f"  {'':30}  {'2024 const':>10}  {'2024 game':>10}  "
        f"{'2025 const':>10}  {'2025 game':>10}")
    hdr(f"  {'Brier score (proxy line)':30}  "
        f"{brier(actual_24,p_over_c24,PROXY):>10.5f}  "
        f"{brier(actual_24,p_over_g24,PROXY):>10.5f}  "
        f"{brier(actual_25,p_over_c25,PROXY):>10.5f}  "
        f"{brier(actual_25,p_over_g25,PROXY):>10.5f}")

    hdr()

    # ── ROI and tier comparison ───────────────────────────────────────────────
    hdr("=" * 74)
    hdr("6. ROI AND CONFIDENCE TIER — CONSTANT σ vs σ_GAME (vs real closing lines)")
    hdr("=" * 74)
    hdr()

    from config import BET_EDGE, BET_PROB, WIN_UNIT

    print("Computing ROI (constant σ)...", flush=True)
    roi_c24 = roi_sim_sigma(preds_24, np.full(len(preds_24), sigma_const),
                             df_24, df_market, BET_EDGE, BET_PROB, WIN_UNIT)
    roi_c25 = roi_sim_sigma(preds_25, np.full(len(preds_25), sigma_const),
                             df_25, df_market, BET_EDGE, BET_PROB, WIN_UNIT)
    print("Computing ROI (σ_game)...", flush=True)
    roi_g24 = roi_sim_sigma(preds_24, sigma_24, df_24, df_market, BET_EDGE, BET_PROB, WIN_UNIT)
    roi_g25 = roi_sim_sigma(preds_25, sigma_25, df_25, df_market, BET_EDGE, BET_PROB, WIN_UNIT)

    hdr(f"  {'Metric':<30}  {'σ_const 2024':>13}  {'σ_game 2024':>12}  "
        f"{'σ_const 2025':>13}  {'σ_game 2025':>12}")
    hdr(f"  {'─'*30}  {'─'*13}  {'─'*12}  {'─'*13}  {'─'*12}")

    def rrow(label, rc24, rg24, rc25, rg25):
        hdr(f"  {label:<30}  {rc24:>13}  {rg24:>12}  {rc25:>13}  {rg25:>12}")

    rrow("N bets",
         str(roi_c24.get("by_year",{}).get(2024,{}).get("n",0)),
         str(roi_g24.get("by_year",{}).get(2024,{}).get("n",0)),
         str(roi_c25.get("by_year",{}).get(2025,{}).get("n",0)),
         str(roi_g25.get("by_year",{}).get(2025,{}).get("n",0)))
    rrow("Win %",
         f"{roi_c24.get('by_year',{}).get(2024,{}).get('win_pct',float('nan'))*100:.1f}%",
         f"{roi_g24.get('by_year',{}).get(2024,{}).get('win_pct',float('nan'))*100:.1f}%",
         f"{roi_c25.get('by_year',{}).get(2025,{}).get('win_pct',float('nan'))*100:.1f}%",
         f"{roi_g25.get('by_year',{}).get(2025,{}).get('win_pct',float('nan'))*100:.1f}%")
    rrow("ROI %",
         f"{roi_c24.get('by_year',{}).get(2024,{}).get('roi',float('nan')):+.1f}%",
         f"{roi_g24.get('by_year',{}).get(2024,{}).get('roi',float('nan')):+.1f}%",
         f"{roi_c25.get('by_year',{}).get(2025,{}).get('roi',float('nan')):+.1f}%",
         f"{roi_g25.get('by_year',{}).get(2025,{}).get('roi',float('nan')):+.1f}%")

    # Tier comparison
    print("Computing tiers (constant σ)...", flush=True)
    tier_c25 = tier_sim_sigma(preds_25, np.full(len(preds_25), sigma_const), df_25, df_market)
    print("Computing tiers (σ_game)...", flush=True)
    tier_g25 = tier_sim_sigma(preds_25, sigma_25, df_25, df_market)

    hdr()
    hdr("  Confidence tiers — 2025 OOS:")
    hdr(f"  {'Tier':<12}  {'σ_const n':>9}  {'σ_const win%':>12}  {'σ_const ROI':>11}  "
        f"{'σ_game n':>8}  {'σ_game win%':>11}  {'σ_game ROI':>10}  {'Δ ROI':>7}")
    hdr(f"  {'─'*12}  {'─'*9}  {'─'*12}  {'─'*11}  "
        f"{'─'*8}  {'─'*11}  {'─'*10}  {'─'*7}")
    tc = {t["tier"]: t for t in tier_c25}
    tg = {t["tier"]: t for t in tier_g25}
    for tier in ["STRONG","BET","WATCHLIST"]:
        c = tc.get(tier, {"n":0,"win_pct":float("nan"),"roi":float("nan")})
        g = tg.get(tier, {"n":0,"win_pct":float("nan"),"roi":float("nan")})
        d = g["roi"] - c["roi"] if not (np.isnan(c["roi"]) or np.isnan(g["roi"])) else float("nan")
        hdr(f"  {tier:<12}  {c['n']:>9}  {c['win_pct']*100:>12.1f}  {c['roi']:>+11.1f}  "
            f"{g['n']:>8}  {g['win_pct']*100:>11.1f}  {g['roi']:>+10.1f}  "
            f"{d:>+7.1f}pp")

    hdr()

    # ── Final verdict ─────────────────────────────────────────────────────────
    hdr("=" * 74)
    hdr("7. VERDICT")
    hdr("=" * 74)
    hdr()

    cov_c25 = ci_coverage(actual_25,
                           preds_25 - 1.282*sigma_const,
                           preds_25 + 1.282*sigma_const)
    cov_g25 = ci_coverage(actual_25,
                           preds_25 - 1.282*sigma_25,
                           preds_25 + 1.282*sigma_25)
    roi_c25_val = roi_c25.get("by_year",{}).get(2025,{}).get("roi", float("nan"))
    roi_g25_val = roi_g25.get("by_year",{}).get(2025,{}).get("roi", float("nan"))
    delta_roi   = roi_g25_val - roi_c25_val if not (np.isnan(roi_c25_val) or np.isnan(roi_g25_val)) else float("nan")

    brier_c25 = brier(actual_25, p_over_c25, PROXY)
    brier_g25 = brier(actual_25, p_over_g25, PROXY)

    cov_improves  = cov_g25 > cov_c25 + 0.002
    roi_improves  = not np.isnan(delta_roi) and delta_roi > 0.1
    brier_improves= brier_g25 < brier_c25 - 0.0001

    hdr(f"  CI coverage (2025):  constant={cov_c25:.3%}  game={cov_g25:.3%}  "
        f"Δ={cov_g25-cov_c25:+.3%}  {'IMPROVED ✓' if cov_improves else 'NO CHANGE ✗'}")
    hdr(f"  Brier score (2025):  constant={brier_c25:.5f}  game={brier_g25:.5f}  "
        f"{'IMPROVED ✓' if brier_improves else 'NO CHANGE ✗'}")
    hdr(f"  ROI 2025 OOS:        constant={roi_c25_val:+.1f}%  game={roi_g25_val:+.1f}%  "
        f"Δ={delta_roi:+.1f}pp  {'IMPROVED ✓' if roi_improves else 'NO GAIN ✗'}")
    hdr()

    if (cov_improves or brier_improves) and not (cov_g25 < 0.75):
        verdict = "KEEP σ_game"
        rationale = (f"CI coverage {'improved' if cov_improves else 'held'}, "
                     f"Brier {'improved' if brier_improves else 'held'}. "
                     f"ROI Δ={delta_roi:+.1f}pp.")
    else:
        verdict = "REVERT to constant σ"
        rationale = (f"σ_game does not improve CI coverage or Brier score OOS. "
                     f"Constant σ={sigma_const:.3f} retained.")

    hdr(f"  VERDICT: {verdict}")
    hdr(f"  {rationale}")

    # ── Save variance model ───────────────────────────────────────────────────
    if verdict.startswith("KEEP"):
        vbundle = {
            "pipeline":        pipe_var,
            "features":        VARIANCE_FEATURES,
            "sigma_floor":     SIGMA_MIN,
            "sqrt_2_pi":       SQRT_2_PI,
            "label":           "Phase 9 heteroskedastic variance model",
            "train_years":     TRAIN_YEARS,
            "alpha":           alpha_v,
            "in_sample_r":     float(r_var_train),
            "in_sample_r2":    float(r2_var_train),
        }
        with open(VARIANCE_MODEL, "wb") as f:
            pickle.dump(vbundle, f)
        hdr()
        hdr(f"  Saved variance model → {VARIANCE_MODEL}")
        hdr(f"  Variance drivers: {VARIANCE_FEATURES}")
    else:
        hdr()
        hdr("  No variance model saved. Use sigma_const from phase9_baseline_model.pkl.")

    hdr()
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lo))
    print(f"\nReport saved → {REPORT_PATH}")


if __name__ == "__main__":
    main()
