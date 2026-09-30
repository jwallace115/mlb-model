"""D256 (FWD6 item 0): the prediction consumes exactly its bundle.

Audit #8 (A1) counterexample: after the bundle was built, the shared CLE week-4 pass_off
`success` rating was changed to 0.99; the real run_week.main() solver call received 0.99
while the bundle held 0.4334993874, and verify_bundle stayed clean. Every test here
fails on e0fc3d2d6 (run_week has no --input-dir; the harness has no read-set proof).
"""
import json
import shutil
import socket
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests._fwd_stub import RATINGS_FILES, write_stub_outputs  # noqa: E402
from nfl.sim.tests.test_fwd3_item0 import (  # noqa: E402
    _build_fixture_root, T, GAME_ID)

CLE_BUNDLE_SUCCESS = 0.4334993874


class _Captured(Exception):
    pass


def _make_inputs(tmp_path):
    d = tmp_path / "run" / "inputs"
    d.mkdir(parents=True)
    for f in RATINGS_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, d / f)
    shutil.copy2(ROOT / "nfl" / "data" / "pbp" / "rosters_weekly.parquet", d / "rosters_weekly.parquet")
    (d / "team_game_counts.json").write_text(json.dumps({"counts": {}, "last_played_week": {}}))
    props = pd.DataFrame([{
        "event_id": "e_pitcle", "commence_time": "2026-10-02T00:15:00Z",
        "home_team": "Cleveland Browns", "away_team": "Pittsburgh Steelers",
        "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
        "player_name": "X Y", "line": 4.5, "over_price": -110, "under_price": -110,
        "pull_timestamp": "2026-10-01T22:00:00+00:00", "snapshot_tag": "close",
        "pull_batch": "b1"}])
    pf = tmp_path / "run" / "props.parquet"
    props.to_parquet(pf, index=False)
    return d, pf


def _shared_with_cle(tmp_path, value):
    """A 'shared' ratings dir identical to the repo's except CLE week-4 pass_off success."""
    sd = tmp_path / "shared_ratings"
    sd.mkdir()
    for f in RATINGS_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, sd / f)
    tr = pd.read_parquet(sd / "team_ratings_weekly.parquet")
    m = (tr.season == 2026) & (tr.week == 4) & (tr.team == "CLE") & (tr.unit == "pass_off")
    tr.loc[m, "success"] = value
    tr.to_parquet(sd / "team_ratings_weekly.parquet", index=False)
    return sd


def _run_week_capturing(monkeypatch, tmp_path, input_dir, props_file):
    import nfl.sim.run_week as rw
    captured = {}

    def fake_solver(home, away, season, week, spread, total, anchoring_log=None, **kw):
        captured["team_r"] = kw["team_r"]
        raise _Captured()
    monkeypatch.setattr(rw, "run_anchored_chunked", fake_solver)
    run_dir = tmp_path / "run" / "outputs"
    with pytest.raises(_Captured):
        rw.main(["--week", "4", "--as-of", "2026-10-01T23:30:00+00:00",
                 "--lines-json", json.dumps({"PIT@CLE": {"spread": -2.5, "total": 38.0}}),
                 "--games", "PIT@CLE", "--run-dir", str(run_dir),
                 "--input-dir", str(input_dir), "--props-file", str(props_file),
                 "--run-id", "20261001T233000Z"])
    return captured, run_dir


def test_solver_receives_bundle_value_not_shared(monkeypatch, tmp_path):
    """The auditor's A1 counterexample through the real run_week.main(): the shared CLE
    rating is 0.99, the bundle copy 0.4334993874 — the solver must receive the copy."""
    import nfl.sim.engine as E
    import nfl.sim.calibration as C
    input_dir, props_file = _make_inputs(tmp_path)
    shared = _shared_with_cle(tmp_path, 0.99)
    monkeypatch.setattr(E, "RATINGS_DIR", shared)
    monkeypatch.setattr(C, "RATINGS_DIR", shared)
    captured, run_dir = _run_week_capturing(monkeypatch, tmp_path, input_dir, props_file)
    tr = captured["team_r"]
    v = tr[(tr.season == 2026) & (tr.week == 4) & (tr.team == "CLE") &
           (tr.unit == "pass_off")]["success"].iloc[0]
    assert abs(v - CLE_BUNDLE_SUCCESS) < 1e-9, f"solver received {v}, bundle holds {CLE_BUNDLE_SUCCESS}"
    # routing is undone after the run
    assert E.RATINGS_DIR == shared


def test_read_set_records_bundle_reads_and_no_shared_ratings(monkeypatch, tmp_path):
    """The real run_week writes read_set.json: every required input read from the run
    directory, with the hash of the bytes parsed; no shared ratings file appears."""
    from nfl.sim.read_set import MUST_READ
    input_dir, props_file = _make_inputs(tmp_path)
    _, run_dir = _run_week_capturing(monkeypatch, tmp_path, input_dir, props_file)
    rs = json.loads((run_dir / "read_set.json").read_text())
    paths = {e["path"] for e in rs["entries"]}
    import hashlib
    for f in MUST_READ:
        p = str((input_dir / f).resolve())
        if f == "team_game_counts.json":
            continue  # read later in main, after the solver (stopped here)
        assert p in paths, f"{f} not read from the run directory"
        e = next(x for x in rs["entries"] if x["path"] == p)
        assert e["sha256"] == hashlib.sha256((input_dir / f).read_bytes()).hexdigest()
    shared = str((ROOT / "nfl" / "data" / "sim" / "ratings").resolve())
    assert not any(p.startswith(shared) for p in paths), "a shared ratings file was read"
    assert not any("odds_archive" in p for p in paths), "the props archive was read"
    assert rs["network_attempts"] == []


def test_missing_input_halts_without_network(monkeypatch, tmp_path):
    """A missing input HALTs — never a shared-file fallback or an nflreadpy fetch."""
    import nfl.sim.run_week as rw
    input_dir, props_file = _make_inputs(tmp_path)
    (input_dir / "rosters_weekly.parquet").unlink()
    with pytest.raises(SystemExit, match="run inputs missing"):
        rw.main(["--week", "4", "--lines-json", json.dumps({"PIT@CLE": {"spread": -2.5, "total": 38.0}}),
                 "--games", "PIT@CLE", "--run-dir", str(tmp_path / "run" / "outputs"),
                 "--input-dir", str(input_dir), "--props-file", str(props_file),
                 "--run-id", "r1"])


def test_run_dir_without_input_dir_halts(tmp_path):
    import nfl.sim.run_week as rw
    with pytest.raises(SystemExit, match="--run-dir requires --input-dir"):
        rw.main(["--week", "4", "--run-dir", str(tmp_path / "o")])


def test_network_blocked_while_recording():
    from nfl.sim.read_set import ReadSetRecorder
    rec = ReadSetRecorder().install()
    try:
        with pytest.raises(RuntimeError, match="network access"):
            socket.getaddrinfo("example.com", 443)
    finally:
        rec.uninstall()
    socket.getaddrinfo("localhost", 80)  # unblocked again


def _harness(root, run_week_fn):
    from nfl.sim.run_forward_v1 import main
    return main(argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                      "--allow-stale-quotes"], root=str(root), run_week_fn=run_week_fn)


def _stub_with_read_set(mutate):
    def stub(root, week, T_, bundle_lines, game_ids, run_dir=None,
             input_dir=None, props_file=None, run_id=None):
        write_stub_outputs(run_dir, week, run_id, input_dir, props_file, GAME_ID, [{
            "game_id": GAME_ID, "player_id": "00-0033118", "player_name": "T.Kelce",
            "family": "receptions", "line": 5.5, "cal_p": 0.62, "side": "over", "tier": "T1"}])
        rs_path = Path(run_dir) / "read_set.json"
        rs = json.loads(rs_path.read_text())
        mutate(rs, Path(root), Path(input_dir))
        rs_path.write_text(json.dumps(rs))
    return stub


def test_harness_halts_on_shared_file_read(tmp_path):
    """A read of the shared ratings file (instead of the bundle copy) HALTs the harness."""
    import hashlib
    root = _build_fixture_root(tmp_path)

    def add_shared(rs, root, input_dir):
        p = root / "nfl" / "data" / "sim" / "ratings" / "team_ratings_weekly.parquet"
        rs["entries"].append({"path": str(p.resolve()),
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "reads": 1})
    with pytest.raises(SystemExit, match="unlisted shared file"):
        _harness(root, _stub_with_read_set(add_shared))


def test_harness_halts_when_input_not_read_from_bundle(tmp_path):
    root = _build_fixture_root(tmp_path)

    def drop_team_ratings(rs, root, input_dir):
        rs["entries"] = [e for e in rs["entries"] if not e["path"].endswith("team_ratings_weekly.parquet")]
    with pytest.raises(SystemExit, match="did not read these inputs"):
        _harness(root, _stub_with_read_set(drop_team_ratings))


def test_harness_halts_when_consumed_bytes_differ_from_bundle(tmp_path):
    """The consumed bytes' hash must equal the bundle manifest's (a copy changed mid-run)."""
    root = _build_fixture_root(tmp_path)

    def wrong_hash(rs, root, input_dir):
        for e in rs["entries"]:
            if e["path"].endswith("team_ratings_weekly.parquet"):
                e["sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="differs from the bundle manifest"):
        _harness(root, _stub_with_read_set(wrong_hash))


def test_harness_halts_without_read_set(tmp_path):
    root = _build_fixture_root(tmp_path)

    def no_rs(root_, week, T_, bundle_lines, game_ids, run_dir=None,
              input_dir=None, props_file=None, run_id=None):
        write_stub_outputs(run_dir, week, run_id, None, None, GAME_ID, [{
            "game_id": GAME_ID, "player_id": "00-0033118", "player_name": "T.Kelce",
            "family": "receptions", "line": 5.5, "cal_p": 0.62, "side": "over", "tier": "T1"}])
    with pytest.raises(SystemExit, match="read_set.json missing"):
        _harness(root, no_rs)


def test_rosters_depth_injuries_copied_and_rosters_required(tmp_path):
    """Rosters are a required, consumed input; depth charts and injuries are copied as record."""
    from nfl.sim.run_forward_v1 import build_bundle
    import nfl.sim.run_forward_v1 as fwd
    from nfl.sim.tests.test_fwd3_item0 import _set_fwd_paths
    root = _build_fixture_root(tmp_path)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        bd, man = build_bundle(2026, 3, T, pilot=True, allow_stale_quotes=True, _root=root)
        assert (bd / "inputs" / "rosters_weekly.parquet").exists()
        assert "inputs/rosters_weekly.parquet" in man
        (root / "nfl" / "data" / "pbp" / "rosters_weekly.parquet").unlink()
        with pytest.raises(SystemExit, match="prediction input missing"):
            build_bundle(2026, 3, T.replace(minute=1), pilot=True, allow_stale_quotes=True, _root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def test_per_team_freshness_halts_on_stale_team_usage(tmp_path):
    """Freshness is per participating team on the consumed copies: a team whose usage
    stops before its last played week HALTs, even when other teams are current."""
    root = _build_fixture_root(tmp_path)
    up = root / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet"
    u = pd.read_parquet(up)
    u = u[~((u.season == 2026) & (u.team == "CAR") & (u.week >= 2))]
    u.to_parquet(up, index=False)
    with pytest.raises(SystemExit, match="CAR: usage max week"):
        _harness(root, _stub_with_read_set(lambda *a: None))


def test_stale_pbp_halts(tmp_path):
    """If the PBP file has no completed week W-1 game, 'last played' is untrustworthy."""
    root = _build_fixture_root(tmp_path)
    pp = root / "nfl" / "data" / "pbp" / "pbp_2026.parquet"
    p = pd.read_parquet(pp)
    p["week"] = 1
    p.to_parquet(pp, index=False)
    with pytest.raises(SystemExit, match="no completed week-2 game"):
        _harness(root, _stub_with_read_set(lambda *a: None))


def test_restore_rebuilds_inputs_and_verifies(tmp_path):
    """Move a completed run's inputs/ aside; restore_run rebuilds it from the archive and
    verify_bundle is clean. A file absent from the archive is reported unavailable."""
    from nfl.sim.restore_run import restore
    from nfl.sim.run_forward_v1 import archive_root_for, verify_bundle
    root = _build_fixture_root(tmp_path)
    from nfl.sim.tests.test_fwd3_item0 import _stub_run_week
    assert _harness(root, _stub_run_week) is not None
    bd = next((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    shutil.move(str(bd / "inputs"), str(tmp_path / "inputs_aside"))
    assert any("missing: inputs/" in b for b in verify_bundle(bd))
    restored, unavailable, bad = restore(bd, archive_root_for(root))
    assert unavailable == [] and bad == []
    assert any(r.startswith("inputs/") for r in restored)
    # a file whose archive copy is gone cannot be restored
    shutil.rmtree(archive_root_for(root))
    (bd / "inputs" / "league_baselines.parquet").unlink()
    _, unavailable, _ = restore(bd, archive_root_for(root))
    assert unavailable == ["inputs/league_baselines.parquet"]
