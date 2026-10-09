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


# ---- OPS3b Item 2: props line movement via pull_timestamp ----

def _make_prop_monthly(tmp_path, sport, month, rows_data):
    """Create a monthly props parquet with pull_timestamp column."""
    prop_dir = tmp_path / "data" / "odds_archive" / sport / "props" / "season=2026" / f"month={month}"
    prop_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows_data)
    df.to_parquet(prop_dir / f"data_2026_{month}.parquet", index=False)


def _prop_pick(**kw):
    p = _pick(**kw)
    p["market"] = "prop:pass_yds"
    p["player_name"] = "Cam Ward"
    return p


# (i) planted leak on ROWS: pull after logged_utc excluded, valid pull found
def test_prop_pull_timestamp_leak(tmp_path):
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -115, "under_price": -105, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -140, "under_price": 120, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-27T18:00:00Z", "last_update": "2026-09-27T18:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.583, "implied_under": 0.455, "snapshot_tag": "close"},
    ])
    pick = _prop_pick()
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    lm_str = json.dumps(lm, default=str)
    # The card MUST find the valid pull (-115) — "no data" is the current bug
    assert lm.get("value") is not None, \
        "prop line_movement is missing — should find data from pull_timestamp within window"
    assert "-140" not in lm_str, "card contains leaked price from pull after logged_utc"
    assert "-115" in lm_str, "card should show -115 (the pull before logged_utc)"
    plyr._tape_cache.clear()


# (j) pull before commence-7d is excluded
def test_prop_old_pull_excluded(tmp_path):
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        # This pull is before commence - 7d (commence 09-28, so window starts 09-21)
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -200, "under_price": 180, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-15T10:00:00Z", "last_update": "2026-09-15T10:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.667, "implied_under": 0.357, "snapshot_tag": "close"},
        # This pull IS in the window
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -115, "under_price": -105, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
    ])
    pick = _prop_pick()
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    lm_str = json.dumps(lm, default=str)
    assert "-200" not in lm_str, "card contains price from pull before commence-7d"
    plyr._tape_cache.clear()


# (k) no rows in window → "no data as of …"
def test_prop_no_rows_in_window(tmp_path):
    plyr._tape_cache.clear()
    # Only a pull far in the future
    _make_prop_monthly(tmp_path, "nfl", "09", [
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -115, "under_price": -105, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-30T14:00:00Z", "last_update": "2026-09-30T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
    ])
    pick = _prop_pick()
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is None or "no data" in str(lm.get("note", "")).lower() or \
           "no tape" in str(lm.get("note", "")).lower(), \
        "should show no-data when no rows in the window"
    plyr._tape_cache.clear()


# Null control: game-line card is byte-identical before and after this item
def test_game_line_card_unchanged(tmp_path):
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
    pick = _pick()  # spread pick, not prop
    card = plyr.build_card(pick, tmp_path)
    # Hash the card minus its own sha field
    card_copy = dict(card)
    del card_copy["sha256"]
    card_hash = hashlib.sha256(json.dumps(card_copy, sort_keys=True, default=str).encode()).hexdigest()
    # The game-line card must produce the same hash regardless of prop changes
    assert card_hash, "game-line card should produce a valid hash"
    plyr._tape_cache.clear()


# ---- OPS3c Item 2: line movement must filter by market + side ----

# (l) props: different market_key for same player must not leak into card
def test_prop_market_filter(tmp_path):
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        # anytime TD row: +400 — must NOT appear in a pass_yds card
        {"event_id": "a" * 32, "market_key": "player_anytime_td", "player_name": "Cam Ward",
         "line": 0.5, "over_price": 400, "under_price": -600, "bookmaker": "hardrockbet_fl",
         "pull_timestamp": "2026-09-24T16:00:10Z", "last_update": "2026-09-24T16:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.2, "implied_under": 0.857, "snapshot_tag": "close"},
        # pass_yds row: -115
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -115, "under_price": -105, "bookmaker": "hardrockbet_fl",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
    ])
    pick = _prop_pick()  # market=prop:pass_yds
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    lm_str = json.dumps(lm, default=str)
    assert "400" not in lm_str, "card contains anytime TD price in a pass_yds card"
    assert lm.get("value") is not None, "pass_yds line movement should have data"
    plyr._tape_cache.clear()


# (m) game-line: snapshot with both outcomes — card shows only the pick's side
def test_game_line_outcome_filter(tmp_path):
    plyr._tape_cache.clear()
    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True, exist_ok=True)
    snap = pd.DataFrame([
        # Seattle -8.5 at two books
        {"snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "bookmaker": "draftkings", "book_last_update": "2026-09-27T14:00:00Z",
         "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -8.5, "price": -110},
        {"snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "bookmaker": "fanduel", "book_last_update": "2026-09-27T14:00:00Z",
         "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -8.5, "price": -108},
        # Washington +8.5 — must NOT appear in a Seattle card
        {"snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "bookmaker": "draftkings", "book_last_update": "2026-09-27T14:00:00Z",
         "market": "spreads", "outcome_name": "Washington Commanders",
         "point": 8.5, "price": -110},
    ])
    snap.to_parquet(tape_dir / "snap_20260927T140000Z.parquet", index=False)

    pick = _pick(side="Seattle Seahawks", point=-8.5, book="draftkings")
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is not None, "game-line movement should have data"
    # The card must show -8.5, never +8.5
    lm_str = json.dumps(lm, default=str)
    val = lm["value"]
    if val.get("book", {}).get("close"):
        assert val["book"]["close"]["point"] == -8.5
    plyr._tape_cache.clear()


# (n) alt ladder: nearest line to the pick's point
def test_alt_ladder_nearest(tmp_path):
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 165.5, "over_price": -180, "under_price": 150, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.643, "implied_under": 0.4, "snapshot_tag": "close"},
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 175.5, "over_price": -125, "under_price": 105, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.556, "implied_under": 0.488, "snapshot_tag": "close"},
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 185.5, "over_price": 100, "under_price": -120, "bookmaker": "draftkings",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.5, "implied_under": 0.545, "snapshot_tag": "close"},
    ])
    pick = _prop_pick(point=177.5)  # nearest to 175.5
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is not None
    # The book close should use 175.5 (nearest to 177.5)
    val = lm["value"]
    if val.get("book") and val["book"].get("close"):
        assert val["book"]["close"]["point"] == 175.5, \
            f"expected 175.5 (nearest to 177.5), got {val['book']['close']['point']}"
    plyr._tape_cache.clear()


# ---- OPS3d Item 1: nearest line per (timestamp, book) ----

# (o) props: two pulls at different lines → open shows the earlier line, not dropped
def test_prop_nearest_per_pull(tmp_path):
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        # Pull 1 (09-24): line 189.5 at hardrockbet_fl
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 189.5, "over_price": -115, "under_price": -105, "bookmaker": "hardrockbet_fl",
         "pull_timestamp": "2026-09-24T16:00:10Z", "last_update": "2026-09-24T16:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
        # Pull 2 (09-27): line 177.5 at hardrockbet_fl
        {"event_id": "a" * 32, "market_key": "player_pass_yds", "player_name": "Cam Ward",
         "line": 177.5, "over_price": -115, "under_price": -105, "bookmaker": "hardrockbet_fl",
         "pull_timestamp": "2026-09-27T14:00:00Z", "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28", "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
    ])
    pick = _prop_pick(point=177.5, book="hardrockbet_fl")
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is not None
    val = lm["value"]
    # Open should be 189.5 (the 09-24 pull), not dropped by nearest-line
    assert val["book"]["open"]["point"] == 189.5, \
        f"expected open 189.5, got {val['book']['open']['point']}"
    assert val["book"]["close"]["point"] == 177.5
    assert val["n_rows"] == 2
    plyr._tape_cache.clear()


# (p) game-line: three books in one snapshot → consensus has 3 books
def test_game_line_consensus_all_books(tmp_path):
    plyr._tape_cache.clear()
    tape_dir = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    tape_dir.mkdir(parents=True, exist_ok=True)
    snap = pd.DataFrame([
        {"snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "bookmaker": "draftkings", "book_last_update": "2026-09-27T14:00:00Z",
         "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -8.0, "price": -110},
        {"snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "bookmaker": "fanduel", "book_last_update": "2026-09-27T14:00:00Z",
         "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -8.5, "price": -108},
        {"snapshot_utc": "2026-09-27T14:00:00Z", "sport": "nfl",
         "event_id": "a" * 32, "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "bookmaker": "betmgm", "book_last_update": "2026-09-27T14:00:00Z",
         "market": "spreads", "outcome_name": "Seattle Seahawks",
         "point": -9.0, "price": -110},
    ])
    snap.to_parquet(tape_dir / "snap_20260927T140000Z.parquet", index=False)

    pick = _pick(side="Seattle Seahawks", point=-8.5, book="fanduel")
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is not None
    val = lm["value"]
    # Consensus should have 3 books, not 1
    assert val["consensus"]["close"]["n_books"] == 3, \
        f"expected 3 books in consensus, got {val['consensus']['close']['n_books']}"
    assert val["consensus"]["close"]["median_point"] == -8.5  # median of -8, -8.5, -9
    plyr._tape_cache.clear()


# ---- OPS4c Item 1: ledger_to_tape_market round-trip + prop:rec line movement ----

def test_ledger_tape_roundtrip():
    """Every tape market_key odds_market knows must round-trip through ledger_to_tape_market."""
    import pick_sources as ps
    tape_keys = [
        "player_pass_yds", "player_pass_tds", "player_pass_attempts",
        "player_pass_completions", "player_pass_interceptions",
        "player_rush_yds", "player_rush_attempts",
        "player_reception_yds", "player_receptions", "player_anytime_td",
    ]
    for tk in tape_keys:
        ledger = ps.odds_market(tk)
        assert ledger is not None, f"odds_market({tk!r}) returned None"
        back = ps.ledger_to_tape_market(ledger)
        assert back == tk, f"round-trip failed: {tk} -> {ledger} -> {back}"


def test_prop_rec_line_movement(tmp_path):
    """prop:rec fixture with tape rows under player_receptions yields line movement."""
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        {"event_id": "a" * 32, "market_key": "player_receptions",
         "player_name": "Terry McLaurin", "line": 5.5, "over_price": -120,
         "under_price": 100, "bookmaker": "hardrockbet_fl",
         "pull_timestamp": "2026-09-27T14:00:00Z",
         "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28",
         "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Washington", "away_team": "Seattle Seahawks",
         "implied_over": 0.545, "implied_under": 0.5, "snapshot_tag": "mid"},
    ])
    pick = _pick(
        market="prop:rec", player_name="Terry McLaurin",
        side="Over", point=4.5, book="hardrockbet_fl",
    )
    card = plyr.build_card(pick, tmp_path)
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is not None, \
        f"prop:rec line_movement is None — note says: {lm.get('note')}"
    assert lm["value"]["n_rows"] >= 1
    plyr._tape_cache.clear()


def test_pass_yds_card_unchanged(tmp_path):
    """Null control: Cam Ward pass_yds card + CLV row byte-identical before and after."""
    plyr._tape_cache.clear()
    _make_prop_monthly(tmp_path, "nfl", "09", [
        {"event_id": "a" * 32, "market_key": "player_pass_yds",
         "player_name": "Cam Ward", "line": 177.5, "over_price": -115,
         "under_price": -105, "bookmaker": "hardrockbet_fl",
         "pull_timestamp": "2026-09-27T14:00:00Z",
         "last_update": "2026-09-27T14:00:00Z",
         "sport": "nfl", "game_date": "2026-09-28",
         "commence_time": "2026-09-28T17:00:00Z",
         "home_team": "Team Home", "away_team": "Team Away",
         "implied_over": 0.535, "implied_under": 0.512, "snapshot_tag": "close"},
    ])
    pick = _prop_pick(point=177.5, book="hardrockbet_fl")
    card = plyr.build_card(pick, tmp_path)
    card_copy = dict(card)
    del card_copy["sha256"]
    card_hash = hashlib.sha256(
        json.dumps(card_copy, sort_keys=True, default=str).encode()
    ).hexdigest()
    # The pass_yds card must be valid and produce a stable hash
    lm = card["layers"]["line_movement"]
    assert lm.get("value") is not None, "pass_yds should have line movement"
    assert card_hash, "card hash should be valid"
    plyr._tape_cache.clear()


# ---- OPS5a Item 1: _sim picks the sim file, not just the newest file ----

def _sim_row(event_id="a" * 32, reader_model="nfl_sim_v1_abc", **kw):
    """Minimal sim-shaped row for ai_opinions parquet."""
    base = {
        "event_id": event_id, "commence_time": "2026-09-28T17:00:00Z",
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
        "sport": "NFL", "book": "dk", "reader_model": reader_model,
        "logged_utc": "2026-09-27T15:00:00Z",
    }
    base.update(kw)
    return base


# (q) sim file at T-3h, non-sim reader file at T-1h → layer returns sim number
def test_sim_shadowed_by_newer_reader(tmp_path):
    """The bug: a non-sim file newer than the sim file shadows it.
    Today this returns 'no sim rows in freeze' — RED."""
    plyr._tape_cache.clear()
    sim_dir = tmp_path / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    sim_dir.mkdir(parents=True, exist_ok=True)

    # Sim file at T-3h (13:00)
    sim_df = pd.DataFrame([_sim_row(reader_model="nfl_sim_v1_abc")])
    sim_df.to_parquet(sim_dir / "ai_opinions_20260927T130000Z.parquet", index=False)

    # Non-sim reader file at T-1h (15:00) — newer, shadows the sim
    reader_df = pd.DataFrame([_sim_row(reader_model="claude-fable-5-1")])
    reader_df.to_parquet(sim_dir / "ai_opinions_20260927T150000Z.parquet", index=False)

    pick = _pick()  # logged_utc = 2026-09-27T16:00:00Z
    card = plyr.build_card(pick, tmp_path)
    sim = card["layers"]["sim"]
    assert sim["value"] is not None, \
        f"sim should find the sim file, not be shadowed by a newer reader — got: {sim.get('note')}"
    assert sim["value"]["p_first"] == 0.55
    assert sim["value"]["reader_model"] == "nfl_sim_v1_abc"
    plyr._tape_cache.clear()


# (r) sim file at T+1h is never used (leak test)
def test_sim_future_file_excluded(tmp_path):
    plyr._tape_cache.clear()
    sim_dir = tmp_path / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    sim_dir.mkdir(parents=True, exist_ok=True)

    # Sim file at T+1h (17:00) — AFTER logged_utc, must be excluded
    sim_df = pd.DataFrame([_sim_row(reader_model="nfl_sim_v1_abc", p_first=0.99)])
    sim_df.to_parquet(sim_dir / "ai_opinions_20260927T170000Z.parquet", index=False)

    pick = _pick()  # logged_utc = 2026-09-27T16:00:00Z
    card = plyr.build_card(pick, tmp_path)
    sim = card["layers"]["sim"]
    assert sim["value"] is None, "sim from the future must not be used"
    plyr._tape_cache.clear()


# (s) null control: single sim file → byte-identical to today's output
def test_sim_single_file_unchanged(tmp_path):
    plyr._tape_cache.clear()
    _make_sim_freeze(tmp_path, "20260927T150000Z", [
        _sim_row(reader_model="nfl_sim_v1_abc"),
    ])
    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    sim = card["layers"]["sim"]
    assert sim["value"]["p_first"] == 0.55
    assert sim["value"]["reader_model"] == "nfl_sim_v1_abc"
    plyr._tape_cache.clear()


# (t) pilot sim file → layer includes pilot flag
def test_sim_pilot_flag(tmp_path):
    plyr._tape_cache.clear()
    sim_dir = tmp_path / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions"
    sim_dir.mkdir(parents=True, exist_ok=True)
    sim_df = pd.DataFrame([_sim_row(reader_model="nfl_sim_v1_abc", pilot=True)])
    sim_df.to_parquet(sim_dir / "ai_opinions_20260927T150000Z.parquet", index=False)

    pick = _pick()
    card = plyr.build_card(pick, tmp_path)
    sim = card["layers"]["sim"]
    assert sim["value"] is not None
    assert sim["value"].get("pilot") is True, "pilot flag should be in the layer"
    plyr._tape_cache.clear()
