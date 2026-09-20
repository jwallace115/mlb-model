"""
Tests for capture_health.py:
  (i)   One stale feed in fixture -> non-zero exit naming it
  (ii)  REGRESSION C(1): tz-naive older partition + tz-aware newer -> reports newer
  (iii) REGRESSION C(2): set fixture mtime to now -> ages unchanged

No network.
"""
import gzip
import json
import os
import time
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _make_fixture_tree(tmp_path, now, fresh_hours=1.0, stale_feed=None, stale_hours=100.0):
    """Build a fixture data tree. All feeds are fresh unless stale_feed is named."""
    ts_fresh = (now - timedelta(hours=fresh_hours)).strftime("%Y%m%dT%H%MZ")
    ts_stale = (now - timedelta(hours=stale_hours)).strftime("%Y%m%dT%H%MZ")

    feeds = {
        "nfl_lines": ("data/odds_archive/nfl/line_history/season=2026", f"snap_{ts_fresh}.parquet"),
        "ncaaf_lines": ("data/odds_archive/ncaaf/line_history/season=2026", f"snap_{ts_fresh}.parquet"),
        "kalshi_nfl": ("data/odds_archive/kalshi/nfl/season=2026", f"snap_{ts_fresh}.parquet"),
        "kalshi_ncaaf": ("data/odds_archive/kalshi/ncaaf/season=2026", f"snap_{ts_fresh}.parquet"),
        "nfl_news": ("data/news_archive/nfl/season=2026", f"news_{ts_fresh}.json.gz"),
        "ncaaf_news": ("data/news_archive/ncaaf/season=2026", f"news_{ts_fresh}.json.gz"),
        "nfl_injuries": ("data/injury_archive/nfl/season=2026", f"injuries_{ts_fresh}.json.gz"),
        "nfl_depth": ("data/depth_archive/nfl/season=2026", f"depth_{ts_fresh}.json.gz"),
        "nflverse_inputs": ("data/depth_archive/nfl/season=2026", f"nflverse_depth_charts_{ts_fresh}.parquet"),
    }

    for name, (dirpath, filename) in feeds.items():
        ts = ts_stale if name == stale_feed else ts_fresh
        if name == stale_feed:
            filename = filename.replace(ts_fresh, ts_stale)
        d = tmp_path / dirpath
        d.mkdir(parents=True, exist_ok=True)
        (d / filename).write_bytes(b"\x00" * 10)

    # Props: create a parquet with pull_timestamp
    import pandas as pd
    props_dir = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=09"
    props_dir.mkdir(parents=True, exist_ok=True)
    ts_val = (now - timedelta(hours=fresh_hours)).isoformat()
    df = pd.DataFrame({"pull_timestamp": [ts_val]})
    df.to_parquet(props_dir / "data_2026_09.parquet", index=False)


class TestHealthCheckStaleFeed:
    """(i) One stale feed in a fixture tree -> non-zero exit naming it."""

    def test_stale_nfl_news_detected(self, tmp_path):
        now = datetime(2026, 9, 20, 15, 0, 0, tzinfo=timezone.utc)  # in capture window
        _make_fixture_tree(tmp_path, now, fresh_hours=0.5, stale_feed="nfl_news", stale_hours=100)

        from shared.pipeline.capture_health import check_feeds
        stale = check_feeds(data_root=tmp_path, now=now)
        assert "nfl_news" in stale
        assert len(stale) == 1  # only the stale one

    def test_all_fresh_returns_empty(self, tmp_path):
        now = datetime(2026, 9, 20, 15, 0, 0, tzinfo=timezone.utc)
        _make_fixture_tree(tmp_path, now, fresh_hours=0.25)

        from shared.pipeline.capture_health import check_feeds
        stale = check_feeds(data_root=tmp_path, now=now)
        assert len(stale) == 0


class TestHealthCheckTzRegression:
    """(ii) REGRESSION C(1): tz-naive older + tz-aware newer -> reports the newer."""

    def test_mixed_tz_props(self, tmp_path):
        """Month=02 has tz-naive, month=09 has tz-aware. Must report month=09 age."""
        import pandas as pd

        now = datetime(2026, 9, 20, 15, 0, 0, tzinfo=timezone.utc)

        # Make the fixture tree first (creates a fresh props)
        _make_fixture_tree(tmp_path, now, fresh_hours=0.5)

        # Overwrite props with two partitions:
        # Month=02: tz-naive (old)
        props_02 = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2025" / "month=02"
        props_02.mkdir(parents=True, exist_ok=True)
        df_old = pd.DataFrame({"pull_timestamp": ["2026-03-28T12:00:00"]})  # tz-naive
        df_old.to_parquet(props_02 / "data_2025_02.parquet", index=False)

        # Month=09: tz-aware (recent)
        props_09 = tmp_path / "data" / "odds_archive" / "nfl" / "props" / "season=2026" / "month=09"
        props_09.mkdir(parents=True, exist_ok=True)
        recent_ts = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        df_new = pd.DataFrame({"pull_timestamp": [recent_ts]})
        df_new.to_parquet(props_09 / "data_2026_09.parquet", index=False)

        from shared.pipeline.capture_health import _newest_props_age
        age, path = _newest_props_age(
            tmp_path / "data" / "odds_archive" / "nfl" / "props", now)

        # Must report ~2h, not ~4226h
        assert age is not None
        assert age < 5, f"Expected ~2h, got {age:.1f}h — tz bug not fixed"


class TestHealthCheckMtimeRegression:
    """(iii) REGRESSION C(2): set mtime to now -> ages unchanged."""

    def test_mtime_does_not_affect_age(self, tmp_path):
        """Touch all fixture files to now. Ages must come from filenames, not mtime."""
        # Use a time OUTSIDE capture window (08:00 UTC) so line/Kalshi max=9h
        now = datetime(2026, 9, 20, 8, 0, 0, tzinfo=timezone.utc)
        _make_fixture_tree(tmp_path, now, fresh_hours=6.0)  # 6h old by filename

        # Touch all files to "now" (mtime = current wall clock)
        for f in tmp_path.rglob("*"):
            if f.is_file():
                f.touch()

        from shared.pipeline.capture_health import check_feeds
        stale = check_feeds(data_root=tmp_path, now=now)

        # With filename-based ages, the feeds are 6h old (within 7h news threshold
        # and 9h line threshold since we're in capture window).
        # If the check used mtime, they'd be 0h old.
        # The test passes if the ages are reported correctly from filenames.
        # All feeds should be OK at 6h (news max=7h, status max=7h, nflverse max=26h).
        assert len(stale) == 0

        # Now verify that the ages are NOT near zero (which would indicate mtime)
        from shared.pipeline.capture_health import _newest_file_age
        nfl_news_dir = tmp_path / "data" / "news_archive" / "nfl"
        age, _ = _newest_file_age(nfl_news_dir, "**/*.json*", now)
        assert age is not None
        assert age > 5.0, f"Age {age:.1f}h is too low — likely using mtime instead of filename"
