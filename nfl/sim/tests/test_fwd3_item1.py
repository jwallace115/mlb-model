"""D242: tests for the anchor state the solver returned.

The sidecar must record the values run_anchored_chunked RETURNS, not
the minimum-error iteration from the log.

Every test calls the real function and must FAIL on 0792fd122.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_sidecar_uses_solver_return_not_min_error():
    """Audit #7 A5 counterexample: the solver returns iteration 2, converged,
    -0.7 / 39.3 against targets 0 / 40. The sidecar must record iteration 2,
    anchored=True.

    On 0792fd122 the sidecar picks iteration 1 (-1.1 / 40) from min |err_m|+|err_t|
    and classifies the game unanchored (miss_m = 1.1 > 1.0).
    """
    from nfl.sim.run_forward_v1 import anchor_sidecar, ANCHOR_MISS_TOL

    # Anchoring log: two iterations
    # Iter 0: margin=-2.0, total=38.0, err_m=2.0, err_t=2.0 (not converged)
    # Iter 1: margin=-1.1, total=40.0, err_m=1.1, err_t=0.0 (not converged; |err_m|+|err_t|=1.1)
    # Iter 2: margin=-0.7, total=39.3, err_m=0.7, err_t=0.7 (converged; |err_m|+|err_t|=1.4)
    #
    # Min-error picks iter 1 (1.1 < 1.4), but the SOLVER returned iter 2 (converged).
    anch_log = pd.DataFrame([
        {"game": "A@B", "iter": 0, "margin": -2.0, "total": 38.0,
         "err_m": 2.0, "err_t": 2.0, "converged": False},
        {"game": "A@B", "iter": 1, "margin": -1.1, "total": 40.0,
         "err_m": 1.1, "err_t": 0.0, "converged": False},
        {"game": "A@B", "iter": 2, "margin": -0.7, "total": 39.3,
         "err_m": 0.7, "err_t": 0.7, "converged": True},
    ])

    # D242: anchor_returned records what the solver actually returned
    anchor_returned = pd.DataFrame([{
        "game": "A@B",
        "iterations": 3,  # ran 3 iterations (0, 1, 2)
        "converged": True,
        "anch_m": -0.7,
        "anch_t": 39.3,
        "target_spread": 0.0,
        "target_total": 40.0,
    }])

    lines = {"A@B": {"spread": 0.0, "total": 40.0}}

    sidecar = anchor_sidecar(anch_log, lines, anchor_returned_df=anchor_returned)
    row = sidecar.iloc[0]

    # The solver returned iteration 2, converged, -0.7 / 39.3
    assert row["iterations"] == 3, f"iterations should be 3, got {row['iterations']}"
    assert row["converged"] == True, f"converged should be True, got {row['converged']}"
    assert abs(row["anch_m"] - (-0.7)) < 0.01, f"anch_m should be -0.7, got {row['anch_m']}"
    assert abs(row["anch_t"] - 39.3) < 0.01, f"anch_t should be 39.3, got {row['anch_t']}"
    # miss_m = |-0.7 - 0| = 0.7, miss_t = |39.3 - 40| = 0.7
    # Both <= ANCHOR_MISS_TOL (1.0), so anchored = True
    assert row["anchored"] == True, (
        f"anchored should be True (miss_m={row['miss_m']}, miss_t={row['miss_t']}), "
        f"got {row['anchored']}")


def test_old_sidecar_picks_wrong_iteration():
    """Verify that the OLD (legacy) sidecar path picks the WRONG iteration
    for the controlled-batch counterexample. This proves the test catches
    the 0792fd122 behaviour."""
    from nfl.sim.run_forward_v1 import anchor_sidecar

    anch_log = pd.DataFrame([
        {"game": "A@B", "iter": 0, "margin": -2.0, "total": 38.0,
         "err_m": 2.0, "err_t": 2.0, "converged": False},
        {"game": "A@B", "iter": 1, "margin": -1.1, "total": 40.0,
         "err_m": 1.1, "err_t": 0.0, "converged": False},
        {"game": "A@B", "iter": 2, "margin": -0.7, "total": 39.3,
         "err_m": 0.7, "err_t": 0.7, "converged": True},
    ])
    lines = {"A@B": {"spread": 0.0, "total": 40.0}}

    # Legacy path: no anchor_returned_df
    sidecar = anchor_sidecar(anch_log, lines, anchor_returned_df=None)
    row = sidecar.iloc[0]

    # The legacy path picks min |err_m|+|err_t| = iter 1
    assert row["iterations"] == 2, f"legacy picks iter 1 (iterations=2), got {row['iterations']}"
    # miss_m = |-1.1 - 0| = 1.1 > 1.0, so anchored = False
    assert row["anchored"] == False, (
        f"legacy should classify as unanchored, got anchored={row['anchored']}")


def test_sidecar_forced_anchored_mutation_caught():
    """Mutation from audit #7 section D (test_fwd2_anchor.py): every sidecar row
    forced to anchored=True. This test catches it because the solver returned
    values show miss > ANCHOR_MISS_TOL."""
    from nfl.sim.run_forward_v1 import anchor_sidecar, ANCHOR_MISS_TOL

    # Solver returned values where miss > tolerance
    anchor_returned = pd.DataFrame([{
        "game": "A@B",
        "iterations": 5,
        "converged": False,
        "anch_m": 3.5,  # target 0 -> miss = 3.5 >> 1.0
        "anch_t": 45.0,  # target 40 -> miss = 5.0 >> 1.0
        "target_spread": 0.0,
        "target_total": 40.0,
    }])
    lines = {"A@B": {"spread": 0.0, "total": 40.0}}
    anch_log = pd.DataFrame([{
        "game": "A@B", "iter": 0, "margin": 3.5, "total": 45.0,
        "err_m": -3.5, "err_t": -5.0, "converged": False,
    }])

    sidecar = anchor_sidecar(anch_log, lines, anchor_returned_df=anchor_returned)
    row = sidecar.iloc[0]
    assert row["anchored"] == False, (
        f"miss_m=3.5, miss_t=5.0 -> must be unanchored, got {row['anchored']}")
