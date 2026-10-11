#!/usr/bin/env python3
"""RED-FIRST tests for PM-1b Item 1: join fixes in build_postgame.py.

Finding 1: build_verdicts matches every ledger row to the FIRST PBP slice.
Finding 2: player matching uses substring (player_name.lower() in name.lower()).

These must FAIL on the current code, then PASS after the fix.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "shared" / "pipeline"))


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
    rows.append({**base, "play_id": 999, "play_type": "no_play", "desc": "END GAME"})
    return pd.DataFrame(rows)


# ── Finding 1: two games, pick belongs to the SECOND slice ──

def test_two_games_pick_matches_second_slice():
    """With two PBP slices, a pick belonging to game 2 must produce a verdict
    for game 2 — not game 1.  On the pre-fix code this fails because
    build_verdicts iterates pbp_slices and breaks on the first entry."""
    from build_postgame import build_verdicts

    # Game 1: KC vs BUF (week 1) — the WRONG game
    pbp_game1 = _pbp_slice("2026_01_BUF_KC", "KC", "BUF", 1, [
        {"posteam": "KC", "pass_attempt": 1, "receiver_player_id": "R_WRONG",
         "receiver_player_name": "J.Wrong", "complete_pass": 1,
         "receiving_yards": 10, "play_type": "pass"},
    ] * 4)

    # Game 2: DET vs CHI (week 1) — the RIGHT game, with our player
    pbp_game2 = _pbp_slice("2026_01_CHI_DET", "DET", "CHI", 1, [
        {"posteam": "DET", "pass_attempt": 1, "receiver_player_id": "R_RIGHT",
         "receiver_player_name": "A.StBrown", "complete_pass": 1,
         "receiving_yards": 15, "play_type": "pass"},
    ] * 6)

    # Ledger row for the DET@CHI game (game 2)
    ledger_row = {
        "pick_id": "test_g2", "owner": "ai_nfl", "sport": "NFL",
        "event_id": "ev_det_chi", "market": "prop:rec", "side": "Over",
        "point": 4.5, "player_name": "A.StBrown", "result": "W",
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
        "home": "DET", "away": "CHI",
    }

    # Dict is ordered in Python 3.7+; game 1 is first
    slices = {
        "2026_01_BUF_KC": pbp_game1,
        "2026_01_CHI_DET": pbp_game2,
    }

    v = build_verdicts([ledger_row], slices, week_filter=1, season=2026)
    assert v is not None and len(v) > 0, "Expected at least one verdict row"

    row = v.iloc[0]
    assert row["game_id"] == "2026_01_CHI_DET", (
        f"Verdict matched game_id={row['game_id']}; expected 2026_01_CHI_DET. "
        "This is Finding 1: the builder matched the FIRST slice, not the correct one."
    )


# ── Finding 2: substring name collision ──

def test_substring_name_collision():
    """'Ian Thomas' must NOT match 'Brian Thomas Jr.' in the PBP.
    Real 2026 pair from player_stats_2026: 'Ian Thomas' (CAR TE) is a
    substring of 'Brian Thomas Jr.' (JAX WR) — 'ian thomas' in
    'brian thomas jr.' is True.

    On the pre-fix code this fails because player matching uses
    `player_name.lower() in name.lower()`.  The PBP fixture uses full
    display names so the substring collision fires."""
    from build_postgame import build_verdicts

    # PBP with BOTH players — use full display names to trigger the bug
    plays = [
        # Brian Thomas Jr. — 5 receptions (comes FIRST in iteration)
        {"posteam": "JAX", "defteam": "IND", "pass_attempt": 1,
         "receiver_player_id": "BTJ01",
         "receiver_player_name": "Brian Thomas Jr.",
         "complete_pass": 1, "receiving_yards": 18, "play_type": "pass"},
    ] * 5 + [
        # Ian Thomas — 2 receptions (the CORRECT player for the pick)
        {"posteam": "JAX", "defteam": "IND", "pass_attempt": 1,
         "receiver_player_id": "IT01",
         "receiver_player_name": "Ian Thomas",
         "complete_pass": 1, "receiving_yards": 8, "play_type": "pass"},
    ] * 2

    pbp = _pbp_slice("2026_01_IND_JAX", "JAX", "IND", 1, plays)

    # Ledger row for Ian Thomas — pick is over 1.5 receptions
    ledger_row = {
        "pick_id": "test_ian", "owner": "ai_nfl", "sport": "NFL",
        "event_id": "ev_jax_ind", "market": "prop:rec", "side": "Over",
        "point": 1.5, "player_name": "Ian Thomas", "result": "W",
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
        "home": "JAX", "away": "IND",
        "player_id": "IT01",
    }

    slices = {"2026_01_IND_JAX": pbp}

    v = build_verdicts([ledger_row], slices, week_filter=1, season=2026)

    assert v is not None and len(v) > 0, "Expected at least one verdict row"
    row = v.iloc[0]
    # actual_stat must be 2 (Ian Thomas), not 5 (Brian Thomas Jr.)
    assert "actual_stat" in row.index and row["actual_stat"] is not None, \
        "Expected actual_stat to be computed"
    assert row["actual_stat"] == 2, (
        f"actual_stat={row['actual_stat']}; expected 2 (Ian Thomas). "
        "Got Brian Thomas Jr.'s 5 receptions — substring match collision. "
        "This is Finding 2: 'ian thomas' in 'brian thomas jr.' is True."
    )
