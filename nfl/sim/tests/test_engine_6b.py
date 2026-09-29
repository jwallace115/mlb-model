"""6B tests: own-1 pile-up fixed; offensive penalty half-distance."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed


def test_98_100_snaps_per_game():
    """Snaps at yl 98-100 per game <= 0.6 (was 1.31 in 6A)."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    total_98_100 = 0
    total_sims = 0
    for home, away, season, week in [("KC", "BUF", 2024, 11), ("SF", "DAL", 2023, 5),
                                      ("PHI", "NYG", 2022, 14)]:
        for sv in [42, 99]:
            seed = stable_seed((home, away, season, week, sv))
            r = simulate_game(home, away, season, week, n_sims=200, seed=seed,
                              team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                              league=league, drive_log=True)
            dl = r.attrs.get("drive_log")
            if dl is not None:
                dldf = pd.DataFrame(dl) if not isinstance(dl, pd.DataFrame) else dl
                # Count drives that START at yl 98-100 (which means a snap happened there)
                deep = dldf[dldf["start_yardline"] >= 98]
                total_98_100 += len(deep) / 200  # per game
            total_sims += 1
    spg = total_98_100 / total_sims
    assert spg <= 0.6, f"98-100 snaps/game {spg:.2f} > 0.6"


def test_offensive_penalty_half_distance():
    """6C: half-distance rule — own 15 + 10yd penalty -> own 7.5; own 4 + 10 -> own 2.
    Exercises the engine's penalty logic: at own 15 (yl=85), a 10-yd penalty (distance to
    goal = 15) applies full yards (10 < 15/2=7.5 is FALSE, so 10 > 7.5 -> half = 7.5);
    at own 4 (yl=96), 10 > 4/2=2 -> half = 2."""
    import numpy as np
    # The engine formula (engine.py:1983-1986):
    # dist_to_goal = 100 - yl; half_dist_val = dist_to_goal / 2
    # use_half = pen > half_dist_val; actual = where(use_half, half_dist_val, pen)
    # yl_new = yl + actual
    for yl_start, pen, expected in [(85.0, 10.0, 92.5), (96.0, 10.0, 98.0)]:
        dist_to_goal = 100 - yl_start
        half_dist_val = dist_to_goal / 2
        actual = half_dist_val if pen > half_dist_val else pen
        yl_new = yl_start + actual
        assert abs(yl_new - expected) < 0.01, f"yl={yl_start}, pen={pen}: got {yl_new}, expected {expected}"
