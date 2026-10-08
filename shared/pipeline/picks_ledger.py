#!/usr/bin/env python3
"""
Append-only pick ledger. One row per leg, JSONL on disk, idempotent append.

  admit(rows, members) — validate every field; HALT with row diagnostics on any failure.
  append(rows, ledger_dir) — write only rows whose pick_id is absent; fsync.
  view(ledger_dir) — latest row per pick_id after applying supersedes + grading.

OPS2 Item 1 — P1 contract.
"""
import hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path

AI_SOURCES = {"ai_nfl", "ai_ncaaf", "ai_nhl", "ai_nba", "sim_nfl"}
VALID_SOURCES = {"ai_opinion", "sim", "ticket_card", "member_share", "jeff_manual"}
VALID_RESULTS = {"W", "L", "P", "VOID", "UNRESOLVED", None}
VALID_SPORTS = {"NFL", "NCAAF", "NHL", "NBA", "MLB", "Soccer", "Golf"}
VALID_SIDES = {"over", "under", "Over", "Under"}  # prop sides; team names also allowed

LEDGER_FILE = "picks.jsonl"


class Halt(Exception):
    pass


def _env_dir():
    d = os.environ.get("PICKS_LEDGER_DIR")
    return Path(d) if d else None


def _parse_utc(s, field):
    """Parse a string to UTC datetime; raise on failure."""
    if s is None or (isinstance(s, float) and s != s):
        raise ValueError(f"{field}: null")
    s = str(s).strip()
    if not s:
        raise ValueError(f"{field}: blank")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError(f"{field}: cannot parse {s!r}")
    if dt.tzinfo is None:
        raise ValueError(f"{field}: no timezone in {s!r}")
    return dt.astimezone(timezone.utc)


def _is_blank(v):
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    s = str(v).strip()
    return s == "" or s.lower() in ("none", "nan", "<na>")


def make_pick_id(ticket_id, owner, source, event_id, market, player_name, side, point):
    """Deterministic pick_id = sha256(ticket_id|owner|source|event_id|market|player_name|side|point)[:16]"""
    parts = "|".join(str(x) for x in [ticket_id, owner, source, event_id, market,
                                        player_name or "", side, point])
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def load_members(ledger_dir):
    p = Path(ledger_dir) / "members.json"
    if not p.exists():
        raise Halt(f"members.json not found at {p}")
    d = json.loads(p.read_text())
    return set(d.get("members", []))


# ---- contract columns (exact names, exact order) ----
COLS = [
    "pick_id", "ticket_id", "owner", "source", "logged_utc", "sport", "event_id",
    "commence_time", "home", "away", "market", "player_id", "player_name", "side",
    "point", "price_american", "book", "reason", "share_link", "supersedes",
    "result", "graded_utc", "result_source", "ingested_utc", "source_file", "source_row",
    "tag", "conf",
]


def admit(rows, members):
    """Validate a list of row dicts. HALT with row diagnostics on any failure.
    Run on raw rows BEFORE any dedup/groupby (A6)."""
    if not rows:
        return rows
    valid_owners = members | AI_SOURCES
    errors = []
    for i, r in enumerate(rows):
        sf = r.get("source_file", "?")
        sr = r.get("source_row", i)
        prefix = f"file={sf} row={sr}"

        # non-null, non-blank after strip
        for field in ("ticket_id", "owner", "source", "sport", "event_id", "market", "side"):
            if _is_blank(r.get(field)):
                errors.append(f"{prefix}: {field} is blank/null (value={r.get(field)!r})")

        # domain checks
        if r.get("owner") and str(r["owner"]).strip().lower() not in {v.lower() for v in valid_owners}:
            errors.append(f"{prefix}: owner={r['owner']!r} not in members ∪ AI_SOURCES")
        if r.get("source") and str(r["source"]).strip() not in VALID_SOURCES:
            errors.append(f"{prefix}: source={r['source']!r} not in {VALID_SOURCES}")
        if r.get("sport") and str(r["sport"]).strip() not in VALID_SPORTS:
            errors.append(f"{prefix}: sport={r['sport']!r} not in {VALID_SPORTS}")

        # event_id = 32 hex
        eid = r.get("event_id")
        if eid is not None and not _is_blank(eid):
            eid_s = str(eid).strip()
            if not re.fullmatch(r"[0-9a-f]{32}", eid_s):
                errors.append(f"{prefix}: event_id={eid_s!r} not 32 hex chars")

        # result domain
        res = r.get("result")
        if res is not None and str(res).strip() != "" and str(res).strip() not in {"W", "L", "P", "VOID", "UNRESOLVED"}:
            errors.append(f"{prefix}: result={res!r} not in valid set")

        # timestamps
        try:
            logged = _parse_utc(r.get("logged_utc"), "logged_utc")
        except (ValueError, TypeError) as e:
            errors.append(f"{prefix}: {e}")
            logged = None
        try:
            commence = _parse_utc(r.get("commence_time"), "commence_time")
        except (ValueError, TypeError) as e:
            errors.append(f"{prefix}: {e}")
            commence = None

        if logged is not None and commence is not None and logged >= commence:
            errors.append(f"{prefix}: logged_utc ({r['logged_utc']}) >= commence_time ({r['commence_time']})")

        # price_american: int ≠ 0 or null with a stated reason
        pa = r.get("price_american")
        if pa is not None and not _is_blank(pa):
            try:
                pv = int(float(pa))
                if pv == 0:
                    errors.append(f"{prefix}: price_american is 0 (invalid)")
            except (ValueError, TypeError):
                errors.append(f"{prefix}: price_american={pa!r} not an int")

    if errors:
        msg = f"admit() HALT: {len(errors)} error(s):\n" + "\n".join(errors)
        raise Halt(msg)
    return rows


def append(rows, ledger_dir):
    """Append only admitted rows whose (pick_id, result) pair is not already present.
    A grade row (same pick_id, new result) IS appended; view() picks the latest by ingested_utc.
    Returns (appended, skipped)."""
    ledger_dir = Path(ledger_dir)
    path = ledger_dir / LEDGER_FILE
    existing = set()  # (pick_id, result) pairs
    if path.exists():
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        existing.add((d["pick_id"], d.get("result")))
                    except (json.JSONDecodeError, KeyError):
                        pass

    now_utc = datetime.now(timezone.utc).isoformat()
    new_rows = []
    for r in rows:
        pid = r.get("pick_id") or make_pick_id(
            r["ticket_id"], r["owner"], r["source"], r["event_id"],
            r["market"], r.get("player_name"), r["side"], r.get("point"))
        r["pick_id"] = pid
        key = (pid, r.get("result"))
        if key in existing:
            continue
        r.setdefault("ingested_utc", now_utc)
        # ensure all contract cols present
        for c in COLS:
            r.setdefault(c, None)
        new_rows.append(r)
        existing.add(key)

    if new_rows:
        ledger_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            for r in new_rows:
                f.write(json.dumps({c: r.get(c) for c in COLS}, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())

    return len(new_rows), len(rows) - len(new_rows)


def _read_all(ledger_dir):
    """Read all rows from the JSONL ledger."""
    path = Path(ledger_dir) / LEDGER_FILE
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def view(ledger_dir):
    """Latest row per pick_id after applying supersedes (a correction row wins over
    the row it names) and grading (same pick_id, later ingested_utc)."""
    rows = _read_all(ledger_dir)
    if not rows:
        return []

    # Group by pick_id; latest ingested_utc wins
    by_id = {}
    for r in rows:
        pid = r["pick_id"]
        existing = by_id.get(pid)
        if existing is None or (r.get("ingested_utc") or "") > (existing.get("ingested_utc") or ""):
            by_id[pid] = r

    # Apply supersedes: if row A supersedes row B, remove B
    superseded = set()
    for r in by_id.values():
        s = r.get("supersedes")
        if s:
            superseded.add(s)

    return [r for pid, r in by_id.items() if pid not in superseded]
