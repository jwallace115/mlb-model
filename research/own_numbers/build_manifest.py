#!/usr/bin/env python3
"""
ON-D7: Build FROZEN_MANIFEST_v2.json.

SHA256 of every code file in research/own_numbers/, engine.py, tables.py,
ratings.py, params_v1.json, hfa_v1.json, every table under nfl/data/sim/tables,
the calibration table, and engine_fingerprint().
"""
import os, sys, json, hashlib
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

ROOT = Path(os.path.dirname(__file__)).resolve().parent.parent

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest():
    manifest = {
        "version": 2,
        "description": "Frozen manifest for ON experiment — SHA256 of all code and data inputs",
        "fit_windows": {
            "mechanics": "2021-2024 (tables, params, HFA)",
            "ratings_params": "2021-2024 (half_life, k, prior_weight tuned on 2021-2024)",
            "calibration": "2021-2023 (ours_m - close variance from prior seasons)",
            "HFA": "2021-2023 (home margin measured on 815 REG games)",
        },
        "files": {},
    }

    # 1. Code files in research/own_numbers/
    on_dir = ROOT / "research" / "own_numbers"
    for p in sorted(on_dir.glob("*.py")):
        key = f"research/own_numbers/{p.name}"
        manifest["files"][key] = sha256_file(p)

    for p in sorted(on_dir.glob("*.md")):
        key = f"research/own_numbers/{p.name}"
        manifest["files"][key] = sha256_file(p)

    # 2. Engine core files
    engine_files = [
        "nfl/sim/engine.py",
        "nfl/sim/ratings.py",
        "nfl/sim/params_v1.json",
        "nfl/sim/hfa_v1.json",
    ]
    # tables.py — check if it exists
    tables_path = ROOT / "nfl" / "sim" / "tables.py"
    if tables_path.exists():
        engine_files.append("nfl/sim/tables.py")

    for rel in engine_files:
        p = ROOT / rel
        if p.exists():
            manifest["files"][rel] = sha256_file(p)
        else:
            manifest["files"][rel] = f"MISSING: {rel}"

    # 3. All tables under nfl/data/sim/tables
    tables_dir = ROOT / "nfl" / "data" / "sim" / "tables"
    for p in sorted(tables_dir.iterdir()):
        if p.is_file():
            key = f"nfl/data/sim/tables/{p.name}"
            manifest["files"][key] = sha256_file(p)

    # 4. Calibration table
    cal_path = ROOT / "nfl" / "data" / "own" / "calibration_table.parquet"
    if cal_path.exists():
        manifest["files"]["nfl/data/own/calibration_table.parquet"] = sha256_file(cal_path)

    # 5. Engine fingerprint
    try:
        from nfl.sim.calibration import engine_fingerprint
        manifest["engine_fingerprint"] = engine_fingerprint()
    except Exception as e:
        manifest["engine_fingerprint"] = f"ERROR: {e}"

    return manifest


if __name__ == "__main__":
    manifest = build_manifest()
    out_path = ROOT / "research" / "own_numbers" / "FROZEN_MANIFEST_v2.json"
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved: {out_path}")
    print(f"Files: {len(manifest['files'])}")
    print(f"Engine fingerprint: {manifest['engine_fingerprint']}")
