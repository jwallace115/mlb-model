"""FWD1c (D219/D220): revision per reader and no_view at floor tests.
All tests call the real functions from log_ai_opinions.py."""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.pipeline.log_ai_opinions import (
    freeze, build_sheet, prior_revisions, set_sport,
    P_MIN, P_MAX, NO_VIEW_TOL, TAGS,
)


def _make_sheet(rows):
    """Build a minimal sheet DataFrame like build_sheet returns."""
    df = pd.DataFrame(rows)
    defaults = {
        "imp_first": 0.50, "imp_second": 0.50, "two_way": True, "q_first": 0.50,
        "source_age_min": 5.0, "source_utc": "2026-10-05T16:00:00Z",
        "first_side": "Over", "second_side": "Under",
        "home_team": "KC", "away_team": "BUF",
    }
    for c, v in defaults.items():
        if c not in df:
            df[c] = v
    return df


def _make_filled(sheet, overrides=None):
    """Build a filled DataFrame matching the sheet."""
    f = sheet.copy()
    f["p_first"] = f["q_first"]
    f["tag"] = "no_view"
    f["reason"] = ""
    f["conf"] = 0.0
    f["conf_rank"] = list(range(1, len(f) + 1))
    if overrides:
        for k, v in overrides.items():
            f[k] = v
    return f


_freeze_counter = [0]

def _freeze_in_temp(sheet, filled, reader_model, pilot=False, d=None, window="adhoc"):
    """Run freeze() in a temp directory and return the resulting DataFrame."""
    set_sport("nfl")
    _freeze_counter[0] += 1
    now = datetime(2026, 10, 5, 15, _freeze_counter[0], tzinfo=timezone.utc)
    dest, sha, m = freeze(sheet, filled, 2026, 99, pilot, now,
                          d=d, reader_model=reader_model, window=window)
    return m


# ── D219 tests ────────────────────────────────────────────────────────────────

def test_revision_reader_a_then_b():
    """Reader A freezes a line, then reader B -> B's row is revision 0."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        row = {"event_id": "e1", "market_key": "player_receptions",
               "player_name": "T.Kelce", "line": 5.5,
               "price_first": -110, "price_second": -110,
               "commence_time": "2026-10-05T17:00:00Z"}
        sheet = _make_sheet([row])
        filled_a = _make_filled(sheet, {"p_first": 0.55, "tag": "matchup",
                                        "reason": "reader A test reason here"})
        _freeze_in_temp(sheet, filled_a, reader_model="reader_A", d=d)
        filled_b = _make_filled(sheet, {"p_first": 0.60, "tag": "sim_v1",
                                        "reason": "reader B test reason here"})
        m = _freeze_in_temp(sheet, filled_b, reader_model="reader_B", d=d)
        assert m.iloc[0]["revision"] == 0, f"Reader B's revision should be 0, got {m.iloc[0]['revision']}"


def test_revision_reader_b_twice():
    """Reader B freezes it again -> revision 1."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        row = {"event_id": "e1", "market_key": "player_receptions",
               "player_name": "T.Kelce", "line": 5.5,
               "price_first": -110, "price_second": -110,
               "commence_time": "2026-10-05T17:00:00Z"}
        sheet = _make_sheet([row])
        filled = _make_filled(sheet, {"p_first": 0.60, "tag": "sim_v1",
                                      "reason": "reader B test reason here"})
        _freeze_in_temp(sheet, filled, reader_model="reader_B", d=d)
        m2 = _freeze_in_temp(sheet, filled, reader_model="reader_B", d=d)
        assert m2.iloc[0]["revision"] == 1, f"Second freeze revision should be 1, got {m2.iloc[0]['revision']}"


def test_revision_pilot_then_live():
    """A pilot file of reader B, then a live file of reader B -> live row is revision 0."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        row = {"event_id": "e1", "market_key": "player_receptions",
               "player_name": "T.Kelce", "line": 5.5,
               "price_first": -110, "price_second": -110,
               "commence_time": "2026-10-05T17:00:00Z"}
        sheet = _make_sheet([row])
        filled = _make_filled(sheet, {"p_first": 0.60, "tag": "sim_v1",
                                      "reason": "reader B test reason here"})
        _freeze_in_temp(sheet, filled, reader_model="reader_B", pilot=True, d=d)
        m_live = _freeze_in_temp(sheet, filled, reader_model="reader_B", pilot=False, d=d)
        assert m_live.iloc[0]["revision"] == 0, f"Live revision should be 0 after pilot, got {m_live.iloc[0]['revision']}"


# ── D220 tests ────────────────────────────────────────────────────────────────

def test_no_view_at_floor_accepted():
    """A +7500 anytime-TD row gets tag no_view and freeze accepts it."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        row = {"event_id": "e1", "market_key": "player_anytime_td",
               "player_name": "J.Doe", "line": 0.5,
               "price_first": 7500, "price_second": np.nan,
               "commence_time": "2026-10-05T17:00:00Z",
               "imp_first": 0.01316, "imp_second": np.nan,
               "two_way": False, "q_first": np.nan}
        sheet = _make_sheet([row])
        sheet["imp_first"] = 0.01316
        sheet["imp_second"] = np.nan
        sheet["two_way"] = False
        sheet["q_first"] = np.nan
        filled = sheet.copy()
        filled["p_first"] = np.clip(0.01316, P_MIN, P_MAX)
        filled["tag"] = "no_view"
        filled["reason"] = ""
        filled["conf"] = 0.0
        filled["conf_rank"] = 1
        m = _freeze_in_temp(sheet, filled, reader_model="test_reader", d=d)
        assert m.iloc[0]["tag"] == "no_view"
