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
import os
import sys
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
# The read set must show the prediction read each of these FROM THE RUN DIRECTORY.
MUST_READ = [
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
    saved = [(E, "RATINGS_DIR", E.RATINGS_DIR),
             (C, "RATINGS_DIR", C.RATINGS_DIR),
             (C, "USAGE_PATH", C.USAGE_PATH),
             (N, "ROSTER_PATH", N.ROSTER_PATH)]
    E.RATINGS_DIR = input_dir
    C.RATINGS_DIR = input_dir
    C.USAGE_PATH = input_dir / "player_usage_weekly.parquet"
    N.ROSTER_PATH = input_dir / "rosters_weekly.parquet"
    U = sys.modules.get("nfl.sim.usage")
    if U is not None and hasattr(U, "PBP_DIR"):
        saved.append((U, "PBP_DIR", U.PBP_DIR))
        U.PBP_DIR = input_dir

    def restore():
        for mod, attr, val in saved:
            setattr(mod, attr, val)
    return restore


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _excluded(path_str):
    """Python installation, site-packages and OS pseudo-files are not data inputs."""
    p = path_str
    prefixes = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    if any(pre and p.startswith(pre + os.sep) for pre in prefixes):
        return True
    if "site-packages" in p or "dist-packages" in p:
        return True
    return p.startswith(("/dev/", "/proc/", "/sys/", "/etc/", "/usr/share/zoneinfo"))


_NET = {"block": False, "attempts": []}
_HOOK_INSTALLED = [False]


def _audit(event, args):
    if _NET["block"] and event in ("socket.connect", "socket.getaddrinfo"):
        _NET["attempts"].append(f"{event} {args[1] if len(args) > 1 else ''}")
        raise RuntimeError(f"HALT: network access from the prediction process ({event})")


class ReadSetRecorder:
    """Records every data file read (path + sha256 of the parsed bytes) and blocks network."""

    def __init__(self):
        self.entries = {}      # abs path -> {"sha256", "reads"}
        self.conflicts = []    # same path read twice with different bytes
        self._orig = {}

    def _record(self, path, data):
        ap = str(Path(path).resolve())
        h = _sha256(data)
        e = self.entries.get(ap)
        if e is None:
            self.entries[ap] = {"sha256": h, "reads": 1}
        else:
            e["reads"] += 1
            if e["sha256"] != h:
                self.conflicts.append(ap)

    def _load(self, path):
        with self._orig["open"](path, "rb") as fh:
            return fh.read()

    def install(self):
        import pandas as pd
        import pyarrow.parquet as pq
        rec = self
        self._orig = {"open": builtins.open, "read_parquet": pd.read_parquet,
                      "read_csv": pd.read_csv, "read_json": pd.read_json,
                      "read_table": pq.read_table}

        def _is_path(x):
            return isinstance(x, (str, os.PathLike)) and os.path.isfile(x)

        def _wrap_pd(name):
            orig = rec._orig[name]

            def wrapper(src, *a, **k):
                if _is_path(src) and not _excluded(str(Path(src).resolve())):
                    data = rec._load(src)
                    rec._record(src, data)
                    return orig(io.BytesIO(data), *a, **k)
                return orig(src, *a, **k)
            return wrapper

        def open_wrapper(file, mode="r", *a, **k):
            if (isinstance(file, (str, os.PathLike)) and not any(c in mode for c in "wax+")
                    and os.path.isfile(file) and not _excluded(str(Path(file).resolve()))):
                data = rec._load(file)
                rec._record(file, data)
                if "b" in mode:
                    return io.BytesIO(data)
                enc = k.get("encoding") or (a[1] if len(a) > 1 else None) or "utf-8"
                return io.StringIO(data.decode(enc))
            return rec._orig["open"](file, mode, *a, **k)

        pd.read_parquet = _wrap_pd("read_parquet")
        pd.read_csv = _wrap_pd("read_csv")
        pd.read_json = _wrap_pd("read_json")
        pq.read_table = _wrap_pd("read_table")
        builtins.open = open_wrapper
        if not _HOOK_INSTALLED[0]:
            sys.addaudithook(_audit)
            _HOOK_INSTALLED[0] = True
        _NET["attempts"] = []
        _NET["block"] = True
        return self

    def uninstall(self):
        import pandas as pd
        import pyarrow.parquet as pq
        if not self._orig:
            return
        builtins.open = self._orig["open"]
        pd.read_parquet = self._orig["read_parquet"]
        pd.read_csv = self._orig["read_csv"]
        pd.read_json = self._orig["read_json"]
        pq.read_table = self._orig["read_table"]
        _NET["block"] = False

    def write(self, out_path):
        doc = {
            "entries": [{"path": p, "sha256": e["sha256"], "reads": e["reads"]}
                        for p, e in sorted(self.entries.items())],
            "conflicts": sorted(set(self.conflicts)),
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
    read_inputs = set()
    for e in read_set.get("entries", []):
        p = Path(e["path"]).resolve()
        h = e["sha256"]
        if p == bundle_dir or bundle_dir in p.parents:
            rel = str(p.relative_to(bundle_dir))
            if rel.startswith("outputs" + os.sep):
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
    if missing:
        bad.append(f"prediction did not read these inputs from the run directory: {missing}")
    if bad:
        raise SystemExit("HALT: read-set proof failed:\n" + "\n".join(f"  {b}" for b in bad))
    return summary
