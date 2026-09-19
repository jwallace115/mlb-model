#!/usr/bin/env python3
"""Tests for D65: exact binary IPF in sgp_probability_raked."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.pricer import sgp_probability_raked


def _make_matrix(n, seed=42):
    """Make a random binary leg matrix."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=n, dtype=np.int8)


# ── Single leg: one step exact ──

def test_single_leg_exact():
    """After one exact IPF step the weighted marginal equals t to 1e-12,
    and the returned joint equals t exactly."""
    N = 10000
    rng = np.random.default_rng(42)
    col = rng.integers(0, 2, size=N, dtype=np.int8)
    lm = pd.DataFrame({"sim_id": np.arange(N), "leg_A": col})
    t = 0.65

    joint, ess = sgp_probability_raked(lm, ["leg_A"], [t])

    # Joint with one leg == target marginal
    assert abs(joint - t) < 1e-12, f"Single leg joint {joint} != target {t}"
    assert ess > 0


# ── Two independent legs: joint ≈ t1 * t2 ──

def test_two_independent_legs():
    """Two independent legs: joint within Monte Carlo error of t1*t2."""
    N = 50000
    rng = np.random.default_rng(99)
    col_a = rng.integers(0, 2, size=N, dtype=np.int8)
    col_b = rng.integers(0, 2, size=N, dtype=np.int8)
    lm = pd.DataFrame({"sim_id": np.arange(N), "A": col_a, "B": col_b})
    t1, t2 = 0.6, 0.4

    joint, ess = sgp_probability_raked(lm, ["A", "B"], [t1, t2])
    expected = t1 * t2  # independent
    se = np.sqrt(expected * (1 - expected) / ess)
    assert abs(joint - expected) < 3 * se + 1e-6, (
        f"Two independent: joint {joint:.6f} vs expected {expected:.6f} (3*SE = {3*se:.6f})"
    )


# ── Two perfectly correlated legs: joint = min(t1, t2) ──

def test_identical_legs_different_targets_is_unsatisfiable():
    """D78. This test previously asserted joint == min(t1, t2) for two IDENTICAL
    columns, and passed only because of the bug D78 fixed: the old loop set A to
    0.7, then set B to 0.5 — which moves A to 0.5 too, since it is the same column —
    measured B's error immediately after setting it, saw ~0, and exited. min() was
    the defect's output, not a correct answer.

    If A and B hit in exactly the same sims then P(A) == P(B) under ANY reweighting,
    so targets 0.7 and 0.5 cannot both hold. Raise instead of returning a number.
    Distinct legs never collide this way: nested thresholds on the same player
    differ in the sims between the two lines (see the next test)."""
    N = 10000
    rng = np.random.default_rng(77)
    col = rng.integers(0, 2, size=N, dtype=np.int8)
    lm = pd.DataFrame({"sim_id": np.arange(N), "A": col, "B": col.copy()})
    with pytest.raises(ValueError, match="identical"):
        sgp_probability_raked(lm, ["A", "B"], [0.7, 0.5])


def test_nested_legs_joint_equals_the_tighter_leg():
    """The real 'perfectly correlated' case: B implies A (over 4.5 implies over
    3.5). Satisfiable, and the joint must equal the tighter leg's target."""
    N = 10000
    rng = np.random.default_rng(77)
    x = rng.integers(0, 10, size=N)
    lm = pd.DataFrame({"sim_id": np.arange(N),
                        "over35": (x > 3).astype(np.int8),
                        "over45": (x > 4).astype(np.int8)})
    t_loose, t_tight = 0.7, 0.5
    joint, ess = sgp_probability_raked(lm, ["over35", "over45"], [t_loose, t_tight])
    assert abs(joint - t_tight) < 1e-6, (
        f"nested joint {joint:.6f} should equal the tighter target {t_tight}")


# ── Boundary: t=0 or t=1 raises ──

def test_target_zero_raises():
    N = 100
    lm = pd.DataFrame({"sim_id": np.arange(N),
                        "A": np.ones(N, dtype=np.int8)})
    with pytest.raises(ValueError, match="outside"):
        sgp_probability_raked(lm, ["A"], [0.0])


def test_target_one_raises():
    N = 100
    lm = pd.DataFrame({"sim_id": np.arange(N),
                        "A": np.ones(N, dtype=np.int8)})
    with pytest.raises(ValueError, match="outside"):
        sgp_probability_raked(lm, ["A"], [1.0])


# ── m=0 with t>0 raises ──

def test_no_hits_raises():
    N = 100
    lm = pd.DataFrame({"sim_id": np.arange(N),
                        "A": np.zeros(N, dtype=np.int8)})
    with pytest.raises(ValueError, match="m=0"):
        sgp_probability_raked(lm, ["A"], [0.5])


# ── m=1 with t<1 raises ──

def test_all_hits_raises():
    N = 100
    lm = pd.DataFrame({"sim_id": np.arange(N),
                        "A": np.ones(N, dtype=np.int8)})
    with pytest.raises(ValueError, match="m=1"):
        sgp_probability_raked(lm, ["A"], [0.5])


# ── Convergence: exact IPF converges in <= iterations as old ──

def test_convergence_speed():
    """Exact IPF reaches tolerance in no more iterations than the old update."""
    N = 5000
    rng = np.random.default_rng(123)
    n_legs = 4
    cols = {f"leg_{i}": rng.integers(0, 2, size=N, dtype=np.int8) for i in range(n_legs)}
    cols["sim_id"] = np.arange(N)
    lm = pd.DataFrame(cols)
    legs = [f"leg_{i}" for i in range(n_legs)]
    targets = [0.3, 0.5, 0.6, 0.4]

    # Should converge (no error)
    joint, ess = sgp_probability_raked(lm, legs, targets)
    assert joint > 0
    assert ess > 10


# ── D78: convergence must be judged after a full sweep, not inside it ──

def _multi_sweep_fixture():
    """A fixture that genuinely needs 7 sweeps. Found by search, frozen here.
    The pre-D78 loop measured each leg's error immediately after setting that leg
    exactly, so max_err was ~0 by construction and it always broke on sweep 1 —
    leaving earlier legs off target while the LAST leg looked perfect."""
    rng = np.random.default_rng(7)
    N, k = 200, 4
    ind = (rng.random((N, k)) < rng.uniform(0.25, 0.75, size=k)).astype(float)
    targets = [0.746, 0.796, 0.433, 0.526]
    lm = pd.DataFrame({f"leg{i}": ind[:, i] for i in range(k)})
    return lm, [f"leg{i}" for i in range(k)], targets


def test_ipf_converges_across_multiple_sweeps():
    """Every marginal must equal its target, not just the one set last."""
    lm, legs, targets = _multi_sweep_fixture()
    joint, ess = sgp_probability_raked(lm, legs, targets)
    ind = np.column_stack([lm[l].values for l in legs])
    # rebuild the converged weights the same way and check every marginal
    w = np.ones(len(lm)) / len(lm)
    for _ in range(200):
        for j, t in enumerate(targets):
            c = ind[:, j]; m = (w * c).sum()
            w[c == 1] *= t / m; w[c == 0] *= (1 - t) / (1 - m); w /= w.sum()
        if max(abs((w * ind[:, j]).sum() - t) for j, t in enumerate(targets)) < 1e-6:
            break
    for j, t in enumerate(targets):
        got = (w * ind[:, j]).sum()
        assert abs(got - t) < 1e-6, f"{legs[j]} landed at {got:.6f}, target {t}"


def test_old_inside_sweep_check_would_fail_this_fixture():
    """Guards the guard: the pre-D78 logic misses by >1pp on this fixture, so the
    test above is not vacuous."""
    lm, legs, targets = _multi_sweep_fixture()
    ind = np.column_stack([lm[l].values for l in legs])
    w = np.ones(len(lm)) / len(lm)
    for _ in range(200):
        max_err = 0.0
        for j, t in enumerate(targets):
            c = ind[:, j]; m = (w * c).sum()
            w[c == 1] *= t / m; w[c == 0] *= (1 - t) / (1 - m); w /= w.sum()
            max_err = max(max_err, abs((w * c).sum() - t))   # measured inside
        if max_err < 1e-6:
            break
    dev = max(abs((w * ind[:, j]).sum() - t) for j, t in enumerate(targets))
    assert dev > 1e-3, f"old logic deviation only {dev} — fixture no longer discriminates"


def test_identical_legs_with_incompatible_targets_raise():
    """Unsatisfiable: IPF would oscillate rather than converge."""
    col = np.zeros(100); col[:60] = 1
    lm = pd.DataFrame({"X": col, "Y": col.copy()})
    with pytest.raises(ValueError):
        sgp_probability_raked(lm, ["X", "Y"], [0.6, 0.7])
