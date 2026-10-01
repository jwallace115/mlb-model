"""D257 (FWD6 item 1): quotes judged row by row; the solver's returned anchor is mandatory;
the prediction outputs must carry this run's identity.

Audit #8 (A3, A4) counterexamples. Every test fails on e0fc3d2d6.
"""
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests._fwd_stub import write_stub_outputs  # noqa: E402
from nfl.sim.tests.test_fwd3_item0 import (  # noqa: E402
    _build_fixture_root, _stub_run_week, T, KICK, GAME_ID, EVENT_ID, HOME_FULL, AWAY_FULL)

PICK = {"game_id": GAME_ID, "player_id": "00-0033118", "player_name": "T.Kelce",
        "family": "receptions", "line": 5.5, "cal_p": 0.62, "side": "over", "tier": "T1"}


def _harness(root, fn=_stub_run_week, extra=()):
    from nfl.sim.run_forward_v1 import main
    return main(argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                      "--allow-stale-quotes", *extra], root=str(root), run_week_fn=fn)


def _lines_rows(snap_ts, total=45.5, commence=None):
    rows = []
    for market, outcome, point in [("spreads", HOME_FULL, -3.0), ("spreads", AWAY_FULL, 3.0),
                                   ("totals", "Over", total), ("totals", "Under", total)]:
        rows.append({"event_id": EVENT_ID, "commence_time": (commence or KICK).isoformat(),
                     "home_team": HOME_FULL, "away_team": AWAY_FULL,
                     "bookmaker": "hardrockbet_fl", "market": market, "outcome_name": outcome,
                     "point": point, "price": -110, "snapshot_utc": snap_ts.isoformat()})
    return rows


def _lines_dir(root):
    return root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"


def _only_run_dir(root):
    runs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    assert len(runs) == 1
    return runs[0]


# ── (a) quotes row by row ──

def test_future_line_row_behind_valid_first_row_is_never_used(tmp_path):
    """The auditor's case: a snapshot whose first rows are before T but whose totals rows
    are 10 min AFTER T. On e0fc3d2d6 the file was chosen (first row <= T) and total 99.0
    was frozen with source_age_min -10. Now that file is not usable at T; the older
    snapshot's total (45.5) is used."""
    root = _build_fixture_root(tmp_path)
    ok = T - timedelta(minutes=5)
    rows = _lines_rows(ok, total=99.0)
    for r in rows:
        if r["market"] == "totals":
            r["snapshot_utc"] = (T + timedelta(minutes=10)).isoformat()
    pd.DataFrame(rows).to_parquet(_lines_dir(root) / "snap_mixed.parquet", index=False)
    _harness(root)
    lines = pd.read_parquet(_only_run_dir(root) / "lines.parquet")
    assert 99.0 not in set(lines["point"].dropna()), "a post-T total was consumed"
    assert (lines["snapshot_utc"].map(pd.Timestamp) <= pd.Timestamp(T)).all()


def test_inconsistent_snapshot_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    rows = _lines_rows(T - timedelta(minutes=5))
    rows[0]["snapshot_utc"] = (T - timedelta(minutes=50)).isoformat()
    pd.DataFrame(rows).to_parquet(_lines_dir(root) / "snap_inconsistent.parquet", index=False)
    with pytest.raises(SystemExit, match="inconsistent game-line snapshot"):
        _harness(root)


def test_props_after_T_never_consumed(tmp_path):
    """A props pull timestamped after T sits in the archive. The bundle takes only the
    pre-T pull; if the loader's `pull_timestamp <= T` filter is removed, the per-row check
    HALTs instead of consuming it."""
    root = _build_fixture_root(tmp_path)
    pdir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=01"
    late = pd.read_parquet(pdir / "data_fixture.parquet")
    late["pull_timestamp"] = (T + timedelta(minutes=20)).isoformat()
    late["over_price"] = 150
    late.to_parquet(pdir / "data_late.parquet", index=False)
    _harness(root)
    props = pd.read_parquet(_only_run_dir(root) / "props.parquet")
    assert (props["pull_timestamp"].map(pd.Timestamp) <= pd.Timestamp(T)).all()
    assert 150 not in set(props["over_price"])


def test_event_metadata_inconsistent_across_props_and_lines_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    for f in _lines_dir(root).glob("*.parquet"):
        f.unlink()
    pd.DataFrame(_lines_rows(T - timedelta(minutes=5), commence=KICK + timedelta(hours=1))).to_parquet(
        _lines_dir(root) / "snap_other_kick.parquet", index=False)
    with pytest.raises(SystemExit, match="inconsistent teams/kickoff"):
        _harness(root)


# ── (b) the returned anchor is mandatory ──

def _stub(anchor=None, identity=None, picks=(PICK,)):
    def fn(root, week, T_, bundle_lines, game_ids, run_dir=None,
           input_dir=None, props_file=None, run_id=None, bundle_dir=None):
        write_stub_outputs(run_dir, week, run_id, input_dir, props_file, GAME_ID, list(picks),
                           anchor=anchor, identity_override=identity, bundle_dir=bundle_dir)
    return fn


def test_missing_anchor_returned_halts(tmp_path):
    """Audit #8 A4: with anchor_returned.parquet deleted the run still froze via the
    minimum-error fallback. Now it HALTs and nothing is frozen."""
    root = _build_fixture_root(tmp_path)
    with pytest.raises(SystemExit, match="anchor_returned.parquet missing"):
        _harness(root, _stub(anchor=False))
    assert not list((root / "nfl" / "data" / "board").rglob("ai_opinions_*.parquet"))


def test_anchor_returned_must_cover_each_simulated_game_once(tmp_path):
    root = _build_fixture_root(tmp_path)
    row = {"game": GAME_ID, "iterations": 1, "converged": True, "anch_m": -3.1,
           "anch_t": 45.6, "target_spread": -3.0, "target_total": 45.5}
    with pytest.raises(SystemExit, match="duplicate games"):
        _harness(root, _stub(anchor=[row, row]))
    root2 = _build_fixture_root(tmp_path / "b")
    with pytest.raises(SystemExit, match="anchor_returned games"):
        _harness(root2, _stub(anchor=[{**row, "game": "BUF@MIA"}]))


def test_sidecar_records_returned_convergence():
    """The sidecar's `converged` is the solver's returned flag (a mutation forcing it
    True survived audit #8)."""
    from nfl.sim.run_forward_v1 import anchor_sidecar
    ret = pd.DataFrame([{"game": "A@B", "iterations": 8, "converged": False,
                         "anch_m": -0.4, "anch_t": 40.3}])
    sc = anchor_sidecar(pd.DataFrame(), {"A@B": {"spread": 0.0, "total": 40.0}},
                        anchor_returned_df=ret)
    assert bool(sc.iloc[0]["converged"]) is False
    assert int(sc.iloc[0]["iterations"]) == 8


def test_anchor_tolerance_is_exactly_one_point():
    """miss 1.02 is unanchored, 0.98 anchored (a mutation to 1.05 survived audit #8)."""
    from nfl.sim.run_forward_v1 import anchor_sidecar
    lines = {"A@B": {"spread": 0.0, "total": 40.0}}
    for miss, want in ((1.02, False), (0.98, True)):
        ret = pd.DataFrame([{"game": "A@B", "iterations": 3, "converged": True,
                             "anch_m": miss, "anch_t": 40.0}])
        sc = anchor_sidecar(pd.DataFrame(), lines, anchor_returned_df=ret)
        assert bool(sc.iloc[0]["anchored"]) is want, f"miss {miss}: anchored={sc.iloc[0]['anchored']}"


# ── (c) output identity ──

def test_outputs_from_another_run_halt(tmp_path):
    """Audit #8 A4: predictions labelled season 2025, week 2, run 'previous-experiment'
    were frozen as 2026 week 3/4. Now they HALT before any opinion is filled."""
    root = _build_fixture_root(tmp_path)
    with pytest.raises(SystemExit, match="but this run is"):
        _harness(root, _stub(identity={"season": 2025, "week": 2, "run_id": "previous-experiment"}))
    assert not list((root / "nfl" / "data" / "board").rglob("ai_opinions_*.parquet"))


def test_each_identity_field_is_checked(tmp_path):
    for field, value in (("season", 2025), ("week", 2), ("run_id", "other")):
        root = _build_fixture_root(tmp_path / field)
        with pytest.raises(SystemExit, match=f"{field} = "):
            _harness(root, _stub(identity={field: value}))


def test_pick_for_a_game_outside_the_bundle_halts(tmp_path):
    root = _build_fixture_root(tmp_path)
    with pytest.raises(SystemExit, match="games outside the bundle"):
        _harness(root, _stub(picks=(PICK, {**PICK, "game_id": "BUF@MIA"})))


def test_outputs_without_identity_columns_halt(tmp_path):
    """Old-style outputs (no season/week/run_id columns) are not accepted."""
    root = _build_fixture_root(tmp_path)

    def old_style(root_, week, T_, bundle_lines, game_ids, run_dir=None,
                  input_dir=None, props_file=None, run_id=None, bundle_dir=None):
        write_stub_outputs(run_dir, week, run_id, input_dir, props_file, GAME_ID, [PICK],
                           bundle_dir=bundle_dir)
        p = pd.read_parquet(Path(run_dir) / "picks_log.parquet").drop(columns=["season", "week", "run_id"])
        p.to_parquet(Path(run_dir) / "picks_log.parquet", index=False)
    with pytest.raises(SystemExit, match="has no season column"):
        _harness(root, old_style)
