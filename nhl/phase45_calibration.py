#!/usr/bin/env python3
"""
NHL Totals Model — Phase 4.5: Calibration Repair
=================================================
Replaces static intercept correction with rolling seasonal drift.
Does NOT modify ridge models, feature table, or simulation architecture.

Outputs
  nhl/nhl_sim_results_calibrated.parquet
  nhl/phase45_calibration_audit.txt
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson as spoi

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
NHL_DIR      = Path(__file__).parent
FEATURE_TABLE = NHL_DIR / "nhl_feature_table.parquet"
CANONICAL_CSV = NHL_DIR / "nhl_games_canonical.csv"
HOME_PKL      = NHL_DIR / "ridge_home_model.pkl"
AWAY_PKL      = NHL_DIR / "ridge_away_model.pkl"
SIM_OUT       = NHL_DIR / "nhl_sim_results_calibrated.parquet"
AUDIT_FILE    = NHL_DIR / "phase45_calibration_audit.txt"

N_SIM  = 10_000
SEED   = 42
MIN_GAMES_FOR_SEASONAL_DRIFT = 10

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
# Helpers
# ---------------------------------------------------------------------------
def american_to_implied(price: float) -> float:
    if pd.isna(price):
        return np.nan
    return abs(price) / (abs(price) + 100.0) if price < 0 else 100.0 / (100.0 + price)

def bucket(line: float) -> str:
    if pd.isna(line):
        return "null"
    return {5.5: "5.5", 6.0: "6.0", 6.5: "6.5"}.get(line, "other")

def predict_raw(pkg: dict, df: pd.DataFrame) -> np.ndarray:
    X    = df[pkg["features"]].to_numpy()
    X_sc = pkg["scaler"].transform(X)
    return pkg["model"].predict(X_sc)

# ---------------------------------------------------------------------------
# STEP 1 — Dynamic seasonal drift calibration
# ---------------------------------------------------------------------------
def compute_dynamic_calibration(ft: pd.DataFrame, hpkg: dict, apkg: dict) -> pd.DataFrame:
    log("=" * 68)
    log("STEP 1 — DYNAMIC SEASONAL DRIFT CALIBRATION")
    log("=" * 68)

    # Fill nulls using train column means (same as Phase 3/4)
    all_feats = sorted(set(hpkg["features"] + apkg["features"]))
    train_means = ft[ft["season_year"].isin(TRAIN_SEASONS)][all_feats].mean()
    ft2 = ft.copy()
    ft2[all_feats] = ft2[all_feats].fillna(train_means)

    # Raw (uncalibrated) predictions for all games
    lh_raw = predict_raw(hpkg, ft2)
    la_raw = predict_raw(apkg, ft2)
    ft2["lh_raw"] = lh_raw
    ft2["la_raw"] = la_raw
    ft2["lt_raw"] = lh_raw + la_raw

    # ---- Validate-season mean drift (fallback prior) ----
    val_mask = ft2["season_year"].isin(VAL_SEASONS)
    val_drift = float(np.mean(ft2.loc[val_mask, "total_goals"].values
                              - ft2.loc[val_mask, "lt_raw"].values))
    log(f"\n  Validate-season mean drift (fallback prior): {val_drift:+.4f}")
    log(f"  Validate mean actual total: {ft2.loc[val_mask,'total_goals'].mean():.4f}")
    log(f"  Validate mean raw lambda:   {ft2.loc[val_mask,'lt_raw'].mean():.4f}")

    # ---- Compute per-game rolling seasonal drift ----
    # Sort by (season_year, game_date) for rolling
    ft2 = ft2.sort_values(["season_year", "game_date", "game_id"]).reset_index(drop=True)

    seasonal_drift_list = np.full(len(ft2), np.nan)

    for season, grp in ft2.groupby("season_year", sort=True):
        grp = grp.sort_values(["game_date", "game_id"])
        idx = grp.index.tolist()

        cum_actual = []
        cum_model  = []

        for pos, gidx in enumerate(idx):
            n_prior = pos  # games before this one in same season

            if n_prior < MIN_GAMES_FOR_SEASONAL_DRIFT:
                drift = val_drift
            else:
                league_avg = float(np.mean(cum_actual))
                model_avg  = float(np.mean(cum_model))
                drift      = league_avg - model_avg

            seasonal_drift_list[gidx] = drift

            # Accumulate for next game (only add after drift is recorded)
            cum_actual.append(ft2.at[gidx, "total_goals"])
            cum_model.append(ft2.at[gidx, "lt_raw"])

    ft2["seasonal_drift"] = seasonal_drift_list

    # Calibrated lambdas
    ft2["lh_cal"] = ft2["lh_raw"] + ft2["seasonal_drift"] / 2.0
    ft2["la_cal"] = ft2["la_raw"] + ft2["seasonal_drift"] / 2.0
    ft2["lt_cal"] = ft2["lh_cal"] + ft2["la_cal"]

    # ---- Diagnostic: mean calibration after dynamic adjustment ----
    log()
    log("  Post-dynamic-calibration mean comparison:")
    log(f"  {'Split':<12} {'λ_h_cal':>10} {'act_h':>10} {'λ_a_cal':>10} {'act_a':>10} "
        f"{'λ_total':>10} {'act_total':>10} {'drift':>8}")
    log("  " + "-" * 84)

    for name, mask in [("train",    ft2["season_year"].isin(TRAIN_SEASONS)),
                       ("validate", ft2["season_year"].isin(VAL_SEASONS)),
                       ("oos",      ft2["season_year"].isin(OOS_SEASONS))]:
        s    = ft2[mask]
        lh_m = s["lh_cal"].mean()
        la_m = s["la_cal"].mean()
        lt_m = s["lt_cal"].mean()
        ah_m = s["home_score"].mean()
        aa_m = s["away_score"].mean()
        at_m = s["total_goals"].mean()
        d_m  = s["seasonal_drift"].mean()
        log(f"  {name:<12} {lh_m:>10.4f} {ah_m:>10.4f} {la_m:>10.4f} {aa_m:>10.4f} "
            f"{lt_m:>10.4f} {at_m:>10.4f} {d_m:>8.4f}")

    # Gate check: OOS mean drift < 0.10
    oos_mask  = ft2["season_year"].isin(OOS_SEASONS)
    oos_drift = float(np.mean(ft2.loc[oos_mask, "total_goals"].values
                              - ft2.loc[oos_mask, "lt_cal"].values))
    log()
    log(f"  OOS mean drift after calibration: {oos_drift:+.4f}")
    ok = abs(oos_drift) < 0.10
    log(f"  {'PASS' if ok else 'FAIL'}  OOS mean drift < 0.10 target {'(proceeding)' if ok else '(STOP)'}")

    return ft2, val_drift, ok

# ---------------------------------------------------------------------------
# STEP 2 — Poisson simulation with calibrated lambdas
# ---------------------------------------------------------------------------
def run_simulation(ft2: pd.DataFrame, canon: pd.DataFrame) -> pd.DataFrame:
    log()
    log("=" * 68)
    log("STEP 2 — POISSON SIMULATION WITH CALIBRATED LAMBDAS (N=10,000)")
    log("=" * 68)

    odds = canon[["game_id", "over_price", "under_price"]].copy()
    rng  = np.random.default_rng(SEED)

    result_rows = []

    for split_name, mask in [("train",    ft2["season_year"].isin(TRAIN_SEASONS)),
                              ("validate", ft2["season_year"].isin(VAL_SEASONS)),
                              ("oos",      ft2["season_year"].isin(OOS_SEASONS))]:
        s = ft2[mask].copy()
        n = len(s)
        log(f"\n  {split_name}: {n} games")

        lh = np.clip(s["lh_cal"].values, 0.5, 8.0)
        la = np.clip(s["la_cal"].values, 0.5, 8.0)

        sims_h  = rng.poisson(lh[:, None], size=(n, N_SIM))
        sims_a  = rng.poisson(la[:, None], size=(n, N_SIM))
        tot_sim = sims_h + sims_a

        mean_sim = tot_sim.mean(axis=1)
        std_sim  = tot_sim.std(axis=1)

        lines    = s["closing_total"].values
        has_line = s["market_available"].values.astype(bool)

        over_p  = np.full(n, np.nan)
        under_p = np.full(n, np.nan)
        push_p  = np.full(n, np.nan)

        for i in range(n):
            if has_line[i] and not np.isnan(lines[i]):
                sim = tot_sim[i]
                over_p[i]  = (sim > lines[i]).mean()
                under_p[i] = (sim < lines[i]).mean()
                push_p[i]  = (sim == lines[i]).mean()

        # Probability sum check
        valid   = ~np.isnan(over_p)
        sum_err = float(np.abs((over_p[valid] + under_p[valid] + push_p[valid]) - 1.0).max())
        log(f"  Probability sum check (max |err|): {sum_err:.2e}  "
            f"{'PASS' if sum_err < 1e-9 else 'FAIL'}")

        df_out = s[["game_id", "game_date", "season_year", "home_team", "away_team",
                    "home_score", "away_score", "total_goals",
                    "closing_total", "market_available",
                    "lh_cal", "la_cal", "lt_cal", "seasonal_drift",
                    "home_backup_flag", "away_backup_flag",
                    "home_goalie_b2b", "away_goalie_b2b",
                    "home_penalties_taken_rolling_20", "away_penalties_taken_rolling_20",
                    ]].copy()

        df_out = df_out.rename(columns={
            "lh_cal": "lambda_home_calibrated",
            "la_cal": "lambda_away_calibrated",
            "lt_cal": "lambda_total_calibrated",
        })

        df_out["mean_sim_total"]         = mean_sim
        df_out["std_sim_total"]          = std_sim
        df_out["sim_over_prob_closing"]  = over_p
        df_out["sim_under_prob_closing"] = under_p
        df_out["sim_push_prob_closing"]  = push_p
        df_out["closing_total_bucket"]   = [bucket(x) for x in lines]
        df_out["split"]                  = split_name

        df_out = df_out.merge(odds, on="game_id", how="left")
        result_rows.append(df_out)

    return pd.concat(result_rows, ignore_index=True)

# ---------------------------------------------------------------------------
# Volatility score
# ---------------------------------------------------------------------------
def compute_volatility(sim: pd.DataFrame) -> pd.DataFrame:
    p75_h = sim.loc[sim["split"] == "validate", "home_penalties_taken_rolling_20"].quantile(0.75)
    p75_a = sim.loc[sim["split"] == "validate", "away_penalties_taken_rolling_20"].quantile(0.75)
    score = (
        sim["home_backup_flag"].astype(int) +
        sim["away_backup_flag"].astype(int) +
        sim["home_goalie_b2b"].astype(int) +
        sim["away_goalie_b2b"].astype(int) +
        (sim["home_penalties_taken_rolling_20"] > p75_h).astype(int) +
        (sim["away_penalties_taken_rolling_20"] > p75_a).astype(int)
    )
    sim["volatility_score"]  = score
    sim["volatility_bucket"] = pd.cut(score, bins=[-1, 1, 3, 6], labels=["low", "medium", "high"])
    return sim

# ---------------------------------------------------------------------------
# Edge calculation
# ---------------------------------------------------------------------------
def compute_edges(sim: pd.DataFrame) -> pd.DataFrame:
    has_mkt = sim["market_available"].astype(bool) & sim["over_price"].notna()

    imp_o = sim["over_price"].apply(lambda p: american_to_implied(p) if pd.notna(p) else np.nan)
    imp_u = sim["under_price"].apply(lambda p: american_to_implied(p) if pd.notna(p) else np.nan)
    vig   = imp_o + imp_u
    fair_o = imp_o / vig
    fair_u = imp_u / vig

    sim["edge_over"]  = np.where(has_mkt, sim["sim_over_prob_closing"]  - fair_o,  np.nan)
    sim["edge_under"] = np.where(has_mkt, sim["sim_under_prob_closing"] - fair_u, np.nan)
    return sim

# ---------------------------------------------------------------------------
# STEP 3 — Diagnostics
# ---------------------------------------------------------------------------
def run_diagnostics(sim: pd.DataFrame) -> list[str]:
    lines: list[str] = []

    def dlog(msg: str = "") -> None:
        lines.append(msg)
        log(msg)

    hr = "=" * 68
    dlog(hr)
    dlog("STEP 3 — DIAGNOSTICS (Phase 4.5)")
    dlog(hr)

    for split_name in ("validate", "oos"):
        s = sim[sim["split"] == split_name]

        # 3A — Mean calibration
        dlog()
        dlog(f"[3A] Mean Calibration — {split_name.upper()}")
        dlog("-" * 50)
        mean_sim = s["mean_sim_total"].mean()
        mean_act = s["total_goals"].mean()
        diff     = mean_sim - mean_act
        tag      = "PASS" if abs(diff) <= 0.10 else "FAIL"
        dlog(f"  mean(simulated total): {mean_sim:.4f}")
        dlog(f"  mean(actual total):    {mean_act:.4f}")
        dlog(f"  difference:            {diff:+.4f}")
        dlog(f"  {tag}  (threshold: ≤ 0.10 goals)")

        # 3B — Variance calibration
        dlog()
        dlog(f"[3B] Variance Calibration — {split_name.upper()}")
        dlog("-" * 50)
        mean_sim_std = float(s["std_sim_total"].mean())
        std_act      = float(s["total_goals"].std())
        diff_std     = mean_sim_std - std_act
        tag_b        = "PASS" if abs(diff_std) <= 0.15 else "FAIL"
        dlog(f"  mean per-game sim std: {mean_sim_std:.4f}")
        dlog(f"  actual total std:      {std_act:.4f}  (reference: 2.31)")
        dlog(f"  difference:            {diff_std:+.4f}")
        dlog(f"  {tag_b}  (threshold: ≤ 0.15)")

        # 3C — Tail calibration
        dlog()
        dlog(f"[3C] Tail Calibration — {split_name.upper()}")
        dlog("-" * 50)
        lh = s["lambda_home_calibrated"].values
        la = s["lambda_away_calibrated"].values

        def total_pmf(lh_arr, la_arr, k):
            p = np.zeros(len(lh_arr))
            for j in range(k + 1):
                p += spoi.pmf(j, lh_arr) * spoi.pmf(k - j, la_arr)
            return p

        p_le3 = sum(total_pmf(lh, la, k) for k in range(4)).mean() * 100
        p_ge7 = (1.0 - sum(total_pmf(lh, la, k) for k in range(7))).mean() * 100

        act_le3 = (s["total_goals"] <= 3).mean() * 100
        act_ge7 = (s["total_goals"] >= 7).mean() * 100

        tag_le3 = "PASS" if abs(p_le3 - act_le3) <= 2.0 else "FAIL"
        tag_ge7 = "PASS" if abs(p_ge7 - act_ge7) <= 2.0 else "FAIL"

        dlog(f"  P(total ≤ 3): sim={p_le3:.2f}%  actual={act_le3:.2f}%  "
             f"diff={p_le3-act_le3:+.2f}pp  {tag_le3}")
        dlog(f"  P(total ≥ 7): sim={p_ge7:.2f}%  actual={act_ge7:.2f}%  "
             f"diff={p_ge7-act_ge7:+.2f}pp  {tag_ge7}")

        # 3D — Market calibration (validate only)
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
                line_val  = float(bkt)
                sim_over  = grp["sim_over_prob_closing"].mean()
                act_over  = (grp["total_goals"] > line_val).mean()
                sim_push  = grp["sim_push_prob_closing"].mean()
                act_push  = (grp["total_goals"] == line_val).mean()
                diff_over = sim_over - act_over
                tag_d     = "PASS" if abs(diff_over) <= 0.03 else "FAIL"
                dlog(f"  Bucket {bkt} (n={len(grp):,}):")
                dlog(f"    sim_over={sim_over:.4f}  act_over={act_over:.4f}  "
                     f"diff={diff_over:+.4f}  {tag_d}")
                if bkt == "6.0":
                    tag_push = "PASS" if abs(sim_push - act_push) <= 0.03 else "FAIL"
                    dlog(f"    sim_push={sim_push:.4f}  act_push={act_push:.4f}  "
                         f"diff={sim_push-act_push:+.4f}  {tag_push}")

        # 3E — Volatility bucket (validate only)
        if split_name == "validate":
            dlog()
            dlog(f"[3E] Volatility Bucket Diagnostics — {split_name.upper()}")
            dlog("-" * 50)
            vol_fail = False
            for vbkt, vgrp in s.groupby("volatility_bucket", observed=True):
                m_sim  = vgrp["mean_sim_total"].mean()
                m_act  = vgrp["total_goals"].mean()
                s_sim  = vgrp["std_sim_total"].mean()
                s_act  = float(vgrp["total_goals"].std())
                s_diff = s_sim - s_act
                flag   = ""
                if vbkt == "high" and s_diff < -0.15:
                    flag     = "  ← FAIL"
                    vol_fail = True
                dlog(f"  {str(vbkt):8s} (n={len(vgrp):4d}): "
                     f"mean_sim={m_sim:.3f}  mean_act={m_act:.3f}  "
                     f"std_sim={s_sim:.3f}  std_act={s_act:.3f}  "
                     f"std_diff={s_diff:+.3f}{flag}")
            if not vol_fail:
                dlog("  PASS  No tail under-pricing in high-vol bucket")

    # 3F — Signal balance (validate and OOS)
    dlog()
    dlog("[3F] Signal Balance Diagnostics")
    dlog("-" * 50)
    for split_name in ("validate", "oos"):
        s = sim[(sim["split"] == split_name) & sim["market_available"].astype(bool)]
        dlog(f"\n  {split_name.upper()} ({len(s):,} market games):")

        lt_diff = (s["lambda_total_calibrated"] - s["closing_total"]).mean()
        dlog(f"  mean(λ_total − closing_total): {lt_diff:+.4f}")

        for side, edge_col, line_col, gt in [
            ("OVER",  "edge_over",  "closing_total", True),
            ("UNDER", "edge_under", "closing_total", False),
        ]:
            sigs = s[s[edge_col] >= 0.04]
            if len(sigs) == 0:
                dlog(f"  {side}: 0 signals at edge ≥ 0.04")
                continue
            if gt:
                hit = (sigs["total_goals"] > sigs[line_col]).mean()
            else:
                hit = (sigs["total_goals"] < sigs[line_col]).mean()
            dlog(f"  {side}: n={len(sigs):,}  mean_edge={sigs[edge_col].mean():+.4f}  "
                 f"hit_rate={hit:.4f}")

    return lines

# ---------------------------------------------------------------------------
# STEP 4 — Empirical edge threshold (validate set)
# ---------------------------------------------------------------------------
def build_edge_threshold(sim: pd.DataFrame) -> tuple[float, list[str]]:
    lines: list[str] = []

    def dlog(msg: str = "") -> None:
        lines.append(msg)
        log(msg)

    dlog()
    dlog("=" * 68)
    dlog("STEP 4 — EMPIRICAL EDGE THRESHOLD (validate set)")
    dlog("=" * 68)

    val = sim[(sim["split"] == "validate") &
              sim["market_available"].astype(bool) &
              sim["closing_total"].notna()].copy()

    # Collect all individual signals (over and under separately)
    sig_rows = []
    for _, row in val.iterrows():
        eo = row["edge_over"]
        eu = row["edge_under"]
        line = row["closing_total"]
        act  = row["total_goals"]
        if pd.notna(eo) and eo > 0:
            sig_rows.append({"edge": eo, "hit": int(act > line)})
        if pd.notna(eu) and eu > 0:
            sig_rows.append({"edge": eu, "hit": int(act < line)})

    signals = pd.DataFrame(sig_rows)

    BREAKEVEN = 110.0 / (110.0 + 100.0)  # 52.38%
    bands = [(0.00, 0.02), (0.02, 0.04), (0.04, 0.06),
             (0.06, 0.08), (0.08, 0.10), (0.10, 1.00)]

    dlog()
    dlog(f"  Break-even hit rate at -110: {BREAKEVEN:.4f} ({BREAKEVEN*100:.2f}%)")
    dlog()
    dlog(f"  {'Edge band':<14} {'n':>6}  {'hit_rate':>10}  {'>=52.5%?':>10}  {'n>=30?':>8}")
    dlog("  " + "-" * 56)

    provisional_threshold: float | None = None

    for lo, hi in bands:
        label = f"{lo:.2f}–{hi:.2f}" if hi < 1.0 else f"{lo:.2f}+"
        mask  = (signals["edge"] >= lo) & (signals["edge"] < hi)
        grp   = signals[mask]
        n     = len(grp)
        if n == 0:
            dlog(f"  {label:<14} {'0':>6}  {'—':>10}  {'—':>10}  {'—':>8}")
            continue
        hit = grp["hit"].mean()
        ok_hit = hit >= 0.525
        ok_n   = n >= 30
        dlog(f"  {label:<14} {n:>6}  {hit:>10.4f}  "
             f"{'YES' if ok_hit else 'NO':>10}  {'YES' if ok_n else 'NO':>8}")
        if provisional_threshold is None and ok_hit and ok_n:
            provisional_threshold = lo

    dlog()
    if provisional_threshold is not None:
        dlog(f"  PROVISIONAL THRESHOLD: {provisional_threshold:.2f}")
        dlog(f"  (lowest band with hit ≥ 52.5% AND n ≥ 30)")
    else:
        dlog("  NO THRESHOLD FOUND: no band meets hit ≥ 52.5% AND n ≥ 30")
        dlog("  Qualified_signal will be set to 0 for all games pending re-calibration.")
        provisional_threshold = 99.0  # sentinel — no signal qualifies

    return provisional_threshold, lines

# ---------------------------------------------------------------------------
# STEP 5 — Assess 6.0 push inflation
# ---------------------------------------------------------------------------
def assess_push_correction(sim: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    lines: list[str] = []

    def dlog(msg: str = "") -> None:
        lines.append(msg)
        log(msg)

    dlog()
    dlog("=" * 68)
    dlog("STEP 5 — 6.0 PUSH INFLATION ASSESSMENT")
    dlog("=" * 68)

    val_60 = sim[(sim["split"] == "validate") &
                 (sim["closing_total_bucket"] == "6.0") &
                 sim["market_available"].astype(bool)].copy()

    sim_push_60  = val_60["sim_push_prob_closing"].mean()
    act_push_60  = (val_60["total_goals"] == 6.0).mean()
    push_diff_60 = sim_push_60 - act_push_60

    dlog(f"\n  Validate bucket 6.0: sim_push={sim_push_60:.4f}  "
         f"act_push={act_push_60:.4f}  diff={push_diff_60:+.4f}")

    if abs(push_diff_60) <= 0.03:
        dlog("  PASS  6.0 push diff ≤ 3pp — mean correction sufficient, no distribution change needed.")
        return sim, lines

    # Push inflation still present — apply mild empirical correction for integer lines
    dlog(f"  FAIL  6.0 push diff = {push_diff_60:+.4f} > 3pp — applying push correction")

    # Compute correction per integer line from validate
    corrections: dict[float, float] = {}
    for int_line in [5.0, 6.0, 7.0]:
        bkt = sim[(sim["split"] == "validate") &
                  (sim["closing_total"] == int_line) &
                  sim["market_available"].astype(bool)]
        if len(bkt) < 10:
            continue
        sim_push  = bkt["sim_push_prob_closing"].mean()
        act_push  = (bkt["total_goals"] == int_line).mean()
        corr      = act_push - sim_push  # positive → sim over-estimates push
        corrections[int_line] = corr
        dlog(f"  Line {int_line}: sim_push={sim_push:.4f}  act_push={act_push:.4f}  "
             f"correction={corr:+.4f}")

    # Apply: redistribute half the push excess to over and under equally
    sim = sim.copy()
    for int_line, corr in corrections.items():
        mask = sim["closing_total"] == int_line
        if not mask.any():
            continue
        # corr = act_push - sim_push
        # If corr < 0: sim pushes too much → reduce push, add to over+under
        # We move (-corr * 0.5) from push to each of over and under
        adj = -corr * 0.5
        sim.loc[mask, "sim_over_prob_closing"]  = np.clip(
            sim.loc[mask, "sim_over_prob_closing"]  + adj, 0, 1)
        sim.loc[mask, "sim_under_prob_closing"] = np.clip(
            sim.loc[mask, "sim_under_prob_closing"] + adj, 0, 1)
        sim.loc[mask, "sim_push_prob_closing"]  = np.clip(
            sim.loc[mask, "sim_push_prob_closing"]  - 2 * adj, 0, 1)

    # Verify sum still ≈ 1
    mkt = sim[sim["market_available"].astype(bool)].copy()
    sum_check = (mkt["sim_over_prob_closing"] +
                 mkt["sim_under_prob_closing"] +
                 mkt["sim_push_prob_closing"])
    max_err = float((sum_check - 1.0).abs().max())
    dlog(f"\n  Post-correction probability sum check (max |err|): {max_err:.2e}  "
         f"{'PASS' if max_err < 0.01 else 'FAIL'}")

    # Re-report 3D for validate after correction
    dlog()
    dlog("  Updated 3D after push correction (validate):")
    val_mkt = sim[(sim["split"] == "validate") &
                  sim["market_available"].astype(bool) &
                  sim["closing_total"].notna()]
    for bkt in ["5.5", "6.0", "6.5"]:
        grp = val_mkt[val_mkt["closing_total_bucket"] == bkt]
        if len(grp) == 0:
            continue
        line_val = float(bkt)
        sim_over = grp["sim_over_prob_closing"].mean()
        act_over = (grp["total_goals"] > line_val).mean()
        sim_push = grp["sim_push_prob_closing"].mean()
        act_push = (grp["total_goals"] == line_val).mean()
        tag_o = "PASS" if abs(sim_over - act_over) <= 0.03 else "FAIL"
        dlog(f"  Bucket {bkt} (n={len(grp)}):  "
             f"sim_over={sim_over:.4f}  act_over={act_over:.4f}  "
             f"diff={sim_over-act_over:+.4f}  {tag_o}")
        if bkt == "6.0":
            tag_push = "PASS" if abs(sim_push - act_push) <= 0.03 else "FAIL"
            dlog(f"    sim_push={sim_push:.4f}  act_push={act_push:.4f}  "
                 f"diff={sim_push-act_push:+.4f}  {tag_push}")

    return sim, lines

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    log("=" * 68)
    log("NHL Phase 4.5: Calibration Repair")
    log("=" * 68)

    ft    = pd.read_parquet(FEATURE_TABLE)
    canon = pd.read_csv(CANONICAL_CSV, usecols=["game_id", "over_price", "under_price"])
    with open(HOME_PKL, "rb") as f: hpkg = pickle.load(f)
    with open(AWAY_PKL, "rb") as f: apkg = pickle.load(f)

    # Step 1
    ft2, val_drift, oos_ok = compute_dynamic_calibration(ft, hpkg, apkg)
    if not oos_ok:
        log("\nHALTING: OOS mean drift gate failed. See audit above.")
        with open(AUDIT_FILE, "w") as f:
            f.write("\n".join(_lines))
        return

    # Step 2
    sim = run_simulation(ft2, canon)
    sim = compute_volatility(sim)

    # Edges (needed for diagnostics 3F and threshold step)
    sim = compute_edges(sim)

    # Step 3 — Diagnostics
    diag_lines = run_diagnostics(sim)

    # Step 4 — Empirical threshold
    threshold, thresh_lines = build_edge_threshold(sim)

    # Step 5 — Push correction
    sim, push_lines = assess_push_correction(sim)

    # Re-run edges after push correction (sim_over/under may have changed)
    sim = compute_edges(sim)

    # Apply provisional threshold to qualified_signal
    val_sentinel = threshold < 99.0
    sim["empirical_threshold"] = threshold if val_sentinel else np.nan
    sim["qualified_signal"] = 0
    if val_sentinel:
        for side_col in ["edge_over", "edge_under"]:
            sim.loc[sim[side_col] >= threshold, "qualified_signal"] = 1

    # Save outputs
    log()
    log("=" * 68)
    log("STEP 6 — SAVING OUTPUTS")
    log("=" * 68)

    out_cols = [
        "game_id", "game_date", "home_team", "away_team", "season_year",
        "lambda_home_calibrated", "lambda_away_calibrated", "lambda_total_calibrated",
        "seasonal_drift",
        "sim_over_prob_closing", "sim_under_prob_closing", "sim_push_prob_closing",
        "closing_total", "closing_total_bucket",
        "edge_over", "edge_under",
        "volatility_score", "volatility_bucket",
        "empirical_threshold", "qualified_signal",
        "total_goals",
        "home_score", "away_score",
        "market_available",
        "split",
    ]
    sim[out_cols].to_parquet(SIM_OUT, index=False)
    log(f"  Saved: {SIM_OUT}  ({len(sim):,} rows)")

    with open(AUDIT_FILE, "w") as f:
        f.write("\n".join(_lines))
    log(f"  Saved: {AUDIT_FILE}")

    log()
    log("Phase 4.5 complete.")


if __name__ == "__main__":
    main()
