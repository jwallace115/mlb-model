#!/usr/bin/env python3
"""
Phase 5L — engine tests for per-sim share dispersion + order invariance.

(a) Jeanty's carry share over n_sims=2500 has > 100 unique values
    and its mean is within 0.03 of his renormalised carry_share.
(b) simulate_game seeds 1-6: SD of Jeanty mean carries < 0.6 (main: 4.2).
(c) Shuffle usage rows 3 times -> LV players' mean carries/targets identical
    to unshuffled (exact equality, same seed).
"""

import sys
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


def test_per_sim_dispersion(engine_data):
    """(a) Jeanty's carry share over 2500 sims has > 100 unique values
    and mean is within 0.03 of his renormalised carry_share.
    FAILS on main (1 unique value)."""
    from nfl.sim.engine import _build_player_context

    rng = np.random.default_rng(42)
    pctx = _build_player_context(
        "LAC", "LV", 2026, 2,
        engine_data["player_usage"], engine_data["active_uni"],
        n_sims=2500, rng=rng)

    # LV is pctx[1]
    ctx = pctx[1]
    assert ctx is not None, "No player context for LV"

    ids = ctx["ids"]
    jeanty_idx = None
    for i, pid in enumerate(ids):
        if "Jeanty" in ctx["names"][i]:
            jeanty_idx = i
            break
    assert jeanty_idx is not None, "Jeanty not found in LV context"

    # Extract per-sim carry share from cumsum
    car_cum = ctx["car_cumsum"]  # (N, n_pl)
    if jeanty_idx == 0:
        jeanty_shares = car_cum[:, 0]
    else:
        jeanty_shares = car_cum[:, jeanty_idx] - car_cum[:, jeanty_idx - 1]

    n_unique = len(np.unique(jeanty_shares))
    assert n_unique > 100, (
        f"Jeanty carry share has only {n_unique} unique values over 2500 sims "
        f"(expected > 100; a single draw is broadcast to all sims)")

    # Mean should be within 0.03 of renormalised carry_share
    # Get the renormalised share from the usage data
    pu = engine_data["player_usage"]
    lv_pu = pu[(pu["season"] == 2026) & (pu["team"] == "LV")]
    if lv_pu.empty or 2 not in lv_pu["week"].values:
        lv_pu = lv_pu[lv_pu["week"] == lv_pu["week"].max()]
    else:
        lv_pu = lv_pu[lv_pu["week"] == 2]
    jeanty_row = lv_pu[lv_pu["player_id"].isin(ids[jeanty_idx:jeanty_idx+1])]
    if not jeanty_row.empty:
        expected_share = jeanty_row["carry_share"].iloc[0]
        # Normalize: his carry_share / sum of all carry_shares
        total_cs = lv_pu["carry_share"].sum()
        if total_cs > 0:
            expected_norm = expected_share / total_cs
            actual_mean = float(np.mean(jeanty_shares))
            assert abs(actual_mean - expected_norm) < 0.03, (
                f"Jeanty mean carry share {actual_mean:.4f} too far from "
                f"renormalised {expected_norm:.4f}")


def test_seed_stability(engine_data):
    """(b) SD of Jeanty mean carries across seeds 1-6 < 0.6 (main: 4.2).
    FAILS on main."""
    from nfl.sim.engine import simulate_game

    means = []
    for seed in range(1, 7):
        td, pdf = simulate_game(
            "LAC", "LV", 2026, 2, n_sims=1000, seed=seed, **engine_data)
        jeanty = pdf[pdf["player_name"].str.contains("Jeanty")]
        means.append(jeanty["carries"].mean())

    sd = float(np.std(means, ddof=1))
    assert sd < 0.6, (
        f"Jeanty mean carries SD across seeds = {sd:.2f} (threshold 0.6). "
        f"Main's value is ~4.2 due to one-draw-per-chunk bug.")


def test_order_invariance(engine_data):
    """(c) Shuffle usage rows 3 times -> every LV player's mean carries
    and targets identical to unshuffled (exact equality, same seed).
    FAILS on main (unstable sort on tied target_share)."""
    from nfl.sim.engine import simulate_game

    pu = engine_data["player_usage"]

    # Baseline: unshuffled
    td0, pdf0 = simulate_game(
        "LAC", "LV", 2026, 2, n_sims=1000, seed=99, **engine_data)
    base_means = pdf0[pdf0["team"] == "LV"].groupby("player_id").agg(
        carries=("carries", "mean"), targets=("targets", "mean")).sort_index()

    for shuffle_seed in [1, 2, 3]:
        rng_s = np.random.default_rng(shuffle_seed)
        shuffled_pu = pu.sample(frac=1, random_state=rng_s).reset_index(drop=True)
        kw_s = dict(engine_data)
        kw_s["player_usage"] = shuffled_pu
        td_s, pdf_s = simulate_game(
            "LAC", "LV", 2026, 2, n_sims=1000, seed=99, **kw_s)
        shuf_means = pdf_s[pdf_s["team"] == "LV"].groupby("player_id").agg(
            carries=("carries", "mean"), targets=("targets", "mean")).sort_index()

        # Must have same players
        assert set(base_means.index) == set(shuf_means.index), (
            f"Different player sets in shuffle {shuffle_seed}")

        for pid in base_means.index:
            for col in ["carries", "targets"]:
                b = base_means.loc[pid, col]
                s = shuf_means.loc[pid, col]
                assert b == s, (
                    f"Player {pid} {col}: base={b:.4f} vs shuffle({shuffle_seed})={s:.4f}")
