"""Tests for game_inputs.py (S40)."""
import copy, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.engine import simulate, league_average_inputs, TeamMultipliers
from nhl.sim.game_inputs import game_inputs_for, load_all


@pytest.fixture(scope="module")
def data():
    return load_all()


class TestAllOnesIsLeagueAverage:
    def test_all_multipliers_one(self, data):
        """All multipliers = 1 gives output identical to league_average_inputs."""
        tr, gr, ft, q = data
        base = league_average_inputs()
        inp = copy.deepcopy(base)
        inp.home = TeamMultipliers()  # all 1.0
        inp.away = TeamMultipliers()
        r1 = simulate(base, 100, seed=42)
        r2 = simulate(inp, 100, seed=42)
        for k in r1:
            assert np.array_equal(r1[k], r2[k]), f"{k} differs"


class TestStrongerTeamWins:
    def test_higher_att_wins_more(self, data):
        tr, gr, ft, q = data
        base = league_average_inputs()
        # Team with 1.1x attack
        strong = copy.deepcopy(base)
        strong.home = TeamMultipliers(ev_att_for=1.1)
        r_strong = simulate(strong, 10000, seed=99)
        r_base = simulate(base, 10000, seed=99)
        assert (r_strong["home_score"] > r_strong["away_score"]).mean() > (r_base["home_score"] > r_base["away_score"]).mean()


class TestDateMatch:
    def test_rating_date_matches_game(self, data):
        tr, gr, ft, q = data
        # Pick a game and verify the rating's date matches
        gid = "2022020100"
        h_row = tr[(tr["game_id"] == gid) & (tr["role"] == "home")]
        if len(h_row) == 0:
            pytest.skip("Game not in ratings")
        # The date on the rating row should match the game date
        import json
        bp = ROOT / "nhl" / "cache" / f"boxscore_{gid}.json"
        if bp.exists():
            with open(bp) as f:
                d = json.load(f)
            game_date = d.get("gameDate", "")
            assert h_row.iloc[0]["date"] == game_date, f"Rating date {h_row.iloc[0]['date']} != game date {game_date}"


class TestGoalieSaveDirection:
    """S49: a better HOME goalie must reduce AWAY goals, not HOME goals."""

    def test_good_home_goalie_reduces_away_goals(self, data):
        """Give the HOME goalie +0.02 gsax/att via the same goalie_ratings code path.
        20,000 sims: mean AWAY goals must fall >=10%, mean HOME goals must change <2%.
        Control: same game with league-average goalies (both 0.00)."""
        tr, gr, ft, q = data
        base = league_average_inputs()

        gid = "2022020100"
        # Control: both goalies league-average
        gr_ctrl = pd.DataFrame([
            {"game_id": gid, "role": "home", "gsax_per_att_rating": 0.00, "season": 2022},
            {"game_id": gid, "role": "away", "gsax_per_att_rating": 0.00, "season": 2022},
        ])
        # Test: home goalie = +0.02 gsax/att (a better goalie)
        gr_test = pd.DataFrame([
            {"game_id": gid, "role": "home", "gsax_per_att_rating": 0.02, "season": 2022},
            {"game_id": gid, "role": "away", "gsax_per_att_rating": 0.00, "season": 2022},
        ])

        inp_ctrl = game_inputs_for(gid, tr, gr_ctrl, ft, q, base)
        inp_test = game_inputs_for(gid, tr, gr_test, ft, q, base)

        r_ctrl = simulate(inp_ctrl, 20000, seed=77)
        r_test = simulate(inp_test, 20000, seed=77)

        ctrl_away = r_ctrl["away_score"].mean()
        ctrl_home = r_ctrl["home_score"].mean()
        test_away = r_test["away_score"].mean()
        test_home = r_test["home_score"].mean()

        away_drop = (ctrl_away - test_away) / ctrl_away
        home_change = abs(test_home - ctrl_home) / ctrl_home

        # A better HOME goalie should reduce AWAY goals by at least 10%
        assert away_drop >= 0.10, (
            f"AWAY goals should fall >=10% with a good HOME goalie, "
            f"but fell only {away_drop:.1%} (ctrl={ctrl_away:.3f}, test={test_away:.3f})")
        # HOME goals should barely change (< 2%)
        assert home_change < 0.02, (
            f"HOME goals should change <2% (goalie is on the other side), "
            f"but changed {home_change:.1%} (ctrl={ctrl_home:.3f}, test={test_home:.3f})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
