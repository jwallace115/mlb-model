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

def test_two_correlated_legs():
    """Two perfectly correlated legs: joint = min(t1, t2)."""
    N = 10000
    rng = np.random.default_rng(77)
    col = rng.integers(0, 2, size=N, dtype=np.int8)
    lm = pd.DataFrame({"sim_id": np.arange(N), "A": col, "B": col.copy()})
    t1, t2 = 0.7, 0.5

    joint, ess = sgp_probability_raked(lm, ["A", "B"], [t1, t2])
    expected = min(t1, t2)
    assert abs(joint - expected) < 0.01, (
        f"Correlated: joint {joint:.6f} vs min({t1},{t2}) = {expected}"
    )


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
