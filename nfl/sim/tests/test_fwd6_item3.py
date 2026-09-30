"""D259 (FWD6 item 3): tests that kill the freeze-side mutations that survived audit #8.

Each test names the mutation it exists for. The scoring-side survivors (game_snap None,
the below-500 branch, the bundle-digest rejection, the bootstrap seed) belong to FWD7.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nfl" / "pipeline" / "tests"))

from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _stub_run_week, T  # noqa: E402


def test_pinned_freeze_rejects_kicked_games():
    """Mutation: remove freeze()'s already-kicked-game rejection (fwd_v1_logger)."""
    import test_ai_opinions_n59 as T59
    from nfl.sim import fwd_v1_logger as P
    s = P.build_sheet(T59._props(), T59._lines(), T59.NOW)
    after_kick = P.parse_utc(T59.KICK) + timedelta(minutes=1)
    with pytest.raises(SystemExit, match="kicked off"):
        P.freeze(s, T59._filled(s), 2026, 4, True, after_kick, d=Path("/tmp/_never_written"),
                 reader_model="nfl_sim_v1_156cd057")


def test_write_finishing_after_kick_is_quarantined(tmp_path):
    """Mutation: disable the post-write quarantine. Controlled clock: T = kick-5 min, the
    pre-write check at kick-1 s (passes), the publication stamp at kick+1 s -> the file is
    moved to quarantine/, marked excluded, and no receipt is written."""
    import nfl.sim.run_forward_v1 as fwd
    kick = datetime(2099, 6, 15, 17, 0, 0, tzinfo=timezone.utc)
    root = _build_fixture_root(tmp_path, kick=kick)
    seq = [kick - timedelta(minutes=5), kick - timedelta(seconds=1)]
    real = datetime

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return seq.pop(0) if seq else kick + timedelta(seconds=1)

        @classmethod
        def fromisoformat(cls, s):
            return real.fromisoformat(s)

    with patch.object(fwd, "datetime", Clock):
        with pytest.raises(SystemExit, match="QUARANTINED"):
            fwd.main(argv=["--week", "3"], root=str(root), run_week_fn=_stub_run_week)
    op = root / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    assert not list(op.glob("ai_opinions_*.parquet")), "a late write stayed in the record"
    assert len(list((op / "quarantine").glob("ai_opinions_*.parquet"))) == 1
    assert fwd.load_receipts(root) == []


def test_depth_charts_and_injuries_are_copied_as_record(tmp_path):
    """Mutation: stop copying rosters, depth charts and injuries. Rosters are consumed
    (test_fwd6_item0); depth charts and injuries are not read by the prediction but are
    kept as the run's record."""
    from nfl.sim.run_forward_v1 import build_bundle
    import nfl.sim.run_forward_v1 as fwd
    from nfl.sim.tests.test_fwd3_item0 import _set_fwd_paths
    root = _build_fixture_root(tmp_path)
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        bd, man = build_bundle(2026, 3, T, pilot=True, allow_stale_quotes=True, _root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved
    for f in ("rosters_weekly.parquet", "depth_charts.parquet", "injuries.parquet"):
        src = root / "nfl" / "data" / "pbp" / f
        if src.exists():
            assert (bd / "inputs" / f).exists(), f"inputs/{f} not copied"
            assert f"inputs/{f}" in man


def test_duplicate_prediction_key_halts():
    """Mutation: remove fill_sheet's duplicate prediction-key rejection."""
    from nfl.sim.run_forward_v1 import fill_sheet
    sheet = pd.DataFrame([{
        "event_id": "e1", "home_team": "Kansas City Chiefs", "away_team": "Carolina Panthers",
        "market_key": "player_receptions", "player_name": "T.Kelce", "line": 5.5,
        "two_way": True, "q_first": 0.5, "imp_first": 0.52, "first_side": "over",
        "price_first": -110, "price_second": -110}])
    pick = {"game_id": "CAR@KC", "player_name": "T.Kelce", "family": "receptions",
            "line": 5.5, "cal_p": 0.62, "side": "over"}
    with pytest.raises(SystemExit, match="duplicate picks_log key"):
        fill_sheet(sheet, pd.DataFrame([pick, {**pick, "cal_p": 0.40}]),
                   event_game_map={"e1": "CAR@KC"})


def test_live_experiment_manifest_check_halts_in_main(tmp_path):
    """Mutation: remove the live experiment-manifest check from main(). A hashed file
    changed after stamping -> main() HALTs before building anything."""
    from nfl.sim.run_forward_v1 import main
    root = _build_fixture_root(tmp_path)
    f = root / "nfl" / "sim" / "seed_util.py"
    f.write_text(f.read_text() + "\n# changed after the stamp\n")
    with pytest.raises(SystemExit, match="experiment manifest hash mismatch"):
        main(argv=["--week", "3", "--pilot", "--as-of", T.isoformat(), "--allow-stale-quotes"],
             root=str(root), run_week_fn=_stub_run_week)
    assert not (root / "nfl" / "data" / "board" / "week=2026_03").exists()
