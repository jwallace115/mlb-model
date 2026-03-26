#!/usr/bin/env python3
"""
S12 Overlay Performance Tracker.
Reads signals_2026.parquet, computes overlay vs non-overlay stats.
"""

import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("s12_tracker")

BASE = Path(__file__).resolve().parent.parent
SIGNALS_PATH = BASE / "logs" / "signals_2026.parquet"
PERF_PATH = BASE / "logs" / "s12_overlay_performance_2026.json"

WIN_UNIT = 100 / 110


def _load_resolved():
    if not SIGNALS_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(SIGNALS_PATH)
    return df[df["resolved"] == 1]


def _group_stats(df):
    if len(df) == 0:
        return {"n": 0, "win_rate": None, "push_rate": None,
                "roi": None, "net_units": None, "avg_final_stake": None}

    n = len(df)
    wins = int((df["result"] == "WIN").sum())
    losses = int((df["result"] == "LOSS").sum())
    pushes = int((df["result"] == "PUSH").sum())
    n_nonpush = wins + losses
    wr = wins / n_nonpush * 100 if n_nonpush > 0 else 0
    push_rate = pushes / n * 100

    net = df["net_units"].sum()
    wagered = df["stake_units"].sum()
    roi = net / wagered * 100 if wagered > 0 else 0
    avg_stake = df["stake_units"].mean()

    return {
        "n": int(n), "win_rate": round(wr, 1), "push_rate": round(push_rate, 1),
        "roi": round(roi, 1), "net_units": round(float(net), 2),
        "avg_final_stake": round(float(avg_stake), 2),
    }


def _incremental(df):
    """Compute incremental net units from overlay staking vs base staking."""
    if len(df) == 0 or "base_stake" not in df.columns:
        return None

    actual_net = df["net_units"].sum()

    # Counterfactual: what would net be at base_stake?
    counterfactual = 0
    for _, r in df.iterrows():
        base = r.get("base_stake")
        if pd.isna(base):
            base = r["stake_units"]  # fallback if no base_stake
        result = r["result"]
        if result == "WIN":
            counterfactual += base * WIN_UNIT
        elif result == "LOSS":
            counterfactual -= base
        # PUSH = 0

    return round(float(actual_net - counterfactual), 2)


def compute_s12_performance():
    """Compute S12 overlay performance and save to JSON."""
    resolved = _load_resolved()

    if len(resolved) == 0:
        result = {
            "insufficient_data": True,
            "last_updated": date.today().isoformat(),
        }
        PERF_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PERF_PATH, "w") as f:
            json.dump(result, f, indent=2)
        return result

    resolved = resolved.sort_values("date").reset_index(drop=True)

    # Check if overlay fields exist
    has_overlay = "s12_overlay_active" in resolved.columns

    windows = {}
    for wname, wdf in [("season_to_date", resolved),
                        ("last_50", resolved.tail(50)),
                        ("last_25", resolved.tail(25))]:
        groups = {"all_v1_under": _group_stats(wdf)}

        if has_overlay:
            active = wdf[wdf["s12_overlay_active"] == 1]
            inactive = wdf[wdf["s12_overlay_active"] == 0]
            groups["s12_active"] = _group_stats(active)
            groups["s12_inactive"] = _group_stats(inactive)
            groups["incremental_net_units"] = _incremental(wdf)
        else:
            groups["s12_active"] = {"n": 0, "note": "overlay fields not yet in log"}
            groups["s12_inactive"] = groups["all_v1_under"]
            groups["incremental_net_units"] = 0

        windows[wname] = groups

    result = {
        "insufficient_data": False,
        "last_updated": date.today().isoformat(),
        "has_overlay_fields": has_overlay,
        **windows,
    }

    with open(PERF_PATH, "w") as f:
        json.dump(result, f, indent=2)

    std = windows["season_to_date"]
    logger.info(f"S12 overlay tracker: all={std['all_v1_under']['n']}sig, "
                f"active={std['s12_active'].get('n',0)}, "
                f"incremental={std.get('incremental_net_units', 0)}u")
    return result
