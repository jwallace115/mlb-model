"""Gate tests for spread sign fix + point audit — RED first, then GREEN.

OPS3c Item 1.
"""
import copy
import json
import os
import sys
import pytest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import picks_ledger as pl


# ---- (1) adapter: second-side spread negates line; totals/props unchanged ----
def test_adapter_spread_sign():
    """Freeze with one spread second (line 8.5) and one spread first (line -7)
    → points -8.5 and -7; totals 44.5 and prop 177.5 unchanged."""
    import picks_adapters as pa

    pa._tape_cache.clear()

    # Build a minimal freeze parquet
    rows = [
        # spread, side=second, line=8.5 → point should be -8.5
        {"event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington Commanders", "away_team": "Seattle Seahawks",
         "market_key": "spreads", "player_name": None, "line": 8.5,
         "first_side": "Washington Commanders", "second_side": "Seattle Seahawks",
         "price_first": -110.0, "price_second": -110.0,
         "source_utc": "2026-09-27T15:58:00Z", "imp_first": 0.5, "imp_second": 0.5,
         "two_way": True, "q_first": 0.5, "source_age_min": 10,
         "p_first": 0.5, "book_p_first": 0.5, "edge": 0.0,
         "tag": "game_script", "reason": "SEA -8.5", "conf": 75, "conf_rank": 1,
         "gap": 0.0, "side": "second", "side_name": "Seattle Seahawks", "side_price": -110.0,
         "revision": 1, "season": 2026, "week": 3, "pilot": False,
         "sport": "NFL", "book": "hardrockbet_fl", "reader_model": "claude-opus-5-5",
         "logged_utc": "2026-09-27T15:58:15Z"},
        # spread, side=first, line=-7 → point should be -7 (unchanged)
        {"event_id": "b" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Denver Broncos", "away_team": "Las Vegas Raiders",
         "market_key": "spreads", "player_name": None, "line": -7.0,
         "first_side": "Denver Broncos", "second_side": "Las Vegas Raiders",
         "price_first": -110.0, "price_second": -110.0,
         "source_utc": "2026-09-27T15:58:00Z", "imp_first": 0.5, "imp_second": 0.5,
         "two_way": True, "q_first": 0.5, "source_age_min": 10,
         "p_first": 0.5, "book_p_first": 0.5, "edge": 0.0,
         "tag": "game_script", "reason": "DEN -7", "conf": 34, "conf_rank": 2,
         "gap": 0.0, "side": "first", "side_name": "Denver Broncos", "side_price": -110.0,
         "revision": 1, "season": 2026, "week": 3, "pilot": False,
         "sport": "NFL", "book": "hardrockbet_fl", "reader_model": "claude-opus-5-5",
         "logged_utc": "2026-09-27T15:58:15Z"},
        # totals, line=44.5 → point unchanged
        {"event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington Commanders", "away_team": "Seattle Seahawks",
         "market_key": "totals", "player_name": None, "line": 44.5,
         "first_side": "Over", "second_side": "Under",
         "price_first": -110.0, "price_second": -110.0,
         "source_utc": "2026-09-27T15:58:00Z", "imp_first": 0.5, "imp_second": 0.5,
         "two_way": True, "q_first": 0.5, "source_age_min": 10,
         "p_first": 0.5, "book_p_first": 0.5, "edge": 0.0,
         "tag": "game_script", "reason": "under 44.5", "conf": 26, "conf_rank": 3,
         "gap": 0.0, "side": "second", "side_name": "Under", "side_price": -110.0,
         "revision": 1, "season": 2026, "week": 3, "pilot": False,
         "sport": "NFL", "book": "hardrockbet_fl", "reader_model": "claude-opus-5-5",
         "logged_utc": "2026-09-27T15:58:15Z"},
        # prop, line=177.5 → point unchanged
        {"event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington Commanders", "away_team": "Seattle Seahawks",
         "market_key": "player_pass_yds", "player_name": "Cam Ward", "line": 177.5,
         "first_side": "Over", "second_side": "Under",
         "price_first": -115.0, "price_second": -105.0,
         "source_utc": "2026-09-27T15:58:00Z", "imp_first": 0.5, "imp_second": 0.5,
         "two_way": True, "q_first": 0.5, "source_age_min": 10,
         "p_first": 0.5, "book_p_first": 0.5, "edge": 0.0,
         "tag": "game_script", "reason": "over 177.5", "conf": 17, "conf_rank": 4,
         "gap": 0.0, "side": "first", "side_name": "Over", "side_price": -115.0,
         "revision": 1, "season": 2026, "week": 3, "pilot": False,
         "sport": "NFL", "book": "hardrockbet_fl", "reader_model": "claude-opus-5-5",
         "logged_utc": "2026-09-27T15:58:15Z"},
    ]
    df = pd.DataFrame(rows)

    # Write to a temp dir as a freeze parquet
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    week_dir = tmp / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    week_dir.mkdir(parents=True)
    df.to_parquet(week_dir / "ai_opinions_20260927T155815Z.parquet", index=False)

    # Also need tape for resolution
    tape_dir = tmp / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True)
    tape_df = pd.DataFrame([
        {"event_id": "a" * 32, "home_team": "Washington Commanders", "away_team": "Seattle Seahawks",
         "commence_time": "2026-09-28T17:00:00Z"},
        {"event_id": "b" * 32, "home_team": "Denver Broncos", "away_team": "Las Vegas Raiders",
         "commence_time": "2026-09-28T17:00:00Z"},
    ])
    tape_df.to_parquet(tape_dir / "snap_20260927T140000Z.parquet", index=False)

    result_rows, rejected, nfiles = pa.adapt_nfl_ai_opinions(root=tmp)

    # Find the rows by side_name
    sea = [r for r in result_rows if r["side"] == "Seattle Seahawks"]
    den = [r for r in result_rows if r["side"] == "Denver Broncos"]
    under = [r for r in result_rows if r["side"] == "Under"]
    over = [r for r in result_rows if r["side"] == "Over" and r.get("player_name")]

    assert len(sea) == 1, f"expected 1 Seattle row, got {len(sea)}"
    assert sea[0]["point"] == -8.5, f"Seattle point should be -8.5, got {sea[0]['point']}"

    assert len(den) == 1, f"expected 1 Denver row, got {len(den)}"
    assert den[0]["point"] == -7.0, f"Denver point should be -7.0, got {den[0]['point']}"

    # Null controls: totals and props unchanged
    assert len(under) == 1
    assert under[0]["point"] == 44.5, f"Under total should be 44.5, got {under[0]['point']}"

    assert len(over) == 1
    assert over[0]["point"] == 177.5, f"Over prop should be 177.5, got {over[0]['point']}"

    pa._tape_cache.clear()


# ---- (2) audit: flipped vs correct + leak exclusion ----
def test_audit_classes(tmp_path):
    import picks_point_audit as ppa
    ppa._snap_cache.clear()

    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "members.json").write_text('{"members":["jeff"]}')

    rows = [
        {"pick_id": "flipped_001", "ticket_id": "t1", "owner": "ai_nfl", "source": "ai_opinion",
         "logged_utc": "2026-09-27T16:00:00Z", "sport": "NFL", "event_id": "a" * 32,
         "commence_time": "2026-09-28T17:00:00Z", "home": "Washington", "away": "Seattle Seahawks",
         "market": "spread", "player_id": None, "player_name": None,
         "side": "Seattle Seahawks", "point": 8.5, "price_american": -110,
         "book": "draftkings", "reason": "SEA -8.5", "share_link": None, "supersedes": None,
         "result": None, "graded_utc": None, "result_source": None,
         "ingested_utc": "2026-09-27T16:00:00Z", "source_file": "test.pq", "source_row": 0,
         "tag": None, "conf": 75},
        {"pick_id": "correct_001", "ticket_id": "t2", "owner": "ai_nfl", "source": "ai_opinion",
         "logged_utc": "2026-09-27T16:00:00Z", "sport": "NFL", "event_id": "b" * 32,
         "commence_time": "2026-09-28T17:00:00Z", "home": "Denver Broncos", "away": "Las Vegas Raiders",
         "market": "spread", "player_id": None, "player_name": None,
         "side": "Denver Broncos", "point": -7.0, "price_american": -110,
         "book": "draftkings", "reason": "DEN -7", "share_link": None, "supersedes": None,
         "result": None, "graded_utc": None, "result_source": None,
         "ingested_utc": "2026-09-27T16:00:00Z", "source_file": "test.pq", "source_row": 1,
         "tag": None, "conf": 34},
    ]
    with open(ledger / "picks.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True)
    before_snap = pd.DataFrame([
        {"event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -8.5, "price": -110, "bookmaker": "draftkings",
         "snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "commence_time": "2026-09-28T17:00:00Z", "home_team": "Washington", "away_team": "Seattle Seahawks",
         "book_last_update": "2026-09-27T14:00:00Z"},
        {"event_id": "b" * 32, "market": "spreads", "outcome_name": "Denver Broncos",
         "point": -7.0, "price": -110, "bookmaker": "draftkings",
         "snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "commence_time": "2026-09-28T17:00:00Z", "home_team": "Denver Broncos", "away_team": "Las Vegas Raiders",
         "book_last_update": "2026-09-27T14:00:00Z"},
    ])
    before_snap.to_parquet(tape_dir / "snap_20260927T140000Z.parquet", index=False)
    # Leak file AFTER logged_utc
    after_snap = before_snap.copy()
    after_snap.loc[0, "point"] = -10.5
    after_snap.to_parquet(tape_dir / "snap_20260927T180000Z.parquet", index=False)

    results = ppa.audit(tmp_path, ledger)
    classes = {r["pick_id"]: r["_class"] for r in results}
    assert classes["flipped_001"] == "SIGN_FLIPPED"
    assert classes["correct_001"] == "AGREES"
    snaps_used = {r["_snapshot"] for r in results}
    assert "snap_20260927T180000Z.parquet" not in snaps_used
    ppa._snap_cache.clear()


# ---- (3) repair + regrade + idempotent ----
def test_repair_and_regrade(tmp_path):
    import picks_point_audit as ppa
    ppa._snap_cache.clear()

    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "members.json").write_text('{"members":["jeff"]}')

    rows = [
        {"pick_id": "flipped_001", "ticket_id": "t1", "owner": "ai_nfl", "source": "ai_opinion",
         "logged_utc": "2026-09-27T16:00:00Z", "sport": "NFL", "event_id": "a" * 32,
         "commence_time": "2026-09-28T17:00:00Z", "home": "Washington", "away": "Seattle Seahawks",
         "market": "spread", "player_id": None, "player_name": None,
         "side": "Seattle Seahawks", "point": 8.5, "price_american": -110,
         "book": "draftkings", "reason": "SEA -8.5", "share_link": None, "supersedes": None,
         "result": None, "graded_utc": None, "result_source": None,
         "ingested_utc": "2026-09-27T16:00:00Z", "source_file": "test.pq", "source_row": 0,
         "tag": None, "conf": 75},
    ]
    with open(ledger / "picks.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True)
    pd.DataFrame([
        {"event_id": "a" * 32, "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -8.5, "price": -110, "bookmaker": "draftkings",
         "snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "commence_time": "2026-09-28T17:00:00Z", "home_team": "Washington", "away_team": "Seattle Seahawks",
         "book_last_update": "2026-09-27T14:00:00Z"},
    ]).to_parquet(tape_dir / "snap_20260927T140000Z.parquet", index=False)

    # Crosswalk: WAS 33 - SEA 31
    pd.DataFrame([
        {"event_id": "a" * 32, "official_game_id": "g1", "home_score": 33, "away_score": 31,
         "completed": True, "home_team": "Washington", "away_team": "Seattle Seahawks"},
    ]).to_parquet(ledger / "crosswalk_nfl.parquet", index=False)

    n = ppa.repair(tmp_path, ledger)
    assert n == 1

    view = pl.view(ledger)
    pids = {r["pick_id"] for r in view}
    assert "flipped_001" not in pids
    corrected = [r for r in view if r.get("supersedes") == "flipped_001"]
    assert len(corrected) == 1
    assert corrected[0]["point"] == -8.5

    graded = [r for r in pl._read_all(ledger) if r.get("pick_id") == corrected[0]["pick_id"] and r.get("result")]
    assert len(graded) == 1
    assert graded[0]["result"] == "L"

    # Idempotent
    n2 = ppa.repair(tmp_path, ledger)
    assert n2 == 0
    ppa._snap_cache.clear()
