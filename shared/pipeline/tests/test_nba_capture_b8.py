"""
Test basketball_nba and basketball_nba_preseason folder/season mapping (WO2 Item 1, B8).

Must FAIL on origin/main: basketball_nba_preseason is not in FOLDER_MAP -> KeyError.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shared.pipeline.multi_book_open_capture import _folder, _season


# ─── folder mapping ──────────────────────────────────────────────────

def test_nba_folder():
    assert _folder("basketball_nba") == "nba"


def test_nba_preseason_folder():
    """Must FAIL on origin/main: KeyError for basketball_nba_preseason."""
    assert _folder("basketball_nba_preseason") == "nba"


# ─── season label ────────────────────────────────────────────────────

def test_nba_season_october():
    """2026-10-03 -> season 2026 (month >= 7 -> current year)."""
    snap = datetime(2026, 10, 3, 23, 0, tzinfo=timezone.utc)
    assert _season("basketball_nba", snap) == 2026


def test_nba_preseason_october():
    """2026-10-03 preseason -> season 2026."""
    snap = datetime(2026, 10, 3, 23, 0, tzinfo=timezone.utc)
    assert _season("basketball_nba_preseason", snap) == 2026


def test_nba_january():
    """2027-01-15 -> season 2026 (month < 7 -> previous year)."""
    snap = datetime(2027, 1, 15, 3, 0, tzinfo=timezone.utc)
    assert _season("basketball_nba", snap) == 2026


def test_nba_preseason_january():
    """2027-01-15 preseason -> season 2026."""
    snap = datetime(2027, 1, 15, 3, 0, tzinfo=timezone.utc)
    assert _season("basketball_nba_preseason", snap) == 2026


# ─── null control: existing sports unchanged ─────────────────────────

def test_nfl_folder_unchanged():
    assert _folder("americanfootball_nfl") == "nfl"

def test_ncaaf_folder_unchanged():
    assert _folder("americanfootball_ncaaf") == "ncaaf"

def test_nhl_folder_unchanged():
    assert _folder("icehockey_nhl") == "nhl"

def test_mlb_folder_unchanged():
    assert _folder("baseball_mlb") == "baseball_mlb"

def test_nfl_season_unchanged():
    snap = datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc)
    assert _season("americanfootball_nfl", snap) == 2026

def test_nhl_season_unchanged():
    snap = datetime(2027, 1, 15, 3, 0, tzinfo=timezone.utc)
    assert _season("icehockey_nhl", snap) == 2026
