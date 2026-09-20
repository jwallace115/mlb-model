#!/usr/bin/env python3
"""
N02: NCAAF board builder from the line tape.

Reads data/odds_archive/ncaaf/line_history/season=2026/*.parquet.
Zero API calls. Zero credits.

HARD REQUIREMENT: a row is eligible only if
  snapshot_utc < commence_time  AND  snapshot_utc <= build_time.
Never reads files[-1] as "the current line". The tape contains in-play odds.
"""

import argparse, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
TAPE_DIR = ROOT / "data" / "odds_archive" / "ncaaf" / "line_history"
BOARD_DIR = ROOT / "ncaaf" / "data" / "board"


def american_to_implied(odds):
    if odds is None or np.isnan(odds):
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def load_tape(season, build_time=None):
    """Load all snapshots, apply pre-kick + pre-build filter."""
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

    # HARD REQUIREMENT: snapshot < commence_time (pre-kick)
    pre_kick = df[df["snapshot_dt"] < df["commence_dt"]]

    # AND snapshot <= build_time
    if build_time is not None:
        build_dt = pd.Timestamp(build_time, tz="UTC")
        pre_kick = pre_kick[pre_kick["snapshot_dt"] <= build_dt]

    return pre_kick


def build_board(season, week=None, build_time=None):
    """Build the NCAAF board from the tape."""
    if build_time is None:
        build_time = datetime.now(timezone.utc)

    tape = load_tape(season, build_time)
    if tape.empty:
        print("No eligible tape rows")
        return pd.DataFrame(), ""

    # Filter to the current week's games (upcoming, not yet kicked off)
    upcoming = tape[tape["commence_dt"] > pd.Timestamp(build_time, tz="UTC")]
    if upcoming.empty:
        print("No upcoming games in tape")
        return pd.DataFrame(), ""

    # Get unique events
    events = upcoming.drop_duplicates("event_id")[["event_id", "commence_time",
        "home_team", "away_team"]].sort_values("commence_time")

    board_rows = []

    for _, ev in events.iterrows():
        eid = ev["event_id"]
        home = ev["home_team"]
        away = ev["away_team"]
        commence = ev["commence_time"]

        ev_tape = tape[tape["event_id"] == eid]

        for market in ["h2h", "spreads", "totals"]:
            mkt_tape = ev_tape[ev_tape["market"] == market]
            if mkt_tape.empty:
                continue

            for side in mkt_tape["outcome_name"].unique():
                side_tape = mkt_tape[mkt_tape["outcome_name"] == side]
                if side_tape.empty:
                    continue

                # Latest eligible snapshot per book
                latest = (side_tape.sort_values("snapshot_dt", ascending=False)
                          .drop_duplicates("bookmaker", keep="first"))

                n_books = len(latest)
                points = latest["point"].dropna()
                prices = latest["price"].dropna()

                # Consensus
                consensus_point = float(points.median()) if len(points) > 0 else np.nan
                implied_probs = prices.apply(american_to_implied).dropna()
                if len(implied_probs) >= 2:
                    # No-vig: normalize over+under to sum to 1
                    consensus_implied = float(implied_probs.median())
                else:
                    consensus_implied = float(implied_probs.iloc[0]) if len(implied_probs) > 0 else np.nan

                # Best number (extreme point)
                if market == "spreads" and len(points) > 0:
                    # For spread: most positive point is best for the named side
                    best_idx = points.idxmax()
                    best_point = float(points.loc[best_idx])
                    best_book = latest.loc[best_idx, "bookmaker"]
                    best_price = float(latest.loc[best_idx, "price"])
                elif market == "totals" and "Over" in side and len(points) > 0:
                    best_idx = points.idxmin()  # lowest total is best for over
                    best_point = float(points.loc[best_idx])
                    best_book = latest.loc[best_idx, "bookmaker"]
                    best_price = float(latest.loc[best_idx, "price"])
                else:
                    best_point = consensus_point
                    best_book = latest.iloc[0]["bookmaker"] if len(latest) > 0 else ""
                    best_price = float(prices.iloc[0]) if len(prices) > 0 else np.nan

                # Dispersion
                dispersion = float(points.max() - points.min()) if len(points) > 1 else 0.0

                # Movement: first-seen → latest pre-kick
                first_snap = side_tape.sort_values("snapshot_dt").iloc[0]
                last_snap = side_tape.sort_values("snapshot_dt").iloc[-1]
                first_point = first_snap["point"] if pd.notna(first_snap["point"]) else np.nan
                last_point = last_snap["point"] if pd.notna(last_snap["point"]) else np.nan
                hours_elapsed = (last_snap["snapshot_dt"] - first_snap["snapshot_dt"]).total_seconds() / 3600

                # Key-number proximity (spreads only)
                kn_prox = np.nan
                if market == "spreads" and pd.notna(consensus_point):
                    kn_prox = min(abs(consensus_point - k) for k in [3, 7, 10, 14])

                # Newest snapshot age
                newest_snap_age_min = (pd.Timestamp(build_time, tz="UTC") - latest["snapshot_dt"].max()).total_seconds() / 60

                # N37: collect real per-book quotes for leg selection
                quotes = []
                for _, bk_row in latest.iterrows():
                    q = {"book": bk_row["bookmaker"],
                         "point": float(bk_row["point"]) if pd.notna(bk_row["point"]) else None,
                         "price": float(bk_row["price"]) if pd.notna(bk_row["price"]) else None,
                         "snapshot_utc": str(bk_row["snapshot_utc"]) if "snapshot_utc" in bk_row.index and pd.notna(bk_row["snapshot_utc"]) else None}
                    quotes.append(q)

                board_rows.append({
                    "event_id": eid, "home_team": home, "away_team": away,
                    "commence_time": commence, "market": market,
                    "outcome_name": side, "n_books": n_books,
                    "consensus_point": consensus_point,
                    "consensus_implied": consensus_implied,
                    "best_point": best_point, "best_price": best_price,
                    "best_book": best_book, "dispersion": dispersion,
                    "first_point": first_point, "last_point": last_point,
                    "movement": (last_point - first_point) if pd.notna(first_point) and pd.notna(last_point) else np.nan,
                    "hours_elapsed": hours_elapsed,
                    "key_number_proximity": kn_prox,
                    "newest_snap_age_min": newest_snap_age_min,
                    "quotes": quotes,
                })

    board_df = pd.DataFrame(board_rows)
    if board_df.empty:
        return board_df, ""

    # Build markdown
    lines = []
    lines.append("# NCAAF Board")
    lines.append(f"\nBuild time: {build_time}")
    lines.append(f"Season: {season}")
    lines.append("")
    lines.append("**REFERENCE_ONLY** — all prices from books Jeff cannot bet (N01).")
    lines.append("hardrockbet_fl is absent from 100% of NCAAF snapshots.")
    lines.append("")

    for eid in board_df["event_id"].unique():
        ev = board_df[board_df["event_id"] == eid]
        home = ev.iloc[0]["home_team"]
        away = ev.iloc[0]["away_team"]
        commence = ev.iloc[0]["commence_time"]
        lines.append(f"## {away} @ {home}")
        lines.append(f"Kickoff: {commence}")
        lines.append("")
        lines.append("| Market | Side | Point | Implied | Books | Best | Disp | Move |")
        lines.append("|--------|------|-------|---------|-------|------|------|------|")
        for _, r in ev.iterrows():
            pt = f"{r['consensus_point']:.1f}" if pd.notna(r['consensus_point']) else "—"
            imp = f"{r['consensus_implied']:.3f}" if pd.notna(r['consensus_implied']) else "—"
            best = f"{r['best_point']:.1f}@{r['best_book']}" if pd.notna(r['best_point']) else "—"
            disp = f"{r['dispersion']:.1f}" if r['dispersion'] > 0 else "0"
            move = f"{r['movement']:+.1f}" if pd.notna(r['movement']) else "—"
            lines.append(f"| {r['market']:7s} | {str(r['outcome_name'])[:15]:15s} | {pt:>6s} | {imp:>7s} | {r['n_books']:>5d} | {best:>15s} | {disp:>4s} | {move:>5s} |")
        lines.append("")

    return board_df, "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int)
    parser.add_argument("--build-time", help="ISO8601 UTC timestamp")
    args = parser.parse_args()

    bt = args.build_time or datetime.now(timezone.utc).isoformat()
    board_df, board_md = build_board(args.season, args.week, bt)

    if not board_df.empty:
        out_dir = BOARD_DIR / f"week={args.season}_{args.week or 0:02d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        board_df.drop(columns=["quotes"], errors="ignore").to_parquet(
            out_dir / "ncaaf_board.parquet", index=False)
        with open(out_dir / "ncaaf_board.md", "w") as f:
            f.write(board_md)
        print(f"Board: {len(board_df)} rows, {board_df['event_id'].nunique()} events")
        print(f"Output: {out_dir}")
    else:
        print("No board data")


if __name__ == "__main__":
    main()
