#!/usr/bin/env python3
"""N41: every _pulls.jsonl line names its feed, and the ESPN hash-skip reads only its own.

The log lines below are the real ones from data/depth_archive/nfl/season=2026/_pulls.jsonl
(2026-09-20 06:30Z ESPN depth, then the three 09:00Z nflverse lines).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

ESPN_SHA = "e00ed75fc47a42cdaee6bcbb33b2f9c49fcd0f8f0ec7df613ebc9d7ef59a6b7d"
REAL_LINES = [
    {"utc": "20260920T0630Z", "sha256": ESPN_SHA, "status": "written"},
    {"utc": "20260920T0900Z", "file": "depth_charts.parquet",
     "sha256": "d23685857746fb7cc9ef2032fb8f0efece33e17fa0bf27fcec0e56193bd65ee0",
     "max_dt": "2026-09-20T06:02:02+00:00", "rows": 2243, "status": "delta"},
    {"utc": "20260920T0900Z", "file": "injuries.parquet",
     "sha256": "150ac873eee064521d069c356bbdc3b19d1d43de95e6fecc30bd5620e0aa6f15", "status": "written"},
    {"utc": "20260920T0900Z", "file": "rosters_weekly.parquet",
     "sha256": "bc551ac1a5fe48cce601a1dc517b1dee0310ce8c3cc194360d457272415ab696", "status": "written"},
]


def _write(path, lines):
    path.write_text("".join(json.dumps(l) + "\n" for l in lines))


def test_espn_hash_skip_ignores_nflverse_lines(tmp_path):
    """After the 09:00Z nflverse run the LAST line is rosters'. ESPN must still find its own."""
    from shared.pipeline.pull_espn_nfl_status import _last_hash
    log = tmp_path / "_pulls.jsonl"
    _write(log, REAL_LINES)
    assert _last_hash(log, "espn_depth") == ESPN_SHA


def test_every_writer_names_its_feed(tmp_path):
    from shared.pipeline.pull_espn_nfl_status import _log_pull
    log = tmp_path / "_pulls.jsonl"
    _log_pull(log, "20260920T1230Z", ESPN_SHA, "unchanged", "espn_depth")
    assert json.loads(log.read_text().strip())["feed"] == "espn_depth"
    assert '"feed": "nflverse_depth"' in (ROOT / "shared/pipeline/archive_nflverse_depth_delta.py").read_text()
    sh = (ROOT / "shared/pipeline/run_nflverse_with_archive.sh").read_text()
    assert sh.count('\\"feed\\":\\"nflverse_${name%_weekly}\\"') == 2


def test_unchanged_espn_pull_counts_as_a_pulse(tmp_path):
    """A quiet day: ESPN depth unchanged at 12:30Z. Health must read 12:30, not 06:30 or 09:00."""
    from shared.pipeline.capture_health import _newest_pulls_age_by_feed
    from shared.pipeline.pull_espn_nfl_status import _log_pull
    log = tmp_path / "_pulls.jsonl"
    _write(log, REAL_LINES)
    now = datetime(2026, 9, 20, 13, 45, tzinfo=timezone.utc)
    # legacy bare line is ESPN's: 06:30 -> 7.25 h
    assert abs(_newest_pulls_age_by_feed(log, "espn_depth", now) - 7.25) < 0.01
    # nflverse lines never lend ESPN their pulse, nor the reverse
    assert abs(_newest_pulls_age_by_feed(log, "nflverse_depth", now) - 4.75) < 0.01
    _log_pull(log, "20260920T1230Z", ESPN_SHA, "unchanged", "espn_depth")
    assert abs(_newest_pulls_age_by_feed(log, "espn_depth", now) - 1.25) < 0.01
    assert abs(_newest_pulls_age_by_feed(log, "nflverse_depth", now) - 4.75) < 0.01
