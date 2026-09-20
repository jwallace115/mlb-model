"""
Test: ESPN news stale fixture -> non-zero exit, NO file written.
Test: ESPN status 31-team fixture -> non-zero exit, no file written.

No network. Uses monkeypatching.
"""
import gzip
import json
import pytest
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestEspnNewsStaleHalt:
    """Newest article 100h old -> HALT (non-zero exit), no file written."""

    def test_stale_news_halts(self, tmp_path, monkeypatch):
        """100h-old newest article triggers HALT."""
        now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
        stale_time = (now - timedelta(hours=100)).strftime("%Y-%m-%dT%H:%M:%SZ")

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "articles": [
                    {"id": 1, "published": stale_time, "lastModified": stale_time,
                     "headline": "Old news"}
                ]
            }
            return resp

        monkeypatch.setattr("shared.pipeline.pull_espn_news.ROOT", tmp_path)
        monkeypatch.setattr("shared.pipeline.pull_espn_news.requests.get", fake_get)

        # Create minimal team map
        nfl_map_dir = tmp_path / "nfl" / "pipeline"
        nfl_map_dir.mkdir(parents=True)
        with open(nfl_map_dir / "espn_team_map.json", "w") as f:
            json.dump({"TestTeam": {"id": 1}}, f)

        from shared.pipeline.pull_espn_news import pull_news

        monkeypatch.setattr("shared.pipeline.pull_espn_news.datetime",
                            type("FakeDT", (), {
                                "now": staticmethod(lambda tz=None: now),
                                "fromisoformat": datetime.fromisoformat,
                                "strptime": datetime.strptime,
                            })())

        # Expect SystemExit because the freshness check fails
        with pytest.raises(SystemExit) as exc_info:
            pull_news("nfl", {"TestTeam": 1}, 2026)
        assert exc_info.value.code == 1

        # No news file written
        news_dir = tmp_path / "data" / "news_archive" / "nfl" / "season=2026"
        news_files = list(news_dir.glob("news_*.json.gz")) if news_dir.exists() else []
        assert len(news_files) == 0

    def test_fresh_news_passes(self, tmp_path, monkeypatch):
        """A fresh article (1h old) does not halt."""
        now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
        fresh_time = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "articles": [
                    {"id": 1, "published": fresh_time, "lastModified": fresh_time,
                     "headline": "Fresh news"}
                ]
            }
            return resp

        monkeypatch.setattr("shared.pipeline.pull_espn_news.ROOT", tmp_path)
        monkeypatch.setattr("shared.pipeline.pull_espn_news.requests.get", fake_get)

        from shared.pipeline.pull_espn_news import pull_news
        # Does not raise
        result = pull_news("nfl", {"TestTeam": 1}, 2026)
        assert result is not None


class TestEspnStatus31Teams:
    """31-team fixture -> HALT (non-zero exit), no file written."""

    def test_31_teams_halts(self, tmp_path, monkeypatch):
        teams_data = [{"team": {"id": i}, "injuries": []} for i in range(31)]

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"injuries": teams_data}
            return resp

        monkeypatch.setattr("shared.pipeline.pull_espn_nfl_status.ROOT", tmp_path)
        monkeypatch.setattr("shared.pipeline.pull_espn_nfl_status.requests.get", fake_get)

        from shared.pipeline.pull_espn_nfl_status import pull_injuries

        with pytest.raises(SystemExit) as exc_info:
            pull_injuries(2026)
        assert exc_info.value.code == 1

    def test_32_teams_passes(self, tmp_path, monkeypatch):
        teams_data = [{"team": {"id": i}, "injuries": []} for i in range(32)]

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"injuries": teams_data}
            return resp

        monkeypatch.setattr("shared.pipeline.pull_espn_nfl_status.ROOT", tmp_path)
        monkeypatch.setattr("shared.pipeline.pull_espn_nfl_status.requests.get", fake_get)

        from shared.pipeline.pull_espn_nfl_status import pull_injuries
        result = pull_injuries(2026)
        assert result is not None
