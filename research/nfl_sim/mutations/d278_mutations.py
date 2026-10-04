"""D277-D280 mutation campaign (FWD7g W1-W24, FWD7i X1-X23, FWD7j/k/l Z1-Z23), for reproduction.

Usage: python3 research/nfl_sim/mutations/d278_mutations.py COPY_ROOT
COPY_ROOT is a COPY of the repository tree (never the working checkout): each operator edits
one file there, runs the focused tests, and restores the file. A mutant is KILLED when the
tests fail. X2 (blank strings not converted to missing) is argued equivalent: X1's rule
refuses every blank first, so the outcome is a HALT either way. W24 (no SSL context) is
in test_fwd7g::test_fetch_verifies_certificates_with_an_explicit_context.
"""
import subprocess
import sys
from pathlib import Path

R = Path(sys.argv[1]).resolve()
OIp = "nfl/sim/official_injuries.py"
Up = "nfl/sim/usage.py"
W=[
("W1 overlay drops every team's week rows","nfl/sim/official_injuries.py",'drop = (inj["season"] == season) & (inj["week"] == week) & inj["team"].isin(teams)','drop = (inj["season"] == season) & (inj["week"] == week)'),
("W2 Thursday two days back","nfl/sim/official_injuries.py","back = 1 if d.weekday() == 3 else 2","back = 2"),
("W3 deadline 17:00 ET","nfl/sim/official_injuries.py","return datetime(day.year, day.month, day.day, 16, 0,","return datetime(day.year, day.month, day.day, 17, 0,"),
("W4 deadline not enforced","nfl/sim/official_injuries.py","if fetched < pd.Timestamp(deadline):","if False:"),
("W5 no reconciliation","nfl/sim/official_injuries.py","if want != have:","if False:"),
("W6 unmatched skill allowed","nfl/sim/official_injuries.py",'if gid is None and (row.position in SKILL_POS or how == "ambiguous"):','if gid is None and how == "ambiguous":'),
("W7 any team's roster","nfl/sim/official_injuries.py",'c = r[r["team"] == row.team]','c = r'),
("W8 any week's roster","nfl/sim/official_injuries.py",'r = rosters[(rosters["season"] == season) & (rosters["week"] == week)]','r = rosters[(rosters["season"] == season)]'),
("W9 titles not checked","nfl/sim/official_injuries.py","if subs != full:","if False:"),
("W10 week heading not checked","nfl/sim/official_injuries.py",'if not re.search(rf"<h2[^>]*>\\s*Injuries\\s*-\\s*WEEK\\s+{int(week)}\\s*</h2>", html_text):','if False:'),
("W11 primary not required","nfl/sim/run_forward_v1.py","require=(not pilot) and (season, week) >= OFFICIAL_REPORT_FROM)","require=False)"),
("W12 gate from week 5","nfl/sim/run_forward_v1.py","OFFICIAL_REPORT_FROM = (2026, 4)","OFFICIAL_REPORT_FROM = (2026, 5)"),
("W13 no sha check","nfl/sim/official_injuries.py",'if hashlib.sha256(body).hexdigest() != rec.get("sha256"):','if False:'),
("W14 dup gsis allowed","nfl/sim/official_injuries.py","if dup:\n        bad.append","if False:\n        bad.append"),
("W15 any game status","nfl/sim/official_injuries.py","if gs is not None and gs not in GAME_STATUSES:","if False:"),
("W16 stale capture kept","nfl/sim/refresh_inputs.py","            (PBP / f).unlink(missing_ok=True)","            pass"),
("W17 capture not copied into the run dir","nfl/sim/run_forward_v1.py",'''RECORD_ONLY_FILES = ["depth_charts.parquet",
                     "official_injuries.html", "official_injuries.json"]''','''RECORD_ONLY_FILES = ["depth_charts.parquet"]'''),
("W18 team on page not required","nfl/sim/official_injuries.py","if on_page.empty:\n            reasons.append","if False:\n            reasons.append"),
("W19 record week not checked","nfl/sim/official_injuries.py",'if (rec.get("season"), rec.get("week")) != (int(season), int(week)):','if False:'),
("W20 written before identified","nfl/sim/refresh_inputs.py",'''    mapped = OI.map_ids(off, ros, SEASON, week)
    rows''','''    OI.write_capture(body, rec, PBP)
    mapped = OI.map_ids(off, ros, SEASON, week)
    rows'''),
("W21 schedule game count not checked","nfl/sim/official_injuries.py","if len(g) != 1:","if len(g) == 99:"),
("W22 unknown code passes","nfl/sim/official_injuries.py","if t not in NFLVERSE_TEAMS:","if False:"),
("W23 header not checked","nfl/sim/official_injuries.py","if head != HEADER:","if False:"),
]


REANCHORED = {  # D278/D280 moved these anchors; same operators
 "W11": ("W11 primary not required","nfl/sim/run_forward_v1.py","require=(not pilot) and (season, week) >= OFFICIAL_REPORT_FROM, cutoff=T)","require=False, cutoff=T)"),
 "W18": ("W18 team on page not required","nfl/sim/official_injuries.py",'        if t not in page:\n            reasons.append("no section on the official page")','        if False:\n            reasons.append("no section on the official page")'),
 "W23": ("W23 header not checked", "nfl/sim/official_injuries.py", "    if head != HEADER:\n        raise SystemExit(f\"HALT: official injury page {team}: columns {head}", "    if False:\n        raise SystemExit(f\"HALT: official injury page {team}: columns {head}"),
 "W20": ("W20 written before identified","nfl/sim/refresh_inputs.py","    with tempfile.TemporaryDirectory() as td:\n        OI.write_capture(body, rec, td)","    OI.write_capture(body, rec, PBP)\n    with tempfile.TemporaryDirectory() as td:\n        OI.write_capture(body, rec, td)"),
}
W = [REANCHORED.get(m[0].split()[0], m) for m in W]

X=[
("X1 blank strings not refused",Up,'        *((f"empty or whitespace-only {c}", blank[c].fillna(False).astype(bool)) for c in strcols),\n',''),
("X2 blank not treated as missing",Up,"        p.loc[blank[c].fillna(False).astype(bool), c] = None","        pass"),
("X3 team domain not checked",Up,'''        ("team key outside the 32 nflverse codes",
         (p["posteam"].notna() & ~p["posteam"].isin(PBP_TEAMS)) |
         (p["defteam"].notna() & ~p["defteam"].isin(PBP_TEAMS))),\n''',''),
("X4 defteam domain dropped",Up,''' |
         (p["defteam"].notna() & ~p["defteam"].isin(PBP_TEAMS))),''','),'),
("X5 no upper bound (cutoff)",OIp,"        if fetched > cutoff:","        if False:"),
("X6 naive time accepted",OIp,"    if t.tzinfo is None or t.utcoffset() is None:","    if False:"),
("X7 naive cutoff accepted",OIp,"    if cutoff.tzinfo is None:","    if False:"),
("X8 canonical not checked",OIp,'    if [c.rstrip("/") for c in canon] != [want]:','    if False:'),
("X9 title not checked",OIp,'    if len(title) != 1 or f"Week {int(week)} of the {int(season)} Season" not in _txt(title[0]):','    if False:'),
("X10 record url not checked",OIp,'    if rec.get("url") != want:','    if False:'),
("X11 final url not checked",OIp,'    if str(rec.get("final_url") or "").rstrip("/") != want:','    if False:'),
("X12 http status not checked",OIp,'    if rec.get("http_status") != 200:','    if False:'),
("X13 bytes not checked",OIp,'    if rec.get("bytes") != len(body):','    if False:'),
("X14 matchup not reconciled",OIp,"            if t in page and page[t] != sg:","            if False:"),
("X15 section from rows",OIp,"        if t not in page:","        if on_page.empty:"),
("X16 skill boundary not checked",OIp,"            if (row.position in SKILL_POS) != (rpos in SKILL_POS):","            if False:"),
("X17 overlay by teams-with-rows",OIp,"    teams = set(teams)\n","    teams = set(rows[\"team\"])\n"),
("X18 refresh skips derive checks","nfl/sim/refresh_inputs.py","        rec, mapped, rows = OI.derive(Path(td) / OI.HTML_NAME, Path(td) / OI.RECORD_NAME, ros,\n                                      SEASON, week)",
 "        mapped = OI.map_ids(OI.parse(body.decode('utf-8'), week, SEASON), ros, SEASON, week)\n        mapped.attrs['matchups'] = OI.matchups(body.decode('utf-8'), week, SEASON)\n        rows = OI.injury_rows(mapped, SEASON, week, rec['fetched_utc'])"),
("X19 bundle passes no cutoff","nfl/sim/run_forward_v1.py","require=(not pilot) and (season, week) >= OFFICIAL_REPORT_FROM, cutoff=T)","require=(not pilot) and (season, week) >= OFFICIAL_REPORT_FROM, cutoff=pd.Timestamp('2999-01-01', tz='UTC'))"),
("X20 record season ignored (N01)",OIp,'    if (rec.get("season"), rec.get("week")) != (int(season), int(week)):','    if rec.get("week") != int(week):'),
("X21 blank player name (N02)",OIp,"                if len(td) != 5 or not td[0]:","                if len(td) != 5:"),
("X22 section shape (M02)",OIp,"        if not (len(abbr) == len(full) == len(subs) == len(tables) == 2):","        if not (len(abbr) == len(full) == 2):"),
("X23 overlay rows outside sections",OIp,"    if not set(rows[\"team\"]) <= teams:","    if False:"),
]

Z = [  # D279 (audit #20)
("Z1 only the first table body", OIp, '    rest = re.sub(r"</?tbody\\b[^>]*>", "", rest)\n',
 '    rest = (re.findall(r"<tbody\\b[^>]*>(.*?)</tbody>", rest, re.S) or [""])[0]\n'),
("Z2 tbody with attributes not recognised", OIp, 'rest = re.sub(r"</?tbody\\b[^>]*>", "", rest)', 'rest = re.sub(r"</?tbody>", "", rest)'),
("Z3 no independent row count", OIp, "    if src != len(rows):", "    if False:"),
("Z4 stray content allowed", OIp, "    if len(re.findall(r\"<tr\\b\", rest)) != len(rows) or leftover.strip():", "    if len(re.findall(r\"<tr\\b\", rest)) != len(rows):"),
("Z5 no harness PBP admission", "nfl/sim/run_forward_v1.py", "        _pbp_admission(season, pbp_snap)", "        pass"),
("Z6 feed not kept", "nfl/sim/refresh_inputs.py", '    shutil.copy2(PBP / "injuries.parquet", PBP / "injuries_feed.parquet")   # D279: archived\n', ""),
("Z7 non-UTC offsets rejected (audit #20 Y1)", OIp, "    return pd.Timestamp(t.astimezone(timezone.utc))",
 "    if t.utcoffset().total_seconds():\n        raise SystemExit('offset')\n    return pd.Timestamp(t.astimezone(timezone.utc))"),
("Z8 final_url slash not normalised (Y2)", OIp, '    if str(rec.get("final_url") or "").rstrip("/") != want:', '    if str(rec.get("final_url") or "") != want:'),
("Z9 posteam upper-cased first (Y3)", Up, '         (p["posteam"].notna() & ~p["posteam"].isin(PBP_TEAMS)) |',
 '         (p["posteam"].notna() & ~p["posteam"].astype("string").str.upper().isin(PBP_TEAMS)) |'),
("Z11 comments not stripped", OIp, 're.sub(r"<!--.*?-->", "", html_text, flags=re.S).split(UNIT)[1:]]', 'html_text.split(UNIT)[1:]]'),
("Z12 script/template allowed", OIp, '        if re.search(r"<(template|script|style|noscript)\\b", u, re.I) or "<!--" in u:', '        if False:'),
("Z13 independent count case-sensitive", OIp, '    src = sum(len(re.findall(r"<tr\\b", u, re.I)) for u in units) - 2 * len(units)', '    src = sum(len(re.findall(r"<tr\\b", u)) for u in units) - 2 * len(units)'),
("Z10 header row count not checked", OIp, '    if not head_tr or len(re.findall(r"<tr\\b", head_m.group(1), re.I)) != 1:', "    if not head_tr:"),
# D280 (audit #21 A): complete row-content validation
("Z14 old cell regex (th ignored, extra cells unseen)", OIp, '                td = _cells(t, tr, "td")',
 '                td = [_txt(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]'),
("Z15 text between cells allowed", OIp, "        if cell_start is None and text.strip():", "        if False:"),
("Z16 any tag inside a cell", OIp, "        elif name not in INLINE_TAGS:", "        elif False:"),
("Z17 colspan allowed", OIp, '            if re.search(r"\\b(colspan|rowspan)\\b", attrs, re.I):', "            if False:"),
("Z18 unbalanced close allowed", OIp, "            if not stack or stack.pop() != name:", "            if stack and stack.pop() and False:"),
("Z19 trailing content allowed", OIp, '    if "<" in rest or rest.strip() or cell_start is not None:', "    if cell_start is not None:"),
("Z20 header not validated by cells", OIp, '    head = _cells(team, head_tr.group(1), "th")',
 '    head = [_txt(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head_tr.group(1), re.S)]'),
("Z21 stray '<' allowed", OIp, '        if "<" in text:\n            bad("unparseable markup")', '        if False:\n            bad("unparseable markup")'),
("Z22 hidden elements allowed", OIp, '        if re.search(r"(?:^|\\s)hidden(?=[\\s=]|$)|display\\s*:\\s*none|visibility\\s*:\\s*hidden", attrs, re.I):', "        if False:"),
("Z23 cell text via _txt (quoted '>' leaks into text)", OIp, '            cells.append(_html.unescape(re.sub(r"\\s+", " ", "".join(text_parts))).strip())',
 '            cells.append(_txt(row_html[cell_start:m.start()]))'),
]
W.append(("W24 no SSL context", OIp, "urllib.request.urlopen(req, timeout=timeout, context=ssl_context())",
          "urllib.request.urlopen(req, timeout=timeout)"))
TESTS = ["nfl/sim/tests/test_fwd7g.py", "nfl/sim/tests/test_fwd7f.py",
         "nfl/sim/tests/test_fwd7a.py::test_refresh_snapshots_the_schedule_before_building_and_archives_the_refresh"]
for name, f, a, b in W + X + Z:
    p = R / f
    orig = p.read_text()
    if orig.count(a) != 1:
        print(name, "ANCHOR COUNT", orig.count(a))
        continue
    p.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                            "--basetemp=/tmp/bt_d278mut", *TESTS], cwd=R, capture_output=True, text=True)
    finally:
        p.write_text(orig)
    last = [ln for ln in r.stdout.splitlines() if "passed" in ln or "failed" in ln or "error" in ln]
    print(("KILLED  " if r.returncode else "SURVIVED"), name, "|", last[-1] if last else r.stdout[-200:])
