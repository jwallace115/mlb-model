#!/usr/bin/env python3
"""
Signal Discovery Safety Layer — Test Execution Framework

Enforces statistical discipline on every signal test:
- Pre-registration required before any data is seen
- Frozen thresholds cannot be changed after registration
- Mandatory permutation testing (500 shuffles minimum)
- 2025 is binding out-of-sample validation
- 2026 is holdout — never touched during testing
- Post-hoc tuning detection

RESEARCH ONLY — does not modify production files.
"""

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger("signal_tester")

BASE = Path(__file__).resolve().parent
REGISTRY_PATH = BASE / "hypothesis_registry.json"
RESULTS_LOG_PATH = BASE / "test_results_log.json"
BOARD_PATH = BASE / "signal_board.json"

TRAIN_SEASONS = [2022, 2023, 2024]
VALIDATION_SEASON_INSAMPLE = 2024  # directional support only
VALIDATION_SEASON_OOS = 2025       # binding out-of-sample
HOLDOUT_SEASON = 2026              # never touch during testing


# ═══════════════════════════════════════════════════════════
# A. PRE-REGISTRATION CHECK
# ═══════════════════════════════════════════════════════════

def load_registry():
    """Load all registered hypotheses."""
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Hypothesis registry not found at {REGISTRY_PATH}")
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def get_registered_hypothesis(canonical_signal_id):
    """
    Look up a registered hypothesis by canonical_signal_id.
    Raises ValueError if not registered.
    """
    registry = load_registry()
    for entry in registry:
        if entry["canonical_signal_id"] == canonical_signal_id:
            if entry.get("status") not in ("REGISTERED", "TESTED"):
                raise ValueError(
                    f"Signal {canonical_signal_id} has status '{entry.get('status')}' — "
                    f"cannot re-test a signal with status PASS/FAIL/INVALID"
                )
            return entry
    raise ValueError(
        f"Signal {canonical_signal_id} is NOT registered in hypothesis_registry.json. "
        f"Pre-registration is REQUIRED before any data examination. "
        f"Register the hypothesis first, then re-run."
    )


def _hash_thresholds(thresholds):
    """Deterministic hash of frozen thresholds for tamper detection."""
    canonical = json.dumps(thresholds, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════
# B. TRAIN / VALIDATION SPLIT ENFORCEMENT
# ═══════════════════════════════════════════════════════════

def enforce_split(df, season_col="season"):
    """
    Split a DataFrame into train, validation_insample, validation_oos.
    Raises if holdout season (2026) data is present.

    Returns: (train_df, val_2024_df, val_2025_df)
    """
    seasons_present = set(df[season_col].unique())

    if HOLDOUT_SEASON in seasons_present:
        raise RuntimeError(
            f"HOLDOUT SEASON {HOLDOUT_SEASON} detected in data. "
            f"Remove {HOLDOUT_SEASON} data before running signal tests. "
            f"Holdout must NEVER be touched during testing."
        )

    train = df[df[season_col].isin(TRAIN_SEASONS)].copy()
    val_2024 = df[df[season_col] == VALIDATION_SEASON_INSAMPLE].copy()
    val_2025 = df[df[season_col] == VALIDATION_SEASON_OOS].copy()

    logger.info(f"  Split: train={len(train)} (2022-2024), "
                f"val_2024={len(val_2024)}, val_2025={len(val_2025)}")

    if len(val_2025) == 0:
        raise RuntimeError(
            f"No {VALIDATION_SEASON_OOS} data found. "
            f"Binding validation season is required."
        )

    return train, val_2024, val_2025


def check_leakage(feature_construction_seasons, label="feature"):
    """
    Warn if feature construction uses validation data.
    Call this when building features to verify no look-ahead.
    """
    if VALIDATION_SEASON_OOS in feature_construction_seasons:
        logger.warning(
            f"⚠️  LEAKAGE WARNING: {label} construction includes "
            f"{VALIDATION_SEASON_OOS} data. Features must be built "
            f"on train seasons only ({TRAIN_SEASONS})."
        )
        return True
    if HOLDOUT_SEASON in feature_construction_seasons:
        raise RuntimeError(
            f"CRITICAL: {label} construction includes holdout season "
            f"{HOLDOUT_SEASON}. This is forbidden."
        )
    return False


# ═══════════════════════════════════════════════════════════
# C. PERMUTATION TEST
# ═══════════════════════════════════════════════════════════

def run_permutation_test(signal_values, outcomes, metric_fn, n_permutations=500,
                         season_labels=None, parent_mask=None, rng_seed=42):
    """
    Mandatory permutation test.

    Args:
        signal_values: array of signal values (e.g., favorable zone flags)
        outcomes: array of outcomes (e.g., went_under flags)
        metric_fn: callable(signal_values, outcomes) -> float
            The metric to test (e.g., under_rate in favorable zone)
        n_permutations: minimum 500
        season_labels: if provided, shuffle within each season independently
        parent_mask: boolean array, same length as signal_values. When provided
            (for overlay/subset signals with a parent_signal), shuffling is
            restricted to rows where parent_mask == True. Rows outside the
            parent population keep their original signal value (always 0).
            This ensures overlay tests measure lift within the parent signal
            population, not against all games.
        rng_seed: for reproducibility

    Returns:
        dict with observed_metric, permutation_distribution, percentile
    """
    if n_permutations < 500:
        raise ValueError("Minimum 500 permutations required by safety protocol")

    rng = np.random.default_rng(rng_seed)
    observed = metric_fn(signal_values, outcomes)

    perm_results = []
    for _ in range(n_permutations):
        shuffled = signal_values.copy()

        if parent_mask is not None and season_labels is not None:
            # Overlay signal: shuffle within parent population × season
            for season in np.unique(season_labels):
                mask = (season_labels == season) & parent_mask
                subset = shuffled[mask]
                rng.shuffle(subset)
                shuffled[mask] = subset
        elif parent_mask is not None:
            # Overlay signal without season stratification
            subset = shuffled[parent_mask]
            rng.shuffle(subset)
            shuffled[parent_mask] = subset
        elif season_labels is not None:
            # Standard: shuffle within each season independently
            for season in np.unique(season_labels):
                mask = season_labels == season
                season_vals = shuffled[mask]
                rng.shuffle(season_vals)
                shuffled[mask] = season_vals
        else:
            rng.shuffle(shuffled)

        perm_results.append(metric_fn(shuffled, outcomes))

    perm_array = np.array(perm_results)
    percentile = (perm_array < observed).mean() * 100

    return {
        "observed_metric": round(float(observed), 6),
        "permutation_mean": round(float(perm_array.mean()), 6),
        "permutation_std": round(float(perm_array.std()), 6),
        "permutation_p5": round(float(np.percentile(perm_array, 5)), 6),
        "permutation_p95": round(float(np.percentile(perm_array, 95)), 6),
        "percentile": round(float(percentile), 1),
        "n_permutations": n_permutations,
        "parent_scoped": parent_mask is not None,
    }


# ═══════════════════════════════════════════════════════════
# D. SEASON SUPPORT CHECK
# ═══════════════════════════════════════════════════════════

def check_season_support(val_2024_positive, val_2025_positive):
    """
    Evaluate season support gate.

    2024: in-sample stability check only (not binding)
    2025: binding out-of-sample validation

    Returns: (pass_flag, verdict_note)
    """
    if val_2025_positive and val_2024_positive:
        return True, "Both 2024 and 2025 directionally positive"
    elif val_2025_positive and not val_2024_positive:
        return False, "INVESTIGATE: 2025 positive but 2024 negative — unstable"
    elif not val_2025_positive and val_2024_positive:
        return False, "FAIL: 2024 positive but 2025 negative — does not validate OOS"
    else:
        return False, "FAIL: Neither 2024 nor 2025 directionally positive"


# ═══════════════════════════════════════════════════════════
# E. EFFECT SIZE REALITY CHECKS
# ═══════════════════════════════════════════════════════════

def check_suspect_flags(n, roi, under_rate=None):
    """
    Flag suspicious results that likely indicate data error or leakage.
    Returns list of flag strings.
    """
    flags = []
    if roi is not None and abs(roi) > 30:
        flags.append("SUSPECT_ROI: ROI > 30% — likely data error or look-ahead leak")
    if n < 50:
        flags.append("THIN_SAMPLE: N < 50 — insufficient for reliable inference")
    if n < 30:
        flags.append("CRITICALLY_THIN: N < 30 — results are noise")
    if under_rate is not None and (under_rate > 0.70 or under_rate < 0.30):
        flags.append("EXTREME_RATE: under_rate outside [0.30, 0.70] — check data quality")
    return flags


# ═══════════════════════════════════════════════════════════
# F. POST-HOC TUNING DETECTION
# ═══════════════════════════════════════════════════════════

def verify_thresholds(canonical_signal_id, used_thresholds):
    """
    Compare thresholds used in the test against registered thresholds.
    Returns (match_flag, detail_note).
    """
    hypothesis = get_registered_hypothesis(canonical_signal_id)
    registered = hypothesis["frozen_thresholds"]
    registered_hash = _hash_thresholds(registered)
    used_hash = _hash_thresholds(used_thresholds)

    if registered_hash != used_hash:
        # Identify which thresholds changed
        changes = []
        for key in registered:
            if registered.get(key) != used_thresholds.get(key):
                changes.append(f"{key}: registered={registered[key]} → used={used_thresholds[key]}")
        detail = f"TAMPER WARNING: Thresholds changed after registration. Changes: {'; '.join(changes)}"
        logger.warning(f"⚠️  {detail}")
        return False, detail

    return True, "Thresholds match registered values"


# ═══════════════════════════════════════════════════════════
# G. RESULTS LOGGER
# ═══════════════════════════════════════════════════════════

def log_test_result(result):
    """
    Append a test result to test_results_log.json.
    Deduplicates by canonical_signal_id (keeps latest).
    """
    results = []
    if RESULTS_LOG_PATH.exists():
        try:
            with open(RESULTS_LOG_PATH) as f:
                results = json.load(f)
        except (json.JSONDecodeError, Exception):
            results = []

    # Remove prior result for same signal
    cid = result.get("canonical_signal_id")
    results = [r for r in results if r.get("canonical_signal_id") != cid]
    results.append(result)

    def _serialize(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    with open(RESULTS_LOG_PATH, "w") as f:
        json.dump(results, f, indent=2, default=_serialize)

    logger.info(f"  Test result logged: {cid} → {result.get('verdict')}")
    return result


def update_board(canonical_signal_id, status, failure_reason=None, advancement_path=None):
    """
    Update signal_board.json with the test outcome.
    """
    hypothesis = get_registered_hypothesis(canonical_signal_id)

    board = []
    if BOARD_PATH.exists():
        try:
            with open(BOARD_PATH) as f:
                board = json.load(f)
        except (json.JSONDecodeError, Exception):
            board = []

    # Remove existing entry for this signal
    board = [b for b in board if b.get("canonical_signal_id") != canonical_signal_id]

    entry = {
        "canonical_signal_id": canonical_signal_id,
        "canonical_name": hypothesis["canonical_name"],
        "domain": hypothesis["domain"],
        "framework_type": hypothesis["framework_type"],
        "market_target": hypothesis["market_target"],
        "status": status,
        "failure_reason": failure_reason,
        "advancement_path": advancement_path,
        "last_updated": datetime.now().isoformat(),
    }
    board.append(entry)

    def _serialize(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    with open(BOARD_PATH, "w") as f:
        json.dump(board, f, indent=2, default=_serialize)

    return entry


# ═══════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════

def run_signal_test(canonical_signal_id, signal_values, outcomes,
                    metric_fn, season_labels,
                    used_thresholds=None,
                    n_permutations=500,
                    val_2024_metric=None, val_2024_positive=None,
                    val_2025_metric=None, val_2025_positive=None,
                    train_n=0, train_under_rate=None, train_roi=None, train_p_value=None,
                    val_2024_n=0, val_2024_under_rate=None, val_2024_roi=None,
                    val_2025_n=0, val_2025_under_rate=None, val_2025_roi=None):
    """
    Full signal test with all safety checks.

    This is the ONLY entry point for running tests.
    Enforces all gates in sequence.

    Returns: result dict with verdict.
    """
    # A. Pre-registration check
    hypothesis = get_registered_hypothesis(canonical_signal_id)
    registered_thresholds = hypothesis["frozen_thresholds"]
    logger.info(f"Testing {canonical_signal_id}: {hypothesis['canonical_name']}")

    # F. Threshold verification
    if used_thresholds is None:
        used_thresholds = registered_thresholds
    thresholds_match, threshold_note = verify_thresholds(canonical_signal_id, used_thresholds)

    if not thresholds_match:
        result = {
            "canonical_signal_id": canonical_signal_id,
            "test_date": datetime.now().isoformat(),
            "registered_hypothesis_used": True,
            "thresholds_match_registered": False,
            "threshold_tamper_note": threshold_note,
            "verdict": "INVALID",
        }
        log_test_result(result)
        update_board(canonical_signal_id, "INVALID",
                     failure_reason=threshold_note)
        return result

    # C. Permutation test
    perm_result = run_permutation_test(
        signal_values, outcomes, metric_fn,
        n_permutations=n_permutations,
        season_labels=season_labels,
    )

    # D. Season support
    season_pass, season_note = check_season_support(
        val_2024_positive if val_2024_positive is not None else False,
        val_2025_positive if val_2025_positive is not None else False,
    )

    # E. Suspect flags
    suspect_flags = []
    suspect_flags.extend(check_suspect_flags(train_n, train_roi, train_under_rate))
    suspect_flags.extend(check_suspect_flags(val_2025_n, val_2025_roi, val_2025_under_rate))

    # Determine verdict
    perm_pass = perm_result["percentile"] >= registered_thresholds["permutation_percentile"]
    n_pass = val_2025_n >= registered_thresholds["minimum_n"]

    if not thresholds_match:
        verdict = "INVALID"
        failure_reason = threshold_note
    elif not perm_pass:
        verdict = "FAIL"
        failure_reason = (f"Permutation percentile {perm_result['percentile']:.1f} < "
                          f"{registered_thresholds['permutation_percentile']} required")
    elif not season_pass and "FAIL" in season_note:
        verdict = "FAIL"
        failure_reason = season_note
    elif not season_pass and "INVESTIGATE" in season_note:
        verdict = "INVESTIGATE"
        failure_reason = season_note
    elif not n_pass:
        verdict = "INVESTIGATE"
        failure_reason = f"Validation N={val_2025_n} < minimum {registered_thresholds['minimum_n']}"
    else:
        verdict = "PASS"
        failure_reason = None

    advancement = None
    if verdict == "PASS":
        advancement = "Advance to shadow monitoring with pre-registered thresholds"
    elif verdict == "INVESTIGATE":
        advancement = "Shadow with caution — review noted concerns before promotion"

    result = {
        "canonical_signal_id": canonical_signal_id,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": thresholds_match,
        "train_result": {
            "n": train_n,
            "under_rate": train_under_rate,
            "roi": train_roi,
            "p_value": train_p_value,
        },
        "validation_2024": {
            "n": val_2024_n,
            "under_rate": val_2024_under_rate,
            "roi": val_2024_roi,
            "direction_positive": val_2024_positive,
            "note": "in-sample stability check only",
        },
        "validation_2025": {
            "n": val_2025_n,
            "under_rate": val_2025_under_rate,
            "roi": val_2025_roi,
            "direction_positive": val_2025_positive,
            "note": "binding out-of-sample validation",
        },
        "permutation_percentile": perm_result["percentile"],
        "permutation_detail": perm_result,
        "season_support_pass": season_pass,
        "season_support_note": season_note,
        "suspect_flags": suspect_flags,
        "verdict": verdict,
        "failure_reason": failure_reason,
    }

    log_test_result(result)
    update_board(canonical_signal_id, verdict,
                 failure_reason=failure_reason,
                 advancement_path=advancement)

    return result
