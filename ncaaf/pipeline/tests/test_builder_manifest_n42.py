#!/usr/bin/env python3
"""N42: production build_board -> build_tickets -> build_cards on a slice of the REAL tape.

fixtures/wo11_outcome_tape.parquet: real DraftKings spread/total rows for five 2026-09-19
games, plus FanDuel rows for Arkansas-Georgia that STOP at 15:00Z. At a 15:40Z build
FanDuel's Under 54.5 -106 is a 40-minute-old quote that beats DraftKings' live -108.
Only the Anthropic client is mocked.
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).resolve().parent / "fixtures"

BUILD_TIME = "2026-09-19T15:40:00+00:00"
ARK = "01e9c4d460a55375a75d025e2b1ddbf5"
KAN = "a317e3ffe5919c8bff3b9b303054f1b3"


def _client():
    """Favourite + Under for every game except Arizona State-Kansas, where it abstains."""
    def create(**kw):
        prompt = kw["messages"][0]["content"]
        if "Kansas" in prompt:
            body = {"legs": [], "abstain": True, "abstain_reason": "no edge", "flags": [],
                    "rationale": "pass"}
        else:
            fav = prompt.split("AVAILABLE SPREAD SIDES:")[1].split('"')[1]
            body = {"legs": [{"market": "spreads", "side": fav, "point": 0, "reason": "r"},
                             {"market": "totals", "side": "Under", "point": 0, "reason": "r"}],
                    "abstain": False, "abstain_reason": None, "flags": [], "rationale": "x"}
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps(body))]
        return msg
    c = MagicMock()
    c.messages.create.side_effect = create
    return c


@pytest.fixture
def built(tmp_path):
    tape_dir = tmp_path / "line_history"
    (tape_dir / "season=2026").mkdir(parents=True)
    shutil.copy(FIX / "wo11_outcome_tape.parquet", tape_dir / "season=2026" / "fixture.parquet")
    from ncaaf.pipeline import build_ncaaf_board as B, build_ncaaf_tickets as T
    with patch.object(B, "TAPE_DIR", tape_dir):
        board, _ = B.build_board(2026, build_time=BUILD_TIME)
        tape = B.load_tape(2026, BUILD_TIME)
    news = [{"id": "a1", "_team_name": "Georgia Bulldogs", "headline": "fresh",
             "published": "2026-09-18T12:00:00Z", "_pull_time": "2026-09-19T12:20:00Z"},
            {"id": "a2", "_team_name": "Georgia Bulldogs", "headline": "a month old",
             "published": "2026-08-20T12:00:00Z", "_pull_time": "2026-09-19T12:20:00Z"}]
    with patch.object(T, "ANTHROPIC_KEY", "test_key"), \
         patch("anthropic.Anthropic", return_value=_client()):
        tickets = T.build_tickets(board, news, BUILD_TIME, tape=tape)
    return board, tape, tickets


def test_every_game_seen_is_logged_with_a_manifest(built):
    board, _, tickets = built
    assert {t["event_id"] for t in tickets} == set(board["event_id"])
    kan = next(t for t in tickets if t["event_id"] == KAN)
    assert kan["abstain"] is True and kan["legs"] == [] and kan["abstain_reason"] == "no edge"
    for t in tickets:
        m = t["manifest"]
        assert m["model"] and len(m["prompt_sha256"]) == 64 and m["raw_response"]
        assert m["tape_snapshots"], t["event_id"]
    ark = next(t for t in tickets if t["event_id"] == ARK)
    assert ark["manifest"]["article_keys"] == ["a1"]        # the month-old article is outside 14 days


def test_leg_is_a_live_row_of_its_own_event(built):
    _, tape, tickets = built
    ark = next(t for t in tickets if t["event_id"] == ARK)
    under = next(l for l in ark["legs"] if l["market"] == "totals")
    # FanDuel's stale -106 is the better price at the same point; it cannot be bet at 15:40Z
    assert (under["book"], under["price"]) == ("draftkings", -108.0), under
    assert under["snapshot_utc"].startswith("2026-09-19T15:30")
    assert (under["complement_side"], under["complement_price"]) == ("Over", -112.0)
    for t in tickets:
        for leg in t["legs"]:
            row = tape[(tape.event_id == t["event_id"]) & (tape.snapshot_utc == leg["snapshot_utc"])
                       & (tape.bookmaker == leg["book"]) & (tape.market == leg["market"])
                       & (tape.outcome_name == leg["side"])]
            assert len(row) == 1 and row.iloc[0].point == leg["point"] and row.iloc[0].price == leg["price"]


def test_tape_validation_checks_event_and_snapshot(built):
    from ncaaf.pipeline.build_ncaaf_tickets import validate_leg_against_tape
    _, tape, tickets = built
    ark = next(t for t in tickets if t["event_id"] == ARK)
    leg = dict(ark["legs"][0])
    validate_leg_against_tape(leg, tape, event_id=ARK)
    with pytest.raises(RuntimeError, match="not in tape"):      # a real row — of another game
        validate_leg_against_tape(leg, tape, event_id=KAN)
    with pytest.raises(RuntimeError, match="not in tape"):      # right game, a snapshot it never had
        validate_leg_against_tape({**leg, "snapshot_utc": "2026-09-19T15:31:00+00:00"}, tape,
                                  event_id=ARK)


def test_card_fillers_are_single_book_rows(built):
    from ncaaf.pipeline.build_ncaaf_cards import build_cards
    board, tape, tickets = built
    conviction = [t for t in tickets if t["event_id"] == ARK]
    card_a, card_b, _, fillers = build_cards(conviction, board, BUILD_TIME)
    legs = card_a + card_b
    assert fillers >= 1 and any(l["leg_type"] == "FILLER" for l in legs)
    for l in legs:
        row = tape[(tape.event_id == l["event_id"]) & (tape.snapshot_utc == l["snapshot_utc"])
                   & (tape.bookmaker == l["book"]) & (tape.market == l["market"])
                   & (tape.outcome_name == l["side"])]
        assert len(row) == 1, l
        assert row.iloc[0].point == l["point"] and row.iloc[0].price == l["price"], l
        assert l["complement_price"] is not None, l
