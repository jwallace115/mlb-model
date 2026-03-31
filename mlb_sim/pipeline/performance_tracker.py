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
SHADOW_PERF_PATH = BASE / "logs" / "rolling_performance_shadow_2026.json"
STATUS_PATH = BASE / "pipeline" / "engine_status.json"

HARD_STOP_ROI = -8.0
HARD_STOP_MIN_N = 50

# Shadow signal classes (excluded from live tracker from 2026-03-30 onward)
SHADOW_CLASSES = {"BASE_HIGH", "S12_HIGH"}
SHADOW_CUTOVER_DATE = "2026-03-30"


def _load_resolved():
    """Load resolved (non-postponed) signals only."""
    if not SIGNALS_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(SIGNALS_PATH)
    return df[df["resolved"] == 1]


def _is_shadow(row):
    """Check if a resolved bet is shadow. Only applies from cutover date forward."""
    if str(row.get("date", "")) < SHADOW_CUTOVER_DATE:
        return False  # pre-cutover bets stay in live tracker
    if row.get("shadow_only") is True:
        return True
    sc = row.get("signal_class")
    if sc and sc in SHADOW_CLASSES:
        return True
    return False


def _split_live_shadow(resolved):
    """Split resolved bets into live and shadow DataFrames."""
    if len(resolved) == 0:
        return resolved, pd.DataFrame()
    shadow_mask = resolved.apply(_is_shadow, axis=1)
    return resolved[~shadow_mask], resolved[shadow_mask]


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


def _build_tracker(resolved, label=""):
    """Build tracker dict from a resolved DataFrame."""
    if len(resolved) == 0:
        return {"insufficient_data": True, "last_updated": date.today().isoformat(),
                "season_to_date": _window_stats(resolved),
                "last_25": _window_stats(resolved), "last_50": _window_stats(resolved)}

    resolved = resolved.sort_values("date").reset_index(drop=True)

    std = _window_stats(resolved, "season_to_date")
    last_25 = _window_stats(resolved.tail(25), "last_25")
    last_50 = _window_stats(resolved.tail(50), "last_50")

    b_057 = _bucket_stats(resolved, "0.57-0.60")
    b_060 = _bucket_stats(resolved, ">0.60")

    clv = _clv_stats(resolved)

    dhc = resolved[resolved.get("dual_high_csw", pd.Series(dtype=float)) == 1] if "dual_high_csw" in resolved.columns else pd.DataFrame()
    dhc_stats = _window_stats(dhc) if len(dhc) >= 10 else {"n": int(len(dhc)), "note": "insufficient_data"}

    return {
        "insufficient_data": False,
        "last_updated": date.today().isoformat(),
        "season_to_date": std,
        "last_25": last_25,
        "last_50": last_50,
        "by_bucket": {"0.57-0.60": b_057, ">0.60": b_060},
        "clv": clv,
        "dual_high_csw": dhc_stats,
    }


def compute_performance():
    """Compute rolling performance metrics for live and shadow trackers."""
    resolved = _load_resolved()
    live, shadow = _split_live_shadow(resolved)

    # Live tracker
    live_result = _build_tracker(live, "live")
    with open(PERF_PATH, "w") as f:
        json.dump(live_result, f, indent=2)
    logger.info(f"Live performance: N={live_result.get('season_to_date',{}).get('n',0)}, "
                f"ROI={live_result.get('season_to_date',{}).get('roi')}")

    # Shadow tracker
    shadow_result = _build_tracker(shadow, "shadow")
    with open(SHADOW_PERF_PATH, "w") as f:
        json.dump(shadow_result, f, indent=2)
    logger.info(f"Shadow performance: N={shadow_result.get('season_to_date',{}).get('n',0)}")

    return live_result


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
