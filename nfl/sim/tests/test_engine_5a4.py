#!/usr/bin/env python3
"""Tests for Phase 5A-4 penalty/first-down/safety fixes.

Spec tolerances (from prompt):
  - Penalties/game per side: within 0.5 of actual
  - First downs by penalty per team: within 0.3 of actual
  - Net penalty yards: within 5 per team
  - Safeties share: within 0.1pp
"""

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
    """Run 80 sample games at N=500 for aggregate checks."""
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


def test_drive_log_byte_identity_5a4(ratings):
    """Drive log ON vs OFF byte-identical after 5A-4 changes."""
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
        assert np.array_equal(r_off[col].values, r_on[col].values), \
            f"Mismatch in {col}"


def test_penalties_per_side(k1_sample):
    """Offense/defense penalties per game within 0.5 of actual.
    Actual (no-play, per game): offense 5.51, defense 3.45."""
    sim = k1_sample
    n_games = sim["game_id"].nunique()
    # Per game (note: ev_pen_offense/defense are per-sim, need mean per game)
    off_pg = sim["ev_pen_offense"].mean()
    def_pg = sim["ev_pen_defense"].mean()
    # Actual per-game (no-play penalties): 5993/1087=5.51 offense, 3751/1087=3.45 defense
    assert abs(off_pg - 5.51) < 0.5, \
        f"Offense penalties/game {off_pg:.2f} vs actual 5.51 (diff {abs(off_pg-5.51):.2f} > 0.5)"
    assert abs(def_pg - 3.45) < 0.5, \
        f"Defense penalties/game {def_pg:.2f} vs actual 3.45 (diff {abs(def_pg-3.45):.2f} > 0.5)"


def test_first_downs_by_penalty(k1_sample):
    """First downs by penalty per team within 0.3 of actual (1.73/team/game).
    Per game (both teams): 3.46. Per team: 1.73."""
    sim = k1_sample
    fd_pen_pg = sim["ev_fd_penalty"].mean()
    # Per team = per_game / 2
    fd_pen_per_team = fd_pen_pg / 2
    actual = 1.73
    assert abs(fd_pen_per_team - actual) < 0.3, \
        f"FD by penalty/team {fd_pen_per_team:.2f} vs actual {actual} (diff {abs(fd_pen_per_team-actual):.2f} > 0.3)"


def test_net_penalty_yards(k1_sample):
    """Net penalty yards (def - off) per team within 5 of actual (-1.2/team/game)."""
    sim = k1_sample
    net_pg = (sim["ev_pen_def_yds"] - sim["ev_pen_off_yds"]).mean()
    # Per team = per_game / 2
    net_per_team = net_pg / 2
    actual = -1.2
    assert abs(net_per_team - actual) < 5.0, \
        f"Net penalty yds/team {net_per_team:.1f} vs actual {actual} (diff {abs(net_per_team-actual):.1f} > 5.0)"


def test_safety_share(k1_sample):
    """Safety share of drives within 0.1pp of actual (0.22%).
    Actual: 53 safeties / 23639 drives = 0.224%."""
    sim = k1_sample
    # Safety share = safeties / drives
    total_safeties = sim["ev_safeties"].sum()
    total_drives = sim["drives"].sum()
    sim_share = total_safeties / total_drives * 100  # in percent
    actual_share = 0.224  # percent
    diff = abs(sim_share - actual_share)
    assert diff < 0.10, \
        f"Safety share {sim_share:.3f}% vs actual {actual_share}% (diff {diff:.3f}pp > 0.10pp)"


def test_penalty_detail_table_loaded(ratings):
    """Penalty detail table exists and has expected categories."""
    assert "penalty_detail" in _CACHE
    pd_table = _CACHE["penalty_detail"]
    expected_cats = ["offense_5yd", "offense_10yd", "defense_dpi",
                     "defense_auto_short", "defense_noauto"]
    for cat in expected_cats:
        assert cat in pd_table, f"Missing category: {cat}"
    # DPI should have yds_q
    assert "yds_q" in pd_table["defense_dpi"]
    assert len(pd_table["defense_dpi"]["yds_q"]) == 101
