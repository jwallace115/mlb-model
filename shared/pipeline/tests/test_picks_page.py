"""Gate tests for the Picks page in build_site.py — RED first, then GREEN."""
import hashlib, json, os, sys, tempfile, pytest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _ledger_row(**kw):
    r = dict(
        pick_id="tp_001", ticket_id="t1", owner="m_alpha", source="ai_opinion",
        logged_utc="2026-09-28T12:00:00Z", sport="NFL", event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z", home="Team A", away="Team B",
        market="spread", player_id=None, player_name=None, side="Team A",
        point=-3.5, price_american=-110, book="hardrockbet_fl", reason="test reason",
        share_link=None, supersedes=None, result=None, graded_utc=None,
        result_source=None, ingested_utc="2026-09-28T12:00:01Z",
        source_file="test.json", source_row=0,
    )
    r.update(kw)
    return r


def _setup_ledger(tmp_path, rows):
    """Write a ledger dir with picks.jsonl and members.json."""
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    (ledger / "members.json").write_text('{"members":["m_alpha","m_beta","jeff"]}')
    with open(ledger / "picks.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return ledger


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SITE_DIR = str(_REPO_ROOT / "site")
if _SITE_DIR not in sys.path:
    sys.path.insert(0, _SITE_DIR)


def _build_site(tmp_path, ledger_dir, repo_root=None):
    """Build the site and return index.html content."""
    out = tmp_path / "site_out"
    rr = repo_root or str(_REPO_ROOT)
    os.environ["SITE_REPO_ROOT"] = rr
    os.environ["PICKS_LEDGER_DIR"] = str(ledger_dir)
    import importlib
    import build_site
    build_site.ROOT = Path(rr)
    importlib.reload(build_site)
    build_site.ROOT = Path(rr)
    build_site.build(str(out),
                     now=datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc))
    picks_html = (out / "index.html").read_text()
    return picks_html


# (a) sentinel values never appear in HTML
def test_sentinels_not_in_html(tmp_path):
    rows = [
        _ledger_row(pick_id="s1", share_link="SHARELINK_SENTINEL", result="W",
                    graded_utc="2026-10-01T00:00:00Z"),
    ]
    # Add stake and slip_id as extra fields (they shouldn't be read, but if they are, they must not render)
    rows[0]["stake"] = "STAKE_SENTINEL_777"
    rows[0]["slip_id"] = "SLIP_SENTINEL_777"
    ledger = _setup_ledger(tmp_path, rows)
    html = _build_site(tmp_path, ledger)
    assert "STAKE_SENTINEL_777" not in html
    assert "SLIP_SENTINEL_777" not in html
    assert "SHARELINK_SENTINEL" not in html


# (b) embargoed owner with 5 graded W rows: no hit-rate or ROI on page
def test_embargo_no_stats(tmp_path):
    rows = [_ledger_row(pick_id=f"emb_{i}", owner="sim_nfl", result="W",
                        graded_utc="2026-10-01T00:00:00Z",
                        price_american=-110)
            for i in range(5)]
    ledger = _setup_ledger(tmp_path, rows)
    html = _build_site(tmp_path, ledger)
    # Should NOT contain a hit rate (100.0%) or ROI figure for sim_nfl
    # Should contain "scoring not published"
    assert "scoring not published" in html
    # Should NOT have "100" as a hit rate next to sim_nfl
    # Check that no percentage appears near sim_nfl
    import re
    sim_section = html[html.find("sim_nfl"):html.find("sim_nfl") + 500] if "sim_nfl" in html else ""
    # Should not have a percentage that looks like hit rate
    assert "100.0%" not in sim_section


# (c) PICKS_LEDGER_DIR unset and default absent → NODATA, build succeeds
def test_nodata_when_no_ledger(tmp_path):
    os.environ.pop("PICKS_LEDGER_DIR", None)
    os.environ["SITE_REPO_ROOT"] = str(_REPO_ROOT)
    import importlib, build_site
    importlib.reload(build_site)
    out = tmp_path / "site_out"
    build_site.build(str(out),
                     now=datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc))
    html = (out / "index.html").read_text()
    assert "no data" in html.lower()


# (d) hit rate and ROI for non-embargoed owner equal hand-computed values
def test_hit_rate_and_roi(tmp_path):
    # 3W at -110, 2L at -110
    # hit rate = 3/5 = 60.0%
    # ROI at real price: W profit = 100/110 = 0.909..., L profit = -1
    # total profit = 3 * (100/110) - 2 = 2.727... - 2 = 0.727...
    # ROI = 0.727.../5 = 0.14545... = +14.5%
    rows = []
    for i in range(3):
        rows.append(_ledger_row(pick_id=f"wr_{i}", owner="m_alpha", result="W",
                                graded_utc="2026-10-01T00:00:00Z",
                                price_american=-110))
    for i in range(2):
        rows.append(_ledger_row(pick_id=f"lr_{i}", owner="m_alpha", result="L",
                                graded_utc="2026-10-01T00:00:00Z",
                                price_american=-110))
    ledger = _setup_ledger(tmp_path, rows)
    html = _build_site(tmp_path, ledger)
    assert "60.0%" in html  # hit rate
    assert "+14.5%" in html  # ROI


# (e) src() citation contains fixture file's sha256[:12]
def test_src_citation_sha(tmp_path):
    rows = [_ledger_row(pick_id="src_1", result="W",
                        graded_utc="2026-10-01T00:00:00Z")]
    ledger = _setup_ledger(tmp_path, rows)
    picks_path = ledger / "picks.jsonl"
    sha = hashlib.sha256(picks_path.read_bytes()).hexdigest()[:12]
    html = _build_site(tmp_path, ledger)
    assert sha in html
