#!/usr/bin/env python3
"""N19: test both-sides invariant and on-board invariant."""

import json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_both_sides_raises():
    """A ticket with both sides of the same market must raise."""
    from ncaaf.pipeline.build_ncaaf_tickets import _validate_ticket

    board_rows = [
        {"market": "spreads", "outcome_name": "Team A", "consensus_point": -3.5},
        {"market": "spreads", "outcome_name": "Team B", "consensus_point": 3.5},
        {"market": "totals", "outcome_name": "Over", "consensus_point": 50.0},
        {"market": "totals", "outcome_name": "Under", "consensus_point": 50.0},
    ]

    # Both sides of spreads — must raise
    bad_ticket = {
        "legs": [
            {"market": "spreads", "side": "Team A", "point": -3.5},
            {"market": "spreads", "side": "Team B", "point": 3.5},
        ]
    }
    with pytest.raises(RuntimeError, match="both-sides"):
        _validate_ticket(bad_ticket, board_rows)


def test_single_side_passes():
    """One side per market is fine."""
    from ncaaf.pipeline.build_ncaaf_tickets import _validate_ticket

    board_rows = [
        {"market": "spreads", "outcome_name": "Team A", "consensus_point": -3.5,
         "quotes": [{"book": "testbook", "point": -3.5, "price": -110}]},
        {"market": "totals", "outcome_name": "Over", "consensus_point": 50.0,
         "quotes": [{"book": "testbook", "point": 50.0, "price": -110}]},
    ]
    good_ticket = {
        "legs": [
            {"market": "spreads", "side": "Team A", "point": -3.5,
             "book": "testbook", "price": -110},
            {"market": "totals", "side": "Over", "point": 50.0,
             "book": "testbook", "price": -110},
        ]
    }
    _validate_ticket(good_ticket, board_rows)  # no raise


def test_leg_not_on_board_raises():
    """A leg that doesn't exist on the board must raise."""
    from ncaaf.pipeline.build_ncaaf_tickets import _validate_ticket

    board_rows = [
        {"market": "spreads", "outcome_name": "Team A", "consensus_point": -3.5,
         "quotes": [{"book": "testbook", "point": -3.5, "price": -110}]},
    ]
    invented_ticket = {
        "legs": [
            {"market": "spreads", "side": "Team A", "point": -7.0,
             "book": "testbook", "price": -110},  # wrong point
        ]
    }
    with pytest.raises(RuntimeError, match="not in any book"):
        _validate_ticket(invented_ticket, board_rows)


def test_favourite_derivation():
    """Favourite is the side with negative spread point."""
    from ncaaf.pipeline.build_ncaaf_tickets import _derive_matchup

    rows = [
        {"market": "spreads", "outcome_name": "Georgia Bulldogs", "consensus_point": -24.5,
         "dispersion": 1.0},
        {"market": "spreads", "outcome_name": "Arkansas Razorbacks", "consensus_point": 24.5,
         "dispersion": 1.0},
        {"market": "totals", "outcome_name": "Over", "consensus_point": 54.5,
         "dispersion": 0.5},
        {"market": "totals", "outcome_name": "Under", "consensus_point": 54.5,
         "dispersion": 0.5},
    ]
    m = _derive_matchup(rows)
    assert m["favourite"] == "Georgia Bulldogs"
    assert m["underdog"] == "Arkansas Razorbacks"
    assert m["spread_magnitude"] == 24.5
