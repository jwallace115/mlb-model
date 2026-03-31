#!/usr/bin/env python3
"""
Phase 5: Market Integration and Signal Generation.

Steps:
  1. Load simulation outputs + canonical market data; join on game_id
  2. Remove vig: fair_over = implied_over / (implied_over + implied_under)
  3. Compute edge_over_2_5 = P_over_2_5 - fair_over  (edge_under = -edge_over)
  4. Generate signals: |edge_over_2_5| >= 0.04
  5. Edge bucket calibration table on validate set
  6. Probability bucket calibration on validate set
  7. Full performance report by split / side / edge bucket / league / line
  8. Save soccer_market_outputs.parquet, soccer_decisions.parquet, phase5_signal_audit.txt

Hard rules:
  - NO look-ahead: calibration tables are built on validate only, then applied to OOS
  - Signal threshold is fixed at EDGE_THRESHOLD_PROVISIONAL = 0.04
  - ROI computed at −110 American: win = +0.9091, loss = −1.0

Usage:
    python3 -m soccer.phase5_market_signals
"""

import io
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd

from soccer.config import (
    CANONICAL_PATH,
    DATA_DIR,
    DECISIONS_PATH,
    EDGE_THRESHOLD_PROVISIONAL,
    MODEL_OUTPUTS_PATH,
    OOS_SEASON,
    SEASON_LABELS,
    TRAIN_SEASONS,
    VALIDATE_SEASON,
)

logger = logging.getLogger(__name__)

SIMULATION_PATH    = os.path.join(DATA_DIR, "soccer_simulation_outputs.parquet")
MARKET_OUTPUT_PATH = os.path.join(DATA_DIR, "soccer_market_outputs.parquet")
AUDIT_PATH         = os.path.join(DATA_DIR, "phase5_signal_audit.txt")

SEP  = "═" * 72
SEP2 = "─" * 72

# ROI constants
WIN_UNIT  = 1.0 / 1.1      # +0.9091 at −110
LOSS_UNIT = -1.0


# ── Step 1: Load & join ───────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    """
    Load simulation outputs; join canonical market columns on game_id.
    Returns merged DataFrame.
    """
    sim = pd.read_parquet(SIMULATION_PATH)
    logger.info(f"Simulation outputs: {len(sim):,} rows, cols: {list(sim.columns)}")

    canonical = pd.read_parquet(CANONICAL_PATH, columns=[
        "game_id", "regulation_total_90", "official_bet_total",
        "over_price", "under_price", "market_available",
        "season_year", "league_id",
    ])
    logger.info(f"Canonical: {len(canonical):,} rows")

    # sim should already have season_year, league_id — drop from canonical if duplicated
    canon_cols = ["game_id", "regulation_total_90", "official_bet_total",
                  "over_price", "under_price", "market_available"]
    # keep season_year/league_id from canonical if not in sim
    if "season_year" not in sim.columns:
        canon_cols += ["season_year"]
    if "league_id" not in sim.columns:
        canon_cols += ["league_id"]

    merged = sim.merge(canonical[canon_cols], on="game_id", how="left",
                       suffixes=("", "_canon"))

    # Resolve any duplicate cols (season_year_canon, league_id_canon)
    for col in ["season_year", "league_id", "regulation_total_90",
                "official_bet_total", "market_available"]:
        dup = f"{col}_canon"
        if dup in merged.columns:
            merged[col] = merged[col].combine_first(merged[dup])
            merged.drop(columns=[dup], inplace=True)

    n_market = merged["market_available"].sum()
    logger.info(f"Merged: {len(merged):,} rows, market_available={n_market:,}")
    return merged


# ── Step 2-3: Vig removal + edge ─────────────────────────────────────────────

def add_fair_probs_and_edges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert decimal B365 odds to fair probabilities (vig removed).
    Compute edge_over_2_5 = P_over_2_5 − fair_over_2_5.
    """
    df = df.copy()

    # Implied probabilities
    df["implied_over_2_5"]  = 1.0 / df["over_price"]
    df["implied_under_2_5"] = 1.0 / df["under_price"]
    df["total_implied_2_5"] = df["implied_over_2_5"] + df["implied_under_2_5"]

    # Vig-removed fair probabilities
    df["fair_over_2_5"]  = df["implied_over_2_5"]  / df["total_implied_2_5"]
    df["fair_under_2_5"] = df["implied_under_2_5"] / df["total_implied_2_5"]

    # Vig (overround) as informational
    df["vig_2_5"] = df["total_implied_2_5"] - 1.0

    # Edge: model probability − fair probability
    df["edge_over_2_5"]  =  df["P_over_2_5"]  - df["fair_over_2_5"]
    df["edge_under_2_5"] = -df["edge_over_2_5"]   # guaranteed: sum = 0

    return df


# ── Step 4: Signal generation ─────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame, threshold: float = EDGE_THRESHOLD_PROVISIONAL) -> pd.DataFrame:
    """
    Generate signal column and result for each signalled game.

    signal_side: "OVER" | "UNDER" | None
    signal_edge: the positive edge magnitude (always >= threshold when signalled)
    result:      "WIN" | "LOSS" | None
    actual_over_2_5: True if regulation_total_90 > 2.5 (>= 3 goals)
    """
    df = df.copy()

    # Actual outcomes
    df["actual_over_2_5"]  = df["regulation_total_90"] > 2.5
    df["actual_under_2_5"] = df["regulation_total_90"] < 2.5   # excludes ties at 2.5 (impossible integer totals)

    # Signals — only where market is available
    over_signal  = df["market_available"] & (df["edge_over_2_5"]  >=  threshold)
    under_signal = df["market_available"] & (df["edge_under_2_5"] >=  threshold)

    df["signal_side"] = None
    df["signal_edge"] = np.nan

    df.loc[over_signal,  "signal_side"] = "OVER"
    df.loc[under_signal, "signal_side"] = "UNDER"
    df.loc[over_signal,  "signal_edge"] = df.loc[over_signal,  "edge_over_2_5"]
    df.loc[under_signal, "signal_edge"] = df.loc[under_signal, "edge_under_2_5"]

    # Result
    df["result"] = None
    df.loc[over_signal  & df["actual_over_2_5"],  "result"] = "WIN"
    df.loc[over_signal  & df["actual_under_2_5"], "result"] = "LOSS"
    df.loc[under_signal & df["actual_under_2_5"], "result"] = "WIN"
    df.loc[under_signal & df["actual_over_2_5"],  "result"] = "LOSS"

    # Units P&L at −110
    df["units"] = np.nan
    df.loc[df["result"] == "WIN",  "units"] = WIN_UNIT
    df.loc[df["result"] == "LOSS", "units"] = LOSS_UNIT

    return df


# ── Step 5: Edge bucket calibration ───────────────────────────────────────────

def edge_bucket_table(df: pd.DataFrame, split_label: str, buf: io.StringIO) -> float:
    """
    Build edge bucket table on validate set.
    Returns the lowest-edge bucket threshold where hit_rate >= 52.5% and n >= 20.
    """
    signalled = df[df["signal_side"].notna()].copy()
    if signalled.empty:
        buf.write(f"  No signals in {split_label}.\n\n")
        return EDGE_THRESHOLD_PROVISIONAL

    bins = [0.02, 0.04, 0.06, 0.08, 0.10, 1.0]
    labels = ["0.02–0.04", "0.04–0.06", "0.06–0.08", "0.08–0.10", "0.10+"]

    signalled["edge_bucket"] = pd.cut(
        signalled["signal_edge"],
        bins=bins,
        labels=labels,
        right=False,
        include_lowest=True,
    )

    buf.write(f"\n  Edge Bucket Calibration — {split_label}\n")
    buf.write(f"  {SEP2[:60]}\n")
    buf.write(f"  {'Bucket':<12} {'N':>6} {'Wins':>6} {'Hit Rate':>10} {'ROI':>8}  Meets Threshold\n")
    buf.write(f"  {SEP2[:60]}\n")

    recommended_threshold = EDGE_THRESHOLD_PROVISIONAL
    for lbl in labels:
        grp = signalled[signalled["edge_bucket"] == lbl]
        n = len(grp)
        if n == 0:
            buf.write(f"  {lbl:<12} {'—':>6}\n")
            continue
        wins = (grp["result"] == "WIN").sum()
        hit  = wins / n
        roi  = grp["units"].sum() / n
        meets = "✓" if (hit >= 0.525 and n >= 20) else "✗"
        buf.write(f"  {lbl:<12} {n:>6} {wins:>6} {hit:>9.1%} {roi:>8.3f}  {meets}\n")

    buf.write(f"\n  Provisional threshold used: {EDGE_THRESHOLD_PROVISIONAL:.2f}\n\n")
    return recommended_threshold


# ── Step 6: Probability bucket calibration ────────────────────────────────────

def prob_bucket_calibration(df: pd.DataFrame, split_label: str, buf: io.StringIO):
    """
    Compare model P_over_2_5 to actual over rate in probability bins.
    Built on validate, informational for OOS.
    """
    market_df = df[df["market_available"]].copy()
    if market_df.empty:
        buf.write(f"  No market rows in {split_label}.\n\n")
        return

    bins   = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 1.01]
    labels = ["0.45–0.50", "0.50–0.55", "0.55–0.60", "0.60–0.65", "0.65–0.70", "0.70+"]

    market_df["p_bucket"] = pd.cut(
        market_df["P_over_2_5"],
        bins=bins,
        labels=labels,
        right=False,
        include_lowest=True,
    )

    buf.write(f"\n  Probability Bucket Calibration — {split_label}\n")
    buf.write(f"  {SEP2[:60]}\n")
    buf.write(f"  {'P_over bucket':<14} {'N':>6} {'Actual Over%':>13} {'Model P_over':>13} {'Delta':>8}\n")
    buf.write(f"  {SEP2[:60]}\n")

    for lbl in labels:
        grp = market_df[market_df["p_bucket"] == lbl]
        n   = len(grp)
        if n == 0:
            buf.write(f"  {lbl:<14} {'—':>6}\n")
            continue
        actual_rate = grp["actual_over_2_5"].mean()
        model_p     = grp["P_over_2_5"].mean()
        delta       = actual_rate - model_p
        buf.write(f"  {lbl:<14} {n:>6} {actual_rate:>12.1%} {model_p:>12.1%} {delta:>+8.3f}\n")

    buf.write("\n")


# ── Step 7: Performance reports ───────────────────────────────────────────────

def _perf_block(grp_df: pd.DataFrame, label: str, buf: io.StringIO, indent: int = 2):
    """Write a single performance block: N, W-L, hit rate, ROI, units."""
    ind = " " * indent
    sig = grp_df[grp_df["signal_side"].notna()]
    n   = len(sig)
    if n == 0:
        buf.write(f"{ind}{label}: no signals\n")
        return
    wins  = (sig["result"] == "WIN").sum()
    loss  = (sig["result"] == "LOSS").sum()
    hit   = wins / n
    units = sig["units"].sum()
    roi   = units / n
    buf.write(f"{ind}{label:30s}  N={n:4d}  {wins}W-{loss}L  hit={hit:.1%}  ROI={roi:+.3f}  Σ={units:+.2f}u\n")


def performance_report(df: pd.DataFrame, buf: io.StringIO):
    """Full performance report by split, side, edge bucket, league, line."""
    splits = {
        "TRAIN":    df[df["season_year"].isin([SEASON_LABELS.get(s, s) for s in TRAIN_SEASONS])],
        "VALIDATE": df[df["season_year"] == SEASON_LABELS.get(VALIDATE_SEASON, VALIDATE_SEASON)],
        "OOS":      df[df["season_year"] == SEASON_LABELS.get(OOS_SEASON, OOS_SEASON)],
        "ALL":      df,
    }

    buf.write(f"\n{SEP}\n")
    buf.write("  PERFORMANCE REPORT — Phase 5 Market Signals\n")
    buf.write(f"{SEP}\n")

    for split_name, sdf in splits.items():
        n_total   = len(sdf)
        n_market  = sdf["market_available"].sum() if "market_available" in sdf.columns else 0
        n_signals = sdf["signal_side"].notna().sum()
        sig_rate  = n_signals / n_market if n_market > 0 else 0

        buf.write(f"\n  ── {split_name} ({n_total:,} games, {n_market:,} with market, "
                  f"{n_signals} signals [{sig_rate:.1%}]) ──\n")

        _perf_block(sdf, "ALL SIGNALS", buf)

        # By side
        for side in ["OVER", "UNDER"]:
            side_df = sdf[sdf["signal_side"] == side]
            _perf_block(side_df, f"  {side}", buf, indent=4)

        # By league
        buf.write("    By league:\n")
        for lg in sorted(sdf["league_id"].dropna().unique()):
            lg_df = sdf[sdf["league_id"] == lg]
            _perf_block(lg_df, f"      {lg}", buf, indent=6)

        # By edge bucket (signals only)
        sig_df = sdf[sdf["signal_side"].notna()].copy()
        if not sig_df.empty:
            bins   = [0.04, 0.06, 0.08, 0.10, 1.0]
            blabels = ["0.04–0.06", "0.06–0.08", "0.08–0.10", "0.10+"]
            sig_df["edge_bucket"] = pd.cut(
                sig_df["signal_edge"], bins=bins, labels=blabels,
                right=False, include_lowest=True,
            )
            buf.write("    By edge bucket:\n")
            for lbl in blabels:
                grp = sig_df[sig_df["edge_bucket"] == lbl]
                _perf_block(grp, f"      {lbl}", buf, indent=6)

    buf.write(f"\n{SEP}\n")


def summary_table(df: pd.DataFrame, buf: io.StringIO):
    """One-line summary table by split."""
    buf.write(f"\n{SEP}\n")
    buf.write("  SUMMARY TABLE\n")
    buf.write(f"  {SEP2}\n")
    buf.write(f"  {'Split':<12} {'Games':>6} {'Signals':>8} {'Sig%':>6} {'W':>5} {'L':>5} {'Hit%':>7} {'ROI':>8} {'Units':>8}\n")
    buf.write(f"  {SEP2}\n")

    rows = [
        ("TRAIN",    SEASON_LABELS.get(VALIDATE_SEASON, VALIDATE_SEASON), True),
        ("VALIDATE", SEASON_LABELS.get(VALIDATE_SEASON, VALIDATE_SEASON), False),
        ("OOS",      SEASON_LABELS.get(OOS_SEASON, OOS_SEASON), False),
        ("ALL",      None, False),
    ]

    def _row(label, sdf):
        n      = len(sdf)
        n_mkt  = sdf["market_available"].sum()
        sig    = sdf[sdf["signal_side"].notna()]
        ns     = len(sig)
        sr     = ns / n_mkt if n_mkt > 0 else 0
        wins   = (sig["result"] == "WIN").sum()
        losses = (sig["result"] == "LOSS").sum()
        hit    = wins / ns if ns > 0 else float("nan")
        units  = sig["units"].sum()
        roi    = units / ns if ns > 0 else float("nan")
        hit_s  = f"{hit:.1%}" if not np.isnan(hit) else "—"
        roi_s  = f"{roi:+.3f}" if not np.isnan(roi) else "—"
        buf.write(f"  {label:<12} {n:>6} {ns:>8} {sr:>5.1%} {wins:>5} {losses:>5} {hit_s:>7} {roi_s:>8} {units:>8.2f}\n")

    split_map = {
        "TRAIN":    df[df["season_year"].isin([SEASON_LABELS.get(s, s) for s in TRAIN_SEASONS])],
        "VALIDATE": df[df["season_year"] == SEASON_LABELS.get(VALIDATE_SEASON, VALIDATE_SEASON)],
        "OOS":      df[df["season_year"] == SEASON_LABELS.get(OOS_SEASON, OOS_SEASON)],
        "ALL":      df,
    }
    for lbl, sdf in split_map.items():
        _row(lbl, sdf)

    buf.write(f"  {SEP2}\n\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    buf = io.StringIO()

    def pw(s=""):
        print(s)
        buf.write(s + "\n")

    pw(SEP)
    pw("  PHASE 5: Market Integration and Signal Generation")
    pw(SEP)

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    df = load_data()
    pw(f"\n  Loaded {len(df):,} rows")
    pw(f"  Columns: {list(df.columns)}")

    # Sanity check
    assert "P_over_2_5" in df.columns, "P_over_2_5 not found in simulation outputs"
    assert "over_price"  in df.columns, "over_price not found — join failed"

    # ── Step 2-3: Vig removal + edge ─────────────────────────────────────────
    df = add_fair_probs_and_edges(df)

    vig_mean = df.loc[df["market_available"], "vig_2_5"].mean()
    pw(f"\n  Vig check (market rows): mean={vig_mean:.3f}  "
       f"min={df['vig_2_5'].min():.3f}  max={df['vig_2_5'].max():.3f}")

    # Fair prob sanity
    fair_mean = df.loc[df["market_available"], "fair_over_2_5"].mean()
    pw(f"  Fair P_over_2_5 (market rows): mean={fair_mean:.3f}")
    pw(f"  Model P_over_2_5 (all rows):   mean={df['P_over_2_5'].mean():.3f}")

    # Edge distribution
    edge_mean = df.loc[df["market_available"], "edge_over_2_5"].mean()
    edge_std  = df.loc[df["market_available"], "edge_over_2_5"].std()
    pw(f"  Edge_over_2_5 (market rows):   mean={edge_mean:+.4f}  std={edge_std:.4f}")

    # ── Step 4: Signals ───────────────────────────────────────────────────────
    df = generate_signals(df, threshold=EDGE_THRESHOLD_PROVISIONAL)

    n_over  = (df["signal_side"] == "OVER").sum()
    n_under = (df["signal_side"] == "UNDER").sum()
    n_total_sig = n_over + n_under
    pw(f"\n  Signals @ threshold={EDGE_THRESHOLD_PROVISIONAL:.2f}:  "
       f"OVER={n_over}  UNDER={n_under}  TOTAL={n_total_sig}")

    # ── Step 5: Edge bucket calibration (validate only) ──────────────────────
    val_label = SEASON_LABELS.get(VALIDATE_SEASON, VALIDATE_SEASON)
    oos_label = SEASON_LABELS.get(OOS_SEASON, OOS_SEASON)

    val_df = df[df["season_year"] == val_label]
    oos_df = df[df["season_year"] == oos_label]

    pw("\n" + SEP)
    pw("  EDGE BUCKET CALIBRATION")
    pw(SEP)
    tmp_buf = io.StringIO()
    edge_bucket_table(val_df, f"VALIDATE ({val_label})", tmp_buf)
    edge_bucket_table(oos_df, f"OOS ({oos_label})", tmp_buf)
    out = tmp_buf.getvalue()
    print(out, end="")
    buf.write(out)

    # ── Step 6: Probability bucket calibration ────────────────────────────────
    pw("\n" + SEP)
    pw("  PROBABILITY BUCKET CALIBRATION")
    pw(SEP)
    tmp_buf2 = io.StringIO()
    prob_bucket_calibration(val_df, f"VALIDATE ({val_label})", tmp_buf2)
    prob_bucket_calibration(oos_df, f"OOS ({oos_label})", tmp_buf2)
    out2 = tmp_buf2.getvalue()
    print(out2, end="")
    buf.write(out2)

    # ── Step 7: Performance report ────────────────────────────────────────────
    tmp_buf3 = io.StringIO()
    performance_report(df, tmp_buf3)
    out3 = tmp_buf3.getvalue()
    print(out3, end="")
    buf.write(out3)

    tmp_buf4 = io.StringIO()
    summary_table(df, tmp_buf4)
    out4 = tmp_buf4.getvalue()
    print(out4, end="")
    buf.write(out4)

    # ── Save outputs ──────────────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)

    # Market outputs: all rows with market columns + edge + fair probs
    market_cols = [
        "game_id", "season_year", "league_id",
        "P_over_2_5", "P_under_2_5",
        "fair_over_2_5", "fair_under_2_5", "vig_2_5",
        "edge_over_2_5", "edge_under_2_5",
        "actual_over_2_5",
        "market_available",
    ]
    # include whatever's available
    market_cols_avail = [c for c in market_cols if c in df.columns]
    df[market_cols_avail].to_parquet(MARKET_OUTPUT_PATH, index=False)
    pw(f"\n  Saved: {MARKET_OUTPUT_PATH}  ({len(df):,} rows)")

    # Decisions: signalled rows only
    decision_cols = [
        "game_id", "game_date", "season_year", "league_id",
        "home_team", "away_team",
        "P_over_2_5", "fair_over_2_5", "edge_over_2_5",
        "signal_side", "signal_edge",
        "closing_total_line",
        "over_price", "under_price",
        "regulation_total_90", "actual_over_2_5",
        "result", "units",
    ]
    decision_cols_avail = [c for c in decision_cols if c in df.columns]
    decisions = df[df["signal_side"].notna()][decision_cols_avail].copy()
    decisions.to_parquet(DECISIONS_PATH, index=False)
    pw(f"  Saved: {DECISIONS_PATH}  ({len(decisions):,} signals)")

    # Audit log
    with open(AUDIT_PATH, "w") as f:
        f.write(buf.getvalue())
    pw(f"  Saved: {AUDIT_PATH}")

    pw(f"\n  Phase 5 complete.\n")


if __name__ == "__main__":
    main()
