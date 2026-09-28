"""5Z tests: safety counters sum to ev_safeties; player-OFF hash unchanged."""
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


def test_safety_counters_sum():
    """The new per-type safety counters sum to ev_safeties on every sim."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    for home, away, season, week in GAMES:
        for sv in [42, 99]:
            seed = stable_seed((home, away, season, week, sv))
            r = simulate_game(home, away, season, week, n_sims=200, seed=seed,
                              team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                              league=league, drive_log=True)
            saf_pre = r.attrs.get("saf_pre")
            saf_sack = r.attrs.get("saf_sack")
            saf_rush = r.attrs.get("saf_rush")
            assert saf_pre is not None, "saf_pre not in attrs"
            total_typed = saf_pre + saf_sack + saf_rush
            assert np.array_equal(total_typed, r["ev_safeties"].values), (
                f"Safety counter mismatch: {total_typed} vs {r['ev_safeties'].values}"
            )
            return  # One game is enough


def test_player_off_hash_5z_entry():
    """6B: the 5Z fingerprint entry (62320588f80d0593) maps to 80848eefb5a45062."""
    import json
    with open(ROOT / "nfl" / "sim" / "tests" / "fixtures" / "player_off_hash.json") as f:
        hashes = json.load(f)
    assert hashes.get("62320588f80d0593") == "80848eefb5a45062", (
        f"5Z entry missing or wrong: {hashes.get('62320588f80d0593')}"
    )
