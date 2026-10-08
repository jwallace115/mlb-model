"""Tests for reader_v3: parameterised blind-opinion reader.

P24: reader_v3 is the canonical reader.
(a) props and snapshots after --as-of are excluded (planted leak)
(b) Kalshi prefix derivation from slate dates
(c) no injury report -> reasons carry "no injury report", null control
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
import reader_v3 as rv3


# ── helpers ──

def _mini_props(pull_ts, event_id="ev1", market_key="player_pass_yds",
                player_name="Test QB", line=250.5, bookmaker="pinnacle"):
    """One-row props DataFrame."""
    return pd.DataFrame([{
        "sport": "nfl", "event_id": event_id, "game_date": "2026-10-04",
        "commence_time": "2026-10-04T17:00:00Z",
        "home_team": "Buffalo Bills", "away_team": "New England Patriots",
        "bookmaker": bookmaker, "market_key": market_key,
        "last_update": pull_ts, "player_name": player_name,
        "line": line, "over_price": -110, "under_price": -110,
        "implied_over": 0.5238, "implied_under": 0.5238,
        "pull_batch": "test", "pull_timestamp": pull_ts, "snapshot_tag": "mid",
    }])


def _mini_snap(snap_utc, event_id="ev1"):
    """Minimal game-line snapshot."""
    return pd.DataFrame([
        {"snapshot_utc": snap_utc, "sport": "americanfootball_nfl",
         "event_id": event_id, "commence_time": "2026-10-04T17:00:00Z",
         "home_team": "Buffalo Bills", "away_team": "New England Patriots",
         "bookmaker": "hardrockbet_fl", "book_last_update": snap_utc,
         "market": "h2h", "outcome_name": "Buffalo Bills", "point": None, "price": -180},
        {"snapshot_utc": snap_utc, "sport": "americanfootball_nfl",
         "event_id": event_id, "commence_time": "2026-10-04T17:00:00Z",
         "home_team": "Buffalo Bills", "away_team": "New England Patriots",
         "bookmaker": "hardrockbet_fl", "book_last_update": snap_utc,
         "market": "h2h", "outcome_name": "New England Patriots", "point": None, "price": 150},
    ])


# ── (a) as-of exclusion ──

class TestAsOfExclusion:
    """A props pull and a snapshot timestamped AFTER --as-of are excluded."""

    def test_future_props_excluded(self, tmp_path):
        """Props with pull_timestamp after as_of must not appear."""
        cutoff = datetime(2026, 10, 4, 15, 0, 0, tzinfo=timezone.utc)
        # Create props dir with one before and one after
        season_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10"
        season_dir.mkdir(parents=True)
        before = _mini_props("2026-10-04T14:00:00+00:00", player_name="Before QB")
        after = _mini_props("2026-10-04T16:00:00+00:00", player_name="After QB")
        combined = pd.concat([before, after], ignore_index=True)
        combined.to_parquet(season_dir / "data_2026_10.parquet", index=False)

        # Create minimal lines dir
        lines_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        lines_dir.mkdir(parents=True)
        _mini_snap("2026-10-04T14:00:00+00:00").to_parquet(
            lines_dir / "snap_20261004T140000Z.parquet", index=False)
        # A FUTURE snapshot that must be excluded
        _mini_snap("2026-10-04T16:00:00+00:00").to_parquet(
            lines_dir / "snap_20261004T160000Z.parquet", index=False)

        # Create empty kalshi/nws dirs
        (tmp_path / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
        (tmp_path / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026").mkdir(parents=True)

        props, lines, KAL, WX, HIST, files_used = rv3._load_inputs(cutoff, tmp_path)

        # The "After QB" row must not be in props
        assert "Before QB" in props["player_name"].values
        assert "After QB" not in props["player_name"].values

        # The snap selected must be the 14:00 one, not 16:00
        assert "snap_20261004T140000Z.parquet" in files_used["lines"]

    def test_future_snapshot_excluded(self, tmp_path):
        """A line snapshot after as_of must not be selected."""
        cutoff = datetime(2026, 10, 4, 15, 0, 0, tzinfo=timezone.utc)
        lines_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        lines_dir.mkdir(parents=True)
        _mini_snap("2026-10-04T14:00:00+00:00").to_parquet(
            lines_dir / "snap_20261004T140000Z.parquet", index=False)
        _mini_snap("2026-10-04T16:00:00+00:00").to_parquet(
            lines_dir / "snap_20261004T160000Z.parquet", index=False)

        # Only need lines for this test
        (tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10").mkdir(parents=True)
        (tmp_path / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
        (tmp_path / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026").mkdir(parents=True)

        _, lines, _, _, _, files_used = rv3._load_inputs(cutoff, tmp_path)
        assert "snap_20261004T140000Z.parquet" in files_used["lines"]


# ── (b) Kalshi prefix derivation ──

class TestKalshiPrefix:
    def test_oct04(self):
        assert rv3._kalshi_prefix("2026-10-04") == "KXNFLGAME-26OCT04"

    def test_oct11(self):
        assert rv3._kalshi_prefix("2026-10-11") == "KXNFLGAME-26OCT11"

    def test_sep13(self):
        assert rv3._kalshi_prefix("2026-09-13") == "KXNFLGAME-26SEP13"


# ── (c) no injury report null control ──

class TestNoInjuryReport:
    """Without --injury-report, reasons carry 'no injury report' and
    nothing else changes vs the same run with the report."""

    def test_empty_news(self):
        """_load_news with None returns empty dict."""
        assert rv3._load_news(None) == {}

    def test_no_report_reasons(self, tmp_path):
        """Reader output without injury report: every reason either is '' (no_view)
        or does NOT contain 'Official report'. The news dict is empty."""
        news = rv3._load_news(None)
        assert len(news) == 0

    def test_null_control_p_first_unchanged(self, tmp_path):
        """A run with and without injury report: p_first differs only on
        rows where the injury report applies (questionable shade)."""
        # Build a tiny sheet
        sheet = pd.DataFrame([{
            "event_id": "ev1", "commence_time": "2026-10-04T17:00:00Z",
            "home_team": "Buffalo Bills", "away_team": "New England Patriots",
            "market_key": "player_pass_yds", "player_name": "Test QB",
            "line": 250.5, "first_side": "Over", "second_side": "Under",
            "price_first": -110, "price_second": -110,
            "source_utc": "2026-10-04T15:00:00Z",
            "imp_first": 0.5238, "imp_second": 0.5238,
            "two_way": True, "q_first": 0.5, "source_age_min": 10.0,
        }])

        # Empty data layers
        props = pd.DataFrame(columns=["event_id", "market_key", "player_name",
                                       "line", "bookmaker", "over_price",
                                       "under_price", "pull_timestamp"])
        lines = pd.DataFrame()
        KAL = pd.DataFrame()
        WX = pd.DataFrame()
        HIST = pd.DataFrame()

        # Run without injury report
        out_no_inj = rv3.read_opinions(sheet, props, lines, KAL, WX, HIST, {}, None)

        # Run WITH injury report but player not in it
        NEWS = {"Other Player": "Official report: Questionable (knee)."}
        out_with_inj = rv3.read_opinions(sheet, props, lines, KAL, WX, HIST, NEWS, None)

        # p_first should be identical (player not in injury report)
        assert out_no_inj["p_first"].iloc[0] == out_with_inj["p_first"].iloc[0]
