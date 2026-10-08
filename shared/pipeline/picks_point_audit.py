#!/usr/bin/env python3
"""
Spread point sign audit: verify every spread row's point against the tape.

--report: print counts by (owner, source, class) and every SIGN_FLIPPED row.
--repair: append correction rows (supersedes the old) and regrade.

OPS3c Item 1, P16.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_sources as ps
import picks_grader as pg
import picks_ledger as pl

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
TS_RE = re.compile(r"(\d{8}T\d{4}(?:\d{2})?Z)")


def _file_ts(p):
    m = TS_RE.search(p.name)
    if m:
        s = m.group(1)
        fmt = "%Y%m%dT%H%M%SZ" if len(s) == 16 else "%Y%m%dT%H%MZ"
        return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)


def _parse_dt(s):
    if not s:
        return None
    s = str(s).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _normalise_side(side, sport):
    """Normalise a side name for matching against tape outcome_name."""
    if not side:
        return ""
    if sport == "NFL":
        n = ps.nfl_team(side)
        return n if n else side.lower()
    return side.lower()


def _find_nearest_snapshot(root, sport_folder, logged_dt, commence_dt):
    """Find the snapshot nearest before logged_utc, >= commence-7d."""
    tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history"
    window_start = commence_dt - timedelta(days=7)
    best = None
    for sd in tape_dir.glob("season=*"):
        for p in sd.glob("snap_*Z.parquet"):
            ts = _file_ts(p)
            if window_start <= ts <= logged_dt:
                if best is None or ts > best[0]:
                    best = (ts, p)
    return best


_snap_cache = {}


def audit(root, ledger_dir):
    """Audit every spread row in the ledger against the tape. Returns list of dicts."""
    root = Path(root)
    view_rows = pl.view(ledger_dir)
    results = []

    for row in view_rows:
        if row.get("market") != "spread":
            continue
        eid = row.get("event_id")
        if not eid:
            continue

        sport = row.get("sport", "")
        sport_folder = {"NFL": "nfl", "NCAAF": "ncaaf"}.get(sport)
        if not sport_folder:
            continue

        logged_dt = _parse_dt(row.get("logged_utc"))
        commence_dt = _parse_dt(row.get("commence_time"))
        if not logged_dt or not commence_dt:
            continue

        # Find nearest snapshot before logged_utc
        snap = _find_nearest_snapshot(root, sport_folder, logged_dt, commence_dt)
        if snap is None:
            results.append({**row, "_class": "NO_TAPE", "_tape_point": None, "_snapshot": None})
            continue

        ts, path = snap
        key = str(path)
        if key not in _snap_cache:
            _snap_cache[key] = pd.read_parquet(path)
        df = _snap_cache[key]

        # Filter for this event + spreads market
        tape_rows = df[(df.event_id == eid) & (df.market == "spreads")]
        if tape_rows.empty:
            results.append({**row, "_class": "NO_TAPE", "_tape_point": None, "_snapshot": path.name})
            continue

        # Find the row matching the pick's side
        side_norm = _normalise_side(row.get("side"), sport)
        book = row.get("book")

        # Try pick's book first, then any book
        for book_filter in ([book] if book else []) + [None]:
            candidates = tape_rows
            if book_filter:
                candidates = candidates[candidates.bookmaker == book_filter]
            for _, tr in candidates.iterrows():
                tape_side = _normalise_side(tr.outcome_name, sport)
                if tape_side == side_norm:
                    tape_point = float(tr.point) if pd.notna(tr.point) else None
                    stored_point = row.get("point")
                    if stored_point is None or tape_point is None:
                        cls = "NO_TAPE"
                    elif abs(stored_point) == abs(tape_point) and (stored_point > 0) == (tape_point > 0):
                        cls = "AGREES"
                    elif abs(stored_point) == abs(tape_point):
                        cls = "SIGN_FLIPPED"
                    elif (stored_point > 0) == (tape_point > 0):
                        cls = "MAGNITUDE"
                    else:
                        cls = "SIGN_FLIPPED"
                    results.append({**row, "_class": cls, "_tape_point": tape_point,
                                    "_snapshot": path.name, "_book_matched": book_filter or tr.bookmaker})
                    break
            else:
                continue
            break
        else:
            results.append({**row, "_class": "NO_TAPE", "_tape_point": None, "_snapshot": path.name})

    return results


def repair(root, ledger_dir):
    """Append correction rows for SIGN_FLIPPED picks and regrade."""
    audit_rows = audit(root, ledger_dir)
    flipped = [r for r in audit_rows if r["_class"] == "SIGN_FLIPPED"]
    if not flipped:
        print("no SIGN_FLIPPED rows to repair")
        return 0

    # Check no already-superseded rows
    view_rows = pl.view(ledger_dir)
    superseded = {r.get("supersedes") for r in view_rows if r.get("supersedes")}

    corrections = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for row in flipped:
        old_pid = row["pick_id"]
        if old_pid in superseded:
            raise pl.Halt(f"pick_id {old_pid} is already superseded — cannot repair")

        corrected = {k: v for k, v in row.items() if not k.startswith("_")}
        corrected["point"] = -corrected["point"]  # negate
        corrected["supersedes"] = old_pid
        corrected["result"] = None
        corrected["graded_utc"] = None
        corrected["result_source"] = None
        corrected["ingested_utc"] = now_iso
        reason = corrected.get("reason") or ""
        corrected["reason"] = (reason + f"; point sign corrected per tape {row['_snapshot']} (P16)")[:200]
        corrected["pick_id"] = pl.make_pick_id(
            corrected["ticket_id"], corrected["owner"], corrected["source"],
            corrected["event_id"], corrected["market"], corrected.get("player_name"),
            corrected["side"], corrected["point"])
        corrections.append(corrected)

    appended, skipped = pl.append(corrections, ledger_dir)
    print(f"repair: {appended} correction rows appended, {skipped} skipped (already present)")

    # Regrade
    graded = pg.grade(ledger_dir)
    if graded:
        g_appended, g_skipped = pl.append(graded, ledger_dir)
        print(f"regrade: {g_appended} grade rows appended, {g_skipped} skipped")
    else:
        print("regrade: nothing to grade")

    return appended


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--repair", action="store_true")
    a = ap.parse_args()

    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    if a.report:
        results = audit(ROOT, LEDGER_DIR)
        from collections import Counter
        counts = Counter()
        for r in results:
            counts[(r.get("owner", "?"), r.get("source", "?"), r["_class"])] += 1
        print("counts by (owner, source, class):")
        for (owner, source, cls), n in sorted(counts.items()):
            print(f"  {owner:12s} {source:15s} {cls}: {n}")
        print()
        flipped = [r for r in results if r["_class"] == "SIGN_FLIPPED"]
        if flipped:
            print(f"SIGN_FLIPPED rows ({len(flipped)}):")
            for r in flipped:
                print(f"  pick_id={r['pick_id'][:12]}, side={r.get('side')}, "
                      f"stored={r.get('point')}, tape={r['_tape_point']}, "
                      f"book={r.get('_book_matched')}, snap={r['_snapshot']}")
        else:
            print("no SIGN_FLIPPED rows")

    if a.repair:
        repair(ROOT, LEDGER_DIR)


if __name__ == "__main__":
    main()
