"""D269 (FWD6e): ChatGPT audit #12 surviving mutations and limits L1/L3/L4.

Bootstrapped processes are tested as REAL subprocesses. No parametrize (CLAUDE.md).
"""
import hashlib
import json
import os
import site
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd6c import _recorded  # noqa: E402

BOOT = ROOT / "nfl" / "sim" / "fwd_bootstrap.py"


def _boot(args, env=None):
    return subprocess.run([sys.executable, "-I", "-S", "-B", str(BOOT), *args],
                          capture_output=True, text=True, env=env, timeout=600)


def _in_process_verifier(monkeypatch):
    """Put fwd_bootstrap's verifier in a state equivalent to a bootstrapped process for
    the modules this pytest process has loaded (set aside site-loaded, unrecorded ones)."""
    import nfl.sim.fwd_bootstrap as FB
    monkeypatch.setattr(FB, "ACTIVE", True)
    std = {str(Path(p).resolve()) + os.sep for p in sys.path if p and "packages" not in p}
    trusted = [str(Path(p).resolve()) for p in site.getsitepackages() + [site.getusersitepackages()]
               if os.path.isdir(p)]
    monkeypatch.setitem(FB._STATE, "stdlib", sorted(std))
    monkeypatch.setitem(FB._STATE, "trusted_paths", trusted)
    repo = {}
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if f and ROOT in Path(f).resolve().parents:
            repo[str(Path(f).resolve())] = hashlib.sha256(Path(f).read_bytes()).hexdigest()
    monkeypatch.setitem(FB._STATE, "verified", repo)
    recorded = FB._record_index(trusted)
    for name, m in list(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if not f:
            continue
        rf = str(Path(f).resolve())
        if rf in recorded or ROOT in Path(rf).parents:
            continue
        if rf.startswith(tuple(std)) and not {"site-packages", "dist-packages"} & set(Path(rf).parts):
            continue
        monkeypatch.delitem(sys.modules, name)
    return FB, trusted, recorded


def test_runtime_pins_full_repo_hashes_and_dependency_identity():
    """Audit #12 D survivor (repository hashes recorded as zeros) and L1/L3: the receipt's
    runtime carries the FULL sha256 of every repository module compiled, recomputable from
    the files, and the identity (version, location, RECORD sha256) of every loaded
    dependency distribution."""
    r = _boot(["selftest", "pandas", "pyarrow.parquet", "nfl.sim.run_week"])
    assert r.returncode == 0, r.stderr[-3000:]
    rt = json.loads(r.stdout.strip().splitlines()[-1])["runtime"]
    assert rt["n_repo_modules"] == len(rt["repo_modules"]) > 0
    for rel, h in rt["repo_modules"].items():
        assert len(h) == 64 and h == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), rel
    assert "nfl/sim/run_week.py" in rt["repo_modules"]
    dd = rt["dependency_distributions"]
    assert "pandas" in dd and "pyarrow" in dd and "numpy" in dd
    for name, ident in dd.items():
        assert len(ident["record_sha256"]) == 64 and ident["version"], name
        loc = Path(ident["location"])
        rec = [p for p in loc.glob("*.dist-info/RECORD")
               if p.parent.name.lower().replace("_", "-").startswith(name.replace("_", "-") + "-")]
        assert any(hashlib.sha256(p.read_text().encode()).hexdigest() == ident["record_sha256"]
                   for p in rec), name
    assert rt["dependency_identity_sha256"] == hashlib.sha256(
        json.dumps(dd, sort_keys=True).encode()).hexdigest()
    assert rt["n_distribution_files_verified"] > rt["n_dependency_files"]


def test_native_extension_module_mismatch_halts(monkeypatch):
    """Audit #12 D survivor: skipping .so/.dylib files in verification must fail a test."""
    import numpy  # noqa: F401  (loads compiled extension modules)
    FB, trusted, recorded = _in_process_verifier(monkeypatch)
    ext = sorted(str(Path(m.__file__).resolve()) for m in list(sys.modules.values())
                 if getattr(m, "__file__", None)
                 and str(m.__file__).endswith((".so", ".dylib", ".pyd"))
                 and str(Path(m.__file__).resolve()) in recorded)
    assert ext, "no compiled extension module loaded from a recorded distribution"
    FB.verify_loaded_modules()
    real = FB._record_index
    monkeypatch.setattr(FB, "_record_index", lambda paths: {**real(paths), ext[0]: "0" * 64})
    with pytest.raises(SystemExit, match="differs from its distribution RECORD"):
        FB.verify_loaded_modules()


def test_every_file_of_a_loaded_distribution_is_verified(monkeypatch):
    """D269 (audit #12 L4): a shared library or data file of a loaded distribution that is
    no module's __file__ (e.g. a vendored .dylib loaded by the dynamic linker) must match
    RECORD, and a RECORD-listed file that is missing HALTs."""
    import pyarrow.parquet  # noqa: F401
    FB, trusted, recorded = _in_process_verifier(monkeypatch)
    module_files = {str(Path(m.__file__).resolve()) for m in list(sys.modules.values())
                    if getattr(m, "__file__", None)}
    owners, dists = FB._dist_index(trusted)
    pa_key = owners[str(Path(sys.modules["pyarrow"].__file__).resolve())]
    others = [f for f in dists[pa_key]["files"] if f not in module_files and f in recorded]
    assert others
    rt = FB.verify_loaded_modules()
    assert rt["n_distribution_files_verified"] > rt["n_dependency_files"]
    real = FB._record_index
    monkeypatch.setattr(FB, "_record_index", lambda paths: {**real(paths), others[0]: "0" * 64})
    with pytest.raises(SystemExit, match="differs from its distribution RECORD"):
        FB.verify_loaded_modules()
    monkeypatch.setattr(FB, "_record_index", real)
    ghost = str(Path(dists[pa_key]["location"]) / "pyarrow" / "no_such_file.so")
    real_di = FB._dist_index

    def with_ghost(paths):
        o, d = real_di(paths)
        d[pa_key]["files"].append(ghost)
        return o, d
    monkeypatch.setattr(FB, "_dist_index", with_ghost)
    monkeypatch.setattr(FB, "_record_index", lambda paths: {**real(paths), ghost: "1" * 64})
    with pytest.raises(SystemExit, match="is in RECORD but missing"):
        FB.verify_loaded_modules()


def test_worker_runtime_is_required_and_checked(tmp_path):
    """Audit #12 D survivor (worker's final verification removed): the harness HALTs unless
    the real worker left a verified isolated runtime."""
    from nfl.sim.run_forward_v1 import check_worker_runtime
    with pytest.raises(SystemExit, match="runtime_worker.json missing"):
        check_worker_runtime(tmp_path)
    good = {"flags": "-I -S -B", "pycache_prefix_fresh": True, "n_repo_modules": 12,
            "n_dependency_files": 400, "dependency_distributions": {"pandas": {}}}
    for k, v in (("flags", "-I -B"), ("pycache_prefix_fresh", False), ("n_repo_modules", 0),
                 ("n_dependency_files", 0), ("dependency_distributions", {})):
        (tmp_path / "runtime_worker.json").write_text(json.dumps({**good, k: v}))
        with pytest.raises(SystemExit, match="not a verified isolated runtime"):
            check_worker_runtime(tmp_path)
    (tmp_path / "runtime_worker.json").write_text(json.dumps(good))
    assert check_worker_runtime(tmp_path)["n_dependency_files"] == 400


def test_bytearray_and_scheme_only_file_uris_are_refused(tmp_path):
    """Audit #12 D branch survivors: a bytearray path and a 'file:' URI without '//'."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    f = tmp_path / "x.parquet"
    pd.DataFrame({"v": [0.99]}).to_parquet(f, index=False)
    t = tmp_path / "x.txt"
    t.write_bytes(b"0.10")
    rec, err = _recorded(lambda: pa.memory_map(bytearray(os.fsencode(str(t)))).read())
    assert isinstance(err, PermissionError) and rec.violations, repr(err)
    for go in (lambda: pq.ParquetFile("file:" + str(f)).read(),
               lambda: pd.read_parquet("file:" + str(f)),
               lambda: pq.read_table(source="FILE:" + str(f))):
        rec, err = _recorded(go)
        assert isinstance(err, PermissionError) and "URI sources are refused" in str(err), repr(err)
        assert rec.violations


def test_worker_on_another_interpreter_or_dependency_halts(tmp_path, monkeypatch):
    """D269: in a bootstrapped harness, the worker must have run the same interpreter and,
    for every distribution both loaded, the same version, location and RECORD."""
    import nfl.sim.fwd_bootstrap as FB
    from nfl.sim.run_forward_v1 import check_worker_runtime
    pd_ident = {"version": "3.0.2", "location": "/x", "record_sha256": "a" * 64}
    mine = {"python": "3.13.1", "executable": "/usr/bin/python3",
            "dependency_distributions": {"pandas": pd_ident}}
    monkeypatch.setattr(FB, "ACTIVE", True)
    monkeypatch.setattr(FB, "verify_loaded_modules", lambda: mine)
    good = {"flags": "-I -S -B", "pycache_prefix_fresh": True, "n_repo_modules": 12,
            "n_dependency_files": 400, "python": "3.13.1", "executable": "/usr/bin/python3",
            "dependency_distributions": {"pandas": dict(pd_ident), "polars": {"version": "1"}}}
    f = tmp_path / "runtime_worker.json"
    f.write_text(json.dumps(good))
    assert check_worker_runtime(tmp_path)["python"] == "3.13.1"
    f.write_text(json.dumps({**good, "python": "3.12.0"}))
    with pytest.raises(SystemExit, match="different interpreter"):
        check_worker_runtime(tmp_path)
    f.write_text(json.dumps({**good, "dependency_distributions":
                             {"pandas": {**pd_ident, "record_sha256": "b" * 64}}}))
    with pytest.raises(SystemExit, match="dependency pandas differs"):
        check_worker_runtime(tmp_path)
