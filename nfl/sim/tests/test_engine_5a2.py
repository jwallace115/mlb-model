#!/usr/bin/env python3
"""Tests for Phase 5A-2 drive log instrumentation."""

import numpy as np
import pytest
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed


@pytest.fixture(scope="module")
def ratings():
    _load_tables()
    return _load_ratings()


def test_drive_log_byte_identity(ratings):
    """Drive log ON vs OFF produces identical game-level outputs (N=2000)."""
    tr, tend, sit, kicker, league = ratings
    games = [
        ("WAS", "ARI", 2023, 1),
        ("KC", "DET", 2024, 4),
        ("SF", "SEA", 2022, 10),
    ]
    for home, away, season, week in games:
        s = stable_seed((f"{season}_{week}_{away}_{home}", 42))
        r_off = simulate_game(home, away, season, week, n_sims=2000, seed=s,
                              team_r=tr, tend=tend, sit=sit, kicker=kicker,
                              league=league, drive_log=False)
        r_on = simulate_game(home, away, season, week, n_sims=2000, seed=s,
                             team_r=tr, tend=tend, sit=sit, kicker=kicker,
                             league=league, drive_log=True)
        for col in r_off.columns:
            assert np.array_equal(r_off[col].values, r_on[col].values), \
                f"Mismatch in {col} for {home} vs {away} {season} wk{week}"


def test_drive_log_has_rows(ratings):
    """Drive log produces rows with expected schema."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r = simulate_game("WAS", "ARI", 2023, 1, n_sims=100, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    dl = r.attrs.get("drive_log")
    assert dl is not None
    assert len(dl) > 0
    expected_cols = {"sim_id", "team", "drive_no", "start_yardline",
                     "start_quarter", "start_clock", "plays", "yards",
                     "result", "points", "reached_rz", "reached_gl"}
    assert expected_cols.issubset(set(dl.columns)), f"Missing cols: {expected_cols - set(dl.columns)}"


def test_drive_log_result_values(ratings):
    """All drive results are in the expected set."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r = simulate_game("WAS", "ARI", 2023, 1, n_sims=500, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    dl = r.attrs["drive_log"]
    valid = {"TD", "FG_made", "FG_missed", "punt", "turnover_int",
             "turnover_fumble", "downs", "end_half", "end_game", "safety"}
    actual_results = set(dl["result"].unique())
    assert actual_results.issubset(valid), f"Unexpected results: {actual_results - valid}"


def test_drive_log_td_points(ratings):
    """TD drives should have points >= 6."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_05_BUF_NYJ", 42))
    r = simulate_game("NYJ", "BUF", 2023, 5, n_sims=500, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    dl = r.attrs["drive_log"]
    td_drives = dl[dl["result"] == "TD"]
    assert len(td_drives) > 0
    # TD drives should have 6, 7, or 8 points
    assert (td_drives["points"] >= 6).all(), \
        f"TD drives with <6 pts: {td_drives[td_drives['points'] < 6]}"


def test_drive_log_drives_count(ratings):
    """Total drives in log should approximately match drives counter."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r = simulate_game("WAS", "ARI", 2023, 1, n_sims=200, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    dl = r.attrs["drive_log"]
    # Each sim's max drive_no should be close to drives count
    dl_max = dl.groupby("sim_id")["drive_no"].max()
    engine_drives = r["drives"].values[:200]
    # Drive log may miss the very last drive if it ends with game_over
    # without a new_drive call, so allow some slack
    diff = np.abs(dl_max.values - engine_drives[dl_max.index])
    assert diff.max() <= 2, f"Drive count mismatch: max diff={diff.max()}"


def test_new_counters_exist(ratings):
    """New diagnostic counters (3rd-down, 4th-down, FG dist) are in output."""
    tr, tend, sit, kicker, league = ratings
    s = stable_seed(("2023_01_ARI_WAS", 42))
    r = simulate_game("WAS", "ARI", 2023, 1, n_sims=100, seed=s,
                      team_r=tr, tend=tend, sit=sit, kicker=kicker,
                      league=league)
    for col in ["ev_3rd_att", "ev_3rd_conv", "ev_4th_go", "ev_4th_conv", "ev_fg_dist_sum"]:
        assert col in r.columns, f"Missing column: {col}"
    # 3rd-down attempts should be positive
    assert r["ev_3rd_att"].sum() > 0
    # Conversion rate should be reasonable (20-60%)
    rate = r["ev_3rd_conv"].sum() / r["ev_3rd_att"].sum()
    assert 0.15 < rate < 0.65, f"3rd-down conv rate {rate:.3f} out of range"
