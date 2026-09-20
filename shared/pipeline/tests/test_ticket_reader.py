"""
Test: ticket builder reader — a directory holding one legacy .json and one
.json.gz returns the union, de-duplicated; a newest pull 30h old halts.

No network.
"""
import gzip
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _read_news_from_dir(news_dir, build_time_iso):
    """Replica of the ticket builder's news-reading logic."""
    import re

    news_articles = []
    newest_pull_utc = None
    TS_RE = re.compile(r"(\d{8}T\d{4}Z)")

    if news_dir.exists():
        for f in sorted(news_dir.iterdir()):
            if f.name.startswith("_") or f.name.startswith("index_"):
                continue
            if f.suffix == ".json":
                with open(f) as fh:
                    news_articles.extend(json.load(fh))
            elif f.name.endswith(".json.gz") and f.name.startswith("news_"):
                with gzip.open(f, "rt", encoding="utf-8") as fh:
                    news_articles.extend(json.load(fh))
            else:
                continue
            m = TS_RE.search(f.name)
            if m:
                ts = datetime.strptime(m.group(1), "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)
                if newest_pull_utc is None or ts > newest_pull_utc:
                    newest_pull_utc = ts

        # De-duplicate by article id
        seen = {}
        for a in news_articles:
            aid = str(a.get("id", ""))
            lm = a.get("lastModified", a.get("published", ""))
            prev_lm = seen.get(aid, ("", None))[0] if aid in seen else ""
            if not aid or lm >= prev_lm:
                seen[aid] = (lm, a)
        news_articles = [v[1] for v in seen.values()]

    # Freshness check
    if newest_pull_utc:
        build_dt = datetime.fromisoformat(build_time_iso.replace("Z", "+00:00"))
        if build_dt.tzinfo is None:
            build_dt = build_dt.replace(tzinfo=timezone.utc)
        pull_age_h = (build_dt - newest_pull_utc).total_seconds() / 3600
        if pull_age_h > 24:
            raise SystemExit(1)

    return news_articles, newest_pull_utc


class TestTicketReader:
    def test_union_deduplication(self, tmp_path):
        """One .json + one .json.gz -> union, de-duplicated by id."""
        news_dir = tmp_path / "news"
        news_dir.mkdir()

        # Legacy .json: articles 1, 2
        legacy = [
            {"id": 1, "headline": "A", "published": "2026-09-20T10:00:00Z",
             "lastModified": "2026-09-20T10:00:00Z"},
            {"id": 2, "headline": "B", "published": "2026-09-20T09:00:00Z",
             "lastModified": "2026-09-20T09:00:00Z"},
        ]
        with open(news_dir / "news_20260920T1000Z.json", "w") as f:
            json.dump(legacy, f)

        # New .json.gz: article 2 (updated) + article 3 (new)
        new = [
            {"id": 2, "headline": "B updated", "published": "2026-09-20T09:00:00Z",
             "lastModified": "2026-09-20T11:00:00Z"},
            {"id": 3, "headline": "C", "published": "2026-09-20T11:00:00Z",
             "lastModified": "2026-09-20T11:00:00Z"},
        ]
        with gzip.open(news_dir / "news_20260920T1100Z.json.gz", "wt") as f:
            json.dump(new, f)

        articles, _ = _read_news_from_dir(news_dir, "2026-09-20T12:00:00Z")
        ids = {a["id"] for a in articles}
        assert ids == {1, 2, 3}, f"Expected union {{1,2,3}}, got {ids}"
        # Article 2 should be the updated version
        art2 = [a for a in articles if a["id"] == 2][0]
        assert art2["headline"] == "B updated"

    def test_stale_30h_halts(self, tmp_path):
        """Newest pull 30h old -> SystemExit."""
        news_dir = tmp_path / "news"
        news_dir.mkdir()

        # File with 30h-old timestamp
        with gzip.open(news_dir / "news_20260919T0600Z.json.gz", "wt") as f:
            json.dump([{"id": 1, "headline": "X", "published": "2026-09-19T06:00:00Z",
                        "lastModified": "2026-09-19T06:00:00Z"}], f)

        with pytest.raises(SystemExit):
            _read_news_from_dir(news_dir, "2026-09-20T12:00:00Z")

    def test_fresh_does_not_halt(self, tmp_path):
        """Newest pull 2h old -> no halt."""
        news_dir = tmp_path / "news"
        news_dir.mkdir()

        with gzip.open(news_dir / "news_20260920T1000Z.json.gz", "wt") as f:
            json.dump([{"id": 1, "headline": "X", "published": "2026-09-20T10:00:00Z",
                        "lastModified": "2026-09-20T10:00:00Z"}], f)

        articles, ts = _read_news_from_dir(news_dir, "2026-09-20T12:00:00Z")
        assert len(articles) == 1
        assert ts is not None
