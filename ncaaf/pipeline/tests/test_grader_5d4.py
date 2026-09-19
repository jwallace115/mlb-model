#!/usr/bin/env python3
"""N12: test that a future-kickoff ticket is NOT graded."""

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_future_kickoff_not_graded(tmp_path):
    """A ticket with commence_time in the future must not be graded."""
    from ncaaf.pipeline.grade_ncaaf_tickets import grade_tickets, TICKET_LOG

    # Create a ticket with a future kickoff
    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    tickets = [{
        "event_id": "test_future",
        "home_team": "Team A",
        "away_team": "Team B",
        "commence_time": future,
        "legs": [{"market": "spreads", "side": "Team A", "point": -3.5,
                  "price": -110, "book": "test", "implied": 0.52,
                  "close_price": None, "clv": None}],
        "ai_flags": [], "ai_rationale": "test",
        "build_time": datetime.now(timezone.utc).isoformat(),
        "reference_only": True, "close_price": None, "clv": None,
        "graded": False,
    }]

    log_path = tmp_path / "test_tickets.json"
    with open(log_path, "w") as f:
        json.dump(tickets, f)

    with patch("ncaaf.pipeline.grade_ncaaf_tickets.TICKET_LOG", log_path):
        changed = grade_tickets(2026)

    assert changed == 0, f"Future-kickoff ticket was graded (changed={changed})"

    with open(log_path) as f:
        result = json.load(f)
    assert result[0]["graded"] == False, "Future ticket marked graded=True"
    assert result[0]["legs"][0]["clv"] is None, "Future ticket has CLV"
