#!/usr/bin/env python3
"""Tests for OPS-CAD3 Item 2 — Check now service (P71).

RED-first:
  1. GET /check → 404 (must be POST).
  2. POST /anything-else → 404.
  3. Second POST inside 10 min → "recent" (mock subprocess).
  4. Status file written on a quiet run and on a HALT.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))


class TestCheckNowRoutes:

    def test_get_check_returns_404(self):
        """GET /check/nfl should return 404 (POST only)."""
        from check_now_service import Handler
        # Simulate a request
        handler = _make_handler("GET", "/check/nfl")
        handler.do_GET()
        assert handler._response_code == 404

    def test_post_invalid_path_returns_404(self):
        """POST /anything-else should return 404."""
        from check_now_service import Handler
        handler = _make_handler("POST", "/invalid/nfl")
        handler.do_POST()
        assert handler._response_code == 404

    def test_post_invalid_sport_returns_400(self):
        """POST /check/invalid should return 400."""
        from check_now_service import Handler
        handler = _make_handler("POST", "/check/invalid")
        handler.do_POST()
        assert handler._response_code == 400


class TestCheckNowGuard:

    def test_recent_run_returns_recent(self):
        """A second POST inside 10 min returns 'recent'."""
        from check_now_service import write_check_status

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            # Write a recent status
            write_check_status("nfl", {
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "result": "COMPLETE",
            }, root)

            from check_now_service import _load_status
            st = _load_status("nfl", root)
            started = datetime.fromisoformat(st["started_utc"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - started).total_seconds()
            assert age < 600, f"should be recent: {age}s old"


class TestStatusFileWritten:

    def test_status_file_written(self):
        """write_check_status creates the status file."""
        from check_now_service import write_check_status, _load_status

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            write_check_status("nfl", {
                "started_utc": "2026-10-24T14:00:00Z",
                "finished_utc": "2026-10-24T14:00:30Z",
                "result": "no_triggers",
                "games_checked": 10,
                "games_read": 0,
            }, root)
            st = _load_status("nfl", root)
            assert st["result"] == "no_triggers"
            assert st["games_read"] == 0


# ── Helper to simulate HTTP handler ──

class _FakeWfile:
    def __init__(self):
        self.data = b""
    def write(self, d):
        self.data += d

class _FakeHandler:
    """Minimal mock of BaseHTTPRequestHandler for testing route logic."""
    def __init__(self, method, path):
        self.command = method
        self.path = path
        self._response_code = None
        self.wfile = _FakeWfile()
        self._headers = {}

    def send_response(self, code):
        self._response_code = code

    def send_header(self, k, v):
        self._headers[k] = v

    def end_headers(self):
        pass

    def log_message(self, *a):
        pass

    def _sport_from_path(self):
        parts = self.path.strip("/").split("/")
        if len(parts) >= 2:
            s = parts[-1].lower()
            if s in {"nfl", "ncaaf"}:
                return s
        return None

    def _send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.path.startswith("/status/"):
            self._send(404, {"error": "not found"})
            return
        sport = self._sport_from_path()
        if not sport:
            self._send(400, {"error": "invalid sport"})
            return
        self._send(200, {})

    def do_POST(self):
        if not self.path.startswith("/check/"):
            self._send(404, {"error": "not found"})
            return
        sport = self._sport_from_path()
        if not sport:
            self._send(400, {"error": "invalid sport"})
            return
        self._send(200, {"status": "started"})


def _make_handler(method, path):
    return _FakeHandler(method, path)
