#!/usr/bin/env python3
"""WO11 Item 3: news must reach the selector as it was known at build time.

Fixture cut from real archive: legacy articles have `team_name` (no underscore),
new puller writes `_team_name`. The old reader filtered on `team_name`, so only
1 of 1,381 de-duped articles passed through to the selector.
"""

import json, gzip, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _make_news_fixture(tmp_path):
    """Create a fixture with legacy + new-format articles."""
    news_dir = tmp_path / "data" / "news_archive" / "ncaaf" / "season=2026"
    news_dir.mkdir(parents=True)

    # Legacy .json file: articles have `team_name` and `id` is present
    legacy = [
        {"id": "101", "team_name": "Ohio State Buckeyes",
         "headline": "Buckeyes win opener", "published": "2026-09-01T12:00:00Z",
         "lastModified": "2026-09-01T12:00:00Z"},
        {"id": "102", "team_name": "Michigan Wolverines",
         "headline": "Michigan prep begins", "published": "2026-09-02T12:00:00Z",
         "lastModified": "2026-09-02T12:00:00Z"},
    ]
    with open(news_dir / "ncaaf_news_20260902.json", "w") as f:
        json.dump(legacy, f)

    # Legacy article with EMPTY id (should be keyed by sha1)
    no_id = [
        {"id": "", "team_name": "Alabama Crimson Tide",
         "headline": "Bama rolls", "published": "2026-09-03T12:00:00Z",
         "lastModified": "2026-09-03T12:00:00Z"},
    ]
    with open(news_dir / "ncaaf_news_20260903.json", "w") as f:
        json.dump(no_id, f)

    # New-format .json.gz: articles have `_team_name` (underscore)
    new_articles = [
        {"id": 201, "_team_name": "Ohio State Buckeyes", "_espn_id": 194,
         "_pull_time": "2026-09-18T06:00:00+00:00",
         "headline": "Buckeyes prepare for WKU", "published": "2026-09-17T15:00:00Z",
         "lastModified": "2026-09-17T15:00:00Z"},
        {"id": 202, "_team_name": "Georgia Bulldogs", "_espn_id": 61,
         "_pull_time": "2026-09-18T06:00:00+00:00",
         "headline": "Georgia dominates", "published": "2026-09-17T14:00:00Z",
         "lastModified": "2026-09-17T14:00:00Z"},
        # Duplicate of 201 with later pull time (should be kept)
        {"id": 201, "_team_name": "Ohio State Buckeyes", "_espn_id": 194,
         "_pull_time": "2026-09-19T06:00:00+00:00",
         "headline": "Buckeyes prepare for WKU (updated)", "published": "2026-09-17T15:00:00Z",
         "lastModified": "2026-09-18T10:00:00Z"},
    ]
    with gzip.open(news_dir / "news_20260919T0600Z.json.gz", "wt", encoding="utf-8") as f:
        json.dump(new_articles, f)

    return news_dir


def test_load_news_accepts_both_field_names(tmp_path):
    """load_news must accept both _team_name and team_name."""
    from ncaaf.pipeline.build_ncaaf_tickets import load_news

    news_dir = _make_news_fixture(tmp_path)
    build_time = "2026-09-19T12:00:00+00:00"
    articles = load_news(news_dir, build_time)

    # Should have articles from both formats
    teams = set(a.get("_team_name", a.get("team_name")) for a in articles)
    assert "Ohio State Buckeyes" in teams
    assert "Michigan Wolverines" in teams
    assert "Georgia Bulldogs" in teams
    assert "Alabama Crimson Tide" in teams  # legacy no-id article


def test_load_news_dedup_keeps_latest_version(tmp_path):
    """De-dup keeps the latest version of an article."""
    from ncaaf.pipeline.build_ncaaf_tickets import load_news

    news_dir = _make_news_fixture(tmp_path)
    build_time = "2026-09-19T12:00:00+00:00"
    articles = load_news(news_dir, build_time)

    # Article 201 should be the updated version
    art_201 = [a for a in articles if str(a.get("id")) == "201"]
    assert len(art_201) == 1, f"Expected 1 version of article 201, got {len(art_201)}"
    assert "updated" in art_201[0]["headline"]


def test_load_news_respects_build_time(tmp_path):
    """Articles pulled AFTER build_time must not enter the build."""
    from ncaaf.pipeline.build_ncaaf_tickets import load_news

    news_dir = _make_news_fixture(tmp_path)
    # Build time BEFORE the second pull of article 201
    build_time = "2026-09-18T12:00:00+00:00"
    articles = load_news(news_dir, build_time)

    # Article 201 should be the original version (pulled at 06:00, before build_time)
    art_201 = [a for a in articles if str(a.get("id")) == "201"]
    assert len(art_201) == 1
    assert "updated" not in art_201[0]["headline"]


def test_game_news_sorted_newest_first(tmp_path):
    """Per-game news must be sorted by published descending."""
    from ncaaf.pipeline.build_ncaaf_tickets import load_news, game_news_for

    news_dir = _make_news_fixture(tmp_path)
    build_time = "2026-09-19T12:00:00+00:00"
    articles = load_news(news_dir, build_time)

    # Ohio State has 2 articles: opener (Sep 1) and WKU prep (Sep 17)
    gn = game_news_for(articles, "Ohio State Buckeyes", "WKU Hilltoppers", max_per_game=10)
    assert len(gn) >= 1
    # Newest first
    pubs = [a.get("published", "") for a in gn]
    assert pubs == sorted(pubs, reverse=True), f"Not sorted newest-first: {pubs}"
