"""D229: tests for the in-process harness (FWD2b item 0).

Every test calls main() on a fixture root with a stub run_week_fn.
Every test must fail on fd0a2a5c6 for the right reason (old main() does
not accept argv/root/run_week_fn).
"""
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ── fixture helpers ──────────────────────────────────────────────────────────

KICK = datetime(2099, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
T = KICK - timedelta(hours=2)
EVENT_ID = "evt_fixture_001"
HOME_FULL = "Kansas City Chiefs"
AWAY_FULL = "Carolina Panthers"
HOME_ABBR = "KC"
AWAY_ABBR = "CAR"
GAME_ID = f"{AWAY_ABBR}@{HOME_ABBR}"


def _build_fixture_root(tmp_path, kick=None, pull_age_minutes=30):
    """Build a minimal fixture root with one event's props and lines."""
    if kick is None:
        kick = KICK
    root = tmp_path / "repo"

    # Copy all files needed for the integrity checks
    for sub in ("nfl/sim/tests", "nfl/sim", "nfl/data/sim/ratings",
                "research/nfl_sim", "nfl/pipeline"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    # Copy files referenced in the experiment manifest
    em = json.loads((ROOT / "research/nfl_sim/FWD_EXPERIMENT_v1.json").read_text())
    for path in em.get("file_hashes", {}):
        src = ROOT / path
        if src.exists():
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # Copy core files needed
    for rel in ("research/nfl_sim/FREEZE_v1.json",
                "research/nfl_sim/FWD_EXPERIMENT_v1.json",
                "nfl/sim/tests/test_freeze_v1.py"):
        src = ROOT / rel
        if src.exists():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, root / rel)

    # Copy freeze table files
    freeze = json.loads((ROOT / "research/nfl_sim/FREEZE_v1.json").read_text())
    for rel_path in freeze.get("table_hashes", {}):
        src = ROOT / rel_path
        if src.exists():
            dest = root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # Copy ratings for freshness checks
    ratings_dir = ROOT / "nfl" / "data" / "sim" / "ratings"
    dest_ratings = root / "nfl" / "data" / "sim" / "ratings"
    dest_ratings.mkdir(parents=True, exist_ok=True)
    for fname in ("team_ratings_weekly.parquet", "tendencies_weekly.parquet",
                  "player_usage_weekly.parquet", "kicker_ratings.parquet"):
        src = ratings_dir / fname
        if src.exists():
            shutil.copy2(src, dest_ratings / fname)

    # Copy Python modules needed for imports
    for rel in ("nfl/sim/calibration.py", "nfl/sim/anchor.py",
                "nfl/sim/names.py", "nfl/sim/__init__.py",
                "nfl/__init__.py", "nfl/pipeline/__init__.py",
                "nfl/sim/fwd_v1_logger.py",
                "nfl/sim/run_forward_v1.py", "nfl/sim/run_week.py"):
        src = ROOT / rel
        if src.exists():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # Build fixture props tape
    fixture_T = kick - timedelta(hours=2)
    pull_ts = (fixture_T - timedelta(minutes=pull_age_minutes)).isoformat()
    props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=01"
    props_dir.mkdir(parents=True, exist_ok=True)
    props = pd.DataFrame([{
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
    }])
    props.to_parquet(props_dir / "data_fixture.parquet", index=False)

    # Build fixture lines tape
    snap_ts = (fixture_T - timedelta(minutes=30)).isoformat()
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

    # Board root + sim output dir
    (root / "nfl" / "data" / "board").mkdir(parents=True, exist_ok=True)
    (root / "nfl" / "data" / "sim" / "outputs").mkdir(parents=True, exist_ok=True)

    # D256: every prediction input a forward run copies, plus a PBP file with week-2 finals
    from nfl.sim.tests._fwd_stub import add_fwd6_fixture_inputs
    add_fwd6_fixture_inputs(root, played_week=2, teams=((HOME_ABBR, AWAY_ABBR),))

    # Update experiment manifest hashes to match the copied (possibly modified) files
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


def _stub_run_week(root, week, T, bundle_lines, game_ids, run_dir=None,
                   input_dir=None, props_file=None, run_id=None):
    """Stub run_week_fn: writes what the real run_week writes in forward-run mode."""
    from nfl.sim.tests._fwd_stub import write_stub_outputs
    out_dir = run_dir or (root / "nfl" / "data" / "sim" / "outputs" / f"week=2026_{week:02d}")
    write_stub_outputs(out_dir, week, run_id, input_dir, props_file, GAME_ID, [{
        "game_id": GAME_ID, "player_id": "00-0033118", "player_name": "T.Kelce",
        "family": "receptions", "line": 5.5, "cal_p": 0.62, "side": "over", "tier": "T1",
    }])

# ── (a) D234: renamed from test_live_freeze_completes ──

def test_pilot_fixture_freeze(tmp_path):
    """D229→D234: pilot with --as-of on fixture root completes a freeze."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)

    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )

    assert dest is not None, "main() should return a frozen file path"
    assert dest.exists(), f"frozen file {dest} should exist"
    df = pd.read_parquet(dest)
    assert df["pilot"].all(), "pilot file must have pilot=True on all rows"


# ── D234(a): TRUE live test — no --pilot, no --as-of ──

def test_live_freeze_no_pilot(tmp_path):
    """D234(a): main() with NO --pilot and NO --as-of, kick = now + 2h,
    pull = now - 30 min. Completes a freeze with pilot==False and canonical reader.
    On 3beed7970: test_live_freeze_completes used --pilot."""
    from nfl.sim.run_forward_v1 import main, READER_MODEL

    now = datetime.now(timezone.utc)
    live_kick = now + timedelta(hours=2)
    root = _build_fixture_root(tmp_path, kick=live_kick, pull_age_minutes=30)

    dest = main(
        argv=["--week", "3"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )

    assert dest is not None, "live freeze should produce a file"
    assert dest.exists()
    df = pd.read_parquet(dest)
    assert not df["pilot"].any(), "live run must have pilot=False on all rows"
    assert (df["reader_model"] == READER_MODEL).all(), "reader must be canonical"
    # Prices match bundle
    prop_rows = df[df["market_key"] == "player_receptions"]
    assert len(prop_rows) > 0
    kelce = prop_rows[prop_rows["player_name"] == "T.Kelce"].iloc[0]
    assert kelce["price_first"] == -110
    assert kelce["price_second"] == -110


def test_live_stale_quotes_halt(tmp_path):
    """D234(a): live run with 4h-old quotes HALTs on quote age, nothing frozen."""
    from nfl.sim.run_forward_v1 import main

    now = datetime.now(timezone.utc)
    live_kick = now + timedelta(hours=2)
    root = _build_fixture_root(tmp_path, kick=live_kick, pull_age_minutes=240)

    opinions_dir = root / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    with pytest.raises(SystemExit, match="props pull is"):
        main(
            argv=["--week", "3"],
            root=str(root),
            run_week_fn=_stub_run_week,
        )
    if opinions_dir.exists():
        assert len(list(opinions_dir.glob("ai_opinions_*.parquet"))) == 0


# ── (b) PILOT with --as-of completes ──

def test_pilot_as_of_completes(tmp_path):
    """D229(b): pilot with --as-of completes and produces a frozen file."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None
    assert dest.exists()
    df = pd.read_parquet(dest)
    assert df["pilot"].all(), "pilot file must have pilot=True on all rows"


# ── (c) Bundle price altered after sheet → HALT ──

def test_bundle_price_altered_halts(tmp_path):
    """D229(c): altering a price in the filled sheet → HALT on validation."""
    from nfl.sim.run_forward_v1 import main, fill_sheet as real_fill

    root = _build_fixture_root(tmp_path)

    orig_fill = real_fill

    def _tamper_fill(sheet_df, picks_log, event_game_map=None):
        filled, n = orig_fill(sheet_df, picks_log, event_game_map=event_game_map)
        if "price_first" in filled.columns and len(filled) > 0:
            filled.loc[filled.index[0], "price_first"] = -999
        return filled, n

    with patch("nfl.sim.run_forward_v1.fill_sheet", _tamper_fill):
        with pytest.raises(SystemExit, match="price_first mismatch"):
            main(
                argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                      "--allow-stale-quotes"],
                root=str(root),
                run_week_fn=_stub_run_week,
            )


# ── (d) Stale ratings → HALT ──

def test_stale_ratings_halts(tmp_path):
    """D229(d): ratings with max week < week-1 for season 2026 → HALT."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)

    # Overwrite team_ratings with max week=0
    ratings_path = root / "nfl" / "data" / "sim" / "ratings" / "team_ratings_weekly.parquet"
    if ratings_path.exists():
        df = pd.read_parquet(ratings_path)
        df.loc[df["season"] == 2026, "week"] = 0
        df.to_parquet(ratings_path, index=False)

    with pytest.raises(SystemExit, match="team_ratings max week"):
        main(
            argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                  "--allow-stale-quotes"],
            root=str(root),
            run_week_fn=_stub_run_week,
        )


# ── (e) Zero matches → HALT with nothing frozen ──

def test_zero_matches_halts(tmp_path):
    """D229(e): zero sim matches → HALT, nothing frozen."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)

    def _empty_run_week(root, week, T, bundle_lines, game_ids, run_dir=None,
                        input_dir=None, props_file=None, run_id=None):
        from nfl.sim.tests._fwd_stub import write_stub_outputs
        write_stub_outputs(run_dir, week, run_id, input_dir, props_file, GAME_ID, [])

    opinions_dir = root / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    with pytest.raises(SystemExit, match="zero sim matches"):
        main(
            argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                  "--allow-stale-quotes"],
            root=str(root),
            run_week_fn=_empty_run_week,
        )
    if opinions_dir.exists():
        assert len(list(opinions_dir.glob("ai_opinions_*.parquet"))) == 0


# ── (f) Usage fingerprint mismatch → HALT ──

def test_usage_fingerprint_mismatch_halts(tmp_path):
    """D229(f): monkeypatched usage fingerprint → HALT."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)

    with patch("nfl.sim.calibration.usage_fingerprint", return_value="TAMPERED"):
        with pytest.raises(SystemExit, match="usage fingerprint mismatch"):
            main(
                argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                      "--allow-stale-quotes"],
                root=str(root),
                run_week_fn=_stub_run_week,
            )


# ── (g) Wall clock past the first kick → HALT ──

def test_wall_clock_past_kick_halts(tmp_path):
    """D229(g): non-pilot run with wall clock >= first kick → HALT.
    Tested by verifying that a non-pilot run with a past kick raises SystemExit.
    Since T=now() for a live run, and now() > past_kick, the bundle finds no
    pre-kick events, which triggers the 'no pre-kick events' HALT."""
    from nfl.sim.run_forward_v1 import main

    # Kick in the past → no pre-kick events in the bundle → HALT
    past_kick = datetime(2020, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
    root = _build_fixture_root(tmp_path, kick=past_kick)

    with pytest.raises(SystemExit):
        main(
            argv=["--week", "3"],
            root=str(root),
            run_week_fn=_stub_run_week,
        )


# ── D235(c): build_bundle reads manual/scratch_*.parquet ──

def test_bundle_reads_manual_scratch(tmp_path):
    """D235(c): build_bundle reads manual/scratch_*.parquet and takes the
    newest pull when it is newer than the archive."""
    from nfl.sim.run_forward_v1 import _load_props_at_T, BOOK

    now = datetime.now(timezone.utc)
    kick = now + timedelta(hours=2)

    root = tmp_path / "repo"
    # Write an older archive pull
    archive_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=01"
    archive_dir.mkdir(parents=True, exist_ok=True)
    old_pull = (now - timedelta(hours=5)).isoformat()
    pd.DataFrame([{
        "event_id": EVENT_ID, "commence_time": kick.isoformat(),
        "home_team": HOME_FULL, "away_team": AWAY_FULL,
        "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
        "player_name": "T.Kelce", "line": 5.5,
        "over_price": -110, "under_price": -110,
        "pull_timestamp": old_pull,
    }]).to_parquet(archive_dir / "data_old.parquet", index=False)

    # Write a newer manual/scratch pull
    manual_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "manual"
    manual_dir.mkdir(parents=True, exist_ok=True)
    new_pull = (now - timedelta(minutes=15)).isoformat()
    pd.DataFrame([{
        "event_id": EVENT_ID, "commence_time": kick.isoformat(),
        "home_team": HOME_FULL, "away_team": AWAY_FULL,
        "bookmaker": "hardrockbet_fl", "market_key": "player_receptions",
        "player_name": "T.Kelce", "line": 5.5,
        "over_price": -120, "under_price": +100,
        "pull_timestamp": new_pull,
    }]).to_parquet(manual_dir / "scratch_20261001T120000Z.parquet", index=False)

    # Override module globals
    import nfl.sim.run_forward_v1 as fwd
    old_props = fwd.PROPS_DIR
    fwd.PROPS_DIR = root / "data" / "odds_archive" / "nfl" / "props"
    try:
        props = _load_props_at_T(2026, now)
        assert len(props) == 1, f"Expected 1 row, got {len(props)}"
        # The newest pull should be the manual one (-120, not -110)
        assert props.iloc[0]["over_price"] == -120, (
            f"Expected -120 from manual pull, got {props.iloc[0]['over_price']}")
    finally:
        fwd.PROPS_DIR = old_props
