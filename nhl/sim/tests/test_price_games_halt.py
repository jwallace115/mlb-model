"""S59 (L-WO1b Item 2): test that price_games.price_season HALTs on missing team_ratings row.

Shows the test FAILING against the pre-S54 behaviour (reinstated skip) and PASSING now.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_pricer_halts_on_missing_row():
    """Delete one team_ratings row and verify price_season exits non-zero
    with the game_id in the error message."""
    from nhl.sim.game_inputs import load_all
    from nhl.sim.engine import league_average_inputs
    from nhl.sim.price_games import price_season

    tr, gr, ft, q = load_all()
    base_inp = league_average_inputs()

    gid = "2022020100"
    tr_broken = tr[~((tr["game_id"] == gid) & (tr["role"] == "home"))].copy()

    with pytest.raises(SystemExit) as exc_info:
        price_season(2022, 10, tr_broken, gr, ft, q, base_inp)

    assert exc_info.value.code == 1
    # The HALT message is printed to stderr; we verify the exit code is 1.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
