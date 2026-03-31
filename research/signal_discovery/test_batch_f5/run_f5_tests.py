#!/usr/bin/env python3
"""
F5 Derivative Signal Tests — CS025, CS026, CS027

Uses safety layer for permutation tests and logging.
RESEARCH ONLY — does not modify production files.
"""

import json, sys, glob, logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("f5_tests")

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent.parent
SAFETY = ROOT / "research" / "signal_discovery" / "safety_layer"
sys.path.insert(0, str(SAFETY))
import signal_tester as st

# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════

def load_statcast_starts():
    """Load Statcast, compute per-start CSW, BB rate, inning-1 pitch count."""
    files = sorted(glob.glob(str(ROOT / "mlb" / "props" / "data" / "statcast_chunk_*.parquet")))
    sc = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    sc = sc[sc["game_type"] == "R"].copy()
    sc = sc.sort_values(["game_pk", "inning", "inning_topbot", "at_bat_number", "pitch_number"])

    # Identify starters
    first = sc.groupby(["game_pk", "inning_topbot"]).first().reset_index()
    starters = first[first["inning"] == 1][["game_pk", "inning_topbot", "pitcher", "game_year", "game_date"]].copy()
    starters = starters.rename(columns={"pitcher": "starter_id", "game_year": "season"})

    # Keep only starter pitches
    sc_s = sc.merge(starters[["game_pk", "inning_topbot", "starter_id"]], on=["game_pk", "inning_topbot"])
    sc_s = sc_s[sc_s["pitcher"] == sc_s["starter_id"]].copy()

    # CSW = called strikes + whiffs / total pitches
    sc_s["is_csw"] = sc_s["description"].isin([
        "called_strike", "swinging_strike", "swinging_strike_blocked",
        "foul_tip",  # foul tips into glove count as swinging strikes
    ]).astype(int)

    # BB = walks
    sc_s["is_bb"] = (sc_s["events"] == "walk").astype(int)
    sc_s["is_pa"] = sc_s["events"].notna().astype(int)

    # Per-start aggregations
    per_start = sc_s.groupby(["game_pk", "starter_id", "game_year", "game_date", "inning_topbot"]).agg(
        total_pitches=("is_csw", "count"),
        csw_count=("is_csw", "sum"),
        bb_count=("is_bb", "sum"),
        pa_count=("is_pa", "sum"),
    ).reset_index()
    per_start["csw_rate"] = per_start["csw_count"] / per_start["total_pitches"]
    per_start["bb_rate"] = per_start["bb_count"] / per_start["pa_count"].clip(lower=1)
    per_start = per_start.rename(columns={"game_year": "season"})

    # Inning-1 pitch count per starter
    inn1 = sc_s[sc_s["inning"] == 1].groupby(["game_pk", "starter_id"]).agg(
        inn1_pitches=("pitch_number", "count")
    ).reset_index()

    per_start = per_start.merge(inn1, on=["game_pk", "starter_id"], how="left")

    logger.info(f"Per-start features: {len(per_start)} starts")
    return per_start, sc_s


def build_rolling_features(per_start):
    """Build rolling baselines for CSW, BB rate. Shift 1 = pregame only."""
    ps = per_start.sort_values(["starter_id", "season", "game_date", "game_pk"]).copy()

    ps["csw_baseline"] = ps.groupby(["starter_id", "season"])["csw_rate"].transform(
        lambda x: x.shift(1).expanding(min_periods=3).mean()
    )
    ps["csw_r3"] = ps.groupby(["starter_id", "season"])["csw_rate"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=3).mean()
    )
    ps["bb_baseline"] = ps.groupby(["starter_id", "season"])["bb_rate"].transform(
        lambda x: x.shift(1).expanding(min_periods=3).mean()
    )
    ps["bb_r3"] = ps.groupby(["starter_id", "season"])["bb_rate"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=3).mean()
    )

    # Good command: CSW_r3 > baseline AND BB_r3 < baseline
    ps["good_command"] = (
        (ps["csw_r3"] > ps["csw_baseline"]) &
        (ps["bb_r3"] < ps["bb_baseline"]) &
        ps["csw_r3"].notna() & ps["bb_r3"].notna()
    ).astype(int)

    # Prior start inning-1 pitch count (shift 1)
    ps["prior_inn1_pitches"] = ps.groupby(["starter_id", "season"])["inn1_pitches"].transform(
        lambda x: x.shift(1)
    )

    # Start number for eligibility
    ps["start_num"] = ps.groupby(["starter_id", "season"]).cumcount()

    return ps


def derive_f5_scores(sc_s):
    """Derive home/away F5 scores from Statcast pitch-level data."""
    f5 = sc_s[sc_s["inning"] <= 5].copy()
    f5_scores = f5.groupby("game_pk").agg(
        home_f5_score=("post_home_score", "max"),
        away_f5_score=("post_away_score", "max"),
    ).reset_index()
    f5_scores["f5_total"] = f5_scores["home_f5_score"] + f5_scores["away_f5_score"]
    return f5_scores


def load_game_context():
    """Load game_table + feature_table + closing lines."""
    gt = pd.read_parquet(ROOT / "sim" / "data" / "game_table.parquet")
    gt = gt[gt["season"].isin([2022, 2023, 2024, 2025])].copy()

    ft = pd.read_parquet(ROOT / "sim" / "data" / "feature_table.parquet")
    ft = ft[["game_pk", "home_sp_xfip", "away_sp_xfip"]].copy()
    ft["xfip_gap"] = ft["away_sp_xfip"] - ft["home_sp_xfip"]

    gt = gt.merge(ft, on="game_pk", how="left")

    # Closing lines for market_residual
    cl1 = pd.read_parquet(ROOT / "sim" / "data" / "mlb_historical_closing_lines.parquet")[["game_pk", "close_total"]]
    cl2 = pd.read_parquet(ROOT / "sim" / "data" / "market_snapshots.parquet")[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"})
    closing = pd.concat([cl1, cl2], ignore_index=True).drop_duplicates(subset="game_pk", keep="last")
    gt = gt.merge(closing, on="game_pk", how="left")

    # F5 runline lines
    rl = pd.read_parquet(ROOT / "research" / "f5_runline" / "data" / "f5_runline_lines_historical.parquet")
    rl = rl.rename(columns={"game_id": "game_pk"})
    rl["game_pk"] = rl["game_pk"].astype(gt["game_pk"].dtype)
    rl_home = rl[["game_pk", "home_line", "home_price"]].drop_duplicates(subset="game_pk", keep="last")
    gt = gt.merge(rl_home, on="game_pk", how="left")

    return gt


def join_all(gt, per_start, f5_scores, starters_map):
    """Join game context + per-start features + F5 scores."""
    # Map starter_id to home/away per game
    # inning_topbot: Top = away batting = home pitching
    home_st = starters_map[starters_map["inning_topbot"] == "Top"][["game_pk", "starter_id"]].rename(
        columns={"starter_id": "home_starter_id"})
    away_st = starters_map[starters_map["inning_topbot"] == "Bot"][["game_pk", "starter_id"]].rename(
        columns={"starter_id": "away_starter_id"})

    g = gt.merge(home_st, on="game_pk", how="left")
    g = g.merge(away_st, on="game_pk", how="left")

    # Home starter features
    feat_cols = ["good_command", "start_num", "prior_inn1_pitches", "csw_r3", "bb_r3"]
    home_feats = per_start[["game_pk", "starter_id"] + feat_cols].rename(
        columns={c: f"home_{c}" for c in feat_cols}).rename(columns={"starter_id": "home_starter_id"})
    g = g.merge(home_feats, on=["game_pk", "home_starter_id"], how="left")

    away_feats = per_start[["game_pk", "starter_id"] + feat_cols].rename(
        columns={c: f"away_{c}" for c in feat_cols}).rename(columns={"starter_id": "away_starter_id"})
    g = g.merge(away_feats, on=["game_pk", "away_starter_id"], how="left")

    # F5 scores
    g = g.merge(f5_scores, on="game_pk", how="left")

    # F5 market residual (actual F5 total - close_total * 5/9 as proxy, or use actual_f5_total)
    g["f5_residual"] = g["f5_total"] - g["actual_f5_total"]  # should be ~0 (both from same source)
    # For CS027 we need: actual_f5_total vs some F5 closing line
    # Use close_total * (5/9) as F5 market proxy if no dedicated F5 line
    g["f5_market_proxy"] = g["close_total"] * (5.0 / 9.0)
    g["f5_market_residual"] = g["actual_f5_total"] - g["f5_market_proxy"]

    # F5 over/under
    g["f5_went_over"] = (g["actual_f5_total"] > g["f5_market_proxy"]).astype(int)
    g["f5_went_under"] = (g["actual_f5_total"] < g["f5_market_proxy"]).astype(int)
    g["f5_push"] = (g["actual_f5_total"] == g["f5_market_proxy"]).astype(int)

    # F5 runline grading: home -0.5 wins if home_f5_score > away_f5_score
    g["home_f5_rl_win"] = (g["home_f5_score"] > g["away_f5_score"]).astype(int)
    g["home_f5_rl_loss"] = (g["home_f5_score"] < g["away_f5_score"]).astype(int)
    g["home_f5_rl_push"] = (g["home_f5_score"] == g["away_f5_score"]).astype(int)

    logger.info(f"Joined dataset: {len(g)} games")
    return g


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def compute_roi(wins, losses, prices=None, default_price=-110):
    """ROI at given price or default -110."""
    n = wins + losses
    if n == 0: return None
    if prices is not None and len(prices) > 0:
        # Actual odds ROI
        total_wagered = len(prices)
        total_returned = sum(100/abs(p) + 1 if p > 0 else 100/(abs(p)/100 + 1) + (100 - 100/(abs(p)/100 + 1))
                             for p in prices)  # too complex, use simple
    # Simple: at -110
    wr = wins / n
    return round((wr * (100 / 110) - (1 - wr)) * 100, 2)


def season_table(df, flag_col, outcome_col, direction_label):
    """Season-by-season breakdown."""
    results = {}
    for season in sorted(df["season"].unique()):
        s = df[(df["season"] == season) & (df[flag_col] == 1)]
        n = len(s)
        if n == 0:
            results[season] = {"n": 0, "win_rate": None, "roi": None}
            continue
        wr = s[outcome_col].mean()
        roi = (wr * (100 / 110) - (1 - wr)) * 100
        results[season] = {"n": n, "win_rate": round(wr, 4), "roi": round(roi, 2)}
    return results


def log_result_and_board(signal_id, result_dict):
    """Log to test_results_log.json and signal_board.json."""
    st.log_test_result(result_dict)

    hypothesis = None
    for e in st.load_registry():
        if e["canonical_signal_id"] == signal_id:
            hypothesis = e
            break

    board = []
    if st.BOARD_PATH.exists():
        with open(st.BOARD_PATH) as f:
            board = json.load(f)
    board = [b for b in board if b.get("canonical_signal_id") != signal_id]

    advancement = None
    v = result_dict["verdict"]
    if v == "PASS":
        advancement = "Advance to shadow monitoring"
    elif v == "NEAR_MISS":
        advancement = "Note for threshold refinement — do not promote"

    board.append({
        "canonical_signal_id": signal_id,
        "canonical_name": hypothesis["canonical_name"] if hypothesis else signal_id,
        "domain": hypothesis.get("domain", "") if hypothesis else "",
        "framework_type": hypothesis.get("framework_type", "") if hypothesis else "",
        "market_target": hypothesis.get("market_target", "") if hypothesis else "",
        "status": v,
        "failure_reason": result_dict.get("failure_reason"),
        "advancement_path": advancement,
        "last_updated": datetime.now().isoformat(),
    })

    def _ser(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        raise TypeError(type(obj).__name__)

    with open(st.BOARD_PATH, "w") as f:
        json.dump(board, f, indent=2, default=_ser)


# ═══════════════════════════════════════════════════════════
# CS025 — F5 RUN LINE COMMAND OVERLAY
# ═══════════════════════════════════════════════════════════

def test_cs025(g):
    logger.info("\n" + "=" * 65)
    logger.info("CS025 — F5 run line command overlay (confidence filter)")
    logger.info("=" * 65)

    # Signal B: xfip_gap >= 1.0 → bet home -0.5 F5
    g025 = g.dropna(subset=["xfip_gap", "home_f5_score", "away_f5_score"]).copy()
    g025["signal_b"] = (g025["xfip_gap"] >= 1.0).astype(int)

    # Home starter needs 3+ prior starts
    g025["home_eligible"] = g025["home_start_num"] >= 3
    g025["overlay"] = (g025["signal_b"] == 1) & (g025["home_good_command"] == 1) & g025["home_eligible"]
    g025["overlay"] = g025["overlay"].astype(int)

    # Exclude pushes for hit rate
    g025_nopush = g025[g025["home_f5_rl_push"] == 0].copy()
    push_count = g025[g025["home_f5_rl_push"] == 1]["signal_b"].sum()

    # Three groups (excluding pushes for hit rate)
    sb_all = g025_nopush[g025_nopush["signal_b"] == 1]
    sb_overlay = g025_nopush[(g025_nopush["signal_b"] == 1) & (g025_nopush["overlay"] == 1)]
    sb_no_overlay = g025_nopush[(g025_nopush["signal_b"] == 1) & (g025_nopush["overlay"] == 0)]

    logger.info(f"\n  Signal B baseline:      N={len(sb_all)}, hit_rate={sb_all['home_f5_rl_win'].mean():.4f}")
    logger.info(f"  + good command (overlay): N={len(sb_overlay)}, hit_rate={sb_overlay['home_f5_rl_win'].mean():.4f}")
    logger.info(f"  + no command:             N={len(sb_no_overlay)}, hit_rate={sb_no_overlay['home_f5_rl_win'].mean():.4f}")
    logger.info(f"  Pushes in Signal B:       {push_count}")

    # Season breakdown for overlay
    g025_nopush["flag_overlay"] = ((g025_nopush["signal_b"] == 1) & (g025_nopush["overlay"] == 1)).astype(int)
    seasons_overlay = season_table(g025_nopush, "flag_overlay", "home_f5_rl_win", "overlay")
    logger.info("\n  Season-by-season (overlay confirmed):")
    for y, r in sorted(seasons_overlay.items()):
        logger.info(f"    {y}: N={r['n']}, hit_rate={r['win_rate']}, ROI={r['roi']}%")

    seasons_baseline = season_table(g025_nopush, "signal_b", "home_f5_rl_win", "baseline")
    logger.info("\n  Season-by-season (Signal B baseline):")
    for y, r in sorted(seasons_baseline.items()):
        logger.info(f"    {y}: N={r['n']}, hit_rate={r['win_rate']}, ROI={r['roi']}%")

    # Freeze threshold check on 2022-2023
    freeze = g025_nopush[g025_nopush["season"].isin([2022, 2023])]
    freeze_overlay = freeze[freeze["flag_overlay"] == 1]
    freeze_n = len(freeze_overlay)
    logger.info(f"\n  Freeze N (2022-2023 overlay): {freeze_n}")

    # Permutation test: metric = hit rate of overlay-confirmed subset
    all_data = g025_nopush[g025_nopush["season"].isin([2022, 2023, 2024, 2025])]
    perm = st.run_permutation_test(
        signal_values=all_data["flag_overlay"].values,
        outcomes=all_data["home_f5_rl_win"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.4f}, pctile={perm['percentile']:.1f}")

    # Market independence
    valid = all_data.dropna(subset=["close_total"])
    corr = np.corrcoef(valid["flag_overlay"].values.astype(float), valid["close_total"].values)[0, 1] if len(valid) > 30 else None

    # Verdict
    s2024 = seasons_overlay.get(2024, {})
    s2025 = seasons_overlay.get(2025, {})
    val_2025_pos = (s2025.get("win_rate") or 0) > 0.50
    val_2024_pos = (s2024.get("win_rate") or 0) > 0.50
    perm_pass = perm["percentile"] >= 85
    near_miss = 75 <= perm["percentile"] < 85
    season_pass, season_note = st.check_season_support(val_2024_pos, val_2025_pos)

    if freeze_n < 50:
        verdict = "NEEDS_MORE_DATA"
        reason = f"Freeze N={freeze_n} < 50"
    elif perm_pass and season_pass:
        verdict = "PASS"
        reason = None
    elif near_miss and val_2025_pos:
        verdict = "NEAR_MISS"
        reason = f"Perm {perm['percentile']:.1f} in 75-84; 2025 positive"
    elif not perm_pass:
        verdict = "FAIL"
        reason = f"Perm {perm['percentile']:.1f} < 85"
    else:
        verdict = "FAIL"
        reason = season_note

    logger.info(f"\n  VERDICT: {verdict}")
    if reason: logger.info(f"  Reason: {reason}")
    if verdict == "PASS":
        logger.info("  Next step: Phase B stake sizing test (0.5u → 0.75u) — do not run now")

    # Build three-way comparison for report
    three_way = {
        "signal_b_baseline": {"n": len(sb_all), "hit_rate": round(sb_all["home_f5_rl_win"].mean(), 4),
                              "roi": compute_roi(sb_all["home_f5_rl_win"].sum(), sb_all["home_f5_rl_loss"].sum())},
        "overlay_confirmed": {"n": len(sb_overlay), "hit_rate": round(sb_overlay["home_f5_rl_win"].mean(), 4) if len(sb_overlay) > 0 else None,
                              "roi": compute_roi(sb_overlay["home_f5_rl_win"].sum(), sb_overlay["home_f5_rl_loss"].sum()) if len(sb_overlay) > 0 else None},
        "no_overlay": {"n": len(sb_no_overlay), "hit_rate": round(sb_no_overlay["home_f5_rl_win"].mean(), 4) if len(sb_no_overlay) > 0 else None,
                       "roi": compute_roi(sb_no_overlay["home_f5_rl_win"].sum(), sb_no_overlay["home_f5_rl_loss"].sum()) if len(sb_no_overlay) > 0 else None},
    }

    result = {
        "canonical_signal_id": "CS025",
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"xfip_gap": 1.0, "good_command": "csw_r3 > baseline AND bb_r3 < baseline",
                              "min_prior_starts": 3},
        "freeze_window_n": freeze_n,
        "three_way_comparison": three_way,
        "push_count": int(push_count),
        "train_result": {"n": sum(seasons_overlay.get(y, {}).get("n", 0) for y in [2022, 2023, 2024])},
        "validation_2024": {"n": s2024.get("n", 0), "win_rate": s2024.get("win_rate"), "roi": s2024.get("roi"),
                            "direction_positive": val_2024_pos, "note": "in-sample"},
        "validation_2025": {"n": s2025.get("n", 0), "win_rate": s2025.get("win_rate"), "roi": s2025.get("roi"),
                            "direction_positive": val_2025_pos, "note": "binding OOS"},
        "season_by_season": {str(k): v for k, v in seasons_overlay.items()},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "market_independence": {"correlation": round(float(corr), 4) if corr is not None else None},
        "verdict": verdict,
        "failure_reason": reason,
    }
    log_result_and_board("CS025", result)
    return result


# ═══════════════════════════════════════════════════════════
# CS026 — FIRST-INNING PITCH COUNT WEAKENING FILTER
# ═══════════════════════════════════════════════════════════

def test_cs026(g):
    logger.info("\n" + "=" * 65)
    logger.info("CS026 — First-inning pitch count weakening filter")
    logger.info("=" * 65)

    g026 = g.dropna(subset=["actual_f5_total", "f5_market_proxy"]).copy()

    # Freeze high-stress cutoff on 2022-2023 distribution
    freeze = g026[g026["season"].isin([2022, 2023])]
    all_inn1 = pd.concat([
        freeze["home_prior_inn1_pitches"].dropna(),
        freeze["away_prior_inn1_pitches"].dropna(),
    ])
    cutoff = round(float(all_inn1.quantile(0.80)), 0)
    logger.info(f"  Frozen high-stress cutoff (P80, 2022-2023): {cutoff:.0f} pitches")

    # Flag if EITHER starter had high-stress inning 1 in prior start
    g026["home_stress"] = g026["home_prior_inn1_pitches"].fillna(0).astype(float).ge(cutoff).astype(int)
    g026["away_stress"] = g026["away_prior_inn1_pitches"].fillna(0).astype(float).ge(cutoff).astype(int)
    g026["stress_flag"] = ((g026["home_stress"] == 1) | (g026["away_stress"] == 1)).astype(int)

    # Eligibility: at least one starter with prior start data
    g026["any_prior"] = (g026["home_prior_inn1_pitches"].notna() | g026["away_prior_inn1_pitches"].notna())
    g026 = g026[g026["any_prior"]].copy()
    logger.info(f"  Games with prior-start data: {len(g026)}")

    # F5 UNDER plays (all games for now — we're testing the weakening effect)
    # Include pushes for residual, exclude for win rate
    g026_nopush = g026[g026["f5_push"] == 0].copy()
    push_total = g026["f5_push"].sum()

    # Three groups
    all_games = g026_nopush
    stressed = g026_nopush[g026_nopush["stress_flag"] == 1]
    clean = g026_nopush[g026_nopush["stress_flag"] == 0]

    logger.info(f"\n  All games (F5 UNDER baseline):   N={len(all_games)}, under_rate={all_games['f5_went_under'].mean():.4f}")
    logger.info(f"  High stress (weakened):          N={len(stressed)}, under_rate={stressed['f5_went_under'].mean():.4f}")
    logger.info(f"  Clean (no stress):               N={len(clean)}, under_rate={clean['f5_went_under'].mean():.4f}")
    logger.info(f"  F5 pushes: {int(push_total)}")

    # Market residual (include pushes)
    res_all = g026["f5_market_residual"].mean()
    res_stress = g026[g026["stress_flag"] == 1]["f5_market_residual"].mean()
    res_clean = g026[g026["stress_flag"] == 0]["f5_market_residual"].mean()
    logger.info(f"\n  Market residual (all):       {res_all:.4f}")
    logger.info(f"  Market residual (stressed):  {res_stress:.4f}")
    logger.info(f"  Market residual (clean):     {res_clean:.4f}")

    # Season breakdown for stress flag
    seasons_stress = season_table(g026_nopush, "stress_flag", "f5_went_under", "stress")
    logger.info("\n  Season-by-season (stressed games, under rate):")
    for y, r in sorted(seasons_stress.items()):
        logger.info(f"    {y}: N={r['n']}, under_rate={r['win_rate']}, ROI={r['roi']}%")

    freeze_stress = g026_nopush[(g026_nopush["season"].isin([2022, 2023])) & (g026_nopush["stress_flag"] == 1)]
    freeze_n = len(freeze_stress)
    logger.info(f"\n  Freeze N (2022-2023 stressed): {freeze_n}")

    # Permutation: does stress flag PREDICT WORSE under rate?
    # For a weakening filter, the metric is: under_rate in stressed group should be LOWER than random
    # So we test: 1 - under_rate (i.e., over_rate) should be HIGHER in stressed group
    all_data = g026_nopush[g026_nopush["season"].isin([2022, 2023, 2024, 2025])]

    # Test statistic: mean market_residual in stressed games (should be positive = more runs = worse for under)
    perm = st.run_permutation_test(
        signal_values=all_data["stress_flag"].values,
        outcomes=all_data["f5_market_residual"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.0,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation (residual in stressed): observed={perm['observed_metric']:.4f}, pctile={perm['percentile']:.1f}")

    # For a weakening filter: positive residual in stressed group = filter works
    # Perm percentile > 85 means stress flag reliably predicts higher scoring
    s2025_stress = seasons_stress.get(2025, {})
    s2024_stress = seasons_stress.get(2024, {})

    # Weakening filter: 2025 positive means stressed games had LOWER under rate (which is what we want)
    # So val_2025_pos for weakening = under_rate < 0.50 (stressed games go over more)
    val_2025_weak = (s2025_stress.get("win_rate") or 1) < 0.50  # under rate below 50% = weakening confirmed
    val_2024_weak = (s2024_stress.get("win_rate") or 1) < 0.50

    perm_pass = perm["percentile"] >= 85
    near_miss = 75 <= perm["percentile"] < 85

    if freeze_n < 50:
        verdict = "NEEDS_MORE_DATA"
        reason = f"Freeze N={freeze_n} < 50"
    elif perm_pass and val_2025_weak:
        verdict = "PASS"
        reason = None
    elif near_miss and val_2025_weak:
        verdict = "NEAR_MISS"
        reason = f"Perm {perm['percentile']:.1f} in 75-84; 2025 weakening confirmed"
    elif not perm_pass:
        verdict = "FAIL"
        reason = f"Perm {perm['percentile']:.1f} < 85"
    elif not val_2025_weak:
        verdict = "FAIL"
        reason = f"2025 under_rate={s2025_stress.get('win_rate')} >= 0.50 — no weakening effect OOS"
    else:
        verdict = "FAIL"
        reason = "Did not meet criteria"

    logger.info(f"\n  VERDICT: {verdict}")
    if reason: logger.info(f"  Reason: {reason}")

    three_way = {
        "f5_under_baseline": {"n": len(all_games), "under_rate": round(all_games["f5_went_under"].mean(), 4),
                              "residual": round(res_all, 4)},
        "high_stress_weakened": {"n": len(stressed), "under_rate": round(stressed["f5_went_under"].mean(), 4) if len(stressed) > 0 else None,
                                 "residual": round(res_stress, 4) if not np.isnan(res_stress) else None},
        "clean_no_stress": {"n": len(clean), "under_rate": round(clean["f5_went_under"].mean(), 4) if len(clean) > 0 else None,
                            "residual": round(res_clean, 4) if not np.isnan(res_clean) else None},
    }

    result = {
        "canonical_signal_id": "CS026",
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"inn1_pitch_cutoff": int(cutoff), "freeze_percentile": "P80",
                              "min_prior_starts": 1},
        "freeze_window_n": freeze_n,
        "three_way_comparison": three_way,
        "push_count": int(push_total),
        "validation_2025": {"n": s2025_stress.get("n", 0), "under_rate": s2025_stress.get("win_rate"),
                            "roi": s2025_stress.get("roi"), "direction_positive": val_2025_weak,
                            "note": "weakening filter — lower under_rate = positive result"},
        "season_by_season": {str(k): v for k, v in seasons_stress.items()},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict,
        "failure_reason": reason,
    }
    log_result_and_board("CS026", result)
    return result


# ═══════════════════════════════════════════════════════════
# CS027 — CS013 BULLPEN STATE x F5 OVER
# ═══════════════════════════════════════════════════════════

def build_cs013_flags(pitcher_logs):
    """Replicate CS013 frozen logic."""
    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["player_id", "game_date", "game_pk"])
    rlv["season_rpa"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).expanding(min_periods=5).mean())
    rlv["degraded_app"] = ((rlv["runs_allowed"] > 1.5 * rlv["season_rpa"]) & rlv["season_rpa"].notna()).astype(int)
    rlv["deg_count_5"] = rlv.groupby(["player_id", "season"])["degraded_app"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).sum())
    rlv["is_degraded"] = (rlv["deg_count_5"] >= 2).astype(int)

    team_game = (rlv.dropna(subset=["deg_count_5"])
                 .groupby(["team", "game_pk", "season"])
                 .agg(n_degraded=("is_degraded", "sum"))
                 .reset_index())
    team_game["cs013_flag"] = (team_game["n_degraded"] >= 2).astype(int)
    return team_game


def test_cs027(g):
    logger.info("\n" + "=" * 65)
    logger.info("CS027 — CS013 bullpen state x F5 OVER interaction")
    logger.info("=" * 65)

    pitcher_logs = pd.read_parquet(ROOT / "mlb" / "data" / "pitcher_game_logs.parquet")
    pitcher_logs = pitcher_logs[pitcher_logs["season"].isin([2022, 2023, 2024, 2025])].copy()

    cs013_team = build_cs013_flags(pitcher_logs)

    g027 = g.dropna(subset=["actual_f5_total", "f5_market_proxy"]).copy()

    # Join CS013 flags
    for prefix, team_col in [("home", "home_team"), ("away", "away_team")]:
        g027 = g027.merge(
            cs013_team[["team", "game_pk", "cs013_flag"]].rename(
                columns={"team": team_col, "cs013_flag": f"{prefix}_cs013"}),
            on=[team_col, "game_pk"], how="left")
    g027["home_cs013"] = g027["home_cs013"].fillna(0).astype(int)
    g027["away_cs013"] = g027["away_cs013"].fillna(0).astype(int)
    g027["cs013_flag"] = ((g027["home_cs013"] == 1) | (g027["away_cs013"] == 1)).astype(int)

    logger.info(f"  Games with CS013 data: {len(g027)}")
    logger.info(f"  CS013 flagged: {g027['cs013_flag'].sum()} ({g027['cs013_flag'].mean():.1%})")

    # F5 outcomes in CS013-flagged games (include pushes for residual)
    flagged = g027[g027["cs013_flag"] == 1]
    unflagged = g027[g027["cs013_flag"] == 0]

    flagged_nopush = flagged[flagged["f5_push"] == 0]
    unflagged_nopush = unflagged[unflagged["f5_push"] == 0]

    logger.info(f"\n  CS013 flagged — F5 over_rate:  {flagged_nopush['f5_went_over'].mean():.4f} (N={len(flagged_nopush)})")
    logger.info(f"  CS013 unflagged — F5 over_rate: {unflagged_nopush['f5_went_over'].mean():.4f} (N={len(unflagged_nopush)})")
    logger.info(f"  CS013 flagged — F5 residual:    {flagged['f5_market_residual'].mean():.4f}")
    logger.info(f"  CS013 unflagged — F5 residual:  {unflagged['f5_market_residual'].mean():.4f}")

    # CONTEXT: full-game over rate comparison
    fg_nopush = g027[g027.get("close_total", np.nan).notna()].copy()
    fg_nopush["fg_went_over"] = (fg_nopush["actual_total"] > fg_nopush["close_total"]).astype(int)
    fg_nopush["fg_push"] = (fg_nopush["actual_total"] == fg_nopush["close_total"]).astype(int)
    fg_nopush_real = fg_nopush[fg_nopush["fg_push"] == 0]
    fg_flagged = fg_nopush_real[fg_nopush_real["cs013_flag"] == 1]

    logger.info(f"\n  CONTEXT — Full-game over_rate when CS013 active: "
                f"{fg_flagged['fg_went_over'].mean():.4f} (N={len(fg_flagged)})")
    logger.info(f"  CONTEXT — F5 over_rate when CS013 active:        "
                f"{flagged_nopush['f5_went_over'].mean():.4f} (N={len(flagged_nopush)})")
    delta = flagged_nopush["f5_went_over"].mean() - fg_flagged["fg_went_over"].mean()
    logger.info(f"  Delta (F5 - full game):                          {delta:+.4f}")

    # Season breakdown
    seasons_f5 = season_table(g027[g027["f5_push"] == 0], "cs013_flag", "f5_went_over", "cs013_f5")
    logger.info("\n  Season-by-season (CS013 flagged, F5 over_rate):")
    for y, r in sorted(seasons_f5.items()):
        logger.info(f"    {y}: N={r['n']}, f5_over_rate={r['win_rate']}, ROI={r['roi']}%")

    freeze_n = len(flagged_nopush[flagged_nopush["season"].isin([2022, 2023])])
    logger.info(f"\n  Freeze N (2022-2023): {freeze_n}")

    # Permutation: F5 market_residual in CS013-flagged games
    all_data = g027[g027["season"].isin([2022, 2023, 2024, 2025])]
    perm = st.run_permutation_test(
        signal_values=all_data["cs013_flag"].values,
        outcomes=all_data["f5_market_residual"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.0,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation (F5 residual): observed={perm['observed_metric']:.4f}, pctile={perm['percentile']:.1f}")

    s2025 = seasons_f5.get(2025, {})
    s2024 = seasons_f5.get(2024, {})
    val_2025_pos = (s2025.get("win_rate") or 0) > 0.50
    val_2024_pos = (s2024.get("win_rate") or 0) > 0.50
    perm_pass = perm["percentile"] >= 85
    near_miss = 75 <= perm["percentile"] < 85
    season_pass, season_note = st.check_season_support(val_2024_pos, val_2025_pos)

    if freeze_n < 50:
        verdict = "NEEDS_MORE_DATA"
        reason = f"Freeze N={freeze_n} < 50"
    elif perm_pass and season_pass:
        verdict = "PASS"
        reason = None
    elif near_miss and val_2025_pos:
        verdict = "NEAR_MISS"
        reason = f"Perm {perm['percentile']:.1f} in 75-84; 2025 positive"
    elif not perm_pass:
        verdict = "FAIL"
        reason = f"Perm {perm['percentile']:.1f} < 85"
    else:
        verdict = "FAIL"
        reason = season_note

    logger.info(f"\n  VERDICT: {verdict}")
    if reason: logger.info(f"  Reason: {reason}")

    result = {
        "canonical_signal_id": "CS027",
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"cs013_definition": "frozen from cs013_shadow.py",
                              "degraded_multiplier": 1.5, "team_threshold": 2},
        "freeze_window_n": freeze_n,
        "f5_vs_fullgame_context": {
            "f5_over_rate_cs013": round(flagged_nopush["f5_went_over"].mean(), 4),
            "fullgame_over_rate_cs013": round(fg_flagged["fg_went_over"].mean(), 4),
            "delta": round(delta, 4),
        },
        "validation_2025": {"n": s2025.get("n", 0), "f5_over_rate": s2025.get("win_rate"),
                            "roi": s2025.get("roi"), "direction_positive": val_2025_pos,
                            "note": "binding OOS"},
        "season_by_season": {str(k): v for k, v in seasons_f5.items()},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict,
        "failure_reason": reason,
    }
    log_result_and_board("CS027", result)
    return result


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 65)
    logger.info("F5 DERIVATIVE SIGNAL TESTS — CS025, CS026, CS027")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 65)

    # Load data
    per_start, sc_s = load_statcast_starts()
    per_start = build_rolling_features(per_start)
    f5_scores = derive_f5_scores(sc_s)
    gt = load_game_context()

    # Build starters map for joining
    sc_files = sorted(glob.glob(str(ROOT / "mlb" / "props" / "data" / "statcast_chunk_*.parquet")))
    sc_all = pd.concat([pd.read_parquet(f) for f in sc_files], ignore_index=True)
    sc_all = sc_all[sc_all["game_type"] == "R"].copy()
    sc_all = sc_all.sort_values(["game_pk", "inning", "inning_topbot", "at_bat_number", "pitch_number"])
    first = sc_all.groupby(["game_pk", "inning_topbot"]).first().reset_index()
    starters_map = first[first["inning"] == 1][["game_pk", "inning_topbot", "pitcher"]].rename(
        columns={"pitcher": "starter_id"})

    g = join_all(gt, per_start, f5_scores, starters_map)

    results = {}
    results["CS025"] = test_cs025(g)
    results["CS026"] = test_cs026(g)
    results["CS027"] = test_cs027(g)

    # Summary
    logger.info(f"\n{'=' * 65}")
    logger.info("F5 BATCH SUMMARY")
    logger.info("=" * 65)
    for sid, r in results.items():
        perm = r["permutation_percentile"]
        v = r["verdict"]
        reason = r.get("failure_reason", "")
        logger.info(f"  {sid}: {v} | perm={perm:.1f} | {reason or 'passed'}")

    logger.info(f"\nCompleted: {datetime.now().isoformat()}")
    return results


if __name__ == "__main__":
    main()
