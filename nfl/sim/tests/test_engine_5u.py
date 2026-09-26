"""5U tests: non-six ez share matches the table's weighted rate within 2pp."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed

GAMES = [("KC", "BUF", 2024, 11), ("SF", "DAL", 2023, 5), ("PHI", "NYG", 2022, 14)]


@pytest.fixture(scope="module")
def int_chain():
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    all_int = []
    for home, away, season, week in GAMES:
        for sv in [42, 99]:
            seed = stable_seed((home, away, season, week, sv))
            r = simulate_game(home, away, season, week, n_sims=200, seed=seed,
                              team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                              league=league, drive_log=True)
            icl = r.attrs.get("int_chain_log")
            if icl is not None and len(icl) > 0:
                all_int.append(icl)
    return pd.concat(all_int, ignore_index=True) if all_int else pd.DataFrame()


def test_ez_share_matches_table(int_chain):
    """Non-six ez share should be within 2pp of the table's weighted rate (~12.15%)."""
    df = int_chain
    non_six = df[~df["six"]]
    assert len(non_six) > 100, f"Too few non-six INTs: {len(non_six)}"
    sim_ez_share = non_six["ez"].mean()
    # Table's weighted rate is 12.15% (from PBP 2021-24 non-six)
    assert abs(sim_ez_share - 0.1215) < 0.02, (
        f"Non-six ez share {sim_ez_share:.3f} vs table 0.1215 (diff {abs(sim_ez_share - 0.1215):.3f} > 0.02)"
    )


def test_int_count_unchanged(int_chain):
    """INT count per game must be within 0.3 of typical ~1.6."""
    n_games = len(GAMES) * 2 * 200
    int_pg = len(int_chain) / n_games
    assert abs(int_pg - 1.6) < 0.3, f"INT/game {int_pg:.2f} too far from ~1.6"
