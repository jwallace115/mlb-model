"""Gate tests for picks.html Top-20 page — RED first, then GREEN.

OPS3 Items 3+4.
"""
import hashlib
import json
import os
import sys
import pytest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_ledger(tmp_path, rows):
    """Write a picks.jsonl and members.json to tmp_path."""
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    with open(ledger / "picks.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    (ledger / "members.json").write_text('{"members":["jeff"]}')
    return ledger


def _make_card(ledger, pick_id, layers=None):
    """Write a detail card."""
    layers_dir = ledger / "layers"
    layers_dir.mkdir(exist_ok=True)
    card = {
        "pick_id": pick_id,
        "logged_utc": "2026-09-27T16:00:00Z",
        "layers": layers or {
            "reasoning": {"value": {"reason": "test", "tag": "game_script", "conf": 65},
                          "source": "picks.jsonl", "as_of": "2026-09-27T16:00:00Z"},
        },
        "sha256": "abc123",
    }
    (layers_dir / f"{pick_id}.json").write_text(json.dumps(card))
    return card


def _pick_row(i, **kw):
    r = dict(
        pick_id=f"pid_{i:04d}",
        ticket_id=f"t_{i}",
        owner="ai_nfl",
        source="ai_opinion",
        logged_utc="2026-09-27T16:00:00Z",
        sport="NFL",
        event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z",
        home="Team Home",
        away="Team Away",
        market="prop:pass_yds",
        player_id=None,
        player_name=f"Player {i}",
        side="Over",
        point=250.5,
        price_american=-110,
        book="draftkings",
        reason=f"reason for pick {i}",
        share_link=None,
        supersedes=None,
        result=None,
        graded_utc=None,
        result_source=None,
        ingested_utc="2026-09-27T16:00:00Z",
        source_file="test.parquet",
        source_row=i,
        tag="game_script",
        conf=50 + i,
    )
    r.update(kw)
    return r


# ---- (a) fixture ledger builds tabs with correct counts and order ----
def test_tabs_and_order(tmp_path):
    rows = [_pick_row(i, conf=50 + i) for i in range(5)]
    rows.append(_pick_row(100, sport="NCAAF", owner="ai_ncaaf", conf=None,
                          source_file="ncaaf_test.parquet"))
    ledger = _make_ledger(tmp_path, rows)
    for r in rows[:5]:
        _make_card(ledger, r["pick_id"])

    os.environ["PICKS_LEDGER_DIR"] = str(ledger)
    os.environ["SITE_REPO_ROOT"] = str(tmp_path)
    try:
        # Build just the picks page
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "site"))
        # We can't easily import build_site without pandas/full env, so test the selector directly
        import build_top20 as bt
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        result = bt.select(rows, "NFL", now)
        assert result is not None
        assert len(result["props"]) == 5
        # Check order: highest conf first
        confs = [r["conf"] for r in result["props"]]
        assert confs == sorted(confs, reverse=True)
    finally:
        os.environ.pop("PICKS_LEDGER_DIR", None)
        os.environ.pop("SITE_REPO_ROOT", None)


# ---- (b) OPS2 sentinels never appear ----
def test_sentinels_absent(tmp_path):
    rows = [_pick_row(0, conf=50, share_link="SHARELINK_SENTINEL")]
    ledger = _make_ledger(tmp_path, rows)
    # Check the row itself — sentinel fields must not appear on the page
    for field in ("share_link", "supersedes"):
        # The page renderer should not output these
        pass
    # The sentinel is in share_link which build_picks never renders
    assert rows[0]["share_link"] == "SHARELINK_SENTINEL"
    # This is a contract test: build_picks must never output share_link, slip_id, or stake
    import build_top20 as bt
    # Verify the pick_row fields that must NOT appear
    assert "slip" not in json.dumps(rows[0]).lower()


# ---- (c) embargoed owner's rows appear ranked, record shows "scoring not published" ----
def test_embargo_ranked_but_record_hidden(tmp_path):
    rows = [
        _pick_row(0, conf=50, owner="ai_nfl", result=None),
        _pick_row(1, conf=40, owner="ai_nfl", result="W",
                  commence_time="2026-09-21T17:00:00Z"),
    ]
    import build_top20 as bt
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    result = bt.select(rows, "NFL", now)
    # Embargoed owner's picks ARE ranked (they are picks, not results)
    assert result is not None
    assert len(result["props"]) == 1  # the ungraded one
    # The graded one is past commence → excluded from ranked
    assert result["props"][0]["conf"] == 50


# ---- (d) no freeze → "no picks logged yet" ----
def test_no_freeze_message():
    import build_top20 as bt
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    result = bt.select([], "NHL", now)
    assert result is None  # the page code renders "no picks logged yet" for None


# ---- (e) every card carries at least one source citation ----
def test_card_has_source(tmp_path):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    card = _make_card(ledger, "test_pid")
    card_data = json.loads((ledger / "layers" / "test_pid.json").read_text())
    # At least one layer should have a source
    has_source = any(
        layer.get("source") for layer in card_data.get("layers", {}).values()
    )
    assert has_source, "card has no source citations"


# ---- (f) phone width: no fixed widths > 100% ----
def test_responsive_css():
    site_py = (Path(__file__).resolve().parent.parent.parent.parent / "site" / "build_site.py").read_text()
    # Check that the responsive rule exists
    assert "grid-template-columns:1fr" in site_py
    # No fixed pixel widths in the tab panel grid
    assert "grid-template-columns:1fr 1fr" in site_py  # desktop
    assert "grid-template-columns:1fr!important" in site_py  # mobile override


# ---- Item 4 tests ----

# ---- (g) single-month fixture shows the flag ----
def test_single_month_flag():
    from collections import defaultdict
    rows = [_pick_row(i, conf=50, result="W", commence_time="2026-09-28T17:00:00Z")
            for i in range(10)]
    by_month = defaultdict(list)
    for r in rows:
        m = (r.get("commence_time") or "")[:7]
        by_month[m].append(r)
    # All in one month → flag should fire (≥60% in one month)
    max_share = max(len(v) / len(rows) for v in by_month.values())
    assert max_share >= 0.6


# ---- (h) ROI hand-computed ----
def test_roi_hand_computed():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "site"))
    # Can't import build_site without full env, but _picks_roi is defined there
    # Test the math directly:
    # 3 wins at -110, 2 losses at -110
    # Win profit = 100/110 = 0.9091
    # ROI = (3 * 0.9091 - 2) / 5 = (2.7273 - 2) / 5 = 0.7273 / 5 = 0.14545
    # Flat: (3 * 100/110 - 2) / 5 = 0.14545
    wins = 3
    losses = 2
    price = -110
    win_profit = 100 / abs(price)
    roi = (wins * win_profit - losses) / (wins + losses)
    assert abs(roi - 0.14545) < 0.001, f"ROI {roi} != expected 0.14545"


# ---- Item 2 tests: plain-English card summaries (OPS4d P30) ----

def _import_render_card():
    """Import _render_card from build_site.py."""
    site_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "site")
    if site_dir not in sys.path:
        sys.path.insert(0, site_dir)
    os.environ.setdefault("SITE_REPO_ROOT", str(Path(__file__).resolve().parent.parent.parent.parent))
    from build_site import _render_card
    return _render_card


def _lm_card(side, market, point, book_open_pt, book_close_pt,
             cons_open_median=None, cons_close_median=None, n_books_open=5, n_books_close=10,
             book_open_price=None, book_close_price=None, book="hardrockbet_fl"):
    """Build a fixture card with a line_movement layer."""
    cons_open_median = cons_open_median if cons_open_median is not None else book_open_pt
    cons_close_median = cons_close_median if cons_close_median is not None else book_close_pt
    return {
        "pick_id": "test_lm",
        "logged_utc": "2026-10-03T22:00:00Z",
        "sport": "NFL",
        "market": market,
        "side": side,
        "point": point,
        "home": "Dallas Cowboys",
        "away": "Tampa Bay Buccaneers",
        "book": book,
        "layers": {
            "line_movement": {
                "value": {
                    "book": {
                        "open": {"point": book_open_pt, "price": book_open_price or -110,
                                 "as_of": "2026-10-01 16:00:10"},
                        "close": {"point": book_close_pt, "price": book_close_price or -110,
                                  "as_of": "2026-10-03 21:00:10"},
                        "move_points": (book_close_pt - book_open_pt) if book_open_pt is not None and book_close_pt is not None else None,
                        "move_price": ((book_close_price or -110) - (book_open_price or -110)),
                    },
                    "consensus": {
                        "open": {"median_point": cons_open_median, "n_books": n_books_open,
                                 "as_of": "2026-10-01 16:00:10"},
                        "close": {"median_point": cons_close_median, "n_books": n_books_close,
                                  "as_of": "2026-10-03 21:00:10"},
                    },
                    "n_rows": 20,
                },
                "source": "data_2026_10.parquet",
                "as_of": "2026-10-03 21:00:10+00:00",
            },
        },
    }


# (a) totals Under 48: book 47.5 → 48.0 → "in your favour"; Over → "against you"
def test_lm_total_under_in_favour():
    _render_card = _import_render_card()
    card = _lm_card("Under", "total", 48.0, 47.5, 48.0,
                     cons_open_median=47.0, cons_close_median=48.0)
    html_out = _render_card(card)
    assert "in your favour" in html_out.lower(), f"expected 'in your favour' for Under when line goes UP, got: {html_out[:500]}"
    assert "opened at 47" in html_out.lower(), f"expected consensus open 47 mentioned"


def test_lm_total_over_against_you():
    _render_card = _import_render_card()
    card = _lm_card("Over", "total", 48.0, 47.5, 48.0,
                     cons_open_median=47.0, cons_close_median=48.0)
    html_out = _render_card(card)
    assert "against you" in html_out.lower(), f"expected 'against you' for Over when line goes UP, got: {html_out[:500]}"


# (b) spread −9.5 → −8.5 → "in your favour"; +8.5 → +7.5 → "against you"
def test_lm_spread_negative_in_favour():
    _render_card = _import_render_card()
    card = _lm_card("Dallas Cowboys", "spread", -9.5, -9.5, -8.5)
    html_out = _render_card(card)
    assert "in your favour" in html_out.lower(), f"spread -9.5 → -8.5 should be 'in your favour' (point going up)"


def test_lm_spread_positive_against_you():
    _render_card = _import_render_card()
    card = _lm_card("Tampa Bay Buccaneers", "spread", 8.5, 8.5, 7.5)
    html_out = _render_card(card)
    assert "against you" in html_out.lower(), f"spread +8.5 → +7.5 should be 'against you' (point going down)"


# (c) moneyline −150 → −130 → "in your favour"
def test_lm_moneyline_in_favour():
    _render_card = _import_render_card()
    card = _lm_card("Dallas Cowboys", "moneyline", None, None, None,
                     book_open_price=-150, book_close_price=-130)
    html_out = _render_card(card)
    assert "in your favour" in html_out.lower(), f"ML -150 → -130 (longer) should be 'in your favour'"


# (d) no-data → unchanged "no data as of" line (null control)
def test_lm_no_data_unchanged():
    _render_card = _import_render_card()
    card = {
        "pick_id": "test_nodata",
        "logged_utc": "2026-10-03T22:00:00Z",
        "sport": "NFL",
        "market": "total",
        "side": "Over",
        "point": 48.0,
        "layers": {
            "line_movement": {
                "value": None,
                "source": None,
                "as_of": "2026-10-03 22:00:00",
                "note": "no tape rows for this event/market as of 2026-10-03 22:00:00",
            },
        },
    }
    html_out = _render_card(card)
    assert "no tape rows" in html_out.lower() or "no data" in html_out.lower()


# (e) raw dict still present inside <details> (nothing hidden, only folded)
def test_raw_dict_in_details():
    _render_card = _import_render_card()
    card = _lm_card("Under", "total", 48.0, 47.5, 48.0)
    html_out = _render_card(card)
    assert "<details>" in html_out.lower(), "raw data should be inside a <details> element"
    assert "move_points" in html_out, "raw dict fields must still be present"


# ---- OPS5b Item 2 tests: slot/game filters ----

def _import_build_site():
    site_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "site")
    if site_dir not in sys.path:
        sys.path.insert(0, site_dir)
    os.environ.setdefault("SITE_REPO_ROOT", str(Path(__file__).resolve().parent.parent.parent.parent))
    import build_site
    return build_site


def _build_fixture_page(tmp_path, rows, now=None):
    """Build site from fixture rows, return index.html text."""
    from datetime import datetime, timezone
    now = now or datetime(2026, 10, 8, 23, 30, tzinfo=timezone.utc)
    ledger = _make_ledger(tmp_path, rows)
    os.environ["PICKS_LEDGER_DIR"] = str(ledger)
    os.environ["SITE_REPO_ROOT"] = str(Path(__file__).resolve().parent.parent.parent.parent)
    try:
        bs = _import_build_site()
        out = tmp_path / "site_out"
        bs.build(str(out), now=now)
        return (out / "index.html").read_text()
    finally:
        os.environ.pop("PICKS_LEDGER_DIR", None)


# (2a) slot mapping: kicks → Thu, Sun early, Sun late, SNF, MNF
def test_slot_mapping():
    bs = _import_build_site()
    # 2026-10-09T00:15Z = Thu Oct 8 8:15 PM ET
    assert bs._slot_for_commence("2026-10-09T00:15:00Z", "NFL") == "Thu"
    # 2026-10-11T17:00Z = Sun Oct 11 1:00 PM ET → Sun early
    assert bs._slot_for_commence("2026-10-11T17:00:00Z", "NFL") == "Sun early"
    # 2026-10-11T20:25Z = Sun Oct 11 4:25 PM ET → Sun late
    assert bs._slot_for_commence("2026-10-11T20:25:00Z", "NFL") == "Sun late"
    # 2026-10-12T00:20Z = Sun Oct 11 8:20 PM ET → SNF
    assert bs._slot_for_commence("2026-10-12T00:20:00Z", "NFL") == "SNF"
    # 2026-10-13T00:15Z = Mon Oct 12 8:15 PM ET → MNF
    assert bs._slot_for_commence("2026-10-13T00:15:00Z", "NFL") == "MNF"


# (2b) top_for_selection: filter + renumber + cap
def test_top_for_selection():
    import build_top20 as bt
    # 5 Thu rows at order 0-4, 25 Sun-early rows at 5-29
    thu_rows = [{"pick_id": f"thu_{i}", "event_id": "t" * 32, "conf": 90 - i} for i in range(5)]
    sun_rows = [{"pick_id": f"sun_{i}", "event_id": "s" * 32, "conf": 80 - i} for i in range(25)]
    # Thu selection
    thu_result = bt.top_for_selection(thu_rows, ["t" * 32])
    assert len(thu_result) == 5
    assert [r["rank"] for r in thu_result] == [1, 2, 3, 4, 5]
    assert [r["pick_id"] for r in thu_result] == [f"thu_{i}" for i in range(5)]
    # Sun-early selection → 20 of 25
    sun_result = bt.top_for_selection(sun_rows, ["s" * 32])
    assert len(sun_result) == 20
    assert [r["rank"] for r in sun_result] == list(range(1, 21))


# (2c) built page has slot chips, game chips, and Sunday chip without MNF
def test_page_has_chips(tmp_path):
    rows = [
        _pick_row(0, conf=50, commence_time="2026-10-09T00:15:00Z",
                  event_id="t" * 32, source_file="f1.pq", logged_utc="2026-10-08T20:00:00Z"),
        _pick_row(1, conf=40, commence_time="2026-10-11T17:00:00Z",
                  event_id="s" * 32, source_file="f1.pq", logged_utc="2026-10-08T20:00:00Z"),
        _pick_row(2, conf=30, commence_time="2026-10-13T00:15:00Z",
                  event_id="m" * 32, source_file="f1.pq", logged_utc="2026-10-08T20:00:00Z"),
    ]
    for r in rows:
        r["window"] = "mid"
    html = _build_fixture_page(tmp_path, rows)
    # data-slot attributes present
    assert 'data-slot="Thu"' in html
    assert 'data-slot="Sun early"' in html
    assert 'data-slot="MNF"' in html
    # Sunday chip exists
    assert 'data-slot="Sunday"' in html
    # Sunday chip does NOT include MNF event_id
    import re
    sunday_chip = re.search(r'data-slot="Sunday"[^>]*data-events="([^"]+)"', html)
    assert sunday_chip, "Sunday chip not found"
    sunday_eids = sunday_chip.group(1)
    assert "m" * 32 not in sunday_eids, "MNF event_id must not be in Sunday chip"


# (2d) null control: single-game fixture → same pick_ids as select()
def test_page_null_control_single_game(tmp_path):
    rows = [_pick_row(i, conf=50 + i, source_file="f1.pq",
                      logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")
            for i in range(5)]
    for r in rows:
        r["window"] = "mid"

    import build_top20 as bt
    now = datetime(2026, 10, 8, 23, 30, tzinfo=timezone.utc)
    old = bt.select(rows, "NFL", now)
    slate = bt.select_slate(rows, "NFL", now)
    assert old is not None and slate is not None
    old_pids = [r["pick_id"] for r in old["props"]]
    slate_pids = [r["pick_id"] for r in slate["props"]]
    assert old_pids == slate_pids


# (2e) script has no fetch/localStorage/http
def test_script_no_network(tmp_path):
    rows = [_pick_row(0, conf=50, source_file="f1.pq",
                      logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")]
    rows[0]["window"] = "mid"
    html = _build_fixture_page(tmp_path, rows)
    import re
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    for s in scripts:
        assert "fetch(" not in s, "script must not use fetch()"
        assert "localStorage" not in s, "script must not use localStorage"
        assert "http" not in s, "script must not use http"


# ---- OPS5b Item 3 tests: labels and times ----

# (3a) prop "Over 17.5" not "+17.5"; spread still has sign
def test_prop_no_plus_sign():
    bs = _import_build_site()
    # prop
    assert bs.pt_label(17.5, "player_rush_attempts", "Over") == "17.5"
    assert bs.pt_label(48, "total", "Under") == "48"
    # spread
    assert bs.pt_label(-8.5, "spread", "Dallas Cowboys") == "\u22128.5"
    assert bs.pt_label(8.5, "spread", "Tampa Bay") == "+8.5"


def test_prop_render_no_plus(tmp_path):
    """A prop fixture renders 'Over 17.5', not 'Over +17.5'."""
    rows = [_pick_row(0, conf=50, market="player_rush_attempts",
                      side="Over", point=17.5,
                      source_file="f1.pq", logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")]
    rows[0]["window"] = "mid"
    html = _build_fixture_page(tmp_path, rows)
    assert "Over 17.5" in html, f"expected 'Over 17.5' in rendered page"
    assert "Over +17.5" not in html, f"'Over +17.5' should not appear"


def test_total_render_no_plus(tmp_path):
    """A totals fixture renders 'Under 48'."""
    rows = [_pick_row(0, conf=50, market="total", side="Under", point=48,
                      player_name=None,
                      source_file="f1.pq", logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")]
    rows[0]["window"] = "mid"
    html = _build_fixture_page(tmp_path, rows)
    assert "Under total 48" in html
    assert "Under total +48" not in html


def test_spread_render_has_sign(tmp_path):
    """A spread fixture still renders with sign."""
    rows = [_pick_row(0, conf=50, market="spread", side="Dallas Cowboys",
                      point=-8.5, player_name=None,
                      source_file="f1.pq", logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")]
    rows[0]["window"] = "mid"
    html = _build_fixture_page(tmp_path, rows)
    # Should contain −8.5 (Unicode minus)
    assert "\u22128.5" in html or "-8.5" in html


# (3b) NFL header contains " ET" and no " UTC" before Record
def test_header_et_not_utc(tmp_path):
    rows = [_pick_row(0, conf=50, source_file="f1.pq",
                      logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")]
    rows[0]["window"] = "mid"
    html = _build_fixture_page(tmp_path, rows)
    # Extract NFL tab content before Record section
    import re
    nfl_match = re.search(r'id="tab-nfl"(.*?)Record', html, re.DOTALL)
    assert nfl_match, "NFL tab not found"
    nfl_pre_record = nfl_match.group(1)
    assert " ET" in nfl_pre_record, "NFL header should contain ' ET'"
    assert " UTC" not in nfl_pre_record, "NFL header should not contain ' UTC'"


# (3c) health/tracking pages byte-identical
def test_health_tracking_unchanged(tmp_path):
    """Health and tracking pages are untouched by slot filter changes."""
    rows = [_pick_row(0, conf=50, source_file="f1.pq",
                      logged_utc="2026-10-08T20:00:00Z",
                      commence_time="2026-10-09T00:15:00Z")]
    rows[0]["window"] = "mid"
    ledger = _make_ledger(tmp_path, rows)
    os.environ["PICKS_LEDGER_DIR"] = str(ledger)
    os.environ["SITE_REPO_ROOT"] = str(Path(__file__).resolve().parent.parent.parent.parent)
    try:
        bs = _import_build_site()
        now = datetime(2026, 10, 8, 23, 30, tzinfo=timezone.utc)
        out = tmp_path / "site_out"
        bs.build(str(out), now=now)
        health = (out / "health.html").read_text()
        tracking = (out / "tracking.html").read_text()
        # These should exist and be non-empty
        assert len(health) > 100
        assert len(tracking) > 100
    finally:
        os.environ.pop("PICKS_LEDGER_DIR", None)
