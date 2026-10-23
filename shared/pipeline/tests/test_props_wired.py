#!/usr/bin/env python3
"""Tests for CAD1b Item 2 — props pulls wired into the watcher.

RED-first tests:
  1. Fixture with kick in 40 min and a 25-min-old pull → one pull request.
  2. Quiet fixture → zero pulls.
  3. resolve_inputs picks newest pull across _mac and _vm month files.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))

import window_watch as ww


class TestClosePullWired:

    def test_close_pull_at_40min_25min_old(self):
        """Kick in 40 min, last pull 25 min old → should pull props."""
        now = datetime(2026, 10, 26, 16, 20, tzinfo=timezone.utc)
        kick = (now + timedelta(minutes=40)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10"
            props_dir.mkdir(parents=True, exist_ok=True)

            # Create a props file with a 25-min-old pull
            pull_ts = (now - timedelta(minutes=25)).isoformat()
            df = pd.DataFrame([{
                "event_id": "ev1", "commence_time": kick,
                "home_team": "Team A", "away_team": "Team B",
                "bookmaker": "hardrockbet_fl", "market_key": "player_rush_yds",
                "player_name": "P1", "line": 75.5,
                "over_price": -110, "under_price": -110,
                "pull_timestamp": pull_ts,
            }])
            df.to_parquet(props_dir / "data_2026_10_vm.parquet", index=False)

            result = ww._should_pull_props(
                "ev1", "nfl", kick, now, root,
                has_injury_trigger=False, has_news_trigger=False,
                has_horizon_trigger=False)
            assert result is True, "kick in 40 min with 25-min-old pull should trigger props pull"

    def test_close_pull_not_at_40min_10min_old(self):
        """Kick in 40 min, last pull 10 min old → should NOT pull (< 20 min)."""
        now = datetime(2026, 10, 26, 16, 20, tzinfo=timezone.utc)
        kick = (now + timedelta(minutes=40)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10"
            props_dir.mkdir(parents=True, exist_ok=True)

            pull_ts = (now - timedelta(minutes=10)).isoformat()
            df = pd.DataFrame([{
                "event_id": "ev1", "commence_time": kick,
                "home_team": "Team A", "away_team": "Team B",
                "bookmaker": "hardrockbet_fl", "market_key": "player_rush_yds",
                "player_name": "P1", "line": 75.5,
                "over_price": -110, "under_price": -110,
                "pull_timestamp": pull_ts,
            }])
            df.to_parquet(props_dir / "data_2026_10_vm.parquet", index=False)

            result = ww._should_pull_props(
                "ev1", "nfl", kick, now, root,
                has_injury_trigger=False, has_news_trigger=False,
                has_horizon_trigger=False)
            assert result is False, "kick in 40 min with 10-min-old pull should NOT trigger"


class TestQuietNoPulls:

    def test_quiet_no_props_pull(self):
        """A game 5 days out with a recent pull → no props pull."""
        now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
        kick = (now + timedelta(days=5)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10"
            props_dir.mkdir(parents=True, exist_ok=True)

            pull_ts = (now - timedelta(hours=2)).isoformat()
            df = pd.DataFrame([{
                "event_id": "ev1", "commence_time": kick,
                "home_team": "Team A", "away_team": "Team B",
                "bookmaker": "hardrockbet_fl", "market_key": "player_rush_yds",
                "player_name": "P1", "line": 75.5,
                "over_price": -110, "under_price": -110,
                "pull_timestamp": pull_ts,
            }])
            df.to_parquet(props_dir / "data_2026_10_vm.parquet", index=False)

            result = ww._should_pull_props(
                "ev1", "nfl", kick, now, root,
                has_injury_trigger=False, has_news_trigger=False,
                has_horizon_trigger=False)
            assert result is False, "game 5 days out with recent pull should not trigger props"

    def test_ncaaf_no_props(self):
        """NCAAF never pulls props."""
        now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=6)).isoformat()
        result = ww._should_pull_props(
            "ev1", "ncaaf", kick, now, Path("/tmp"),
            has_injury_trigger=True, has_news_trigger=True,
            has_horizon_trigger=True)
        assert result is False


class TestResolveInputsCrossPlatform:

    def test_resolve_inputs_newest_across_files(self):
        """resolve_inputs glob picks up both _mac and _vm; newest_inputs reads both."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10"
            props_dir.mkdir(parents=True, exist_ok=True)
            lines_dir = root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
            lines_dir.mkdir(parents=True, exist_ok=True)

            # VM file: newer pull
            vm_df = pd.DataFrame([{
                "event_id": "ev1", "commence_time": "2026-10-26T17:00:00Z",
                "home_team": "Team A", "away_team": "Team B",
                "bookmaker": "hardrockbet_fl", "market_key": "player_rush_yds",
                "player_name": "P1", "line": 75.5,
                "over_price": -110, "under_price": -110,
                "pull_timestamp": "2026-10-23T14:00:00Z",
            }])
            vm_df.to_parquet(props_dir / "data_2026_10_vm.parquet", index=False)

            # Mac file: older pull
            mac_df = pd.DataFrame([{
                "event_id": "ev1", "commence_time": "2026-10-26T17:00:00Z",
                "home_team": "Team A", "away_team": "Team B",
                "bookmaker": "hardrockbet_fl", "market_key": "player_rush_yds",
                "player_name": "P1", "line": 75.5,
                "over_price": -115, "under_price": -105,
                "pull_timestamp": "2026-10-23T12:00:00Z",
            }])
            mac_df.to_parquet(props_dir / "data_2026_10_mac.parquet", index=False)

            # Snapshot
            snap_df = pd.DataFrame([{
                "event_id": "ev1", "commence_time": "2026-10-26T17:00:00Z",
                "home_team": "Team A", "away_team": "Team B",
                "bookmaker": "hardrockbet_fl", "market": "spreads",
                "outcome_name": "Team A", "point": -3.0, "price": -110,
                "snapshot_utc": "2026-10-23T14:00:00Z",
            }])
            snap_df.to_parquet(lines_dir / "snap_20261023T140000Z.parquet", index=False)

            import log_ai_opinions as lao
            lao.set_sport("nfl")
            old_props, old_lines = lao.PROPS_DIR, lao.LINES_DIR
            lao.PROPS_DIR = root / "data" / "odds_archive" / "nfl" / "props"
            lao.LINES_DIR = root / "data" / "odds_archive" / "nfl" / "line_history"
            try:
                now = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)
                # newest_inputs reads both and takes the newest per event
                props, lines = lao.newest_inputs(2026, now)
                assert len(props) > 0
                assert str(props.pull_timestamp.iloc[0]) == "2026-10-23T14:00:00Z"
            finally:
                lao.PROPS_DIR, lao.LINES_DIR = old_props, old_lines
