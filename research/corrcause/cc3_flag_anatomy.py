#!/usr/bin/env python3
"""
CC-3 Item 1: Anatomy of the NHL f1 divergence flag.

For every NHL DEV game with a Pinnacle close, compute:
  (a) Pinnacle's last pre-tip snapshot time and book_last_update age
  (b) Each soft book's last pre-tip snapshot, book_last_update age, whether it quoted
      in the SAME snapshot as Pinnacle's last
  (c) Driving book of the v2 flag, sign, gap in minutes vs Pinnacle's close snapshot
  (d) SYNCHRONOUS re-flag: max |soft_fair_h - pin_fair_h| >= 0.02 over soft books
      quoting in Pinnacle's own last snapshot with book_last_update age <= 10 min
  (e) Pinnacle's ML move in last 3h (prob pts) and total-line move in last 3h

Outputs:
  results/cc3/flag_anatomy.parquet
  results/cc3/flag_anatomy.md
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results" / "cc3"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

SOFT_BOOKS = [
    "draftkings", "fanduel", "betmgm", "williamhill_us",
    "betrivers", "bovada", "pointsbetus", "unibet_us", "betonlineag"
]

SEASONS = [2022, 2023]


def american_to_implied(price):
    if pd.isna(price):
        return np.nan
    if price >= 100:
        return 100.0 / (price + 100.0)
    elif price <= -100:
        return abs(price) / (abs(price) + 100.0)
    return np.nan


def devig_fair_h(ml_h, ml_a):
    imp_h = american_to_implied(ml_h)
    imp_a = american_to_implied(ml_a)
    if pd.isna(imp_h) or pd.isna(imp_a) or (imp_h + imp_a) == 0:
        return np.nan
    return imp_h / (imp_h + imp_a)


def load_pretip_tape(seasons):
    """Load all NHL in-play tape files, filter to pre-tip rows."""
    frames = []
    for s in seasons:
        path = Path.home() / f"mlb-model-nhlE/data/odds_archive/nhl/history/inplay/season={s}"
        files = sorted(path.glob("*.parquet"))
        print(f"  season={s}: {len(files)} files")
        frames.extend(pd.read_parquet(f) for f in files)
    tape = pd.concat(frames, ignore_index=True)
    tape["snap"] = pd.to_datetime(tape["snapshot_utc"])
    tape["ct"] = pd.to_datetime(tape["commence_time"])
    tape["blu"] = pd.to_datetime(tape["book_last_update"])
    tape = tape[tape["snap"] < tape["ct"]].copy()
    # book_last_update age at snapshot time (minutes)
    tape["blu_age_min"] = (tape["snap"] - tape["blu"]).dt.total_seconds() / 60.0
    return tape


def main():
    t0 = time.time()
    print("=== CC-3 Item 1: Flag Anatomy ===")

    # Load tape
    print("Loading in-play tape...")
    tape = load_pretip_tape(SEASONS)
    print(f"  Pre-tip rows: {len(tape):,}")

    # Load games table for event list + outcomes
    games = pd.read_parquet(DATA_DIR / "games_nhl.parquet")
    games["ct"] = pd.to_datetime(games["commence_time"])
    event_ids = set(games["event_id"])
    tape = tape[tape["event_id"].isin(event_ids)].copy()
    print(f"  Tape rows for DEV events: {len(tape):,}")

    # Load existing market features for v2 flag comparison
    mf = pd.read_parquet(DATA_DIR / "market_features_nhl.parquet")

    # === Per-event analysis ===
    print("Analyzing per-event...")
    rows = []
    unique_snaps = tape.groupby("event_id")["snap"].apply(set).to_dict()

    for _, g in games.iterrows():
        eid = g["event_id"]
        ct = g["ct"]
        row = {"event_id": eid, "season": g["season"], "commence_time": ct}

        etape = tape[tape["event_id"] == eid]
        if len(etape) == 0:
            rows.append(row)
            continue

        home = g["home_team"]

        # === (a) Pinnacle's last pre-tip snapshot ===
        pin = etape[etape["bookmaker"] == "pinnacle"]
        pin_h2h = pin[pin["market"] == "h2h"]
        if len(pin_h2h) == 0:
            rows.append(row)
            continue

        pin_last_snap = pin_h2h["snap"].max()
        row["pin_last_snap"] = pin_last_snap
        row["pin_close_age_min"] = (ct - pin_last_snap).total_seconds() / 60.0

        # Pinnacle's book_last_update age at its last snapshot
        pin_at_last = pin_h2h[pin_h2h["snap"] == pin_last_snap]
        if len(pin_at_last) > 0:
            row["pin_blu_age_min"] = pin_at_last["blu_age_min"].iloc[0]

        # Pinnacle's de-vigged fair_h at close
        pin_h = pin_at_last[pin_at_last["outcome_name"] == home]
        pin_a = pin_at_last[pin_at_last["outcome_name"] != home]
        pin_fair_h = np.nan
        if len(pin_h) > 0 and len(pin_a) > 0:
            pin_fair_h = devig_fair_h(pin_h["price"].iloc[0], pin_a["price"].iloc[0])
        row["pin_close_fair_h"] = pin_fair_h

        # === (b) Each soft book's last pre-tip snapshot ===
        soft_data = {}
        for book in SOFT_BOOKS:
            bk = etape[(etape["bookmaker"] == book) & (etape["market"] == "h2h")]
            if len(bk) == 0:
                continue
            bk_last_snap = bk["snap"].max()
            bk_at_last = bk[bk["snap"] == bk_last_snap]
            blu_age = bk_at_last["blu_age_min"].iloc[0] if len(bk_at_last) > 0 else np.nan

            # Did this book quote in Pinnacle's last snapshot?
            in_pin_snap = (bk["snap"] == pin_last_snap).any()

            # De-vig fair_h at book's own last snapshot
            bk_h = bk_at_last[bk_at_last["outcome_name"] == home]
            bk_a = bk_at_last[bk_at_last["outcome_name"] != home]
            bk_fair_h = np.nan
            if len(bk_h) > 0 and len(bk_a) > 0:
                bk_fair_h = devig_fair_h(bk_h["price"].iloc[0], bk_a["price"].iloc[0])

            # Fair_h from Pinnacle's snapshot (if the book was in it)
            bk_sync_fair_h = np.nan
            bk_sync_blu_age = np.nan
            if in_pin_snap:
                bk_in_pin = bk[bk["snap"] == pin_last_snap]
                bk_in_pin_h = bk_in_pin[bk_in_pin["outcome_name"] == home]
                bk_in_pin_a = bk_in_pin[bk_in_pin["outcome_name"] != home]
                if len(bk_in_pin_h) > 0 and len(bk_in_pin_a) > 0:
                    bk_sync_fair_h = devig_fair_h(
                        bk_in_pin_h["price"].iloc[0], bk_in_pin_a["price"].iloc[0]
                    )
                    bk_sync_blu_age = bk_in_pin_h["blu_age_min"].iloc[0]

            soft_data[book] = {
                "last_snap": bk_last_snap,
                "blu_age": blu_age,
                "in_pin_snap": in_pin_snap,
                "fair_h": bk_fair_h,
                "sync_fair_h": bk_sync_fair_h,
                "sync_blu_age": bk_sync_blu_age,
                "gap_min": (bk_last_snap - pin_last_snap).total_seconds() / 60.0,
            }

        row["n_soft_books_quoting"] = len(soft_data)
        row["n_soft_in_pin_snap"] = sum(1 for v in soft_data.values() if v["in_pin_snap"])
        row["n_soft_sync_fresh"] = sum(
            1 for v in soft_data.values()
            if v["in_pin_snap"] and not pd.isna(v["sync_blu_age"]) and v["sync_blu_age"] <= 10
        )

        # === (c) Driving book of the v2 flag ===
        if not pd.isna(pin_fair_h) and soft_data:
            max_div = 0.0
            driving_book = None
            driving_sign = 0
            driving_gap_min = np.nan
            driving_blu_age = np.nan
            for book, sd in soft_data.items():
                if pd.isna(sd["fair_h"]):
                    continue
                div = sd["fair_h"] - pin_fair_h
                if abs(div) > abs(max_div):
                    max_div = div
                    driving_book = book
                    driving_sign = 1 if div > 0 else -1
                    driving_gap_min = abs(sd["gap_min"])
                    driving_blu_age = sd["blu_age"]

            row["v2_max_div"] = max_div
            row["v2_max_div_abs"] = abs(max_div)
            row["v2_flag"] = 1 if abs(max_div) >= 0.02 else 0
            row["driving_book"] = driving_book
            row["driving_sign"] = driving_sign  # +1 = soft higher on home, -1 = soft lower
            row["driving_gap_min"] = driving_gap_min
            row["driving_blu_age"] = driving_blu_age

        # === (d) SYNCHRONOUS re-flag ===
        # max |soft_fair_h - pin_fair_h| >= 0.02 over soft books quoting in Pinnacle's
        # own last snapshot with book_last_update age <= 10 min
        sync_max_div = 0.0
        sync_driving_book = None
        n_sync_books_used = 0
        if not pd.isna(pin_fair_h):
            for book, sd in soft_data.items():
                if not sd["in_pin_snap"]:
                    continue
                if pd.isna(sd["sync_blu_age"]) or sd["sync_blu_age"] > 10:
                    continue
                if pd.isna(sd["sync_fair_h"]):
                    continue
                n_sync_books_used += 1
                div = sd["sync_fair_h"] - pin_fair_h
                if abs(div) > abs(sync_max_div):
                    sync_max_div = div
                    sync_driving_book = book

        row["n_sync_books_used"] = n_sync_books_used
        row["sync_max_div"] = sync_max_div
        row["sync_max_div_abs"] = abs(sync_max_div)
        row["sync_flag"] = 1 if abs(sync_max_div) >= 0.02 else 0
        row["sync_driving_book"] = sync_driving_book

        # === (e) Pinnacle ML move last 3h and total move last 3h ===
        pin_ml_home = pin_h2h[pin_h2h["outcome_name"] == home].sort_values("snap")
        if len(pin_ml_home) > 0:
            pin_ml_home = pin_ml_home.copy()
            pin_ml_home["imp"] = pin_ml_home["price"].apply(american_to_implied)
            pin_ml_home["hours_before"] = (ct - pin_ml_home["snap"]).dt.total_seconds() / 3600.0
            close_imp = pin_ml_home.iloc[-1]["imp"]
            # 3h-ago value
            before_3h = pin_ml_home[pin_ml_home["hours_before"] > 3]
            if len(before_3h) > 0:
                snap_3h_imp = before_3h.iloc[-1]["imp"]
            else:
                snap_3h_imp = pin_ml_home.iloc[0]["imp"]
            row["pin_ml_move_3h"] = close_imp - snap_3h_imp

        # Total line move last 3h
        pin_tot = pin[(pin["market"] == "totals") & (pin["outcome_name"] == "Over")].sort_values("snap")
        if len(pin_tot) > 0:
            pin_tot = pin_tot.copy()
            pin_tot["hours_before"] = (ct - pin_tot["snap"]).dt.total_seconds() / 3600.0
            close_total = pin_tot.iloc[-1]["point"]
            before_3h_tot = pin_tot[pin_tot["hours_before"] > 3]
            if len(before_3h_tot) > 0:
                snap_3h_total = before_3h_tot.iloc[-1]["point"]
            else:
                snap_3h_total = pin_tot.iloc[0]["point"]
            row["pin_total_move_3h"] = close_total - snap_3h_total

        # Store per-book close snap and blu_age for driving book analysis
        for book, sd in soft_data.items():
            row[f"soft_{book}_gap_min"] = sd["gap_min"]
            row[f"soft_{book}_blu_age"] = sd["blu_age"]
            row[f"soft_{book}_in_pin_snap"] = 1 if sd["in_pin_snap"] else 0

        rows.append(row)

    df = pd.DataFrame(rows)
    print(f"  Built {len(df)} rows ({time.time()-t0:.0f}s)")

    # Merge v2 flag from existing market features for comparison
    mf_sub = mf[["event_id", "f1_max_div_abs"]].copy()
    mf_sub["v2_flag_original"] = (mf_sub["f1_max_div_abs"].notna()).astype(int)
    df = df.merge(mf_sub[["event_id", "v2_flag_original"]], on="event_id", how="left")
    df["v2_flag_original"] = df["v2_flag_original"].fillna(0).astype(int)

    # === Null control: sync re-flag vs v2 flag on games where ALL books quote in same snapshot ===
    all_sync = df[df["n_soft_in_pin_snap"] == df["n_soft_books_quoting"]]
    all_sync = all_sync[all_sync["n_soft_books_quoting"] >= 3]  # meaningful comparison
    if len(all_sync) > 0:
        agree = (all_sync["sync_flag"] == all_sync["v2_flag"]).mean()
        print(f"\n  NULL CONTROL: {len(all_sync)} games where ALL books in same snapshot")
        print(f"  sync_flag agrees with v2_flag: {agree:.3f} ({agree*100:.1f}%)")
        if agree < 0.90:
            print("  *** STOP: agreement < 90% — v2 feature is not what it says ***")
            sys.exit(1)
    else:
        print("\n  WARNING: No games found where ALL soft books quote in same snapshot")

    # Save parquet
    out = RESULTS_DIR / "flag_anatomy.parquet"
    df.to_parquet(out, index=False)
    print(f"  Wrote {out}")

    # === Build report ===
    print("\n=== Building report ===")
    lines = []
    lines.append("# CC-3 Item 1: Flag Anatomy\n")
    lines.append(f"Total games: {len(df)}\n")

    # Games with Pinnacle close
    has_pin = df["pin_last_snap"].notna()
    lines.append(f"Games with Pinnacle close: {has_pin.sum()}\n")

    # v2 flag distribution
    has_v2 = df["v2_flag"] == 1
    lines.append(f"v2 flag=yes: {has_v2.sum()}, flag=no: {(~has_v2 & has_pin).sum()}\n")

    # Sync flag distribution
    has_sync = df["sync_flag"] == 1
    n_sync_eligible = (df["n_sync_books_used"] > 0).sum()
    lines.append(f"Sync-eligible games (≥1 book in Pinnacle snap with blu≤10m): {n_sync_eligible}")
    lines.append(f"Sync flag=yes: {has_sync.sum()}, sync flag=no: {(~has_sync & (df['n_sync_books_used'] > 0)).sum()}\n")

    # === (c) gaps: flagged vs unflagged ===
    lines.append("## Driving-book gap (flagged games)\n")
    flagged = df[has_v2 & df["driving_gap_min"].notna()]
    unflagged = df[~has_v2 & has_pin]

    lines.append(f"| Metric | Flagged (n={len(flagged)}) | Unflagged (n={len(unflagged)}) |")
    lines.append("|---|---|---|")

    for label, subset in [("Flagged", flagged), ("Unflagged", unflagged)]:
        pass  # will do table below

    if len(flagged) > 0:
        gap = flagged["driving_gap_min"]
        lines.append(f"| Driving-book gap median | {gap.median():.1f} min | — |")
        lines.append(f"| Driving-book gap p90 | {gap.quantile(0.9):.1f} min | — |")
        lines.append(f"| Share gap > 60 min | {(gap > 60).mean():.3f} | — |")
        lines.append(f"| Driving-book blu age median | {flagged['driving_blu_age'].median():.1f} min | — |")
        lines.append(f"| Share driving-book blu > 30 min | {(flagged['driving_blu_age'] > 30).mean():.3f} | — |")

    lines.append("")

    # Pinnacle close age comparison
    lines.append("## Pinnacle close age\n")
    lines.append(f"| Metric | Flagged (n={len(flagged)}) | Unflagged (n={len(unflagged)}) |")
    lines.append("|---|---|---|")
    for label, subset in [("Flagged", flagged), ("Unflagged", unflagged)]:
        age = subset["pin_close_age_min"]
        lines.append(f"| {label} pin close age median | {age.median():.1f} min | |")
    lines.append("")

    # Driving book counts
    lines.append("## Driving book distribution (flagged games)\n")
    if len(flagged) > 0:
        bc = flagged["driving_book"].value_counts()
        lines.append("| Book | Count | Share |")
        lines.append("|---|---|---|")
        for book in bc.index:
            lines.append(f"| {book} | {bc[book]} | {bc[book]/len(flagged):.3f} |")
    lines.append("")

    # Sign split
    lines.append("## Sign of divergence (flagged games)\n")
    if len(flagged) > 0:
        pos = (flagged["driving_sign"] == 1).sum()
        neg = (flagged["driving_sign"] == -1).sum()
        lines.append(f"Soft higher on home: {pos} ({pos/len(flagged):.3f})")
        lines.append(f"Soft lower on home: {neg} ({neg/len(flagged):.3f})\n")

    # Sync vs v2 comparison on all-in-same-snapshot games
    lines.append("## Null control: sync flag vs v2 flag (all books in same snapshot)\n")
    if len(all_sync) > 0:
        lines.append(f"Games where ALL soft books quote in Pinnacle's last snapshot (n≥3 books): {len(all_sync)}")
        lines.append(f"Agreement: {agree:.3f} ({agree*100:.1f}%)")
        # Cross-tab
        ct = pd.crosstab(all_sync["v2_flag"], all_sync["sync_flag"], margins=True)
        lines.append(f"\n```\n{ct.to_string()}\n```\n")
    else:
        lines.append("No games found.\n")

    # Summary stats
    lines.append("## Summary statistics\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total games | {len(df)} |")
    lines.append(f"| With Pinnacle close | {has_pin.sum()} |")
    lines.append(f"| v2 flagged | {has_v2.sum()} ({has_v2.mean():.3f}) |")
    lines.append(f"| Sync-eligible | {n_sync_eligible} |")
    lines.append(f"| Sync flagged | {has_sync.sum()} ({has_sync.mean():.3f}) |")
    lines.append(f"| v2 flagged AND sync flagged | {((has_v2) & (has_sync)).sum()} |")
    lines.append(f"| v2 flagged BUT NOT sync flagged | {((has_v2) & (~has_sync)).sum()} |")
    lines.append(f"| NOT v2 flagged BUT sync flagged | {((~has_v2) & (has_sync)).sum()} |")

    report_path = RESULTS_DIR / "flag_anatomy.md"
    report_path.write_text("\n".join(lines))
    print(f"  Wrote {report_path}")
    print(f"  Done ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
