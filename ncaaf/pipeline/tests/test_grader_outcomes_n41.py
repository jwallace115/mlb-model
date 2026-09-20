#!/usr/bin/env python3
"""N41: the grader's OUTCOME path, run through production grade_tickets() on real data.

WO11 shipped CFBD outcomes with no test that read one. On real event tickets every leg came
back `outcome_unavailable`. These tests use:
  fixtures/wo11_outcome_tape.parquet  real DraftKings spread/total rows, 2026-09-19 14:00Z on,
                                      for five Week 3 games (+ FanDuel rows for Arkansas-Georgia
                                      that stop at 15:00Z, i.e. no close inside 30 minutes)
  fixtures/wo11_outcome_cfbd.parquet  the real CFBD rows for those games, plus
                                      Southern 50-31 Louisiana Christian (so "Southern" exists
                                      as a CFBD team, which is what made the mis-map possible)
Tickets are EVENT-shaped, the way build_tickets() writes them: event_id, teams and
commence_time on the ticket, none of them on the leg.
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).resolve().parent / "fixtures"

ENTRY_SNAPSHOT = "2026-09-19T14:30"   # the entry rows are cut from this real snapshot

ARK = "01e9c4d460a55375a75d025e2b1ddbf5"   # Georgia 45 @ Arkansas 17, total 62
KAN = "a317e3ffe5919c8bff3b9b303054f1b3"   # neutral site: tape home = Arizona State, CFBD home = Kansas
USM = "1088ecb8a4c34880f9fb0b9274a8d3e4"   # UConn 48 @ Southern Miss 20
UVA = "eda972dc55ded05916deafa37efab9c3"   # neutral site: tape home = West Virginia, CFBD home = Virginia
APP = "3db3de2fb9101f01f676c1f319837667"   # scheduled 22:00Z, delayed, kicked 01:32Z next day


def _tape():
    return pd.read_parquet(FIX / "wo11_outcome_tape.parquet")


def _event_ticket(event_id, market, side_contains, book="draftkings"):
    """An event-shaped ticket whose leg is one real row of the tape at ENTRY_SNAPSHOT."""
    t = _tape()
    rows = t[(t.event_id == event_id) & (t.bookmaker == book) & (t.market == market)
             & t.snapshot_utc.str.startswith(ENTRY_SNAPSHOT)]
    assert len(rows) == 2, f"fixture: expected 2 {market} rows at entry, got {len(rows)}"
    row = rows[rows.outcome_name.str.contains(side_contains)].iloc[0]
    comp = rows[~rows.outcome_name.str.contains(side_contains)].iloc[0]
    return {
        "event_id": event_id,
        "home_team": row.home_team, "away_team": row.away_team,
        "commence_time": row.commence_time,
        "build_time": row.snapshot_utc,
        "graded": False, "reference_only": True,
        "legs": [{
            "market": market, "side": row.outcome_name,
            "point": float(row.point), "price": float(row.price),
            "book": book, "snapshot_utc": row.snapshot_utc,
            "complement_side": comp.outcome_name,
            "complement_point": float(comp.point), "complement_price": float(comp.price),
        }],
    }


def _grade(tmp_path, tickets, cfbd_edit=None):
    tape_dir = tmp_path / "data" / "odds_archive" / "ncaaf" / "line_history"
    (tape_dir / "season=2026").mkdir(parents=True)
    shutil.copy(FIX / "wo11_outcome_tape.parquet", tape_dir / "season=2026" / "fixture.parquet")
    cfbd = pd.read_parquet(FIX / "wo11_outcome_cfbd.parquet")
    if cfbd_edit is not None:
        cfbd = cfbd_edit(cfbd)
    (tmp_path / "research" / "ncaaf").mkdir(parents=True)
    cfbd.to_parquet(tmp_path / "research" / "ncaaf" / "cfbd_games_2026.parquet", index=False)
    log = tmp_path / "tickets.json"
    log.write_text(json.dumps(tickets))

    from ncaaf.pipeline.grade_ncaaf_tickets import grade_tickets
    with patch("ncaaf.pipeline.grade_ncaaf_tickets.TICKET_LOG", log), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.TAPE_DIR", tape_dir), \
         patch("ncaaf.pipeline.grade_ncaaf_tickets.ROOT", tmp_path):
        changed = grade_tickets(2026)
    return changed, json.loads(log.read_text())


def test_event_ticket_gets_an_outcome(tmp_path):
    """commence_time lives on the ticket. Georgia won 45-17: Georgia -x covers unless x > 28."""
    tickets = [_event_ticket(ARK, "spreads", "Georgia"), _event_ticket(ARK, "totals", "Over")]
    changed, out = _grade(tmp_path, tickets)
    spread, total = out[0]["legs"][0], out[1]["legs"][0]
    assert spread["outcome"] == ("win" if 28 + spread["point"] > 0 else "loss"), spread
    assert total["outcome"] == ("win" if 62 > total["point"] else "loss"), total
    assert changed == 2 and out[0]["graded"] and out[1]["graded"]


def test_neutral_site_home_away_flip(tmp_path):
    """Tape says Arizona State is home, CFBD says Kansas. ASU won 24-17; WVU won 38-27."""
    tickets = [_event_ticket(KAN, "spreads", "Arizona State"),
               _event_ticket(UVA, "spreads", "West Virginia")]
    _, out = _grade(tmp_path, tickets)
    asu, wvu = out[0]["legs"][0], out[1]["legs"][0]
    assert asu["outcome"] == ("win" if 7 + asu["point"] > 0 else "loss" if 7 + asu["point"] < 0 else "push"), asu
    assert wvu["outcome"] == ("win" if 11 + wvu["point"] > 0 else "loss" if 11 + wvu["point"] < 0 else "push"), wvu


def test_southern_miss_is_not_southern(tmp_path):
    """The mascot-stripper turned 'Southern Mississippi Golden Eagles' into 'Southern'."""
    from ncaaf.pipeline.grade_ncaaf_tickets import _odds_to_cfbd
    cfbd = pd.read_parquet(FIX / "wo11_outcome_cfbd.parquet")
    teams = set(cfbd.homeTeam) | set(cfbd.awayTeam)
    assert "Southern" in teams
    assert _odds_to_cfbd("Southern Mississippi Golden Eagles", teams) == "Southern Miss"
    _, out = _grade(tmp_path, [_event_ticket(USM, "spreads", "UConn")])
    leg = out[0]["legs"][0]
    assert leg["outcome"] == ("win" if 28 + leg["point"] > 0 else "loss"), leg


def test_delayed_kickoff_matches_and_closes_at_the_real_kick(tmp_path):
    """App State-Charlotte: ticket says 22:00Z, the game kicked 01:32Z on the next UTC date."""
    _, out = _grade(tmp_path, [_event_ticket(APP, "totals", "Under")])
    leg = out[0]["legs"][0]
    assert leg["outcome"] == ("win" if 47 < leg["point"] else "loss" if 47 > leg["point"] else "push"), leg
    assert out[0]["commence_time"].startswith("2026-09-19T22:00")
    assert leg["close_snapshot_utc"] > "2026-09-20T01:00", leg   # not the 21:30Z quote
    assert leg["kickoff_used_utc"] > "2026-09-20T01:00"


def test_cfbd_not_completed_is_pending_and_not_graded(tmp_path):
    """The 13:00Z grade can run before CFBD has the score. That must not freeze the ticket."""
    def not_yet(cfbd):
        m = cfbd.homeTeam == "Arkansas"
        cfbd.loc[m, ["completed", "homePoints", "awayPoints"]] = [False, None, None]
        return cfbd
    changed, out = _grade(tmp_path, [_event_ticket(ARK, "spreads", "Georgia")], cfbd_edit=not_yet)
    assert out[0]["legs"][0]["outcome"] == "pending"
    assert out[0]["legs"][0]["point_clv"] is not None      # the close was still measured
    assert changed == 0 and out[0]["graded"] is False
    assert out[0]["grade_status"] == "outcome_pending"


def test_no_close_still_gets_an_outcome(tmp_path):
    """FanDuel's fixture rows stop an hour before kick: no close, but Georgia still won."""
    changed, out = _grade(tmp_path, [_event_ticket(ARK, "spreads", "Georgia", book="fanduel")])
    leg = out[0]["legs"][0]
    assert leg["outcome"] in ("win", "loss", "push"), leg
    assert leg["point_clv"] is None and leg.get("last_observed_age_min", 0) > 30
    assert changed == 0 and out[0]["graded"] is False
    assert out[0]["grade_status"] == "close_unavailable"
