"""D227: tests for settlement, cohort, and scoring.

Every test calls the real function and fails on 9eb505235.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_inactive_player_void():
    """A1: an inactive player's Under is VOID (None), not 0.

    On 9eb505235, _first_side_won returned 0 for a player not in PBP stats,
    which scored the Under as a win (0.0 < 5.5). D227 makes it VOID.
    """
    from nfl.pipeline.log_ai_opinions import _first_side_won

    row = pd.Series({
        "market_key": "player_receptions",
        "line": 5.5,
    })

    # Game actuals with a participants set that does NOT include the player
    act = {
        "tabs": {
            "rec": pd.DataFrame(columns=["player_id", "actual_rec"]),
        },
        "ints": pd.Series(dtype=float),
        "home_pts": 24, "away_pts": 17,
        "home": "KC", "away": "CAR",
        "n_plays": 150,
        "participants": {"00-0001111", "00-0002222"},  # player NOT here
    }

    pid = "00-0099999"  # not in participants
    result = _first_side_won(row, act, pid)
    assert result is None, (
        f"inactive player should be VOID (None), got {result}")


def test_active_player_zero_receptions():
    """An active player with 0 receptions is scored normally (Under wins)."""
    from nfl.pipeline.log_ai_opinions import _first_side_won

    row = pd.Series({
        "market_key": "player_receptions",
        "line": 5.5,
    })

    act = {
        "tabs": {
            "rec": pd.DataFrame(columns=["player_id", "actual_rec"]),
        },
        "ints": pd.Series(dtype=float),
        "home_pts": 24, "away_pts": 17,
        "home": "KC", "away": "CAR",
        "n_plays": 150,
        "participants": {"00-0099999", "00-0001111"},  # player IS here
    }

    pid = "00-0099999"  # in participants but no stats
    result = _first_side_won(row, act, pid)
    # 0.0 < 5.5, so first side (Over) lost -> 0
    assert result == 0, f"active player with 0 rec should score 0, got {result}"


def test_cohort_excludes_wrong_reader():
    """A7: another reader must NOT enter the primary cohort."""
    from nfl.pipeline.log_ai_opinions import primary_cohort

    df = pd.DataFrame([{
        "reader_model": "some_other_model",
        "pilot": False, "revision": 0,
        "tag": "sim_v1", "two_way": True,
        "market_key": "player_receptions",
        "settlement": "settled",
        "graded": True,
        "home_team": "Kansas City Chiefs",
        "away_team": "Carolina Panthers",
        "p_first": 0.55, "book_p_first": 0.50, "y_first": 1,
    }])

    cohort, exclusions = primary_cohort(df, "nfl_sim_v1_156cd057")
    assert len(cohort) == 0, "wrong reader should be excluded from cohort"
    assert "reader != canonical" in exclusions


def test_cohort_excludes_unanchored_game():
    """A7: an unanchored game must NOT enter the primary cohort."""
    from nfl.pipeline.log_ai_opinions import primary_cohort

    df = pd.DataFrame([{
        "reader_model": "nfl_sim_v1_156cd057",
        "pilot": False, "revision": 0,
        "tag": "sim_v1", "two_way": True,
        "market_key": "player_receptions",
        "settlement": "settled",
        "graded": True,
        "home_team": "Kansas City Chiefs",
        "away_team": "Carolina Panthers",
        "p_first": 0.55, "book_p_first": 0.50, "y_first": 1,
    }])

    # Sidecar says CAR@KC is NOT anchored
    sidecar = pd.DataFrame([{
        "game": "CAR@KC",
        "anchored": False,
        "target_spread": -3.0, "target_total": 43.5,
    }])

    cohort, exclusions = primary_cohort(df, "nfl_sim_v1_156cd057",
                                         anchor_sidecar_df=sidecar)
    assert len(cohort) == 0, "unanchored game should be excluded"
    assert "game not anchored" in exclusions


def test_settlement_column_exists():
    """D227: the score function must produce a settlement column."""
    import inspect
    from nfl.pipeline.log_ai_opinions import score
    src = inspect.getsource(score)
    assert '"settlement"' in src or "'settlement'" in src, (
        "score() must produce a settlement column (settled/void/unresolved)")


def test_participants_in_game_actuals():
    """D227: _game_actuals must return a participants set."""
    import inspect
    from nfl.pipeline.log_ai_opinions import _game_actuals
    src = inspect.getsource(_game_actuals)
    assert "participants" in src, (
        "_game_actuals must include a participants set for VOID detection")
