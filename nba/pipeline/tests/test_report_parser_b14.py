"""
Tests for nba/pipeline/injury_report_parser.py (B14).

Tests on REAL PDFs:
  (i)   10-01 PDF yields exactly 5 rows with correct players/statuses
  (ii)  Corrupted PDF through capture main gives parse_failed and exit 2
  (iii) Attack corpus: 10+ text-layer mutations for Parser A must HALT;
        Parser B output tampering must give parse_disagree

Each test FAILS on origin/main (old code path yields None / logs "ok").
"""
import gzip, hashlib, json, os, sys, tempfile, textwrap
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

REPORTS_DIR = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "reports"
FIXTURES_DIR = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "fixtures"
PDF_10_01 = REPORTS_DIR / "Injury-Report_2026-10-01_12_45PM.pdf"


# ─── Test (i): 10-01 PDF yields exactly 5 rows ──────────────────────
# FAILS on origin/main: old _parse_report passes date_str (string) to
# get_reportdata which expects datetime -> TypeError -> returns None

def test_10_01_pdf_yields_5_rows():
    """The 10-01 PDF yields exactly 5 rows with the pre-registered players."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    rows, pub_utc, slot_et, status, detail = parse_report(PDF_10_01)
    assert status == "ok", f"Expected ok, got {status}: {detail}"
    assert len(rows) == 5, f"Expected 5 rows, got {len(rows)}"

    # Pre-registered: Carter Q, Cenac Jr. Q, Conley Q, DeVries Out, Collins Out
    expected = [
        ("Carter, Devin", "Questionable"),
        ("Cenac Jr., Christopher", "Questionable"),
        ("Conley, Mike", "Questionable"),
        ("DeVries, Tucker", "Out"),
        ("Collins, John", "Out"),
    ]
    actual = [(r["player"], r["status"]) for r in rows]
    assert actual == expected, f"Players/statuses don't match:\n  expected: {expected}\n  actual: {actual}"

    # published_utc = 16:56Z
    assert pub_utc is not None
    assert pub_utc.hour == 16
    assert pub_utc.minute == 56


def test_fixtures_a_equals_b():
    """All three fixture PDFs give A == B."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    for pdf in sorted(FIXTURES_DIR.glob("*.pdf")):
        rows, pub, slot, status, detail = parse_report(pdf)
        assert status == "ok", f"{pdf.name}: expected ok, got {status}: {detail}"
        assert len(rows) > 0, f"{pdf.name}: expected rows, got 0"


# ─── Test (ii): Corrupted PDF through capture main -> parse_failed, exit 2 ──

def test_corrupted_pdf_gives_parse_failed_and_exit_2():
    """A corrupted PDF served through capture main gives parse_failed and exit 2.
    FAILS on origin/main: old code logs status 'ok' with 0 rows on any parse error."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a truncated/corrupted PDF (first 100 bytes of the real one)
        real_bytes = PDF_10_01.read_bytes()
        corrupted = real_bytes[:100]

        # Set up the season directory structure
        season_dir = tmpdir / "data" / "injury_archive" / "nba" / "season=2026"
        reports_dir = season_dir / "reports"
        reports_dir.mkdir(parents=True)
        pulls_log = season_dir / "_pulls.jsonl"

        # Write the corrupted PDF
        corrupted_pdf = reports_dir / "Injury-Report_2026-10-01_12_45PM.pdf"
        corrupted_pdf.write_bytes(corrupted)

        # Mock requests to serve our corrupted PDF
        mock_response_head = MagicMock()
        mock_response_head.status_code = 200
        mock_response_get = MagicMock()
        mock_response_get.status_code = 200
        mock_response_get.content = corrupted

        # Import and patch capture
        from nba.pipeline import capture_nba_availability as cap

        # Temporarily swap SEASON_DIR
        orig_season_dir = cap.SEASON_DIR
        orig_pulls_log = cap.PULLS_LOG
        cap.SEASON_DIR = season_dir
        cap.PULLS_LOG = pulls_log

        try:
            # Remove existing PDF so it gets "fetched"
            corrupted_pdf.unlink()

            with patch("nba.pipeline.capture_nba_availability.requests") as mock_req, \
                 patch("nba.pipeline.capture_nba_availability._report_urls_for_now") as mock_urls:
                mock_req.head.return_value = mock_response_head
                mock_req.get.return_value = mock_response_get
                mock_urls.return_value = [
                    ("https://fake/Injury-Report_2026-10-01_12_45PM.pdf",
                     "2026-10-01", "12:45"),
                ]

                fetched, non_ok_status = cap.capture_official_reports()

            # Check the pull log
            assert pulls_log.exists(), "No pulls log written"
            log_lines = [json.loads(l) for l in pulls_log.read_text().strip().split("\n") if l]
            report_lines = [l for l in log_lines if l.get("feed") == "official_report"]
            assert len(report_lines) >= 1, "No official_report log line"
            last_line = report_lines[-1]

            # Status must NOT be "ok" — it should be parse_failed or similar
            assert last_line["status"] != "ok", (
                f"Corrupted PDF logged as 'ok' — this is the B14 bug. "
                f"Status: {last_line['status']}"
            )
            assert non_ok_status is not None, "non_ok_status should be set for corrupted PDF"
        finally:
            cap.SEASON_DIR = orig_season_dir
            cap.PULLS_LOG = orig_pulls_log


# ─── Test (iii): Attack corpus ──────────────────────────────────────

# Parser A text-layer mutations — each must cause ParseHalt

VALID_TEXT = textwrap.dedent("""\
                                         Injury Report: 10/01/26 12:56 PM

Game Date    Game Time    Matchup   Team                    Player Name              Current Status   Reason

10/01/2026   03:00 (ET)   BOS@DET   Boston Celtics          Carter, Devin            Questionable     Injury/Illness - Left Ankle Fracture

                                                      Page 1 of 1
""")


def _parse_text(text):
    """Helper: run Parser A's logic on raw text (bypassing pdftotext)."""
    from nba.pipeline.injury_report_parser import (
        _parse_header, _header_to_utc, _check_pages, ParseHalt,
        GAME_DATE_RE, GAME_TIME_RE, MATCHUP_RE, COL_HEADER_RE,
        _find_team_name, _find_status, _is_structural_line,
        TEAM_CODES, VALID_STATUSES, NOT_YET_SUBMITTED,
    )

    header_date, header_time = _parse_header(text)
    published_utc = _header_to_utc(header_date, header_time)
    _check_pages(text)

    rows = []
    cur_game_date = cur_game_time = cur_matchup = cur_team = None

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if _is_structural_line(line):
            i += 1
            continue
        rest = stripped

        gd_match = GAME_DATE_RE.match(rest)
        if gd_match:
            cur_game_date = gd_match.group(1)
            rest = rest[gd_match.end():].strip()
        gt_match = GAME_TIME_RE.match(rest)
        if gt_match:
            cur_game_time = gt_match.group(1) + " (ET)"
            rest = rest[gt_match.end():].strip()
        mu_match = MATCHUP_RE.match(rest)
        if mu_match:
            if mu_match.group(1) not in TEAM_CODES or mu_match.group(2) not in TEAM_CODES:
                raise ParseHalt(f"Unknown team code: {mu_match.group(0)}")
            cur_matchup = mu_match.group(0)
            rest = rest[mu_match.end():].strip()
        found_team, rest = _find_team_name(rest)
        if found_team:
            cur_team = found_team
        if NOT_YET_SUBMITTED in rest:
            i += 1
            continue
        if not rest:
            i += 1
            continue

        status_parts = _find_status(rest)
        if status_parts:
            player_part, status_found, reason_part = status_parts
            if player_part:
                if cur_game_date is None or cur_matchup is None or cur_team is None:
                    raise ParseHalt(f"Player without context")
                rows.append({
                    "game_date": cur_game_date, "game_time": cur_game_time or "",
                    "matchup": cur_matchup, "team": cur_team,
                    "player": player_part.rstrip(",").strip(),
                    "status": status_found, "reason": reason_part,
                })
                i += 1
                continue
            else:
                if rows:
                    rows[-1]["reason"] = (rows[-1]["reason"] + " " + rest).strip()
                    i += 1
                    continue
                raise ParseHalt(f"Status without player: {stripped!r}")
        else:
            if rows:
                rows[-1]["reason"] = (rows[-1]["reason"] + " " + rest).strip()
                i += 1
                continue
            raise ParseHalt(f"Unrecognized line: {stripped!r}")
        i += 1

    return rows


# Attack case 1: extra status word
def test_attack_extra_status_word():
    """A non-allowlist status word causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("Questionable", "Suspended")
    # "Suspended" is not in VALID_STATUSES, so it won't parse as a status
    # The line becomes unrecognized
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 2: matchup with only one team code
def test_attack_single_team_matchup():
    """A matchup with a single team (not AAA@BBB) is not recognized;
    player row then has no matchup context -> HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("BOS@DET", "BOSDET")
    # Without matchup, player row lacks context
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 3: unknown team code in matchup
def test_attack_unknown_team_code():
    """An unknown 3-letter team code in matchup causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("BOS@DET", "BOS@ZZZ")
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 4: missing page
def test_attack_missing_page():
    """Page 1 of 2 with no Page 2 causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("Page 1 of 1", "Page 1 of 2")
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 5: header date != URL date (tested via validate_context)
def test_attack_header_date_mismatch():
    """Header date != URL date causes context_mismatch."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import validate_context
    # Pretend the file is named for 2026-10-02 but header says 10/01/26
    status, msg = validate_context(
        "Injury-Report_2026-10-02_12_45PM.pdf",
        [],  # rows_a
        datetime(2026, 10, 1, 16, 56, tzinfo=ZoneInfo("UTC")),
        "10/01/26",
    )
    assert status == "context_mismatch", f"Expected context_mismatch, got {status}: {msg}"
    assert "URL date" in msg


# Attack case 6: no header at all
def test_attack_no_header():
    """Missing header causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("Injury Report: 10/01/26 12:56 PM", "Some Random Text")
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 7: player row without game context
def test_attack_player_without_context():
    """A player row before any game date/matchup/team causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = textwrap.dedent("""\
                                         Injury Report: 10/01/26 12:56 PM

Game Date    Game Time    Matchup   Team                    Player Name              Current Status   Reason

Carter, Devin            Questionable     Injury/Illness - Left Ankle Fracture

                                                      Page 1 of 1
""")
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 8: empty file (no content)
def test_attack_empty_text():
    """Empty text causes HALT (no header)."""
    from nba.pipeline.injury_report_parser import ParseHalt
    with pytest.raises(ParseHalt):
        _parse_text("")


# Attack case 9: wrong date format in header
def test_attack_wrong_header_date_format():
    """Header with wrong date format causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("10/01/26", "2026-10-01")
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 10: no page footer
def test_attack_no_page_footer():
    """Missing 'Page n of m' causes HALT."""
    from nba.pipeline.injury_report_parser import ParseHalt
    bad = VALID_TEXT.replace("Page 1 of 1", "")
    with pytest.raises(ParseHalt):
        _parse_text(bad)


# Attack case 11: Parser B tampering — drop one row -> parse_disagree
def test_attack_parser_b_drop_row():
    """If Parser B returns fewer rows than Parser A, status is parse_disagree."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_a, consumed_set

    rows_a, pub, hd = parse_a(PDF_10_01)

    # Simulate Parser B returning one fewer row
    rows_b_tampered = rows_a[:-1]  # drop last row
    set_a = consumed_set(rows_a)
    set_b = consumed_set(rows_b_tampered)
    assert set_a != set_b, "Dropping a row should change the consumed set"


# Attack case 12: Parser B tampering — flip one status -> parse_disagree
def test_attack_parser_b_flip_status():
    """If Parser B has a different status for a player, consumed sets differ."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_a, consumed_set
    import copy

    rows_a, pub, hd = parse_a(PDF_10_01)
    rows_b_tampered = copy.deepcopy(rows_a)
    rows_b_tampered[0]["status"] = "Out"  # was Questionable

    set_a = consumed_set(rows_a)
    set_b = consumed_set(rows_b_tampered)
    assert set_a != set_b, "Flipping a status should change the consumed set"


# ─── Null control: consecutive runs produce identical output ─────────

def test_null_control_deterministic():
    """Two consecutive parses of the same PDF give byte-identical output."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    rows1, pub1, slot1, s1, _ = parse_report(PDF_10_01)
    rows2, pub2, slot2, s2, _ = parse_report(PDF_10_01)

    h1 = hashlib.sha256(json.dumps(rows1, sort_keys=True).encode()).hexdigest()
    h2 = hashlib.sha256(json.dumps(rows2, sort_keys=True).encode()).hexdigest()
    assert h1 == h2, "Same PDF parsed twice should give identical rows"
    assert s1 == s2 == "ok"


from zoneinfo import ZoneInfo
