"""Gate tests for pull_nfl_results.py and event_crosswalk NFL path — RED first, then GREEN.

OPS2b Item 1.
"""
import os, sys, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---- (a) empty results folder → SystemExit ----
def test_empty_folder_halts(tmp_path):
    import picks_ledger as pl
    import event_crosswalk as ec

    nfl_dir = tmp_path / "nfl"
    nfl_dir.mkdir()
    with pytest.raises(pl.Halt, match="empty"):
        os.environ["RESULTS_ARCHIVE_DIR"] = str(tmp_path)
        try:
            ec._load_nfl_officials(tmp_path)
        finally:
            os.environ.pop("RESULTS_ARCHIVE_DIR", None)


# ---- (b) 48h-old file → SystemExit ----
def test_stale_file_halts(tmp_path):
    import picks_ledger as pl
    import event_crosswalk as ec

    nfl_dir = tmp_path / "nfl"
    nfl_dir.mkdir()
    # Create a file with old mtime
    f = nfl_dir / "schedules_2026_20260901T000000Z.parquet"
    sched = pd.DataFrame({
        "game_id": ["2026_01_KC_DET"], "season": [2026], "week": [1],
        "gameday": ["2026-09-10"], "gametime": ["20:20"],
        "home_team": ["DET"], "away_team": ["KC"],
        "home_score": [24.0], "away_score": [17.0], "game_type": ["REG"],
    })
    sched.to_parquet(f, index=False)
    # Set mtime to 48h ago
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).timestamp()
    os.utime(f, (old_ts, old_ts))

    with pytest.raises(pl.Halt, match="stale"):
        os.environ["RESULTS_ARCHIVE_DIR"] = str(tmp_path)
        try:
            ec._load_nfl_officials(tmp_path)
        finally:
            os.environ.pop("RESULTS_ARCHIVE_DIR", None)


# ---- (c) fresh file with 3 games crosswalks exactly those 3 ----
def test_fresh_file_crosswalks(tmp_path):
    import event_crosswalk as ec

    nfl_dir = tmp_path / "nfl"
    nfl_dir.mkdir()
    sched = pd.DataFrame({
        "game_id": ["2026_01_KC_DET", "2026_01_BUF_MIA", "2026_01_PHI_GB"],
        "season": [2026, 2026, 2026], "week": [1, 1, 1],
        "gameday": ["2026-09-10", "2026-09-14", "2026-09-14"],
        "gametime": ["20:20", "13:00", "16:25"],
        "home_team": ["DET", "MIA", "GB"],
        "away_team": ["KC", "BUF", "PHI"],
        "home_score": [24.0, 17.0, 31.0],
        "away_score": [17.0, 20.0, 28.0],
        "game_type": ["REG", "REG", "REG"],
    })
    f = nfl_dir / "schedules_2026_20260915T090000Z.parquet"
    sched.to_parquet(f, index=False)

    events = pd.DataFrame({
        "event_id": ["a" * 32, "b" * 32, "c" * 32],
        "home_team": ["Detroit Lions", "Miami Dolphins", "Green Bay Packers"],
        "away_team": ["Kansas City Chiefs", "Buffalo Bills", "Philadelphia Eagles"],
        "commence_time": [
            "2026-09-11T00:20:00+00:00",
            "2026-09-14T17:00:00+00:00",
            "2026-09-14T20:25:00+00:00",
        ],
    })

    os.environ["RESULTS_ARCHIVE_DIR"] = str(tmp_path)
    try:
        officials = ec._load_nfl_officials(tmp_path)
        xw, unmatched = ec.build_crosswalk(
            events, officials, "NFL",
            team_map=lambda n: ec._nfl_team_norm(n))
    finally:
        os.environ.pop("RESULTS_ARCHIVE_DIR", None)

    assert len(xw) == 3
    assert len(unmatched) == 0
    assert set(xw.event_id) == {"a" * 32, "b" * 32, "c" * 32}


# ---- (d) no nflreadpy in event_crosswalk.py; P0.3 grep stays empty ----
def test_no_nflreadpy_in_crosswalk():
    src = Path(__file__).resolve().parent.parent / "event_crosswalk.py"
    text = src.read_text()
    assert "nflreadpy" not in text, "event_crosswalk.py still imports nflreadpy"


def test_no_network_imports_in_crosswalk():
    src = Path(__file__).resolve().parent.parent / "event_crosswalk.py"
    text = src.read_text()
    for pat in ("requests", "httpx", "urlopen"):
        assert pat not in text, f"event_crosswalk.py contains '{pat}'"


# ---- (e) pull_nfl_results HALTs on a 10-row frame (monkeypatched) ----
def test_pull_halts_on_small_frame():
    import pull_nfl_results as pnr
    small = pd.DataFrame({
        "game_id": [f"g{i}" for i in range(10)],
        "season": [2026] * 10, "week": [1] * 10,
        "gameday": ["2026-09-10"] * 10, "gametime": ["20:20"] * 10,
        "home_team": ["DET"] * 10, "away_team": ["KC"] * 10,
        "home_score": [24.0] * 10, "away_score": [17.0] * 10,
        "game_type": ["REG"] * 10,
    })

    mock_sched = MagicMock()
    mock_sched.to_pandas.return_value = small

    with patch("pull_nfl_results.nflreadpy") as mock_nfl:
        mock_nfl.load_schedules.return_value = mock_sched
        with pytest.raises(SystemExit) as exc_info:
            pnr.pull()
        assert exc_info.value.code == 1
