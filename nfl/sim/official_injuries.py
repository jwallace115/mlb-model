"""D277: the NFL's OFFICIAL injury report (nfl.com) as the week's game-status source.

Why. Audit #18 (A2) found the nflverse injury feed carried no final-report game statuses for
26 of 28 Sunday week-4 teams the night before the games, while nfl.com already showed every
team's final report. On those inputs 19 skill players the official reports list as OUT
(three starting QBs among them) were ACTIVE in the active universe.

What this module does (stdlib only — no new packages on the Mac, D269/D270):
  fetch_page(season, week)        GET https://www.nfl.com/injuries/league/{season}/reg{week}
  parse(html, week)               one row per player, per team section, with structural HALTs
  map_ids(official, rosters, ...) gsis_id from that team's week-W roster, by exact
                                  normalised full name; HALT on any unmatched or ambiguous
                                  skill-position row, or a gsis_id listed twice
  injury_rows(...)                rows in injuries.parquet's schema (only report_status is
                                  consumed downstream: usage.build_active_universe)
  overlay(inj, rows, ...)         for the week's teams on the page, the official rows REPLACE
                                  the feed's rows; every other season/week/team is untouched
  final_report_deadline(...)      16:00 ET two days before the game (one day before a
                                  Thursday game) — the league's final-report deadline
  check(inputs_dir, ...)          the forward gate's per-team verification + reconciliation

The record written next to the page (official_injuries.json) names the URL, the fetch time
and the page's sha256, so the gate re-derives every row from the archived bytes.
"""
import hashlib
import html as _html
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

URL = "https://www.nfl.com/injuries/league/{season}/reg{week}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
HTML_NAME = "official_injuries.html"
RECORD_NAME = "official_injuries.json"

# nfl.com abbreviations that differ from nflverse's; every other code must already be an
# nflverse team code (NFLVERSE_TEAMS) or the parse HALTs.
NFLCOM_TO_NFLVERSE = {"AZ": "ARI", "LAR": "LA"}
NFLVERSE_TEAMS = {"ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
                  "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO",
                  "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"}
HEADER = ["Player", "Position", "Injuries", "Practice Status", "Game Status"]
GAME_STATUSES = {"Out", "Doubtful", "Questionable"}
SKILL_POS = {"QB", "RB", "WR", "TE", "FB"}       # any of these unmatched: HALT

UNIT = '<section class="nfl-o-injury-report__unit">'


def _txt(s):
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s))).strip()


def norm_name(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.'’\-]", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return " ".join(s.split())


def ssl_context():
    """FWD7h: the macOS framework Python has no usable system CA store for `ssl` (the Mac run
    of FWD7g failed certificate verification). Use certifi's bundle when it is installed (it
    is on the Mac, as a dependency of requests; nothing is installed here), else the default.
    Verification is never disabled."""
    import ssl
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch_page(season, week, timeout=30):
    """Returns (bytes, record). The record is what the gate later checks the bytes against."""
    url = URL.format(season=season, week=week)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    fetched = datetime.now(timezone.utc)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        status, body, final_url = r.status, r.read(), r.geturl()
    if status != 200:
        raise SystemExit(f"HALT: {url} returned HTTP {status}")
    return body, {"url": url, "final_url": final_url, "season": int(season), "week": int(week),
                  "fetched_utc": fetched.isoformat(), "http_status": int(status),
                  "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _read(html_text, week, season):
    """The page's matchups and rows. HALTs on anything that is not the official week-W report
    of `season` (D278, audit #19 A3: the page's own identity — its canonical URL and title —
    must name the season and week; a relabelled or other-season page is refused)."""
    if not re.search(rf"<h2[^>]*>\s*Injuries\s*-\s*WEEK\s+{int(week)}\s*</h2>", html_text):
        raise SystemExit(f"HALT: official injury page is not the week-{week} report "
                         f"(no 'Injuries - WEEK {week}' heading)")
    canon = re.findall(r'<link[^>]*rel="canonical"[^>]*href="([^"]*)"', html_text)
    want = URL.format(season=season, week=week)
    if [c.rstrip("/") for c in canon] != [want]:
        raise SystemExit(f"HALT: official injury page canonical URL {canon} is not {want}")
    title = re.findall(r"<title>(.*?)</title>", html_text, re.S)
    if len(title) != 1 or f"Week {int(week)} of the {int(season)} Season" not in _txt(title[0]):
        raise SystemExit(f"HALT: official injury page title {[_txt(t) for t in title]} does not "
                         f"name week {week} of the {season} season")
    # D279b: HTML comments are not content — a commented-out row is neither a row nor counted
    # (the real sections carry only IE conditional comments around logo images); and a
    # script, template or style element inside a report section is unsupported (HALT)
    # D282 (audit #23 A1): comments are removed by a quote-aware scan of each section, so a
    # comment delimiter inside a quoted attribute value is never treated as a comment
    units = [_section_body(k, p) for k, p in enumerate(html_text.split(UNIT)[1:])]
    if not units:
        raise SystemExit("HALT: official injury page has no team sections")
    for k, u in enumerate(units):
        if re.search(r"<(template|script|style|noscript)\b", u, re.I) or "<!--" in u:
            raise SystemExit(f"HALT: official injury page section {k}: unsupported element "
                             f"(script/template/style/noscript or an unclosed comment)")
    rows, seen, matchups, skipped_sections = [], set(), [], []
    for k, u in enumerate(units):
        abbr = [a.strip() for a in re.findall(r'nfl-c-matchup-strip__team-abbreviation">([^<]*)<', u)]
        full = [_txt(a) for a in re.findall(r'nfl-c-matchup-strip__team-fullname"[^>]*>(.*?)</a>', u, re.S)]
        subs = [_txt(s) for s in re.findall(r'd3-o-section-sub-title"><span>(.*?)</span>', u, re.S)]
        tables = re.findall(r"<table[^>]*>(.*?)</table>", u, re.S)
        if not (len(abbr) == len(full) == len(subs) == len(tables) == 2):
            msg = (f"section {k} {abbr}: parse error — "
                   f"expected 2 teams/2 tables, found abbr {abbr}, names {full}, "
                   f"titles {subs}, tables {len(tables)} — skipped")
            print(f"WARNING: official injury page {msg}")
            skipped_sections.append(k)
            continue
        if subs != full:
            raise SystemExit(f"HALT: official injury page section {k}: table titles {subs} do not "
                             f"match the matchup {full}")
        teams = []
        for a in abbr:
            t = NFLCOM_TO_NFLVERSE.get(a, a)
            if t not in NFLVERSE_TEAMS:
                raise SystemExit(f"HALT: official injury page: unknown team code {a!r}")
            if t in seen:
                raise SystemExit(f"HALT: official injury page lists {t} twice")
            seen.add(t)
            teams.append(t)
        matchups.append({"away": teams[0], "home": teams[1]})
        for i, (t, tab) in enumerate(zip(teams, tables)):
            for tr in _table_rows(t, tab):
                td = _cells(t, tr, "td")
                if len(td) != 5 or not td[0]:
                    raise SystemExit(f"HALT: official injury page {t}: malformed row {td}")
                gs = td[4] or None
                if gs is not None and gs not in GAME_STATUSES:
                    raise SystemExit(f"HALT: official injury page {t} {td[0]}: unknown game "
                                     f"status {gs!r}")
                rows.append({"team": t, "opp": teams[1 - i], "player": td[0], "position": td[1],
                             "injuries": td[2] or None, "practice_status": td[3] or None,
                             "game_status": gs})
    parsed_units = [u for k, u in enumerate(units) if k not in skipped_sections]
    for k, u in enumerate(parsed_units):
        _section_markup(k, u)
    # D279 (audit #20 A1): an independent count of every player row inside the report
    # sections must equal the rows emitted — no source row may be dropped by structure
    src = sum(len(re.findall(r"<tr\b", u, re.I)) for u in parsed_units) - 2 * len(parsed_units)
    if src != len(rows):
        raise SystemExit(f"HALT: official injury page has {src} player rows but {len(rows)} were "
                         f"parsed")
    if skipped_sections:
        print(f"WARNING: {len(skipped_sections)} section(s) skipped; "
              f"teams in those sections are NOT covered by the official report")
    return matchups, pd.DataFrame(rows, columns=["team", "opp", "player", "position", "injuries",
                                                 "practice_status", "game_status"])


def _table_rows(team, tab):
    """D279 (audit #20 A1): every player row of one team table, whatever its body structure.
    The table must be exactly one header row (the 5 expected columns) followed by player rows,
    in any number of <tbody> elements with or without attributes. Anything else between rows
    — other tags, text, a nested table, an unclosed row — HALTs; nothing is silently skipped."""
    if len(re.findall(r"<table\b", tab)) or len(re.findall(r"<thead\b", tab)) != 1:
        raise SystemExit(f"HALT: official injury page {team}: unsupported table structure "
                         f"(nested table or not exactly one header)")
    head_m = re.search(r"<thead\b[^>]*>(.*?)</thead>", tab, re.S)
    if not head_m:
        raise SystemExit(f"HALT: official injury page {team}: header not closed")
    head_tr = re.fullmatch(r"\s*<tr\b[^>]*>(.*?)</tr>\s*", head_m.group(1), re.S)
    if not head_tr or len(re.findall(r"<tr\b", head_m.group(1), re.I)) != 1:
        raise SystemExit(f"HALT: official injury page {team}: columns (not exactly one header "
                         f"row), expected {HEADER}")
    head = _cells(team, head_tr.group(1), "th")
    if head != HEADER:
        raise SystemExit(f"HALT: official injury page {team}: columns {head}, expected {HEADER}")
    rest = tab[:head_m.start()] + tab[head_m.end():]
    rest = re.sub(r"</?tbody\b[^>]*>", "", rest)
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", rest, re.S)
    leftover = re.sub(r"<tr\b[^>]*>.*?</tr>", "", rest, flags=re.S)
    if len(re.findall(r"<tr\b", rest)) != len(rows) or leftover.strip():
        raise SystemExit(f"HALT: official injury page {team}: unsupported table body structure "
                         f"({len(re.findall(r'<tr', rest))} row tags, {len(rows)} complete rows, "
                         f"stray content {leftover.strip()[:60]!r})")
    return rows


# D280 (audit #21 A): the complete content of every row is validated, not only the cells a
# pattern happens to find. A row is exactly a sequence of <kind> cells separated by whitespace;
# inside a cell only these inline elements may appear (balanced). Any other tag — a <th> in a
# body row, a nested <td>/<tr>/<table>, <del>, … —, any text between cells or a stray '<' HALTs.
# Attributes (colspan, style, hidden, unknown classes, …) are checked for the whole section by
# _section_markup (D281). Cell text is the text between
# the cell's tags, collapsed and decoded as _txt does, so a well-formed page parses identically.
INLINE_TAGS = {"a", "span", "b", "strong", "em", "i", "br"}
VOID_TAGS = {"br"}
_TAG = re.compile(r"""<(/?)([A-Za-z][A-Za-z0-9-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*)\s*(/?)>""")


# D281 (audit #22 A1): attributes are parsed and their values entity-decoded before they are
# judged, and the grammar is an ALLOWLIST taken from the real report sections (fail closed): every
# tag in a section must be one of SECTION_TAGS, every attribute name one of ALLOWED_ATTRS (so a
# style, hidden, colspan or rowspan attribute HALTs however it is spelled or encoded), and every
# class token one that the real sections use on that same tag (CLASS_BY_TAG; inside a team table
# only the player link's class, CLASS_IN_TABLE; a class could hide content through the page's CSS). The
# meaning of these known classes under nfl.com's CSS is assumed stable (declared).
SECTION_TAGS = frozenset({"a", "div", "img", "p", "picture", "source", "span", "svg", "use", "table",
                          "thead", "tbody", "tr", "th", "td"}) | INLINE_TAGS
ALLOWED_ATTRS = frozenset({"aria-label", "aria-hidden", "class", "href", "alt", "data-src",
                           "data-srcset", "role", "src", "media", "viewbox", "scope", "tabindex",
                           "xlink:href"})
CLASS_BY_TAG = {  # every (tag, class token) pair the real report sections use
    "a": {"nfl-c-matchup-strip__team-fullname", "nfl-c-matchup-strip__team-logo", "nfl-o-cta--link"},
    "div": {"d3-o-section-sub-title", "d3-o-table--horizontal-scroll", "nfl-c-matchup-strip",
            "nfl-c-matchup-strip__game", "nfl-c-matchup-strip__game-info",
            "nfl-c-matchup-strip__record", "nfl-c-matchup-strip__team",
            "nfl-c-matchup-strip__team--opponent", "nfl-c-matchup-strip__team-separator",
            "nfl-t-stats__title", "nfl-u-hide-empty"},
    "img": {"img-responsive"},
    "p": {"nfl-c-matchup-strip__date-info", "nfl-c-matchup-strip__networks",
          "nfl-c-matchup-strip__team-name"},
    "span": {"nfl-c-matchup-strip__date-time", "nfl-c-matchup-strip__date-timezone",
             "nfl-c-matchup-strip__team-abbreviation", "nfl-o-icon", "nfl-o-icon--medium"},
    "svg": {"nfl-o-icon--nfl-at", "nfl-o-icon--nfl-vs"},
    "table": {"d3-o-table", "d3-o-table--detailed", "d3-o-reports--detailed"},
}
# inside a team table the real page uses exactly one class: the player link's
CLASS_IN_TABLE = {"a": {"nfl-o-cta--link"}}
# and inside a team table only these attributes (the real rows: <td scope tabindex>, <a href class
# aria-label>; header, body and row tags carry none)
ATTRS_IN_TABLE = {"td": {"scope", "tabindex"}, "a": {"href", "class", "aria-label"}}
_ATTR = re.compile(r"""([^\s"'>/=]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+))?""")


_SCAN = re.compile(r"""<!--(.*?)-->|(</section\s*>)|(<(/?)([A-Za-z][A-Za-z0-9-]*)"""
                   r"""(?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*\s*/?>)|<""", re.S)


def _section_body(k, piece):
    """D282 (audit #23 A1): the content of report section k, from just after its opening tag to
    its closing </section>, with HTML comments removed — but only comments that start in text.
    The scan is quote-aware: a tag is matched as a whole, including quoted attribute values, so
    '<a aria-label="<!--">' is a tag, not a comment opener. A '<' that starts neither a comment,
    a tag nor </section> is kept (the section checks then HALT on it: an unclosed comment, a
    stray '<'). A piece that never reaches a real </section> HALTs."""
    out, pos = [], 0
    for m in _SCAN.finditer(piece):
        out.append(piece[pos:m.start()])
        pos = m.end()
        body = m.group(1)
        if body is not None and (body.startswith(">") or body.startswith("->") or "--!>" in body):
            # HTML ends a comment at '<!-->', '<!--->' or '--!>' too; this scan would not, so
            # it could drop text a browser shows — fail closed
            raise SystemExit(f"HALT: official injury page section {k}: abruptly or incorrectly "
                             f"closed comment")
        if m.group(2):                      # the section's real closing tag
            return "".join(out)
        if m.group(3):                      # a whole tag, quoted attribute values included
            out.append(m.group(3))
        elif m.group(0) == "<":             # neither comment nor tag: keep it for the checks
            out.append("<")
        # else: a comment that starts in text — dropped
    raise SystemExit(f"HALT: official injury page section {k}: no closing </section> outside "
                     f"comments and attribute values")


def _section_markup(k, u):
    """D281: HALT unless every tag, attribute and class in report section k is on the allowlist."""
    tags = list(_TAG.finditer(u))
    if u.count("<") != len(tags):
        raise SystemExit(f"HALT: official injury page section {k}: unparseable markup")
    in_table = False
    for m in tags:
        name = m.group(2).lower()
        allowed = CLASS_IN_TABLE if in_table else CLASS_BY_TAG
        names = ATTRS_IN_TABLE.get(name, set()) if in_table else ALLOWED_ATTRS
        if name == "table":
            in_table = not m.group(1)
        if name not in SECTION_TAGS:
            raise SystemExit(f"HALT: official injury page section {k}: unsupported element <{name}>")
        if m.group(1) and m.group(3).strip():
            raise SystemExit(f"HALT: official injury page section {k}: attributes on </{name}>")
        for a in _ATTR.finditer(m.group(3)):
            an, v = a.group(1).lower(), a.group(2) or ""
            if "<" in v or ">" in v:
                # D282: a raw angle bracket inside an attribute value could desynchronise the
                # pattern-based steps (sections, tables, rows); the real page has none
                raise SystemExit(f"HALT: official injury page section {k}: raw '<' or '>' in the "
                                 f"{an!r} attribute of <{name}>")
            if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
                v = v[1:-1]
            v = _html.unescape(v)
            if an not in names:
                raise SystemExit(f"HALT: official injury page section {k}: unsupported attribute "
                                 f"{an!r} on <{name}>")
            if an == "class":
                unknown = [c for c in v.split() if c not in allowed.get(name, ())]
                if unknown:
                    raise SystemExit(f"HALT: official injury page section {k}: unknown class "
                                     f"{unknown} on <{name}>")


def _cells(team, row_html, kind):
    """The text of each <kind> cell of one row; HALTs on any other row content (D280)."""
    def bad(why):
        raise SystemExit(f"HALT: official injury page {team}: unsupported row content ({why}) in "
                         f"{_txt(row_html)[:60]!r}")
    cells, pos, cell_start, stack, text_parts = [], 0, None, [], []
    for m in _TAG.finditer(row_html):
        text = row_html[pos:m.start()]
        if "<" in text:
            bad("unparseable markup")
        if cell_start is None and text.strip():
            bad(f"text outside a cell: {text.strip()[:30]!r}")
        if cell_start is not None:
            text_parts.append(text)
        pos = m.end()
        close, name = m.group(1) == "/", m.group(2).lower()
        if cell_start is None:
            if close or name != kind:
                bad(f"<{m.group(1)}{name}> outside a cell")
            cell_start, text_parts = m.end(), []
        elif name == kind and close and not stack:
            # the cell's text is its text between tags (a '>' inside a quoted attribute is
            # part of the tag, not text), whitespace-collapsed and entity-decoded as _txt does
            cells.append(_html.unescape(re.sub(r"\s+", " ", "".join(text_parts))).strip())
            cell_start = None
        elif name not in INLINE_TAGS:
            bad(f"<{m.group(1)}{name}> inside a cell")
        elif name in VOID_TAGS:
            if close:
                bad(f"</{name}>")
        elif close:
            if not stack or stack.pop() != name:
                bad(f"unbalanced </{name}>")
        elif m.group(4):
            bad(f"self-closed <{name}/>")
        else:
            stack.append(name)
    rest = row_html[pos:]
    if "<" in rest or rest.strip() or cell_start is not None:
        bad("unclosed cell or trailing content")
    return cells


def parse(html_text, week, season):
    """One row per listed player: team, opp, player, position, injuries, practice_status,
    game_status (None when blank). HALTs on anything that is not the expected page."""
    return _read(html_text, week, season)[1]


def matchups(html_text, week, season):
    """The page's sections as [{away, home}], including a team whose table has no rows."""
    return _read(html_text, week, season)[0]


def map_ids(official, rosters, season, week):
    """gsis_id for every official row, from THAT team's week-W roster (exact normalised
    full_name, then football_name + last_name). Unmatched non-skill rows get gsis_id None
    (they cannot reach the skill-player active universe); an unmatched or ambiguous
    skill-position row, or one gsis_id listed twice, HALTs."""
    r = rosters[(rosters["season"] == season) & (rosters["week"] == week)]
    r = r[["team", "gsis_id", "full_name", "position"] +
          [c for c in ("football_name", "last_name") if c in r.columns]].copy()
    r["k_full"] = r["full_name"].fillna("").map(norm_name)
    if {"football_name", "last_name"} <= set(r.columns):
        r["k_alt"] = (r["football_name"].fillna("").map(norm_name) + " " +
                      r["last_name"].fillna("").map(norm_name)).str.strip()
    else:
        r["k_alt"] = ""
    out, bad = [], []
    for row in official.itertuples(index=False):
        c = r[r["team"] == row.team]
        k = norm_name(row.player)
        gid, how = None, "unmatched"
        for col in ("k_full", "k_alt"):
            ids = c.loc[c[col] == k, "gsis_id"].dropna().unique()
            if len(ids) == 1:
                gid, how = ids[0], col
                break
            if len(ids) > 1:
                how = "ambiguous"
                break
        if gid is None and (row.position in SKILL_POS or how == "ambiguous"):
            bad.append(f"{row.team} {row.player} ({row.position}): {how} in the week-{week} roster")
        if gid is not None:
            # D278 (audit #19 C): a name match must not cross the skill boundary — a page
            # non-skill row must never mark a same-named skill player Out, nor the reverse
            rpos = c.loc[c["gsis_id"] == gid, "position"].iloc[0]
            if (row.position in SKILL_POS) != (rpos in SKILL_POS):
                bad.append(f"{row.team} {row.player}: page position {row.position} vs roster "
                           f"position {rpos} ({gid})")
        out.append((gid, how))
    o = official.copy()
    o["gsis_id"] = [g for g, _ in out]
    o["match"] = [h for _, h in out]
    dup = o["gsis_id"].dropna()
    dup = sorted(set(dup[dup.duplicated()]))
    if dup:
        bad.append(f"gsis_id listed more than once: {dup[:5]}")
    if bad:
        raise SystemExit("HALT: official injury report rows cannot be identified:\n" +
                         "\n".join(f"  {b}" for b in bad))
    return o


def injury_rows(mapped, season, week, fetched_utc):
    """Rows in injuries.parquet's schema. Unmatched (non-skill) rows are not written: with
    no gsis_id they cannot be joined to anyone."""
    m = mapped[mapped["gsis_id"].notna()]
    first = m["player"].str.split(" ", n=1).str[0]
    last = m["player"].str.split(" ", n=1).str[1]
    return pd.DataFrame({
        "season": float(season), "game_type": "REG", "team": m["team"].values,
        "week": float(week), "gsis_id": m["gsis_id"].values, "position": m["position"].values,
        "full_name": m["player"].values, "first_name": first.values, "last_name": last.values,
        "report_primary_injury": m["injuries"].values, "report_secondary_injury": None,
        "report_status": m["game_status"].values, "practice_primary_injury": m["injuries"].values,
        "practice_secondary_injury": None, "practice_status": m["practice_status"].values,
        "date_modified": pd.Timestamp(fetched_utc), "season_type": "REG"})


def page_teams(mapped):
    """Every team with a section on the page, including a section whose table is empty."""
    return sorted({t for mu in mapped.attrs["matchups"] for t in (mu["away"], mu["home"])})


def overlay(inj, rows, season, week, teams):
    """The feed's rows for (season, week, team with a section on the official page) are
    replaced by the official rows; all other rows are kept as they are, in the feed's column
    order/dtypes. D278: `teams` is the page's sections, not the teams that have rows — a team
    whose official table is empty must not keep the feed's rows."""
    teams = set(teams)
    if not set(rows["team"]) <= teams:
        raise SystemExit(f"HALT: official rows for teams without a page section: "
                         f"{sorted(set(rows['team']) - teams)}")
    drop = (inj["season"] == season) & (inj["week"] == week) & inj["team"].isin(teams)
    new = rows.copy()
    for c in inj.columns:
        if c not in new.columns:
            new[c] = None
    new = new[list(inj.columns)]
    for c in inj.columns:
        try:
            new[c] = new[c].astype(inj[c].dtype)
        except (TypeError, ValueError):
            pass
    return pd.concat([inj[~drop], new], ignore_index=True)


def final_report_deadline(gameday):
    """16:00 America/New_York on the final-report day: two days before the game, one day
    before a Thursday game. Returns a UTC datetime."""
    from zoneinfo import ZoneInfo
    d = pd.Timestamp(str(gameday)).date()
    back = 1 if d.weekday() == 3 else 2
    day = d - timedelta(days=back)
    return datetime(day.year, day.month, day.day, 16, 0,
                    tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)


def write_capture(body, record, dest_dir):
    dest_dir = Path(dest_dir)
    (dest_dir / HTML_NAME).write_bytes(body)
    (dest_dir / RECORD_NAME).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")


def derive(html_path, record_path, rosters, season, week):
    """Re-derive the official rows from archived bytes: (record, mapped rows, injury rows).
    HALTs if the bytes are not the recorded ones or the record is for another week."""
    body = Path(html_path).read_bytes()
    rec = json.loads(Path(record_path).read_text())
    if hashlib.sha256(body).hexdigest() != rec.get("sha256"):
        raise SystemExit(f"HALT: {Path(html_path).name} does not match the sha256 in "
                         f"{Path(record_path).name}")
    if (rec.get("season"), rec.get("week")) != (int(season), int(week)):
        raise SystemExit(f"HALT: the official injury record is for season {rec.get('season')} "
                         f"week {rec.get('week')}, not {season} week {week}")
    # D278 (audit #19 A3): the record must describe a successful fetch of THIS report's URL
    want = URL.format(season=season, week=week)
    probs = []
    if rec.get("url") != want:
        probs.append(f"url {rec.get('url')!r} is not {want}")
    if str(rec.get("final_url") or "").rstrip("/") != want:
        probs.append(f"final (post-redirect) url {rec.get('final_url')!r} is not {want}")
    if rec.get("http_status") != 200:
        probs.append(f"http_status {rec.get('http_status')!r}")
    if rec.get("bytes") != len(body):
        probs.append(f"bytes {rec.get('bytes')!r} != {len(body)}")
    if probs:
        raise SystemExit("HALT: the official injury record does not describe this report: " +
                         "; ".join(probs))
    fetched = retrieval_time(rec)
    m, off = _read(body.decode("utf-8"), week, season)
    mapped = map_ids(off, rosters, season, week)
    mapped.attrs["matchups"] = m
    return rec, mapped, injury_rows(mapped, season, week, fetched.isoformat())


def retrieval_time(rec):
    """D278 (audit #19 A2): the record's retrieval time as a finite, timezone-aware UTC
    timestamp. A missing, NaT, naive or unparseable value HALTs."""
    v = rec.get("fetched_utc")
    try:
        t = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        raise SystemExit(f"HALT: official injury record fetched_utc {v!r} is not an ISO timestamp")
    if t.tzinfo is None or t.utcoffset() is None:
        raise SystemExit(f"HALT: official injury record fetched_utc {v!r} has no time zone")
    return pd.Timestamp(t.astimezone(timezone.utc))


def _pairs(df):
    """(gsis_id, report_status) pairs with nulls as '' — comparable whatever the null type."""
    f = lambda v: "" if pd.isna(v) else str(v)  # noqa: E731
    return sorted((f(a), f(b)) for a, b in df[["gsis_id", "report_status"]].itertuples(index=False))


def check(inputs_dir, season, week, teams, schedule, require, cutoff):
    """D277 gate (D278-hardened), on the run directory's copies. Per team: the official page
    has its section, for the team's SCHEDULED matchup (away@home); the page was retrieved at
    or after that game's final-report deadline and at or before the run cutoff; and the
    consumed injuries.parquet rows for the team-week equal the rows re-derived from the
    archived page (gsis_id, report_status). Returns the per-team record; when `require`
    (a primary run) any failure HALTs."""
    inputs_dir = Path(inputs_dir)
    hp, rp = inputs_dir / HTML_NAME, inputs_dir / RECORD_NAME
    per, bad = {}, []
    if not (hp.is_file() and rp.is_file()):
        msg = "no official injury report in the run directory (refresh without it?)"
        if require:
            raise SystemExit(f"HALT (D277): a primary run needs every team's official final "
                             f"injury report; {msg}. Re-run as a declared --pilot.")
        return {t: {"official_verified": False, "official_reason": msg} for t in teams}
    rosters = pd.read_parquet(inputs_dir / "rosters_weekly.parquet")
    rec, mapped, rows = derive(hp, rp, rosters, season, week)
    fetched = retrieval_time(rec)
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise SystemExit(f"HALT: the D277 gate needs a timezone-aware run cutoff, got {cutoff!r}")
    page = {}
    for mu in mapped.attrs["matchups"]:
        page[mu["away"]] = page[mu["home"]] = (mu["away"], mu["home"])
    inj = pd.read_parquet(inputs_dir / "injuries.parquet",
                          columns=["season", "week", "team", "gsis_id", "report_status"])
    inj = inj[(inj["season"] == season) & (inj["week"] == week)]
    sched = schedule[(schedule["week"] == week) & (schedule["game_type"] == "REG")]
    for t in teams:
        g = sched[(sched["home_team"] == t) | (sched["away_team"] == t)]
        reasons = []
        if len(g) != 1:
            reasons.append(f"{len(g)} week-{week} schedule games")
            deadline = None
        else:
            deadline = final_report_deadline(g["gameday"].iloc[0])
            if fetched < pd.Timestamp(deadline):
                reasons.append(f"page fetched {fetched.isoformat()} before the final-report "
                               f"deadline {deadline.isoformat()}")
            sg = (g["away_team"].iloc[0], g["home_team"].iloc[0])
            if t in page and page[t] != sg:
                reasons.append(f"page matchup {page[t][0]}@{page[t][1]} is not the scheduled "
                               f"{sg[0]}@{sg[1]}")
        if fetched > cutoff:
            reasons.append(f"page fetched {fetched.isoformat()} after the run cutoff "
                           f"{cutoff.isoformat()}")
        on_page = mapped[mapped["team"] == t]
        if t not in page:
            reasons.append("no section on the official page")
        want = _pairs(rows[rows["team"] == t])
        have = _pairs(inj[inj["team"] == t])
        if want != have:
            reasons.append(f"consumed injury rows ({len(have)}) differ from the official page "
                           f"({len(want)})")
        per[t] = {"official_rows": int(len(on_page)),
                  "official_game_statuses": int(on_page["game_status"].notna().sum()),
                  "official_fetched_utc": fetched.isoformat(),
                  "final_report_deadline_utc": None if deadline is None else deadline.isoformat(),
                  "official_verified": not reasons}
        if reasons:
            per[t]["official_reason"] = "; ".join(reasons)
            bad.append(f"{t}: " + "; ".join(reasons))
    if bad and require:
        raise SystemExit("HALT (D277): official final injury report not verified — a primary "
                         "run needs every team verified; re-run as a declared --pilot:\n" +
                         "\n".join(f"  {b}" for b in bad))
    return per


def export(week, out_dir, pbp_dir=None, season=2026, backups_root=None):
    """D277: the committable evidence of the capture a refresh used — the fetch record (URL,
    retrieval UTC, sha256 of the page), the parsed and identified rows, and the latest refresh
    manifest. The page itself stays in the local refresh archive (sources/official_injuries.html)."""
    root = Path(__file__).resolve().parents[2]
    pbp_dir = Path(pbp_dir) if pbp_dir else root / "nfl" / "data" / "pbp"
    rosters = pd.read_parquet(pbp_dir / "rosters_weekly.parquet")
    rec, mapped, _ = derive(pbp_dir / HTML_NAME, pbp_dir / RECORD_NAME, rosters, season, week)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / RECORD_NAME).write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    mapped.to_csv(out / "official_injuries_rows.csv", index=False)
    broot = Path(backups_root) if backups_root else root.parent / "mlb-model-archive" / "nfl_ratings_backups"
    backups = sorted(broot.glob("*/refreshed"))
    if backups:
        man = backups[-1] / "refresh_manifest.json"
        m = json.loads(man.read_text())
        if m["files"].get("sources/official_injuries.html") != rec["sha256"]:
            raise SystemExit(f"HALT: the latest refresh manifest ({man}) does not record this page")
        (out / "refresh_manifest.json").write_text(man.read_text())
    else:
        raise SystemExit("HALT: no refresh archive found")
    per = mapped.groupby("team").agg(rows=("player", "size"), game_statuses=("game_status", "count"))
    print(f"exported {len(mapped)} rows ({mapped['team'].nunique()} teams) fetched {rec['fetched_utc']} "
          f"sha256 {rec['sha256'][:16]} to {out}")
    print(per.to_string())


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["export"])
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    export(a.week, a.out)
