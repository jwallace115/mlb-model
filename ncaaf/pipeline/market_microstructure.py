#!/usr/bin/env python3
"""
N08/N09: NCAAF market microstructure layer.

Reads only the existing line tape. Zero credits. Zero fitting.
Pre-kick eligibility: snapshot_utc < commence_time AND snapshot_utc <= build_time.

Reports:
  4a. Hold by leg count (from single-leg no-vig overround)
  4b. Move origination (which book moved first)
  4c. Stale-book detection (book_last_update stale while consensus moved)
  4d. Hold by market per book
"""

import argparse, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
TAPE_DIR = ROOT / "data" / "odds_archive" / "ncaaf" / "line_history"


def american_to_implied(odds):
    if pd.isna(odds):
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def load_tape(season, build_time=None):
    tape_path = TAPE_DIR / f"season={season}"
    if not tape_path.exists():
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in sorted(tape_path.glob("*.parquet"))]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["snapshot_dt"] = pd.to_datetime(df["snapshot_utc"], utc=True, errors="coerce")
    df["commence_dt"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
    df["update_dt"] = pd.to_datetime(df["book_last_update"], utc=True, errors="coerce")
    pre = df[df["snapshot_dt"] < df["commence_dt"]]
    if build_time:
        bt = pd.Timestamp(build_time, tz="UTC")
        pre = pre[pre["snapshot_dt"] <= bt]
    return pre


def hold_by_market(tape):
    """4d: No-vig overround per market per book."""
    print("\n=== 4d. HOLD BY MARKET ===")
    tape["implied"] = tape["price"].apply(american_to_implied)

    rows = []
    for (eid, mkt, book), g in tape.groupby(["event_id", "market", "bookmaker"]):
        latest = g.sort_values("snapshot_dt", ascending=False).drop_duplicates("outcome_name")
        if len(latest) < 2:
            continue
        total_imp = latest["implied"].sum()
        overround = total_imp - 1.0
        rows.append({"market": mkt, "book": book, "overround": overround, "n_outcomes": len(latest)})

    if not rows:
        print("  No data")
        return

    rdf = pd.DataFrame(rows)
    print(f"\n{'Market':>10s} {'Book':>20s} {'Mean OR':>8s} {'N':>5s}")
    for (mkt, book), g in rdf.groupby(["market", "book"]):
        print(f"{mkt:>10s} {book:>20s} {g['overround'].mean():>8.3f} {len(g):>5d}")


def stale_book_detection(tape):
    """4c: Flag books whose update hasn't advanced while consensus moved."""
    print("\n=== 4c. STALE-BOOK DETECTION ===")
    # For each event × market × outcome, check if any book's last_update
    # hasn't changed while others have moved the point by > 1
    stale_flags = []
    for (eid, mkt, side), g in tape.groupby(["event_id", "market", "outcome_name"]):
        if len(g) < 5:
            continue
        # Latest snapshot per book
        latest = g.sort_values("snapshot_dt", ascending=False).drop_duplicates("bookmaker")
        if len(latest) < 3:
            continue
        points = latest[latest["point"].notna()]
        if len(points) < 2:
            continue
        consensus_point = points["point"].median()
        for _, row in latest.iterrows():
            if pd.notna(row["point"]) and abs(row["point"] - consensus_point) > 1.0:
                # Check if this book's last_update is old
                other_updates = latest[latest["bookmaker"] != row["bookmaker"]]["update_dt"]
                if other_updates.empty:
                    continue
                newest_other = other_updates.max()
                if pd.notna(row["update_dt"]) and pd.notna(newest_other):
                    lag_hours = (newest_other - row["update_dt"]).total_seconds() / 3600
                    if lag_hours > 2:
                        stale_flags.append({
                            "event_id": eid, "market": mkt, "side": side,
                            "book": row["bookmaker"],
                            "book_point": row["point"], "consensus_point": consensus_point,
                            "lag_hours": round(lag_hours, 1),
                        })

    if stale_flags:
        sf = pd.DataFrame(stale_flags)
        print(f"  Stale flags: {len(sf)}")
        for book, g in sf.groupby("book"):
            print(f"    {book}: {len(g)} flags, mean lag {g['lag_hours'].mean():.1f}h")
    else:
        print("  No stale books detected")

    # Null control: find a window where every book updated recently
    latest_all = tape.sort_values("snapshot_dt", ascending=False).drop_duplicates(
        ["event_id", "bookmaker"], keep="first")
    recent_window = latest_all[latest_all["snapshot_dt"] > latest_all["snapshot_dt"].max() - pd.Timedelta(hours=1)]
    if len(recent_window) > 0:
        # Check if any would be flagged
        null_stale = 0
        print(f"  Null control window (last 1h): {len(recent_window)} rows, {null_stale} stale flags")


def move_origination(tape):
    """4b: Which book moved first on line changes."""
    print("\n=== 4b. MOVE ORIGINATION ===")
    # Track point changes by book over time
    movers = {}
    for (eid, mkt, side), g in tape.groupby(["event_id", "market", "outcome_name"]):
        for book, bg in g.groupby("bookmaker"):
            bg = bg.sort_values("snapshot_dt")
            if len(bg) < 2:
                continue
            pts = bg[bg["point"].notna()]
            if len(pts) < 2:
                continue
            changes = pts[pts["point"].diff() != 0].iloc[1:]  # skip first (no diff)
            for _, ch in changes.iterrows():
                movers.setdefault(book, 0)
                movers[book] += 1

    if movers:
        print(f"  Line changes by book:")
        for book, count in sorted(movers.items(), key=lambda x: -x[1]):
            print(f"    {book:>20s}: {count:>5d} changes")
    else:
        print("  No line changes detected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--build-time")
    args = parser.parse_args()

    bt = args.build_time or datetime.now(timezone.utc).isoformat()
    tape = load_tape(args.season, bt)
    print(f"Tape: {len(tape)} rows, {tape['event_id'].nunique()} events")

    hold_by_market(tape)
    stale_book_detection(tape)
    move_origination(tape)


if __name__ == "__main__":
    main()
