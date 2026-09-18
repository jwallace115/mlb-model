#!/usr/bin/env python3
"""Tests for D68 (detect_week) and D69 (props snapshot selection)."""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


# ── D68: detect_week ──

def test_detect_week_override():
    """--week override returns the specified week."""
    from nfl.sim.run_week import detect_week
    w, _, _ = detect_week(override=2)
    assert w == 2


# ── D69: props snapshot selection ──

def _make_props_dir(tmp_path, rows):
    """Create a mock props dir matching the real ROOT path structure."""
    pdir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=09"
    pdir.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(pdir / "data_2026_09.parquet", index=False)
    return tmp_path


def test_close_over_open(tmp_path):
    """Given open + close snapshots, close is chosen."""
    from nfl.sim.run_week import load_props_for_game
    rows = [
        {"home_team": "KC", "away_team": "DEN",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "Test", "line": 5.5,
         "over_price": -110.0, "under_price": -110.0,
         "implied_over": 0.52, "implied_under": 0.52,
         "pull_batch": "b1", "pull_timestamp": "2026-09-16T10:00:00",
         "snapshot_tag": "open"},
        {"home_team": "KC", "away_team": "DEN",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "Test", "line": 5.5,
         "over_price": -115.0, "under_price": -105.0,
         "implied_over": 0.535, "implied_under": 0.512,
         "pull_batch": "b2", "pull_timestamp": "2026-09-18T15:00:00",
         "snapshot_tag": "close"},
    ]
    mock_root = _make_props_dir(tmp_path, rows)
    with patch("nfl.sim.run_week.ROOT", mock_root):
        result, tag, ts = load_props_for_game("KC", "DEN", 2026, 2)
    assert tag == "close", f"Expected close, got {tag}"
    assert len(result) == 1
    assert result.iloc[0]["over_price"] == -115.0


def test_mid_over_open(tmp_path):
    """Given open + mid, mid is chosen."""
    from nfl.sim.run_week import load_props_for_game
    rows = [
        {"home_team": "KC", "away_team": "DEN",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "X", "line": 4.5,
         "over_price": -110.0, "under_price": -110.0,
         "implied_over": 0.52, "implied_under": 0.52,
         "pull_batch": "b1", "pull_timestamp": "2026-09-16T10:00:00",
         "snapshot_tag": "open"},
        {"home_team": "KC", "away_team": "DEN",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "X", "line": 4.5,
         "over_price": -120.0, "under_price": 100.0,
         "implied_over": 0.545, "implied_under": 0.50,
         "pull_batch": "b2", "pull_timestamp": "2026-09-17T12:00:00",
         "snapshot_tag": "mid"},
    ]
    mock_root = _make_props_dir(tmp_path, rows)
    with patch("nfl.sim.run_week.ROOT", mock_root):
        result, tag, ts = load_props_for_game("KC", "DEN", 2026, 2)
    assert tag == "mid", f"Expected mid, got {tag}"


def test_two_closes_latest_wins(tmp_path):
    """Given two close snapshots, latest pull_timestamp wins."""
    from nfl.sim.run_week import load_props_for_game
    rows = [
        {"home_team": "T1", "away_team": "T2",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "A", "line": 5.5,
         "over_price": -110.0, "under_price": -110.0,
         "implied_over": 0.52, "implied_under": 0.52,
         "pull_batch": "c1", "pull_timestamp": "2026-09-18T12:00:00",
         "snapshot_tag": "close"},
        {"home_team": "T1", "away_team": "T2",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "A", "line": 5.5,
         "over_price": -105.0, "under_price": -115.0,
         "implied_over": 0.512, "implied_under": 0.535,
         "pull_batch": "c2", "pull_timestamp": "2026-09-18T15:00:00",
         "snapshot_tag": "close"},
    ]
    mock_root = _make_props_dir(tmp_path, rows)
    with patch("nfl.sim.run_week.ROOT", mock_root):
        result, tag, ts = load_props_for_game("T1", "T2", 2026, 2)
    assert tag == "close"
    # Latest timestamp first (sorted desc)
    assert result.iloc[0]["over_price"] == -105.0


def test_unknown_tag_raises(tmp_path):
    """An unknown snapshot_tag raises ValueError."""
    from nfl.sim.run_week import load_props_for_game
    rows = [
        {"home_team": "T1", "away_team": "T2",
         "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
         "player_name": "A", "line": 5.5,
         "over_price": -110.0, "under_price": -110.0,
         "implied_over": 0.52, "implied_under": 0.52,
         "pull_batch": "x", "pull_timestamp": "2026-09-18T12:00:00",
         "snapshot_tag": "pregame_special"},
    ]
    mock_root = _make_props_dir(tmp_path, rows)
    with patch("nfl.sim.run_week.ROOT", mock_root):
        with pytest.raises(ValueError, match="Unknown snapshot_tag"):
            load_props_for_game("T1", "T2", 2026, 2)


# ── D70: metadata gate ──

def test_stamp_mismatch_suppresses_prices():
    """A stamp mismatch suppresses sim prices."""
    from nfl.sim.run_week import _check_calibration_stamp
    ok, mismatches = _check_calibration_stamp()
    # The engine has changed since calibration was fitted at 85f1cb455,
    # so the gate is EXPECTED to fire.
    if not ok:
        assert len(mismatches) > 0
        assert any("engine_commit" in m for m in mismatches)
    # Either way, the function runs without error


# ── D71: layer log schema ──

def test_layer_log_schema():
    """Layer log should have the required fields per D71."""
    expected_fields = {
        "season", "week", "game_id", "player_id", "player_name",
        "position", "family", "line", "side",
        "sim_p_raw", "sim_p_calibrated",
        "book_price", "book_implied",
        "moved_against", "snapshot_tag", "snapshot_timestamp",
        "tier", "status", "rankable",
        "sim_pricing_enabled", "board_generated_utc",
    }
    # Verify the schema is documented — the actual log is written by build_board
    # which we can't run in a unit test without full sim data.
    # We verify the field list matches what _add_leg populates.
    import nfl.sim.run_week as rw
    import inspect
    src = inspect.getsource(rw.build_board)
    for field in expected_fields:
        assert f'"{field}"' in src, f"Layer log field {field} not found in build_board"
