"""N50: a FINAL ticket cannot be logged without the reader's own reason on every leg, and the
message Jeff gets shows leg / game / reason. Runs the production logger on the N43 fixtures."""
import json
import pytest
from nfl.pipeline import build_nfl_slate as S
from nfl.pipeline.tests.test_nfl_slate_n46 import _build, SPECS


def _setup(tmp_path):
    cand, meta = _build(tmp_path)
    log = tmp_path / "log.json"; log.write_text("[]")
    hands = S.log_rule_tickets(log, cand, meta, "s1", specs=SPECS)
    spec = SPECS[0]
    keys = [(r["event_id"], r["player_name"], r["market_key"]) for r in hands[spec["ticket_id"]]]
    base = {k: {"availability_source": "inactives", "checked_at": "2026-09-20T15:40Z"} for k in keys}
    reader = {"model": "test", "inputs": ["x"], "raw_output": "y"}
    return cand, meta, log, spec, keys, base, reader


def _with(base, reasons):
    return {k: {**v, "ai_reason": reasons[i]} for i, (k, v) in enumerate(base.items()) if reasons[i] is not None} | \
           {k: v for i, (k, v) in enumerate(base.items()) if reasons[i] is None}


def test_missing_short_boilerplate_and_sure_thing_reasons_are_refused(tmp_path):
    cand, meta, log, spec, keys, base, reader = _setup(tmp_path)
    good = [f"{k[1]} led the team in week-1 volume and is active today" for k in keys]
    args = (log, cand, meta, "s1", spec, keys, {})
    with pytest.raises(RuntimeError, match="needs an ai_reason"):
        S.log_final_slate_ticket(*args, _with(base, [None] + good[1:]), reader)
    with pytest.raises(RuntimeError, match="needs an ai_reason"):
        S.log_final_slate_ticket(*args, _with(base, ["lead back"] + good[1:]), reader)
    with pytest.raises(RuntimeError, match="sure-thing language"):
        S.log_final_slate_ticket(*args, _with(base, ["This one is a lock, he always clears it"] + good[1:]), reader)
    if len(keys) >= 3:
        with pytest.raises(RuntimeError, match="same ai_reason"):
            S.log_final_slate_ticket(*args, _with(base, ["Lead role and active, line unchanged"] * len(keys)), reader)
    assert json.loads(log.read_text())[-1]["kind"] != "slate_final"      # nothing was appended


def test_reasons_are_logged_and_shown_with_leg_and_game(tmp_path):
    cand, meta, log, spec, keys, base, reader = _setup(tmp_path)
    good = [f"{k[1]} led the team in week-1 volume and is active today" for k in keys]
    n, entry = S.log_final_slate_ticket(log, cand, meta, "s1", spec, keys, {}, _with(base, good), reader)
    saved = json.loads(log.read_text())[-1]
    assert [x["ai_reason"] for x in saved["leg_notes"]] == good
    md = S.final_ticket_markdown(saved)
    for k, leg in zip(keys, saved["legs"]):
        assert k[1] in md and f"{leg['away_team']} @ {leg['home_team']}" in md
    assert all(g in md for g in good) and "NO REASON LOGGED" not in md
    assert "not a claim of edge" in md
