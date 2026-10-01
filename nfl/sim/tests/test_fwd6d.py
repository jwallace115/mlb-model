"""D266-D267 (FWD6d): ChatGPT audit #11 counterexamples and surviving mutations.

Bootstrapped processes are tested as REAL subprocesses (python3 -I -S -B
nfl/sim/fwd_bootstrap.py ...), never in-process. No parametrize (CLAUDE.md).
"""
import ast
import hashlib
import importlib.util
import io
import json
import marshal
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _set_fwd_paths, T  # noqa: E402
from nfl.sim.tests.test_fwd6b import _harness, _run_dir, _stub  # noqa: E402
from nfl.sim.tests.test_fwd6c import _recorded, _sha, _bundle  # noqa: E402

BOOT = ROOT / "nfl" / "sim" / "fwd_bootstrap.py"


def _boot(args, env=None, cwd=None, boot=BOOT):
    cmd = [sys.executable, "-I", "-S", "-B", str(boot), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd, timeout=600)


def _repo_copy(dst):
    """A minimal copy of the repository code (everything the manifest hashes under nfl/,
    plus conftest.py and the manifest) for tests that plant files."""
    dst = Path(dst)
    hashes = json.loads((ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_text())["file_hashes"]
    for rel in list(hashes) + ["research/nfl_sim/FWD_EXPERIMENT_v1.json"]:
        src = ROOT / rel
        if src.is_file() and (rel.endswith(".py") or rel.endswith(".json")):
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / rel)
    return dst


# ── A1: startup and import paths are controlled ─────────────────────────────────

def test_bootstrap_refuses_a_process_without_isolation_flags():
    r = subprocess.run([sys.executable, str(BOOT), "selftest"], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode != 0 and "python3 -I -S -B" in (r.stderr + r.stdout)


def test_hostile_startup_files_and_fake_pytest_never_run(tmp_path):
    """Audit #11 A1: a sitecustomize on PYTHONPATH rewrote the frozen probability, and a
    fake pytest on PYTHONPATH produced a passing four-test report with no tests run. A
    .pth in the user site would run at startup. In a bootstrapped process none of them
    executes, and pytest resolves to the real installation."""
    plant = tmp_path / "plant"
    plant.mkdir()
    marker = tmp_path / "MARKERS"
    marker.mkdir()
    for name in ("sitecustomize", "usercustomize", "pytest"):
        (plant / f"{name}.py").write_text(f"open({str(marker / name)!r}, 'w').write('ran')\n")
    home = tmp_path / "home"
    usersite = home / ".local" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    usersite.mkdir(parents=True)
    (usersite / "evil.pth").write_text(f"import os; open({str(marker / 'pth')!r}, 'w').write('ran')\n")
    env = {**os.environ, "PYTHONPATH": str(plant), "PYTHONSTARTUP": str(plant / "pytest.py"),
           "HOME": str(home), "PYTEST_PLUGINS": "pytest"}
    r = _boot(["selftest", "pytest"], env=env, cwd=str(plant))
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["flags_ok"] and not out["sitecustomize"] and not out["usercustomize"]
    assert str(plant) not in out["modules"]["pytest"]
    assert list(marker.iterdir()) == [], f"planted code ran: {list(marker.iterdir())}"


def test_gate_child_ignores_a_fake_pytest_on_pythonpath(tmp_path, monkeypatch):
    """The real gate (run_freeze_gate) with a fake pytest that writes a perfect report."""
    import nfl.sim.run_forward_v1 as fwd
    plant = tmp_path / "plant"
    plant.mkdir()
    marker = tmp_path / "FAKE_PYTEST_RAN"
    names = "".join(f'<testcase name="{n}"/>' for n in fwd.FREEZE_GATE_TESTS)
    (plant / "pytest.py").write_text(
        "import sys\n"
        f"open({str(marker)!r}, 'w').write('x')\n"
        "def main(args):\n"
        "    xml = [a.split('=', 1)[1] for a in args if a.startswith('--junitxml=')][0]\n"
        f"    open(xml, 'w').write('<testsuites><testsuite>{names}</testsuite></testsuites>')\n"
        "    return 0\n")
    monkeypatch.setenv("PYTHONPATH", str(plant))
    fwd.run_freeze_gate()
    assert not marker.exists()


def test_gate_halts_on_nonzero_exit_even_with_a_valid_report(tmp_path):
    """Kills audit #11 N7 (ignore a nonzero gate exit when the XML parses)."""
    import nfl.sim.run_forward_v1 as fwd
    names = "".join(f'<testcase name="{n}"/>' for n in fwd.FREEZE_GATE_TESTS)

    class R:
        returncode, stdout, stderr = 1, "", ""

    def fake(cmd, **k):
        xml = Path([c for c in cmd if str(c).endswith(".xml")][0])
        xml.write_text(f"<testsuites><testsuite>{names}</testsuite></testsuites>")
        return R()
    with patch.object(fwd.subprocess, "run", side_effect=fake):
        with pytest.raises(SystemExit, match="test_freeze_v1 failed"):
            fwd.run_freeze_gate()


def test_gate_timeout_is_600_seconds():
    """Kills audit #11 N6 (timeout 600 -> 36000)."""
    import nfl.sim.run_forward_v1 as fwd
    seen = {}

    def fake(cmd, **k):
        seen.update(k)
        raise subprocess.TimeoutExpired(cmd, k["timeout"])
    with patch.object(fwd.subprocess, "run", side_effect=fake):
        with pytest.raises(subprocess.TimeoutExpired):
            fwd.run_freeze_gate()
    assert seen["timeout"] == 600 == fwd.GATE_TIMEOUT_S


def test_gate_report_rejects_a_duplicated_test_name():
    """Kills audit #11 N5 (deduplicate names before comparing)."""
    from nfl.sim.run_forward_v1 import check_gate_report, FREEZE_GATE_TESTS
    cases = list(FREEZE_GATE_TESTS) + [FREEZE_GATE_TESTS[0]]
    xml = "<testsuites><testsuite>" + "".join(f'<testcase name="{n}"/>' for n in cases) + \
        "</testsuite></testsuites>"
    with pytest.raises(SystemExit, match="freeze gate did not pass"):
        check_gate_report(xml)


def test_primary_freeze_requires_the_bootstrap(tmp_path, monkeypatch):
    """A live freeze in a process not started through fwd_bootstrap HALTs before anything
    is built; a pilot does not need it (and records runtime None)."""
    import nfl.sim.run_forward_v1 as fwd
    from datetime import datetime, timedelta, timezone
    from nfl.sim.tests.test_fwd3_item0 import _stub_run_week
    monkeypatch.setattr(fwd, "REQUIRE_LAUNCHER", True)
    kick = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
    root = _build_fixture_root(tmp_path / "live", kick=kick)
    with pytest.raises(SystemExit, match="must be launched as"):
        fwd.main(argv=["--week", "3", "--window-hours", "4"], root=str(root),
                 run_week_fn=_stub_run_week)
    assert not (root / "nfl" / "data" / "board" / "week=2026_03").exists()
    root2 = _build_fixture_root(tmp_path / "pilot")
    _harness(root2)
    rec = fwd.load_receipts(root2)
    assert rec[0]["pilot"] is True and rec[0]["runtime"] is None


def test_worker_is_started_through_the_bootstrap(tmp_path):
    import nfl.sim.run_forward_v1 as fwd
    seen = {}

    class R:
        returncode, stdout, stderr = 0, "", ""

    def fake(cmd, **k):
        seen["cmd"] = cmd
        return R()
    with patch.object(fwd.subprocess, "run", side_effect=fake):
        fwd._default_run_week(tmp_path, 4, T, {}, [], run_dir=tmp_path / "o",
                              input_dir=tmp_path, props_file=tmp_path / "p", run_id="r",
                              bundle_dir=tmp_path)
    c = seen["cmd"]
    assert c[1:4] == ["-I", "-S", "-B"] and c[4].endswith("fwd_bootstrap.py") and c[5] == "worker"


def test_bootstrapped_worker_reads_only_wrapper_bytes(tmp_path):
    """The real worker in a FRESH bootstrapped process (kills audit #11 N1: an import the
    allow-list misses shows up as an unproven read here, not hidden by a warm process)."""
    from nfl.sim.fwd_bootstrap import child_cmd
    from nfl.sim.read_set import classify_read_set
    from nfl.sim.tests.test_fwd6_item0 import _make_inputs
    input_dir, props_file = _make_inputs(tmp_path)
    bundle = tmp_path / "run"
    run_dir = bundle / "outputs"
    r = subprocess.run(child_cmd("worker", "--week", 4, "--run-dir", run_dir, "--input-dir",
                                 input_dir, "--props-file", props_file, "--run-id",
                                 "20261001T233000Z", "--bundle-dir", bundle),
                       capture_output=True, text=True, cwd=str(ROOT), timeout=1200)
    assert r.returncode == 0, r.stderr[-3000:]
    rs = json.loads((run_dir / "read_set.json").read_text())
    assert rs["violations"] == [] and rs["network_attempts"] == [] and rs["conflicts"] == []
    assert all(e["via"] == ["wrapper"] for e in rs["entries"]), \
        [e for e in rs["entries"] if e["via"] != ["wrapper"]]
    man = {str(p.relative_to(bundle)): _sha(p) for p in bundle.rglob("*") if p.is_file()}
    hashes = json.loads((ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_text())["file_hashes"]
    classify_read_set(rs, bundle, ROOT, hashes, man)


# ── A2: executed repository code is the hashed source ───────────────────────────

def test_doctored_bytecode_is_never_executed(tmp_path):
    """Audit #11 A2: a timestamp-valid .pyc with altered code was executed although the
    source hash matched. Plain python3 loads it (the control); the bootstrap never does."""
    repo = _repo_copy(tmp_path / "repo")
    src = repo / "nfl" / "sim" / "seed_util.py"
    st = src.stat()
    planted = compile(src.read_text() + "\nPLANTED = 1\n", str(src), "exec")
    import importlib._bootstrap_external as be
    pyc = Path(importlib.util.cache_from_source(str(src)))
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(be._code_to_timestamp_pyc(planted, int(st.st_mtime), st.st_size))
    ctl = subprocess.run([sys.executable, "-c",
                          "import nfl.sim.seed_util as m; print(getattr(m, 'PLANTED', None))"],
                         capture_output=True, text=True, cwd=str(repo), timeout=120)
    assert ctl.stdout.strip() == "1", "control: plain python should load the planted .pyc"
    r = _boot(["selftest", "nfl.sim.seed_util"], boot=repo / "nfl" / "sim" / "fwd_bootstrap.py",
              cwd=str(repo))
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["markers"]["nfl.sim.seed_util"] is None


def test_unlisted_or_modified_repository_module_cannot_run(tmp_path):
    repo = _repo_copy(tmp_path / "repo")
    boot = repo / "nfl" / "sim" / "fwd_bootstrap.py"
    (repo / "nfl" / "sim" / "rogue.py").write_text("X = 1\n")
    r = _boot(["selftest", "nfl.sim.rogue"], boot=boot, cwd=str(repo))
    assert r.returncode != 0 and "not in the experiment manifest" in r.stderr
    f = repo / "nfl" / "sim" / "seed_util.py"
    f.write_text(f.read_text() + "\n# changed\n")
    r = _boot(["selftest", "nfl.sim.seed_util"], boot=boot, cwd=str(repo))
    assert r.returncode != 0 and "differs from the experiment manifest" in r.stderr
    boot.write_text(boot.read_text() + "\n# changed\n")
    r = _boot(["selftest"], boot=boot, cwd=str(repo))
    assert r.returncode != 0 and "fwd_bootstrap.py differs" in (r.stderr + r.stdout)


def test_loaded_module_verification_rejects_unrecorded_and_altered_files(tmp_path, monkeypatch):
    import types
    import nfl.sim.fwd_bootstrap as FB
    import site
    monkeypatch.setattr(FB, "ACTIVE", True)
    std = {str(Path(p).resolve()) + os.sep for p in sys.path if p and "packages" not in p}
    trusted = [str(Path(p).resolve()) for p in site.getsitepackages() + [site.getusersitepackages()]
               if os.path.isdir(p)]
    monkeypatch.setitem(FB._STATE, "stdlib", sorted(std))
    monkeypatch.setitem(FB._STATE, "trusted_paths", trusted)
    # every repository module currently loaded must have come through the verifier:
    # in this (pytest) process none did, so they are reported
    with pytest.raises(SystemExit, match="did not load through the verifier"):
        FB.verify_loaded_modules()
    monkeypatch.setitem(FB._STATE, "verified",
                        {str(Path(m.__file__).resolve()): "x" for m in list(sys.modules.values())
                         if getattr(m, "__file__", None) and ROOT in Path(m.__file__).resolve().parents})
    f = tmp_path / "stray.py"
    f.write_text("X = 1\n")
    stray = types.ModuleType("stray_mod")
    stray.__file__ = str(f)
    monkeypatch.setitem(sys.modules, "stray_mod", stray)
    with pytest.raises(SystemExit, match="neither standard library nor in a distribution RECORD"):
        FB.verify_loaded_modules()
    monkeypatch.delitem(sys.modules, "stray_mod")
    real = FB._record_index
    pd_file = str(Path(pd.__file__).resolve())
    monkeypatch.setattr(FB, "_record_index", lambda paths: {**real(paths), pd_file: "0" * 64})
    with pytest.raises(SystemExit, match="differs from its distribution RECORD"):
        FB.verify_loaded_modules()


def test_hashed_code_paths_is_exactly_the_manifest_py_set():
    """Kills audit #11 N1 (omit a module from the allow-list)."""
    from nfl.sim.read_set import hashed_code_paths
    hashes = json.loads((ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_text())["file_hashes"]
    want = {str((ROOT / r).resolve()) for r in hashes if r.endswith(".py")}
    assert hashed_code_paths(ROOT) == want and str((ROOT / "nfl/sim/usage.py").resolve()) in want


def test_repository_bytecode_is_data_not_code(tmp_path):
    """D266 retires the .pyc -> source mapping (audit #11 N2): a .pyc is never code."""
    from nfl.sim.read_set import _code_source
    assert _code_source("/x/nfl/sim/__pycache__/usage.cpython-313.pyc") is None
    assert _code_source("/x/nfl/sim/usage.py") == "/x/nfl/sim/usage.py"


# ── A3: native sources are refused in every argument form ───────────────────────

def test_uri_bytes_and_keyword_sources_are_refused(tmp_path):
    """Audit #11 A3: dataset(file URI), memory_map(bytes path) and ParquetFile(URI)
    returned data with no entry and no violation."""
    import pyarrow as pa
    import pyarrow.dataset as pads
    import pyarrow.parquet as pq
    f = tmp_path / "x.parquet"
    pd.DataFrame({"v": [0.99]}).to_parquet(f, index=False)
    t = tmp_path / "x.txt"
    t.write_bytes(b"0.10")
    cases = {
        "dataset uri": lambda: pads.dataset(f.as_uri()).to_table(),
        "dataset kw": lambda: pads.dataset(source=str(f)).to_table(),
        "memory_map bytes": lambda: pa.memory_map(os.fsencode(str(t))).read(),
        "memory_map kw": lambda: pa.memory_map(path=str(t)).read(),
        "ParquetFile uri": lambda: pq.ParquetFile(f.as_uri()).read(),
        "ParquetFile kw uri": lambda: pq.ParquetFile(source=f.as_uri()).read(),
        "read_parquet uri": lambda: pd.read_parquet(f.as_uri()),
        "read_table kw uri": lambda: pq.read_table(source=f.as_uri()),
        "read_parquet missing": lambda: pd.read_parquet(str(tmp_path / "nope.parquet")),
    }
    for name, go in cases.items():
        rec, err = _recorded(go)
        assert isinstance(err, PermissionError), f"{name}: not refused ({err!r})"
        assert rec.violations, name
    # a bytes path to a WRAPPED reader is normalised into the byte-serving path instead:
    # served from recorded bytes, hash equal to the file's
    served = {"ParquetFile bytes": lambda: pq.ParquetFile(os.fsencode(str(f))).read(),
              "read_table bytes": lambda: pq.read_table(os.fsencode(str(f))),
              "read_parquet kw": lambda: pd.read_parquet(path=str(f))}
    for name, go in served.items():
        rec, err = _recorded(go)
        assert err is None, f"{name}: {err!r}"
        e = rec.entries[str(f.resolve())]
        assert e["via"] == {"wrapper"} and e["sha256"] == _sha(f) and not rec.violations, name


def test_native_filesystem_and_handles_are_refused(tmp_path):
    import pyarrow.fs as pafs
    import pyarrow.parquet as pq
    f = tmp_path / "x.parquet"
    pd.DataFrame({"v": [0.99]}).to_parquet(f, index=False)
    handle = pafs.LocalFileSystem().open_input_file(str(f))     # opened before recording
    cases = {
        "LocalFileSystem.open_input_file": lambda: pafs.LocalFileSystem().open_input_file(str(f)).read(),
        "LocalFileSystem.open_input_stream": lambda: pafs.LocalFileSystem().open_input_stream(str(f)).read(),
        "FileSystem.from_uri": lambda: pafs.FileSystem.from_uri(f.as_uri()),
        "read_parquet(native handle)": lambda: pd.read_parquet(handle),
        "ParquetFile(native handle)": lambda: pq.ParquetFile(handle).read(),
    }
    for name, go in cases.items():
        rec, err = _recorded(go)
        assert isinstance(err, PermissionError), f"{name}: not refused ({err!r})"
        assert rec.violations, name
    # restored afterwards
    assert pafs.LocalFileSystem().open_input_file(str(f)).read()


def test_a_swallowed_refusal_still_fails_the_proof(tmp_path):
    """Audit #11: a hidden dataset read inside an otherwise complete read set passed
    classification. A refusal caught by the caller still leaves a persisted violation."""
    import pyarrow.dataset as pads
    from nfl.sim.read_set import classify_read_set
    f = tmp_path / "x.parquet"
    pd.DataFrame({"v": [0.99]}).to_parquet(f, index=False)

    def go():
        try:
            pads.dataset(f.as_uri()).to_table()
        except PermissionError:
            pass
    rec, err = _recorded(go)
    assert err is None
    doc = rec.write(tmp_path / "rs.json")
    with pytest.raises(SystemExit, match="forbidden reads"):
        classify_read_set(doc, tmp_path / "b", tmp_path, {}, {})


def test_update_mode_os_open_is_refused_at_the_open(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"0.10")

    def go():
        fd = os.open(f, os.O_RDWR)
        os.write(fd, b"0.99")
        os.close(fd)
    rec, err = _recorded(go)
    assert isinstance(err, PermissionError) and f.read_bytes() == b"0.10" and rec.violations


def test_every_read_mechanism_is_kept(tmp_path):
    """Kills audit #11 N3: wrapper then raw FileIO of identical bytes must be 'audit' too."""
    from nfl.sim.read_set import classify_read_set
    f = tmp_path / "x.json"
    f.write_text("{}")

    def go():
        f.read_text()
        with io.FileIO(str(f), "r") as fh:
            fh.read()
    rec, _ = _recorded(go)
    assert rec.entries[str(f.resolve())]["via"] == {"wrapper", "audit"}
    with pytest.raises(SystemExit, match="not byte-bound"):
        classify_read_set(rec.write(tmp_path / "rs.json"), tmp_path / "b", tmp_path, {}, {})


def test_hashed_code_calls_no_unrecordable_reader():
    """AST scan of EVERY hashed module (read_set.py and fwd_bootstrap.py included): no call
    to a native/unrecordable reader, no dynamic code. Two documented exceptions: the
    bootstrap compiles and execs verified source; read_set reflects over the APIs it
    guards (getattr/setattr)."""
    banned_attr = {"memory_map", "input_stream", "OSFile", "open_input_file",
                   "open_input_stream", "from_uri", "ParquetDataset", "fromfile", "memmap",
                   "mmap", "FileIO", "read_feather", "read_orc", "read_pickle", "read_hdf",
                   "read_excel", "import_module", "dataset"}
    banned_name = {"exec", "eval", "compile", "__import__"}
    allow = {"nfl/sim/fwd_bootstrap.py": {"exec", "compile", "__import__"}}
    hashes = json.loads((ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_text())["file_hashes"]
    checked, hits = 0, []
    for rel in hashes:
        if not rel.endswith(".py") or "/tests/" in rel:
            continue
        tree = ast.parse((ROOT / rel).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and \
                    fn.value.id in ("os", "np", "pickle") and fn.attr in ("open", "load", "loads"):
                hits.append(f"{rel}:{node.lineno} {fn.value.id}.{fn.attr}")
            elif name in banned_attr or (isinstance(fn, ast.Name) and name in banned_name
                                         and name not in allow.get(rel, ())):
                hits.append(f"{rel}:{node.lineno} {name}")
            elif name in ("getattr", "setattr") and rel != "nfl/sim/read_set.py" and \
                    len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
                hits.append(f"{rel}:{node.lineno} dynamic {name}")
        checked += 1
    assert not hits, hits
    assert checked >= 15


# ── old (audit #10) survivors ───────────────────────────────────────────────────

def test_user_site_is_an_installation_prefix():
    import site
    from nfl.sim.read_set import _PREFIXES
    assert str(Path(site.getusersitepackages()).resolve()) + os.sep in _PREFIXES


def test_csv_parsed_while_recording_is_complete(tmp_path):
    """Kills the 'wrapped CSV reader drops its first row' operator: the frame parsed
    UNDER the recorder is compared, not a fresh read afterwards."""
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n3,4\n")
    got = {}
    rec, err = _recorded(lambda: got.setdefault("df", pd.read_csv(f)))
    assert err is None and got["df"].to_dict("list") == {"a": [1, 3], "b": [2, 4]}


def test_restore_hashes_whole_large_objects(tmp_path):
    from nfl.sim.restore_run import _sha, _from_archive
    big = tmp_path / "big.bin"
    big.write_bytes(os.urandom(17 * 1024 * 1024))
    h = hashlib.sha256(big.read_bytes()).hexdigest()
    assert _sha(big) == h
    (tmp_path / "sha256").mkdir()
    data = bytearray(big.read_bytes())
    data[-1] ^= 1                                    # tail changed beyond 16 MiB
    (tmp_path / "sha256" / h).write_bytes(bytes(data))
    restored, unavailable = [], []
    _from_archive(tmp_path, h, tmp_path / "out" / "big", restored, unavailable, "big")
    assert unavailable == ["big (archive copy corrupt)"] and not (tmp_path / "out" / "big").exists()


def test_find_receipt_refuses_duplicates(tmp_path):
    from nfl.sim.restore_run import find_receipt
    from nfl.sim.run_forward_v1 import RECEIPTS_REL
    reg = tmp_path / RECEIPTS_REL
    reg.parent.mkdir(parents=True)
    line = json.dumps({"run_id": "R"}) + "\n"
    reg.write_text(line + line)
    with pytest.raises(SystemExit, match="2 receipts for run R in the registry"):
        find_receipt("R", tmp_path, tmp_path / "archive")


def test_restore_cli_reports_status_mismatch(tmp_path, monkeypatch, capsys):
    """Kills 'CLI assumes complete': a frozen file changed after publication -> the run
    directory verifies clean but receipt_status is 'mismatch', and the CLI exits 1."""
    import nfl.sim.restore_run as RR
    from nfl.sim.run_forward_v1 import archive_root_for
    root = _build_fixture_root(tmp_path)
    dest = Path(_harness(root))
    dest.write_bytes(dest.read_bytes() + b"tamper")
    monkeypatch.setattr(RR, "ROOT", root)
    with pytest.raises(SystemExit) as ex:
        RR.main(["--run-id", _run_dir(root).name, "--archive", str(archive_root_for(root))])
    out = capsys.readouterr().out
    assert ex.value.code == 1 and "verify_bundle: clean" in out and "receipt_status: mismatch" in out


def test_receipt_status_checks_the_opinions_manifest_entry(tmp_path):
    from nfl.sim.run_forward_v1 import receipt_status
    root = _build_fixture_root(tmp_path)
    dest = Path(_harness(root))
    rid = _run_dir(root).name
    assert receipt_status(rid, root) == "complete"
    om = dest.parent / "manifest.json"
    entries = json.loads(om.read_text())
    for e in entries:
        if e["file"] == dest.name:
            e["sha256"] = "0" * 64
    om.write_text(json.dumps(entries, indent=1) + "\n")
    assert receipt_status(rid, root) == "mismatch"


# ── new (audit #11) survivors ───────────────────────────────────────────────────

def test_claimed_cutoff_same_day_other_time_halts(tmp_path):
    """Kills audit #11 N8 (compare dates only)."""
    root = _build_fixture_root(tmp_path)

    def edit(run_dir, bundle_dir):
        inv = json.loads((run_dir / "invocation.json").read_text())
        inv["cutoff_T"] = T.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        assert inv["cutoff_T"] != T.isoformat()
        (run_dir / "invocation.json").write_text(json.dumps(inv))
    with pytest.raises(SystemExit, match="claims cutoff"):
        _harness(root, _stub(after=edit))


def test_claimed_bundle_with_same_basename_halts(tmp_path):
    """Kills audit #11 N9 (compare basenames only)."""
    root = _build_fixture_root(tmp_path)

    def edit(run_dir, bundle_dir):
        inv = json.loads((run_dir / "invocation.json").read_text())
        inv["bundle_dir"] = str(Path("/elsewhere") / bundle_dir.name)
        (run_dir / "invocation.json").write_text(json.dumps(inv))
    with pytest.raises(SystemExit, match="ran against bundle"):
        _harness(root, _stub(after=edit))


def test_last_played_weeks_come_from_the_snapshot(tmp_path, monkeypatch):
    """Kills audit #11 N10: the shared refresh CHANGES KC/CAR's last played week (their
    week-2 game becomes week 1; another pair keeps week 2 so the global guard passes)."""
    import nfl.sim.run_week as rw
    root = _build_fixture_root(tmp_path)
    shared = root / "nfl" / "data" / "pbp" / "pbp_2026.parquet"
    real = rw.count_team_completed_games

    def refresh_then_count(season, pbp_path=None):
        df = pd.read_parquet(shared)
        moved = df.copy()
        moved["week"] = 1
        moved["game_id"] = moved["game_id"].str.replace("_02_", "_01_")
        other = df.copy()
        other["home_team"], other["away_team"] = "PIT", "CLE"
        other["game_id"] = "2026_02_CLE_PIT"
        pd.concat([moved, other]).to_parquet(shared, index=False)
        return real(season, pbp_path=pbp_path)
    monkeypatch.setattr(rw, "count_team_completed_games", refresh_then_count)
    bd, _ = _bundle(root)
    tgc = json.loads((bd / "inputs" / "team_game_counts.json").read_text())
    assert {k: int(v) for k, v in tgc["last_played_week"].items()} == {"KC": 2, "CAR": 2}
