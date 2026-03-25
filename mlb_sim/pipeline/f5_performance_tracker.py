#!/usr/bin/env python3
"""
F5 Performance Tracker — Rolling stats and hard stop for F5 signals.
Independent from V1 full-game performance tracker.
Uses combined F5 ROI (under + over) for hard stop — side-specific
ROI does not trigger a pause.
"""

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger("f5_perf")

BASE = Path(__file__).resolve().parent.parent
F5_SIGNALS_PATH = BASE / "logs" / "f5_signals_2026.parquet"
F5_PERF_PATH = BASE / "logs" / "f5_rolling_performance_2026.json"
F5_STATUS_PATH = BASE / "pipeline" / "f5_engine_status.json"

HARD_STOP_ROI = -8.0
HARD_STOP_MIN_N = 50


def _load_resolved():
    """Load resolved (non-postponed) F5 signals only."""
    if not F5_SIGNALS_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(F5_SIGNALS_PATH)
    return df[df["resolved"] == 1]


def _window_stats(df):
    """Compute stats for a window of resolved signals."""
    if len(df) == 0:
        return {"n": 0, "win_rate": None, "roi": None, "net_units": None}
    n = len(df)
    wins = (df["result"] == "WIN").sum()
    losses = (df["result"] == "LOSS").sum()
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    net = df["net_units"].sum()
    wagered = df["stake_units"].sum()
    roi = net / wagered * 100 if wagered > 0 else 0
    return {"n": int(n), "win_rate": round(wr, 1), "roi": round(roi, 1),
            "net_units": round(float(net), 2)}


def _side_stats(df, side):
    """Stats for a specific side (UNDER or OVER)."""
    sub = df[df["f5_signal_side"] == side]
    if len(sub) < 5:
        return {"n": int(len(sub)), "insufficient": True}
    return _window_stats(sub)


def _clv_stats(df):
    """CLV stats for F5 signals with closing line data."""
    clv_rows = df[df["f5_clv_signed"].notna()]
    if len(clv_rows) < 10:
        return {"avg_f5_clv_signed": None, "pct_positive_f5_clv_signed": None,
                "n_clv": int(len(clv_rows))}
    avg = clv_rows["f5_clv_signed"].mean()
    pct_pos = (clv_rows["f5_clv_signed"] > 0).mean() * 100
    return {"avg_f5_clv_signed": round(float(avg), 3),
            "pct_positive_f5_clv_signed": round(pct_pos, 1),
            "n_clv": int(len(clv_rows))}


def compute_performance():
    """Compute all F5 rolling performance metrics and save to JSON."""
    resolved = _load_resolved()

    if len(resolved) == 0:
        result = {
            "insufficient_data": True,
            "last_updated": date.today().isoformat(),
            "season_to_date": _window_stats(resolved),
            "last_25": _window_stats(resolved),
            "last_50": _window_stats(resolved),
        }
        BASE.joinpath("logs").mkdir(parents=True, exist_ok=True)
        with open(F5_PERF_PATH, "w") as f:
            json.dump(result, f, indent=2)
        return result

    resolved = resolved.sort_values("date").reset_index(drop=True)

    # Windows
    std = _window_stats(resolved)
    last_25 = _window_stats(resolved.tail(25))
    last_50 = _window_stats(resolved.tail(50))

    # Side breakdown for each window
    sides = {}
    for window_name, window_df in [("season_to_date", resolved),
                                    ("last_25", resolved.tail(25)),
                                    ("last_50", resolved.tail(50))]:
        sides[window_name] = {
            "under": _side_stats(window_df, "UNDER"),
            "over": _side_stats(window_df, "OVER"),
        }

    # CLV
    clv = _clv_stats(resolved)

    result = {
        "insufficient_data": False,
        "last_updated": date.today().isoformat(),
        "season_to_date": std,
        "last_25": last_25,
        "last_50": last_50,
        "by_side": sides,
        "clv": clv,
    }

    with open(F5_PERF_PATH, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"F5 performance updated: STD N={std['n']}, ROI={std['roi']}")
    return result


def check_hard_stop(perf):
    """
    Check F5 hard stop. Uses COMBINED F5 ROI only.
    Returns True if engine should pause.
    """
    std = perf.get("season_to_date", {})
    n = std.get("n", 0)
    roi = std.get("roi")

    if roi is None or n < HARD_STOP_MIN_N:
        return False

    if roi < HARD_STOP_ROI:
        logger.warning(f"F5 HARD STOP TRIGGERED: ROI={roi}% at N={n} "
                       f"(threshold={HARD_STOP_ROI}%)")
        status = {
            "status": "PAUSED",
            "last_updated": date.today().isoformat(),
            "pause_reason": f"Hard stop: combined F5 ROI={roi}% at N={n}",
            "pause_triggered_at_n": n,
            "pause_triggered_at_roi": roi,
            "resume_authorized_by": None,
            "resume_date": None,
        }
        with open(F5_STATUS_PATH, "w") as f:
            json.dump(status, f, indent=2)
        return True

    return False
