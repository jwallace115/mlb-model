"""Tests for game_inputs.py (S40)."""
import copy, sys
from pathlib import Path
import numpy as np
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
