"""Phase 5A-7 tests — 10-yard-zone outcome tables (KM), timeout policy, kneel table.

Tolerances are the acceptance spec; a failing test is reported red, never widened.
"""
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import nfl.sim.engine as E  # noqa: E402
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, NZONES  # noqa: E402
from nfl.sim.seed_util import stable_seed  # noqa: E402

TABLES = ROOT / "nfl" / "data" / "sim" / "tables"

# Measured 2021-2024 regular season, per game (see phase5a7 report)
ACT_LATE_Q2_SNAPS = 9.03      # pass/run snaps, last 2:00 of Q2
ACT_LATE_Q4_SNAPS = 5.61      # pass/run snaps, last 2:00 of Q4
ACT_TO_OFF = 1.78             # offensive timeouts after snaps, last 3:00 of Q2+Q4
ACT_TO_DEF = 2.08             # defensive timeouts, same window
ACT_KNEELS = 1.51             # kneel-downs per game
ACT_COMP_MEAN_20_30 = 9.98    # mean completion yards, snaps from the 21-30

SAMPLE_GAMES = [("KC", "BUF", 2023, 6), ("PHI", "DAL", 2022, 10), ("SF", "SEA", 2024, 12),
                ("DET", "GB", 2023, 4), ("BAL", "CIN", 2022, 14), ("MIA", "NYJ", 2024, 8),
                ("LA", "ARI", 2023, 12), ("MIN", "CHI", 2022, 6), ("TB", "ATL", 2024, 15),
                ("DEN", "LV", 2023, 17), ("CLE", "PIT", 2022, 2), ("HOU", "IND", 2024, 5)]


@pytest.fixture(scope="module")
def ratings():
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    return dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)


def _td(r):
    return r[0] if isinstance(r, tuple) else r


# ── T1: 10-yard-zone tables exist, cover the field, and carry censoring counts ──

def test_t1_z10_tables():
    for name in ("pass_outcomes_z10", "rush_outcomes_z10"):
        t = pd.read_parquet(TABLES / f"{name}.parquet")
        assert set(t["zone"]) == {f"y{k}" for k in range(10, 101, 10)}
        assert "n_censored" in t.columns and (t["n"] >= 20).all()
        assert len(t) >= 80, f"{name}: only {len(t)} cells"
    assert NZONES == 10


def test_t1_engine_arrays_are_z10_with_fallback(ratings):
    arrs = E._build_pass_arrays()
    assert arrs[6].shape == (5, 3, 10, 101)          # yds_succ_q
    assert E._CACHE["_pass_z10_cells"] >= 80
    # neighbouring zones inside the 20 differ from each other (not one pooled cell)
    q = arrs[6]
    assert not np.allclose(q[1, 2, 0], q[1, 2, 1])   # 1st & long: y10 vs y20


def test_t1_no_hand_scale_constants():
    src = (ROOT / "nfl" / "sim" / "engine.py").read_text()
    assert "*= 0.687" not in src, "5A-4 sack-yardage scale constant is back"


# ── T2: liveness — perturbing each new table changes the output ──────────────

def test_t2_timeout_policy_live(ratings):
    home, away, season, week = SAMPLE_GAMES[0]
    seed = stable_seed("5a7_t2")
    r = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    assert float(r["ev_to_off"].mean() + r["ev_to_def"].mean()) > 1.0
    saved = E._CACHE["timeout_policy"].copy()
    try:
        z = saved.copy(); z["p_to"] = 0.0
        E._CACHE["timeout_policy"] = z
        r0 = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
        assert float(r0["ev_to_off"].sum() + r0["ev_to_def"].sum()) == 0.0
        assert abs(float(r0["ev_late_snaps_q2"].mean()) - float(r["ev_late_snaps_q2"].mean())) > 0.2
    finally:
        E._CACHE["timeout_policy"] = saved


def test_t2_kneel_table_live(ratings):
    home, away, season, week = SAMPLE_GAMES[1]
    seed = stable_seed("5a7_t2k")
    r = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    assert float(r["ev_kneels"].mean()) > 0.5
    saved = E._CACHE["kneel"].copy()
    try:
        z = saved.copy(); z["p_kneel"] = 0.0
        E._CACHE["kneel"] = z
        r0 = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
        assert float(r0["ev_kneels"].sum()) == 0.0
    finally:
        E._CACHE["kneel"] = saved


# ── T3: acceptance on a 12-game sample, N=500 ────────────────────────────────

@pytest.fixture(scope="module")
def sample(ratings):
    E._DEBUG_YDS = []
    rows = []
    for home, away, season, week in SAMPLE_GAMES:
        r = _td(simulate_game(home, away, season, week, n_sims=500,
                              seed=stable_seed(f"5a7_{season}_{week}_{away}_{home}"), **ratings))
        rows.append({k: float(r[k].mean()) for k in
                     ("ev_late_snaps_q2", "ev_late_snaps_q4", "ev_to_off", "ev_to_def", "ev_kneels", "plays")})
    rec = E._DEBUG_YDS
    E._DEBUG_YDS = None
    return pd.DataFrame(rows).mean(), rec


def test_t3_late_half_snaps(sample):
    m, _ = sample
    assert abs(m["ev_late_snaps_q2"] - ACT_LATE_Q2_SNAPS) <= 0.7, f"Q2 late snaps {m['ev_late_snaps_q2']:.2f}"
    assert abs(m["ev_late_snaps_q4"] - ACT_LATE_Q4_SNAPS) <= 0.8, f"Q4 late snaps {m['ev_late_snaps_q4']:.2f}"


def test_t3_timeouts_and_kneels(sample):
    m, _ = sample
    assert abs(m["ev_to_off"] - ACT_TO_OFF) <= 0.4, f"off TO {m['ev_to_off']:.2f}"
    assert abs(m["ev_to_def"] - ACT_TO_DEF) <= 0.4, f"def TO {m['ev_to_def']:.2f}"
    assert abs(m["ev_kneels"] - ACT_KNEELS) <= 0.4, f"kneels {m['ev_kneels']:.2f}"


def test_t3_completion_yards_by_zone(sample):
    _, rec = sample
    y = np.concatenate([a[1] for a in rec if a[0] == "pass"])
    yl = np.concatenate([a[2] for a in rec if a[0] == "pass"])
    m = (yl > 20) & (yl <= 30)
    got = float(y[m].mean())
    assert abs(got - ACT_COMP_MEAN_20_30) <= 0.6, f"mean completion yards from the 21-30: {got:.2f}"
