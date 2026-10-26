#!/usr/bin/env python3
"""Tests for OPS-ON-1c Item 1 — redacted VM crontab snapshot.

RED first: _redact_line and write_crontab_snapshot did not exist.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

from pipeline_health import _redact_line, write_crontab_snapshot


class TestRedaction:

    def test_api_key_redacted(self):
        """A line with API_KEY=abc123... comes out redacted."""
        line = "0 * * * * source /root/env && ODDS_API_KEY=a1b2c3d4e5f6g7h8 python3 script.py"
        out = _redact_line(line)
        assert "a1b2c3d4e5f6g7h8" not in out
        assert "API_KEY=<redacted>" in out

    def test_40char_hex_redacted(self):
        """A 40-char hex string is redacted."""
        line = "5 * * * * echo abcdef0123456789abcdef0123456789abcdef01"
        out = _redact_line(line)
        assert "abcdef0123456789abcdef0123456789abcdef01" not in out
        assert "<redacted>" in out

    def test_normal_line_verbatim(self):
        """A normal cron line comes out unchanged."""
        line = "40 15 * * 1 bash /root/mlb-model/shared/on_monday.sh"
        out = _redact_line(line)
        assert out == line

    def test_password_env_redacted(self):
        """password=... is redacted (case-insensitive)."""
        line = "0 0 * * * PASSWORD=hunter2 run.sh"
        out = _redact_line(line)
        assert "hunter2" not in out
        assert "PASSWORD=<redacted>" in out


class TestSnapshot:

    def test_write_snapshot(self):
        """write_crontab_snapshot writes a file with the header and redacted content."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crontab = root / "fake_crontab.txt"
            crontab.write_text(
                "# comment\n"
                "SHELL=/bin/bash\n"
                "0 * * * * ODDS_API_KEY=secret123longkey python3 run.py\n"
                "40 15 * * 1 bash /root/mlb-model/shared/on_monday.sh\n"
            )
            out = write_crontab_snapshot(root, str(crontab))
            text = out.read_text()
            assert "# VM crontab as of" in text
            assert "secret123longkey" not in text
            assert "on_monday.sh" in text
