"""Gate tests for build_top20.py selection — RED first, then GREEN.

OPS3 Item 1.
"""
import copy
import json
import os
import sys
import pytest
from datetime import datetime, timezone

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..")))
import build_top20 as bt
import picks_ledger as pl

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def _row(i, **kw):
    r = dict(
        pick_id=f"pid_{i:04d}",
        ticket_id=f"t_{i}",
        owner="ai_nfl",
        source="ai_opinion",
        logged_utc="2026-09-27T16:00:00Z",
        sport="NFL",
        event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z",
        home="Team Home",
        away="Team Away",
        market="prop:pass_yds",
        player_id=None,
        player_name=f"Player {i}",
        side="Over",
        point=250.5,
        price_american=-110,
        book="draftkings",
        reason="test reason",
        share_link=None,
        supersedes=None,
        result=None,
        graded_utc=None,
        result_source=None,
        ingested_utc="2026-09-27T16:00:00Z",
        source_file="nfl/data/board/week=2026_03/ai_opinions/ai_opinions_20260927T155815Z.parquet",
        source_row=i,
        tag="game_script",
        conf=50 + i,
    )
    r.update(kw)
    return r


# ---- (a) 25 props with conf → exactly 20 in conf order, 5 lowest omitted ----
def test_25_props_top_20():
    rows = [_row(i, conf=i + 1) for i in range(25)]
    result = bt.select(rows, "NFL", NOW)
    assert result is not None
    assert len(result["props"]) == 20
    # Top 20 by conf desc: rows with conf 25, 24, ..., 6
    confs = [r["conf"] for r in result["props"]]
    assert confs == sorted(confs, reverse=True)
    assert confs[0] == 25  # highest
    assert confs[-1] == 6  # 20th highest
    # The 5 lowest (conf 1-5) are NOT in unranked (they have conf)
    assert len(result["unranked"]) == 0
    assert result["n_picks_in_freeze"] == 25


# ---- (b) null-conf rows land in unranked, never ranked ----
def test_null_conf_unranked():
    rows = [_row(0, conf=None), _row(1, conf=50), _row(2, conf=None)]
    result = bt.select(rows, "NFL", NOW)
    assert len(result["props"]) == 1  # only conf=50
    assert len(result["unranked"]) == 2
    assert all(r["conf"] is None for r in result["unranked"])


# ---- (c) sim_nfl row with highest conf is NOT ranked ----
def test_sim_nfl_excluded():
    rows = [_row(0, conf=99, owner="sim_nfl"), _row(1, conf=50)]
    result = bt.select(rows, "NFL", NOW)
    assert len(result["props"]) == 1
    assert result["props"][0]["conf"] == 50


# ---- (d) pick with commence_time < now is excluded ----
def test_past_commence_excluded():
    rows = [_row(0, conf=50, commence_time="2026-09-27T12:00:00Z"),  # past
            _row(1, conf=40)]  # upcoming
    result = bt.select(rows, "NFL", NOW)
    assert len(result["props"]) == 1
    assert result["props"][0]["conf"] == 40


# ---- (e) tie order: |edge| desc then logged_utc asc ----
def test_tie_order():
    rows = [
        _row(0, conf=50, price_american=-200, logged_utc="2026-09-27T16:02:00Z"),
        _row(1, conf=50, price_american=-110, logged_utc="2026-09-27T16:01:00Z"),
        _row(2, conf=50, price_american=-300, logged_utc="2026-09-27T16:03:00Z"),
    ]
    result = bt.select(rows, "NFL", NOW)
    # -300 has largest |edge|, -200 next, -110 smallest
    # Within same |edge|, earlier logged_utc first
    picks = result["props"]
    assert picks[0]["price_american"] == -300  # biggest edge
    assert picks[1]["price_american"] == -200
    assert picks[2]["price_american"] == -110


# ---- (f) two freezes with one logged_utc → HALT ----
def test_duplicate_freeze_halts():
    rows = [
        _row(0, conf=50, source_file="freeze_a.parquet"),
        _row(1, conf=40, source_file="freeze_b.parquet",
             logged_utc="2026-09-27T16:00:00Z"),  # same logged_utc as row 0
    ]
    with pytest.raises(pl.Halt, match="two freezes"):
        bt.select(rows, "NFL", NOW)


# ---- Null control: select() does not mutate its input ----
def test_select_no_mutation():
    rows = [_row(i, conf=i + 1) for i in range(5)]
    original = copy.deepcopy(rows)
    bt.select(rows, "NFL", NOW)
    assert rows == original, "select() mutated its input"


# ---- OPS3b Item 1 ----

# (h) graded rows must not be filtered — ranked lists identical with and without result
def test_graded_rows_not_filtered():
    """Half the rows carry result W/L — select() must return identical ranked lists
    regardless of whether the result field is set."""
    base_rows = [_row(i, conf=50 + i, market="spread", player_name=None,
                       side=f"Team{i}", event_id=f"{i:032x}") for i in range(10)]
    # Copy 1: no results
    clean = copy.deepcopy(base_rows)
    # Copy 2: half graded
    graded = copy.deepcopy(base_rows)
    for i, r in enumerate(graded):
        if i % 2 == 0:
            r["result"] = "W"

    r_clean = bt.select(clean, "NFL", NOW)
    r_graded = bt.select(graded, "NFL", NOW)

    assert r_clean is not None
    assert r_graded is not None
    assert [p["pick_id"] for p in r_clean["sides"]] == [p["pick_id"] for p in r_graded["sides"]]
    assert r_clean["n_picks_in_freeze"] == r_graded["n_picks_in_freeze"]
