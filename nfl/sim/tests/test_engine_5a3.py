#!/usr/bin/env python3
"""Tests for Phase 5A-3 scoring-conversion fix."""

import numpy as np
import pandas as pd
import pytest
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _CACHE
from nfl.sim.seed_util import stable_seed

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"


@pytest.fixture(scope="module")
def ratings():
    _CACHE.clear()
    _load_tables()
    return _load_ratings()


@pytest.fixture(scope="module")
def k1_sample(ratings):
    """Run 50 sample games at N=500 for aggregate checks."""
    tr, tend, sit, kicker, league = ratings
    games = pd.read_parquet(PBP_DIR / "pbp_2023.parquet",
                             columns=["game_id", "season", "week", "home_team",
                                       "away_team", "home_score", "away_score"])
    games = games.drop_duplicates("game_id").query("week <= 18")
    rng = np.random.default_rng(42)
    sample = games.iloc[rng.choice(len(games), 50, replace=False)]

    results = []
    for _, g in sample.iterrows():
        s = stable_seed((g["game_id"], 42))
        r = simulate_game(g["home_team"], g["away_team"], 2023, int(g["week"]),
                          n_sims=500, seed=s,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker, league=league,
                          drive_log=True)
        r["game_id"] = g["game_id"]
        results.append(r)
    return pd.concat(results, ignore_index=True)


def test_drive_log_byte_identity_5a3(ratings):
    """Drive log ON vs OFF still byte-identical after 5A-3 changes."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r_off = simulate_game("WAS", "ARI", 2023, 1, n_sims=2000, seed=s,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker,
                          league=league, drive_log=False)
    r_on = simulate_game("WAS", "ARI", 2023, 1, n_sims=2000, seed=s,
                         team_r=tr, tend=tend, sit=sit, kicker=kicker,
                         league=league, drive_log=True)
    for col in r_off.columns:
        assert np.array_equal(r_off[col].values, r_on[col].values), \
            f"Mismatch in {col}"


def test_t1_4th_down_go_rate(k1_sample):
    """T1: pooled sim 4th-down go rate within 3.0pp of actual (19.8%).
    The 5A-3 fixes (GOE + rounding) reduced the gap from 3.4pp (pre-5a3)
    to ~2.1pp. The residual is from table-granularity: the sim's 4th-down
    situation mix differs from reality's due to the floating-point distance
    distribution producing a different yd_b mix than integer PBP ydstogo.
    Threshold set to 3.0pp to gate the fix while acknowledging the residual."""
    sim = k1_sample
    total_4th_decisions = sim["ev_4th_go"].sum() + sim["ev_punts"].sum() + sim["ev_fg_att"].sum()
    sim_go_rate = sim["ev_4th_go"].sum() / max(total_4th_decisions, 1)
    actual_go_rate = 0.198
    assert abs(sim_go_rate - actual_go_rate) < 0.030, \
        f"4th-down go rate {sim_go_rate:.3f} vs actual {actual_go_rate:.3f} (diff {abs(sim_go_rate-actual_go_rate):.3f} > 0.030)"


def test_t2_fg_attempts_per_game(k1_sample):
    """T2: FG attempts per game within 0.50 of actual (3.92).
    Pre-5A3: 3.41. Post-5A3: ~3.53. Threshold 0.50 gates the improvement."""
    sim_fg_pg = k1_sample["ev_fg_att"].mean()
    actual = 3.92
    assert abs(sim_fg_pg - actual) < 0.50, \
        f"FG att/game {sim_fg_pg:.2f} vs actual {actual} (diff {abs(sim_fg_pg-actual):.2f} > 0.50)"


def test_explosive_counters(ratings):
    """Explosive play counters exist and are reasonable."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r = simulate_game("WAS", "ARI", 2023, 1, n_sims=500, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker, league=league)
    assert "ev_explosive_pass" in r.columns
    assert "ev_explosive_rush" in r.columns
    # Explosive plays should be positive
    assert r["ev_explosive_pass"].sum() > 0
    assert r["ev_explosive_rush"].sum() > 0


def test_goe_in_tendencies(ratings):
    """GOE column exists and has non-trivial values in tendencies."""
    _, tend, _, _, _ = ratings
    assert "fourth_down_goe" in tend.columns
    goe = tend[tend["season"].isin([2021, 2022, 2023, 2024]) & (tend["n_plays"] > 0)]
    # GOE should have mean near 0 and some variance
    assert abs(goe["fourth_down_goe"].mean()) < 1.0, "GOE mean too far from 0"
    assert goe["fourth_down_goe"].std() > 0.1, "GOE has no variance — likely all zeros"


def test_clock_table_has_score_state():
    """Clock table has score_state and clock_period columns."""
    _CACHE.clear()
    _load_tables()
    tbl = _CACHE["clock"]
    assert "score_state" in tbl.columns
    assert "clock_period" in tbl.columns
    # Check that we have level-0 rows (finest)
    l0 = tbl[(~tbl["score_state"].str.startswith("p_")) &
             (~tbl["score_state"].str.startswith("all")) &
             (tbl["clock_period"] != "all")]
    assert len(l0) > 0, "No level-0 clock rows found"
