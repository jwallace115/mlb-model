"""Tests for the NHL game simulation engine."""
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.engine import simulate, league_average_inputs, StartState


@pytest.fixture(scope="module")
def inp():
    return league_average_inputs()


class TestDeterminism:
    def test_same_seed_identical(self, inp):
        r1 = simulate(inp, 100, seed=42)
        r2 = simulate(inp, 100, seed=42)
        assert np.array_equal(r1["home_score"], r2["home_score"])
        assert np.array_equal(r1["away_score"], r2["away_score"])
        assert np.array_equal(r1["decided"], r2["decided"])


class TestStartState:
    def test_puck_drop_equals_none(self, inp):
        r1 = simulate(inp, 100, seed=42, start_state=None)
        r2 = simulate(inp, 100, seed=42, start_state=StartState())
        assert np.array_equal(r1["home_score"], r2["home_score"])
        assert np.array_equal(r1["decided"], r2["decided"])


class TestOvertimeLogic:
    def test_tied_after_60_gets_ot_or_so(self, inp):
        """A game tied after regulation always goes to OT or SO."""
        r = simulate(inp, 10000, seed=123)
        reg_tied = r["reg_home_score"] == r["reg_away_score"]
        if reg_tied.any():
            decided = r["decided"][reg_tied]
            assert all(d in ("OT", "SO") for d in decided), "Some tied games decided in REG"

    def test_no_goals_after_sudden_death(self, inp):
        """No goals should be scored after a sudden-death OT goal."""
        # This is structurally guaranteed by the engine's ot_mask logic
        r = simulate(inp, 1000, seed=456)
        ot_games = r["decided"] == "OT"
        if ot_games.any():
            # OT games should have exactly 1 goal difference in final score
            diff = np.abs(r["home_score"][ot_games] - r["away_score"][ot_games])
            assert (diff == 1).all(), f"OT games have score diff != 1: {diff[diff != 1]}"


class TestPulledGoalie:
    def test_trailing_pulled_loses_more(self, inp):
        """Trailing by 1 with 30s left and goalie pulled wins less often than tied."""
        N = 10000
        # Tied with 30s left
        ss_tied = StartState(period=3, second=1170, home_score=2, away_score=2)
        r_tied = simulate(inp, N, seed=789, start_state=ss_tied)
        # Trailing by 1 with 30s left, goalie pulled
        ss_trail = StartState(period=3, second=1170, home_score=2, away_score=3, home_pulled=True)
        r_trail = simulate(inp, N, seed=789, start_state=ss_trail)

        tied_win = (r_tied["home_score"] > r_tied["away_score"]).mean()
        trail_win = (r_trail["home_score"] > r_trail["away_score"]).mean()
        assert trail_win < tied_win, f"Trailing+pulled should win less: {trail_win:.3f} vs tied {tied_win:.3f}"


class TestBlowout:
    def test_home_3_up_last_minute(self, inp):
        """Home ahead by 3 with 1:00 left wins > 99%."""
        ss = StartState(period=3, second=1140, home_score=5, away_score=2)
        r = simulate(inp, 10000, seed=321, start_state=ss)
        win_pct = (r["home_score"] > r["away_score"]).mean()
        assert win_pct > 0.99, f"Home +3 last minute should win >99%: {win_pct:.4f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
