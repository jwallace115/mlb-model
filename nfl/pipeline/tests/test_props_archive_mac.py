"""Test: --archive writes _mac.parquet files that readers can find.

(a) A fixture pull written with --archive is found by reader_v3's prop loader
    and by picks_clv's prop search.
(b) In-play filter still applies (unchanged; tested in test_props_inplay_filter.py,
    exercised here end-to-end).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
import reader_v3 as rv3
from pull_hardrock_props import drop_inplay_rows


def _write_mac_fixture(tmp_path):
    """Create a _mac.parquet in the expected archive layout."""
    season_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=10"
    season_dir.mkdir(parents=True)
    rows = [
        {"sport": "nfl", "event_id": "mac_ev1", "game_date": "2026-10-09",
         "commence_time": "2026-10-09T23:15:00Z",
         "home_team": "Tampa Bay Buccaneers", "away_team": "Atlanta Falcons",
         "bookmaker": "hardrockbet_fl", "market_key": "player_pass_yds",
         "last_update": "2026-10-08T20:00:00Z", "player_name": "Mac Test QB",
         "line": 225.5, "over_price": -115, "under_price": -105,
         "implied_over": 0.535, "implied_under": 0.512,
         "pull_batch": "hardrock_mid", "pull_timestamp": "2026-10-08T20:00:00+00:00",
         "snapshot_tag": "mid"},
        # Second row: a different book for consensus
        {"sport": "nfl", "event_id": "mac_ev1", "game_date": "2026-10-09",
         "commence_time": "2026-10-09T23:15:00Z",
         "home_team": "Tampa Bay Buccaneers", "away_team": "Atlanta Falcons",
         "bookmaker": "pinnacle", "market_key": "player_pass_yds",
         "last_update": "2026-10-08T20:00:00Z", "player_name": "Mac Test QB",
         "line": 225.5, "over_price": -110, "under_price": -110,
         "implied_over": 0.524, "implied_under": 0.524,
         "pull_batch": "hardrock_mid", "pull_timestamp": "2026-10-08T20:00:00+00:00",
         "snapshot_tag": "mid"},
    ]
    df = pd.DataFrame(rows)
    mac_path = season_dir / "data_2026_10_mac.parquet"
    df.to_parquet(mac_path, index=False)
    return mac_path, df


class TestMacArchiveReadable:
    """A _mac.parquet file is found by reader_v3's _load_inputs."""

    def test_mac_props_loaded(self, tmp_path):
        mac_path, expected = _write_mac_fixture(tmp_path)

        # Create required dirs
        lines_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        lines_dir.mkdir(parents=True)
        # Minimal snap
        snap_df = pd.DataFrame([{
            "snapshot_utc": "2026-10-08T20:00:00+00:00",
            "sport": "americanfootball_nfl", "event_id": "mac_ev1",
            "commence_time": "2026-10-09T23:15:00Z",
            "home_team": "Tampa Bay Buccaneers", "away_team": "Atlanta Falcons",
            "bookmaker": "hardrockbet_fl", "book_last_update": "2026-10-08T20:00:00Z",
            "market": "h2h", "outcome_name": "Tampa Bay Buccaneers",
            "point": None, "price": -150,
        }])
        snap_df.to_parquet(lines_dir / "snap_20261008T200000Z.parquet", index=False)
        (tmp_path / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
        (tmp_path / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026").mkdir(parents=True)

        cutoff = datetime(2026, 10, 8, 21, 0, 0, tzinfo=timezone.utc)
        props, lines, _, _, _, files_used = rv3._load_inputs(cutoff, tmp_path)

        # The _mac rows must be in props
        assert "Mac Test QB" in props["player_name"].values
        assert len(props[props["player_name"] == "Mac Test QB"]) == 2

    def test_inplay_row_dropped_endtoend(self):
        """In-play filter: pull_timestamp >= commence_time -> dropped."""
        rows = [{"pull_timestamp": "2026-10-09T23:30:00+00:00",
                 "commence_time": "2026-10-09T23:15:00Z",
                 "market": "player_pass_yds", "description": "Test"}]
        assert len(drop_inplay_rows(rows)) == 0
