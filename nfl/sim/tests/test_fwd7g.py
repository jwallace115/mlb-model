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


def _page(units=None, week=4):
    units = units if units is not None else [_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS)]
    return (f'<html><body><h2 class="x">Injuries - WEEK {week}</h2><h2>SUNDAY, OCTOBER 4TH</h2>'
            + "".join(units) + "</body></html>")


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
    o = OI.parse(_page(), 4)
    assert o["team"].tolist() == ["CAR"] * 3 + ["KC"] * 2
    assert o["opp"].tolist() == ["KC"] * 3 + ["CAR"] * 2
    assert o["player"].tolist()[3] == "D'Andre Swift"          # HTML entities decoded
    assert [None if pd.isna(v) else v for v in o["game_status"]] == [None, "Out", "Out", "Questionable", "Doubtful"]


def test_parse_maps_nflcom_codes_and_rejects_unknown_ones():
    o = OI.parse(_page([_unit(("AZ", "Cardinals"), ("LAR", "Rams"), AWAY_ROWS[:1], HOME_ROWS[:1])]), 4)
    assert set(o["team"]) == {"ARI", "LA"}
    with pytest.raises(SystemExit, match="unknown team code 'XX'"):
        OI.parse(_page([_unit(("XX", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS)]), 4)


def test_parse_halts_on_anything_but_the_expected_page():
    with pytest.raises(SystemExit, match="not the week-4 report"):
        OI.parse(_page(week=5), 4)
    with pytest.raises(SystemExit, match="no team sections"):
        OI.parse(_page([]), 4)
    with pytest.raises(SystemExit, match="lists KC twice"):
        OI.parse(_page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS, HOME_ROWS),
                        _unit(("KC", "Chiefs"), ("DEN", "Broncos"), HOME_ROWS, [])]), 4)
    bad_title = _page().replace("<span>Chiefs</span>", "<span>Broncos</span>")
    with pytest.raises(SystemExit, match="do not match the matchup"):
        OI.parse(bad_title, 4)
    with pytest.raises(SystemExit, match="columns"):
        OI.parse(_page().replace("<th>Game Status</th>", "<th>Status</th>", 1), 4)
    with pytest.raises(SystemExit, match="unknown game status 'Inactive'"):
        OI.parse(_page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"),
                              [("Bryce Young", "QB", "", "", "Inactive")], HOME_ROWS)]), 4)
    with pytest.raises(SystemExit, match="malformed row"):
        OI.parse(_page().replace("<td>QB</td>", "", 1), 4)


# ── identify ──────────────────────────────────────────────────────────────────

def test_rows_are_identified_from_that_teams_week_roster():
    m = OI.map_ids(OI.parse(_page(), 4), _rosters(), 2026, 4)
    assert m["gsis_id"].tolist() == ["00-c1", "00-c2", "00-c3", "00-k1", "00-k2"]  # Jr. dropped


def test_an_unidentified_skill_player_halts_and_a_non_skill_one_is_not_written():
    r = _rosters()
    with pytest.raises(SystemExit, match="KC D'Andre Swift \\(RB\\): unmatched"):
        OI.map_ids(OI.parse(_page(), 4), r[r["gsis_id"] != "00-k1"], 2026, 4)
    m = OI.map_ids(OI.parse(_page(), 4), r[r["gsis_id"] != "00-c3"], 2026, 4)   # Lewis, G
    assert m.loc[m["player"] == "Damien Lewis", "gsis_id"].isna().all()
    rows = OI.injury_rows(m, 2026, 4, "2026-10-03T01:00:00+00:00")
    assert "Damien Lewis" not in rows["full_name"].tolist() and len(rows) == 4


def test_the_same_name_on_another_team_or_week_never_matches():
    r = _rosters()
    moved = r.copy()
    moved.loc[moved["gsis_id"] == "00-k1", "team"] = "DEN"
    with pytest.raises(SystemExit, match="D'Andre Swift"):
        OI.map_ids(OI.parse(_page(), 4), moved, 2026, 4)
    with pytest.raises(SystemExit, match="D'Andre Swift"):
        OI.map_ids(OI.parse(_page(), 4), r.assign(week=3), 2026, 4)


def test_ambiguous_names_and_a_player_listed_twice_halt():
    two = _rosters(extra=[("KC", "00-k9", "D'Andre Swift", "RB")])
    with pytest.raises(SystemExit, match="ambiguous"):
        OI.map_ids(OI.parse(_page(), 4), two, 2026, 4)
    twice = _page([_unit(("CAR", "Panthers"), ("KC", "Chiefs"), AWAY_ROWS + AWAY_ROWS[1:2], HOME_ROWS)])
    with pytest.raises(SystemExit, match="listed more than once"):
        OI.map_ids(OI.parse(twice, 4), _rosters(), 2026, 4)


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
    m = OI.map_ids(OI.parse(_page(), 4), _rosters(), 2026, 4)
    rows = OI.injury_rows(m, 2026, 4, "2026-10-03T01:29:28+00:00")
    feed = _feed()
    new = OI.overlay(feed, rows, 2026, 4)
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
    d.mkdir()
    body = (page or _page()).encode()
    rec = {"url": "u", "season": 2026, "week": 4, "fetched_utc": fetched, "http_status": 200,
           "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    OI.write_capture(body, rec, d)
    ros = _rosters()
    ros.to_parquet(d / "rosters_weekly.parquet", index=False)
    m = OI.map_ids(OI.parse(body.decode(), 4), ros, 2026, 4)
    inj = OI.overlay(_feed(), OI.injury_rows(m, 2026, 4, fetched), 2026, 4)
    if edit:
        inj = edit(inj)
    inj.to_parquet(d / "injuries.parquet", index=False)
    return d


def test_gate_verifies_and_reconciles_each_team(tmp_path):
    per = OI.check(_inputs(tmp_path), 2026, 4, ["CAR", "KC"], SCHED, require=True)
    assert per["CAR"]["official_verified"] and per["KC"]["official_verified"]
    assert per["CAR"]["official_game_statuses"] == 2 and per["KC"]["official_rows"] == 2
    assert per["KC"]["final_report_deadline_utc"] == "2026-10-02T20:00:00+00:00"


def test_gate_halts_a_primary_on_a_page_fetched_before_the_final_report(tmp_path):
    d = _inputs(tmp_path, fetched="2026-10-02T19:59:00+00:00")
    with pytest.raises(SystemExit, match="(?s)HALT \\(D277\\).*fetched 2026-10-02T19:59:00\\+00:00 before"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True)
    per = OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False)       # a pilot records it
    assert not per["KC"]["official_verified"] and "before the final-report deadline" in per["KC"]["official_reason"]


def test_gate_halts_when_the_consumed_rows_differ_from_the_page(tmp_path):
    def flip(inj):
        inj.loc[(inj["gsis_id"] == "00-c2") & (inj["week"] == 4), "report_status"] = None
        return inj
    with pytest.raises(SystemExit, match="CAR: consumed injury rows \\(3\\) differ from the official page \\(3\\)"):
        OI.check(_inputs(tmp_path, edit=flip), 2026, 4, ["CAR", "KC"], SCHED, require=True)


def test_gate_halts_on_a_team_missing_from_the_page_or_changed_bytes(tmp_path):
    d = _inputs(tmp_path)
    sched = pd.concat([SCHED, SCHED.assign(game_id="g2", home_team="DEN", away_team="LV")])
    with pytest.raises(SystemExit, match="DEN: no section on the official page"):
        OI.check(d, 2026, 4, ["CAR", "KC", "DEN"], sched, require=True)
    (d / OI.HTML_NAME).write_bytes((d / OI.HTML_NAME).read_bytes() + b" ")
    with pytest.raises(SystemExit, match="does not match the sha256"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False)


def test_gate_halts_on_a_record_for_another_week_or_no_capture(tmp_path):
    d = _inputs(tmp_path)
    rec = json.loads((d / OI.RECORD_NAME).read_text())
    (d / OI.RECORD_NAME).write_text(json.dumps(dict(rec, week=3)))
    with pytest.raises(SystemExit, match="record is for season 2026 week 3"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=False)
    (d / OI.RECORD_NAME).unlink()
    with pytest.raises(SystemExit, match="(?s)HALT \\(D277\\).*no official injury report"):
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True)
    assert OI.check(d, 2026, 4, ["KC"], SCHED, require=False)["KC"]["official_verified"] is False


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
        return body, {"url": "u", "season": season, "week": week, "fetched_utc": fetched,
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
    per = OI.check(d, 2026, 4, ["CAR", "KC"], SCHED, require=True)
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
    rec = {"url": "u", "season": 2026, "week": 3, "fetched_utc": "2099-01-01T00:00:00+00:00",
           "http_status": 200, "bytes": len(page), "sha256": hashlib.sha256(page).hexdigest()}
    OI.write_capture(page, rec, pb)
    m = OI.map_ids(OI.parse(page.decode(), 3), pd.read_parquet(pb / "rosters_weekly.parquet"), 2026, 3)
    inj = pd.read_parquet(pb / "injuries.parquet")
    OI.overlay(inj, OI.injury_rows(m, 2026, 3, rec["fetched_utc"]), 2026, 3).to_parquet(
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
        OI.check(d, 2026, 4, ["CAR", "KC"], SCHED.assign(home_team="DEN"), require=True)
    with pytest.raises(SystemExit, match="KC: 2 week-4 schedule games"):
        OI.check(d, 2026, 4, ["CAR", "KC"], pd.concat([SCHED, SCHED.assign(away_team="LV")]), require=True)


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
