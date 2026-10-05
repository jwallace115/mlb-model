"""
B18: Tests for the pending_reason fix (Parser A).

Three legacy PDFs that have reason text appearing ABOVE the player/status line
in the pdftotext layout. These caused ParseHalt ("Unrecognized line: ...") on
079606ccf's parser (before the pending_reason buffer was added).

FAILS on 771174b77 (commit 079606ccf parser): parse_failed with ParseHalt.
"""
import os, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIXTURE_DIR = ROOT / "nba" / "pipeline" / "tests" / "fixtures"


def test_pending_reason_2024_10_22():
    """Injury-Report_2024-10-22_12PM.pdf: reason wraps above player line.
    FAILS on 079606ccf: ParseHalt('Unrecognized line: Injury/Illness - Left Hamstring;')"""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    pdf = FIXTURE_DIR / "Injury-Report_2024-10-22_12PM.pdf"
    rows, pub, slot, status, detail = parse_report(pdf)
    assert status == "ok", f"Expected ok, got {status}: {detail}"
    assert len(rows) > 0


def test_pending_reason_2024_10_27():
    """Injury-Report_2024-10-27_12PM.pdf: reason wraps above player line.
    FAILS on 079606ccf: ParseHalt('Unrecognized line: Injury/Illness - Left Knee; Injury')"""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    pdf = FIXTURE_DIR / "Injury-Report_2024-10-27_12PM.pdf"
    rows, pub, slot, status, detail = parse_report(pdf)
    assert status == "ok", f"Expected ok, got {status}: {detail}"
    assert len(rows) > 0


def test_pending_reason_2024_10_31():
    """Injury-Report_2024-10-31_12PM.pdf: reason wraps above player line.
    FAILS on 079606ccf: ParseHalt('Unrecognized line: Injury/Illness - Right Patella;')"""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    pdf = FIXTURE_DIR / "Injury-Report_2024-10-31_12PM.pdf"
    rows, pub, slot, status, detail = parse_report(pdf)
    assert status == "ok", f"Expected ok, got {status}: {detail}"
    assert len(rows) > 0
