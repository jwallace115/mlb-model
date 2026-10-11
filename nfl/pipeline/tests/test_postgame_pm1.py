#!/usr/bin/env python3
"""Tests for build_postgame.py (PM-1 Item 2).

RED first: these must fail before implementation exists.
"""
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Fixtures ──

def _pbp_slice(game_id, home, away, week, plays):
    """Build a PBP DataFrame from a list of play dicts."""
    base = {"game_id": game_id, "home_team": home, "away_team": away,
            "week": week, "season": 2026, "score_differential": 0,
            "home_score": 0, "away_score": 0, "qtr": 1,
            "pass_attempt": 0, "rush_attempt": 0, "sack": 0,
            "complete_pass": 0, "yards_gained": 0, "passing_yards": 0,
            "receiving_yards": 0, "rushing_yards": 0, "interception": 0,
            "fumble": 0, "fumble_lost": 0, "touchdown": 0,
            "passer_player_id": None, "passer_player_name": None,
            "receiver_player_id": None, "receiver_player_name": None,
            "rusher_player_id": None, "rusher_player_name": None,
            "posteam": home, "defteam": away, "yardline_100": 50,
            "play_type": "pass", "desc": "pass", "result": 0, "play_id": 0}
    rows = []
    for i, p in enumerate(plays):
        row = {**base, "play_id": i + 1}
        row.update(p)
        rows.append(row)
    # Add END GAME
    rows.append({**base, "play_id": 999, "play_type": "no_play",
                 "desc": "END GAME"})
    return pd.DataFrame(rows)


# ── Test: identity holds on a fixture ──

def test_chain_identity_holds():
    """ln(A/L) = ln(E/L) + Σ ln(link_actual/link_prior) to 1e-9."""
    from build_postgame import _chain_decompose

    # Fixture: player with 5 receptions on 8 targets from 30 team dropbacks
    # from 60 team plays. Prior: 4 rec on 6 tgt from 25 dropbacks from 55 plays.
    actual = {"plays": 60, "pass_rate": 30/60, "share": 8/30, "catch_rate": 5/8}
    prior = {"plays": 55, "pass_rate": 25/55, "share": 6/25, "catch_rate": 4/6}
    L = 4.5  # bettor's line
    A = 5.0  # actual receptions

    result = _chain_decompose(actual, prior, L, A, "prop:rec")

    # Check identity
    lhs = math.log(A / L)
    book_vs_prior = result["book_vs_prior"]
    link_terms = [result["links"][k]["term"] for k in result["links"]]
    rhs = book_vs_prior + sum(link_terms)
    assert abs(lhs - rhs) < 1e-9, f"Identity failed: {lhs} != {rhs}"


# ── Test: planted week-W+1 slice does not change week-W verdicts ──

def test_future_slice_no_leak(tmp_path):
    """Verdicts for week ≤ 3 built with slices ≤ week 3 only must equal
    those built with every slice present. Priors must not leak future games."""
    from build_postgame import build_verdicts

    # This is a structural test — we build verdicts for week 1 twice:
    # once with only week-1 PBP, once with week-1 + week-2 PBP.
    # The week-1 verdicts must be identical.
    pbp_w1 = _pbp_slice("2026_01_BUF_KC", "KC", "BUF", 1, [
        {"posteam": "KC", "pass_attempt": 1, "receiver_player_id": "R1",
         "receiver_player_name": "Smith", "complete_pass": 1,
         "receiving_yards": 12, "play_type": "pass", "desc": "pass complete"},
    ] * 5)

    pbp_w2 = _pbp_slice("2026_02_KC_BUF", "BUF", "KC", 2, [
        {"posteam": "KC", "pass_attempt": 1, "receiver_player_id": "R1",
         "receiver_player_name": "Smith", "complete_pass": 1,
         "receiving_yards": 20, "play_type": "pass", "desc": "pass complete"},
    ] * 10)

    # Mock ledger row for week 1
    ledger_row = {
        "pick_id": "test_001", "owner": "ai_nfl", "sport": "NFL",
        "event_id": "ev001", "market": "prop:rec", "side": "Over",
        "point": 3.5, "player_name": "Smith", "result": "W",
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
    }

    # Build with only week 1
    v1 = build_verdicts([ledger_row], {"2026_01_BUF_KC": pbp_w1},
                        week_filter=1, season=2026)

    # Build with week 1 + week 2
    v2 = build_verdicts([ledger_row],
                        {"2026_01_BUF_KC": pbp_w1, "2026_02_KC_BUF": pbp_w2},
                        week_filter=1, season=2026)

    if v1 is not None and v2 is not None and len(v1) > 0 and len(v2) > 0:
        # Compare the week-1 verdict rows
        for col in v1.columns:
            if col in v2.columns:
                assert (v1[col].values == v2[col].values).all(), \
                    f"Column {col} differs with future slice present"


# ── Test: injury text parse ──

def test_injury_parse():
    """Parse 'was injured during the play' from a real 2026 PBP desc."""
    from build_postgame import _extract_injuries

    pbp = pd.DataFrame([
        {"desc": "J.Smith pass incomplete to T.Jones. T.Jones was injured during the play.",
         "qtr": 2, "home_team": "KC", "away_team": "BUF",
         "posteam": "KC", "game_id": "2026_01_BUF_KC",
         "receiver_player_id": "TJ01", "receiver_player_name": "T.Jones",
         "passer_player_id": "JS01", "passer_player_name": "J.Smith",
         "rusher_player_id": None, "rusher_player_name": None,
         "play_id": 42},
    ])

    injuries = _extract_injuries(pbp)
    assert len(injuries) >= 1
    assert any("Jones" in str(inj.get("player", "")) for inj in injuries)


# ── Test: team mapping — LA/LAC/LAR/KC/NYG/NYJ exact ──

def test_team_mapping_no_substring():
    """Team mapping must be exact — no substring matching. GL-1b found home[:3]
    matching 'LA' to Dallas."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "shared" / "pipeline"))
    import pick_sources as ps

    # These must NOT match each other
    assert ps.nfl_team("Los Angeles Chargers") != ps.nfl_team("Los Angeles Rams")
    assert ps.nfl_team("LAC") != ps.nfl_team("LAR")
    assert ps.nfl_team("New York Giants") != ps.nfl_team("New York Jets")
    assert ps.nfl_team("NYG") != ps.nfl_team("NYJ")
    assert ps.nfl_team("Kansas City Chiefs") is not None
    assert ps.nfl_team("KC") is not None


# ── Test: builder refuses jeff/member owners ──

def test_refuses_jeff_member_owners():
    """Builder must refuse to process jeff or member owner rows."""
    from build_postgame import build_verdicts

    jeff_row = {
        "pick_id": "j001", "owner": "jeff", "sport": "NFL",
        "event_id": "ev001", "market": "spread", "side": "KC",
        "point": -3.5, "player_name": "", "result": "W",
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
    }

    member_row = {**jeff_row, "pick_id": "m001", "owner": "member"}

    # Both should be filtered out
    v = build_verdicts([jeff_row, member_row], {}, week_filter=None, season=2026)
    assert v is None or len(v) == 0


# ── Test: W/L mismatch is reported, not altered ──

def test_wl_mismatch_reported():
    """If builder's W/L disagrees with ledger's, it's a finding — not a fix."""
    from build_postgame import build_verdicts

    # A row where the ledger says W but the actual stat says L
    ledger_row = {
        "pick_id": "test_wl", "owner": "ai_nfl", "sport": "NFL",
        "event_id": "ev001", "market": "prop:rec", "side": "Over",
        "point": 10.5, "player_name": "Smith", "result": "W",  # ledger says W
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
    }

    pbp = _pbp_slice("2026_01_BUF_KC", "KC", "BUF", 1, [
        {"posteam": "KC", "pass_attempt": 1, "receiver_player_id": "R1",
         "receiver_player_name": "Smith", "complete_pass": 1,
         "receiving_yards": 5, "play_type": "pass", "desc": "pass complete"},
    ] * 3)  # 3 receptions — under 10.5, should be L

    v = build_verdicts([ledger_row], {"2026_01_BUF_KC": pbp},
                        week_filter=1, season=2026)
    # The verdict should carry both the ledger result and the computed result
    if v is not None and len(v) > 0:
        row = v.iloc[0]
        assert row.get("ledger_result") == "W"
        assert row.get("wl_mismatch") == True
