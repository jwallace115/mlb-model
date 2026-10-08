"""Tests for picks_clv.py — RED first, then GREEN.

OPS4a Item 3.
"""
import json
import os
import sys
import pytest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import picks_clv as clv


def _pick(pid="test1", market="spread", side="Seattle Seahawks", point=-8.5,
          price=-110, **kw):
    r = dict(
        pick_id=pid, owner="ai_nfl", sport="NFL", event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z", logged_utc="2026-09-27T16:00:00Z",
        home="Washington", away="Seattle Seahawks",
        market=market, side=side, point=point, price_american=price,
        book="draftkings",
    )
    r.update(kw)
    return r


def _make_snap(tmp_path, ts_str, rows):
    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(tape_dir / f"snap_{ts_str}.parquet", index=False)


# ---- (a) spread: pick -8.5, close -9.5 → clv_points +1.0 ----
def test_spread_clv(tmp_path):
    clv._snap_cache.clear()
    clv._snap_index.clear()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    _make_snap(tmp_path, "20260928T163000Z", [{
        "event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
        "point": -9.5, "price": -110, "bookmaker": "draftkings",
        "snapshot_utc": "2026-09-28T16:30:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T16:30:00Z",
    }])
    picks = [_pick()]
    results = clv.compute_clv(picks, tmp_path, now)
    assert len(results) == 1
    assert results[0]["clv_points"] == 1.0, f"expected +1.0, got {results[0]['clv_points']}"
    assert results[0]["close_point"] == -9.5
    clv._snap_cache.clear()
    clv._snap_index.clear()


# ---- (b) Over 44.5 closing 45.5 → +1.0; Under 44.5 closing 45.5 → -1.0 ----
def test_total_clv(tmp_path):
    clv._snap_cache.clear()
    clv._snap_index.clear()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    _make_snap(tmp_path, "20260928T163000Z", [{
        "event_id": "a" * 32, "market": "totals", "outcome_name": "Over",
        "point": 45.5, "price": -110, "bookmaker": "draftkings",
        "snapshot_utc": "2026-09-28T16:30:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T16:30:00Z",
    }, {
        "event_id": "a" * 32, "market": "totals", "outcome_name": "Under",
        "point": 45.5, "price": -110, "bookmaker": "draftkings",
        "snapshot_utc": "2026-09-28T16:30:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T16:30:00Z",
    }])
    over_pick = _pick(pid="over1", market="total", side="Over", point=44.5)
    under_pick = _pick(pid="under1", market="total", side="Under", point=44.5)
    results = clv.compute_clv([over_pick, under_pick], tmp_path, now)
    by_pid = {r["pick_id"]: r for r in results}
    assert by_pid["over1"]["clv_points"] == 1.0
    assert by_pid["under1"]["clv_points"] == -1.0
    clv._snap_cache.clear()
    clv._snap_index.clear()


# ---- (c) snapshot AFTER commence → never used ----
def test_clv_no_leak(tmp_path):
    clv._snap_cache.clear()
    clv._snap_index.clear()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    # Snap BEFORE commence: -9.5
    _make_snap(tmp_path, "20260928T163000Z", [{
        "event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
        "point": -9.5, "price": -110, "bookmaker": "draftkings",
        "snapshot_utc": "2026-09-28T16:30:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T16:30:00Z",
    }])
    # Snap AFTER commence: -12.0 (planted leak)
    _make_snap(tmp_path, "20260928T180000Z", [{
        "event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
        "point": -12.0, "price": -110, "bookmaker": "draftkings",
        "snapshot_utc": "2026-09-28T18:00:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T18:00:00Z",
    }])
    results = clv.compute_clv([_pick()], tmp_path, now)
    assert results[0]["close_point"] == -9.5, "should use pre-commence snapshot, not the leak"
    clv._snap_cache.clear()
    clv._snap_index.clear()


# ---- (d) no book row → consensus, flagged ----
def test_clv_consensus_fallback(tmp_path):
    clv._snap_cache.clear()
    clv._snap_index.clear()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    _make_snap(tmp_path, "20260928T163000Z", [{
        "event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
        "point": -9.0, "price": -110, "bookmaker": "fanduel",  # not draftkings
        "snapshot_utc": "2026-09-28T16:30:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T16:30:00Z",
    }])
    results = clv.compute_clv([_pick()], tmp_path, now)
    assert results[0]["close_basis"] == "consensus"
    clv._snap_cache.clear()
    clv._snap_index.clear()


# ---- (e) running twice appends nothing ----
def test_clv_idempotent(tmp_path):
    clv._snap_cache.clear()
    clv._snap_index.clear()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    _make_snap(tmp_path, "20260928T163000Z", [{
        "event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
        "point": -9.5, "price": -110, "bookmaker": "draftkings",
        "snapshot_utc": "2026-09-28T16:30:00Z", "sport": "nfl",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "book_last_update": "2026-09-28T16:30:00Z",
    }])
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    clv_path = ledger / "clv.jsonl"

    picks = [_pick()]
    r1 = clv.compute_clv(picks, tmp_path, now)
    with open(clv_path, "w") as f:
        for r in r1:
            f.write(json.dumps(r, default=str) + "\n")

    # Second run: existing pick_ids → nothing new
    existing = {r["pick_id"] for r in r1}
    todo = [p for p in picks if p.get("pick_id") not in existing]
    r2 = clv.compute_clv(todo, tmp_path, now)
    assert len(r2) == 0, "second run should produce 0 rows"
    clv._snap_cache.clear()
    clv._snap_index.clear()


# ---- (f) prop:rec CLV uses player_receptions tape market ----
def _make_prop(tmp_path, rows):
    prop_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=09"
    prop_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(prop_dir / "data_2026_09.parquet", index=False)


def test_prop_rec_clv(tmp_path):
    """prop:rec must match tape market_key=player_receptions, not player_rec."""
    clv._snap_cache.clear()
    clv._snap_index.clear()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    _make_prop(tmp_path, [{
        "event_id": "a" * 32, "market_key": "player_receptions",
        "player_name": "Terry McLaurin", "line": 5.5, "over_price": -120,
        "under_price": 100, "bookmaker": "draftkings",
        "pull_timestamp": "2026-09-28T16:30:00+00:00",
        "last_update": "2026-09-28T16:30:00Z",
        "sport": "nfl", "game_date": "2026-09-28",
        "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Washington", "away_team": "Seattle Seahawks",
        "implied_over": 0.545, "implied_under": 0.5, "snapshot_tag": "close",
    }])
    pick = _pick(pid="rec1", market="prop:rec", side="Over", point=4.5,
                 player_name="Terry McLaurin")
    results = clv.compute_clv([pick], tmp_path, now)
    assert len(results) == 1
    assert results[0]["close_point"] == 5.5, \
        f"expected close 5.5 from player_receptions, got {results[0]['close_point']}"
    clv._snap_cache.clear()
    clv._snap_index.clear()
