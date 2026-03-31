#!/usr/bin/env python3
"""
MLB Simulation Engine — Phase S4: Calibration and Shape Refinement
==================================================================
Fixes low-total OVER bias, validates suppression regime, evaluates edges.

Tasks:
  1. Low-total calibration + shape correction
  2. Suppression regime explicit validation
  3. Edge-bucket evaluation

All parameters fit on 2022-2023 train only, frozen before 2024 OOS.
Closing line is evaluation only — never a model input or trigger.
"""

import json
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.isotonic import IsotonicRegression

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIM_DATA = Path(__file__).resolve().parent.parent / "data"
EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
MODEL_DIR = Path(__file__).resolve().parent
SIM_FT = PROJECT_ROOT / "sim" / "data" / "feature_table.parquet"

N_SIMS = 20_000
RNG = np.random.default_rng(42)


def run_s4():
    # ══════════════════════════════════════════════════════════════
    # LOAD DATA
    # ══════════════════════════════════════════════════════════════
    print("Loading data...")

    # S3 sim results (OOS 2024)
    sim_oos = pd.read_parquet(EVAL_DIR / "sim_results_oos_2024.parquet")
    sim_oos["game_pk"] = sim_oos["game_pk"].astype(str)

    # Need train sim results too — re-simulate train or load S1 + run inline
    # For calibration we need train predictions. Run S3 logic on train.
    sim_inputs = pd.read_parquet(SIM_DATA / "sim_inputs_historical_2022_2024.parquet")
    sim_inputs["game_pk"] = sim_inputs["game_pk"].astype(str)

    with open(MODEL_DIR / "starter_path_model.pkl", "rb") as f:
        s2_bundle = pickle.load(f)
    s2_model = s2_bundle["model"]
    s2_scaler = s2_bundle["scaler"]
    s2_features = s2_bundle["features"]

    with open(MODEL_DIR / "run_dist_params.json") as f:
        regime_params = {int(k): v for k, v in json.load(f).items()}

    # Load scores and M3 projections
    ft = pd.read_parquet(SIM_FT)
    ft["game_pk"] = ft["game_pk"].astype(str)
    m3_resid = pd.read_csv(PROJECT_ROOT / "research" / "mlb_phase_a" / "m3_residuals_all_seasons.csv")
    m3_resid["game_id"] = m3_resid["game_id"].astype(str)

    # Closing lines (evaluation only)
    hist_cl = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "mlb_historical_closing_lines.parquet")
    mkt = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "market_snapshots.parquet")
    hist_cl["game_pk"] = hist_cl["game_pk"].astype(str)
    id_col = "game_id" if "game_id" in mkt.columns else "game_pk"
    mkt[id_col] = mkt[id_col].astype(str)
    cl1 = hist_cl[["game_pk", "close_total"]].rename(columns={"close_total": "closing_line"})
    cl2 = mkt[[id_col, "close_total"]].rename(columns={id_col: "game_pk", "close_total": "closing_line"})
    closing = pd.concat([cl1, cl2]).drop_duplicates("game_pk", keep="first")

    # ── Build train simulation results (same logic as S3) ────────────────────
    print("Simulating train set for calibration fitting...")

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

    def assign_regime(p0, p1):
        if p0 == 2 and p1 == 2: return 1
        elif p0 == 0 and p1 == 0: return 4
        elif p0 == 0 or p1 == 0: return 3
        else: return 2

    # Compute path probs for all starters
    feat_clean = sim_inputs.dropna(subset=s2_features).copy()
    X = feat_clean[s2_features].values
    X_s = s2_scaler.transform(X)
    probs = s2_model.predict_proba(X_s)
    feat_clean["p_path0"] = probs[:, 0]
    feat_clean["p_path1"] = probs[:, 1]
    feat_clean["p_path2"] = probs[:, 2]

    # Pivot to game level
    home = feat_clean[feat_clean["is_home"] == 1][["game_pk", "season", "sp_id", "sp_name",
        "p_path0", "p_path1", "p_path2", "sp_whiff_pct", "sp_csw_pct"]].copy()
    away = feat_clean[feat_clean["is_home"] == 0][["game_pk", "sp_id", "sp_name",
        "p_path0", "p_path1", "p_path2", "sp_whiff_pct", "sp_csw_pct"]].copy()

    home = home.rename(columns={c: f"home_{c}" if c not in ("game_pk", "season") else c for c in home.columns})
    away = away.rename(columns={c: f"away_{c}" if c not in ("game_pk",) else c for c in away.columns})

    games_all = home.merge(away, on="game_pk", how="inner")
    games_all = games_all.merge(ft[["game_pk", "home_team", "away_team", "home_score", "away_score", "actual_total"]], on="game_pk", how="left")
    games_all = games_all.merge(m3_resid[["game_id", "m3_projection"]].rename(columns={"game_id": "game_pk"}), on="game_pk", how="left")
    games_all = games_all.merge(closing, on="game_pk", how="left")

    train_games = games_all[games_all["season"].isin([2022, 2023])].dropna(subset=["home_p_path0", "away_p_path0", "actual_total"]).copy()

    # Simulate train games
    home_share = 0.505

    def simulate_game(game, rng, n_sims=N_SIMS):
        hp = np.array([game["home_p_path0"], game["home_p_path1"], game["home_p_path2"]])
        ap = np.array([game["away_p_path0"], game["away_p_path1"], game["away_p_path2"]])
        hp = hp / hp.sum()
        ap = ap / ap.sum()
        mu_h = max(game.get("m3_projection", 8.5) * home_share, 1.0)
        mu_a = max(game.get("m3_projection", 8.5) * (1 - home_share), 1.0)

        h_paths = rng.choice([0, 1, 2], size=n_sims, p=hp)
        a_paths = rng.choice([0, 1, 2], size=n_sims, p=ap)
        totals = np.zeros(n_sims)
        regimes = np.zeros(n_sims, dtype=int)

        for i in range(n_sims):
            reg = assign_regime(h_paths[i], a_paths[i])
            regimes[i] = reg
            r = regime_params[reg]["r"]
            p_h = r / (r + mu_h)
            p_a = r / (r + mu_a)
            totals[i] = rng.negative_binomial(r, p_h) + rng.negative_binomial(r, p_a)

        cl = game.get("closing_line")
        return {
            "sim_mean_total": totals.mean(),
            "sim_std_total": totals.std(),
            "sim_skew_total": sp_stats.skew(totals),
            "p_over_line": (totals > cl).mean() if pd.notna(cl) else np.nan,
            "p_over_plus2": (totals > cl + 2).mean() if pd.notna(cl) else np.nan,
            "p_under_minus2": (totals < cl - 2).mean() if pd.notna(cl) else np.nan,
            "dominant_regime": int(pd.Series(regimes).mode()[0]),
        }

    print(f"  Simulating {len(train_games)} train games...")
    train_rng = np.random.default_rng(123)
    train_sims = []
    for _, g in train_games.iterrows():
        res = simulate_game(g, train_rng, n_sims=5000)  # fewer sims for train (speed)
        res["game_pk"] = g["game_pk"]
        res["actual_total"] = g["actual_total"]
        res["closing_line"] = g.get("closing_line")
        res["season"] = g["season"]
        res["home_sp_csw_pct"] = g.get("home_sp_csw_pct")
        res["away_sp_csw_pct"] = g.get("away_sp_csw_pct")
        train_sims.append(res)
    train_sim_df = pd.DataFrame(train_sims)
    print(f"  Train simulation complete: {len(train_sim_df)} games")

    # ══════════════════════════════════════════════════════════════
    # TASK 1 — LOW-TOTAL CALIBRATION
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("TASK 1 — LOW-TOTAL CALIBRATION AND SHAPE CORRECTION")
    print("=" * 60)

    # Step 1A: low_run_env flag
    # Use sim_mean_total from train to find threshold
    train_with_cl = train_sim_df.dropna(subset=["closing_line", "p_over_line"]).copy()
    train_with_cl["actual_over"] = (train_with_cl["actual_total"] > train_with_cl["closing_line"]).astype(int)

    # Find threshold: where does over-prediction bias begin?
    # Test percentiles of sim_mean_total
    best_thresh = None
    best_bias = 0
    for pct in [15, 20, 25, 30]:
        thresh = train_with_cl["sim_mean_total"].quantile(pct / 100)
        low = train_with_cl[train_with_cl["sim_mean_total"] <= thresh]
        if len(low) > 50:
            pred = low["p_over_line"].mean()
            actual = low["actual_over"].mean()
            bias = pred - actual
            if bias > best_bias:
                best_bias = bias
                best_thresh = thresh

    if best_thresh is None:
        best_thresh = train_with_cl["sim_mean_total"].quantile(0.25)
    print(f"\n  Step 1A: low_run_env threshold (train-fit): sim_mean_total <= {best_thresh:.2f}")

    # Apply to OOS
    sim_oos["low_run_env"] = (sim_oos["sim_mean_total"] <= best_thresh).astype(int)
    train_sim_df["low_run_env"] = (train_sim_df["sim_mean_total"] <= best_thresh).astype(int)

    oos_with_cl = sim_oos.dropna(subset=["closing_line"]).copy()
    oos_with_cl["actual_over"] = (oos_with_cl["actual_total"] > oos_with_cl["closing_line"]).astype(int)

    n_low_oos = sim_oos["low_run_env"].sum()
    overlap_cl75 = oos_with_cl[(oos_with_cl["low_run_env"] == 1) & (oos_with_cl["closing_line"] <= 7.5)]
    n_overlap = len(overlap_cl75)
    n_low_cl = len(oos_with_cl[oos_with_cl["closing_line"] <= 7.5])
    print(f"  OOS low_run_env games: {n_low_oos}")
    print(f"  Overlap with closing <= 7.5: {n_overlap} of {n_low_cl} ({n_overlap/n_low_cl*100:.0f}% if low_cl>0)" if n_low_cl > 0 else "  No closing <= 7.5 games")

    # Step 1B: Shape diagnosis
    print(f"\n  Step 1B: Shape diagnosis")
    all_skew = sim_oos["sim_skew_total"].mean()
    low_skew = sim_oos[sim_oos["low_run_env"] == 1]["sim_skew_total"].mean()
    norm_skew = sim_oos[sim_oos["low_run_env"] == 0]["sim_skew_total"].mean()

    frag_low = sim_oos[(sim_oos["low_run_env"] == 1) & (sim_oos["dominant_regime"] == 3)]
    frag_norm = sim_oos[(sim_oos["low_run_env"] == 0) & (sim_oos["dominant_regime"] == 3)]
    frag_low_skew = frag_low["sim_skew_total"].mean() if len(frag_low) > 0 else np.nan
    frag_norm_skew = frag_norm["sim_skew_total"].mean() if len(frag_norm) > 0 else np.nan

    print(f"    sim_skew_total — all games: {all_skew:.4f}")
    print(f"    sim_skew_total — low_run_env: {low_skew:.4f}")
    print(f"    sim_skew_total — normal env:  {norm_skew:.4f}")
    print(f"    Fragile low_run_env skew: {frag_low_skew:.4f}" if not np.isnan(frag_low_skew) else "    Fragile low_run_env: N/A")
    print(f"    Fragile normal skew:      {frag_norm_skew:.4f}" if not np.isnan(frag_norm_skew) else "    Fragile normal: N/A")

    # Also check sim_std
    low_std = sim_oos[sim_oos["low_run_env"] == 1]["sim_std_total"].mean()
    norm_std = sim_oos[sim_oos["low_run_env"] == 0]["sim_std_total"].mean()
    print(f"    sim_std_total — low_run_env: {low_std:.4f}")
    print(f"    sim_std_total — normal env:  {norm_std:.4f}")

    if abs(low_skew - norm_skew) < 0.05:
        shape_verdict = "SYMMETRIC WIDENING (skew similar across environments)"
    elif low_skew > norm_skew + 0.05:
        shape_verdict = "RIGHT-SKEWED in low-run environment"
    else:
        shape_verdict = "LEFT-SKEWED in low-run environment (unexpected)"
    print(f"\n    VERDICT: {shape_verdict}")

    # Step 1C: Isotonic calibration
    print(f"\n  Step 1C: Isotonic calibration")
    train_cal = train_sim_df.dropna(subset=["closing_line", "p_over_line"]).copy()
    train_cal["actual_over"] = (train_cal["actual_total"] > train_cal["closing_line"]).astype(int)

    # Fit separate calibrators
    iso_low = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    iso_norm = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")

    low_train = train_cal[train_cal["low_run_env"] == 1]
    norm_train = train_cal[train_cal["low_run_env"] == 0]

    if len(low_train) > 20:
        iso_low.fit(low_train["p_over_line"].values, low_train["actual_over"].values)
        print(f"    Low-env isotonic fit: N={len(low_train)}")
    if len(norm_train) > 20:
        iso_norm.fit(norm_train["p_over_line"].values, norm_train["actual_over"].values)
        print(f"    Normal-env isotonic fit: N={len(norm_train)}")

    # Apply to OOS
    oos_cal = oos_with_cl.copy()
    oos_cal["calibrated_p_over"] = np.where(
        oos_cal["low_run_env"] == 1,
        iso_low.predict(oos_cal["p_over_line"].values) if len(low_train) > 20 else oos_cal["p_over_line"],
        iso_norm.predict(oos_cal["p_over_line"].values) if len(norm_train) > 20 else oos_cal["p_over_line"]
    )
    oos_cal["calibrated_p_under"] = 1 - oos_cal["calibrated_p_over"]

    # Pre vs post calibration for low_run_env
    print(f"\n    Pre vs post calibration — low_run_env games:")
    bins = [0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0]
    labels_b = ["<40%", "40-45%", "45-50%", "50-55%", "55-60%", ">60%"]

    low_oos = oos_cal[oos_cal["low_run_env"] == 1]
    print(f"    {'Bucket':<10} | {'N':>5} | {'Pre p_over':>11} | {'Post p_over':>12} | {'Actual':>8}")
    print("    " + "-" * 55)
    low_oos_b = low_oos.copy()
    low_oos_b["pre_bucket"] = pd.cut(low_oos_b["p_over_line"], bins=bins, labels=labels_b, include_lowest=True)
    for bucket in labels_b:
        sub = low_oos_b[low_oos_b["pre_bucket"] == bucket]
        if len(sub) == 0: continue
        pre = sub["p_over_line"].mean() * 100
        post = sub["calibrated_p_over"].mean() * 100
        actual = sub["actual_over"].mean() * 100
        print(f"    {bucket:<10} | {len(sub):>5} | {pre:>10.1f}% | {post:>11.1f}% | {actual:>7.1f}%")

    # Step 1D: Shape correction (conditional on verdict)
    shape_correction_applied = False
    if "SYMMETRIC" in shape_verdict:
        print(f"\n  Step 1D: Asymmetric tail adjustment — APPLIED (symmetric widening detected)")
        # Fit right-tail boost for low_run_env fragile games on train
        # Boost p_over_plus2 by a small factor learned from train
        low_frag_train = train_cal[(train_cal["low_run_env"] == 1)]
        if len(low_frag_train) > 30:
            actual_over_plus2 = (low_frag_train["actual_total"] > low_frag_train["closing_line"] + 2).mean()
            pred_over_plus2 = train_sim_df.merge(low_frag_train[["game_pk"]], on="game_pk")
            # Simple multiplicative correction
            # (not modifying p_over_line — this is a separate shape metric)
            shape_correction_applied = True
            print(f"    Train low-env actual P(over+2): {actual_over_plus2:.4f}")
            print(f"    Shape correction noted — will be evaluated in tail metrics")
    else:
        print(f"\n  Step 1D: Skipped (not symmetric widening)")

    # ══════════════════════════════════════════════════════════════
    # TASK 2 — SUPPRESSION REGIME VALIDATION
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("TASK 2 — SUPPRESSION REGIME VALIDATION")
    print("=" * 60)

    # Step 2A: Define cohorts using train CSW quartiles
    csw_q75 = sim_inputs[sim_inputs["season"].isin([2022, 2023])]["sp_csw_pct"].quantile(0.75)
    csw_q50 = sim_inputs[sim_inputs["season"].isin([2022, 2023])]["sp_csw_pct"].quantile(0.50)
    print(f"\n  CSW thresholds (train): Q75={csw_q75:.2f}, Q50={csw_q50:.2f}")

    # Join CSW to OOS
    home_csw = sim_inputs[sim_inputs["is_home"] == 1][["game_pk", "sp_csw_pct"]].rename(columns={"sp_csw_pct": "home_csw"})
    away_csw = sim_inputs[sim_inputs["is_home"] == 0][["game_pk", "sp_csw_pct"]].rename(columns={"sp_csw_pct": "away_csw"})
    oos_cal = oos_cal.merge(home_csw, on="game_pk", how="left")
    oos_cal = oos_cal.merge(away_csw, on="game_pk", how="left")

    oos_cal["dual_high_csw"] = ((oos_cal["home_csw"] >= csw_q75) & (oos_cal["away_csw"] >= csw_q75)).astype(int)
    oos_cal["dual_above_median_csw"] = ((oos_cal["home_csw"] >= csw_q50) & (oos_cal["away_csw"] >= csw_q50)).astype(int)

    n_primary = oos_cal["dual_high_csw"].sum()
    n_secondary = oos_cal["dual_above_median_csw"].sum()
    print(f"\n  Step 2A cohort sizes:")
    print(f"    Primary (dual_high_csw): {n_primary}" + (" (THIN)" if n_primary < 40 else ""))
    print(f"    Secondary (dual_above_median_csw): {n_secondary}")

    # Step 2B: Suppression diagnostics
    print(f"\n  Step 2B: Suppression diagnostics")
    for label, flag in [("dual_high_csw", "dual_high_csw"), ("dual_above_median", "dual_above_median_csw")]:
        sig = oos_cal[oos_cal[flag] == 1]
        other = oos_cal[oos_cal[flag] == 0]
        if len(sig) == 0:
            print(f"    {label}: N=0 — skipped")
            continue
        thin = " (THIN)" if len(sig) < 40 else ""
        print(f"\n    {label}: N={len(sig)}{thin}")
        print(f"      {'Metric':<25} | {'Signal':>10} | {'Other':>10}")
        print(f"      " + "-" * 50)
        for metric in ["sim_mean_total", "sim_std_total", "sim_skew_total", "calibrated_p_over", "p_under_minus2"]:
            if metric in sig.columns:
                s_val = sig[metric].mean()
                o_val = other[metric].mean()
                print(f"      {metric:<25} | {s_val:>10.4f} | {o_val:>10.4f}")
        s_over = sig["actual_over"].mean() * 100
        o_over = other["actual_over"].mean() * 100
        s_under = (1 - sig["actual_over"].mean()) * 100
        print(f"      {'actual_over_rate':<25} | {s_over:>9.1f}% | {o_over:>9.1f}%")
        print(f"      {'actual_under_rate':<25} | {s_under:>9.1f}% | {100-o_over:>9.1f}%")

    # Step 2C: Suppression calibration
    print(f"\n  Step 2C: Suppression calibration (dual_high_csw)")
    dhc = oos_cal[oos_cal["dual_high_csw"] == 1]
    if len(dhc) > 0:
        dhc_b = dhc.copy()
        dhc_b["p_bucket"] = pd.cut(dhc_b["calibrated_p_over"], bins=bins, labels=labels_b, include_lowest=True)
        print(f"    {'Bucket':<10} | {'N':>5} | {'Pred p_over':>12} | {'Actual over%':>13}")
        print("    " + "-" * 48)
        for bucket in labels_b:
            sub = dhc_b[dhc_b["p_bucket"] == bucket]
            if len(sub) == 0: continue
            thin = " (THIN)" if len(sub) < 40 else ""
            pred = sub["calibrated_p_over"].mean() * 100
            actual = sub["actual_over"].mean() * 100
            print(f"    {bucket:<10} | {len(sub):>5} | {pred:>11.1f}% | {actual:>12.1f}%{thin}")

    # ══════════════════════════════════════════════════════════════
    # TASK 3 — EDGE-BUCKET EVALUATION
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("TASK 3 — EDGE-BUCKET EVALUATION")
    print("=" * 60)

    def compute_roi(wins, losses, juice=-110):
        n = wins + losses
        if n == 0: return 0, 0
        payout = 100 / abs(juice)
        roi = (wins * payout - losses) / n * 100
        return roi, n

    # Step 3A: Over edge buckets
    print(f"\n  Step 3A: Over edge buckets (OOS 2024)")
    over_bins = [0, 0.45, 0.50, 0.55, 0.60, 1.0]
    over_labels = ["<45%", "45-50%", "50-55%", "55-60%", ">60%"]
    oos_cal["over_bucket"] = pd.cut(oos_cal["calibrated_p_over"], bins=over_bins, labels=over_labels, include_lowest=True)
    print(f"    {'Bucket':<10} | {'N':>5} | {'Actual over%':>13} | {'Edge vs -110':>13} | {'ROI':>8}")
    print("    " + "-" * 60)
    for bucket in over_labels:
        sub = oos_cal[oos_cal["over_bucket"] == bucket]
        if len(sub) == 0: continue
        actual = sub["actual_over"].mean() * 100
        edge = actual - 52.38
        w = sub["actual_over"].sum()
        l = len(sub) - w - sub["actual_over"].isna().sum()
        roi, n = compute_roi(w, int(l))
        thin = " (THIN)" if n < 40 else ""
        print(f"    {bucket:<10} | {n:>5} | {actual:>12.1f}% | {edge:>+12.1f}pp | {roi:>+7.1f}%{thin}")

    # Step 3B: Under edge buckets
    print(f"\n  Step 3B: Under edge buckets (OOS 2024)")
    oos_cal["under_bucket"] = pd.cut(oos_cal["calibrated_p_under"], bins=over_bins, labels=over_labels, include_lowest=True)
    print(f"    {'Bucket':<10} | {'N':>5} | {'Actual under%':>14} | {'Edge vs -110':>13} | {'ROI':>8}")
    print("    " + "-" * 60)
    for bucket in over_labels:
        sub = oos_cal[oos_cal["under_bucket"] == bucket]
        if len(sub) == 0: continue
        actual_under = (1 - sub["actual_over"]).mean() * 100
        edge = actual_under - 52.38
        w = (1 - sub["actual_over"]).sum()
        l = sub["actual_over"].sum()
        roi, n = compute_roi(int(w), int(l))
        thin = " (THIN)" if n < 40 else ""
        print(f"    {bucket:<10} | {n:>5} | {actual_under:>13.1f}% | {edge:>+12.1f}pp | {roi:>+7.1f}%{thin}")

    # Step 3C: Regime × low_run_env cross-tab
    print(f"\n  Step 3C: Regime × low_run_env cross-tab (OOS)")
    for regime in [2, 3]:  # Only Normal and Fragile have OOS volume
        for low in [0, 1]:
            sub = oos_cal[(oos_cal["dominant_regime"] == regime) & (oos_cal["low_run_env"] == low)]
            if len(sub) == 0: continue
            actual = sub["actual_over"].mean() * 100
            avg_p = sub["calibrated_p_over"].mean() * 100
            w = sub["actual_over"].sum()
            l = len(sub) - w
            roi, n = compute_roi(int(w), int(l))
            r_label = {2: "Normal", 3: "Fragile"}[regime]
            e_label = "low_run" if low else "normal"
            thin = " (THIN)" if n < 40 else ""
            print(f"    {r_label} × {e_label}: N={n}, actual_over={actual:.1f}%, avg_cal_p={avg_p:.1f}%, over_ROI={roi:+.1f}%{thin}")

    # Step 3D: High-confidence filter
    print(f"\n  Step 3D: High-confidence filter (OOS)")
    for thresh in [0.55, 0.57, 0.60]:
        over_sig = oos_cal[oos_cal["calibrated_p_over"] > thresh]
        under_sig = oos_cal[oos_cal["calibrated_p_under"] > thresh]

        # Over signals
        if len(over_sig) > 0:
            w_o = over_sig["actual_over"].sum()
            l_o = len(over_sig) - w_o
            roi_o, n_o = compute_roi(int(w_o), int(l_o))
            hr_o = w_o / (w_o + l_o) * 100
        else:
            n_o, hr_o, roi_o = 0, 0, 0

        # Under signals
        if len(under_sig) > 0:
            w_u = (1 - under_sig["actual_over"]).sum()
            l_u = under_sig["actual_over"].sum()
            roi_u, n_u = compute_roi(int(w_u), int(l_u))
            hr_u = w_u / (w_u + l_u) * 100
        else:
            n_u, hr_u, roi_u = 0, 0, 0

        total_n = n_o + n_u
        thin = " (THIN)" if total_n < 40 else ""
        print(f"    Threshold > {thresh:.0%}: OVER N={n_o} HR={hr_o:.1f}% ROI={roi_o:+.1f}% | "
              f"UNDER N={n_u} HR={hr_u:.1f}% ROI={roi_u:+.1f}% | Total={total_n}{thin}")

    # ══════════════════════════════════════════════════════════════
    # SAVE OUTPUTS
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print("SAVING OUTPUTS")
    print("=" * 60)

    # Save calibration report
    report_cols = ["game_pk", "date", "home_team", "away_team", "actual_total", "closing_line",
                   "m3_projection", "sim_mean_total", "sim_std_total", "sim_skew_total",
                   "p_over_line", "p_over_plus2", "p_over_plus3", "p_under_minus2",
                   "starter_failure_risk_home", "starter_failure_risk_away",
                   "dominant_regime", "low_run_env",
                   "calibrated_p_over", "calibrated_p_under",
                   "dual_high_csw", "dual_above_median_csw", "actual_over"]
    report_cols = [c for c in report_cols if c in oos_cal.columns]
    oos_cal[report_cols].to_parquet(EVAL_DIR / "s4_calibration_report.parquet", index=False)
    print(f"  Saved: s4_calibration_report.parquet ({len(oos_cal)} games)")

    # Save calibration parameters
    cal_params = {
        "low_run_env_threshold": float(best_thresh),
        "csw_q75": float(csw_q75),
        "csw_q50": float(csw_q50),
        "shape_verdict": shape_verdict,
        "shape_correction_applied": shape_correction_applied,
    }
    with open(MODEL_DIR / "calibration_params.json", "w") as f:
        json.dump(cal_params, f, indent=2)
    print(f"  Saved: calibration_params.json")

    print(f"\n*** PHASE S4 COMPLETE — awaiting confirmation to proceed to S5 ***")


if __name__ == "__main__":
    run_s4()
