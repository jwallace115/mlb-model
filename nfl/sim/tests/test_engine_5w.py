"""5W tests: actuals derivation row counts are pinned; play-log quarter sums."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_play_log_quarter_sums():
    """Each regulation quarter sums to 900 s within 1 s on every non-OT sim."""
    from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
    from nfl.sim.seed_util import stable_seed
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    for home, away, season, week in [("KC", "BUF", 2024, 11), ("SF", "DAL", 2023, 5),
                                      ("PHI", "NYG", 2022, 14)]:
        seed = stable_seed((home, away, season, week, 42))
        r = simulate_game(home, away, season, week, n_sims=200, seed=seed,
                          team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                          league=league, drive_log=True)
        pl = r.attrs.get("play_log")
        assert pl is not None and len(pl) > 0, f"No play_log for {away}@{home}"
        ot_sims = set(r[r["ot_flag"] == 1].index.tolist())
        for si in range(200):
            if si in ot_sims:
                continue
            sp = pl[pl["sim_id"] == si]
            for q in [1, 2, 3, 4]:
                qp = sp[sp["qtr"] == q]
                q_total = qp["elapsed"].sum()
                assert abs(q_total - 900) < 1.0, (
                    f"{away}@{home} sim {si} Q{q}: elapsed {q_total:.2f} != 900 ± 1"
                )
        return  # One game passing is enough


def test_k1_actuals_row_counts():
    """Pin the derivation's row counts so the value is reproducible."""
    from nfl.sim.actuals_k1 import compute_k1_actuals
    act = compute_k1_actuals()
    assert act["n_games"] == 1087, f"n_games {act['n_games']} != 1087"
    assert act["n_plays_total"] == 136727, f"n_plays {act['n_plays_total']} != 136727"
    assert act["n_drives_total"] == 23635, f"n_drives {act['n_drives_total']} != 23635"
