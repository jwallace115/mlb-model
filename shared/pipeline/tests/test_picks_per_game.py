#!/usr/bin/env python3
"""Tests for OPS-CAD2 Item 1 — picks belong to one game (P67).

RED-first:
  1. Two games both quoting spreads -10.5; pick for game A → only game A's row.
  2. Pick naming unquoted line for the event → HALT for that game only.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
import ai_reader as ar


def _row(eid, mk="spreads", player="", line=-10.5, pf=-110, ps=-110):
    imp_f = ar._implied(pf)
    imp_s = ar._implied(ps)
    return {
        "event_id": eid, "market_key": mk, "player_name": player, "line": line,
        "commence_time": "2026-10-26T17:00:00Z",
        "home_team": "H", "away_team": "A",
        "price_first": pf, "price_second": ps,
        "first_side": "H", "second_side": "A",
        "imp_first": imp_f, "imp_second": imp_s,
        "two_way": True, "q_first": imp_f / (imp_f + imp_s),
        "source_utc": "2026-10-23T12:00:00Z", "source_age_min": 60,
    }


class TestPicksPerGame:

    def test_pick_goes_to_correct_game_only(self):
        """A pick for game A must NOT land on game B even if (market, line) match."""
        sheet = pd.DataFrame([_row("gameA"), _row("gameB")])
        picks = [{"market": "spreads", "player": "", "line": -10.5,
                  "side": "first", "tag": "matchup", "conf": 15,
                  "reason": "Home covers -10.5 at -110 with key injuries",
                  "thesis": "points:up"}]

        # P67: with event_id, only game A's row gets the pick
        filled = ar.picks_to_filled(picks, sheet, "nfl", event_id="gameA")
        view_rows = filled[filled.tag != "no_view"]
        assert len(view_rows) == 1, f"expected 1 view row, got {len(view_rows)}"
        assert view_rows.iloc[0].event_id == "gameA"

        # Game B should be all no_view
        filled_b = ar.picks_to_filled([], sheet, "nfl", event_id="gameB")
        assert (filled_b.tag == "no_view").all()

    def test_unquoted_line_halts_game(self):
        """A pick naming a line not quoted for the event → HALT."""
        sheet = pd.DataFrame([_row("gameA", line=-3.0)])
        picks = [{"market": "spreads", "player": "", "line": -10.5,
                  "side": "first", "tag": "matchup", "conf": 15,
                  "reason": "Home covers -10.5 at -110 with key injuries",
                  "thesis": "points:up"}]

        with pytest.raises(SystemExit, match="HALT.*unquoted"):
            ar.picks_to_filled(picks, sheet, "nfl", event_id="gameA")

    def test_reader_version_is_v1b(self):
        """Reader model string is now ai_reader_v1b."""
        assert "v1b" in f"ai_reader_v1b/{ar.DEFAULT_MODEL}"


def test_spread_sign_normalised_and_side_flipped():
    """10-23 live: the model echoed +2.5 for a quoted -2.5 spread; same contract, other side."""
    import pandas as pd
    from shared.pipeline.ai_reader import picks_to_filled
    sheet = pd.DataFrame([{"event_id": "e1", "market_key": "spreads", "player_name": "", "line": -2.5,
                           "q_first": 0.5, "imp_first": 0.52, "two_way": True, "price_first": -110, "price_second": -110,
                           "first_side": "Home", "second_side": "Away", "home_team": "Home X", "away_team": "Away Y"}])
    picks = [{"market": "spreads", "player": "", "line": 2.5, "side": "first", "tag": "matchup", "conf": 10,
              "reason": "Away +2.5 is the number, twelve chars plus.", "thesis": "points:up"}]
    f = picks_to_filled(picks, sheet, "ncaaf", event_id="e1")
    row = f.iloc[0]
    assert float(row.line) == -2.5 and row.tag != "no_view"
    assert row.p_first < 0.5  # the away side -> p_first below the home no-vig
