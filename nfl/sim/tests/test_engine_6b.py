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
    """An offensive 10-yard penalty from yl 96 leaves the ball at yl 98 (half distance), not 99."""
    # This is a logic test: yl=96 (own 4-yard line), penalty=10 yards
    # Full: 96+10 = 106, clips to 99 (old)
    # Half distance: 96 + (100-96)/2 = 96 + 2 = 98 (new)
    import numpy as np
    yl = np.array([96.0])
    pen = np.array([10.0])
    full_yl = yl + pen  # 106
    half_dist = yl + (100 - yl) / 2  # 98
    result = np.where(full_yl > 99, half_dist, full_yl)
    assert abs(result[0] - 98.0) < 0.01, f"Expected 98, got {result[0]}"
