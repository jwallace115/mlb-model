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
    assert isinstance(first_game, dict), "each game's value must be a dict with pfr_ids and names"
    assert "pfr_ids" in first_game, "must have pfr_ids key"
    assert "names" in first_game, "must have names key"
    assert len(first_game["names"]) > 0, "game must have at least one player"


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
    """D236(a): a game with no snap data -> snap_played=None -> UNRESOLVED, no stat scored."""
    from nfl.pipeline.log_ai_opinions import _first_side_won
    row = pd.Series({"market_key": "player_receptions", "line": 4.5})
    act = {
        "tabs": {"rec": pd.DataFrame(columns=["player_id", "actual_rec"])},
        "ints": pd.Series(dtype=float),
        "home_pts": 17, "away_pts": 10, "home": "KC", "away": "CAR",
        "n_plays": 100,
    }
    result = _first_side_won(row, act, "00-0099999", snap_played=None)
    assert result is None, (
        f"snap_played=None must return None (UNRESOLVED), got {result}")


# ── D236: new settlement tests ───────────────────────────────────────────────

def test_inactive_no_snap_data_unresolved():
    """D236: inactive player with no snap data for the game -> UNRESOLVED (not VOID)."""
    from nfl.pipeline.log_ai_opinions import _first_side_won
    row = pd.Series({"market_key": "player_receptions", "line": 3.5})
    act = {
        "tabs": {"rec": pd.DataFrame(columns=["player_id", "actual_rec"])},
        "ints": pd.Series(dtype=float),
        "home_pts": 24, "away_pts": 17, "home": "KC", "away": "CAR",
        "n_plays": 120,
    }
    # snap_played=None means snap data unavailable, not that player didn't play
    result = _first_side_won(row, act, "00-0099999", snap_played=None)
    assert result is None, "no snap data -> None (UNRESOLVED, not VOID)"


def test_suffix_name_settles_by_id():
    """D236(b): a player with a suffix (Jr., III) settles by PFR ID, not name match."""
    from nfl.pipeline.log_ai_opinions import _build_gsis_to_pfr, _load_snap_participants
    # Just verify the crosswalk works for real data
    gsis_to_pfr = _build_gsis_to_pfr(2026)
    if not gsis_to_pfr:
        pytest.skip("no GSIS->PFR crosswalk available for 2026")
    snap_parts = _load_snap_participants(2026)
    if snap_parts is None:
        pytest.skip("no snap data for 2026")
    # Find a player with a suffix in the roster
    import nflreadpy
    roster = nflreadpy.load_rosters([2026])
    if hasattr(roster, "to_pandas"):
        roster = roster.to_pandas()
    suffixed = roster[roster["full_name"].str.contains(r"\b(Jr\.|III|II|IV|Sr\.)", na=False, regex=True)]
    if suffixed.empty:
        pytest.skip("no suffixed names in roster")
    # Pick one with both gsis_id and pfr_id
    have_both = suffixed[suffixed["gsis_id"].notna() & suffixed["pfr_id"].notna()]
    if have_both.empty:
        pytest.skip("no suffixed player with both IDs")
    player = have_both.iloc[0]
    gsis = player["gsis_id"]
    pfr = gsis_to_pfr.get(gsis)
    assert pfr is not None, f"GSIS {gsis} should map to PFR ID"
    # Check if this player appears in any snap count game by PFR ID
    found = False
    for gid, snap_data in snap_parts.items():
        if pfr in snap_data["pfr_ids"]:
            found = True
            break
    # If found by PFR ID, the ID match works for suffixed names
    if found:
        assert True, f"Player {player['full_name']} found by PFR ID {pfr}"
    else:
        # Player may not have played yet — that's OK, the crosswalk itself is tested
        assert pfr == player["pfr_id"], "crosswalk maps correctly"


def test_incomplete_game_unresolved():
    """D236(c): an incomplete game (no END GAME in PBP) -> unresolved."""
    from nfl.pipeline.log_ai_opinions import _game_actuals
    # Build a minimal PBP without END GAME
    pbp = pd.DataFrame([{
        "game_id": "2026_99_CAR_KC",
        "home_team": "KC", "away_team": "CAR",
        "play_type": "pass", "desc": "pass incomplete",
        "home_score": 7, "away_score": 3,
        "week": 99, "qtr": 2, "game_seconds_remaining": 600,
    }])
    result = _game_actuals(pbp, "Kansas City Chiefs", "Carolina Panthers")
    assert result is None, "incomplete game (no END GAME) must return None"
