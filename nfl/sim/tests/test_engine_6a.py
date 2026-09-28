"""6A tests: timeout_followed cell used for stop_code; kneel uses measured table."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed


def test_timeout_followed_cell_used():
    """A stop_code play should draw from timeout_followed, not incomplete.
    Verify by checking the play_log has timeout_followed events."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    seed = stable_seed(("KC", "BUF", 2024, 11, 42))
    r = simulate_game("KC", "BUF", 2024, 11, n_sims=200, seed=seed,
                      team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    pl = r.attrs.get("play_log")
    assert pl is not None and len(pl) > 0
    # The play_log should have "timeout_followed" events if timeouts are called
    to_events = pl[pl["event_class"] == "timeout_followed"]
    # At least some timeout_followed events expected (timeouts are ~2.2/game)
    # With 200 sims, we should see many
    assert len(to_events) > 0, "No timeout_followed events in play_log"


def test_kneel_uses_measured_table():
    """Kneel runoff should draw from the 'kneel' cell, not 'complete_inbounds'.
    Verify by checking the play_log kneel events have elapsed > 25 s on average
    (the measured kneel is ~32 s vs the old ~20 s)."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    seed = stable_seed(("KC", "BUF", 2024, 11, 42))
    r = simulate_game("KC", "BUF", 2024, 11, n_sims=200, seed=seed,
                      team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    pl = r.attrs.get("play_log")
    assert pl is not None
    kneels = pl[pl["event_class"] == "kneel"]
    if len(kneels) > 10:
        mean_el = kneels["elapsed"].mean()
        assert mean_el > 25.0, (
            f"Kneel mean elapsed {mean_el:.1f}s < 25: still using old complete_inbounds cell"
        )
