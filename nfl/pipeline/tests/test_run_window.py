"""Test: run_window.py — OPS4b + OPS4c + OPS-R2 tests.

OPS4b: --no-pull STOPs when freeze HALTs on kicked games.
OPS4c: --tag prekick accepted by puller; --auto-prekick gates on kick window;
       --commit branch:<name> produces a commit.
OPS-R2 Item 1 (P56): one tape per window — a newer snapshot between sheet and freeze
       must NOT cause the freeze to HALT.
OPS-R2 Item 2 (P57): prekick slot 2h45–3h12 + double-fire guard + git-pull retry.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable


class TestRunWindowHalt:
    """--no-pull run on a fixture tree STOPs when freeze HALTs (kicked games)."""

    def test_freeze_halts_on_kicked_games(self, tmp_path):
        """A sheet with only kicked games -> freeze HALTs -> run_window exits non-zero."""
        # Build a fixture tree with props and lines where all games have kicked
        kicked_time = "2026-09-20T17:00:00Z"  # in the past

        # Props with a kicked game
        props_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=09"
        props_dir.mkdir(parents=True)
        props = pd.DataFrame([{
            "sport": "nfl", "event_id": "kicked_ev1", "game_date": "2026-09-20",
            "commence_time": kicked_time,
            "home_team": "Buffalo Bills", "away_team": "New England Patriots",
            "bookmaker": "hardrockbet_fl", "market_key": "player_pass_yds",
            "last_update": "2026-09-20T14:00:00Z", "player_name": "Test QB",
            "line": 250.5, "over_price": -110, "under_price": -110,
            "implied_over": 0.524, "implied_under": 0.524,
            "pull_batch": "test", "pull_timestamp": "2026-09-20T14:00:00+00:00",
            "snapshot_tag": "mid",
        }])
        props.to_parquet(props_dir / "data_2026_09.parquet", index=False)

        # Game-line snapshot
        lines_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        lines_dir.mkdir(parents=True)
        lines = pd.DataFrame([
            {"snapshot_utc": "2026-09-20T14:00:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "kicked_ev1",
             "commence_time": kicked_time,
             "home_team": "Buffalo Bills", "away_team": "New England Patriots",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-09-20T14:00:00Z",
             "market": "h2h", "outcome_name": "Buffalo Bills", "point": None, "price": -180},
            {"snapshot_utc": "2026-09-20T14:00:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "kicked_ev1",
             "commence_time": kicked_time,
             "home_team": "Buffalo Bills", "away_team": "New England Patriots",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-09-20T14:00:00Z",
             "market": "h2h", "outcome_name": "New England Patriots", "point": None, "price": 150},
        ])
        lines.to_parquet(lines_dir / "snap_20260920T140000Z.parquet", index=False)

        # Empty Kalshi/NWS dirs
        (tmp_path / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").mkdir(parents=True)
        (tmp_path / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026").mkdir(parents=True)

        # Board dir
        (tmp_path / "nfl" / "data" / "board").mkdir(parents=True)

        # run_window should HALT because all games have kicked
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "run_window.py"),
             "--sport", "nfl", "--window", "adhoc", "--no-pull",
             "--reader-model", "test-model", "--week", "3"],
            cwd=str(tmp_path),
            capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                 "MLB_REPO_ROOT": str(tmp_path),
                 "PYTHONPATH": str(ROOT),
                 "HOME": str(Path.home())},
            timeout=120)

        # Should exit non-zero (HALT from sheet or freeze)
        assert result.returncode != 0, (
            f"Expected non-zero exit (HALT on kicked games), got 0.\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}")


# ---- OPS4c Item 2 ----

class TestPullerTagPrekick:
    """--tag prekick must be accepted by pull_hardrock_props.py argparse."""

    def test_tag_prekick_accepted(self):
        """--tag prekick --dry-run should NOT exit with argparse error."""
        result = subprocess.run(
            [PY, str(ROOT / "nfl" / "pipeline" / "pull_hardrock_props.py"),
             "--window-hours", "6", "--tag", "prekick", "--dry-run"],
            capture_output=True, text=True, timeout=30,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                 "HOME": str(Path.home()),
                 "PYTHONPATH": str(ROOT),
                 "ODDS_API_KEY": ""})
        # argparse error = exit 2 with "invalid choice"
        assert "invalid choice" not in result.stderr, \
            f"--tag prekick rejected by argparse: {result.stderr[:300]}"


class TestAutoPreKick:
    """--auto-prekick gates on the kick window."""

    def test_no_game_in_slot(self):
        """Fixture snapshot with game 5h away → 'no game in the prekick slot', exit 0."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import run_window as rw
        # A game 5 hours from now is outside the [2h52m, 3h08m] window
        future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        result = rw._check_prekick_slot([future])
        assert result is False, f"game at +5h should NOT be in prekick slot"

    def test_game_in_slot(self):
        """Fixture snapshot with game at +3h 00m → in the slot → should freeze."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import run_window as rw
        future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        result = rw._check_prekick_slot([future])
        assert result is True, f"game at +3h should be in prekick slot"


# ---- OPS-R2 Item 1 (P56): one tape per window ----

class TestResolvePinning:
    """P56: resolve_inputs returns file paths, and pinning prevents tape races."""

    def _fixture_tape(self, tmp_path):
        """Build a two-snapshot fixture: snap A and snap B with DIFFERENT events."""
        kick = "2026-12-01T18:00:00+00:00"
        props_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=12"
        props_dir.mkdir(parents=True)
        props = pd.DataFrame([{
            "sport": "nfl", "event_id": "ev_A", "game_date": "2026-12-01",
            "commence_time": kick,
            "home_team": "Buffalo Bills", "away_team": "Miami Dolphins",
            "bookmaker": "hardrockbet_fl", "market_key": "player_pass_yds",
            "last_update": "2026-12-01T12:00:00Z", "player_name": "QB A",
            "line": 250.5, "over_price": -110, "under_price": -110,
            "implied_over": 0.524, "implied_under": 0.524,
            "pull_batch": "test", "pull_timestamp": "2026-12-01T12:00:00+00:00",
            "snapshot_tag": "mid",
        }])
        props.to_parquet(props_dir / "data_2026_12.parquet", index=False)

        lines_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
        lines_dir.mkdir(parents=True)
        # Snapshot A: 14:00Z
        lines_a = pd.DataFrame([
            {"snapshot_utc": "2026-12-01T14:00:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "ev_A",
             "commence_time": kick,
             "home_team": "Buffalo Bills", "away_team": "Miami Dolphins",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-12-01T14:00:00Z",
             "market": "h2h", "outcome_name": "Buffalo Bills", "point": None, "price": -180},
            {"snapshot_utc": "2026-12-01T14:00:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "ev_A",
             "commence_time": kick,
             "home_team": "Buffalo Bills", "away_team": "Miami Dolphins",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-12-01T14:00:00Z",
             "market": "h2h", "outcome_name": "Miami Dolphins", "point": None, "price": 150},
        ])
        lines_a.to_parquet(lines_dir / "snap_20261201T140000Z.parquet", index=False)
        # Snapshot B: 14:30Z — adds a second event the props don't cover
        lines_b = lines_a.copy()
        lines_b["snapshot_utc"] = "2026-12-01T14:30:00+00:00"
        extra = pd.DataFrame([
            {"snapshot_utc": "2026-12-01T14:30:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "ev_B",
             "commence_time": kick,
             "home_team": "New York Jets", "away_team": "New England Patriots",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-12-01T14:30:00Z",
             "market": "h2h", "outcome_name": "New York Jets", "point": None, "price": -150},
            {"snapshot_utc": "2026-12-01T14:30:00+00:00",
             "sport": "americanfootball_nfl", "event_id": "ev_B",
             "commence_time": kick,
             "home_team": "New York Jets", "away_team": "New England Patriots",
             "bookmaker": "hardrockbet_fl", "book_last_update": "2026-12-01T14:30:00Z",
             "market": "h2h", "outcome_name": "New England Patriots", "point": None, "price": 130},
        ])
        lines_b = pd.concat([lines_b, extra], ignore_index=True)
        lines_b.to_parquet(lines_dir / "snap_20261201T143000Z.parquet", index=False)
        return props_dir, lines_dir

    def test_resolve_inputs_exists(self):
        """resolve_inputs is importable from log_ai_opinions — RED until Item 1 adds it."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import log_ai_opinions as lao
        importlib.reload(lao)
        assert hasattr(lao, "resolve_inputs"), "log_ai_opinions has no resolve_inputs function"

    def test_resolve_returns_paths(self, tmp_path):
        """resolve_inputs returns (props_path, lines_path) strings."""
        self._fixture_tape(tmp_path)
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import log_ai_opinions as lao
        importlib.reload(lao)
        lao.set_sport("nfl")
        # Point module at fixture dirs
        lao.PROPS_DIR = tmp_path / "data" / "odds_archive" / "nfl" / "props"
        lao.LINES_DIR = tmp_path / "data" / "odds_archive" / "nfl" / "line_history"
        now = datetime.fromisoformat("2026-12-01T14:15:00+00:00")
        props_path, lines_path = lao.resolve_inputs(2026, now)
        assert props_path is not None and Path(props_path).exists()
        assert lines_path is not None and Path(lines_path).exists()

    def test_pinned_snapshot_deterministic(self, tmp_path):
        """Sheet built twice on pinned files is identical (determinism)."""
        self._fixture_tape(tmp_path)
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import log_ai_opinions as lao
        importlib.reload(lao)
        lao.set_sport("nfl")
        lao.PROPS_DIR = tmp_path / "data" / "odds_archive" / "nfl" / "props"
        lao.LINES_DIR = tmp_path / "data" / "odds_archive" / "nfl" / "line_history"
        now = datetime.fromisoformat("2026-12-01T14:15:00+00:00")
        props_path, lines_path = lao.resolve_inputs(2026, now)
        s1 = lao.build_sheet(*lao.newest_inputs(2026, now, props_file=props_path, lines_file=lines_path), now)
        s2 = lao.build_sheet(*lao.newest_inputs(2026, now, props_file=props_path, lines_file=lines_path), now)
        assert s1.equals(s2), "sheets differ on the same pinned files"


# ---- OPS-R2 Item 2 (P57): prekick slot + double-fire guard + git-pull retry ----

class TestPrekickSlot:
    """P57(a): PREKICK_LOW/HIGH are 2h45/3h12."""

    def test_prekick_bounds(self):
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import run_window as rw
        importlib.reload(rw)
        assert rw.PREKICK_LOW == timedelta(hours=2, minutes=45), f"PREKICK_LOW={rw.PREKICK_LOW}"
        assert rw.PREKICK_HIGH == timedelta(hours=3, minutes=12), f"PREKICK_HIGH={rw.PREKICK_HIGH}"

    def test_slot_coverage(self):
        """Every kick minute (:00,:05,:15,:20,:25,:30) has at least one tick in the slot."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import run_window as rw
        importlib.reload(rw)
        kick_mins = [0, 5, 15, 20, 25, 30]
        tick_offsets = [8, 23, 38, 53]  # VM cron :08/:23/:38/:53
        for km in kick_mins:
            hits = []
            for to in tick_offsets:
                # delta = kick - tick in minutes (from tick to kick)
                delta_min = km + 180 - to  # kicks at HH:km, tick at (HH-3):to
                if rw.PREKICK_LOW.total_seconds() / 60 <= delta_min <= rw.PREKICK_HIGH.total_seconds() / 60:
                    hits.append(to)
            assert len(hits) > 0, f"kick at :0{km} has no tick in [{rw.PREKICK_LOW}, {rw.PREKICK_HIGH}]"


class TestDoubleFire:
    """P57(b): if a prekick freeze for the same events exists within 20 min, skip."""

    def test_double_fire_guard_exists(self):
        """run_window must have _check_recent_prekick function."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import run_window as rw
        importlib.reload(rw)
        assert hasattr(rw, "_check_recent_prekick"), "no _check_recent_prekick function"

    def test_double_fire_skips(self, tmp_path):
        """A manifest with a prekick freeze 10 min ago -> guard returns True (skip)."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import run_window as rw
        importlib.reload(rw)
        now = datetime(2026, 12, 1, 15, 30, tzinfo=timezone.utc)
        manifest_dir = tmp_path / "nfl" / "data" / "board" / "week=2026_13" / "ai_opinions"
        manifest_dir.mkdir(parents=True)
        entry = [{"file": "test.parquet", "sha256": "abc", "logged_utc": "2026-12-01T15:20:00+00:00",
                  "window": "prekick", "first_kickoff_utc": "2026-12-01T18:00:00+00:00"}]
        (manifest_dir / "manifest.json").write_text(json.dumps(entry))
        assert rw._check_recent_prekick(manifest_dir, "prekick", now) is True


class TestGitPullRetry:
    """P57(c): git pull retries 3x before STOP."""

    def test_git_pull_retry_exists(self):
        """run_window must have _run_git_pull_with_retry."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import importlib
        import run_window as rw
        importlib.reload(rw)
        assert hasattr(rw, "_run_git_pull_with_retry"), "no _run_git_pull_with_retry function"
