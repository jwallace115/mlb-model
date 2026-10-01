"""
Tests for NBA in log_ai_opinions.py (WO2 Item 2, B9).

Each test must FAIL on origin/main (NBA not in SPORTS dict -> KeyError).
Fixtures: real 2025-26 tape snapshot reshaped to tape schema, real ESPN scoreboard.
"""
import json, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TAPE_FIXTURE = FIXTURE_DIR / "nba_tape_20260316T2300Z.parquet"


def _set_nba():
    """Set sport to nba. FAILS on origin/main: KeyError."""
    from nfl.pipeline.log_ai_opinions import set_sport
    set_sport("nba")


def _load_tape_fixture():
    return pd.read_parquet(TAPE_FIXTURE)


def _nba_sheet(slate_date, tape=None, now=None):
    """Build an NBA sheet from the fixture tape."""
    _set_nba()
    from nfl.pipeline.log_ai_opinions import build_sheet
    if tape is None:
        tape = _load_tape_fixture()
    if now is None:
        now = datetime(2026, 3, 16, 22, 0, tzinfo=timezone.utc)  # before 23:10 tip
    props = pd.DataFrame(columns=["event_id", "commence_time", "home_team", "away_team",
                                  "bookmaker", "market_key", "player_name", "line",
                                  "over_price", "under_price", "pull_timestamp"])
    return build_sheet(props, tape, now, slate_date=slate_date)


def _filled(sheet, tag="matchup", drivers="market,history"):
    """Minimal filled CSV from a sheet."""
    filled = sheet.copy()
    filled["p_first"] = 0.55
    filled["tag"] = tag
    filled["reason"] = "test reason for b9"
    filled["side"] = "first"
    filled["drivers"] = drivers
    filled["conf"] = 0.6
    filled["conf_rank"] = range(1, len(filled) + 1)
    return filled


# ─── Test: NBA set_sport works ────────────────────────────────────────

def test_nba_sport_registered():
    """FAILS on origin/main: KeyError for 'nba'."""
    _set_nba()
    from nfl.pipeline.log_ai_opinions import SPORT, BOOK
    assert SPORT == "nba"
    assert BOOK == "pinnacle"


# ─── Test: date_season works ─────────────────────────────────────────

def test_date_season():
    from nfl.pipeline.log_ai_opinions import date_season
    assert date_season("2026-10-20") == 2026
    assert date_season("2027-03-15") == 2026


# ─── Test: sheet from tape ───────────────────────────────────────────

def test_nba_sheet_from_tape():
    """Sheet builds from tape fixture with Pinnacle prices."""
    sheet = _nba_sheet("2026-03-16")
    assert len(sheet) > 0
    assert set(sheet["market_key"].unique()) == {"h2h", "spreads", "totals"}


# ─── Test: freeze refuses without --reader-model ─────────────────────

def test_freeze_requires_reader_model():
    _set_nba()
    from nfl.pipeline.log_ai_opinions import freeze
    sheet = _nba_sheet("2026-03-16")
    filled = _filled(sheet)
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(SystemExit, match="reader-model"):
            freeze(sheet, filled, 2025, None, False,
                   datetime(2026, 3, 16, 22, 0, tzinfo=timezone.utc),
                   d=Path(tmpdir), reader_model=None, slate_date="2026-03-16")


# ─── Test: freeze refuses started game ───────────────────────────────

def test_freeze_refuses_started_game():
    _set_nba()
    from nfl.pipeline.log_ai_opinions import freeze
    sheet = _nba_sheet("2026-03-16")
    filled = _filled(sheet)
    # now AFTER game tip (23:10Z) -> games have kicked off
    now_late = datetime(2026, 3, 16, 23, 30, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(SystemExit, match="kicked off"):
            freeze(sheet, filled, 2025, None, False, now_late,
                   d=Path(tmpdir), reader_model="test", slate_date="2026-03-16")


# ─── Test: freeze refuses preseason without --pilot ──────────────────

def test_freeze_refuses_preseason_without_pilot():
    _set_nba()
    tape = _load_tape_fixture().copy()
    tape["sport"] = "basketball_nba_preseason"  # mark as preseason
    sheet = _nba_sheet("2026-03-16", tape=tape)
    filled = _filled(sheet)
    from nfl.pipeline.log_ai_opinions import freeze
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(SystemExit, match="preseason"):
            freeze(sheet, filled, 2025, None, False,  # pilot=False
                   datetime(2026, 3, 16, 22, 0, tzinfo=timezone.utc),
                   d=Path(tmpdir), reader_model="test", slate_date="2026-03-16")


# ─── Test: freeze requires --packet for NBA (drivers_required) ───────

def test_freeze_requires_packet():
    _set_nba()
    from nfl.pipeline.log_ai_opinions import freeze
    sheet = _nba_sheet("2026-03-16")
    filled = _filled(sheet)
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(SystemExit, match="packet"):
            freeze(sheet, filled, 2025, None, False,
                   datetime(2026, 3, 16, 22, 0, tzinfo=timezone.utc),
                   d=Path(tmpdir), reader_model="test", slate_date="2026-03-16",
                   packet_path=None)


# ─── Test: ESPN NBA outcomes grades a real game ──────────────────────

def test_espn_nba_outcomes():
    """_espn_nba_actuals returns home_pts/away_pts for a real game."""
    from nfl.pipeline.log_ai_opinions import _espn_nba_actuals
    actuals_fn = _espn_nba_actuals()
    # ATL vs ORL on 2026-03-16 — ATL 124, ORL 112 (from ESPN)
    act = actuals_fn("Atlanta Hawks", "Orlando Magic", "2026-03-16T23:10:00Z")
    assert act is not None, "Game not found"
    assert act["home_pts"] == 124
    assert act["away_pts"] == 112
    total = act["home_pts"] + act["away_pts"]
    assert total == 236


# ─── Test: OT game total includes OT ─────────────────────────────────

def test_espn_nba_ot_included():
    """DEN vs POR 2026-04-06: 5 periods, total 269 (not 250 regulation)."""
    from nfl.pipeline.log_ai_opinions import _espn_nba_actuals
    actuals_fn = _espn_nba_actuals()
    act = actuals_fn("Denver Nuggets", "Portland Trail Blazers", "2026-04-07T02:00:00Z")
    assert act is not None
    total = act["home_pts"] + act["away_pts"]
    assert total == 269, f"OT total should be 269, got {total}"


# ─── Test: CLV computation runs for NBA ──────────────────────────────

def test_nba_clv_branch_exists():
    """The CLV block covers espn_nba outcomes type."""
    _set_nba()
    from nfl.pipeline.log_ai_opinions import SPORTS
    assert SPORTS["nba"]["outcomes"] == "espn_nba"
    assert SPORTS["nba"]["book"] == "pinnacle"
