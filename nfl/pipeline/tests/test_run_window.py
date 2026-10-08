"""Test: run_window.py — OPS4b + OPS4c tests.

OPS4b: --no-pull STOPs when freeze HALTs on kicked games.
OPS4c: --tag prekick accepted by puller; --auto-prekick gates on kick window;
       --commit branch:<name> produces a commit.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
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
            timeout=120)

        # Should exit non-zero (HALT from sheet or freeze)
        assert result.returncode != 0, (
            f"Expected non-zero exit (HALT on kicked games), got 0.\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}")


# ---- OPS4c Item 2 ----

class TestPullerTagPrekick:
    """--tag prekick must be accepted by pull_hardrock_props.py argparse."""

    def test_tag_prekick_accepted(self):
        """--tag prekick --dry-run should NOT exit with argparse error."""
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "pull_hardrock_props.py"),
             "--window-hours", "6", "--tag", "prekick", "--dry-run"],
            capture_output=True, text=True, timeout=30,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                 "HOME": str(Path.home()),
                 "PYTHONPATH": str(ROOT),
                 "ODDS_API_KEY": ""})
        # argparse error = exit 2 with "invalid choice"
        assert "invalid choice" not in result.stderr, \
            f"--tag prekick rejected by argparse: {result.stderr[:300]}"


class TestAutoPreKick:
    """--auto-prekick gates on the kick window."""

    def test_no_game_in_slot(self):
        """Fixture snapshot with game 5h away → 'no game in the prekick slot', exit 0."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import run_window as rw
        # A game 5 hours from now is outside the [2h52m, 3h08m] window
        future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        result = rw._check_prekick_slot([future])
        assert result is False, f"game at +5h should NOT be in prekick slot"

    def test_game_in_slot(self):
        """Fixture snapshot with game at +3h 00m → in the slot → should freeze."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import run_window as rw
        future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        result = rw._check_prekick_slot([future])
        assert result is True, f"game at +3h should be in prekick slot"
