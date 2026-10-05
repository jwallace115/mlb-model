"""
B14: Official NBA injury report parser to A7 standard.

Two independent parsers:
  Parser A — pdftotext -layout text extraction + allowlist grammar
  Parser B — nbainjuries library (tabula-based)

Both must agree on the consumed set {(game_date, matchup, team, player, status)}
or the report gets status "parse_disagree".

Context binding: URL date == header date; header time within [slot, slot+30min];
sha256 of PDF recorded.

Statuses: ok | verified_empty | parse_failed | parse_disagree | context_mismatch
Non-ok -> raw PDF still archived, pull-log carries status, process exits 2.
"""
import hashlib, os, re, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# 30 NBA teams: full name -> 3-letter code
TEAM_MAP = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}
TEAM_CODES = set(TEAM_MAP.values())
VALID_STATUSES = {"Out", "Doubtful", "Questionable", "Probable", "Available"}
NOT_YET_SUBMITTED = "NOT YET SUBMITTED"

HEADER_RE = re.compile(r"Injury\s+Report:\s+(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2}\s+[AP]M)")
PAGE_RE = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)")
GAME_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")
GAME_TIME_RE = re.compile(r"(\d{2}:\d{2})\s*\(ET\)")
MATCHUP_RE = re.compile(r"([A-Z]{3})@([A-Z]{3})")
COL_HEADER_RE = re.compile(
    r"Game\s+Date\s+Game\s+Time\s+Matchup\s+Team\s+Player\s+Name\s+Current\s+Status\s+Reason"
)
# Sorted by length descending for longest-match
_TEAM_NAMES_SORTED = sorted(TEAM_MAP.keys(), key=len, reverse=True)


class ParseHalt(Exception):
    pass


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pdftotext(pdf_path):
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise ParseHalt(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


def _parse_header(text):
    m = HEADER_RE.search(text)
    if not m:
        raise ParseHalt("No header 'Injury Report: MM/DD/YY HH:MM AM|PM' found")
    return m.group(1), m.group(2)


def _header_to_utc(date_mmddyy, time_str):
    dt_et = datetime.strptime(f"{date_mmddyy} {time_str}", "%m/%d/%y %I:%M %p")
    dt_et = dt_et.replace(tzinfo=ET)
    return dt_et.astimezone(UTC)


def _check_pages(text):
    pages_found = PAGE_RE.findall(text)
    if not pages_found:
        raise ParseHalt("No 'Page n of m' found in PDF text")
    total = int(pages_found[0][1])
    found_nums = sorted(set(int(p[0]) for p in pages_found))
    expected = list(range(1, total + 1))
    if found_nums != expected:
        raise ParseHalt(f"Missing pages: expected {expected}, found {found_nums}")
    return total


def _find_team_name(text):
    """Find the longest team name at the start of text. Returns (name, rest) or (None, text)."""
    for tname in _TEAM_NAMES_SORTED:
        if text.startswith(tname):
            return tname, text[len(tname):].strip()
    return None, text


def _find_status(text):
    """Find a status keyword in text. Returns (before, status, after) or None."""
    best = None
    for st in VALID_STATUSES:
        pattern = r'\b' + re.escape(st) + r'\b'
        m = re.search(pattern, text)
        if m:
            if best is None or m.start() < best[1]:
                best = (st, m.start(), m.end())
    if best is None:
        return None
    st, start, end = best
    return text[:start].strip(), st, text[end:].strip()


def _is_structural_line(line):
    """Check if a line is header, column header, or page footer."""
    s = line.strip()
    return (not s or HEADER_RE.search(s) or COL_HEADER_RE.search(s) or PAGE_RE.search(s))


def parse_a(pdf_path):
    """
    Parser A: pdftotext + allowlist grammar.
    Returns (rows, published_utc, header_date_mmddyy).
    Raises ParseHalt on grammar violation.
    """
    text = _pdftotext(pdf_path)
    header_date, header_time = _parse_header(text)
    published_utc = _header_to_utc(header_date, header_time)
    _check_pages(text)

    rows = []
    cur_game_date = None
    cur_game_time = None
    cur_matchup = None
    cur_team = None
    pending_reason = ""  # reason text that appears before its player row

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _is_structural_line(line):
            i += 1
            continue

        rest = stripped

        # 1. Parse game date if present
        gd_match = GAME_DATE_RE.match(rest)
        if gd_match:
            cur_game_date = gd_match.group(1)
            rest = rest[gd_match.end():].strip()

        # 2. Parse game time if present
        gt_match = GAME_TIME_RE.match(rest)
        if gt_match:
            cur_game_time = gt_match.group(1) + " (ET)"
            rest = rest[gt_match.end():].strip()

        # 3. Parse matchup if present
        mu_match = MATCHUP_RE.match(rest)
        if mu_match:
            away_code, home_code = mu_match.group(1), mu_match.group(2)
            if away_code not in TEAM_CODES or home_code not in TEAM_CODES:
                raise ParseHalt(f"Unknown team code in matchup: {mu_match.group(0)}")
            cur_matchup = mu_match.group(0)
            rest = rest[mu_match.end():].strip()

        # 4. Parse team name if present
        found_team, rest = _find_team_name(rest)
        if found_team:
            cur_team = found_team

        # 5. Check for NOT YET SUBMITTED — emit a row, never silence
        if NOT_YET_SUBMITTED in rest:
            pending_reason = ""
            if cur_game_date is not None and cur_matchup is not None and cur_team is not None:
                rows.append({
                    "game_date": cur_game_date,
                    "game_time": cur_game_time or "",
                    "matchup": cur_matchup,
                    "team": cur_team,
                    "player": "",
                    "status": "NOT_YET_SUBMITTED",
                    "reason": "",
                })
            i += 1
            continue

        # 6. Try to find player + status
        if not rest:
            i += 1
            continue

        status_parts = _find_status(rest)
        if status_parts:
            player_part, status_found, reason_part = status_parts

            if player_part:
                # Prepend any pending reason from lines above
                if pending_reason:
                    reason_part = (pending_reason + " " + reason_part).strip() if reason_part else pending_reason
                    pending_reason = ""

                # Collect continuation reason lines
                j = i + 1
                while j < len(lines):
                    nxt = lines[j].strip()
                    if not nxt:
                        j += 1
                        continue
                    if _is_structural_line(lines[j]):
                        break
                    if GAME_DATE_RE.match(nxt) or GAME_TIME_RE.match(nxt) or MATCHUP_RE.match(nxt):
                        break
                    if NOT_YET_SUBMITTED in nxt:
                        break
                    t, _ = _find_team_name(nxt)
                    if t:
                        break
                    sp = _find_status(nxt)
                    if sp and sp[0] and ',' in sp[0]:
                        break
                    reason_part = (reason_part + " " + nxt).strip()
                    j += 1

                if cur_game_date is None or cur_matchup is None or cur_team is None:
                    raise ParseHalt(
                        f"Player row without game context: player={player_part}, "
                        f"game_date={cur_game_date}, matchup={cur_matchup}, team={cur_team}"
                    )

                rows.append({
                    "game_date": cur_game_date,
                    "game_time": cur_game_time or "",
                    "matchup": cur_matchup,
                    "team": cur_team,
                    "player": player_part.rstrip(",").strip(),
                    "status": status_found,
                    "reason": reason_part,
                })
                i = j
                continue
            else:
                # No player name before status — reason continuation or pending
                if rows:
                    rows[-1]["reason"] = (rows[-1]["reason"] + " " + rest).strip()
                else:
                    pending_reason = (pending_reason + " " + rest).strip()
                i += 1
                continue
        else:
            # No status — reason continuation or pending
            if rows:
                rows[-1]["reason"] = (rows[-1]["reason"] + " " + rest).strip()
            else:
                # Buffer as pending reason (appears before player row in PDF layout)
                pending_reason = (pending_reason + " " + rest).strip()
            i += 1
            continue

        i += 1

    return rows, published_utc, header_date


def parse_b(pdf_path, slot_dt):
    """
    Parser B: nbainjuries library (tabula-based).
    slot_dt is a naive datetime for the report slot.
    Returns list of dicts (excluding NOT YET SUBMITTED / nan rows).
    """
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nbainjuries.injury import get_reportdata

    df = get_reportdata(slot_dt, local=True,
                        localdir=str(Path(pdf_path).parent),
                        return_df=True)
    # Collect player rows and nan rows separately, then decide NYS
    player_rows = []
    nan_rows = []
    for _, r in df.iterrows():
        player = str(r.get("Player Name", ""))
        status = str(r.get("Current Status", ""))
        gd = str(r.get("Game Date", ""))
        mu = str(r.get("Matchup", ""))
        team = str(r.get("Team", ""))
        if player in ("nan", "") or status in ("nan", ""):
            if team and team != "nan":
                nan_rows.append((gd, mu, team, str(r.get("Game Time", ""))))
            continue
        player_rows.append({
            "game_date": gd,
            "game_time": str(r.get("Game Time", "")),
            "matchup": mu,
            "team": team,
            "player": player,
            "status": status,
            "reason": str(r.get("Reason", "")),
        })

    # A nan row is genuine NYS only if no player rows exist for that (game_date, matchup, team)
    teams_with_players = {(r["game_date"], r["matchup"], r["team"]) for r in player_rows}
    rows = list(player_rows)
    for gd, mu, team, gt in nan_rows:
        if (gd, mu, team) not in teams_with_players:
            rows.append({
                "game_date": gd,
                "game_time": gt,
                "matchup": mu,
                "team": team,
                "player": "",
                "status": "NOT_YET_SUBMITTED",
                "reason": "",
            })
    return rows


def consumed_set(rows):
    """The consumed set: {(game_date, matchup, team, player, status)}."""
    return {(r["game_date"], r["matchup"], r["team"], r["player"], r["status"])
            for r in rows}


def slot_datetime_from_filename(filename):
    """Parse slot datetime from PDF filename. Returns datetime with ET tz."""
    # New format: Injury-Report_YYYY-MM-DD_HH_MMAM|PM.pdf
    m = re.match(
        r"Injury-Report_(\d{4})-(\d{2})-(\d{2})_(\d{1,2})_(\d{2})(AM|PM)\.pdf",
        filename,
    )
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h, mi = int(m.group(4)), int(m.group(5))
        ampm = m.group(6)
        if ampm == "PM" and h != 12:
            h += 12
        if ampm == "AM" and h == 12:
            h = 0
        return datetime(y, mo, d, h, mi, tzinfo=ET)

    # Legacy format: Injury-Report_YYYY-MM-DD_HHAM|PM.pdf
    m = re.match(
        r"Injury-Report_(\d{4})-(\d{2})-(\d{2})_(\d{1,2})(AM|PM)\.pdf",
        filename,
    )
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h = int(m.group(4))
        ampm = m.group(5)
        if ampm == "PM" and h != 12:
            h += 12
        if ampm == "AM" and h == 12:
            h = 0
        return datetime(y, mo, d, h, 0, tzinfo=ET)

    raise ParseHalt(f"Cannot parse slot datetime from filename: {filename}")


def is_legacy_format(filename):
    """True if filename is legacy hourly format (no minute component)."""
    return bool(re.match(
        r"Injury-Report_\d{4}-\d{2}-\d{2}_\d{1,2}(AM|PM)\.pdf$", filename
    ))


def url_date_from_filename(filename):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if not m:
        raise ParseHalt(f"No date in filename: {filename}")
    return m.group(1)


def validate_context(pdf_path, rows_a, published_utc, header_date_mmddyy):
    """Context binding checks. Returns (status, message).

    Binding window: legacy hourly files [slot, slot+60min],
    new q15 files [slot, slot+30min].
    """
    fname = Path(pdf_path).name
    url_date = url_date_from_filename(fname)
    hd = datetime.strptime(header_date_mmddyy, "%m/%d/%y")
    header_date_iso = hd.strftime("%Y-%m-%d")

    if url_date != header_date_iso:
        return "context_mismatch", f"URL date {url_date} != header date {header_date_iso}"

    try:
        slot_dt = slot_datetime_from_filename(fname)
        slot_utc = slot_dt.astimezone(UTC)
        delta = published_utc - slot_utc
        window = timedelta(minutes=60) if is_legacy_format(fname) else timedelta(minutes=30)
        if delta < timedelta(0) or delta > window:
            return "context_mismatch", (
                f"Header time {published_utc.isoformat()} not within "
                f"[slot {slot_utc.isoformat()}, slot+{int(window.total_seconds()//60)}min]"
            )
    except ParseHalt:
        pass

    for r in rows_a:
        mu = r.get("matchup", "")
        m = MATCHUP_RE.match(mu)
        if m:
            if m.group(1) not in TEAM_CODES or m.group(2) not in TEAM_CODES:
                return "context_mismatch", f"Unknown team code in matchup: {mu}"

    return "ok", ""


def parse_report(pdf_path):
    """
    Full A7 parse: both parsers, consumed-set comparison, context binding.
    Returns (rows, published_utc, slot_et, status, detail).
    """
    pdf_path = Path(pdf_path)
    fname = pdf_path.name

    try:
        rows_a, published_utc, header_date = parse_a(pdf_path)
    except (ParseHalt, Exception) as e:
        return [], None, None, "parse_failed", f"Parser A: {e}"

    try:
        slot_dt = slot_datetime_from_filename(fname)
        slot_et = slot_dt.strftime("%H:%M")
    except ParseHalt:
        slot_et = ""
        slot_dt = None

    if slot_dt is not None:
        try:
            rows_b = parse_b(pdf_path, slot_dt.replace(tzinfo=None))
        except Exception as e:
            return rows_a, published_utc, slot_et, "parse_failed", f"Parser B: {e}"
    else:
        return rows_a, published_utc, slot_et, "parse_failed", "No slot datetime for Parser B"

    set_a = consumed_set(rows_a)
    set_b = consumed_set(rows_b)

    if len(rows_a) == 0 and len(rows_b) == 0:
        ctx_status, ctx_msg = validate_context(pdf_path, rows_a, published_utc, header_date)
        if ctx_status != "ok":
            return [], published_utc, slot_et, ctx_status, ctx_msg
        return [], published_utc, slot_et, "verified_empty", "Both parsers agree: 0 player rows"

    if set_a != set_b:
        only_a = set_a - set_b
        only_b = set_b - set_a
        detail = f"A-only({len(only_a)}): {only_a}, B-only({len(only_b)}): {only_b}"
        return rows_a, published_utc, slot_et, "parse_disagree", detail

    ctx_status, ctx_msg = validate_context(pdf_path, rows_a, published_utc, header_date)
    if ctx_status != "ok":
        return rows_a, published_utc, slot_et, ctx_status, ctx_msg

    return rows_a, published_utc, slot_et, "ok", f"{len(rows_a)} rows, A == B"
