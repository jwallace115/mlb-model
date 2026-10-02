"""D270 (FWD6f): ChatGPT audit #13 A1 (dependency-drift rule as one predicate), the
launcher hash, and audit #13's six focused-suite survivors. No parametrize (CLAUDE.md).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd6c import _recorded  # noqa: E402

BOOT = ROOT / "nfl" / "sim" / "fwd_bootstrap.py"


def _ident(version="2.3.3", location="/sp", record="a" * 64):
    return {"version": version, "location": location, "record_sha256": record}


def _rt(dists, python="3.13.1", exe="/fw/python3"):
    return {"python": python, "executable": exe, "dependency_distributions": dists}


def _run(**kw):
    """A run's three runtimes (D272 requires all three keys); unspecified ones are clean."""
    out = {k: _rt({}) for k in ("runtime", "runtime_before_freeze", "runtime_worker")}
    out.update(kw)
    return out


# ── A1: the drift rule ─────────────────────────────────────────────────────────

def test_drift_rule_rejects_a_distribution_not_in_the_baseline():
    """Audit #13 A1 counterexample: all 12 baseline identities equal, but an extra
    distribution (bottleneck, from a temporary user site) loaded. That is drift."""
    from nfl.sim.run_forward_v1 import dependency_drift
    base = [_rt({"pandas": _ident(), "numpy": _ident("2.4.3")}),
            _rt({"pandas": _ident(), "numpy": _ident("2.4.3")}),
            _rt({"pandas": _ident(), "scipy": _ident("1.17.1")})]
    same = _run(runtime=_rt({"pandas": _ident()}), runtime_worker=_rt({"scipy": _ident("1.17.1")}))
    assert dependency_drift(base, same) == []          # the baseline is the UNION
    extra = _run(runtime_worker=_rt({"pandas": _ident(), "bottleneck": _ident("0.0.0", "/home/x")}))
    d = dependency_drift(base, extra)
    assert d and "bottleneck" in d[0] and "not in the baseline" in d[0]


def test_drift_rule_rejects_version_location_record_and_interpreter_changes():
    from nfl.sim.run_forward_v1 import dependency_drift
    base = [_rt({"pandas": _ident()})] * 3
    for changed in (_ident(version="2.3.4"), _ident(location="/home/u/site"), _ident(record="b" * 64)):
        assert dependency_drift(base, _run(runtime=_rt({"pandas": changed}))), changed
    assert dependency_drift(base, _run(runtime=_rt({"pandas": _ident()}, exe="/other/python3")))
    assert dependency_drift(base, _run(runtime=_rt({"pandas": _ident()}, python="3.13.2")))
    assert dependency_drift(base, _run(runtime=None)) == ["runtime: no verified runtime"]
    assert dependency_drift(base, _run()) == []


def test_drift_rule_requires_all_three_runtimes_on_both_sides():
    """Audit #14: an empty or partial mapping returned [] — a missing KEY is drift; and a
    baseline missing one runtime (survivor: the 'baseline: a runtime is missing' branch)."""
    from nfl.sim.run_forward_v1 import dependency_drift
    base = [_rt({"pandas": _ident()})] * 3
    assert dependency_drift(base, {}) and all("missing from the run" in p for p in dependency_drift(base, {}))
    partial = _run()
    del partial["runtime_worker"]
    assert dependency_drift(base, partial) == ["runtime_worker: missing from the run's runtimes"]
    assert "baseline: a runtime is missing" in dependency_drift([base[0], None, base[2]], _run())
    assert dependency_drift(base[:2], _run()) == ["baseline: 2 runtimes, need 3"]


def test_the_baseline_is_the_first_primary_in_the_registry(tmp_path):
    """Survivor: choosing the LAST primary receipt. Three primaries: both later ones point
    at the first, and the drift is measured against the first's identity."""
    from nfl.sim.run_forward_v1 import dependency_fields, append_receipt
    import json as _json
    first = {"run_id": "R1", "pilot": False, **_run(runtime=_rt({"pandas": _ident()}))}
    pilot = {"run_id": "P0", "pilot": True, **_run(runtime=_rt({"pandas": _ident("0.1")}))}
    second = {"run_id": "R2", "pilot": False, **_run(runtime=_rt({"pandas": _ident("2.3.4")}))}
    append_receipt(tmp_path, pilot)
    assert dependency_fields(tmp_path, first)["dependency_baseline_run_id"] == "R1"
    append_receipt(tmp_path, first)
    f2 = dependency_fields(tmp_path, second)
    assert f2["dependency_baseline_run_id"] == "R1" and f2["dependency_drift"]
    append_receipt(tmp_path, second)
    third = {"run_id": "R3", "pilot": False, **_run(runtime=_rt({"pandas": _ident()}))}
    f3 = dependency_fields(tmp_path, third)
    assert f3 == {"dependency_baseline_run_id": "R1", "dependency_drift": []}


def test_drift_baseline_must_be_self_consistent():
    from nfl.sim.run_forward_v1 import dependency_drift
    bad = [_rt({"pandas": _ident()}), _rt({"pandas": _ident("9")}), _rt({})]
    assert any("differs between its own runtimes" in p for p in dependency_drift(bad, _run()))
    two = [_rt({}), _rt({}, exe="/b"), _rt({})]
    assert any("2 interpreters" in p for p in dependency_drift(two, _run()))


# ── the launcher is in repo_modules ────────────────────────────────────────────

def test_launcher_full_hash_is_in_repo_modules():
    r = subprocess.run([sys.executable, "-I", "-S", "-B", str(BOOT), "selftest", "json"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    rt = json.loads(r.stdout.strip().splitlines()[-1])["runtime"]
    assert rt["repo_modules"]["nfl/sim/fwd_bootstrap.py"] == hashlib.sha256(BOOT.read_bytes()).hexdigest()


# ── audit #13 survivors ────────────────────────────────────────────────────────

def test_hash_cache_sees_a_same_size_same_inode_rewrite(tmp_path):
    """Survivor: mtime dropped from the cache key."""
    from nfl.sim.fwd_bootstrap import _sha256_file
    f = tmp_path / "lib.so"
    f.write_bytes(b"AAAA")
    ino = f.stat().st_ino
    first = _sha256_file(str(f))
    with open(f, "r+b") as fh:
        fh.write(b"BBBB")
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert f.stat().st_ino == ino and f.stat().st_size == 4
    assert _sha256_file(str(f)) == hashlib.sha256(b"BBBB").hexdigest() != first


def test_worker_with_same_version_but_other_executable_halts(tmp_path, monkeypatch):
    """Survivor: the executable comparison removed (the old test changed the version)."""
    import nfl.sim.fwd_bootstrap as FB
    from nfl.sim.run_forward_v1 import check_worker_runtime
    pd_ident = _ident()
    mine = {"python": "3.13.1", "executable": "/fw/python3",
            "dependency_distributions": {"pandas": pd_ident}}
    monkeypatch.setattr(FB, "ACTIVE", True)
    monkeypatch.setattr(FB, "verify_loaded_modules", lambda: mine)
    good = {"flags": "-I -S -B", "pycache_prefix_fresh": True, "n_repo_modules": 12,
            "n_dependency_files": 400, "python": "3.13.1", "executable": "/fw/python3",
            "dependency_distributions": {"pandas": dict(pd_ident)}}
    f = tmp_path / "runtime_worker.json"
    f.write_text(json.dumps({**good, "executable": "/usr/local/bin/python3"}))
    with pytest.raises(SystemExit, match="different interpreter"):
        check_worker_runtime(tmp_path)
    # Survivor: compare only the RECORD hash — version-only and location-only changes
    for changed in (_ident(version="2.3.4"), _ident(location="/home/u/site")):
        f.write_text(json.dumps({**good, "dependency_distributions": {"pandas": changed}}))
        with pytest.raises(SystemExit, match="dependency pandas differs"):
            check_worker_runtime(tmp_path)


def test_filesystem_classes_are_restored_after_uninstall_even_on_error():
    """Survivor: FileSystem not restored."""
    import pyarrow.fs as pafs
    lfs, fs = pafs.LocalFileSystem, pafs.FileSystem

    def boom():
        raise RuntimeError("inside the recorder")
    rec, err = _recorded(boom)
    assert isinstance(err, RuntimeError)
    assert pafs.LocalFileSystem is lfs and pafs.FileSystem is fs
    rec, err = _recorded(lambda: None)
    assert err is None and pafs.LocalFileSystem is lfs and pafs.FileSystem is fs


def test_non_file_uri_schemes_get_the_uri_refusal():
    """Survivor: only file: URIs recognised. No network is reached: the refusal comes first."""
    import pyarrow.parquet as pq
    for go in (lambda: pq.ParquetFile("s3://bucket/x.parquet").read(),
               lambda: pd.read_parquet("https://example.invalid/x.parquet"),
               lambda: pq.read_table(source="hdfs://namenode/x.parquet"),
               lambda: pq.ParquetFile("gs://bucket/x.parquet").read()):
        rec, err = _recorded(go)
        assert isinstance(err, PermissionError) and "URI sources are refused" in str(err), repr(err)
        assert rec.violations


def test_pathlike_source_to_a_native_reader_is_refused(tmp_path):
    """Survivor: PathLike normalisation removed (the mutant raised TypeError, no violation)."""
    import pyarrow as pa
    t = tmp_path / "x.txt"
    t.write_bytes(b"0.10")
    rec, err = _recorded(lambda: pa.memory_map(t).read())
    assert isinstance(err, PermissionError) and rec.violations, repr(err)
