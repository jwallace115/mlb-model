#!/usr/bin/env python3
"""
CS028 — Bullpen positive state as V1 UNDER amplifier.

Tests whether V1 UNDER plays are stronger when both bullpens
are in a positive state regime.

NOTE: V1 p_under only available from model_outputs for 2024-2025.
Threshold freeze uses 2024 (earliest available), validated on 2025.
This is narrower than the pre-registered 2022-2023 freeze window.
Bullpen features use full 2022-2025 pitcher_game_logs.

RESEARCH ONLY.
"""

import json, sys, logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("cs028")

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SAFETY = ROOT / "research" / "signal_discovery" / "safety_layer"
sys.path.insert(0, str(SAFETY))
import signal_tester as st

MIN_PRIOR_APPEARANCES = 5


# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════

def load_v1_under_games():
    """Load games where V1 UNDER would fire (p_under >= 0.57)."""
    mo = pd.read_parquet(ROOT / "sim" / "data" / "model_outputs.parquet")
    gt = pd.read_parquet(ROOT / "sim" / "data" / "game_table.parquet")
    gt = gt[gt["season"].isin([2024, 2025])].copy()

    # Closing lines
    ms = pd.read_parquet(ROOT / "sim" / "data" / "market_snapshots.parquet")
    ms = ms[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"})
    ms = ms.drop_duplicates(subset="game_pk", keep="last")

    g = gt.merge(mo[["game_id", "p_under", "p_over", "sim_mean"]].rename(
        columns={"game_id": "game_pk"}), on="game_pk", how="inner")
    g = g.merge(ms, on="game_pk", how="inner")

    g["v1_under"] = (g["p_under"] >= 0.57).astype(int)
    g["went_under"] = (g["actual_total"] < g["close_total"]).astype(int)
    g["went_over"] = (g["actual_total"] > g["close_total"]).astype(int)
    g["push"] = (g["actual_total"] == g["close_total"]).astype(int)
    g["market_residual"] = g["actual_total"] - g["close_total"]

    logger.info(f"Games with V1 probs + closing lines: {len(g)}")
    logger.info(f"V1 UNDER fires (p_under >= 0.57): {g['v1_under'].sum()}")
    logger.info(f"Seasons: {sorted(g['season'].unique())}")
    return g


def build_cs013_flags(pitcher_logs):
    """Replicate CS013 frozen logic: 2+ degraded relievers on team."""
    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["player_id", "game_date", "game_pk"])

    rlv["season_rpa"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).expanding(min_periods=MIN_PRIOR_APPEARANCES).mean())
    rlv["degraded_app"] = (
        (rlv["runs_allowed"] > 1.5 * rlv["season_rpa"]) & rlv["season_rpa"].notna()
    ).astype(int)
    rlv["deg_count_5"] = rlv.groupby(["player_id", "season"])["degraded_app"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).sum())
    rlv["is_degraded"] = (rlv["deg_count_5"] >= 2).astype(int)

    team_game = (rlv.dropna(subset=["deg_count_5"])
                 .groupby(["team", "game_pk", "season"])
                 .agg(n_degraded=("is_degraded", "sum"))
                 .reset_index())
    team_game["cs013_team_flag"] = (team_game["n_degraded"] >= 2).astype(int)
    return team_game


def build_bullpen_ra_baseline(pitcher_logs):
    """Team bullpen RA per appearance, rolling 7 games vs season baseline."""
    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["team", "season", "game_date", "game_pk"])

    # Per-game, per-team: mean RA of relievers who appeared
    team_game_ra = (rlv.groupby(["team", "game_pk", "season", "game_date"])
                    .agg(team_bp_ra=("runs_allowed", "mean"),
                         n_relievers=("player_id", "nunique"))
                    .reset_index())
    team_game_ra = team_game_ra.sort_values(["team", "season", "game_date", "game_pk"])

    # Rolling 7-game mean (shift 1 = pregame)
    team_game_ra["bp_ra_r7"] = team_game_ra.groupby(["team", "season"])["team_bp_ra"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=5).mean())
    # Season baseline (shift 1)
    team_game_ra["bp_ra_baseline"] = team_game_ra.groupby(["team", "season"])["team_bp_ra"].transform(
        lambda x: x.shift(1).expanding(min_periods=7).mean())

    # Positive = rolling below baseline
    team_game_ra["bp_ra_positive"] = (
        (team_game_ra["bp_ra_r7"] < team_game_ra["bp_ra_baseline"]) &
        team_game_ra["bp_ra_r7"].notna()
    ).astype(int)

    return team_game_ra[["team", "game_pk", "season", "bp_ra_r7", "bp_ra_baseline", "bp_ra_positive"]]


def build_reliever_availability(pitcher_logs):
    """Top 2 relievers by appearances available (not pitched in last 2 days)."""
    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["team", "season", "game_date", "game_pk"])
    rlv["game_date_dt"] = pd.to_datetime(rlv["game_date"])

    results = []
    for (team, season), grp in rlv.groupby(["team", "season"]):
        # Identify top 2 relievers by total appearances (proxy for leverage)
        app_counts = grp.groupby("player_id").size().sort_values(ascending=False)
        if len(app_counts) < 2:
            continue
        top2 = set(app_counts.head(2).index)

        # Per game: check if top 2 are available (not appeared in last 2 days)
        game_dates = grp[["game_pk", "game_date_dt"]].drop_duplicates("game_pk").sort_values("game_date_dt")
        for _, game_row in game_dates.iterrows():
            gpk = game_row["game_pk"]
            gd = game_row["game_date_dt"]
            cutoff = gd - pd.Timedelta(days=2)

            recent = grp[(grp["game_date_dt"] > cutoff) & (grp["game_date_dt"] < gd)]
            recent_pitchers = set(recent["player_id"].unique())

            top2_available = len(top2 - recent_pitchers)
            results.append({
                "team": team, "season": season, "game_pk": gpk,
                "top2_available": top2_available,
                "key_relievers_available": int(top2_available == 2),
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════
# JOIN ALL COMPONENTS
# ═══════════════════════════════════════════════════════════

def build_positive_state(games, cs013_team, bp_ra, reliever_avail):
    """Join all three components and compute positive_state flag."""
    g = games.copy()

    # CS013: no deterioration on EITHER team
    for prefix, tcol in [("home", "home_team"), ("away", "away_team")]:
        g = g.merge(cs013_team[["team", "game_pk", "cs013_team_flag"]].rename(
            columns={"team": tcol, "cs013_team_flag": f"{prefix}_cs013"}),
            on=[tcol, "game_pk"], how="left")
    g["home_cs013"] = g["home_cs013"].fillna(0).astype(int)
    g["away_cs013"] = g["away_cs013"].fillna(0).astype(int)
    # No deterioration = flag is FALSE
    g["home_no_deterioration"] = (g["home_cs013"] == 0).astype(int)
    g["away_no_deterioration"] = (g["away_cs013"] == 0).astype(int)

    # Bullpen RA below baseline
    for prefix, tcol in [("home", "home_team"), ("away", "away_team")]:
        g = g.merge(bp_ra[["team", "game_pk", "bp_ra_positive"]].rename(
            columns={"team": tcol, "bp_ra_positive": f"{prefix}_bp_ra_pos"}),
            on=[tcol, "game_pk"], how="left")
    g["home_bp_ra_pos"] = g["home_bp_ra_pos"].fillna(0).astype(int)
    g["away_bp_ra_pos"] = g["away_bp_ra_pos"].fillna(0).astype(int)

    # Key relievers available
    for prefix, tcol in [("home", "home_team"), ("away", "away_team")]:
        g = g.merge(reliever_avail[["team", "game_pk", "key_relievers_available"]].rename(
            columns={"team": tcol, "key_relievers_available": f"{prefix}_relievers_avail"}),
            on=[tcol, "game_pk"], how="left")
    g["home_relievers_avail"] = g["home_relievers_avail"].fillna(0).astype(int)
    g["away_relievers_avail"] = g["away_relievers_avail"].fillna(0).astype(int)

    # Per-team positive state = all 3 components
    g["home_positive"] = ((g["home_no_deterioration"] == 1) &
                          (g["home_bp_ra_pos"] == 1) &
                          (g["home_relievers_avail"] == 1)).astype(int)
    g["away_positive"] = ((g["away_no_deterioration"] == 1) &
                          (g["away_bp_ra_pos"] == 1) &
                          (g["away_relievers_avail"] == 1)).astype(int)

    # Primary: BOTH bullpens positive
    g["both_positive"] = ((g["home_positive"] == 1) & (g["away_positive"] == 1)).astype(int)
    # Secondary variants
    g["home_positive_only"] = g["home_positive"]
    g["away_positive_only"] = g["away_positive"]
    g["either_positive"] = ((g["home_positive"] == 1) | (g["away_positive"] == 1)).astype(int)

    return g


# ═══════════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════════

def compute_stats(df, label=""):
    n = len(df)
    if n == 0:
        return {"label": label, "n": 0, "hit_rate": None, "roi": None,
                "residual": None, "push_count": 0}
    nopush = df[df["push"] == 0]
    hr = nopush["went_under"].mean() if len(nopush) > 0 else None
    roi = (hr * (100/110) - (1 - hr)) * 100 if hr else None
    res = df["market_residual"].mean()
    pc = int(df["push"].sum())
    return {"label": label, "n": len(nopush), "hit_rate": round(hr, 4) if hr else None,
            "roi": round(roi, 2) if roi else None, "residual": round(res, 4),
            "push_count": pc}


def print_stats(s):
    logger.info(f"  {s['label']:<40} N={s['n']:>5}  HR={s['hit_rate']}  "
                f"ROI={s['roi']}%  resid={s['residual']}  pushes={s['push_count']}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 65)
    logger.info("CS028 — Bullpen positive state as V1 UNDER amplifier")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 65)

    # Load data
    games = load_v1_under_games()
    pitcher_logs = pd.read_parquet(ROOT / "mlb" / "data" / "pitcher_game_logs.parquet")
    pitcher_logs = pitcher_logs[pitcher_logs["season"].isin([2024, 2025])].copy()
    logger.info(f"Pitcher logs (2024-2025): {len(pitcher_logs)}")

    # Build components
    cs013_team = build_cs013_flags(pitcher_logs)
    bp_ra = build_bullpen_ra_baseline(pitcher_logs)
    reliever_avail = build_reliever_availability(pitcher_logs)
    logger.info(f"CS013 team-game flags: {len(cs013_team)}")
    logger.info(f"BP RA baseline records: {len(bp_ra)}")
    logger.info(f"Reliever availability records: {len(reliever_avail)}")

    # Join
    g = build_positive_state(games, cs013_team, bp_ra, reliever_avail)

    # Filter to V1 UNDER games only
    v1u = g[g["v1_under"] == 1].copy()
    logger.info(f"\nV1 UNDER games: {len(v1u)}")
    logger.info(f"Both bullpens positive in V1 UNDER: {v1u['both_positive'].sum()}")

    # Component breakdown
    logger.info(f"\nComponent prevalence (V1 UNDER games):")
    logger.info(f"  Home no CS013 deterioration: {v1u['home_no_deterioration'].mean():.1%}")
    logger.info(f"  Away no CS013 deterioration: {v1u['away_no_deterioration'].mean():.1%}")
    logger.info(f"  Home BP RA below baseline:   {v1u['home_bp_ra_pos'].mean():.1%}")
    logger.info(f"  Away BP RA below baseline:   {v1u['away_bp_ra_pos'].mean():.1%}")
    logger.info(f"  Home key relievers avail:    {v1u['home_relievers_avail'].mean():.1%}")
    logger.info(f"  Away key relievers avail:    {v1u['away_relievers_avail'].mean():.1%}")
    logger.info(f"  Home positive (all 3):       {v1u['home_positive'].mean():.1%}")
    logger.info(f"  Away positive (all 3):       {v1u['away_positive'].mean():.1%}")
    logger.info(f"  Both positive:               {v1u['both_positive'].mean():.1%}")

    # ─── PRIMARY THREE-WAY COMPARISON ───────────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("PRIMARY — Three-way comparison (V1 UNDER games)")
    logger.info("=" * 65)

    baseline = v1u
    amplified = v1u[v1u["both_positive"] == 1]
    not_amplified = v1u[v1u["both_positive"] == 0]

    s_base = compute_stats(baseline, "V1 UNDER baseline")
    s_amp = compute_stats(amplified, "V1 UNDER + both BP positive")
    s_not = compute_stats(not_amplified, "V1 UNDER + not both positive")

    print_stats(s_base)
    print_stats(s_amp)
    print_stats(s_not)

    # Season breakdown
    logger.info(f"\n  Season breakdown (amplified = both positive):")
    for season in sorted(v1u["season"].unique()):
        s = amplified[amplified["season"] == season]
        sp = s[s["push"] == 0]
        n = len(sp)
        hr = sp["went_under"].mean() if n > 0 else None
        roi = (hr * (100/110) - (1-hr)) * 100 if hr else None
        logger.info(f"    {season}: N={n}, HR={hr:.4f}, ROI={roi:+.2f}%" if hr else f"    {season}: N=0")

    # Freeze N
    freeze = amplified[amplified["season"] == 2024]
    freeze_nopush = freeze[freeze["push"] == 0]
    freeze_n = len(freeze_nopush)
    logger.info(f"\n  Freeze N (2024): {freeze_n}")

    # ─── PERMUTATION TEST (parent-scoped) ───────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("PERMUTATION TEST (parent_mask = V1 UNDER games)")
    logger.info("=" * 65)

    # Use all games (not just V1 UNDER) but with parent_mask
    all_games = g[g["season"].isin([2024, 2025])].copy()
    all_nopush = all_games[all_games["push"] == 0].copy()

    parent_mask = (all_nopush["v1_under"] == 1).values

    # Signal: both_positive AND v1_under
    signal = ((all_nopush["v1_under"] == 1) & (all_nopush["both_positive"] == 1)).astype(int).values
    outcomes = all_nopush["went_under"].values
    seasons = all_nopush["season"].values

    perm = st.run_permutation_test(
        signal_values=signal,
        outcomes=outcomes,
        metric_fn=lambda sig, out: out[sig == 1].mean() if (sig == 1).sum() > 0 else 0.5,
        n_permutations=500,
        season_labels=seasons,
        parent_mask=parent_mask,
    )
    logger.info(f"  Observed: {perm['observed_metric']:.4f}")
    logger.info(f"  Perm mean: {perm['permutation_mean']:.4f}")
    logger.info(f"  Percentile: {perm['percentile']:.1f}")
    logger.info(f"  Parent-scoped: {perm.get('parent_scoped', False)}")

    # ─── SECONDARY VARIANTS ────────────────────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("SECONDARY VARIANTS (diagnostic only, no permutation)")
    logger.info("=" * 65)

    for variant, col in [("Home BP positive only", "home_positive_only"),
                         ("Away BP positive only", "away_positive_only"),
                         ("Either BP positive", "either_positive")]:
        sub = v1u[v1u[col] == 1]
        sub_np = sub[sub["push"] == 0]
        n = len(sub_np)
        hr = sub_np["went_under"].mean() if n > 0 else None
        logger.info(f"  {variant:<30} N={n:>5}  HR={hr:.4f}" if hr else f"  {variant:<30} N=0")

    # ─── REDUNDANCY CHECK vs S12 / P09 ─────────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("REDUNDANCY CHECK vs S12 and P09")
    logger.info("=" * 65)

    # Load V1 signal parquet which has overlay fields
    v1_sigs_path = ROOT / "mlb_sim" / "logs" / "signals_2026.parquet"
    # For historical: check if S12/P09 are in model_outputs or feature_table
    # S12 and P09 are overlays computed at signal time — may not be in historical data
    # Check sim_inputs or bullpen_features
    bf = pd.read_parquet(ROOT / "sim" / "data" / "bullpen_features.parquet")
    bf = bf[bf["season"].isin([2024, 2025])].copy()

    # S12 fires when dual_high_csw_shadow is true (both starters have high CSW)
    # P09 fires based on weather/park interaction
    # These are generated at runtime, not stored in historical features
    # Best proxy: check if high_leverage_available correlates
    logger.info("  S12 and P09 overlay flags are runtime-only and not stored")
    logger.info("  in historical data. Cannot compute overlap directly.")
    logger.info("  Noting as OVERLAP_UNKNOWN — not a blocking issue for verdict.")

    redundancy = {"s12_overlap": "UNKNOWN (runtime overlay, not in historical data)",
                  "p09_overlap": "UNKNOWN (runtime overlay, not in historical data)"}

    # ─── 2025 SUBSAMPLE ────────────────────────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("2025 OOS BINDING VALIDATION")
    logger.info("=" * 65)

    oos = amplified[amplified["season"] == 2025]
    oos_np = oos[oos["push"] == 0]
    s_oos = compute_stats(oos, "2025 OOS")
    print_stats(s_oos)

    # ─── VERDICT ───────────────────────────────────────
    logger.info(f"\n{'=' * 65}")
    logger.info("VERDICT")
    logger.info("=" * 65)

    val_2025_pos = (s_oos.get("hit_rate") or 0) > 0.50
    perm_pass = perm["percentile"] >= 85
    near_miss = 75 <= perm["percentile"] < 85

    if freeze_n < 50:
        verdict = "NEEDS_MORE_DATA"
        reason = f"Freeze N={freeze_n} < 50"
    elif perm_pass and val_2025_pos:
        verdict = "PASS"
        reason = None
    elif near_miss and val_2025_pos:
        verdict = "NEAR_MISS"
        reason = f"Perm {perm['percentile']:.1f} in 75-84 range; 2025 positive"
    elif not perm_pass:
        verdict = "FAIL"
        reason = f"Perm {perm['percentile']:.1f} < 85"
    elif not val_2025_pos:
        verdict = "FAIL"
        reason = f"2025 HR={s_oos.get('hit_rate')} <= 0.50 — not directionally positive OOS"
    else:
        verdict = "FAIL"
        reason = "Did not meet criteria"

    # Suspect check
    if s_oos.get("roi") and abs(s_oos["roi"]) > 30:
        verdict = "SUSPECT"
        reason = f"2025 ROI={s_oos['roi']:.1f}% — flag for review"

    logger.info(f"  VERDICT: {verdict}")
    if reason:
        logger.info(f"  Reason: {reason}")
    if verdict == "PASS":
        logger.info("  Next step: Phase B stake sizing test — do not run now")

    # ─── LOG RESULTS ───────────────────────────────────
    result = {
        "canonical_signal_id": "CS028",
        "test_date": datetime.now().isoformat(),
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "data_limitation": "V1 p_under only available 2024-2025; freeze on 2024 instead of pre-registered 2022-2023",
        "frozen_thresholds": {
            "cs013_deterioration": "frozen CS013 team flag = FALSE",
            "bp_ra_positive": "rolling 7-game mean < season baseline",
            "key_relievers_available": "top 2 by appearances not pitched in last 2 days",
            "min_prior_appearances": MIN_PRIOR_APPEARANCES,
            "freeze_window": "2024 (limitation: 2022-2023 V1 probs unavailable)",
        },
        "freeze_window_n": freeze_n,
        "three_way_comparison": {
            "v1_under_baseline": {"n": s_base["n"], "hit_rate": s_base["hit_rate"],
                                  "roi": s_base["roi"], "residual": s_base["residual"],
                                  "push_count": s_base["push_count"]},
            "both_bp_positive": {"n": s_amp["n"], "hit_rate": s_amp["hit_rate"],
                                 "roi": s_amp["roi"], "residual": s_amp["residual"],
                                 "push_count": s_amp["push_count"]},
            "not_both_positive": {"n": s_not["n"], "hit_rate": s_not["hit_rate"],
                                  "roi": s_not["roi"], "residual": s_not["residual"],
                                  "push_count": s_not["push_count"]},
        },
        "validation_2025": {"n": s_oos["n"], "hit_rate": s_oos["hit_rate"],
                            "roi": s_oos["roi"], "direction_positive": val_2025_pos,
                            "note": "binding OOS"},
        "permutation_percentile": perm["percentile"],
        "permutation_detail": perm,
        "redundancy_check": redundancy,
        "verdict": verdict,
        "failure_reason": reason,
    }

    st.log_test_result(result)

    # Update board
    board = []
    if st.BOARD_PATH.exists():
        with open(st.BOARD_PATH) as f:
            board = json.load(f)
    board = [b for b in board if b.get("canonical_signal_id") != "CS028"]

    advancement = None
    if verdict == "PASS":
        advancement = "Phase B stake sizing test — do not run now"
    elif verdict == "NEAR_MISS":
        advancement = "Note for threshold refinement — do not promote"

    board.append({
        "canonical_signal_id": "CS028",
        "canonical_name": "Bullpen positive state as V1 UNDER amplifier",
        "domain": "BULLPEN",
        "framework_type": "STATE_MODEL",
        "market_target": "FULL_GAME_TOTAL",
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
    return result


if __name__ == "__main__":
    main()
