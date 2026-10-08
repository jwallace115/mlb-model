"""P20 window tests for log_ai_opinions.py — RED first, then GREEN.

OPS4a Item 1.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.pipeline.log_ai_opinions import (
    freeze, prior_revisions, set_sport, verify,
    P_MIN, P_MAX, NO_VIEW_TOL, TAGS,
)


def _make_sheet(rows):
    df = pd.DataFrame(rows)
    defaults = {
        "imp_first": 0.50, "imp_second": 0.50, "two_way": True, "q_first": 0.50,
        "source_age_min": 5.0, "source_utc": "2026-10-10T16:00:00Z",
        "first_side": "Over", "second_side": "Under",
        "home_team": "KC", "away_team": "BUF",
    }
    for c, v in defaults.items():
        if c not in df:
            df[c] = v
    return df


def _make_filled(sheet):
    f = sheet.copy()
    f["p_first"] = f["q_first"]
    f["tag"] = "no_view"
    f["reason"] = ""
    f["conf"] = 0.0
    f["conf_rank"] = list(range(1, len(f) + 1))
    # Ensure player_name is string type for merge compatibility
    if "player_name" in f.columns:
        f["player_name"] = f["player_name"].fillna("").astype(str)
    return f


_counter = [0]


def _freeze_with_window(sheet, filled, reader_model, window, pilot=False, d=None, now=None):
    set_sport("nfl")
    _counter[0] += 1
    if now is None:
        now = datetime(2026, 10, 10, 15, _counter[0], tzinfo=timezone.utc)
    dest, sha, m = freeze(sheet, filled, 2026, 99, pilot, now,
                          d=d, reader_model=reader_model, window=window)
    return dest, sha, m


def _game_row(eid="a" * 32, commence="2026-10-10T20:00:00Z", **kw):
    r = {"event_id": eid, "commence_time": commence,
         "market_key": "h2h", "player_name": "",
         "line": np.nan, "price_first": -110.0, "price_second": -110.0,
         "book_p_first": 0.5238}
    r.update(kw)
    return r


# ---- (a) freeze without --window → SystemExit ----
def test_freeze_no_window_halts():
    sheet = _make_sheet([_game_row()])
    filled = _make_filled(sheet)
    set_sport("nfl")
    with pytest.raises(SystemExit, match="window"):
        freeze(sheet, filled, 2026, 99, False,
               datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc),
               d=Path(tempfile.mkdtemp()), reader_model="test-model",
               window=None)


# ---- (b) same contract in mid then prekick → both rev 0, no HALT ----
def test_different_windows_no_halt():
    d = Path(tempfile.mkdtemp())
    sheet = _make_sheet([_game_row(commence="2026-10-10T20:00:00Z")])
    filled = _make_filled(sheet)

    # Freeze in mid window
    now1 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    _, _, m1 = _freeze_with_window(sheet, filled, "test-reader", "mid", d=d, now=now1)
    assert (m1["revision"] == 0).all(), "mid freeze should be revision 0"

    # Same contract in prekick window — should NOT HALT
    now2 = datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc)
    _, _, m2 = _freeze_with_window(sheet, filled, "test-reader", "prekick", d=d, now=now2)
    assert (m2["revision"] == 0).all(), "prekick freeze should also be revision 0"


# ---- (c) same window twice in same dir → revision 1 (pilot bypasses cross-dedup) ----
def test_same_window_twice_rev1():
    d = Path(tempfile.mkdtemp())
    # Use spread with a real line (not NaN) so prior_revisions can match
    sheet = _make_sheet([_game_row(
        commence="2026-10-11T20:00:00Z",
        market_key="spreads", line=-3.5, price_first=-110.0, price_second=-110.0,
        book_p_first=0.5238)])
    filled = _make_filled(sheet)

    now1 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    _, _, m1 = _freeze_with_window(sheet, filled, "test-reader", "mid", pilot=True, d=d, now=now1)
    assert (m1["revision"] == 0).all()

    now2 = datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)
    _, _, m2 = _freeze_with_window(sheet, filled, "test-reader", "mid", pilot=True, d=d, now=now2)
    assert (m2["revision"] == 1).all(), "second freeze in same window should be revision 1"


# ---- (d) mid window excludes game 2h out ----
def test_mid_excludes_prekick_game():
    d = Path(tempfile.mkdtemp())
    now = datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc)
    # Game 1: kicks in 2h (inside prekick band) — should be excluded
    # Game 2: kicks in 5h — should stay
    sheet = _make_sheet([
        _game_row(eid="a" * 32, commence="2026-10-10T20:00:00Z"),  # 2h away
        _game_row(eid="b" * 32, commence="2026-10-10T23:00:00Z"),  # 5h away
    ])
    filled = _make_filled(sheet)

    _, _, m = _freeze_with_window(sheet, filled, "test-reader", "mid", d=d, now=now)
    # Only game 2 should be frozen
    assert set(m["event_id"].unique()) == {"b" * 32}, \
        f"mid should exclude game within 3h; got events {m['event_id'].unique()}"


# ---- (e) verify on legacy manifest still passes ----
def test_verify_legacy_manifest():
    d = Path(tempfile.mkdtemp())
    set_sport("nfl")
    # Create a legacy manifest entry (no window key)
    sheet = _make_sheet([_game_row(commence="2026-10-10T20:00:00Z")])
    filled = _make_filled(sheet)
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    dest, sha, m = freeze(sheet, filled, 2026, 99, False, now,
                          d=d, reader_model="test-reader", window="mid")
    # Remove window from manifest to simulate legacy
    man = json.loads((d / "manifest.json").read_text())
    for entry in man:
        entry.pop("window", None)
    (d / "manifest.json").write_text(json.dumps(man))

    # verify should still pass
    verify(season=2026, week=99, d=d)  # no exception = pass
