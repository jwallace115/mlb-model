"""S56: verify BOOKS list includes hardrockbet and has exactly 10 entries."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_books_has_hardrock_and_exactly_10():
    from nhl.pipeline.pull_nhl_live_lines import BOOKS
    assert len(BOOKS) == 10, f"BOOKS has {len(BOOKS)} entries, expected 10"
    assert "hardrockbet" in BOOKS, "hardrockbet not in BOOKS"
    assert "pointsbetus" not in BOOKS, "pointsbetus still in BOOKS (should have been swapped)"
