"""5W tests: actuals derivation row counts are pinned; play-log quarter sums."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_k1_actuals_row_counts():
    """Pin the derivation's row counts so the value is reproducible."""
    from nfl.sim.actuals_k1 import compute_k1_actuals
    act = compute_k1_actuals()
    assert act["n_games"] == 1087, f"n_games {act['n_games']} != 1087"
    assert act["n_plays_total"] == 136727, f"n_plays {act['n_plays_total']} != 136727"
    assert act["n_drives_total"] == 23635, f"n_drives {act['n_drives_total']} != 23635"
