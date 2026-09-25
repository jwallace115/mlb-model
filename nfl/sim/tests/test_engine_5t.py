"""5T tests: INT chain log records correct LOS (no stale values)."""
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
def int_chain_data():
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


def test_int_los_not_stale(int_chain_data):
    """INT LOS must never be 0.0 (stale from initialisation) and must be
    in the valid field range [1, 99]."""
    df = int_chain_data
    assert len(df) > 100, f"Too few INT events: {len(df)}"
    assert (df["los"] > 0).all(), f"Stale LOS (0.0) found in {(df['los'] == 0).sum()} INTs"
    assert (df["los"] >= 1).all() and (df["los"] <= 99).all(), "LOS out of range [1,99]"


def test_int_air_non_negative(int_chain_data):
    """Air yards drawn must be non-negative (table clips to 0)."""
    df = int_chain_data
    non_six = df[~df["six"]]
    assert (non_six["air"] >= 0).all(), "Negative air_yards found"
