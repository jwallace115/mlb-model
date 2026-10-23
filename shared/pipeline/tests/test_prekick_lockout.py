#!/usr/bin/env python3
"""Tests for CAD1b Item 3 — pre-kick lockout (P62 amendment).

RED-first test: fixture at 15 min to kick with a line move → no triggers.

Note: the blackout check (hours_to_kick < 20/60) was already present in the
CAD1 window_watch.py (line 234-236). This test confirms it works as specified:
a 2-point spread move 15 minutes before kick produces zero triggers.
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

import window_watch as ww


class TestPrekickLockout:

    def test_line_move_blocked_at_15min(self):
        """A 2.0-point spread move 15 min before kick → zero triggers (blackout)."""
        now = datetime(2026, 10, 26, 16, 45, tzinfo=timezone.utc)
        kick = (now + timedelta(minutes=15)).isoformat()  # 15 min out

        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110), ("Away", 3.0, -110)]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -5.0, -110), ("Away", 5.0, -110)]}

        triggers = ww.detect_triggers(
            "ev1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (now - timedelta(hours=1)).isoformat(),  # last read 1h ago
            kick, now)

        assert len(triggers) == 0, \
            f"15 min before kick: line move should be blocked by blackout, got {triggers}"

    def test_line_move_allowed_at_25min(self):
        """A 2.0-point spread move 25 min before kick → triggers (outside blackout)."""
        now = datetime(2026, 10, 26, 16, 35, tzinfo=timezone.utc)
        kick = (now + timedelta(minutes=25)).isoformat()  # 25 min out

        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110), ("Away", 3.0, -110)]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -5.0, -110), ("Away", 5.0, -110)]}

        triggers = ww.detect_triggers(
            "ev1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (now - timedelta(hours=1)).isoformat(),
            kick, now)

        assert len(triggers) > 0, \
            f"25 min before kick: line move should trigger, got {triggers}"

    def test_injury_also_blocked_at_15min(self):
        """Even an injury change at 15 min before kick is blocked."""
        now = datetime(2026, 10, 26, 16, 45, tzinfo=timezone.utc)
        kick = (now + timedelta(minutes=15)).isoformat()

        old_comp = {"inj_Home": "aaa"}
        new_comp = {"inj_Home": "bbb"}

        triggers = ww.detect_triggers(
            "ev1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (now - timedelta(minutes=5)).isoformat(),
            kick, now)

        assert len(triggers) == 0, \
            f"15 min before kick: even injury should be blocked, got {triggers}"
