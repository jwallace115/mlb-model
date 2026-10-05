"""H5 tests: packet core (shared/layers/packet.py) and NHL packet builder integration."""
import json
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.layers.packet import (
    to_canonical_json, packet_sha256, build_header, build_packet,
    validate_packet_for_freeze, validate_drivers_vs_packet, builder_sha256
)


# ── Canonical JSON determinism ──

def test_canonical_json_deterministic():
    """Same inputs in different order -> same JSON and same hash."""
    p1 = {"header": {"sport": "nhl", "b": 1.0, "a": 2}, "games": [{"x": 3.14159265}]}
    p2 = {"games": [{"x": 3.14159265}], "header": {"a": 2, "sport": "nhl", "b": 1.0}}
    assert to_canonical_json(p1) == to_canonical_json(p2)
    assert packet_sha256(p1) == packet_sha256(p2)


def test_canonical_json_float_precision():
    """Floats are rounded to 6 decimal places."""
    p = {"v": 3.14159265358979}
    j = to_canonical_json(p)
    assert '"v":3.141593' in j


# ── Header validation ──

def test_source_utc_after_built_utc_halts():
    """HALT if any source's source_utc >= built_utc."""
    with pytest.raises(SystemExit, match="source_utc.*>=.*built_utc"):
        build_header("nhl", "2026-09-29", "2026-09-29T20:00:00+00:00", [],
                     [{"path": "x", "sha256": "abc", "source_utc": "2026-09-29T21:00:00+00:00"}])


def test_built_utc_after_first_puck_halts():
    """HALT if built_utc >= first commence_time."""
    header = {"sport": "nhl", "slate_date": "2026-09-29",
              "built_utc": "2026-09-29T22:00:00+00:00", "builder_sha256": "x", "sources": []}
    games = [{"event_id": "e1", "home": "A", "away": "B",
              "commence_time": "2026-09-29T21:00:00+00:00", "layers": {}}]
    with pytest.raises(SystemExit, match="built_utc.*>=.*commence"):
        build_packet(header, games, "2026-09-29T21:00:00+00:00")


# ── Packet validation for freeze ──

def test_packet_sport_mismatch_halts():
    packet = {"header": {"sport": "nfl", "slate_date": "2026-09-29",
                         "built_utc": "2026-09-29T20:00:00+00:00"},
              "games": []}
    with pytest.raises(SystemExit, match="sport.*nfl.*nhl"):
        validate_packet_for_freeze(packet, "nhl", "2026-09-29",
                                   "2026-09-29T20:30:00+00:00", set())


def test_packet_missing_events_halts():
    packet = {"header": {"sport": "nhl", "slate_date": "2026-09-29",
                         "built_utc": "2026-09-29T20:00:00+00:00"},
              "games": [{"event_id": "e1", "commence_time": "2026-09-29T21:00:00+00:00"}]}
    with pytest.raises(SystemExit, match="missing.*sheet event"):
        validate_packet_for_freeze(packet, "nhl", "2026-09-29",
                                   "2026-09-29T20:30:00+00:00", {"e1", "e2"})


# ── Driver vs layer validation ──

def test_driver_absent_model_halts():
    """'model' while L4 is absent -> HALT."""
    packet = {"games": [{"event_id": "e1", "layers": {
        "market": {"h2h": {}}, "news": {}, "history": {},
        "model": {"absent": "outputs end 2025-04-17"}}}]}
    with pytest.raises(SystemExit, match="driver.*model.*absent"):
        validate_drivers_vs_packet("market,model", "e1", packet)


def test_driver_present_layers_pass():
    """Drivers naming only present (non-absent) layers pass."""
    packet = {"games": [{"event_id": "e1", "layers": {
        "market": {"h2h": {}}, "news": {"status": "no observations"},
        "history": {"TOR": {}}, "model": {"absent": "no output"}}}]}
    # No HALT for market,news,history
    validate_drivers_vs_packet("history,market,news", "e1", packet)


def test_driver_missing_layer_halts():
    """A driver naming a layer not in the packet -> HALT."""
    packet = {"games": [{"event_id": "e1", "layers": {"market": {}}}]}
    with pytest.raises(SystemExit, match="driver.*news.*no layer"):
        validate_drivers_vs_packet("market,news", "e1", packet)


# ── Builder SHA is content-based, not HEAD-based ──

def test_builder_sha_is_content_stamp(tmp_path):
    """builder_sha256 is computed from file content, not git HEAD."""
    f1 = tmp_path / "a.py"
    f1.write_text("# version 1")
    sha1 = builder_sha256(f1)
    f1.write_text("# version 2")
    sha2 = builder_sha256(f1)
    assert sha1 != sha2


# ── Freeze integration ──

def test_nhl_freeze_requires_packet(tmp_path):
    """NHL freeze without --packet -> HALT."""
    import nfl.pipeline.log_ai_opinions as L
    L.set_sport("nhl")
    fixture = pd.read_parquet(Path(__file__).resolve().parents[3] /
                              "nfl/pipeline/tests/fixtures/nhl_tape_20260929T2000Z.parquet")
    now = L.parse_utc("2026-09-29T20:00:08+00:00")
    props = pd.DataFrame(columns=["event_id","commence_time","home_team","away_team","bookmaker",
                                   "market_key","player_name","line","over_price","under_price","pull_timestamp"])
    sheet = L.build_sheet(props, fixture, now, slate_date="2026-09-29")
    sheet = sheet[sheet["home_team"] == "Carolina Hurricanes"].reset_index(drop=True)
    filled = sheet.copy()
    book = sheet["q_first"].where(sheet["two_way"], sheet["imp_first"])
    filled["p_first"] = np.clip(book + 0.03, L.P_MIN, L.P_MAX)
    filled["tag"] = "matchup"
    filled["reason"] = "test packet required HALT"
    filled["conf"] = list(range(100, 100 - len(filled), -1))
    filled["conf_rank"] = list(range(1, len(filled) + 1))
    filled["drivers"] = "market,news"
    d = tmp_path / "ai_opinions"
    d.mkdir()
    with pytest.raises(SystemExit, match="--packet is required"):
        L.freeze(sheet, filled, 2026, None, True, now, d=d,
                 reader_model="test", slate_date="2026-09-29")
    L.set_sport("nfl")


def test_football_freeze_no_packet_needed(tmp_path, monkeypatch):
    """Football freeze should NOT require a packet — null control."""
    import nfl.pipeline.log_ai_opinions as L
    L.set_sport("nfl")
    # Verify that SPORTS["nfl"]["drivers_required"] is False
    assert not L.SPORTS["nfl"].get("drivers_required", False)
    assert not L.SPORTS["ncaaf"].get("drivers_required", False)
    L.set_sport("nfl")


def test_packet_tamper_detected(tmp_path):
    """Editing a packet after freeze -> verify catches it."""
    import nfl.pipeline.log_ai_opinions as L
    L.set_sport("nhl")
    fixture = pd.read_parquet(Path(__file__).resolve().parents[3] /
                              "nfl/pipeline/tests/fixtures/nhl_tape_20260929T2000Z.parquet")
    now = L.parse_utc("2026-09-29T20:00:08+00:00")
    props = pd.DataFrame(columns=["event_id","commence_time","home_team","away_team","bookmaker",
                                   "market_key","player_name","line","over_price","under_price","pull_timestamp"])
    sheet = L.build_sheet(props, fixture, now, slate_date="2026-09-29")
    sheet = sheet[sheet["home_team"] == "Carolina Hurricanes"].reset_index(drop=True)
    filled = sheet.copy()
    book = sheet["q_first"].where(sheet["two_way"], sheet["imp_first"])
    filled["p_first"] = np.clip(book + 0.03, L.P_MIN, L.P_MAX)
    filled["tag"] = "matchup"
    filled["reason"] = "test tamper detection packet"
    filled["conf"] = list(range(100, 100 - len(filled), -1))
    filled["conf_rank"] = list(range(1, len(filled) + 1))
    filled["drivers"] = "history,market,news"
    # Write a minimal valid packet
    packet = {"header": {"sport": "nhl", "slate_date": "2026-09-29",
                         "built_utc": "2026-09-29T19:59:00+00:00", "builder_sha256": "x",
                         "sources": []},
              "games": []}
    # Add game entries for events in the sheet
    for eid in sheet["event_id"].unique():
        ev = sheet[sheet["event_id"] == eid].iloc[0]
        packet["games"].append({
            "event_id": eid, "home": ev["home_team"], "away": ev["away_team"],
            "commence_time": ev["commence_time"],
            "layers": {"market": {"h2h": {}}, "news": {"status": "no obs"},
                       "history": {"CAR": {}, "FLA": {}},
                       "model": {"absent": "no output"}}
        })
    pp = tmp_path / "packet.json"
    pp.write_text(json.dumps(packet))
    d = tmp_path / "ai_opinions"
    d.mkdir()
    L.freeze(sheet, filled, 2026, None, True, now, d=d,
             reader_model="test", slate_date="2026-09-29", packet_path=str(pp))
    # Verify passes
    entries, bad, unlisted = L.verify(slate_date="2026-09-29", d=d)
    assert not bad and not unlisted
    # Tamper with packet
    pf = d / entries[0]["packet_file"]
    pf.write_text(pf.read_text().replace('"nhl"', '"nba"'))
    entries2, bad2, _ = L.verify(slate_date="2026-09-29", d=d)
    assert entries2[0]["packet_file"] in bad2
    L.set_sport("nfl")
