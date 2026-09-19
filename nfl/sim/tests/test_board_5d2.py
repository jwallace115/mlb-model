#!/usr/bin/env python3
"""Tests for D68 (detect_week) and D69 (props snapshot selection)."""

import json
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

def test_engine_fingerprint_is_deterministic():
    """D72: same inputs, same fingerprint."""
    from nfl.sim.calibration import engine_fingerprint
    assert engine_fingerprint() == engine_fingerprint()
    assert len(engine_fingerprint()) == 16


def test_engine_fingerprint_moves_when_an_input_changes(tmp_path, monkeypatch):
    """D72: touching any engine input must change the fingerprint."""
    import nfl.sim.calibration as cal
    src = tmp_path / "engine.py"; src.write_text("x = 1")
    tables = tmp_path / "tables"; tables.mkdir()
    (tables / "a.parquet").write_bytes(b"AAA")
    monkeypatch.setattr(cal, "ENGINE_FINGERPRINT_FILES", [src])
    monkeypatch.setattr(cal, "ENGINE_TABLES_DIR", tables)

    before = cal.engine_fingerprint()
    (tables / "a.parquet").write_bytes(b"BBB")
    assert cal.engine_fingerprint() != before, "table change did not move the fingerprint"

    mid = cal.engine_fingerprint()
    src.write_text("x = 2")
    assert cal.engine_fingerprint() != mid, "engine change did not move the fingerprint"


def test_missing_engine_input_raises(tmp_path, monkeypatch):
    """A partial fingerprint would compare equal across a real change."""
    import nfl.sim.calibration as cal
    tables = tmp_path / "tables"; tables.mkdir()
    monkeypatch.setattr(cal, "ENGINE_FINGERPRINT_FILES", [tmp_path / "nope.py"])
    monkeypatch.setattr(cal, "ENGINE_TABLES_DIR", tables)
    with pytest.raises(FileNotFoundError):
        cal.engine_fingerprint()


def test_gate_passes_when_fingerprint_matches(tmp_path):
    """D72: a stamp carrying the live fingerprint passes."""
    from nfl.sim.run_week import _check_calibration_stamp
    from nfl.sim.calibration import engine_fingerprint, usage_fingerprint
    stamp = tmp_path / "cal.json"
    stamp.write_text(json.dumps({
        "engine_fingerprint": engine_fingerprint(),
        "usage_file_sha256": usage_fingerprint(),
        "maps": {},
    }))
    ok, mismatches = _check_calibration_stamp(cal_path=stamp)
    assert ok, f"gate fired on a matching stamp: {mismatches}"


def test_gate_ignores_git_head_and_engine_commit(tmp_path):
    """THE POINT OF D72. The dashboard auto-committer moves HEAD every 30
    minutes. A stamp with the right fingerprint but a nonsense engine_commit
    must still pass, or the gate is permanently red and gets ignored."""
    from nfl.sim.run_week import _check_calibration_stamp
    from nfl.sim.calibration import engine_fingerprint, usage_fingerprint
    stamp = tmp_path / "cal.json"
    stamp.write_text(json.dumps({
        "engine_fingerprint": engine_fingerprint(),
        "usage_file_sha256": usage_fingerprint(),
        "engine_commit": "deadbeef",      # deliberately wrong
        "maps": {},
    }))
    ok, mismatches = _check_calibration_stamp(cal_path=stamp)
    assert ok, f"gate fired on a stale engine_commit: {mismatches}"


def test_gate_fires_on_fingerprint_mismatch(tmp_path):
    """A real engine change must fire it."""
    from nfl.sim.run_week import _check_calibration_stamp
    from nfl.sim.calibration import usage_fingerprint
    stamp = tmp_path / "cal.json"
    stamp.write_text(json.dumps({
        "engine_fingerprint": "0" * 16,
        "usage_file_sha256": usage_fingerprint(),
        "maps": {},
    }))
    ok, mismatches = _check_calibration_stamp(cal_path=stamp)
    assert not ok
    assert any("engine_fingerprint" in m for m in mismatches)


def test_gate_fires_on_prefingerprint_stamp(tmp_path):
    """The stamp in the repo today has no fingerprint — it was hand-written.
    The gate must say so rather than pass."""
    from nfl.sim.run_week import _check_calibration_stamp
    stamp = tmp_path / "cal.json"
    stamp.write_text(json.dumps({"engine_commit": "85f1cb455", "maps": {}}))
    ok, mismatches = _check_calibration_stamp(cal_path=stamp)
    assert not ok
    assert any("predates D72" in m for m in mismatches)



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


# ── D77: the usage fingerprint covers only the fit window ──

def _write_usage(path, rows):
    pd.DataFrame(rows).to_parquet(path, index=False)


def _usage_rows():
    out = []
    for season in (2021, 2022, 2023, 2024, 2026):
        for wk in (1, 2):
            out.append({"season": season, "week": wk, "team": "MIN",
                        "player_id": "00-0000001", "target_share": 0.10,
                        "carry_share": 0.40})
    return out


def test_usage_fingerprint_ignores_non_fit_seasons(tmp_path, monkeypatch):
    """THE POINT OF D77. A 2026-only refresh must not move the fingerprint —
    the maps are fitted on 2021-24, so 2026 roster churn cannot affect them.
    Before D77 the whole file was hashed and every routine refresh reddened
    the gate."""
    import nfl.sim.calibration as cal
    rows = _usage_rows()
    a = tmp_path / "a.parquet"; _write_usage(a, rows)
    monkeypatch.setattr(cal, "USAGE_PATH", a)
    before = cal.usage_fingerprint()

    changed = [dict(r) for r in rows]
    for r in changed:                      # move 2026 a lot; fit window untouched
        if r["season"] == 2026:
            r["carry_share"] = 0.95
    b = tmp_path / "b.parquet"; _write_usage(b, changed)
    monkeypatch.setattr(cal, "USAGE_PATH", b)
    assert cal.usage_fingerprint() == before, "2026-only change moved the fingerprint"


def test_usage_fingerprint_moves_on_fit_season_change(tmp_path, monkeypatch):
    """A change inside the fit window MUST move it, or the gate is useless."""
    import nfl.sim.calibration as cal
    rows = _usage_rows()
    a = tmp_path / "a.parquet"; _write_usage(a, rows)
    monkeypatch.setattr(cal, "USAGE_PATH", a)
    before = cal.usage_fingerprint()

    changed = [dict(r) for r in rows]
    for r in changed:
        if r["season"] == 2023:
            r["carry_share"] = 0.41       # one fit-window cell
    b = tmp_path / "b.parquet"; _write_usage(b, changed)
    monkeypatch.setattr(cal, "USAGE_PATH", b)
    assert cal.usage_fingerprint() != before, "fit-window change did NOT move the fingerprint"


def test_usage_fingerprint_is_row_order_stable(tmp_path, monkeypatch):
    """Deterministic across rebuilds: row order must not matter."""
    import nfl.sim.calibration as cal
    rows = _usage_rows()
    a = tmp_path / "a.parquet"; _write_usage(a, rows)
    monkeypatch.setattr(cal, "USAGE_PATH", a)
    before = cal.usage_fingerprint()
    b = tmp_path / "b.parquet"; _write_usage(b, list(reversed(rows)))
    monkeypatch.setattr(cal, "USAGE_PATH", b)
    assert cal.usage_fingerprint() == before, "fingerprint depends on row order"
