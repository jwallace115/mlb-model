#!/usr/bin/env python3
"""
CC-3 Item 2: Where the under excess lives.

All numbers = under residual vs Pinnacle fair, per season and pooled.
Under residual = (1 - over) - pin_close_fair_under.
Population base = all games with Pinnacle totals close and outcome.

Cuts:
  (a) v2 flag yes/no x driving-book quote age (<=10m / 10-60 / >60)
  (b) SYNCHRONOUS flag yes/no
  (c) v2 flag yes/no x sign of divergence (soft higher/lower on home)
  (d) by driving book (9 rows)
  (e) ALL games by Pinnacle last-3h ML move bins (<1pt / 1-3 / >=3pts)
      and by last-3h total move (down/flat/up) -- flag or not
  (f) flag yes/no x backup goalie (A-01 definition)
  (g) by month, both flag groups side by side
  (h) ROI at best same-snapshot soft under price for sync-flag rows

Positive control: synchronous rows, home ML within +/-0.01.
"""

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


def stat_row(label, arr):
    """Return dict with n, mean, SE for a series."""
    valid = arr.dropna()
    n = len(valid)
    if n == 0:
        return {"label": label, "n": 0, "mean": np.nan, "SE": np.nan}
    return {"label": label, "n": n, "mean": valid.mean(), "SE": valid.std(ddof=1) / np.sqrt(n)}


def fmt_row(d, base_mean=None):
    """Format a stat row for markdown."""
    base_str = f" (base: {base_mean:+.4f})" if base_mean is not None else ""
    if d["n"] == 0:
        return f"| {d['label']} | 0 | — | — |{base_str}"
    return f"| {d['label']} | {d['n']} | {d['mean']:+.4f} | {d['SE']:.4f} |"


def main():
    t0 = time.time()
    print("=== CC-3 Item 2: Under Excess Analysis ===")

    # Load data
    games = pd.read_parquet(DATA_DIR / "games_nhl.parquet")
    anatomy = pd.read_parquet(RESULTS_DIR / "flag_anatomy.parquet")
    features = pd.read_parquet(DATA_DIR / "features_nhl.parquet")

    # Merge anatomy into games
    df = games.merge(anatomy, on="event_id", how="left", suffixes=("", "_anat"))

    # Under residual: (1 - over) - pin_close_fair_under
    # Need: over (boolean for over hit) and pin_close_fair_under
    valid = df["pin_close_fair_under"].notna() & df["over"].notna()
    df = df[valid].copy()
    df["under_hit"] = 1 - df["over"].astype(float)
    df["under_resid"] = df["under_hit"] - df["pin_close_fair_under"]
    print(f"Games with valid under residual: {len(df)}")

    # Merge backup goalie data
    feat_cols = ["event_id", "home_is_backup", "away_is_backup"]
    feat_cols = [c for c in feat_cols if c in features.columns]
    df = df.merge(features[feat_cols], on="event_id", how="left")
    df["any_backup"] = ((df.get("home_is_backup", 0) == 1) | (df.get("away_is_backup", 0) == 1)).astype(int)

    # Use v2_flag from anatomy
    df["v2_flag"] = df["v2_flag"].fillna(0).astype(int)
    df["sync_flag"] = df["sync_flag"].fillna(0).astype(int)

    # Season column
    if "season_anat" in df.columns:
        df["season"] = df["season_anat"].fillna(df["season"])

    # Month from commence_time
    ct = pd.to_datetime(df["commence_time"])
    df["month"] = ct.dt.month

    # Driving book age bins
    df["drv_age_bin"] = pd.cut(
        df["driving_blu_age"],
        bins=[-0.001, 10, 60, 1e6],
        labels=["<=10m", "10-60m", ">60m"]
    )

    # Pin ML move bins (prob pts -> approximate American move; use abs value)
    # The move is in implied prob pts. <0.01 ~ <1pt, 0.01-0.03 ~ 1-3pt, >=0.03 ~ >=3pt
    # Actually the work order says "< 1 pt / 1-3 / >= 3 pts" in prob pts
    df["ml_move_abs"] = df["pin_ml_move_3h"].abs()
    df["ml_move_bin"] = pd.cut(
        df["ml_move_abs"] * 100,  # convert to "points" (prob pts * 100)
        bins=[-0.001, 1, 3, 100],
        labels=["<1pt", "1-3pt", ">=3pt"]
    )

    # Total move bins
    df["total_move_bin"] = df["pin_total_move_3h"].apply(
        lambda x: "down" if x < -0.01 else ("up" if x > 0.01 else "flat") if not pd.isna(x) else None
    )

    # === Population base ===
    lines = []
    lines.append("# CC-3 Item 2: Where the Under Excess Lives\n")

    pop_all = stat_row("ALL", df["under_resid"])
    pop_2022 = stat_row("2022-23", df[df["season"] == 2022]["under_resid"])
    pop_2023 = stat_row("2023-24", df[df["season"] == 2023]["under_resid"])

    lines.append("## Population base (all games with Pinnacle totals close + outcome)\n")
    lines.append("| Season | n | mean | SE |")
    lines.append("|---|---|---|---|")
    lines.append(fmt_row(pop_all))
    lines.append(fmt_row(pop_2022))
    lines.append(fmt_row(pop_2023))
    lines.append("")

    print(f"Population base: pooled {pop_all['mean']:+.4f} (n={pop_all['n']}), "
          f"2022 {pop_2022['mean']:+.4f}, 2023 {pop_2023['mean']:+.4f}")

    def section_table(title, groups, base=pop_all["mean"]):
        """Build a markdown table section from a list of (label, mask) tuples."""
        lines_out = [f"## {title}\n"]
        lines_out.append(f"Population base: {base:+.4f}\n")
        lines_out.append("| Cut | n | mean under_resid | SE |")
        lines_out.append("|---|---|---|---|")
        for label, mask in groups:
            sub = df[mask]
            for szn_label, szn_mask in [("pooled", pd.Series(True, index=df.index)),
                                         ("2022-23", df["season"] == 2022),
                                         ("2023-24", df["season"] == 2023)]:
                r = stat_row(f"{label} ({szn_label})", sub[szn_mask]["under_resid"])
                lines_out.append(fmt_row(r))
            lines_out.append("|---|---|---|---|")
        lines_out.append("")
        return lines_out

    # === (a) v2 flag x driving-book quote age ===
    groups_a = []
    for flag_val, flag_label in [(1, "flag=yes"), (0, "flag=no")]:
        for age_label in ["<=10m", "10-60m", ">60m"]:
            mask = (df["v2_flag"] == flag_val) & (df["drv_age_bin"] == age_label)
            groups_a.append((f"{flag_label}, drv_age {age_label}", mask))
        # Also flag=no with no driving book (NaN age)
        if flag_val == 0:
            mask = (df["v2_flag"] == 0)
            groups_a.append((f"flag=no (all)", mask))

    lines.extend(section_table("(a) v2 flag x driving-book quote age", groups_a))

    # === (b) SYNCHRONOUS flag yes/no ===
    groups_b = [
        ("sync_flag=yes", df["sync_flag"] == 1),
        ("sync_flag=no", df["sync_flag"] == 0),
    ]
    lines.extend(section_table("(b) SYNCHRONOUS flag yes/no", groups_b))

    # === (c) v2 flag x sign of divergence ===
    groups_c = [
        ("flag=yes, soft higher on home (+1)", (df["v2_flag"] == 1) & (df["driving_sign"] == 1)),
        ("flag=yes, soft lower on home (-1)", (df["v2_flag"] == 1) & (df["driving_sign"] == -1)),
        ("flag=no", df["v2_flag"] == 0),
    ]
    lines.extend(section_table("(c) v2 flag x sign of divergence", groups_c))

    # === (d) by driving book ===
    groups_d = []
    for book in SOFT_BOOKS:
        mask = (df["v2_flag"] == 1) & (df["driving_book"] == book)
        groups_d.append((f"driving={book}", mask))
    lines.extend(section_table("(d) By driving book (flagged games)", groups_d))

    # === (e) ALL games by Pinnacle ML move and total move ===
    groups_e = []
    for ml_bin in ["<1pt", "1-3pt", ">=3pt"]:
        for flag_val, flag_label in [(1, "flag=yes"), (0, "flag=no")]:
            mask = (df["ml_move_bin"] == ml_bin) & (df["v2_flag"] == flag_val)
            groups_e.append((f"ML move {ml_bin}, {flag_label}", mask))
    for tot_bin in ["down", "flat", "up"]:
        for flag_val, flag_label in [(1, "flag=yes"), (0, "flag=no")]:
            mask = (df["total_move_bin"] == tot_bin) & (df["v2_flag"] == flag_val)
            groups_e.append((f"Total move {tot_bin}, {flag_label}", mask))
    lines.extend(section_table("(e) Pinnacle last-3h moves x flag", groups_e))

    # === (f) flag x backup goalie ===
    groups_f = []
    for flag_val, flag_label in [(1, "flag=yes"), (0, "flag=no")]:
        for bk_val, bk_label in [(1, "backup=yes"), (0, "backup=no")]:
            mask = (df["v2_flag"] == flag_val) & (df["any_backup"] == bk_val)
            groups_f.append((f"{flag_label}, {bk_label}", mask))

    # Also report share of backup games in each flag group
    flag_yes = df[df["v2_flag"] == 1]
    flag_no = df[df["v2_flag"] == 0]
    bk_share_yes = flag_yes["any_backup"].mean() if len(flag_yes) > 0 else np.nan
    bk_share_no = flag_no["any_backup"].mean() if len(flag_no) > 0 else np.nan

    lines.append(f"## (f) v2 flag x backup goalie (A-01 definition)\n")
    lines.append(f"Share of backup-goalie games: flag=yes {bk_share_yes:.3f}, flag=no {bk_share_no:.3f}\n")
    lines.append(f"Population base: {pop_all['mean']:+.4f}\n")
    lines.append("| Cut | n | mean under_resid | SE |")
    lines.append("|---|---|---|---|")
    for label, mask in groups_f:
        for szn_label, szn_mask in [("pooled", pd.Series(True, index=df.index)),
                                     ("2022-23", df["season"] == 2022),
                                     ("2023-24", df["season"] == 2023)]:
            r = stat_row(f"{label} ({szn_label})", df[mask & szn_mask]["under_resid"])
            lines.append(fmt_row(r))
        lines.append("|---|---|---|---|")
    lines.append("")

    # === (g) by month, both flag groups side by side ===
    lines.append("## (g) By month, flag=yes vs flag=no\n")
    lines.append(f"Population base: {pop_all['mean']:+.4f}\n")
    lines.append("| Month | flag=yes n | flag=yes mean | flag=yes SE | flag=no n | flag=no mean | flag=no SE |")
    lines.append("|---|---|---|---|---|---|---|")
    for m in sorted(df["month"].unique()):
        fy = df[(df["month"] == m) & (df["v2_flag"] == 1)]["under_resid"]
        fn = df[(df["month"] == m) & (df["v2_flag"] == 0)]["under_resid"]
        fy_n, fy_m, fy_se = len(fy), fy.mean() if len(fy) > 0 else np.nan, fy.std(ddof=1)/np.sqrt(len(fy)) if len(fy) > 1 else np.nan
        fn_n, fn_m, fn_se = len(fn), fn.mean() if len(fn) > 0 else np.nan, fn.std(ddof=1)/np.sqrt(len(fn)) if len(fn) > 1 else np.nan
        fy_str = f"{fy_m:+.4f}" if not pd.isna(fy_m) else "—"
        fn_str = f"{fn_m:+.4f}" if not pd.isna(fn_m) else "—"
        fy_se_str = f"{fy_se:.4f}" if not pd.isna(fy_se) else "—"
        fn_se_str = f"{fn_se:.4f}" if not pd.isna(fn_se) else "—"
        lines.append(f"| {m} | {fy_n} | {fy_str} | {fy_se_str} | {fn_n} | {fn_str} | {fn_se_str} |")
    lines.append("")

    # === (h) ROI at best same-snapshot soft under price for sync-flag rows ===
    lines.append("## (h) ROI at best same-snapshot soft under price (sync-flag rows)\n")

    # For sync-flag rows, find the best soft under price from books in Pinnacle's snapshot
    # with same total point and age <= 10 min
    # We need to go back to the raw tape for this... but we don't have it loaded here.
    # Instead, use the games table's soft book under prices, filtered by the anatomy's
    # per-book in_pin_snap flags.
    sync_games = df[df["sync_flag"] == 1].copy()
    print(f"Sync-flag games for ROI: {len(sync_games)}")

    # For each sync game, find the best soft under decimal price
    best_prices = []
    for _, row in sync_games.iterrows():
        best_dec = np.nan
        best_book = None
        for book in SOFT_BOOKS:
            in_snap_col = f"soft_{book}_in_pin_snap"
            if in_snap_col not in row.index or row.get(in_snap_col, 0) != 1:
                continue
            # Check same total point
            soft_total = row.get(f"soft_{book}_close_total")
            pin_total = row.get("pin_close_total")
            if pd.isna(soft_total) or pd.isna(pin_total) or soft_total != pin_total:
                continue
            # Check blu age <= 10 min
            blu_col = f"soft_{book}_blu_age"
            if blu_col in row.index:
                blu_age = row.get(blu_col)
                if pd.isna(blu_age) or blu_age > 10:
                    continue
            under_price = row.get(f"soft_{book}_close_under_price")
            if pd.isna(under_price):
                continue
            dec = american_to_decimal(under_price)
            if pd.isna(dec):
                continue
            if pd.isna(best_dec) or dec > best_dec:
                best_dec = dec
                best_book = book
        best_prices.append({"event_id": row["event_id"], "best_soft_dec": best_dec, "best_book": best_book})

    bp = pd.DataFrame(best_prices)
    sync_games = sync_games.merge(bp, on="event_id", how="left")
    priced = sync_games[sync_games["best_soft_dec"].notna()]
    if len(priced) > 0:
        priced = priced.copy()
        priced["pnl"] = priced["under_hit"] * priced["best_soft_dec"] - 1.0
        roi = priced["pnl"].mean()
        roi_se = priced["pnl"].std(ddof=1) / np.sqrt(len(priced))
        lines.append(f"n_priced: {len(priced)}")
        lines.append(f"ROI (sync soft best under): {roi:+.4f} (SE: {roi_se:.4f})")

        # Also compute v2 ROI for comparison
        v2_games = df[df["v2_flag"] == 1].copy()
        # v2 ROI: use all soft books' under prices at their own close
        v2_best = []
        for _, row in v2_games.iterrows():
            best_dec = np.nan
            for book in SOFT_BOOKS:
                soft_total = row.get(f"soft_{book}_close_total")
                pin_total = row.get("pin_close_total")
                if pd.isna(soft_total) or pd.isna(pin_total) or soft_total != pin_total:
                    continue
                under_price = row.get(f"soft_{book}_close_under_price")
                if pd.isna(under_price):
                    continue
                dec = american_to_decimal(under_price)
                if pd.isna(dec):
                    continue
                if pd.isna(best_dec) or dec > best_dec:
                    best_dec = dec
            v2_best.append(best_dec)
        v2_games["best_soft_dec"] = v2_best
        v2_priced = v2_games[v2_games["best_soft_dec"].notna()]
        if len(v2_priced) > 0:
            v2_priced = v2_priced.copy()
            v2_priced["pnl"] = v2_priced["under_hit"] * v2_priced["best_soft_dec"] - 1.0
            v2_roi = v2_priced["pnl"].mean()
            v2_roi_se = v2_priced["pnl"].std(ddof=1) / np.sqrt(len(v2_priced))
            lines.append(f"n_priced (v2): {len(v2_priced)}")
            lines.append(f"ROI (v2 soft best under): {v2_roi:+.4f} (SE: {v2_roi_se:.4f})")
    else:
        lines.append("No priced sync-flag games found.")

    lines.append("")

    # === Positive control: synchronous rows, home ML ===
    lines.append("## Positive-control sanity: synchronous rows, home ML\n")
    sync_all = df[df["sync_flag"].isin([0, 1])].copy()
    sync_rows = df[df["sync_flag"] == 1].copy()
    home_resid_sync = sync_rows["under_resid"].copy()
    # Actually the positive control is HOME ML residual, not under
    # home_ml_resid = home_win - pin_close_fair_h
    sync_rows["home_ml_resid"] = sync_rows["home_win"].astype(float) - sync_rows["pin_close_fair_h"]
    hm = stat_row("sync rows, home ML resid", sync_rows["home_ml_resid"])
    lines.append(f"Home ML residual (sync rows): mean={hm['mean']:+.4f} (SE={hm['SE']:.4f}, n={hm['n']})")
    lines.append(f"Within +/-0.01: {'YES' if abs(hm['mean']) <= 0.01 else 'NO'}")
    lines.append("")

    # Write report
    report_path = RESULTS_DIR / "under_excess.md"
    report_path.write_text("\n".join(lines))
    print(f"Wrote {report_path}")
    print(f"Done ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
