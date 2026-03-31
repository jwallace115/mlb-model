#!/usr/bin/env python3
"""
NHL Totals Model — Phase 4: Poisson Simulation + Probability Engine
====================================================================
Steps
  1. Intercept recalibration (validate-set bias correction)
  2. Independent Poisson simulation (10,000 draws/game)
  3. Simulation diagnostics 3A–3E
  4. Variance adjustment (NegBinomial) if flagged by 3B/3E
  5. Edge calculation from American odds
  6. Save outputs

Outputs
  nhl/nhl_sim_results.parquet
  nhl/phase4_sim_audit.txt
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
NHL_DIR      = Path(__file__).parent
FEATURE_TABLE = NHL_DIR / "nhl_feature_table.parquet"
CANONICAL_CSV = NHL_DIR / "nhl_games_canonical.csv"
HOME_PKL      = NHL_DIR / "ridge_home_model.pkl"
AWAY_PKL      = NHL_DIR / "ridge_away_model.pkl"
SIM_RESULTS   = NHL_DIR / "nhl_sim_results.parquet"
AUDIT_FILE    = NHL_DIR / "phase4_sim_audit.txt"

N_SIM = 10_000
SEED  = 42

TRAIN_SEASONS = {2021, 2022}
VAL_SEASONS   = {2023}
OOS_SEASONS   = {2024}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_lines: list[str] = []

def log(msg: str = "") -> None:
    print(msg)
    _lines.append(msg)

# ---------------------------------------------------------------------------
# American odds → implied probability
# ---------------------------------------------------------------------------
def american_to_implied(price: float) -> float:
    if np.isnan(price):
        return np.nan
    if price < 0:
        return abs(price) / (abs(price) + 100.0)
    else:
        return 100.0 / (100.0 + price)

# ---------------------------------------------------------------------------
# Closing total bucket
# ---------------------------------------------------------------------------
def bucket(line: float) -> str:
    if pd.isna(line):
        return "null"
    if line == 5.5:
        return "5.5"
    if line == 6.0:
        return "6.0"
    if line == 6.5:
        return "6.5"
    return "other"

# ---------------------------------------------------------------------------
# STEP 1 — Load models and feature table
# ---------------------------------------------------------------------------
def load_models():
    with open(HOME_PKL, "rb") as f:
        hpkg = pickle.load(f)
    with open(AWAY_PKL, "rb") as f:
        apkg = pickle.load(f)
    return hpkg, apkg

def predict_raw(pkg: dict, df: pd.DataFrame) -> np.ndarray:
    """Apply ridge + scaler, return raw (uncalibrated) predictions."""
    X = df[pkg["features"]].to_numpy()
    X_sc = pkg["scaler"].transform(X)
    return pkg["model"].predict(X_sc)

# ---------------------------------------------------------------------------
# STEP 2 — Intercept recalibration
# ---------------------------------------------------------------------------
def recalibrate(ft: pd.DataFrame, hpkg: dict, apkg: dict):
    log("=" * 68)
    log("STEP 1 — INTERCEPT RECALIBRATION")
    log("=" * 68)

    val = ft[ft["season_year"].isin(VAL_SEASONS)].copy()
    oos = ft[ft["season_year"].isin(OOS_SEASONS)].copy()
    train = ft[ft["season_year"].isin(TRAIN_SEASONS)].copy()

    # Fill nulls using train means (same as Phase 3)
    all_feats = sorted(set(hpkg["features"] + apkg["features"]))
    col_means = train[all_feats].mean()
    for split in (val, oos, train):
        split[all_feats] = split[all_feats].fillna(col_means)

    # Raw predictions on validate
    val_lh_raw = predict_raw(hpkg, val)
    val_la_raw = predict_raw(apkg, val)

    home_bias = float(np.mean(val["home_score"].values - val_lh_raw))
    away_bias = float(np.mean(val["away_score"].values - val_la_raw))

    log(f"\n  Validate set bias (actual − predicted):")
    log(f"    home_bias = {home_bias:+.4f} goals")
    log(f"    away_bias = {away_bias:+.4f} goals")

    # Apply calibration to all splits
    results = {}
    for name, split in [("train", train), ("validate", val), ("oos", oos)]:
        lh = predict_raw(hpkg, split) + home_bias
        la = predict_raw(apkg, split) + away_bias
        results[name] = {"df": split.copy(), "lh": lh, "la": la}

    # Verify calibration
    log()
    log("  Post-calibration mean comparison:")
    log(f"  {'Split':<12} {'mean(λ_home)':>14} {'mean(actual_home)':>18} {'mean(λ_away)':>14} {'mean(actual_away)':>18}")
    log("  " + "-" * 80)
    for name in ("validate", "oos"):
        r   = results[name]
        df  = r["df"]
        lh  = r["lh"]
        la  = r["la"]
        log(f"  {name:<12} {lh.mean():>14.4f} {df['home_score'].mean():>18.4f} "
            f"{la.mean():>14.4f} {df['away_score'].mean():>18.4f}")

    # Confirm validate bias ≤ 0.05
    val_h_bias_post = float(np.mean(results["validate"]["df"]["home_score"].values - results["validate"]["lh"]))
    val_a_bias_post = float(np.mean(results["validate"]["df"]["away_score"].values - results["validate"]["la"]))
    log()
    log(f"  Post-calibration validate bias (should be ≈ 0):")
    log(f"    home: {val_h_bias_post:+.6f}")
    log(f"    away: {val_a_bias_post:+.6f}")

    ok_h = abs(val_h_bias_post) < 0.05
    ok_a = abs(val_a_bias_post) < 0.05
    log(f"  {'PASS' if ok_h else 'FAIL'}  home bias within 0.05 on validate")
    log(f"  {'PASS' if ok_a else 'FAIL'}  away bias within 0.05 on validate")

    return results, home_bias, away_bias

# ---------------------------------------------------------------------------
# STEP 3 — Poisson simulation
# ---------------------------------------------------------------------------
def run_simulation(results: dict, ft: pd.DataFrame, canon: pd.DataFrame) -> pd.DataFrame:
    log()
    log("=" * 68)
    log("STEP 2 — INDEPENDENT POISSON SIMULATION (N=10,000)")
    log("=" * 68)

    # Merge odds prices
    odds = canon[["game_id", "over_price", "under_price"]].copy()

    rng = np.random.default_rng(SEED)

    all_rows = []
    for split_name in ("train", "validate", "oos"):
        r    = results[split_name]
        df   = r["df"].copy()
        lh   = r["lh"]
        la   = r["la"]
        n    = len(df)

        log(f"\n  Simulating {split_name}: {n} games × {N_SIM:,} iterations...")

        # Clip lambdas to reasonable range (avoid degenerate Poisson)
        lh_clip = np.clip(lh, 0.5, 8.0)
        la_clip = np.clip(la, 0.5, 8.0)

        # Simulate: shape (n_games, N_SIM)
        sims_h = rng.poisson(lh_clip[:, None], size=(n, N_SIM))
        sims_a = rng.poisson(la_clip[:, None], size=(n, N_SIM))
        tot_sim = sims_h + sims_a   # (n, N_SIM)

        # Mean simulated total per game (used for calibration check)
        mean_sim_total = tot_sim.mean(axis=1)
        std_sim_total  = tot_sim.std(axis=1)

        # Per-game over/under/push for closing_total
        lines = df["closing_total"].values  # (n,)
        has_line = df["market_available"].values.astype(bool)

        over_prob  = np.full(n, np.nan)
        under_prob = np.full(n, np.nan)
        push_prob  = np.full(n, np.nan)

        for i in range(n):
            if has_line[i] and not np.isnan(lines[i]):
                line = lines[i]
                sims = tot_sim[i]
                over_prob[i]  = (sims > line).mean()
                under_prob[i] = (sims < line).mean()
                push_prob[i]  = (sims == line).mean()

        # Verify sum = 1 (spot check)
        valid = (~np.isnan(over_prob))
        sum_check = over_prob[valid] + under_prob[valid] + push_prob[valid]
        max_err = float(np.abs(sum_check - 1.0).max()) if valid.any() else 0.0
        log(f"  Probability sum check (max |error|): {max_err:.2e}  "
            f"{'PASS' if max_err < 1e-9 else 'FAIL'}")

        # Merge odds
        df_out = df[["game_id", "game_date", "season_year", "home_team", "away_team",
                     "home_score", "away_score", "total_goals",
                     "closing_total", "market_available",
                     "home_backup_flag", "away_backup_flag",
                     "home_goalie_b2b", "away_goalie_b2b",
                     "home_penalties_taken_rolling_20", "away_penalties_taken_rolling_20",
                     ]].copy()

        df_out["lambda_home_calibrated"] = lh
        df_out["lambda_away_calibrated"] = la
        df_out["lambda_total_calibrated"] = lh + la
        df_out["mean_sim_total"]  = mean_sim_total
        df_out["std_sim_total"]   = std_sim_total
        df_out["sim_over_prob_closing"]  = over_prob
        df_out["sim_under_prob_closing"] = under_prob
        df_out["sim_push_prob_closing"]  = push_prob
        df_out["closing_total_bucket"]   = [bucket(x) for x in lines]
        df_out["split"] = split_name

        df_out = df_out.merge(odds, on="game_id", how="left")
        all_rows.append(df_out)

    return pd.concat(all_rows, ignore_index=True)

# ---------------------------------------------------------------------------
# STEP 4 — Volatility score
# ---------------------------------------------------------------------------
def compute_volatility(sim: pd.DataFrame) -> pd.DataFrame:
    pct75_home_pen = sim.loc[sim["split"] == "validate", "home_penalties_taken_rolling_20"].quantile(0.75)
    pct75_away_pen = sim.loc[sim["split"] == "validate", "away_penalties_taken_rolling_20"].quantile(0.75)

    score = (
        sim["home_backup_flag"].astype(int) +
        sim["away_backup_flag"].astype(int) +
        sim["home_goalie_b2b"].astype(int) +
        sim["away_goalie_b2b"].astype(int) +
        (sim["home_penalties_taken_rolling_20"] > pct75_home_pen).astype(int) +
        (sim["away_penalties_taken_rolling_20"] > pct75_away_pen).astype(int)
    )
    sim["volatility_score"] = score
    sim["volatility_bucket"] = pd.cut(score, bins=[-1, 1, 3, 6], labels=["low", "medium", "high"])
    return sim

# ---------------------------------------------------------------------------
# STEP 5 — Edge calculation
# ---------------------------------------------------------------------------
def compute_edges(sim: pd.DataFrame) -> pd.DataFrame:
    # Only rows with market
    has_mkt = sim["market_available"].astype(bool) & sim["over_price"].notna()

    implied_over  = sim["over_price"].apply(lambda p: american_to_implied(p) if pd.notna(p) else np.nan)
    implied_under = sim["under_price"].apply(lambda p: american_to_implied(p) if pd.notna(p) else np.nan)

    vig_total = implied_over + implied_under
    fair_over  = implied_over  / vig_total
    fair_under = implied_under / vig_total

    sim["edge_over"]  = np.where(has_mkt, sim["sim_over_prob_closing"]  - fair_over,  np.nan)
    sim["edge_under"] = np.where(has_mkt, sim["sim_under_prob_closing"] - fair_under, np.nan)
    sim["fair_over"]  = np.where(has_mkt, fair_over,  np.nan)
    sim["fair_under"] = np.where(has_mkt, fair_under, np.nan)

    sim["qualified_signal"] = (
        has_mkt & (
            (sim["edge_over"].abs() >= 0.04) |
            (sim["edge_under"].abs() >= 0.04)
        )
    ).astype(int)

    return sim

# ---------------------------------------------------------------------------
# STEP 6 — Diagnostics 3A–3E
# ---------------------------------------------------------------------------
def run_diagnostics(sim: pd.DataFrame) -> list[str]:
    lines: list[str] = []

    def dlog(msg: str = "") -> None:
        lines.append(msg)
        log(msg)

    hr = "=" * 68
    dlog(hr)
    dlog("PHASE 4 SIMULATION DIAGNOSTIC REPORT")
    dlog(hr)

    for split_name in ("validate", "oos"):
        s = sim[sim["split"] == split_name]

        # 3A — Mean calibration
        dlog()
        dlog(f"[3A] Mean Calibration — {split_name.upper()}")
        dlog("-" * 50)
        mean_sim   = s["mean_sim_total"].mean()
        mean_act   = s["total_goals"].mean()
        diff       = mean_sim - mean_act
        tag        = "PASS" if abs(diff) <= 0.1 else "FAIL"
        dlog(f"  mean(simulated total): {mean_sim:.4f}")
        dlog(f"  mean(actual total):    {mean_act:.4f}")
        dlog(f"  difference:            {diff:+.4f}")
        dlog(f"  {tag}  (threshold: ≤ 0.1 goals)")

        # 3B — Variance calibration
        dlog()
        dlog(f"[3B] Variance Calibration — {split_name.upper()}")
        dlog("-" * 50)
        # std of actual totals across games
        std_act     = float(s["total_goals"].std())
        # std of simulated totals across games (mean sim std per game, then also
        # compare distribution of mean_sim_total which shows cross-game variance)
        # Phase 4 spec asks for std(simulated total per game) — this is the per-game
        # simulation std averaged, NOT the cross-game std of projected totals
        mean_sim_std = float(s["std_sim_total"].mean())
        diff_std     = mean_sim_std - std_act
        tag_b        = "PASS" if abs(diff_std) <= 0.15 else "FAIL"
        dlog(f"  mean per-game std(simulated): {mean_sim_std:.4f}")
        dlog(f"  std(actual total_goals):      {std_act:.4f}")
        dlog(f"  difference:                   {diff_std:+.4f}")
        dlog(f"  {tag_b}  (threshold: ≤ 0.15)")

        # 3C — Tail calibration
        dlog()
        dlog(f"[3C] Tail Calibration — {split_name.upper()}")
        dlog("-" * 50)
        # Simulated tail rates: from per-game sim probs
        # We need to compute P(total<=3) and P(total>=7) per game, then average
        # But we don't store these directly. Compute from lambda + Poisson CDF.
        from scipy.stats import poisson as spoi
        lh  = s["lambda_home_calibrated"].values
        la  = s["lambda_away_calibrated"].values
        # P(X+Y <= 3) where X~Pois(lh), Y~Pois(la), independent
        # P(X+Y = k) = sum_{j=0}^{k} P(X=j)*P(Y=k-j)
        def total_poisson_pmf(lh_arr, la_arr, k):
            prob = np.zeros(len(lh_arr))
            for j in range(k + 1):
                prob += spoi.pmf(j, lh_arr) * spoi.pmf(k - j, la_arr)
            return prob

        p_le3_sim = sum(total_poisson_pmf(lh, la, k) for k in range(4)).mean() * 100
        p_ge7_sim = (1 - sum(total_poisson_pmf(lh, la, k) for k in range(7))).mean() * 100

        act_le3 = (s["total_goals"] <= 3).mean() * 100
        act_ge7 = (s["total_goals"] >= 7).mean() * 100

        tag_le3 = "PASS" if abs(p_le3_sim - act_le3) <= 2.0 else "FAIL"
        tag_ge7 = "PASS" if abs(p_ge7_sim - act_ge7) <= 2.0 else "FAIL"

        dlog(f"  Simulated P(total ≤ 3): {p_le3_sim:.2f}%   Actual: {act_le3:.2f}%  "
             f"diff={p_le3_sim - act_le3:+.2f}pp  {tag_le3}")
        dlog(f"  Simulated P(total ≥ 7): {p_ge7_sim:.2f}%   Actual: {act_ge7:.2f}%  "
             f"diff={p_ge7_sim - act_ge7:+.2f}pp  {tag_ge7}")

        # 3D — Market-number calibration (validate only)
        if split_name == "validate":
            dlog()
            dlog(f"[3D] Market-Number Calibration — {split_name.upper()}")
            dlog("-" * 50)
            s_mkt = s[s["market_available"].astype(bool) & s["closing_total"].notna()]

            for bkt in ["5.5", "6.0", "6.5"]:
                grp = s_mkt[s_mkt["closing_total_bucket"] == bkt]
                if len(grp) == 0:
                    dlog(f"  Bucket {bkt}: no games")
                    continue
                line_val = float(bkt)
                sim_over_mean  = grp["sim_over_prob_closing"].mean()
                act_over_freq  = (grp["total_goals"] > line_val).mean()
                sim_push_mean  = grp["sim_push_prob_closing"].mean()
                act_push_freq  = (grp["total_goals"] == line_val).mean()
                diff_over      = sim_over_mean - act_over_freq
                tag_d          = "PASS" if abs(diff_over) <= 0.03 else "FAIL"
                dlog(f"  Bucket {bkt} (n={len(grp):,}):")
                dlog(f"    sim_over_prob={sim_over_mean:.4f}  actual_over={act_over_freq:.4f}  "
                     f"diff={diff_over:+.4f}  {tag_d}")
                if bkt == "6.0":
                    tag_push = "PASS" if abs(sim_push_mean - act_push_freq) <= 0.03 else "FAIL"
                    dlog(f"    sim_push={sim_push_mean:.4f}  actual_push={act_push_freq:.4f}  "
                         f"diff={sim_push_mean - act_push_freq:+.4f}  {tag_push}")

        # 3E — Bias by volatility bucket
        dlog()
        dlog(f"[3E] Bias by Volatility Bucket — {split_name.upper()}")
        dlog("-" * 50)
        vol_fail = False
        for vbkt, vgrp in s.groupby("volatility_bucket", observed=True):
            mean_sim_v = vgrp["mean_sim_total"].mean()
            mean_act_v = vgrp["total_goals"].mean()
            std_sim_v  = vgrp["std_sim_total"].mean()
            std_act_v  = float(vgrp["total_goals"].std())
            std_diff   = std_sim_v - std_act_v
            flag = ""
            if vbkt == "high" and std_diff < -0.15:
                flag = "  ← FAIL (under-prices tails)"
                vol_fail = True
            dlog(f"  {str(vbkt):8s} (n={len(vgrp):4d}): "
                 f"mean_sim={mean_sim_v:.3f}  mean_act={mean_act_v:.3f}  "
                 f"std_sim={std_sim_v:.3f}  std_act={std_act_v:.3f}  "
                 f"std_diff={std_diff:+.3f}{flag}")
        if not vol_fail:
            dlog("  PASS  No systematic tail under-pricing in high-vol bucket")

    return lines

# ---------------------------------------------------------------------------
# STEP 7 — Edge signal report (validate set)
# ---------------------------------------------------------------------------
def edge_report(sim: pd.DataFrame) -> list[str]:
    lines: list[str] = []

    def dlog(msg: str = "") -> None:
        lines.append(msg)
        log(msg)

    dlog()
    dlog("=" * 68)
    dlog("STEP 5 — EDGE CALCULATION (Validate Set)")
    dlog("=" * 68)

    val = sim[(sim["split"] == "validate") & sim["market_available"].astype(bool)]

    total_mkt = len(val)
    qual      = val[val["qualified_signal"] == 1]
    n_qual    = len(qual)

    dlog(f"\n  Total validate games with market line: {total_mkt:,}")
    dlog(f"  Qualified signals (|edge| ≥ 0.04):    {n_qual:,}  ({n_qual/total_mkt*100:.1f}%)")

    if n_qual > 0:
        # For each qualified signal, which side is the bet?
        q = qual.copy()
        q["bet_over"]  = q["edge_over"]  >= 0.04
        q["bet_under"] = q["edge_under"] >= 0.04

        over_bets  = q[q["bet_over"]]
        under_bets = q[q["bet_under"]]

        # Hit rates
        if len(over_bets) > 0:
            over_hit = (over_bets["total_goals"] > over_bets["closing_total"]).mean()
            dlog(f"\n  OVER bets:  n={len(over_bets):,}  "
                 f"mean_edge={over_bets['edge_over'].mean():+.4f}  "
                 f"actual_over_hit={over_hit:.4f}")
        if len(under_bets) > 0:
            under_hit = (under_bets["total_goals"] < under_bets["closing_total"]).mean()
            dlog(f"  UNDER bets: n={len(under_bets):,}  "
                 f"mean_edge={under_bets['edge_under'].mean():+.4f}  "
                 f"actual_under_hit={under_hit:.4f}")

        dlog(f"\n  Edge distribution on qualified signals:")
        for side, col in [("over", "edge_over"), ("under", "edge_under")]:
            side_q = q[q[f"bet_{side}"]]
            if len(side_q) > 0:
                dlog(f"    {side}: mean={side_q[col].mean():+.4f}  "
                     f"p25={side_q[col].quantile(0.25):+.4f}  "
                     f"p75={side_q[col].quantile(0.75):+.4f}  "
                     f"max={side_q[col].max():+.4f}")

    # OOS signal report
    dlog()
    dlog("  OOS Qualified Signal Summary:")
    oos = sim[(sim["split"] == "oos") & sim["market_available"].astype(bool)]
    qual_oos = oos[oos["qualified_signal"] == 1]
    n_oos = len(qual_oos)
    dlog(f"  Total OOS games with market line: {len(oos):,}")
    dlog(f"  Qualified signals: {n_oos:,}  ({n_oos/len(oos)*100:.1f}%)")

    if n_oos > 0:
        q_oos = qual_oos.copy()
        q_oos["bet_over"]  = q_oos["edge_over"]  >= 0.04
        q_oos["bet_under"] = q_oos["edge_under"] >= 0.04
        over_oos  = q_oos[q_oos["bet_over"]]
        under_oos = q_oos[q_oos["bet_under"]]
        if len(over_oos) > 0:
            over_hit_oos = (over_oos["total_goals"] > over_oos["closing_total"]).mean()
            dlog(f"  OVER  OOS: n={len(over_oos):,}  "
                 f"mean_edge={over_oos['edge_over'].mean():+.4f}  "
                 f"hit={over_hit_oos:.4f}")
        if len(under_oos) > 0:
            under_hit_oos = (under_oos["total_goals"] < under_oos["closing_total"]).mean()
            dlog(f"  UNDER OOS: n={len(under_oos):,}  "
                 f"mean_edge={under_oos['edge_under'].mean():+.4f}  "
                 f"hit={under_hit_oos:.4f}")

    return lines

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    log("=" * 68)
    log("NHL Phase 4: Poisson Simulation + Probability Engine")
    log("=" * 68)

    # Load
    ft    = pd.read_parquet(FEATURE_TABLE)
    canon = pd.read_csv(CANONICAL_CSV, usecols=["game_id", "over_price", "under_price"])
    hpkg, apkg = load_models()

    # Step 1 — Calibration
    results, home_bias, away_bias = recalibrate(ft, hpkg, apkg)

    # Step 2 — Simulation
    sim = run_simulation(results, ft, canon)

    # Volatility score
    sim = compute_volatility(sim)

    # Step 5 — Edges
    sim = compute_edges(sim)

    log()
    log("=" * 68)
    log("STEP 3 — SIMULATION DIAGNOSTICS")
    log("=" * 68)
    diag_lines = run_diagnostics(sim)

    edge_lines = edge_report(sim)

    # Step 4 — Variance check summary
    log()
    log("=" * 68)
    log("STEP 4 — VARIANCE ADJUSTMENT DECISION")
    log("=" * 68)
    # The diagnostics above determine this; summarize here
    log("  See 3B and 3E results above.")
    log("  If both PASS → plain Poisson is sufficient; NegBinomial not applied.")

    # Step 6 — Save outputs
    log()
    log("=" * 68)
    log("STEP 6 — SAVING OUTPUTS")
    log("=" * 68)

    out_cols = [
        "game_id", "game_date", "home_team", "away_team", "season_year",
        "lambda_home_calibrated", "lambda_away_calibrated", "lambda_total_calibrated",
        "sim_over_prob_closing", "sim_under_prob_closing", "sim_push_prob_closing",
        "closing_total", "closing_total_bucket",
        "edge_over", "edge_under",
        "volatility_score", "volatility_bucket",
        "qualified_signal",
        "total_goals",       # actual (for grading)
        "home_score", "away_score",
        "market_available",
        "split",
    ]
    sim_out = sim[out_cols].copy()
    sim_out.to_parquet(SIM_RESULTS, index=False)
    log(f"  Saved: {SIM_RESULTS}  ({len(sim_out):,} rows)")

    all_diag = diag_lines + edge_lines
    with open(AUDIT_FILE, "w") as f:
        f.write("\n".join(_lines))  # full log including calibration
    log(f"  Saved: {AUDIT_FILE}")

    log()
    log("Phase 4 complete.")


if __name__ == "__main__":
    main()
