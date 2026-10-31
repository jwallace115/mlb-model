"""P80 (RED first): a 9:47 AM ET sweep must not mark the morning sweep; the 10:02 tick must still be a sweep."""
from datetime import datetime, timezone
from shared.pipeline import window_watch as ww


def test_pre_ten_sweep_does_not_preempt_morning_anchor(tmp_path):
    (tmp_path / "status").mkdir()
    t947 = datetime(2026, 10, 31, 13, 47, tzinfo=timezone.utc)   # 9:47 AM EDT
    ww.record_sweep("nfl", t947, tmp_path)
    state = ww._load_watch_state(tmp_path)
    assert "morning_sweep_nfl:2026-10-31" not in state
    t1002 = datetime(2026, 10, 31, 14, 2, tzinfo=timezone.utc)  # 10:02 AM EDT, Sunday slate 28 h out
    cadence, why = ww.decide_cadence("nfl", 28.0, t1002, tmp_path)
    assert cadence == "sweep" and "anchor_morning" in why


def test_ten_am_sweep_marks_morning_once(tmp_path):
    (tmp_path / "status").mkdir()
    t1002 = datetime(2026, 10, 31, 14, 2, tzinfo=timezone.utc)
    ww.record_sweep("nfl", t1002, tmp_path)
    assert "morning_sweep_nfl:2026-10-31" in ww._load_watch_state(tmp_path)
    t1017 = datetime(2026, 10, 31, 14, 17, tzinfo=timezone.utc)
    cadence, _ = ww.decide_cadence("nfl", 27.8, t1017, tmp_path)
    assert cadence == "quiet"
