"""
Test _report_urls_for_now coverage (WO1b Item 2, B7).

Must FAIL on c715f643a: that version only covered 10:00-12:45 ET.
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_report_urls_include_afternoon_slots():
    """On a day with a 22:00 ET tip, the URL list must include 17:30 and 21:45 slots.
    FAILS on c715f643a because that version stopped at 12:45 ET."""
    from nba.pipeline.capture_nba_availability import official_report_url
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    # Mock _utcnow to return a time on 2026-03-16 at 10:00 ET
    mock_now = datetime(2026, 3, 16, 15, 0, tzinfo=timezone.utc)  # 10:00 ET (EST+5)

    # Mock ESPN scoreboard to return a game tipping at 22:00 ET
    mock_espn_response = MagicMock()
    mock_espn_response.status_code = 200
    mock_espn_response.json.return_value = {
        "events": [{
            "date": "2026-03-17T03:00:00Z",  # 22:00 ET (EST+5)
            "competitions": [{}],
        }]
    }

    with patch("nba.pipeline.capture_nba_availability._utcnow", return_value=mock_now), \
         patch("nba.pipeline.capture_nba_availability.requests.get", return_value=mock_espn_response):
        from nba.pipeline.capture_nba_availability import _report_urls_for_now
        urls = _report_urls_for_now()

    url_times = [t[2] for t in urls]  # third element is "HH:MM"

    assert "17:30" in url_times, "5:30 PM slot missing — capture would miss the freeze report"
    assert "21:45" in url_times, "9:45 PM slot missing — capture stops too early"
    assert "10:00" in url_times, "10:00 AM slot missing — morning reports lost"
