"""Sport-agnostic packet builder core.

A packet is the immutable record of what the reader saw before freezing an opinion.
It is canonical JSON (sorted keys, fixed float format) so that identical inputs always
produce the identical hash. It is saved beside the frozen file and verified on every
verify call.

Structure:
  header: {sport, slate_date, built_utc, builder_sha256, sources: [{path, sha256, source_utc}]}
  games: [{event_id, home, away, commence_time, layers: {market, news, history, model}}]
"""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


def parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _canonical_float(v):
    """Fixed-precision float for canonical JSON: 6 decimal places, no trailing zeros
    beyond the first, ±Inf/NaN -> string."""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return str(v)
        return round(v, 6)
    return v


def _canonical_obj(obj):
    """Recursively prepare an object for canonical JSON."""
    if isinstance(obj, dict):
        return {k: _canonical_obj(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_canonical_obj(v) for v in obj]
    if isinstance(obj, float):
        return _canonical_float(v=obj)
    return obj


def to_canonical_json(packet):
    """Canonical JSON: sorted keys, fixed float format, deterministic."""
    return json.dumps(_canonical_obj(packet), sort_keys=True, separators=(",", ":"))


def packet_sha256(packet):
    """SHA-256 of the canonical JSON representation."""
    return hashlib.sha256(to_canonical_json(packet).encode()).hexdigest()


def builder_sha256(*source_files):
    """Content stamp of the builder source files (never git HEAD — CLAUDE.md)."""
    h = hashlib.sha256()
    for f in sorted(str(s) for s in source_files):
        h.update(Path(f).read_bytes())
    return h.hexdigest()


def build_header(sport, slate_date, built_utc, builder_files, sources):
    """Construct the packet header.

    sources: list of {path, sha256, source_utc} dicts.
    builder_files: list of Path objects whose content forms the builder stamp.
    """
    built_t = parse_utc(built_utc)
    for s in sources:
        src_t = parse_utc(s["source_utc"])
        if src_t >= built_t:
            raise SystemExit(f"HALT: source {s['path']} source_utc {s['source_utc']} >= built_utc {built_utc}")
    return {
        "sport": sport,
        "slate_date": str(slate_date),
        "built_utc": str(built_utc),
        "builder_sha256": builder_sha256(*builder_files),
        "sources": sources,
    }


def build_packet(header, games, first_commence_time):
    """Assemble and validate the full packet.

    first_commence_time: the earliest game start; built_utc must be < this.
    games: list of {event_id, home, away, commence_time, layers: {...}}.
    """
    built_t = parse_utc(header["built_utc"])
    first_t = parse_utc(first_commence_time)
    if built_t >= first_t:
        raise SystemExit(f"HALT: built_utc {header['built_utc']} >= first commence_time {first_commence_time}")
    return {"header": header, "games": games}


def validate_packet_for_freeze(packet, sport, slate_date, freeze_utc, sheet_events):
    """Validate a packet before freeze.

    Checks: sport/date match; built_utc <= freeze_utc and < first puck;
    packet games include every sheet event.
    """
    h = packet["header"]
    if h["sport"] != sport:
        raise SystemExit(f"HALT: packet sport '{h['sport']}' != freeze sport '{sport}'")
    if h["slate_date"] != str(slate_date):
        raise SystemExit(f"HALT: packet slate_date '{h['slate_date']}' != freeze date '{slate_date}'")
    built_t = parse_utc(h["built_utc"])
    freeze_t = parse_utc(freeze_utc)
    if built_t > freeze_t:
        raise SystemExit(f"HALT: packet built_utc {h['built_utc']} > freeze time {freeze_utc}")
    # built_utc < first puck
    game_times = [parse_utc(g["commence_time"]) for g in packet["games"]]
    if game_times:
        first_puck = min(game_times)
        if built_t >= first_puck:
            raise SystemExit(f"HALT: packet built_utc >= first puck {first_puck.isoformat()}")
    # Every sheet event must be in the packet
    packet_events = {g["event_id"] for g in packet["games"]}
    missing = sheet_events - packet_events
    if missing:
        raise SystemExit(f"HALT: packet missing {len(missing)} sheet event(s): {sorted(missing)[:5]}")


def validate_drivers_vs_packet(drivers_str, event_id, packet):
    """Check that every driver in the frozen row names a layer present for its game.

    'model' while L4 is absent -> HALT.
    """
    game = None
    for g in packet["games"]:
        if g["event_id"] == event_id:
            game = g
            break
    if game is None:
        raise SystemExit(f"HALT: event {event_id} not found in packet")
    layers = game.get("layers", {})
    for d in drivers_str.split(","):
        d = d.strip()
        if not d:
            continue
        layer = layers.get(d)
        if layer is None:
            raise SystemExit(f"HALT: driver '{d}' on event {event_id} has no layer in packet")
        if isinstance(layer, dict) and layer.get("absent"):
            raise SystemExit(f"HALT: driver '{d}' on event {event_id} is absent in packet: {layer['absent']}")
