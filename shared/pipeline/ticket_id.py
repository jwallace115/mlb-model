#!/usr/bin/env python3
"""
Item 2 of claude/ops_workorder_bet_ledger_2026-10-03.md: one `ticket_id` per pick, from the
moment it is built to the slip it becomes.

  ticket_id = <lane>_<slate>_<kind>_<buildtime as YYYYMMDDTHHMMSSZ>
              e.g. ncaaf_2026-10-04_card5_20261004T150212Z

LANE LOGGERS (ncaaf/, nhl/, nba/, nfl/sim/, nfl/pipeline/) call `stamp()` on each pick dict
just before they append it to their log. It adds `ticket_id` (and `build_time` if missing) and
never changes an id that is already there, so re-logging is safe and old picks without an id
still log exactly as before.

WHEN JEFF PASTES A SLIP, the chat that logged the pick calls `record_placement(slip_id,
ticket_id, lane)`. That writes ONE row to bets/placements.csv (gitignored: slip ids never
enter the public repo). The lane's own placement JSON may carry the ticket_id; it never
carries the slip id.

build_pick_ledger.py joins picks to slips on ticket_id through bets/placements.csv first, and
falls back to the item-1 leg-agreement rule only for picks logged before this existed.
"""
import csv, os, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
PLACEMENTS = ROOT / "bets" / "placements.csv"
PLACEMENT_COLS = ["slip_id", "ticket_id", "lane", "recorded_utc", "note"]
LANES = {"nfl", "ncaaf", "nhl", "nba", "mlb", "golf", "soccer", "ops"}


def _token(s):
    return re.sub(r"[^A-Za-z0-9.-]+", "-", str(s)).strip("-").lower()


def _utc(ts):
    if ts is None:
        return datetime.now(timezone.utc)
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        raise ValueError("build time must be timezone-aware (UTC)")
    return ts.astimezone(timezone.utc)


def make_ticket_id(lane, slate, kind, build_time=None):
    lane = _token(lane)
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; one of {sorted(LANES)}")
    if not str(slate).strip() or not str(kind).strip():
        raise ValueError("slate and kind are required")
    return f"{lane}_{_token(slate)}_{_token(kind)}_{_utc(build_time):%Y%m%dT%H%M%SZ}"


def stamp(pick, lane, slate, kind, build_time=None):
    """Add ticket_id (and build_time) to a pick dict in place; return the id.
    An existing ticket_id is kept as is (backward compatible, idempotent)."""
    if pick.get("ticket_id"):
        return pick["ticket_id"]
    bt = _utc(build_time or pick.get("build_time"))
    pick.setdefault("build_time", bt.isoformat())
    pick["ticket_id"] = make_ticket_id(lane, slate, kind, bt)
    return pick["ticket_id"]


def record_placement(slip_id, ticket_id, lane, note="", path=None):
    """Append slip_id -> ticket_id to bets/placements.csv (private). Refuses a slip already
    linked to a different ticket: a slip comes from one ticket."""
    path = Path(path or PLACEMENTS)
    slip_id, ticket_id = str(slip_id).strip(), str(ticket_id).strip()
    if not slip_id or not ticket_id:
        raise ValueError("slip_id and ticket_id are required")
    rows = read_placements(path)
    for r in rows:
        if r["slip_id"] == slip_id:
            if r["ticket_id"] == ticket_id:
                return False                       # already recorded
            raise ValueError(f"slip already linked to another ticket ({r['ticket_id']})")
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PLACEMENT_COLS)
        if new:
            w.writeheader()
        w.writerow(dict(slip_id=slip_id, ticket_id=ticket_id, lane=_token(lane),
                        recorded_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), note=note))
    return True


def read_placements(path=None):
    path = Path(path or PLACEMENTS)
    if not path.exists():
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def attach_slips(picks, placements):
    """Exact join, no fuzzy matching: every pick row whose ticket_id has a placement row gets
    that slip_id and join_method='ticket_id'. `picks` is a DataFrame with a ticket_id column;
    `placements` is read_placements() output. Returns a copy."""
    P = picks.copy()
    by_ticket = {}
    for r in placements:
        by_ticket.setdefault(r["ticket_id"], r["slip_id"])
    if "slip_id" not in P:
        P["slip_id"] = None
    if "join_method" not in P:
        P["join_method"] = None
    hit = P.ticket_id.isin(by_ticket)
    P.loc[hit, "slip_id"] = P.loc[hit, "ticket_id"].map(by_ticket)
    P.loc[hit, "join_method"] = "ticket_id"
    return P
