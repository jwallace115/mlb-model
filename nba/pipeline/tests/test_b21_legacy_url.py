"""B21: legacy_report_url zero-padding test."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from nba.pipeline.backfill_official_reports import legacy_report_url


def test_legacy_url_zero_padded():
    """h=17 -> _05PM, h=9 -> _09AM, h=12 -> _12PM. FAILS on 01c7ca076."""
    d = date(2025, 1, 15)
    url17 = legacy_report_url(d, 17)
    url9 = legacy_report_url(d, 9)
    url12 = legacy_report_url(d, 12)

    assert "_05PM.pdf" in url17, f"Expected _05PM, got {url17}"
    assert "_09AM.pdf" in url9, f"Expected _09AM, got {url9}"
    assert "_12PM.pdf" in url12, f"Expected _12PM, got {url12}"


def test_legacy_url_matches_old_script_format():
    """Cross-check: legacy_report_url matches the old %I%p format from pull_injury_reports.py."""
    from datetime import datetime
    d = date(2025, 1, 15)
    for h in [9, 10, 11, 12, 13, 14, 15, 16, 17]:
        url = legacy_report_url(d, h)
        # Old script used strftime('%I%p') which produces zero-padded 12-hour
        dt = datetime(d.year, d.month, d.day, h, 0)
        expected_suffix = dt.strftime("%I%p").upper()
        assert f"_{expected_suffix}.pdf" in url, f"h={h}: expected _{expected_suffix}, got {url}"


if __name__ == "__main__":
    test_legacy_url_zero_padded()
    test_legacy_url_matches_old_script_format()
    print("All B21 tests passed")
