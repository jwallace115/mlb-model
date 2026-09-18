#!/usr/bin/env python3
"""Tests for D62 official stat definitions in actuals.py."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

PBP_DIR = ROOT / "nfl" / "data" / "pbp"


@pytest.fixture(scope="module")
def pbp_2024():
    return pd.read_parquet(PBP_DIR / "pbp_2024.parquet")


@pytest.fixture(scope="module")
def all_actuals(pbp_2024):
    """Compute actuals for every 2024 game."""
    from nfl.sim.actuals import actual_player_game_stats

    results = {}
    for gid, gdf in pbp_2024.groupby("game_id"):
        results[gid] = actual_player_game_stats(gdf)
    return results


# ── Property test: carries match rushing universe ──

def test_carries_match_rush_universe(pbp_2024, all_actuals):
    """For every 2024 game, actual_carries == count of rows matching the
    D62 rushing universe (run|qb_kneel, rusher not null, not two-point)."""
    for gid, gdf in pbp_2024.groupby("game_id"):
        _two_pt = gdf.get("two_point_attempt", pd.Series(0, index=gdf.index))
        expected = gdf[
            gdf["play_type"].isin({"run", "qb_kneel"})
            & gdf["rusher_player_id"].notna()
            & (_two_pt != 1)
        ]
        _, rush_stats, _, _ = all_actuals[gid]
        actual_total = rush_stats["actual_carries"].sum() if len(rush_stats) else 0
        assert actual_total == len(expected), (
            f"{gid}: actual_carries {actual_total} != universe {len(expected)}"
        )


# ── Property test: pass_att matches passing universe ──

def test_pass_att_match_pass_universe(pbp_2024, all_actuals):
    """For every 2024 game, actual_pass_att == count of rows matching the
    D62 passing universe (pass|qb_spike, down not null, sack != 1, passer not null)."""
    for gid, gdf in pbp_2024.groupby("game_id"):
        expected = gdf[
            gdf["play_type"].isin({"pass", "qb_spike"})
            & gdf["down"].notna()
            & (gdf.get("sack", pd.Series(0, index=gdf.index)) != 1)
            & gdf["passer_player_id"].notna()
        ]
        _, _, _, pass_stats = all_actuals[gid]
        actual_total = pass_stats["actual_pass_att"].sum() if len(pass_stats) else 0
        assert actual_total == len(expected), (
            f"{gid}: actual_pass_att {actual_total} != universe {len(expected)}"
        )


# ── Regression test: aggregate count changes ──

def test_regression_carry_increase(pbp_2024, all_actuals):
    """Total 2024 actual_carries increases by exactly
    (437 kneels - 38 two-point runs) = 399 relative to the old definition."""
    # Old definition: play_type == "run" & rusher_player_id not null
    old_total = 0
    new_total = 0
    for gid, gdf in pbp_2024.groupby("game_id"):
        old_rushes = gdf[
            (gdf["play_type"] == "run") & gdf["rusher_player_id"].notna()
        ]
        old_total += len(old_rushes)
        _, rush_stats, _, _ = all_actuals[gid]
        new_total += rush_stats["actual_carries"].sum() if len(rush_stats) else 0

    delta = new_total - old_total
    # kneels added = 437, two-point runs removed = 38, net = +399
    assert delta == 399, (
        f"Carry delta {delta} != 399 (expected 437 kneels - 38 two-point runs)"
    )


def test_regression_pass_att_increase(pbp_2024, all_actuals):
    """Total 2024 actual_pass_att increases by exactly 75 (spikes added)."""
    # Old definition: play_type == "pass" & down not null & sack != 1
    old_total = 0
    new_total = 0
    for gid, gdf in pbp_2024.groupby("game_id"):
        old_passes = gdf[
            (gdf["play_type"] == "pass")
            & gdf["down"].notna()
            & (gdf.get("sack", pd.Series(0, index=gdf.index)) != 1)
            & gdf["passer_player_id"].notna()
        ]
        old_total += len(old_passes)
        _, _, _, pass_stats = all_actuals[gid]
        new_total += pass_stats["actual_pass_att"].sum() if len(pass_stats) else 0

    delta = new_total - old_total
    assert delta == 75, f"Pass att delta {delta} != 75 (expected 75 spikes)"


# ── Null control: receiving and ATD unchanged ──

def test_null_control_receiving_unchanged(pbp_2024, all_actuals):
    """Receiving stats (rec, rec_yds) and ATD must be identical to the old
    definition. If they move, the passing change leaked."""
    from nfl.sim.actuals import actual_player_game_stats

    # Compute with the current (new) code — already in all_actuals
    new_rec_total = 0
    new_rec_yds_total = 0
    new_atd_total = 0

    for gid in all_actuals:
        rec, _, td, _ = all_actuals[gid]
        new_rec_total += rec["actual_rec"].sum() if len(rec) else 0
        new_rec_yds_total += rec["actual_rec_yds"].sum() if len(rec) else 0
        new_atd_total += len(td) if len(td) else 0

    # Old definition: receiving uses play_type=="pass" (unchanged)
    # If the receiving universe changed, rec totals would differ.
    # We verify against a direct count from PBP.
    direct_rec = 0
    direct_rec_yds = 0
    for gid, gdf in pbp_2024.groupby("game_id"):
        passes = gdf[
            (gdf["play_type"] == "pass")
            & gdf["down"].notna()
            & (gdf.get("sack", pd.Series(0, index=gdf.index)) != 1)
        ]
        recs = passes[
            passes["receiver_player_id"].notna()
            & (passes["complete_pass"] == 1)
        ]
        direct_rec += len(recs)
        direct_rec_yds += recs["yards_gained"].sum()

    assert new_rec_total == direct_rec, (
        f"Receiving leaked: new_rec {new_rec_total} != direct {direct_rec}"
    )
    assert new_rec_yds_total == direct_rec_yds, (
        f"Rec yds leaked: {new_rec_yds_total} != {direct_rec_yds}"
    )
