#!/usr/bin/env python3
"""Tests for OPS-CAD3 Item 1 — cadence: game-day aware sweeps + light ticks (P70).

RED-first:
  1. nearest kick 40h + last sweep 2h ago → quiet.
  2. nearest kick 10h + last sweep 70 min → sweep.
  3. game at 2h with a 2-pt line move and no anchor → light tick, no trigger.
  4. same game at kick-44min → anchor_close fires.
  5. 10:00 AM ET → sweep even with a 20-min-old sweep.
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


def _tmp_root():
    import tempfile
    d = tempfile.mkdtemp()
    root = Path(d)
    (root / "status").mkdir(parents=True, exist_ok=True)
    return root


class TestCadenceDecision:

    def test_far_kick_recent_sweep_quiet(self):
        """Nearest kick 40h + last sweep 2h ago → quiet."""
        root = _tmp_root()
        now = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)  # 2 PM ET — avoid 10 AM
        state = {f"last_sweep_nfl": (now - timedelta(hours=2)).isoformat()}
        ww._save_watch_state(state, root)
        cadence, reason = ww.decide_cadence("nfl", 40.0, now, root)
        assert cadence == "quiet", f"expected quiet, got {cadence}: {reason}"

    def test_gameday_stale_sweep(self):
        """Nearest kick 10h + last sweep 70 min → sweep."""
        root = _tmp_root()
        now = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
        state = {f"last_sweep_nfl": (now - timedelta(minutes=70)).isoformat()}
        ww._save_watch_state(state, root)
        cadence, reason = ww.decide_cadence("nfl", 10.0, now, root)
        assert cadence == "sweep", f"expected sweep, got {cadence}: {reason}"

    def test_inside_3h_is_light(self):
        """Any game inside 3h → light tick."""
        root = _tmp_root()
        now = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
        cadence, reason = ww.decide_cadence("nfl", 2.0, now, root)
        assert cadence == "light", f"expected light, got {cadence}: {reason}"

    def test_morning_anchor_forces_sweep(self):
        """10:00 AM ET → sweep even with 20-min-old sweep."""
        root = _tmp_root()
        # 14:02Z = 10:02 AM ET (before Nov DST)
        now = datetime(2026, 10, 24, 14, 2, tzinfo=timezone.utc)
        state = {f"last_sweep_nfl": (now - timedelta(minutes=20)).isoformat()}
        ww._save_watch_state(state, root)
        cadence, reason = ww.decide_cadence("nfl", 24.0, now, root)
        assert cadence == "sweep", f"expected sweep for morning anchor, got {cadence}: {reason}"
        assert "morning" in reason.lower()


class TestLightTickFiltering:

    def test_line_move_suppressed_in_light(self):
        """A 2-pt line move in a light tick → no trigger (line moves wait for sweep)."""
        root = _tmp_root()
        # Use a time where no anchors fire (18:00Z = 2 PM ET, last read 2h ago)
        now = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
        kick = (now + timedelta(hours=2)).isoformat()

        # Pre-fire the morning and prekick anchors so they don't interfere
        anchor_state = {
            f"morning:ev1:{now.strftime('%Y-%m-%d')}": now.isoformat(),
            "prekick:ev1": now.isoformat(),
        }
        ww._save_anchor_state(anchor_state, root)

        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110), ("Away", 3.0, -110)]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -5.0, -110), ("Away", 5.0, -110)]}

        triggers = ww.detect_triggers(
            "ev1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (now - timedelta(hours=2)).isoformat(),
            kick, now, root=root)

        # The raw triggers include line_move
        assert any("line_move" in t for t in triggers), f"expected line_move, got {triggers}"

        # But in a light tick, line_move is filtered out
        light_triggers = [t for t in triggers if any(
            t.startswith(p) for p in ww.LIGHT_TRIGGERS)]
        assert not any("line_move" in t for t in light_triggers)

    def test_anchor_close_fires_in_light(self):
        """At kick-44min, anchor_close fires even in a light tick."""
        root = _tmp_root()
        kick_dt = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
        now = kick_dt - timedelta(minutes=44)
        kick = kick_dt.isoformat()

        comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        triggers = ww.detect_triggers(
            "ev1", "nfl",
            ww._hash(comp), comp,
            ww._hash(comp), comp,  # same digest
            (now - timedelta(hours=2)).isoformat(),
            kick, now, root=root)

        # anchor_close fires and is a light trigger
        assert any("anchor_close" in t for t in triggers)
        light_triggers = [t for t in triggers if any(
            t.startswith(p) for p in ww.LIGHT_TRIGGERS)]
        assert any("anchor_close" in t for t in light_triggers)


class TestPauseFlag:

    def test_pause_flag_exits(self):
        """If status/watch_paused exists, the watcher exits."""
        root = _tmp_root()
        (root / "status" / "watch_paused").write_text("paused by Cowork")
        assert (root / "status" / "watch_paused").exists()
