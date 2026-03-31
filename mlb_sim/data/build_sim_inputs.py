#!/usr/bin/env python3
"""
MLB Simulation Engine — Phase S1: Feature Assembly
===================================================
Assembles the daily simulation feature table by reading existing M3 data
sources and enriching with CSW/Whiff/F-Strike per-start rolling metrics.

Output: mlb_sim/data/sim_inputs_YYYY-MM-DD.parquet
  One row per starter per game.

Data sources (READ ONLY — no re-pulling):
  - sim/data/feature_table.parquet (Phase 9 baseline, 65 cols)
  - mlb/model_m3/m3_features.parquet (lineup wOBA)
  - mlb/data/pitcher_game_logs.parquet (innings pitched, pitch count)
  - research/mlb_phase_a/pitcher_start_metrics_per_start.csv (CSW rolling)

Hard rules:
  - All joins use IDs (sp_id, game_pk, team_id). Never join on names.
  - All season-to-date features use strictly prior-start data only.
  - No closing line or opening line anywhere in this feature table.
  - CSW is a path-probability input, not a mean-runs feature.
"""

import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIM_DIR = PROJECT_ROOT / "sim" / "data"
M3_DIR = PROJECT_ROOT / "mlb" / "model_m3"
MLB_DATA = PROJECT_ROOT / "mlb" / "data"
RESEARCH = PROJECT_ROOT / "research" / "mlb_phase_a"
OUT_DIR = Path(__file__).resolve().parent


def build_historical_sim_inputs(seasons=(2022, 2023, 2024)):
    """
    Build the full historical feature table for model training and evaluation.
    Returns DataFrame with one row per starter per game.
    """

    # ── Load M3 data sources (read only) ─────────────────────────────────────
    print("Loading M3 data sources...")
    ft = pd.read_parquet(SIM_DIR / "feature_table.parquet")
    m3f = pd.read_parquet(M3_DIR / "m3_features.parquet")
    pgl = pd.read_parquet(MLB_DATA / "pitcher_game_logs.parquet")
    csw_starts = pd.read_csv(RESEARCH / "pitcher_start_metrics_per_start.csv")

    # Normalize IDs to string for consistent joins
    ft["game_pk"] = ft["game_pk"].astype(str)
    m3f["game_pk"] = m3f["game_pk"].astype(str)
    pgl["game_pk"] = pgl["game_pk"].astype(str)
    csw_starts["game_pk"] = csw_starts["game_pk"].astype(str)

    # Filter to requested seasons
    ft = ft[ft["season"].isin(seasons)].copy()
    m3f = m3f[m3f["season"].isin(seasons)].copy()

    print(f"  feature_table: {len(ft)} games")
    print(f"  m3_features: {len(m3f)} games")
    print(f"  pitcher_game_logs: {len(pgl)} rows ({(pgl['starter_flag']==1).sum()} starters)")
    print(f"  csw_starts: {len(csw_starts)} starts")

    # ── Unpivot: one row per starter per game ────────────────────────────────
    # Build home-side rows and away-side rows, then stack
    print("\nUnpivoting to one row per starter per game...")

    rows = []
    for side, sp_id_col, opp_side in [("home", "home_sp_id", "away"),
                                       ("away", "away_sp_id", "home")]:
        side_df = ft[["game_pk", "date", "season",
                       f"{side}_team", f"{opp_side}_team",
                       f"{side}_sp_id", f"{side}_sp_name", f"{side}_sp_throws",
                       f"{side}_sp_xfip", f"{side}_sp_siera",
                       f"{side}_sp_k_pct", f"{side}_sp_bb_pct",
                       f"{side}_sp_avg_ip",
                       f"{side}_bp_xfip",
                       f"{side}_rest_days",
                       "park_factor_runs", "umpire_over_rate",
                       "temperature", "wind_factor_effective",
                       ]].copy()

        # Rename to generic column names
        rename = {
            f"{side}_team": "team_id",
            f"{opp_side}_team": "opponent_team_id",
            f"{side}_sp_id": "sp_id",
            f"{side}_sp_name": "sp_name",
            f"{side}_sp_throws": "handedness_flag",
            f"{side}_sp_xfip": "sp_xfip",
            f"{side}_sp_siera": "sp_siera",
            f"{side}_sp_k_pct": "sp_k_pct",
            f"{side}_sp_bb_pct": "sp_bb_pct",
            f"{side}_sp_avg_ip": "sp_avg_ip",
            f"{side}_bp_xfip": "bullpen_xfip",
            f"{side}_rest_days": "days_rest",
            "park_factor_runs": "park_factor",
            "umpire_over_rate": "umpire_runs_factor",
            "wind_factor_effective": "weather_run_modifier",
        }
        side_df = side_df.rename(columns=rename)
        side_df["is_home"] = 1 if side == "home" else 0

        rows.append(side_df)

    df = pd.concat(rows, ignore_index=True)
    df["sp_id"] = df["sp_id"].astype(int)
    print(f"  Unpivoted: {len(df)} starter-rows ({len(df)//2} games)")

    # ── Join opponent lineup wOBA from m3_features ───────────────────────────
    print("Joining opponent lineup wOBA...")

    # For home starters, opponent is away lineup → away_lineup_woba
    # For away starters, opponent is home lineup → home_lineup_woba
    m3_slim = m3f[["game_pk", "home_lineup_woba", "away_lineup_woba"]].copy()

    df = df.merge(m3_slim, on="game_pk", how="left")
    df["opp_lineup_woba"] = np.where(
        df["is_home"] == 1,
        df["away_lineup_woba"],
        df["home_lineup_woba"]
    )
    df = df.drop(columns=["home_lineup_woba", "away_lineup_woba"])

    # ── Join pitcher game log data (IP, pitches per start) ───────────────────
    print("Joining pitcher game log data...")

    starters = pgl[pgl["starter_flag"] == 1][
        ["game_pk", "player_id", "innings_pitched", "pitches", "game_date", "season"]
    ].copy()
    starters["player_id"] = starters["player_id"].astype(int)
    starters["game_date"] = pd.to_datetime(starters["game_date"])

    # Join actual IP and pitches for this start
    df = df.merge(
        starters[["game_pk", "player_id", "innings_pitched", "pitches"]].rename(
            columns={"player_id": "sp_id",
                     "innings_pitched": "actual_ip",
                     "pitches": "actual_pitches"}),
        on=["game_pk", "sp_id"],
        how="left"
    )

    # ── Compute sp_recent_pc (avg pitch count, last 3 starts) ────────────────
    # LEAKAGE RULE: strictly prior starts only
    print("Computing sp_recent_pc (rolling 3-start pitch count)...")

    starters_sorted = starters.sort_values(["player_id", "season", "game_date"])
    starters_sorted["prior_pc_r3"] = (
        starters_sorted.groupby(["player_id", "season"])["pitches"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )

    pc_lookup = starters_sorted[["game_pk", "player_id", "prior_pc_r3"]].rename(
        columns={"player_id": "sp_id", "prior_pc_r3": "sp_recent_pc"})
    df = df.merge(pc_lookup, on=["game_pk", "sp_id"], how="left")

    # ── Join CSW/Whiff/F-Strike rolling metrics ──────────────────────────────
    # LEAKAGE RULE: pitcher_start_metrics already uses shift(1).rolling()
    # so csw_r5, whiff_r5, f_strike_r5 are strictly prior-start data
    print("Joining CSW/Whiff/F-Strike rolling metrics...")

    csw_starts["pitcher_id"] = csw_starts["pitcher_id"].astype(int)

    # Use rolling 5-start values (strictly prior via shift in Phase A build)
    # Fall back to season-level when rolling incomplete
    csw_cols = csw_starts[["game_pk", "pitcher_id",
                            "csw_r5", "whiff_r5", "f_strike_r5",
                            "csw_pct", "whiff_pct", "f_strike_pct",
                            "fb_velo_r5",
                            "f_strike_season", "whiff_season",
                            "rolling_complete"]].copy()
    csw_cols = csw_cols.rename(columns={"pitcher_id": "sp_id"})

    df = df.merge(csw_cols, on=["game_pk", "sp_id"], how="left")

    # Build final columns: prefer rolling, fall back to season-level
    df["sp_csw_pct"] = df["csw_r5"].fillna(df["csw_pct"])
    df["sp_whiff_pct"] = df["whiff_r5"].fillna(df["whiff_pct"])
    df["sp_fstrike_pct"] = df["f_strike_r5"].fillna(df["f_strike_pct"])

    # Convert handedness to numeric flag (L=0, R=1)
    df["handedness_flag"] = (df["handedness_flag"] == "R").astype(int)

    # ── Select final output columns ─────────────────────────────────────────
    output_cols = [
        # IDs and metadata
        "game_pk", "date", "season", "team_id", "opponent_team_id",
        "is_home", "sp_name", "sp_id",
        # From M3 (read from existing outputs)
        "sp_xfip", "sp_siera", "bullpen_xfip",
        "opp_lineup_woba", "park_factor", "umpire_runs_factor",
        "weather_run_modifier", "handedness_flag", "days_rest",
        # New sim-specific columns
        "sp_csw_pct", "sp_whiff_pct", "sp_fstrike_pct", "sp_recent_pc",
        # Actuals (for training/evaluation only — not model inputs)
        "actual_ip", "actual_pitches",
    ]
    df = df[[c for c in output_cols if c in df.columns]]

    print(f"\nFinal feature table: {len(df)} rows, {len(df.columns)} columns")
    return df


def run_null_coverage_gate(df):
    """Check null coverage for new sim-specific columns. Hard stop if >10%."""
    print("\n" + "=" * 60)
    print("NULL COVERAGE GATE")
    print("=" * 60)

    new_cols = ["sp_csw_pct", "sp_whiff_pct", "sp_fstrike_pct", "sp_recent_pc"]
    total = len(df)
    gate_pass = True

    print(f"\nTotal rows: {total}")
    print(f"\n{'Column':<20} | {'Nulls':>7} | {'Null%':>7} | {'Status':>8}")
    print("-" * 55)
    for col in new_cols:
        if col not in df.columns:
            print(f"{col:<20} | {'MISSING':>7} | {'100.0%':>7} | {'FAIL':>8}")
            gate_pass = False
            continue
        nulls = df[col].isna().sum()
        pct = nulls / total * 100
        status = "PASS" if pct <= 10 else "FAIL"
        if pct > 10:
            gate_pass = False
        print(f"{col:<20} | {nulls:>7} | {pct:>6.1f}% | {status:>8}")

    print(f"\nGate: {'PASS' if gate_pass else '*** FAIL — STOP ***'}")
    return gate_pass


def run_diagnostics(df):
    """Print Phase S1 gate diagnostics."""
    print("\n" + "=" * 60)
    print("PHASE S1 GATE DIAGNOSTICS")
    print("=" * 60)

    print(f"\nRow count: {len(df)}")
    print(f"Seasons: {sorted(df['season'].unique())}")
    print(f"Per season:")
    for s in sorted(df["season"].unique()):
        n = len(df[df["season"] == s])
        print(f"  {s}: {n} starter-rows ({n//2} games)")

    # Distribution summary for new columns
    new_cols = ["sp_csw_pct", "sp_whiff_pct", "sp_fstrike_pct", "sp_recent_pc"]
    print(f"\nDistribution summary (new sim-specific columns):")
    print(f"{'Column':<20} | {'mean':>8} | {'std':>8} | {'min':>8} | {'max':>8} | {'p25':>8} | {'p75':>8}")
    print("-" * 85)
    for col in new_cols:
        if col in df.columns:
            v = df[col].dropna()
            print(f"{col:<20} | {v.mean():>8.2f} | {v.std():>8.2f} | {v.min():>8.2f} | "
                  f"{v.max():>8.2f} | {v.quantile(.25):>8.2f} | {v.quantile(.75):>8.2f}")

    # Correlation matrix: sp_csw_pct vs sp_xfip vs sp_siera
    print(f"\nCorrelation matrix (sp_csw_pct vs sp_xfip vs sp_siera):")
    corr_cols = ["sp_csw_pct", "sp_xfip", "sp_siera"]
    corr_df = df[corr_cols].dropna()
    corr = corr_df.corr()
    print(f"{'':>20} | {'sp_csw_pct':>12} | {'sp_xfip':>12} | {'sp_siera':>12}")
    print("-" * 62)
    for row in corr_cols:
        vals = " | ".join(f"{corr.loc[row, c]:>12.4f}" for c in corr_cols)
        print(f"{row:>20} | {vals}")

    # Also show CSW vs whiff vs fstrike correlations
    print(f"\nCorrelation matrix (sim-specific columns):")
    sim_cols = ["sp_csw_pct", "sp_whiff_pct", "sp_fstrike_pct", "sp_recent_pc"]
    sim_corr = df[sim_cols].dropna().corr()
    print(f"{'':>20} | " + " | ".join(f"{c:>15}" for c in sim_cols))
    print("-" * 85)
    for row in sim_cols:
        vals = " | ".join(f"{sim_corr.loc[row, c]:>15.4f}" for c in sim_cols)
        print(f"{row:>20} | {vals}")


if __name__ == "__main__":
    df = build_historical_sim_inputs(seasons=(2022, 2023, 2024))

    gate_pass = run_null_coverage_gate(df)

    if not gate_pass:
        print("\n*** NULL COVERAGE GATE FAILED — stopping before model fit ***")
        print("Report null columns to user before proceeding.")
        sys.exit(1)

    run_diagnostics(df)

    # Save historical feature table
    out_path = OUT_DIR / "sim_inputs_historical_2022_2024.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path} ({len(df)} rows)")

    print("\n*** PHASE S1 COMPLETE — awaiting confirmation to proceed to S2 ***")
