"""D277 (FWD7g): the official nfl.com injury report — parse, identify, overlay, and the
forward gate's per-team verification and reconciliation. The page fixture is synthetic,
built in the real page's structure (nothing copied from nfl.com). No parametrize (CLAUDE.md)."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import nfl.sim.official_injuries as OI  # noqa: E402

HEAD = "<tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>"


def _team_html(abbr, nick, cls=""):
    return (f'<div class="nfl-c-matchup-strip__team{cls}"><p class="nfl-c-matchup-strip__team-name">'
            f'<span class="nfl-c-matchup-strip__team-abbreviation"> {abbr} </span> '
            f'<a class="nfl-c-matchup-strip__team-fullname" href="/teams/x/" aria-label="Go"> {nick} </a></p></div>')


def _table(nick, rows, head=HEAD):
    trs = "".join("<tr>" + f'<td scope="row" tabindex="0"><a href="/players/x/" class="nfl-o-cta--link"> {r[0]} </a></td>'
                  + "".join(f"<td>{c}</td>" for c in r[1:]) + "</tr>" for r in rows)
    return (f'<div class="nfl-t-stats__title"><div class="d3-o-section-sub-title"><span>{nick}</span></div></div>'
            f'<div class="d3-o-table--horizontal-scroll"><table class="d3-o-table"><thead>{head}</thead>'
            f"<tbody>{trs}</tbody></table></div>")


def _unit(away, home, away_rows, home_rows):
    (aa, an), (ha, hn) = away, home
    return ('<section class="nfl-o-injury-report__unit"><div class="nfl-c-matchup-strip">'
            + _team_html(aa, an, " nfl-c-matchup-strip__team--opponent") + _team_html(ha, hn)
            + "</div>" + _table(an, away_rows) + _table(hn, home_rows) + "</section>")


AWAY_ROWS = [("Bryce Young", "QB", "", "Full Participation in Practice", ""),
             ("Xavier Legette", "WR", "Knee", "Did Not Participate In Practice", "Out"),
             ("Damien Lewis", "G", "Elbow", "Did Not Participate In Practice", "Out")]
HOME_ROWS = [("D&#x27;Andre Swift", "RB", "Ankle", "Limited Participation in Practice", "Questionable"),
             ("Travis Kelce Jr.", "TE", "Knee", "Did Not Participate In Practice", "Doubtful")]


def _page(units=None, week=4, season=2026):
    units = units if units is not None else [_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS)]
    return (f'<html><head><title>Official NFL Injury Report for Players - Week {week} of the {season} Season '
            f'| NFL.com</title><link rel="canonical" href="https://www.nfl.com/injuries/league/{season}/reg{week}">'
            f'</head><body><h2 class="x">Injuries - WEEK {week}</h2><h2>SUNDAY, OCTOBER 4TH</h2>'
            + "".join(units) + "</body></html>")


CUT = pd.Timestamp("2026-10-04T12:00:00Z")      # a run cutoff after the 01:29Z capture


def _rosters(extra=()):
    rows = [("CAR", "00-c1", "Bryce Young", "QB"), ("CAR", "00-c2", "Xavier Legette", "WR"),
            ("CAR", "00-c3", "Damien Lewis", "G"), ("CAR", "00-c4", "Chuba Hubbard", "RB"),
            ("KC", "00-k1", "D'Andre Swift", "RB"), ("KC", "00-k2", "Travis Kelce", "TE"),
            ("KC", "00-k3", "Patrick Mahomes", "QB"), *extra]
    return pd.DataFrame([{"season": 2026, "week": 4, "team": t, "gsis_id": g, "full_name": n,
                          "football_name": n.split()[0], "last_name": n.split()[-1], "position": p,
                          "status": "ACT"} for t, g, n, p in rows])


# ── parse ─────────────────────────────────────────────────────────────────────

def test_parse_reads_every_row_with_its_team_and_status():
    o = OI.parse(_page(), 4, 2026)
    assert o["team"].tolist() == ["CAR"] * 3 + ["KC"] * 2
    assert o["opp"].tolist() == ["KC"] * 3 + ["CAR"] * 2
    assert o["player"].tolist()[3] == "D'Andre Swift"          # HTML entities decoded
    assert [None if pd.isna(v) else v for v in o["game_status"]] == [None, "Out", "Out", "Questionable", "Doubtful"]


def test_parse_maps_nflcom_codes_and_rejects_unknown_ones():
    o = OI.parse(_page([_unit(("AZ", "Cardinals"), ("LAR", "Rams"), AWAY_ROWS[:1], HOME_ROWS[:1])]), 4, 2026)
    assert set(o["team"]) == {"ARI", "LA"}
    with pytest.raises(SystemExit, match="unknown team code 'XX'"):
        OI.parse(_page([_unit(("XX", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS)]), 4, 2026)


def test_parse_halts_on_anything_but_the_expected_page():
    with pytest.raises(SystemExit, match="not the week-4 report"):
        OI.parse(_page(week=5), 4, 2026)
    with pytest.raises(SystemExit, match="no team sections"):
        OI.parse(_page([]), 4, 2026)
    with pytest.raises(SystemExit, match="lists KC twice"):
        OI.parse(_page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS),
                        _unit(("KC", "Chiefs"), ("DEN", "Broncos"), HOME_ROWS, [])]), 4, 2026)
    bad_title = _page().replace("<span>Chiefs</span>", "<span>Broncos</span>")
    with pytest.raises(SystemExit, match="do not match the matchup"):
        OI.parse(bad_title, 4, 2026)
    with pytest.raises(SystemExit, match="columns"):
        OI.parse(_page().replace("<th>Game Status</th>", "<th>Status</th>", 1), 4, 2026)
    with pytest.raises(SystemExit, match="unknown game status 'Inactive'"):
        OI.parse(_page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"),
                              [("Bryce Young", "QB", "", "", "Inactive")], HOME_ROWS)]), 4, 2026)
    with pytest.raises(SystemExit, match="malformed row"):
        OI.parse(_page().replace("<td>QB</td>", "", 1), 4, 2026)


# ── identify ──────────────────────────────────────────────────────────────────

def test_rows_are_identified_from_that_teams_week_roster():
    m = OI.map_ids(OI.parse(_page(), 4, 2026), _rosters(), 2026, 4)
    assert m["gsis_id"].tolist() == ["00-c1", "00-c2", "00-c3", "00-k1", "00-k2"]  # Jr. dropped


def test_an_unidentified_skill_player_halts_and_a_non_skill_one_is_not_written():
    r = _rosters()
    with pytest.raises(SystemExit, match="KC D'Andre Swift \\(RB\\): unmatched"):
        OI.map_ids(OI.parse(_page(), 4, 2026), r[r["gsis_id"] != "00-k1"], 2026, 4)
    m = OI.map_ids(OI.parse(_page(), 4, 2026), r[r["gsis_id"] != "00-c3"], 2026, 4)   # Lewis, G
    assert m.loc[m["player"] == "Damien Lewis", "gsis_id"].isna().all()
    rows = OI.injury_rows(m, 2026, 4, "2026-10-03T01:00:00+00:00")
    assert "Damien Lewis" not in rows["full_name"].tolist() and len(rows) == 4


def test_the_same_name_on_another_team_or_week_never_matches():
    r = _rosters()
    moved = r.copy()
    moved.loc[moved["gsis_id"] == "00-k1", "team"] = "DEN"
    with pytest.raises(SystemExit, match="D'Andre Swift"):
        OI.map_ids(OI.parse(_page(), 4, 2026), moved, 2026, 4)
    with pytest.raises(SystemExit, match="D'Andre Swift"):
        OI.map_ids(OI.parse(_page(), 4, 2026), r.assign(week=3), 2026, 4)


def test_ambiguous_names_and_a_player_listed_twice_halt():
    two = _rosters(extra=[("KC", "00-k9", "D'Andre Swift", "RB")])
    with pytest.raises(SystemExit, match="ambiguous"):
        OI.map_ids(OI.parse(_page(), 4, 2026), two, 2026, 4)
    twice = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS + AWAY_ROWS[1:2], HOME_ROWS)])
    with pytest.raises(SystemExit, match="listed more than once"):
        OI.map_ids(OI.parse(twice, 4, 2026), _rosters(), 2026, 4)


# ── overlay ───────────────────────────────────────────────────────────────────

def _feed():
    base = {"game_type": "REG", "season_type": "REG", "report_primary_injury": None,
            "report_secondary_injury": None, "practice_primary_injury": None,
            "practice_secondary_injury": None, "practice_status": None, "position": "WR",
            "first_name": "x", "last_name": "y", "date_modified": pd.NaT}
    rows = [dict(base, season=2026.0, week=4.0, team="CAR", gsis_id="00-c2", full_name="X L", report_status=None),
            dict(base, season=2026.0, week=4.0, team="DEN", gsis_id="00-d1", full_name="D D", report_status="Out"),
            dict(base, season=2026.0, week=3.0, team="CAR", gsis_id="00-c2", full_name="X L", report_status="Questionable"),
            dict(base, season=2025.0, week=4.0, team="KC", gsis_id="00-k2", full_name="T K", report_status=None)]
    df = pd.DataFrame(rows)
    df["date_modified"] = pd.to_datetime(df["date_modified"], utc=True)
    return df


def test_overlay_replaces_only_the_weeks_rows_for_teams_on_the_page():
    m = OI.map_ids(OI.parse(_page(), 4, 2026), _rosters(), 2026, 4)
    m.attrs["matchups"] = OI.matchups(_page(), 4, 2026)
    rows = OI.injury_rows(m, 2026, 4, "2026-10-03T01:29:28+00:00")
    feed = _feed()
    new = OI.overlay(feed, rows, 2026, 4, OI.page_teams(m))
    assert list(new.columns) == list(feed.columns) and (new.dtypes == feed.dtypes).all()
    w = new[(new["season"] == 2026) & (new["week"] == 4)]
    assert sorted(w["team"]) == ["CAR", "CAR", "CAR", "DEN", "KC", "KC"]
    assert w.set_index("gsis_id").loc["00-c2", "report_status"] == "Out"          # was null
    keep = new[~((new["season"] == 2026) & (new["week"] == 4) & new["team"].isin(["CAR", "KC"]))]
    pd.testing.assert_frame_equal(
        keep.reset_index(drop=True),
        feed[~((feed["season"] == 2026) & (feed["week"] == 4) & feed["team"].isin(["CAR", "KC"]))].reset_index(drop=True))


# ── deadline ──────────────────────────────────────────────────────────────────

def test_final_report_deadline_is_4pm_eastern_two_days_out_one_for_thursday():
    utc = timezone.utc
    assert OI.final_report_deadline("2026-10-04") == datetime(2026, 10, 2, 20, 0, tzinfo=utc)   # Sun
    assert OI.final_report_deadline("2026-10-05") == datetime(2026, 10, 3, 20, 0, tzinfo=utc)   # Mon
    assert OI.final_report_deadline("2026-10-01") == datetime(2026, 9, 30, 20, 0, tzinfo=utc)   # Thu
    assert OI.final_report_deadline("2026-11-15") == datetime(2026, 11, 13, 21, 0, tzinfo=utc)  # EST


# ── the gate ──────────────────────────────────────────────────────────────────

SCHED = pd.DataFrame([{"game_id": "2026_04_CAR_KC", "season": 2026, "game_type": "REG", "week": 4,
                       "gameday": "2026-10-04", "gametime": "13:00", "home_team": "KC", "away_team": "CAR"}])


def _inputs(tmp_path, fetched="2026-10-03T01:29:28+00:00", page=None, edit=None):
    d = tmp_path / "inputs"
    d.mkdir(parents=True)
    body = (page or _page()).encode()
    rec = {"url": OI.URL.format(season=2026, week=4), "final_url": OI.URL.format(season=2026, week=4),
           "season": 2026, "week": 4, "fetched_utc": fetched, "http_status": 200,
           "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    OI.write_capture(body, rec, d)
    ros = _rosters()
    ros.to_parquet(d / "rosters_weekly.parquet", index=False)
    m = OI.map_ids(OI.parse(body.decode(), 4, 2026), ros, 2026, 4)
    m.attrs["matchups"] = OI.matchups(body.decode(), 4, 2026)
    inj = OI.overlay(_feed(), OI.injury_rows(m, 2026, 4, fetched), 2026, 4, OI.page_teams(m))
    if edit:
        inj = edit(inj)
    inj.to_parquet(d / "injuries.parquet", index=False)
    return d


def test_gate_verifies_and_reconciles_each_team(tmp_path):
    per = OI.check(_inputs(tmp_path), 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)
    assert per["CAR"]["official_verified"] and per["KC"]["official_verified"]
    assert per["CAR"]["official_game_statuses"] == 2 and per["KC"]["official_rows"] == 2
    assert per["KC"]["final_report_deadline_utc"] == "2026-10-02T20:00:00+00:00"


def test_gate_halts_a_primary_on_a_page_fetched_before_the_final_report(tmp_path):
    d = _inputs(tmp_path, fetched="2026-10-02T19:59:00+00:00")
    with pytest.raises(SystemExit, match="(?s)HALT \\(D277\\).*fetched 2026-10-02T19:59:00\\+00:00 before"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)
    per = OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)       # a pilot records it
    assert not per["KC"]["official_verified"] and "before the final-report deadline" in per["KC"]["official_reason"]


def test_gate_halts_when_the_consumed_rows_differ_from_the_page(tmp_path):
    def flip(inj):
        inj.loc[(inj["gsis_id"] == "00-c2") & (inj["week"] == 4), "report_status"] = None
        return inj
    with pytest.raises(SystemExit, match="CAR: consumed injury rows \\(3\\) differ from the official page \\(3\\)"):
        OI.check(_inputs(tmp_path, edit=flip), 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)


def test_gate_halts_on_a_team_missing_from_the_page_or_changed_bytes(tmp_path):
    d = _inputs(tmp_path)
    sched = pd.concat([SCHED, SCHED.assign(game_id="g2", home_team="DEN", away_team="LV")])
    with pytest.raises(SystemExit, match="DEN: no section on the official page"):
        OI.check(d, 2026, 4, ["CAR", "KC", "DEN"], sched, require=True, cutoff=CUT)
    (d / OI.HTML_NAME).write_bytes((d / OI.HTML_NAME).read_bytes() + b" ")
    with pytest.raises(SystemExit, match="does not match the sha256"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)


def test_gate_halts_on_a_record_for_another_week_or_no_capture(tmp_path):
    d = _inputs(tmp_path)
    rec = json.loads((d / OI.RECORD_NAME).read_text())
    (d / OI.RECORD_NAME).write_text(json.dumps(dict(rec, week=3)))
    with pytest.raises(SystemExit, match="record is for season 2026 week 3"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)
    (d / OI.RECORD_NAME).unlink()
    with pytest.raises(SystemExit, match="(?s)HALT \\(D277\\).*no official injury report"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)
    assert OI.check(d, 2026, 4, ["KC"], SCHED, require=False, cutoff=CUT)["KC"]["official_verified"] is False


# ── refresh step ──────────────────────────────────────────────────────────────

def _refresh_world(tmp_path, monkeypatch):
    import nfl.sim.refresh_inputs as R
    monkeypatch.setattr(R, "PBP", tmp_path)
    _rosters().to_parquet(tmp_path / "rosters_weekly.parquet", index=False)
    _feed().to_parquet(tmp_path / "injuries.parquet", index=False)
    return R


def _fake_fetch(page=None, fetched="2026-10-03T01:29:28+00:00"):
    body = (page or _page()).encode()

    def f(season, week):
        u = OI.URL.format(season=season, week=week)
        return body, {"url": u, "final_url": u, "season": season, "week": week, "fetched_utc": fetched,
                      "http_status": 200, "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest()}
    return f


def test_refresh_step_overlays_and_writes_a_checkable_capture(tmp_path, monkeypatch):
    R = _refresh_world(tmp_path, monkeypatch)
    R.official_step(4, fetch=_fake_fetch())
    inj = pd.read_parquet(tmp_path / "injuries.parquet")
    w = inj[(inj["season"] == 2026) & (inj["week"] == 4) & (inj["team"] == "CAR")]
    st = {g: (None if pd.isna(v) else v) for g, v in zip(w["gsis_id"], w["report_status"])}
    assert st == {"00-c1": None, "00-c2": "Out", "00-c3": "Out"}
    d = tmp_path / "inputs"
    d.mkdir()
    for f in ("rosters_weekly.parquet", "injuries.parquet", OI.HTML_NAME, OI.RECORD_NAME):
        (d / f).write_bytes((tmp_path / f).read_bytes())
    per = OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)
    assert all(v["official_verified"] for v in per.values())


def test_refresh_step_writes_nothing_when_a_row_cannot_be_identified(tmp_path, monkeypatch):
    R = _refresh_world(tmp_path, monkeypatch)
    before = (tmp_path / "injuries.parquet").read_bytes()
    r = _rosters()
    r[r["gsis_id"] != "00-k1"].to_parquet(tmp_path / "rosters_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="cannot be identified"):
        R.official_step(4, fetch=_fake_fetch())
    assert (tmp_path / "injuries.parquet").read_bytes() == before
    assert not (tmp_path / OI.HTML_NAME).exists() and not (tmp_path / OI.RECORD_NAME).exists()


# ── the forward run ───────────────────────────────────────────────────────────

def test_a_primary_bundle_without_a_verified_official_report_halts_and_a_pilot_records_it(tmp_path, monkeypatch):
    """D277 wiring in build_bundle: from OFFICIAL_REPORT_FROM on, a non-pilot bundle needs
    the official report (fixture: week 3, with the start moved to week 3)."""
    from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _set_fwd_paths, T
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    monkeypatch.setattr(fwd, "OFFICIAL_REPORT_FROM", (2026, 3))
    try:
        with pytest.raises(SystemExit, match="HALT \\(D277\\)"):
            fwd.build_bundle(2026, 3, T, pilot=False, allow_stale_quotes=True, _root=root)
        bd, _ = fwd.build_bundle(2026, 3, T + pd.Timedelta(seconds=1), pilot=True,
                                 allow_stale_quotes=True, _root=root)
        fr = json.loads((bd / "freshness.json").read_text())["per_team"]
        assert all(v["official_verified"] is False for v in fr.values())
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def test_the_gate_starts_at_week_4_of_2026():
    import nfl.sim.run_forward_v1 as fwd
    assert fwd.OFFICIAL_REPORT_FROM == (2026, 4)
    assert "official_injuries.html" in fwd.RECORD_ONLY_FILES and "official_injuries.json" in fwd.RECORD_ONLY_FILES


def test_refresh_archives_the_capture_and_never_reuses_an_earlier_one(tmp_path, monkeypatch):
    """The capture is archived with the refresh (manifest-hashed); a capture left by an
    earlier refresh is deleted before anything is pulled, so --no-official cannot reuse it."""
    from nfl.sim.tests.test_fwd7a import ROOT as R0
    import shutil
    import nfl.sim.refresh_inputs as R
    import nfl.sim.calibration as C
    import nfl.sim.pull_pbp as P
    from nfl.sim.calibration import FIT_INPUT_FILES
    for official in (True, False):
        root = tmp_path / f"repo{official}"
        rd, pb = root / "nfl" / "data" / "sim" / "ratings", root / "nfl" / "data" / "pbp"
        rd.mkdir(parents=True)
        pb.mkdir(parents=True)
        for f in FIT_INPUT_FILES:
            shutil.copy2(R0 / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
        for f in R.SOURCES + R.OPTIONAL_SOURCES:
            (pb / f).write_bytes(f"old {f}".encode())
        (root / "params_v1.json").write_text("{}")
        (root / "FREEZE_v1.json").write_text(json.dumps({"usage_fingerprint": "abc"}))
        for k, v in (("ROOT", root), ("RATINGS", rd), ("PBP", pb), ("PARAMS", root / "params_v1.json"),
                     ("FREEZE", root / "FREEZE_v1.json")):
            monkeypatch.setattr(R, k, v)
        monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
        monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")
        monkeypatch.setattr(R, "_run", lambda script: None)
        monkeypatch.setattr(R, "snapshot_schedule", lambda: None)

        def step(week, pb=pb):
            assert not (pb / OI.HTML_NAME).exists()            # the earlier capture is gone
            (pb / OI.HTML_NAME).write_bytes(b"new page")
            (pb / OI.RECORD_NAME).write_text("{}")
        monkeypatch.setattr(R, "official_step", step)
        monkeypatch.setattr(P, "pull_season", lambda s: pd.DataFrame({"week": [1, 2, 3]}))
        monkeypatch.setattr(P, "write_safe", lambda df, path: None)
        monkeypatch.setattr(R, "freshness_report", lambda week: True)
        assert R.main(["--week", "4"] + ([] if official else ["--no-official"])) == 0
        [backup] = list((root.parent / "mlb-model-archive" / "nfl_ratings_backups").iterdir())
        man = json.loads((backup / "refreshed" / "refresh_manifest.json").read_text())
        shutil.rmtree(root.parent / "mlb-model-archive")
        if official:
            assert man["files"]["sources/official_injuries.html"] == hashlib.sha256(b"new page").hexdigest()
        else:
            assert not (pb / OI.HTML_NAME).exists() and not (pb / OI.RECORD_NAME).exists()
            assert "sources/official_injuries.html" not in man["files"]


def test_a_primary_bundle_with_a_verified_report_passes_the_d277_gate(tmp_path, monkeypatch):
    """The positive path through build_bundle: the capture is copied into the run directory,
    hashed in the bundle manifest, and every team verifies and reconciles."""
    from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _set_fwd_paths, T
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    pb = root / "nfl" / "data" / "pbp"
    page = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"),
                        [("Darren Waller", "TE", "Knee", "Limited Participation in Practice", "Questionable")],
                        [("Travis Kelce", "TE", "Ankle", "Limited Participation in Practice", "Questionable")])],
                 week=3).encode()
    rec = {"url": OI.URL.format(season=2026, week=3), "final_url": OI.URL.format(season=2026, week=3),
           "season": 2026, "week": 3, "fetched_utc": "2099-01-01T00:00:00+00:00",
           "http_status": 200, "bytes": len(page), "sha256": hashlib.sha256(page).hexdigest()}
    OI.write_capture(page, rec, pb)
    m = OI.map_ids(OI.parse(page.decode(), 3, 2026), pd.read_parquet(pb / "rosters_weekly.parquet"), 2026, 3)
    m.attrs["matchups"] = OI.matchups(page.decode(), 3, 2026)
    inj = pd.read_parquet(pb / "injuries.parquet")
    OI.overlay(inj, OI.injury_rows(m, 2026, 3, rec["fetched_utc"]), 2026, 3, OI.page_teams(m)).to_parquet(
        pb / "injuries.parquet", index=False)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    monkeypatch.setattr(fwd, "OFFICIAL_REPORT_FROM", (2026, 3))
    try:
        bd, man = fwd.build_bundle(2026, 3, T, pilot=False, allow_stale_quotes=True, _root=root)
        fr = json.loads((bd / "freshness.json").read_text())["per_team"]
        assert fr["KC"]["official_verified"] and fr["CAR"]["official_verified"]
        assert man["inputs/official_injuries.html"] == hashlib.sha256(page).hexdigest()
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def test_gate_halts_on_a_team_without_exactly_one_schedule_game(tmp_path):
    """Survivor W21: the deadline needs the team's one game this week."""
    d = _inputs(tmp_path)
    with pytest.raises(SystemExit, match="KC: 0 week-4 schedule games"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED.assign(home_team="DEN"), require=True, cutoff=CUT)
    with pytest.raises(SystemExit, match="KC: 2 week-4 schedule games"):
        OI.check(d, 2026, 4, ["CAR", "KC"], pd.concat([SCHED, SCHED.assign(away_team="LV")]), require=True, cutoff=CUT)


def test_export_writes_the_committable_evidence_and_refuses_a_foreign_manifest(tmp_path):
    d = _inputs(tmp_path)
    rec = json.loads((d / OI.RECORD_NAME).read_text())
    b = tmp_path / "backups" / "20261004T110000Z" / "refreshed"
    b.mkdir(parents=True)
    (b / "refresh_manifest.json").write_text(json.dumps({"files": {"sources/official_injuries.html": rec["sha256"]}}))
    OI.export(4, tmp_path / "out", pbp_dir=d, backups_root=tmp_path / "backups")
    assert json.loads((tmp_path / "out" / OI.RECORD_NAME).read_text()) == rec
    rows = pd.read_csv(tmp_path / "out" / "official_injuries_rows.csv")
    assert len(rows) == 5 and set(rows["gsis_id"]) == {"00-c1", "00-c2", "00-c3", "00-k1", "00-k2"}
    (b / "refresh_manifest.json").write_text(json.dumps({"files": {"sources/official_injuries.html": "x"}}))
    with pytest.raises(SystemExit, match="does not record this page"):
        OI.export(4, tmp_path / "out2", pbp_dir=d, backups_root=tmp_path / "backups")


def test_fetch_verifies_certificates_with_an_explicit_context(monkeypatch):
    """FWD7h: the Mac's framework Python failed certificate verification with urlopen's
    default; fetch_page passes a verifying context (certifi's CA bundle when installed)."""
    import ssl
    import urllib.request
    seen = {}

    class Resp:
        status = 200

        def read(self):
            return b"<html></html>"

        def geturl(self):
            return "https://www.nfl.com/injuries/league/2026/reg4"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None, context=None):
        seen["url"], seen["context"] = req.full_url, context
        return Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    body, rec = OI.fetch_page(2026, 4)
    assert seen["url"] == "https://www.nfl.com/injuries/league/2026/reg4"
    ctx = seen["context"]
    assert isinstance(ctx, ssl.SSLContext) and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    assert rec["sha256"] == hashlib.sha256(b"<html></html>").hexdigest() and rec["week"] == 4
    assert rec["final_url"] == "https://www.nfl.com/injuries/league/2026/reg4"


# ── D278: audit #19 ───────────────────────────────────────────────────────────

def _rewrite(d, page=None, **rec_changes):
    """Rewrite the run-dir capture with a new page and/or record fields, re-hashing the page
    so the integrity check passes and the context checks are what is tested."""
    rec = json.loads((d / OI.RECORD_NAME).read_text())
    body = page.encode() if page is not None else (d / OI.HTML_NAME).read_bytes()
    rec.update(sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
    rec.update(rec_changes)
    OI.write_capture(body, rec, d)


def test_a2_missing_naive_or_unparseable_retrieval_times_halt(tmp_path):
    """Audit #19 A2: fetched_utc 'NaT' passed (NaT < deadline is False)."""
    for i, v in enumerate(("NaT", None, "", "2026-10-03T05:59:23", "yesterday")):
        d = _inputs(tmp_path / f"t{i}")
        _rewrite(d, fetched_utc=v)
        with pytest.raises(SystemExit, match="fetched_utc"):
            OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)


def test_a2_a_page_retrieved_after_the_run_cutoff_is_not_verified(tmp_path):
    """Audit #19 A2: 2099 passed — the gate had no upper bound and no cutoff."""
    d = _inputs(tmp_path, fetched="2099-01-01T00:00:00+00:00")
    with pytest.raises(SystemExit, match="(?s)HALT \\(D277\\).*after the run cutoff"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)
    per = OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)
    assert not per["KC"]["official_verified"]
    assert OI.check(d, 2026, 4, ["KC"], SCHED, require=True,
                    cutoff=pd.Timestamp("2099-01-01T00:00:00Z"))["KC"]["official_verified"]
    with pytest.raises(SystemExit, match="timezone-aware run cutoff"):
        OI.check(d, 2026, 4, ["KC"], SCHED, require=False, cutoff=pd.Timestamp("2099-01-02"))


def test_a3_a_page_of_another_season_halts_even_when_rehashed(tmp_path):
    """Audit #19 A3: a page relabelled 2025 (title, canonical) with a 2026 record verified."""
    d = _inputs(tmp_path)
    p25 = _page(season=2025)
    _rewrite(d, page=p25)
    with pytest.raises(SystemExit, match="canonical URL"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)
    d2 = _inputs(tmp_path / "t")
    _rewrite(d2, page=_page().replace("of the 2026 Season", "of the 2025 Season"))
    with pytest.raises(SystemExit, match="does not\\s+name week 4 of the 2026 season"):
        OI.check(d2, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)


def test_a3_the_record_must_describe_a_successful_fetch_of_this_url(tmp_path):
    for i, (k, v, msg) in enumerate((("url", "https://example.invalid/unrelated", "url"),
                                     ("final_url", "https://www.nfl.com/injuries/league/2025/reg4", "final"),
                                     ("final_url", None, "final"),
                                     ("http_status", 500, "http_status 500"))):
        d = _inputs(tmp_path / f"r{i}")
        _rewrite(d, **{k: v})
        with pytest.raises(SystemExit, match=f"does not describe this report: .*{msg}"):
            OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)
    d = _inputs(tmp_path / "b")
    rec = json.loads((d / OI.RECORD_NAME).read_text())
    (d / OI.RECORD_NAME).write_text(json.dumps(dict(rec, bytes=1)))
    with pytest.raises(SystemExit, match="bytes 1 !="):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)
    d = _inputs(tmp_path / "s")
    rec = json.loads((d / OI.RECORD_NAME).read_text())
    (d / OI.RECORD_NAME).write_text(json.dumps(dict(rec, season=2025)))       # survivor N01
    with pytest.raises(SystemExit, match="record is for season 2025 week 4"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False, cutoff=CUT)


def test_a3_page_matchups_must_be_the_scheduled_games(tmp_path):
    """Audit #19 A3: IND-CHI and NYJ-WAS (internally consistent, each team's own rows)
    verified although the schedule says IND@WAS and NYJ@CHI."""
    sched = pd.concat([SCHED, SCHED.assign(game_id="g2", home_team="DEN", away_team="LV")])
    good = [_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS),
            _unit(("LV", "Raiders"), ("DEN", "Broncos"), [], [])]
    swapped = [_unit(("CAR", "Panthers"), ("DEN", "Broncos"), AWAY_ROWS, []),
               _unit(("LV", "Raiders"), ("KC", "Chiefs"), [], HOME_ROWS)]
    d = _inputs(tmp_path / "g", page=_page(good))
    per = OI.check(d, 2026, 4, ["CAR", "KC", "LV", "DEN"], sched, require=True, cutoff=CUT)
    assert all(v["official_verified"] for v in per.values())
    assert per["DEN"]["official_rows"] == 0          # a section with an empty table is present
    d = _inputs(tmp_path / "s", page=_page(swapped))
    with pytest.raises(SystemExit, match="KC: page matchup LV@KC is not the scheduled CAR@KC"):
        OI.check(d, 2026, 4, ["CAR", "KC", "LV", "DEN"], sched, require=True, cutoff=CUT)
    flipped = [_unit(("KC", "Chiefs"), ("CAR", "Panthers"), HOME_ROWS, AWAY_ROWS),
               _unit(("LV", "Raiders"), ("DEN", "Broncos"), [], [])]
    d = _inputs(tmp_path / "f", page=_page(flipped))
    with pytest.raises(SystemExit, match="page matchup KC@CAR is not the scheduled CAR@KC"):
        OI.check(d, 2026, 4, ["CAR", "KC"], sched, require=True, cutoff=CUT)


def test_survivor_m02_a_section_missing_one_table_halts():
    """Audit #19 survivor M02: delete KC's table but keep both headers and titles."""
    page = _page()
    i = page.index('<div class="d3-o-table--horizontal-scroll">', page.index("<span>Chiefs</span>"))
    j = page.index("</table></div>", i) + len("</table></div>")
    with pytest.raises(SystemExit, match="expected 2 teams/2 tables"):
        OI.parse(page[:i] + page[j:], 4, 2026)


def test_survivor_n02_a_row_with_a_blank_player_name_halts():
    page = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS + [("", "G", "", "", "Out")], HOME_ROWS)])
    with pytest.raises(SystemExit, match="malformed row \\['', 'G'"):
        OI.parse(page, 4, 2026)


def test_c_a_name_match_never_crosses_the_skill_boundary():
    """Audit #19 C: the report's TE row mapped to a same-named roster CB."""
    r = _rosters()
    r.loc[r["gsis_id"] == "00-k2", "position"] = "DB"
    with pytest.raises(SystemExit, match="KC Travis Kelce Jr.: page position TE vs roster position DB"):
        OI.map_ids(OI.parse(_page(), 4, 2026), r, 2026, 4)
    r = _rosters()
    r.loc[r["gsis_id"] == "00-c3", "position"] = "RB"            # page lists Damien Lewis as G
    with pytest.raises(SystemExit, match="CAR Damien Lewis: page position G vs roster position RB"):
        OI.map_ids(OI.parse(_page(), 4, 2026), r, 2026, 4)


def test_refresh_step_refuses_a_capture_the_gate_would_refuse(tmp_path, monkeypatch):
    """D278: the refresh derives through the gate's own checks before writing anything."""
    R = _refresh_world(tmp_path, monkeypatch)
    before = (tmp_path / "injuries.parquet").read_bytes()
    with pytest.raises(SystemExit, match="canonical URL"):
        R.official_step(4, fetch=_fake_fetch(page=_page(season=2025)))
    with pytest.raises(SystemExit, match="fetched_utc"):
        R.official_step(4, fetch=_fake_fetch(fetched="NaT"))
    assert (tmp_path / "injuries.parquet").read_bytes() == before
    assert not (tmp_path / OI.HTML_NAME).exists()


def test_overlay_clears_the_feed_rows_of_a_team_whose_official_table_is_empty():
    """D278: overlay keyed by page sections — DEN's empty official table replaces the feed's
    DEN row (keyed by teams-with-rows, the stale feed row survived)."""
    page = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS),
                  _unit(("LV", "Raiders"), ("DEN", "Broncos"), [], [])])
    m = OI.map_ids(OI.parse(page, 4, 2026), _rosters(), 2026, 4)
    m.attrs["matchups"] = OI.matchups(page, 4, 2026)
    new = OI.overlay(_feed(), OI.injury_rows(m, 2026, 4, "2026-10-03T01:29:28+00:00"), 2026, 4,
                     OI.page_teams(m))
    w = new[(new["season"] == 2026) & (new["week"] == 4)]
    assert "DEN" not in set(w["team"]) and OI.page_teams(m) == ["CAR", "DEN", "KC", "LV"]
    with pytest.raises(SystemExit, match="without a page section"):
        OI.overlay(_feed(), OI.injury_rows(m, 2026, 4, "2026-10-03T01:29:28+00:00"), 2026, 4, ["CAR"])


def test_d278_a_primary_bundle_refuses_a_capture_retrieved_after_its_cutoff(tmp_path, monkeypatch):
    """Survivor X19: build_bundle must pass its own cutoff T to the gate."""
    from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _set_fwd_paths, T
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    pb = root / "nfl" / "data" / "pbp"
    page = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"),
                        [("Darren Waller", "TE", "Knee", "Limited Participation in Practice", "Questionable")],
                        [("Travis Kelce", "TE", "Ankle", "Limited Participation in Practice", "Questionable")])],
                 week=3).encode()
    late = (T + pd.Timedelta(minutes=1)).isoformat()
    rec = {"url": OI.URL.format(season=2026, week=3), "final_url": OI.URL.format(season=2026, week=3),
           "season": 2026, "week": 3, "fetched_utc": late,
           "http_status": 200, "bytes": len(page), "sha256": hashlib.sha256(page).hexdigest()}
    OI.write_capture(page, rec, pb)
    m = OI.map_ids(OI.parse(page.decode(), 3, 2026), pd.read_parquet(pb / "rosters_weekly.parquet"), 2026, 3)
    m.attrs["matchups"] = OI.matchups(page.decode(), 3, 2026)
    inj = pd.read_parquet(pb / "injuries.parquet")
    OI.overlay(inj, OI.injury_rows(m, 2026, 3, late), 2026, 3, OI.page_teams(m)).to_parquet(
        pb / "injuries.parquet", index=False)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    monkeypatch.setattr(fwd, "OFFICIAL_REPORT_FROM", (2026, 3))
    try:
        with pytest.raises(SystemExit, match="(?s)HALT \\(D277\\).*after the run cutoff"):
            fwd.build_bundle(2026, 3, T, pilot=False, allow_stale_quotes=True, _root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


# ── D279: audit #20 ───────────────────────────────────────────────────────────

def _was_like_page():
    return _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS)])


def test_d279_every_table_body_is_parsed():
    """Audit #20 A1: '</tbody><tbody>' after a team's first row hid the rest of its rows (and
    two officially Out players) from both the refresh and the gate."""
    page = _was_like_page()
    first_row_end = page.index("</tr>", page.index("<tbody>")) + len("</tr>")
    split = page[:first_row_end] + "</tbody><tbody>" + page[first_row_end:]
    clean = OI.parse(page, 4, 2026)
    for variant in (split, page.replace("</tbody>", "</tbody>\n<tbody>\n</tbody>", 1)):
        got = OI.parse(variant, 4, 2026)
        pd.testing.assert_frame_equal(got, clean)
    assert len(clean) == 5


def test_d279_a_genuinely_empty_table_parses_as_zero_rows():
    page = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), [], HOME_ROWS)])
    o = OI.parse(page, 4, 2026)
    assert (o["team"] == "CAR").sum() == 0 and (o["team"] == "KC").sum() == 2
    no_body = page.replace("<tbody></tbody>", "", 1)
    assert len(OI.parse(no_body, 4, 2026)) == 2


def test_d279_unsupported_table_structures_halt():
    page = _was_like_page()
    row_end = page.index("</tr>", page.index("<tbody>")) + len("</tr>")
    for bad, msg in ((page[:row_end] + "<div>x</div>" + page[row_end:], "stray content"),
                     (page[:row_end] + "<tr><td>Unclosed</td>" + page[row_end:], "row tags"),
                     (page.replace("<tbody>", "<tbody><table><tr><td>x</td></tr></table>", 1), "unsupported table"),
                     (page.replace("<thead>", "<thead><tr><th>Extra</th></tr>", 1), "columns")):
        with pytest.raises(SystemExit, match=msg):
            OI.parse(bad, 4, 2026)


def test_d279_a_player_row_outside_the_tables_halts_by_the_independent_count():
    page = _was_like_page()
    outside = page.replace('<div class="nfl-t-stats__title">',
                           '<tr><td>Ghost Player</td></tr><div class="nfl-t-stats__title">', 1)
    with pytest.raises(SystemExit, match="player rows but 5 were parsed"):
        OI.parse(outside, 4, 2026)


def test_d279_y1_a_non_utc_offset_normalises():
    assert OI.retrieval_time({"fetched_utc": "2026-10-03T11:48:51.308172-04:00"}) == \
        pd.Timestamp("2026-10-03T15:48:51.308172Z")


def test_d279_y2_a_trailing_slash_on_the_final_url_is_accepted(tmp_path):
    d = _inputs(tmp_path)
    _rewrite(d, final_url=OI.URL.format(season=2026, week=4) + "/")
    assert OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)["KC"]["official_verified"]
    _rewrite(d, final_url=OI.URL.format(season=2026, week=4) + "?x=1")
    with pytest.raises(SystemExit, match="final"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True, cutoff=CUT)


def test_d279_a_primary_bundle_refuses_inadmissible_pbp(tmp_path, monkeypatch):
    """Audit #20 B: the harness checks the archived PBP snapshot itself, not only the build."""
    from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _set_fwd_paths, T
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    f = root / "nfl" / "data" / "pbp" / "pbp_2026.parquet"
    p = pd.read_parquet(f)
    extra = {"play_type": "pass", "posteam": "", "defteam": "KC", "complete_pass": 1, "pass_attempt": 1,
             "rush_attempt": 0, "receiver_player_id": "00-1", "passer_player_id": "00-q",
             "rusher_player_id": None}
    for c, v in extra.items():
        p[c] = v
    p.to_parquet(f, index=False)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        with pytest.raises(SystemExit, match="empty or whitespace-only posteam"):
            fwd.build_bundle(2026, 3, T, pilot=True, allow_stale_quotes=True, _root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def test_d279_the_feed_before_the_overlay_is_kept(tmp_path, monkeypatch):
    """Audit #20: the pre-overlay feed was not archived, so 'the feed caught up' could not be
    checked. official_step now keeps it as injuries_feed.parquet (archived with the refresh)."""
    R = _refresh_world(tmp_path, monkeypatch)
    before = (tmp_path / "injuries.parquet").read_bytes()
    R.official_step(4, fetch=_fake_fetch())
    assert (tmp_path / "injuries_feed.parquet").read_bytes() == before
    assert (tmp_path / "injuries.parquet").read_bytes() != before
    assert "injuries_feed.parquet" in R.OPTIONAL_SOURCES


def test_d279_a_second_header_row_halts_as_a_header_error():
    """Z10: an empty extra header row (same columns) is a header error, not a count error."""
    page = _was_like_page().replace("<thead>", "<thead><tr></tr>", 1)
    with pytest.raises(SystemExit, match="columns"):
        OI.parse(page, 4, 2026)


def test_d279b_comments_are_not_rows_and_unsupported_elements_halt():
    """P2 hardening: a commented-out row is neither parsed nor counted; script/template/style
    inside a report section, or an upper-case row tag the parser would not read, HALTs."""
    page = _was_like_page()
    row_end = page.index("</tr>", page.index("<tbody>")) + len("</tr>")
    commented = page[:row_end] + "<!--<tr><td>Ghost</td><td>QB</td><td></td><td></td><td>Out</td></tr>-->" + page[row_end:]
    pd.testing.assert_frame_equal(OI.parse(commented, 4, 2026), OI.parse(page, 4, 2026))
    for bad, msg in ((page[:row_end] + "<template><tr><td>x</td></tr></template>" + page[row_end:], "unsupported element"),
                     (page[:row_end] + "<script>var x=1;</script>" + page[row_end:], "unsupported element"),
                     (page[:row_end] + "<TR><td>Upper</td><td>QB</td><td></td><td></td><td>Out</td></TR>" + page[row_end:],
                      "player rows but 5 were parsed|unsupported table body")):
        with pytest.raises(SystemExit, match=msg):
            OI.parse(bad, 4, 2026)


def test_d279b_an_upper_case_row_outside_the_tables_halts_by_the_count():
    """Z13: the independent row count is case-insensitive."""
    page = _was_like_page().replace('<div class="nfl-t-stats__title">',
                                    '<TR><TD>Ghost</TD></TR><div class="nfl-t-stats__title">', 1)
    with pytest.raises(SystemExit, match="player rows but 5 were parsed"):
        OI.parse(page, 4, 2026)


# ── D280: audit #21 ───────────────────────────────────────────────────────────

def _row_edit(page, player, old, new):
    """Replace `old` with `new` once inside the named player's row."""
    i = page.index(f"> {player} </a>")
    s, e = page.rindex("<tr>", 0, i), page.index("</tr>", i) + len("</tr>")
    row = page[s:e]
    assert row.count(old) >= 1
    k = row.rindex(old)
    return page[:s] + row[:k] + new + row[k + len(old):] + page[e:]


def _six_cell(page=None):
    """Audit #21 A, exactly: the Out cell '<td>Out</td>' becomes '<th>Out</th><td></td>' — a
    six-cell row whose fifth cell still says Out. The old parser ignored the <th>, found five
    <td>s and read the trailing blank as the game status (Out lost, gate passed)."""
    return _row_edit(page or _was_like_page(), "Xavier Legette", "<td>Out</td>", "<th>Out</th><td></td>")


def test_d280_a_th_status_cell_plus_a_blank_cell_halts_the_parse_refresh_and_gate(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="unsupported row content"):
        OI.parse(_six_cell(), 4, 2026)
    # the refresh writes nothing
    R = _refresh_world(tmp_path, monkeypatch)
    before = (tmp_path / "injuries.parquet").read_bytes()
    with pytest.raises(SystemExit, match="unsupported row content"):
        R.official_step(4, fetch=_fake_fetch(page=_six_cell()))
    assert (tmp_path / "injuries.parquet").read_bytes() == before
    assert not (tmp_path / OI.HTML_NAME).exists() and not (tmp_path / OI.RECORD_NAME).exists()
    # the gate re-derives from the bundled capture: a primary AND a pilot HALT
    d = _inputs(tmp_path / "g")
    _rewrite(d, page=_six_cell())
    for req in (True, False):
        with pytest.raises(SystemExit, match="unsupported row content"):
            OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=req, cutoff=CUT)


def test_d280_any_row_content_but_five_cells_of_inline_markup_halts():
    page = _was_like_page()
    L = "Xavier Legette"
    cases = [
        (_row_edit(page, L, "<td>Out</td>", "<th>Out</th>"), "outside a cell"),               # th in a body row
        (_row_edit(page, L, "<td>Out</td>", "<td>Out</td><td></td>"), "malformed row"),        # six cells
        (_row_edit(page, L, "<td>Knee</td>", "<td>Knee</td>stray"), "text outside a cell"),
        (_row_edit(page, L, "<td>Out</td>", "<td>Out</td> x"), "trailing content"),          # trailing text
        (_row_edit(page, L, "<td>Out</td>", "<td><td></td>Out</td>"), "<td> inside a cell"),   # nested cell
        (_row_edit(page, L, "<td>Out</td>", "<td><del>Out</del></td>"), "<del> inside a cell"),
        (_row_edit(page, L, "<td>Knee</td>", '<td colspan="2">Knee</td>'), "colspan"),
        (_row_edit(page, L, "<td>Knee</td>", "<td>Knee</span></td>"), "unbalanced"),
        (_row_edit(page, L, "<td>Knee</td>", "<td><span>Knee</td>"), "inside a cell"),         # unclosed span
        (_row_edit(page, L, "<td>Knee</td>", "<td>Knee <x</td>"), "unparseable markup"),
        (_row_edit(page, L, "<td>Knee</td>", "<td>Knee<br/></td><span>"), "outside a cell"),
        (_row_edit(page, L, "<td>Out</td>", "<td>Out"), "unsupported row content|row tags"),
        (_row_edit(page, L, "<td>Out</td>", '<td><span style="display: none">Out</span></td>'), "attribute 'style'"),
        (_row_edit(page, L, "<td>Out</td>", "<td hidden>Out</td>"), "attribute 'hidden'"),
    ]
    for bad, msg in cases:
        with pytest.raises(SystemExit, match=msg):
            OI.parse(bad, 4, 2026)


def test_d280_benign_markup_parses_identically():
    """Controls: attributes on rows and cells, nested inline elements, entities, whitespace,
    upper-case cell tags and a '>' inside a quoted attribute leave the parse unchanged."""
    page = _was_like_page()
    clean = OI.parse(page, 4, 2026)
    L = "Xavier Legette"
    variants = [
        page.replace("<tr><td", '<tr>\n  <td', 1),
        _row_edit(page, L, "<td>Out</td>", '<td scope="row"> <span><b>Out</b></span> </td>'),
        _row_edit(page, L, "<td>Knee</td>", "<td>Kn&#101;e</td>\n\t"),
        _row_edit(page, L, "<td>Out</td>", "<TD>Out</TD>"),
        _row_edit(page, L, 'class="nfl-o-cta--link"', 'class="nfl-o-cta--link" aria-label="a > b"'),
        _row_edit(page, L, "<td>Knee</td>", "<td>Knee<br></td>"),
        _row_edit(page, L, 'class="nfl-o-cta--link"', 'CLASS="nfl-o-cta&#45;-link"'),
    ]
    for v in variants:
        pd.testing.assert_frame_equal(OI.parse(v, 4, 2026), clean)


def test_d280_the_header_row_is_validated_the_same_way():
    page = _was_like_page()
    for bad in (page.replace("<th>Game Status</th></tr>", "<th>Game Status</th><td>x</td></tr>", 1),
                page.replace("<th>Player</th>", "x<th>Player</th>", 1),
                page.replace("<thead>", "<thead>x", 1)):
        with pytest.raises(SystemExit, match="columns|unsupported row content"):
            OI.parse(bad, 4, 2026)


# ── D281: audit #22 ───────────────────────────────────────────────────────────

def _hidden_out(page=None, cell='<td><span style="display:n&#111;ne">Out</span></td>'):
    """Audit #22 A1, exactly: a blank status cell gets a span whose ENCODED style hides it
    ('display:n&#111;ne' decodes to display:none). The raw-text guard missed the spelling, so the
    parser read a hidden 'Out' (blank -> Out, active true -> false, predictions changed)."""
    return _row_edit(page or _was_like_page(), "Bryce Young", "<td></td>", cell)


def test_d281_an_encoded_hidden_status_halts_the_parse_refresh_and_gate(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="unsupported attribute 'style' on <span>"):
        OI.parse(_hidden_out(), 4, 2026)
    R = _refresh_world(tmp_path, monkeypatch)
    before = (tmp_path / "injuries.parquet").read_bytes()
    with pytest.raises(SystemExit, match="unsupported attribute 'style'"):
        R.official_step(4, fetch=_fake_fetch(page=_hidden_out()))
    assert (tmp_path / "injuries.parquet").read_bytes() == before
    assert not (tmp_path / OI.HTML_NAME).exists() and not (tmp_path / OI.RECORD_NAME).exists()
    d = _inputs(tmp_path / "g")
    _rewrite(d, page=_hidden_out())
    for req in (True, False):
        with pytest.raises(SystemExit, match="unsupported attribute 'style'"):
            OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=req, cutoff=CUT)


def test_d281_attributes_tags_and_classes_outside_the_allowlist_halt():
    page = _was_like_page()
    wrap = '<div class="d3-o-table--horizontal-scroll">'
    cases = [
        (_hidden_out(cell='<td><span style="visibility:h&#105;dden">Out</span></td>'), "attribute 'style'"),
        (_hidden_out(cell='<td><span style="display:/**/none">Out</span></td>'), "attribute 'style'"),
        (_hidden_out(cell="<td><span STYLE=display:none>Out</span></td>"), "attribute 'style'"),
        (_hidden_out(cell='<td><span class="hidden">Out</span></td>'), "attribute 'class' on <span>"),
        (_hidden_out(cell='<td><a class="hidden">Out</a></td>'), r"unknown class \['hidden'\] on <a>"),
        (_hidden_out(cell='<td><a class="nfl-u-hide-empty">Out</a></td>'), "unknown class"),
        (_hidden_out(cell='<td><span aria-hidden="true">Out</span></td>'), "attribute 'aria-hidden'"),
        (_hidden_out(cell='<td scope="row" tabindex="0" title="x">Out</td>'), "attribute 'title'"),
        (page.replace("<tbody>", '<tbody class="report-body">', 1), "attribute 'class' on <tbody>"),
        (page.replace("<tr><td", '<tr data-x="1"><td', 1), "attribute 'data-x' on <tr>"),
        (page.replace(wrap, '<div class="d3-o-table--horizontal-scroll" style="display:none">', 1),
         "attribute 'style' on <div>"),
        (page.replace(wrap, '<div class="d3-o-table--horizontal-scroll" hidden>', 1), "attribute 'hidden'"),
        (page.replace(wrap, '<div class="d3-o-table--horizontal-scroll x-hide">', 1), r"unknown class \['x-hide'\]"),
        (page.replace(wrap, "<details>" + wrap, 1).replace("</table></div>", "</table></div></details>", 1),
         "unsupported element <details>"),
        (page.replace("</tbody>", '</tbody class="x">', 1), "attributes on </tbody>"),
        (_hidden_out(cell='<td><a class="nfl-c-matchup-strip__team-logo">Out</a></td>'), "unknown class"),
        (page.replace(wrap, "a < b" + wrap, 1), "unparseable markup"),
    ]
    for bad, msg in cases:
        with pytest.raises(SystemExit, match=msg):
            OI.parse(bad, 4, 2026)


def test_d281_allowed_markup_still_parses_identically():
    page = _was_like_page()
    clean = OI.parse(page, 4, 2026)
    for v in (_row_edit(page, "Xavier Legette", 'class="nfl-o-cta--link"', "class='nfl-o-cta&#45;-link'"),
              _row_edit(page, "Xavier Legette", 'class="nfl-o-cta--link"', 'aria-label="Visit &amp; see"'),
              page.replace('<table class="d3-o-table">', '<table class="d3-o-table d3-o-reports--detailed">', 1)):
        pd.testing.assert_frame_equal(OI.parse(v, 4, 2026), clean)
