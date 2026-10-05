"""B22: legacy [slot, slot+60min] vs new [slot, slot+30min] context window."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from nba.pipeline.injury_report_parser import validate_context, is_legacy_format

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def test_legacy_45min_is_ok():
    """A legacy file with header 45 min after its slot is ok. FAILS on 01c7ca076."""
    # Injury-Report_2025-12-20_12PM.pdf has slot 12:00 ET, header 12:45 PM ET
    fname = "Injury-Report_2025-12-20_12PM.pdf"
    assert is_legacy_format(fname)

    # published_utc = 12:45 PM ET = 17:45 UTC
    published_utc = datetime(2025, 12, 20, 17, 45, tzinfo=UTC)
    header_date = "12/20/25"  # MM/DD/YY
    rows_a = []  # empty is fine for this test

    status, msg = validate_context(fname, rows_a, published_utc, header_date)
    assert status == "ok", f"Expected ok, got {status}: {msg}"


def test_new_format_45min_is_mismatch():
    """A new-format file 45 min after its slot is context_mismatch."""
    fname = "Injury-Report_2025-12-25_12_00PM.pdf"
    assert not is_legacy_format(fname)

    # 45 min after 12:00 PM ET = 12:45 PM ET = 17:45 UTC
    published_utc = datetime(2025, 12, 25, 17, 45, tzinfo=UTC)
    header_date = "12/25/25"
    rows_a = []

    status, msg = validate_context(fname, rows_a, published_utc, header_date)
    assert status == "context_mismatch", f"Expected context_mismatch, got {status}: {msg}"


def test_new_format_25min_is_ok():
    """A new-format file 25 min after its slot is ok (within 30min)."""
    fname = "Injury-Report_2025-12-25_12_00PM.pdf"
    assert not is_legacy_format(fname)

    published_utc = datetime(2025, 12, 25, 17, 25, tzinfo=UTC)
    header_date = "12/25/25"
    rows_a = []

    status, msg = validate_context(fname, rows_a, published_utc, header_date)
    assert status == "ok", f"Expected ok, got {status}: {msg}"


if __name__ == "__main__":
    test_legacy_45min_is_ok()
    test_new_format_45min_is_mismatch()
    test_new_format_25min_is_ok()
    print("All B22 tests passed")
