#!/usr/bin/env python3
"""
Tests for the per-sport Hard Rock key selector (books_for).
Every test must FAIL on origin/main (books_for does not exist there).
Network-free — all requests are mocked.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared.pipeline.multi_book_open_capture import books_for, BOOKS
from shared.pipeline.pull_event_markets import compute_market_set


# ── books_for: NFL keeps hardrockbet_fl ──

class TestBooksForNFL:
    def test_nfl_contains_hardrockbet_fl(self):
        b = books_for("americanfootball_nfl")
        assert "hardrockbet_fl" in b

    def test_nfl_does_not_contain_generic(self):
        b = books_for("americanfootball_nfl")
        assert "hardrockbet" not in b

    def test_nfl_has_10_books(self):
        assert len(books_for("americanfootball_nfl")) == 10


# ── books_for: every other sport uses generic hardrockbet ──

class TestBooksForOtherSports:
    @pytest.mark.parametrize("sport", [
        "americanfootball_ncaaf",
        "icehockey_nhl",
        "basketball_nba",
        "baseball_mlb",
    ])
    def test_contains_generic_hardrockbet(self, sport):
        b = books_for(sport)
        assert "hardrockbet" in b

    @pytest.mark.parametrize("sport", [
        "americanfootball_ncaaf",
        "icehockey_nhl",
        "basketball_nba",
        "baseball_mlb",
    ])
    def test_does_not_contain_hardrockbet_fl(self, sport):
        b = books_for(sport)
        assert "hardrockbet_fl" not in b

    @pytest.mark.parametrize("sport", [
        "americanfootball_ncaaf",
        "icehockey_nhl",
        "basketball_nba",
        "baseball_mlb",
    ])
    def test_has_10_books(self, sport):
        assert len(books_for(sport)) == 10


# ── pull() sends the sport's key ──

class TestPullSendsCorrectKey:
    def _mock_response(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        resp.headers = {"x-requests-last": "3", "x-requests-remaining": "80000"}
        return resp

    def test_nfl_pull_sends_hardrockbet_fl(self, monkeypatch):
        from shared.pipeline import multi_book_open_capture as mod
        captured = {}

        def fake_get(url, **kwargs):
            captured["params"] = kwargs.get("params", {})
            return self._mock_response()

        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr(mod, "KEY", "testkey")
        mod.pull("americanfootball_nfl")
        bm = captured["params"]["bookmakers"]
        assert "hardrockbet_fl" in bm
        assert "hardrockbet" not in bm.replace("hardrockbet_fl", "")

    def test_nhl_pull_sends_generic_hardrockbet(self, monkeypatch):
        from shared.pipeline import multi_book_open_capture as mod
        captured = {}

        def fake_get(url, **kwargs):
            captured["params"] = kwargs.get("params", {})
            return self._mock_response()

        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr(mod, "KEY", "testkey")
        mod.pull("icehockey_nhl")
        bm = captured["params"]["bookmakers"]
        assert "hardrockbet" in bm
        assert "hardrockbet_fl" not in bm


# ── compute_market_set picks up markets from both HR keys ──

class TestComputeMarketSetBothKeys:
    def test_picks_up_generic_hardrockbet_market(self):
        bm = {
            "hardrockbet": ["alternate_totals", "team_totals"],
            "pinnacle": ["alternate_spreads"],
        }
        result = compute_market_set(bm, [])
        assert "alternate_totals" in result
        assert "team_totals" in result
        assert "alternate_spreads" in result

    def test_picks_up_hardrockbet_fl_market(self):
        bm = {
            "hardrockbet_fl": ["player_pass_yds"],
            "pinnacle": ["alternate_totals"],
        }
        result = compute_market_set(bm, [])
        assert "player_pass_yds" in result
        assert "alternate_totals" in result

    def test_union_of_both_hr_keys(self):
        bm = {
            "hardrockbet_fl": ["market_a"],
            "hardrockbet": ["market_b"],
            "pinnacle": [],
        }
        result = compute_market_set(bm, [])
        assert "market_a" in result
        assert "market_b" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
