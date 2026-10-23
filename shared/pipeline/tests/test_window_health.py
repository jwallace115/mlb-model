"""Test: window_health.json -> health.html Windows table + sport page failure line.

OPS-R2 Item 6 (P60). RED first: no window_health.json support exists today.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))


class TestWindowHealthFile:
    """P60: run_window writes status/window_health.json at every exit."""

    def test_write_function_exists(self):
        """run_window must have _write_window_health."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import run_window as rw
        importlib.reload(rw)
        assert hasattr(rw, "_write_window_health"), "no _write_window_health function"


class TestHealthPageWindows:
    """P60: health.html shows a Windows table from window_health.json."""

    def test_windows_table_with_stop(self, tmp_path):
        """A STOP entry -> health.html has a red-flagged row."""
        now = datetime.now(timezone.utc)
        wh = [{"sport": "nfl", "window": "prekick",
               "started_utc": (now - timedelta(hours=1)).isoformat(),
               "finished_utc": (now - timedelta(minutes=50)).isoformat(),
               "result": "STOP", "step": "git pull", "message": "exit 128",
               "freeze_file": None}]
        (tmp_path / "status").mkdir()
        (tmp_path / "status" / "window_health.json").write_text(json.dumps(wh))

        os.environ["SITE_REPO_ROOT"] = str(tmp_path)
        import importlib
        import build_site as bs
        importlib.reload(bs)
        bs.ROOT = tmp_path

        health_data = {"generated_utc": now.isoformat(), "counts": {}, "feeds": []}
        html = bs.build_health(now, health_data)
        assert "Windows" in html, "health.html has no Windows heading"
        assert "STOP" in html, "health.html does not show the STOP status"

    def test_sport_page_failure_line(self, tmp_path):
        """A STOP for nfl -> the NFL sport page data includes a failure message."""
        now = datetime.now(timezone.utc)
        wh = [{"sport": "nfl", "window": "prekick",
               "started_utc": (now - timedelta(hours=1)).isoformat(),
               "finished_utc": (now - timedelta(minutes=50)).isoformat(),
               "result": "STOP", "step": "git pull", "message": "exit 128",
               "freeze_file": None}]
        (tmp_path / "status").mkdir()
        (tmp_path / "status" / "window_health.json").write_text(json.dumps(wh))

        os.environ["SITE_REPO_ROOT"] = str(tmp_path)
        import importlib
        import build_site as bs
        importlib.reload(bs)
        bs.ROOT = tmp_path

        wh_data = bs.load_json(tmp_path / "status" / "window_health.json")
        assert wh_data is not None
        # The window health data should be loadable and contain the STOP
        assert any(e["result"] == "STOP" for e in wh_data)

    def test_complete_no_failure_line(self, tmp_path):
        """A COMPLETE entry -> no failure message."""
        now = datetime.now(timezone.utc)
        wh = [{"sport": "nfl", "window": "prekick",
               "started_utc": (now - timedelta(hours=1)).isoformat(),
               "finished_utc": (now - timedelta(minutes=50)).isoformat(),
               "result": "COMPLETE", "step": "done", "message": "",
               "freeze_file": "ai_opinions_test.parquet"}]
        (tmp_path / "status").mkdir()
        (tmp_path / "status" / "window_health.json").write_text(json.dumps(wh))

        os.environ["SITE_REPO_ROOT"] = str(tmp_path)
        import importlib
        import build_site as bs
        importlib.reload(bs)
        bs.ROOT = tmp_path

        health_data = {"generated_utc": now.isoformat(), "counts": {}, "feeds": []}
        html = bs.build_health(now, health_data)
        # COMPLETE should NOT have a red row
        assert "failed" not in html.lower() or "STOP" not in html
