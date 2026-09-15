#!/usr/bin/env python3
"""Tests for Phase 5A-5 non-offensive scoring and drive log extensions."""

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
    """Run 80 sample games at N=500."""
    tr, tend, sit, kicker, league = ratings
    games = pd.read_parquet(PBP_DIR / "pbp_2023.parquet",
                             columns=["game_id", "season", "week", "home_team",
                                       "away_team", "home_score", "away_score"])
    games = games.drop_duplicates("game_id").query("week <= 18")
    rng = np.random.default_rng(42)
    sample = games.iloc[rng.choice(len(games), 80, replace=False)]
    results = []
    for _, g in sample.iterrows():
        s = stable_seed((g["game_id"], 42))
        r = simulate_game(g["home_team"], g["away_team"], 2023, int(g["week"]),
                          n_sims=500, seed=s,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker, league=league)
        r["game_id"] = g["game_id"]
        results.append(r)
    return pd.concat(results, ignore_index=True)


def test_drive_log_byte_identity_5a5(ratings):
    """Drive log ON vs OFF byte-identical after 5A-5 changes."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r_off = simulate_game("WAS", "ARI", 2023, 1, n_sims=2000, seed=s,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker,
                          league=league, drive_log=False)
    r_on = simulate_game("WAS", "ARI", 2023, 1, n_sims=2000, seed=s,
                         team_r=tr, tend=tend, sit=sit, kicker=kicker,
                         league=league, drive_log=True)
    shared = set(r_off.columns) & set(r_on.columns)
    for col in sorted(shared):
        assert np.array_equal(r_off[col].values, r_on[col].values), f"Mismatch in {col}"


def test_nonoff_counters_exist(k1_sample):
    """Non-offensive scoring counters are present and non-negative."""
    for col in ["ev_int_ret_td", "ev_fum_ret_td", "ev_punt_ret_td", "ev_ko_ret_td"]:
        assert col in k1_sample.columns, f"Missing column: {col}"
        assert (k1_sample[col] >= 0).all(), f"Negative values in {col}"


def test_int_ret_td_rate(k1_sample):
    """INT return TD rate per turnover within 0.5pp of actual (9.07%).
    Spec: return-TD rate per turnover type within 0.5pp."""
    total_ints = k1_sample["ev_ints"].sum()
    total_int_tds = k1_sample["ev_int_ret_td"].sum()
    sim_rate = total_int_tds / max(total_ints, 1)
    actual = 0.0907
    diff_pp = abs(sim_rate - actual) * 100
    assert diff_pp < 0.5, \
        f"INT ret TD rate {sim_rate:.4f} vs actual {actual} (diff {diff_pp:.2f}pp > 0.5pp)"


def test_nonoff_pts_per_team(k1_sample):
    """Non-offensive points per team within 0.3 of actual (0.92)."""
    xp = 0.948
    nonoff_tds = (k1_sample["ev_int_ret_td"] + k1_sample["ev_fum_ret_td"] +
                  k1_sample["ev_punt_ret_td"] + k1_sample["ev_ko_ret_td"]).mean()
    safety_pts = k1_sample["ev_safeties"].mean() * 2
    nonoff_pts_per_team = (nonoff_tds * (6 + xp) + safety_pts) / 2
    actual = 0.92
    assert abs(nonoff_pts_per_team - actual) < 0.3, \
        f"Non-off pts/team {nonoff_pts_per_team:.2f} vs actual {actual} (diff {abs(nonoff_pts_per_team-actual):.2f} > 0.3)"


def test_drive_log_has_end_state(ratings):
    """Drive log includes end-state columns."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r = simulate_game("WAS", "ARI", 2023, 1, n_sims=100, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    dl = r.attrs.get("drive_log")
    assert dl is not None, "No drive log"
    for col in ["end_yardline", "end_down", "end_dist", "score_state"]:
        assert col in dl.columns, f"Missing drive log column: {col}"
    assert len(dl) > 0
    # Score state should have valid values
    valid_ss = {"trail9+", "trail1-8", "tied", "lead1-8", "lead9+"}
    assert set(dl["score_state"].unique()).issubset(valid_ss), \
        f"Invalid score states: {set(dl['score_state'].unique()) - valid_ss}"
