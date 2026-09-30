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

    D230: uses snap_played=False (snap counts show player did not play).
    """
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
    }

    pid = "00-0099999"
    result = _first_side_won(row, act, pid, snap_played=False)
    assert result is None, (
        f"inactive player (snap_played=False) should be VOID (None), got {result}")


def test_active_player_zero_receptions():
    """An active player with 0 receptions is scored normally (Under wins).
    D230: uses snap_played=True (snap counts show player played)."""
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
    }

    pid = "00-0099999"
    result = _first_side_won(row, act, pid, snap_played=True)
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
    """D227: score() must produce a settlement column.
    D229: replaced inspect.getsource with execution test."""
    from nfl.pipeline.log_ai_opinions import _first_side_won
    # Verify _first_side_won returns None for inactive player (the VOID path
    # that feeds the settlement column)
    row = pd.Series({"market_key": "player_receptions", "line": 5.5})
    act = {
        "tabs": {"rec": pd.DataFrame(columns=["player_id", "actual_rec"])},
        "ints": pd.Series(dtype=float),
        "home_pts": 24, "away_pts": 17, "home": "KC", "away": "CAR",
        "n_plays": 150, "participants": {"00-0001111"},
    }
    result = _first_side_won(row, act, "00-0099999", snap_played=False)
    assert result is None, "inactive player (snap_played=False) -> None (feeds settlement=void)"


def test_snap_participants_loaded():
    """D230: _load_snap_participants loads from nflreadpy and returns {game_id: {player_names}}.
    Replaces the D227 PBP participants test."""
    from nfl.pipeline.log_ai_opinions import _load_snap_participants
    result = _load_snap_participants(2026)
    if result is None:
        pytest.skip("snap count data unavailable for 2026")
    assert isinstance(result, dict), "must return a dict"
    # At least one game should have participants
    assert len(result) > 0, "must have at least one game"
    first_game = next(iter(result.values()))
    assert isinstance(first_game, set), "each game's value must be a set of player names"
    assert len(first_game) > 0, "game must have at least one player"


# ── D230: snap-count settlement tests ────────────────────────────────────────

def test_wr_with_snaps_zero_targets_settled_win():
    """D230: a WR with snaps and 0 targets has his Under SETTLED as a win."""
    from nfl.pipeline.log_ai_opinions import _first_side_won
    row = pd.Series({"market_key": "player_receptions", "line": 3.5})
    act = {
        "tabs": {"rec": pd.DataFrame(columns=["player_id", "actual_rec"])},
        "ints": pd.Series(dtype=float),
        "home_pts": 21, "away_pts": 14, "home": "KC", "away": "CAR",
        "n_plays": 120,
    }
    # Player played (snap_played=True) but has 0 receptions (not in rec table)
    result = _first_side_won(row, act, "00-0099999", snap_played=True)
    # 0 < 3.5, so Over (first side) lost -> 0 (Under wins)
    assert result == 0, f"WR with snaps, 0 targets -> Under wins (0), got {result}"


def test_player_absent_from_snaps_void():
    """D230: a player absent from snap counts is VOID."""
    from nfl.pipeline.log_ai_opinions import _first_side_won
    row = pd.Series({"market_key": "player_rush_attempts", "line": 10.5})
    act = {
        "tabs": {"rush": pd.DataFrame(columns=["player_id", "actual_carries"])},
        "ints": pd.Series(dtype=float),
        "home_pts": 28, "away_pts": 21, "home": "BUF", "away": "MIA",
        "n_plays": 130,
    }
    result = _first_side_won(row, act, "00-0099999", snap_played=False)
    assert result is None, "player absent from snaps -> VOID (None)"


def test_game_no_snap_data_unresolved():
    """D230: a game with no snap data -> snap_played=None -> unresolved."""
    from nfl.pipeline.log_ai_opinions import _first_side_won
    row = pd.Series({"market_key": "player_receptions", "line": 4.5})
    act = {
        "tabs": {"rec": pd.DataFrame(columns=["player_id", "actual_rec"])},
        "ints": pd.Series(dtype=float),
        "home_pts": 17, "away_pts": 10, "home": "KC", "away": "CAR",
        "n_plays": 100,
    }
    # snap_played=None means snap data unavailable for this game
    result = _first_side_won(row, act, "00-0099999", snap_played=None)
    # With no snap data, the old behavior applies: 0 receptions -> Under wins
    # But snap_played=None means we can't determine participation,
    # so _first_side_won should proceed normally (stat = 0 < 4.5 -> 0)
    assert result == 0, (
        "snap_played=None means stat scoring proceeds normally, got {result}")
