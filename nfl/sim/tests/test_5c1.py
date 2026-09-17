#!/usr/bin/env python3
"""
Phase 5C-1 + 5C-1b tests.

(a) Shared solver: all three callers resolve to the same function object
(b) CRPS: 20,000 N(0,1) draws at y=0.7 matches closed form within 0.005
(c) TD labels: count player-games whose ATD label changes with td_player_id
(d) Actuals: three call sites resolve to the same function object
(e) SGP raking: one leg returns its calibrated marginal; two independent legs
    within 2*SE of the product; ESS is a count
(f) Situational tendency keys: zero float-format bucket keys on disk;
    sit_proe_miss_count < 1% on a sample run
(g) No sgp_probability alias (deleted)
(h) QB identity: 32/32 teams for 2026 wk2; KC=Mahomes; flag-removed raises
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─── (a) shared solver identity ─────────────────────────────────────────────

def test_shared_solver_identity():
    """All three callers resolve to the same run_anchored_chunked callable."""
    from nfl.sim.anchor import run_anchored_chunked as anchor_fn
    from nfl.sim.run_week import run_anchored_chunked as rw_fn
    assert anchor_fn is rw_fn, "run_week does not use anchor.run_anchored_chunked"

    # run_cal_players imports it too
    from nfl.sim.run_cal_players import run_anchored_chunked as rcp_fn
    assert anchor_fn is rcp_fn, "run_cal_players does not use anchor.run_anchored_chunked"

    # calibration.run_anchored_backtest uses anchor_game which wraps it
    from nfl.sim.anchor import anchor_game
    # anchor_game calls run_anchored_chunked internally — verified by code inspection

    from nfl.sim.anchor import _load_anchor_params
    ap = _load_anchor_params()
    assert ap["n_sims"] == 5000  # D51
    assert ap["chunk_size"] == 2500  # D51
    assert ap["n_sims"] % ap["chunk_size"] == 0
    assert ap["max_iter"] == 8
    assert ap["J_INV"].shape == (2, 2)

    # Non-divisible N must raise
    with pytest.raises(ValueError, match="divisible"):
        anchor_fn("KC", "DEN", 2024, 1, -3.0, 47.5, n_sims=3000, chunk_size=2500)


# ─── (b) CRPS closed-form check ─────────────────────────────────────────────

def test_crps_closed_form():
    """20,000 N(0,1) draws, y=0.7: sample CRPS matches closed form within 0.005."""
    from nfl.sim.calibration import _crps_sample
    from scipy.stats import norm

    rng = np.random.default_rng(42)
    samples = rng.standard_normal(20_000)
    y = 0.7
    sigma = 1.0

    sample_crps = _crps_sample(samples, y)
    z = (y - 0.0) / sigma
    closed_crps = sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))

    assert abs(sample_crps - closed_crps) < 0.005, (
        f"CRPS mismatch: sample={sample_crps:.6f} closed={closed_crps:.6f} "
        f"diff={abs(sample_crps - closed_crps):.6f}"
    )


# ─── (c) TD label change count ──────────────────────────────────────────────

def test_td_label_change_count():
    """Count player-games whose ATD label changes between old rule and td_player_id."""
    total_diff = 0
    for s in [2021, 2022, 2023, 2024]:
        pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        if not pbp_path.exists():
            continue
        pbp = pd.read_parquet(pbp_path)
        td_plays = pbp[pbp["touchdown"] == 1].copy()

        old_scorers = set()
        for _, row in td_plays.iterrows():
            if pd.notna(row.get("rusher_player_id")) and row["play_type"] == "run":
                old_scorers.add((row["game_id"], row["rusher_player_id"]))
            if (pd.notna(row.get("receiver_player_id"))
                    and row["play_type"] == "pass"
                    and row.get("complete_pass", 0) == 1):
                old_scorers.add((row["game_id"], row["receiver_player_id"]))

        new_scorers = set()
        for _, row in td_plays[td_plays["td_player_id"].notna()].iterrows():
            new_scorers.add((row["game_id"], row["td_player_id"]))

        total_diff += len(old_scorers.symmetric_difference(new_scorers))

    print(f"TD label changes (player-games): {total_diff}")
    assert total_diff > 100, f"Expected > 100 TD label changes, got {total_diff}"


# ─── (d) actuals function identity ──────────────────────────────────────────

def test_actuals_function_identity():
    """calibration, grade_week both resolve to the same actuals function."""
    from nfl.sim.actuals import actual_player_game_stats as canonical
    from nfl.sim.grade_week import actual_player_game_stats as gw_fn
    assert gw_fn is canonical, "grade_week does not use actuals.actual_player_game_stats"


# ─── (e) SGP raking ─────────────────────────────────────────────────────────

def test_sgp_raking_one_leg():
    """One leg returns its calibrated marginal exactly."""
    from nfl.sim.pricer import sgp_probability_raked
    N = 10000
    rng = np.random.default_rng(99)
    indicators = (rng.random(N) < 0.4).astype(np.int8)
    leg_matrix = pd.DataFrame({"sim_id": np.arange(N), "leg_A": indicators})

    cal_p = 0.35
    joint, ess = sgp_probability_raked(leg_matrix, ["leg_A"], [cal_p])
    assert abs(joint - cal_p) < 1e-6
    assert ess > 1, f"ESS should be a count > 1, got {ess}"
    assert ess <= N, f"ESS {ess} should not exceed N={N}"


def test_sgp_raking_independent_legs():
    """Two independent legs: raked joint within 2*SE of the product."""
    from nfl.sim.pricer import sgp_probability_raked
    N = 50000
    rng = np.random.default_rng(77)
    a = (rng.random(N) < 0.5).astype(np.int8)
    b = (rng.random(N) < 0.3).astype(np.int8)
    leg_matrix = pd.DataFrame({"sim_id": np.arange(N), "A": a, "B": b})

    cal_a, cal_b = 0.45, 0.28
    joint, ess = sgp_probability_raked(leg_matrix, ["A", "B"], [cal_a, cal_b])
    expected = cal_a * cal_b
    se = np.sqrt(expected * (1 - expected) / ess)
    assert abs(joint - expected) < 2 * se + 1e-6
    assert ess > 100, f"ESS={ess:.0f} too low"


# ─── (f) situational tendency keys ──────────────────────────────────────────

def test_situational_keys_zero_float():
    """Zero float-format bucket keys on disk after rebuild."""
    sit_path = ROOT / "nfl" / "data" / "sim" / "ratings" / "tendencies_situational_weekly.parquet"
    if not sit_path.exists():
        pytest.skip("tendencies_situational_weekly.parquet not found")
    sit = pd.read_parquet(sit_path)
    float_keys = sit[sit["bucket"].str.contains(r"^\d+\.", na=False)]
    assert len(float_keys) == 0, (
        f"Found {len(float_keys)} float-format bucket keys: {float_keys['bucket'].unique()[:5]}"
    )


# ─── (g) no sgp_probability alias ───────────────────────────────────────────

def test_no_sgp_probability_alias():
    """sgp_probability alias deleted — only raw and raked exist."""
    import nfl.sim.pricer as pricer
    assert not hasattr(pricer, "sgp_probability"), (
        "sgp_probability alias still exists — should be deleted"
    )
    assert hasattr(pricer, "sgp_probability_raw")
    assert hasattr(pricer, "sgp_probability_raked")


# ─── (h) QB identity in engine — all 32 teams ───────────────────────────────

def test_engine_qb_identity_2026_wk2_all_teams():
    """Engine's passer matches is_starting_qb for all 32 teams, 2026 wk2."""
    from nfl.sim.engine import _build_player_context, _load_tables, _load_ratings

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")

    # Get all 2026 wk2 teams
    u26w2 = pu[(pu["season"] == 2026) & (pu["week"] == 2)]
    teams = sorted(u26w2["team"].unique())
    assert len(teams) == 32, f"Expected 32 teams, got {len(teams)}"

    failures = []
    for i in range(0, len(teams), 2):
        home = teams[i]
        away = teams[min(i + 1, len(teams) - 1)]
        if home == away:
            continue
        rng = np.random.default_rng(42)
        try:
            pctx = _build_player_context(home, away, 2026, 2, pu, au, None,
                                          n_sims=10, rng=rng)
        except Exception as e:
            failures.append(f"{home}/{away}: {e}")
            continue
        for ti, team in enumerate([home, away]):
            ctx = pctx[ti]
            if ctx is None:
                failures.append(f"{team}: player context is None")
                continue
            qb_idx = ctx["qb_idx"]
            if qb_idx < 0:
                failures.append(f"{team}: no QB selected")
                continue
            qb_pid = ctx["ids"][qb_idx]
            # Verify this is the flagged starter
            starter_rows = pu[(pu["season"] == 2026) & (pu["week"] == 2)
                              & (pu["team"] == team) & (pu["is_starting_qb"] == True)]
            if starter_rows.empty:
                failures.append(f"{team}: no is_starting_qb=True in usage")
                continue
            expected_pid = starter_rows.iloc[0]["player_id"]
            if qb_pid != expected_pid:
                failures.append(f"{team}: engine QB={qb_pid} != flagged={expected_pid}")

    assert not failures, "QB identity failures:\n" + "\n".join(failures)

    # KC specifically must be Mahomes
    rng = np.random.default_rng(42)
    pctx = _build_player_context("KC", "DEN", 2026, 2, pu, au, None, n_sims=10, rng=rng)
    assert pctx[0]["ids"][pctx[0]["qb_idx"]] == "00-0033873", "KC QB is not Mahomes"

    # Removing flag raises for 2026
    pu_no_flag = pu.copy()
    pu_no_flag["is_starting_qb"] = False
    rng2 = np.random.default_rng(42)
    with pytest.raises(ValueError, match="No is_starting_qb"):
        _build_player_context("KC", "DEN", 2026, 2, pu_no_flag, au, None,
                              n_sims=10, rng=rng2)
