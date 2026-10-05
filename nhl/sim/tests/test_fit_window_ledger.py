"""S57 (L-WO1b Item 0): parse the fit-window ledger and assert season statuses
and that no row's 'looked at' column names a season other than its own."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research" / "nhl_sim" / "FIT_WINDOW_LEDGER.md"


def _parse_ledger():
    """Parse the markdown table into {season: {status, looked_at_text}}."""
    text = LEDGER.read_text()
    rows = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        season = cells[0].strip()
        if not re.match(r"^\d{4}-\d{2}$", season):
            continue
        status = cells[-1].strip()
        looked_at = cells[3].strip()
        rows[season] = {"status": status, "looked_at": looked_at}
    return rows


def test_statuses():
    rows = _parse_ledger()
    assert rows["2021-22"]["status"] == "DISCOVERY"
    assert rows["2022-23"]["status"] == "DISCOVERY"
    assert rows["2023-24"]["status"] == "VALIDATION"
    assert rows["2024-25"]["status"] == "CONSUMED"
    assert rows["2025-26"]["status"] == "PARTIAL"
    assert rows["2026-27"]["status"] == "PROSPECTIVE"


def _is_nhl_season(s):
    """True if s looks like an NHL season (e.g. '2023-24' where 24 = 23+1)."""
    m = re.match(r"^(20\d{2})-(\d{2})$", s)
    if not m:
        return False
    y = int(m.group(1))
    yy = int(m.group(2))
    return yy == (y + 1) % 100


def test_no_cross_season_references():
    """No row's 'looked at' column should name a season other than its own.
    E.g. the 2022-23 row should not mention '2023-24' in its looked-at text.
    Dates like '2026-09-30' are not season references."""
    rows = _parse_ledger()
    # Match season-shaped strings: YYYY-YY where YY = (YYYY+1) mod 100
    season_pat = re.compile(r"20\d{2}-\d{2}")
    errors = []
    for season, data in rows.items():
        text = data["looked_at"]
        if text == "--":
            continue
        for m in season_pat.finditer(text):
            candidate = m.group()
            if not _is_nhl_season(candidate):
                continue
            if candidate != season:
                errors.append(f"Row {season} 'looked at' mentions season {candidate}")
    assert not errors, "Cross-season references found:\n" + "\n".join(errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
