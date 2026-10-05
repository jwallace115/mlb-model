"""Tests for shared/pipeline/pipeline_health.py — each status must be reachable, and a dead feed must go red."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_health as ph  # noqa: E402

NOW = datetime(2026, 10, 1, 19, 27, tzinfo=timezone.utc)


def _touch(p: Path, when: datetime, text=""):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    ts = when.timestamp()
    os.utime(p, (ts, ts))


def _setup(tmp_path, feeds, crontab):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"feeds": feeds}))
    ct = tmp_path / "crontab.txt"
    ct.write_text(crontab)
    return reg, ct


def _status(res, fid):
    return next(f for f in res["feeds"] if f["id"] == fid)["status"]


def test_cron_due_times_match_known_counts():
    s = NOW - timedelta(days=7)
    assert len(ph.due_times(["*/30 14-23,0-5 * * *"], s, NOW)) == 224
    assert len(ph.due_times(["0 14 * * 3-6"], s, NOW)) == 4
    assert len(ph.due_times(["5,35 0-5,14-23 * * *"], s, NOW)) == 224


def test_fresh_feed_is_firing_and_dead_feed_is_silent(tmp_path):
    root = tmp_path / "repo"
    log = tmp_path / "k.log"
    _touch(root / "a/snap_20261001T1905Z.parquet", NOW)
    _touch(root / "b/snap_20261001T1505Z.parquet", NOW)  # 4h old on a 30-min cadence
    _touch(log, NOW - timedelta(minutes=20), "ok\n")
    feeds = [
        {"id": "fresh", "cron_match": "pull_a.py", "outputs": ["a/snap_*Z.parquet"]},
        {"id": "dead", "cron_match": "pull_b.py", "outputs": ["b/snap_*Z.parquet"]},
    ]
    ct = f"5,35 * * * * python3 pull_a.py >> {log} 2>&1\n5,35 * * * * python3 pull_b.py >> {log} 2>&1\n"
    reg, ctf = _setup(tmp_path, feeds, ct)
    res = ph.build(NOW, root, str(ctf), str(reg), with_host=False)
    assert _status(res, "fresh") == "FIRING"
    assert _status(res, "dead") == "SILENT"


def test_one_missed_slot_is_late(tmp_path):
    root = tmp_path / "repo"
    _touch(root / "a/snap_20261001T1835Z.parquet", NOW)  # 19:05 slot missing, 18:35 present
    reg, ctf = _setup(tmp_path, [{"id": "x", "cron_match": "pull_a.py", "outputs": ["a/snap_*Z.parquet"]}],
                      "5,35 * * * * python3 pull_a.py\n")
    res = ph.build(NOW, root, str(ctf), str(reg), with_host=False)
    assert _status(res, "x") == "LATE"


def test_crash_after_last_slot_is_erroring(tmp_path):
    root = tmp_path / "repo"
    log = tmp_path / "y.log"
    _touch(root / "m/yrfi.json", NOW - timedelta(days=100))
    _touch(log, NOW - timedelta(hours=7, minutes=57),
           "Traceback (most recent call last):\nrequests.exceptions.HTTPError: 406 Client Error\n")
    reg, ctf = _setup(tmp_path, [{"id": "y", "cron_match": "yrfi_shadow_daily.py", "outputs": ["m/yrfi.json"], "ts": "mtime"}],
                      f"30 11 * * * python3 yrfi_shadow_daily.py >> {log} 2>&1\n")
    res = ph.build(NOW, root, str(ctf), str(reg), with_host=False)
    assert _status(res, "y") == "ERRORING"


def test_quiet_and_off_season_and_missing_job(tmp_path):
    root = tmp_path / "repo"
    log = tmp_path / "p.log"
    _touch(root / "props/data.parquet", NOW - timedelta(days=2))
    _touch(log, NOW - timedelta(hours=5), "credits used: 0  events: 0\n")
    feeds = [
        {"id": "quiet", "cron_match": "props.py", "outputs": ["props/data.parquet"], "ts": "mtime", "quiet_ok": True},
        {"id": "off", "cron_match": "props.py", "outputs": ["props/data.parquet"], "ts": "mtime", "active_months": [4, 5]},
        {"id": "nojob", "cron_match": "basketball_nba", "outputs": ["x/*.parquet"]},
    ]
    reg, ctf = _setup(tmp_path, feeds, f"0 14 * * * python3 props.py >> {log} 2>&1\n")
    res = ph.build(NOW, root, str(ctf), str(reg), with_host=False)
    assert _status(res, "quiet") == "QUIET"
    assert _status(res, "off") == "OFF"
    assert _status(res, "nojob") == "NO_JOB"


def test_unregistered_cron_line_is_still_reported(tmp_path):
    root = tmp_path / "repo"
    log = tmp_path / "golf_grader.log"
    _touch(log, NOW - timedelta(minutes=10), "golf_daily_runner.py: error: argument --capture: invalid choice: 'grade'\n")
    reg, ctf = _setup(tmp_path, [], f"0 * * * * python3 golf.py --capture grade >> {log} 2>&1\n")
    res = ph.build(NOW, root, str(ctf), str(reg), with_host=False)
    assert any(f["id"].startswith("cron:golf_grader") and f["status"] == "ERRORING" for f in res["feeds"])
