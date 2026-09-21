#!/usr/bin/env python3
"""
Phase 5J — layer-3 starting-QB date rule test.

D59 put a dt-before-kickoff rule on depth_order; layer 3 (the static
depth-chart QB fallback) never got it. This test verifies the fix:
a rank-1 QB snapshot with dt AFTER a week's first kickoff does NOT
set the starting QB for that week, while the same row dated BEFORE
kickoff DOES.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.usage import derive_starting_qbs, PBP_DIR


def _get_kickoff_2026_wk1():
    """Get the first kickoff time for 2026 week 1 from nflverse schedule."""
    import nflreadpy
    sched = nflreadpy.load_schedules([2026]).to_pandas()
    sched["_ko"] = pd.to_datetime(
        sched["gameday"].astype(str) + " " + sched["gametime"].fillna("13:00"),
        errors="coerce", utc=True,
    )
    wk1 = sched[sched["week"] == 1]
    return wk1["_ko"].min()


def _make_depth_row(team, gsis_id, dt_str):
    """Build a minimal new-schema depth-chart row."""
    return {
        "team": team,
        "gsis_id": gsis_id,
        "pos_abb": "QB",
        "pos_rank": 1,
        "dt": dt_str,
        "position": "QB",
        "season": 2026,
        "week": 0,
        "club_code": team,
        "depth_team": 1,
        "full_name": f"Fake QB {gsis_id}",
    }


@pytest.fixture(scope="module")
def kickoff_wk1():
    return _get_kickoff_2026_wk1()


@pytest.fixture(scope="module")
def depth_no_team():
    """Real depth chart with ALL ARI QB rows removed, so layer 3
    has nothing to fill (2026, 1, ARI) from — the slot is empty."""
    real = pd.read_parquet(PBP_DIR / "depth_charts.parquet")
    mask = (real["team"] == "ARI") & (real.get("pos_abb", pd.Series(dtype=str)) == "QB")
    return real[~mask].copy()


def test_layer3_rejects_post_kickoff_qb(kickoff_wk1, depth_no_team):
    """A rank-1 QB snapshot dated AFTER week 1's first game day does NOT set the
    starting QB for week 1 on that team. The slot stays empty.

    The layer-3 kickoff lookup uses PBP game_date (midnight UTC on game day)
    for seasons with PBP data, so "after kickoff" means on or after game day."""
    ko = kickoff_wk1
    fake_gsis = "00-FAKEFAKE"
    # On game day itself (after the PBP game_date midnight cutoff)
    after_dt = ko.normalize().isoformat()  # midnight UTC on game day
    row = _make_depth_row("ARI", fake_gsis, after_dt)
    depth = pd.concat([depth_no_team, pd.DataFrame([row])], ignore_index=True)

    starting = derive_starting_qbs(depth, plays=None)
    wk1 = starting.get((2026, 1, "ARI"))
    assert wk1 is None or wk1["gsis_id"] != fake_gsis, (
        f"Post-kickoff fake QB {fake_gsis} was accepted as starter for wk1. "
        f"Layer 3 date filter is NOT working."
    )


def test_layer3_accepts_pre_kickoff_qb(kickoff_wk1, depth_no_team):
    """The same fake QB dated BEFORE the first game day IS chosen as starter."""
    ko = kickoff_wk1
    fake_gsis = "00-FAKEFAKE"
    # One day before game day — clearly before any kickoff
    before_dt = (ko.normalize() - pd.Timedelta(days=1)).isoformat()
    row = _make_depth_row("ARI", fake_gsis, before_dt)
    depth = pd.concat([depth_no_team, pd.DataFrame([row])], ignore_index=True)

    starting = derive_starting_qbs(depth, plays=None)
    wk1 = starting.get((2026, 1, "ARI"))
    assert wk1 is not None, "No starter set for (2026, 1, ARI) despite pre-kickoff row"
    assert wk1["gsis_id"] == fake_gsis, (
        f"Pre-kickoff fake QB was NOT chosen. Got {wk1['gsis_id']}. "
        f"Layer 3 is not using the injected row."
    )
