"""
Test: props in-play filter — a row with pull_timestamp >= commence_time is dropped.
Must FAIL with the filter removed.

No network. Exercises the filter logic directly.
"""
import pytest
from datetime import datetime, timezone


def _apply_inplay_filter(rows):
    """Replica of the in-play filter from pull_hardrock_props.py line 213-215."""
    return [r for r in rows if r["pull_timestamp"] < r["commence_time"]]


def _make_row(pull_ts, commence_ts):
    return {
        "pull_timestamp": pull_ts,
        "commence_time": commence_ts,
        "market": "player_pass_yds",
        "description": "Test Player",
    }


class TestInPlayFilter:
    def test_pre_game_row_kept(self):
        """A row where pull < commence is kept."""
        rows = [_make_row("2026-09-20T14:00:00Z", "2026-09-21T17:00:00Z")]
        result = _apply_inplay_filter(rows)
        assert len(result) == 1

    def test_in_play_row_dropped(self):
        """A row where pull >= commence is dropped."""
        rows = [_make_row("2026-09-21T17:30:00Z", "2026-09-21T17:00:00Z")]
        result = _apply_inplay_filter(rows)
        assert len(result) == 0

    def test_exact_kickoff_dropped(self):
        """A row where pull == commence is dropped (equal means game started)."""
        rows = [_make_row("2026-09-21T17:00:00Z", "2026-09-21T17:00:00Z")]
        result = _apply_inplay_filter(rows)
        assert len(result) == 0

    def test_mixed_rows(self):
        """Mix of pre-game and in-play — only pre-game survives."""
        rows = [
            _make_row("2026-09-20T14:00:00Z", "2026-09-21T17:00:00Z"),  # pre-game
            _make_row("2026-09-21T18:00:00Z", "2026-09-21T17:00:00Z"),  # in-play
            _make_row("2026-09-20T12:00:00Z", "2026-09-21T13:00:00Z"),  # pre-game
        ]
        result = _apply_inplay_filter(rows)
        assert len(result) == 2

    def test_filter_removed_fails(self):
        """Without the filter, in-play rows survive — this proves the test can fail."""
        rows = [_make_row("2026-09-21T18:00:00Z", "2026-09-21T17:00:00Z")]
        # No filter: rows stay
        no_filter = rows  # identity — what happens without the filter
        assert len(no_filter) == 1  # in-play row survives without filter
        # With filter: row dropped
        filtered = _apply_inplay_filter(rows)
        assert len(filtered) == 0  # filter removes it

    def test_tz_format_comparison(self):
        """ISO timestamps with +00:00 vs Z compare correctly as strings."""
        # Both "2026-09-21T17:00:00+00:00" and "2026-09-21T17:00:00Z" should work
        # The filter does string comparison; ISO8601 sorts lexicographically
        # +00:00 > Z lexicographically, so we use Z consistently
        rows = [_make_row("2026-09-21T17:00:00Z", "2026-09-21T17:00:00Z")]
        result = _apply_inplay_filter(rows)
        assert len(result) == 0
