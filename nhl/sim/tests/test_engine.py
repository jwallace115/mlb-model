"""Tests for the NHL game engine (S32 tests kept; S34 tests added by Cowork)."""
import copy, re, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.engine import simulate, league_average_inputs, StartState, MINOR


@pytest.fixture(scope="module")
def inp():
    return league_average_inputs()


class TestDeterminism:
    def test_same_seed_identical(self, inp):
        r1, r2 = simulate(inp, 200, seed=42), simulate(inp, 200, seed=42)
        for k in r1:
            assert np.array_equal(r1[k], r2[k]), k


class TestStartState:
    def test_puck_drop_equals_none(self, inp):
        r1 = simulate(inp, 200, seed=42, start_state=None)
        r2 = simulate(inp, 200, seed=42, start_state=StartState())
        for k in r1:
            assert np.array_equal(r1[k], r2[k]), k


class TestOvertimeLogic:
    def test_tied_after_60_gets_ot_or_so(self, inp):
        r = simulate(inp, 5000, seed=123)
        tied = r["reg_home_score"] == r["reg_away_score"]
        assert tied.any() and np.isin(r["decided"][tied], ["OT", "SO"]).all()
        assert (r["decided"][~tied] == "REG").all()

    def test_ot_and_so_margin_is_one(self, inp):
        r = simulate(inp, 5000, seed=456)
        m = r["decided"] != "REG"
        assert (np.abs(r["home_score"] - r["away_score"])[m] == 1).all()

    def test_ot_penalty_gives_4v3(self, inp):
        """Start OT with an away minor: home is 4v3, so home scores first more often than away (and than 3v3)."""
        base = simulate(inp, 20000, seed=7, start_state=StartState(period=4, second=0, home_score=2, away_score=2))
        pp = simulate(inp, 20000, seed=7, start_state=StartState(period=4, second=0, home_score=2, away_score=2,
                                                                 away_penalties=[(MINOR, MINOR)]))
        ot_home = lambda r: ((r["decided"] == "OT") & (r["home_score"] > r["away_score"])).mean()
        assert ot_home(pp) > ot_home(base) + 0.03
        assert pp["home_pp_seconds"].mean() > 60


class TestPulledGoalie:
    def test_trailing_pulled_loses_more(self, inp):
        tied = simulate(inp, 10000, seed=789, start_state=StartState(period=3, second=1170, home_score=2, away_score=2))
        trail = simulate(inp, 10000, seed=789, start_state=StartState(period=3, second=1170, home_score=2, away_score=3, home_pulled=True))
        assert (trail["home_score"] > trail["away_score"]).mean() < (tied["home_score"] > tied["away_score"]).mean()

    def test_both_teams_pull(self, inp):
        """S34: the AWAY team must also pull when trailing late (S32 only let the home team pull)."""
        h = simulate(inp, 5000, seed=11, start_state=StartState(period=3, second=1080, home_score=1, away_score=2))
        a = simulate(inp, 5000, seed=11, start_state=StartState(period=3, second=1080, home_score=2, away_score=1))
        assert h["away_en_goals"].mean() > 0.05, "home trailing -> away should score empty-net goals"
        assert a["home_en_goals"].mean() > 0.05, "away trailing -> home should score empty-net goals"
        assert abs(h["away_en_goals"].mean() - a["home_en_goals"].mean()) < 0.04


class TestBlowout:
    def test_home_3_up_last_minute(self, inp):
        r = simulate(inp, 10000, seed=321, start_state=StartState(period=3, second=1140, home_score=5, away_score=2))
        assert (r["home_score"] > r["away_score"]).mean() > 0.99


class TestSymmetry:
    def test_neutral_site_is_fair(self, inp):
        """With the home effect removed the engine must be symmetric: home win 50% +- 1 pt (40k sims, SE 0.25 pt)."""
        z = copy.deepcopy(inp)
        z.home_att_mult = z.away_att_mult = z.home_q_mult = z.away_q_mult = 1.0
        r = simulate(z, 40000, seed=5)
        assert abs((r["home_score"] > r["away_score"]).mean() - 0.5) < 0.01


class TestPowerPlay:
    def test_pp_goal_ends_minor(self, inp):
        """Home 5v4 with a fresh away minor and a forced goal chance: PP seconds must stop at the goal."""
        z = copy.deepcopy(inp)
        z.goal_per_att = {k: (1.0 if k == (5, 4) else 0.0) for k in z.goal_per_att}
        z.att_per_sec = {k: (0.05 if k == (5, 4) else v) for k, v in z.att_per_sec.items()}   # ~100% shot within 120 s
        z.ea_goal_per_att = z.en_goal_per_att = 0.0
        z.pp_pen_per_sec = 0.0
        r = simulate(z, 2000, seed=9, start_state=StartState(period=1, second=0, away_penalties=[(MINOR, MINOR)]))
        assert (r["home_pp_goals"] >= 1).mean() > 0.99
        assert (r["home_pp_goals"] <= 1).all(), "one minor -> at most one PP goal"
        assert r["home_pp_seconds"].mean() < 0.5 * MINOR


class TestNoLiteralRates:
    def test_no_rate_literals(self):
        src = (ROOT / "nhl" / "sim" / "engine.py").read_text()
        assert ".get(" not in src.split("def league_average_inputs")[1].split("def ")[0], "league_average_inputs must not use .get defaults"
