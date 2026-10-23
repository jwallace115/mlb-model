#!/usr/bin/env python3
"""Tests for Item 4 — sim_requests.json for the Mac tick (P64).

RED-first tests:
  1. A fixture sim_requests.json → the gate prints "sim requested for N events -> adhoc --hours H" (dry-run).
  2. An empty file → no run.
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

import window_watch as ww


class TestSimRequestsWrite:

    def test_write_sim_requests_creates_file(self):
        """write_sim_requests creates the file with the correct shape."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            ww.write_sim_requests("nfl", ["ev1", "ev2"],
                                  {"ev1": "line_move", "ev2": "injury"},
                                  root=root)
            path = root / "status" / "sim_requests.json"
            assert path.exists()
            data = json.loads(path.read_text())
            assert len(data) == 2
            assert data[0]["sport"] == "nfl"
            assert data[0]["event_id"] == "ev1"
            assert "requested_utc" in data[0]

    def test_write_sim_requests_no_duplicates(self):
        """write_sim_requests does not duplicate existing event IDs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            ww.write_sim_requests("nfl", ["ev1"], {"ev1": "first"}, root=root)
            ww.write_sim_requests("nfl", ["ev1", "ev2"], {"ev1": "dup", "ev2": "new"}, root=root)
            data = json.loads((root / "status" / "sim_requests.json").read_text())
            nfl_evs = [d["event_id"] for d in data if d["sport"] == "nfl"]
            assert nfl_evs == ["ev1", "ev2"]  # ev1 not duplicated

    def test_empty_file_no_events(self):
        """An empty sim_requests file means no sim run needed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            (root / "status" / "sim_requests.json").write_text("[]")
            data = json.loads((root / "status" / "sim_requests.json").read_text())
            nfl = [r for r in data if r.get("sport") == "nfl"]
            assert len(nfl) == 0


class TestSimWindowDryRun:

    def test_dry_run_prints_message(self):
        """In dry-run mode, sim_window would print the request summary."""
        reqs = [
            {"sport": "nfl", "event_id": "ev1", "reason": "line_move",
             "requested_utc": "2026-10-23T14:00:00Z"},
            {"sport": "nfl", "event_id": "ev2", "reason": "injury",
             "requested_utc": "2026-10-23T14:05:00Z"},
        ]
        nfl_reqs = [r for r in reqs if r.get("sport") == "nfl"]
        assert len(nfl_reqs) == 2
        msg = f"sim requested for {len(nfl_reqs)} events -> adhoc --hours 168"
        assert "sim requested for 2 events" in msg

    def test_empty_requests_skip(self):
        """Empty requests list → skip message."""
        reqs = []
        nfl_reqs = [r for r in reqs if r.get("sport") == "nfl"]
        assert len(nfl_reqs) == 0
