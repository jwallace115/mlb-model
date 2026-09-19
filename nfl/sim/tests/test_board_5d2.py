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


# ── D77 + D81: fingerprint scope (fixtures live in the D81 block below) ──
# The original D77 tests monkeypatched calibration.USAGE_PATH. D81 widened the
# fingerprint to read every file in FIT_INPUT_FILES from RATINGS_DIR, so USAGE_PATH
# is no longer the surface under test and those tests were stale. The D81 tests
# cover the same invariants: fit-window changes are caught, live-season changes are
# ignored, and a missing input raises.


# ── D79: the calibration stamp must enter the ranking decision ──

def _selection(legs):
    """The board's own cross-game top-20 filter (run_week.py ~696)."""
    return [l for l in legs
            if l["tier"].startswith("TRUSTED")
            and l["status"] != "BOOK-MORE-CONFIDENT"
            and l["side"] == "over"
            and l.get("rankable", False)]


def _legs(sim_pricing_enabled):
    from nfl.sim.run_week import is_rankable
    out = []
    for i in range(5):
        out.append({"tier": "TRUSTED", "status": "OK", "side": "over",
                    "cal_p": 0.7, "rankable":
                        is_rankable(has_book=True, converged=True,
                                    sim_pricing_enabled=sim_pricing_enabled)})
    return out


def test_red_stamp_makes_nothing_rankable():
    """THE POINT OF D79. Before it, `rankable = has_book and converged` and the
    stamp only printed a banner, so a red gate still shipped ranked legs into the
    top 20. Reproduced by ChatGPT audit #3 on a real board run."""
    assert _selection(_legs(sim_pricing_enabled=False)) == [], \
        "a red calibration stamp still produced rankable legs"


def test_green_stamp_still_ranks():
    """The gate must not be so strict it blocks a valid run."""
    assert len(_selection(_legs(sim_pricing_enabled=True))) == 5


def test_is_rankable_requires_all_three():
    from nfl.sim.run_week import is_rankable
    assert is_rankable(True, True, True)
    assert not is_rankable(False, True, True)    # no book price
    assert not is_rankable(True, False, True)    # not converged
    assert not is_rankable(True, True, False)    # bad stamp  <- the D79 addition


def test_board_call_site_uses_the_gate():
    """Guards against the fix being reverted to the inline expression: the source
    must pass sim_pricing_enabled into the decision, not recompute it."""
    import inspect
    import nfl.sim.run_week as rw
    src = inspect.getsource(rw.build_board)
    assert "is_rankable(has_book, converged, sim_pricing_enabled)" in src
    assert "rankable = has_book and converged" not in src


# ── D81: the fingerprint covers every fit input, not usage alone ──

def _ratings_fixture(tmp_path):
    """Minimal stand-ins for every file in FIT_INPUT_FILES."""
    import nfl.sim.calibration as cal
    for f in cal.FIT_INPUT_FILES:
        rows = [{"season": s, "week": 1, "team": "MIN", "player_id": "00-1",
                 "val": 0.5} for s in (2021, 2022, 2023, 2024, 2026)]
        pd.DataFrame(rows).to_parquet(tmp_path / f, index=False)
    return tmp_path


def _bump(tmp_path, fname, season, newval):
    d = pd.read_parquet(tmp_path / fname)
    d.loc[d.season == season, "val"] = newval
    d.to_parquet(tmp_path / fname, index=False)


def test_fingerprint_catches_historical_ratings_change(tmp_path, monkeypatch):
    """ChatGPT audit #3 reproduced this: altering HISTORICAL team-ratings EPA left
    the D77 gate green because the fingerprint covered usage alone."""
    import nfl.sim.calibration as cal
    d = _ratings_fixture(tmp_path)
    monkeypatch.setattr(cal, "RATINGS_DIR", d)
    before = cal.usage_fingerprint()
    _bump(d, "team_ratings_weekly.parquet", 2023, 0.9)
    assert cal.usage_fingerprint() != before, "historical ratings change not caught"


def test_fingerprint_catches_historical_active_universe_change(tmp_path, monkeypatch):
    """The other audit reproduction: removing a player from a historical lineup."""
    import nfl.sim.calibration as cal
    d = _ratings_fixture(tmp_path)
    monkeypatch.setattr(cal, "RATINGS_DIR", d)
    before = cal.usage_fingerprint()
    _bump(d, "active_universe_weekly.parquet", 2023, 0.9)
    assert cal.usage_fingerprint() != before, "historical active-universe change not caught"


def test_fingerprint_still_ignores_2026_in_every_fit_input(tmp_path, monkeypatch):
    """D77 must survive D81: a live-season change in ANY fit input stays green."""
    import nfl.sim.calibration as cal
    d = _ratings_fixture(tmp_path)
    monkeypatch.setattr(cal, "RATINGS_DIR", d)
    before = cal.usage_fingerprint()
    for f in cal.FIT_INPUT_FILES:
        _bump(d, f, 2026, 0.99)
    assert cal.usage_fingerprint() == before, "a 2026-only change reddened the gate"


def test_missing_fit_input_raises(tmp_path, monkeypatch):
    import nfl.sim.calibration as cal
    d = _ratings_fixture(tmp_path)
    (d / cal.FIT_INPUT_FILES[0]).unlink()
    monkeypatch.setattr(cal, "RATINGS_DIR", d)
    with pytest.raises(FileNotFoundError):
        cal.usage_fingerprint()


def test_fingerprint_is_row_order_stable(tmp_path, monkeypatch):
    """Deterministic across rebuilds: parquet row order must not move it."""
    import nfl.sim.calibration as cal
    d = _ratings_fixture(tmp_path)
    monkeypatch.setattr(cal, "RATINGS_DIR", d)
    before = cal.usage_fingerprint()
    for f in cal.FIT_INPUT_FILES:
        df = pd.read_parquet(d / f)
        df.iloc[::-1].to_parquet(d / f, index=False)
    assert cal.usage_fingerprint() == before, "fingerprint depends on row order"


# ── D82: MOVED-AGAINST — like-for-like scale, correct side, None when unmeasured ──

R110 = 110 / 210          # -110 raw implied, both sides => 0.52381
R130 = 130 / 230          # -130
R100 = 100 / 210          # the other side of a -110/-130 pair


def _flag(open_o, open_u, now_o, now_u, side):
    from nfl.sim.run_week import compute_moved_against, devig_side
    bi, one_sided = devig_side(now_o, now_u, side)
    return compute_moved_against(bi, one_sided, (open_o, open_u), side)


def test_moved_against_false_on_an_unchanged_market():
    """THE POINT OF D82. book_implied was de-vigged while the open was RAW, so on an
    unchanged -110/-110 market the comparison was 0.5000 > 0.5238 — always False,
    and unable to fire on any move smaller than the book's margin."""
    assert _flag(R110, R110, R110, R110, "over") is False
    assert _flag(R110, R110, R110, R110, "under") is False


def test_moved_against_fires_on_the_side_that_got_more_expensive():
    assert _flag(R110, R110, R130, R100, "over") is True
    assert _flag(R110, R110, R100, R130, "under") is True


def test_moved_against_does_not_fire_on_the_other_side():
    """The over and under branches used to be byte-identical, so an under leg was
    compared against the OVER's raw implied."""
    assert _flag(R110, R110, R130, R100, "under") is False
    assert _flag(R110, R110, R100, R130, "over") is False


def test_moved_against_is_none_when_not_measured():
    """None != False. Every leg on the Week 2 board had no opening snapshot;
    recording False there is an observation the ablation never made."""
    from nfl.sim.run_week import compute_moved_against
    assert compute_moved_against(0.5, False, None, "over") is None


def test_moved_against_is_none_when_scales_are_not_comparable():
    """One-sided quote vs two-sided quote cannot be compared: one carries the
    margin and the other does not."""
    from nfl.sim.run_week import compute_moved_against, devig_side
    bi, one_sided = devig_side(R110, R110, "over")       # two-sided, de-vigged
    assert compute_moved_against(bi, one_sided, (R110, None), "over") is None


def test_devig_side_matches_for_both_sides():
    from nfl.sim.run_week import devig_side
    o, _ = devig_side(R130, R100, "over")
    u, _ = devig_side(R130, R100, "under")
    assert abs(o + u - 1.0) < 1e-12, "de-vigged sides must sum to 1"


# ── D83: the stamp describes the fit run, not the moment of writing ──

def _fake_fit(tmp_path, monkeypatch, engine_fp="AAAA", inputs_fp="BBBB"):
    import nfl.sim.calibration as cal
    monkeypatch.setattr(cal, "OUT_DIR", tmp_path)
    fd = tmp_path / "fit_test"; fd.mkdir()
    (fd / "fit_meta.json").write_text(json.dumps({
        "engine_fingerprint": engine_fp,
        "fit_inputs_fingerprint": inputs_fp,
        "fit_seasons": [2021, 2022, 2023, 2024],
        "engine_commit": "abc1234",
    }))
    return "fit_test"


def test_stamp_comes_from_the_fit_not_the_moment(tmp_path, monkeypatch):
    """THE POINT OF D83. ChatGPT audit #3 changed a watched input, saw the gate go
    red, then re-saved the unchanged maps and got green — without fitting anything.
    The stamp must carry the FIT's fingerprints, so re-saving cannot launder it."""
    import nfl.sim.calibration as cal
    fd = _fake_fit(tmp_path, monkeypatch, engine_fp="FITENGINE", inputs_fp="FITINPUTS")
    out = tmp_path / "cal.json"
    cal.save_calibration({"fam": {"x": [0, 1], "y": [0, 1], "n": 2}},
                         path=out, fit_dir=fd)
    stamp = json.loads(out.read_text())
    assert stamp["engine_fingerprint"] == "FITENGINE", "stamp sampled the live environment"
    assert stamp["usage_file_sha256"] == "FITINPUTS", "stamp sampled the live environment"
    assert cal.engine_fingerprint() != "FITENGINE", "fixture no longer discriminates"


def test_save_calibration_requires_a_fit_dir(tmp_path, monkeypatch):
    import nfl.sim.calibration as cal
    monkeypatch.setattr(cal, "OUT_DIR", tmp_path)
    with pytest.raises(ValueError, match="fit_dir"):
        cal.save_calibration({}, path=tmp_path / "c.json")


def test_save_calibration_refuses_a_fit_without_meta(tmp_path, monkeypatch):
    """A fit that did not record its environment cannot be stamped from."""
    import nfl.sim.calibration as cal
    monkeypatch.setattr(cal, "OUT_DIR", tmp_path)
    (tmp_path / "fit_nometa").mkdir()
    with pytest.raises(FileNotFoundError, match="fit_meta.json"):
        cal.save_calibration({}, path=tmp_path / "c.json", fit_dir="fit_nometa")


def test_restamp_cannot_launder_an_environment_change(tmp_path, monkeypatch):
    """Re-saving after the environment drifts must leave the gate red."""
    import nfl.sim.calibration as cal
    from nfl.sim.run_week import _check_calibration_stamp
    fd = _fake_fit(tmp_path, monkeypatch, engine_fp="FITENGINE", inputs_fp="FITINPUTS")
    out = tmp_path / "cal.json"
    cal.save_calibration({"fam": {"x": [0, 1], "y": [0, 1], "n": 2}},
                         path=out, fit_dir=fd)
    ok, mismatches = _check_calibration_stamp(cal_path=out)
    assert not ok, "a stamp from a different environment should not pass"
    # and re-saving does not change that
    cal.save_calibration({"fam": {"x": [0, 1], "y": [0, 1], "n": 2}},
                         path=out, fit_dir=fd)
    ok2, _ = _check_calibration_stamp(cal_path=out)
    assert not ok2, "re-stamping laundered an environment mismatch"
