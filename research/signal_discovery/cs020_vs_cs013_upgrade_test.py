#!/usr/bin/env python3
"""
CS020 vs CS013 — Upgrade Diagnostic

Determines whether CS020 (bullpen collapse Bayesian/acceleration) is a
better classifier than CS013 (bullpen blowup state model) on the SAME
population of games.

POPULATION RULE:
  1. Build the CS013-flagged game table using frozen thresholds from
     cs013_shadow.py.
  2. Freeze that table.
  3. Evaluate BOTH CS013 and CS020 only on that exact table.
  Do not recompute CS013 flags during evaluation.
  Do not allow filtering differences between signals.

RESEARCH ONLY — does not modify any model or pipeline files.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("cs020_upgrade")

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent


# ═══════════════════════════════════════════════════════════
# STEP 1 — LOAD GAME OUTCOMES (FULL DATASET, 2022-2025)
# ═══════════════════════════════════════════════════════════

def load_full_game_dataset():
    """Load all games with closing lines, exclude pushes. 2026 holdout excluded."""
    gt = pd.read_parquet(ROOT / "sim" / "data" / "game_table.parquet")
    gt = gt[gt["season"].isin([2022, 2023, 2024, 2025])].copy()

    cl_22_23 = pd.read_parquet(
        ROOT / "sim" / "data" / "mlb_historical_closing_lines.parquet"
    )[["game_pk", "close_total"]]
    ms_24_25 = pd.read_parquet(
        ROOT / "sim" / "data" / "market_snapshots.parquet"
    )[["game_id", "close_total"]].rename(columns={"game_id": "game_pk"})

    closing = pd.concat([cl_22_23, ms_24_25], ignore_index=True).drop_duplicates(
        subset="game_pk", keep="last"
    )
    gt = gt.merge(closing, on="game_pk", how="inner")
    gt["went_over"] = (gt["actual_total"] > gt["close_total"]).astype(int)
    gt["push"] = (gt["actual_total"] == gt["close_total"]).astype(int)
    gt = gt[gt["push"] == 0].copy()

    logger.info(f"Full game dataset: {len(gt)} games (pushes excluded)")
    return gt


# ═══════════════════════════════════════════════════════════
# STEP 2 — BUILD CS013 FLAGS (FROZEN THRESHOLDS)
# ═══════════════════════════════════════════════════════════

def build_cs013_flags(pitcher_logs):
    """
    Replicate CS013 using EXACT frozen thresholds from cs013_shadow.py:
      DEGRADED_MULTIPLIER = 1.5
      DEGRADED_COUNT_IN_5 = 2
      TEAM_THRESHOLD = 2
      MIN_PRIOR_APPEARANCES = 5
    """
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

    team_game = (
        rlv.dropna(subset=["deg_count_5"])
        .groupby(["team", "game_pk", "season"])
        .agg(n_degraded=("is_degraded", "sum"))
        .reset_index()
    )
    team_game["cs013_team_flag"] = (team_game["n_degraded"] >= TEAM_THRESHOLD).astype(int)
    return team_game


# ═══════════════════════════════════════════════════════════
# STEP 3 — BUILD CS020 FLAGS (FROZEN THRESHOLDS)
# ═══════════════════════════════════════════════════════════

def build_cs020_flags(pitcher_logs):
    """
    Build CS020 using frozen thresholds from batch4_wave1_test:
      acceleration cutoff: 0.3 (3g RA - 10g RA)
      bayesian shift cutoff: 0.2 (3g RA - season mean)
      team threshold: 2+ accelerating relievers
    """
    ACCEL_CUTOFF = 0.3
    BAYESIAN_CUTOFF = 0.2
    TEAM_THRESHOLD = 2

    rlv = pitcher_logs[pitcher_logs["starter_flag"] == 0].copy()
    rlv = rlv.sort_values(["player_id", "game_date", "game_pk"])

    rlv["ra_r3"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=3).mean()
    )
    rlv["ra_r10"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).rolling(10, min_periods=5).mean()
    )
    rlv["season_mean"] = rlv.groupby(["player_id", "season"])["runs_allowed"].transform(
        lambda x: x.shift(1).expanding(min_periods=5).mean()
    )

    rlv["acceleration"] = rlv["ra_r3"] - rlv["ra_r10"]
    rlv["bayesian_shift"] = rlv["ra_r3"] - rlv["season_mean"]

    rlv["accel_flag"] = (
        (rlv["acceleration"] > ACCEL_CUTOFF)
        & (rlv["bayesian_shift"] > BAYESIAN_CUTOFF)
        & rlv["ra_r3"].notna()
        & rlv["ra_r10"].notna()
    ).astype(int)

    team_game = (
        rlv.groupby(["team", "game_pk", "season"])
        .agg(n_accel_relievers=("accel_flag", "sum"))
        .reset_index()
    )
    team_game["cs020_team_flag"] = (team_game["n_accel_relievers"] >= TEAM_THRESHOLD).astype(int)
    return team_game


# ═══════════════════════════════════════════════════════════
# STEP 4 — JOIN FLAGS TO GAME LEVEL
# ═══════════════════════════════════════════════════════════

def join_flags_to_games(games, cs013_team, cs020_team):
    """Join both signals to game level. One row per game, both flags present."""
    g = games.copy()

    # CS013: game is flagged if EITHER team has 2+ degraded relievers
    for prefix, team_col in [("home", "home_team"), ("away", "away_team")]:
        g = g.merge(
            cs013_team[["team", "game_pk", "cs013_team_flag"]].rename(
                columns={"team": team_col, "cs013_team_flag": f"{prefix}_cs013"}
            ),
            on=[team_col, "game_pk"], how="left"
        )
    g["home_cs013"] = g["home_cs013"].fillna(0).astype(int)
    g["away_cs013"] = g["away_cs013"].fillna(0).astype(int)
    g["cs013_flag"] = ((g["home_cs013"] == 1) | (g["away_cs013"] == 1)).astype(int)

    # CS020: game is flagged if EITHER team has 2+ accelerating relievers
    for prefix, team_col in [("home", "home_team"), ("away", "away_team")]:
        g = g.merge(
            cs020_team[["team", "game_pk", "cs020_team_flag"]].rename(
                columns={"team": team_col, "cs020_team_flag": f"{prefix}_cs020"}
            ),
            on=[team_col, "game_pk"], how="left"
        )
    g["home_cs020"] = g["home_cs020"].fillna(0).astype(int)
    g["away_cs020"] = g["away_cs020"].fillna(0).astype(int)
    g["cs020_flag"] = ((g["home_cs020"] == 1) | (g["away_cs020"] == 1)).astype(int)

    return g


# ═══════════════════════════════════════════════════════════
# STEP 5 — COMPUTE STATS HELPER
# ═══════════════════════════════════════════════════════════

def compute_stats(df, label=""):
    """Compute over_rate and ROI at -110 for a subset."""
    n = len(df)
    if n == 0:
        return {"label": label, "n": 0, "over_rate": None, "roi": None}
    wr = df["went_over"].mean()
    roi = (wr * (100 / 110) - (1 - wr)) * 100
    return {"label": label, "n": n, "over_rate": round(wr, 4), "roi": round(roi, 2)}


def season_table(df, label=""):
    """Compute stats by season with combined total."""
    rows = []
    for season in sorted(df["season"].unique()):
        s = df[df["season"] == season]
        rows.append(compute_stats(s, label=f"{label} {season}"))
    rows.append(compute_stats(df, label=f"{label} COMBINED"))
    return rows


# ═══════════════════════════════════════════════════════════
# MAIN DIAGNOSTIC
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 70)
    logger.info("CS020 vs CS013 — UPGRADE DIAGNOSTIC")
    logger.info(f"Run: {datetime.now().isoformat()}")
    logger.info("=" * 70)

    # Load data
    full_games = load_full_game_dataset()
    pitcher_logs = pd.read_parquet(ROOT / "mlb" / "data" / "pitcher_game_logs.parquet")
    pitcher_logs = pitcher_logs[pitcher_logs["season"].isin([2022, 2023, 2024, 2025])].copy()
    logger.info(f"Pitcher logs: {len(pitcher_logs)} rows")

    # Build flags from frozen thresholds
    cs013_team = build_cs013_flags(pitcher_logs)
    cs020_team = build_cs020_flags(pitcher_logs)

    # Join to game level
    g = join_flags_to_games(full_games, cs013_team, cs020_team)
    logger.info(f"Games with both flags joined: {len(g)}")

    # ─── FLAG RATES (against full dataset) ───────────────
    logger.info("\n" + "─" * 70)
    logger.info("FLAG RATES (full dataset denominator)")
    logger.info("─" * 70)
    full_n = len(g)
    cs013_n = g["cs013_flag"].sum()
    cs020_n = g["cs020_flag"].sum()
    both_n = ((g["cs013_flag"] == 1) & (g["cs020_flag"] == 1)).sum()
    logger.info(f"  Full dataset:       {full_n}")
    logger.info(f"  CS013 flagged:      {cs013_n} ({cs013_n/full_n:.1%})")
    logger.info(f"  CS020 flagged:      {cs020_n} ({cs020_n/full_n:.1%})")
    logger.info(f"  Both flagged:       {both_n} ({both_n/full_n:.1%})")
    logger.info(f"  CS013-only:         {cs013_n - both_n}")
    logger.info(f"  CS020-only:         {cs020_n - both_n}")

    # ─── FREEZE POPULATION: CS013 == TRUE ────────────────
    pop = g[g["cs013_flag"] == 1].copy()
    logger.info(f"\n  FROZEN POPULATION: {len(pop)} CS013-flagged games")
    logger.info("  All comparisons below use ONLY this population.")

    # ─── TEST 1: HEAD-TO-HEAD ON CS013 POPULATION ────────
    logger.info("\n" + "─" * 70)
    logger.info("TEST 1 — HEAD-TO-HEAD: CS013 vs CS020 on CS013 population")
    logger.info("─" * 70)

    logger.info("\n  CS013 (all flagged games in population):")
    logger.info(f"  {'Year':<8} {'N':>6} {'Over Rate':>11} {'ROI':>8}")
    logger.info(f"  {'─'*8} {'─'*6} {'─'*11} {'─'*8}")
    for row in season_table(pop, "CS013"):
        logger.info(f"  {row['label'].split()[-1]:<8} {row['n']:>6} "
                     f"{row['over_rate']:>11.4f} {row['roi']:>7.2f}%")

    # CS020 on same population (only games where CS020 also fires)
    pop_cs020_true = pop[pop["cs020_flag"] == 1]
    logger.info(f"\n  CS020 TRUE within CS013 population:")
    logger.info(f"  {'Year':<8} {'N':>6} {'Over Rate':>11} {'ROI':>8}")
    logger.info(f"  {'─'*8} {'─'*6} {'─'*11} {'─'*8}")
    for row in season_table(pop_cs020_true, "CS020T"):
        logger.info(f"  {row['label'].split()[-1]:<8} {row['n']:>6} "
                     f"{row['over_rate']:>11.4f} {row['roi']:>7.2f}%")

    # ─── TEST 2: DISAGREEMENT SUBSETS ────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("TEST 2 — DISAGREEMENT SUBSETS (within CS013 population)")
    logger.info("─" * 70)

    # Subset A: CS013 TRUE + CS020 TRUE
    subset_a = pop[pop["cs020_flag"] == 1]
    # Subset B: CS013 TRUE + CS020 FALSE
    subset_b = pop[pop["cs020_flag"] == 0]

    logger.info(f"\n  Subset A: CS013=TRUE + CS020=TRUE  (N={len(subset_a)})")
    logger.info(f"  {'Year':<8} {'N':>6} {'Over Rate':>11} {'ROI':>8}")
    logger.info(f"  {'─'*8} {'─'*6} {'─'*11} {'─'*8}")
    for row in season_table(subset_a, "A"):
        logger.info(f"  {row['label'].split()[-1]:<8} {row['n']:>6} "
                     f"{row['over_rate']:>11.4f} {row['roi']:>7.2f}%")

    logger.info(f"\n  Subset B: CS013=TRUE + CS020=FALSE  (N={len(subset_b)})")
    logger.info(f"  {'Year':<8} {'N':>6} {'Over Rate':>11} {'ROI':>8}")
    logger.info(f"  {'─'*8} {'─'*6} {'─'*11} {'─'*8}")
    for row in season_table(subset_b, "B"):
        logger.info(f"  {row['label'].split()[-1]:<8} {row['n']:>6} "
                     f"{row['over_rate']:>11.4f} {row['roi']:>7.2f}%")

    # ─── TEST 3: DELTA ANALYSIS ──────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("TEST 3 — PRECISION DELTA")
    logger.info("─" * 70)

    a_combined = compute_stats(subset_a, "A")
    b_combined = compute_stats(subset_b, "B")
    cs013_combined = compute_stats(pop, "CS013")

    delta_wr = (a_combined["over_rate"] or 0) - (b_combined["over_rate"] or 0)
    delta_roi = (a_combined["roi"] or 0) - (b_combined["roi"] or 0)

    logger.info(f"\n  Subset A over_rate: {a_combined['over_rate']:.4f}  (N={a_combined['n']})")
    logger.info(f"  Subset B over_rate: {b_combined['over_rate']:.4f}  (N={b_combined['n']})")
    logger.info(f"  Delta (A - B):      {delta_wr:+.4f}")
    logger.info(f"")
    logger.info(f"  Subset A ROI:       {a_combined['roi']:+.2f}%")
    logger.info(f"  Subset B ROI:       {b_combined['roi']:+.2f}%")
    logger.info(f"  Delta (A - B):      {delta_roi:+.2f}pp")

    # ─── TEST 4: 2025 OOS FOCUS ──────────────────────────
    logger.info("\n" + "─" * 70)
    logger.info("TEST 4 — 2025 OOS BINDING VALIDATION")
    logger.info("─" * 70)

    oos = pop[pop["season"] == 2025]
    oos_a = oos[oos["cs020_flag"] == 1]
    oos_b = oos[oos["cs020_flag"] == 0]

    oos_cs013 = compute_stats(oos, "CS013 2025")
    oos_a_stats = compute_stats(oos_a, "A 2025")
    oos_b_stats = compute_stats(oos_b, "B 2025")

    logger.info(f"\n  CS013 full 2025:           N={oos_cs013['n']:>5}  "
                f"over_rate={oos_cs013['over_rate']:.4f}  ROI={oos_cs013['roi']:+.2f}%")
    logger.info(f"  A (CS013+CS020) 2025:      N={oos_a_stats['n']:>5}  "
                f"over_rate={oos_a_stats['over_rate']:.4f}  ROI={oos_a_stats['roi']:+.2f}%")
    logger.info(f"  B (CS013 only)  2025:      N={oos_b_stats['n']:>5}  "
                f"over_rate={oos_b_stats['over_rate']:.4f}  ROI={oos_b_stats['roi']:+.2f}%")

    oos_delta = (oos_a_stats["over_rate"] or 0) - (oos_b_stats["over_rate"] or 0)
    logger.info(f"  2025 Delta (A - B):        {oos_delta:+.4f}")

    # ─── VERDICT ─────────────────────────────────────────
    logger.info("\n" + "=" * 70)
    logger.info("UPGRADE VERDICT")
    logger.info("=" * 70)

    upgrade_criteria = []
    # Criterion 1: Subset A beats Subset B on over_rate (combined)
    c1 = delta_wr > 0
    upgrade_criteria.append(("A > B overall", c1, f"delta={delta_wr:+.4f}"))

    # Criterion 2: Subset A beats Subset B in 2025 OOS
    c2 = oos_delta > 0
    upgrade_criteria.append(("A > B in 2025 OOS", c2, f"delta={oos_delta:+.4f}"))

    # Criterion 3: Subset B is weaker than CS013 overall (precision improvement)
    c3 = (b_combined["over_rate"] or 0) < (cs013_combined["over_rate"] or 0)
    upgrade_criteria.append(("B < CS013 overall", c3,
                            f"B={b_combined['over_rate']:.4f} vs CS013={cs013_combined['over_rate']:.4f}"))

    # Criterion 4: Sufficient N in Subset A (not a thin-sample artifact)
    c4 = (a_combined["n"] or 0) >= 100
    upgrade_criteria.append(("Subset A N >= 100", c4, f"N={a_combined['n']}"))

    for label, passed, detail in upgrade_criteria:
        status = "PASS" if passed else "FAIL"
        logger.info(f"  [{status}] {label}: {detail}")

    all_pass = all(p for _, p, _ in upgrade_criteria)

    if all_pass:
        logger.info("\n  RESULT: CS020 qualifies as CS013 v2 upgrade candidate.")
        logger.info("  Recommendation: Replace CS013 logic with CS020 acceleration variant")
        logger.info("  in shadow pipeline. Monitor 2026 shadow before full promotion.")
    else:
        n_pass = sum(1 for _, p, _ in upgrade_criteria if p)
        logger.info(f"\n  RESULT: CS020 does NOT clearly qualify as upgrade ({n_pass}/4 criteria met).")
        if c1 and not c2:
            logger.info("  Note: Overall positive but 2025 OOS does not confirm — may be in-sample artifact.")
        elif c2 and not c1:
            logger.info("  Note: 2025 positive but overall weak — small sample effect possible.")
        logger.info("  Recommendation: Keep CS013 as-is. Archive CS020 as redundant.")

    logger.info(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
