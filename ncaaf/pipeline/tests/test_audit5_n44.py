#!/usr/bin/env python3
"""N44: the three NCAAF defects ChatGPT audit #5 found at 73bf63f, on production functions."""

import gzip
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).resolve().parent / "fixtures"
REAL_LOG = ROOT / "ncaaf" / "logs" / "ncaaf_board_tickets_2026.json"


def test_writer_appends_to_the_real_log_shape(tmp_path):
    """The committed log holds card entries (card_id, no top-level event_id). The writer keyed on
    t["event_id"] and raised KeyError — mocked builds never called it."""
    from ncaaf.pipeline import build_ncaaf_tickets as T
    log = tmp_path / "log.json"
    shutil.copy(REAL_LOG, log)
    before = json.loads(log.read_text())
    assert any("event_id" not in t for t in before), "fixture no longer has a card entry"
    new = [{"event_id": "e_new", "build_time": "2026-09-26T14:30:00Z", "legs": [], "abstain": True}]
    with patch.object(T, "TICKET_LOG", log):
        T.write_ticket_log(new)
        after = json.loads(log.read_text())
        assert len(after) == len(before) + 1 and after[:len(before)] == before
        with pytest.raises(RuntimeError, match="duplicate"):
            T.write_ticket_log(new)


def test_article_without_a_readable_pull_time_does_not_enter(tmp_path):
    from ncaaf.pipeline import build_ncaaf_tickets as T
    base = {"headline": "h", "published": "2026-09-18T12:00:00Z", "_team_name": "Georgia Bulldogs"}
    arts = [{**base, "id": "ok", "_pull_time": "2026-09-19T12:20:00Z"},
            {**base, "id": "late", "_pull_time": "2026-09-19T18:20:00Z"},
            {**base, "id": "garbled", "_pull_time": "yesterday-ish"},
            {**base, "id": "none"}]
    with gzip.open(tmp_path / "news_20260919T1220Z.json.gz", "wt") as fh:
        json.dump(arts, fh)
    got = T.load_news(tmp_path, "2026-09-19T14:35:00+00:00")
    assert [a["id"] for a in got] == ["ok"]
    assert T.LOAD_NEWS_STATS["dropped_bad_pull_time"] == 2


def test_coverage_counts_only_what_the_selector_would_be_shown():
    from ncaaf.pipeline.build_ncaaf_tickets import news_coverage
    board = pd.DataFrame({"home_team": ["Georgia Bulldogs"], "away_team": ["Arkansas Razorbacks"]})
    arts = [{"id": "fresh", "_team_name": "Georgia Bulldogs", "published": "2026-09-18T12:00:00Z"},
            {"id": "old", "_team_name": "Arkansas Razorbacks", "published": "2026-08-01T12:00:00Z"}]
    assert news_coverage(board, arts, "2026-09-19T14:35:00+00:00") == (1, 2)   # was 2 of 2


def test_unchanged_minus_110_has_negative_C(tmp_path):
    """Entry -110/-110, close -110/-110 at the same point: q unchanged, C = 1.909*0.5-1 = -4.55%."""
    eid, commence = "ev1", "2026-09-19T20:00:00Z"
    snap = (pd.Timestamp(commence) - pd.Timedelta(minutes=15)).isoformat()
    rows = [{"event_id": eid, "home_team": "Team H", "away_team": "Team A", "commence_time": commence,
             "market": "spreads", "outcome_name": n, "bookmaker": "bovada", "point": p, "price": -110,
             "snapshot_utc": snap} for n, p in (("Team H", -7.0), ("Team A", 7.0))]
    tape_dir = tmp_path / "tape" / "season=2026"
    tape_dir.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(tape_dir / "f.parquet", index=False)
    (tmp_path / "research" / "ncaaf").mkdir(parents=True)
    pd.DataFrame([{"homeTeam": "Team H", "awayTeam": "Team A", "homePoints": 35.0, "awayPoints": 10.0,
                   "completed": True, "startDate": commence}]).to_parquet(
        tmp_path / "research" / "ncaaf" / "cfbd_games_2026.parquet", index=False)
    log = tmp_path / "log.json"
    log.write_text(json.dumps([{"event_id": eid, "home_team": "Team H", "away_team": "Team A",
                                "commence_time": commence, "build_time": "2026-09-19T10:00:00Z",
                                "graded": False,
                                "legs": [{"market": "spreads", "side": "Team H", "point": -7.0, "price": -110,
                                          "book": "bovada", "complement_side": "Team A",
                                          "complement_point": 7.0, "complement_price": -110}]}]))
    from ncaaf.pipeline import grade_ncaaf_tickets as G
    with patch.object(G, "TICKET_LOG", log), patch.object(G, "TAPE_DIR", tmp_path / "tape"), \
         patch.object(G, "ROOT", tmp_path):
        G.grade_tickets(2026)
    leg = json.loads(log.read_text())[0]["legs"][0]
    assert leg["prob_clv"] == 0.0
    assert abs(leg["prob_clv_C"] - (210 / 110 * 0.5 - 1)) < 1e-6 and leg["prob_clv_C"] < -0.045
