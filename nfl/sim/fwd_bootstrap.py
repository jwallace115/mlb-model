#!/usr/bin/env python3
"""D266 (audit #11 A1/A2): the only way a forward run's processes start.

    python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 2

Every process of a forward run — the harness (parent), the freeze gate and the worker —
is started through this file with ``-I -S -B``:

- ``-I``  ignores every PYTHON* environment variable (PYTHONPATH, PYTHONSTARTUP, …), the
          user's current directory and the script directory on sys.path;
- ``-S``  does not import ``site``: no ``sitecustomize``/``usercustomize`` and no ``.pth``
          file is ever executed or processed;
- ``-B``  writes no bytecode.

Then, before ANY project module is imported:

1. ``sys.pycache_prefix`` is pointed at a fresh, empty, private directory, so no existing
   ``.pyc`` (project or dependency) can be selected: every module is compiled from source.
2. The dependency directories (``site.getsitepackages()`` and the user site, computed
   without processing any ``.pth`` file) are appended to sys.path.
3. A meta-path finder is installed in front of every other finder. Any module whose file
   is inside the repository is executed ONLY from source bytes whose sha256 matches the
   experiment manifest (``research/nfl_sim/FWD_EXPERIMENT_v1.json``); the bytes hashed
   are the bytes compiled. An unlisted repository module, or a listed one whose bytes
   differ, cannot be imported.
4. ``verify_loaded_modules()`` checks every module file loaded in the process: repository
   files must have come through that finder; standard-library files must lie under the
   interpreter's own library directories; every other file must match the sha256 recorded
   for it in its installed distribution's RECORD. Anything else HALTs.

Limit, stated plainly: the interpreter binary and the standard library are trusted (their
paths and the Python version are recorded, not hashed). A process that is not started
through this file is not covered — which is why a primary freeze refuses to run unless it
was (run_forward_v1.REQUIRE_LAUNCHER).
"""
import base64
import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"
FLAGS = ["-I", "-S", "-B"]
ACTIVE = False                 # True only in a process started through this file
_STATE = {"verified": {}, "trusted_paths": [], "stdlib": [], "pycache_prefix": None}


def child_cmd(mode, *args):
    """The command that starts another forward-run process (gate or worker)."""
    return [sys.executable, *FLAGS, str(Path(__file__).resolve()), mode, *map(str, args)]


def _flags_ok():
    return bool(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode)


def _manifest_hashes():
    with open(MANIFEST, "rb") as fh:
        return json.loads(fh.read())["file_hashes"]


class _VerifiedLoader(importlib.abc.Loader):
    def __init__(self, data, origin):
        self._data, self._origin = data, origin

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        code = compile(self._data, self._origin, "exec", dont_inherit=True)
        exec(code, module.__dict__)


class VerifiedSourceFinder(importlib.abc.MetaPathFinder):
    """Repository modules execute only from manifest-verified source bytes."""

    def __init__(self, root, hashes):
        self.root = Path(root).resolve()
        self.hashes = dict(hashes)

    def find_spec(self, name, path, target=None):
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or not spec.has_location or spec.origin is None:
            return None
        origin = Path(spec.origin).resolve()
        if self.root not in origin.parents:
            return None
        rel = origin.relative_to(self.root).as_posix()
        want = self.hashes.get(rel)
        if want is None or not rel.endswith(".py"):
            raise ImportError(f"HALT: repository module {rel} is not in the experiment "
                              f"manifest — it may not run in a forward run")
        with open(origin, "rb") as fh:
            data = fh.read()
        if hashlib.sha256(data).hexdigest()[:len(want)] != want:
            raise ImportError(f"HALT: {rel} differs from the experiment manifest")
        _STATE["verified"][str(origin)] = hashlib.sha256(data).hexdigest()
        spec.loader = _VerifiedLoader(data, str(origin))
        spec.cached = None
        return spec


def _record_index(paths):
    """{absolute file path: sha256 hex} from every distribution RECORD under `paths`."""
    import importlib.metadata as md
    idx = {}
    for dist in md.distributions(path=list(paths)):
        for f in dist.files or ():
            if not f.hash or f.hash.mode != "sha256":
                continue
            raw = base64.urlsafe_b64decode(f.hash.value + "=" * (-len(f.hash.value) % 4))
            idx[str(Path(dist.locate_file(f)).resolve())] = raw.hex()
    return idx


def verify_loaded_modules():
    """HALT unless every loaded module file is verified repository source, interpreter
    standard library, or a dependency file matching its distribution RECORD. Returns the
    runtime fingerprint recorded in the receipt."""
    if not ACTIVE:
        raise SystemExit("HALT: verify_loaded_modules outside a bootstrapped process")
    idx = _record_index(_STATE["trusted_paths"])
    bad, deps = [], {}
    for name, mod in sorted(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        p = str(Path(f).resolve())
        if p == str(Path(__file__).resolve()):
            continue
        if Path(ROOT) in Path(p).parents:
            if p not in _STATE["verified"]:
                bad.append(f"repository module {name} ({p}) did not load through the verifier")
            continue
        # D268: a file under a dependency directory is a dependency even when that
        # directory sits inside the interpreter's library dir (macOS python.org and
        # standalone builds: <prefix>/lib/python3.X/site-packages); it must match RECORD
        in_dep_dir = (p.startswith(tuple(t.rstrip(os.sep) + os.sep for t in _STATE["trusted_paths"]))
                      or bool({"site-packages", "dist-packages"} & set(Path(p).parts)))
        if not in_dep_dir and p.startswith(tuple(_STATE["stdlib"])):
            continue
        want = idx.get(p)
        if want is None:
            bad.append(f"{name}: {p} is neither standard library nor in a distribution RECORD")
            continue
        with open(p, "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        if got != want:
            bad.append(f"{name}: {p} differs from its distribution RECORD")
        deps[p] = got
    if bad:
        raise SystemExit("HALT: unverified code in the process:\n" +
                         "\n".join(f"  {b}" for b in bad[:50]))
    digest = hashlib.sha256(json.dumps(sorted({**deps, **_STATE["verified"]}.items()))
                            .encode()).hexdigest()
    return {"python": sys.version.split()[0], "executable": sys.executable,
            "flags": "-I -S -B", "pycache_prefix_fresh": True,
            "n_repo_modules": len(_STATE["verified"]), "n_dependency_files": len(deps),
            "loaded_code_sha256": digest}


def bootstrap():
    """Make this process a verified forward-run process. Idempotent."""
    global ACTIVE
    if ACTIVE:
        return
    if not _flags_ok():
        raise SystemExit("HALT: a forward-run process must be started with python3 -I -S -B "
                         "nfl/sim/fwd_bootstrap.py … (no site, no PYTHON* environment, no "
                         "bytecode writes)")
    if os.environ.get("PYTHONUSERBASE"):
        # site.getusersitepackages() honours PYTHONUSERBASE even under -I (D268)
        raise SystemExit("HALT: PYTHONUSERBASE is set; a forward run takes no PYTHON* environment")
    import site
    import sysconfig
    import tempfile
    # (1) no existing .pyc may be selected for any module imported from now on
    import atexit
    import shutil
    prefix = tempfile.mkdtemp(prefix="fwd_pyc_")
    atexit.register(shutil.rmtree, prefix, True)
    sys.pycache_prefix = prefix
    _STATE["pycache_prefix"] = prefix
    # standard library = the interpreter's own library dirs (the initial -I -S sys.path)
    std = {str(Path(p).resolve()) for p in sys.path if p}
    for k in ("stdlib", "platstdlib"):
        std.add(str(Path(sysconfig.get_paths()[k]).resolve()))
    trusted = []
    for p in list(site.getsitepackages()) + [site.getusersitepackages()]:
        rp = str(Path(p).resolve())
        if os.path.isdir(rp) and rp not in trusted:
            trusted.append(rp)
    _STATE["stdlib"] = sorted(s.rstrip(os.sep) + os.sep for s in std if s not in trusted)
    _STATE["trusted_paths"] = trusted
    # (2) dependency directories, appended WITHOUT processing any .pth file
    for p in trusted:
        if p not in sys.path:
            sys.path.append(p)
    # (3) repository code only from manifest-verified source
    hashes = _manifest_hashes()
    me = Path(__file__).resolve().relative_to(ROOT).as_posix()
    with open(Path(__file__).resolve(), "rb") as fh:
        if hashlib.sha256(fh.read()).hexdigest()[:len(hashes.get(me, "x"))] != hashes.get(me):
            raise SystemExit(f"HALT: {me} differs from the experiment manifest")
    sys.meta_path.insert(0, VerifiedSourceFinder(ROOT, hashes))
    sys.path.insert(0, str(ROOT))
    ACTIVE = True
    # anything that imports this module by name gets THIS (bootstrapped) instance
    sys.modules["nfl.sim.fwd_bootstrap"] = sys.modules[__name__]


def _gate(xml_path):
    for k in ("PYTEST_PLUGINS", "PYTEST_ADDOPTS"):
        os.environ.pop(k, None)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    import pytest
    test_file = ROOT / "nfl" / "sim" / "tests" / "test_freeze_v1.py"
    ret = pytest.main(["-q", "-p", "no:cacheprovider", "--assert=plain", "--noconftest",
                       "-c", os.devnull, "--rootdir", str(ROOT),
                       f"--junitxml={xml_path}", str(test_file)])
    verify_loaded_modules()
    return int(ret)


def _worker(argv):
    import nfl.sim.run_week as rw
    rw.main(argv)
    verify_loaded_modules()
    return 0


def _harness(argv):
    import nfl.sim.run_forward_v1 as fwd
    fwd.main(argv=argv)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("harness", "gate", "worker", "selftest"):
        raise SystemExit("usage: python3 -I -S -B nfl/sim/fwd_bootstrap.py "
                         "{harness|gate|worker|selftest} …")
    mode, rest = argv[0], argv[1:]
    bootstrap()
    if mode == "gate":
        return _gate(rest[0])
    if mode == "worker":
        return _worker(rest)
    if mode == "harness":
        return _harness(rest)
    # selftest: report the process's isolation and import provenance (tests use this)
    for name in rest:
        __import__(name)
    print(json.dumps({"flags_ok": _flags_ok(),
                      "sitecustomize": "sitecustomize" in sys.modules,
                      "usercustomize": "usercustomize" in sys.modules,
                      "modules": {n: getattr(sys.modules[n], "__file__", None) for n in rest},
                      "markers": {n: getattr(sys.modules[n], "PLANTED", None) for n in rest},
                      "runtime": verify_loaded_modules()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
