#!/usr/bin/env python3
"""
CLV per pick: closing line value, deterministic, in a sidecar file.

For every kicked pick with event_id + market + side + point/price:
finds the closing quote from the tape, computes clv_points and clv_price_pct.
Output: PICKS_LEDGER_DIR/clv.jsonl (append-only, one row per pick_id).

OPS4a Item 3, P22.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_sources as ps
import picks_ledger as pl

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
TS_RE = re.compile(r"(\d{8}T\d{4}(?:\d{2})?Z)")

_snap_cache = {}


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


def _implied_prob(american):
    """American odds → implied probability (raw, no de-vig)."""
    if american is None:
        return None
    try:
        p = float(american)
        if p < 0:
            return abs(p) / (abs(p) + 100)
        elif p > 0:
            return 100 / (p + 100)
        return None
    except (ValueError, TypeError):
        return None


_snap_index = {}  # sport_folder → sorted list of (ts, path)


def _build_snap_index(root, sport_folder):
    key = sport_folder
    if key not in _snap_index:
        tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history"
        entries = []
        for sd in tape_dir.glob("season=*"):
            for p in sd.glob("snap_*Z.parquet"):
                entries.append((_file_ts(p), p))
        _snap_index[key] = sorted(entries)
    return _snap_index[key]


def _find_closing_snapshot(root, sport_folder, commence_dt):
    """Find the LAST tape snapshot ≤ commence_time."""
    entries = _build_snap_index(root, sport_folder)
    best = None
    for ts, p in entries:
        if ts <= commence_dt:
            best = (ts, p)
        else:
            break  # sorted, so stop early
    return best


def _side_matches(outcome_name, side, sport):
    """Does the tape outcome match the pick's side?"""
    if not side or not outcome_name:
        return False
    s_lower = str(side).lower()
    o_lower = str(outcome_name).lower()
    if s_lower in ("over", "under"):
        return o_lower == s_lower
    if sport == "NFL":
        s_nick = ps.nfl_team(side)
        o_nick = ps.nfl_team(outcome_name)
        if s_nick and o_nick:
            return s_nick == o_nick
    return s_lower in o_lower or o_lower in s_lower


def compute_clv(view_rows, root, now):
    """Compute CLV for all kicked picks. Returns list of CLV rows."""
    root = Path(root)
    results = []

    for row in view_rows:
        eid = row.get("event_id")
        market = row.get("market", "")
        side = row.get("side")
        point = row.get("point")
        price = row.get("price_american")
        sport = row.get("sport", "")
        book = row.get("book")
        commence_dt = _parse_dt(row.get("commence_time"))

        if not eid or not market or not side or commence_dt is None:
            continue
        if commence_dt > now:
            continue  # not kicked yet

        sport_folder = {"NFL": "nfl", "NCAAF": "ncaaf", "NHL": "nhl", "NBA": "nba"}.get(sport)
        if not sport_folder:
            continue

        is_prop = market.startswith("prop") or "player_" in market
        close_point = None
        close_price = None
        close_book = None
        close_basis = None
        close_as_of = None
        close_source = None

        if is_prop:
            # Props: last pull ≤ commence_time
            tape_dir = root / "data" / "odds_archive" / sport_folder / "props"
            prop_market = "player_" + market.split(":", 1)[1] if ":" in market else market
            best_rows = []
            best_file = None
            for month_dir in tape_dir.glob("season=*/month=*"):
                for p in month_dir.glob("data_*.parquet"):
                    key = str(p)
                    if key not in _snap_cache:
                        df = pd.read_parquet(p)
                        if "pull_timestamp" in df.columns:
                            df["_pt"] = pd.to_datetime(df.pull_timestamp, utc=True, errors="coerce")
                        _snap_cache[key] = df
                    df = _snap_cache[key]
                    if "_pt" not in df.columns:
                        continue
                    mask = (df.event_id == eid) & (df._pt <= commence_dt)
                    if "market_key" in df.columns:
                        mask &= df.market_key == prop_market
                    if row.get("player_name"):
                        mask &= df.player_name == row["player_name"]
                    matched = df[mask]
                    if not matched.empty:
                        # Take the latest pull
                        latest_pt = matched["_pt"].max()
                        latest_rows = matched[matched["_pt"] == latest_pt]
                        if not best_rows or latest_pt > best_rows[0].get("_pt_val", datetime.min.replace(tzinfo=timezone.utc)):
                            best_rows = [{"_pt_val": latest_pt, "file": p.name, **r.to_dict()}
                                         for _, r in latest_rows.iterrows()]
                            best_file = p.name

            if best_rows:
                # Find nearest line for the pick's book
                book_rows = [r for r in best_rows if r.get("bookmaker") == book]
                if not book_rows:
                    # Consensus: median across books
                    by_book = {}
                    for r in best_rows:
                        bk = r.get("bookmaker", "?")
                        if bk not in by_book or abs(float(r.get("line", 999)) - float(point or 0)) < abs(float(by_book[bk].get("line", 999)) - float(point or 0)):
                            by_book[bk] = r
                    lines = [float(r.get("line", 0)) for r in by_book.values()]
                    if lines:
                        lines.sort()
                        mid = len(lines) // 2
                        close_point = lines[mid] if len(lines) % 2 else (lines[mid-1] + lines[mid]) / 2
                        close_basis = "consensus"
                        close_as_of = str(best_rows[0].get("_pt_val"))[:19]
                        close_source = best_file
                else:
                    # Nearest line to pick's point
                    best = min(book_rows, key=lambda r: abs(float(r.get("line", 0)) - float(point or 0)))
                    close_point = float(best.get("line", 0))
                    s = str(side).lower()
                    close_price = best.get("over_price") if "over" in s else best.get("under_price") if "under" in s else best.get("over_price")
                    close_book = book
                    close_basis = "book"
                    close_as_of = str(best.get("_pt_val"))[:19]
                    close_source = best_file
        else:
            # Game lines: last snapshot ≤ commence_time
            snap = _find_closing_snapshot(root, sport_folder, commence_dt)
            if snap:
                ts, path = snap
                key = str(path)
                if key not in _snap_cache:
                    _snap_cache[key] = pd.read_parquet(path)
                df = _snap_cache[key]
                tape_market = {"spread": "spreads", "moneyline": "h2h", "total": "totals"}.get(market, market)
                mask = (df.event_id == eid) & (df.market == tape_market)
                if "outcome_name" in df.columns:
                    mask &= df.outcome_name.apply(lambda o: _side_matches(o, side, sport))
                matched = df[mask]
                if not matched.empty:
                    # Pick's book first
                    book_matched = matched[matched.bookmaker == book] if book else pd.DataFrame()
                    if not book_matched.empty:
                        # Nearest line
                        if point is not None and book_matched["point"].notna().any():
                            book_matched = book_matched[book_matched["point"].notna()].copy()
                            book_matched["_d"] = (book_matched["point"].astype(float) - float(point)).abs()
                            best = book_matched.loc[book_matched["_d"].idxmin()]
                        else:
                            best = book_matched.iloc[0]
                        close_point = float(best["point"]) if pd.notna(best.get("point")) else None
                        close_price = best.get("price")
                        close_book = book
                        close_basis = "book"
                    else:
                        # Consensus: nearest line per book
                        by_book = {}
                        for _, r in matched.iterrows():
                            bk = r.get("bookmaker", "?")
                            if bk not in by_book or (point is not None and pd.notna(r.get("point")) and
                                abs(float(r["point"]) - float(point)) < abs(float(by_book[bk].get("point", 999)) - float(point))):
                                by_book[bk] = r
                        points = [float(r["point"]) for r in by_book.values() if pd.notna(r.get("point"))]
                        if points:
                            points.sort()
                            mid = len(points) // 2
                            close_point = points[mid] if len(points) % 2 else (points[mid-1] + points[mid]) / 2
                        close_basis = "consensus"
                    close_as_of = str(ts)[:19]
                    close_source = path.name

        # Compute CLV
        clv_points = None
        clv_price_pct = None

        if market == "moneyline":
            clv_points = None  # moneyline has no point
        elif close_point is not None and point is not None:
            if market == "spread":
                clv_points = float(point) - close_point  # bettor's favour
            elif "over" in str(side).lower():
                clv_points = close_point - float(point)
            elif "under" in str(side).lower():
                clv_points = float(point) - close_point
            else:
                clv_points = float(point) - close_point

        if close_price is not None and price is not None:
            cp = _implied_prob(close_price)
            pp = _implied_prob(price)
            if cp is not None and pp is not None:
                clv_price_pct = round(cp - pp, 4)

        results.append({
            "pick_id": row.get("pick_id"),
            "close_point": close_point,
            "close_price": int(float(close_price)) if close_price is not None and not (isinstance(close_price, float) and close_price != close_price) else None,
            "close_book": close_book,
            "close_basis": close_basis,
            "close_as_of": close_as_of,
            "close_source": close_source,
            "clv_points": round(clv_points, 2) if clv_points is not None else None,
            "clv_price_pct": clv_price_pct,
            "computed_utc": now.isoformat(),
        })

    return results


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    view_rows = pl.view(LEDGER_DIR)
    clv_path = LEDGER_DIR / "clv.jsonl"

    # Load existing pick_ids
    existing = set()
    if clv_path.exists():
        with open(clv_path) as f:
            for line in f:
                if line.strip():
                    try:
                        existing.add(json.loads(line)["pick_id"])
                    except (json.JSONDecodeError, KeyError):
                        pass

    # Filter to picks not already computed
    todo = [r for r in view_rows if r.get("pick_id") not in existing]
    results = compute_clv(todo, ROOT, now)

    if results:
        with open(clv_path, "a") as f:
            for r in results:
                f.write(json.dumps(r, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())

    n_with_close = sum(1 for r in results if r.get("close_point") is not None)
    print(f"clv: {len(results)} rows written ({n_with_close} with close), {len(existing)} already present")


if __name__ == "__main__":
    main()
