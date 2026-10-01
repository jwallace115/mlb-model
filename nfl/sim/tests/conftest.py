"""Test-only settings for nfl/sim/tests (not part of the experiment manifest).

D266: a primary freeze refuses to run outside nfl/sim/fwd_bootstrap.py. In-process tests
that exercise live (non-pilot) freezes turn that requirement off here; the requirement
itself is tested with it ON (test_fwd6d.test_primary_freeze_requires_the_bootstrap), and
bootstrapped processes are tested as real subprocesses."""
import pytest


@pytest.fixture(autouse=True)
def _in_process_live_freezes_allowed(monkeypatch):
    import nfl.sim.run_forward_v1 as fwd
    monkeypatch.setattr(fwd, "REQUIRE_LAUNCHER", False)
