"""CAD3d tests (RED first)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_guard_counts_only_button_runs():
    src = (ROOT / "shared" / "pipeline" / "check_now_service.py").read_text()
    assert 'st.get("requested_by") == "button"' in src


def test_picks_payload_carries_freeze_utc():
    src = (ROOT / "site" / "picks_data.py").read_text()
    assert src.count('"freeze_utc"') >= 3


def test_newest_read_sorted_by_utc_not_et_string():
    html = (ROOT / "site" / "templates" / "picks.html").read_text()
    assert "freeze_utc" in html
    assert "map(function(p){return p.freeze_et;}).sort().pop()" not in html
