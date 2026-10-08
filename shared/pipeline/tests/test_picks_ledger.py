"""Gate tests for picks_ledger.py — RED first, then GREEN."""
import json, os, sys, pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import picks_ledger as pl


def _base_row(**kw):
    r = dict(
        ticket_id="test_t1", owner="jeff", source="ai_opinion", logged_utc="2026-09-28T12:00:00Z",
        sport="NFL", event_id="a" * 32, commence_time="2026-09-28T17:00:00Z",
        home="Team A", away="Team B", market="spread", player_id=None, player_name=None,
        side="Team A", point=-3.5, price_american=-110, book="hardrockbet_fl", reason="test",
        share_link=None, supersedes=None, result=None, graded_utc=None, result_source=None,
        source_file="test.json", source_row=0,
    )
    r.update(kw)
    return r


MEMBERS = {"jeff"}


# (a) null event_id HALTs
def test_null_event_id_halts():
    with pytest.raises(pl.Halt, match="event_id"):
        pl.admit([_base_row(event_id=None)], MEMBERS)


# (b) blank/whitespace side HALTs
def test_blank_side_halts():
    with pytest.raises(pl.Halt, match="side"):
        pl.admit([_base_row(side="   ")], MEMBERS)


# (c) logged_utc >= commence_time HALTs
def test_logged_after_commence_halts():
    with pytest.raises(pl.Halt, match="logged_utc.*commence"):
        pl.admit([_base_row(logged_utc="2026-09-28T18:00:00Z")], MEMBERS)


# (d) team-name-only row with no event_id HALTs
def test_team_name_no_event_id_halts():
    with pytest.raises(pl.Halt, match="event_id"):
        pl.admit([_base_row(event_id="")], MEMBERS)


# (e) owner not in members HALTs
def test_unknown_owner_halts():
    with pytest.raises(pl.Halt, match="owner"):
        pl.admit([_base_row(owner="stranger")], MEMBERS)


# (f) append twice → second call appends 0
def test_append_idempotent(tmp_path):
    rows = [_base_row()]
    pl.admit(rows, MEMBERS)
    a1, s1 = pl.append(rows, tmp_path)
    assert a1 == 1 and s1 == 0
    a2, s2 = pl.append(rows, tmp_path)
    assert a2 == 0 and s2 == 1


# (g) supersedes row replaces its target in view()
def test_supersedes_replaces(tmp_path):
    r1 = _base_row(pick_id="orig_001")
    r2 = _base_row(pick_id="corr_001", supersedes="orig_001",
                    ingested_utc="2026-09-29T00:00:00Z")
    pl.append([r1, r2], tmp_path)
    v = pl.view(tmp_path)
    ids = {r["pick_id"] for r in v}
    assert "orig_001" not in ids
    assert "corr_001" in ids


# (h) fuzz: each of these on a LATER row of an otherwise valid batch HALTs
@pytest.mark.parametrize("field,val", [
    ("owner", None),
    ("owner", float("nan")),
    ("side", "<NA>"),
    ("side", ""),
    ("side", "  "),
    ("source", "WRONG_CASE"),
    ("event_id", "12345"),  # not 32 hex
    ("price_american", "not_a_number"),
])
def test_fuzz_halts(field, val):
    good = _base_row()
    bad = _base_row(**{field: val})
    bad["source_row"] = 1
    with pytest.raises(pl.Halt):
        pl.admit([good, bad], MEMBERS)


# Null control: a valid 3-row batch appends 3 and view() returns 3
def test_null_control_valid_batch(tmp_path):
    (tmp_path / "members.json").write_text('{"members":["jeff"]}')
    rows = [_base_row(event_id="a" * 32, ticket_id=f"t{i}", side=f"Team{i}") for i in range(3)]
    pl.admit(rows, MEMBERS)
    appended, skipped = pl.append(rows, tmp_path)
    assert appended == 3
    v = pl.view(tmp_path)
    assert len(v) == 3


# ---- OPS2b Item 2 tests ----

# (i) tag and conf columns are in the contract
def test_tag_conf_in_cols():
    assert "tag" in pl.COLS
    assert "conf" in pl.COLS


# (j) row with tag and conf admits and roundtrips
def test_tag_conf_roundtrip(tmp_path):
    row = _base_row(tag="injury_news", conf=72.5)
    pl.admit([row], MEMBERS)
    appended, _ = pl.append([row], tmp_path)
    assert appended == 1
    v = pl.view(tmp_path)
    assert v[0]["tag"] == "injury_news"
    assert v[0]["conf"] == 72.5


# (k) row without tag/conf gets null defaults
def test_tag_conf_defaults(tmp_path):
    row = _base_row()
    pl.admit([row], MEMBERS)
    appended, _ = pl.append([row], tmp_path)
    assert appended == 1
    v = pl.view(tmp_path)
    assert v[0].get("tag") is None
    assert v[0].get("conf") is None
