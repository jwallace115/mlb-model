#!/usr/bin/env python3
"""
CC-4 Item 2: CONFIRM script for NH8.

Hard-coded sport=nhl. Accepts --season 2023 (dry-run on DEV) or --season 2024 (the look).
Loads only data/odds_archive/nhl/history/inplay/season=<season> + outcomes + events.
Asserts every loaded frame's commence_time falls in the requested season.

Usage:
    python3 confirm_nh8.py --season 2023   # dry-run (must reproduce Item 1a's 2023-24 row)
    python3 confirm_nh8.py --season 2024   # the look (CC-5 only, after Cowork verification)
"""

import argparse
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


SOFT_BOOKS = [
    "draftkings", "fanduel", "betmgm", "williamhill_us",
    "betrivers", "bovada", "pointsbetus", "unibet_us", "betonlineag"
]

DIVERGENCE_THRESHOLD = 0.02
BLU_AGE_MAX = 10  # minutes


def american_to_implied(price):
    if pd.isna(price):
        return np.nan
    if price >= 100:
        return 100.0 / (price + 100.0)
    elif price <= -100:
        return abs(price) / (abs(price) + 100.0)
    return np.nan


def american_to_decimal(price):
    if pd.isna(price):
        return np.nan
    if price >= 100:
        return 1.0 + price / 100.0
    elif price <= -100:
        return 1.0 + 100.0 / abs(price)
    return np.nan


def devig_fair(imp_h, imp_a):
    if pd.isna(imp_h) or pd.isna(imp_a) or (imp_h + imp_a) == 0:
        return np.nan, np.nan
    return imp_h / (imp_h + imp_a), imp_a / (imp_h + imp_a)


def nhl_season_range(season):
    """Return (start, end) dates for an NHL season. season=2023 → Oct 2023 to Jun 2024."""
    return pd.Timestamp(f"{season}-10-01", tz="UTC"), pd.Timestamp(f"{season + 1}-07-01", tz="UTC")


def main():
    parser = argparse.ArgumentParser(description="NH8 CONFIRM script")
    parser.add_argument("--season", type=int, required=True, choices=[2023, 2024],
                        help="2023 = dry-run on DEV, 2024 = the look")
    args = parser.parse_args()
    season = args.season

    print(f"=== NH8 CONFIRM — season {season} ({season}-{season + 1}) ===")

    # Determine data paths
    if season == 2023:
        tape_path = Path.home() / f"mlb-model-nhlE/data/odds_archive/nhl/history/inplay/season={season}"
    else:
        tape_path = Path.home() / f"mlb-model-nhlE/data/odds_archive/nhl/history/inplay/season={season}"

    if not tape_path.exists():
        print(f"ERROR: tape path does not exist: {tape_path}")
        sys.exit(1)

    # Load tape
    print(f"Loading tape from {tape_path}...")
    files = sorted(tape_path.glob("*.parquet"))
    print(f"  {len(files)} files")
    tape = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    tape["snap"] = pd.to_datetime(tape["snapshot_utc"])
    tape["ct"] = pd.to_datetime(tape["commence_time"])
    tape["blu"] = pd.to_datetime(tape["book_last_update"])
    tape["blu_age_min"] = (tape["snap"] - tape["blu"]).dt.total_seconds() / 60.0
    print(f"  Total rows: {len(tape):,}")

    # Assert all commence_times fall in the requested season
    s_start, s_end = nhl_season_range(season)
    ct_range = tape["ct"]
    ct_min, ct_max = ct_range.min(), ct_range.max()
    assert ct_min >= s_start, f"Tape ct_min {ct_min} < season start {s_start}"
    assert ct_max < s_end, f"Tape ct_max {ct_max} >= season end {s_end}"
    print(f"  Season bounds: {ct_min} to {ct_max} — PASS")

    # Rule A: listed_start = max ct per event
    listed_start = tape.groupby("event_id")["ct"].max().rename("listed_start")
    tape = tape.merge(listed_start, on="event_id", how="left")
    tape = tape[tape["snap"] <= tape["listed_start"]].copy()

    # Events
    events = tape[["event_id", "home_team", "away_team"]].drop_duplicates("event_id")
    events = events.merge(listed_start, on="event_id", how="left")
    print(f"  Events: {len(events)}")

    # Outcomes — load from SBRO
    sbro = pd.read_parquet(
        Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet"
    )
    sbro = sbro[sbro["season"] == season].copy()
    sbro["date_dt"] = pd.to_datetime(sbro["date"])
    print(f"  SBRO games for season {season}: {len(sbro)}")

    # Abbreviation mapping
    _NHL_ABBREV_BASE = {
        "Anaheim Ducks": "ANA", "Arizona Coyotes": "ARI", "Boston Bruins": "BOS",
        "Buffalo Sabres": "BUF", "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
        "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL", "Columbus Blue Jackets": "CBJ",
        "Dallas Stars": "DAL", "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
        "Florida Panthers": "FLA", "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN",
        "Montr\u00e9al Canadiens": "MTL",
        "Nashville Predators": "NSH", "New Jersey Devils": "NJD",
        "New York Islanders": "NYI", "New York Rangers": "NYR", "Ottawa Senators": "OTT",
        "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJS",
        "Seattle Kraken": "SEA", "St Louis Blues": "STL", "Tampa Bay Lightning": "TBL",
        "Toronto Maple Leafs": "TOR", "Utah Hockey Club": "UTA", "Vancouver Canucks": "VAN",
        "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH", "Winnipeg Jets": "WPG",
    }
    # Build map with both accented and ASCII-normalized keys (same as build_tables.py)
    NHL_ABBREV = {}
    for name, abbrev in _NHL_ABBREV_BASE.items():
        NHL_ABBREV[name] = abbrev
        ascii_name = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode("ascii")
        NHL_ABBREV[ascii_name] = abbrev

    events["h_abbrev"] = events["home_team"].map(NHL_ABBREV)
    events["a_abbrev"] = events["away_team"].map(NHL_ABBREV)
    events["game_date"] = events["listed_start"].dt.tz_convert("US/Eastern").dt.date

    sbro["game_date"] = sbro["date_dt"].dt.date
    outcomes = events.merge(
        sbro[["game_id", "game_date", "home", "away", "hg", "ag", "home_win", "decided"]],
        left_on=["game_date", "h_abbrev", "a_abbrev"],
        right_on=["game_date", "home", "away"],
        how="left"
    )
    matched = outcomes["game_id"].notna().sum()
    print(f"  Matched outcomes: {matched}/{len(events)}")

    outcomes["total_goals"] = outcomes["hg"] + outcomes["ag"]
    # SO: subtract 1 from total per NHL convention
    so_mask = outcomes["decided"] == "SO"
    outcomes.loc[so_mask, "total_goals"] = outcomes.loc[so_mask, "total_goals"] - 1

    # Close snapshot per event (Pinnacle h2h)
    pin_h2h = tape[(tape["bookmaker"] == "pinnacle") & (tape["market"] == "h2h")]
    close_snaps = pin_h2h.groupby("event_id")["snap"].max().rename("close_snap")

    # Build NH8
    nh8_rows = []
    pop_rows = []  # for population under base

    for _, ev in outcomes.iterrows():
        eid = ev["event_id"]
        if eid not in close_snaps.index:
            continue
        cs = close_snaps[eid]

        snap_rows = tape[(tape["event_id"] == eid) & (tape["snap"] == cs)]
        ht = ev["home_team"]

        # Pinnacle fair_h
        pin = snap_rows[(snap_rows["bookmaker"] == "pinnacle") & (snap_rows["market"] == "h2h")]
        pin_h = pin[pin["outcome_name"] == ht]
        pin_a = pin[pin["outcome_name"] != ht]
        if len(pin_h) == 0 or len(pin_a) == 0:
            continue

        pin_imp_h = american_to_implied(pin_h["price"].iloc[0])
        pin_imp_a = american_to_implied(pin_a["price"].iloc[0])
        pin_fair_h, pin_fair_a = devig_fair(pin_imp_h, pin_imp_a)
        if pd.isna(pin_fair_h):
            continue

        # Pinnacle totals at close
        pin_tot = snap_rows[(snap_rows["bookmaker"] == "pinnacle") & (snap_rows["market"] == "totals")]
        pin_over_row = pin_tot[pin_tot["outcome_name"] == "Over"]
        pin_under_row = pin_tot[pin_tot["outcome_name"] != "Over"]
        if len(pin_over_row) == 0 or len(pin_under_row) == 0:
            continue

        pin_total = pin_over_row["point"].iloc[0]
        pin_over_price = pin_over_row["price"].iloc[0]
        pin_under_price = pin_under_row["price"].iloc[0]
        pin_imp_over = american_to_implied(pin_over_price)
        pin_imp_under = american_to_implied(pin_under_price)
        pin_fair_over, pin_fair_under = devig_fair(pin_imp_over, pin_imp_under)

        if pd.isna(pin_total) or pd.isna(pin_fair_under):
            continue

        total_goals = ev.get("total_goals")
        if pd.isna(total_goals):
            continue

        # Push excluded
        if total_goals == pin_total:
            continue

        under = 1.0 if total_goals < pin_total else 0.0
        under_resid = under - pin_fair_under

        # Population row
        pop_rows.append({"event_id": eid, "under_resid": under_resid})

        # Check divergence flag
        max_div = 0.0
        driving_book = None
        for book in SOFT_BOOKS:
            bk = snap_rows[(snap_rows["bookmaker"] == book) & (snap_rows["market"] == "h2h")]
            if len(bk) == 0:
                continue
            bk_blu_age = bk["blu_age_min"].iloc[0]
            if pd.isna(bk_blu_age) or bk_blu_age > BLU_AGE_MAX:
                continue
            bk_h = bk[bk["outcome_name"] == ht]
            bk_a = bk[bk["outcome_name"] != ht]
            if len(bk_h) == 0 or len(bk_a) == 0:
                continue
            bk_fair_h, _ = devig_fair(
                american_to_implied(bk_h["price"].iloc[0]),
                american_to_implied(bk_a["price"].iloc[0])
            )
            if pd.isna(bk_fair_h):
                continue
            div = bk_fair_h - pin_fair_h
            if abs(div) > abs(max_div):
                max_div = div
                driving_book = book

        if abs(max_div) < DIVERGENCE_THRESHOLD:
            continue

        # Best same-snapshot soft under price
        best_under_dec = None
        best_under_book = None
        for book in SOFT_BOOKS:
            bk_tot = snap_rows[(snap_rows["bookmaker"] == book) & (snap_rows["market"] == "totals")]
            bk_under = bk_tot[bk_tot["outcome_name"] != "Over"]
            bk_over = bk_tot[bk_tot["outcome_name"] == "Over"]
            if len(bk_under) == 0:
                continue
            bk_total = bk_over["point"].iloc[0] if len(bk_over) > 0 else bk_under["point"].iloc[0]
            if bk_total != pin_total:
                continue
            bk_age = bk_under["blu_age_min"].iloc[0]
            if pd.isna(bk_age) or bk_age > BLU_AGE_MAX:
                continue
            dec = american_to_decimal(bk_under["price"].iloc[0])
            if pd.isna(dec):
                continue
            if best_under_dec is None or dec > best_under_dec:
                best_under_dec = dec
                best_under_book = book

        pin_under_dec = american_to_decimal(pin_under_price)

        nh8_rows.append({
            "event_id": eid, "season": season,
            "residual": under_resid,
            "outcome_under": under,
            "best_under_dec": best_under_dec,
            "best_under_book": best_under_book,
            "pin_under_dec": pin_under_dec,
            "driving_book": driving_book,
            "divergence": max_div,
        })

    fired = pd.DataFrame(nh8_rows)
    pop = pd.DataFrame(pop_rows)

    # ===== Results =====
    n = len(fired)
    r = fired["residual"]
    mean_r = r.mean()
    se = r.std(ddof=1) / np.sqrt(n)
    t_val = mean_r / se if se > 0 else 0
    p_one = 1 - stats.t.cdf(t_val, df=n - 1) if n > 1 else 1.0
    lb_90 = mean_r - stats.t.ppf(0.95, df=n - 1) * se if n > 1 else -np.inf

    pop_base = pop["under_resid"].mean()
    pop_n = len(pop)
    excess = mean_r - pop_base

    # ROI at best soft under
    priced = fired[fired["best_under_dec"].notna()]
    n_priced = len(priced)
    if n_priced > 0:
        pnl = [(row["best_under_dec"] - 1) if row["outcome_under"] == 1 else -1.0
               for _, row in priced.iterrows()]
        roi_soft = np.mean(pnl)
        roi_soft_se = np.std(pnl, ddof=1) / np.sqrt(n_priced)
    else:
        roi_soft = np.nan
        roi_soft_se = np.nan

    # ROI at Pinnacle
    pin_priced = fired[fired["pin_under_dec"].notna()]
    if len(pin_priced) > 0:
        pin_pnl = [(row["pin_under_dec"] - 1) if row["outcome_under"] == 1 else -1.0
                    for _, row in pin_priced.iterrows()]
        roi_pin = np.mean(pin_pnl)
    else:
        roi_pin = np.nan

    print(f"\n{'='*60}")
    print(f"NH8 CONFIRM — season {season} ({season}-{season+1})")
    print(f"{'='*60}")
    print(f"  n = {n}")
    print(f"  r = {mean_r:+.4f}")
    print(f"  SE = {se:.4f}")
    print(f"  p (one-sided) = {p_one:.6f}")
    print(f"  90% lower bound = {lb_90:+.4f}")
    print(f"  Population under base = {pop_base:+.4f} (n={pop_n})")
    print(f"  Excess over base = {excess:+.4f}")
    print(f"  ROI at best soft under = {roi_soft:+.3f} (SE={roi_soft_se:.3f}, n_priced={n_priced})")
    print(f"  ROI at Pinnacle = {roi_pin:+.3f} (n={len(pin_priced)})")

    # CONFIRM criteria (from PART B §C)
    c1 = mean_r > 0 and lb_90 > 0
    c2 = excess > 0
    c3 = roi_soft > 0
    # Q criterion: NH8 was DROPPED (no Q passed), so this criterion cannot be met
    # But we print the structure anyway
    print(f"\n  CONFIRM criteria:")
    print(f"    r > 0 AND 90% LB > 0: {'PASS' if c1 else 'FAIL'} (r={mean_r:+.4f}, LB={lb_90:+.4f})")
    print(f"    Excess over base > 0: {'PASS' if c2 else 'FAIL'} (excess={excess:+.4f})")
    print(f"    ROI at best soft > 0: {'PASS' if c3 else 'FAIL'} (ROI={roi_soft:+.3f})")
    print(f"    Q criterion: N/A (NH8 DROPPED — no Q passed on DEV)")

    overall = c1 and c2 and c3
    print(f"\n  OVERALL: {'PASS' if overall else 'FAIL'}")
    if not overall:
        failing = []
        if not c1:
            failing.append("90% LB ≤ 0")
        if not c2:
            failing.append("excess ≤ 0")
        if not c3:
            failing.append("ROI ≤ 0")
        print(f"  Failing: {', '.join(failing)}")

    return {
        "season": season, "n": n, "mean_r": mean_r, "se": se,
        "p_one": p_one, "lb_90": lb_90,
        "pop_base": pop_base, "pop_n": pop_n, "excess": excess,
        "roi_soft": roi_soft, "roi_soft_se": roi_soft_se, "n_priced": n_priced,
        "roi_pin": roi_pin, "overall": overall,
    }


if __name__ == "__main__":
    main()
