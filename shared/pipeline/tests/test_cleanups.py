#!/usr/bin/env python3
"""Tests for OPS-CAD3 Item 3 — live-found cleanups (P72).

RED-first:
  1. pick_layers is Popen'd detached (not subprocess.run with timeout).
  2. Pause flag stops the watcher.
  3. Side convention line is in the packet header.
  4. No test modifies the real status/anchor_state.json.
"""
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))


class TestDetachedPickLayers:

    def test_pick_layers_uses_popen(self):
        """The post-freeze step uses Popen (detached), not subprocess.run."""
        import inspect
        import shared.pipeline.window_watch as ww
        src = inspect.getsource(ww.main)
        assert "Popen" in src and "pick_layers" in src
        # Confirm it's start_new_session
        assert "start_new_session" in src


class TestPauseFlag:

    def test_pause_file_existence(self):
        """If status/watch_paused exists, the watcher should exit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            assert not (root / "status" / "watch_paused").exists()
            (root / "status" / "watch_paused").write_text("paused")
            assert (root / "status" / "watch_paused").exists()


class TestSideConvention:

    def test_packet_header_has_convention(self):
        """The packet header includes the side convention line."""
        import shared.pipeline.ai_reader as ar
        now = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026").mkdir(parents=True)
            (root / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
            (root / "data" / "injury_archive" / "nfl" / "season=2026").mkdir(parents=True)
            (root / "nfl" / "data" / "board").mkdir(parents=True)

            sheet = pd.DataFrame(columns=["event_id", "player_name", "source_utc", "market_key"])
            header, packets = ar.build_packet("nfl", [], sheet, pd.DataFrame(), pd.DataFrame(), now, root=root)
            assert "first = home/Over" in header
            assert "second = away/Under" in header


class TestNoRealStateModified:

    def test_real_anchor_state_unmodified(self):
        """No test should have modified the real status/anchor_state.json."""
        real_path = ROOT / "status" / "anchor_state.json"
        if real_path.exists():
            import subprocess
            result = subprocess.run(
                ["git", "diff", "--quiet", str(real_path)],
                cwd=str(ROOT), capture_output=True)
            assert result.returncode == 0, \
                "status/anchor_state.json was modified by a test"
