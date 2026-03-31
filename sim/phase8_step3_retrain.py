"""
Phase 8 Step 3 — Bullpen Feature Retrain & Ablation
=====================================================
Compares Phase 6 retained baseline (19-feature Ridge) against Phase 8 models
augmented with bullpen availability features.

Candidate bullpen features:
  Depth depletion (Group A):
    home/away_relievers_last1     : # distinct relievers used previous game
    home/away_relievers_last3     : # distinct relievers used prior 3 games
  Closer availability (Group B):
    home/away_high_leverage_avail : top-3 closers not tired (< 25 pitches last 2 games)
  Bullpen quality delta (Group C):
    home/away_bullpen_delta       : bp_xFIP - sp_xFIP (how much quality drops in relief)
    home/away_bp_delta_exposure   : bullpen_delta × proj_bullpen_innings

Evaluation:
  Train: 2022+2023 | Validate: 2024 | OOS: 2025
  Metrics vs real closing lines (where available) and vs proxy for 2022+2023.

Usage:
    python3 sim/phase8_step3_retrain.py
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

SIM_DIR     = Path(__file__).resolve().parent
PROJECT_DIR = SIM_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from config import BET_EDGE, BET_PROB, WIN_UNIT
from sim.phase6_interactions import (
    BASELINE_FEATURES,
    TRAIN_YEARS,
    VALIDATE_YEAR,
    OOS_YEAR,
    ALPHAS,
    add_flyball_wind_interaction,
    enrich_with_approved,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FEATURE_TABLE    = SIM_DIR / "data" / "feature_table.parquet"
BULLPEN_FEATURES = SIM_DIR / "data" / "bullpen_features.parquet"
MARKET_SNAPS     = SIM_DIR / "data" / "market_snapshots.parquet"
REPORT_PATH      = SIM_DIR / "reports" / "phase8_bullpen_retrain.txt"
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Phase 6 retained feature set (18 baseline + flyball×wind)
PHASE6_FEATURES = BASELINE_FEATURES + ["flyball_wind_interaction"]

# Bullpen candidate feature columns (after merge)
BULLPEN_COLS = [
    "home_relievers_last1",
    "away_relievers_last1",
    "home_relievers_last3",
    "away_relievers_last3",
    "home_high_leverage_avail",
    "away_high_leverage_avail",
    "home_bullpen_delta",
    "away_bullpen_delta",
    "home_bp_delta_exposure",
    "away_bp_delta_exposure",
]

# Ablation groups
ABLATION_GROUPS = {
    "no_depth_depletion": [c for c in BULLPEN_COLS if "last" not in c],
    "no_closer_avail":    [c for c in BULLPEN_COLS if "high_leverage" not in c],
    "no_quality_delta":   [c for c in BULLPEN_COLS if "delta" not in c],
}

PROXY_LINE = 8.86
N_SIMS     = 10_000
SEED       = 42

# ---------------------------------------------------------------------------
# 1. Data loading and feature construction
# ---------------------------------------------------------------------------

def load_and_merge() -> pd.DataFrame:
    """
    Load feature_table, add flyball interaction, merge home+away bullpen
    features, compute delta features. Returns full enriched DataFrame.
    """
    ft = pd.read_parquet(FEATURE_TABLE)
    ft["doubleheader_flag"] = ft["doubleheader_flag"].astype(int)

    # Add flyball×wind per year (cached)
    chunks = []
    for yr in [2022, 2023, 2024, 2025]:
        sub = ft[ft["season"] == yr].copy()
        sub = add_flyball_wind_interaction(sub, yr)
        chunks.append(sub)
    ft = pd.concat(chunks, ignore_index=True)

    # Load bullpen features
    bf = pd.read_parquet(BULLPEN_FEATURES)

    # Merge home team bullpen features
    home_bp = bf.rename(columns={
        "relievers_used_last_game":   "home_relievers_last1",
        "relievers_used_last_3_games":"home_relievers_last3",
        "high_leverage_available":    "home_high_leverage_avail",
        "bullpen_pitches_last_game":  "home_bp_pitches_last1",
        "bullpen_pitches_last_3_games":"home_bp_pitches_last3",
    })[["game_pk","team",
        "home_relievers_last1","home_relievers_last3",
        "home_high_leverage_avail"]].rename(columns={"team":"home_team"})

    away_bp = bf.rename(columns={
        "relievers_used_last_game":   "away_relievers_last1",
        "relievers_used_last_3_games":"away_relievers_last3",
        "high_leverage_available":    "away_high_leverage_avail",
        "bullpen_pitches_last_game":  "away_bp_pitches_last1",
        "bullpen_pitches_last_3_games":"away_bp_pitches_last3",
    })[["game_pk","team",
        "away_relievers_last1","away_relievers_last3",
        "away_high_leverage_avail"]].rename(columns={"team":"away_team"})

    ft = ft.merge(home_bp, on=["game_pk","home_team"], how="left")
    ft = ft.merge(away_bp, on=["game_pk","away_team"], how="left")

    # Derived delta features (from existing feature_table columns)
    ft["home_bullpen_delta"]    = ft["home_bp_xfip"] - ft["home_sp_xfip"]
    ft["away_bullpen_delta"]    = ft["away_bp_xfip"] - ft["away_sp_xfip"]
    ft["home_bp_delta_exposure"]= ft["home_bullpen_delta"] * ft["home_bp_proj_inn"]
    ft["away_bp_delta_exposure"]= ft["away_bullpen_delta"] * ft["away_bp_proj_inn"]

    return ft


def load_market() -> pd.DataFrame:
    """Real closing lines for 2024+2025 games."""
    ms = pd.read_parquet(MARKET_SNAPS)
    ms = ms.rename(columns={"game_id": "game_pk"})
    return ms[["game_pk","close_total","over_price","under_price"]]


# ---------------------------------------------------------------------------
# 2. Ridge training
# ---------------------------------------------------------------------------

def fit_ridge(df_train: pd.DataFrame, features: list[str]) -> Pipeline:
    X = df_train[features].copy()
    for c in features:
        if X[c].isna().any():
            X[c] = X[c].fillna(X[c].median())
    y = df_train["actual_total"].values
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  RidgeCV(alphas=ALPHAS, cv=5)),
    ])
    pipe.fit(X.values, y)
    return pipe


def predict(df: pd.DataFrame, pipe: Pipeline, features: list[str]) -> np.ndarray:
    X = df[features].copy()
    for c in features:
        if X[c].isna().any():
            X[c] = X[c].fillna(X[c].median())
    return pipe.predict(X.values)


def train_sigma(df_train: pd.DataFrame, pipe: Pipeline, features: list[str]) -> float:
    preds = predict(df_train, pipe, features)
    return float((df_train["actual_total"].values - preds).std(ddof=1))


# ---------------------------------------------------------------------------
# 3. Probability simulation
# ---------------------------------------------------------------------------

def compute_p_over(preds: np.ndarray, sigma: float, line: float) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    noise = rng.normal(0, sigma, size=(len(preds), N_SIMS))
    sims = preds[:, None] + noise
    return (sims > line).mean(axis=1)


# ---------------------------------------------------------------------------
# 4. Metrics
# ---------------------------------------------------------------------------

def compute_metrics(actual: np.ndarray, preds: np.ndarray,
                    line: float = PROXY_LINE) -> dict:
    mae  = mean_absolute_error(actual, preds)
    rmse = np.sqrt(mean_squared_error(actual, preds))
    r    = np.corrcoef(actual, preds)[0, 1]
    rho  = stats.spearmanr(actual, preds).statistic
    over_lean  = preds > line
    under_lean = preds < line
    has_lean   = over_lean | under_lean
    hits = ((over_lean & (actual > line)) | (under_lean & (actual <= line))) & has_lean
    dhr  = float(hits.sum() / has_lean.sum()) if has_lean.sum() > 0 else float("nan")
    return dict(mae=mae, rmse=rmse, r=r, rho=rho, dhr=dhr)


def roi_vs_real(preds: np.ndarray, sigma: float,
                df_eval: pd.DataFrame, df_market: pd.DataFrame) -> dict:
    """
    Simulate ROI using real closing lines. BET_EDGE=1.0, BET_PROB=0.55.
    Returns dict with n_bets, win_pct, roi, and by-year breakdown.
    """
    merged = df_eval[["game_pk","actual_total","season"]].copy()
    merged["pred"] = preds
    merged = merged.merge(df_market, on="game_pk", how="inner")
    merged = merged.dropna(subset=["close_total"])

    results = []
    for _, row in merged.iterrows():
        line   = row["close_total"]
        pred   = row["pred"]
        actual = row["actual_total"]
        edge   = abs(pred - line)
        if edge < BET_EDGE:
            continue

        # P(over) vs real closing line
        rng  = np.random.default_rng(SEED + int(row["game_pk"]) % 10000)
        sims = rng.normal(pred, sigma, N_SIMS)
        if pred > line:
            p_side = (sims > line).mean()
            if p_side < BET_PROB:
                continue
            won = actual > line
        else:
            p_side = (sims < line).mean()
            if p_side < BET_PROB:
                continue
            won = actual <= line

        results.append({"season": int(row["season"]), "won": won})

    if not results:
        return dict(n_bets=0, win_pct=float("nan"), roi=float("nan"),
                    by_year={})

    df_res = pd.DataFrame(results)
    total  = len(df_res)
    wins   = df_res["won"].sum()
    roi    = float((wins * WIN_UNIT - (total - wins)) / total * 100)

    by_year = {}
    for yr, grp in df_res.groupby("season"):
        w = grp["won"].sum()
        n = len(grp)
        by_year[int(yr)] = dict(
            n=n, wins=int(w),
            win_pct=float(w/n),
            roi=float((w * WIN_UNIT - (n-w)) / n * 100)
        )

    return dict(n_bets=total, win_pct=float(wins/total), roi=roi, by_year=by_year)


def confidence_tier_perf(preds: np.ndarray, sigma: float,
                          df_eval: pd.DataFrame, df_market: pd.DataFrame) -> list[dict]:
    """ROI by confidence tier (WATCHLIST/BET/STRONG) vs real closing lines."""
    from config import (WATCHLIST_EDGE, BET_EDGE, STRONG_EDGE,
                        WATCHLIST_PROB, BET_PROB, STRONG_PROB)

    merged = df_eval[["game_pk","actual_total"]].copy()
    merged["pred"] = preds
    merged = merged.merge(df_market, on="game_pk", how="inner")
    merged = merged.dropna(subset=["close_total"])

    rows = []
    for _, row in merged.iterrows():
        line   = row["close_total"]
        pred   = row["pred"]
        actual = row["actual_total"]
        edge   = abs(pred - line)

        rng  = np.random.default_rng(SEED + int(row["game_pk"]) % 10000)
        sims = rng.normal(pred, sigma, N_SIMS)
        if pred > line:
            p_side = float((sims > line).mean())
            won    = actual > line
        else:
            p_side = float((sims < line).mean())
            won    = actual <= line

        if edge >= STRONG_EDGE and p_side >= STRONG_PROB:
            tier = "STRONG"
        elif edge >= BET_EDGE and p_side >= BET_PROB:
            tier = "BET"
        elif edge >= WATCHLIST_EDGE and p_side >= WATCHLIST_PROB:
            tier = "WATCHLIST"
        else:
            continue
        rows.append({"tier": tier, "won": won})

    if not rows:
        return []

    df_t = pd.DataFrame(rows)
    out  = []
    for tier in ["STRONG","BET","WATCHLIST"]:
        sub = df_t[df_t["tier"] == tier]
        if len(sub) == 0:
            continue
        w  = sub["won"].sum()
        n  = len(sub)
        roi= float((w * WIN_UNIT - (n-w)) / n * 100)
        out.append(dict(tier=tier, n=n, win_pct=float(w/n), roi=roi))
    return out


def edge_bucket_table(preds: np.ndarray, actual: np.ndarray,
                       close_total: np.ndarray) -> list[dict]:
    """Directional hit rate by |pred − close_total| bucket."""
    bins   = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, np.inf]
    labels = ["0.0–0.5","0.5–1.0","1.0–1.5","1.5–2.0",
              "2.0–2.5","2.5–3.0","3.0–4.0","4.0+"]
    edge   = np.abs(preds - close_total)
    over   = preds > close_total
    under  = preds < close_total
    hit    = ((over & (actual > close_total)) | (under & (actual <= close_total)))
    rows = []
    for lo, hi, lbl in zip(bins[:-1], bins[1:], labels):
        mask = (edge >= lo) & (edge < hi)
        if mask.sum() == 0:
            continue
        rows.append({"bucket": lbl, "n": int(mask.sum()),
                     "hit_pct": float(hit[mask].mean())})
    return rows


def residual_diagnostics(preds: np.ndarray, actual: np.ndarray,
                          market: np.ndarray) -> dict:
    """
    corr(model, market), ΔR² over market alone.
    market = close_total for matched games.
    """
    from sklearn.linear_model import LinearRegression as LR

    # R² with market alone
    lm_mkt = LR().fit(market.reshape(-1,1), actual)
    r2_mkt = lm_mkt.score(market.reshape(-1,1), actual)

    # R² with market + model
    X_both = np.column_stack([market, preds])
    lm_both = LR().fit(X_both, actual)
    r2_both = lm_both.score(X_both, actual)

    corr_model_mkt = float(np.corrcoef(preds, market)[0, 1])
    mkt_error      = actual - market          # what market gets wrong
    model_edge     = preds - market           # model's excess over market
    corr_edge_err  = float(np.corrcoef(model_edge, mkt_error)[0, 1])

    return dict(
        corr_model_market=corr_model_mkt,
        corr_edge_market_error=corr_edge_err,
        r2_market_only=float(r2_mkt),
        r2_market_plus_model=float(r2_both),
        delta_r2=float(r2_both - r2_mkt),
    )


# ---------------------------------------------------------------------------
# 5. Full evaluation for one model on one season
# ---------------------------------------------------------------------------

def evaluate_model(label: str, df_eval: pd.DataFrame,
                   pipe: Pipeline, features: list[str], sigma: float,
                   df_market: pd.DataFrame) -> dict:
    actual = df_eval["actual_total"].values
    preds  = predict(df_eval, pipe, features)

    # Primary metrics vs proxy
    m_proxy = compute_metrics(actual, preds, PROXY_LINE)

    # Merge with real closing lines
    merged = df_eval[["game_pk","actual_total","season"]].copy()
    merged["pred"] = preds
    merged = merged.merge(df_market, on="game_pk", how="inner")
    merged = merged.dropna(subset=["close_total"])

    m_real = {}
    diag   = {}
    edge_bkts = []
    roi_r  = {}
    tier_r = []

    if len(merged) > 0:
        a_r    = merged["actual_total"].values
        p_r    = merged["pred"].values
        cl_r   = merged["close_total"].values
        m_real = compute_metrics(a_r, p_r, line=cl_r.mean())
        # directional vs real closing line per-game
        over_lean  = p_r > cl_r
        under_lean = p_r < cl_r
        has_lean   = over_lean | under_lean
        hits = ((over_lean & (a_r > cl_r)) | (under_lean & (a_r <= cl_r))) & has_lean
        m_real["dhr_real"] = float(hits.sum() / has_lean.sum()) if has_lean.sum() > 0 else float("nan")

        diag      = residual_diagnostics(p_r, a_r, cl_r)
        edge_bkts = edge_bucket_table(p_r, a_r, cl_r)
        roi_r     = roi_vs_real(preds, sigma, df_eval, df_market)
        tier_r    = confidence_tier_perf(preds, sigma, df_eval, df_market)

    p_over = compute_p_over(preds, sigma, PROXY_LINE)

    return dict(
        label=label, n=len(actual),
        preds=preds, actual=actual, p_over=p_over, sigma=sigma,
        metrics_proxy=m_proxy,
        metrics_real=m_real,
        diagnostics=diag,
        edge_buckets=edge_bkts,
        roi=roi_r,
        tiers=tier_r,
        n_matched=len(merged),
    )


# ---------------------------------------------------------------------------
# 6. Coefficient table
# ---------------------------------------------------------------------------

def coef_table(pipe: Pipeline, features: list[str]) -> list[dict]:
    scaler = pipe.named_steps["scaler"]
    ridge  = pipe.named_steps["ridge"]
    rows = []
    for i, feat in enumerate(features):
        std_coef = float(ridge.coef_[i])
        raw_coef = float(std_coef / scaler.scale_[i]) if scaler.scale_[i] != 0 else 0.0
        rows.append(dict(feature=feat, std_coef=std_coef, raw_coef=raw_coef,
                         abs_std=abs(std_coef)))
    return sorted(rows, key=lambda r: -r["abs_std"])


# ---------------------------------------------------------------------------
# 7. Report printer
# ---------------------------------------------------------------------------

def print_section(lines_out: list, *args):
    s = " ".join(str(a) for a in args)
    print(s)
    lines_out.append(s)

def pln(lines_out: list, s: str = ""):
    print(s)
    lines_out.append(s)


def print_eval_block(e24: dict, e25: dict, tag: str, lines_out: list):
    pln(lines_out)
    pln(lines_out, f"  ── {tag} ──")
    pln(lines_out, f"  {'Metric':<30}  {'2024 Validate':>15}  {'2025 OOS':>15}")
    pln(lines_out, f"  {'─'*30}  {'─'*15}  {'─'*15}")

    def row(label, v24, v25, fmt=".4f"):
        s = f"  {label:<30}  {v24:>15{fmt}}  {v25:>15{fmt}}"
        pln(lines_out, s)

    mp24 = e24["metrics_proxy"]
    mp25 = e25["metrics_proxy"]
    row("MAE (vs proxy)",     mp24["mae"],  mp25["mae"])
    row("RMSE (vs proxy)",    mp24["rmse"], mp25["rmse"])
    row("Pearson r",          mp24["r"],    mp25["r"])
    row("Spearman ρ",         mp24["rho"],  mp25["rho"])
    row("DHR proxy",          mp24["dhr"],  mp25["dhr"], fmt=".3f")

    mr24 = e24.get("metrics_real", {})
    mr25 = e25.get("metrics_real", {})
    if mr24 and mr25:
        row("DHR vs real closing line", mr24.get("dhr_real", float("nan")),
                                        mr25.get("dhr_real", float("nan")), fmt=".3f")

    d24 = e24.get("diagnostics", {})
    d25 = e25.get("diagnostics", {})
    if d24 and d25:
        row("corr(model, market)",      d24["corr_model_market"],     d25["corr_model_market"])
        row("corr(edge, mkt_error)",    d24["corr_edge_market_error"],d25["corr_edge_market_error"])
        row("R²(actual ~ market)",      d24["r2_market_only"],        d25["r2_market_only"])
        row("R²(actual ~ mkt+model)",   d24["r2_market_plus_model"],  d25["r2_market_plus_model"])
        row("ΔR² over market",          d24["delta_r2"],              d25["delta_r2"])

    r24 = e24.get("roi", {})
    r25 = e25.get("roi", {})
    if r24 and r25:
        pln(lines_out)
        pln(lines_out, f"  {'ROI vs real closing lines':}")
        pln(lines_out, f"  {'─'*62}")

        def rrow(label, v24, v25, fmt=".1f"):
            pln(lines_out, f"  {label:<30}  {v24:>15{fmt}}  {v25:>15{fmt}}")

        rrow("N bets",    float(r24.get("n_bets",0)), float(r25.get("n_bets",0)), fmt=".0f")
        rrow("Win %",     r24.get("win_pct", float("nan"))*100,
                          r25.get("win_pct", float("nan"))*100, fmt=".1f")
        rrow("ROI %",     r24.get("roi", float("nan")),
                          r25.get("roi", float("nan")), fmt=".1f")

        # by-year for each season
        for yr in [2024, 2025]:
            by24 = r24.get("by_year",{}).get(yr, {})
            by25 = r25.get("by_year",{}).get(yr, {})
            if by24 or by25:
                rrow(f"  {yr} ROI %",
                     by24.get("roi", float("nan")),
                     by25.get("roi", float("nan")), fmt=".1f")


def print_tier_block(e24: dict, e25: dict, tag: str, lines_out: list):
    pln(lines_out)
    pln(lines_out, f"  Confidence tiers ({tag}):")
    pln(lines_out, f"  {'Tier':<12}  {'2024 N':>7}  {'2024 Win%':>9}  {'2024 ROI%':>9}"
                   f"  {'2025 N':>7}  {'2025 Win%':>9}  {'2025 ROI%':>9}")
    pln(lines_out, f"  {'─'*12}  {'─'*7}  {'─'*9}  {'─'*9}  {'─'*7}  {'─'*9}  {'─'*9}")

    tiers24 = {t["tier"]: t for t in e24.get("tiers", [])}
    tiers25 = {t["tier"]: t for t in e25.get("tiers", [])}
    for tier in ["STRONG","BET","WATCHLIST"]:
        t24 = tiers24.get(tier, {})
        t25 = tiers25.get(tier, {})
        pln(lines_out,
            f"  {tier:<12}  "
            f"{t24.get('n',0):>7}  {t24.get('win_pct',float('nan'))*100:>9.1f}  "
            f"{t24.get('roi',float('nan')):>9.1f}  "
            f"{t25.get('n',0):>7}  {t25.get('win_pct',float('nan'))*100:>9.1f}  "
            f"{t25.get('roi',float('nan')):>9.1f}")


def print_edge_bucket(e24: dict, e25: dict, tag: str, lines_out: list):
    pln(lines_out)
    pln(lines_out, f"  Edge bucket monotonicity ({tag}) — vs real closing line:")
    pln(lines_out, f"  {'Bucket':>10}  {'2024 N':>7}  {'2024 Hit%':>9}  {'2025 N':>7}  {'2025 Hit%':>9}")
    pln(lines_out, f"  {'─'*10}  {'─'*7}  {'─'*9}  {'─'*7}  {'─'*9}")

    bkts24 = {r["bucket"]: r for r in e24.get("edge_buckets",[])}
    bkts25 = {r["bucket"]: r for r in e25.get("edge_buckets",[])}
    all_bkts = list(dict.fromkeys(
        list(bkts24.keys()) + list(bkts25.keys())
    ))
    for bkt in all_bkts:
        b24 = bkts24.get(bkt, {"n":0,"hit_pct":float("nan")})
        b25 = bkts25.get(bkt, {"n":0,"hit_pct":float("nan")})
        pln(lines_out,
            f"  {bkt:>10}  {b24['n']:>7}  {b24['hit_pct']:>9.1%}  "
            f"{b25['n']:>7}  {b25['hit_pct']:>9.1%}")


def print_coef_block(pipe: Pipeline, features: list[str], label: str, lines_out: list):
    pln(lines_out)
    pln(lines_out, f"  Coefficients — {label} (sorted by |std coef|):")
    pln(lines_out, f"  {'Feature':<32}  {'Std coef':>10}  {'Raw coef':>10}")
    pln(lines_out, f"  {'─'*32}  {'─'*10}  {'─'*10}")
    for r in coef_table(pipe, features):
        pln(lines_out, f"  {r['feature']:<32}  {r['std_coef']:>+10.4f}  {r['raw_coef']:>+10.4f}")


def compare_roi(base_roi: dict, new_roi: dict, label: str, lines_out: list):
    b25 = base_roi.get("by_year",{}).get(2025,{})
    n25 = new_roi.get("by_year",{}).get(2025,{})
    b_roi = b25.get("roi", float("nan"))
    n_roi = n25.get("roi", float("nan"))
    delta = n_roi - b_roi if not (np.isnan(b_roi) or np.isnan(n_roi)) else float("nan")
    improved = (not np.isnan(delta)) and delta > 0.1
    pln(lines_out,
        f"  {label:<35}  base={b_roi:+.1f}%  new={n_roi:+.1f}%  "
        f"Δ={delta:+.1f}%  {'IMPROVED ✓' if improved else 'NO GAIN ✗'}")


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main():
    lines_out: list[str] = []

    def hdr(s: str = ""):
        pln(lines_out, s)

    hdr("=" * 78)
    hdr("PHASE 8 STEP 3 — BULLPEN FEATURE RETRAIN & ABLATION")
    hdr("=" * 78)
    hdr()
    hdr("  Baseline: Phase 6 retained (19 features, Ridge α=CV, train=2022+2023)")
    hdr("  Bullpen candidate features: depth depletion (A), closer avail (B), quality Δ (C)")
    hdr("  Keep rule: 2025 OOS ROI vs real closing lines must improve")
    hdr("  Real closing lines available for 2024+2025 (4,855 games, all closing_only)")
    hdr()

    # ── Load data ─────────────────────────────────────────────────────────────
    print("Loading and merging data...", flush=True)
    df = load_and_merge()
    df_market = load_market()
    print(f"  df shape: {df.shape}  market: {len(df_market)} games")

    # Null counts for bullpen features
    hdr("  Bullpen feature null rates (first game of each team-season = NaN, expected ~0.5%):")
    for c in BULLPEN_COLS:
        if c in df.columns:
            pct = df[c].isna().mean() * 100
            hdr(f"    {c:<30}  {pct:.2f}% null")
    hdr()

    # Split
    df_train = df[df["season"].isin(TRAIN_YEARS)].copy()
    df_24    = df[df["season"] == VALIDATE_YEAR].copy()
    df_25    = df[df["season"] == OOS_YEAR].copy()

    print(f"  Train: {len(df_train)}  Val2024: {len(df_24)}  OOS2025: {len(df_25)}")

    # Impute NaN in bullpen features with median from training set (first game of season)
    for c in BULLPEN_COLS:
        if c in df.columns:
            med = df_train[c].median()
            df_train[c] = df_train[c].fillna(med)
            df_24[c]    = df_24[c].fillna(med)
            df_25[c]    = df_25[c].fillna(med)

    # ── Phase 6 baseline ──────────────────────────────────────────────────────
    hdr("=" * 78)
    hdr("PHASE 6 BASELINE (19 features)")
    hdr("=" * 78)
    print("Fitting Phase 6 baseline...", flush=True)
    pipe_base  = fit_ridge(df_train, PHASE6_FEATURES)
    sigma_base = train_sigma(df_train, pipe_base, PHASE6_FEATURES)
    alpha_base = pipe_base.named_steps["ridge"].alpha_
    hdr(f"  α={alpha_base:.1f}  σ={sigma_base:.4f}")

    ev_base_24 = evaluate_model("Phase6 2024", df_24, pipe_base, PHASE6_FEATURES,
                                 sigma_base, df_market)
    ev_base_25 = evaluate_model("Phase6 2025", df_25, pipe_base, PHASE6_FEATURES,
                                 sigma_base, df_market)

    print_eval_block(ev_base_24, ev_base_25, "Phase 6 Baseline", lines_out)
    print_tier_block(ev_base_24, ev_base_25, "Phase 6 Baseline", lines_out)
    print_edge_bucket(ev_base_24, ev_base_25, "Phase 6 Baseline", lines_out)
    print_coef_block(pipe_base, PHASE6_FEATURES, "Phase 6 Baseline", lines_out)

    # ── Phase 8 full bullpen block ─────────────────────────────────────────────
    hdr()
    hdr("=" * 78)
    hdr("PHASE 8 — FULL BULLPEN BLOCK (19 + 10 = 29 features)")
    hdr("=" * 78)

    FULL_FEATURES = PHASE6_FEATURES + BULLPEN_COLS
    print("Fitting Phase 8 full bullpen model...", flush=True)
    pipe_full  = fit_ridge(df_train, FULL_FEATURES)
    sigma_full = train_sigma(df_train, pipe_full, FULL_FEATURES)
    alpha_full = pipe_full.named_steps["ridge"].alpha_
    hdr(f"  α={alpha_full:.1f}  σ={sigma_full:.4f}")

    ev_full_24 = evaluate_model("Phase8Full 2024", df_24, pipe_full, FULL_FEATURES,
                                 sigma_full, df_market)
    ev_full_25 = evaluate_model("Phase8Full 2025", df_25, pipe_full, FULL_FEATURES,
                                 sigma_full, df_market)

    print_eval_block(ev_full_24, ev_full_25, "Phase 8 Full Bullpen", lines_out)
    print_tier_block(ev_full_24, ev_full_25, "Phase 8 Full Bullpen", lines_out)
    print_edge_bucket(ev_full_24, ev_full_25, "Phase 8 Full Bullpen", lines_out)
    print_coef_block(pipe_full, FULL_FEATURES, "Phase 8 Full Bullpen", lines_out)

    # ── Ablation ──────────────────────────────────────────────────────────────
    hdr()
    hdr("=" * 78)
    hdr("ABLATION TABLE (remove one feature group at a time)")
    hdr("=" * 78)

    ablation_results = {}
    for abl_name, abl_cols in ABLATION_GROUPS.items():
        abl_features = PHASE6_FEATURES + abl_cols
        removed = set(BULLPEN_COLS) - set(abl_cols)
        hdr()
        hdr(f"  Ablation: {abl_name}")
        hdr(f"    Kept bullpen cols ({len(abl_cols)}): {abl_cols}")
        hdr(f"    Removed: {sorted(removed)}")

        pipe_abl  = fit_ridge(df_train, abl_features)
        sigma_abl = train_sigma(df_train, pipe_abl, abl_features)
        hdr(f"    α={pipe_abl.named_steps['ridge'].alpha_:.1f}  σ={sigma_abl:.4f}")

        ev_abl_24 = evaluate_model(f"{abl_name} 2024", df_24, pipe_abl, abl_features,
                                   sigma_abl, df_market)
        ev_abl_25 = evaluate_model(f"{abl_name} 2025", df_25, pipe_abl, abl_features,
                                   sigma_abl, df_market)

        print_eval_block(ev_abl_24, ev_abl_25, f"Ablation: {abl_name}", lines_out)
        print_tier_block(ev_abl_24, ev_abl_25, f"Ablation: {abl_name}", lines_out)
        print_coef_block(pipe_abl, abl_features, f"Ablation: {abl_name}", lines_out)

        ablation_results[abl_name] = (ev_abl_24, ev_abl_25)

    # ── Summary comparison table ───────────────────────────────────────────────
    hdr()
    hdr("=" * 78)
    hdr("SUMMARY: 2025 OOS ROI vs REAL CLOSING LINES")
    hdr("=" * 78)
    hdr("  (Key question: does any bullpen configuration improve -0.5% baseline ROI?)")
    hdr()
    hdr(f"  {'Model':<35}  {'Base 2025 ROI':>13}  {'New 2025 ROI':>13}  {'Delta':>8}  Verdict")
    hdr(f"  {'─'*35}  {'─'*13}  {'─'*13}  {'─'*8}  {'─'*8}")

    base_roi = ev_base_25.get("roi", {})
    base_r25 = base_roi.get("by_year",{}).get(2025,{}).get("roi", float("nan"))

    def verdict_row(label: str, new_ev25: dict):
        new_roi = new_ev25.get("roi",{})
        new_r25 = new_roi.get("by_year",{}).get(2025,{}).get("roi", float("nan"))
        new_n   = new_roi.get("by_year",{}).get(2025,{}).get("n", 0)
        delta   = new_r25 - base_r25 if not (np.isnan(base_r25) or np.isnan(new_r25)) else float("nan")
        verdict = "IMPROVED ✓" if (not np.isnan(delta) and delta > 0.1) else "NO GAIN ✗"
        hdr(f"  {label:<35}  {base_r25:>+13.1f}%  {new_r25:>+13.1f}%  "
            f"{delta:>+8.1f}%  {verdict}  (n={new_n})")

    verdict_row("Phase 8 Full (all bullpen)",       ev_full_25)
    for abl_name, (_, ev_abl_25) in ablation_results.items():
        verdict_row(f"Ablation: {abl_name}", ev_abl_25)

    # Full side-by-side metric comparison
    hdr()
    hdr("=" * 78)
    hdr("FULL METRIC COMPARISON — Phase 6 Baseline vs Phase 8 Full Bullpen")
    hdr("=" * 78)
    hdr()
    hdr(f"  {'Metric':<30}  {'P6 2024':>10}  {'P8 2024':>10}  {'Δ2024':>8}  "
        f"{'P6 2025':>10}  {'P8 2025':>10}  {'Δ2025':>8}")
    hdr(f"  {'─'*30}  {'─'*10}  {'─'*10}  {'─'*8}  {'─'*10}  {'─'*10}  {'─'*8}")

    def compare_row(label, key, sub=None, fmt=".4f", good="lower"):
        def get(ev, key, sub):
            d = ev
            if sub:
                d = d.get(sub, {})
            return d.get(key, float("nan"))

        v_b24 = get(ev_base_24, key, sub)
        v_n24 = get(ev_full_24, key, sub)
        v_b25 = get(ev_base_25, key, sub)
        v_n25 = get(ev_full_25, key, sub)

        d24   = v_n24 - v_b24 if not (np.isnan(v_b24) or np.isnan(v_n24)) else float("nan")
        d25   = v_n25 - v_b25 if not (np.isnan(v_b25) or np.isnan(v_n25)) else float("nan")

        def mark(d, good):
            if np.isnan(d): return "  "
            return " ✓" if ((d < 0 and good=="lower") or (d > 0 and good=="higher")) else " ✗"

        hdr(f"  {label:<30}  {v_b24:>{10}{fmt}}  {v_n24:>{10}{fmt}}  "
            f"{d24:>{8}.4f}{mark(d24,good)}  "
            f"{v_b25:>{10}{fmt}}  {v_n25:>{10}{fmt}}  "
            f"{d25:>{8}.4f}{mark(d25,good)}")

    compare_row("MAE (proxy)",         "mae",  "metrics_proxy", good="lower")
    compare_row("RMSE (proxy)",        "rmse", "metrics_proxy", good="lower")
    compare_row("Pearson r",           "r",    "metrics_proxy", good="higher")
    compare_row("Spearman ρ",          "rho",  "metrics_proxy", good="higher")
    compare_row("DHR proxy",           "dhr",  "metrics_proxy", good="higher")
    compare_row("DHR vs real line",    "dhr_real", "metrics_real", good="higher")
    compare_row("corr(model,market)",  "corr_model_market", "diagnostics", good="higher")
    compare_row("corr(edge,mkt_err)",  "corr_edge_market_error", "diagnostics", good="higher")
    compare_row("R²(market alone)",    "r2_market_only", "diagnostics", good="higher")
    compare_row("R²(mkt+model)",       "r2_market_plus_model", "diagnostics", good="higher")
    compare_row("ΔR²",                 "delta_r2", "diagnostics", good="higher")

    # ROI rows
    def roi_compare_row(label, yr):
        b24r = ev_base_24.get("roi",{}).get("by_year",{}).get(yr,{}).get("roi", float("nan"))
        n24r = ev_full_24.get("roi",{}).get("by_year",{}).get(yr,{}).get("roi", float("nan"))
        b25r = ev_base_25.get("roi",{}).get("by_year",{}).get(yr,{}).get("roi", float("nan"))
        n25r = ev_full_25.get("roi",{}).get("by_year",{}).get(yr,{}).get("roi", float("nan"))
        d24  = n24r - b24r if not (np.isnan(b24r) or np.isnan(n24r)) else float("nan")
        d25  = n25r - b25r if not (np.isnan(b25r) or np.isnan(n25r)) else float("nan")
        def mk(d): return " ✓" if (not np.isnan(d) and d > 0) else " ✗"
        hdr(f"  {label:<30}  {b24r:>10.1f}  {n24r:>10.1f}  "
            f"{d24:>+8.1f}%{mk(d24)}  "
            f"{b25r:>10.1f}  {n25r:>10.1f}  "
            f"{d25:>+8.1f}%{mk(d25)}")

    roi_compare_row("ROI % (2024 games)",    2024)
    roi_compare_row("ROI % (2025 games)",    2025)

    # Win pct compare
    b24w = ev_base_24.get("roi",{}).get("by_year",{}).get(2024,{}).get("win_pct",float("nan"))
    n24w = ev_full_24.get("roi",{}).get("by_year",{}).get(2024,{}).get("win_pct",float("nan"))
    b25w = ev_base_25.get("roi",{}).get("by_year",{}).get(2025,{}).get("win_pct",float("nan"))
    n25w = ev_full_25.get("roi",{}).get("by_year",{}).get(2025,{}).get("win_pct",float("nan"))
    hdr(f"  {'Win % (bets)':<30}  {b24w*100:>10.1f}  {n24w*100:>10.1f}  "
        f"{'':>10}  "
        f"{b25w*100:>10.1f}  {n25w*100:>10.1f}")

    # Final verdict
    hdr()
    hdr("=" * 78)
    hdr("FINAL VERDICT")
    hdr("=" * 78)
    hdr()

    b25_roi  = base_r25
    f25_roi  = ev_full_25.get("roi",{}).get("by_year",{}).get(2025,{}).get("roi", float("nan"))
    delta_roi = f25_roi - b25_roi if not (np.isnan(b25_roi) or np.isnan(f25_roi)) else float("nan")

    b25_mae  = ev_base_25["metrics_proxy"]["mae"]
    f25_mae  = ev_full_25["metrics_proxy"]["mae"]
    delta_mae = f25_mae - b25_mae

    if not np.isnan(delta_roi) and delta_roi > 0.5:
        verdict = "KEEP full bullpen block"
        rationale = f"2025 OOS ROI improved by {delta_roi:+.1f}pp vs real closing lines"
    elif not np.isnan(delta_roi) and delta_roi > 0.0:
        verdict = "KEEP (marginal) — ablation to find minimal subset"
        rationale = f"2025 OOS ROI improved by {delta_roi:+.1f}pp — marginal, check ablation"
    else:
        verdict = "DROP — bullpen block does not improve 2025 OOS ROI vs real lines"
        rationale = (f"2025 OOS ROI: {b25_roi:+.1f}% → {f25_roi:+.1f}% "
                     f"(Δ={delta_roi:+.1f}pp). MAE: {b25_mae:.4f}→{f25_mae:.4f}.")

    hdr(f"  VERDICT: {verdict}")
    hdr(f"  {rationale}")
    hdr()

    # Ablation-informed keep/drop
    hdr("  Ablation guidance:")
    for abl_name, (_, ev_abl_25) in ablation_results.items():
        a25_roi = ev_abl_25.get("roi",{}).get("by_year",{}).get(2025,{}).get("roi", float("nan"))
        d = a25_roi - b25_roi if not (np.isnan(a25_roi) or np.isnan(b25_roi)) else float("nan")
        removed = set(BULLPEN_COLS) - set(ABLATION_GROUPS[abl_name])
        verdict_a = "contributes ✓" if (not np.isnan(d) and d > 0) else "redundant/harmful ✗"
        hdr(f"    {abl_name:<35}: ROI Δ={d:+.1f}pp → removed group is {verdict_a}")

    hdr()
    hdr("  Proceed to Phase 9 only if 2025 OOS ROI vs real closing lines is positive.")
    hdr()

    # Save
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines_out))
    print(f"\nReport saved → {REPORT_PATH}")


if __name__ == "__main__":
    main()
