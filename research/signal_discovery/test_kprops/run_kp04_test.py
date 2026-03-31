#!/usr/bin/env python3
"""
KP04 — Breaking-ball pitcher x high-K lineup (K OVER)
Full safety-layer test.
RESEARCH ONLY.
"""

import json, sys, logging, glob
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("kp04")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SAFETY = ROOT / "research" / "signal_discovery" / "safety_layer"
sys.path.insert(0, str(SAFETY))
import signal_tester as st

PRICE_FLOOR = -150  # exclude over odds <= -150


def build_dataset():
    """Build master dataset with BB%, lineup K%, price floor applied."""
    kp = pd.read_parquet(ROOT / "research/kprop/data/kprop_lines_historical_backfilled.parquet")
    kp = kp[kp["actual_k"].notna()].copy()
    kp["game_id_int"] = kp["game_id"].astype(int)
    kp["pitcher_id"] = kp["pitcher_id"].astype(int)
    kp["season"] = pd.to_datetime(kp["date"]).dt.year
    kp["k_over"] = (kp["actual_k"] > kp["k_line"]).astype(int)
    kp["k_under"] = (kp["actual_k"] < kp["k_line"]).astype(int)
    kp["k_push"] = (kp["actual_k"] == kp["k_line"]).astype(int)
    kp["k_diff"] = kp["actual_k"] - kp["k_line"]

    # BB usage from Statcast
    sc_files = sorted(glob.glob(str(ROOT / "mlb/props/data/statcast_chunk_*.parquet")))
    dfs = []
    for f in sc_files:
        chunk = pd.read_parquet(f, columns=["game_pk", "pitcher", "game_year", "pitch_type",
                                              "game_type", "inning", "inning_topbot",
                                              "at_bat_number", "pitch_number"])
        chunk = chunk[chunk["game_type"] == "R"]
        dfs.append(chunk)
    sc_raw = pd.concat(dfs, ignore_index=True)
    sc_raw = sc_raw.sort_values(["game_pk", "inning", "inning_topbot", "at_bat_number", "pitch_number"])
    first = sc_raw.groupby(["game_pk", "inning_topbot"]).first().reset_index()
    starters = first[first["inning"] == 1][["game_pk", "inning_topbot", "pitcher"]].rename(
        columns={"pitcher": "starter_id"})
    sc_s = sc_raw.merge(starters, on=["game_pk", "inning_topbot"])
    sc_s = sc_s[sc_s["pitcher"] == sc_s["starter_id"]].copy()

    bb_types = {"SL", "CU", "KC", "CS", "ST", "SV"}
    sc_s["is_bb"] = sc_s["pitch_type"].isin(bb_types).astype(int)
    per_start = sc_s.groupby(["game_pk", "starter_id"]).agg(
        n_pitches=("pitch_type", "count"), n_bb=("is_bb", "sum")).reset_index()
    per_start["bb_pct"] = per_start["n_bb"] / per_start["n_pitches"]
    per_start = per_start.rename(columns={"game_pk": "game_id_int", "starter_id": "pitcher_id"})
    kp = kp.merge(per_start[["game_id_int", "pitcher_id", "bb_pct"]],
                   on=["game_id_int", "pitcher_id"], how="left")

    # Lineup K%
    lineups = pd.read_parquet(ROOT / "research/mlb_v3_lineup_model/historical_lineups_long.parquet")
    hp = pd.read_parquet(ROOT / "research/mlb_v3_lineup_model/hitter_rolling_profiles.parquet")
    lineup_k = lineups.merge(hp[["game_pk", "player_id", "hitter_k_rate_last20"]],
                              on=["game_pk", "player_id"], how="left")
    lineup_team_k = lineup_k.groupby(["game_pk", "team"]).agg(
        lineup_k_rate=("hitter_k_rate_last20", "mean"),
        lineup_n=("hitter_k_rate_last20", "count")).reset_index()
    lineup_team_k = lineup_team_k[lineup_team_k["lineup_n"] >= 7]

    # Map pitcher → team → opponent (kp already has home_team/away_team)
    pl = pd.read_parquet(ROOT / "mlb/data/pitcher_game_logs.parquet")
    pl_s = pl[pl["starter_flag"] == 1].copy()
    pl_team = pl_s[["game_pk", "player_id", "team"]].rename(
        columns={"game_pk": "game_id_int", "player_id": "pitcher_id", "team": "pitcher_team"})
    pl_team = pl_team.drop_duplicates(subset=["game_id_int", "pitcher_id"])
    kp = kp.merge(pl_team, on=["game_id_int", "pitcher_id"], how="left")
    kp["opponent"] = np.where(kp["pitcher_team"] == kp["home_team"], kp["away_team"], kp["home_team"])
    kp = kp.merge(lineup_team_k[["game_pk", "team", "lineup_k_rate"]].rename(
        columns={"game_pk": "game_id_int", "team": "opponent", "lineup_k_rate": "opp_lineup_k_rate"}),
        on=["game_id_int", "opponent"], how="left")

    # Start count for eligibility
    pl_s2 = pl_s.sort_values(["player_id", "game_date", "game_pk"]).copy()
    pl_s2["start_num"] = pl_s2.groupby(["player_id", "season"]).cumcount()
    kp = kp.merge(pl_s2[["game_pk", "player_id", "start_num"]].rename(
        columns={"game_pk": "game_id_int", "player_id": "pitcher_id"}),
        on=["game_id_int", "pitcher_id"], how="left")

    # Apply price floor
    pre_floor = len(kp)
    kp = kp[kp["over_price"].notna() & (kp["over_price"] > PRICE_FLOOR)].copy()
    logger.info(f"Price floor (>{PRICE_FLOOR}): {pre_floor} → {len(kp)} ({pre_floor - len(kp)} excluded)")

    logger.info(f"Dataset: {len(kp)} starts, BB% matched: {kp['bb_pct'].notna().mean():.1%}, "
                f"lineup K% matched: {kp['opp_lineup_k_rate'].notna().mean():.1%}")
    return kp


def compute_roi(df, side="over"):
    price_col = "over_price" if side == "over" else "under_price"
    outcome_col = "k_over" if side == "over" else "k_under"
    valid = df[df[price_col].notna()].copy()
    if len(valid) == 0:
        return None, 0
    wagered = len(valid)
    returned = 0.0
    for _, r in valid.iterrows():
        price = float(r[price_col])
        if int(r[outcome_col]) == 1:
            returned += 1.0 + (price / 100.0 if price > 0 else 100.0 / abs(price))
        elif int(r.get("k_push", 0)) == 1:
            returned += 1.0
    roi = round((returned - wagered) / wagered * 100, 2)
    return roi, wagered


def group_stats(df, label):
    n = len(df)
    nopush = df[df["k_push"] == 0]
    hr = nopush["k_over"].mean() if len(nopush) > 0 else None
    roi, _ = compute_roi(df, "over")
    k_err = df["k_diff"].mean() if n > 0 else None
    pushes = int(df["k_push"].sum())
    return {"label": label, "n": len(nopush), "hit_rate": round(hr, 4) if hr else None,
            "roi": roi, "k_err": round(k_err, 3) if k_err else None, "pushes": pushes}


def main():
    logger.info("=" * 65)
    logger.info("KP04 — Full Safety Layer Test")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 65)

    kp = build_dataset()

    # Freeze thresholds on 2023
    freeze = kp[kp["season"] == 2023]
    bb_q75 = float(freeze["bb_pct"].dropna().quantile(0.75))
    lineup_k_q75 = float(freeze["opp_lineup_k_rate"].dropna().quantile(0.75))
    logger.info(f"\nFrozen thresholds (2023):")
    logger.info(f"  BB% P75: {bb_q75:.4f}")
    logger.info(f"  Lineup K% P75: {lineup_k_q75:.4f}")
    logger.info(f"  Price floor: >{PRICE_FLOOR}")

    # Apply flags
    valid = kp[kp["bb_pct"].notna() & kp["opp_lineup_k_rate"].notna() & (kp["start_num"] >= 5)].copy()
    logger.info(f"Eligible starts (5+ prior, BB% + lineup K% available, price floor): {len(valid)}")

    valid["bb_high"] = (valid["bb_pct"] >= bb_q75).astype(int)
    valid["k_high"] = (valid["opp_lineup_k_rate"] >= lineup_k_q75).astype(int)
    valid["kp04_flag"] = ((valid["bb_high"] == 1) & (valid["k_high"] == 1)).astype(int)

    # Four-way groups
    flagged = valid[valid["kp04_flag"] == 1]
    baseline = valid
    neither = valid[(valid["bb_high"] == 0) & (valid["k_high"] == 0)]
    partial = valid[((valid["bb_high"] == 1) ^ (valid["k_high"] == 1))]

    logger.info(f"\n{'='*65}")
    logger.info("FOUR-WAY COMPARISON")
    logger.info("=" * 65)

    s_flag = group_stats(flagged, "KP04 flagged")
    s_base = group_stats(baseline, "Baseline (all)")
    s_neither = group_stats(neither, "Neither component")
    s_partial_n = len(partial[partial["k_push"] == 0])
    s_partial_hr = partial[partial["k_push"] == 0]["k_over"].mean() if s_partial_n > 0 else None

    for s in [s_flag, s_base, s_neither]:
        logger.info(f"  {s['label']:<25} N={s['n']:>5}  HR={s['hit_rate']}  ROI={s['roi']}%  "
                     f"K-err={s['k_err']}  pushes={s['pushes']}")
    logger.info(f"  {'Partial match':<25} N={s_partial_n:>5}  HR={round(s_partial_hr, 4) if s_partial_hr else None}")

    freeze_n = len(flagged[flagged["season"] == 2023])
    logger.info(f"\n  Freeze N (2023): {freeze_n}")

    # Year stability
    logger.info(f"\n{'='*65}")
    logger.info("YEAR STABILITY")
    logger.info("=" * 65)

    year_results = {}
    for year in [2023, 2024, 2025]:
        sub = flagged[flagged["season"] == year]
        nopush = sub[sub["k_push"] == 0]
        n = len(nopush)
        hr = nopush["k_over"].mean() if n > 0 else None
        roi, _ = compute_roi(sub, "over")
        year_results[year] = {"n": n, "hit_rate": round(hr, 4) if hr else None, "roi": roi}
        logger.info(f"  {year}: N={n}, HR={hr:.4f}, ROI={roi}%" if hr else f"  {year}: N=0")

    # Trend assessment
    rois = [year_results[y]["roi"] for y in [2023, 2024, 2025] if year_results[y]["roi"] is not None]
    if len(rois) == 3:
        if rois[2] > rois[0] and rois[2] > rois[1]:
            trend = "STRENGTHENING"
        elif all(r > 0 for r in rois) and max(rois) - min(rois) < 15:
            trend = "STABLE"
        elif rois[2] < 0:
            trend = "WEAKENING"
        else:
            trend = "INCONSISTENT"
    else:
        trend = "INSUFFICIENT"
    logger.info(f"  Trend: {trend}")

    # Pitcher breadth
    logger.info(f"\n{'='*65}")
    logger.info("PITCHER BREADTH")
    logger.info("=" * 65)

    pitcher_stats = flagged.groupby(["pitcher_id", "pitcher_name"]).agg(
        n=("k_over", "count"), over_rate=("k_over", "mean")).reset_index()
    pitcher_rois = []
    for _, p in pitcher_stats.iterrows():
        sub = flagged[flagged["pitcher_id"] == p["pitcher_id"]]
        roi, _ = compute_roi(sub, "over")
        pitcher_rois.append(roi)
    pitcher_stats["roi"] = pitcher_rois
    pitcher_stats = pitcher_stats.sort_values("n", ascending=False)

    total_flagged = len(flagged)
    top1_share = pitcher_stats.iloc[0]["n"] / total_flagged if total_flagged > 0 else 0
    concentrated = top1_share > 0.15

    logger.info(f"  Unique pitchers: {len(pitcher_stats)}")
    logger.info(f"  Top 1 share: {top1_share:.1%}")
    logger.info(f"  {'CONCENTRATED' if concentrated else 'BROAD'}")
    logger.info(f"\n  Top 5 pitchers:")
    for _, p in pitcher_stats.head(5).iterrows():
        roi_str = f"{p['roi']:+.1f}%" if p["roi"] is not None else "—"
        logger.info(f"    {p['pitcher_name']:<25} N={int(p['n']):>3}  HR={p['over_rate']:.3f}  ROI={roi_str}")

    # Permutation test
    logger.info(f"\n{'='*65}")
    logger.info("PERMUTATION TEST")
    logger.info("=" * 65)

    all_data = valid[valid["season"].isin([2023, 2024, 2025])].copy()

    def roi_metric(sig, _outcomes):
        idx = sig == 1
        if idx.sum() == 0:
            return 0.0
        sub = all_data.iloc[np.where(idx)[0]]
        roi, _ = compute_roi(sub, "over")
        return roi if roi is not None else 0.0

    perm = st.run_permutation_test(
        signal_values=all_data["kp04_flag"].values,
        outcomes=all_data["k_over"].values,
        metric_fn=roi_metric,
        n_permutations=500,
        season_labels=all_data["season"].values,
    )
    logger.info(f"  Observed ROI: {perm['observed_metric']:.2f}%")
    logger.info(f"  Perm mean: {perm['permutation_mean']:.2f}%")
    logger.info(f"  Percentile: {perm['percentile']:.1f}")

    # Verdict
    logger.info(f"\n{'='*65}")
    logger.info("VERDICT")
    logger.info("=" * 65)

    s2025 = year_results.get(2025, {})
    val_2025_pos = (s2025.get("roi") or -999) > 0
    perm_pass = perm["percentile"] >= 85
    near_miss = 75 <= perm["percentile"] < 85

    if freeze_n < 50:
        verdict, reason = "NEEDS_MORE_DATA", f"Freeze N={freeze_n} < 50"
    elif s2025.get("roi") is not None and abs(s2025["roi"]) > 30:
        verdict, reason = "SUSPECT", f"2025 ROI={s2025['roi']:.1f}% — flag for review"
    elif perm_pass and val_2025_pos:
        verdict, reason = "PASS", None
    elif near_miss and val_2025_pos:
        verdict, reason = "NEAR_MISS", f"Perm {perm['percentile']:.1f} in 75-84; 2025 positive"
    elif not perm_pass:
        verdict, reason = "FAIL", f"Perm {perm['percentile']:.1f} < 85"
    elif not val_2025_pos:
        verdict, reason = "FAIL", f"2025 ROI={s2025.get('roi')}% not positive"
    else:
        verdict, reason = "FAIL", "Did not meet criteria"

    logger.info(f"  VERDICT: {verdict}")
    if reason:
        logger.info(f"  Reason: {reason}")
    if verdict == "PASS":
        logger.info(f"\n  OPERATIONAL REQUIREMENTS:")
        logger.info(f"  (1) Confirmed lineups only — do not fire before lineup announcements")
        logger.info(f"  (2) Over odds > -150 — skip heavy favorites")
        logger.info(f"  (3) Minimum 5 prior starts for pitcher")

    # Log results
    result = {
        "canonical_signal_id": "KP04",
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "frozen_thresholds": {"bb_pct_p75": round(bb_q75, 4), "lineup_k_p75": round(lineup_k_q75, 4),
                              "price_floor": PRICE_FLOOR, "min_prior_starts": 5,
                              "freeze_window": "2023"},
        "freeze_window_n": freeze_n,
        "four_way_comparison": {
            "kp04_flagged": s_flag,
            "baseline": s_base,
            "neither_component": s_neither,
            "partial_match": {"n": s_partial_n, "hit_rate": round(s_partial_hr, 4) if s_partial_hr else None},
        },
        "year_stability": {str(k): v for k, v in year_results.items()},
        "trend": trend,
        "pitcher_breadth": {"unique_pitchers": len(pitcher_stats), "top1_share": round(top1_share, 4),
                            "concentrated": concentrated},
        "validation_2025": {"n": s2025.get("n", 0), "hit_rate": s2025.get("hit_rate"),
                            "roi": s2025.get("roi"), "direction_positive": val_2025_pos},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "verdict": verdict,
        "failure_reason": reason,
    }

    st.log_test_result(result)

    # Update board
    board = []
    if st.BOARD_PATH.exists():
        with open(st.BOARD_PATH) as f:
            board = json.load(f)
    board = [b for b in board if b.get("canonical_signal_id") != "KP04"]

    advancement = None
    if verdict == "PASS":
        advancement = "Shadow deployment with confirmed lineups + price floor"
    elif verdict == "NEAR_MISS":
        advancement = "Note for threshold refinement"

    board.append({
        "canonical_signal_id": "KP04",
        "canonical_name": "Breaking-ball pitcher x high-K lineup (K OVER)",
        "domain": "PITCHER",
        "framework_type": "STATE_MODEL",
        "market_target": "PLAYER_PROP_K",
        "status": verdict,
        "failure_reason": reason,
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

    logger.info(f"\nLogged to test_results_log.json and signal_board.json")
    logger.info(f"Completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
