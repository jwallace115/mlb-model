#!/usr/bin/env python3
"""WO11 Item 4: feed health must not borrow another feed's pulse.

Fixture: _pulls.jsonl has a fresh ESPN depth line (10 min ago) followed by
a stale nflverse line (100h ago). The OLD health check reads the last line
whoever wrote it, so a fresh ESPN line makes stale nflverse read fresh.

Also: existing lines without `feed` are inferred from `file` key where present.
"""

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _make_health_fixture(tmp_path, now, espn_age_h=0.2, nflverse_age_h=100.0):
    """Create a fixture tree with separate ESPN depth and nflverse depth feeds."""
    from shared.pipeline.tests.test_capture_health import _make_fixture_tree
    _make_fixture_tree(tmp_path, now, fresh_hours=espn_age_h)

    depth_dir = tmp_path / "data" / "depth_archive" / "nfl" / "season=2026"

    # Remove the fresh nflverse file that _make_fixture_tree created
    for f in depth_dir.glob("nflverse_*.parquet"):
        f.unlink()

    # Create a STALE nflverse file instead
    nflv_ts = (now - timedelta(hours=nflverse_age_h)).strftime("%Y%m%dT%H%MZ")
    (depth_dir / f"nflverse_depth_charts_{nflv_ts}.parquet").write_bytes(b"\x00" * 10)

    # _pulls.jsonl: fresh ESPN depth + stale nflverse depth
    espn_ts = (now - timedelta(hours=espn_age_h)).strftime("%Y%m%dT%H%MZ")
    pulls_path = depth_dir / "_pulls.jsonl"
    with open(pulls_path, "w") as f:
        f.write(json.dumps({
            "utc": espn_ts, "sha256": "aaa", "status": "written",
            "feed": "espn_depth"
        }) + "\n")
        f.write(json.dumps({
            "utc": nflv_ts, "file": "depth_charts.parquet",
            "sha256": "bbb", "status": "delta",
            "feed": "nflverse_depth"
        }) + "\n")

    return pulls_path


def test_espn_depth_does_not_mask_stale_nflverse(tmp_path):
    """A fresh ESPN depth line must NOT make a stale nflverse feed read fresh."""
    from shared.pipeline.capture_health import check_feeds

    now = datetime(2026, 9, 20, 15, 0, 0, tzinfo=timezone.utc)
    _make_health_fixture(tmp_path, now, espn_age_h=0.2, nflverse_age_h=100.0)

    stale = check_feeds(data_root=tmp_path, now=now)
    assert "nflverse_inputs" in stale, (
        f"nflverse_inputs (100h old) not detected as stale — borrowed ESPN's pulse. "
        f"Stale feeds: {stale}")


def test_feed_field_filters_correctly(tmp_path):
    """Each feed in _pulls.jsonl is checked independently by its `feed` field."""
    from shared.pipeline.capture_health import _newest_pulls_age_by_feed

    now = datetime(2026, 9, 20, 15, 0, 0, tzinfo=timezone.utc)
    pulls_path = tmp_path / "_pulls.jsonl"

    espn_ts = (now - timedelta(hours=0.5)).strftime("%Y%m%dT%H%MZ")
    nflv_ts = (now - timedelta(hours=50.0)).strftime("%Y%m%dT%H%MZ")
    with open(pulls_path, "w") as f:
        f.write(json.dumps({"utc": espn_ts, "feed": "espn_depth"}) + "\n")
        f.write(json.dumps({"utc": nflv_ts, "feed": "nflverse_depth"}) + "\n")

    espn_age = _newest_pulls_age_by_feed(pulls_path, "espn_depth", now)
    nflv_age = _newest_pulls_age_by_feed(pulls_path, "nflverse_depth", now)

    assert espn_age is not None and espn_age < 1.0, f"ESPN age {espn_age} too high"
    assert nflv_age is not None and nflv_age > 40.0, f"nflverse age {nflv_age} too low"


def test_infer_feed_from_file_key(tmp_path):
    """Lines without `feed` get it inferred from the `file` key."""
    from shared.pipeline.capture_health import _newest_pulls_age_by_feed

    now = datetime(2026, 9, 20, 15, 0, 0, tzinfo=timezone.utc)
    pulls_path = tmp_path / "_pulls.jsonl"

    ts = (now - timedelta(hours=2.0)).strftime("%Y%m%dT%H%MZ")
    with open(pulls_path, "w") as f:
        # No `feed` field, but `file` = depth_charts.parquet -> nflverse_depth
        f.write(json.dumps({"utc": ts, "file": "depth_charts.parquet",
                            "sha256": "abc", "status": "delta"}) + "\n")
        # No `feed`, no `file` -> unknown, should be ignored
        f.write(json.dumps({"utc": ts, "sha256": "def",
                            "status": "written"}) + "\n")

    nflv_age = _newest_pulls_age_by_feed(pulls_path, "nflverse_depth", now)
    assert nflv_age is not None and abs(nflv_age - 2.0) < 0.1, (
        f"Expected ~2h, got {nflv_age}")

    # Lines without feed or file key should not count for any feed
    espn_age = _newest_pulls_age_by_feed(pulls_path, "espn_depth", now)
    assert espn_age is None, f"Expected None for espn_depth, got {espn_age}"
