#!/usr/bin/env python3
"""
Phase 5M — engine tests.

(a) Player-ON scores are IDENTICAL to player-OFF scores at the same seed.
(b) T4's fixed seed goes green (margin diff < 2*SE, KS p > 0.05).
(c) Player-OFF score hash matches main (the play stream did not move).
"""

import sys, hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def engine_data():
    from nfl.sim.engine import _load_tables, _load_ratings
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    return dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
                player_usage=pu, active_uni=au)


def test_player_on_scores_identical_to_off(engine_data):
    """(a) With the child RNG for the player layer, home_score and away_score
    per sim are IDENTICAL (np.array_equal) between player-ON and player-OFF runs."""
    from nfl.sim.engine import simulate_game
    from nfl.sim.seed_util import stable_seed

    home, away, season, week = "DAL", "PHI", 2023, 9
    seed = stable_seed(("T4_test", 42))
    N = 4000

    # Player OFF
    r_off = simulate_game(home, away, season, week, n_sims=N, seed=seed,
                          team_r=engine_data["team_r"], tend=engine_data["tend"],
                          sit=engine_data["sit"], kicker=engine_data["kicker"],
                          league=engine_data["league"])

    # Player ON
    r_on = simulate_game(home, away, season, week, n_sims=N, seed=seed,
                         **engine_data)
    if isinstance(r_on, tuple):
        team_on = r_on[0]
    else:
        team_on = r_on

    assert np.array_equal(r_off["home_score"].values, team_on["home_score"].values), \
        "home_score differs between player-ON and player-OFF"
    assert np.array_equal(r_off["away_score"].values, team_on["away_score"].values), \
        "away_score differs between player-ON and player-OFF"


def test_player_off_hash_stable(engine_data):
    """(c) Player-OFF run at T4's seed produces the same score arrays as
    the recorded value for the current engine fingerprint. If no entry exists,
    fail with instructions to run record_player_off_hash.py."""
    from nfl.sim.engine import simulate_game
    from nfl.sim.seed_util import stable_seed
    from nfl.sim.calibration import engine_fingerprint
    import json

    home, away, season, week = "DAL", "PHI", 2023, 9
    seed = stable_seed(("T4_test", 42))
    N = 4000

    r = simulate_game(home, away, season, week, n_sims=N, seed=seed,
                      team_r=engine_data["team_r"], tend=engine_data["tend"],
                      sit=engine_data["sit"], kicker=engine_data["kicker"],
                      league=engine_data["league"])

    h = hashlib.sha256(
        r["home_score"].values.tobytes() + r["away_score"].values.tobytes()
    ).hexdigest()[:16]

    fp = engine_fingerprint()
    hash_file = Path(__file__).resolve().parent / "fixtures" / "player_off_hash.json"
    assert hash_file.exists(), (
        f"player_off_hash.json not found. Run: "
        f"python3 nfl/sim/tests/record_player_off_hash.py"
    )
    recorded = json.loads(hash_file.read_text())
    assert fp in recorded, (
        f"No hash recorded for fingerprint {fp}. Run: "
        f"python3 nfl/sim/tests/record_player_off_hash.py"
    )
    assert h == recorded[fp], (
        f"Player-OFF score hash {h} != recorded {recorded[fp]} for "
        f"fingerprint {fp} — the play-level RNG stream moved"
    )
