"""Gate tests for picks_intake.py — RED first, then GREEN."""
import json, os, sys, pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_fixture(tmp_path, legs, **kw):
    """Write a confirmed intake JSON file."""
    confirmed = tmp_path / "inbox_confirmed"
    confirmed.mkdir(exist_ok=True)
    d = {
        "owner": kw.get("owner", "m_alpha"),
        "source": "member_share",
        "book": "hardrockbet",
        "logged_utc": kw.get("logged_utc", "2026-09-28T12:00:00Z"),
        "share_link": kw.get("share_link", "SHARELINK_SENTINEL"),
        "legs": legs,
        "unreadable": [],
        "confirmed_by": kw.get("confirmed_by", "jeff"),
        "confirmed_utc": kw.get("confirmed_utc", "2026-09-28T13:00:00Z"),
    }
    d.update({k: v for k, v in kw.items() if k not in d})
    f = confirmed / "test_fixture.json"
    f.write_text(json.dumps(d))
    return f


def _make_ledger(tmp_path, members=None):
    """Set up a ledger dir with members.json and a tape stub."""
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    m = members or ["m_alpha", "m_beta", "jeff"]
    (ledger / "members.json").write_text(json.dumps({"members": m}))
    return ledger


def _valid_leg():
    return {
        "sport": "NFL",
        "home": "Miami Dolphins",
        "away": "Kansas City Chiefs",
        "commence_time": "2026-09-28T17:00:00Z",
        "market": "spread",
        "player_name": None,
        "side": "Miami Dolphins",
        "point": -3.5,
        "price_american": -110,
    }


# (a) file with one UNREADABLE leg is rejected whole
def test_unreadable_leg_rejects_whole(tmp_path):
    import picks_intake as pi
    ledger = _make_ledger(tmp_path)
    leg = _valid_leg()
    leg["side"] = "UNREADABLE"
    _make_fixture(tmp_path, [leg])
    result = pi.process_inbox(tmp_path / "inbox_confirmed", ledger,
                               resolve_fn=lambda *a, **k: ("a" * 32, "2026-09-28T17:00:00Z"))
    assert result["rejected_files"] == 1
    assert result["appended"] == 0


# (b) missing confirmed_utc rejected
def test_missing_confirmed_utc_rejected(tmp_path):
    import picks_intake as pi
    ledger = _make_ledger(tmp_path)
    _make_fixture(tmp_path, [_valid_leg()], confirmed_utc=None)
    # Patch the file to remove confirmed_utc
    f = tmp_path / "inbox_confirmed" / "test_fixture.json"
    d = json.loads(f.read_text())
    del d["confirmed_utc"]
    f.write_text(json.dumps(d))
    result = pi.process_inbox(tmp_path / "inbox_confirmed", ledger,
                               resolve_fn=lambda *a, **k: ("a" * 32, "2026-09-28T17:00:00Z"))
    assert result["rejected_files"] == 1


# (c) logged_utc after commence rejected
def test_logged_after_commence_rejected(tmp_path):
    import picks_intake as pi
    ledger = _make_ledger(tmp_path)
    _make_fixture(tmp_path, [_valid_leg()], logged_utc="2026-09-28T18:00:00Z")
    result = pi.process_inbox(tmp_path / "inbox_confirmed", ledger,
                               resolve_fn=lambda *a, **k: ("a" * 32, "2026-09-28T17:00:00Z"))
    assert result["rejected_files"] == 1


# (d) leg matching two tape events HALTs
def test_ambiguous_tape_halts(tmp_path):
    import picks_intake as pi
    ledger = _make_ledger(tmp_path)
    _make_fixture(tmp_path, [_valid_leg()])

    def ambig_resolve(*a, **k):
        from picks_ledger import Halt
        raise Halt("multiple event_ids")

    with pytest.raises(Exception, match="multiple"):
        pi.process_inbox(tmp_path / "inbox_confirmed", ledger, resolve_fn=ambig_resolve)


# (e) null control: valid 2-leg fixture appends 2 rows, file moves to done/
def test_valid_fixture_appends_and_moves(tmp_path):
    import picks_intake as pi
    ledger = _make_ledger(tmp_path)
    leg1 = _valid_leg()
    leg2 = _valid_leg()
    leg2["side"] = "Kansas City Chiefs"
    leg2["point"] = 3.5
    _make_fixture(tmp_path, [leg1, leg2], share_link="SHARELINK_SENTINEL")
    result = pi.process_inbox(tmp_path / "inbox_confirmed", ledger,
                               resolve_fn=lambda *a, **k: ("a" * 32, "2026-09-28T17:00:00Z"))
    assert result["appended"] == 2
    assert result["rejected_files"] == 0
    # File moved to done/
    assert not (tmp_path / "inbox_confirmed" / "test_fixture.json").exists()
    assert (tmp_path / "inbox_confirmed" / "done" / "test_fixture.json").exists()


# (f) module source contains no requests/httpx/urlopen
def test_no_network_imports():
    src = Path(__file__).resolve().parent.parent / "picks_intake.py"
    text = src.read_text()
    for pat in ("requests", "httpx", "urlopen"):
        assert pat not in text, f"picks_intake.py contains '{pat}'"
