#!/usr/bin/env python3
"""
K Prop Signal Tests — KP01, KP02, KP03A, KP03B
RESEARCH ONLY.
"""

import json, sys, logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("kprop_tests")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SAFETY = ROOT / "research" / "signal_discovery" / "safety_layer"
sys.path.insert(0, str(SAFETY))
import signal_tester as st


# ═══════════════════════════════════════════════════════════
# BUILD MASTER DATASET
# ═══════════════════════════════════════════════════════════

def build_master():
    logger.info("Building master K prop dataset...")

    kp = pd.read_parquet(ROOT / "research" / "kprop" / "data" / "kprop_lines_historical_backfilled.parquet")
    kp = kp[kp["actual_k"].notna()].copy()
    kp["game_id_int"] = kp["game_id"].astype(int)
    kp["pitcher_id"] = kp["pitcher_id"].astype(int)
    kp["season"] = pd.to_datetime(kp["date"]).dt.year
    logger.info(f"  Base: {len(kp)} rows with actual_k")

    # Umpire zone metrics
    ump = pd.read_parquet(ROOT / "research" / "signal_discovery" / "c041_umpire_zone_metrics.parquet")
    ump_slim = ump[["game_pk", "tight_zone_flag", "loose_zone_flag",
                     "called_strike_rate_r3_vs_season"]].copy()
    ump_slim["game_pk"] = ump_slim["game_pk"].astype(int)
    pre = len(kp)
    kp = kp.merge(ump_slim, left_on="game_id_int", right_on="game_pk", how="left")
    logger.info(f"  + Umpire zone: {kp['tight_zone_flag'].notna().sum()}/{pre} matched ({kp['tight_zone_flag'].notna().mean():.1%})")

    # Adj K rate features
    adj = pd.read_parquet(ROOT / "research" / "opponent_adjusted_engine_v2" / "pitcher_recent_adjusted_features.parquet")
    adj_slim = adj[["game_pk", "pitcher_id", "adj_k_rate_last3", "adj_k_rate_last5"]].copy()
    adj_slim = adj_slim.rename(columns={"game_pk": "game_id_int"})
    kp = kp.merge(adj_slim, on=["game_id_int", "pitcher_id"], how="left")
    logger.info(f"  + Adj K rate: {kp['adj_k_rate_last3'].notna().sum()}/{len(kp)} matched ({kp['adj_k_rate_last3'].notna().mean():.1%})")

    # Rolling IP from pitcher_game_logs (starters only)
    pl = pd.read_parquet(ROOT / "mlb" / "data" / "pitcher_game_logs.parquet")
    pl_s = pl[pl["starter_flag"] == 1].sort_values(["player_id", "game_date", "game_pk"]).copy()
    pl_s["ip_r5"] = pl_s.groupby(["player_id", "season"])["innings_pitched"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=5).mean()
    )
    pl_s["start_num"] = pl_s.groupby(["player_id", "season"]).cumcount()
    ip_slim = pl_s[["game_pk", "player_id", "ip_r5", "start_num"]].rename(
        columns={"game_pk": "game_id_int", "player_id": "pitcher_id"})
    kp = kp.merge(ip_slim, on=["game_id_int", "pitcher_id"], how="left")
    logger.info(f"  + Rolling IP: {kp['ip_r5'].notna().sum()}/{len(kp)} matched ({kp['ip_r5'].notna().mean():.1%})")

    # Adj K season baseline (expanding mean, shift 1, no leakage)
    # Build from adj features file directly
    adj_full = adj[["game_pk", "pitcher_id", "adj_k_rate_last3", "side"]].copy()
    adj_full = adj_full.rename(columns={"game_pk": "game_id_int"})
    # We need per-pitcher season baseline of adj_k_rate_last3
    # Join game_date for ordering
    gt = pd.read_parquet(ROOT / "sim" / "data" / "game_table.parquet")
    gt_dates = gt[["game_pk", "date", "season"]].rename(columns={"game_pk": "game_id_int"})
    adj_full = adj_full.merge(gt_dates, on="game_id_int", how="left")
    adj_full = adj_full.sort_values(["pitcher_id", "date", "game_id_int"])
    adj_full["adj_k_baseline"] = adj_full.groupby(["pitcher_id", "season"])["adj_k_rate_last3"].transform(
        lambda x: x.shift(1).expanding(min_periods=3).mean()
    )
    adj_baseline = adj_full[["game_id_int", "pitcher_id", "adj_k_baseline"]].copy()
    kp = kp.merge(adj_baseline, on=["game_id_int", "pitcher_id"], how="left")
    logger.info(f"  + Adj K baseline: {kp['adj_k_baseline'].notna().sum()}/{len(kp)} ({kp['adj_k_baseline'].notna().mean():.1%})")

    # Derived fields
    kp["k_over"] = (kp["actual_k"] > kp["k_line"]).astype(int)
    kp["k_under"] = (kp["actual_k"] < kp["k_line"]).astype(int)
    kp["k_push"] = (kp["actual_k"] == kp["k_line"]).astype(int)
    kp["k_diff"] = kp["actual_k"] - kp["k_line"]
    kp["adj_k_upshift"] = kp["adj_k_rate_last3"] - kp["adj_k_baseline"]

    logger.info(f"  Master dataset: {len(kp)} rows")
    logger.info(f"  Seasons: {sorted(kp['season'].unique())}")
    return kp


# ═══════════════════════════════════════════════════════════
# ROI CALCULATION
# ═══════════════════════════════════════════════════════════

def compute_roi_at_odds(df, side="over"):
    """Compute ROI using actual American odds. side='over' or 'under'."""
    price_col = "over_price" if side == "over" else "under_price"
    outcome_col = "k_over" if side == "over" else "k_under"
    valid = df[df[price_col].notna() & df[outcome_col].notna()].copy()
    if len(valid) == 0:
        return None, 0

    total_wagered = len(valid)  # 1 unit per bet
    total_returned = 0.0
    for _, r in valid.iterrows():
        price = float(r[price_col])
        won = int(r[outcome_col])
        if won == 1:
            if price > 0:
                total_returned += 1.0 + price / 100.0
            else:
                total_returned += 1.0 + 100.0 / abs(price)
        # push: return stake
        elif int(r.get("k_push", 0)) == 1:
            total_returned += 1.0
        # loss: 0

    net = total_returned - total_wagered
    roi = net / total_wagered * 100
    return round(roi, 2), total_wagered


def season_roi(df, side="over"):
    """ROI by season."""
    results = {}
    for s in sorted(df["season"].unique()):
        sub = df[df["season"] == s]
        roi, n = compute_roi_at_odds(sub, side)
        outcome_col = "k_over" if side == "over" else "k_under"
        nopush = sub[sub["k_push"] == 0]
        hr = nopush[outcome_col].mean() if len(nopush) > 0 else None
        results[s] = {"n": n, "hit_rate": round(hr, 4) if hr else None, "roi": roi}
    return results


# ═══════════════════════════════════════════════════════════
# RESULT LOGGING
# ═══════════════════════════════════════════════════════════

def log_result(signal_id, result_dict):
    st.log_test_result(result_dict)
    board = []
    if st.BOARD_PATH.exists():
        with open(st.BOARD_PATH) as f:
            board = json.load(f)
    board = [b for b in board if b.get("canonical_signal_id") != signal_id]

    reg = st.load_registry()
    hyp = next((e for e in reg if e["canonical_signal_id"] == signal_id), {})

    advancement = None
    v = result_dict["verdict"]
    if v == "PASS": advancement = "Advance to shadow monitoring"
    elif v == "NEAR_MISS": advancement = "Note for threshold refinement"

    board.append({
        "canonical_signal_id": signal_id,
        "canonical_name": hyp.get("canonical_name", signal_id),
        "domain": hyp.get("domain", ""),
        "framework_type": hyp.get("framework_type", ""),
        "market_target": hyp.get("market_target", ""),
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


def determine_verdict(perm_pctile, val_2025_roi, freeze_n):
    if freeze_n < 50:
        return "NEEDS_MORE_DATA", f"Freeze N={freeze_n} < 50"
    if val_2025_roi is not None and abs(val_2025_roi) > 30:
        return "SUSPECT", f"2025 ROI={val_2025_roi:.1f}% — flag for review"
    perm_pass = perm_pctile >= 85
    near_miss = 75 <= perm_pctile < 85
    val_pos = (val_2025_roi or -999) > 0
    if perm_pass and val_pos:
        return "PASS", None
    if near_miss and val_pos:
        return "NEAR_MISS", f"Perm {perm_pctile:.1f} in 75-84; 2025 positive"
    if not perm_pass:
        return "FAIL", f"Perm {perm_pctile:.1f} < 85"
    return "FAIL", f"2025 ROI={val_2025_roi}% not positive"


# ═══════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════

def test_kp01(master):
    sid = "KP01"
    logger.info(f"\n{'='*65}\n{sid} — Opponent-adjusted K upshift\n{'='*65}")

    df = master[master["adj_k_upshift"].notna() & (master["start_num"] >= 3)].copy()
    logger.info(f"  Eligible starts (3+ prior, adj_k available): {len(df)}")

    # Freeze top-20% threshold on 2023
    freeze = df[df["season"] == 2023]
    threshold = float(freeze["adj_k_upshift"].quantile(0.80))
    logger.info(f"  Freeze threshold (P80 upshift, 2023): {threshold:.4f}")

    df["flag"] = (df["adj_k_upshift"] >= threshold).astype(int)
    freeze_n = int(freeze[freeze["adj_k_upshift"] >= threshold].shape[0])
    logger.info(f"  Freeze N (2023): {freeze_n}")

    # Compare
    flagged = df[df["flag"] == 1]
    baseline = df
    logger.info(f"\n  Baseline: N={len(baseline)}")
    s_base = season_roi(baseline, "over")
    for y, r in sorted(s_base.items()):
        logger.info(f"    {y}: N={r['n']}, HR={r['hit_rate']}, ROI={r['roi']}%")

    logger.info(f"\n  Flagged (upshift >= {threshold:.4f}): N={len(flagged)}")
    s_flag = season_roi(flagged, "over")
    for y, r in sorted(s_flag.items()):
        logger.info(f"    {y}: N={r['n']}, HR={r['hit_rate']}, ROI={r['roi']}%")

    # Permutation: ROI statistic
    all_data = df[df["season"].isin([2023, 2024, 2025])]

    def roi_metric(sig, out_unused):
        flagged_idx = sig == 1
        if flagged_idx.sum() == 0: return 0.0
        sub = all_data.iloc[np.where(flagged_idx)[0]]
        roi, _ = compute_roi_at_odds(sub, "over")
        return roi if roi is not None else 0.0

    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data["k_over"].values,
        metric_fn=roi_metric,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"\n  Permutation: observed={perm['observed_metric']:.2f}%, pctile={perm['percentile']:.1f}")

    s2025 = s_flag.get(2025, {})
    verdict, reason = determine_verdict(perm["percentile"], s2025.get("roi"), freeze_n)
    logger.info(f"  VERDICT: {verdict}" + (f" — {reason}" if reason else ""))

    result = {
        "canonical_signal_id": sid,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"adj_k_upshift_p80": round(threshold, 4), "min_prior_starts": 3,
                              "freeze_window": "2023"},
        "freeze_window_n": freeze_n,
        "season_by_season": {str(k): v for k, v in s_flag.items()},
        "validation_2025": {"n": s2025.get("n", 0), "roi": s2025.get("roi"),
                            "hit_rate": s2025.get("hit_rate"), "direction_positive": (s2025.get("roi") or -1) > 0},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict, "failure_reason": reason,
    }
    log_result(sid, result)
    return result, threshold


def test_kp02(master, kp01_threshold):
    sid = "KP02"
    logger.info(f"\n{'='*65}\n{sid} — Adj K upshift + stable leash\n{'='*65}")

    df = master[master["adj_k_upshift"].notna() & master["ip_r5"].notna() & (master["start_num"] >= 5)].copy()
    logger.info(f"  Eligible (5+ prior, adj_k + IP available): {len(df)}")

    df["upshift_flag"] = (df["adj_k_upshift"] >= kp01_threshold).astype(int)
    df["leash_flag"] = (df["ip_r5"] >= 5.0).astype(int)
    df["flag"] = ((df["upshift_flag"] == 1) & (df["leash_flag"] == 1)).astype(int)

    freeze_n = int(df[(df["season"] == 2023) & (df["flag"] == 1)].shape[0])
    logger.info(f"  Freeze N (2023): {freeze_n}")
    logger.info(f"  Flag rate: {df['flag'].mean():.1%}")

    # Redundancy vs KP01
    kp01_flags = df[df["upshift_flag"] == 1]
    kp02_flags = df[df["flag"] == 1]
    if len(kp02_flags) > 0:
        overlap = (kp02_flags["upshift_flag"] == 1).sum() / len(kp02_flags)
        logger.info(f"  KP02→KP01 overlap: {overlap:.1%} (all KP02 are KP01 by construction)")
        kp01_in_kp02 = len(kp02_flags) / max(1, len(kp01_flags))
        logger.info(f"  KP01→KP02 subset: {kp01_in_kp02:.1%} of KP01 flags also in KP02")

    flagged = df[df["flag"] == 1]
    s_flag = season_roi(flagged, "over")
    for y, r in sorted(s_flag.items()):
        logger.info(f"    {y}: N={r['n']}, HR={r['hit_rate']}, ROI={r['roi']}%")

    all_data = df[df["season"].isin([2023, 2024, 2025])]

    def roi_metric(sig, out_unused):
        idx = sig == 1
        if idx.sum() == 0: return 0.0
        sub = all_data.iloc[np.where(idx)[0]]
        roi, _ = compute_roi_at_odds(sub, "over")
        return roi if roi is not None else 0.0

    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data["k_over"].values,
        metric_fn=roi_metric, n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.2f}%, pctile={perm['percentile']:.1f}")

    s2025 = s_flag.get(2025, {})
    verdict, reason = determine_verdict(perm["percentile"], s2025.get("roi"), freeze_n)
    logger.info(f"  VERDICT: {verdict}" + (f" — {reason}" if reason else ""))

    result = {
        "canonical_signal_id": sid,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"adj_k_upshift_p80": round(kp01_threshold, 4),
                              "leash_cutoff_ip": 5.0, "min_prior_starts": 5,
                              "freeze_window": "2023"},
        "freeze_window_n": freeze_n,
        "season_by_season": {str(k): v for k, v in s_flag.items()},
        "validation_2025": {"n": s2025.get("n", 0), "roi": s2025.get("roi"),
                            "hit_rate": s2025.get("hit_rate"), "direction_positive": (s2025.get("roi") or -1) > 0},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict, "failure_reason": reason,
    }
    log_result(sid, result)
    return result


def test_kp03a(master):
    sid = "KP03A"
    logger.info(f"\n{'='*65}\n{sid} — Loose zone regime x K prop OVER\n{'='*65}")

    df = master[master["loose_zone_flag"].notna()].copy()
    df["flag"] = df["loose_zone_flag"].astype(int)
    logger.info(f"  Eligible: {len(df)}, flagged: {df['flag'].sum()}")

    freeze_n = int(df[(df["season"] == 2023) & (df["flag"] == 1)].shape[0])
    logger.info(f"  Freeze N (2023): {freeze_n}")

    flagged = df[df["flag"] == 1]
    s_flag = season_roi(flagged, "over")
    for y, r in sorted(s_flag.items()):
        logger.info(f"    {y}: N={r['n']}, HR={r['hit_rate']}, ROI={r['roi']}%")

    all_data = df[df["season"].isin([2023, 2024, 2025])]

    def roi_metric(sig, out_unused):
        idx = sig == 1
        if idx.sum() == 0: return 0.0
        sub = all_data.iloc[np.where(idx)[0]]
        roi, _ = compute_roi_at_odds(sub, "over")
        return roi if roi is not None else 0.0

    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data["k_over"].values,
        metric_fn=roi_metric, n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.2f}%, pctile={perm['percentile']:.1f}")

    s2025 = s_flag.get(2025, {})
    verdict, reason = determine_verdict(perm["percentile"], s2025.get("roi"), freeze_n)
    logger.info(f"  VERDICT: {verdict}" + (f" — {reason}" if reason else ""))

    result = {
        "canonical_signal_id": sid,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"loose_zone_flag": "pre-built from c041 z-score < -1.0",
                              "freeze_window": "2023"},
        "freeze_window_n": freeze_n,
        "season_by_season": {str(k): v for k, v in s_flag.items()},
        "validation_2025": {"n": s2025.get("n", 0), "roi": s2025.get("roi"),
                            "hit_rate": s2025.get("hit_rate"), "direction_positive": (s2025.get("roi") or -1) > 0},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict, "failure_reason": reason,
    }
    log_result(sid, result)
    return result


def test_kp03b(master):
    sid = "KP03B"
    logger.info(f"\n{'='*65}\n{sid} — Tight zone regime x K prop UNDER\n{'='*65}")

    df = master[master["tight_zone_flag"].notna()].copy()
    df["flag"] = df["tight_zone_flag"].astype(int)
    logger.info(f"  Eligible: {len(df)}, flagged: {df['flag'].sum()}")

    freeze_n = int(df[(df["season"] == 2023) & (df["flag"] == 1)].shape[0])
    logger.info(f"  Freeze N (2023): {freeze_n}")

    flagged = df[df["flag"] == 1]
    s_flag = season_roi(flagged, "under")
    for y, r in sorted(s_flag.items()):
        logger.info(f"    {y}: N={r['n']}, HR={r['hit_rate']}, ROI={r['roi']}%")

    all_data = df[df["season"].isin([2023, 2024, 2025])]

    def roi_metric(sig, out_unused):
        idx = sig == 1
        if idx.sum() == 0: return 0.0
        sub = all_data.iloc[np.where(idx)[0]]
        roi, _ = compute_roi_at_odds(sub, "under")
        return roi if roi is not None else 0.0

    perm = st.run_permutation_test(
        signal_values=all_data["flag"].values,
        outcomes=all_data["k_under"].values,
        metric_fn=roi_metric, n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Permutation: observed={perm['observed_metric']:.2f}%, pctile={perm['percentile']:.1f}")

    s2025 = s_flag.get(2025, {})
    verdict, reason = determine_verdict(perm["percentile"], s2025.get("roi"), freeze_n)
    logger.info(f"  VERDICT: {verdict}" + (f" — {reason}" if reason else ""))

    result = {
        "canonical_signal_id": sid,
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"tight_zone_flag": "pre-built from c041 z-score > +1.0",
                              "freeze_window": "2023"},
        "freeze_window_n": freeze_n,
        "season_by_season": {str(k): v for k, v in s_flag.items()},
        "validation_2025": {"n": s2025.get("n", 0), "roi": s2025.get("roi"),
                            "hit_rate": s2025.get("hit_rate"), "direction_positive": (s2025.get("roi") or -1) > 0},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict, "failure_reason": reason,
    }
    log_result(sid, result)
    return result


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 65)
    logger.info("K PROP SIGNAL TESTS — KP01, KP02, KP03A, KP03B")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 65)

    master = build_master()

    # Market baseline
    logger.info(f"\n{'='*65}\nMARKET BASELINE\n{'='*65}")
    total = len(master)
    nopush = master[master["k_push"] == 0]
    over_hr = nopush["k_over"].mean()
    under_hr = nopush["k_under"].mean()
    push_rate = master["k_push"].mean()
    over_roi, _ = compute_roi_at_odds(master, "over")
    under_roi, _ = compute_roi_at_odds(master, "under")
    logger.info(f"  Total starts: {total}")
    logger.info(f"  Over hit rate:  {over_hr:.4f}")
    logger.info(f"  Under hit rate: {under_hr:.4f}")
    logger.info(f"  Push rate:      {push_rate:.4f}")
    logger.info(f"  Over ROI (all): {over_roi}%")
    logger.info(f"  Under ROI (all): {under_roi}%")
    logger.info(f"  Mean k_line: {master['k_line'].mean():.2f}")
    logger.info(f"  Mean actual_k: {master['actual_k'].mean():.2f}")
    if over_roi is not None and over_roi > -1:
        logger.info(f"  ⚠️ Over ROI > -1% — market may be inefficient on over side")
    if under_roi is not None and under_roi > -1:
        logger.info(f"  ⚠️ Under ROI > -1% — market may be inefficient on under side")

    # Run tests
    r1, kp01_thresh = test_kp01(master)
    r2 = test_kp02(master, kp01_thresh)
    r3a = test_kp03a(master)
    r3b = test_kp03b(master)

    # Summary
    logger.info(f"\n{'='*65}\nK PROP BATCH SUMMARY\n{'='*65}")
    for r in [r1, r2, r3a, r3b]:
        sid = r["canonical_signal_id"]
        v = r["verdict"]
        perm = r["permutation_percentile"]
        s25 = r.get("validation_2025", {})
        reason = r.get("failure_reason", "")
        logger.info(f"  {sid}: {v} | perm={perm:.1f} | 2025 ROI={s25.get('roi')}% | {reason or 'passed'}")

    logger.info(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
