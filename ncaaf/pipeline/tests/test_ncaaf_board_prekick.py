#!/usr/bin/env python3
"""N02 regression test: pre-kick guard prevents in-play odds from reaching the board."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

TAPE_DIR = ROOT / "data" / "odds_archive" / "ncaaf" / "line_history" / "season=2026"

# Pittsburgh vs Syracuse: event_id f06e90b4212fb514f3564ded9f190107
# Kickoff: 2026-09-17T23:30:00Z
# DK spreads Pittsburgh: -10.5 @ -112 (T-30min) vs -14.5 @ +970 (T+210min)
PITT_EVENT = "f06e90b4212fb514f3564ded9f190107"
PITT_COMMENCE = "2026-09-17T23:30:00Z"


@pytest.fixture(scope="module")
def tape():
    """Load all snapshots."""
    frames = []
    for f in sorted(TAPE_DIR.glob("*.parquet")):
        frames.append(pd.read_parquet(f))
    return pd.concat(frames, ignore_index=True)


def test_prekick_returns_closing_not_inplay(tape):
    """The pre-kick filter returns the T-30min line, not the T+210min in-play line."""
    from ncaaf.pipeline.build_ncaaf_board import load_tape

    # Build time after the game ended but pre-kick filter should still work
    filtered = load_tape(2026, build_time="2026-09-18T05:00:00Z")

    pitt = filtered[
        (filtered["event_id"] == PITT_EVENT)
        & (filtered["market"] == "spreads")
        & (filtered["bookmaker"] == "draftkings")
        & (filtered["outcome_name"].str.contains("Pittsburgh", na=False))
    ]

    if pitt.empty:
        pytest.skip("Pitt event not in tape")

    # The latest eligible row should have the pre-kick line
    latest = pitt.sort_values("snapshot_dt", ascending=False).iloc[0]
    assert abs(latest["point"] - (-10.5)) < 0.1, (
        f"Expected point=-10.5 (pre-kick), got {latest['point']}"
    )
    # Must NOT contain the +970 in-play line
    assert (pitt["price"] > 500).sum() == 0, (
        "In-play odds (+970) leaked through the pre-kick filter"
    )


def test_naive_last_would_get_inplay(tape):
    """Confirm the test CAN fail: without pre-kick filter, in-play odds appear."""
    pitt = tape[
        (tape["event_id"] == PITT_EVENT)
        & (tape["market"] == "spreads")
        & (tape["bookmaker"] == "draftkings")
        & (tape["outcome_name"].str.contains("Pittsburgh", na=False))
    ]

    if pitt.empty:
        pytest.skip("Pitt event not in tape")

    # Without any filter, the latest snapshot has the in-play line
    latest_unfiltered = pitt.sort_values("snapshot_utc", ascending=False).iloc[0]
    # This SHOULD be the in-play line (point around -14.5 or worse, price +970)
    assert latest_unfiltered["point"] != -10.5 or latest_unfiltered["price"] > 500, (
        "Unfiltered latest is the same as pre-kick — test cannot distinguish them"
    )


def test_null_control_unstarted_games(tape):
    """For games not yet kicked off, pre-kick filter changes nothing."""
    from ncaaf.pipeline.build_ncaaf_board import load_tape

    # Use a build_time well before any future games
    bt = "2026-09-18T20:00:00Z"
    filtered = load_tape(2026, build_time=bt)

    # Games with commence_time > build_time are "unstarted"
    bt_dt = pd.Timestamp(bt, tz="UTC")
    tape_with_dt = tape.copy()
    tape_with_dt["snapshot_dt"] = pd.to_datetime(tape_with_dt["snapshot_utc"], utc=True, errors="coerce")
    tape_with_dt["commence_dt"] = pd.to_datetime(tape_with_dt["commence_time"], utc=True, errors="coerce")

    unstarted = tape_with_dt[tape_with_dt["commence_dt"] > bt_dt]
    # For unstarted: ALL snapshots are before commence_time by definition (since snapshot <= build_time < commence_time)
    # So the filter should keep the same rows as the raw tape (minus any post-build snapshots)
    unstarted_pre_build = unstarted[unstarted["snapshot_dt"] <= bt_dt]

    filtered_unstarted = filtered[filtered["commence_dt"] > bt_dt]

    # Row counts should be identical
    assert len(filtered_unstarted) == len(unstarted_pre_build), (
        f"Unstarted: filtered {len(filtered_unstarted)} != raw {len(unstarted_pre_build)}"
    )
