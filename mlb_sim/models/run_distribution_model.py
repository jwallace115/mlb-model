#!/usr/bin/env python3
"""
MLB Simulation Engine — Phase S3: Conditional Run Distribution Engine
=====================================================================
Generates full run scoring distributions conditional on starter path
probabilities from S2. Emphasis on tail shape and skew, not MAE.

Architecture:
  1. Sample starter paths (soft weighted, not argmax)
  2. Assign scoring regime from path combination
  3. Draw runs from Negative Binomial parameterized by regime
  4. Monte Carlo: 20,000 draws per game

Regimes:
  1 — Suppression (both Deep): tightest distribution
  2 — Normal (≥1 Path 1, no Path 0): medium variance
  3 — Fragile (exactly 1 Path 0): widened right tail
  4 — High Chaos (both Path 0): widest variance, heaviest right tail

Hard rules:
  - Path probabilities are SOFT WEIGHTS, not hard switches
  - CSW is never a direct mean-runs feature
  - Closing line is evaluation only — never a model input
  - All parameters frozen on train before touching 2024 OOS
"""

import json
import sys
import warnings
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.optimize import minimize_scalar

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIM_DATA = Path(__file__).resolve().parent.parent / "data"
EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
MODEL_DIR = Path(__file__).resolve().parent
SIM_FT = PROJECT_ROOT / "sim" / "data" / "feature_table.parquet"
M3_PROJ = PROJECT_ROOT / "mlb" / "model_m3" / "m3_projections.parquet"
M3_FEAT = PROJECT_ROOT / "mlb" / "model_m3" / "m3_features.parquet"
M3_MODEL = PROJECT_ROOT / "mlb" / "model_m3" / "m3_ridge_model.pkl"

N_SIMS = 20_000
RNG = np.random.default_rng(42)


def ip_to_outs(ip_val):
    if pd.isna(ip_val): return np.nan
    whole = int(ip_val)
    frac = round((ip_val - whole) * 10)
    return whole * 3 + frac


def assign_path(outs):
    if pd.isna(outs): return np.nan
    if outs < 15: return 0
    elif outs <= 20: return 1
    else: return 2


def assign_regime(path_home, path_away):
    """Map path combination to scoring regime."""
    if path_home == 2 and path_away == 2:
        return 1  # Suppression
    elif path_home == 0 and path_away == 0:
        return 4  # High Chaos
    elif path_home == 0 or path_away == 0:
        return 3  # Fragile
    else:
        return 2  # Normal


def nb_negloglik(r, data, mu):
    """Negative log-likelihood for NB(mu, r) given observed data."""
    r = max(r, 0.1)
    p = r / (r + mu)
    ll = sp_stats.nbinom.logpmf(data, n=r, p=p).sum()
    return -ll


def fit_nb_r(runs, mu):
    """Fit NB dispersion parameter r given observed runs and mean mu."""
    runs_int = np.round(runs).astype(int)
    runs_int = np.clip(runs_int, 0, None)
    result = minimize_scalar(nb_negloglik, bounds=(0.5, 100), method="bounded",
                             args=(runs_int, mu))
    return result.x


def run_phase_s3():
    # ══════════════════════════════════════════════════════════════
    # LOAD DATA
    # ══════════════════════════════════════════════════════════════
    print("Loading data...")
    sim_inputs = pd.read_parquet(SIM_DATA / "sim_inputs_historical_2022_2024.parquet")
    ft = pd.read_parquet(SIM_FT)
    ft["game_pk"] = ft["game_pk"].astype(str)
    sim_inputs["game_pk"] = sim_inputs["game_pk"].astype(str)

    # Load S2 path model for OOS predictions
    with open(MODEL_DIR / "starter_path_model.pkl", "rb") as f:
        s2_bundle = pickle.load(f)
    s2_model = s2_bundle["model"]
    s2_scaler = s2_bundle["scaler"]
    s2_features = s2_bundle["features"]

    # Generate M3 projections for all games
    # (reuse the backfill logic from Phase A)
    m3_resid = pd.read_csv(PROJECT_ROOT / "research" / "mlb_phase_a" / "m3_residuals_all_seasons.csv")
    m3_resid["game_id"] = m3_resid["game_id"].astype(str)

    # Compute path probabilities for all starters
    print("Computing path probabilities...")
    feat_clean = sim_inputs.dropna(subset=s2_features).copy()
    X = feat_clean[s2_features].values
    X_s = s2_scaler.transform(X)
    probs = s2_model.predict_proba(X_s)
    feat_clean["p_path0"] = probs[:, 0]
    feat_clean["p_path1"] = probs[:, 1]
    feat_clean["p_path2"] = probs[:, 2]

    # Compute actual paths
    feat_clean["outs_recorded"] = feat_clean["actual_ip"].apply(ip_to_outs)
    feat_clean["actual_path"] = feat_clean["outs_recorded"].apply(assign_path)

    # Pivot to game level (one row per game with both starters)
    print("Pivoting to game level...")
    home = feat_clean[feat_clean["is_home"] == 1].copy()
    away = feat_clean[feat_clean["is_home"] == 0].copy()

    home_cols = {
        "game_pk": "game_pk", "date": "date", "season": "season",
        "team_id": "home_team", "opponent_team_id": "away_team",
        "sp_id": "home_sp_id", "sp_name": "home_sp_name",
        "sp_whiff_pct": "home_sp_whiff_pct",
        "p_path0": "home_p_path0", "p_path1": "home_p_path1", "p_path2": "home_p_path2",
        "actual_path": "home_actual_path",
        "actual_ip": "home_actual_ip",
    }
    away_cols = {
        "game_pk": "game_pk",
        "sp_id": "away_sp_id", "sp_name": "away_sp_name",
        "sp_whiff_pct": "away_sp_whiff_pct",
        "p_path0": "away_p_path0", "p_path1": "away_p_path1", "p_path2": "away_p_path2",
        "actual_path": "away_actual_path",
        "actual_ip": "away_actual_ip",
    }

    home_g = home[[v for v in home_cols.keys() if v in home.columns]].rename(columns=home_cols)
    away_g = away[[v for v in away_cols.keys() if v in away.columns]].rename(columns=away_cols)

    games = home_g.merge(away_g, on="game_pk", how="inner")

    # Join actual scores
    scores = ft[ft["season"].isin([2022, 2023, 2024])][
        ["game_pk", "home_score", "away_score", "actual_total"]].copy()
    scores["game_pk"] = scores["game_pk"].astype(str)
    games = games.merge(scores, on="game_pk", how="left")

    # Join M3 projection
    games = games.merge(
        m3_resid[["game_id", "m3_projection"]].rename(columns={"game_id": "game_pk"}),
        on="game_pk", how="left"
    )

    # Join closing line (evaluation only — never a model input)
    hist_cl = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "mlb_historical_closing_lines.parquet")
    mkt = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "market_snapshots.parquet")
    hist_cl["game_pk"] = hist_cl["game_pk"].astype(str)
    mkt["game_id"] = mkt["game_id"].astype(str) if "game_id" in mkt.columns else mkt["game_pk"].astype(str)
    cl1 = hist_cl[["game_pk", "close_total"]].rename(columns={"close_total": "closing_line"})
    id_col = "game_id" if "game_id" in mkt.columns else "game_pk"
    cl2 = mkt[[id_col, "close_total"]].rename(columns={id_col: "game_pk", "close_total": "closing_line"})
    closing = pd.concat([cl1, cl2]).drop_duplicates("game_pk", keep="first")
    games = games.merge(closing, on="game_pk", how="left")

    # Assign actual regimes
    games["actual_regime"] = games.apply(
        lambda r: assign_regime(r["home_actual_path"], r["away_actual_path"])
        if pd.notna(r["home_actual_path"]) and pd.notna(r["away_actual_path"]) else np.nan, axis=1)

    train = games[games["season"].isin([2022, 2023])].dropna(subset=["actual_regime", "actual_total"]).copy()
    oos = games[games["season"] == 2024].copy()

    print(f"Games: train={len(train)}, OOS={len(oos)}")

    # ══════════════════════════════════════════════════════════════
    # STEP 0 — EMPIRICAL PATH BUCKET TABLE
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP 0 — EMPIRICAL PATH BUCKET TABLE (2022-2023 train)")
    print("=" * 60)

    # Per-team runs allowed by starter path
    # home starters: runs allowed = away_score; away starters: runs allowed = home_score
    train_home = train.copy()
    train_home["runs_allowed"] = train_home["away_score"]  # opponent scored against home starter
    train_home["starter_path"] = train_home["home_actual_path"]

    train_away = train.copy()
    train_away["runs_allowed"] = train_away["home_score"]  # opponent scored against away starter
    train_away["starter_path"] = train_away["away_actual_path"]

    all_starts = pd.concat([
        train_home[["runs_allowed", "starter_path"]],
        train_away[["runs_allowed", "starter_path"]]
    ]).dropna()

    # Also compute game total by regime
    print(f"\nPer-starter runs allowed by path bucket:")
    print(f"{'Path':<20} | {'N':>6} | {'Mean':>6} | {'Var':>7} | {'Std':>6} | {'P(>=mu+2)':>10} | {'P(>=mu+3)':>10} | {'P(<=mu-2)':>10}")
    print("-" * 90)
    for path in [0, 1, 2]:
        sub = all_starts[all_starts["starter_path"] == path]["runs_allowed"]
        n = len(sub)
        mu = sub.mean()
        var = sub.var()
        std = sub.std()
        p_up2 = (sub >= mu + 2).mean() * 100
        p_up3 = (sub >= mu + 3).mean() * 100
        p_dn2 = (sub <= mu - 2).mean() * 100
        label = {0: "Path 0 (Early Exit)", 1: "Path 1 (Normal)", 2: "Path 2 (Deep)"}[path]
        print(f"{label:<20} | {n:>6} | {mu:>6.2f} | {var:>7.2f} | {std:>6.2f} | {p_up2:>9.1f}% | {p_up3:>9.1f}% | {p_dn2:>9.1f}%")

    print(f"\nPer-game total runs by actual regime:")
    print(f"{'Regime':<25} | {'N':>6} | {'Mean':>6} | {'Var':>7} | {'Std':>6} | {'P(>=mu+3)':>10}")
    print("-" * 75)
    for regime in [1, 2, 3, 4]:
        sub = train[train["actual_regime"] == regime]["actual_total"]
        n = len(sub)
        if n == 0: continue
        mu = sub.mean()
        var = sub.var()
        std = sub.std()
        p_up3 = (sub >= mu + 3).mean() * 100
        label = {1: "Regime 1 (Suppression)", 2: "Regime 2 (Normal)",
                 3: "Regime 3 (Fragile)", 4: "Regime 4 (Chaos)"}[regime]
        print(f"{label:<25} | {n:>6} | {mu:>6.2f} | {var:>7.2f} | {std:>6.2f} | {p_up3:>9.1f}%")

    # ══════════════════════════════════════════════════════════════
    # STEP 1-2: REGIME DISTRIBUTION (TRAIN)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("STEP 1-2 — REGIME DISTRIBUTION (train)")
    print("=" * 60)
    regime_counts = train["actual_regime"].value_counts().sort_index()
    for r in [1, 2, 3, 4]:
        n = regime_counts.get(r, 0)
        pct = n / len(train) * 100
        label = {1: "Suppression", 2: "Normal", 3: "Fragile", 4: "Chaos"}[r]
        print(f"  Regime {r} ({label}): {n} games ({pct:.1f}%)")

    # ══════════════════════════════════════════════════════════════
    # STEP 3-4: FIT NB DISPERSION BY REGIME
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("STEP 3-4 — FIT NB DISPERSION PARAMETERS")
    print("=" * 60)

    # For each regime, fit r using per-team runs
    # Use M3 projection as mu when available, else use actual mean
    regime_params = {}
    for regime in [1, 2, 3, 4]:
        regime_games = train[train["actual_regime"] == regime].copy()
        if len(regime_games) == 0:
            regime_params[regime] = {"r": 5.0, "n": 0}
            continue

        # Collect per-team runs for this regime
        home_runs = regime_games["home_score"].values
        away_runs = regime_games["away_score"].values
        all_team_runs = np.concatenate([home_runs, away_runs])

        # Use overall mean for this regime as mu
        mu = all_team_runs.mean()
        r_fit = fit_nb_r(all_team_runs, mu)

        # Compute implied variance: var = mu + mu^2/r
        implied_var = mu + mu**2 / r_fit
        actual_var = all_team_runs.var()

        # Compute log-likelihood
        runs_int = np.clip(np.round(all_team_runs).astype(int), 0, None)
        p = r_fit / (r_fit + mu)
        ll = sp_stats.nbinom.logpmf(runs_int, n=r_fit, p=p).sum()

        regime_params[regime] = {"r": round(r_fit, 3), "mu": round(mu, 3),
                                  "n": len(regime_games),
                                  "actual_var": round(actual_var, 3),
                                  "implied_var": round(implied_var, 3),
                                  "loglik": round(ll, 1)}

        label = {1: "Suppression", 2: "Normal", 3: "Fragile", 4: "Chaos"}[regime]
        print(f"\n  Regime {regime} ({label}): N={len(regime_games)}")
        print(f"    r={r_fit:.3f}, mu={mu:.3f}")
        print(f"    Actual variance: {actual_var:.3f}")
        print(f"    NB implied var:  {implied_var:.3f}")
        print(f"    Log-likelihood:  {ll:.1f}")

        # Tail mass comparison
        actual_p_up3 = (all_team_runs >= mu + 3).mean()
        nb_p_up3 = 1 - sp_stats.nbinom.cdf(int(np.round(mu + 3)) - 1, n=r_fit, p=p)
        print(f"    Actual P(runs >= mu+3): {actual_p_up3:.3f}")
        print(f"    NB fit P(runs >= mu+3): {nb_p_up3:.3f}")

    # Save parameters
    params_path = MODEL_DIR / "run_dist_params.json"
    with open(params_path, "w") as f:
        json.dump({str(k): v for k, v in regime_params.items()}, f, indent=2)
    print(f"\nParameters saved: {params_path}")

    # ══════════════════════════════════════════════════════════════
    # STEP 5 — MONTE CARLO SIMULATION (OOS 2024)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("STEP 5 — MONTE CARLO SIMULATION (2024 OOS)")
    print("=" * 60)

    oos_valid = oos.dropna(subset=["home_p_path0", "away_p_path0", "actual_total"]).copy()
    print(f"OOS games for simulation: {len(oos_valid)}")

    # Get M3 per-team projection (split game total roughly)
    # M3 gives game total — split proportional to historical H/A scoring
    home_share = 0.505  # slight home advantage
    oos_valid["mu_home"] = oos_valid["m3_projection"].fillna(oos_valid["actual_total"].mean()) * home_share
    oos_valid["mu_away"] = oos_valid["m3_projection"].fillna(oos_valid["actual_total"].mean()) * (1 - home_share)

    results = []
    for idx, game in oos_valid.iterrows():
        home_probs = np.array([game["home_p_path0"], game["home_p_path1"], game["home_p_path2"]])
        away_probs = np.array([game["away_p_path0"], game["away_p_path1"], game["away_p_path2"]])

        # Normalize (safety)
        home_probs = home_probs / home_probs.sum()
        away_probs = away_probs / away_probs.sum()

        mu_h = max(game["mu_home"], 1.0)
        mu_a = max(game["mu_away"], 1.0)

        # Draw paths and simulate
        home_paths = RNG.choice([0, 1, 2], size=N_SIMS, p=home_probs)
        away_paths = RNG.choice([0, 1, 2], size=N_SIMS, p=away_probs)

        totals = np.zeros(N_SIMS)
        regime_draws = np.zeros(N_SIMS, dtype=int)

        for i in range(N_SIMS):
            regime = assign_regime(home_paths[i], away_paths[i])
            regime_draws[i] = regime
            r = regime_params[regime]["r"]

            # Draw home runs
            p_h = r / (r + mu_h)
            home_runs = RNG.negative_binomial(r, p_h)

            # Draw away runs
            p_a = r / (r + mu_a)
            away_runs = RNG.negative_binomial(r, p_a)

            totals[i] = home_runs + away_runs

        closing = game.get("closing_line")

        results.append({
            "game_pk": game["game_pk"],
            "date": game["date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "actual_total": game["actual_total"],
            "closing_line": closing,
            "m3_projection": game["m3_projection"],
            "sim_mean_total": round(totals.mean(), 3),
            "sim_median_total": round(np.median(totals), 1),
            "sim_std_total": round(totals.std(), 3),
            "sim_skew_total": round(sp_stats.skew(totals), 3),
            "p_over_line": round((totals > closing).mean(), 4) if pd.notna(closing) else np.nan,
            "p_over_plus2": round((totals > closing + 2).mean(), 4) if pd.notna(closing) else np.nan,
            "p_over_plus3": round((totals > closing + 3).mean(), 4) if pd.notna(closing) else np.nan,
            "p_under_minus2": round((totals < closing - 2).mean(), 4) if pd.notna(closing) else np.nan,
            "starter_failure_risk_home": round(game["home_p_path0"], 4),
            "starter_failure_risk_away": round(game["away_p_path0"], 4),
            "dominant_regime": int(pd.Series(regime_draws).mode()[0]),
            "home_sp_whiff_pct": game.get("home_sp_whiff_pct"),
            "away_sp_whiff_pct": game.get("away_sp_whiff_pct"),
        })

    sim_df = pd.DataFrame(results)
    sim_path = EVAL_DIR / "sim_results_oos_2024.parquet"
    sim_df.to_parquet(sim_path, index=False)
    print(f"Simulation results saved: {sim_path} ({len(sim_df)} games)")

    # ══════════════════════════════════════════════════════════════
    # PHASE S3 GATE DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("PHASE S3 GATE DIAGNOSTICS")
    print("=" * 60)

    # Gate 5: Distribution shape check
    print(f"\n5. DISTRIBUTION SHAPE CHECK")
    print(f"{'Regime':<25} | {'mean sim_std':>12} | {'mean sim_skew':>13}")
    print("-" * 55)
    for regime in [1, 2, 3, 4]:
        sub = sim_df[sim_df["dominant_regime"] == regime]
        if len(sub) == 0: continue
        label = {1: "Suppression", 2: "Normal", 3: "Fragile", 4: "Chaos"}[regime]
        print(f"{label:<25} | {sub['sim_std_total'].mean():>12.3f} | {sub['sim_skew_total'].mean():>13.3f}")

    r1_std = sim_df[sim_df["dominant_regime"] == 1]["sim_std_total"].mean()
    r4_std = sim_df[sim_df["dominant_regime"] == 4]["sim_std_total"].mean() if len(sim_df[sim_df["dominant_regime"] == 4]) > 0 else r1_std
    std_diff = r4_std - r1_std
    print(f"\n  Std difference (Regime 4 - Regime 1): {std_diff:.3f}")
    if std_diff < 1.0:
        print(f"  *** FLAG: std difference < 1.0 — simulation may be collapsing toward mean ***")
    else:
        print(f"  PASS: meaningful distribution shape difference")

    # Gate 6: OOS calibration
    print(f"\n6. OOS CALIBRATION (p_over_line buckets)")
    cal = sim_df.dropna(subset=["p_over_line", "closing_line"]).copy()
    cal["actual_over"] = (cal["actual_total"] > cal["closing_line"]).astype(int)
    bins = [0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0]
    labels_b = ["<40%", "40-45%", "45-50%", "50-55%", "55-60%", ">60%"]
    cal["p_bucket"] = pd.cut(cal["p_over_line"], bins=bins, labels=labels_b, include_lowest=True)
    print(f"{'Bucket':<10} | {'N':>6} | {'Pred p_over':>12} | {'Actual over%':>13}")
    print("-" * 50)
    for bucket in labels_b:
        sub = cal[cal["p_bucket"] == bucket]
        if len(sub) == 0: continue
        pred = sub["p_over_line"].mean() * 100
        actual = sub["actual_over"].mean() * 100
        print(f"{bucket:<10} | {len(sub):>6} | {pred:>11.1f}% | {actual:>12.1f}%")

    # Gate 7: Low-total subgroup
    print(f"\n7. LOW-TOTAL SUBGROUP CALIBRATION (closing <= 7.5, OOS)")
    low = cal[cal["closing_line"] <= 7.5]
    if len(low) > 0:
        print(f"{'Bucket':<10} | {'N':>6} | {'Pred p_over':>12} | {'Actual over%':>13}")
        print("-" * 50)
        low["p_bucket"] = pd.cut(low["p_over_line"], bins=bins, labels=labels_b, include_lowest=True)
        for bucket in labels_b:
            sub = low[low["p_bucket"] == bucket]
            if len(sub) == 0: continue
            pred = sub["p_over_line"].mean() * 100
            actual = sub["actual_over"].mean() * 100
            print(f"{bucket:<10} | {len(sub):>6} | {pred:>11.1f}% | {actual:>12.1f}%")
    else:
        print("  No low-total games with closing line in OOS")

    # Gate 8: Regime-level OOS over rate
    print(f"\n8. REGIME-LEVEL OOS OVER RATE")
    for regime in [1, 2, 3, 4]:
        sub = cal[cal["dominant_regime"] == regime]
        if len(sub) == 0: continue
        over_rate = sub["actual_over"].mean() * 100
        label = {1: "Suppression", 2: "Normal", 3: "Fragile", 4: "Chaos"}[regime]
        print(f"  {label:<20}: N={len(sub):>5}, actual over rate={over_rate:.1f}%")

    # Gate 9: Whiff flag check
    print(f"\n9. WHIFF FLAG CHECK (OOS)")
    whiff_q75 = sim_inputs[sim_inputs["season"].isin([2022, 2023])]["sp_whiff_pct"].quantile(0.75)
    print(f"  Whiff top quartile threshold (train): {whiff_q75:.2f}")

    # Check home starters
    high_whiff = sim_df[sim_df["home_sp_whiff_pct"].notna() & (sim_df["home_sp_whiff_pct"] >= whiff_q75)]
    low_whiff = sim_df[sim_df["home_sp_whiff_pct"].notna() & (sim_df["home_sp_whiff_pct"] < whiff_q75)]
    print(f"\n  High-whiff home starters (>= {whiff_q75:.1f}%): N={len(high_whiff)}")
    print(f"    Mean p_path0: {high_whiff['starter_failure_risk_home'].mean():.4f}")
    print(f"    Regime distribution:")
    for regime in [1, 2, 3, 4]:
        n = (high_whiff["dominant_regime"] == regime).sum()
        pct = n / len(high_whiff) * 100 if len(high_whiff) > 0 else 0
        print(f"      Regime {regime}: {n} ({pct:.1f}%)")

    print(f"\n  Low-whiff home starters (< {whiff_q75:.1f}%): N={len(low_whiff)}")
    print(f"    Mean p_path0: {low_whiff['starter_failure_risk_home'].mean():.4f}")
    print(f"    Regime distribution:")
    for regime in [1, 2, 3, 4]:
        n = (low_whiff["dominant_regime"] == regime).sum()
        pct = n / len(low_whiff) * 100 if len(low_whiff) > 0 else 0
        print(f"      Regime {regime}: {n} ({pct:.1f}%)")

    # Whiff anomaly flag
    if len(high_whiff) > 0 and len(low_whiff) > 0:
        hw_p0 = high_whiff["starter_failure_risk_home"].mean()
        lw_p0 = low_whiff["starter_failure_risk_home"].mean()
        if hw_p0 > lw_p0:
            print(f"\n  *** WHIFF ANOMALY FLAG: high-whiff starters have HIGHER p_path0 ({hw_p0:.4f}) "
                  f"than low-whiff ({lw_p0:.4f}) — counterintuitive sign from S2 confirmed ***")
        else:
            print(f"\n  Whiff check OK: high-whiff p_path0 ({hw_p0:.4f}) < low-whiff ({lw_p0:.4f})")

    print(f"\n*** PHASE S3 COMPLETE — awaiting confirmation to proceed to S4 ***")


if __name__ == "__main__":
    run_phase_s3()
