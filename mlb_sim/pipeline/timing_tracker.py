#!/usr/bin/env python3
"""
MLB Sim Engine — Timing Performance Tracker
=============================================
Computes observational win/loss/push graded at each cohort's captured
line, NOT the production closing line. Research output only — does not
affect signal generation, sizing, or hard stop.

Timing-cohort grades exist only in timing_analysis_2026.json.
Never written back to signals_2026.parquet.
"""

import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("timing_tracker")

BASE = Path(__file__).resolve().parent.parent
SIGNALS_PATH = BASE / "logs" / "signals_2026.parquet"
TIMING_PATH = BASE / "logs" / "timing_analysis_2026.json"

MIN_N = 25


def _cohort_grade(actual_total, cohort_line, stake):
    """Grade a single signal at a cohort's line (for under signals)."""
    if pd.isna(actual_total) or pd.isna(cohort_line):
        return None, None
    actual = float(actual_total)
    line = float(cohort_line)
    if actual < line:
        return "WIN", float(stake) * (100 / 110)
    elif actual > line:
        return "LOSS", -float(stake)
    else:
        return "PUSH", 0.0


def _cohort_stats(df, line_col, stake_col="stake_units", closing_col="closing_line"):
    """Compute stats for one timing cohort."""
    # Filter to resolved signals where cohort line exists
    valid = df[(df["resolved"] == 1) & df[line_col].notna() & df["actual_total"].notna()].copy()
    n = len(valid)

    if n == 0:
        return {"n": 0, "win_rate": None, "observational_roi": None,
                "net_units": None, "avg_clv": None, "pct_positive_clv": None,
                "avg_line": None, "insufficient": True}

    # Grade at cohort line
    results = valid.apply(
        lambda r: _cohort_grade(r["actual_total"], r[line_col], r[stake_col]),
        axis=1, result_type="expand"
    )
    valid["coh_result"] = results[0]
    valid["coh_net"] = results[1]

    graded = valid[valid["coh_result"].notna()]
    n_graded = len(graded)
    if n_graded == 0:
        return {"n": 0, "win_rate": None, "observational_roi": None,
                "net_units": None, "avg_clv": None, "pct_positive_clv": None,
                "avg_line": None, "insufficient": True}

    wins = (graded["coh_result"] == "WIN").sum()
    win_rate = round(wins / n_graded * 100, 1)
    net = graded["coh_net"].sum()
    wagered = graded[stake_col].sum()
    roi = round(net / wagered * 100, 1) if wagered > 0 else 0

    # CLV: closing_line - cohort_line (positive = line moved up, good for unders)
    clv_valid = graded[graded[closing_col].notna()]
    if len(clv_valid) > 0:
        clv_vals = clv_valid[closing_col].astype(float) - clv_valid[line_col].astype(float)
        avg_clv = round(float(clv_vals.mean()), 3)
        pct_pos = round((clv_vals > 0).mean() * 100, 1)
    else:
        avg_clv = None
        pct_pos = None

    avg_line = round(float(graded[line_col].mean()), 2)
    insufficient = n_graded < MIN_N

    return {
        "n": int(n_graded),
        "win_rate": win_rate,
        "observational_roi": roi,
        "net_units": round(float(net), 2),
        "avg_clv": avg_clv,
        "pct_positive_clv": pct_pos,
        "avg_line": avg_line,
        "insufficient": insufficient,
    }


def compute_timing_analysis():
    """Compute all timing cohort stats and save to JSON."""
    if not SIGNALS_PATH.exists():
        return {}

    df = pd.read_parquet(SIGNALS_PATH)

    cohort_defs = {
        "signal_time": "line_at_signal_time",
        "open": "line_at_open",
        "midday": "line_at_midday",
        "close_pull": "line_at_close",
    }

    # Per-cohort stats (all resolved signals with that cohort's line)
    cohorts = {}
    for name, col in cohort_defs.items():
        if col in df.columns:
            cohorts[name] = _cohort_stats(df, col)
        else:
            cohorts[name] = {"n": 0, "insufficient": True, "note": f"column {col} not present"}

    # Complete-record comparison: signals where ALL FOUR lines are non-null
    complete_mask = pd.Series(True, index=df.index)
    for col in cohort_defs.values():
        if col in df.columns:
            complete_mask &= df[col].notna()
        else:
            complete_mask = pd.Series(False, index=df.index)
            break

    complete_df = df[complete_mask & (df["resolved"] == 1) & df["actual_total"].notna()]
    complete = {}
    for name, col in cohort_defs.items():
        if col in complete_df.columns:
            complete[name] = _cohort_stats(complete_df, col)
        else:
            complete[name] = {"n": 0, "insufficient": True}
    complete["n_complete_records"] = int(len(complete_df))

    result = {
        "last_updated": date.today().isoformat(),
        "cohorts": cohorts,
        "complete_records": complete,
    }

    BASE.joinpath("logs").mkdir(parents=True, exist_ok=True)
    with open(TIMING_PATH, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Timing analysis updated: "
                f"signal_time N={cohorts.get('signal_time',{}).get('n',0)}, "
                f"complete N={complete.get('n_complete_records',0)}")
    return result
