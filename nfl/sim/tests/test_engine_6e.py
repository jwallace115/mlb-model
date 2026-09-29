"""6E tests: live-play FD penalty; late-game reds."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed

SAMPLE = ROOT / "research" / "nfl_sim" / "phase5z_sample.txt"
N = 100


def _load():
    _load_tables()
    return _load_ratings()


def _run_sample(team_r, tend, sit, kicker, league, n_games=50):
    games = open(SAMPLE).read().strip().split("\n")[:n_games]
    results = []
    for g in games:
        parts = g.split("_")
        season, week, away, home = int(parts[0]), int(parts[1]), parts[2], parts[3]
        seed = stable_seed((home, away, season, week, 42))
        r = simulate_game(home, away, season, week, n_sims=N, seed=seed,
                          team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                          league=league)
        results.append(r)
    return results


def test_fd_penalty_within_tolerance():
    """6E: first downs by penalty per team within 0.3 of 1.73 (the K1 tolerance).
    On eng/6d the sim produced 1.27; the live-play FD penalty fix targets 1.73."""
    team_r, tend, sit, kicker, league = _load()
    results = _run_sample(team_r, tend, sit, kicker, league, n_games=50)
    fd_pen = np.mean([r["ev_fd_penalty"].mean() / 2 for r in results])
    assert abs(fd_pen - 1.73) < 0.30, (
        f"fd_pen/team {fd_pen:.3f} vs actual 1.73 (diff {abs(fd_pen - 1.73):.3f} > 0.30)")
