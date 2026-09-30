"""D226: tests for the anchor sidecar with actual market targets.

Every test calls the real function and fails on 9eb505235.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_anchor_sidecar_actual_targets():
    """A6: CAR@ATL targets must be -3.0/43.5 from the actual lines, not the
    reconstructed -3.2572/43.9996 that the old fallback produced.

    On 9eb505235, anchor_sidecar accepted lines={} and used the fallback
    anch_m - err_m, which gives the wrong targets.
    """
    from nfl.sim.run_forward_v1 import anchor_sidecar

    anch_log_path = ROOT / "nfl" / "data" / "sim" / "outputs" / "week=2026_02" / "anchoring_log.parquet"
    if not anch_log_path.exists():
        pytest.skip("week=2026_02 anchoring_log.parquet not available")

    anch_log = pd.read_parquet(anch_log_path)

    # Provide the ACTUAL market lines that run_week used for week 2
    lines = {"CAR@ATL": {"spread": -3.0, "total": 43.5}}
    # Only test CAR@ATL
    car_log = anch_log[anch_log["game"] == "CAR@ATL"]
    if car_log.empty:
        pytest.skip("CAR@ATL not in anchoring log")

    sidecar = anchor_sidecar(car_log, lines)
    row = sidecar[sidecar["game"] == "CAR@ATL"].iloc[0]

    assert row["target_spread"] == -3.0, (
        f"target_spread should be -3.0 (actual), got {row['target_spread']}")
    assert row["target_total"] == 43.5, (
        f"target_total should be 43.5 (actual), got {row['target_total']}")


def test_anchor_sidecar_halts_without_lines():
    """D226: anchor_sidecar must HALT (not silently fall back) when lines are missing."""
    from nfl.sim.run_forward_v1 import anchor_sidecar

    anch_log = pd.DataFrame([{
        "game": "CAR@ATL", "iter": 0, "margin": 1.5,
        "total": 50.0, "err_m": -4.5, "err_t": -6.5,
        "converged": False,
    }])

    # Empty lines dict must raise, not silently reconstruct
    with pytest.raises(SystemExit, match="no lines entry"):
        anchor_sidecar(anch_log, {})


def test_anchor_sidecar_column_names():
    """D226: sidecar uses target_spread/target_total (not spread/total_line).
    D229: replaced inspect.getsource with execution test."""
    from nfl.sim.run_forward_v1 import anchor_sidecar

    anch_log = pd.DataFrame([{
        "game": "CAR@KC", "iter": 0, "margin": -3.1,
        "total": 45.6, "err_m": -0.1, "err_t": 0.1, "converged": True,
    }])
    lines = {"CAR@KC": {"spread": -3.0, "total": 45.5}}
    sidecar = anchor_sidecar(anch_log, lines)
    assert "target_spread" in sidecar.columns, "sidecar must have target_spread column"
    assert "target_total" in sidecar.columns, "sidecar must have target_total column"
    assert sidecar.iloc[0]["target_spread"] == -3.0
    assert sidecar.iloc[0]["target_total"] == 45.5
