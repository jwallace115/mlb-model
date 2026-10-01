"""D263-D265 (FWD6c): ChatGPT audit #10 counterexamples and surviving mutations.

Every audit-#10 (A) item and the freeze-side (D) survivors have a test here. All fixtures
are committed. No parametrize (CLAUDE.md): cases are looped inside one test.
"""
import hashlib
import io
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests._fwd_stub import write_stub_outputs  # noqa: E402
from nfl.sim.tests.test_fwd3_item0 import (  # noqa: E402
    _build_fixture_root, _stub_run_week, _set_fwd_paths, T, GAME_ID)
from nfl.sim.tests.test_fwd6b import _harness, _run_dir, _stub, PICK  # noqa: E402


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _bundle(root, week=3):
    import nfl.sim.run_forward_v1 as fwd
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        return fwd.build_bundle(2026, week, T, pilot=True, allow_stale_quotes=True, _root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def _recorded(fn, code_allow=None):
    from nfl.sim.read_set import ReadSetRecorder
    rec = ReadSetRecorder().install(code_allow=code_allow)
    err = None
    try:
        fn()
    except Exception as e:     # noqa: BLE001 — the test inspects it
        err = e
    finally:
        rec.uninstall()
    return rec, err


# ── A1: the freeze gate is isolated from the freezing process ──────────────────

def test_hostile_pytest_plugin_cannot_reach_the_freeze(tmp_path, monkeypatch):
    """Audit #10 A1: a plugin injected through PYTEST_PLUGINS ran inside the harness (via
    in-process pytest.main) and froze p_first 0.97 where the worker said 0.62. Now the
    harness never calls pytest.main, and the gate subprocess drops PYTEST_PLUGINS and
    disables autoload — the plugin is never loaded and the frozen value is the worker's."""
    import pytest as _pytest
    plug = tmp_path / "plugdir"
    plug.mkdir()
    marker = tmp_path / "PLUGIN_LOADED"
    (plug / "hostile_plugin.py").write_text(
        f"open({str(marker)!r}, 'w').write('x')\n"
        "def pytest_sessionfinish(session, exitstatus):\n"
        "    import sys\n"
        "    m = sys.modules.get('nfl.sim.run_forward_v1')\n"
        "    if m:\n"
        "        real = m.fill_sheet\n"
        "        def evil(*a, **k):\n"
        "            f, n = real(*a, **k)\n"
        "            f.loc[f['tag'] == 'sim_v1', 'p_first'] = 0.97\n"
        "            return f, n\n"
        "        m.fill_sheet = evil\n")
    monkeypatch.setenv("PYTEST_PLUGINS", "hostile_plugin")
    monkeypatch.setenv("PYTHONPATH", str(plug) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    monkeypatch.setattr(_pytest, "main", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("pytest.main called inside the freezing process")))
    root = _build_fixture_root(tmp_path)
    dest = _harness(root)
    assert not marker.exists(), "the hostile plugin was loaded"
    fz = pd.read_parquet(dest)
    sim = fz[fz["tag"] == "sim_v1"]
    assert len(sim) == 1 and abs(float(sim["p_first"].iloc[0]) - 0.62) < 1e-9


def test_gate_environment_drops_plugins_and_options():
    from nfl.sim.run_forward_v1 import freeze_gate_env
    env = freeze_gate_env({"PYTEST_PLUGINS": "x", "PYTEST_ADDOPTS": "-k nothing", "HOME": "/h"})
    assert "PYTEST_PLUGINS" not in env and "PYTEST_ADDOPTS" not in env
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1" and env["HOME"] == "/h"


def test_gate_report_requires_all_four_named_tests_passed():
    from nfl.sim.run_forward_v1 import check_gate_report, FREEZE_GATE_TESTS

    def xml(cases):
        return "<testsuites><testsuite>" + "".join(
            f'<testcase name="{n}">{extra}</testcase>' for n, extra in cases) + \
            "</testsuite></testsuites>"
    ok = [(n, "") for n in FREEZE_GATE_TESTS]
    check_gate_report(xml(ok))
    bad_cases = {
        "skipped": ok[:3] + [(FREEZE_GATE_TESTS[3], '<skipped message="s"/>')],
        "failure": ok[:3] + [(FREEZE_GATE_TESTS[3], '<failure message="f"/>')],
        "error": ok[:3] + [(FREEZE_GATE_TESTS[3], '<error message="e"/>')],
        "deselected": ok[:3],
        "extra": ok + [("test_other", "")],
    }
    for label, cases in bad_cases.items():
        with pytest.raises(SystemExit, match="freeze gate did not pass"):
            check_gate_report(xml(cases))
            raise AssertionError(label)


def test_real_gate_runs_in_a_subprocess_and_passes():
    import nfl.sim.run_forward_v1 as fwd
    calls = []
    real = fwd.subprocess.run

    def spy(cmd, *a, **k):
        calls.append((cmd, k.get("env", {})))
        return real(cmd, *a, **k)
    with patch.object(fwd.subprocess, "run", side_effect=spy):
        fwd.run_freeze_gate()
    assert len(calls) == 1
    cmd, env = calls[0]
    assert cmd[1:3] == ["-m", "pytest"] and any(c.startswith("--junitxml=") for c in cmd)
    assert env.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"


# ── A2: the read set certifies only bytes it served ────────────────────────────

def test_update_mode_open_is_refused_and_rejected(tmp_path):
    """Audit #10 A2: through an 'r+' handle the consumer read 0.99 while the record held
    the hash of 0.10, and classify_read_set passed."""
    from nfl.sim.read_set import classify_read_set
    f = tmp_path / "x.bin"
    f.write_bytes(b"0.10")

    def go():
        with open(f, "r+b", buffering=0) as fh:
            fh.write(b"0.99")
    rec, err = _recorded(go)
    assert isinstance(err, PermissionError)
    assert f.read_bytes() == b"0.10"
    assert rec.violations
    doc = rec.write(tmp_path / "rs.json")
    with pytest.raises(SystemExit, match="forbidden reads"):
        classify_read_set(doc, tmp_path / "b", tmp_path, {}, {})


def test_os_open_rdwr_is_a_violation_and_audit_reads_are_unproven(tmp_path):
    from nfl.sim.read_set import classify_read_set
    f = tmp_path / "x.bin"
    f.write_bytes(b"0.10")

    def rdwr():
        fd = os.open(f, os.O_RDWR)
        os.close(fd)
    rec, _ = _recorded(rdwr)
    assert rec.violations, "an O_RDWR open of an input was not flagged"

    def rdonly():
        fd = os.open(f, os.O_RDONLY)
        os.read(fd, 4)
        os.close(fd)

    def fileio():
        with io.FileIO(str(f), "r") as fh:
            fh.read()
    for go in (rdonly, fileio):
        rec, _ = _recorded(go)
        e = rec.entries[str(f.resolve())]
        assert e["via"] == {"audit"}, e
        doc = rec.write(tmp_path / "rs.json")
        assert doc["entries"][0]["via"] == ["audit"]
        with pytest.raises(SystemExit, match="not byte-bound"):
            classify_read_set(doc, tmp_path / "b", tmp_path, {}, {})


def test_native_arrow_readers_are_refused(tmp_path):
    """Audit #10 C: pyarrow.dataset and pyarrow.memory_map returned data with no entry."""
    import pyarrow as pa
    import pyarrow.dataset as pads
    import pyarrow.parquet as pq
    f = tmp_path / "x.parquet"
    pd.DataFrame({"v": [0.99]}).to_parquet(f, index=False)
    cases = {"dataset": lambda: pads.dataset(str(f)).to_table(),
             "memory_map": lambda: pa.memory_map(str(f)).read(),
             "input_stream": lambda: pa.input_stream(str(f)).read(),
             "read_pandas": lambda: pq.read_pandas(str(f)),
             "read_metadata": lambda: pq.read_metadata(str(f)),
             "ParquetDataset": lambda: pq.ParquetDataset(str(f)).read()}
    for name, go in cases.items():
        rec, err = _recorded(go)
        assert isinstance(err, PermissionError), f"{name}: not refused ({err!r})"
        assert rec.violations, name
    # BytesIO sources (what the wrappers hand the parsers) still work
    rec, err = _recorded(lambda: pd.read_parquet(f))
    assert err is None and rec.entries[str(f.resolve())]["via"] == {"wrapper"}
    # and every API is restored afterwards
    assert pads.dataset(str(f)).to_table().num_rows == 1


def test_py_suffix_is_not_a_data_exemption(tmp_path):
    """Audit #10 C: float(Path('prediction_input.py').read_text()) gave 0.99 with no record."""
    f = tmp_path / "prediction_input.py"
    f.write_text("0.99")
    rec, err = _recorded(lambda: float(f.read_text()))
    assert err is None and str(f.resolve()) in rec.entries
    rec, err = _recorded(lambda: float(f.read_text()), code_allow={str(f)})
    assert str(f.resolve()) not in rec.entries      # only listed code is exempt


def test_classifier_rejects_entries_without_byte_binding(tmp_path):
    from nfl.sim.read_set import classify_read_set
    root = tmp_path / "repo"
    (root / "t").mkdir(parents=True)
    f = root / "t" / "table.parquet"
    f.write_bytes(b"abc")
    h = _sha(f)
    hashes = {"t/table.parquet": h[:16]}
    for via in (None, ["wrapper", "audit"], ["audit"]):
        e = {"path": str(f), "sha256": h, "reads": 1}
        if via is not None:
            e["via"] = via
        with pytest.raises(SystemExit, match="not byte-bound"):
            classify_read_set({"entries": [e]}, tmp_path / "b", root, hashes, {})


def test_conflicting_rereads_and_network_attempts_are_rejected(tmp_path):
    from nfl.sim.read_set import classify_read_set
    f = tmp_path / "x.json"
    f.write_text('{"a": 1}')

    def go():
        f.read_text()
        f.write_text('{"a": 2}')
        f.read_text()
    rec, _ = _recorded(go)
    assert rec.conflicts == [str(f.resolve())]
    doc = rec.write(tmp_path / "rs.json")
    with pytest.raises(SystemExit, match="file changed between two reads"):
        classify_read_set(doc, tmp_path / "b", tmp_path, {}, {})
    with pytest.raises(SystemExit, match="network access attempted"):
        classify_read_set({"entries": [], "network_attempts": ["socket.connect x"]},
                          tmp_path / "b", tmp_path, {}, {})


def test_parquetfile_and_large_reads_hash_the_delivered_bytes(tmp_path):
    import pyarrow.parquet as pq
    f = tmp_path / "x.parquet"
    pd.DataFrame({"v": [0.5]}).to_parquet(f, index=False)
    rec, err = _recorded(lambda: pq.ParquetFile(str(f)).read())
    assert err is None and rec.entries[str(f.resolve())]["sha256"] == _sha(f)
    big = tmp_path / "big.bin"
    big.write_bytes(os.urandom(17 * 1024 * 1024))
    got = {}
    rec, err = _recorded(lambda: got.setdefault("b", big.read_bytes()))
    assert err is None and len(got["b"]) == 17 * 1024 * 1024
    assert rec.entries[str(big.resolve())]["sha256"] == _sha(big)


def test_text_reads_without_errors_policy_raise_like_open(tmp_path):
    f = tmp_path / "bad.txt"
    f.write_bytes(b"ok\xff")
    with pytest.raises(UnicodeDecodeError):
        f.read_text(encoding="utf-8")
    rec, err = _recorded(lambda: f.read_text(encoding="utf-8"))
    assert isinstance(err, UnicodeDecodeError)


def test_csv_files_are_data(tmp_path):
    from nfl.sim.read_set import _excluded
    f = tmp_path / "x.csv"
    f.write_text("a\n1\n")
    assert not _excluded(str(f))
    rec, err = _recorded(lambda: pd.read_csv(f))
    assert err is None and rec.entries[str(f.resolve())]["via"] == {"wrapper"}
    assert len(pd.read_csv(f)) == 1


def test_uninstall_restores_every_api_even_after_an_exception(tmp_path):
    import builtins
    import pyarrow as pa
    import pyarrow.dataset as pads
    import pyarrow.parquet as pq
    before = (builtins.open, io.open, pd.read_parquet, pd.read_csv, pd.read_json,
              pq.read_table, pq.ParquetFile, pa.memory_map, pa.input_stream, pads.dataset,
              pq.read_pandas, pq.read_metadata)
    rec, err = _recorded(lambda: (_ for _ in ()).throw(ValueError("boom")))
    assert isinstance(err, ValueError)
    after = (builtins.open, io.open, pd.read_parquet, pd.read_csv, pd.read_json,
             pq.read_table, pq.ParquetFile, pa.memory_map, pa.input_stream, pads.dataset,
             pq.read_pandas, pq.read_metadata)
    assert all(a is b for a, b in zip(before, after))


def test_route_inputs_restores_every_routed_path(tmp_path):
    from nfl.sim.read_set import route_inputs
    from nfl.sim.tests.test_fwd6_item0 import _make_inputs
    import nfl.sim.engine as E
    import nfl.sim.calibration as C
    import nfl.sim.names as N
    import nfl.sim.usage as U
    before = (E.RATINGS_DIR, C.RATINGS_DIR, C.USAGE_PATH, N.ROSTER_PATH, U.PBP_DIR)
    input_dir, _ = _make_inputs(tmp_path)
    restore = route_inputs(input_dir)
    assert Path(U.PBP_DIR).resolve() == Path(input_dir).resolve()
    restore()
    assert (E.RATINGS_DIR, C.RATINGS_DIR, C.USAGE_PATH, N.ROSTER_PATH, U.PBP_DIR) == before


def test_persisted_read_set_carries_via_and_violations(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")
    rec, _ = _recorded(lambda: f.read_text())
    doc = rec.write(tmp_path / "rs.json")
    on_disk = json.loads((tmp_path / "rs.json").read_text())
    assert on_disk == doc and on_disk["entries"][0]["via"] == ["wrapper"]
    assert on_disk["violations"] == []


# ── A3: PBP-derived metadata comes from one immutable snapshot ─────────────────

def test_pbp_replaced_mid_build_cannot_mix_versions(tmp_path, monkeypatch):
    """Audit #10 A3: the shared PBP was replaced right after the counts were computed; the
    JSON held counts from one version and the hash of another."""
    import nfl.sim.run_week as rw
    from nfl.sim.run_forward_v1 import archive_root_for, _last_played_weeks
    real = rw.count_team_completed_games
    # the refresh lands AFTER the counts (audit #10's injection) or BEFORE them (between
    # the snapshot and the count) — either way every field must come from the snapshot
    for when in ("after", "before"):
        root = _build_fixture_root(tmp_path / when)
        shared = root / "nfl" / "data" / "pbp" / "pbp_2026.parquet"

        def refresh(shared=shared):
            df = pd.read_parquet(shared)
            extra = df.copy()
            extra["game_id"] = extra["game_id"] + "_dup"
            pd.concat([df, extra]).to_parquet(shared, index=False)

        def count_with_refresh(season, pbp_path=None, when=when, refresh=refresh):
            if when == "before":
                refresh()
            out = real(season, pbp_path=pbp_path)
            if when == "after":
                refresh()
            return out
        monkeypatch.setattr(rw, "count_team_completed_games", count_with_refresh)
        bd, _ = _bundle(root)
        tgc = json.loads((bd / "inputs" / "team_game_counts.json").read_text())
        snap = archive_root_for(root) / "sha256" / tgc["source_sha256"]
        assert snap.exists() and _sha(snap) == tgc["source_sha256"], when
        assert tgc["counts"] == real(2026, pbp_path=snap) == {"KC": 1, "CAR": 1}, when
        assert {k: int(v) for k, v in tgc["last_played_week"].items()} == \
            _last_played_weeks(snap, 3), when


# ── A4: the claimed cutoff and bundle are checked ──────────────────────────────

def test_invocation_cutoff_or_bundle_not_the_bundles_halts(tmp_path):
    """Audit #10 A4: invocation.json claiming cutoff 1900-01-01 and bundle /wrong/bundle froze."""
    for key, val, msg in (("cutoff_T", "1900-01-01T00:00:00+00:00", "claims cutoff"),
                          ("cutoff_T", None, "claims cutoff"),
                          ("bundle_dir", "/wrong/bundle", "ran against bundle"),
                          ("season", 2025, "does not match the bundle")):
        root = _build_fixture_root(tmp_path / f"{key}_{val}".replace("/", "_"))

        def edit(run_dir, bundle_dir, key=key, val=val):
            inv = json.loads((run_dir / "invocation.json").read_text())
            inv[key] = val
            (run_dir / "invocation.json").write_text(json.dumps(inv))
        with pytest.raises(SystemExit, match=msg):
            _harness(root, _stub(after=edit))


def test_freshness_json_is_a_mandatory_bundle_read(tmp_path):
    from nfl.sim.read_set import MUST_READ_BUNDLE
    assert "freshness.json" in MUST_READ_BUNDLE
    root = _build_fixture_root(tmp_path)

    def drop(run_dir, bundle_dir):
        rs = json.loads((run_dir / "read_set.json").read_text())
        rs["entries"] = [e for e in rs["entries"] if not e["path"].endswith("freshness.json")]
        (run_dir / "read_set.json").write_text(json.dumps(rs))
    with pytest.raises(SystemExit, match="did not read these inputs"):
        _harness(root, _stub(after=drop))


def test_real_worker_outputs_pass_parent_validation(tmp_path):
    """End to end: the REAL worker's outputs (identity, invocation cutoff and bundle) pass
    the parent's checks. Kills 'worker emits week+1' and 'worker writes cutoff 1900'."""
    import nfl.sim.run_week as rw
    from nfl.sim.run_forward_v1 import _validate_outputs, lines_dict_from_bundle
    from nfl.sim.tests.test_fwd6_item0 import _make_inputs
    input_dir, props_file = _make_inputs(tmp_path)
    bundle = tmp_path / "run"
    run_dir = bundle / "outputs"
    rw.main(["--week", "4", "--run-dir", str(run_dir), "--input-dir", str(input_dir),
             "--props-file", str(props_file), "--run-id", "20261001T233000Z",
             "--bundle-dir", str(bundle)])
    lines = lines_dict_from_bundle(bundle)
    picks, ar = _validate_outputs(run_dir, 4, "20261001T233000Z", sorted(lines),
                                  bundle_lines=lines, bundle_dir=bundle)
    assert len(ar) == 1
    rs = json.loads((run_dir / "read_set.json").read_text())
    assert rs["violations"] == [] and all(e["via"] == ["wrapper"] for e in rs["entries"])


# ── A5: rating units are required by name ──────────────────────────────────────

def test_required_rating_units_by_name_and_worst_unit(tmp_path):
    """Audit #10 A5: renaming CLE's pass_off unit to junk_unit still passed (four distinct
    labels). Also: three fresh units plus one stale unit must HALT (kills min -> max)."""
    from nfl.sim.run_forward_v1 import _team_freshness, REQUIRED_RATING_UNITS
    src = ROOT / "nfl" / "data" / "sim" / "ratings"
    base = tmp_path / "base"
    base.mkdir()
    for f in ("team_ratings_weekly.parquet", "tendencies_weekly.parquet",
              "tendencies_situational_weekly.parquet", "player_usage_weekly.parquet",
              "active_universe_weekly.parquet", "kicker_weekly.parquet",
              "qb_ratings_weekly.parquet"):
        shutil.copy2(src / f, base / f)
    _team_freshness(base, 2026, 4, ["CLE"], {"CLE": 3})       # untouched: passes
    tr = pd.read_parquet(base / "team_ratings_weekly.parquet")
    for unit in REQUIRED_RATING_UNITS:
        d = tmp_path / f"rename_{unit}"
        shutil.copytree(base, d)
        x = tr.copy()
        x.loc[(x["team"] == "CLE") & (x["unit"] == unit), "unit"] = "junk_unit"
        x.to_parquet(d / "team_ratings_weekly.parquet", index=False)
        with pytest.raises(SystemExit, match="team_ratings"):
            _team_freshness(d, 2026, 4, ["CLE"], {"CLE": 3})
    d = tmp_path / "one_stale"
    shutil.copytree(base, d)
    x = tr[~((tr["team"] == "CLE") & (tr["unit"] == "rush_def") & (tr["season"] == 2026)
             & (tr["week"] >= 3))]
    x.to_parquet(d / "team_ratings_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="team_ratings"):
        _team_freshness(d, 2026, 4, ["CLE"], {"CLE": 3})


# ── audit-#10 (D) freeze-side survivors ─────────────────────────────────────────

def test_schedule_tolerance_is_exactly_sixty_minutes():
    from nfl.sim.run_forward_v1 import _map_events_to_schedule
    sched = pd.DataFrame([{"game_id": "2026_04_PIT_CLE", "season": 2026, "game_type": "REG",
                           "week": 4, "gameday": "2026-10-01", "gametime": "20:15",
                           "home_team": "CLE", "away_team": "PIT"}])
    for minutes, ok in ((60, True), (61, False)):
        kick = datetime(2026, 10, 2, 0, 15, tzinfo=timezone.utc) + timedelta(minutes=minutes)
        ev = pd.DataFrame([{"event_id": "e", "game_id": "PIT@CLE", "home_abbr": "CLE",
                            "away_abbr": "PIT",
                            "commence_time": kick.strftime("%Y-%m-%dT%H:%M:%SZ")}])
        if ok:
            assert _map_events_to_schedule(ev, sched, 4) == ["2026_04_PIT_CLE"]
        else:
            with pytest.raises(SystemExit):
                _map_events_to_schedule(ev, sched, 4)


def test_schedule_from_other_seasons_is_filtered(tmp_path):
    from nfl.sim.run_forward_v1 import _load_schedule
    d = tmp_path / "nfl" / "data" / "pbp"
    d.mkdir(parents=True)
    rows = [{"game_id": f"{s}_04_PIT_CLE", "season": s, "game_type": "REG", "week": 4,
             "gameday": f"{s}-10-01", "gametime": "20:15", "home_team": "CLE", "away_team": "PIT"}
            for s in (2025, 2026)]
    pd.DataFrame(rows).to_parquet(d / "schedules_2026.parquet", index=False)
    df, _ = _load_schedule(2026, tmp_path)
    assert list(df["season"]) == [2026]


def test_finalisation_halts_on_a_vanished_listed_file(tmp_path):
    from nfl.sim.run_forward_v1 import _finalize_bundle_manifest
    root = _build_fixture_root(tmp_path)
    bd, _ = _bundle(root)
    (bd / "inputs" / "kicker_weekly.parquet").unlink()
    with pytest.raises(SystemExit, match=r"missing=\['inputs/kicker_weekly.parquet'\]"):
        _finalize_bundle_manifest(bd)


def test_conflicting_archived_receipt_is_refused_and_kept(tmp_path):
    from nfl.sim.run_forward_v1 import archive_receipt
    archive_receipt(tmp_path, {"run_id": "R", "rows": 1})
    f = tmp_path / "receipts" / "R.json"
    before = f.read_bytes()
    with pytest.raises(SystemExit, match="different receipt"):
        archive_receipt(tmp_path, {"run_id": "R", "rows": 2})
    assert f.read_bytes() == before


def test_default_worker_timeout_is_two_hours(tmp_path):
    import nfl.sim.run_forward_v1 as fwd
    seen = {}

    class R:
        returncode, stdout, stderr = 0, "", ""

    def fake(cmd, **k):
        seen.update(k)
        return R()
    with patch.object(fwd.subprocess, "run", side_effect=fake):
        fwd._default_run_week(tmp_path, 4, T, {}, [], run_dir=tmp_path, input_dir=tmp_path,
                              props_file=tmp_path / "p", run_id="r", bundle_dir=tmp_path)
    assert seen["timeout"] == 7200


def test_live_freeze_records_pilot_false_everywhere(tmp_path):
    """A live (non-pilot) success: receipt, bundle manifest and frozen rows all say pilot
    False (kills 'every receipt says pilot=True')."""
    from nfl.sim.run_forward_v1 import main, load_receipts
    kick = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
    root = _build_fixture_root(tmp_path, kick=kick)
    dest = main(argv=["--week", "3", "--window-hours", "4"], root=str(root),
                run_week_fn=_stub_run_week)
    rec = load_receipts(root)
    assert len(rec) == 1 and rec[0]["pilot"] is False
    bd = _run_dir(root)
    assert json.loads((bd / "bundle_manifest.json").read_text())["pilot"] is False
    assert not pd.read_parquet(dest)["pilot"].any()


# ── R5: recovery reports what it cannot vouch for ──────────────────────────────

def test_restore_reports_a_tampered_manifest_entry_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    """Audit #10 R5: an opinions-manifest entry with a zeroed sha was silently kept and the
    CLI printed clean/complete with exit 0."""
    import nfl.sim.restore_run as RR
    from nfl.sim.run_forward_v1 import archive_root_for
    root = _build_fixture_root(tmp_path)
    dest = Path(_harness(root))
    om = dest.parent / "manifest.json"
    entries = json.loads(om.read_text())
    for e in entries:
        if e["file"] == dest.name:
            e["sha256"] = "0" * 64
    om.write_text(json.dumps(entries, indent=1) + "\n")
    monkeypatch.setattr(RR, "ROOT", root)
    with pytest.raises(SystemExit) as ex:
        RR.main(["--run-id", _run_dir(root).name, "--archive", str(archive_root_for(root))])
    assert ex.value.code == 1
    assert "differs from the receipt" in capsys.readouterr().out


def test_restore_rebuilds_the_exact_manifest_entry(tmp_path):
    from nfl.sim.restore_run import find_receipt, restore
    from nfl.sim.run_forward_v1 import archive_root_for
    root = _build_fixture_root(tmp_path)
    dest = Path(_harness(root))
    om = dest.parent / "manifest.json"
    want = [e for e in json.loads(om.read_text()) if e["file"] == dest.name]
    om.unlink()
    receipt, _ = find_receipt(_run_dir(root).name, root, archive_root_for(root))
    restore(_run_dir(root), archive_root_for(root), receipt=receipt, root=root)
    got = [e for e in json.loads(om.read_text()) if e["file"] == dest.name]
    assert got == want and len(got) == 1


def test_restore_cli_exits_nonzero_when_receipt_status_is_not_complete(tmp_path, monkeypatch):
    import nfl.sim.restore_run as RR
    from nfl.sim.run_forward_v1 import archive_root_for, RECEIPTS_REL
    root = _build_fixture_root(tmp_path)
    _harness(root)
    reg = root / RECEIPTS_REL
    line = reg.read_text()
    reg.write_text(line + line)          # a duplicate receipt -> status 'mismatch'
    monkeypatch.setattr(RR, "ROOT", root)
    with pytest.raises(SystemExit):
        RR.main(["--run-id", _run_dir(root).name, "--archive", str(archive_root_for(root))])


def test_archive_receipt_index_must_hold_the_requested_run(tmp_path):
    from nfl.sim.restore_run import find_receipt
    d = tmp_path / "receipts"
    d.mkdir()
    (d / "another-run.json").write_text(json.dumps({"run_id": "20260927T165000Z"}))
    with pytest.raises(SystemExit, match="holds run 20260927T165000Z"):
        find_receipt("another-run", tmp_path / "repo", tmp_path)


def test_corrupt_archive_object_is_not_installed(tmp_path):
    from nfl.sim.restore_run import _from_archive
    h = hashlib.sha256(b"good").hexdigest()
    (tmp_path / "sha256").mkdir()
    (tmp_path / "sha256" / h).write_bytes(b"evil")
    restored, unavailable = [], []
    _from_archive(tmp_path, h, tmp_path / "out" / "f", restored, unavailable, "f")
    assert not (tmp_path / "out" / "f").exists()
    assert restored == [] and unavailable == ["f (archive copy corrupt)"]


def test_hashed_code_uses_no_unrecordable_read_api():
    """Native readers the recorder cannot serve bytes for must not appear in ANY hashed
    module (pa.OSFile cannot be wrapped; deep pyarrow.dataset APIs bypass the wrappers)."""
    import re
    banned = re.compile(r"np\.load\(|np\.fromfile|np\.memmap|pickle\.load|pyarrow\.dataset|"
                        r"\bds\.dataset\(|ParquetDataset|memory_map|OSFile|input_stream\(|"
                        r"make_fragment|FileSystemDataset|mmap\.mmap|os\.open\(|FileIO\(|"
                        r"read_feather\(|read_orc\(|read_pickle\(|read_hdf\(|read_excel\(")
    hashes = json.loads((ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_text())["file_hashes"]
    checked = 0
    for rel in hashes:
        if not rel.endswith(".py") or "/tests/" in rel or rel.endswith("read_set.py"):
            continue
        hits = [l for l in (ROOT / rel).read_text().splitlines() if banned.search(l)]
        assert not hits, f"{rel}: unrecordable read API: {hits}"
        checked += 1
    assert checked >= 10
