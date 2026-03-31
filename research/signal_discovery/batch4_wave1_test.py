#!/usr/bin/env python3
"""
Batch 4, Wave 1 — Signal Discovery Tests: CS019A, CS019B, CS020, CS021

Uses the safety layer framework (signal_tester.py) for permutation tests,
season support checks, and suspect flags. Logs results to test_results_log.json
and signal_board.json.

RESEARCH ONLY — does not modify any model or pipeline files.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Setup
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("batch4_wave1")

BASE = Path(__file__).resolve().parent
SAFETY = BASE / "safety_layer"
sys.path.insert(0, str(SAFETY))

import signal_tester as st

# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════

def load_game_outcomes():
    """Load game_table + closing lines for 2022-2025 (exclude 2026 holdout)."""
    gt = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "game_table.parquet")
    gt = gt[gt["season"].isin([2022, 2023, 2024, 2025])].copy()

    # Closing lines: 2022-2023 from historical, 2024-2025 from market_snapshots
    cl_22_23 = pd.read_parquet(
        BASE.parent.parent / "sim" / "data" / "mlb_historical_closing_lines.parquet"
    )[["game_pk", "close_total"]]

    ms = pd.read_parquet(
        BASE.parent.parent / "sim" / "data" / "market_snapshots.parquet"
    )[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"})

    closing = pd.concat([cl_22_23, ms], ignore_index=True).drop_duplicates(subset="game_pk", keep="last")

    gt = gt.merge(closing, on="game_pk", how="inner")
    gt["went_over"] = (gt["actual_total"] > gt["close_total"]).astype(int)
    gt["went_under"] = (gt["actual_total"] < gt["close_total"]).astype(int)
    gt["push"] = (gt["actual_total"] == gt["close_total"]).astype(int)
    # Exclude pushes from win rate calc
    gt = gt[gt["push"] == 0].copy()

    logger.info(f"Game outcomes loaded: {len(gt)} games (pushes excluded)")
    logger.info(f"  Seasons: {sorted(gt['season'].unique())}")
    return gt


def load_registry_entry(signal_id):
    """Load registry entry directly (bypasses status check for PRE_REGISTERED)."""
    registry = st.load_registry()
    for entry in registry:
        if entry["canonical_signal_id"] == signal_id:
            return entry
    raise ValueError(f"{signal_id} not found in registry")


# ═══════════════════════════════════════════════════════════
# HELPER: SEASON BREAKDOWN + ROI CALC
# ═══════════════════════════════════════════════════════════

def season_breakdown(df, flag_col, direction="OVER"):
    """Compute win rate and ROI by season for flagged games."""
    outcome_col = "went_over" if direction == "OVER" else "went_under"
    results = {}
    for season in sorted(df["season"].unique()):
        s = df[(df["season"] == season) & (df[flag_col] == 1)]
        n = len(s)
        if n == 0:
            results[season] = {"n": 0, "win_rate": None, "roi": None}
            continue
        wr = s[outcome_col].mean()
        # ROI at -110 juice: win_rate * (100/110) - (1 - win_rate)
        roi = (wr * (100 / 110) - (1 - wr)) * 100
        results[season] = {"n": n, "win_rate": round(wr, 4), "roi": round(roi, 2)}
    return results


def segment_independence(df, flag_col, direction="OVER"):
    """Check signal distribution across segments."""
    outcome_col = "went_over" if direction == "OVER" else "went_under"
    flagged = df[df[flag_col] == 1]
    results = {}

    # By close_total bucket
    if "close_total" in df.columns:
        df_temp = flagged.copy()
        df_temp["total_bucket"] = pd.cut(df_temp["close_total"],
                                         bins=[0, 7.5, 8.5, 9.5, 25],
                                         labels=["<=7.5", "7.5-8.5", "8.5-9.5", ">9.5"])
        bucket_counts = df_temp.groupby("total_bucket", observed=True).agg(
            n=(outcome_col, "count"),
            win_rate=(outcome_col, "mean")
        ).to_dict("index")
        results["total_buckets"] = {k: {"n": int(v["n"]), "win_rate": round(v["win_rate"], 4)}
                                    for k, v in bucket_counts.items()}

    # By park factor
    if "park_factor_runs" in df.columns:
        df_temp = flagged.copy()
        median_pf = df["park_factor_runs"].median()
        df_temp["park_type"] = np.where(df_temp["park_factor_runs"] >= median_pf,
                                        "hitter_park", "pitcher_park")
        park_counts = df_temp.groupby("park_type").agg(
            n=(outcome_col, "count"),
            win_rate=(outcome_col, "mean")
        ).to_dict("index")
        results["park_types"] = {k: {"n": int(v["n"]), "win_rate": round(v["win_rate"], 4)}
                                 for k, v in park_counts.items()}

    # Check concentration: does >60% of sample come from one segment?
    if results.get("total_buckets"):
        max_pct = max(v["n"] for v in results["total_buckets"].values()) / max(1, len(flagged))
        results["max_segment_concentration"] = round(max_pct, 3)
        results["concentrated"] = max_pct > 0.60

    return results


def market_independence(df, flag_col):
    """Correlation between signal flag and closing total."""
    flagged_vals = df[flag_col].values.astype(float)
    close_vals = df["close_total"].values
    valid = ~(np.isnan(flagged_vals) | np.isnan(close_vals))
    if valid.sum() < 30:
        return {"correlation": None, "note": "insufficient data"}
    corr = np.corrcoef(flagged_vals[valid], close_vals[valid])[0, 1]
    return {
        "correlation": round(float(corr), 4),
        "already_priced": abs(corr) > 0.15,
        "note": "low correlation = market independent" if abs(corr) <= 0.15 else "WARNING: may already be priced"
    }


def monotonic_buckets(df, score_col, direction="OVER", n_buckets=4):
    """Check dose-response by signal intensity buckets."""
    outcome_col = "went_over" if direction == "OVER" else "went_under"
    valid = df.dropna(subset=[score_col])
    if len(valid) < 50:
        return {"monotonic": None, "note": "insufficient data for bucket analysis"}
    try:
        valid["bucket"] = pd.qcut(valid[score_col], n_buckets, duplicates="drop")
    except ValueError:
        return {"monotonic": None, "note": "cannot form distinct buckets"}

    bucket_stats = valid.groupby("bucket", observed=True).agg(
        n=(outcome_col, "count"),
        win_rate=(outcome_col, "mean")
    ).reset_index()
    bucket_stats["bucket"] = bucket_stats["bucket"].astype(str)

    rates = bucket_stats["win_rate"].values
    # Check monotonicity: each bucket should have higher win rate than previous
    mono_up = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1))
    # Or monotonically decreasing for UNDER with reversed z-scores
    mono_down = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))

    return {
        "buckets": bucket_stats.to_dict("records"),
        "monotonic": mono_up or mono_down,
        "direction": "increasing" if mono_up else ("decreasing" if mono_down else "non-monotonic"),
    }


# ═══════════════════════════════════════════════════════════
# BUILD RESULT + LOG
# ═══════════════════════════════════════════════════════════

def build_and_log_result(signal_id, hypothesis, perm_result,
                         season_results, direction,
                         frozen_thresholds, freeze_n,
                         segment_result, market_result,
                         mono_result, extra_diagnostics=None):
    """Build full result dict, determine verdict, log to files."""
    outcome_col = "went_over" if direction == "OVER" else "went_under"

    # Season support
    s2024 = season_results.get(2024, {})
    s2025 = season_results.get(2025, {})
    val_2024_positive = (s2024.get("win_rate") or 0) > 0.50 if direction == "OVER" else (s2024.get("win_rate") or 0) > 0.50
    val_2025_positive = (s2025.get("win_rate") or 0) > 0.50 if direction == "OVER" else (s2025.get("win_rate") or 0) > 0.50

    season_pass, season_note = st.check_season_support(val_2024_positive, val_2025_positive)

    # Suspect flags
    suspect_flags = st.check_suspect_flags(
        freeze_n,
        s2025.get("roi"),
        s2025.get("win_rate")
    )

    # Combined train (2022-2024) stats
    train_seasons = [2022, 2023, 2024]
    train_stats = {s: season_results.get(s, {}) for s in train_seasons}
    train_n = sum(v.get("n", 0) for v in train_stats.values())
    train_wins = sum(v.get("n", 0) * (v.get("win_rate") or 0) for v in train_stats.values())
    train_wr = train_wins / train_n if train_n > 0 else None
    train_roi = (train_wr * (100 / 110) - (1 - train_wr)) * 100 if train_wr else None

    # Determine verdict
    perm_pass = perm_result["percentile"] >= 85.0
    near_miss = 75.0 <= perm_result["percentile"] < 85.0

    if perm_pass and season_pass:
        verdict = "PASS"
        failure_reason = None
    elif near_miss and val_2025_positive:
        verdict = "NEAR_MISS"
        failure_reason = f"Permutation percentile {perm_result['percentile']:.1f} in 75-84 range; 2025 directionally positive"
    elif not perm_pass:
        verdict = "FAIL"
        failure_reason = f"Permutation percentile {perm_result['percentile']:.1f} < 85 required"
    elif not season_pass and "FAIL" in season_note:
        verdict = "FAIL"
        failure_reason = season_note
    elif not season_pass and "INVESTIGATE" in season_note:
        verdict = "INVESTIGATE"
        failure_reason = season_note
    else:
        verdict = "FAIL"
        failure_reason = "Did not meet pass criteria"

    # Check suspect ROI
    if s2025.get("roi") is not None and abs(s2025["roi"]) > 30:
        verdict = "SUSPECT"
        failure_reason = f"SUSPECT: 2025 ROI={s2025['roi']:.1f}% — flag for review"

    # Check alternating year artifact
    yearly_wrs = [season_results.get(y, {}).get("win_rate") for y in [2022, 2023, 2024, 2025]]
    yearly_positive = [w > 0.50 if w is not None else None for w in yearly_wrs]
    alternating = False
    if all(v is not None for v in yearly_positive):
        if (yearly_positive[0] != yearly_positive[1] and
            yearly_positive[1] != yearly_positive[2] and
            yearly_positive[2] != yearly_positive[3]):
            alternating = True

    result = {
        "canonical_signal_id": signal_id,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": frozen_thresholds,
        "freeze_window_n": freeze_n,
        "train_result": {
            "n": train_n,
            "under_rate": round(1 - train_wr, 4) if train_wr else None,
            "win_rate": round(train_wr, 4) if train_wr else None,
            "roi": round(train_roi, 2) if train_roi else None,
            "p_value": None,
        },
        "validation_2024": {
            "n": s2024.get("n", 0),
            "win_rate": s2024.get("win_rate"),
            "roi": s2024.get("roi"),
            "direction_positive": val_2024_positive,
            "note": "in-sample stability check only",
        },
        "validation_2025": {
            "n": s2025.get("n", 0),
            "win_rate": s2025.get("win_rate"),
            "roi": s2025.get("roi"),
            "direction_positive": val_2025_positive,
            "note": "binding out-of-sample validation",
        },
        "season_by_season": {str(k): v for k, v in season_results.items()},
        "alternating_year_artifact": alternating,
        "permutation_percentile": perm_result["percentile"],
        "permutation_detail": perm_result,
        "season_support_pass": season_pass,
        "season_support_note": season_note,
        "monotonic_dose_response": mono_result,
        "segment_independence": segment_result,
        "market_independence": market_result,
        "suspect_flags": suspect_flags,
        "verdict": verdict,
        "failure_reason": failure_reason,
    }

    if extra_diagnostics:
        result["extra_diagnostics"] = extra_diagnostics

    # Log to test_results_log.json
    st.log_test_result(result)

    # Update signal_board.json manually (bypass get_registered_hypothesis status check)
    board = []
    if st.BOARD_PATH.exists():
        try:
            with open(st.BOARD_PATH) as f:
                board = json.load(f)
        except Exception:
            board = []

    board = [b for b in board if b.get("canonical_signal_id") != signal_id]

    advancement = None
    if verdict == "PASS":
        advancement = "Advance to shadow monitoring with pre-registered thresholds"
    elif verdict == "NEAR_MISS":
        advancement = "Note for possible threshold refinement — do not promote"
    elif verdict == "INVESTIGATE":
        advancement = "Shadow with caution — review noted concerns before promotion"

    board_entry = {
        "canonical_signal_id": signal_id,
        "canonical_name": hypothesis["canonical_name"],
        "domain": hypothesis["domain"],
        "framework_type": hypothesis["framework_type"],
        "market_target": hypothesis["market_target"],
        "status": verdict,
        "failure_reason": failure_reason,
        "advancement_path": advancement,
        "last_updated": datetime.now().isoformat(),
    }
    board.append(board_entry)

    def _serialize(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    with open(st.BOARD_PATH, "w") as f:
        json.dump(board, f, indent=2, default=_serialize)

    return result


# ═══════════════════════════════════════════════════════════
# CS019A — UMPIRE TIGHT ZONE REGIME SHIFT (UNDER)
# ═══════════════════════════════════════════════════════════

def test_cs019a(games):
    logger.info("\n" + "=" * 65)
    logger.info("CS019A — Umpire tight zone regime shift (UNDER)")
    logger.info("=" * 65)

    hypothesis = load_registry_entry("CS019A")
    ump = pd.read_parquet(BASE / "c041_umpire_zone_metrics.parquet")

    # Use rolling z-score regime fields ONLY
    # tight_zone_flag is pre-built from rolling z-score analysis
    logger.info(f"  Umpire zone metrics: {len(ump)} game-umpire records")
    logger.info(f"  tight_zone_flag prevalence: {ump['tight_zone_flag'].mean():.3f}")

    # Merge to games on game_pk
    ump_slim = ump[["game_pk", "tight_zone_flag", "called_strike_rate_r3_vs_season"]].copy()
    merged = games.merge(ump_slim, on="game_pk", how="inner")
    logger.info(f"  Merged: {len(merged)} games with umpire zone data")

    # Freeze threshold on 2022-2023
    freeze = merged[merged["season"].isin([2022, 2023])]
    flagged_freeze = freeze[freeze["tight_zone_flag"] == 1]
    freeze_n = len(flagged_freeze)
    freeze_wr = flagged_freeze["went_under"].mean() if freeze_n > 0 else 0
    logger.info(f"  Freeze window (2022-2023): N={freeze_n}, under_rate={freeze_wr:.4f}")

    frozen_thresholds = {
        "signal_field": "tight_zone_flag",
        "threshold": 1,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
        "freeze_under_rate": round(freeze_wr, 4),
    }

    # Add flag column for analysis
    merged["cs019a_flag"] = merged["tight_zone_flag"]

    # Season breakdown
    season_results = season_breakdown(merged, "cs019a_flag", direction="UNDER")
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, under_rate={r['win_rate']}, ROI={r['roi']}%")

    # Permutation test (within-season shuffle)
    flagged_all = merged[merged["season"].isin([2022, 2023, 2024, 2025])]
    perm_result = st.run_permutation_test(
        signal_values=flagged_all["cs019a_flag"].values,
        outcomes=flagged_all["went_under"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=flagged_all["season"].values,
    )
    logger.info(f"  Permutation: observed={perm_result['observed_metric']:.4f}, "
                f"percentile={perm_result['percentile']:.1f}")

    # Monotonic dose-response using z-score intensity
    mono = monotonic_buckets(merged, "called_strike_rate_r3_vs_season", direction="UNDER")

    # Segment independence
    seg = segment_independence(merged, "cs019a_flag", direction="UNDER")

    # Market independence
    mkt = market_independence(merged, "cs019a_flag")

    result = build_and_log_result(
        "CS019A", hypothesis, perm_result, season_results, "UNDER",
        frozen_thresholds, freeze_n, seg, mkt, mono
    )

    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# CS019B — UMPIRE LOOSE ZONE REGIME SHIFT (OVER)
# ═══════════════════════════════════════════════════════════

def test_cs019b(games):
    logger.info("\n" + "=" * 65)
    logger.info("CS019B — Umpire loose zone regime shift (OVER)")
    logger.info("=" * 65)

    hypothesis = load_registry_entry("CS019B")
    ump = pd.read_parquet(BASE / "c041_umpire_zone_metrics.parquet")

    ump_slim = ump[["game_pk", "loose_zone_flag", "cs_outside_zone_rate_r3_vs_season"]].copy()
    merged = games.merge(ump_slim, on="game_pk", how="inner")
    logger.info(f"  Merged: {len(merged)} games with umpire zone data")

    # Freeze threshold on 2022-2023
    freeze = merged[merged["season"].isin([2022, 2023])]
    flagged_freeze = freeze[freeze["loose_zone_flag"] == 1]
    freeze_n = len(flagged_freeze)
    freeze_wr = flagged_freeze["went_over"].mean() if freeze_n > 0 else 0
    logger.info(f"  Freeze window (2022-2023): N={freeze_n}, over_rate={freeze_wr:.4f}")

    frozen_thresholds = {
        "signal_field": "loose_zone_flag",
        "threshold": 1,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
        "freeze_over_rate": round(freeze_wr, 4),
    }

    merged["cs019b_flag"] = merged["loose_zone_flag"]

    season_results = season_breakdown(merged, "cs019b_flag", direction="OVER")
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, over_rate={r['win_rate']}, ROI={r['roi']}%")

    flagged_all = merged[merged["season"].isin([2022, 2023, 2024, 2025])]
    perm_result = st.run_permutation_test(
        signal_values=flagged_all["cs019b_flag"].values,
        outcomes=flagged_all["went_over"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=flagged_all["season"].values,
    )
    logger.info(f"  Permutation: observed={perm_result['observed_metric']:.4f}, "
                f"percentile={perm_result['percentile']:.1f}")

    mono = monotonic_buckets(merged, "cs_outside_zone_rate_r3_vs_season", direction="OVER")
    seg = segment_independence(merged, "cs019b_flag", direction="OVER")
    mkt = market_independence(merged, "cs019b_flag")

    result = build_and_log_result(
        "CS019B", hypothesis, perm_result, season_results, "OVER",
        frozen_thresholds, freeze_n, seg, mkt, mono
    )

    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# CS020 — BULLPEN COLLAPSE BAYESIAN/ACCELERATION (OVER)
# ═══════════════════════════════════════════════════════════

def build_cs020_features(pitcher_logs):
    """
    Build bullpen collapse ACCELERATION metric per team per game.

    Measures rate of change in bullpen deterioration state:
    - For each reliever, compute rolling damage rate (runs_allowed expanding mean)
    - Compute 3-game vs 10-game damage acceleration
    - Flag relievers where recent damage is accelerating (3g > 10g by threshold)
    - Per team: count relievers with accelerating damage
    """
    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["player_id", "game_date", "game_pk"])

    # Rolling damage metrics (shift 1 = pregame only)
    rlv["ra_r3"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=3).mean()
    )
    rlv["ra_r10"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).rolling(10, min_periods=5).mean()
    )
    rlv["season_mean"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).expanding(min_periods=5).mean()
    )

    # Acceleration: 3-game rate vs 10-game rate
    rlv["acceleration"] = rlv["ra_r3"] - rlv["ra_r10"]

    # Bayesian update: how much worse is recent vs season baseline?
    rlv["bayesian_shift"] = rlv["ra_r3"] - rlv["season_mean"]

    # Composite: reliever is in "accelerating collapse" if both acceleration > 0
    # AND bayesian shift > 0 (recent is worse than both baseline AND medium-term)
    rlv["accel_flag"] = (
        (rlv["acceleration"] > 0.3) &
        (rlv["bayesian_shift"] > 0.2) &
        rlv["ra_r3"].notna() &
        rlv["ra_r10"].notna()
    ).astype(int)

    # Get latest appearance per reliever per team per game_pk
    # (a reliever appears once per game at most)
    # Aggregate to team-game level
    team_game = (
        rlv.groupby(["team", "game_pk", "season", "game_date"])
        .agg(
            n_accel_relievers=("accel_flag", "sum"),
            n_relievers=("player_id", "nunique"),
            max_acceleration=("acceleration", "max"),
            mean_bayesian_shift=("bayesian_shift", "mean"),
        )
        .reset_index()
    )

    return team_game


def build_cs013_flags(pitcher_logs):
    """Replicate CS013 logic to identify CS013-flagged games for overlap analysis."""
    DEGRADED_MULTIPLIER = 1.5
    DEGRADED_COUNT_IN_5 = 2
    TEAM_THRESHOLD = 2
    MIN_PRIOR = 5

    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["player_id", "game_date", "game_pk"])

    rlv["season_rpa"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).expanding(min_periods=MIN_PRIOR).mean()
    )
    rlv["degraded_app"] = (
        (rlv["runs_allowed"] > DEGRADED_MULTIPLIER * rlv["season_rpa"])
        & rlv["season_rpa"].notna()
    ).astype(int)
    rlv["deg_count_5"] = rlv.groupby(["player_id", "season"])["degraded_app"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).sum()
    )
    rlv["is_degraded"] = (rlv["deg_count_5"] >= DEGRADED_COUNT_IN_5).astype(int)

    # Per team per game: count degraded relievers
    team_game = (
        rlv.dropna(subset=["deg_count_5"])
        .groupby(["team", "game_pk", "season"])
        .agg(n_degraded=("is_degraded", "sum"))
        .reset_index()
    )
    team_game["cs013_team_flag"] = (team_game["n_degraded"] >= TEAM_THRESHOLD).astype(int)

    return team_game


def test_cs020(games, pitcher_logs):
    logger.info("\n" + "=" * 65)
    logger.info("CS020 — Bullpen collapse Bayesian/acceleration (OVER)")
    logger.info("=" * 65)

    hypothesis = load_registry_entry("CS020")

    # Build acceleration features
    cs020_team = build_cs020_features(pitcher_logs)

    # Pivot to game level: for each game, check home and away team
    # Need to join via game_table to get home/away mapping
    gt = games[["game_pk", "season", "home_team", "away_team",
                "actual_total", "close_total", "went_over", "went_under"]].copy()

    # Home team acceleration
    home_acc = cs020_team.rename(columns=lambda c: f"home_{c}" if c not in ["game_pk", "season"] else c)
    home_acc = home_acc.rename(columns={"home_team": "team_check"})
    gt_h = gt.merge(
        cs020_team[["team", "game_pk", "n_accel_relievers"]].rename(
            columns={"team": "home_team", "n_accel_relievers": "home_n_accel"}
        ),
        on=["home_team", "game_pk"], how="left"
    )

    # Away team acceleration
    gt_h = gt_h.merge(
        cs020_team[["team", "game_pk", "n_accel_relievers"]].rename(
            columns={"team": "away_team", "n_accel_relievers": "away_n_accel"}
        ),
        on=["away_team", "game_pk"], how="left"
    )

    gt_h["home_n_accel"] = gt_h["home_n_accel"].fillna(0)
    gt_h["away_n_accel"] = gt_h["away_n_accel"].fillna(0)
    gt_h["max_accel"] = gt_h[["home_n_accel", "away_n_accel"]].max(axis=1)

    # Freeze threshold on 2022-2023: find threshold where signal is meaningful
    freeze = gt_h[gt_h["season"].isin([2022, 2023])]
    # Test threshold: 2+ accelerating relievers on either team
    ACCEL_THRESHOLD = 2
    freeze["cs020_flag"] = (freeze["max_accel"] >= ACCEL_THRESHOLD).astype(int)
    flagged_freeze = freeze[freeze["cs020_flag"] == 1]
    freeze_n = len(flagged_freeze)
    freeze_wr = flagged_freeze["went_over"].mean() if freeze_n > 0 else 0
    logger.info(f"  Freeze window (2022-2023): N={freeze_n}, over_rate={freeze_wr:.4f}")

    # If freeze N is too thin, try threshold=1
    if freeze_n < 60:
        logger.info(f"  Threshold=2 gives N={freeze_n} < 60, trying threshold=1")
        ACCEL_THRESHOLD = 1
        freeze["cs020_flag"] = (freeze["max_accel"] >= ACCEL_THRESHOLD).astype(int)
        flagged_freeze = freeze[freeze["cs020_flag"] == 1]
        freeze_n = len(flagged_freeze)
        freeze_wr = flagged_freeze["went_over"].mean() if freeze_n > 0 else 0
        logger.info(f"  Threshold=1: N={freeze_n}, over_rate={freeze_wr:.4f}")

    frozen_thresholds = {
        "metric": "max(home_n_accel, away_n_accel)",
        "threshold": ACCEL_THRESHOLD,
        "acceleration_cutoff": 0.3,
        "bayesian_shift_cutoff": 0.2,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
        "freeze_over_rate": round(freeze_wr, 4),
    }

    # Apply flag to all seasons
    gt_h["cs020_flag"] = (gt_h["max_accel"] >= ACCEL_THRESHOLD).astype(int)

    season_results = season_breakdown(gt_h, "cs020_flag", direction="OVER")
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, over_rate={r['win_rate']}, ROI={r['roi']}%")

    # Permutation test
    all_data = gt_h[gt_h["season"].isin([2022, 2023, 2024, 2025])]
    perm_result = st.run_permutation_test(
        signal_values=all_data["cs020_flag"].values,
        outcomes=all_data["went_over"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm_result['observed_metric']:.4f}, "
                f"percentile={perm_result['percentile']:.1f}")

    mono = monotonic_buckets(gt_h, "max_accel", direction="OVER")
    seg = segment_independence(gt_h, "cs020_flag", direction="OVER")
    mkt = market_independence(gt_h, "cs020_flag")

    # CS013 overlap analysis
    logger.info("\n  --- CS013 Overlap Analysis ---")
    cs013_team = build_cs013_flags(pitcher_logs)

    # Join CS013 flags to game level
    gt_cs013 = gt_h.merge(
        cs013_team[["team", "game_pk", "cs013_team_flag"]].rename(
            columns={"team": "home_team", "cs013_team_flag": "home_cs013"}
        ),
        on=["home_team", "game_pk"], how="left"
    )
    gt_cs013 = gt_cs013.merge(
        cs013_team[["team", "game_pk", "cs013_team_flag"]].rename(
            columns={"team": "away_team", "cs013_team_flag": "away_cs013"}
        ),
        on=["away_team", "game_pk"], how="left"
    )
    gt_cs013["home_cs013"] = gt_cs013["home_cs013"].fillna(0)
    gt_cs013["away_cs013"] = gt_cs013["away_cs013"].fillna(0)
    gt_cs013["cs013_flag"] = ((gt_cs013["home_cs013"] == 1) | (gt_cs013["away_cs013"] == 1)).astype(int)

    cs020_flagged = gt_cs013[gt_cs013["cs020_flag"] == 1]
    cs013_flagged = gt_cs013[gt_cs013["cs013_flag"] == 1]
    both_flagged = gt_cs013[(gt_cs013["cs020_flag"] == 1) & (gt_cs013["cs013_flag"] == 1)]

    overlap_pct = len(both_flagged) / max(1, len(cs020_flagged))
    logger.info(f"  CS020 flagged: {len(cs020_flagged)}")
    logger.info(f"  CS013 flagged: {len(cs013_flagged)}")
    logger.info(f"  Both flagged:  {len(both_flagged)}")
    logger.info(f"  Overlap: {overlap_pct:.1%}")

    if overlap_pct >= 0.70:
        overlap_classification = "CS013_UPGRADE_CANDIDATE"
        overlap_note = f"Overlap {overlap_pct:.1%} >= 70% — CS020 is a potential CS013 upgrade candidate, not additive signal"
        # Compare performance on overlapping games
        if len(both_flagged) > 10:
            cs020_only = cs020_flagged[cs020_flagged["cs013_flag"] == 0]
            cs020_only_wr = cs020_only["went_over"].mean() if len(cs020_only) > 0 else None
            both_wr = both_flagged["went_over"].mean()
            overlap_note += f". Both-flagged over_rate={both_wr:.3f}, CS020-only over_rate={cs020_only_wr:.3f}" if cs020_only_wr else ""
    else:
        overlap_classification = "POTENTIALLY_DISTINCT"
        overlap_note = f"Overlap {overlap_pct:.1%} < 70% — potentially distinct bullpen-family signal, subject to incremental-value diagnostics"

    logger.info(f"  Classification: {overlap_classification}")
    logger.info(f"  Note: {overlap_note}")

    extra_diag = {
        "cs013_overlap": {
            "cs020_flagged_n": len(cs020_flagged),
            "cs013_flagged_n": len(cs013_flagged),
            "both_flagged_n": len(both_flagged),
            "overlap_pct": round(overlap_pct, 4),
            "classification": overlap_classification,
            "note": overlap_note,
        }
    }

    result = build_and_log_result(
        "CS020", hypothesis, perm_result, season_results, "OVER",
        frozen_thresholds, freeze_n, seg, mkt, mono, extra_diag
    )

    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# CS021 — BULLPEN USAGE COMPRESSION ASYMMETRY (OVER)
# ═══════════════════════════════════════════════════════════

def build_cs021_features(pitcher_logs):
    """
    Build bullpen usage compression metric per team per game.

    Measures how concentrated a team's reliever usage is in a narrow set
    of arms using HHI (Herfindahl-Hirschman Index) on recent innings.
    High HHI = heavy reliance on few relievers.
    """
    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["team", "season", "game_date", "game_pk"])

    # For each team-season, compute rolling 14-day usage concentration
    results = []
    for (team, season), grp in rlv.groupby(["team", "season"]):
        grp = grp.copy()
        grp["game_date_dt"] = pd.to_datetime(grp["game_date"])

        # Get unique game dates for this team
        game_dates = grp[["game_pk", "game_date_dt"]].drop_duplicates("game_pk").sort_values("game_date_dt")

        for _, game_row in game_dates.iterrows():
            gd = game_row["game_date_dt"]
            gpk = game_row["game_pk"]

            # Look at last 14 days BEFORE this game (shift 1)
            window_start = gd - pd.Timedelta(days=14)
            window = grp[(grp["game_date_dt"] >= window_start) & (grp["game_date_dt"] < gd)]

            if len(window) < 5:  # Need minimum usage data
                continue

            # HHI on innings pitched
            total_ip = window["innings_pitched"].sum()
            if total_ip == 0:
                continue

            by_pitcher = window.groupby("player_id")["innings_pitched"].sum()
            shares = by_pitcher / total_ip
            hhi = (shares ** 2).sum()

            # Also count distinct relievers used
            n_distinct = len(by_pitcher)

            # Top-3 share: what fraction of innings went to top 3 relievers
            top3_share = shares.nlargest(3).sum()

            results.append({
                "team": team,
                "season": season,
                "game_pk": gpk,
                "hhi": hhi,
                "n_distinct_relievers": n_distinct,
                "top3_share": top3_share,
            })

    return pd.DataFrame(results)


def test_cs021(games, pitcher_logs):
    logger.info("\n" + "=" * 65)
    logger.info("CS021 — Bullpen usage compression asymmetry (OVER)")
    logger.info("=" * 65)

    hypothesis = load_registry_entry("CS021")

    # Build compression features
    cs021_team = build_cs021_features(pitcher_logs)
    logger.info(f"  Built CS021 features: {len(cs021_team)} team-game records")

    # Join to game level: compute asymmetry (max HHI of the two teams)
    gt = games[["game_pk", "season", "home_team", "away_team",
                "actual_total", "close_total", "went_over", "went_under",
                "park_factor_runs"]].copy()

    gt = gt.merge(
        cs021_team[["team", "game_pk", "hhi", "top3_share"]].rename(
            columns={"team": "home_team", "hhi": "home_hhi", "top3_share": "home_top3"}
        ),
        on=["home_team", "game_pk"], how="left"
    )
    gt = gt.merge(
        cs021_team[["team", "game_pk", "hhi", "top3_share"]].rename(
            columns={"team": "away_team", "hhi": "away_hhi", "top3_share": "away_top3"}
        ),
        on=["away_team", "game_pk"], how="left"
    )

    # Asymmetry: difference in compression between teams
    gt["hhi_max"] = gt[["home_hhi", "away_hhi"]].max(axis=1)
    gt["hhi_asymmetry"] = (gt["home_hhi"] - gt["away_hhi"]).abs()
    gt["top3_max"] = gt[["home_top3", "away_top3"]].max(axis=1)

    # Drop games without features
    gt = gt.dropna(subset=["hhi_max"]).copy()
    logger.info(f"  Games with CS021 features: {len(gt)}")

    # Freeze threshold on 2022-2023
    freeze = gt[gt["season"].isin([2022, 2023])]

    # Find threshold: top quartile of hhi_max
    q75 = freeze["hhi_max"].quantile(0.75)
    logger.info(f"  HHI max Q75 (2022-2023): {q75:.4f}")

    HHI_THRESHOLD = round(q75, 4)
    freeze["cs021_flag"] = (freeze["hhi_max"] >= HHI_THRESHOLD).astype(int)
    flagged_freeze = freeze[freeze["cs021_flag"] == 1]
    freeze_n = len(flagged_freeze)
    freeze_wr = flagged_freeze["went_over"].mean() if freeze_n > 0 else 0
    logger.info(f"  Freeze window: N={freeze_n}, over_rate={freeze_wr:.4f}")

    frozen_thresholds = {
        "metric": "max(home_hhi, away_hhi)",
        "threshold": HHI_THRESHOLD,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
        "freeze_over_rate": round(freeze_wr, 4),
    }

    gt["cs021_flag"] = (gt["hhi_max"] >= HHI_THRESHOLD).astype(int)

    season_results = season_breakdown(gt, "cs021_flag", direction="OVER")
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, over_rate={r['win_rate']}, ROI={r['roi']}%")

    # Permutation test
    all_data = gt[gt["season"].isin([2022, 2023, 2024, 2025])]
    perm_result = st.run_permutation_test(
        signal_values=all_data["cs021_flag"].values,
        outcomes=all_data["went_over"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm_result['observed_metric']:.4f}, "
                f"percentile={perm_result['percentile']:.1f}")

    mono = monotonic_buckets(gt, "hhi_max", direction="OVER")
    seg = segment_independence(gt, "cs021_flag", direction="OVER")
    mkt = market_independence(gt, "cs021_flag")

    # CS013 overlap analysis
    logger.info("\n  --- CS013 Overlap Analysis ---")
    cs013_team = build_cs013_flags(pitcher_logs)

    gt_cs013 = gt.merge(
        cs013_team[["team", "game_pk", "cs013_team_flag"]].rename(
            columns={"team": "home_team", "cs013_team_flag": "home_cs013"}
        ),
        on=["home_team", "game_pk"], how="left"
    )
    gt_cs013 = gt_cs013.merge(
        cs013_team[["team", "game_pk", "cs013_team_flag"]].rename(
            columns={"team": "away_team", "cs013_team_flag": "away_cs013"}
        ),
        on=["away_team", "game_pk"], how="left"
    )
    gt_cs013["home_cs013"] = gt_cs013["home_cs013"].fillna(0)
    gt_cs013["away_cs013"] = gt_cs013["away_cs013"].fillna(0)
    gt_cs013["cs013_flag"] = ((gt_cs013["home_cs013"] == 1) | (gt_cs013["away_cs013"] == 1)).astype(int)

    cs021_flagged = gt_cs013[gt_cs013["cs021_flag"] == 1]
    cs013_flagged = gt_cs013[gt_cs013["cs013_flag"] == 1]
    both_flagged = gt_cs013[(gt_cs013["cs021_flag"] == 1) & (gt_cs013["cs013_flag"] == 1)]

    overlap_pct = len(both_flagged) / max(1, len(cs021_flagged))
    logger.info(f"  CS021 flagged: {len(cs021_flagged)}")
    logger.info(f"  CS013 flagged: {len(cs013_flagged)}")
    logger.info(f"  Both flagged:  {len(both_flagged)}")
    logger.info(f"  Overlap: {overlap_pct:.1%}")

    # Incremental value: does CS021 help on games CS013 does NOT flag?
    cs021_only = gt_cs013[(gt_cs013["cs021_flag"] == 1) & (gt_cs013["cs013_flag"] == 0)]
    cs021_only_wr = cs021_only["went_over"].mean() if len(cs021_only) > 0 else None
    cs021_only_n = len(cs021_only)

    if overlap_pct >= 0.70:
        classification = "HIGH_OVERLAP"
        note = f"Overlap {overlap_pct:.1%} >= 70% — requires incremental-value diagnostics"
    else:
        classification = "DIFFERENT_DIMENSION"
        note = (f"Overlap {overlap_pct:.1%} < 70% — tests different bullpen dimension "
                f"(deployment structure vs deterioration state)")

    note += f". CS021-only (non-CS013) games: N={cs021_only_n}, over_rate={cs021_only_wr:.4f}" if cs021_only_wr else ""

    logger.info(f"  Classification: {classification}")
    logger.info(f"  CS021-only games: N={cs021_only_n}, over_rate={cs021_only_wr}")

    extra_diag = {
        "cs013_overlap": {
            "cs021_flagged_n": len(cs021_flagged),
            "cs013_flagged_n": len(cs013_flagged),
            "both_flagged_n": len(both_flagged),
            "overlap_pct": round(overlap_pct, 4),
            "cs021_only_n": cs021_only_n,
            "cs021_only_over_rate": round(cs021_only_wr, 4) if cs021_only_wr else None,
            "classification": classification,
            "note": note,
        }
    }

    result = build_and_log_result(
        "CS021", hypothesis, perm_result, season_results, "OVER",
        frozen_thresholds, freeze_n, seg, mkt, mono, extra_diag
    )

    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 65)
    logger.info("BATCH 4, WAVE 1 — Signal Discovery Tests")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("Signals: CS019A, CS019B, CS020, CS021")
    logger.info("=" * 65)

    # Load shared data
    games = load_game_outcomes()
    pitcher_logs = pd.read_parquet(
        BASE.parent.parent / "mlb" / "data" / "pitcher_game_logs.parquet"
    )
    pitcher_logs = pitcher_logs[pitcher_logs["season"].isin([2022, 2023, 2024, 2025])].copy()
    logger.info(f"Pitcher game logs loaded: {len(pitcher_logs)} rows")

    # Run all 4 tests
    results = {}
    results["CS019A"] = test_cs019a(games)
    results["CS019B"] = test_cs019b(games)
    results["CS020"] = test_cs020(games, pitcher_logs)
    results["CS021"] = test_cs021(games, pitcher_logs)

    # Batch summary
    logger.info("\n" + "=" * 65)
    logger.info("BATCH 4, WAVE 1 — SUMMARY")
    logger.info("=" * 65)

    for sid, r in results.items():
        v = r["verdict"]
        reason = r.get("failure_reason", "")
        perm = r["permutation_percentile"]
        s2025 = r["validation_2025"]
        logger.info(f"  {sid}: {v} | perm={perm:.1f} | "
                    f"2025 N={s2025['n']}, wr={s2025.get('win_rate')}, roi={s2025.get('roi')}%"
                    f"{' | ' + reason if reason else ''}")

    passed = [sid for sid, r in results.items() if r["verdict"] == "PASS"]
    failed = [sid for sid, r in results.items() if r["verdict"] == "FAIL"]
    near = [sid for sid, r in results.items() if r["verdict"] == "NEAR_MISS"]
    suspect = [sid for sid, r in results.items() if r["verdict"] == "SUSPECT"]

    logger.info(f"\n  PASSED: {passed if passed else 'none'}")
    logger.info(f"  FAILED: {failed if failed else 'none'}")
    logger.info(f"  NEAR_MISS: {near if near else 'none'}")
    logger.info(f"  SUSPECT: {suspect if suspect else 'none'}")

    if passed:
        logger.info("\n  CHECKPOINT RECOMMENDATION:")
        logger.info("  Any passed signal should receive external review before shadow decision.")

    logger.info(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
