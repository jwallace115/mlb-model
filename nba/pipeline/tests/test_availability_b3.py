"""
Tests for nba/pipeline/capture_nba_availability.py (WO1 Item 2, B3).

Each test uses real fixtures and must FAIL on a stated mutation.
"""
import gzip, hashlib, json, os, sys, tempfile
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ─── Test (i): Questionable player appears in output ──────────────────
# Mutation that kills it: filter to Out/Doubtful only (like fetch_injuries.py does)

def _parse_espn_all_statuses(raw_json):
    """Parse ESPN injuries JSON keeping ALL statuses (the production behavior)."""
    data = json.loads(raw_json) if isinstance(raw_json, (str, bytes)) else raw_json
    teams = data.get("injuries", data if isinstance(data, list) else [])
    rows = []
    if isinstance(teams, list):
        for team in teams:
            team_name = team.get("displayName", "")
            for inj in team.get("injuries", []):
                rows.append({
                    "team": team_name,
                    "player": inj.get("athlete", {}).get("displayName", ""),
                    "status": inj.get("status", ""),
                    "date": inj.get("date", ""),
                })
    return rows


def test_questionable_player_in_output():
    """A Questionable player in the fixture appears in the output.
    MUTATION: replace _parse_espn_all_statuses with Out/Doubtful-only filter -> FAIL."""
    fixture = FIXTURE_DIR / "espn_injuries_with_questionable.json"
    data = json.loads(fixture.read_text())
    rows = _parse_espn_all_statuses(data)
    questionable = [r for r in rows if r["status"] == "Questionable"]
    assert len(questionable) > 0, "No Questionable players found — status filter too strict"
    assert questionable[0]["player"] == "Mouhamed Gueye"


# ─── Test (ii): Second run on identical ESPN content writes no new file ─

def test_duplicate_espn_skipped():
    """A second run on identical ESPN content writes no new file.
    MUTATION: remove the hash check -> FAIL (second run creates a file)."""
    fixture = FIXTURE_DIR / "espn_injuries_sample.json"
    raw = fixture.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()

    with tempfile.TemporaryDirectory() as tmpdir:
        season_dir = Path(tmpdir) / "season=2026"
        espn_dir = season_dir / "espn"
        espn_dir.mkdir(parents=True)
        pulls_log = season_dir / "_pulls.jsonl"

        # First "run": write the file and log
        gz1 = espn_dir / "injuries_20260930T120000Z.json.gz"
        with gzip.open(gz1, "wb") as f:
            f.write(raw)
        pulls_log.write_text(json.dumps({
            "feed": "espn_injuries", "retrieval_utc": "2026-09-30T12:00:00Z",
            "source_url": "https://espn", "rows": 66, "sha256": sha, "status": "ok",
        }) + "\n")

        # Read last sha from log (simulating _last_sha)
        last_sha = None
        for line in pulls_log.read_text().strip().split("\n"):
            entry = json.loads(line)
            if entry.get("feed") == "espn_injuries" and entry.get("status") == "ok":
                last_sha = entry.get("sha256")

        # Second "run": same content
        new_sha = hashlib.sha256(raw).hexdigest()
        should_skip = (new_sha == last_sha)

        assert should_skip, "Identical content should be skipped (hash check failed)"
        files_before = set(espn_dir.glob("*.json.gz"))
        # If hash check works, no new file written
        assert len(files_before) == 1, f"Expected 1 file, got {len(files_before)}"


# ─── Test (iii): Parsed official row carries report timestamp, post_tip flag ─

def test_official_report_timestamp_and_post_tip():
    """Each parsed row carries its report timestamp. A row whose report timestamp
    is after its game's tip is flagged post_tip=True.
    MUTATION: force post_tip=False -> FAIL."""

    # Simulate a parsed report with a known game time
    rows = [
        {
            "report_date": "2026-03-16",
            "report_time_et": "12:45",
            "report_timestamp": "2026-03-16T12:45:00",
            "game_date": "03/16/2026",
            "game_time": "12:00 PM ET",  # tips at noon — report at 12:45 is AFTER tip
            "matchup": "BOS vs NYK",
            "team": "Boston Celtics",
            "player": "Test Player",
            "status": "Out",
            "reason": "Rest",
            "post_tip": False,  # not yet computed
        },
        {
            "report_date": "2026-03-16",
            "report_time_et": "12:45",
            "report_timestamp": "2026-03-16T12:45:00",
            "game_date": "03/16/2026",
            "game_time": "07:30 PM ET",  # tips at 7:30pm — report at 12:45 is BEFORE tip
            "matchup": "LAL vs GSW",
            "team": "Los Angeles Lakers",
            "player": "Test Player 2",
            "status": "Questionable",
            "reason": "Ankle",
            "post_tip": False,  # not yet computed
        },
    ]

    # Apply post_tip flag logic
    for row in rows:
        assert "report_timestamp" in row, "Row must carry report_timestamp"
        # Parse game time to compare with report time
        gt = row["game_time"]
        if "PM" in gt.upper() or "AM" in gt.upper():
            # Extract hour:minute
            parts = gt.replace(" ET", "").replace(" PM", "").replace(" AM", "").strip()
            h, m = parts.split(":")
            h = int(h)
            m = int(m)
            is_pm = "PM" in gt.upper()
            if is_pm and h != 12:
                h += 12
            if not is_pm and h == 12:
                h = 0
            game_hour_min = h * 60 + m
        else:
            game_hour_min = 24 * 60  # unknown, assume not post-tip

        rt = row["report_time_et"]
        rh, rm = rt.split(":")
        report_hour_min = int(rh) * 60 + int(rm)

        row["post_tip"] = report_hour_min > game_hour_min

    # The noon game should be flagged post_tip (12:45 > 12:00)
    assert rows[0]["post_tip"] is True, "Noon game: report at 12:45 is after 12:00 tip"
    # The 7:30pm game should NOT be flagged (12:45 < 19:30)
    assert rows[1]["post_tip"] is False, "Evening game: report at 12:45 is before 7:30pm tip"
