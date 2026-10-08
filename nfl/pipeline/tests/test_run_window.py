"""Test: run_window.py --no-pull STOPs when freeze HALTs on kicked games.

The freeze must refuse when all games have kicked off (commence_time <= now).
A fixture tree with only kicked games triggers this HALT.
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable


class TestRunWindowHalt:
    """--no-pull run on a fixture tree STOPs when freeze HALTs (kicked games)."""

    def test_freeze_halts_on_kicked_games(self, tmp_path):
        """A sheet with only kicked games -> freeze HALTs -> run_window exits non-zero."""
        # Build a fixture tree with props and lines where all games have kicked
        kicked_time = "2026-09-20T17:00:00Z"  # in the past

        # Props with a kicked game
        props_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=09"
        props_dir.mkdir(parents=True)
        props = pd.DataFrame([{
            "sport": "nfl", "event_id": "kicked_ev1", "game_date": "2026-09-20",
            "commence_time": kicked_time,
            "home_team": "Buffalo Bills", "away_team": "New England Patriots",
            "bookmaker": "hardrockbet_fl", "market_key": "player_pass_yds",
            "last_update": "2026-09-20T14:00:00Z", "player_name": "Test QB",
            "line": 250.5, "over_price": -110, "under_price": -110,
            "implied_over": 0.524, "implied_under": 0.524,
            "pull_batch": "test", "pull_timestamp": "2026-09-20T14:00:00+00:00",
            "snapshot_tag": "mid",
        }])
        props.to_parquet(props_dir / "data_2026_09.parquet", index=False)

        # Game-line snapshot
        lines_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        lines_dir.mkdir(parents=True)
        lines = pd.DataFrame([
            {"snapshot_utc": "2026-09-20T14:00:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "kicked_ev1",
             "commence_time": kicked_time,
             "home_team": "Buffalo Bills", "away_team": "New England Patriots",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-09-20T14:00:00Z",
             "market": "h2h", "outcome_name": "Buffalo Bills", "point": None, "price": -180},
            {"snapshot_utc": "2026-09-20T14:00:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "kicked_ev1",
             "commence_time": kicked_time,
             "home_team": "Buffalo Bills", "away_team": "New England Patriots",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-09-20T14:00:00Z",
             "market": "h2h", "outcome_name": "New England Patriots", "point": None, "price": 150},
        ])
        lines.to_parquet(lines_dir / "snap_20260920T140000Z.parquet", index=False)

        # Empty Kalshi/NWS dirs
        (tmp_path / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
        (tmp_path / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026").mkdir(parents=True)

        # Board dir
        (tmp_path / "nfl" / "data" / "board").mkdir(parents=True)

        # run_window should HALT because all games have kicked
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "run_window.py"),
             "--sport", "nfl", "--window", "adhoc", "--no-pull",
             "--reader-model", "test-model", "--week", "3"],
            cwd=str(tmp_path),
            capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                 "MLB_REPO_ROOT": str(tmp_path),
                 "PYTHONPATH": str(ROOT),
                 "HOME": str(Path.home())},
            timeout=30)

        # Should exit non-zero (HALT from sheet or freeze)
        assert result.returncode != 0, (
            f"Expected non-zero exit (HALT on kicked games), got 0.\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}")
