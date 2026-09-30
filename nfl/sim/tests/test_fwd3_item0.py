"""D241: tests for the run record — complete, exclusive and immutable.

Every test calls the real function and must FAIL on 0792fd122.
"""
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ── fixture helpers (shared with test_fwd2b_harness.py) ──

KICK = datetime(2099, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
T = KICK - timedelta(hours=2)
EVENT_ID = "evt_fixture_001"
HOME_FULL = "Kansas City Chiefs"
AWAY_FULL = "Carolina Panthers"
HOME_ABBR = "KC"
AWAY_ABBR = "CAR"
GAME_ID = f"{AWAY_ABBR}@{HOME_ABBR}"


def _build_fixture_root(tmp_path, kick=None, pull_age_minutes=30,
                        line_age_minutes=30):
    """Build a minimal fixture root with one event's props and lines."""
    if kick is None:
        kick = KICK
    root = tmp_path / "repo"

    for sub in ("nfl/sim/tests", "nfl/sim", "nfl/data/sim/ratings",
                "research/nfl_sim", "nfl/pipeline"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    em = json.loads((ROOT / "research/nfl_sim/FWD_EXPERIMENT_v1.json").read_text())
    for path in em.get("file_hashes", {}):
        src = ROOT / path
        if src.exists():
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    for rel in ("research/nfl_sim/FREEZE_v1.json",
                "research/nfl_sim/FWD_EXPERIMENT_v1.json",
                "nfl/sim/tests/test_freeze_v1.py"):
        src = ROOT / rel
        if src.exists():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, root / rel)

    freeze = json.loads((ROOT / "research/nfl_sim/FREEZE_v1.json").read_text())
    for rel_path in freeze.get("table_hashes", {}):
        src = ROOT / rel_path
        if src.exists():
            dest = root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    ratings_dir = ROOT / "nfl" / "data" / "sim" / "ratings"
    dest_ratings = root / "nfl" / "data" / "sim" / "ratings"
    dest_ratings.mkdir(parents=True, exist_ok=True)
    for fname in ("team_ratings_weekly.parquet", "tendencies_weekly.parquet",
                  "player_usage_weekly.parquet", "kicker_weekly.parquet",
                  "tendencies_situational_weekly.parquet",
                  "qb_ratings_weekly.parquet", "league_baselines.parquet",
                  "active_universe_weekly.parquet"):
        src = ratings_dir / fname
        if src.exists():
            shutil.copy2(src, dest_ratings / fname)

    # Rosters
    pbp_dir = ROOT / "nfl" / "data" / "pbp"
    dest_pbp = root / "nfl" / "data" / "pbp"
    dest_pbp.mkdir(parents=True, exist_ok=True)
    for fname in ("rosters_weekly.parquet", "depth_charts.parquet",
                  "injuries.parquet"):
        src = pbp_dir / fname
        if src.exists():
            shutil.copy2(src, dest_pbp / fname)

    for rel in ("nfl/sim/calibration.py", "nfl/sim/anchor.py",
                "nfl/sim/names.py", "nfl/sim/__init__.py",
                "nfl/__init__.py", "nfl/pipeline/__init__.py",
                "nfl/pipeline/log_ai_opinions.py",
                "nfl/sim/run_forward_v1.py", "nfl/sim/run_week.py"):
        src = ROOT / rel
        if src.exists():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    fixture_T = kick - timedelta(hours=2)
    pull_ts = (fixture_T - timedelta(minutes=pull_age_minutes)).isoformat()
    props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=01"
    props_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "event_id": EVENT_ID,
        "commence_time": kick.isoformat(),
        "home_team": HOME_FULL,
        "away_team": AWAY_FULL,
        "bookmaker": "hardrockbet_fl",
        "market_key": "player_receptions",
        "player_name": "T.Kelce",
        "line": 5.5,
        "over_price": -110,
        "under_price": -110,
        "pull_timestamp": pull_ts,
    }]).to_parquet(props_dir / "data_fixture.parquet", index=False)

    snap_ts = (fixture_T - timedelta(minutes=line_age_minutes)).isoformat()
    lines_dir = root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    lines_dir.mkdir(parents=True, exist_ok=True)
    lines_rows = []
    for market, outcome, point, price in [
        ("spreads", HOME_FULL, -3.0, -110),
        ("spreads", AWAY_FULL, 3.0, -110),
        ("totals", "Over", 45.5, -110),
        ("totals", "Under", 45.5, -110),
        ("h2h", HOME_FULL, None, -150),
        ("h2h", AWAY_FULL, None, 130),
    ]:
        lines_rows.append({
            "event_id": EVENT_ID,
            "commence_time": kick.isoformat(),
            "home_team": HOME_FULL,
            "away_team": AWAY_FULL,
            "bookmaker": "hardrockbet_fl",
            "market": market,
            "outcome_name": outcome,
            "point": point,
            "price": price,
            "snapshot_utc": snap_ts,
        })
    snap_fname = f"snap_{fixture_T.strftime('%Y%m%dT%H%M%SZ')}.parquet"
    pd.DataFrame(lines_rows).to_parquet(lines_dir / snap_fname, index=False)

    (root / "nfl" / "data" / "board").mkdir(parents=True, exist_ok=True)
    (root / "nfl" / "data" / "sim" / "outputs").mkdir(parents=True, exist_ok=True)

    import hashlib as _hl
    em_path = root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"
    if em_path.exists():
        em_data = json.loads(em_path.read_text())
        for rel_path in list(em_data.get("file_hashes", {})):
            fp = root / rel_path
            if fp.exists():
                em_data["file_hashes"][rel_path] = _hl.sha256(
                    fp.read_bytes()).hexdigest()[:16]
        em_path.write_text(json.dumps(em_data, indent=1) + "\n")

    return root


def _stub_run_week(root, week, T, bundle_lines, game_ids, run_dir=None):
    out_dir = run_dir or (root / "nfl" / "data" / "sim" / "outputs" / f"week=2026_{week:02d}")
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "game_id": GAME_ID,
        "player_id": "00-0033118",
        "player_name": "T.Kelce",
        "family": "receptions",
        "line": 5.5,
        "cal_p": 0.62,
        "side": "over",
        "tier": "T1",
    }]).to_parquet(out_dir / "picks_log.parquet", index=False)
    pd.DataFrame([{
        "game": GAME_ID,
        "iter": 0,
        "margin": -3.1,
        "total": 45.6,
        "err_m": -0.1,
        "err_t": 0.1,
        "converged": True,
    }]).to_parquet(out_dir / "anchoring_log.parquet", index=False)


# ── D241(a): build_bundle REFUSES an existing run directory ──

def _set_fwd_paths(fwd, root):
    """Override module-level paths for a fixture root."""
    fwd.PROPS_DIR = root / "data" / "odds_archive" / "nfl" / "props"
    fwd.LINES_DIR = root / "data" / "odds_archive" / "nfl" / "line_history"
    fwd.BOARD_ROOT = root / "nfl" / "data" / "board"
    fwd.EXPERIMENT_MANIFEST = root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"


def test_build_bundle_refuses_existing_run_dir(tmp_path):
    """Audit #7 A2 counterexample: the same run_id twice -> HALT, first bundle
    unchanged. On 0792fd122 build_bundle uses exist_ok=True."""
    from nfl.sim.run_forward_v1 import build_bundle

    root = _build_fixture_root(tmp_path)
    import nfl.sim.run_forward_v1 as fwd
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        bd1, _ = build_bundle(2026, 3, T, pilot=True,
                              allow_stale_quotes=True, _root=root)
        h1 = hashlib.sha256((bd1 / "events.parquet").read_bytes()).hexdigest()

        with pytest.raises(SystemExit, match="run directory already exists"):
            build_bundle(2026, 3, T, pilot=True,
                         allow_stale_quotes=True, _root=root)

        h1_after = hashlib.sha256(
            (bd1 / "events.parquet").read_bytes()).hexdigest()
        assert h1 == h1_after, "first bundle must be unchanged after refusal"
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


# ── D241(b): prediction inputs are copied and isolated ──

def test_inputs_copied_into_bundle(tmp_path):
    """Audit #7 A2: the bundle must copy ratings, usage, active_universe,
    and rosters. On 0792fd122 these are not preserved."""
    from nfl.sim.run_forward_v1 import build_bundle

    root = _build_fixture_root(tmp_path)
    import nfl.sim.run_forward_v1 as fwd
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        bd, _ = build_bundle(2026, 3, T, pilot=True,
                             allow_stale_quotes=True, _root=root)
        inputs_dir = bd / "inputs"
        assert inputs_dir.exists(), "inputs/ directory must exist"
        for fname in ("team_ratings_weekly.parquet", "player_usage_weekly.parquet",
                      "active_universe_weekly.parquet"):
            assert (inputs_dir / fname).exists(), f"inputs/{fname} must exist"
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def test_shared_ratings_change_not_in_bundle(tmp_path):
    """After a run, changing the shared ratings file must NOT change what the
    run directory holds. On 0792fd122 ratings are not copied."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    # Find the run directory
    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    assert len(run_dirs) == 1
    bd = run_dirs[0]
    inputs_dir = bd / "inputs"

    # Record hash of the copied ratings
    ratings_in_bundle = inputs_dir / "team_ratings_weekly.parquet"
    assert ratings_in_bundle.exists(), "ratings must be copied into bundle"
    h_before = hashlib.sha256(ratings_in_bundle.read_bytes()).hexdigest()

    # Tamper the shared ratings
    shared = root / "nfl" / "data" / "sim" / "ratings" / "team_ratings_weekly.parquet"
    df = pd.read_parquet(shared)
    df.iloc[0, df.columns.get_loc(df.select_dtypes("number").columns[0])] += 999
    df.to_parquet(shared, index=False)

    # Bundle copy must be unchanged
    h_after = hashlib.sha256(ratings_in_bundle.read_bytes()).hexdigest()
    assert h_before == h_after, "bundle's ratings must be isolated from shared"


def test_outputs_only_under_run_dir(tmp_path):
    """D241(b): outputs exist only under the run directory, not in the shared
    weekly directory. On 0792fd122 run_week writes to the shared directory."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    # Shared weekly dir should NOT have picks_log
    shared_out = root / "nfl" / "data" / "sim" / "outputs" / "week=2026_03"
    if shared_out.exists():
        assert not (shared_out / "picks_log.parquet").exists(), \
            "picks_log must NOT be in the shared weekly directory"

    # Run dir MUST have picks_log
    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    assert (bd / "outputs" / "picks_log.parquet").exists(), \
        "picks_log must be in <run-dir>/outputs/"


# ── D241(c): game-line freshness ──

def test_stale_lines_halt(tmp_path):
    """Audit #7 A6: fresh props + 5-day-old lines -> HALT.
    On 0792fd122 only props age is checked."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path, line_age_minutes=5 * 24 * 60)
    with pytest.raises(SystemExit, match="game-line snapshot is"):
        main(
            argv=["--week", "3", "--pilot", "--as-of", T.isoformat()],
            root=str(root),
            run_week_fn=_stub_run_week,
        )


# ── D241(d): sidecar in run directory, no weekly copy ──

def test_sidecar_in_run_dir_not_weekly(tmp_path):
    """D241(d): sidecar is in the run directory and hashed.
    On 0792fd122 the sidecar is written to the weekly opinions dir."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    assert (bd / "anchor_sidecar.parquet").exists(), \
        "sidecar must be in the run directory"

    # Verify it's hashed in the manifest
    man = json.loads((bd / "bundle_manifest.json").read_text())
    assert "anchor_sidecar.parquet" in man, \
        "sidecar must be hashed in the bundle manifest"


# ── D241(e): publication atomic — quarantine past-kick writes ──

def test_publication_past_kick_halts_live(tmp_path):
    """Audit #7 A6: a live run where wall clock >= first kick -> HALT.
    On 0792fd122 the publication check runs before the write and
    a time gap between check and write is not caught.
    This tests the simpler case: wall clock already past kick at check time."""
    from nfl.sim.run_forward_v1 import main

    # Kick in the past -> pre-write wall clock >= first_kick -> HALT
    past_kick = datetime(2020, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
    root = _build_fixture_root(tmp_path, kick=past_kick)

    with pytest.raises(SystemExit):
        main(
            argv=["--week", "3"],
            root=str(root),
            run_week_fn=_stub_run_week,
        )


# ── D241(f): bundle manifest hashes everything, verify detects tampering ──

def test_bundle_manifest_hashes_inputs(tmp_path):
    """D241(f): the bundle manifest must hash every file including inputs
    and sidecar. On 0792fd122 only events/props/lines/freshness are hashed."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    man = json.loads((bd / "bundle_manifest.json").read_text())

    # Must hash input files
    input_keys = [k for k in man if k.startswith("inputs/")]
    assert len(input_keys) > 0, "manifest must hash input files"

    # Must hash sidecar
    assert "anchor_sidecar.parquet" in man, "manifest must hash sidecar"

    # Must hash output files
    output_keys = [k for k in man if k.startswith("outputs/")]
    assert len(output_keys) > 0, "manifest must hash output files"


def test_verify_detects_tampered_file(tmp_path):
    """D241(f): altering any run-directory file is detected by verify."""
    from nfl.sim.run_forward_v1 import main, verify_bundle

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]

    # Verify clean
    bad = verify_bundle(bd)
    assert bad == [], f"clean bundle should verify: {bad}"

    # Tamper a file
    events_path = bd / "events.parquet"
    events_path.write_bytes(events_path.read_bytes() + b"\x00")

    bad = verify_bundle(bd)
    assert len(bad) > 0, "tampered file must be detected"
    assert any("events.parquet" in b for b in bad)
