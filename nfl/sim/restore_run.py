#!/usr/bin/env python3
"""D256(d): rebuild a forward run directory's missing files from the content-addressed
archive, then verify the whole run directory against its bundle manifest.

Usage:
  python3 nfl/sim/restore_run.py --run-dir nfl/data/board/week=2026_04/sim_runs/<run_id> [--archive DIR]

The archive defaults to <repo parent>/mlb-model-archive/nfl_fwd_v1 (NFL_FWD_ARCHIVE
overrides), where build_bundle and the freeze store every run-directory file under
sha256/<hash>. Files already present are never overwritten; a present file with the
wrong hash is reported by the verify step, not replaced.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def restore(run_dir, archive_root):
    from nfl.sim.run_forward_v1 import verify_bundle
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "bundle_manifest.json").read_text())
    restored, unavailable = [], []
    for rel, h in manifest.items():
        if not isinstance(h, str) or len(h) != 64:
            continue
        dest = run_dir / rel
        if dest.exists():
            continue
        src = Path(archive_root) / "sha256" / h
        if not src.exists():
            unavailable.append(rel)
            continue
        if hashlib.sha256(src.read_bytes()).hexdigest() != h:
            unavailable.append(f"{rel} (archive copy corrupt)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        restored.append(rel)
    bad = verify_bundle(run_dir)
    return restored, unavailable, bad


def main(argv=None):
    from nfl.sim.run_forward_v1 import archive_root_for
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--archive", default=None)
    a = ap.parse_args(argv)
    archive = Path(a.archive) if a.archive else archive_root_for(ROOT)
    restored, unavailable, bad = restore(a.run_dir, archive)
    print(f"Archive: {archive}")
    print(f"Restored {len(restored)} file(s):")
    for r in restored:
        print(f"  {r}")
    if unavailable:
        print(f"UNAVAILABLE in the archive: {unavailable}")
    if bad:
        print("verify_bundle: FAILED")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    if unavailable:
        raise SystemExit(1)
    print("verify_bundle: clean")


if __name__ == "__main__":
    main()
