"""D274 (FWD7d): ChatGPT audit #16 — historical cutoffs, schedule/PBP contradictions, and
audit #16's survivors. No parametrize (CLAUDE.md)."""
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd7a import _depth_world, _inputs, _au_week, _gate  # noqa: E402
from nfl.sim.tests.test_fwd7c import _season_schedule, _fake_nflreadpy  # noqa: E402


def _world(tmp_path, tag):
    (tmp_path / tag).mkdir()
    return _depth_world(tmp_path / tag, False)


def _with_2025(d, rosters, null_week=None, drop_week=None):
    """Add a 2025 season (weeks 1-3) to the world: rosters and a PBP with one game per week;
    no 2025 schedule snapshot (history)."""
    dates = {1: "2025-09-04", 2: "2025-09-11", 3: "2025-09-18"}
    pd.DataFrame([{"season": 2025, "week": w, "game_id": f"h{w}",
                   "game_date": None if w == null_week else dates[w]}
                  for w in (1, 2, 3) if w != drop_week]).to_parquet(d / "pbp_2025.parquet", index=False)
    r25 = rosters[rosters["week"].isin([1, 2, 3])].assign(season=2025)
    return pd.concat([r25, rosters], ignore_index=True)


# ── A1: historical cutoffs ────────────────────────────────────────────────────

def test_missing_historical_cutoff_halts_the_multi_season_build(tmp_path, monkeypatch):
    """Audit #16 A1: 2025 week 3 with null dates (no 2025 snapshot) silently lost its depth
    layer in the ordinary 2025+2026 build, changing the priors 2026 usage is built from.
    Every season-week being built now needs a valid cutoff: HALT."""
    d, U, rosters, injuries, depth = _world(tmp_path, "clean")
    monkeypatch.setattr(U, "PBP_DIR", d)
    ok = U.build_active_universe(_with_2025(d, rosters), injuries, depth)
    assert set(ok["season"]) == {2025, 2026}
    d, U, rosters, injuries, depth = _world(tmp_path, "null")
    monkeypatch.setattr(U, "PBP_DIR", d)
    both = _with_2025(d, rosters, null_week=3)
    with pytest.raises(RuntimeError, match="pbp_2025.parquet: invalid game dates/identities — "
                                           "null/unparseable game_date in games \\['h3'\\]"):
        U.build_active_universe(both, injuries, depth)
    # a historical week the rosters have but the PBP lacks entirely: HALT, not skip
    d, U, rosters, injuries, depth = _world(tmp_path, "gap")
    monkeypatch.setattr(U, "PBP_DIR", d)
    both = _with_2025(d, rosters, drop_week=3)
    with pytest.raises(RuntimeError, match="no valid week cutoff for season 2025 weeks \\[3\\]"):
        U.build_active_universe(both, injuries, depth)


def test_a_game_with_two_dates_or_weeks_halts(tmp_path, monkeypatch):
    d, U, rosters, injuries, depth = _world(tmp_path, "x")
    monkeypatch.setattr(U, "PBP_DIR", d)
    p = pd.read_parquet(d / "pbp_2026.parquet")
    for extra in ({"season": 2026, "week": 2, "game_id": "g2", "game_date": "2026-09-18"},
                  {"season": 2026, "week": 3, "game_id": "g2", "game_date": "2026-09-17"}):
        pd.concat([p, pd.DataFrame([extra])], ignore_index=True).to_parquet(d / "pbp_2026.parquet", index=False)
        with pytest.raises(RuntimeError, match="more than one date or week \\['g2'\\]"):
            U._week_cutoffs([2026])
    # a row from another season inside pbp_2026 (survivor T3)
    pd.concat([p, pd.DataFrame([{"season": 2025, "week": 3, "game_id": "g9", "game_date": "2025-09-18"}])],
              ignore_index=True).to_parquet(d / "pbp_2026.parquet", index=False)
    with pytest.raises(RuntimeError, match="1 rows with season missing or != 2026"):
        U._week_cutoffs([2026])


# ── A2: schedule / PBP contradictions ─────────────────────────────────────────

def _add_pbp(d, row):
    p = pd.read_parquet(d / "pbp_2026.parquet")
    pd.concat([p, pd.DataFrame([row])], ignore_index=True).to_parquet(d / "pbp_2026.parquet", index=False)


def test_pbp_date_contradicting_the_snapshot_halts_in_both_directions(tmp_path, monkeypatch):
    """Audit #16 A2: a valid-looking week-4 PBP date one day BEFORE the snapshot's gameday
    moved the cutoff (min) and changed 35 real-worker probabilities. Both directions, a game
    missing from the snapshot, and a week mismatch now HALT."""
    cases = (({"season": 2026, "week": 4, "game_id": "g4", "game_date": "2026-09-30"}, "'g4', 4, '2026-09-30', 4, '2026-10-01'"),
             ({"season": 2026, "week": 4, "game_id": "g4", "game_date": "2026-10-02"}, "'g4', 4, '2026-10-02', 4, '2026-10-01'"),
             ({"season": 2026, "week": 4, "game_id": "zz", "game_date": "2026-10-01"}, "'zz', 4, '2026-10-01', None, None"),
             ({"season": 2026, "week": 5, "game_id": "g4", "game_date": "2026-10-01"}, "'g4', 5, '2026-10-01', 4, '2026-10-01'"))
    for i, (row, ex) in enumerate(cases):
        d, U, rosters, injuries, depth = _world(tmp_path, f"c{i}")
        monkeypatch.setattr(U, "PBP_DIR", d)
        _add_pbp(d, row)
        with pytest.raises(RuntimeError, match="contradicts the archived schedule snapshot for 1 games") as e:
            U.build_active_universe(rosters, injuries, depth)
        assert ex in str(e.value), (ex, str(e.value))


def test_schedule_only_and_schedule_plus_pbp_give_identical_rows(tmp_path, monkeypatch):
    """The transition the live run goes through: week 4 live (snapshot only) and after its
    first game is played (snapshot + a consistent week-4 PBP game) give the same rows."""
    outs = []
    for tag, extra in (("live", None),
                       ("played", {"season": 2026, "week": 4, "game_id": "g4", "game_date": "2026-10-01"})):
        d, U, rosters, injuries, depth = _world(tmp_path, tag)
        monkeypatch.setattr(U, "PBP_DIR", d)
        if extra:
            _add_pbp(d, extra)
        qb = depth.iloc[[0]].assign(gsis_id="00-9", position="QB", pos_abb="QB", pos_rank=1)
        outs.append((U.build_active_universe(rosters, injuries, depth)
                     .sort_values(["season", "week", "team", "player_id"]).reset_index(drop=True),
                     U.derive_starting_qbs(pd.concat([depth, qb], ignore_index=True), None)))
    assert outs[0][0].equals(outs[1][0]) and outs[0][1] == outs[1][1]
    assert outs[0][0][outs[0][0]["week"] == 4]["depth_order"].notna().all()


# ── audit #16 survivors ───────────────────────────────────────────────────────

def test_snapshot_coverage_counts_only_this_seasons_regular_season(tmp_path, monkeypatch):
    """Survivors N1/N2: week 7 covered only by a 2025 row, or only by a non-REG row, is NOT
    covered."""
    import nfl.sim.refresh_inputs as R
    monkeypatch.setattr(R, "PBP", tmp_path)
    base = _season_schedule(drop_week=7)
    for patch in (lambda r: r.assign(season=2025), lambda r: r.assign(game_type="POST")):
        add = patch(_season_schedule().query("week == 7"))
        monkeypatch.setitem(sys.modules, "nflreadpy", _fake_nflreadpy(pd.concat([base, add], ignore_index=True)))
        with pytest.raises(SystemExit, match="no valid regular-season gameday for weeks \\[7\\]"):
            R.snapshot_schedule()
        assert not (tmp_path / "schedules_2026.parquet").exists()


def test_depth_gate_ignores_ranks_of_inactive_players(tmp_path):
    """Survivor N3: the gate counted any rank. Active players unranked + an inactive player
    ranked must still HALT."""
    d = _inputs(tmp_path)
    au, wk = _au_week(d, "KC")
    act = wk[wk["active_flag"]]
    pid = act.iloc[0]["player_id"]
    inj = pd.read_parquet(d / "injuries.parquet")
    pd.concat([inj, pd.DataFrame([{"season": 2026, "week": 3, "team": "KC", "gsis_id": pid,
                                   "report_status": "Out"}])], ignore_index=True
              ).to_parquet(d / "injuries.parquet", index=False)
    au = au.copy()
    au.loc[(au.index.isin(wk.index)) & (au["player_id"] == pid), "active_flag"] = False
    au.loc[(au.index.isin(wk.index)) & (au["player_id"] != pid), "depth_order"] = float("nan")
    au.loc[(au.index.isin(wk.index)) & (au["player_id"] == pid), "depth_order"] = 1.0
    au.to_parquet(d / "active_universe_weekly.parquet", index=False)
    with pytest.raises(SystemExit, match="KC: week-3 active universe has no depth ranks"):
        _gate(d)


def test_require_cutoffs_rejects_a_nat_value():
    """Survivor N4: the helper's contract — a key holding NaT is not a cutoff."""
    from nfl.sim.usage import _require_cutoffs
    cut = {(2026, 1): pd.Timestamp("2026-09-10", tz="UTC"), (2026, 2): pd.NaT}
    _require_cutoffs(cut, 2026, [1], "t")
    with pytest.raises(RuntimeError, match="t: no valid week cutoff for season 2026 weeks \\[2\\]"):
        _require_cutoffs(cut, 2026, [1, 2], "t")
