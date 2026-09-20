#!/usr/bin/env python3
"""
Phase 5J — run_week.py line-reading tests.

(a) An in-play snapshot is never chosen.
(b) A game with no Hard Rock row is skipped, not priced from another book.
(c) --as-of earlier than every snapshot returns no lines.
"""

import sys
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def line_dir(tmp_path):
    """Create a temporary line-history directory with test fixtures."""
    lh = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    lh.mkdir(parents=True)
    return lh


def _copy_fixture(src_name, dest_dir, dest_name):
    shutil.copy(FIXTURES / src_name, dest_dir / dest_name)


def test_in_play_snapshot_never_chosen(line_dir, monkeypatch):
    """(a) An in-play snapshot (snapshot_utc >= commence_time) is not used."""
    from nfl.sim import run_week

    # Put the in-play snapshot (17:30Z) as the only file
    _copy_fixture("snap_in_play.parquet", line_dir, "snap_20260920T173000Z.parquet")

    monkeypatch.setattr(run_week, "ROOT", line_dir.parent.parent.parent.parent.parent)
    lines = run_week.get_lines_from_history()

    # CAR@ATL kicks at 17:00Z; snapshot at 17:30Z is in-play → no line
    assert "CAR@ATL" not in lines, (
        f"In-play snapshot was chosen for CAR@ATL: {lines.get('CAR@ATL')}"
    )


def test_no_hr_game_skipped(line_dir, monkeypatch):
    """(b) A game with no Hard Rock row is skipped, not priced from another book."""
    from nfl.sim import run_week

    _copy_fixture("snap_no_hr_atl.parquet", line_dir, "snap_20260920T150009Z.parquet")

    monkeypatch.setattr(run_week, "ROOT", line_dir.parent.parent.parent.parent.parent)
    lines = run_week.get_lines_from_history()

    assert "CAR@ATL" not in lines, (
        f"Game without HR was priced: {lines.get('CAR@ATL')}"
    )
    # WAS@DAL should still have a line (HR rows present)
    assert "WAS@DAL" in lines, "WAS@DAL should have a line (HR rows present)"


def test_as_of_before_all_snapshots(line_dir, monkeypatch):
    """(c) --as-of earlier than every snapshot returns no lines."""
    from nfl.sim import run_week

    _copy_fixture("snap_pre_kick.parquet", line_dir, "snap_20260920T150009Z.parquet")

    monkeypatch.setattr(run_week, "ROOT", line_dir.parent.parent.parent.parent.parent)
    # as_of before the snapshot
    lines = run_week.get_lines_from_history(as_of=pd.Timestamp("2026-09-20T14:00:00Z"))

    assert len(lines) == 0, f"Expected no lines with as_of before all snapshots, got {len(lines)}"
