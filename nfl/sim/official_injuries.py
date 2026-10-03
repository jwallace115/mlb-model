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


def fetch_page(season, week, timeout=30):
    """Returns (bytes, record). The record is what the gate later checks the bytes against."""
    url = URL.format(season=season, week=week)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    fetched = datetime.now(timezone.utc)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        status, body = r.status, r.read()
    if status != 200:
        raise SystemExit(f"HALT: {url} returned HTTP {status}")
    return body, {"url": url, "season": int(season), "week": int(week),
                  "fetched_utc": fetched.isoformat(), "http_status": int(status),
                  "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def parse(html_text, week):
    """One row per listed player: team, opp, player, position, injuries, practice_status,
    game_status (None when blank). HALTs on anything that is not the expected page."""
    if not re.search(rf"<h2[^>]*>\s*Injuries\s*-\s*WEEK\s+{int(week)}\s*</h2>", html_text):
        raise SystemExit(f"HALT: official injury page is not the week-{week} report "
                         f"(no 'Injuries - WEEK {week}' heading)")
    units = html_text.split(UNIT)[1:]
    if not units:
        raise SystemExit("HALT: official injury page has no team sections")
    rows, seen = [], set()
    for k, u in enumerate(units):
        u = u.split("</section>", 1)[0]
        abbr = [a.strip() for a in re.findall(r'nfl-c-matchup-strip__team-abbreviation">([^<]*)<', u)]
        full = [_txt(a) for a in re.findall(r'nfl-c-matchup-strip__team-fullname"[^>]*>(.*?)</a>', u, re.S)]
        subs = [_txt(s) for s in re.findall(r'd3-o-section-sub-title"><span>(.*?)</span>', u, re.S)]
        tables = re.findall(r"<table[^>]*>(.*?)</table>", u, re.S)
        if not (len(abbr) == len(full) == len(subs) == len(tables) == 2):
            raise SystemExit(f"HALT: official injury page section {k}: expected 2 teams/2 tables, "
                             f"found abbr {abbr}, names {full}, titles {subs}, tables {len(tables)}")
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
        for i, (t, tab) in enumerate(zip(teams, tables)):
            head = [_txt(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
            if head != HEADER:
                raise SystemExit(f"HALT: official injury page {t}: columns {head}, expected {HEADER}")
            body = re.findall(r"<tbody>(.*?)</tbody>", tab, re.S)
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body[0] if body else "", re.S):
                td = [_txt(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
                if len(td) != 5 or not td[0]:
                    raise SystemExit(f"HALT: official injury page {t}: malformed row {td}")
                gs = td[4] or None
                if gs is not None and gs not in GAME_STATUSES:
                    raise SystemExit(f"HALT: official injury page {t} {td[0]}: unknown game "
                                     f"status {gs!r}")
                rows.append({"team": t, "opp": teams[1 - i], "player": td[0], "position": td[1],
                             "injuries": td[2] or None, "practice_status": td[3] or None,
                             "game_status": gs})
    return pd.DataFrame(rows, columns=["team", "opp", "player", "position", "injuries",
                                       "practice_status", "game_status"])


def map_ids(official, rosters, season, week):
    """gsis_id for every official row, from THAT team's week-W roster (exact normalised
    full_name, then football_name + last_name). Unmatched non-skill rows get gsis_id None
    (they cannot reach the skill-player active universe); an unmatched or ambiguous
    skill-position row, or one gsis_id listed twice, HALTs."""
    r = rosters[(rosters["season"] == season) & (rosters["week"] == week)]
    r = r[["team", "gsis_id", "full_name"] +
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


def overlay(inj, rows, season, week):
    """The feed's rows for (season, week, team on the official page) are replaced by the
    official rows; all other rows are kept as they are, in the feed's column order/dtypes."""
    teams = set(rows["team"])
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
    off = parse(body.decode("utf-8"), week)
    mapped = map_ids(off, rosters, season, week)
    return rec, mapped, injury_rows(mapped, season, week, rec["fetched_utc"])


def _pairs(df):
    """(gsis_id, report_status) pairs with nulls as '' — comparable whatever the null type."""
    f = lambda v: "" if pd.isna(v) else str(v)  # noqa: E731
    return sorted((f(a), f(b)) for a, b in df[["gsis_id", "report_status"]].itertuples(index=False))


def check(inputs_dir, season, week, teams, schedule, require):
    """D277 gate, on the run directory's copies. Per team: the official page has its
    section; the page was fetched at or after that game's final-report deadline; and the
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
    fetched = pd.Timestamp(rec["fetched_utc"])
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
        on_page = mapped[mapped["team"] == t]
        if on_page.empty:
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
