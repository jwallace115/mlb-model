"""D271 (FWD7a): the forward run's inputs must include each team's most recent game, and
the active universe must be this week's. No parametrize (CLAUDE.md)."""
import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests._fwd_stub import add_fwd6_fixture_inputs, RATINGS_FILES  # noqa: E402

TEAMS = (("KC", "CAR"),)


def _inputs(tmp_path, week=3, played_week=2):
    """An inputs dir as build_bundle copies it, from a fixture refreshed for `week`."""
    root = tmp_path / "repo"
    add_fwd6_fixture_inputs(root, played_week=played_week, teams=TEAMS, target_week=week)
    d = tmp_path / "inputs"
    d.mkdir()
    for f in RATINGS_FILES:
        shutil.copy2(root / "nfl" / "data" / "sim" / "ratings" / f, d / f)
    for f in ("rosters_weekly.parquet", "injuries.parquet"):
        shutil.copy2(root / "nfl" / "data" / "pbp" / f, d / f)
    return d


def _gate(d, week=3, lp=2):
    from nfl.sim.run_forward_v1 import _team_freshness
    return _team_freshness(d, 2026, week, ["CAR", "KC"], {"KC": lp, "CAR": lp})


def test_refreshed_inputs_pass(tmp_path):
    table = _gate(_inputs(tmp_path))
    for t in ("KC", "CAR"):
        assert table[t]["usage"] >= 3 and table[t]["qb_ratings"] >= 3 and table[t]["kickers"] >= 3
        assert table[t]["active_universe_current"] > 0
        assert table[t]["injury_game_statuses"] == 1      # the fixture's one Questionable


def _drop_week(d, fname, team, week=3):
    df = pd.read_parquet(d / fname)
    df[~((df["season"] == 2026) & (df["week"] == week) & (df["team"] == team))].to_parquet(
        d / fname, index=False)


def test_usage_built_without_the_last_game_halts(tmp_path):
    """The D271 defect: a week-3 run whose usage row 3 is missing selects row 2 (built from
    week-1 games). The old rule (>= last played week) passed it."""
    d = _inputs(tmp_path)
    _drop_week(d, "player_usage_weekly.parquet", "KC")
    with pytest.raises(SystemExit, match="KC: usage selected week 2 — built without its last game"):
        _gate(d)


def test_qb_and_kicker_ratings_built_without_the_last_game_halt(tmp_path):
    for fname, label in (("qb_ratings_weekly.parquet", "qb_ratings"),
                         ("kicker_weekly.parquet", "kickers"),
                         ("team_ratings_weekly.parquet", "team_ratings"),
                         ("tendencies_weekly.parquet", "tendencies")):
        d = _inputs(tmp_path / label)
        _drop_week(d, fname, "CAR")
        with pytest.raises(SystemExit, match=f"CAR: {label} selected week"):
            _gate(d)


def test_active_universe_not_rebuilt_after_the_injury_report_halts(tmp_path):
    """Rico Dowdle (OUT) was simulated on TNF: the active universe predated the report."""
    d = _inputs(tmp_path)
    ros = pd.read_parquet(d / "rosters_weekly.parquet")
    au = pd.read_parquet(d / "active_universe_weekly.parquet")
    act = au[(au["season"] == 2026) & (au["week"] == 3) & (au["team"] == "KC") & au["active_flag"]]
    inj = pd.read_parquet(d / "injuries.parquet")
    listed = set(inj.loc[inj["week"] == 3, "gsis_id"])
    pid = act[~act["player_id"].isin(listed)].iloc[0]["player_id"]
    inj = pd.concat([inj, pd.DataFrame([{"season": 2026, "week": 3, "team": "KC",
                                          "gsis_id": pid, "report_status": "Out"}])],
                    ignore_index=True)
    inj.to_parquet(d / "injuries.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: week-3 active universe was not built from this week"):
        _gate(d)
    assert len(ros)


def test_active_universe_copied_forward_halts(tmp_path):
    """usage.py copies the last roster week forward; a copied week must not pass."""
    d = _inputs(tmp_path)
    ros = pd.read_parquet(d / "rosters_weekly.parquet")
    r3 = ros[(ros["season"] == 2026) & (ros["week"] == 3) & (ros["team"] == "CAR")]
    ros = ros.drop(r3.index[:3])          # this week's roster differs from the copy
    ros.to_parquet(d / "rosters_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: week-3 active universe was not built"):
        _gate(d)


def test_missing_rosters_or_injury_report_halts(tmp_path):
    d = _inputs(tmp_path / "r")
    ros = pd.read_parquet(d / "rosters_weekly.parquet")
    ros[~((ros["week"] == 3) & (ros["team"] == "KC"))].to_parquet(d / "rosters_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: no week-3 rosters in the bundle"):
        _gate(d)
    d = _inputs(tmp_path / "i")
    inj = pd.read_parquet(d / "injuries.parquet")
    inj[~((inj["week"] == 3) & (inj["team"] == "CAR"))].to_parquet(d / "injuries.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: no week-3 injury report in the bundle"):
        _gate(d)


def test_injuries_are_a_required_bundle_input():
    from nfl.sim.run_forward_v1 import PBP_DIR_FILES, RECORD_ONLY_FILES
    assert "injuries.parquet" in PBP_DIR_FILES and "injuries.parquet" not in RECORD_ONLY_FILES


# ── ratings.py: the entering-week row ───────────────────────────────────────────

def test_entering_weeks_adds_the_next_week_only():
    from nfl.sim.ratings import _entering_weeks
    assert _entering_weeks(pd.Series([1, 2, 3, 3])) == [1, 2, 3, 4]
    assert _entering_weeks(pd.Series(range(1, 23))) == list(range(1, 23))   # cap 22
    assert _entering_weeks(pd.Series([], dtype=int)) == []


def test_qb_and_kicker_loops_use_the_entering_weeks():
    """Both loops that used `sorted(<df>["week"].unique())` now use _entering_weeks."""
    src = (ROOT / "nfl" / "sim" / "ratings.py").read_text()
    tree = ast.parse(src)
    fors = [n for n in ast.walk(tree) if isinstance(n, ast.For)
            and isinstance(n.iter, ast.Call) and getattr(n.iter.func, "id", None) == "_entering_weeks"]
    assert len(fors) == 2, len(fors)
    assert 'for w in sorted(sq["week"].unique())' not in src
    assert 'for w in sorted(sf["week"].unique())' not in src


# ── refresh_inputs.py ───────────────────────────────────────────────────────────

def test_splice_keeps_history_and_takes_the_current_season():
    from nfl.sim.refresh_inputs import splice
    old = pd.DataFrame({"season": pd.Series([2025, 2025, 2026], dtype="int32"),
                        "week": [1, 2, 1], "x": [0.1, 0.2, 0.3]})
    new = pd.DataFrame({"season": [2025, 2026, 2026], "week": [1, 1, 2],
                        "x": [9.9, 0.31, 0.4], "extra": [1, 2, 3]})
    out = splice(old, new)
    assert list(out.columns) == ["season", "week", "x"]
    assert out["season"].dtype == old["season"].dtype
    assert out[out["season"] == 2025]["x"].tolist() == [0.1, 0.2]          # history kept
    assert out[out["season"] == 2026]["x"].tolist() == [0.31, 0.4]         # current rebuilt


def test_refresh_restores_the_tables_when_a_step_fails(tmp_path, monkeypatch):
    import nfl.sim.refresh_inputs as R
    import nfl.sim.calibration as C
    from nfl.sim.calibration import FIT_INPUT_FILES
    root = tmp_path / "repo"
    rd = root / "nfl" / "data" / "sim" / "ratings"
    rd.mkdir(parents=True)
    for f in FIT_INPUT_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    before = {f: hashlib.sha256((rd / f).read_bytes()).hexdigest() for f in FIT_INPUT_FILES}
    params = root / "params_v1.json"
    params.write_text("{}")
    freeze = root / "FREEZE_v1.json"
    freeze.write_text(json.dumps({"usage_fingerprint": "abc"}))
    monkeypatch.setattr(R, "ROOT", root)
    monkeypatch.setattr(R, "RATINGS", rd)
    monkeypatch.setattr(R, "PARAMS", params)
    monkeypatch.setattr(R, "FREEZE", freeze)
    monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
    monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")

    def boom(script):
        (rd / "player_usage_weekly.parquet").write_bytes(b"half-written")
        raise RuntimeError(f"{script} failed")
    monkeypatch.setattr(R, "_run", boom)
    with pytest.raises(RuntimeError, match="pull_nflverse_inputs.py failed"):
        R.main(["--week", "4"])
    assert {f: hashlib.sha256((rd / f).read_bytes()).hexdigest() for f in FIT_INPUT_FILES} == before


def test_refresh_refuses_tables_that_are_not_the_frozen_fit():
    import nfl.sim.refresh_inputs as R
    src = Path(R.__file__).read_text()
    assert "BEFORE the refresh" in src and "after the splice" in src


# ── D272 (audit #14) ────────────────────────────────────────────────────────────

def _au_week(d, team, week=3):
    au = pd.read_parquet(d / "active_universe_weekly.parquet")
    return au, au[(au["season"] == 2026) & (au["week"] == week) & (au["team"] == team)]


def test_duplicate_active_universe_rows_halt_in_either_order(tmp_path):
    """Audit #14 A2: an OUT player with one inactive row passed; prepending a duplicate
    ACTIVE row for him still passed (last row wins) while the engine includes any active
    row. Duplicate keys are now refused, whichever row comes first."""
    for order in ("active_first", "active_last"):
        d = _inputs(tmp_path / order)
        au, wk = _au_week(d, "KC")
        pid = wk[wk["active_flag"]].iloc[0]["player_id"]
        row = au[(au["season"] == 2026) & (au["week"] == 3) & (au["player_id"] == pid)].copy()
        flip = row.copy()
        flip["active_flag"] = False
        parts = [row, au, flip] if order == "active_first" else [flip, au, row]
        pd.concat(parts, ignore_index=True).to_parquet(d / "active_universe_weekly.parquet", index=False)
        with pytest.raises(SystemExit, match="KC: week-3 active universe has duplicate rows"):
            _gate(d)


def test_missing_or_non_boolean_active_flags_halt(tmp_path):
    d = _inputs(tmp_path)
    au, wk = _au_week(d, "CAR")
    au = au.copy()
    au["active_flag"] = au["active_flag"].astype(object)
    au.loc[wk.index[0], "active_flag"] = None
    au.to_parquet(d / "active_universe_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: week-3 active universe has non-boolean or missing"):
        _gate(d)


def test_doubtful_is_excluded_like_out(tmp_path):
    """Survivor: excluding only Out, not Doubtful."""
    d = _inputs(tmp_path)
    _, wk = _au_week(d, "KC")
    inj = pd.read_parquet(d / "injuries.parquet")
    listed = set(inj.loc[inj["week"] == 3, "gsis_id"])
    pid = wk[wk["active_flag"] & ~wk["player_id"].isin(listed)].iloc[0]["player_id"]
    pd.concat([inj, pd.DataFrame([{"season": 2026, "week": 3, "team": "KC", "gsis_id": pid,
                                   "report_status": "Doubtful"}])], ignore_index=True
              ).to_parquet(d / "injuries.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: week-3 active universe was not built from this week"):
        _gate(d)


def test_stale_situational_tendencies_alone_halt(tmp_path):
    """Survivor: situational tendencies dropped from the gate."""
    d = _inputs(tmp_path)
    _drop_week(d, "tendencies_situational_weekly.parquet", "KC")
    with pytest.raises(SystemExit, match="KC: tendencies_situational selected week"):
        _gate(d)


def test_entering_weeks_adds_22_after_21():
    """Survivor: cap at 21 instead of 22."""
    from nfl.sim.ratings import _entering_weeks
    assert _entering_weeks(pd.Series(range(1, 22))) == list(range(1, 23))


def test_splice_preserves_every_earlier_season_exactly():
    """Survivor: dropping pre-2021 rows."""
    from nfl.sim.refresh_inputs import splice
    old = pd.DataFrame({"season": [2020, 2021, 2025, 2026], "week": [22, 1, 18, 1], "x": [1.0, 2.0, 3.0, 4.0]})
    new = pd.DataFrame({"season": [2020, 2026, 2026], "week": [22, 1, 2], "x": [9.0, 4.5, 5.0]})
    out = splice(old, new)
    assert out[out["season"] < 2026].reset_index(drop=True).equals(old[old["season"] < 2026].reset_index(drop=True))


def test_refresh_restores_all_eight_tables(tmp_path, monkeypatch):
    """Survivor: restoring only player_usage_weekly. Corrupt two tables, verify all eight."""
    import nfl.sim.refresh_inputs as R
    import nfl.sim.calibration as C
    from nfl.sim.calibration import FIT_INPUT_FILES
    root = tmp_path / "repo"
    rd = root / "nfl" / "data" / "sim" / "ratings"
    rd.mkdir(parents=True)
    for f in FIT_INPUT_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    before = {f: hashlib.sha256((rd / f).read_bytes()).hexdigest() for f in FIT_INPUT_FILES}
    (root / "params_v1.json").write_text("{}")
    (root / "FREEZE_v1.json").write_text(json.dumps({"usage_fingerprint": "abc"}))
    monkeypatch.setattr(R, "ROOT", root)
    monkeypatch.setattr(R, "RATINGS", rd)
    monkeypatch.setattr(R, "PARAMS", root / "params_v1.json")
    monkeypatch.setattr(R, "FREEZE", root / "FREEZE_v1.json")
    monkeypatch.setattr(R, "PBP", root / "nfl" / "data" / "pbp")
    monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
    monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")
    monkeypatch.setattr(R, "snapshot_schedule", lambda: None)

    def boom(script):
        for f in ("team_ratings_weekly.parquet", "kicker_weekly.parquet"):
            (rd / f).write_bytes(b"half-written")
        raise RuntimeError(f"{script} failed")
    monkeypatch.setattr(R, "_run", boom)
    with pytest.raises(RuntimeError):
        R.main(["--week", "4"])
    assert {f: hashlib.sha256((rd / f).read_bytes()).hexdigest() for f in FIT_INPUT_FILES} == before


def _depth_world(tmp_path, with_week4_pbp_date):
    """Rosters/injuries/depth for KC weeks 1-4; PBP has weeks 1-3 (optionally plus an
    outcome-free week-4 row carrying only its date); the schedule snapshot has week 4."""
    import nfl.sim.usage as U
    d = tmp_path / ("with" if with_week4_pbp_date else "without")
    d.mkdir()
    dates = {1: "2026-09-10", 2: "2026-09-17", 3: "2026-09-24", 4: "2026-10-01"}
    pbp = [{"season": 2026, "week": w, "game_date": dates[w], "game_id": f"g{w}"} for w in (1, 2, 3)]
    if with_week4_pbp_date:
        pbp.append({"season": 2026, "week": 4, "game_date": dates[4], "game_id": "g4"})
    pd.DataFrame(pbp).to_parquet(d / "pbp_2026.parquet", index=False)
    # the snapshot covers the whole regular season, as refresh_inputs.snapshot_schedule requires
    sched_dates = {**dates, **{w: str((pd.Timestamp(dates[4]) + pd.Timedelta(days=7 * (w - 4))).date())
                               for w in range(5, 19)}}
    pd.DataFrame([{"season": 2026, "week": w, "gameday": sched_dates[w], "gametime": "20:15",
                   "game_type": "REG", "home_team": "KC", "away_team": "CAR",
                   "game_id": f"g{w}"} for w in range(1, 19)]).to_parquet(d / "schedules_2026.parquet", index=False)
    players = [("00-1", "WR"), ("00-2", "WR"), ("00-3", "RB")]
    rosters = pd.DataFrame([{"season": 2026, "week": w, "team": "KC", "gsis_id": p, "position": pos,
                             "status": "ACT", "full_name": p} for w in (1, 2, 3, 4) for p, pos in players])
    injuries = pd.DataFrame([{"season": 2026, "week": 4, "team": "KC", "gsis_id": "00-3",
                              "report_status": "Questionable"}])
    depth = pd.DataFrame([{"season": None, "week": None, "club_code": None, "depth_team": None,
                           "team": "KC", "gsis_id": p, "position": pos, "pos_abb": pos,
                           "pos_rank": r, "dt": "2026-09-29T12:00:00Z"}
                          for r, (p, pos) in enumerate(players, start=1)])
    return d, U, rosters, injuries, depth


def test_live_week_depth_ranks_do_not_depend_on_an_outcome_free_pbp_date(tmp_path, monkeypatch):
    """Audit #14 A1: week-4 depth ranks were empty unless the PBP held a week-4 date; the
    same pre-kickoff information must give the same inputs either way."""
    outs = []
    for flag in (False, True):
        d, U, rosters, injuries, depth = _depth_world(tmp_path, flag)
        monkeypatch.setattr(U, "PBP_DIR", d)
        outs.append(U.build_active_universe(rosters, injuries, depth)
                    .sort_values(["season", "week", "team", "player_id"]).reset_index(drop=True))
    w4 = outs[0][outs[0]["week"] == 4]
    assert w4["depth_order"].notna().all() and len(w4) == 3
    assert outs[0].equals(outs[1])


def test_week_cutoffs_use_one_convention_for_pbp_and_schedule_weeks(tmp_path, monkeypatch):
    d, U, *_ = _depth_world(tmp_path, False)
    monkeypatch.setattr(U, "PBP_DIR", d)
    cut = U._week_cutoffs([2026])
    assert cut[(2026, 4)] == pd.Timestamp("2026-10-01", tz="UTC")       # from the schedule
    assert cut[(2026, 3)] == pd.Timestamp("2026-09-24", tz="UTC")       # from the PBP


def test_refresh_snapshots_the_schedule_before_building_and_archives_the_refresh(tmp_path, monkeypatch):
    """D272: the schedule snapshot is written BEFORE usage.py (the builders' only schedule),
    and a successful refresh archives its exact source and table bytes with a manifest
    naming the declared input version."""
    import nfl.sim.refresh_inputs as R
    import nfl.sim.calibration as C
    import nfl.sim.pull_pbp as P
    from nfl.sim.calibration import FIT_INPUT_FILES
    root = tmp_path / "repo"
    rd = root / "nfl" / "data" / "sim" / "ratings"
    pb = root / "nfl" / "data" / "pbp"
    rd.mkdir(parents=True)
    pb.mkdir(parents=True)
    for f in FIT_INPUT_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    for f in R.SOURCES:
        (pb / f).write_bytes(f"source {f}".encode())
    (root / "params_v1.json").write_text("{}")
    (root / "FREEZE_v1.json").write_text(json.dumps({"usage_fingerprint": "abc"}))
    for k, v in (("ROOT", root), ("RATINGS", rd), ("PBP", pb), ("PARAMS", root / "params_v1.json"),
                 ("FREEZE", root / "FREEZE_v1.json")):
        monkeypatch.setattr(R, k, v)
    monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
    monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")
    calls = []
    monkeypatch.setattr(R, "_run", lambda script: calls.append(script))
    monkeypatch.setattr(R, "snapshot_schedule", lambda: calls.append("schedule"))
    monkeypatch.setattr(R, "official_step", lambda week: calls.append(f"official {week}"))   # D277
    monkeypatch.setattr(P, "pull_season", lambda s: pd.DataFrame({"week": [1, 2, 3]}))
    monkeypatch.setattr(P, "write_safe", lambda df, path: calls.append("pbp"))
    monkeypatch.setattr(R, "freshness_report", lambda week: True)
    assert R.main(["--week", "4"]) == 0
    assert calls == ["pull_nflverse_inputs.py", "schedule", "official 4", "pbp", "usage.py", "ratings.py"]
    [backup] = list((tmp_path / "mlb-model-archive" / "nfl_ratings_backups").iterdir())
    man = json.loads((backup / "refreshed" / "refresh_manifest.json").read_text())
    assert man["input_version"] == R.INPUT_VERSION == "D277-v7" and man["week"] == 4
    for f in R.SOURCES:
        assert (backup / "refreshed" / f).read_bytes() == (pb / f).read_bytes()
        assert man["files"][f"sources/{f}"] == hashlib.sha256((pb / f).read_bytes()).hexdigest()
    for f in FIT_INPUT_FILES:
        assert man["files"][f"tables/{f}"] == hashlib.sha256((rd / f).read_bytes()).hexdigest()
    assert "schedules_2026.parquet" in R.SOURCES


def _runbook():
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_runbook", ROOT / "research" / "nfl_sim" / "make_runbook.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_runbook_gives_an_early_sunday_game_its_own_window():
    """Audit #14 A3: a 09:30 ET Sunday game (13:30Z) precedes the VM's 16:00Z pull and must
    not share the main window; 13:00/16:25/20:20 ET games share one."""
    M = _runbook()
    g = lambda gid, day, t: {"game_id": gid, "away_team": gid[:3], "home_team": gid[4:],
                             "gameday": day, "gametime": t}
    df = pd.DataFrame([g("IND@WAS", "2026-10-04", "09:30"), g("MIN@CHI", "2026-10-04", "13:00"),
                       g("DEN@LAC", "2026-10-04", "16:25"), g("SF@LAR", "2026-10-04", "20:20"),
                       g("ATL@NO.", "2026-10-05", "20:15")])
    wins = [[x["game_id"] for x in w] for w in M.group_windows(df)]
    assert wins == [["IND@WAS"], ["MIN@CHI", "DEN@LAC", "SF@LAR"], ["ATL@NO."]]
    assert M._early_sunday(M.game_kick_utc(df.iloc[0])) and not M._early_sunday(M.game_kick_utc(df.iloc[1]))
    # Monday has only the 23:45Z VM slot: nothing on Monday before a 23:30Z start
    from datetime import datetime, timezone
    slot = M.latest_vm_slot_before(datetime(2026, 10, 5, 23, 30, tzinfo=timezone.utc))
    assert slot == datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc)


def test_nullable_boolean_flag_with_na_halts(tmp_path):
    """Survivor: dtype check only (a nullable boolean column with <NA> is a bool dtype)."""
    d = _inputs(tmp_path)
    au, wk = _au_week(d, "CAR")
    au = au.copy()
    au["active_flag"] = au["active_flag"].astype("boolean")
    au.loc[wk.index[0], "active_flag"] = pd.NA
    au.to_parquet(d / "active_universe_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: week-3 active universe has non-boolean or missing"):
        _gate(d)


def test_week_cutoffs_take_only_the_snapshot_season(tmp_path, monkeypatch):
    """Survivor: the season filter on the schedule snapshot removed."""
    d, U, *_ = _depth_world(tmp_path, False)
    sch = pd.read_parquet(d / "schedules_2026.parquet")
    stray = sch.iloc[[0]].assign(season=2025, week=5, gameday="2025-10-02")
    pd.concat([stray, sch], ignore_index=True).to_parquet(d / "schedules_2026.parquet", index=False)
    monkeypatch.setattr(U, "PBP_DIR", d)
    cut = U._week_cutoffs([2026])
    assert cut[(2026, 5)] == pd.Timestamp("2026-10-08", tz="UTC")      # not the stray 2025 date
    assert cut[(2026, 4)] == pd.Timestamp("2026-10-01", tz="UTC")


def test_layer3_qb_uses_the_snapshot_cutoffs_and_halts_without_one(tmp_path, monkeypatch):
    """D272: the live week's depth-chart QB comes from the same cutoff whether or not the PBP
    holds a week-4 date; with no archived schedule snapshot the build halts."""
    got = []
    for flag in (False, True):
        d, U, rosters, injuries, depth = _depth_world(tmp_path, flag)
        qb = depth.iloc[[0]].assign(gsis_id="00-9", position="QB", pos_abb="QB", pos_rank=1)
        monkeypatch.setattr(U, "PBP_DIR", d)
        st = U.derive_starting_qbs(pd.concat([depth, qb], ignore_index=True), None)
        got.append(st.get((2026, 4, "KC")))
    assert got[0] == got[1] == {"gsis_id": "00-9", "source": "depth_chart"}
    (d / "schedules_2026.parquet").unlink()
    with pytest.raises(RuntimeError, match="no valid week cutoff for season 2026 weeks \\[5, 6"):
        U.derive_starting_qbs(pd.concat([depth, qb], ignore_index=True), None)


def test_refresh_exits_1_with_tables_installed_when_teams_are_not_ready(tmp_path, monkeypatch):
    """D272: exit 1 = refreshed and INSTALLED, some teams not ready (not a failure, not 0)."""
    import nfl.sim.refresh_inputs as R
    import nfl.sim.calibration as C
    import nfl.sim.pull_pbp as P
    from nfl.sim.calibration import FIT_INPUT_FILES
    root = tmp_path / "repo"
    rd, pb = root / "nfl" / "data" / "sim" / "ratings", root / "nfl" / "data" / "pbp"
    rd.mkdir(parents=True)
    pb.mkdir(parents=True)
    for f in FIT_INPUT_FILES:
        shutil.copy2(ROOT / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    for f in R.SOURCES:
        (pb / f).write_bytes(b"x")
    (root / "params_v1.json").write_text("{}")
    (root / "FREEZE_v1.json").write_text(json.dumps({"usage_fingerprint": "abc"}))
    for k, v in (("ROOT", root), ("RATINGS", rd), ("PBP", pb), ("PARAMS", root / "params_v1.json"),
                 ("FREEZE", root / "FREEZE_v1.json")):
        monkeypatch.setattr(R, k, v)
    monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
    monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")
    monkeypatch.setattr(R, "_run", lambda script: None)
    monkeypatch.setattr(R, "snapshot_schedule", lambda: None)
    monkeypatch.setattr(R, "official_step", lambda week: None)   # D277 (network)
    monkeypatch.setattr(P, "pull_season", lambda s: pd.DataFrame({"week": [1]}))
    monkeypatch.setattr(P, "write_safe", lambda df, path: None)
    monkeypatch.setattr(R, "freshness_report", lambda week: False)
    assert R.main(["--week", "4"]) == 1
    [backup] = list((tmp_path / "mlb-model-archive" / "nfl_ratings_backups").iterdir())
    assert (backup / "refreshed" / "refresh_manifest.json").exists()
