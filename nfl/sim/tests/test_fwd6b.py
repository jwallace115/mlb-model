"""D260-D262 (FWD6b): ChatGPT audit #9 counterexamples and surviving mutations.

Every audit-#9 (A) item and every (C)/(D) finding that is a freeze-side defect has a test
here that fails on e826a30ae. All fixtures are committed (the roster is
nfl/sim/tests/fixtures/rosters_weekly_fixture.parquet) — nothing reads gitignored data.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests._fwd_stub import write_stub_outputs  # noqa: E402
from nfl.sim.tests.test_fwd3_item0 import (  # noqa: E402
    _build_fixture_root, _stub_run_week, _set_fwd_paths, T, KICK, GAME_ID)

PICK = {"game_id": GAME_ID, "player_id": "00-0033118", "player_name": "T.Kelce",
        "family": "receptions", "line": 5.5, "cal_p": 0.62, "side": "over", "tier": "T1"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _harness(root, fn=_stub_run_week, extra=()):
    from nfl.sim.run_forward_v1 import main
    return main(argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                      "--allow-stale-quotes", *extra], root=str(root), run_week_fn=fn)


def _run_dir(root):
    return next((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())


def _stub(after=None, anchor=None, identity=None, alog_identity=None):
    """Stub worker; `after(run_dir, bundle_dir)` runs after the outputs are written."""
    def fn(root, week, T_, bundle_lines, game_ids, run_dir=None,
           input_dir=None, props_file=None, run_id=None, bundle_dir=None):
        write_stub_outputs(run_dir, week, run_id, input_dir, props_file, GAME_ID, [PICK],
                           anchor=anchor, identity_override=identity, bundle_dir=bundle_dir)
        if alog_identity:
            a = pd.read_parquet(Path(run_dir) / "anchoring_log.parquet")
            for k, v in alog_identity.items():
                a[k] = v
            a.to_parquet(Path(run_dir) / "anchoring_log.parquet", index=False)
        if after:
            after(Path(run_dir), Path(bundle_dir))
    return fn


# ── A1: the record keeps the hashes of what was consumed ───────────────────────

def test_input_changed_after_the_worker_read_it_halts(tmp_path):
    """Audit #9 A1: the worker finished, then the bundled CLE-style rating was changed
    before control returned. e826a30ae re-hashed it at finalisation and froze with a
    clean verify and a complete receipt."""
    root = _build_fixture_root(tmp_path)

    def tamper(run_dir, bundle_dir):
        f = bundle_dir / "inputs" / "team_ratings_weekly.parquet"
        df = pd.read_parquet(f)
        df.loc[df.index[0], "success"] = 0.99
        df.to_parquet(f, index=False)
    with pytest.raises(SystemExit, match="read-set proof failed|changed or vanished"):
        _harness(root, _stub(after=tamper))
    assert not list((root / "nfl" / "data" / "board").rglob("ai_opinions_*.parquet"))


def test_finalisation_never_reauthorises_a_changed_listed_file(tmp_path):
    from nfl.sim.run_forward_v1 import _finalize_bundle_manifest, build_bundle
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        bd, man = build_bundle(2026, 3, T, pilot=True, allow_stale_quotes=True, _root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved
    (bd / "freshness.json").write_text("{}")
    with pytest.raises(SystemExit, match=r"changed=\['freshness.json'\]"):
        _finalize_bundle_manifest(bd)
    assert json.loads((bd / "bundle_manifest.json").read_text())["freshness.json"] == man["freshness.json"]


def test_change_between_finalisation_and_freeze_halts(tmp_path, monkeypatch):
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    real = fwd._finalize_bundle_manifest

    def finalize_then_tamper(bd):
        real(bd)
        (bd / "props.parquet").write_bytes(b"tampered")
    monkeypatch.setattr(fwd, "_finalize_bundle_manifest", finalize_then_tamper)
    with pytest.raises(SystemExit, match="read-set proof failed|changed before the freeze"):
        _harness(root)


# ── A2: numerical controls are bound to the bundle ─────────────────────────────

def test_returned_target_differing_from_bundle_halts(tmp_path):
    """Audit #9 A2: the total sent to the worker was 38.5 while the bundle held 38.0; the
    worker returned target_total 38.5 and e826a30ae published target_total 38.0."""
    root = _build_fixture_root(tmp_path)
    row = {"game": GAME_ID, "iterations": 2, "converged": True, "anch_m": 2.9,
           "anch_t": 46.0, "target_spread": 3.0, "target_total": 46.0}
    with pytest.raises(SystemExit, match="solver target target_total"):
        _harness(root, _stub(anchor=[row]))


def test_invocation_not_matching_bundle_halts(tmp_path):
    root = _build_fixture_root(tmp_path)

    def bump(run_dir, bundle_dir):
        inv = json.loads((run_dir / "invocation.json").read_text())
        inv["lines"][GAME_ID]["total"] += 0.5
        (run_dir / "invocation.json").write_text(json.dumps(inv))
    with pytest.raises(SystemExit, match="invocation.json does not match"):
        _harness(root, _stub(after=bump))


def test_missing_invocation_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    with pytest.raises(SystemExit, match="invocation.json missing"):
        _harness(root, _stub(after=lambda r, b: (r / "invocation.json").unlink()))


def test_anchoring_log_identity_checked(tmp_path):
    """Audit #9: anchoring_log with season 1900 / week 99 / run 'other' was accepted."""
    root = _build_fixture_root(tmp_path)
    with pytest.raises(SystemExit, match="anchoring_log season"):
        _harness(root, _stub(alog_identity={"season": 1900, "week": 99, "run_id": "other"}))


def test_fractional_identity_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    with pytest.raises(SystemExit, match="season = "):
        _harness(root, _stub(identity={"season": 2026.5}))


def test_forward_worker_refuses_command_line_lines(tmp_path):
    import nfl.sim.run_week as rw
    with pytest.raises(SystemExit, match="never from --lines-json"):
        rw.main(["--week", "3", "--run-dir", str(tmp_path / "o"), "--input-dir", str(tmp_path),
                 "--props-file", str(tmp_path / "p"), "--run-id", "r", "--bundle-dir", str(tmp_path),
                 "--lines-json", json.dumps({"A@B": {"spread": 1, "total": 40}})])


def test_real_worker_reads_targets_from_bundle(monkeypatch, tmp_path):
    """The real run_week reads lines/events/cutoff FROM the bundle (they appear in its read
    set) and records them in invocation.json; the solver receives the bundle's total."""
    from nfl.sim.tests.test_fwd6_item0 import _make_inputs, _run_week_capturing
    import nfl.sim.run_week as rw
    seen = {}
    input_dir, props_file = _make_inputs(tmp_path)

    class Stop(Exception):
        pass

    def fake(home, away, season, week, spread, total, anchoring_log=None, **kw):
        seen["spread"], seen["total"] = spread, total
        raise Stop()
    monkeypatch.setattr(rw, "run_anchored_chunked", fake)
    run_dir = tmp_path / "run" / "outputs"
    with pytest.raises(Stop):
        rw.main(["--week", "4", "--run-dir", str(run_dir), "--input-dir", str(input_dir),
                 "--props-file", str(props_file), "--run-id", "20261001T233000Z",
                 "--bundle-dir", str(tmp_path / "run")])
    assert seen == {"spread": 2.5, "total": 38.0}
    inv = json.loads((run_dir / "invocation.json").read_text())
    assert inv["lines"] == {"PIT@CLE": {"spread": 2.5, "total": 38.0}}
    paths = {Path(e["path"]).name for e in json.loads((run_dir / "read_set.json").read_text())["entries"]}
    assert {"lines.parquet", "events.parquet", "freshness.json"} <= paths


# ── A3: the complete record is recoverable ─────────────────────────────────────

def test_complete_run_record_restored_from_archive_alone(tmp_path):
    """Delete the run directory, the frozen opinions file, the ai_opinions manifest and
    the receipts registry; restore from the archive by run_id; verify clean, receipt
    complete, frozen bytes identical."""
    from nfl.sim.restore_run import find_receipt, restore
    from nfl.sim.run_forward_v1 import archive_root_for, receipt_status, verify_bundle, RECEIPTS_REL
    root = _build_fixture_root(tmp_path)
    dest = Path(_harness(root))
    bd = _run_dir(root)
    run_id, frozen_sha = bd.name, _sha(dest)
    shutil.rmtree(bd)
    dest.unlink()
    (dest.parent / "manifest.json").unlink()
    (root / RECEIPTS_REL).unlink()
    arch = archive_root_for(root)
    receipt, src = find_receipt(run_id, root, arch)
    assert src == "archive"
    restored, unavailable, bad = restore(root / receipt["run_dir"], arch, receipt=receipt, root=root)
    assert unavailable == [] and bad == []
    assert "bundle_manifest.json" in restored and "publication.json" in restored
    assert _sha(dest) == frozen_sha
    assert verify_bundle(bd) == []
    assert receipt_status(run_id, root) == "complete"


def test_restore_cli_by_run_id_and_pre_d262_receipt(tmp_path, monkeypatch, capsys):
    """The CLI path Jeff runs: restore_run.main(['--run-id', X]) after the run directory,
    the frozen file and the registry are deleted -> clean and complete. A receipt written
    before D262 (no run_dir) HALTs with a clear message instead of a KeyError."""
    import nfl.sim.restore_run as RR
    from nfl.sim.run_forward_v1 import archive_root_for, RECEIPTS_REL
    root = _build_fixture_root(tmp_path)
    dest = Path(_harness(root))
    bd = _run_dir(root)
    frozen_sha = _sha(dest)
    shutil.rmtree(bd)
    dest.unlink()
    (root / RECEIPTS_REL).unlink()
    monkeypatch.setattr(RR, "ROOT", root)
    RR.main(["--run-id", bd.name, "--archive", str(archive_root_for(root))])
    out = capsys.readouterr().out
    assert "verify_bundle: clean" in out and "receipt_status: complete" in out
    assert _sha(dest) == frozen_sha
    old = {"run_id": "20260927T164500Z", "bundle_digest": "0" * 64}
    (root / RECEIPTS_REL).write_text((root / RECEIPTS_REL).read_text() + json.dumps(old) + "\n")
    with pytest.raises(SystemExit, match="predates D262"):
        RR.main(["--run-id", "20260927T164500Z", "--archive", str(archive_root_for(root))])


def test_missing_manifest_alone_is_bootstrapped_from_the_receipt(tmp_path):
    from nfl.sim.restore_run import find_receipt, restore
    from nfl.sim.run_forward_v1 import archive_root_for
    root = _build_fixture_root(tmp_path)
    _harness(root)
    bd = _run_dir(root)
    (bd / "bundle_manifest.json").unlink()
    (bd / "publication.json").unlink()
    receipt, _ = find_receipt(bd.name, root, archive_root_for(root))
    restored, unavailable, bad = restore(bd, archive_root_for(root), receipt=receipt, root=root)
    assert {"bundle_manifest.json", "publication.json"} <= set(restored) and bad == []


def test_receipt_index_and_registry_are_archived(tmp_path):
    from nfl.sim.run_forward_v1 import archive_root_for, RECEIPTS_REL
    root = _build_fixture_root(tmp_path)
    dest = _harness(root)
    arch = archive_root_for(root)
    bd = _run_dir(root)
    assert (arch / "receipts" / f"{bd.name}.json").exists()
    assert (arch / "sha256" / _sha(root / RECEIPTS_REL)).exists()
    assert (arch / "sha256" / _sha(dest)).exists()
    # finalisation archived the outputs and the final manifest too
    for f in ("outputs/picks_log.parquet", "outputs/read_set.json", "bundle_manifest.json"):
        assert (arch / "sha256" / _sha(bd / f)).exists(), f


# ── A4: the event -> nflverse game mapping is frozen ───────────────────────────

def test_events_carry_the_schedule_game_id_and_schedule_is_bundled(tmp_path):
    root = _build_fixture_root(tmp_path)
    _harness(root)
    bd = _run_dir(root)
    ev = pd.read_parquet(bd / "events.parquet")
    assert ev["nflverse_game_id"].tolist() == ["2026_03_CAR_KC"]
    man = json.loads((bd / "bundle_manifest.json").read_text())
    assert "inputs/schedule.parquet" in man


def _set_schedule(root, rows):
    pd.DataFrame(rows).to_parquet(root / "nfl" / "data" / "pbp" / "schedules_2026.parquet", index=False)


def _sched_row(**over):
    r = {"game_id": "2026_03_CAR_KC", "season": 2026, "game_type": "REG", "week": 3,
         "gameday": "2099-01-01", "gametime": "12:00", "home_team": "KC", "away_team": "CAR"}
    r.update(over)
    return r


def test_no_schedule_match_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    _set_schedule(root, [_sched_row(week=4)])
    with pytest.raises(SystemExit, match="0 schedule matches"):
        _harness(root)


def test_two_schedule_matches_halt(tmp_path):
    root = _build_fixture_root(tmp_path)
    _set_schedule(root, [_sched_row(), _sched_row(game_id="dup")])
    with pytest.raises(SystemExit, match="2 schedule matches"):
        _harness(root)


def test_schedule_kickoff_mismatch_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    _set_schedule(root, [_sched_row(gametime="15:00")])
    with pytest.raises(SystemExit, match="schedule kick"):
        _harness(root)


# ── A5: freshness on the row the selector uses ─────────────────────────────────

def test_freshness_uses_the_selected_week_not_the_max(tmp_path):
    """Audit #9 A5: CLE ratings kept for weeks 1 and 5 only, target week 4: the max (5)
    passed, the selector used week 1. Here: KC ratings for weeks 1 and 9, target 3."""
    root = _build_fixture_root(tmp_path)
    f = root / "nfl" / "data" / "sim" / "ratings" / "team_ratings_weekly.parquet"
    tr = pd.read_parquet(f)
    kc = (tr.season == 2026) & (tr.team == "KC")
    keep = tr[~kc | (tr.week == 1)]
    late = tr[kc & (tr.week == 1)].assign(week=9)
    pd.concat([keep, late]).to_parquet(f, index=False)
    with pytest.raises(SystemExit, match="KC: team_ratings max week 1"):
        _harness(root)


def test_team_missing_a_rating_unit_is_not_fresh(tmp_path):
    root = _build_fixture_root(tmp_path)
    f = root / "nfl" / "data" / "sim" / "ratings" / "team_ratings_weekly.parquet"
    tr = pd.read_parquet(f)
    tr[~((tr.season == 2026) & (tr.team == "KC") & (tr.unit == "rush_def"))].to_parquet(f, index=False)
    with pytest.raises(SystemExit, match="KC: team_ratings max week -1"):
        _harness(root)


def test_stale_kicker_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    f = root / "nfl" / "data" / "sim" / "ratings" / "kicker_weekly.parquet"
    k = pd.read_parquet(f)
    k[~((k.season == 2026) & (k.team == "CAR") & (k.week >= 2))].to_parquet(f, index=False)
    with pytest.raises(SystemExit, match="CAR: kickers max week"):
        _harness(root)


def test_end_game_matching_is_case_insensitive(tmp_path):
    from nfl.sim.run_forward_v1 import _last_played_weeks
    p = tmp_path / "pbp.parquet"
    pd.DataFrame([{"game_id": "g", "week": 2, "home_team": "KC", "away_team": "CAR",
                   "desc": "End Game"}]).to_parquet(p, index=False)
    assert _last_played_weeks(p, 3) == {"KC": 2, "CAR": 2}


def test_pbp_source_hash_recorded(tmp_path):
    root = _build_fixture_root(tmp_path)
    _harness(root)
    tgc = json.loads((_run_dir(root) / "inputs" / "team_game_counts.json").read_text())
    assert tgc["source_sha256"] == _sha(root / "nfl" / "data" / "pbp" / "pbp_2026.parquet")


# ── C: read-set bypasses ───────────────────────────────────────────────────────

def _record(fn, tmp_path):
    from nfl.sim.read_set import ReadSetRecorder
    rec = ReadSetRecorder().install()
    try:
        fn()
    finally:
        rec.uninstall()
    return {Path(p).name: e for p, e in rec.entries.items()}


def test_recorded_text_reads_decode_exactly_like_open_with_utf8_mode_off(tmp_path):
    """Found by the FWD6b mutation run: with Python's UTF-8 mode OFF (a normal macOS UTF-8
    locale), Path.read_text passes encoding='locale' and the wrapper raised LookupError;
    it also skipped universal-newline translation. Runs in a child with -X utf8=0 and
    compares every recorded text read with the same read made without the recorder."""
    d = tmp_path / "data"
    d.mkdir()
    (d / "crlf.txt").write_bytes(b"a\r\nb\rc\n")
    (d / "latin.txt").write_bytes("café".encode("latin-1"))
    (d / "bad.txt").write_bytes(b"ok\xff")
    (d / "x.json").write_bytes(b'{"k": "v"}')
    code = textwrap.dedent(f"""
        import sys, json
        from pathlib import Path
        sys.path.insert(0, {str(ROOT)!r})
        assert sys.flags.utf8_mode == 0, sys.flags.utf8_mode
        from nfl.sim.read_set import ReadSetRecorder
        d = Path({str(d)!r})
        def reads():
            out = [(d / "x.json").read_text(), (d / "crlf.txt").read_text()]
            out.append(open(d / "crlf.txt").read())
            out.append(open(d / "crlf.txt", newline="").read())
            out.append(open(d / "latin.txt", encoding="latin-1").read())
            out.append(open(d / "bad.txt", "r", -1, "utf-8", "replace").read())
            out.append(json.load(open(d / "x.json")))
            return out
        plain = reads()
        rec = ReadSetRecorder().install()
        try:
            recorded = reads()
        finally:
            rec.uninstall()
        assert recorded == plain, (recorded, plain)
        names = sorted(Path(p).name for p in rec.entries)
        assert names == ["bad.txt", "crlf.txt", "latin.txt", "x.json"], names
        print("OK")
    """)
    env = {**os.environ, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    env.pop("PYTHONUTF8", None)
    r = subprocess.run([sys.executable, "-X", "utf8=0", "-c", code], capture_output=True,
                       text=True, env=env, timeout=120)
    assert r.returncode == 0 and r.stdout.strip() == "OK", r.stderr[-2000:]


def test_os_pseudo_files_excluded_on_macos_real_paths_but_data_is_not():
    """macOS resolves /etc to /private/etc; the /etc exclusion must hold there too. Data
    under /private/var/folders (the macOS temp root) and the user's home stays recorded."""
    from nfl.sim.read_set import _excluded
    for p in ("/private/etc/hosts", "/etc/hosts", "/private/var/db/timezone/zoneinfo/UTC"):
        assert _excluded(p), p
    for p in ("/private/var/folders/xy/T/inputs/team_ratings_weekly.parquet",
              "/Users/someone/mlb-model/nfl/data/pbp/pbp_2026.parquet",
              "/tmp/run/inputs/props.parquet"):
        assert not _excluded(p), p


def test_reads_through_other_apis_are_recorded(tmp_path):
    """Audit #9 (C): Path.read_text/read_bytes, io.open, os.open, 'r+', ParquetFile and a
    'site-packages-lookalike' directory all bypassed the e826a30ae recorder."""
    import pyarrow.parquet as pq
    for how in ("read_text", "read_bytes", "io_open", "os_open", "r_plus", "parquetfile",
                "lookalike_dir"):
        d = tmp_path / how / ("site-packages-lookalike" if how == "lookalike_dir" else "data")
        d.mkdir(parents=True)
        f = d / "x.parquet"
        pd.DataFrame({"v": [0.99]}).to_parquet(f, index=False)
        j = d / "x.json"
        j.write_text("{}")

        def go():
            if how == "read_text":
                j.read_text()
            elif how == "read_bytes":
                f.read_bytes()
            elif how == "io_open":
                with io.open(f, "rb") as fh:
                    fh.read()
            elif how == "os_open":
                fd = os.open(f, os.O_RDONLY)
                os.read(fd, 10)
                os.close(fd)
            elif how == "r_plus":
                with open(f, "r+b") as fh:
                    fh.read()
            elif how == "parquetfile":
                pq.ParquetFile(str(f)).read()
            else:
                with open(f, "rb") as fh:
                    fh.read()
        seen = _record(go, tmp_path)
        name = "x.json" if how == "read_text" else "x.parquet"
        assert name in seen, f"{how}: not recorded"
        # a wrapped API hands the parser the very bytes it hashed ('wrapper'); only a raw
        # os.open falls through to the audit-hook backstop, which hashes the file at open
        # time ('audit'). Kills "io.open not wrapped", which the backstop alone would mask.
        want_via = "audit" if how == "os_open" else "wrapper"
        assert seen[name]["via"] == want_via, f"{how}: recorded via {seen[name]['via']}"


def test_engine_cache_is_cleared_so_tables_are_recorded_every_run(tmp_path):
    import nfl.sim.engine as E
    from nfl.sim.read_set import route_inputs
    from nfl.sim.tests.test_fwd6_item0 import _make_inputs
    E._load_tables()
    assert E._CACHE
    input_dir, _ = _make_inputs(tmp_path)
    restore = route_inputs(input_dir)
    try:
        assert not E._CACHE
    finally:
        restore()


def test_late_imported_usage_module_is_routed(tmp_path):
    from nfl.sim.read_set import route_inputs
    from nfl.sim.tests.test_fwd6_item0 import _make_inputs
    input_dir, _ = _make_inputs(tmp_path)
    sys.modules.pop("nfl.sim.usage", None)
    restore = route_inputs(input_dir)
    try:
        import nfl.sim.usage as U
        assert Path(U.PBP_DIR).resolve() == Path(input_dir).resolve()
    finally:
        restore()


def test_output_entry_with_wrong_hash_halts(tmp_path):
    root = _build_fixture_root(tmp_path)

    def add_fake_output(run_dir, bundle_dir):
        (run_dir / "planted.json").write_text("{}")
        rs = json.loads((run_dir / "read_set.json").read_text())
        rs["entries"].append({"path": str((run_dir / "planted.json").resolve()),
                              "sha256": "0" * 64, "reads": 1})
        (run_dir / "read_set.json").write_text(json.dumps(rs))
    with pytest.raises(SystemExit, match="read an output whose bytes are not the run's"):
        _harness(root, _stub(after=add_fake_output))


def test_qb_ratings_is_a_mandatory_read():
    from nfl.sim.read_set import MUST_READ, REQUIRED_INPUTS
    assert set(REQUIRED_INPUTS) == set(MUST_READ)


def test_worker_modules_use_only_recorded_read_apis():
    """Every hashed worker module reads data only through APIs the recorder wraps (or the
    audit hook sees). A new raw read path in hashed code fails here before it can bypass
    the read set. Allowed: calibration.engine_fingerprint's Path.read_bytes (now recorded
    through io.open)."""
    import re
    banned = re.compile(r"np\.load\(|pickle\.load|pyarrow\.dataset|pa\.memory_map|"
                        r"mmap\.mmap|read_feather\(|read_pickle\(|read_hdf\(|read_excel\(")
    for f in ("run_week.py", "engine.py", "anchor.py", "calibration.py", "names.py",
              "usage.py", "seed_util.py", "tables.py", "pricer.py"):
        hits = [l for l in (ROOT / "nfl" / "sim" / f).read_text().splitlines() if banned.search(l)]
        assert not hits, f"{f}: unrecorded read API: {hits}"


# ── D: surviving mutations ─────────────────────────────────────────────────────

def test_default_archive_location(tmp_path, monkeypatch):
    from nfl.sim.run_forward_v1 import archive_root_for
    monkeypatch.delenv("NFL_FWD_ARCHIVE", raising=False)
    assert archive_root_for(tmp_path / "mlb-model") == (tmp_path / "mlb-model-archive" / "nfl_fwd_v1").resolve()
    monkeypatch.setenv("NFL_FWD_ARCHIVE", str(tmp_path / "elsewhere"))
    assert archive_root_for(tmp_path / "mlb-model") == tmp_path / "elsewhere"


def test_corrupt_archive_object_halts(tmp_path):
    from nfl.sim.run_forward_v1 import archive_file
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    h = archive_file(f, tmp_path / "arch")
    (tmp_path / "arch" / "sha256" / h).write_bytes(b"corrupt")
    with pytest.raises(SystemExit, match="corrupt"):
        archive_file(f, tmp_path / "arch")


def test_snapshot_exactly_at_cutoff_is_usable(tmp_path):
    import nfl.sim.run_forward_v1 as fwd
    d = tmp_path / "lh" / "season=2026"
    d.mkdir(parents=True)
    pd.DataFrame([{"snapshot_utc": T.isoformat(), "bookmaker": "hardrockbet_fl", "x": 1}]
                 ).to_parquet(d / "snap_a.parquet", index=False)
    saved = fwd.LINES_DIR
    fwd.LINES_DIR = tmp_path / "lh"
    try:
        assert len(fwd._load_lines_at_T(2026, T)) == 1
    finally:
        fwd.LINES_DIR = saved


def test_two_freezes_append_two_receipts_and_duplicates_mismatch(tmp_path):
    from nfl.sim.run_forward_v1 import load_receipts, receipt_status, append_receipt
    root = _build_fixture_root(tmp_path)
    _harness(root)
    from datetime import timedelta
    from nfl.sim.run_forward_v1 import main
    main(argv=["--week", "3", "--pilot", "--as-of", (T + timedelta(minutes=1)).isoformat(),
               "--allow-stale-quotes"], root=str(root), run_week_fn=_stub_run_week)
    recs = load_receipts(root)
    assert len(recs) == 2 and recs[0]["run_id"] != recs[1]["run_id"]
    append_receipt(root, recs[0])
    assert receipt_status(recs[0]["run_id"], root) == "mismatch"


def test_receipt_rows_equal_frozen_rows(tmp_path):
    from nfl.sim.run_forward_v1 import load_receipts
    root = _build_fixture_root(tmp_path)
    dest = _harness(root)
    assert load_receipts(root)[0]["rows"] == len(pd.read_parquet(dest))


def test_every_listed_bundle_file_is_verified(tmp_path):
    from nfl.sim.run_forward_v1 import verify_bundle
    root = _build_fixture_root(tmp_path)
    _harness(root)
    bd = _run_dir(root)
    man = json.loads((bd / "bundle_manifest.json").read_text())
    for rel in [k for k, v in man.items() if isinstance(v, str) and len(v) == 64]:
        f = bd / rel
        orig = f.read_bytes()
        f.write_bytes(orig + b" ")
        assert any(rel in b for b in verify_bundle(bd)), f"{rel} not verified"
        f.write_bytes(orig)


def test_anchor_miss_exactly_one_is_anchored():
    from nfl.sim.run_forward_v1 import anchor_sidecar
    ret = pd.DataFrame([{"game": "A@B", "iterations": 3, "converged": True,
                         "anch_m": 1.0, "anch_t": 41.0}])
    sc = anchor_sidecar(pd.DataFrame(), {"A@B": {"spread": 0.0, "total": 40.0}},
                        anchor_returned_df=ret)
    assert bool(sc.iloc[0]["anchored"]) is True


def test_real_default_worker_path_never_imports_shared_logger(tmp_path):
    """Audit #9 (D): importing the shared logger inside the REAL _default_run_week
    survived, because the live-path test substituted a worker. Here the real
    _default_run_week runs in a subprocess (its subprocess.run is replaced by a stub that
    writes the worker's outputs), and the shared module must stay unloaded."""
    code = textwrap.dedent(f"""
        import sys, json
        from datetime import datetime, timezone, timedelta
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from unittest.mock import patch
        from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _stub_run_week
        import nfl.sim.run_forward_v1 as fwd
        kick = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
        root = _build_fixture_root(Path({str(tmp_path)!r}), kick=kick)

        real_run = fwd.subprocess.run

        def fake_run(cmd, *args, **kw):
            # only the worker invocation is stubbed; anything else (e.g. a pytest plugin
            # shelling out while the harness runs test_freeze_v1) runs for real
            if not (isinstance(cmd, (list, tuple)) and "--bundle-dir" in cmd):
                return real_run(cmd, *args, **kw)
            a = {{cmd[i]: cmd[i + 1] for i in range(2, len(cmd) - 1) if str(cmd[i]).startswith("--")}}
            bd = Path(a["--bundle-dir"])
            lines = fwd.lines_dict_from_bundle(bd)
            _stub_run_week(root, int(a["--week"]), None, lines, sorted(lines),
                           run_dir=Path(a["--run-dir"]), input_dir=Path(a["--input-dir"]),
                           props_file=Path(a["--props-file"]), run_id=a["--run-id"], bundle_dir=bd)
            class R: returncode = 0; stdout = "ok"; stderr = ""
            return R()
        with patch.object(fwd.subprocess, "run", side_effect=fake_run):
            dest = fwd.main(argv=["--week", "3", "--window-hours", "4"], root=str(root))
        print("FROZEN", dest is not None)
        print("SHARED_LOADED", "nfl.pipeline.log_ai_opinions" in sys.modules)
    """)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert "FROZEN True" in r.stdout, r.stdout[-2000:] + r.stderr[-2000:]
    assert "SHARED_LOADED False" in r.stdout
