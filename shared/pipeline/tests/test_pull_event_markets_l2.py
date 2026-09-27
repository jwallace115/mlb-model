#!/usr/bin/env python3
"""
Tests for L2: pull_event_markets — cost pre-check, started-event exclusion,
player name in rows, --exclude-prefix.
Network-free — all requests mocked.
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared.pipeline.pull_event_markets import (
    compute_market_set, flatten_event, filter_window, TAPE_MARKETS,
)


# ── compute_market_set ──

class TestComputeMarketSet:
    def test_union_of_hr_and_pinnacle(self):
        bm = {
            "hardrockbet_fl": ["h2h", "spreads", "totals", "player_pass_yds", "alternate_spreads"],
            "pinnacle": ["h2h", "spreads", "totals", "player_rush_yds", "alternate_totals"],
            "draftkings": ["h2h", "spreads", "totals", "some_dk_only"],
        }
        result = compute_market_set(bm, [])
        # Should include HR + Pinnacle markets minus tape markets, NOT dk-only
        assert "player_pass_yds" in result
        assert "player_rush_yds" in result
        assert "alternate_spreads" in result
        assert "alternate_totals" in result
        assert "h2h" not in result
        assert "spreads" not in result
        assert "totals" not in result
        assert "some_dk_only" not in result

    def test_exclude_prefix(self):
        bm = {
            "hardrockbet_fl": ["player_pass_yds", "alternate_spreads"],
            "pinnacle": ["player_rush_yds", "team_totals"],
        }
        result = compute_market_set(bm, ["player_"])
        assert "alternate_spreads" in result
        assert "team_totals" in result
        assert "player_pass_yds" not in result
        assert "player_rush_yds" not in result


# ── flatten_event carries player description ──

class TestFlattenEvent:
    def test_rows_carry_player_name(self):
        data = {
            "id": "evt1",
            "commence_time": "2026-10-01T00:00:00Z",
            "home_team": "Boston Bruins",
            "away_team": "Montreal Canadiens",
            "bookmakers": [{
                "key": "hardrockbet_fl",
                "last_update": "2026-09-30T12:00:00Z",
                "markets": [{
                    "key": "player_points",
                    "outcomes": [{
                        "name": "Over",
                        "description": "David Pastrnak",
                        "price": -115,
                        "point": 2.5,
                    }]
                }]
            }]
        }
        rows = flatten_event(data, "icehockey_nhl", "2026-09-30T12:00:00Z", "open")
        assert len(rows) == 1
        assert rows[0]["description"] == "David Pastrnak"
        assert rows[0]["market"] == "player_points"
        assert rows[0]["price"] == -115
        assert rows[0]["point"] == 2.5


# ── filter_window excludes started events ──

class TestFilterWindow:
    def test_excludes_started_events(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        events = [
            {"id": "past", "commence_time": "2026-10-01T10:00:00Z"},
            {"id": "soon", "commence_time": "2026-10-01T20:00:00Z"},
            {"id": "far", "commence_time": "2026-10-05T00:00:00Z"},
        ]
        result = filter_window(events, now, 24)
        ids = [e["id"] for e in result]
        assert "past" not in ids
        assert "soon" in ids
        assert "far" not in ids  # outside 24h window


# ── Cost pre-check halts below floor ──

class TestCostPreCheck:
    def test_halts_below_floor(self, tmp_path):
        from shared.pipeline import pull_event_markets as mod

        events_resp = MagicMock()
        events_resp.status_code = 200
        events_resp.json.return_value = [
            {"id": "e1", "commence_time": "2099-01-01T00:00:00Z",
             "home_team": "A", "away_team": "B"},
            {"id": "e2", "commence_time": "2099-01-01T01:00:00Z",
             "home_team": "C", "away_team": "D"},
        ]
        events_resp.headers = {"x-requests-remaining": "100", "x-requests-last": "0"}

        # Discovery response: 5 non-tape markets -> cost = 2 events x 5 = 10
        # With remaining=100 and floor=95, after=90 < 95 -> HALT
        disc_resp = MagicMock()
        disc_resp.status_code = 200
        disc_resp.json.return_value = {
            "bookmakers": [{
                "key": "hardrockbet_fl",
                "markets": [
                    {"key": "h2h"}, {"key": "spreads"}, {"key": "totals"},
                    {"key": "m1"}, {"key": "m2"}, {"key": "m3"}, {"key": "m4"}, {"key": "m5"},
                ]
            }]
        }
        disc_resp.headers = {"x-requests-remaining": "100", "x-requests-last": "0"}

        call_count = [0]
        def side_effect(url, **kw):
            call_count[0] += 1
            if "/events" in url and "/odds" not in url and "/markets" not in url:
                return events_resp
            return disc_resp

        with patch("requests.get", side_effect=side_effect), \
             patch.object(mod, "KEY", "testkey"), \
             patch("sys.argv", ["prog", "--sport", "icehockey_nhl",
                                "--window-hours", "999999", "--tag", "open",
                                "--floor", "95"]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
