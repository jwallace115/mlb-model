#!/usr/bin/env python3
"""Tests for pull_nfl_postgame_data.py (PM-1 Item 1).

RED first: these must fail before implementation exists.
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Fixtures ──

def _make_pbp_game(game_id, home, away, week, final=True):
    """Create a minimal PBP slice for one game."""
    plays = [
        {"game_id": game_id, "home_team": home, "away_team": away, "week": week,
         "play_id": 1, "play_type": "pass", "desc": f"{away} pass complete",
         "qtr": 1, "score_differential": 0, "home_score": 0, "away_score": 0,
         "pass_attempt": 1, "sack": 0, "rush_attempt": 0, "complete_pass": 1,
         "yards_gained": 10, "passing_yards": 10, "receiving_yards": 10,
         "rushing_yards": 0, "interception": 0, "fumble": 0, "fumble_lost": 0,
         "touchdown": 0, "posteam": away, "defteam": home,
         "receiver_player_id": "R1", "receiver_player_name": "Smith",
         "passer_player_id": "P1", "passer_player_name": "Jones",
         "rusher_player_id": None, "rusher_player_name": None,
         "yardline_100": 50, "season": 2026, "result": 0},
    ]
    if final:
        plays.append({
            **plays[0], "play_id": 999, "play_type": "no_play",
            "desc": "END GAME", "result": 0,
        })
    return pd.DataFrame(plays)


def _make_snap_counts(game_ids, week):
    rows = []
    for gid in game_ids:
        rows.append({"game_id": gid, "season": 2026, "week": week,
                      "player": "Smith", "pfr_player_id": "Smi01",
                      "position": "WR", "team": "KC", "opponent": "BUF",
                      "offense_snaps": 40, "offense_pct": 0.6,
                      "defense_snaps": 0, "defense_pct": 0.0,
                      "st_snaps": 2, "st_pct": 0.1,
                      "pfr_game_id": "xxx", "game_type": "REG"})
    return pd.DataFrame(rows)


@pytest.fixture
def scratch_dir(tmp_path):
    """Temp dir for RESULTS_ARCHIVE_DIR."""
    d = tmp_path / "results_archive"
    d.mkdir()
    return d


# ── Test: identical second run writes nothing ──

def test_idempotent_second_run(scratch_dir):
    """An identical second run writes nothing new (hash-skip)."""
    from pull_nfl_postgame_data import pull

    game_id = "2026_01_BUF_KC"
    pbp = _make_pbp_game(game_id, "KC", "BUF", 1, final=True)
    snaps = _make_snap_counts([game_id], 1)
    ftn = pd.DataFrame({"nflverse_game_id": [game_id], "season": [2026], "week": [1],
                         "qb_location": ["under_center"]})

    with patch.dict(os.environ, {"RESULTS_ARCHIVE_DIR": str(scratch_dir)}):
        with patch("pull_nfl_postgame_data.nflreadpy") as mock_nfl:
            mock_nfl.load_pbp.return_value = MagicMock(to_pandas=lambda: pbp)
            mock_nfl.load_snap_counts.return_value = MagicMock(to_pandas=lambda: snaps)
            mock_nfl.load_ftn_charting.return_value = MagicMock(to_pandas=lambda: ftn)

            result1 = pull(season=2026)
            written1 = result1["pbp_written"]

            # Second run — same data
            result2 = pull(season=2026)
            written2 = result2["pbp_written"]

    assert written1 > 0, "First run should write files"
    assert written2 == 0, "Second run should write nothing (hash-skip)"


# ── Test: changed slice writes new file, keeps old ──

def test_changed_slice_appends(scratch_dir):
    """A changed PBP slice writes a NEW file and leaves the old one."""
    from pull_nfl_postgame_data import pull

    game_id = "2026_01_BUF_KC"
    pbp_v1 = _make_pbp_game(game_id, "KC", "BUF", 1, final=True)
    snaps = _make_snap_counts([game_id], 1)
    ftn = pd.DataFrame()

    with patch.dict(os.environ, {"RESULTS_ARCHIVE_DIR": str(scratch_dir)}):
        with patch("pull_nfl_postgame_data.nflreadpy") as mock_nfl:
            mock_nfl.load_pbp.return_value = MagicMock(to_pandas=lambda: pbp_v1)
            mock_nfl.load_snap_counts.return_value = MagicMock(to_pandas=lambda: snaps)
            mock_nfl.load_ftn_charting.return_value = MagicMock(to_pandas=lambda: ftn)
            pull(season=2026)

        pbp_dir = scratch_dir / "nfl" / "pbp" / "season=2026"
        files_after_v1 = list(pbp_dir.glob(f"pbp_{game_id}_*.parquet"))
        assert len(files_after_v1) == 1

        # V2: add a play (stat correction)
        pbp_v2 = _make_pbp_game(game_id, "KC", "BUF", 1, final=True)
        extra = pbp_v2.iloc[:1].copy()
        extra["play_id"] = 500
        extra["desc"] = "Stat correction play"
        pbp_v2 = pd.concat([pbp_v2, extra], ignore_index=True)

        with patch("pull_nfl_postgame_data.nflreadpy") as mock_nfl:
            mock_nfl.load_pbp.return_value = MagicMock(to_pandas=lambda: pbp_v2)
            mock_nfl.load_snap_counts.return_value = MagicMock(to_pandas=lambda: snaps)
            mock_nfl.load_ftn_charting.return_value = MagicMock(to_pandas=lambda: ftn)
            pull(season=2026)

        files_after_v2 = list(pbp_dir.glob(f"pbp_{game_id}_*.parquet"))
        assert len(files_after_v2) == 2, "Changed slice should write new file, keep old"


# ── Test: non-final game is not written ──

def test_non_final_game_skipped(scratch_dir):
    """A game that is not final (no END GAME play) is not written."""
    from pull_nfl_postgame_data import pull

    game_id = "2026_05_NYG_PHI"
    pbp_live = _make_pbp_game(game_id, "PHI", "NYG", 5, final=False)
    snaps = pd.DataFrame()
    ftn = pd.DataFrame()

    with patch.dict(os.environ, {"RESULTS_ARCHIVE_DIR": str(scratch_dir)}):
        with patch("pull_nfl_postgame_data.nflreadpy") as mock_nfl:
            mock_nfl.load_pbp.return_value = MagicMock(to_pandas=lambda: pbp_live)
            mock_nfl.load_snap_counts.return_value = MagicMock(to_pandas=lambda: snaps)
            mock_nfl.load_ftn_charting.return_value = MagicMock(to_pandas=lambda: ftn)
            result = pull(season=2026)

    assert result["pbp_written"] == 0, "Non-final game should not be written"


# ── Test: missing required column HALTs ──

def test_missing_column_halts(scratch_dir):
    """If PBP lacks a required column, pull() must HALT (raise)."""
    from pull_nfl_postgame_data import pull

    game_id = "2026_01_BUF_KC"
    pbp = _make_pbp_game(game_id, "KC", "BUF", 1, final=True)
    # Drop a required column
    pbp = pbp.drop(columns=["score_differential"])

    with patch.dict(os.environ, {"RESULTS_ARCHIVE_DIR": str(scratch_dir)}):
        with patch("pull_nfl_postgame_data.nflreadpy") as mock_nfl:
            mock_nfl.load_pbp.return_value = MagicMock(to_pandas=lambda: pbp)
            mock_nfl.load_snap_counts.return_value = MagicMock(to_pandas=lambda: pd.DataFrame())
            mock_nfl.load_ftn_charting.return_value = MagicMock(to_pandas=lambda: pd.DataFrame())
            with pytest.raises(SystemExit):
                pull(season=2026)
