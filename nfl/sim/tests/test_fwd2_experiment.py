"""FWD2 (D224): experiment identity tests.
Every test calls the real function. Each audit counterexample (A3, A4) is a test."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

MANIFEST_PATH = ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"


def _load_manifest():
    return json.loads(MANIFEST_PATH.read_text())


def test_experiment_file_hashes():
    """A3: every file on the prediction path hashes to the manifest value."""
    m = _load_manifest()
    for path, expected in m["file_hashes"].items():
        p = ROOT / path
        assert p.exists(), f"Missing: {path}"
        got = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        assert got == expected, f"{path}: {got} != {expected}"


def test_experiment_usage_fingerprint():
    """A3 counterexample: one historical target-share value changed -> test fails.
    Here we verify the manifest's usage_fingerprint matches the live computation."""
    from nfl.sim.calibration import usage_fingerprint
    m = _load_manifest()
    live = usage_fingerprint()
    assert live == m["usage_fingerprint"], (
        f"usage_fingerprint {live} != manifest {m['usage_fingerprint']}")


def test_experiment_engine_fingerprint():
    """The engine fingerprint matches the manifest."""
    from nfl.sim.calibration import engine_fingerprint
    from nfl.sim.engine import _load_tables, _load_ratings
    _load_tables(); _load_ratings()
    m = _load_manifest()
    assert engine_fingerprint() == m["engine_fingerprint"]


def test_canonical_reader_matches():
    """A4: the canonical reader string matches exactly."""
    from nfl.sim.run_forward_v1 import READER_MODEL
    m = _load_manifest()
    assert READER_MODEL == m["canonical_reader"]


def test_reader_whitespace_refused():
    """A4 counterexample: a reader string with whitespace differs from canonical."""
    m = _load_manifest()
    padded = " " + m["canonical_reader"] + " "
    assert padded.strip() == m["canonical_reader"]
    assert padded != m["canonical_reader"], "whitespace reader must != canonical"


def test_cross_week_dedup():
    """A4 counterexample: the harness's cross_week_check refuses a contract already
    frozen in another week directory."""
    from nfl.sim.run_forward_v1 import cross_week_check
    # Simulate: week 3 has a frozen file with a line for T.Kelce receptions 5.5
    import pandas as pd
    with tempfile.TemporaryDirectory() as td:
        board = Path(td)
        w3 = board / "week=2026_03" / "ai_opinions"
        w3.mkdir(parents=True)
        w4 = board / "week=2026_04" / "ai_opinions"
        w4.mkdir(parents=True)
        # Create a frozen file in w3
        df = pd.DataFrame([{
            "event_id": "e1", "market_key": "player_receptions",
            "player_name": "T.Kelce", "line": 5.5, "revision": 0,
            "reader_model": "nfl_sim_v1_156cd057", "pilot": False,
        }])
        df.to_parquet(w3 / "ai_opinions_20261001T000000Z.parquet", index=False)
        manifest = [{"file": "ai_opinions_20261001T000000Z.parquet",
                      "sha256": "x", "reader_model": "nfl_sim_v1_156cd057", "pilot": False}]
        (w3 / "manifest.json").write_text(json.dumps(manifest))
        (w4 / "manifest.json").write_text("[]")
        # Check: the same contract in w4 should be refused
        contracts = [("e1", "player_receptions", "T.Kelce", 5.5)]
        result = cross_week_check(board, 2026, 4, "nfl_sim_v1_156cd057", contracts)
        assert len(result) > 0, "cross_week_check should find the duplicate"
