"""CAD3e tests (RED first)."""
import pandas as pd
import pytest
from shared.pipeline import ai_reader as ar

SHEET = pd.DataFrame([
    {"event_id": "e1", "market_key": "player_rush_attempts", "player_name": "A Back", "line": 14.5, "first_side": "Over", "second_side": "Under",
     "price_first": -110, "price_second": -110, "imp_first": 0.52, "imp_second": 0.52, "home_team": "H", "away_team": "A"},
])


def _pick(thesis):
    return [{"market": "player_rush_attempts", "player": "A Back", "line": 14.5, "side": "first", "conf": 40, "tag": "usage_trend",
             "reason": "twenty carries last week as the lead back in a close game", "thesis": thesis}]


def test_rush_alias_becomes_run_rate():
    df = ar.picks_to_filled(_pick("rush:up"), SHEET, "nfl", event_id="e1")
    th = df.loc[df.player_name == "A Back", "thesis"].iloc[0]
    assert th == "run_rate:up"


def test_unknown_claim_is_dropped_not_halted():
    df = ar.picks_to_filled(_pick("vibes:up; share:up"), SHEET, "nfl", event_id="e1")
    assert df.loc[df.player_name == "A Back", "thesis"].iloc[0] == "share:up"


def test_all_unknown_falls_back_to_market_link():
    df = ar.picks_to_filled(_pick("vibes:sideways"), SHEET, "nfl", event_id="e1")
    assert df.loc[df.player_name == "A Back", "thesis"].iloc[0] == "efficiency:up"


def test_failure_line_names_layer_and_only_latest(tmp_path):
    from pathlib import Path
    src = (Path(ar.__file__).resolve().parents[2] / "site" / "picks_data.py").read_text()
    assert "the AI reads on the cards are unaffected" in src
    assert "latest[(sp, layer)]" in src
