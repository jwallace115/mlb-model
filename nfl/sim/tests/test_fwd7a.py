"""D271 (FWD7a): the forward run's inputs must include each team's most recent game, and
the active universe must be this week's. No parametrize (CLAUDE.md)."""
import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests._fwd_stub import add_fwd6_fixture_inputs, RATINGS_FILES  # noqa: E402

TEAMS = (("KC", "CAR"),)


def _inputs(tmp_path, week=3, played_week=2):
    """An inputs dir as build_bundle copies it, from a fixture refreshed for `week`."""
    root = tmp_path / "repo"
    add_fwd6_fixture_inputs(root, played_week=played_week, teams=TEAMS, target_week=week)
    d = tmp_path / "inputs"
    d.mkdir()
    for f in RATINGS_FILES:
        shutil.copy2(root / "nfl" / "data" / "sim" / "ratings" / f, d / f)
    for f in ("rosters_weekly.parquet", "injuries.parquet"):
        shutil.copy2(root / "nfl" / "data" / "pbp" / f, d / f)
    return d


def _gate(d, week=3, lp=2):
    from nfl.sim.run_forward_v1 import _team_freshness
    return _team_freshness(d, 2026, week, ["CAR", "KC"], {"KC": lp, "CAR": lp})


def test_refreshed_inputs_pass(tmp_path):
    table = _gate(_inputs(tmp_path))
    for t in ("KC", "CAR"):
        assert table[t]["usage"] >= 3 and table[t]["qb_ratings"] >= 3 and table[t]["kickers"] >= 3
        assert table[t]["active_universe_current"] > 0
        assert table[t]["injury_game_statuses"] == 1      # the fixture's one Questionable


def _drop_week(d, fname, team, week=3):
    df = pd.read_parquet(d / fname)
    df[~((df["season"] == 2026) & (df["week"] == week) & (df["team"] == team))].to_parquet(
        d / fname, index=False)


def test_usage_built_without_the_last_game_halts(tmp_path):
    """The D271 defect: a week-3 run whose usage row 3 is missing selects row 2 (built from
    week-1 games). The old rule (>= last played week) passed it."""
    d = _inputs(tmp_path)
    _drop_week(d, "player_usage_weekly.parquet", "KC")
    with pytest.raises(SystemExit, match="KC: usage selected week 2 — built without its last game"):
        _gate(d)


def test_qb_and_kicker_ratings_built_without_the_last_game_halt(tmp_path):
    for fname, label in (("qb_ratings_weekly.parquet", "qb_ratings"),
                         ("kicker_weekly.parquet", "kickers"),
                         ("team_ratings_weekly.parquet", "team_ratings"),
                         ("tendencies_weekly.parquet", "tendencies")):
        d = _inputs(tmp_path / label)
        _drop_week(d, fname, "CAR")
        with pytest.raises(SystemExit, match=f"CAR: {label} selected week"):
            _gate(d)


def test_active_universe_not_rebuilt_after_the_injury_report_halts(tmp_path):
    """Rico Dowdle (OUT) was simulated on TNF: the active universe predated the report."""
    d = _inputs(tmp_path)
    ros = pd.read_parquet(d / "rosters_weekly.parquet")
    au = pd.read_parquet(d / "active_universe_weekly.parquet")
    act = au[(au["season"] == 2026) & (au["week"] == 3) & (au["team"] == "KC") & au["active_flag"]]
    inj = pd.read_parquet(d / "injuries.parquet")
    listed = set(inj.loc[inj["week"] == 3, "gsis_id"])
    pid = act[~act["player_id"].isin(listed)].iloc[0]["player_id"]
    inj = pd.concat([inj, pd.DataFrame([{"season": 2026, "week": 3, "team": "KC",
                                          "gsis_id": pid, "report_status": "Out"}])],
                    ignore_index=True)
    inj.to_parquet(d / "injuries.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: week-3 active universe was not built from this week"):
        _gate(d)
    assert len(ros)


def test_active_universe_copied_forward_halts(tmp_path):
    """usage.py copies the last roster week forward; a copied week must not pass."""
    d = _inputs(tmp_path)
    ros = pd.read_parquet(d / "rosters_weekly.parquet")
    r3 = ros[(ros["season"] == 2026) & (ros["week"] == 3) & (ros["team"] == "CAR")]
    ros = ros.drop(r3.index[:3])          # this week's roster differs from the copy
    ros.to_parquet(d / "rosters_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: week-3 active universe was not built"):
        _gate(d)


def test_missing_rosters_or_injury_report_halts(tmp_path):
    d = _inputs(tmp_path / "r")
    ros = pd.read_parquet(d / "rosters_weekly.parquet")
    ros[~((ros["week"] == 3) & (ros["team"] == "KC"))].to_parquet(d / "rosters_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: no week-3 rosters in the bundle"):
        _gate(d)
    d = _inputs(tmp_path / "i")
    inj = pd.read_parquet(d / "injuries.parquet")
    inj[~((inj["week"] == 3) & (inj["team"] == "CAR"))].to_parquet(d / "injuries.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: no week-3 injury report in the bundle"):
        _gate(d)


def test_injuries_are_a_required_bundle_input():
    from nfl.sim.run_forward_v1 import PBP_DIR_FILES, RECORD_ONLY_FILES
    assert "injuries.parquet" in PBP_DIR_FILES and "injuries.parquet" not in RECORD_ONLY_FILES


# ── ratings.py: the entering-week row ───────────────────────────────────────────

def test_entering_weeks_adds_the_next_week_only():
    from nfl.sim.ratings import _entering_weeks
    assert _entering_weeks(pd.Series([1, 2, 3, 3])) == [1, 2, 3, 4]
    assert _entering_weeks(pd.Series(range(1, 23))) == list(range(1, 23))   # cap 22
    assert _entering_weeks(pd.Series([], dtype=int)) == []


def test_qb_and_kicker_loops_use_the_entering_weeks():
    """Both loops that used `sorted(<df>["week"].unique())` now use _entering_weeks."""
    src = (ROOT / "nfl" / "sim" / "ratings.py").read_text()
    tree = ast.parse(src)
    fors = [n for n in ast.walk(tree) if isinstance(n, ast.For)
            and isinstance(n.iter, ast.Call) and getattr(n.iter.func, "id", None) == "_entering_weeks"]
    assert len(fors) == 2, len(fors)
    assert 'for w in sorted(sq["week"].unique())' not in src
    assert 'for w in sorted(sf["week"].unique())' not in src


# ── refresh_inputs.py ───────────────────────────────────────────────────────────

def test_splice_keeps_history_and_takes_the_current_season():
    from nfl.sim.refresh_inputs import splice
    old = pd.DataFrame({"season": pd.Series([2025, 2025, 2026], dtype="int32"),
                        "week": [1, 2, 1], "x": [0.1, 0.2, 0.3]})
    new = pd.DataFrame({"season": [2025, 2026, 2026], "week": [1, 1, 2],
                        "x": [9.9, 0.31, 0.4], "extra": [1, 2, 3]})
    out = splice(old, new)
    assert list(out.columns) == ["season", "week", "x"]
    assert out["season"].dtype == old["season"].dtype
    assert out[out["season"] == 2025]["x"].tolist() == [0.1, 0.2]          # history kept
    assert out[out["season"] == 2026]["x"].tolist() == [0.31, 0.4]         # current rebuilt


def test_refresh_restores_the_tables_when_a_step_fails(tmp_path, monkeypatch):
    import nfl.sim.refresh_inputs as R
    import nfl.sim.calibration as C
    from nfl.sim.calibration import FIT_INPUT_FILES
    root = tmp_path / "repo"
    rd = root / "nfl" / "data" / "sim" / "ratings"
    rd.mkdir(parents=True)
    for f in FIT_INPUT_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    before = {f: hashlib.sha256((rd / f).read_bytes()).hexdigest() for f in FIT_INPUT_FILES}
    params = root / "params_v1.json"
    params.write_text("{}")
    freeze = root / "FREEZE_v1.json"
    freeze.write_text(json.dumps({"usage_fingerprint": "abc"}))
    monkeypatch.setattr(R, "ROOT", root)
    monkeypatch.setattr(R, "RATINGS", rd)
    monkeypatch.setattr(R, "PARAMS", params)
    monkeypatch.setattr(R, "FREEZE", freeze)
    monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
    monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")

    def boom(script):
        (rd / "player_usage_weekly.parquet").write_bytes(b"half-written")
        raise RuntimeError(f"{script} failed")
    monkeypatch.setattr(R, "_run", boom)
    with pytest.raises(RuntimeError, match="pull_nflverse_inputs.py failed"):
        R.main(["--week", "4"])
    assert {f: hashlib.sha256((rd / f).read_bytes()).hexdigest() for f in FIT_INPUT_FILES} == before


def test_refresh_refuses_tables_that_are_not_the_frozen_fit():
    import nfl.sim.refresh_inputs as R
    src = Path(R.__file__).read_text()
    assert "BEFORE the refresh" in src and "after the splice" in src
