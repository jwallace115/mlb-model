#!/usr/bin/env python3
"""WO11 Item 2: grader handles cards+events, skips pre_repair, 30-min close rule.

Fixture cut from the real ticket log: one event ticket (entry 0) and one card
entry (entry 27 structure), plus a small tape slice and CFBD game result.
"""

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pandas as pd
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _make_tape(tmp_path, event_id, commence, book, market, side, point, price,
               snap_offset_min, complement_side, complement_point, complement_price):
    """Create a tape parquet with one close snapshot."""
    snap_utc = (pd.Timestamp(commence, tz="UTC")
                - pd.Timedelta(minutes=snap_offset_min)).isoformat()
    rows = [
        {"event_id": event_id, "home_team": "Team H", "away_team": "Team A",
         "commence_time": commence, "market": market,
         "outcome_name": side, "bookmaker": book,
         "point": point, "price": price, "snapshot_utc": snap_utc},
        {"event_id": event_id, "home_team": "Team H", "away_team": "Team A",
         "commence_time": commence, "market": market,
         "outcome_name": complement_side, "bookmaker": book,
         "point": complement_point, "price": complement_price,
         "snapshot_utc": snap_utc},
    ]
    tape_dir = tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(tape_dir / "fixture.parquet", index=False)
    return tmp_path


def _make_cfbd(tmp_path, cfbd_home, cfbd_away, home_pts, away_pts, start_date):
    """Create a CFBD games parquet."""
    out_dir = tmp_path / "research" / "ncaaf"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{
        "homeTeam": cfbd_home, "awayTeam": cfbd_away,
        "homePoints": home_pts, "awayPoints": away_pts,
        "completed": True, "startDate": start_date,
    }])
    df.to_parquet(out_dir / "cfbd_games_2026.parquet", index=False)


@pytest.fixture
def grader_fixture(tmp_path):
    """Fixture with one event ticket and one card entry + tape + CFBD."""
    eid = "test_event_01"
    commence = "2026-09-19T20:00:00Z"

    # Tape: close 15 min before kickoff (within 30-min window)
    _make_tape(tmp_path, eid, commence,
               book="bovada", market="spreads",
               side="Team H", point=-7.5, price=-115,
               snap_offset_min=15,
               complement_side="Team A", complement_point=7.5,
               complement_price=-105)

    # CFBD result
    # N41: was "Team H CFBD"/"Team A CFBD" — names the grader could never map from the
    # ticket's "Team H"/"Team A", so this fixture never resolved an outcome and nothing
    # asserted one.
    _make_cfbd(tmp_path, "Team H", "Team A", 35.0, 10.0, commence)

    # Ticket log: one event ticket + one card + one pre_repair
    tickets = [
        {  # event ticket
            "event_id": eid,
            "home_team": "Team H", "away_team": "Team A",
            "commence_time": commence,
            "legs": [{"market": "spreads", "side": "Team H",
                      "point": -7.0, "price": -110, "book": "bovada",
                      "snapshot_utc": "2026-09-19T10:00:00Z",
                      "complement_side": "Team A",
                      "complement_point": 7.0, "complement_price": -110}],
            "build_time": "2026-09-19T10:00:00Z",
            "graded": False, "reference_only": True,
        },
        {  # card entry (event_id on legs)
            "card_id": "TEST_CARD",
            "build_time": "2026-09-19T10:00:00Z",
            "graded": False, "reference_only": True,
            "legs": [{"market": "spreads", "side": "Team H",
                      "point": -7.0, "price": -110, "book": "bovada",
                      "snapshot_utc": "2026-09-19T10:00:00Z",
                      "event_id": eid,
                      "home_team": "Team H", "away_team": "Team A",
                      "commence_time": commence}],
        },
        {  # pre_repair entry (must be skipped)
            "event_id": eid,
            "home_team": "Team H", "away_team": "Team A",
            "commence_time": commence,
            "legs": [{"market": "spreads", "side": "Team H",
                      "point": -7.0, "price": -110, "book": "bovada"}],
            "build_time": "2026-09-19T10:00:00Z",
            "graded": False, "reference_only": True,
            "pre_repair": True,
        },
    ]
    log_path = tmp_path / "test_tickets.json"
    with open(log_path, "w") as f:
        json.dump(tickets, f)
    return tmp_path, log_path


def test_grader_handles_cards_and_events(grader_fixture):
    """Grader must not crash on card entries (event_id on legs)."""
    tmp_path, log_path = grader_fixture
    from ncaaf.pipeline.grade_ncaaf_tickets import grade_tickets

    with patch("ncaaf.pipeline.grade_ncaaf_tickets.TICKET_LOG", log_path), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.TAPE_DIR",
               tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history"), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.ROOT", tmp_path):
        changed = grade_tickets(2026)

    # 2 tickets graded (event + card), pre_repair skipped
    assert changed == 2, f"Expected 2 graded, got {changed}"

    with open(log_path) as f:
        result = json.load(f)
    # N41: Team H -7.0 won 35-10 — event ticket and card leg both resolve
    assert result[0]["legs"][0]["outcome"] == "win"
    assert result[1]["legs"][0]["outcome"] == "win"
    # pre_repair entry stays ungraded
    assert result[2]["graded"] == False
    assert result[2].get("pre_repair") == True


def test_30min_close_rule(tmp_path):
    """A snapshot older than 30 min before kickoff must not produce CLV."""
    from ncaaf.pipeline.grade_ncaaf_tickets import grade_tickets

    eid = "test_old_close"
    commence = "2026-09-19T20:00:00Z"

    # Tape: snapshot 60 min before kickoff (outside 30-min window)
    _make_tape(tmp_path, eid, commence,
               book="bovada", market="spreads",
               side="Team H", point=-7.5, price=-115,
               snap_offset_min=60,
               complement_side="Team A", complement_point=7.5,
               complement_price=-105)

    _make_cfbd(tmp_path, "Team H", "Team A", 35.0, 10.0, commence)

    tickets = [{
        "event_id": eid,
        "home_team": "Team H", "away_team": "Team A",
        "commence_time": commence,
        "legs": [{"market": "spreads", "side": "Team H",
                  "point": -7.0, "price": -110, "book": "bovada",
                  "snapshot_utc": "2026-09-19T10:00:00Z"}],
        "build_time": "2026-09-19T10:00:00Z",
        "graded": False, "reference_only": True,
    }]
    log_path = tmp_path / "test_tickets.json"
    with open(log_path, "w") as f:
        json.dump(tickets, f)

    with patch("ncaaf.pipeline.grade_ncaaf_tickets.TICKET_LOG", log_path), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.TAPE_DIR",
               tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history"), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.ROOT", tmp_path):
        changed = grade_tickets(2026)

    with open(log_path) as f:
        result = json.load(f)

    # Ticket stays ungraded because close is too old
    assert result[0]["graded"] == False
    assert result[0].get("grade_status") == "close_unavailable"
    leg = result[0]["legs"][0]
    assert leg.get("point_clv") is None
    assert leg.get("last_observed_point") == -7.5


def test_point_clv_spread(tmp_path):
    """Spread CLV = entry_point - close_point (same team)."""
    from ncaaf.pipeline.grade_ncaaf_tickets import grade_tickets

    eid = "test_clv_spread"
    commence = "2026-09-19T20:00:00Z"

    # Entry: -7.0, Close: -7.5 -> point_clv = -7.0 - (-7.5) = +0.5
    _make_tape(tmp_path, eid, commence,
               book="bovada", market="spreads",
               side="Team H", point=-7.5, price=-115,
               snap_offset_min=15,
               complement_side="Team A", complement_point=7.5,
               complement_price=-105)
    _make_cfbd(tmp_path, "Team H", "Team A", 35.0, 10.0, commence)

    tickets = [{
        "event_id": eid,
        "home_team": "Team H", "away_team": "Team A",
        "commence_time": commence,
        "legs": [{"market": "spreads", "side": "Team H",
                  "point": -7.0, "price": -110, "book": "bovada",
                  "snapshot_utc": "2026-09-19T10:00:00Z",
                  "complement_side": "Team A",
                  "complement_point": 7.0, "complement_price": -110}],
        "build_time": "2026-09-19T10:00:00Z",
        "graded": False, "reference_only": True,
    }]
    log_path = tmp_path / "test_tickets.json"
    with open(log_path, "w") as f:
        json.dump(tickets, f)

    with patch("ncaaf.pipeline.grade_ncaaf_tickets.TICKET_LOG", log_path), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.TAPE_DIR",
               tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history"), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.ROOT", tmp_path):
        changed = grade_tickets(2026)

    with open(log_path) as f:
        result = json.load(f)

    assert result[0]["graded"] == True
    leg = result[0]["legs"][0]
    assert leg["point_clv"] == 0.5, f"Expected +0.5, got {leg.get('point_clv')}"
