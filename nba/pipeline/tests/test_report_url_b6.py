"""
Test official_report_url (WO1b Item 1, B6).

Must FAIL on c715f643a (the old code used 24-hour format: 17_30PM instead of 05_30PM).
"""
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nba.pipeline.capture_nba_availability import official_report_url

CDN = "https://ak-static.cms.nba.com/referee/injury"


def test_1pm():
    url = official_report_url(date(2026, 3, 16), 13, 0)
    assert url == f"{CDN}/Injury-Report_2026-03-16_01_00PM.pdf"


def test_530pm():
    url = official_report_url(date(2026, 3, 16), 17, 30)
    assert url == f"{CDN}/Injury-Report_2026-03-16_05_30PM.pdf"


def test_1245pm():
    url = official_report_url(date(2026, 3, 16), 12, 45)
    assert url == f"{CDN}/Injury-Report_2026-03-16_12_45PM.pdf"


def test_1015am():
    url = official_report_url(date(2026, 3, 16), 10, 15)
    assert url == f"{CDN}/Injury-Report_2026-03-16_10_15AM.pdf"
