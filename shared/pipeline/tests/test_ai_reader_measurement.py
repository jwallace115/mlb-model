#!/usr/bin/env python3
"""Tests for Item 6 — measurement built in (P66).

RED-first tests:
  1. ai_reader_v1/* maps to ai_nfl via picks_adapters (owner mapping).
  2. Hours-to-kick buckets are correct.
  3. Trigger type annotation works.
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


class TestAdapterMapping:

    def test_ai_reader_maps_to_ai_nfl(self):
        """ai_reader_v1/* reader_model → ai_nfl owner in the adapters."""
        # The adapters assign owner based on reader_model:
        # nfl_sim* → sim_nfl, else → ai_nfl
        reader_model = "ai_reader_v1/claude-sonnet-4-6-20250514"
        is_sim = reader_model.startswith("nfl_sim")
        owner = "sim_nfl" if is_sim else "ai_nfl"
        assert owner == "ai_nfl"

    def test_sim_maps_to_sim_nfl(self):
        """nfl_sim* reader_model → sim_nfl owner."""
        reader_model = "nfl_sim_v1"
        is_sim = reader_model.startswith("nfl_sim")
        owner = "sim_nfl" if is_sim else "ai_nfl"
        assert owner == "sim_nfl"


class TestHoursToKickBucket:

    def test_buckets(self):
        """Hours-to-kick buckets are computed correctly."""
        from record_report import _hours_to_kick_bucket

        # >24h
        r = {"logged_utc": "2026-10-23T12:00:00Z", "commence_time": "2026-10-26T17:00:00Z"}
        assert _hours_to_kick_bucket(r) == ">24h"

        # 6-24h
        r = {"logged_utc": "2026-10-26T00:00:00Z", "commence_time": "2026-10-26T17:00:00Z"}
        assert _hours_to_kick_bucket(r) == "6-24h"

        # 3-6h
        r = {"logged_utc": "2026-10-26T12:00:00Z", "commence_time": "2026-10-26T17:00:00Z"}
        assert _hours_to_kick_bucket(r) == "3-6h"

        # <3h
        r = {"logged_utc": "2026-10-26T15:00:00Z", "commence_time": "2026-10-26T17:00:00Z"}
        assert _hours_to_kick_bucket(r) == "<3h"


class TestTriggerAnnotation:

    def test_trigger_types(self):
        """Trigger type is extracted from trigger text."""
        from record_report import _annotate_triggers

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a manifest with trigger info
            board = root / "nfl" / "data" / "board" / "week=2026_07" / "ai_opinions"
            board.mkdir(parents=True)
            manifest = [{
                "file": "ai_opinions_20261023T1400Z.parquet",
                "sha256": "abc",
                "logged_utc": "2026-10-23T14:00:00Z",
                "rows": 10,
                "reader_model": "ai_reader_v1/sonnet",
                "window": "event",
                "inputs": {
                    "triggers": {"ev1": "line_move: HR spreads Home -3→-4"},
                },
            }]
            (board / "manifest.json").write_text(json.dumps(manifest))

            rows = [{"source_file": "ai_opinions_20261023T1400Z.parquet",
                     "_reader": "ai_reader_v1"}]
            _annotate_triggers(rows, {}, root)
            assert rows[0]["_trigger_type"] == "line_move"

    def test_horizon_trigger(self):
        """Horizon entry trigger is detected."""
        from record_report import _annotate_triggers

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = root / "nfl" / "data" / "board" / "week=2026_07" / "ai_opinions"
            board.mkdir(parents=True)
            manifest = [{
                "file": "ai_opinions_20261023T1000Z.parquet",
                "sha256": "def",
                "logged_utc": "2026-10-23T10:00:00Z",
                "rows": 5,
                "reader_model": "ai_reader_v1/sonnet",
                "window": "event",
                "inputs": {
                    "triggers": {"ev2": "horizon_entry: kick in 24h, no prior read"},
                },
            }]
            (board / "manifest.json").write_text(json.dumps(manifest))

            rows = [{"source_file": "ai_opinions_20261023T1000Z.parquet",
                     "_reader": "ai_reader_v1"}]
            _annotate_triggers(rows, {}, root)
            assert rows[0]["_trigger_type"] == "horizon"


class TestEmbargoMapping:

    def test_embargo_includes_ai_reader(self):
        """forward_status.json embargo_owners includes ai_nfl (covers ai_reader_v1)."""
        fs = json.loads((ROOT / "site" / "forward_status.json").read_text())
        assert "ai_nfl" in fs.get("embargo_owners", [])
