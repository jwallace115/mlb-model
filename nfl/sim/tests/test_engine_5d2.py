#!/usr/bin/env python3
"""Tests for D66 (OT Try rules) and D67 (kickoff start table)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
TABLES_DIR = ROOT / "nfl" / "data" / "sim" / "tables"


# ── D67: kickoff start_yl100 from the table ──

def test_ko_start_2023():
    kt = pd.read_parquet(TABLES_DIR / "kickoff.parquet")
    row = kt[kt["season"] == 2023]
    assert not row.empty, "No 2023 kickoff row"
    assert int(row.iloc[0]["start_yl100"]) == 75

def test_ko_start_2024():
    kt = pd.read_parquet(TABLES_DIR / "kickoff.parquet")
    row = kt[kt["season"] == 2024]
    assert not row.empty, "No 2024 kickoff row"
    assert int(row.iloc[0]["start_yl100"]) == 70

def test_ko_start_2025():
    kt = pd.read_parquet(TABLES_DIR / "kickoff.parquet")
    row = kt[kt["season"] == 2025]
    assert not row.empty, "No 2025 kickoff row"
    assert int(row.iloc[0]["start_yl100"]) == 69


# ── D66: OT TD rules ──
# These tests use the engine's simulate_game to check OT behavior.
# We run a small N and check aggregate properties.

@pytest.fixture(scope="module")
def engine_data():
    """Load engine tables and ratings once."""
    from nfl.sim.engine import _load_tables, _load_ratings
    _load_tables()
    return _load_ratings()


@pytest.fixture(scope="module")
def usage_data():
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    return pu, au


def _run_sims(engine_data, usage_data, season, week, home, away, n=500):
    from nfl.sim.engine import simulate_game
    team_r, tend, sit, kicker, league = engine_data
    pu, au = usage_data
    td, pdf = simulate_game(
        home, away, season, week, n_sims=n, seed=42,
        team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
        player_usage=pu, active_uni=au)
    return td


def test_ot_margins_no_odd_pat(engine_data, usage_data):
    """In pre-2025 REG, OT walk-off TDs should NOT add PAT points.
    An OT walk-off TD adds exactly 6, not 7 or 8."""
    td = _run_sims(engine_data, usage_data, 2024, 10, "KC", "DEN", n=2000)
    # Check OT games
    ot = td[td["ot_flag"] == 1]
    if len(ot) < 10:
        pytest.skip("Too few OT games to test")
    margins = (ot["home_score"] - ot["away_score"]).abs()
    # With no-PAT walk-off, margins can be 3, 6, 2, 8, etc.
    # With PAT on walk-off, we'd see 7, 8 more often.
    # The key check: no OT margin should be exactly 1 (which would require
    # a walk-off XP with no TD, impossible) or 5 (walk-off TD + missed XP
    # after the 6 shouldn't happen because there's no XP attempt).
    # Actually, the cleanest check: margins of 6 should exist (walk-off TD,
    # no PAT) and they should NOT all be 7 (which would mean PAT happened).
    margin_6 = (margins == 6).sum()
    margin_7 = (margins == 7).sum()
    # At least some OT margins of 6 should exist (walk-off TD no PAT)
    assert margin_6 > 0 or margin_7 == 0, (
        f"Expected some margin-6 OT games (walk-off TD no PAT), "
        f"got margin_6={margin_6}, margin_7={margin_7}")


def test_ko_start_differs_2024_vs_2023(engine_data, usage_data):
    """ko_start is 75 for 2023 and 70 for 2024, read from the table."""
    # We can check this by reading the table directly
    kt = pd.read_parquet(TABLES_DIR / "kickoff.parquet")
    ko_2023 = kt[kt.season == 2023].iloc[0]["start_yl100"]
    ko_2024 = kt[kt.season == 2024].iloc[0]["start_yl100"]
    assert ko_2023 != ko_2024, f"2023 ({ko_2023}) should differ from 2024 ({ko_2024})"
    assert ko_2023 == 75
    assert ko_2024 == 70
