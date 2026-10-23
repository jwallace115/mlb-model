#!/usr/bin/env python3
"""Tests for shared/pipeline/window_watch.py — P62 OPS-CAD1 Item 2.

RED-first tests:
  1. Spread moves 0.5 → no trigger; 1.0 → trigger.
  2. Injury-hash change triggers immediately inside the 30-min limit.
  3. Identical digest → freeze HALTs.
  4. Quiet fixture → "no triggers" and no API call.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

import window_watch as ww


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────

def _now():
    return datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)


def _kick():
    return "2026-10-26T17:00:00Z"  # 3 days out


# ──────────────────────────────────────────────────────────────────────────
# Test 1: Spread move thresholds
# ──────────────────────────────────────────────────────────────────────────

class TestSpreadMoveThreshold:

    def test_spread_05_no_trigger(self):
        """A 0.5 spread move does NOT trigger."""
        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110), ("Away", 3.0, -110)]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -3.5, -110), ("Away", 3.5, -110)]}
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (_now() - timedelta(hours=1)).isoformat(),
            _kick(), _now())
        line_triggers = [t for t in triggers if "line_move" in t and "spreads" in t]
        assert len(line_triggers) == 0, f"0.5 move should not trigger: {triggers}"

    def test_spread_10_triggers(self):
        """A 1.0 spread move DOES trigger."""
        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110), ("Away", 3.0, -110)]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -4.0, -110), ("Away", 4.0, -110)]}
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (_now() - timedelta(hours=1)).isoformat(),
            _kick(), _now())
        line_triggers = [t for t in triggers if "line_move" in t and "spreads" in t]
        assert len(line_triggers) > 0, f"1.0 move should trigger: {triggers}"


# ──────────────────────────────────────────────────────────────────────────
# Test 2: Injury-hash change triggers immediately inside 30-min limit
# ──────────────────────────────────────────────────────────────────────────

class TestInjuryBypassRateLimit:

    def test_injury_bypasses_30min(self):
        """An injury-hash change triggers even if last read was 10 min ago."""
        old_comp = {"inj_Home": "aaa", "hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        new_comp = {"inj_Home": "bbb", "hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        # Last read only 10 min ago
        last_logged = (_now() - timedelta(minutes=10)).isoformat()
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            last_logged, _kick(), _now())
        assert any("injury" in t for t in triggers), \
            f"injury change should bypass 30-min limit: {triggers}"

    def test_non_injury_rate_limited(self):
        """A non-injury change within 30 min is rate-limited."""
        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)],
                    "news": ["old headline"]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)],
                    "news": ["old headline", "new headline"]}
        last_logged = (_now() - timedelta(minutes=10)).isoformat()
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            last_logged, _kick(), _now())
        assert len(triggers) == 0, \
            f"non-injury change within 30 min should be rate-limited: {triggers}"


# ──────────────────────────────────────────────────────────────────────────
# Test 3: Identical digest → no trigger (freeze would HALT)
# ──────────────────────────────────────────────────────────────────────────

class TestIdenticalDigest:

    def test_identical_digest_no_trigger(self):
        """Same digest → no triggers returned."""
        comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        digest = ww._hash(comp)
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            digest, comp,
            digest, comp,  # same digest
            (_now() - timedelta(hours=1)).isoformat(),
            _kick(), _now())
        assert len(triggers) == 0, f"identical digest should not trigger: {triggers}"


# ──────────────────────────────────────────────────────────────────────────
# Test 4: Quiet fixture → "no triggers"
# ──────────────────────────────────────────────────────────────────────────

class TestQuietFixture:

    def test_quiet_returns_empty(self):
        """When nothing changed, watch_once returns empty triggers."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create minimal structure with no games
            (root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026").mkdir(parents=True)
            (root / "nfl" / "data" / "board").mkdir(parents=True)

            triggered, details = ww.watch_once("nfl", root=root, now=_now(), dry_run=True)
            assert triggered == []
            assert details == {}


# ──────────────────────────────────────────────────────────────────────────
# Test: Horizon entry trigger
# ──────────────────────────────────────────────────────────────────────────

class TestHorizonEntry:

    def test_horizon_triggers_within_48h(self):
        """A game within 48h with no prior read triggers horizon_entry."""
        comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        kick = (_now() + timedelta(hours=24)).isoformat()  # 24h out
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(comp), comp,
            None, None, None,  # no prior read
            kick, _now())
        assert any("horizon" in t for t in triggers)

    def test_no_horizon_beyond_48h(self):
        """A game beyond 48h with no prior read does NOT trigger."""
        comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        kick = (_now() + timedelta(hours=72)).isoformat()  # 72h out
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(comp), comp,
            None, None, None,
            kick, _now())
        assert len(triggers) == 0


# ──────────────────────────────────────────────────────────────────────────
# Test: Blackout zone
# ──────────────────────────────────────────────────────────────────────────

class TestBlackout:

    def test_blackout_inside_20min(self):
        """No trigger inside the last 20 min before kick."""
        old_comp = {"hardrockbet_fl_spreads": [("Home", -3.0, -110)]}
        new_comp = {"hardrockbet_fl_spreads": [("Home", -5.0, -110)]}
        kick = (_now() + timedelta(minutes=15)).isoformat()  # 15 min out
        triggers = ww.detect_triggers(
            "eid1", "nfl",
            ww._hash(new_comp), new_comp,
            ww._hash(old_comp), old_comp,
            (_now() - timedelta(hours=1)).isoformat(),
            kick, _now())
        assert len(triggers) == 0, f"blackout should prevent trigger: {triggers}"
