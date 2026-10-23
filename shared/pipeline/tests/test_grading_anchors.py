#!/usr/bin/env python3
"""Tests for OPS-CAD2 Item 4 — grading anchors (P69).

RED-first:
  1. Tick at 13:59Z on 10-24 → no morning anchor.
  2. Tick at 14:02Z → anchor_morning for game ≤ 48h, exactly once.
  3. Prekick at kick-2h58 fires once.
  4. Close at kick-44min fires once; never at kick-15min.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

import window_watch as ww


class TestAnchorMorning:

    def test_no_morning_at_1359z(self):
        """13:59Z on 10-24 is 9:59 AM ET → no morning anchor."""
        now = datetime(2026, 10, 24, 13, 59, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=24)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            anchors = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_morning" not in anchors, \
                f"9:59 AM ET should not fire morning anchor: {anchors}"

    def test_morning_at_1402z(self):
        """14:02Z on 10-24 is 10:02 AM ET → anchor_morning fires."""
        now = datetime(2026, 10, 24, 14, 2, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=24)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            anchors = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_morning" in anchors, \
                f"10:02 AM ET should fire morning anchor: {anchors}"

    def test_morning_fires_once(self):
        """Morning anchor fires only once per day per event."""
        now = datetime(2026, 10, 24, 14, 2, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=24)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            a1 = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_morning" in a1

            # Second call same day → no anchor
            a2 = ww._check_anchors("ev1", "nfl", kick, now + timedelta(minutes=5), root)
            assert "anchor_morning" not in a2

    def test_morning_skips_game_beyond_48h(self):
        """Morning anchor does NOT fire for games > 48h out."""
        now = datetime(2026, 10, 24, 14, 2, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=72)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            anchors = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_morning" not in anchors


class TestAnchorPrekick:

    def test_prekick_at_kick_minus_2h58(self):
        """Kick - 2h58m fires anchor_prekick."""
        kick_dt = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
        now = kick_dt - timedelta(hours=2, minutes=58)
        kick = kick_dt.isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            anchors = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_prekick" in anchors

    def test_prekick_fires_once(self):
        """Prekick fires only once per game."""
        kick_dt = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
        now = kick_dt - timedelta(hours=2, minutes=58)
        kick = kick_dt.isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            a1 = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_prekick" in a1

            a2 = ww._check_anchors("ev1", "nfl", kick, now + timedelta(minutes=5), root)
            assert "anchor_prekick" not in a2


class TestAnchorClose:

    def test_close_at_kick_minus_44min(self):
        """Kick - 44min fires anchor_close."""
        kick_dt = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
        now = kick_dt - timedelta(minutes=44)
        kick = kick_dt.isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            anchors = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_close" in anchors

    def test_close_blocked_at_kick_minus_15min(self):
        """Kick - 15min is inside the 20-min blackout → no anchor_close."""
        kick_dt = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
        now = kick_dt - timedelta(minutes=15)
        kick = kick_dt.isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            anchors = ww._check_anchors("ev1", "nfl", kick, now, root)
            assert "anchor_close" not in anchors


class TestAnchorBypassDedup:

    def test_anchor_fires_even_with_identical_digest(self):
        """Anchors bypass the digest dedup — they fire on unchanged inputs."""
        now = datetime(2026, 10, 26, 14, 2, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=3)).isoformat()  # within 48h

        comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        digest = ww._hash(comp)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            # Same digest → normal triggers would be empty
            triggers = ww.detect_triggers(
                "ev1", "nfl", digest, comp, digest, comp,
                (now - timedelta(hours=1)).isoformat(),
                kick, now, root=root)
            # But the anchor fires because it's anchor_prekick time
            assert any("anchor" in t for t in triggers), \
                f"anchor should bypass dedup: {triggers}"
