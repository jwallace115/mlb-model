#!/usr/bin/env python3
"""
MLB Sim Engine — Performance Tracker
Reads signals_2026.parquet, computes rolling stats, checks hard stop.
"""

import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent
SIGNALS_PATH = BASE / "logs" / "signals_2026.parquet"
PERF_PATH = BASE / "logs" / "rolling_performance_2026.json"
STATUS_PATH = BASE / "pipeline" / "engine_status.json"

HARD_STOP_ROI = -8.0
HARD_STOP_MIN_N = 50


def _load_resolved():
    """Load resolved (non-postponed) signals only."""
    if not SIGNALS_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(SIGNALS_PATH)
    return df[df["resolved"] == 1]


def _window_stats(df, label=""):
    """Compute stats for a window of resolved signals. Pushes count as losses."""
    if len(df) == 0:
        return {"n": 0, "win_rate": None, "roi": None, "net_units": None}
    n = len(df)
    wins = int((df["result"] == "WIN").sum())
    decided = n  # all resolved signals count (pushes are losses)
    wr = wins / decided * 100 if decided > 0 else 0
    # Pushes: treat as -stake instead of net_units=0
    net = sum(-float(r["stake_units"]) if r.get("result") == "PUSH" else float(r.get("net_units", 0))
              for _, r in df.iterrows())
    wagered = df["stake_units"].sum()
    roi = net / wagered * 100 if wagered > 0 else 0
    return {"n": int(n), "win_rate": round(wr, 1), "roi": round(roi, 1),
            "net_units": round(float(net), 2)}


def _bucket_stats(df, bucket):
    sub = df[df["threshold_bucket"] == bucket]
    return _window_stats(sub)


def _clv_stats(df):
    clv_rows = df[df["clv"].notna()]
    if len(clv_rows) < 10:
        return {"avg_clv": None, "pct_positive_clv": None, "n_clv": int(len(clv_rows))}
    avg = clv_rows["clv"].mean()
    pct_pos = (clv_rows["clv"] > 0).mean() * 100
    return {"avg_clv": round(float(avg), 3), "pct_positive_clv": round(pct_pos, 1),
            "n_clv": int(len(clv_rows))}


def compute_performance():
    """Compute all rolling performance metrics and save to JSON."""
    resolved = _load_resolved()

    if len(resolved) == 0:
        result = {"insufficient_data": True, "last_updated": date.today().isoformat(),
                  "season_to_date": _window_stats(resolved),
                  "last_25": _window_stats(resolved), "last_50": _window_stats(resolved)}
        with open(PERF_PATH, "w") as f:
            json.dump(result, f, indent=2)
        return result

    resolved = resolved.sort_values("date").reset_index(drop=True)

    # Windows
    std = _window_stats(resolved, "season_to_date")
    last_25 = _window_stats(resolved.tail(25), "last_25")
    last_50 = _window_stats(resolved.tail(50), "last_50")

    # Buckets
    b_057 = _bucket_stats(resolved, "0.57-0.60")
    b_060 = _bucket_stats(resolved, ">0.60")

    # CLV
    clv = _clv_stats(resolved)

    # dual_high_csw subset
    dhc = resolved[resolved["dual_high_csw"] == 1]
    dhc_stats = _window_stats(dhc) if len(dhc) >= 10 else {"n": int(len(dhc)), "note": "insufficient_data"}

    result = {
        "insufficient_data": False,
        "last_updated": date.today().isoformat(),
        "season_to_date": std,
        "last_25": last_25,
        "last_50": last_50,
        "by_bucket": {"0.57-0.60": b_057, ">0.60": b_060},
        "clv": clv,
        "dual_high_csw": dhc_stats,
    }

    with open(PERF_PATH, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Performance updated: STD N={std['n']}, ROI={std['roi']}")
    return result


def check_hard_stop(perf):
    """Check hard stop threshold. Returns True if engine should pause."""
    std = perf.get("season_to_date", {})
    n = std.get("n", 0)
    roi = std.get("roi")
    if roi is None or n < HARD_STOP_MIN_N:
        return False
    if roi < HARD_STOP_ROI:
        logger.warning(f"HARD STOP TRIGGERED: ROI={roi}% at N={n} (threshold={HARD_STOP_ROI}%)")
        # Update engine status
        status = {
            "status": "PAUSED",
            "last_updated": date.today().isoformat(),
            "pause_reason": f"Hard stop: ROI={roi}% at N={n}",
            "pause_triggered_at_n": n,
            "pause_triggered_at_roi": roi,
            "resume_authorized_by": None,
            "resume_date": None,
        }
        with open(STATUS_PATH, "w") as f:
            json.dump(status, f, indent=2)
        return True
    return False
