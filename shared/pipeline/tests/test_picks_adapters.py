"""Gate tests for picks_adapters.py Item 2 — RED first, then GREEN.

OPS2b Item 2.
"""
import json, os, sys, pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import picks_adapters as pa
import picks_ledger as pl
import pick_sources as ps


def _inject_tape(events):
    """Inject events directly into the tape cache for testing."""
    df = pd.DataFrame(events)
    df["snap_commence"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
    pa._tape_cache["nfl"] = df


# ---- (a) row with game "A @ B", build_time, no commence resolves to single tape event ----
def test_no_commence_resolves_from_build_time():
    pa._tape_cache.clear()
    _inject_tape([{
        "event_id": "a" * 32,
        "home_team": "Detroit Lions",
        "away_team": "Kansas City Chiefs",
        "commence_time": "2026-09-28T17:00:00+00:00",
    }])
    try:
        eid, tc = pa._resolve_event_from_build_time(
            "Detroit Lions", "Kansas City Chiefs", "2026-09-27T12:00:00Z", "NFL", "nfl")
        assert eid == "a" * 32
        assert "2026-09-28" in tc
    finally:
        pa._tape_cache.clear()


# ---- (b) two events for the same pair in the window → HALT ----
def test_two_events_same_pair_halts():
    pa._tape_cache.clear()
    _inject_tape([
        {"event_id": "a" * 32, "home_team": "Detroit Lions", "away_team": "Kansas City Chiefs",
         "commence_time": "2026-09-28T17:00:00+00:00"},
        {"event_id": "b" * 32, "home_team": "Detroit Lions", "away_team": "Kansas City Chiefs",
         "commence_time": "2026-09-29T17:00:00+00:00"},
    ])
    try:
        with pytest.raises(pl.Halt, match="multiple"):
            pa._resolve_event_from_build_time(
                "Detroit Lions", "Kansas City Chiefs", "2026-09-27T12:00:00Z", "NFL", "nfl")
    finally:
        pa._tape_cache.clear()


# ---- (c) OPS2 fixture rows still admit unchanged ----
def test_ops2_fixture_row_still_admits():
    """A row that worked under OPS2 still works after the Item 2 changes."""
    row = dict(
        ticket_id="test_t1", owner="jeff", source="ai_opinion",
        logged_utc="2026-09-28T12:00:00Z",
        sport="NFL", event_id="a" * 32, commence_time="2026-09-28T17:00:00Z",
        home="Team A", away="Team B", market="spread", player_id=None,
        player_name=None, side="Team A", point=-3.5, price_american=-110,
        book="hardrockbet_fl", reason="test", share_link=None, supersedes=None,
        result=None, graded_utc=None, result_source=None,
        source_file="test.json", source_row=0,
    )
    pl.admit([row], {"jeff"})  # must not raise


# ---- (d) freeze fixture: no_view excluded, sim owner, tag+conf carried ----
def test_freeze_fixture_owners_and_tag(tmp_path):
    """A freeze with three rows: tag=no_view with side, tag=injury_news, tag=sim_v1
    yields exactly two picks with correct owners and tag/conf."""
    pa._tape_cache.clear()

    # Create a tape
    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "event_id": "a" * 32,
        "home_team": "Team Home",
        "away_team": "Team Away",
        "commence_time": "2026-09-28T17:00:00+00:00",
    }]).to_parquet(tape_dir / "snap_20260927T000000Z.parquet", index=False)

    # Create a freeze file
    week_dir = tmp_path / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    week_dir.mkdir(parents=True, exist_ok=True)
    base = {
        "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00+00:00",
        "home_team": "Team Home", "away_team": "Team Away",
        "first_side": "Team Home", "second_side": "Team Away",
        "price_first": -110.0, "price_second": -110.0,
        "source_utc": "2026-09-27T20:00:00Z", "imp_first": 0.5, "imp_second": 0.5,
        "two_way": True, "q_first": 0.5, "source_age_min": 10, "p_first": 0.5,
        "book_p_first": 0.5, "gap": 0.0,
        "edge": 0.0, "revision": 1, "season": 2026, "week": 3, "pilot": False,
        "sport": "NFL", "book": "fanduel", "logged_utc": "2026-09-27T20:00:00Z",
    }
    rows = [
        {**base, "market_key": "spreads", "player_name": None, "line": -3.5,
         "tag": "no_view", "reason": "no opinion", "conf": 0, "conf_rank": 0,
         "side": "first", "side_name": "Team Home", "side_price": -110.0,
         "reader_model": "claude-opus-5-5"},
        {**base, "market_key": "totals", "player_name": None, "line": 45.5,
         "tag": "injury_news", "reason": "key player out", "conf": 78, "conf_rank": 2,
         "side": "second", "side_name": "Under", "side_price": -110.0,
         "reader_model": "claude-opus-5-5"},
        {**base, "market_key": "h2h", "player_name": None, "line": None,
         "tag": "sim_v1", "reason": "sim pick", "conf": 65, "conf_rank": 5,
         "side": "first", "side_name": "Team Home", "side_price": -110.0,
         "reader_model": "nfl_sim_v1_abc123"},
    ]
    pd.DataFrame(rows).to_parquet(week_dir / "ai_opinions_20260927T200000Z.parquet", index=False)

    try:
        result_rows, rejected, nfiles = pa.adapt_nfl_ai_opinions(root=tmp_path)
        assert nfiles == 1
        assert len(result_rows) == 2, f"expected 2 picks (no_view excluded), got {len(result_rows)}"
        assert len(rejected) == 0

        owners = {r["owner"] for r in result_rows}
        assert "ai_nfl" in owners
        assert "sim_nfl" in owners

        ai_row = [r for r in result_rows if r["owner"] == "ai_nfl"][0]
        assert ai_row["tag"] == "injury_news"
        assert ai_row["conf"] == 78

        sim_row = [r for r in result_rows if r["owner"] == "sim_nfl"][0]
        assert sim_row["tag"] == "sim_v1"
        assert sim_row["conf"] == 65
    finally:
        pa._tape_cache.clear()
