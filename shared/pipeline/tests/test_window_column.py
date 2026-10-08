"""Tests for window column through the ledger — RED first, then GREEN.

OPS4a Item 2.
"""
import json
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import picks_ledger as pl


def _base_row(**kw):
    r = dict(
        pick_id="test_t1", ticket_id="t1", owner="ai_nfl", source="ai_opinion",
        logged_utc="2026-09-28T12:00:00Z", sport="NFL", event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z", home="Team A", away="Team B",
        market="spread", player_id=None, player_name=None,
        side="Team A", point=-3.5, price_american=-110, book="hardrockbet_fl",
        reason="test", share_link=None, supersedes=None, result=None,
        graded_utc=None, result_source=None, source_file="test.json", source_row=0,
        tag=None, conf=50,
    )
    r.update(kw)
    return r


MEMBERS = {"jeff"}


# ---- (a) window column in COLS; "mid" row admits; missing → view() says "legacy" ----
def test_window_in_ledger(tmp_path):
    # window is in COLS
    assert "window" in pl.COLS

    # Row with window="mid" admits
    row_mid = _base_row(window="mid")
    pl.admit([row_mid], MEMBERS)  # no exception

    # Row without window → view() fills "legacy"
    row_no_window = _base_row(pick_id="test_t2", ticket_id="t2")
    # Don't set window at all
    pl.admit([row_no_window], MEMBERS)
    appended, _ = pl.append([row_no_window], tmp_path)
    assert appended == 1

    v = pl.view(tmp_path)
    assert len(v) == 1
    assert v[0]["window"] == "legacy", f"expected 'legacy', got {v[0].get('window')}"
