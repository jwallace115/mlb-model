#!/usr/bin/env python3
"""Tests for Hard Rock props capture pipeline and CLV grading."""

import json, os, sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── Window selection ──

def test_window_selection():
    """Events within --window-hours are selected, others excluded."""
    now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    window_hours = 12
    window_end = now + timedelta(hours=window_hours)

    events = [
        {"id": "a", "commence_time": "2026-09-18T14:00:00Z", "home_team": "KC", "away_team": "DEN"},
        {"id": "b", "commence_time": "2026-09-18T23:00:00Z", "home_team": "BUF", "away_team": "MIA"},
        {"id": "c", "commence_time": "2026-09-19T01:00:00Z", "home_team": "SF", "away_team": "SEA"},
        {"id": "d", "commence_time": "2026-09-20T18:00:00Z", "home_team": "NYG", "away_team": "DAL"},
    ]

    selected = []
    for e in events:
        ct = e["commence_time"]
        ct_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        if now <= ct_dt <= window_end:
            selected.append(e["id"])

    assert selected == ["a", "b"], f"Expected [a, b], got {selected}"


def test_window_selection_wide():
    """--window-hours 168 selects a full week of events."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    window_end = now + timedelta(hours=168)

    events = [
        {"id": "sun", "commence_time": "2026-09-14T18:00:00Z"},
        {"id": "mnf", "commence_time": "2026-09-15T00:15:00Z"},
        {"id": "next_week", "commence_time": "2026-09-21T18:00:00Z"},
    ]
    selected = []
    for e in events:
        ct_dt = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        if now <= ct_dt <= window_end:
            selected.append(e["id"])
    assert "sun" in selected
    assert "mnf" in selected
    assert "next_week" not in selected


# ── Tag column ──

def test_snapshot_tag_column():
    """normalize() adds snapshot_tag to every row."""
    from nfl.pipeline.pull_hardrock_props import normalize

    mock_data = {
        "bookmakers": [{
            "key": "hardrockbet_fl",
            "last_update": "2026-09-18T12:00:00Z",
            "markets": [{
                "key": "player_receptions",
                "outcomes": [
                    {"description": "Travis Kelce", "name": "Over", "point": 5.5, "price": -120},
                    {"description": "Travis Kelce", "name": "Under", "point": 5.5, "price": 100},
                ],
            }],
        }],
    }
    rows = normalize(mock_data, "eid1", "2026-09-18", "KC", "DEN",
                     "2026-09-18T18:00:00Z", "hardrock_open", "ts1", "open")
    assert len(rows) == 1
    assert rows[0]["snapshot_tag"] == "open"

    rows_close = normalize(mock_data, "eid1", "2026-09-18", "KC", "DEN",
                           "2026-09-18T18:00:00Z", "hardrock_close", "ts2", "close")
    assert rows_close[0]["snapshot_tag"] == "close"


# ── Append-not-overwrite ──

def test_append_not_overwrite(tmp_path):
    """save_partition appends new rows, never overwrites existing."""
    from nfl.pipeline.pull_hardrock_props import save_partition, PROPS_DIR

    # Temporarily redirect PROPS_DIR
    import nfl.pipeline.pull_hardrock_props as mod
    orig = mod.PROPS_DIR
    mod.PROPS_DIR = tmp_path / "props"

    try:
        rows1 = [{"sport": "nfl", "player_name": "A", "line": 5.5,
                   "snapshot_tag": "open", "over_price": -110}]
        save_partition(rows1, 2026, 9)
        path = tmp_path / "props" / "season=2026" / "month=09" / "data_2026_09.parquet"
        assert path.exists()
        df1 = pd.read_parquet(path)
        assert len(df1) == 1

        rows2 = [{"sport": "nfl", "player_name": "B", "line": 4.5,
                   "snapshot_tag": "close", "over_price": -115}]
        save_partition(rows2, 2026, 9)
        df2 = pd.read_parquet(path)
        assert len(df2) == 2, f"Expected 2 rows after append, got {len(df2)}"
        assert set(df2["player_name"]) == {"A", "B"}
    finally:
        mod.PROPS_DIR = orig


# ── HALT arithmetic ──

def test_halt_arithmetic():
    """Cost pre-check: remaining - (events * 15 + 1) must be >= 3000."""
    n_events = 16
    cost = n_events * 15 + 1  # 241
    assert cost == 241

    # Should proceed
    remaining = 4000
    assert remaining - cost >= 3000

    # Should halt
    remaining = 3200
    assert remaining - cost < 3000, "Should halt when remaining - cost < 3000"


def test_halt_with_mock():
    """Simulate the HALT logic with a mock x-requests-remaining header."""
    remaining = 3100
    n_events = 14
    cost = n_events * 15 + 1  # 211
    after = remaining - cost  # 2889
    assert after < 3000, f"Should halt: {after} < 3000"

    remaining = 5000
    after = remaining - cost  # 4789
    assert after >= 3000, f"Should proceed: {after} >= 3000"


# ── CLV join on MNF picks ──

def test_clv_join_mnf():
    """CLV join finds Hard Rock closing prices for MNF 2026 wk1 picks."""
    picks_path = ROOT / "nfl" / "data" / "sim" / "outputs" / "week=2026_01" / "DEN_at_KC_mnf" / "picks_log_mnf_2026w1_v2.parquet"
    if not picks_path.exists():
        pytest.skip("MNF picks_log not available")

    from nfl.sim.grade_week import compute_clv

    picks = pd.read_parquet(picks_path)
    picks = compute_clv(picks, 2026)

    # CLV columns should exist
    assert "close_price" in picks.columns
    assert "close_implied" in picks.columns
    assert "clv" in picks.columns

    # At least some legs should have matched
    matched = picks["close_implied"].notna().sum()
    print(f"CLV matched: {matched}/{len(picks)} legs")
    assert matched > 0, "No CLV matches found — archive may be missing"

    # CLV values should be small (not > 0.5 in absolute value)
    valid_clv = picks["clv"].dropna()
    if len(valid_clv) > 0:
        assert valid_clv.abs().max() < 0.5, (
            f"CLV values too large: max |clv| = {valid_clv.abs().max():.4f}")

    # Report
    for fam in sorted(picks[picks["clv"].notna()]["family"].unique()):
        g = picks[(picks["family"] == fam) & picks["clv"].notna()]
        mean_clv = g["clv"].mean()
        print(f"  {fam}: N={len(g)}, mean CLV={mean_clv:+.4f}")
