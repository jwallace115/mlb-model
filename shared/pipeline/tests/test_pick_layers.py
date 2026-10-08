"""Gate tests for pick_layers.py — RED first, then GREEN.

OPS3 Item 2.
"""
import gzip
import hashlib
import json
import os
import sys
import pytest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pick_layers as plyr
import picks_ledger as pl


def _pick(**kw):
    r = dict(
        pick_id="test_pid_001",
        owner="ai_nfl",
        source="ai_opinion",
        logged_utc="2026-09-27T16:00:00Z",
        sport="NFL",
        event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z",
        home="Kansas City Chiefs",
        away="Buffalo Bills",
        market="spread",
        player_id=None,
        player_name=None,
        side="Kansas City Chiefs",
        point=-3.5,
        price_american=-110,
        book="draftkings",
        reason="test reason",
        tag="game_script",
        conf=65,
    )
    r.update(kw)
    return r


def _make_tape(tmp_path, sport, snapshots, is_prop=False):
    """Create tape files. snapshots = [(timestamp_str, rows_df)]"""
    if is_prop:
        tape_dir = tmp_path / "data" / "odds_archive" / sport / "props" / "season=2026" / "month=09"
    else:
        tape_dir = tmp_path / "data" / "odds_archive" / sport / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True, exist_ok=True)
    for ts_str, df in snapshots:
        if is_prop:
            fname = f"data_2026_09.parquet"
        else:
            fname = f"snap_{ts_str}.parquet"
        df.to_parquet(tape_dir / fname, index=False)


def _make_weather(tmp_path, ts_str, rows):
    wx_dir = tmp_path / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026"
    wx_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(wx_dir / f"snap_{ts_str}.parquet", index=False)


def _make_sim_freeze(tmp_path, ts_str, rows):
    sim_dir = tmp_path / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    sim_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(sim_dir / f"ai_opinions_{ts_str}.parquet", index=False)


def _make_injuries(tmp_path, ts_str, data):
    inj_dir = tmp_path / "data" / "injury_archive" / "nfl" / "season=2026"
    inj_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(inj_dir / f"injuries_{ts_str}.json.gz", "wt") as f:
        json.dump(data, f)


def _make_news(tmp_path, ts_str, articles):
    news_dir = tmp_path / "data" / "news_archive" / "nfl" / "season=2026"
    news_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(news_dir / f"news_{ts_str}.json.gz", "wt") as f:
        json.dump(articles, f)


# ---- (a) planted leak: tape file AFTER logged_utc excluded ----
def test_tape_leak_excluded(tmp_path):
    plyr._tape_cache.clear()
    # Before logged_utc: price -110
    before_df = pd.DataFrame([{
        "snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
        "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Kansas City Chiefs", "away_team": "Buffalo Bills",
        "bookmaker": "draftkings", "book_last_update": "2026-09-27T14:00:00Z",
        "market": "spreads", "outcome_name": "Kansas City Chiefs",
        "point": -3.5, "price": -110,
    }])
    # AFTER logged_utc: price -150 (this must NOT appear)
    after_df = pd.DataFrame([{
        "snapshot_utc": "2026-09-27T18:00:00Z", "sport": "nfl",
        "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Kansas City Chiefs", "away_team": "Buffalo Bills",
        "bookmaker": "draftkings", "book_last_update": "2026-09-27T18:00:00Z",
        "market": "spreads", "outcome_name": "Kansas City Chiefs",
        "point": -3.5, "price": -150,
    }])
    _make_tape(tmp_path, "nfl", [
        ("20260927T140000Z", before_df),
    ])
    # Make the after file separately
    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    after_df.to_parquet(tape_dir / "snap_20260927T180000Z.parquet", index=False)

    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    # The card must NOT contain -150
    assert "-150" not in json.dumps(lm), "card contains leaked price from after logged_utc"
    # The source must only reference the before file
    assert "20260927T180000Z" not in str(lm.get("source", "")), "card references file after logged_utc"
    plyr._tape_cache.clear()


# ---- (b) dome stadium → "indoor" and no wind ----
def test_dome_indoor(tmp_path):
    plyr._tape_cache.clear()
    _make_weather(tmp_path, "20260927T150000Z", [{
        "fetched_at_utc": "2026-09-27T15:00:00Z", "generated_at": "2026-09-27T15:00:00Z",
        "update_time": "2026-09-27T15:00:00Z",
        "stadium_key": "IND", "team": "Indianapolis Colts", "stadium": "Lucas Oil Stadium",
        "roof": "retractable", "lat": 39.76, "lon": -86.16, "grid_id": "", "grid_x": 0, "grid_y": 0,
        "valid_start": "2026-09-28T16:00:00Z", "valid_end": "2026-09-28T17:00:00Z",
        "is_daytime": True, "temp_f": 72, "wind_mph_low": 0, "wind_mph_high": 0,
        "wind_mph_mean": 0, "wind_text": "", "wind_dir": None,
        "precip_prob_pct": 0, "short_forecast": "Clear",
    }])
    pick = _pick(home="Indianapolis Colts")
    card = plyr.build_card(pick, tmp_path)
    wx = card["layers"]["weather"]
    assert wx["value"]["indoor"] is True
    assert "wind" not in str(wx["value"]).lower() or wx["value"].get("wind_mph") is None
    plyr._tape_cache.clear()


# ---- (c) no NWS file ≤ logged_utc → "no data as of …" ----
def test_no_weather(tmp_path):
    plyr._tape_cache.clear()
    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    wx = card["layers"]["weather"]
    assert wx["value"] is None
    assert "no data" in (wx.get("note") or "").lower() or "no NWS" in (wx.get("note") or "")
    plyr._tape_cache.clear()


# ---- (d) sim row present → numbers shown; absent → "no number" ----
def test_sim_present(tmp_path):
    plyr._tape_cache.clear()
    _make_sim_freeze(tmp_path, "20260927T150000Z", [{
        "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Kansas City Chiefs", "away_team": "Buffalo Bills",
        "market_key": "spreads", "player_name": None, "line": -3.5,
        "first_side": "KC", "second_side": "BUF",
        "price_first": -110, "price_second": -110,
        "source_utc": "2026-09-27T15:00:00Z", "imp_first": 0.5, "imp_second": 0.5,
        "two_way": True, "q_first": 0.5, "source_age_min": 10,
        "p_first": 0.55, "book_p_first": 0.52, "edge": 0.03,
        "tag": "sim_v1", "reason": "sim", "conf": 60, "conf_rank": 5,
        "gap": 0.03, "side": "first", "side_name": "KC", "side_price": -110,
        "revision": 1, "season": 2026, "week": 3, "pilot": False,
        "sport": "NFL", "book": "dk", "reader_model": "nfl_sim_v1_abc",
        "logged_utc": "2026-09-27T15:00:00Z",
    }])
    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    sim = card["layers"]["sim"]
    assert sim["value"]["p_first"] == 0.55
    assert sim["value"]["book_p_first"] == 0.52
    assert sim["value"]["edge"] == 0.03
    plyr._tape_cache.clear()


def test_sim_absent(tmp_path):
    plyr._tape_cache.clear()
    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    sim = card["layers"]["sim"]
    assert "no number" in (sim.get("note") or "") or sim["value"] is None
    plyr._tape_cache.clear()


# ---- (e) write-once: second call returns "exists", sha unchanged ----
def test_write_once(tmp_path):
    plyr._tape_cache.clear()
    pick = _pick()
    layers_dir = tmp_path / "layers"
    status1, path1 = plyr.write_card(pick, tmp_path, layers_dir)
    assert status1 == "built"
    sha1 = hashlib.sha256(path1.read_bytes()).hexdigest()

    status2, path2 = plyr.write_card(pick, tmp_path, layers_dir)
    assert status2 == "exists"
    sha2 = hashlib.sha256(path2.read_bytes()).hexdigest()
    assert sha1 == sha2
    plyr._tape_cache.clear()


# ---- (f) news item after logged_utc excluded ----
def test_news_after_excluded(tmp_path):
    plyr._tape_cache.clear()
    # News BEFORE logged_utc
    _make_news(tmp_path, "20260927T140000Z", [
        {"headline": "Chiefs injury update", "description": "Player X is questionable",
         "published": "2026-09-27T14:00:00Z"},
    ])
    # News AFTER logged_utc — must be excluded
    _make_news(tmp_path, "20260927T180000Z", [
        {"headline": "LEAKED: Chiefs secret play", "description": "This is from the future",
         "published": "2026-09-27T18:00:00Z"},
    ])
    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    news = card["layers"]["news"]
    news_str = json.dumps(news)
    assert "LEAKED" not in news_str, "card contains news from after logged_utc"
    plyr._tape_cache.clear()


# ---- Null control: source set matches planted files ----
def test_source_set(tmp_path):
    plyr._tape_cache.clear()
    before_df = pd.DataFrame([{
        "snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
        "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
        "home_team": "Kansas City Chiefs", "away_team": "Buffalo Bills",
        "bookmaker": "draftkings", "book_last_update": "2026-09-27T14:00:00Z",
        "market": "spreads", "outcome_name": "Kansas City Chiefs",
        "point": -3.5, "price": -110,
    }])
    _make_tape(tmp_path, "nfl", [("20260927T140000Z", before_df)])
    _make_weather(tmp_path, "20260927T150000Z", [{
        "fetched_at_utc": "2026-09-27T15:00:00Z", "generated_at": "2026-09-27T15:00:00Z",
        "update_time": "2026-09-27T15:00:00Z",
        "stadium_key": "KC", "team": "Kansas City Chiefs", "stadium": "Arrowhead",
        "roof": "outdoors", "lat": 39.0, "lon": -94.0, "grid_id": "", "grid_x": 0, "grid_y": 0,
        "valid_start": "2026-09-28T16:00:00Z", "valid_end": "2026-09-28T18:00:00Z",
        "is_daytime": True, "temp_f": 75, "wind_mph_low": 5, "wind_mph_high": 10,
        "wind_mph_mean": 7, "wind_text": "S 7 mph", "wind_dir": "S",
        "precip_prob_pct": 10, "short_forecast": "Partly Cloudy",
    }])
    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    # Check that sources reference only the planted files
    all_sources = json.dumps(card["layers"])
    assert "20260927T140000Z" in all_sources  # tape
    assert "20260927T150000Z" in all_sources  # weather
    plyr._tape_cache.clear()
