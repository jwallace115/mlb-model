"""
B17: NOT YET SUBMITTED rows appear in parsed output with status NOT_YET_SUBMITTED.

Test uses the Jan 14 fixture (86 rows = 67 player + 19 NYS) from the existing archive.
FAILS on 771174b77: NYS rows are skipped, so parse_report returns only 67 rows.
"""
import os, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIXTURES_DIR = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "fixtures"
JAN14_PDF = FIXTURES_DIR / "Injury-Report_2026-01-14_12_45PM.pdf"


def test_nys_rows_emitted():
    """Jan 14 fixture has 19 NOT YET SUBMITTED teams; all must appear as rows.
    FAILS on 771174b77: old parser skips NYS -> only 67 rows instead of 86."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    rows, pub, slot, status, detail = parse_report(JAN14_PDF)
    assert status == "ok", f"Expected ok, got {status}: {detail}"

    nys = [r for r in rows if r["status"] == "NOT_YET_SUBMITTED"]
    player_rows = [r for r in rows if r["status"] != "NOT_YET_SUBMITTED"]

    assert len(nys) >= 19, f"Expected >= 19 NYS rows, got {len(nys)}"
    assert len(player_rows) == 67, f"Expected 67 player rows, got {len(player_rows)}"
    assert len(rows) >= 86, f"Expected >= 86 total rows, got {len(rows)}"

    # Each NYS row has player="" and status="NOT_YET_SUBMITTED"
    for r in nys:
        assert r["player"] == "", f"NYS row should have empty player, got {r['player']!r}"
        assert r["status"] == "NOT_YET_SUBMITTED"
        assert r["team"] != "", "NYS row must name the team"
