#!/usr/bin/env python3
"""
Top-20 picks selector: ranks AI reader picks by confidence for the upcoming slate.

select(view_rows, sport, now) → {freeze_logged_utc, props, sides, unranked, n_picks_in_freeze}
  - AI owners only (ai_<sport>); sim_nfl rows are NOT ranked (they feed the sim layer)
  - member/jeff rows never appear
  - Ranked by conf desc, ties by |edge| desc then logged_utc asc
  - null conf → unranked (listed, never ranked)
  - commence_time <= now → excluded (past games drop at the next build)
  - ≤ 20 per column (props vs sides/totals/ML)

OPS3 Item 1, P10.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import picks_ledger as pl

LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
MAX_PER_COLUMN = 20
AI_OWNERS = {"ai_nfl", "ai_ncaaf", "ai_nhl", "ai_nba"}
SPORTS = ["NFL", "NCAAF", "NHL", "NBA"]


def _is_prop(market):
    return bool(market) and (market.startswith("prop") or "player_" in market)


def _sort_key(r):
    """Sort: conf desc, |edge| desc, logged_utc asc."""
    conf = r.get("conf") or 0
    # edge approximation from price: further from -110 → larger |edge|
    price = r.get("price_american")
    edge = 0
    if price is not None:
        try:
            p = float(price)
            # implied prob diff from 50%
            if p < 0:
                edge = abs(abs(p) / (abs(p) + 100) - 0.5)
            else:
                edge = abs(100 / (p + 100) - 0.5)
        except (ValueError, TypeError):
            pass
    logged = r.get("logged_utc") or ""
    return (-conf, -edge, logged)


def select(view_rows, sport, now):
    """Select top-20 picks for a sport from the ledger view.

    Returns dict with keys: freeze_logged_utc, props, sides, unranked,
    n_picks_in_freeze. Returns None if no upcoming freeze.
    """
    ai_owner = f"ai_{sport.lower()}"

    # Filter to AI owner for this sport — results are never an input to ranking
    candidates = [r for r in view_rows
                  if r.get("owner") == ai_owner
                  and r.get("sport") == sport]

    if not candidates:
        return None

    # Group by source_file (freeze) — find the latest freeze whose picks are upcoming
    from collections import defaultdict
    by_source = defaultdict(list)
    for r in candidates:
        sf = r.get("source_file", "")
        by_source[sf].append(r)

    # Find the latest freeze with at least one upcoming pick
    # Only consider freezes whose logged_utc <= now (no future data)
    best_freeze = None
    best_logged = ""
    for sf, rows in by_source.items():
        logged = rows[0].get("logged_utc", "")
        if logged and _parse_dt(logged) > now:
            continue  # freeze from the future
        has_upcoming = any(
            r.get("commence_time") and _parse_dt(r["commence_time"]) > now
            for r in rows
        )
        if not has_upcoming:
            continue
        if logged > best_logged:
            best_logged = logged
            best_freeze = sf

    if best_freeze is None:
        return None

    freeze_rows = by_source[best_freeze]

    # Check: no two freezes share the same logged_utc
    freeze_logged_times = set()
    for sf, rows in by_source.items():
        lt = rows[0].get("logged_utc", "")
        if lt in freeze_logged_times and lt:
            raise pl.Halt(f"two freezes share logged_utc {lt}: {sf}")
        freeze_logged_times.add(lt)

    # Filter to upcoming picks only
    upcoming = [r for r in freeze_rows
                if r.get("commence_time") and _parse_dt(r["commence_time"]) > now]

    # Validate ranked rows
    for r in upcoming:
        if r.get("conf") is not None:
            for field in ("event_id", "price_american", "side"):
                if pl._is_blank(r.get(field)):
                    raise pl.Halt(
                        f"ranked row lacks {field}: pick_id={r.get('pick_id')}, "
                        f"market={r.get('market')}, side={r.get('side')}")

    # Split into props vs sides
    props_all = [r for r in upcoming if _is_prop(r.get("market"))]
    sides_all = [r for r in upcoming if not _is_prop(r.get("market"))]

    # Separate ranked (has conf) from unranked (null conf)
    props_ranked = sorted([r for r in props_all if r.get("conf") is not None], key=_sort_key)
    sides_ranked = sorted([r for r in sides_all if r.get("conf") is not None], key=_sort_key)
    unranked = [r for r in upcoming if r.get("conf") is None]

    # Determine freeze window (from the first row's window field)
    freeze_window = freeze_rows[0].get("window") or "legacy"

    return {
        "freeze_logged_utc": best_logged,
        "freeze_source": best_freeze,
        "window": freeze_window,
        "props": props_ranked[:MAX_PER_COLUMN],
        "sides": sides_ranked[:MAX_PER_COLUMN],
        "unranked": unranked,
        "n_picks_in_freeze": len(freeze_rows),
    }


def _parse_dt(s):
    """Parse a datetime string to UTC."""
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    s = str(s).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def main():
    ap = argparse.ArgumentParser(description="Top-20 picks selector")
    ap.add_argument("--as-of", help="UTC datetime (default: now)")
    ap.add_argument("--sport", help="single sport to select")
    ap.add_argument("--print-top", type=int, help="print both columns in full (for chat post)")
    a = ap.parse_args()

    now = datetime.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    view_rows = pl.view(LEDGER_DIR)
    sports = [a.sport.upper()] if a.sport else SPORTS

    for sport in sports:
        result = select(view_rows, sport, now)
        if result is None:
            print(f"{sport}: no upcoming freeze")
            continue
        window = result.get("window", "legacy")
        print(f"{sport}: {window} freeze={result['freeze_logged_utc'][:19]}, "
              f"n_in_freeze={result['n_picks_in_freeze']}, "
              f"props={len(result['props'])}/{MAX_PER_COLUMN}, "
              f"sides={len(result['sides'])}/{MAX_PER_COLUMN}, "
              f"unranked={len(result['unranked'])}")
        top_n = a.print_top if a.print_top else 3
        for col, label in [("props", "Props"), ("sides", "Sides/Totals/ML")]:
            picks = result[col]
            if picks:
                print(f"  {label} top {min(top_n, len(picks))}:")
                for i, p in enumerate(picks[:top_n]):
                    reason_short = (str(p.get('reason') or '')[:80]).replace('\n', ' ')
                    print(f"    {i+1}. conf={p.get('conf')}, {p.get('player_name') or p.get('side')}, "
                          f"{p.get('market')}, {p.get('point')}, price={p.get('price_american')}, "
                          f"book={p.get('book')}, {reason_short}")


if __name__ == "__main__":
    main()
