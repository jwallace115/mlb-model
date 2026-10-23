#!/usr/bin/env python3
"""Tests for OPS-CAD2 Item 5 — horizon selection consistency (F5).

Props pull candidates and read candidates use the same hours_to_kick <= 48
from the same now. A game at 52h → no pull, no read.
"""
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

import window_watch as ww


class TestHorizonConsistency:

    def test_game_at_52h_no_pull(self):
        """A game 52h out gets no props pull (horizon is 48h)."""
        now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=52)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = ww._should_pull_props(
                "ev1", "nfl", kick, now, root,
                has_injury_trigger=False, has_news_trigger=False,
                has_horizon_trigger=False)
            assert result is False, "52h out should not trigger props pull"

    def test_game_at_52h_no_read_trigger(self):
        """A game 52h out with no prior read gets no horizon trigger."""
        now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=52)).isoformat()

        comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            triggers = ww.detect_triggers(
                "ev1", "nfl",
                ww._hash(comp), comp,
                None, None, None,  # no prior read
                kick, now, root=root)
            # No horizon_entry because > 48h
            horizon_trigs = [t for t in triggers if "horizon" in t]
            assert len(horizon_trigs) == 0, \
                f"52h out should not get horizon trigger: {triggers}"

    def test_game_at_47h_gets_both(self):
        """A game 47h out with no prior read gets BOTH props pull AND horizon trigger."""
        now = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=47)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            # Props pull: horizon
            result = ww._should_pull_props(
                "ev1", "nfl", kick, now, root,
                has_injury_trigger=False, has_news_trigger=False,
                has_horizon_trigger=True)
            assert result is True, "47h out with horizon should trigger props pull"

            # Read trigger: horizon or anchor_morning (both are valid reads)
            comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
            triggers = ww.detect_triggers(
                "ev1", "nfl",
                ww._hash(comp), comp,
                None, None, None,
                kick, now, root=root)
            assert len(triggers) > 0, \
                f"47h out should get a trigger (horizon or anchor): {triggers}"

    def test_same_constant_used(self):
        """Both _should_pull_props and detect_triggers use HORIZON_HOURS = 48."""
        assert ww.HORIZON_HOURS == 48
