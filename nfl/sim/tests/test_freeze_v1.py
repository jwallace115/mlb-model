"""FREEZE v1: verify engine fingerprint and table hashes match the frozen state."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FREEZE_PATH = ROOT / "research" / "nfl_sim" / "FREEZE_v1.json"
TABLES_DIR = ROOT / "nfl" / "data" / "sim" / "tables"


def _load_freeze():
    with open(FREEZE_PATH) as f:
        return json.load(f)


def test_engine_fingerprint():
    """The engine fingerprint must match FREEZE_v1."""
    from nfl.sim.calibration import engine_fingerprint
    from nfl.sim.engine import _load_tables, _load_ratings
    _load_tables()
    _load_ratings()
    fp = engine_fingerprint()
    freeze = _load_freeze()
    assert fp == freeze["engine_fingerprint"], (
        f"Engine FP {fp} != frozen {freeze['engine_fingerprint']}")


def test_table_hashes():
    """Every table file hash must match FREEZE_v1."""
    freeze = _load_freeze()
    for name, expected_hash in freeze["table_hashes"].items():
        p = TABLES_DIR / name
        assert p.exists(), f"Missing table file: {name}"
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        assert h == expected_hash, f"Table {name}: {h} != frozen {expected_hash}"


def test_calibration_hash():
    """Calibration file hash must match FREEZE_v1."""
    freeze = _load_freeze()
    p = ROOT / "nfl" / "sim" / "calibration_v1.json"
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    assert h == freeze["calibration_hash"], (
        f"Calibration: {h} != frozen {freeze['calibration_hash']}")


def test_params_hash():
    """Params file hash must match FREEZE_v1."""
    freeze = _load_freeze()
    p = ROOT / "nfl" / "sim" / "params_v1.json"
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    assert h == freeze["params_hash"], (
        f"Params: {h} != frozen {freeze['params_hash']}")
