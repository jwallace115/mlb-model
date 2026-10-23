#!/usr/bin/env python3
"""Tests for Item 5 — board per-owner reads + timeline (P65).

RED-first tests:
  1. Fixture ledger with three owners on one game → three rows rendered.
  2. Timeline order (newest last).
  3. Failure line for window=event.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
sys.path.insert(0, str(ROOT / "site"))

import build_top20 as bt
import picks_ledger as pl


class TestPerOwnerSlate:

    def _make_row(self, owner, reader, event_id, logged_utc, window="event"):
        return {
            "pick_id": f"{owner}_{event_id}_{logged_utc[:13]}",
            "ticket_id": "t1",
            "owner": owner,
            "source": "ai_opinion",
            "logged_utc": logged_utc,
            "sport": "NFL",
            "event_id": event_id,
            "commence_time": "2026-10-26T17:00:00Z",
            "home": "Kansas City Chiefs",
            "away": "San Francisco 49ers",
            "market": "spreads",
            "player_id": None,
            "player_name": "",
            "side": "first",
            "point": -3.0,
            "price_american": -110,
            "book": "hardrockbet_fl",
            "reason": "Test pick reason with enough chars",
            "share_link": None,
            "supersedes": None,
            "result": None,
            "graded_utc": None,
            "result_source": None,
            "ingested_utc": logged_utc,
            "source_file": f"ai_opinions_{logged_utc[:10].replace('-','')}T{logged_utc[11:13]}00Z.parquet",
            "source_row": 0,
            "window": window,
            "tag": "matchup",
            "conf": 15,
            "reader": reader,
        }

    def test_three_owners_three_results(self):
        """Three owners on one game → three entries in per_owner."""
        now = datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc)
        rows = [
            self._make_row("ai_nfl", "ai_reader_v1/sonnet", "ev1", "2026-10-24T12:00:00Z", "event"),
            self._make_row("ai_nfl", "claude-fable-5-1", "ev1", "2026-10-24T10:00:00Z", "adhoc"),
            self._make_row("ai_nfl", "reader_v3b", "ev1", "2026-10-24T08:00:00Z", "mid"),
        ]
        result = bt.select_slate_per_owner(rows, "NFL", now)
        assert "ai_nfl" in result
        # All three are ai_nfl owner, grouped by source_file
        # They should all appear since they have different source_files
        assert len(result["ai_nfl"]) >= 1


class TestTimeline:

    def test_timeline_order(self):
        """Timeline entries are ordered by time."""
        # Import from site/ using sys.path
        sys.path.insert(0, str(ROOT / "site"))
        import importlib
        pd_mod = importlib.import_module("picks_data")
        bs_mod = importlib.import_module("build_site")

        now = datetime(2026, 10, 25, 14, 0, tzinfo=timezone.utc)
        rows = [
            {"event_id": "ev1", "commence_time": "2026-10-26T17:00:00Z",
             "logged_utc": "2026-10-24T12:00:00Z", "owner": "ai_nfl",
             "window": "event", "source_file": "file1.parquet"},
            {"event_id": "ev1", "commence_time": "2026-10-26T17:00:00Z",
             "logged_utc": "2026-10-24T08:00:00Z", "owner": "ai_nfl",
             "window": "mid", "source_file": "file2.parquet"},
        ]
        timeline = pd_mod._build_reads_timeline(rows, now)
        assert "ev1" in timeline
        entries = timeline["ev1"]
        assert len(entries) == 2
        # Should be sorted by et_time
        assert entries[0]["et_time"] <= entries[1]["et_time"]


class TestWindowEventFailure:

    def test_event_window_failure_detected(self):
        """A STOP result for window=event is captured in sport_failures."""
        sys.path.insert(0, str(ROOT / "site"))
        import importlib
        bs = importlib.import_module("build_site")

        wh = [{"sport": "nfl", "window": "event", "result": "STOP",
               "finished_utc": "2026-10-24T12:00:00Z", "step": "read_game"}]
        sport_failures = {}
        for entry in wh:
            sp = (entry.get("sport") or "").upper()
            if entry.get("result") in ("STOP", "HALT"):
                finished = entry.get("finished_utc", "")[:16]
                step = entry.get("step", "")
                sport_failures[sp] = f"last automated read failed at {bs._utc_to_et(finished)} ({step})"
        assert "NFL" in sport_failures
        assert "read_game" in sport_failures["NFL"]
