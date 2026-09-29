"""Tests for pull_nhl_history.py — schema correctness.
Each test must FAIL on the old normalize() from run_multi_sport_backfill.py."""
import sys, json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.pipeline.pull_nhl_history import flatten_snapshot, flatten_event

# ── Fixtures: realistic API responses ──

SNAPSHOT_FIXTURE = {
    "timestamp": "2024-10-10T22:45:00Z",
    "previous_timestamp": "2024-10-10T22:30:00Z",
    "data": [
        {
            "id": "evt1", "commence_time": "2024-10-11T00:00:00Z",
            "home_team": "Boston Bruins", "away_team": "Montreal Canadiens",
            "bookmakers": [{
                "key": "pinnacle", "last_update": "2024-10-10T22:40:00Z",
                "markets": [
                    {"key": "h2h", "outcomes": [
                        {"name": "Boston Bruins", "price": -150},
                        {"name": "Montreal Canadiens", "price": 130},
                    ]},
                    {"key": "spreads", "outcomes": [
                        {"name": "Boston Bruins", "price": -180, "point": -1.5},
                        {"name": "Montreal Canadiens", "price": 155, "point": 1.5},
                    ]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "price": -110, "point": 6.0},
                        {"name": "Under", "price": -110, "point": 6.0},
                    ]},
                ]
            }]
        },
        # In-play event (snapshot_utc >= commence_time) — should be dropped
        {
            "id": "evt2", "commence_time": "2024-10-10T22:00:00Z",
            "home_team": "Tampa Bay Lightning", "away_team": "Carolina Hurricanes",
            "bookmakers": [{
                "key": "pinnacle", "last_update": "2024-10-10T22:40:00Z",
                "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Tampa Bay Lightning", "price": -120},
                    {"name": "Carolina Hurricanes", "price": 100},
                ]}]
            }]
        },
    ]
}

EVENT_PROPS_FIXTURE = {
    "timestamp": "2024-10-10T23:50:00Z",
    "data": {
        "id": "evt3", "commence_time": "2024-10-11T00:00:00Z",
        "home_team": "Boston Bruins", "away_team": "Montreal Canadiens",
        "bookmakers": [{
            "key": "draftkings", "last_update": "2024-10-10T23:49:00Z",
            "markets": [{
                "key": "player_points", "outcomes": [
                    {"name": "Over", "description": "David Pastrnak", "price": -120, "point": 1.5},
                    {"name": "Under", "description": "David Pastrnak", "price": 100, "point": 1.5},
                    {"name": "Over", "description": "Nick Suzuki", "price": -110, "point": 0.5},
                    {"name": "Under", "description": "Nick Suzuki", "price": -110, "point": 0.5},
                ]
            }]
        }]
    }
}


class TestH2hKeepsTeamNames:
    def test_h2h_yields_two_rows_with_team_names(self):
        rows = flatten_snapshot(SNAPSHOT_FIXTURE, "2024-10-10T22:45:00Z")
        h2h = [r for r in rows if r["market"] == "h2h"]
        assert len(h2h) == 2
        names = {r["outcome_name"] for r in h2h}
        assert names == {"Boston Bruins", "Montreal Canadiens"}

    def test_spreads_keeps_both_teams_and_points(self):
        rows = flatten_snapshot(SNAPSHOT_FIXTURE, "2024-10-10T22:45:00Z")
        sp = [r for r in rows if r["market"] == "spreads"]
        assert len(sp) == 2
        points = {r["point"] for r in sp}
        assert points == {-1.5, 1.5}
        names = {r["outcome_name"] for r in sp}
        assert names == {"Boston Bruins", "Montreal Canadiens"}


class TestInPlayDropped:
    def test_inplay_event_excluded(self):
        """evt2 has commence_time 22:00Z and snapshot 22:45Z — in play, must drop."""
        rows = flatten_snapshot(SNAPSHOT_FIXTURE, "2024-10-10T22:45:00Z")
        eids = {r["event_id"] for r in rows}
        assert "evt2" not in eids
        assert "evt1" in eids


class TestPropsKeepPlayer:
    def test_props_carry_player_name_and_over_under(self):
        rows = flatten_event(EVENT_PROPS_FIXTURE, "2024-10-10T23:50:00Z")
        assert len(rows) == 4
        pastrnak = [r for r in rows if r["description"] == "David Pastrnak"]
        assert len(pastrnak) == 2
        sides = {r["outcome_name"] for r in pastrnak}
        assert sides == {"Over", "Under"}


class TestOldNormalizerFails:
    """The old normalize() from run_multi_sport_backfill.py loses team names on h2h."""

    def test_old_normalizer_loses_team_names(self):
        """Import the old normalize and show it produces only 1 h2h row (the bug)."""
        sys.path.insert(0, str(ROOT / "research" / "odds_api_backfill" / "multi_sport_props_archive"))
        from run_multi_sport_backfill import normalize
        # The old normalizer expects a different input shape — adapt
        # It takes (data, sport_key, eid, game_date, home, away, commence, batch_label, ts)
        # where data is a single event's bookmaker response
        event = SNAPSHOT_FIXTURE["data"][0]
        old_rows = normalize(
            event, "nhl", "evt1", "2024-10-10", "Boston Bruins", "Montreal Canadiens",
            "2024-10-11T00:00:00Z", "test", "2024-10-10T22:45:00Z"
        )
        # Old normalizer keys on (description, point) — for h2h both are ("", None)
        # so it collapses to 1 row instead of 2
        h2h_rows = [r for r in old_rows if r["market_key"] == "h2h"]
        # The old normalizer should produce only 1 h2h row (the bug)
        assert len(h2h_rows) == 1, (
            f"Expected old normalizer to collapse h2h to 1 row, got {len(h2h_rows)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
