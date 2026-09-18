#!/usr/bin/env python3
"""
N04: Grade NCAAF tickets — CLV from the last pre-kick snapshot.

Closing price = last snapshot STRICTLY BEFORE commence_time.
CLV on no-vig scale, game identity required, push = void (D64 convention).
UPDATE-ONLY: never append a row, never re-grade a row already marked graded.
"""

import json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

TAPE_DIR = ROOT / "data" / "odds_archive" / "ncaaf" / "line_history"
TICKET_LOG = ROOT / "ncaaf" / "logs" / "ncaaf_board_tickets_2026.json"


def american_to_implied(odds):
    if odds is None or (isinstance(odds, float) and np.isnan(odds)):
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def _load_closing_prices(season):
    """Load the last pre-kick snapshot per (event_id, market, outcome_name, bookmaker)."""
    tape_path = TAPE_DIR / f"season={season}"
    if not tape_path.exists():
        return pd.DataFrame()

    frames = []
    for f in sorted(tape_path.glob("*.parquet")):
        frames.append(pd.read_parquet(f))
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["snapshot_dt"] = pd.to_datetime(df["snapshot_utc"], utc=True, errors="coerce")
    df["commence_dt"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")

    # Pre-kick only
    pre = df[df["snapshot_dt"] < df["commence_dt"]]
    # Latest per (event_id, bookmaker, market, outcome_name)
    close = (pre.sort_values("snapshot_dt", ascending=False)
             .drop_duplicates(["event_id", "bookmaker", "market", "outcome_name"],
                              keep="first"))
    return close


def grade_tickets(season=2026):
    """Grade ungraded tickets. Returns count of rows changed."""
    if not TICKET_LOG.exists():
        return 0

    with open(TICKET_LOG) as f:
        tickets = json.load(f)

    close = _load_closing_prices(season)
    if close.empty:
        print("No closing prices available")
        return 0

    changed = 0
    for ticket in tickets:
        if ticket.get("graded"):
            continue  # UPDATE-ONLY: never re-grade

        eid = ticket["event_id"]
        for leg in ticket.get("legs", []):
            market = leg["market"]
            side = leg["side"]
            book = leg.get("book", "")

            # Match on game identity (event_id)
            match = close[
                (close["event_id"] == eid)
                & (close["market"] == market)
                & (close["outcome_name"] == side)
                & (close["bookmaker"] == book)
            ]

            if match.empty:
                # Try any book for this event/market/side
                match = close[
                    (close["event_id"] == eid)
                    & (close["market"] == market)
                    & (close["outcome_name"] == side)
                ]

            if match.empty:
                leg["close_price"] = None
                leg["clv"] = None
                continue

            cr = match.iloc[0]
            close_price = cr["price"]
            leg["close_price"] = float(close_price) if pd.notna(close_price) else None

            # CLV on no-vig scale
            pick_imp = american_to_implied(leg.get("price"))
            close_imp = american_to_implied(close_price)

            if pd.notna(pick_imp) and pd.notna(close_imp):
                # Devig: need both sides. Find the complement.
                comp_side = close[
                    (close["event_id"] == eid)
                    & (close["market"] == market)
                    & (close["outcome_name"] != side)
                    & (close["bookmaker"] == cr["bookmaker"])
                ]
                if not comp_side.empty:
                    comp_imp = american_to_implied(comp_side.iloc[0]["price"])
                    if pd.notna(comp_imp):
                        close_total = close_imp + comp_imp
                        close_devig = close_imp / close_total
                        pick_devig = pick_imp / (pick_imp + comp_imp)  # approx
                        leg["clv"] = round(float(close_devig - pick_devig), 4)
                    else:
                        leg["clv"] = None
                else:
                    leg["clv"] = None
            else:
                leg["clv"] = None

        ticket["graded"] = True
        changed += 1

    with open(TICKET_LOG, "w") as f:
        json.dump(tickets, f, indent=2)

    return changed


def report(season=2026):
    """Print CLV breakdown."""
    if not TICKET_LOG.exists():
        return

    with open(TICKET_LOG) as f:
        tickets = json.load(f)

    graded = [t for t in tickets if t.get("graded")]
    if not graded:
        print("No graded tickets")
        return

    # Flatten legs
    legs = []
    for t in graded:
        for leg in t.get("legs", []):
            leg["event_id"] = t["event_id"]
            leg["home_team"] = t["home_team"]
            leg["away_team"] = t["away_team"]
            leg["reference_only"] = t.get("reference_only", True)
            legs.append(leg)

    df = pd.DataFrame(legs)
    valid = df[df["clv"].notna()]

    print(f"\nCLV Report: {len(valid)}/{len(df)} legs with CLV")
    if valid.empty:
        return

    # By market
    print("\n| Market | N | Mean CLV |")
    print("|--------|---|----------|")
    for mkt in sorted(valid["market"].unique()):
        g = valid[valid["market"] == mkt]
        print(f"| {mkt:10s} | {len(g):3d} | {g['clv'].mean():+.4f} |")

    print(f"\nOverall: {valid['clv'].mean():+.4f} (N={len(valid)})")
    print(f"REFERENCE_ONLY: {valid['reference_only'].all()}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    if not args.report_only:
        changed = grade_tickets(args.season)
        print(f"Graded: {changed} tickets changed")

    report(args.season)


if __name__ == "__main__":
    main()
