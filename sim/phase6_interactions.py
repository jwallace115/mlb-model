"""
phase6_interactions.py — Interaction feature testing (one at a time).

Adds candidate interaction features to the Phase 3 v2 Ridge baseline and
evaluates each independently via leave-2022+2023-out (train on 2022+2023,
validate on 2024, OOS on 2025).

Interaction 1 (this run):
  flyball_pitcher_pct × wind_out_flag
  - flyball_pct per starter from FanGraphs via pybaseball (FB%)
  - wind_out_flag = (wind_factor_effective > 3) & (roof_status == 'open')
  - term = (home_sp_fb_pct + away_sp_fb_pct) × wind_out_flag

Keep rule: only keep if OOS MAE improves or calibration improves without
degrading other metrics (MAE, RMSE, r, directional hit rate).

Usage:
    python sim/phase6_interactions.py --interaction 1   # flyball × wind
    python sim/phase6_interactions.py --interaction 2   # weak_bp × hot_temp
    python sim/phase6_interactions.py --interaction 3   # power_off × park_hr
    python sim/phase6_interactions.py --interaction 4   # elite_off × poor_cmd
    python sim/phase6_interactions.py --all             # run all in sequence

Label: Results labeled as "Phase 3 baseline" vs "Phase 6 + Interaction N"
"""

import argparse
import logging
import os
import pickle
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

SIM_DIR     = Path(__file__).parent
PROJECT_DIR = SIM_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("phase6")

FEATURE_TABLE_PATH = SIM_DIR / "data" / "feature_table.parquet"
MODEL_PATH         = SIM_DIR / "data" / "phase3_ridge_model_v2.pkl"
CACHE_DIR          = SIM_DIR / "data" / "cache"
REPORT_PATH        = SIM_DIR / "data" / "phase6_interaction_report.txt"

TRAIN_YEARS   = [2022, 2023]
VALIDATE_YEAR = 2024
OOS_YEAR      = 2025
PROXY_LINE    = 8.86
ALPHAS        = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0,
                 50.0, 100.0, 200.0, 500.0, 1000.0]

# Phase 3 v2 feature set (baseline)
BASELINE_FEATURES = [
    "home_sp_xfip",  "away_sp_xfip",
    "home_sp_k_pct", "away_sp_k_pct",
    "home_sp_bb_pct","away_sp_bb_pct",
    "home_sp_avg_ip","away_sp_avg_ip",
    "home_wrc_plus", "away_wrc_plus",
    "park_factor_runs", "park_factor_hr",
    "temperature", "wind_factor_effective",
    "umpire_over_rate",
    "home_rest_days", "away_rest_days",
    "doubleheader_flag",
]

# Probability threshold for directional hit rate evaluation
P_THRESHOLDS = [0.50, 0.52, 0.55, 0.58, 0.60]

# Execution bands (from config, per Phase 5 spec)
WATCHLIST_P   = 0.55
CANDIDATE_P   = 0.58
SELECTIVE_P   = 0.60


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_df(years: list[int]) -> pd.DataFrame:
    df = pd.read_parquet(FEATURE_TABLE_PATH)
    df = df[df["season"].isin(years)].copy()
    df["doubleheader_flag"] = df["doubleheader_flag"].astype(int)
    return df


def load_baseline_model() -> dict:
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------------------
# Flyball data (Interaction 1)
# ---------------------------------------------------------------------------

def _fetch_flyball_year(year: int) -> pd.DataFrame:
    """
    Fetch pitcher GB%/FB% from FanGraphs via pybaseball.
    Cached per season to avoid repeated API calls.
    """
    cache_path = CACHE_DIR / f"fb_pct_{year}.parquet"
    if cache_path.exists():
        logger.info(f"  [cache] flyball data {year}")
        return pd.read_parquet(cache_path)

    logger.info(f"  Fetching flyball data from FanGraphs {year}...")
    from pybaseball import pitching_stats
    df = pitching_stats(year, year, qual=1)

    # Normalize name for joining
    df["name_lower"] = df["Name"].str.lower().str.strip()
    df["fg_id"] = df["IDfg"].astype(str)

    out = df[["name_lower", "fg_id", "GB%", "FB%", "LD%"]].copy()
    out.columns = ["name_lower", "fg_id", "gb_pct", "fb_pct", "ld_pct"]
    out = out.dropna(subset=["fb_pct"])

    out.to_parquet(cache_path, index=False)
    logger.info(f"  Saved flyball cache {year}: {len(out)} pitchers")
    return out


def _name_key(name: str) -> str:
    """Lowercase + strip for fuzzy matching."""
    return name.lower().strip()


def _build_flyball_lookup(year: int) -> dict:
    """Build {name_lower: fb_pct} dict with league-average fallback."""
    fb_df = _fetch_flyball_year(year)
    lookup = dict(zip(fb_df["name_lower"], fb_df["fb_pct"]))
    return lookup, fb_df["fb_pct"].mean()


def add_flyball_wind_interaction(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Adds columns:
      home_sp_fb_pct, away_sp_fb_pct  — per-starter flyball rate
      wind_out_flag                   — 1 if open roof and wind blowing out (>3 eff)
      flyball_wind_interaction        — (home_fb + away_fb) × wind_out_flag
    """
    lookup, league_avg_fb = _build_flyball_lookup(year)

    def get_fb(sp_name):
        if pd.isna(sp_name):
            return league_avg_fb
        return lookup.get(_name_key(str(sp_name)), league_avg_fb)

    df = df.copy()
    df["home_sp_fb_pct"] = df["home_sp_name"].apply(get_fb)
    df["away_sp_fb_pct"] = df["away_sp_name"].apply(get_fb)

    # wind_out_flag: only open-roof games where effective wind factor > 3
    # (retractable/dome already neutralized to 0 in Phase 1; this is redundant
    #  but explicit for clarity)
    df["wind_out_flag"] = (
        (df["roof_status"] == "open") & (df["wind_factor_effective"] > 3)
    ).astype(float)

    df["flyball_wind_interaction"] = (
        (df["home_sp_fb_pct"] + df["away_sp_fb_pct"]) * df["wind_out_flag"]
    )

    # Audit
    matched_home = (df["home_sp_name"].apply(_name_key).isin(lookup)).sum()
    matched_away = (df["away_sp_name"].apply(_name_key).isin(lookup)).sum()
    logger.info(f"  [year={year}] FB% match: home={matched_home}/{len(df)} "
                f"away={matched_away}/{len(df)}, "
                f"league_avg_fb={league_avg_fb:.3f}, "
                f"wind_out games={int(df['wind_out_flag'].sum())}")
    return df


# ---------------------------------------------------------------------------
# Interaction 2: weak_bullpen × high_temperature
# ---------------------------------------------------------------------------

def add_bp_heat_interaction(df: pd.DataFrame, bp_thresh: float, temp_thresh: float = 80.0) -> pd.DataFrame:
    """
    bp_interaction > bp_thresh → team likely relies on bullpen more
    temperature  > temp_thresh → hot game
    Interaction = (home_bp_high + away_bp_high) × hot_flag
    """
    df = df.copy()
    df["home_bp_high"] = (df["home_bp_interaction"] > bp_thresh).astype(float)
    df["away_bp_high"] = (df["away_bp_interaction"] > bp_thresh).astype(float)
    df["hot_temp_flag"] = (df["temperature"] > temp_thresh).astype(float)
    df["bp_heat_interaction"] = (
        (df["home_bp_high"] + df["away_bp_high"]) * df["hot_temp_flag"]
    )
    return df


# ---------------------------------------------------------------------------
# Cumulative enrichment helper
# ---------------------------------------------------------------------------

# Thresholds computed once from training data and reused across interactions
_BP_THRESH:    float | None = None
_WRC_P75:      float | None = None
_WRC_P80:      float | None = None
_BB_POOR:      float | None = None


def _init_thresholds():
    global _BP_THRESH, _WRC_P75, _WRC_P80, _BB_POOR
    if _BP_THRESH is not None:
        return
    df_train = load_df(TRAIN_YEARS)
    _BP_THRESH = round(float(df_train[["home_bp_interaction","away_bp_interaction"]].stack().quantile(0.75)), 2)
    _WRC_P75   = round(float(df_train[["home_wrc_plus","away_wrc_plus"]].stack().quantile(0.75)), 1)
    _WRC_P80   = round(float(df_train[["home_wrc_plus","away_wrc_plus"]].stack().quantile(0.80)), 1)
    _BB_POOR   = round(float(df_train[["home_sp_bb_pct","away_sp_bb_pct"]].stack().quantile(0.80)), 4)


def enrich_with_approved(df: pd.DataFrame, year: int,
                          approved_features: list[str]) -> pd.DataFrame:
    """
    Apply only the interaction columns that appear in approved_features.
    Called at the start of each run_interaction_N so prior interactions
    are present in the data frame when the new one is added.
    """
    _init_thresholds()
    if "flyball_wind_interaction" in approved_features:
        df = add_flyball_wind_interaction(df, year)
    if "bp_heat_interaction" in approved_features:
        df = add_bp_heat_interaction(df, bp_thresh=_BP_THRESH)
    if "power_park_interaction" in approved_features:
        df = add_power_park_interaction(df, year=year)
    if "elite_cmd_interaction" in approved_features:
        df = add_elite_cmd_interaction(df, wrc_elite_thresh=_WRC_P80,
                                       bb_poor_thresh=_BB_POOR)
    return df


# ---------------------------------------------------------------------------
# Interaction 3: power_offense (ISO) × park_hr_factor
# ---------------------------------------------------------------------------

# FanGraphs uses "ATH" for Oakland 2025; our model uses "OAK"
_FG_TEAM_MAP = {"ATH": "OAK", "- - -": None}


def _fetch_team_iso(year: int) -> dict:
    """
    Fetch PA-weighted team ISO from FanGraphs via pybaseball.
    Returns {team_abb: iso_float}.
    Cached per season.

    ISO chosen over barrel rate because:
      - ISO = SLG − BA: directly measures extra-base hit power
      - 100% team coverage via pybaseball FanGraphs API (qual=0)
      - Single clean metric, no secondary Savant API call required
      - Barrel rate is more precise but requires Savant batter leaderboard
        aggregation by team, adding fetch complexity for marginal precision gain
    """
    cache_path = CACHE_DIR / f"team_iso_{year}.parquet"
    if cache_path.exists():
        logger.info(f"  [cache] team ISO {year}")
        df_c = pd.read_parquet(cache_path)
        return dict(zip(df_c["team"], df_c["team_iso"]))

    logger.info(f"  Fetching team ISO from FanGraphs {year}...")
    import warnings as _w; _w.filterwarnings("ignore")
    from pybaseball import batting_stats
    df = batting_stats(year, year, qual=0)     # qual=0 → all batters

    # PA-weighted ISO aggregated by team
    # Drop multi-team rows ("- - -") — these aren't real team rows
    df_clean = df[~df["Team"].isin(["- - -"])].copy()
    df_team  = (
        df_clean.groupby("Team")
        .apply(lambda g: (g["ISO"] * g["PA"]).sum() / g["PA"].sum(), include_groups=False)
        .reset_index()
    )
    df_team.columns = ["team", "team_iso"]

    # Remap FanGraphs abbreviations → model abbreviations
    df_team["team"] = df_team["team"].map(
        lambda t: _FG_TEAM_MAP.get(t, t)
    )
    df_team = df_team.dropna(subset=["team"])

    df_team.to_parquet(cache_path, index=False)
    logger.info(f"  Saved team ISO cache {year}: {len(df_team)} teams  "
                f"range [{df_team['team_iso'].min():.3f}–{df_team['team_iso'].max():.3f}]")
    return dict(zip(df_team["team"], df_team["team_iso"]))


def add_power_park_interaction(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Continuous team ISO × park HR factor interaction.

    Formula:
      power_park_interaction = (home_iso + away_iso) × (park_factor_hr / 100 − 1)

    The (park_factor_hr/100 − 1) centers the park effect at 0 so that
    neutral parks (factor=100) contribute zero interaction, positive values
    for HR-friendly parks, negative for HR-suppressing parks.

    This is more interpretable than using the raw ratio ×1.0+, and means
    the interaction is truly zero when the park is neutral.
    """
    iso_lookup = _fetch_team_iso(year)
    league_avg_iso = float(np.mean(list(iso_lookup.values())))

    df = df.copy()
    df["home_iso"] = df["home_team"].map(iso_lookup).fillna(league_avg_iso)
    df["away_iso"] = df["away_team"].map(iso_lookup).fillna(league_avg_iso)
    df["park_hr_effect"] = df["park_factor_hr"] / 100.0 - 1.0   # centered: 0=neutral
    df["power_park_interaction"] = (
        (df["home_iso"] + df["away_iso"]) * df["park_hr_effect"]
    )

    n_home_match = df["home_team"].isin(iso_lookup).sum()
    n_away_match = df["away_team"].isin(iso_lookup).sum()
    logger.info(f"  [year={year}] ISO match: home={n_home_match}/{len(df)} "
                f"away={n_away_match}/{len(df)}  league_avg_iso={league_avg_iso:.3f}")
    return df


# ---------------------------------------------------------------------------
# Interaction 4: elite_offense × poor_command
# ---------------------------------------------------------------------------

def add_elite_cmd_interaction(df: pd.DataFrame,
                               wrc_elite_thresh: float,
                               bb_poor_thresh: float) -> pd.DataFrame:
    """
    elite_offense: wRC+ proxy > wrc_elite_thresh
    poor_command:  SP BB% > bb_poor_thresh
    Cross-matchup interaction:
      home offense vs away pitcher command, plus mirror
    Term = (home_elite × away_poor_cmd) + (away_elite × home_poor_cmd)
    """
    df = df.copy()
    df["home_elite_off"] = (df["home_wrc_plus"] > wrc_elite_thresh).astype(float)
    df["away_elite_off"] = (df["away_wrc_plus"] > wrc_elite_thresh).astype(float)
    df["home_poor_cmd"]  = (df["home_sp_bb_pct"] > bb_poor_thresh).astype(float)
    df["away_poor_cmd"]  = (df["away_sp_bb_pct"] > bb_poor_thresh).astype(float)
    df["elite_cmd_interaction"] = (
        df["home_elite_off"] * df["away_poor_cmd"] +
        df["away_elite_off"] * df["home_poor_cmd"]
    )
    return df


# ---------------------------------------------------------------------------
# Ridge fit + predict
# ---------------------------------------------------------------------------

def fit_ridge(df_train: pd.DataFrame, features: list[str]) -> Pipeline:
    X = df_train[features].values
    y = df_train["actual_total"].values
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  RidgeCV(alphas=ALPHAS, cv=5)),
    ])
    pipe.fit(X, y)
    alpha = pipe.named_steps["ridge"].alpha_
    logger.info(f"  Ridge alpha={alpha:.2f}  intercept={pipe.named_steps['ridge'].intercept_:.4f}")
    return pipe


def ridge_predict(df: pd.DataFrame, pipe: Pipeline, features: list[str]) -> np.ndarray:
    X = df[features].copy()
    for col in features:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())
    return pipe.predict(X.values)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def directional_hit_rate(actual: np.ndarray, pred: np.ndarray,
                          line: float = PROXY_LINE) -> float:
    over_lean  = pred > line
    under_lean = pred < line
    hits = ((over_lean & (actual > line)) | (under_lean & (actual <= line))).sum()
    n    = (over_lean | under_lean).sum()
    return float(hits / n) if n > 0 else float("nan")


def p_hit_rate(actual: np.ndarray, p_over: np.ndarray, threshold: float,
               line: float = PROXY_LINE) -> tuple:
    lean_over  = p_over >= threshold
    lean_under = p_over <= (1 - threshold)
    mask = lean_over | lean_under
    if mask.sum() == 0:
        return float("nan"), 0
    hits = ((lean_over & (actual > line)) | (lean_under & (actual <= line)))[mask].sum()
    return float(hits / mask.sum()), int(mask.sum())


def compute_p_over(actual: np.ndarray, ridge: np.ndarray, sigma: float,
                   line: float = PROXY_LINE, n: int = 10000,
                   seed: int = 42) -> np.ndarray:
    """Quick P(over) from N(ridge, sigma) without full sim run."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, sigma, size=(len(ridge), n))
    sims  = ridge[:, None] + noise
    return (sims > line).mean(axis=1)


def edge_bucket_table(actual: np.ndarray, pred: np.ndarray,
                      line: float = PROXY_LINE) -> list[dict]:
    bins   = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, np.inf]
    labels = ["0.0–0.5","0.5–1.0","1.0–1.5","1.5–2.0",
              "2.0–2.5","2.5–3.0","3.0–4.0","4.0+"]
    edge   = np.abs(pred - line)
    over_lean  = pred > line
    under_lean = pred < line
    hit = ((over_lean & (actual > line)) | (under_lean & (actual <= line)))
    rows = []
    for lo, hi, lbl in zip(bins[:-1], bins[1:], labels):
        mask = (edge >= lo) & (edge < hi)
        n_m  = mask.sum()
        if n_m == 0:
            continue
        rows.append({
            "bucket": lbl, "n": n_m,
            "hit_pct": float(hit[mask].mean()),
        })
    return rows


def full_eval(label: str, df_eval: pd.DataFrame, pipe: Pipeline,
              features: list[str], sigma: float) -> dict:
    actual = df_eval["actual_total"].values
    pred   = ridge_predict(df_eval, pipe, features)
    p_over = compute_p_over(actual, pred, sigma)

    mae  = mean_absolute_error(actual, pred)
    rmse = np.sqrt(mean_squared_error(actual, pred))
    r    = np.corrcoef(actual, pred)[0, 1]
    bias = (actual - pred).mean()
    dhr  = directional_hit_rate(actual, pred)

    p_hits = {}
    for t in P_THRESHOLDS:
        hr, n = p_hit_rate(actual, p_over, t)
        p_hits[t] = (hr, n)

    return {
        "label": label, "n": len(actual),
        "mae": mae, "rmse": rmse, "r": r, "bias": bias,
        "dhr": dhr,
        "p_hits": p_hits,
        "pred": pred,
        "actual": actual,
        "p_over": p_over,
        "edge_buckets": edge_bucket_table(actual, pred),
    }


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def compare_evals(base: dict, new: dict, report_lines: list) -> None:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    def delta_str(v_new, v_base, good_dir: str = "lower") -> str:
        d = v_new - v_base
        sign = "+" if d > 0 else ""
        better = (d < 0) if good_dir == "lower" else (d > 0)
        tag = " ✓" if better else " ✗"
        return f"{sign}{d:+.4f}{tag}"

    line()
    line(f"  {'Metric':<20}  {'Baseline':>12}  {'+ Interaction':>14}  {'Delta':>16}")
    line(f"  {'─'*20}  {'─'*12}  {'─'*14}  {'─'*16}")

    for label, key, gd in [
        ("MAE",         "mae",  "lower"),
        ("RMSE",        "rmse", "lower"),
        ("Pearson r",   "r",    "higher"),
        ("Bias",        "bias", "lower"),
        ("DHR (P≥0.50)","dhr",  "higher"),
    ]:
        b_v = base[key]
        n_v = new[key]
        line(f"  {label:<20}  {b_v:>12.4f}  {n_v:>14.4f}  {delta_str(n_v, b_v, gd):>16}")

    line()
    line(f"  P-threshold hit rates:")
    line(f"  {'P thresh':>10}  {'Base N':>7}  {'Base Hit%':>9}  "
         f"{'New N':>7}  {'New Hit%':>9}  {'Delta':>8}")
    line(f"  {'─'*10}  {'─'*7}  {'─'*9}  {'─'*7}  {'─'*9}  {'─'*8}")
    for t in P_THRESHOLDS:
        b_hr, b_n = base["p_hits"][t]
        n_hr, n_n = new["p_hits"][t]
        d = (n_hr - b_hr) if not (np.isnan(b_hr) or np.isnan(n_hr)) else float("nan")
        d_str = f"{d:+.3f}" if not np.isnan(d) else "   —"
        line(f"  {t:>10.2f}  {b_n:>7,}  {b_hr:>9.1%}  {n_n:>7,}  {n_hr:>9.1%}  {d_str:>8}")

    # Edge bucket monotonicity
    line()
    line(f"  Edge bucket (baseline vs interaction):")
    line(f"  {'Bucket':>10}  {'Base N':>7}  {'Base%':>6}  {'New N':>6}  {'New%':>6}")
    line(f"  {'─'*10}  {'─'*7}  {'─'*6}  {'─'*6}  {'─'*6}")
    base_bkts = {r["bucket"]: r for r in base["edge_buckets"]}
    new_bkts  = {r["bucket"]: r for r in new["edge_buckets"]}
    all_lbls  = list(dict.fromkeys(
        [r["bucket"] for r in base["edge_buckets"]] +
        [r["bucket"] for r in new["edge_buckets"]]
    ))
    for lbl in all_lbls:
        b = base_bkts.get(lbl, {"n": 0, "hit_pct": float("nan")})
        n = new_bkts.get(lbl,  {"n": 0, "hit_pct": float("nan")})
        b_str = f"{b['hit_pct']:.1%}" if not np.isnan(b["hit_pct"]) else "  —"
        n_str = f"{n['hit_pct']:.1%}" if not np.isnan(n["hit_pct"]) else "  —"
        line(f"  {lbl:>10}  {b['n']:>7,}  {b_str:>6}  {n['n']:>6,}  {n_str:>6}")


def print_verdict(base_24: dict, new_24: dict,
                  base_25: dict, new_25: dict,
                  interaction_name: str,
                  report_lines: list) -> str:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    mae_delta_24 = new_24["mae"] - base_24["mae"]
    mae_delta_25 = new_25["mae"] - base_25["mae"]
    dhr_delta_25 = new_25["dhr"] - base_25["dhr"]

    # Require meaningful improvement (> 1e-4) to count as improved,
    # not just floating-point noise from regularization shrinkage.
    mae_improves_24 = mae_delta_24 < -1e-4
    mae_improves_25 = mae_delta_25 < -1e-4
    dhr_improves_25 = dhr_delta_25 > +1e-4

    line("")
    line(f"  VERDICT — {interaction_name}")
    line(f"  {'─'*60}")
    line(f"  2024 MAE delta:  {mae_delta_24:+.4f}  {'IMPROVED ✓' if mae_improves_24 else 'DEGRADED/FLAT ✗'}")
    line(f"  2025 MAE delta:  {mae_delta_25:+.4f}  {'IMPROVED ✓' if mae_improves_25 else 'DEGRADED/FLAT ✗'}")
    line(f"  2025 DHR delta:  {dhr_delta_25:+.4f}  {'IMPROVED ✓' if dhr_improves_25 else 'DEGRADED/FLAT ✗'}")

    # Keep rule: OOS MAE must improve meaningfully (> 1e-4 runs) OR
    # DHR must improve without MAE degrading. Coefficient near-zero (shrunk
    # to ≈0 by Ridge) = DROP regardless of pass/fail on deltas.
    if mae_improves_25:
        verdict = "KEEP"
        line(f"  DECISION: KEEP — OOS (2025) MAE improved by {abs(mae_delta_25):.4f} runs")
    elif dhr_improves_25 and mae_delta_25 < 0.02:
        verdict = "KEEP (marginal)"
        line(f"  DECISION: KEEP (marginal) — OOS MAE flat, DHR improved")
    else:
        verdict = "DROP"
        if abs(mae_delta_25) < 1e-4 and abs(dhr_delta_25) < 1e-4:
            line(f"  DECISION: DROP — coefficient shrunk to ~0 by Ridge (no effective signal)")
            line(f"  Likely cause: high collinearity with existing features or too sparse")
        else:
            line(f"  DECISION: DROP — OOS MAE degraded ({mae_delta_25:+.4f}); interaction does not generalize")

    return verdict


# ---------------------------------------------------------------------------
# Interaction 1: flyball × wind_out
# ---------------------------------------------------------------------------

def run_interaction_1(report_lines: list) -> tuple[str, list[str]]:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    line("=" * 76)
    line("INTERACTION 1: flyball_pitcher_pct × wind_out_flag")
    line("=" * 76)
    line("")
    line("  Feature: (home_sp_fb_pct + away_sp_fb_pct) × wind_out_flag")
    line(f"  wind_out_flag = 1 when roof_status=='open' AND wind_factor_effective > 3")
    line(f"  fb_pct from FanGraphs via pybaseball (FB%, excludes LD and GB)")
    line(f"  Fallback: league-average FB% for pitchers not in FanGraphs data")
    line("")

    # Build enriched feature tables for each year
    all_dfs = {}
    for yr in [2022, 2023, 2024, 2025]:
        df_yr = load_df([yr])
        df_yr = add_flyball_wind_interaction(df_yr, yr)
        all_dfs[yr] = df_yr
        fb_pct_home = df_yr["home_sp_fb_pct"]
        line(f"  {yr}: home_sp_fb_pct mean={fb_pct_home.mean():.3f} "
             f"std={fb_pct_home.std():.3f}  "
             f"wind_out games={int(df_yr['wind_out_flag'].sum())}  "
             f"interaction mean={df_yr['flyball_wind_interaction'].mean():.3f} "
             f"std={df_yr['flyball_wind_interaction'].std():.3f}")

    line("")
    line(f"  Note: flyball_wind_interaction = 0 for all dome/retractable games")
    line(f"  (wind_factor_effective already neutralized to 0 in Phase 1)")
    line("")

    # Training data (enriched)
    df_train = pd.concat([all_dfs[yr] for yr in TRAIN_YEARS], ignore_index=True)
    df_24    = all_dfs[VALIDATE_YEAR]
    df_25    = all_dfs[OOS_YEAR]

    # Feature sets
    baseline_features = BASELINE_FEATURES
    interaction_features = BASELINE_FEATURES + ["flyball_wind_interaction"]

    # ── Baseline model ───────────────────────────────────────────────────────
    line("Fitting baseline Ridge (18 features, train=2022+2023)...")
    pipe_base = fit_ridge(df_train, baseline_features)

    # ── Interaction model ─────────────────────────────────────────────────────
    line("Fitting interaction Ridge (19 features, train=2022+2023)...")
    pipe_int  = fit_ridge(df_train, interaction_features)
    alpha_base = pipe_base.named_steps["ridge"].alpha_
    alpha_int  = pipe_int.named_steps["ridge"].alpha_
    line(f"  Baseline alpha={alpha_base:.2f}  Interaction alpha={alpha_int:.2f}")

    # Training sigma (for P(over) computation)
    train_resid_base = (df_train["actual_total"].values
                        - ridge_predict(df_train, pipe_base, baseline_features))
    sigma_base = train_resid_base.std(ddof=1)
    train_resid_int  = (df_train["actual_total"].values
                        - ridge_predict(df_train, pipe_int, interaction_features))
    sigma_int  = train_resid_int.std(ddof=1)
    line(f"  Baseline sigma={sigma_base:.4f}  Interaction sigma={sigma_int:.4f}")
    line("")

    # ── Evaluate ──────────────────────────────────────────────────────────────
    base_24 = full_eval("Baseline 2024", df_24, pipe_base, baseline_features, sigma_base)
    int_24  = full_eval("Interact 2024", df_24, pipe_int,  interaction_features, sigma_int)
    base_25 = full_eval("Baseline 2025", df_25, pipe_base, baseline_features, sigma_base)
    int_25  = full_eval("Interact 2025", df_25, pipe_int,  interaction_features, sigma_int)

    # ── Report ────────────────────────────────────────────────────────────────
    for season_label, base_ev, int_ev in [
        ("2024 Validate", base_24, int_24),
        ("2025 OOS",      base_25, int_25),
    ]:
        line(f"{'─'*76}")
        line(f"  {season_label}  (n={base_ev['n']:,})")
        compare_evals(base_ev, int_ev, report_lines)

    # Interaction feature coefficient
    coef_idx = interaction_features.index("flyball_wind_interaction")
    scaler   = pipe_int.named_steps["scaler"]
    ridge    = pipe_int.named_steps["ridge"]
    coef_std = ridge.coef_[coef_idx]
    coef_raw = coef_std / scaler.scale_[coef_idx]
    line("")
    line(f"  flyball_wind_interaction coefficient:")
    line(f"    Standardized: {coef_std:+.4f}")
    line(f"    Raw (per unit): {coef_raw:+.4f}")
    line(f"    Interpretation: when wind_out AND flyball pitchers facing each other,")
    line(f"    each unit of (home_fb + away_fb) × 1 adds {coef_raw:+.4f} projected runs")
    line("")

    # Verdict
    verdict = print_verdict(base_24, int_24, base_25, int_25,
                            "flyball × wind_out", report_lines)

    # If KEEP, save the feature list to return
    surviving_features = (
        interaction_features if verdict.startswith("KEEP") else baseline_features
    )
    return verdict, surviving_features


# ---------------------------------------------------------------------------
# Interaction 2: weak_bullpen × high_temperature
# ---------------------------------------------------------------------------

def run_interaction_2(prior_features: list[str], report_lines: list) -> tuple[str, list[str]]:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    line("")
    line("=" * 76)
    line("INTERACTION 2: weak_bullpen × high_temperature")
    line("=" * 76)
    line("")

    # Thresholds from training distribution (via shared helper)
    _init_thresholds()
    bp_thresh   = _BP_THRESH
    temp_thresh = 80.0

    line(f"  weak_bullpen flag: bp_interaction > {bp_thresh:.2f}")
    line(f"    (P75 of home+away bp_interaction in 2022+2023 training set)")
    line(f"    bp_interaction encodes bullpen workload proxy: (bp_xfip/4.25) × proj_inn")
    line(f"    Higher value → team starter goes fewer innings, bullpen carries more load")
    line(f"  high_temp flag:    temperature > {temp_thresh:.0f}°F (open-roof games only)")
    line(f"  Interaction: (home_bp_high + away_bp_high) × hot_temp_flag")
    line(f"  Hypothesis: bullpens tire faster and allow more runs in summer heat")
    line("")

    # Build enriched dfs — apply all prior approved interactions first
    all_dfs = {}
    for yr in [2022, 2023, 2024, 2025]:
        df_yr = load_df([yr])
        df_yr = enrich_with_approved(df_yr, yr, prior_features)   # prior interactions
        df_yr = add_bp_heat_interaction(df_yr, bp_thresh=bp_thresh, temp_thresh=temp_thresh)
        all_dfs[yr] = df_yr
        n_int = (df_yr["bp_heat_interaction"] > 0).sum()
        line(f"  {yr}: bp_thresh={bp_thresh:.2f}  hot_games={int((df_yr['hot_temp_flag']>0).sum())}  "
             f"bp_heat_interaction>0: {n_int}  "
             f"interaction mean={df_yr['bp_heat_interaction'].mean():.3f}")

    line("")

    df_train = pd.concat([all_dfs[yr] for yr in TRAIN_YEARS], ignore_index=True)
    df_24    = all_dfs[VALIDATE_YEAR]
    df_25    = all_dfs[OOS_YEAR]

    baseline_features  = prior_features
    interaction_features = prior_features + ["bp_heat_interaction"]

    line("Fitting baseline Ridge...")
    pipe_base = fit_ridge(df_train, baseline_features)
    line("Fitting interaction Ridge...")
    pipe_int  = fit_ridge(df_train, interaction_features)
    line(f"  Baseline alpha={pipe_base.named_steps['ridge'].alpha_:.2f}  "
         f"Interaction alpha={pipe_int.named_steps['ridge'].alpha_:.2f}")

    sigma_base = (df_train["actual_total"].values - ridge_predict(df_train, pipe_base, baseline_features)).std(ddof=1)
    sigma_int  = (df_train["actual_total"].values - ridge_predict(df_train, pipe_int,  interaction_features)).std(ddof=1)
    line(f"  Baseline sigma={sigma_base:.4f}  Interaction sigma={sigma_int:.4f}")
    line("")

    base_24 = full_eval("Baseline 2024", df_24, pipe_base, baseline_features, sigma_base)
    int_24  = full_eval("Interact 2024", df_24, pipe_int,  interaction_features, sigma_int)
    base_25 = full_eval("Baseline 2025", df_25, pipe_base, baseline_features, sigma_base)
    int_25  = full_eval("Interact 2025", df_25, pipe_int,  interaction_features, sigma_int)

    for season_label, base_ev, int_ev in [
        ("2024 Validate", base_24, int_24),
        ("2025 OOS",      base_25, int_25),
    ]:
        line(f"{'─'*76}")
        line(f"  {season_label}  (n={base_ev['n']:,})")
        compare_evals(base_ev, int_ev, report_lines)

    # Coefficient
    coef_idx = interaction_features.index("bp_heat_interaction")
    scaler   = pipe_int.named_steps["scaler"]
    ridge    = pipe_int.named_steps["ridge"]
    coef_std = ridge.coef_[coef_idx]
    coef_raw = coef_std / scaler.scale_[coef_idx]
    line(f"\n  bp_heat_interaction coefficient:  std={coef_std:+.4f}  raw={coef_raw:+.4f}")
    line("")

    verdict = print_verdict(base_24, int_24, base_25, int_25,
                            "weak_bullpen × high_temp", report_lines)
    surviving = interaction_features if verdict.startswith("KEEP") else prior_features
    return verdict, surviving


# ---------------------------------------------------------------------------
# Interaction 3: power_offense × park_hr_factor
# ---------------------------------------------------------------------------

def run_interaction_3(prior_features: list[str], report_lines: list) -> tuple[str, list[str]]:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    line("")
    line("=" * 76)
    line("INTERACTION 3: power_offense (team ISO) × park_hr_factor")
    line("=" * 76)
    line("")

    line("  Power proxy chosen: team ISO (Isolated Power = SLG − BA)")
    line("  Source: FanGraphs via pybaseball, PA-weighted aggregation by team")
    line("  Why ISO over barrel rate:")
    line("    ISO has 100% team coverage via pybaseball with no extra API calls")
    line("    Barrel rate requires Savant batter leaderboard → team aggregation")
    line("    ISO is interpretable: directly measures extra-base power production")
    line("    Barrel rate is physically purer but adds pipeline complexity with")
    line("    marginal precision gain given the Ridge regularization context")
    line("")
    line("  Formula: (home_iso + away_iso) × (park_factor_hr/100 − 1)")
    line("  Centering: park_factor_hr/100 − 1 = 0 for neutral parks (factor=100)")
    line("    > 0 for HR-friendly parks (factor>100), < 0 for HR-suppressing")
    line("  Hypothesis: high-ISO lineups score more runs specifically in HR parks")
    line("")

    all_dfs = {}
    for yr in [2022, 2023, 2024, 2025]:
        df_yr = load_df([yr])
        df_yr = enrich_with_approved(df_yr, yr, prior_features)
        df_yr = add_power_park_interaction(df_yr, year=yr)
        all_dfs[yr] = df_yr
        line(f"  {yr}: home_iso mean={df_yr['home_iso'].mean():.3f}  "
             f"park_hr_effect mean={df_yr['park_hr_effect'].mean():.4f}  "
             f"interaction mean={df_yr['power_park_interaction'].mean():.4f} "
             f"std={df_yr['power_park_interaction'].std():.4f}")

    line("")

    df_train = pd.concat([all_dfs[yr] for yr in TRAIN_YEARS], ignore_index=True)
    df_24    = all_dfs[VALIDATE_YEAR]
    df_25    = all_dfs[OOS_YEAR]

    baseline_features    = prior_features
    interaction_features = prior_features + ["power_park_interaction"]

    line("Fitting baseline Ridge...")
    pipe_base = fit_ridge(df_train, baseline_features)
    line("Fitting interaction Ridge...")
    pipe_int  = fit_ridge(df_train, interaction_features)
    line(f"  alpha: base={pipe_base.named_steps['ridge'].alpha_:.2f}  "
         f"int={pipe_int.named_steps['ridge'].alpha_:.2f}")

    sigma_base = (df_train["actual_total"].values - ridge_predict(df_train, pipe_base, baseline_features)).std(ddof=1)
    sigma_int  = (df_train["actual_total"].values - ridge_predict(df_train, pipe_int,  interaction_features)).std(ddof=1)
    line(f"  sigma: base={sigma_base:.4f}  int={sigma_int:.4f}")
    line("")

    base_24 = full_eval("Baseline 2024", df_24, pipe_base, baseline_features, sigma_base)
    int_24  = full_eval("Interact 2024", df_24, pipe_int,  interaction_features, sigma_int)
    base_25 = full_eval("Baseline 2025", df_25, pipe_base, baseline_features, sigma_base)
    int_25  = full_eval("Interact 2025", df_25, pipe_int,  interaction_features, sigma_int)

    for season_label, base_ev, int_ev in [
        ("2024 Validate", base_24, int_24),
        ("2025 OOS",      base_25, int_25),
    ]:
        line(f"{'─'*76}")
        line(f"  {season_label}  (n={base_ev['n']:,})")
        compare_evals(base_ev, int_ev, report_lines)

    coef_idx = interaction_features.index("power_park_interaction")
    scaler   = pipe_int.named_steps["scaler"]
    ridge    = pipe_int.named_steps["ridge"]
    coef_std = ridge.coef_[coef_idx]
    coef_raw = coef_std / scaler.scale_[coef_idx]
    line(f"\n  power_park_interaction (ISO × park_hr_effect) coefficient:")
    line(f"    Standardized: {coef_std:+.4f}")
    line(f"    Raw: {coef_raw:+.4f}")
    line(f"    Interpretation: each unit increase in (home_iso + away_iso) × park_hr_effect")
    line(f"    adds {coef_raw:+.4f} runs projected — sign {'✓ positive (baseball sense)' if coef_raw > 0 else '✗ negative (unexpected)'}")
    line("")

    verdict = print_verdict(base_24, int_24, base_25, int_25,
                            "power_offense_ISO × park_hr_factor", report_lines)
    surviving = interaction_features if verdict.startswith("KEEP") else prior_features
    return verdict, surviving


# ---------------------------------------------------------------------------
# Interaction 4: elite_offense × poor_command
# ---------------------------------------------------------------------------

def run_interaction_4(prior_features: list[str], report_lines: list) -> tuple[str, list[str]]:

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    line("")
    line("=" * 76)
    line("INTERACTION 4: elite_offense × poor_command")
    line("=" * 76)
    line("")

    _init_thresholds()
    wrc_elite = _WRC_P80
    bb_poor   = _BB_POOR

    line(f"  elite_offense: wRC+ proxy > {wrc_elite:.1f} (P80 training)")
    line(f"  poor_command:  SP BB% > {bb_poor:.4f} (P80 training)")
    line(f"  Interaction: (home_elite × away_poor_cmd) + (away_elite × home_poor_cmd)")
    line("")

    all_dfs = {}
    for yr in [2022, 2023, 2024, 2025]:
        df_yr = load_df([yr])
        df_yr = enrich_with_approved(df_yr, yr, prior_features)
        df_yr = add_elite_cmd_interaction(df_yr, wrc_elite_thresh=wrc_elite,
                                          bb_poor_thresh=bb_poor)
        all_dfs[yr] = df_yr
        line(f"  {yr}: elite_wrc>{wrc_elite:.1f}, bb_poor>{bb_poor:.4f}  "
             f"interaction mean={df_yr['elite_cmd_interaction'].mean():.3f} "
             f"std={df_yr['elite_cmd_interaction'].std():.3f}")

    line("")

    df_train = pd.concat([all_dfs[yr] for yr in TRAIN_YEARS], ignore_index=True)
    df_24    = all_dfs[VALIDATE_YEAR]
    df_25    = all_dfs[OOS_YEAR]

    baseline_features    = prior_features
    interaction_features = prior_features + ["elite_cmd_interaction"]

    line("Fitting baseline Ridge...")
    pipe_base = fit_ridge(df_train, baseline_features)
    line("Fitting interaction Ridge...")
    pipe_int  = fit_ridge(df_train, interaction_features)
    line(f"  alpha: base={pipe_base.named_steps['ridge'].alpha_:.2f}  "
         f"int={pipe_int.named_steps['ridge'].alpha_:.2f}")

    sigma_base = (df_train["actual_total"].values - ridge_predict(df_train, pipe_base, baseline_features)).std(ddof=1)
    sigma_int  = (df_train["actual_total"].values - ridge_predict(df_train, pipe_int,  interaction_features)).std(ddof=1)
    line(f"  sigma: base={sigma_base:.4f}  int={sigma_int:.4f}")
    line("")

    base_24 = full_eval("Baseline 2024", df_24, pipe_base, baseline_features, sigma_base)
    int_24  = full_eval("Interact 2024", df_24, pipe_int,  interaction_features, sigma_int)
    base_25 = full_eval("Baseline 2025", df_25, pipe_base, baseline_features, sigma_base)
    int_25  = full_eval("Interact 2025", df_25, pipe_int,  interaction_features, sigma_int)

    for season_label, base_ev, int_ev in [
        ("2024 Validate", base_24, int_24),
        ("2025 OOS",      base_25, int_25),
    ]:
        line(f"{'─'*76}")
        line(f"  {season_label}  (n={base_ev['n']:,})")
        compare_evals(base_ev, int_ev, report_lines)

    coef_idx = interaction_features.index("elite_cmd_interaction")
    scaler   = pipe_int.named_steps["scaler"]
    ridge    = pipe_int.named_steps["ridge"]
    coef_std = ridge.coef_[coef_idx]
    coef_raw = coef_std / scaler.scale_[coef_idx]
    line(f"\n  elite_cmd_interaction coefficient:  std={coef_std:+.4f}  raw={coef_raw:+.4f}")
    line("")

    verdict = print_verdict(base_24, int_24, base_25, int_25,
                            "elite_offense × poor_command", report_lines)
    surviving = interaction_features if verdict.startswith("KEEP") else prior_features
    return verdict, surviving


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

INTERACTION_MAP = {
    1: run_interaction_1,
    2: run_interaction_2,
    3: run_interaction_3,
    4: run_interaction_4,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interaction", type=int, nargs="+", choices=[1, 2, 3, 4],
                        help="Which interaction(s) to test, in sequence (e.g. --interaction 1 2)")
    parser.add_argument("--all", action="store_true",
                        help="Run all interactions in sequence")
    args = parser.parse_args()

    report_lines: list[str] = []

    def hdr(s: str):
        print(s)
        report_lines.append(s)

    hdr("=" * 76)
    hdr("PHASE 6 — INTERACTION FEATURE TESTING")
    hdr("=" * 76)
    hdr("")
    hdr("  Baseline: Ridge α=500, train=2022+2023 (Phase 3 v2)")
    hdr("  Protocol: one interaction added at a time, OOS test on 2025")
    hdr("  Keep rule: OOS MAE must improve, or calibration must improve")
    hdr("             without OOS MAE degrading more than 0.02 runs")
    hdr("")
    hdr("  ⚠ Model status: strong directional baseline, NOT finished sharp model")
    hdr("  ⚠ Proxy line 8.86 used for edge/review calcs — not actual posted totals")
    hdr("")

    if args.all:
        interactions = [1, 2, 3, 4]
    elif args.interaction:
        interactions = sorted(args.interaction)
    else:
        interactions = [1]

    surviving_features = BASELINE_FEATURES
    verdicts = {}

    for i in interactions:
        fn = INTERACTION_MAP[i]
        if i == 1:
            verdict, surviving_features = fn(report_lines)
        else:
            verdict, surviving_features = fn(surviving_features, report_lines)
        verdicts[i] = verdict

    # Summary
    hdr("")
    hdr("=" * 76)
    hdr("PHASE 6 SUMMARY")
    hdr("=" * 76)
    hdr("")
    for i, v in verdicts.items():
        hdr(f"  Interaction {i}: {v}")
    hdr("")
    hdr(f"  Final feature set ({len(surviving_features)} features):")
    for f in surviving_features:
        hdr(f"    {f}")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))
    logger.info(f"Report saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
