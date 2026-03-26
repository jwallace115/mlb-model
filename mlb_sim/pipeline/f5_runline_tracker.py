#!/usr/bin/env python3
"""
F5 Run Line Performance Tracker — independent from all other engines.
"""

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger("f5_rl_perf")

BASE = Path(__file__).resolve().parent.parent
SIGNALS_PATH = BASE / "logs" / "f5_runline_2026.parquet"
PERF_PATH = BASE / "logs" / "f5_runline_performance_2026.json"
STATUS_PATH = BASE / "pipeline" / "f5_runline_status.json"

HARD_STOP_ROI = -10.0
HARD_STOP_MIN_N = 40


def _load_resolved():
    if not SIGNALS_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(SIGNALS_PATH)
    return df[df["resolved"] == 1]


def _window_stats(df):
    if len(df) == 0:
        return {"n": 0, "win_rate": None, "push_rate": None,
                "roi": None, "net_units": None, "avg_price": None}
    n = len(df)
    wins = (df["result"] == "WIN").sum()
    losses = (df["result"] == "LOSS").sum()
    pushes = (df["result"] == "PUSH").sum()
    n_nonpush = wins + losses
    wr = wins / n_nonpush * 100 if n_nonpush > 0 else 0
    push_rate = pushes / n * 100
    net = df["net_units"].sum()
    wagered = df["stake_units"].sum()
    roi = net / wagered * 100 if wagered > 0 else 0
    avg_price = df["bet_price"].mean() if "bet_price" in df.columns else None

    return {"n": int(n), "win_rate": round(wr, 1), "push_rate": round(push_rate, 1),
            "roi": round(roi, 1), "net_units": round(float(net), 2),
            "avg_price": round(float(avg_price), 0) if avg_price is not None else None}


def _clv_stats(df):
    clv_rows = df[df["f5_clv"].notna()]
    if len(clv_rows) < 10:
        return {"avg_f5_clv": None, "pct_positive_f5_clv": None, "n_clv": int(len(clv_rows))}
    avg = clv_rows["f5_clv"].mean()
    pct_pos = (clv_rows["f5_clv"] > 0).mean() * 100
    return {"avg_f5_clv": round(float(avg), 3),
            "pct_positive_f5_clv": round(pct_pos, 1),
            "n_clv": int(len(clv_rows))}


def compute_performance():
    resolved = _load_resolved()

    if len(resolved) == 0:
        result = {
            "insufficient_data": True,
            "last_updated": date.today().isoformat(),
            "season_to_date": _window_stats(resolved),
            "last_25": _window_stats(resolved),
            "last_50": _window_stats(resolved),
        }
        PERF_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PERF_PATH, "w") as f:
            json.dump(result, f, indent=2)
        return result

    resolved = resolved.sort_values("date").reset_index(drop=True)

    std = _window_stats(resolved)
    last_25 = _window_stats(resolved.tail(25))
    last_50 = _window_stats(resolved.tail(50))
    clv = _clv_stats(resolved)

    result = {
        "insufficient_data": False,
        "last_updated": date.today().isoformat(),
        "season_to_date": std,
        "last_25": last_25,
        "last_50": last_50,
        "clv": clv,
    }

    with open(PERF_PATH, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"F5 RL performance: STD N={std['n']}, ROI={std['roi']}")
    return result


def check_hard_stop(perf):
    std = perf.get("season_to_date", {})
    n = std.get("n", 0)
    roi = std.get("roi")
    if roi is None or n < HARD_STOP_MIN_N:
        return False
    if roi < HARD_STOP_ROI:
        logger.warning(f"F5 RL HARD STOP: ROI={roi}% at N={n}")
        status = {
            "status": "PAUSED",
            "last_updated": date.today().isoformat(),
            "pause_reason": f"Hard stop: ROI={roi}% at N={n}",
            "pause_triggered_at_n": n,
            "pause_triggered_at_roi": roi,
            "resume_authorized_by": None,
            "resume_date": None,
            "deployment_note": None,
        }
        with open(STATUS_PATH, "w") as f:
            json.dump(status, f, indent=2)
        return True
    return False
