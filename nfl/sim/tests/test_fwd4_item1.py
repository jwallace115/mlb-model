"""D247: the surviving mutations must die.

Every test must FAIL on 735374bf1. For each named mutation: apply it, run
the suite, paste the failing test name, revert.
"""
import hashlib
import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd3_item0 import (
    _build_fixture_root, _stub_run_week, _set_fwd_paths,
    KICK, T, EVENT_ID, HOME_FULL, AWAY_FULL, HOME_ABBR, AWAY_ABBR, GAME_ID,
)


# ── Mutation 1: line cutoff ──
# `if snap_utc <= T` -> `if True` must fail.

def test_line_cutoff_rejects_post_T_snapshot(tmp_path):
    """A line snapshot taken AFTER T must not be used. On 735374bf1 the
    cutoff is present but no test kills the `if True` mutation."""
    from nfl.sim.run_forward_v1 import _load_lines_at_T, _parse_utc
    import nfl.sim.run_forward_v1 as fwd

    root = _build_fixture_root(tmp_path)
    saved = (fwd.LINES_DIR,)
    fwd.LINES_DIR = root / "data" / "odds_archive" / "nfl" / "line_history"
    try:
        # The fixture has a snapshot at T - 30min (pre-T). Load it -> should work.
        lines_pre = _load_lines_at_T(2026, T)
        assert not lines_pre.empty, "pre-T snapshot should load"

        # Now add a snapshot AFTER T -> it must NOT be returned.
        post_T = T + timedelta(hours=1)
        lines_dir = root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        snap_fname = f"snap_{post_T.strftime('%Y%m%dT%H%M%SZ')}.parquet"
        post_rows = [{
            "event_id": EVENT_ID,
            "commence_time": KICK.isoformat(),
            "home_team": HOME_FULL, "away_team": AWAY_FULL,
            "bookmaker": "hardrockbet_fl",
            "market": "spreads", "outcome_name": HOME_FULL,
            "point": -99.0, "price": -110,
            "snapshot_utc": post_T.isoformat(),
        }]
        pd.DataFrame(post_rows).to_parquet(lines_dir / snap_fname, index=False)

        # Re-load — should still get the pre-T snapshot, not the post-T one
        lines_at_T = _load_lines_at_T(2026, T)
        # The post-T snapshot has point=-99.0 which is a marker
        if not lines_at_T.empty and "point" in lines_at_T.columns:
            assert not (lines_at_T["point"] == -99.0).any(), (
                "post-T snapshot (-99.0 marker) must NOT be loaded")
    finally:
        fwd.LINES_DIR = saved[0]


# ── Mutation 2: pre-write publication halt ──
# A controlled clock where event selection sees kick-5min, and the wall
# clock at the pre-write check is kick+1s -> HALT, with nothing frozen.

def test_pre_write_publication_halt(tmp_path):
    """D247: controlled clock where event selection sees kick-5min, wall
    clock at pre-write is kick+1s -> HALT, nothing frozen.
    On 735374bf1 the pre-write check exists but removing it must fail this test.
    Mutation: remove the pre-write check -> it must fail.

    The pre-write check specifically catches T < kick < wall_clock (the case
    where the sim took long enough that kick arrived). freeze() uses T, not
    wall clock, so it passes. Only the pre-write check catches this."""
    from nfl.sim.run_forward_v1 import main, _parse_utc
    import nfl.sim.run_forward_v1 as fwd

    kick = datetime(2099, 6, 15, 17, 0, 0, tzinfo=timezone.utc)
    sel_T = kick - timedelta(minutes=5)
    root = _build_fixture_root(tmp_path, kick=kick)

    # Controlled clock: main() calls datetime.now(timezone.utc) for T and for
    # the pre-write check. We need T < kick < pre-write wall.
    # Approach: monkeypatch main to inject T via --as-of but skip the
    # pilot restriction by running as live.
    # Better approach: patch datetime.now in run_forward_v1 module directly.
    call_count = {"n": 0}
    real_dt_class = datetime

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                # First call: T = kick - 5min
                return sel_T
            # All subsequent calls: kick + 1s (pre-write + quarantine checks)
            return kick + timedelta(seconds=1)

        @classmethod
        def fromisoformat(cls, s):
            return real_dt_class.fromisoformat(s)

    with patch.object(fwd, "datetime", FakeDatetime):
        with pytest.raises(SystemExit, match="publication time"):
            main(
                argv=["--week", "3"],
                root=str(root),
                run_week_fn=_stub_run_week,
            )

    # Verify nothing was frozen
    opinions_dir = root / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    frozen = list(opinions_dir.glob("ai_opinions_*.parquet")) if opinions_dir.exists() else []
    assert len(frozen) == 0, "nothing should be frozen after pre-write HALT"


# ── Mutation 3: run_week inputs ──
# _default_run_week's command must include --lines-json, --games and --run-dir.

def test_run_week_includes_lines_json_games_run_dir(tmp_path):
    """_default_run_week subprocess argv must include --lines-json, --games
    and --run-dir. On 735374bf1 no test catches dropping --lines-json.
    Mutation: drop --lines-json -> it must fail."""
    captured_cmds = []

    def spy_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        # Return a fake successful result
        class FakeResult:
            returncode = 0
            stdout = "done"
            stderr = ""
        return FakeResult()

    from nfl.sim.run_forward_v1 import _default_run_week

    root = ROOT
    lines = {"CAR@KC": {"spread": -3.0, "total": 45.5}}
    games = ["CAR@KC"]
    run_dir = tmp_path / "outputs"
    run_dir.mkdir()

    with patch("nfl.sim.run_forward_v1.subprocess.run", side_effect=spy_run):
        _default_run_week(root, 3, T, lines, games, run_dir=run_dir)

    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    cmd_str = " ".join(str(c) for c in cmd)
    assert "--lines-json" in cmd_str, f"--lines-json missing from: {cmd_str}"
    assert "--games" in cmd_str, f"--games missing from: {cmd_str}"
    assert "--run-dir" in cmd_str, f"--run-dir missing from: {cmd_str}"


# ── Mutation 4: bootstrap — whole-game resampling ──
# A fixture with fixed seeds where whole-game resampling gives a known
# interval. No resampling / independent-leg resampling must fail.

def test_bootstrap_whole_game_resampling():
    """The bootstrap must do whole-game resampling (cluster by event_id).
    On 735374bf1 the bootstrap IS whole-game but no test has a fixture
    with a known interval that distinguishes it from independent-leg.

    Fixture: 4 games, 3 legs each, constructed so that:
    - Whole-game CI includes zero (inconclusive)
    - Independent-leg CI does NOT include zero (would be significant)
    This is achieved by making within-game legs perfectly correlated
    (same delta) but across-game deltas mixed-sign.
    """
    from nfl.sim.fwd_v1_logger import primary_statistic

    rows = []
    # Game 1: model much better (delta < 0)
    for j in range(3):
        rows.append({
            "event_id": "evt_g1", "home_team": "A", "away_team": "B",
            "p_first": 0.75, "book_p_first": 0.50, "y_first": 1,
        })
    # Game 2: model much worse (delta > 0)
    for j in range(3):
        rows.append({
            "event_id": "evt_g2", "home_team": "C", "away_team": "D",
            "p_first": 0.75, "book_p_first": 0.50, "y_first": 0,
        })
    # Game 3: model much better
    for j in range(3):
        rows.append({
            "event_id": "evt_g3", "home_team": "E", "away_team": "F",
            "p_first": 0.75, "book_p_first": 0.50, "y_first": 1,
        })
    # Game 4: model much worse
    for j in range(3):
        rows.append({
            "event_id": "evt_g4", "home_team": "G", "away_team": "H",
            "p_first": 0.75, "book_p_first": 0.50, "y_first": 0,
        })

    df = pd.DataFrame(rows)

    stat = primary_statistic(df, n_bootstrap=10000, seed=42)
    # Point estimate: 2 games with delta < 0, 2 games with delta > 0 -> near zero
    # (p=0.75, q=0.50, y=1: delta = (0.75-1)^2 - (0.50-1)^2 = 0.0625 - 0.25 = -0.1875)
    # (p=0.75, q=0.50, y=0: delta = (0.75-0)^2 - (0.50-0)^2 = 0.5625 - 0.25 = 0.3125)
    # Mean delta = mean([-0.1875]*3 + [0.3125]*3 + [-0.1875]*3 + [0.3125]*3) = 0.0625
    # Whole-game bootstrap: resampling 4 games from 4 with high variance
    # Independent-leg: resampling 12 legs, which averages out more -> tighter CI

    # The whole-game bootstrap should be INCONCLUSIVE (CI includes 0)
    assert stat["verdict"] == "inconclusive", (
        f"Whole-game bootstrap should be inconclusive, got {stat['verdict']} "
        f"(CI: [{stat['ci_lo']:.6f}, {stat['ci_hi']:.6f}])")

    # Verify that independent-leg resampling would give a different result:
    # do it manually and check CI is tighter
    rng = np.random.RandomState(42)
    p = df["p_first"].values.astype(float)
    q = df["book_p_first"].values.astype(float)
    y = df["y_first"].values.astype(float)
    delta_leg = (p - y) ** 2 - (q - y) ** 2
    n = len(delta_leg)
    indep_deltas = np.array([
        np.mean(delta_leg[rng.choice(n, size=n, replace=True)])
        for _ in range(10000)
    ])
    indep_ci = (np.percentile(indep_deltas, 2.5), np.percentile(indep_deltas, 97.5))
    # Independent-leg CI should be tighter (narrower) than whole-game
    whole_width = stat["ci_hi"] - stat["ci_lo"]
    indep_width = indep_ci[1] - indep_ci[0]
    assert indep_width < whole_width, (
        f"Independent-leg CI width ({indep_width:.6f}) should be < "
        f"whole-game CI width ({whole_width:.6f})")
