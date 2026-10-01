#!/usr/bin/env python3
"""D256(d)/D260: rebuild a forward run's complete record from the content-addressed archive,
then verify it.

Usage:
  python3 nfl/sim/restore_run.py --run-id 20261002T233000Z          (a published run)
  python3 nfl/sim/restore_run.py --run-dir nfl/data/board/.../sim_runs/<run_id>   (a dry run)

A published run is restored from its RECEIPT (repo registry, or <archive>/receipts/<run_id>.json
when the registry is gone): the bundle manifest is bootstrapped from the archive by the
receipt's bundle_digest, then every manifest file, publication.json (by the receipt's hash),
the frozen opinions file (by frozen_sha256), its ai_opinions manifest entry, and the
registry line. A file already present is never overwritten. The run passes only if
verify_bundle is clean AND receipt_status is 'complete'.

The archive defaults to <repo parent>/mlb-model-archive/nfl_fwd_v1 (NFL_FWD_ARCHIVE overrides).
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _from_archive(archive_root, h, dest, restored, unavailable, label):
    dest = Path(dest)
    if dest.exists():
        return
    src = Path(archive_root) / "sha256" / h
    if not src.exists():
        unavailable.append(label)
        return
    if _sha(src) != h:
        unavailable.append(f"{label} (archive copy corrupt)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    restored.append(label)


def find_receipt(run_id, root, archive_root):
    from nfl.sim.run_forward_v1 import load_receipts
    recs = [r for r in load_receipts(root) if r.get("run_id") == run_id]
    if len(recs) > 1:
        raise SystemExit(f"HALT: {len(recs)} receipts for run {run_id} in the registry")
    if recs:
        return recs[0], "registry"
    f = Path(archive_root) / "receipts" / f"{run_id}.json"
    if f.exists():
        rec = json.loads(f.read_text())
        # D263 (audit #10 R5): the index name is not the identity — the payload must be
        # the requested run's
        if rec.get("run_id") != run_id:
            raise SystemExit(f"HALT: archive receipt {f.name} holds run {rec.get('run_id')}, "
                             f"not {run_id}")
        return rec, "archive"
    return None, None


def restore(run_dir, archive_root, receipt=None, root=ROOT):
    """Restore one run directory (and, with a receipt, its publication record)."""
    from nfl.sim.run_forward_v1 import verify_bundle, append_receipt, load_receipts, RECEIPTS_REL
    run_dir = Path(run_dir)
    restored, unavailable = [], []
    man = run_dir / "bundle_manifest.json"
    if receipt is not None:
        _from_archive(archive_root, receipt["bundle_digest"], man, restored, unavailable,
                      "bundle_manifest.json")
    if not man.exists():
        raise SystemExit(f"HALT: {man} missing and no receipt to bootstrap it from")
    if receipt is not None and _sha(man) != receipt["bundle_digest"]:
        raise SystemExit("HALT: bundle_manifest.json does not match the receipt's bundle_digest")
    manifest = json.loads(man.read_text())
    for rel, h in manifest.items():
        if isinstance(h, str) and len(h) == 64:
            _from_archive(archive_root, h, run_dir / rel, restored, unavailable, rel)
    if receipt is not None:
        _from_archive(archive_root, receipt["publication_json_sha256"], run_dir / "publication.json",
                      restored, unavailable, "publication.json")
        _from_archive(archive_root, receipt["frozen_sha256"], Path(root) / receipt["frozen_file"],
                      restored, unavailable, receipt["frozen_file"])
        entry = receipt.get("opinions_manifest_entry")
        if entry is not None:
            om = (Path(root) / receipt["frozen_file"]).parent / "manifest.json"
            entries = json.loads(om.read_text()) if om.exists() else []
            existing = [e for e in entries if e.get("file") == entry["file"]]
            if any(e != entry for e in existing):
                # D263 (audit #10 R5): an existing entry that differs from the receipt's
                # authoritative one is reported, never silently kept or overwritten
                bad_entry = f"{om.relative_to(root)}: entry for {entry['file']} differs from the receipt"
                unavailable.append(bad_entry)
            if not existing:
                entries.append(entry)
                om.parent.mkdir(parents=True, exist_ok=True)
                om.write_text(json.dumps(entries, indent=1) + "\n")
                restored.append(f"{om.relative_to(root)} (entry for {entry['file']})")
        if not any(r.get("run_id") == receipt["run_id"] for r in load_receipts(root)):
            append_receipt(root, receipt)
            restored.append(f"{RECEIPTS_REL} (receipt line)")
    bad = verify_bundle(run_dir)
    return restored, unavailable, bad


def main(argv=None):
    from nfl.sim.run_forward_v1 import archive_root_for, receipt_status
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-id")
    g.add_argument("--run-dir")
    ap.add_argument("--archive", default=None)
    a = ap.parse_args(argv)
    archive = Path(a.archive) if a.archive else archive_root_for(ROOT)
    receipt, src = (None, None)
    if a.run_id:
        receipt, src = find_receipt(a.run_id, ROOT, archive)
        if receipt is None:
            raise SystemExit(f"HALT: no receipt for run {a.run_id} in the registry or the archive")
        if "run_dir" not in receipt:
            raise SystemExit(f"HALT: the receipt for run {a.run_id} predates D262 (no run_dir); "
                             "a full-record restore is not possible — use --run-dir")
        run_dir = ROOT / receipt["run_dir"]
    else:
        run_dir = Path(a.run_dir)
    restored, unavailable, bad = restore(run_dir, archive, receipt=receipt, root=ROOT)
    print(f"Archive: {archive}" + (f"  (receipt from the {src})" if src else ""))
    print(f"Restored {len(restored)} file(s):")
    for r in restored:
        print(f"  {r}")
    if unavailable:
        print(f"UNAVAILABLE in the archive: {unavailable}")
    status = receipt_status(receipt["run_id"], ROOT) if receipt else None
    if bad:
        print("verify_bundle: FAILED")
        for b in bad:
            print(f"  {b}")
    else:
        print("verify_bundle: clean")
    if status is not None:
        print(f"receipt_status: {status}")
    if bad or unavailable or (status is not None and status != "complete"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
