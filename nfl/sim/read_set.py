"""D256 (FWD6 item 0): a forward run's prediction consumes exactly its bundle.

Two pieces:

1. ``route_inputs(input_dir)`` points every prediction data path at the run's copied
   inputs (``<run-dir>/inputs``) by setting module constants. It edits no FREEZE_v1 file:
   ``engine.RATINGS_DIR`` is a module constant read at call time by ``_load_ratings()``.
   It HALTs if any required input is missing, so nothing ever falls back to a shared
   file or to a network fetch.

2. ``ReadSetRecorder`` records every data file the prediction process reads, with the
   sha256 OF THE BYTES ACTUALLY PARSED (the file is read once, hashed, and the parser is
   handed those same bytes). It also refuses any network connection. The harness then
   classifies each entry (``classify_read_set``): it must be inside the run directory
   with the bundle's hash, or a repo file hashed by the experiment manifest with a
   matching hash. Anything else HALTs.
"""
import builtins
import hashlib
import io
import json
import locale
import os
import site
import sys
import sysconfig
import threading
from pathlib import Path

# Files a forward run copies into <run-dir>/inputs and the prediction must read from there.
REQUIRED_INPUTS = [
    "team_ratings_weekly.parquet",
    "tendencies_weekly.parquet",
    "tendencies_situational_weekly.parquet",
    "qb_ratings_weekly.parquet",
    "kicker_weekly.parquet",
    "league_baselines.parquet",
    "player_usage_weekly.parquet",
    "active_universe_weekly.parquet",
    "rosters_weekly.parquet",
    "team_game_counts.json",
]
# D260: the bundle files the worker itself reads (lines/events for its targets, props).
# D263: and freshness.json, the source of the cutoff the worker claims in invocation.json.
MUST_READ_BUNDLE = ["lines.parquet", "events.parquet", "props.parquet", "freshness.json"]
# The read set must show the prediction read each of these FROM THE RUN DIRECTORY.
MUST_READ = [
    "qb_ratings_weekly.parquet",
    "team_ratings_weekly.parquet",
    "tendencies_weekly.parquet",
    "tendencies_situational_weekly.parquet",
    "kicker_weekly.parquet",
    "league_baselines.parquet",
    "player_usage_weekly.parquet",
    "active_universe_weekly.parquet",
    "rosters_weekly.parquet",
    "team_game_counts.json",
]


def route_inputs(input_dir):
    """Point the prediction's data paths at ``input_dir``. Returns a restore() callable."""
    input_dir = Path(input_dir).resolve()
    missing = [f for f in REQUIRED_INPUTS if not (input_dir / f).is_file()]
    if missing:
        raise SystemExit(f"HALT: run inputs missing from {input_dir}: {missing} "
                         f"(a forward run never falls back to shared files or the network)")
    import nfl.sim.engine as E
    import nfl.sim.calibration as C
    import nfl.sim.names as N
    import nfl.sim.usage as U          # D260: import BEFORE routing so a late import cannot escape
    # D260: anything already cached in-process was read before this run's recorder existed
    E._CACHE.clear()
    saved = [(E, "RATINGS_DIR", E.RATINGS_DIR),
             (C, "RATINGS_DIR", C.RATINGS_DIR),
             (C, "USAGE_PATH", C.USAGE_PATH),
             (N, "ROSTER_PATH", N.ROSTER_PATH)]
    E.RATINGS_DIR = input_dir
    C.RATINGS_DIR = input_dir
    C.USAGE_PATH = input_dir / "player_usage_weekly.parquet"
    N.ROSTER_PATH = input_dir / "rosters_weekly.parquet"
    saved.append((U, "PBP_DIR", U.PBP_DIR))
    U.PBP_DIR = input_dir

    def restore():
        for mod, attr, val in saved:
            setattr(mod, attr, val)
    return restore


def hashed_code_paths(root):
    """D263: absolute paths of the .py files the experiment manifest hashes — the only repo
    code the recorder treats as code rather than data."""
    root = Path(root)
    with open(root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json") as fh:
        hashes = json.load(fh)["file_hashes"]
    return {str((root / rel).resolve()) for rel in hashes if rel.endswith(".py")}


def _text_like_open(data, a, k):
    """A text stream over recorded bytes with the SAME decoding as the open() call it
    replaces: open(file, mode, buffering, encoding, errors, newline, ...). encoding=None
    and the 'locale' pseudo-encoding (what Path.read_text passes when UTF-8 mode is off,
    i.e. on a normal macOS/Linux UTF-8 locale) both mean the locale's preferred encoding;
    newline=None keeps universal-newline translation. (Before this, the wrapper raised
    LookupError on 'locale' and skipped newline translation.)"""
    names = ("buffering", "encoding", "errors", "newline")
    args = dict(zip(names, a))
    args.update({n: k[n] for n in names if n in k})
    enc = args.get("encoding")
    if enc is None or enc == "locale":
        enc = "utf-8" if sys.flags.utf8_mode else locale.getpreferredencoding(False)
    return io.TextIOWrapper(io.BytesIO(data), encoding=enc, errors=args.get("errors"),
                            newline=args.get("newline"))


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _install_prefixes():
    """D260: real installation directories (no substring matching)."""
    pre = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    for k in ("stdlib", "platstdlib", "purelib", "platlib"):
        try:
            pre.add(sysconfig.get_paths()[k])
        except Exception:
            pass
    try:
        pre.update(site.getsitepackages())
        pre.add(site.getusersitepackages())
    except Exception:
        pass
    return tuple(sorted({str(Path(x).resolve()) + os.sep for x in pre if x}))


_PREFIXES = _install_prefixes()
# D263: repo code exempt from the data read set = exactly the experiment-hashed .py files
# (set by ReadSetRecorder.install(code_allow=...)). A '.py' suffix alone is NOT an
# exemption: a data file named x.py outside this set is recorded like any other file.
_CODE_ALLOW = set()


def _code_source(p):
    """The .py source a code path stands for. D266: a .pyc never stands for repository
    code — forward-run processes compile repository modules from verified source
    (fwd_bootstrap), so a read of a repository .pyc is recorded and rejected as data."""
    pp = Path(p)
    return str(pp) if pp.suffix == ".py" else None


def _excluded(path_str):
    """Python installation (by real directory, not substring), the experiment's hashed code
    and OS pseudo-files are not data inputs."""
    p = str(Path(path_str).resolve())
    if p.startswith(_PREFIXES):
        return True
    src = _code_source(p)
    if src is not None and src in _CODE_ALLOW:
        return True
    # macOS: /etc and /var are symlinks into /private, and resolve() follows them
    return p.startswith(("/dev/", "/proc/", "/sys/", "/etc/", "/private/etc/",
                         "/usr/share/zoneinfo", "/private/var/db/timezone", "/usr/lib/locale"))


_NET = {"block": False, "attempts": []}
_HOOK_INSTALLED = [False]


def _audit(event, args):
    if _NET["block"] and event in ("socket.connect", "socket.getaddrinfo"):
        _NET["attempts"].append(f"{event} {args[1] if len(args) > 1 else ''}")
        raise RuntimeError(f"HALT: network access from the prediction process ({event})")


_GUARD = threading.local()
_ACTIVE = [None]


def _audit_open(event, args):
    """D260 backstop: any open() of a file for reading that bypassed the wrappers
    (os.open, io.FileIO, a captured alias, numpy, ...) is still recorded with the hash of
    the file at that moment. D263: such a record is marked via='audit' and the classifier
    REJECTS it — an open-time snapshot does not bind the bytes later read (audit #10). Only
    byte-serving wrapper reads are accepted as proof. An update-mode open is a violation."""
    rec = _ACTIVE[0]
    if rec is None or event != "open" or getattr(_GUARD, "busy", False):
        return
    path, mode, flags = (list(args) + [None, None, None])[:3]
    if not isinstance(path, (str, bytes, os.PathLike)):
        return
    path = os.fsdecode(path)
    reading = (mode is None and flags is not None and (flags & 3) in (os.O_RDONLY, os.O_RDWR)) \
        or (isinstance(mode, str) and ("r" in mode or "+" in mode))
    if not reading or not os.path.isfile(path) or _excluded(path):
        return
    if (isinstance(mode, str) and "+" in mode) or \
            (mode is None and flags is not None and (flags & 3) == os.O_RDWR):
        rec.violations.append(f"update-mode open of an input: {path}")
        # D266 (audit #11): refused at the open itself, not only at classification
        raise PermissionError(f"HALT: update-mode open of {path} is not permitted in a "
                              f"forward run")
    _GUARD.busy = True
    try:
        with rec._orig["open"](path, "rb") as fh:
            rec._record(path, fh.read(), via="audit")
    finally:
        _GUARD.busy = False


_SOURCE_KW = ("source", "path", "where", "path_or_paths", "filename", "uri", "filepath_or_buffer")


def _as_local_path(src):
    """D266 (audit #11 A3): a str/bytes/PathLike source as a local path string, or None for
    anything that is not a path (an in-memory buffer). A URI ('scheme://…', 'file:…') is
    returned as-is so the caller can refuse it."""
    if isinstance(src, (bytes, bytearray)):
        return os.fsdecode(bytes(src))
    if isinstance(src, (str, os.PathLike)):
        return os.fspath(src) if not isinstance(src, str) else src
    return None


def _is_uri(s):
    return "://" in s or s.lower().startswith("file:")


class ReadSetRecorder:
    """Records every data file read (path + sha256 of the parsed bytes) and blocks network."""

    def __init__(self):
        self.entries = {}      # abs path -> {"sha256", "reads", "via": set of mechanisms}
        self.conflicts = []    # same path read twice with different bytes
        self.violations = []   # D263: update-mode opens, forbidden native readers
        self._orig = {}

    def _record(self, path, data, via="wrapper"):
        ap = str(Path(path).resolve())
        h = _sha256(data)
        e = self.entries.get(ap)
        if e is None:
            self.entries[ap] = {"sha256": h, "reads": 1, "via": {via}}
        else:
            e["reads"] += 1
            e["via"].add(via)      # D263: every mechanism, not just the first
            if e["sha256"] != h:
                self.conflicts.append(ap)

    def _load(self, path):
        _GUARD.busy = True
        try:
            with self._orig["open"](path, "rb") as fh:
                return fh.read()
        finally:
            _GUARD.busy = False

    def install(self, code_allow=None):
        """code_allow: absolute paths of the experiment-hashed .py files (D263)."""
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.dataset as pads
        import pyarrow.feather as paf
        rec = self
        _CODE_ALLOW.clear()
        _CODE_ALLOW.update(str(Path(c).resolve()) for c in (code_allow or ()))
        self._orig = {"open": builtins.open, "io_open": io.open,
                      "read_parquet": pd.read_parquet,
                      "read_csv": pd.read_csv, "read_json": pd.read_json,
                      "read_table": pq.read_table, "ParquetFile": pq.ParquetFile}
        # D263: native readers that open a PATH without Python's open() cannot be served
        # recorded bytes; in forward mode they are refused (fail closed), not bypassed.
        # pq.ParquetDataset (a class) is replaced by a guarded SUBCLASS so isinstance
        # checks still hold; pa.OSFile (a final extension type) cannot be, and is covered
        # by the static scan of the hashed code (test_fwd6c).
        import pyarrow.fs as pafs
        self._fs = pafs
        self._orig[("pyarrow.fs", "LocalFileSystem")] = pafs.LocalFileSystem
        self._orig[("pyarrow.fs", "FileSystem")] = pafs.FileSystem
        self._native = [(pa, "memory_map"), (pa, "input_stream"), (pq, "ParquetDataset"),
                        (pads, "dataset"), (pq, "read_pandas"),
                        (pq, "read_metadata"), (pq, "read_schema"),
                        (paf, "read_table"), (paf, "read_feather"),
                        (pd, "read_feather"), (pd, "read_orc")]
        for mod, attr in self._native:
            self._orig[(mod.__name__, attr)] = getattr(mod, attr)

        def _serve(name, src):
            """D266: the bytes to hand a parser for `src`, or None to pass `src` through
            untouched (an in-memory buffer, or an installation/OS file). Every other source
            form — a URI, a bytes path, a path that is not an existing regular file, an
            opaque native pyarrow file — is REFUSED, never passed to native code."""
            import pyarrow as pa
            if isinstance(src, pa.NativeFile) and not isinstance(src, pa.BufferReader):
                rec.violations.append(f"{name}: opaque native file source")
                raise PermissionError(f"HALT: {name} given a native file handle; only "
                                      f"recorded bytes may be parsed in a forward run")
            lp = _as_local_path(src)
            if lp is None:
                return None
            if _is_uri(lp):
                rec.violations.append(f"{name}: URI source {lp}")
                raise PermissionError(f"HALT: {name}({lp}) — URI sources are refused")
            if os.path.isfile(lp):
                if _excluded(str(Path(lp).resolve())):
                    return None
                data = rec._load(lp)
                rec._record(lp, data)
                return data
            rec.violations.append(f"{name}: unsupported source {lp!r}")
            raise PermissionError(f"HALT: {name}({lp!r}) is not an existing regular file")

        def _wrap_pd(name):
            orig = rec._orig[name]

            def wrapper(*a, **k):
                key = next((kk for kk in _SOURCE_KW if kk in k), None)
                src = k[key] if key else (a[0] if a else None)
                data = _serve(name, src)
                if data is None:
                    return orig(*a, **k)
                if key:
                    return orig(*a, **{**k, key: io.BytesIO(data)})
                return orig(io.BytesIO(data), *a[1:], **k)
            return wrapper

        def open_wrapper(file, mode="r", *a, **k):
            if (isinstance(file, (str, os.PathLike)) and os.path.isfile(file)
                    and not _excluded(str(Path(file).resolve()))):
                if "+" in mode:
                    # D263: an update-mode handle can change the bytes after they are
                    # hashed (audit #10: consumed 0.99, recorded 0.10). Refused.
                    rec.violations.append(f"update-mode open of an input: {file}")
                    raise PermissionError(f"HALT: update-mode open of {file} is not "
                                          f"permitted in a forward run")
            if (isinstance(file, (str, os.PathLike)) and "r" in mode
                    and os.path.isfile(file) and not _excluded(str(Path(file).resolve()))):
                data = rec._load(file)
                rec._record(file, data)
                if "b" in mode:
                    return io.BytesIO(data)
                return _text_like_open(data, a, k)
            return rec._orig["open"](file, mode, *a, **k)

        def parquetfile_wrapper(*a, **k):
            key = next((kk for kk in _SOURCE_KW if kk in k), None)
            src = k[key] if key else (a[0] if a else None)
            data = _serve("pyarrow.parquet.ParquetFile", src)
            if data is None:
                return rec._orig["ParquetFile"](*a, **k)
            if key:
                return rec._orig["ParquetFile"](*a, **{**k, key: io.BytesIO(data)})
            return rec._orig["ParquetFile"](io.BytesIO(data), *a[1:], **k)

        def _refuse_paths(name, a, k):
            """D266: a native reader is refused for ANY path-like source — str, bytes,
            PathLike or URI, positional or keyword, existing or not — unless it is an
            installation/OS file."""
            import pyarrow as pa
            srcs = a[:1] + tuple(v for kk, v in k.items() if kk in _SOURCE_KW)
            for src in srcs:
                items = src if isinstance(src, (list, tuple)) else [src]
                for it in items:
                    if isinstance(it, pa.NativeFile) and not isinstance(it, pa.BufferReader):
                        rec.violations.append(f"native reader {name} on a native file")
                        raise PermissionError(f"HALT: {name}(<native file>) is refused")
                    lp = _as_local_path(it)
                    if lp is None:
                        continue
                    if not _is_uri(lp) and os.path.exists(lp) and _excluded(str(Path(lp).resolve())):
                        continue
                    rec.violations.append(f"native reader {name} on {lp}")
                    raise PermissionError(f"HALT: {name}({lp}) reads natively, "
                                          f"outside the read-set recorder")

        def _forbid(name, orig):
            if isinstance(orig, type):
                class Guarded(orig):
                    def __init__(self, *a, **k):
                        _refuse_paths(name, a, k)
                        super().__init__(*a, **k)
                Guarded.__name__ = orig.__name__
                return Guarded

            def refused(*a, **k):
                _refuse_paths(name, a, k)
                return orig(*a, **k)
            return refused

        for mod, attr in self._native:
            setattr(mod, attr, _forbid(f"{mod.__name__}.{attr}", self._orig[(mod.__name__, attr)]))

        # D266 (audit #11 C): pyarrow's native local filesystem opens files without
        # Python's open(); its input-opening methods and FileSystem.from_uri are refused.
        def _fs_refuse(name):
            def refused(self_or_cls, *a, **k):
                rec.violations.append(f"pyarrow.fs {name}")
                raise PermissionError(f"HALT: pyarrow.fs {name} reads natively, outside "
                                      f"the read-set recorder")
            return refused

        class GuardedLocalFileSystem(self._orig[("pyarrow.fs", "LocalFileSystem")]):
            open_input_file = _fs_refuse("LocalFileSystem.open_input_file")
            open_input_stream = _fs_refuse("LocalFileSystem.open_input_stream")

        class GuardedFileSystem(self._orig[("pyarrow.fs", "FileSystem")]):
            @staticmethod
            def from_uri(*a, **k):
                rec.violations.append("pyarrow.fs FileSystem.from_uri")
                raise PermissionError("HALT: pyarrow.fs FileSystem.from_uri is refused")

        pafs.LocalFileSystem = GuardedLocalFileSystem
        pafs.FileSystem = GuardedFileSystem
        pd.read_parquet = _wrap_pd("read_parquet")
        pd.read_csv = _wrap_pd("read_csv")
        pd.read_json = _wrap_pd("read_json")
        pq.read_table = _wrap_pd("read_table")
        pq.ParquetFile = parquetfile_wrapper
        builtins.open = open_wrapper
        io.open = open_wrapper            # D260: Path.open/read_bytes/read_text go through io.open
        if not _HOOK_INSTALLED[0]:
            sys.addaudithook(_audit)
            sys.addaudithook(_audit_open)
            _HOOK_INSTALLED[0] = True
        _ACTIVE[0] = self
        _NET["attempts"] = []
        _NET["block"] = True
        return self

    def uninstall(self):
        import pandas as pd
        import pyarrow.parquet as pq
        if not self._orig:
            return
        builtins.open = self._orig["open"]
        io.open = self._orig["io_open"]
        pq.ParquetFile = self._orig["ParquetFile"]
        _ACTIVE[0] = None
        pd.read_parquet = self._orig["read_parquet"]
        pd.read_csv = self._orig["read_csv"]
        pd.read_json = self._orig["read_json"]
        pq.read_table = self._orig["read_table"]
        for mod, attr in getattr(self, "_native", []):
            setattr(mod, attr, self._orig[(mod.__name__, attr)])
        if getattr(self, "_fs", None) is not None:
            self._fs.LocalFileSystem = self._orig[("pyarrow.fs", "LocalFileSystem")]
            self._fs.FileSystem = self._orig[("pyarrow.fs", "FileSystem")]
        _CODE_ALLOW.clear()
        _NET["block"] = False

    def write(self, out_path):
        doc = {
            "entries": [{"path": p, "sha256": e["sha256"], "reads": e["reads"],
                         "via": sorted(e["via"])}
                        for p, e in sorted(self.entries.items())],
            "conflicts": sorted(set(self.conflicts)),
            "violations": list(self.violations),
            "network_attempts": list(_NET["attempts"]),
        }
        with self._orig.get("open", builtins.open)(out_path, "w") as fh:
            fh.write(json.dumps(doc, indent=1) + "\n")
        return doc


def classify_read_set(read_set, bundle_dir, root, file_hashes, bundle_manifest):
    """Classify every read-set entry; HALT (SystemExit) on anything unproven.

    (i)  inside the run directory: an outputs/ file the run produced, or a bundle file whose
         sha256 equals the bundle manifest's;
    (ii) a repo file hashed by the experiment manifest, with a matching hash.
    Anything else — a shared ratings file, the props archive, PBP, a file outside the repo —
    HALTs. Every MUST_READ input must appear as a class-(i) read of inputs/<name>.
    Returns a list of (relative path, class) for the report.
    """
    bundle_dir = Path(bundle_dir).resolve()
    root = Path(root).resolve()
    bad, summary = [], []
    if read_set.get("conflicts"):
        bad.append(f"file changed between two reads: {read_set['conflicts']}")
    if read_set.get("network_attempts"):
        bad.append(f"network access attempted: {read_set['network_attempts']}")
    if read_set.get("violations"):
        bad.append(f"forbidden reads: {read_set['violations']}")
    read_inputs, read_bundle = set(), set()
    for e in read_set.get("entries", []):
        p = Path(e["path"]).resolve()
        h = e["sha256"]
        # D263: only byte-serving wrapper reads prove what was parsed; an entry without
        # 'via' (pre-D263 format) or with an audit-only snapshot is unproven
        via = e.get("via")
        if via is None or set(via) != {"wrapper"}:
            bad.append(f"read not byte-bound (via={via}): {p}")
            continue
        if p == bundle_dir or bundle_dir in p.parents:
            rel = str(p.relative_to(bundle_dir))
            if rel.startswith("outputs" + os.sep):
                # D260: an output the worker read back must be the file now on disk (and,
                # once finalised, the manifest's) — never an unconditional pass
                want = bundle_manifest.get(rel)
                if want is None:
                    want = _sha256(p.read_bytes()) if p.is_file() else None
                if want is None or want != h:
                    bad.append(f"read an output whose bytes are not the run's: {rel}")
                else:
                    summary.append((rel, "i-output"))
                continue
            want = bundle_manifest.get(rel)
            if want is None:
                bad.append(f"read a run-directory file not in the bundle manifest: {rel}")
            elif want != h:
                bad.append(f"run-directory file differs from the bundle manifest: {rel}")
            else:
                summary.append((rel, "i"))
                if rel.startswith("inputs" + os.sep):
                    read_inputs.add(rel.split(os.sep, 1)[1])
                else:
                    read_bundle.add(rel)
            continue
        if root in p.parents:
            rel = str(p.relative_to(root))
            want = file_hashes.get(rel)
            if want is None:
                bad.append(f"read an unlisted shared file: {rel}")
            elif h[:len(want)] != want:
                bad.append(f"hashed repo file differs from the experiment manifest: {rel}")
            else:
                summary.append((rel, "ii"))
            continue
        bad.append(f"read a file outside the repo: {p}")
    missing = [f for f in MUST_READ if f not in read_inputs]
    missing += [f for f in MUST_READ_BUNDLE if f not in read_bundle]
    if missing:
        bad.append(f"prediction did not read these inputs from the run directory: {missing}")
    if bad:
        raise SystemExit("HALT: read-set proof failed:\n" + "\n".join(f"  {b}" for b in bad))
    return summary
