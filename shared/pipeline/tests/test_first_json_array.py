"""P74 (RED first): trailing text after the picks array must not fail the parse."""
import json
import pandas as pd
import pytest
from shared.pipeline import ai_reader as ar

SHEET = pd.DataFrame([{"event_id": "e1", "market_key": "spreads", "player_name": "", "line": -3.5,
                       "side": "Saints", "price": -110}])
ARRAY = '[{"market": "spreads", "player": "", "line": -3.5, "side": "Saints", "conf": 60, "thesis": "points:home"}]'


def test_trailing_text_after_array_parses():
    content = ARRAY + "\n\nNotes:\n- the Paris crowd favours the Saints\n"
    picks = ar._parse_response(content, SHEET, "nfl")
    assert isinstance(picks, list) and picks and picks[0]["line"] == -3.5


def test_second_array_after_first_is_ignored():
    content = ARRAY + "\n[]"
    picks = ar._parse_response(content, SHEET, "nfl")
    assert len(picks) == 1


def test_no_array_still_raises_for_retry():
    with pytest.raises(json.JSONDecodeError):
        ar._parse_response("I cannot form a view on this game.", SHEET, "nfl")


def test_first_json_array_helper():
    assert ar._first_json_array("prefix [1, 2] suffix [3]") == [1, 2]
    assert ar._first_json_array("[not json") is None
