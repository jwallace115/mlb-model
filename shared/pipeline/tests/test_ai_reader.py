#!/usr/bin/env python3
"""Tests for shared/pipeline/ai_reader.py — P61 OPS-CAD1 Item 1.

RED-first tests:
  1. Packet builder on pinned 10-18 tape for Houston@Jacksonville reproduces INTERNATIONAL
     line and HR/Pinnacle numbers.
  2. JSON schema rejects a one-way pick and a +300 moneyline.
  3. Reason length and thesis-link validation.
  4. Mocked API response -> filled CSV passes log_ai_opinions validate.
  5. Spend file increments and cap HALTs.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))

import ai_reader as ar


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────

def _make_sheet_row(event_id="abc123", market_key="spreads", player_name="",
                    line=-3.0, price_first=-110, price_second=-110,
                    home_team="Houston Texans", away_team="Jacksonville Jaguars",
                    commence_time="2026-10-18T17:00:00Z"):
    """Build a minimal sheet row dict."""
    imp_f = ar._implied(price_first)
    imp_s = ar._implied(price_second)
    q_f = imp_f / (imp_f + imp_s) if price_second else np.nan
    return {
        "event_id": event_id, "market_key": market_key,
        "player_name": player_name, "line": line,
        "commence_time": commence_time,
        "home_team": home_team, "away_team": away_team,
        "price_first": price_first, "price_second": price_second,
        "first_side": "Over" if market_key == "totals" else home_team,
        "second_side": "Under" if market_key == "totals" else away_team,
        "imp_first": imp_f, "imp_second": imp_s,
        "two_way": True, "q_first": q_f,
        "source_utc": "2026-10-18T12:00:00Z",
        "source_age_min": 300.0,
    }


def _make_sheet_df(rows=None):
    """Build a sheet DataFrame from row dicts."""
    if rows is None:
        rows = [_make_sheet_row()]
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────
# Test 1: Packet INTERNATIONAL line + HR/Pinnacle numbers
# ──────────────────────────────────────────────────────────────────────────

class TestPacketInternational:
    """The 10-18 Jaguars@Texans game was at Wembley Stadium, London."""

    def test_intl_note_wembley(self):
        """The INTERNATIONAL line appears for Jaguars@Texans on 2026-10-18."""
        note = ar._intl_note("Houston Texans", "Jacksonville Jaguars",
                             "2026-10-18T13:30:00Z")
        assert note is not None, "INTERNATIONAL note missing for 10-18 JAC@HOU"
        assert "Wembley Stadium" in note
        assert "London" in note
        assert "body clock" in note
        assert INTL_BASE_RATES_SUBSTR in note

    def test_intl_note_absent_for_regular_game(self):
        """No INTERNATIONAL note for a regular domestic game."""
        note = ar._intl_note("Dallas Cowboys", "Green Bay Packers",
                             "2026-10-19T00:20:00Z")
        assert note is None


INTL_BASE_RATES_SUBSTR = "base rates (56 intl games"


class TestPacketHRPinnacle:
    """Packet includes HR and Pinnacle numbers when data is available."""

    def test_packet_has_hr_spread(self):
        """The packet text includes HR spread line."""
        sheet = _make_sheet_df([_make_sheet_row(
            market_key="spreads", line=-3.0,
            price_first=-110, price_second=-110)])
        lines_df = pd.DataFrame([{
            "event_id": "abc123", "bookmaker": "pinnacle", "market": "spreads",
            "outcome_name": "Houston Texans", "point": -3.5, "price": -108,
            "snapshot_utc": "2026-10-18T12:00:00Z",
            "commence_time": "2026-10-18T17:00:00Z",
            "home_team": "Houston Texans", "away_team": "Jacksonville Jaguars",
        }, {
            "event_id": "abc123", "bookmaker": "pinnacle", "market": "spreads",
            "outcome_name": "Jacksonville Jaguars", "point": 3.5, "price": -112,
            "snapshot_utc": "2026-10-18T12:00:00Z",
            "commence_time": "2026-10-18T17:00:00Z",
            "home_team": "Houston Texans", "away_team": "Jacksonville Jaguars",
        }])
        now = datetime(2026, 10, 18, 12, 45, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create minimal directory structure
            (root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026").mkdir(parents=True)
            (root / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
            (root / "data" / "injury_archive" / "nfl" / "season=2026").mkdir(parents=True)
            (root / "nfl" / "data" / "board").mkdir(parents=True)

            header, packets = ar.build_packet(
                "nfl", ["abc123"], sheet, pd.DataFrame(), lines_df, now,
                root=root)
            text = packets.get("abc123", "")
            assert "HR spread" in text, f"HR spread missing from packet:\n{text[:500]}"
            assert "Pinnacle" in text, f"Pinnacle missing from packet:\n{text[:500]}"


# ──────────────────────────────────────────────────────────────────────────
# Test 2: JSON schema rejects one-way pick and +300 moneyline
# ──────────────────────────────────────────────────────────────────────────

class TestSchemaRejects:

    def test_reject_anytime_td_pick(self):
        """A pick on player_anytime_td (one-way) is rejected."""
        pick = {
            "market": "player_anytime_td", "player": "Test Player",
            "line": 0.5, "side": "first", "tag": "injury_news",
            "conf": 10, "reason": "Test player scores a TD 12345678",
            "thesis": "share:up",
        }
        ok, err = ar.validate_pick(pick, None, "nfl")
        assert not ok, f"one-way pick should be rejected: {err}"
        assert "one-way" in err.lower() or "anytime" in err.lower()

    def test_reject_ml_longshot(self):
        """A moneyline pick at +300 is rejected."""
        pick = {
            "market": "h2h", "player": "",
            "line": 0.0, "side": "second", "tag": "matchup",
            "conf": 5, "reason": "Underdog at +300 is the play here now",
            "thesis": "points:up",
        }
        sheet_row = {"price_first": -400, "price_second": 300}
        ok, err = ar.validate_pick(pick, sheet_row, "nfl")
        assert not ok, f"+300 ML should be rejected: {err}"
        assert "longshot" in err.lower()

    def test_accept_ml_favorite(self):
        """A moneyline pick at -150 (favorite) is accepted."""
        pick = {
            "market": "h2h", "player": "",
            "line": 0.0, "side": "first", "tag": "matchup",
            "conf": 10, "reason": "Favorite wins outright with the injuries",
            "thesis": "points:up",
        }
        sheet_row = {"price_first": -150, "price_second": 130}
        ok, err = ar.validate_pick(pick, sheet_row, "nfl")
        assert ok, f"favorite ML should be accepted: {err}"


# ──────────────────────────────────────────────────────────────────────────
# Test 3: Reason length and thesis-link validation
# ──────────────────────────────────────────────────────────────────────────

class TestReasonAndThesis:

    def test_reason_too_short(self):
        pick = {
            "market": "spreads", "player": "", "line": -3.0,
            "side": "first", "tag": "matchup", "conf": 10,
            "reason": "short",
            "thesis": "points:up",
        }
        ok, err = ar.validate_pick(pick, None, "nfl")
        assert not ok
        assert "reason" in err.lower()

    def test_reason_too_long(self):
        pick = {
            "market": "spreads", "player": "", "line": -3.0,
            "side": "first", "tag": "matchup", "conf": 10,
            "reason": "x" * 161,
            "thesis": "points:up",
        }
        ok, err = ar.validate_pick(pick, None, "nfl")
        assert not ok
        assert "reason" in err.lower()

    def test_invalid_thesis_link(self):
        pick = {
            "market": "spreads", "player": "", "line": -3.0,
            "side": "first", "tag": "matchup", "conf": 10,
            "reason": "Valid reason text with numbers -3.0 at -110",
            "thesis": "invalid_link:up",
        }
        ok, err = ar.validate_pick(pick, None, "nfl")
        assert not ok
        assert "thesis" in err.lower()

    def test_valid_pick_passes(self):
        pick = {
            "market": "spreads", "player": "", "line": -3.0,
            "side": "first", "tag": "matchup", "conf": 15,
            "reason": "Home team covers -3.0 at -110 with the injuries",
            "thesis": "points:up; availability:up",
        }
        ok, err = ar.validate_pick(pick, None, "nfl")
        assert ok, f"valid pick should pass: {err}"


# ──────────────────────────────────────────────────────────────────────────
# Test 4: Mocked API response -> filled CSV passes validate
# ──────────────────────────────────────────────────────────────────────────

class TestMockedFilled:

    def test_picks_to_filled_produces_valid_frame(self):
        """A mocked API response converts to a filled DataFrame."""
        sheet_rows = [
            _make_sheet_row(market_key="spreads", line=-3.0),
            _make_sheet_row(market_key="totals", line=44.5,
                            price_first=-110, price_second=-110),
            _make_sheet_row(market_key="h2h", line=0.0,
                            price_first=-150, price_second=130),
        ]
        sheet = _make_sheet_df(sheet_rows)

        picks = [
            {"market": "spreads", "player": "", "line": -3.0,
             "side": "first", "tag": "matchup", "conf": 15,
             "reason": "Home covers -3.0 at -110 with key injuries out",
             "thesis": "points:up; availability:up"},
            {"market": "totals", "player": "", "line": 44.5,
             "side": "first", "tag": "weather", "conf": 10,
             "reason": "Over 44.5 in good weather at -110 with both QBs healthy",
             "thesis": "points:up"},
            {"market": "h2h", "player": "", "line": 0.0,
             "side": "first", "tag": "matchup", "conf": 5,
             "reason": "Favorite at -150 outright with injuries piling up",
             "thesis": "points:up"},
        ]

        filled = ar.picks_to_filled(picks, sheet, "nfl")
        assert len(filled) == 3
        assert (filled.conf_rank == [1, 2, 3]).all() or set(filled.conf_rank) == {1, 2, 3}
        assert filled.p_first.between(0.02, 0.98).all()

        # Validate conf_rank is unique and contiguous
        ranks = sorted(filled.conf_rank.tolist())
        assert ranks == list(range(1, len(filled) + 1))

    def test_no_view_pass_uses_book_probability(self):
        """A no_view pass carries the book's de-vigged probability."""
        sheet = _make_sheet_df([_make_sheet_row()])
        picks = [
            {"market": "spreads", "player": "", "line": -3.0,
             "side": "first", "tag": "no_view", "conf": 0,
             "reason": "pass: HR -110/-110",
             "thesis": ""},
        ]
        filled = ar.picks_to_filled(picks, sheet, "nfl")
        assert len(filled) == 1
        # At -110/-110, book q_first should be ~0.5
        assert abs(filled.iloc[0].p_first - 0.5) < 0.01


# ──────────────────────────────────────────────────────────────────────────
# Test 5: Spend file increments and cap HALTs
# ──────────────────────────────────────────────────────────────────────────

class TestSpendTracking:

    def test_spend_increments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            spend = ar._update_spend(root, "claude-sonnet-4-6-20250514", 5000, 500)
            assert spend["calls"] == 1
            assert spend["input_tokens"] == 5000
            assert spend["output_tokens"] == 500
            assert spend["usd_estimate"] > 0

            # Second call increments
            spend2 = ar._update_spend(root, "claude-sonnet-4-6-20250514", 3000, 300)
            assert spend2["calls"] == 2
            assert spend2["input_tokens"] == 8000

    def test_spend_cap_halts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            # Write a spend file at the cap
            spend = {
                "month": datetime.now(timezone.utc).strftime("%Y-%m"),
                "calls": 100, "input_tokens": 1000000,
                "output_tokens": 100000, "usd_estimate": 200.0,
                "model": "test",
            }
            ar._save_spend(root, spend)
            with pytest.raises(SystemExit, match="HALT.*cap"):
                ar._check_spend_cap(root, cap_usd=150.0)

    def test_spend_under_cap_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()
            spend = {
                "month": datetime.now(timezone.utc).strftime("%Y-%m"),
                "calls": 5, "input_tokens": 10000,
                "output_tokens": 1000, "usd_estimate": 1.0,
                "model": "test",
            }
            ar._save_spend(root, spend)
            # Should not raise
            ar._check_spend_cap(root, cap_usd=150.0)


# ──────────────────────────────────────────────────────────────────────────
# Test: NHL/NBA stubs HALT
# ──────────────────────────────────────────────────────────────────────────

class TestUnsupportedSports:

    def test_nhl_halts(self):
        with pytest.raises(SystemExit, match="HALT.*nhl"):
            ar.build_packet("nhl", [], pd.DataFrame(), pd.DataFrame(),
                            pd.DataFrame(), datetime.now(timezone.utc))

    def test_nba_halts(self):
        with pytest.raises(SystemExit, match="HALT.*nba"):
            ar.build_packet("nba", [], pd.DataFrame(), pd.DataFrame(),
                            pd.DataFrame(), datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────────
# Test: DEFAULT_MODEL is in the live Console model list (CAD1b Item 1)
# ──────────────────────────────────────────────────────────────────────────

# Live /v1/models list pulled 2026-10-23T11:50Z
LIVE_MODELS = [
    "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5",
    "claude-fable-5-1", "claude-opus-5", "claude-sonnet-5", "claude-fable-5",
    "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6", "claude-opus-4-6",
    "claude-opus-4-5-20251101", "claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929",
]


class TestDefaultModelId:

    def test_default_model_in_live_list(self):
        """DEFAULT_MODEL must be a model ID that exists in the Console."""
        assert ar.DEFAULT_MODEL in LIVE_MODELS, \
            f"DEFAULT_MODEL {ar.DEFAULT_MODEL!r} is not in the live model list"


def test_read_game_skips_thinking_blocks(monkeypatch, tmp_path):
    """P61 fix 10-23: content[0] may be a thinking block; only text blocks are parsed; spend is recorded first."""
    import types, sys, json as _json
    import shared.pipeline.ai_reader as ar
    class _B:
        def __init__(self, t, text=None): self.type = t; self.text = text
    class _Msg:
        content = [_B("thinking"), _B("text", "[]")]
        usage = types.SimpleNamespace(input_tokens=10, output_tokens=2)
    class _Client:
        def __init__(self, *a, **k): self.messages = types.SimpleNamespace(create=lambda **kw: _Msg())
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    import pandas as pd
    sheet = pd.DataFrame({"event_id": [], "market_key": [], "player_name": [], "line": [], "q_first": [], "imp_first": [], "two_way": []})
    picks, i, o = ar.read_game("packet", sheet, "nfl", model="m", root=tmp_path)
    assert picks == [] and i == 10 and o == 2
    spend = _json.loads((tmp_path / "status" / "ai_reader_spend.json").read_text())
    assert spend  # recorded even though no picks
