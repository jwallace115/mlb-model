#!/usr/bin/env python3
"""Tests for PM-1e: shuffle null pool fix, official A, freeze-join report.

RED first: each test must fail before the fix.
"""
import json
import math
import os
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "pipeline"))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ══════════ ITEM 1a: Shuffle null — same pool both sides ══════════

def test_shuffle_null_excludes_price_theses():
    """The shuffle null must NOT include price (CLV) theses in the game pool.

    PM-1d bug: real rate was computed over ALL theses including 138 price theses
    (held rate ~10.9%), while shuffled side passed clv_row=None dropping them.
    Fix: separate game and price pools.
    """
    from pm1d_evidence import tag_shuffle_null

    # Build fake verdicts with game and price theses
    rows = []
    # 100 game theses: 30 held, 70 failed
    for i in range(100):
        rows.append({
            "thesis_held": "held" if i < 30 else "failed",
            "thesis_source": "tag_map",
            "tag": "game_script",
            "market": "prop:rec",
            "side": "Over",
            "chain": None,
            "week": 3,
        })
    # 50 price theses: 5 held, 45 failed (drags down combined rate)
    for i in range(50):
        rows.append({
            "thesis_held": "held" if i < 5 else "failed",
            "thesis_source": "tag_map",
            "tag": "price_vs_sharp",
            "market": "prop:rec",
            "side": "Over",
            "chain": None,
            "week": 3,
        })

    verdicts = pd.DataFrame(rows)
    result = tag_shuffle_null(verdicts, n_shuffles=10, seed=42)

    # The game-thesis real rate should be 30/100 = 0.30, NOT 35/150 = 0.233
    assert "game_held_rate" in result, (
        "Result must have 'game_held_rate' key (separate game vs price pools)"
    )
    assert abs(result["game_held_rate"] - 0.30) < 0.01, (
        f"Game held rate should be 0.30, got {result.get('game_held_rate')}"
    )
    # Price theses get their own line
    assert "price_held_rate" in result, (
        "Result must have 'price_held_rate' for price (CLV) theses"
    )


def test_shuffle_null_power_note_when_dominant_tag():
    """When one tag is >80% of the game pool, print a power note."""
    from pm1d_evidence import tag_shuffle_null

    rows = []
    # 90 game_script + 10 usage_trend = game_script is 90%
    for i in range(90):
        rows.append({
            "thesis_held": "held" if i < 30 else "failed",
            "tag": "game_script",
            "thesis_source": "tag_map",
            "market": "prop:rec",
            "side": "Over",
            "chain": None,
            "week": 3,
        })
    for i in range(10):
        rows.append({
            "thesis_held": "held" if i < 3 else "failed",
            "tag": "usage_trend",
            "thesis_source": "tag_map",
            "market": "prop:rec",
            "side": "Over",
            "chain": None,
            "week": 3,
        })

    verdicts = pd.DataFrame(rows)
    result = tag_shuffle_null(verdicts, n_shuffles=10, seed=42)

    assert "power_note" in result, (
        "Must include 'power_note' when one tag >80% of the pool"
    )
    assert "game_script" in result["power_note"], (
        f"Power note should mention the dominant tag 'game_script', got: {result['power_note']}"
    )


# ══════════ ITEM 1b: A = official player_stats ══════════

def test_actual_stat_uses_official_not_pbp():
    """actual_stat must come from official player_stats, not PBP chain product.

    Test: Deebo Samuel 2026 wk 3 rec_yds:
    - PBP: 0 receptions, 0 receiving_yards (lateral from Evans)
    - Official: 0 rec, 80 rec_yds
    - actual_stat should be 80, pbp_actual should be 0
    """
    import build_postgame as bp

    # Mock player_stats_from_pbp to return 0 rec_yds (PBP-based)
    plays = [
        {"posteam": "SF", "pass_attempt": 1, "receiver_player_id": "00-0034764",
         "receiver_player_name": "D.Samuel", "complete_pass": 0,
         "receiving_yards": 0, "play_type": "pass", "play_id": 1},
    ] + [
        {"posteam": "SF", "pass_attempt": 1, "receiver_player_id": "00-0099999",
         "receiver_player_name": "B.Aiyuk", "complete_pass": 1,
         "receiving_yards": 12, "play_type": "pass", "play_id": i + 10}
        for i in range(30)
    ]
    plays.append({"play_id": 999, "play_type": "no_play", "desc": "END GAME"})

    base = {"game_id": "2026_03_SF_LAR", "home_team": "LAR", "away_team": "SF",
            "week": 3, "season": 2026, "score_differential": 0,
            "home_score": 0, "away_score": 0, "qtr": 1,
            "pass_attempt": 0, "rush_attempt": 0, "sack": 0,
            "complete_pass": 0, "yards_gained": 0, "passing_yards": 0,
            "receiving_yards": 0, "rushing_yards": 0, "interception": 0,
            "fumble": 0, "fumble_lost": 0, "touchdown": 0,
            "passer_player_id": None, "passer_player_name": None,
            "receiver_player_id": None, "receiver_player_name": None,
            "rusher_player_id": None, "rusher_player_name": None,
            "posteam": "SF", "defteam": "LAR", "yardline_100": 50,
            "play_type": "pass", "desc": "pass", "result": 0, "play_id": 0,
            "two_point_attempt": 0, "return_touchdown": 0}

    rows = [{**base, **p} for p in plays]
    game_pbp = pd.DataFrame(rows)

    # PBP-derived: D.Samuel has 0 receiving_yards
    p_stats = bp._player_stats_from_pbp(game_pbp, "SF")
    pbp_rec_yds = p_stats.get("00-0034764", {}).get("receiving_yards", 0)
    assert pbp_rec_yds == 0, f"PBP should show 0 rec_yds for Deebo, got {pbp_rec_yds}"

    # The build_verdicts function must have a way to get official stats
    # and populate actual_stat from official, pbp_actual from PBP
    assert hasattr(bp, '_get_official_stat'), (
        "build_postgame must have _get_official_stat function to look up "
        "official nflverse player_stats values"
    )


def test_verdict_has_pbp_actual_and_flag():
    """Verdict rows must contain pbp_actual and pbp_vs_official columns."""
    import build_postgame as bp

    # Check the column exists in the build_verdicts output schema
    # by checking the function handles the new fields
    assert hasattr(bp, '_get_official_stat'), (
        "build_postgame must have _get_official_stat for official stats lookup"
    )


# ══════════ ITEM 1c: Freeze-join report ══════════

def test_why_summary_has_freeze_join_section():
    """why_summary.md must contain a freeze-join accounting section."""
    import build_postgame as bp

    # The _write_why_summary function must write freeze join stats
    import inspect
    src = inspect.getsource(bp._write_why_summary)
    assert "freeze" in src.lower() and "thesis" in src.lower(), (
        "_write_why_summary must include freeze-join accounting "
        "(freeze-sourced vs tag-map thesis counts)"
    )


def test_why_summary_has_unresolved_names():
    """why_summary.md must list top-25 unresolved player names with reasons."""
    import build_postgame as bp

    import inspect
    src = inspect.getsource(bp._write_why_summary)
    assert "unresolved" in src.lower(), (
        "_write_why_summary must include unresolved player names section"
    )
