"""Test: current_week.py — OPS-R2 Item 5 (P59).

Week from the schedule, not the calendar.
RED first: today's code has no nfl/pipeline/current_week.py.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable


class TestCurrentWeek:
    """P59: week from the schedule parquet, not calendar arithmetic."""

    def test_script_exists(self):
        """nfl/pipeline/current_week.py must exist."""
        assert (ROOT / "nfl" / "pipeline" / "current_week.py").exists(), \
            "nfl/pipeline/current_week.py does not exist"

    def test_week7_on_tue_open(self):
        """--now 2026-10-20T16:07Z (Tue open window) -> week 7.
        Today's calendar formula: (10-20 - 09-10) / 7 + 1 = 40/7+1 = 6 — the RED."""
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "current_week.py"),
             "--sport", "nfl", "--now", "2026-10-20T16:07:00+00:00"],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"
        week = int(result.stdout.strip())
        assert week == 7, f"expected 7, got {week}"

    def test_week6_on_mnf_day(self):
        """--now 2026-10-19T23:00Z (MNF day, week 6 game still in future) -> 6."""
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "current_week.py"),
             "--sport", "nfl", "--now", "2026-10-19T23:00:00+00:00"],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"
        week = int(result.stdout.strip())
        assert week == 6, f"expected 6, got {week}"

    def test_week7_after_tnf(self):
        """--now 2026-10-23T02:00Z (after week 7 TNF) -> 7 (other week 7 games still ahead)."""
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "current_week.py"),
             "--sport", "nfl", "--now", "2026-10-23T02:00:00+00:00"],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"
        week = int(result.stdout.strip())
        assert week == 7, f"expected 7, got {week}"

    def test_ncaaf_week(self):
        """--sport ncaaf returns a week number."""
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "current_week.py"),
             "--sport", "ncaaf"],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"
        week = int(result.stdout.strip())
        assert week > 0, f"expected positive week, got {week}"
