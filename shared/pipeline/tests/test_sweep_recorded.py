"""RED first: a quiet sweep must record last_sweep (today it does not → sweeps every tick)."""
import json
from datetime import datetime, timezone, timedelta
from shared.pipeline import window_watch as ww


def test_quiet_sweep_records_last_sweep(tmp_path, monkeypatch):
    (tmp_path / "status").mkdir()
    now = datetime(2026, 10, 24, 21, 17, tzinfo=timezone.utc)
    # a slate with one game 15 h out and nothing changed → cadence sweep (last sweep 75 min ago), no triggers
    ww._save_watch_state({"last_sweep_nfl": (now - timedelta(minutes=75)).isoformat()}, tmp_path)
    cadence = ww.decide_cadence("nfl", 15.0, now, tmp_path)
    cadence = cadence[0] if isinstance(cadence, tuple) else cadence
    assert cadence == "sweep"
    # emulate the end of watch_once: the recording rule under test
    triggered = []
    if cadence == "sweep":
        ww.record_sweep("nfl", now, tmp_path)
    state = json.loads((tmp_path / "status" / "watch_state.json").read_text())
    assert state["last_sweep_nfl"] == now.isoformat()


def test_watch_once_source_records_sweep_without_triggers():
    import inspect
    src = inspect.getsource(ww.watch_once)
    assert 'if cadence == "sweep" and triggered' not in src
    assert "record_sweep(sport, now, root)" in src
