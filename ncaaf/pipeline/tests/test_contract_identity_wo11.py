#!/usr/bin/env python3
"""WO11 Item 1: every leg is one row of one book — no consensus/best mixing.

Fixture cut from real tape: Ohio State event 6eee31d7 (2026-09-19T11 build).
betonlineag offered -52.0 @ -110; betmgm offered -53.0 @ -115.
consensus_point = -52.5 — a number NO book offers.
The old code wrote point=-52.5, book=betonlineag, price=-110 (mixed sources).
"""

import json, sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


FIXTURE_ROWS = [
    # betonlineag: Buckeyes -52.0 @ -110
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "spreads", "outcome_name": "Ohio State Buckeyes",
     "bookmaker": "betonlineag", "point": -52.0, "price": -110,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "spreads", "outcome_name": "WKU Hilltoppers",
     "bookmaker": "betonlineag", "point": 52.0, "price": -110,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    # betmgm: Buckeyes -53.0 @ -115
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "spreads", "outcome_name": "Ohio State Buckeyes",
     "bookmaker": "betmgm", "point": -53.0, "price": -115,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "spreads", "outcome_name": "WKU Hilltoppers",
     "bookmaker": "betmgm", "point": 53.0, "price": -115,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    # Totals: bovada Over 48.5 @ -115, williamhill_us Over 49.5 @ -117
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "totals", "outcome_name": "Over",
     "bookmaker": "bovada", "point": 48.5, "price": -115,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "totals", "outcome_name": "Under",
     "bookmaker": "bovada", "point": 48.5, "price": -105,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "totals", "outcome_name": "Over",
     "bookmaker": "williamhill_us", "point": 49.5, "price": -117,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
    {"event_id": "6eee31d7", "home_team": "Ohio State Buckeyes",
     "away_team": "WKU Hilltoppers", "commence_time": "2026-09-19T20:00:00Z",
     "market": "totals", "outcome_name": "Under",
     "bookmaker": "williamhill_us", "point": 49.5, "price": -103,
     "snapshot_utc": "2026-09-19T10:00:00Z"},
]


@pytest.fixture
def tape_fixture(tmp_path):
    """Create a mini tape with books offering different points."""
    tape_dir = tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True)
    df = pd.DataFrame(FIXTURE_ROWS)
    df.to_parquet(tape_dir / "fixture.parquet", index=False)
    return tmp_path, df


def test_board_carries_quotes(tape_fixture):
    """Board rows must carry per-book quotes so legs are real contracts."""
    tmp_path, _ = tape_fixture
    from ncaaf.pipeline.build_ncaaf_board import build_board

    with patch("ncaaf.pipeline.build_ncaaf_board.TAPE_DIR",
               tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history"):
        board_df, _ = build_board(2026, build_time="2026-09-19T12:00:00Z")

    assert not board_df.empty, "Board is empty"
    assert "quotes" in board_df.columns, (
        "Board row missing 'quotes' — legs cannot be verified as real contracts")

    for _, row in board_df.iterrows():
        qs = row["quotes"]
        assert isinstance(qs, list) and len(qs) > 0, f"No quotes for {row['outcome_name']}"
        for q in qs:
            assert all(k in q for k in ("book", "point", "price", "snapshot_utc")), (
                f"Quote missing required field: {q}")


def test_select_best_quote_spreads():
    """Spread: best quote = most positive point, then best price, then book name."""
    from ncaaf.pipeline.build_ncaaf_tickets import select_best_quote

    quotes = [
        {"book": "betonlineag", "point": -52.0, "price": -110,
         "snapshot_utc": "2026-09-19T10:00:00Z"},
        {"book": "betmgm", "point": -53.0, "price": -115,
         "snapshot_utc": "2026-09-19T10:00:00Z"},
    ]
    best = select_best_quote(quotes, "spreads", "Ohio State Buckeyes")
    assert best["point"] == -52.0, f"Expected -52.0 (most positive), got {best['point']}"
    assert best["book"] == "betonlineag"


def test_select_best_quote_over():
    """Over: best quote = lowest point."""
    from ncaaf.pipeline.build_ncaaf_tickets import select_best_quote

    quotes = [
        {"book": "bovada", "point": 48.5, "price": -115,
         "snapshot_utc": "2026-09-19T10:00:00Z"},
        {"book": "williamhill_us", "point": 49.5, "price": -117,
         "snapshot_utc": "2026-09-19T10:00:00Z"},
    ]
    best = select_best_quote(quotes, "totals", "Over")
    assert best["point"] == 48.5, f"Over: expected 48.5 (lowest), got {best['point']}"


def test_select_best_quote_under():
    """Under: best quote = HIGHEST point (today's code uses consensus — wrong)."""
    from ncaaf.pipeline.build_ncaaf_tickets import select_best_quote

    quotes = [
        {"book": "bovada", "point": 48.5, "price": -105,
         "snapshot_utc": "2026-09-19T10:00:00Z"},
        {"book": "williamhill_us", "point": 49.5, "price": -103,
         "snapshot_utc": "2026-09-19T10:00:00Z"},
    ]
    best = select_best_quote(quotes, "totals", "Under")
    assert best["point"] == 49.5, f"Under: expected 49.5 (highest), got {best['point']}"


def test_validate_leg_against_tape(tape_fixture):
    """A leg with consensus_point must fail tape validation."""
    _, tape_df = tape_fixture
    from ncaaf.pipeline.build_ncaaf_tickets import validate_leg_against_tape

    # Consensus point -52.5 does not exist at betonlineag (they have -52.0)
    bad_leg = {"market": "spreads", "side": "Ohio State Buckeyes",
               "point": -52.5, "price": -110, "book": "betonlineag",
               "snapshot_utc": "2026-09-19T10:00:00Z"}
    with pytest.raises(RuntimeError, match="not in tape"):
        validate_leg_against_tape(bad_leg, tape_df)

    # A real row should pass
    good_leg = {"market": "spreads", "side": "Ohio State Buckeyes",
                "point": -52.0, "price": -110, "book": "betonlineag",
                "snapshot_utc": "2026-09-19T10:00:00Z"}
    validate_leg_against_tape(good_leg, tape_df)  # no raise
