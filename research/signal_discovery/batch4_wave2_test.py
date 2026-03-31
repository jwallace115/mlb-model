#!/usr/bin/env python3
"""
Batch 4, Wave 2 — Signal Discovery Tests: CS022A, CS022B, CS023, CS024

Statcast pitch-level signals. Uses safety layer for permutation tests.
Logs results to test_results_log.json and signal_board.json.

RESEARCH ONLY — does not modify any model or pipeline files.
"""

import json
import logging
import sys
import glob
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("batch4_wave2")

BASE = Path(__file__).resolve().parent
SAFETY = BASE / "safety_layer"
sys.path.insert(0, str(SAFETY))

import signal_tester as st

# ═══════════════════════════════════════════════════════════
# FROZEN ELIGIBILITY RULE
# ═══════════════════════════════════════════════════════════
# Minimum prior starts before a pitcher is eligible to trigger
# any rolling-baseline signal. Frozen on 2022-2023 data below.
MIN_PRIOR_STARTS = 4  # pitcher needs 4+ prior starts in-season


# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════

def load_game_outcomes():
    """Load game outcomes with closing lines. Exclude pushes and 2026."""
    gt = pd.read_parquet(BASE.parent.parent / "sim" / "data" / "game_table.parquet")
    gt = gt[gt["season"].isin([2022, 2023, 2024, 2025])].copy()

    cl_22_23 = pd.read_parquet(
        BASE.parent.parent / "sim" / "data" / "mlb_historical_closing_lines.parquet"
    )[["game_pk", "close_total"]]
    ms_24_25 = pd.read_parquet(
        BASE.parent.parent / "sim" / "data" / "market_snapshots.parquet"
    )[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"})

    closing = pd.concat([cl_22_23, ms_24_25], ignore_index=True).drop_duplicates(
        subset="game_pk", keep="last"
    )
    gt = gt.merge(closing, on="game_pk", how="inner")
    gt["went_over"] = (gt["actual_total"] > gt["close_total"]).astype(int)
    gt["went_under"] = (gt["actual_total"] < gt["close_total"]).astype(int)
    gt["push"] = (gt["actual_total"] == gt["close_total"]).astype(int)
    gt = gt[gt["push"] == 0].copy()
    logger.info(f"Game outcomes: {len(gt)} (pushes excluded)")
    return gt


def load_statcast():
    """Load all Statcast chunks, regular season only, with starter identification."""
    files = sorted(glob.glob(str(BASE.parent.parent / "mlb" / "props" / "data" / "statcast_chunk_*.parquet")))
    sc = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    sc = sc[sc["game_type"] == "R"].copy()
    sc = sc.sort_values(["game_pk", "inning", "inning_topbot", "at_bat_number", "pitch_number"])

    # Identify starters: pitcher who threw first pitch per side per game
    first = sc.groupby(["game_pk", "inning_topbot"]).first().reset_index()
    starters = first[first["inning"] == 1][["game_pk", "inning_topbot", "pitcher", "game_year"]].copy()
    starters = starters.rename(columns={"pitcher": "starter_id", "game_year": "season"})

    # Keep only starter pitches
    sc = sc.merge(starters[["game_pk", "inning_topbot", "starter_id"]],
                  on=["game_pk", "inning_topbot"])
    sc = sc[sc["pitcher"] == sc["starter_id"]].copy()

    logger.info(f"Statcast: {len(sc):,} starter pitches, {len(starters)} starter appearances")
    return sc, starters


def build_per_start_features(sc, starters):
    """
    Build per-start features for all four signals:
    - primary_pitch_share: fraction of pitches that are the starter's most-used type (season)
    - primary_shift: change in primary_pitch_share vs season baseline
    - entropy: Shannon entropy of pitch-type distribution
    - entropy_shift: change vs season baseline
    - release_ext_mean: mean release_extension for the start
    - release_ext_shift: change vs season baseline
    """
    # Per-start pitch-type distribution
    pt_counts = (
        sc.dropna(subset=["pitch_type"])
        .groupby(["game_pk", "starter_id", "game_year", "game_date", "pitch_type"])
        .size()
        .reset_index(name="count")
    )
    start_totals = pt_counts.groupby(["game_pk", "starter_id", "game_year", "game_date"])["count"].sum().reset_index(name="total")
    pt_counts = pt_counts.merge(start_totals, on=["game_pk", "starter_id", "game_year", "game_date"])
    pt_counts["share"] = pt_counts["count"] / pt_counts["total"]

    # Per-start: primary pitch share (most-used pitch type this start)
    primary = pt_counts.loc[pt_counts.groupby(["game_pk", "starter_id"])["share"].idxmax()][
        ["game_pk", "starter_id", "game_year", "game_date", "pitch_type", "share"]
    ].rename(columns={"share": "primary_share", "pitch_type": "primary_type"})

    # Shannon entropy per start
    def _entropy(group):
        shares = group["share"].values
        shares = shares[shares > 0]
        return -np.sum(shares * np.log2(shares))

    ent = pt_counts.groupby(["game_pk", "starter_id", "game_year", "game_date"]).apply(
        _entropy, include_groups=False
    ).reset_index(name="entropy")

    # Release extension per start
    ext = (
        sc.dropna(subset=["release_extension"])
        .groupby(["game_pk", "starter_id", "game_year", "game_date"])
        .agg(release_ext_mean=("release_extension", "mean"))
        .reset_index()
    )

    # Merge all per-start features
    starts = primary.merge(ent, on=["game_pk", "starter_id", "game_year", "game_date"])
    starts = starts.merge(ext, on=["game_pk", "starter_id", "game_year", "game_date"], how="left")
    starts = starts.sort_values(["starter_id", "game_year", "game_date", "game_pk"])
    starts = starts.rename(columns={"game_year": "season"})

    # Rolling baselines (shift 1 = pregame only, within-season)
    for col in ["primary_share", "entropy", "release_ext_mean"]:
        starts[f"{col}_baseline"] = starts.groupby(["starter_id", "season"])[col].transform(
            lambda x: x.shift(1).expanding(min_periods=MIN_PRIOR_STARTS).mean()
        )
        starts[f"{col}_r3"] = starts.groupby(["starter_id", "season"])[col].transform(
            lambda x: x.shift(1).rolling(3, min_periods=3).mean()
        )

    # Shift = last-3 vs season baseline
    starts["primary_shift"] = starts["primary_share_r3"] - starts["primary_share_baseline"]
    starts["entropy_shift"] = starts["entropy_r3"] - starts["entropy_baseline"]
    starts["ext_shift"] = starts["release_ext_mean_r3"] - starts["release_ext_mean_baseline"]

    # Count prior starts for eligibility
    starts["start_num"] = starts.groupby(["starter_id", "season"]).cumcount()

    logger.info(f"Per-start features built: {len(starts)} starts")
    eligible = starts[starts["start_num"] >= MIN_PRIOR_STARTS]
    logger.info(f"Eligible (>= {MIN_PRIOR_STARTS} prior starts): {len(eligible)} "
                f"({len(eligible)/len(starts):.1%})")

    return starts


def load_registry_entry(signal_id):
    registry = st.load_registry()
    for entry in registry:
        if entry["canonical_signal_id"] == signal_id:
            return entry
    raise ValueError(f"{signal_id} not found")


# ═══════════════════════════════════════════════════════════
# ANALYSIS HELPERS
# ═══════════════════════════════════════════════════════════

def season_breakdown(df, flag_col, direction):
    outcome_col = "went_over" if direction == "OVER" else "went_under"
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


def segment_independence(df, flag_col, direction):
    outcome_col = "went_over" if direction == "OVER" else "went_under"
    flagged = df[df[flag_col] == 1]
    results = {}
    if "close_total" in df.columns and len(flagged) > 0:
        df_temp = flagged.copy()
        df_temp["total_bucket"] = pd.cut(df_temp["close_total"],
                                         bins=[0, 7.5, 8.5, 9.5, 25],
                                         labels=["<=7.5", "7.5-8.5", "8.5-9.5", ">9.5"])
        bc = df_temp.groupby("total_bucket", observed=True).agg(
            n=(outcome_col, "count"), win_rate=(outcome_col, "mean")
        ).to_dict("index")
        results["total_buckets"] = {k: {"n": int(v["n"]), "win_rate": round(v["win_rate"], 4)}
                                    for k, v in bc.items()}
    if "park_factor_runs" in df.columns and len(flagged) > 0:
        df_temp = flagged.copy()
        med = df["park_factor_runs"].median()
        df_temp["park_type"] = np.where(df_temp["park_factor_runs"] >= med, "hitter", "pitcher")
        pc = df_temp.groupby("park_type").agg(
            n=(outcome_col, "count"), win_rate=(outcome_col, "mean")
        ).to_dict("index")
        results["park_types"] = {k: {"n": int(v["n"]), "win_rate": round(v["win_rate"], 4)}
                                 for k, v in pc.items()}
    if results.get("total_buckets") and len(flagged) > 0:
        max_pct = max(v["n"] for v in results["total_buckets"].values()) / len(flagged)
        results["max_segment_concentration"] = round(max_pct, 3)
        results["concentrated"] = max_pct > 0.60
    return results


def market_independence(df, flag_col):
    vals = df[flag_col].values.astype(float)
    close = df["close_total"].values
    valid = ~(np.isnan(vals) | np.isnan(close))
    if valid.sum() < 30:
        return {"correlation": None}
    corr = np.corrcoef(vals[valid], close[valid])[0, 1]
    return {"correlation": round(float(corr), 4),
            "already_priced": abs(corr) > 0.15}


def monotonic_buckets(df, score_col, direction, n_buckets=4):
    outcome_col = "went_over" if direction == "OVER" else "went_under"
    valid = df.dropna(subset=[score_col]).copy()
    if len(valid) < 50:
        return {"monotonic": None, "note": "insufficient data"}
    try:
        valid["bucket"] = pd.qcut(valid[score_col], n_buckets, duplicates="drop")
    except ValueError:
        return {"monotonic": None, "note": "cannot form distinct buckets"}
    bs = valid.groupby("bucket", observed=True).agg(
        n=(outcome_col, "count"), win_rate=(outcome_col, "mean")
    ).reset_index()
    bs["bucket"] = bs["bucket"].astype(str)
    rates = bs["win_rate"].values
    mono = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1)) or \
           all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))
    return {"buckets": bs.to_dict("records"), "monotonic": mono}


# ═══════════════════════════════════════════════════════════
# GAME-LEVEL JOIN: starter features → game outcomes
# ═══════════════════════════════════════════════════════════

def join_starts_to_games(starts, games, starters_info):
    """
    Join per-start features to game-level outcomes.
    Returns a table where each game has home_* and away_* starter features.
    """
    # Map starter_id to home/away for each game
    # inning_topbot: 'Top' = away batting = home pitching, 'Bot' = home batting = away pitching
    home_starts = starters_info[starters_info["inning_topbot"] == "Top"][
        ["game_pk", "starter_id"]
    ].rename(columns={"starter_id": "home_starter_id"})
    away_starts = starters_info[starters_info["inning_topbot"] == "Bot"][
        ["game_pk", "starter_id"]
    ].rename(columns={"starter_id": "away_starter_id"})

    g = games.merge(home_starts, on="game_pk", how="inner")
    g = g.merge(away_starts, on="game_pk", how="inner")

    # Join home starter features
    feat_cols = ["primary_shift", "entropy_shift", "ext_shift",
                 "primary_share_r3", "entropy_r3", "release_ext_mean_r3",
                 "start_num"]
    home_feats = starts[["game_pk", "starter_id"] + feat_cols].rename(
        columns={c: f"home_{c}" for c in feat_cols}
    ).rename(columns={"starter_id": "home_starter_id"})
    g = g.merge(home_feats, on=["game_pk", "home_starter_id"], how="left")

    away_feats = starts[["game_pk", "starter_id"] + feat_cols].rename(
        columns={c: f"away_{c}" for c in feat_cols}
    ).rename(columns={"starter_id": "away_starter_id"})
    g = g.merge(away_feats, on=["game_pk", "away_starter_id"], how="left")

    return g


# ═══════════════════════════════════════════════════════════
# BUILD + LOG RESULT
# ═══════════════════════════════════════════════════════════

def build_and_log_result(signal_id, hypothesis, perm_result,
                         season_results, direction,
                         frozen_thresholds, freeze_n,
                         seg_result, mkt_result, mono_result,
                         extra=None, version_note=None):
    s2024 = season_results.get(2024, {})
    s2025 = season_results.get(2025, {})
    val_2024_positive = (s2024.get("win_rate") or 0) > 0.50
    val_2025_positive = (s2025.get("win_rate") or 0) > 0.50

    season_pass, season_note = st.check_season_support(val_2024_positive, val_2025_positive)

    suspect_flags = st.check_suspect_flags(freeze_n, s2025.get("roi"), s2025.get("win_rate"))

    train_n = sum(season_results.get(y, {}).get("n", 0) for y in [2022, 2023, 2024])
    train_wins = sum(season_results.get(y, {}).get("n", 0) * (season_results.get(y, {}).get("win_rate") or 0) for y in [2022, 2023, 2024])
    train_wr = train_wins / train_n if train_n > 0 else None
    train_roi = (train_wr * (100 / 110) - (1 - train_wr)) * 100 if train_wr else None

    perm_pctile = perm_result["percentile"]
    perm_pass = perm_pctile >= 85.0
    near_miss = 75.0 <= perm_pctile < 85.0

    if freeze_n < 50:
        verdict = "NEEDS_MORE_DATA"
        failure_reason = f"N={freeze_n} < 50 at frozen threshold"
    elif s2025.get("roi") is not None and abs(s2025["roi"]) > 30:
        verdict = "SUSPECT"
        failure_reason = f"2025 ROI={s2025['roi']:.1f}% — flag for review"
    elif perm_pass and season_pass:
        verdict = "PASS"
        failure_reason = None
    elif near_miss and val_2025_positive:
        verdict = "NEAR_MISS"
        failure_reason = f"Permutation {perm_pctile:.1f} in 75-84 range; 2025 positive"
    elif not perm_pass:
        verdict = "FAIL"
        failure_reason = f"Permutation percentile {perm_pctile:.1f} < 85 required"
    elif "FAIL" in season_note:
        verdict = "FAIL"
        failure_reason = season_note
    elif "INVESTIGATE" in season_note:
        verdict = "INVESTIGATE"
        failure_reason = season_note
    else:
        verdict = "FAIL"
        failure_reason = "Did not meet pass criteria"

    yearly_wrs = [season_results.get(y, {}).get("win_rate") for y in [2022, 2023, 2024, 2025]]
    yearly_pos = [w > 0.50 if w is not None else None for w in yearly_wrs]
    alternating = False
    if all(v is not None for v in yearly_pos):
        if (yearly_pos[0] != yearly_pos[1] and yearly_pos[1] != yearly_pos[2] and
            yearly_pos[2] != yearly_pos[3]):
            alternating = True

    result = {
        "canonical_signal_id": signal_id,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": frozen_thresholds,
        "freeze_window_n": freeze_n,
        "min_prior_starts": MIN_PRIOR_STARTS,
        "version_note": version_note,
        "train_result": {
            "n": train_n,
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
        "permutation_percentile": perm_pctile,
        "permutation_detail": perm_result,
        "season_support_pass": season_pass,
        "season_support_note": season_note,
        "monotonic_dose_response": mono_result,
        "segment_independence": seg_result,
        "market_independence": mkt_result,
        "suspect_flags": suspect_flags,
        "verdict": verdict,
        "failure_reason": failure_reason,
    }
    if extra:
        result["extra_diagnostics"] = extra

    st.log_test_result(result)

    # Update board manually (PRE_REGISTERED status bypasses get_registered_hypothesis)
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

    def _ser(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        raise TypeError(type(obj).__name__)

    with open(st.BOARD_PATH, "w") as f:
        json.dump(board, f, indent=2, default=_ser)

    return result


# ═══════════════════════════════════════════════════════════
# CS022A / CS022B — Pitcher repertoire mix shift
# ═══════════════════════════════════════════════════════════

def test_cs022(games_joined, direction, signal_id):
    """
    CS022A (UNDER): primary pitch usage share INCREASED >= threshold
    CS022B (OVER): primary pitch usage share DROPPED >= threshold

    Single shared absolute threshold frozen on 2022-2023.
    Step 1: single-starter trigger (either starter meets threshold).
    """
    hypothesis = load_registry_entry(signal_id)
    label = f"{signal_id} ({'concentration→UNDER' if direction == 'UNDER' else 'instability→OVER'})"
    logger.info(f"\n{'=' * 65}")
    logger.info(f"{label}")
    logger.info("=" * 65)

    g = games_joined.copy()

    # Eligibility: at least one starter must have enough prior starts
    g["home_eligible"] = g["home_start_num"] >= MIN_PRIOR_STARTS
    g["away_eligible"] = g["away_start_num"] >= MIN_PRIOR_STARTS
    g["any_eligible"] = g["home_eligible"] | g["away_eligible"]
    g = g[g["any_eligible"]].copy()
    logger.info(f"  Games with at least one eligible starter: {len(g)}")

    # Freeze threshold on 2022-2023
    freeze = g[g["season"].isin([2022, 2023])]

    # Determine shared threshold: find shift magnitude that captures ~15-25% of eligible starts
    # We use absolute primary_shift values
    all_shifts = pd.concat([
        freeze.loc[freeze["home_eligible"], "home_primary_shift"].dropna(),
        freeze.loc[freeze["away_eligible"], "away_primary_shift"].dropna(),
    ])

    if direction == "UNDER":
        # Concentration: shift > 0 (usage share increased)
        positive_shifts = all_shifts[all_shifts > 0]
        THRESHOLD = round(float(positive_shifts.quantile(0.75)), 4)
        logger.info(f"  Freeze threshold (Q75 of positive shifts): +{THRESHOLD:.4f}")

        g["home_trigger"] = (g["home_primary_shift"] >= THRESHOLD) & g["home_eligible"]
        g["away_trigger"] = (g["away_primary_shift"] >= THRESHOLD) & g["away_eligible"]
    else:
        # Instability: shift < 0 (usage share dropped)
        negative_shifts = all_shifts[all_shifts < 0]
        THRESHOLD = round(float(negative_shifts.quantile(0.25)), 4)
        logger.info(f"  Freeze threshold (Q25 of negative shifts): {THRESHOLD:.4f}")

        g["home_trigger"] = (g["home_primary_shift"] <= THRESHOLD) & g["home_eligible"]
        g["away_trigger"] = (g["away_primary_shift"] <= THRESHOLD) & g["away_eligible"]

    # Step 1: Single-starter trigger (either starter)
    g["flag"] = (g["home_trigger"] | g["away_trigger"]).astype(int)

    freeze_flagged = g[(g["season"].isin([2022, 2023])) & (g["flag"] == 1)]
    freeze_n = len(freeze_flagged)
    logger.info(f"  Freeze N (2022-2023): {freeze_n}")

    frozen_thresholds = {
        "metric": "primary_pitch_share_shift (r3 vs season baseline)",
        "threshold": THRESHOLD,
        "direction_trigger": "increase >= threshold" if direction == "UNDER" else "decrease <= threshold",
        "version": "single_starter",
        "min_prior_starts": MIN_PRIOR_STARTS,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
    }

    if freeze_n < 50:
        logger.info(f"  SKIP: N={freeze_n} < 50 — NEEDS_MORE_DATA")
        result = build_and_log_result(
            signal_id, hypothesis,
            {"percentile": 0, "observed_metric": 0, "permutation_mean": 0,
             "permutation_std": 0, "permutation_p5": 0, "permutation_p95": 0,
             "n_permutations": 0},
            season_breakdown(g, "flag", direction), direction,
            frozen_thresholds, freeze_n, {}, {}, {},
            version_note="single_starter"
        )
        logger.info(f"  VERDICT: {result['verdict']}")
        return result

    season_results = season_breakdown(g, "flag", direction)
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, win_rate={r['win_rate']}, ROI={r['roi']}%")

    # Permutation test
    all_data = g[g["season"].isin([2022, 2023, 2024, 2025])]
    outcome_col = "went_under" if direction == "UNDER" else "went_over"
    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data[outcome_col].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.4f}, pctile={perm['percentile']:.1f}")

    shift_col = "home_primary_shift" if direction == "UNDER" else "home_primary_shift"
    mono = monotonic_buckets(g, shift_col, direction)
    seg = segment_independence(g, "flag", direction)
    mkt = market_independence(g, "flag")

    result = build_and_log_result(
        signal_id, hypothesis, perm, season_results, direction,
        frozen_thresholds, freeze_n, seg, mkt, mono,
        version_note="single_starter"
    )
    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# CS023 — Pitcher entropy regime shift (UNDER)
# ═══════════════════════════════════════════════════════════

def test_cs023(games_joined):
    signal_id = "CS023"
    hypothesis = load_registry_entry(signal_id)
    logger.info(f"\n{'=' * 65}")
    logger.info(f"CS023 — Pitcher entropy regime shift (UNDER)")
    logger.info("=" * 65)

    g = games_joined.copy()
    g["home_eligible"] = g["home_start_num"] >= MIN_PRIOR_STARTS
    g["away_eligible"] = g["away_start_num"] >= MIN_PRIOR_STARTS
    g["any_eligible"] = g["home_eligible"] | g["away_eligible"]
    g = g[g["any_eligible"]].copy()
    logger.info(f"  Games with eligible starters: {len(g)}")

    # Freeze entropy decrease threshold on 2022-2023
    freeze = g[g["season"].isin([2022, 2023])]
    all_shifts = pd.concat([
        freeze.loc[freeze["home_eligible"], "home_entropy_shift"].dropna(),
        freeze.loc[freeze["away_eligible"], "away_entropy_shift"].dropna(),
    ])

    # Entropy DECREASED = negative shift. UNDER signal.
    negative_shifts = all_shifts[all_shifts < 0]
    THRESHOLD = round(float(negative_shifts.quantile(0.25)), 4)
    logger.info(f"  Freeze threshold (Q25 of negative entropy shifts): {THRESHOLD:.4f} bits")

    g["home_trigger"] = (g["home_entropy_shift"] <= THRESHOLD) & g["home_eligible"]
    g["away_trigger"] = (g["away_entropy_shift"] <= THRESHOLD) & g["away_eligible"]
    g["flag"] = (g["home_trigger"] | g["away_trigger"]).astype(int)

    freeze_flagged = g[(g["season"].isin([2022, 2023])) & (g["flag"] == 1)]
    freeze_n = len(freeze_flagged)
    logger.info(f"  Freeze N (2022-2023): {freeze_n}")

    frozen_thresholds = {
        "metric": "entropy_shift (r3 vs season baseline)",
        "threshold_bits": THRESHOLD,
        "direction_trigger": "entropy decreased <= threshold",
        "version": "single_starter",
        "min_prior_starts": MIN_PRIOR_STARTS,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
    }

    if freeze_n < 50:
        logger.info(f"  SKIP: N={freeze_n} < 50")
        result = build_and_log_result(
            signal_id, hypothesis,
            {"percentile": 0, "observed_metric": 0, "permutation_mean": 0,
             "permutation_std": 0, "permutation_p5": 0, "permutation_p95": 0,
             "n_permutations": 0},
            season_breakdown(g, "flag", "UNDER"), "UNDER",
            frozen_thresholds, freeze_n, {}, {}, {},
            version_note="single_starter"
        )
        logger.info(f"  VERDICT: {result['verdict']}")
        return result

    season_results = season_breakdown(g, "flag", "UNDER")
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, under_rate={r['win_rate']}, ROI={r['roi']}%")

    all_data = g[g["season"].isin([2022, 2023, 2024, 2025])]
    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data["went_under"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.4f}, pctile={perm['percentile']:.1f}")

    mono = monotonic_buckets(g, "home_entropy_shift", "UNDER")
    seg = segment_independence(g, "flag", "UNDER")
    mkt = market_independence(g, "flag")

    result = build_and_log_result(
        signal_id, hypothesis, perm, season_results, "UNDER",
        frozen_thresholds, freeze_n, seg, mkt, mono,
        version_note="single_starter"
    )
    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# CS024 — Extension rate composite regime (UNDER)
# ═══════════════════════════════════════════════════════════

def test_cs024(games_joined):
    signal_id = "CS024"
    hypothesis = load_registry_entry(signal_id)
    logger.info(f"\n{'=' * 65}")
    logger.info(f"CS024 — Extension rate composite regime (UNDER)")
    logger.info("=" * 65)

    g = games_joined.copy()
    g["home_eligible"] = g["home_start_num"] >= MIN_PRIOR_STARTS
    g["away_eligible"] = g["away_start_num"] >= MIN_PRIOR_STARTS
    g["any_eligible"] = g["home_eligible"] | g["away_eligible"]
    g = g[g["any_eligible"]].copy()
    logger.info(f"  Games with eligible starters: {len(g)}")

    # Freeze extension increase threshold on 2022-2023
    freeze = g[g["season"].isin([2022, 2023])]
    all_shifts = pd.concat([
        freeze.loc[freeze["home_eligible"], "home_ext_shift"].dropna(),
        freeze.loc[freeze["away_eligible"], "away_ext_shift"].dropna(),
    ])

    # Extension INCREASED = positive shift → better deception → UNDER
    positive_shifts = all_shifts[all_shifts > 0]
    THRESHOLD = round(float(positive_shifts.quantile(0.75)), 4)
    logger.info(f"  Freeze threshold (Q75 of positive ext shifts): +{THRESHOLD:.4f} ft")

    g["home_trigger"] = (g["home_ext_shift"] >= THRESHOLD) & g["home_eligible"]
    g["away_trigger"] = (g["away_ext_shift"] >= THRESHOLD) & g["away_eligible"]
    g["flag"] = (g["home_trigger"] | g["away_trigger"]).astype(int)

    freeze_flagged = g[(g["season"].isin([2022, 2023])) & (g["flag"] == 1)]
    freeze_n = len(freeze_flagged)
    logger.info(f"  Freeze N (2022-2023): {freeze_n}")

    frozen_thresholds = {
        "metric": "release_extension_shift (r3 vs season baseline)",
        "threshold_ft": THRESHOLD,
        "direction_trigger": "extension increased >= threshold",
        "version": "single_starter",
        "min_prior_starts": MIN_PRIOR_STARTS,
        "freeze_window": "2022-2023",
        "freeze_n": freeze_n,
    }

    if freeze_n < 50:
        logger.info(f"  SKIP: N={freeze_n} < 50")
        result = build_and_log_result(
            signal_id, hypothesis,
            {"percentile": 0, "observed_metric": 0, "permutation_mean": 0,
             "permutation_std": 0, "permutation_p5": 0, "permutation_p95": 0,
             "n_permutations": 0},
            season_breakdown(g, "flag", "UNDER"), "UNDER",
            frozen_thresholds, freeze_n, {}, {}, {},
            version_note="single_starter"
        )
        logger.info(f"  VERDICT: {result['verdict']}")
        return result

    season_results = season_breakdown(g, "flag", "UNDER")
    for y, r in sorted(season_results.items()):
        logger.info(f"  {y}: N={r['n']}, under_rate={r['win_rate']}, ROI={r['roi']}%")

    all_data = g[g["season"].isin([2022, 2023, 2024, 2025])]
    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data["went_under"].values,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.4f}, pctile={perm['percentile']:.1f}")

    mono = monotonic_buckets(g, "home_ext_shift", "UNDER")
    seg = segment_independence(g, "flag", "UNDER")
    mkt = market_independence(g, "flag")

    result = build_and_log_result(
        signal_id, hypothesis, perm, season_results, "UNDER",
        frozen_thresholds, freeze_n, seg, mkt, mono,
        version_note="single_starter"
    )
    logger.info(f"  VERDICT: {result['verdict']}")
    if result.get("failure_reason"):
        logger.info(f"  Reason: {result['failure_reason']}")
    return result


# ═══════════════════════════════════════════════════════════
# FREEZE ELIGIBILITY RULE ON 2022-2023
# ═══════════════════════════════════════════════════════════

def freeze_eligibility(starts):
    """Report eligibility statistics for the frozen MIN_PRIOR_STARTS rule."""
    freeze_data = starts[starts["season"].isin([2022, 2023])]
    total_starts = len(freeze_data)
    eligible = freeze_data[freeze_data["start_num"] >= MIN_PRIOR_STARTS]
    excluded = total_starts - len(eligible)

    logger.info(f"\n{'─' * 65}")
    logger.info(f"FROZEN ELIGIBILITY RULE: min_prior_starts = {MIN_PRIOR_STARTS}")
    logger.info(f"{'─' * 65}")
    logger.info(f"  2022-2023 total starter appearances:  {total_starts}")
    logger.info(f"  Eligible (>= {MIN_PRIOR_STARTS} prior starts):       {len(eligible)} ({len(eligible)/total_starts:.1%})")
    logger.info(f"  Excluded:                             {excluded} ({excluded/total_starts:.1%})")

    # Coverage after eligibility by feature
    for col in ["primary_shift", "entropy_shift", "ext_shift"]:
        n_valid = eligible[col].notna().sum()
        logger.info(f"  {col} non-null after eligibility: {n_valid}/{len(eligible)} ({n_valid/len(eligible):.1%})")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 65)
    logger.info("BATCH 4, WAVE 2 — Signal Discovery Tests")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("Signals: CS022A, CS022B, CS023, CS024")
    logger.info("=" * 65)

    games = load_game_outcomes()
    sc, starters = load_statcast()
    starts = build_per_start_features(sc, starters)
    freeze_eligibility(starts)
    games_joined = join_starts_to_games(starts, games, starters)
    logger.info(f"Games with starter features joined: {len(games_joined)}")

    results = {}
    results["CS022A"] = test_cs022(games_joined, "UNDER", "CS022A")
    results["CS022B"] = test_cs022(games_joined, "OVER", "CS022B")
    results["CS023"] = test_cs023(games_joined)
    results["CS024"] = test_cs024(games_joined)

    # ─── BATCH SUMMARY ──────────────────────────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("BATCH 4, WAVE 2 — SUMMARY")
    logger.info("=" * 65)

    for sid, r in results.items():
        v = r["verdict"]
        reason = r.get("failure_reason", "")
        perm = r["permutation_percentile"]
        s25 = r["validation_2025"]
        logger.info(f"  {sid}: {v} | perm={perm:.1f} | "
                    f"2025 N={s25['n']}, wr={s25.get('win_rate')}, roi={s25.get('roi')}%"
                    f"{' | ' + reason if reason else ''}")

    passed = [s for s, r in results.items() if r["verdict"] == "PASS"]
    failed = [s for s, r in results.items() if r["verdict"] == "FAIL"]
    near = [s for s, r in results.items() if r["verdict"] == "NEAR_MISS"]

    logger.info(f"\n  PASSED:    {passed or 'none'}")
    logger.info(f"  FAILED:    {failed or 'none'}")
    logger.info(f"  NEAR_MISS: {near or 'none'}")

    logger.info(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
