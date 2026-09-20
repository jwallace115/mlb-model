#!/usr/bin/env python3
"""Phase 5I tests — yards-to-go after offensive penalty, like-for-like go rate,
3rd-down-at-11+ share.

New file per work order: no existing test edited."""

import copy
import numpy as np
import pandas as pd
import pytest
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _CACHE
from nfl.sim.seed_util import stable_seed

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"

GAME = ("WAS", "ARI", 2023, 1)
SEED_VAL = stable_seed(("2023_01_ARI_WAS", 42))


@pytest.fixture(scope="module")
def ratings():
    _CACHE.clear()
    _load_tables()
    return _load_ratings()


@pytest.fixture(scope="module")
def k1_sample(ratings):
    """5A-3 sample: 50 games from 2023, rng seed 42, N=500."""
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


def test_offense_penalty_increases_ytg(ratings):
    """(a) Force an elevated penalty rate with normal category mix, verify that
    offensive penalties cause drives to end with yards-to-go > 15 at a rate that
    is only possible if dist is raised by the marched-off yardage.

    On the pre-fix engine, dist is never modified by offensive penalties, so the
    only source of end_dist > 15 is negative-yardage scrimmage plays (sacks).
    With the fix, offensive penalties push dist above 10, producing a materially
    higher fraction of drives ending at dist > 15."""
    _CACHE.clear()
    _load_tables()
    saved_scalars = copy.deepcopy(_CACHE["scalars"])
    try:
        sc = copy.deepcopy(_CACHE["scalars"])
        sc["penalty"]["p_no_play_penalty"] = 0.20
        _CACHE["scalars"] = sc
        tr, tend, sit, kicker, league = _load_ratings()
        r = simulate_game(*GAME, n_sims=2000, seed=SEED_VAL,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker,
                          league=league, drive_log=True)
        dl = r.attrs["drive_log"]
        frac = (dl.end_dist > 15).mean()
        # Pre-fix: ~0.065 (only from sacks/negative plays)
        # Post-fix: ~0.13+ (offensive penalties add to dist)
        assert frac > 0.10, (
            f"Fraction of drives with end_dist > 15 is {frac:.4f}; "
            f"expected > 0.10 with penalty-distance fix active"
        )
    finally:
        _CACHE["scalars"] = saved_scalars


def test_like_for_like_4th_go_rate(k1_sample):
    """(b) Like-for-like 4th-down go rate, down == 4 only.
    ev_4th_go / (ev_4th_go + ev_punts + ev_fg_att - ev_fg_non4th)
    within 0.010 of 0.198."""
    sim = k1_sample
    ev_4th_go = sim["ev_4th_go"].sum()
    ev_punts = sim["ev_punts"].sum()
    ev_fg_att = sim["ev_fg_att"].sum()
    ev_fg_non4th = sim["ev_fg_non4th"].sum()
    denom = ev_4th_go + ev_punts + ev_fg_att - ev_fg_non4th
    go_rate = ev_4th_go / max(denom, 1)
    assert abs(go_rate - 0.198) < 0.010, (
        f"Like-for-like 4th-down go rate {go_rate:.5f} vs 0.198 "
        f"(diff {abs(go_rate - 0.198):.5f} > 0.010)"
    )


def test_3rd_down_long_share(k1_sample):
    """(c) 3rd-down share at 11+ to go within 0.03 of real 0.182."""
    sim = k1_sample
    share = sim["ev_3rd_long"].sum() / max(sim["ev_3rd_att"].sum(), 1)
    assert abs(share - 0.182) < 0.03, (
        f"3rd-down 11+ share {share:.4f} vs 0.182 "
        f"(diff {abs(share - 0.182):.4f} > 0.030)"
    )
