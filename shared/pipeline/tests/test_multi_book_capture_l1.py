#!/usr/bin/env python3
"""
Tests for L1: multi_book_open_capture folder map, season label, per-sport isolation.
Network-free — all requests are mocked.
Each test must FAIL on the file before the L1 edit.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared.pipeline.multi_book_open_capture import (
    FOLDER_MAP, _folder, _season, _SPLIT_JULY_SPORTS,
)


# ── Folder map tests ──

class TestFolderMap:
    def test_nfl(self):
        assert _folder("americanfootball_nfl") == "nfl"

    def test_ncaaf(self):
        assert _folder("americanfootball_ncaaf") == "ncaaf"

    def test_nhl(self):
        assert _folder("icehockey_nhl") == "nhl"

    def test_nba(self):
        assert _folder("basketball_nba") == "nba"

    def test_mlb_unchanged(self):
        assert _folder("baseball_mlb") == "baseball_mlb"

    def test_unknown_sport_raises(self):
        with pytest.raises(KeyError):
            _folder("soccer_epl")


# ── Season label tests ──

class TestSeasonLabel:
    def test_nhl_october_uses_current_year(self):
        """2026-10-15 NHL -> season=2026"""
        snap = datetime(2026, 10, 15, tzinfo=timezone.utc)
        assert _season("icehockey_nhl", snap) == 2026

    def test_nhl_march_uses_previous_year(self):
        """2027-03-15 NHL -> season=2026 (the season that started in Oct 2026)"""
        snap = datetime(2027, 3, 15, tzinfo=timezone.utc)
        assert _season("icehockey_nhl", snap) == 2026

    def test_nhl_june_uses_previous_year(self):
        """2027-06-10 NHL (playoffs) -> season=2026"""
        snap = datetime(2027, 6, 10, tzinfo=timezone.utc)
        assert _season("icehockey_nhl", snap) == 2026

    def test_nhl_july_uses_current_year(self):
        """2027-07-01 NHL (preseason) -> season=2027"""
        snap = datetime(2027, 7, 1, tzinfo=timezone.utc)
        assert _season("icehockey_nhl", snap) == 2027

    def test_nba_november_uses_current_year(self):
        """2026-11-01 NBA -> season=2026"""
        snap = datetime(2026, 11, 1, tzinfo=timezone.utc)
        assert _season("basketball_nba", snap) == 2026

    def test_nba_february_uses_previous_year(self):
        """2027-02-15 NBA -> season=2026"""
        snap = datetime(2027, 2, 15, tzinfo=timezone.utc)
        assert _season("basketball_nba", snap) == 2026

    def test_nfl_september_unchanged(self):
        """NFL keeps existing rule: month >= 3 -> current year"""
        snap = datetime(2026, 9, 1, tzinfo=timezone.utc)
        assert _season("americanfootball_nfl", snap) == 2026

    def test_nfl_january_unchanged(self):
        """NFL Jan 2027 -> season=2026 (playoffs)"""
        snap = datetime(2027, 1, 15, tzinfo=timezone.utc)
        assert _season("americanfootball_nfl", snap) == 2026

    def test_nfl_february_unchanged(self):
        """NFL Feb 2027 -> season=2026 (Super Bowl)"""
        snap = datetime(2027, 2, 10, tzinfo=timezone.utc)
        assert _season("americanfootball_nfl", snap) == 2026

    def test_nfl_march_new_season(self):
        """NFL March 2027 -> season=2027 (new league year)"""
        snap = datetime(2027, 3, 1, tzinfo=timezone.utc)
        assert _season("americanfootball_nfl", snap) == 2027

    def test_mlb_unchanged(self):
        """MLB April -> current year"""
        snap = datetime(2026, 4, 1, tzinfo=timezone.utc)
        assert _season("baseball_mlb", snap) == 2026


# ── Per-sport isolation tests ──

def _mock_response(status=200, json_data=None, used="3", rem="80000"):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or []
    resp.headers = {"x-requests-last": used, "x-requests-remaining": rem}
    resp.text = "error text"
    return resp


class TestPerSportIsolation:
    """A failing sport does not stop the next one, and exit code is 1."""

    def test_failing_sport_does_not_stop_next(self, tmp_path):
        """Sport A fails (HTTP 404), sport B succeeds. B's data is written; exit code is 1."""
        from shared.pipeline import multi_book_open_capture as mod

        game = {
            "id": "g1", "commence_time": "2026-10-01T00:00:00Z",
            "home_team": "Team H", "away_team": "Team A",
            "bookmakers": [{
                "key": "draftkings", "last_update": "2026-10-01T00:00:00Z",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [{"name": "Team H", "price": -110, "point": None}]
                }]
            }]
        }

        fail_resp = _mock_response(status=404)
        ok_resp = _mock_response(json_data=[game])

        def side_effect(url, **kwargs):
            if "icehockey_nhl" in url:
                return fail_resp
            return ok_resp

        with patch.object(mod, "OUT_ROOT", tmp_path / "archive"), \
             patch.object(mod, "KEY", "testkey"), \
             patch("requests.get", side_effect=side_effect), \
             patch("sys.argv", ["prog", "--sports", "icehockey_nhl", "americanfootball_nfl"]):

            with pytest.raises(SystemExit) as exc_info:
                mod.main()

            assert exc_info.value.code == 1

        # NFL data was written despite NHL failure
        nfl_files = list((tmp_path / "archive" / "nfl").rglob("*.parquet"))
        assert len(nfl_files) == 1

        # NHL data was NOT written
        nhl_files = list((tmp_path / "archive" / "nhl").rglob("*.parquet"))
        assert len(nhl_files) == 0

    def test_network_error_isolation(self, tmp_path):
        """A network exception on one sport doesn't kill the others."""
        from shared.pipeline import multi_book_open_capture as mod

        game = {
            "id": "g2", "commence_time": "2026-09-28T00:00:00Z",
            "home_team": "Team H", "away_team": "Team A",
            "bookmakers": [{
                "key": "pinnacle", "last_update": "2026-09-28T00:00:00Z",
                "markets": [{
                    "key": "totals",
                    "outcomes": [{"name": "Over", "price": -110, "point": 44.5}]
                }]
            }]
        }

        def side_effect(url, **kwargs):
            if "baseball_mlb" in url:
                raise requests.ConnectionError("DNS failed")
            return _mock_response(json_data=[game])

        with patch.object(mod, "OUT_ROOT", tmp_path / "archive"), \
             patch.object(mod, "KEY", "testkey"), \
             patch("requests.get", side_effect=side_effect), \
             patch("sys.argv", ["prog", "--sports", "baseball_mlb", "americanfootball_nfl"]):

            with pytest.raises(SystemExit) as exc_info:
                mod.main()

            assert exc_info.value.code == 1

        # NFL was written
        nfl_files = list((tmp_path / "archive" / "nfl").rglob("*.parquet"))
        assert len(nfl_files) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
