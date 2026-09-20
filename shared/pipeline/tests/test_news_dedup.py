"""
Test: news de-dup — second pull with one changed and one new article writes
exactly those two; the index lists all.

No network.
"""
import gzip
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _make_article(aid, headline, last_modified, team_name="TestTeam", espn_id=1):
    return {
        "id": aid,
        "headline": headline,
        "published": last_modified,
        "lastModified": last_modified,
        "_team_name": team_name,
        "_espn_id": espn_id,
        "_pull_time": "2026-09-20T12:00:00+00:00",
    }


class TestNewsDedup:
    def test_second_pull_writes_only_new_and_changed(self, tmp_path, monkeypatch):
        """Second pull: 1 changed + 1 new = 2 in news; all 3 in index."""
        from shared.pipeline import pull_espn_news as mod

        monkeypatch.setattr(mod, "ROOT", tmp_path)
        out_dir = tmp_path / "data" / "news_archive" / "nfl" / "season=2026"
        out_dir.mkdir(parents=True)

        # Seed state: article 100 with original lastModified
        seen = {"100": "2026-09-20T10:00:00Z"}
        with open(out_dir / "_seen.json", "w") as f:
            json.dump(seen, f)

        # Simulate pull returning 3 articles:
        #   id=100 with CHANGED lastModified
        #   id=200 EXISTING (same lastModified as seen)
        #   id=300 NEW

        # We need to seed seen with id=200 too for it to be "existing"
        seen["200"] = "2026-09-20T09:00:00Z"
        with open(out_dir / "_seen.json", "w") as f:
            json.dump(seen, f)

        articles_in_pull = [
            _make_article(100, "Updated article", "2026-09-20T11:00:00Z"),  # changed
            _make_article(200, "Same article", "2026-09-20T09:00:00Z"),     # unchanged
            _make_article(300, "Brand new article", "2026-09-20T11:30:00Z"),  # new
        ]

        call_count = [0]
        def fake_get(url, **kwargs):
            resp = type("Resp", (), {
                "status_code": 200,
                "json": lambda self: {"articles": articles_in_pull},
            })()
            call_count[0] += 1
            return resp

        monkeypatch.setattr(mod, "requests", type("FakeRequests", (), {
            "get": staticmethod(fake_get),
            "RequestException": Exception,
        })())
        monkeypatch.setattr(mod, "time", type("FakeTime", (), {
            "sleep": staticmethod(lambda x: None),
            "time": staticmethod(lambda: 1000.0),
        })())

        team_ids = {"TestTeam": 1}
        news_path, index_path = mod.pull_news("nfl", team_ids, 2026)

        # Read the news file
        with gzip.open(news_path, "rt") as f:
            written_articles = json.load(f)

        # Should contain exactly 2: the changed (id=100) and new (id=300)
        written_ids = {a["id"] for a in written_articles}
        assert written_ids == {100, 300}, f"Expected {{100, 300}}, got {written_ids}"

        # Read the index
        with gzip.open(index_path, "rt") as f:
            index = json.load(f)

        # Index should list all 3 articles
        index_aids = {str(e["article_id"]) for e in index}
        assert index_aids == {"100", "200", "300"}, f"Expected all 3 in index, got {index_aids}"
