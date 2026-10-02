"""D273 (FWD7c): ChatGPT audit #15 — invalid week cutoffs, the depth-layer gate, and audit
#15's seven focused survivors. No parametrize (CLAUDE.md)."""
import hashlib
import json
import shutil
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd7a import _depth_world, _inputs, _au_week, _gate, _runbook  # noqa: E402
from nfl.sim.tests.test_fwd6f import _run, _rt, _ident  # noqa: E402


def _build(tmp_path, monkeypatch, pbp_extra=None, sched_edit=None, tag="x"):
    """build_active_universe on the KC depth world; optionally add PBP rows / edit the schedule."""
    (tmp_path / tag).mkdir()
    d, U, rosters, injuries, depth = _depth_world(tmp_path / tag, False)
    if pbp_extra is not None:
        p = pd.read_parquet(d / "pbp_2026.parquet")
        pd.concat([p, pd.DataFrame(pbp_extra)], ignore_index=True).to_parquet(d / "pbp_2026.parquet", index=False)
    if sched_edit is not None:
        sched_edit(d / "schedules_2026.parquet")
    monkeypatch.setattr(U, "PBP_DIR", d)
    return (U.build_active_universe(rosters, injuries, depth)
            .sort_values(["season", "week", "team", "player_id"]).reset_index(drop=True)), U, d


# ── A1: a null / unparseable PBP date ─────────────────────────────────────────

def test_null_pbp_date_leaves_the_build_unchanged(tmp_path, monkeypatch):
    """Audit #15 A1: an outcome-free week-4 PBP row with game_date=None recorded (2026,4): NaT,
    suppressing the valid schedule date; week-4 depth ranks vanished and the gate passed.
    Now only valid dates count and the result equals the clean build."""
    clean, *_ = _build(tmp_path, monkeypatch, tag="clean")
    for bad in (None, "not-a-date"):
        got, *_ = _build(tmp_path, monkeypatch, tag=f"bad{bad}",
                         pbp_extra=[{"season": 2026, "week": 4, "game_date": bad, "game_id": "g4"}])
        assert got.equals(clean), bad
    w4 = clean[clean["week"] == 4]
    assert w4["depth_order"].notna().all()


def test_null_pbp_date_cannot_reach_layer3(tmp_path, monkeypatch):
    out = []
    for tag, extra in (("c", None), ("n", [{"season": 2026, "week": 4, "game_date": None, "game_id": "g4"}])):
        (tmp_path / tag).mkdir()
        d, U, rosters, injuries, depth = _depth_world(tmp_path / tag, False)
        if extra:
            p = pd.read_parquet(d / "pbp_2026.parquet")
            pd.concat([p, pd.DataFrame(extra)], ignore_index=True).to_parquet(d / "pbp_2026.parquet", index=False)
        monkeypatch.setattr(U, "PBP_DIR", d)
        qb = depth.iloc[[0]].assign(gsis_id="00-9", position="QB", pos_abb="QB", pos_rank=1)
        out.append(U.derive_starting_qbs(pd.concat([depth, qb], ignore_index=True), None))
    assert out[0] == out[1] and out[0][(2026, 4, "KC")]["gsis_id"] == "00-9"


def test_incomplete_snapshot_halts_instead_of_skipping_the_depth_layer(tmp_path, monkeypatch):
    """A present snapshot WITHOUT the week being built is not coverage: HALT."""
    def drop_week4(p):
        s = pd.read_parquet(p)
        s[s["week"] != 4].to_parquet(p, index=False)
    with pytest.raises(RuntimeError, match="build_active_universe: no valid week cutoff for season 2026 weeks \\[4\\]"):
        _build(tmp_path, monkeypatch, tag="inc", sched_edit=drop_week4)

    def null_week4(p):
        s = pd.read_parquet(p)
        s.loc[s["week"] == 4, "gameday"] = None
        s.to_parquet(p, index=False)
    with pytest.raises(RuntimeError, match="weeks \\[4\\]"):
        _build(tmp_path, monkeypatch, tag="nul", sched_edit=null_week4)


def test_cutoff_is_the_earliest_valid_date_of_the_week(tmp_path, monkeypatch):
    """Survivor: max instead of min. Thursday and Sunday dates in one week -> Thursday."""
    d, U, *_ = _depth_world(tmp_path, False)
    p = pd.read_parquet(d / "pbp_2026.parquet")
    p = pd.concat([p, pd.DataFrame([{"season": 2026, "week": 3, "game_date": "2026-09-27", "game_id": "g3b"}])],
                  ignore_index=True)
    p.to_parquet(d / "pbp_2026.parquet", index=False)
    monkeypatch.setattr(U, "PBP_DIR", d)
    assert U._week_cutoffs([2026])[(2026, 3)] == pd.Timestamp("2026-09-24", tz="UTC")
    # a season without a snapshot (history): the earliest valid PBP date, Thursday
    pd.DataFrame([{"season": 2025, "week": 3, "game_date": dd, "game_id": f"h{i}"}
                  for i, dd in enumerate(("2025-09-21", "2025-09-18", None, "2025-09-22"))]
                 ).to_parquet(d / "pbp_2025.parquet", index=False)
    assert U._week_cutoffs([2025]) == {(2025, 3): pd.Timestamp("2025-09-18", tz="UTC")}
    # and an earlier schedule date than the PBP's wins (live week and rebuilt week agree)
    s = pd.read_parquet(d / "schedules_2026.parquet")
    s.loc[s["week"] == 3, "gameday"] = "2026-09-23"
    s.to_parquet(d / "schedules_2026.parquet", index=False)
    assert U._week_cutoffs([2026])[(2026, 3)] == pd.Timestamp("2026-09-23", tz="UTC")


def test_snapshot_exactly_at_the_cutoff_is_excluded(tmp_path, monkeypatch):
    """Survivor: dt <= cutoff in layer 3 (and the depth layer). A snapshot stamped exactly
    at the week-4 cutoff (2026-10-01T00:00Z) is NOT used for week 4."""
    d, U, rosters, injuries, depth = _depth_world(tmp_path, False)
    monkeypatch.setattr(U, "PBP_DIR", d)
    qb = depth.iloc[[0]].assign(gsis_id="00-9", position="QB", pos_abb="QB", pos_rank=1,
                                dt="2026-10-01T00:00:00Z")
    st = U.derive_starting_qbs(pd.concat([depth, qb], ignore_index=True), None)
    assert st.get((2026, 4, "KC"), {}).get("gsis_id") != "00-9"
    assert st.get((2026, 5, "KC"), {}).get("gsis_id") == "00-9"
    at = depth.assign(dt="2026-10-01T00:00:00Z")
    au = U.build_active_universe(rosters, injuries, at)
    assert au[(au["season"] == 2026) & (au["week"] == 4)]["depth_order"].isna().all()


# ── the forward gate ──────────────────────────────────────────────────────────

def test_gate_halts_when_the_week_has_no_depth_ranks(tmp_path):
    """D273: every historical team-week has depth ranks for its active players; a week whose
    depth layer did not run must HALT before the worker."""
    d = _inputs(tmp_path)
    au, wk = _au_week(d, "KC")
    au = au.copy()
    au.loc[wk.index, "depth_order"] = float("nan")
    au.to_parquet(d / "active_universe_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: week-3 active universe has no depth ranks"):
        _gate(d)


def test_string_flags_without_nulls_halt(tmp_path):
    """Survivor: dtype check removed, null check kept. All non-null 'True'/'False' strings."""
    d = _inputs(tmp_path)
    au, wk = _au_week(d, "CAR")
    au = au.copy()
    au["active_flag"] = au["active_flag"].map({True: "True", False: "False"}).astype(object)
    au.to_parquet(d / "active_universe_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="CAR: week-3 active universe has non-boolean or missing"):
        _gate(d)


# ── dependency baseline ───────────────────────────────────────────────────────

def test_receipt_without_a_pilot_field_is_not_the_first_primary(tmp_path):
    """Survivor: `not r.get("pilot")` instead of `is False`."""
    from nfl.sim.run_forward_v1 import dependency_fields, append_receipt
    legacy = {"run_id": "L0", **_run(runtime=_rt({"pandas": _ident("0.1")}))}     # no pilot field
    append_receipt(tmp_path, legacy)
    first = {"run_id": "R1", "pilot": False, **_run(runtime=_rt({"pandas": _ident()}))}
    assert dependency_fields(tmp_path, first) == {"dependency_baseline_run_id": "R1",
                                                  "dependency_drift": []}


# ── refresh ───────────────────────────────────────────────────────────────────

def _refresh_world(tmp_path, monkeypatch):
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
        (pb / f).write_bytes(f"source {f}".encode())
    (root / "params_v1.json").write_text("{}")
    (root / "FREEZE_v1.json").write_text(json.dumps({"usage_fingerprint": "abc"}))
    for k, v in (("ROOT", root), ("RATINGS", rd), ("PBP", pb), ("PARAMS", root / "params_v1.json"),
                 ("FREEZE", root / "FREEZE_v1.json")):
        monkeypatch.setattr(R, k, v)
    monkeypatch.setattr(C, "usage_fingerprint", lambda *a, **k: "abc")
    monkeypatch.setattr(C, "engine_fingerprint", lambda: "e")
    monkeypatch.setattr(R, "_run", lambda script: None)
    monkeypatch.setattr(P, "pull_season", lambda s: pd.DataFrame({"week": [1]}))
    monkeypatch.setattr(P, "write_safe", lambda df, path: None)
    monkeypatch.setattr(R, "freshness_report", lambda week: True)
    return R, rd, pb, FIT_INPUT_FILES


def test_archive_holds_every_table_copy_with_its_hash(tmp_path, monkeypatch):
    """Survivor: table copies omitted while the manifest still hashes the installed tables."""
    R, rd, pb, FIT = _refresh_world(tmp_path, monkeypatch)
    monkeypatch.setattr(R, "snapshot_schedule", lambda: None)
    assert R.main(["--week", "4"]) == 0
    [backup] = list((tmp_path / "mlb-model-archive" / "nfl_ratings_backups").iterdir())
    ref = backup / "refreshed"
    man = json.loads((ref / "refresh_manifest.json").read_text())
    assert len(FIT) == 8
    for f in FIT:
        assert hashlib.sha256((ref / f).read_bytes()).hexdigest() == man["files"][f"tables/{f}"]
        assert (ref / f).read_bytes() == (rd / f).read_bytes()


def _fake_nflreadpy(df):
    m = types.ModuleType("nflreadpy")
    m.load_schedules = lambda seasons: df
    return m


def _season_schedule(drop_week=None, null_week=None):
    rows = []
    for w in range(1, 19):
        if w == drop_week:
            continue
        day = (pd.Timestamp("2026-09-10") + pd.Timedelta(days=7 * (w - 1))).date()
        rows.append({"game_id": f"2026_{w:02d}_A_B", "season": 2026, "game_type": "REG", "week": w,
                     "gameday": None if w == null_week else str(day), "gametime": "20:15",
                     "home_team": "B", "away_team": "A"})
    return pd.DataFrame(rows)


def test_snapshot_schedule_writes_the_real_file_and_refuses_incomplete_seasons(tmp_path, monkeypatch):
    """Survivor: the writer's path. The real snapshot_schedule writes schedules_2026.parquet
    with the downloaded content; a season missing a week, or with a null gameday, HALTs and
    writes nothing."""
    import nfl.sim.refresh_inputs as R
    monkeypatch.setattr(R, "PBP", tmp_path)
    good = _season_schedule()
    monkeypatch.setitem(sys.modules, "nflreadpy", _fake_nflreadpy(good))
    R.snapshot_schedule()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["schedules_2026.parquet"]
    assert pd.read_parquet(tmp_path / "schedules_2026.parquet").equals(good)
    for bad in (_season_schedule(drop_week=4), _season_schedule(null_week=7)):
        (tmp_path / "schedules_2026.parquet").unlink(missing_ok=True)
        monkeypatch.setitem(sys.modules, "nflreadpy", _fake_nflreadpy(bad))
        with pytest.raises(SystemExit, match="no valid regular-season gameday for weeks"):
            R.snapshot_schedule()
        assert not (tmp_path / "schedules_2026.parquet").exists()


# ── runbook boundary ──────────────────────────────────────────────────────────

def test_runbook_morning_boundary_is_1630z():
    """Survivor: a 16:00Z boundary. A 16:15Z (12:15 ET) Sunday kick precedes the 16:00Z VM
    pull's usable window and is early; 16:30Z (12:30 ET) is main."""
    M = _runbook()
    assert M._early_sunday(datetime(2026, 10, 4, 16, 15, tzinfo=timezone.utc))
    assert not M._early_sunday(datetime(2026, 10, 4, 16, 30, tzinfo=timezone.utc))
