#!/usr/bin/env python3
"""
CC-2 Item 2: NB10 CONFIRM — April regular-season OVER, one run.

Hard-coded: sport="nba", season=2024, month=4, market="totals".
Refuses to run otherwise (asserts on every loaded frame's commence_time month/year).

Rule (from REGISTRY_v2_ADDENDUM.md §B):
- NBA regular-season games with Pinnacle closing total
- Tip date in April (through 2025-04-13 regular-season finale)
- Side: OVER at the closing point
- Pushes excluded
- r vs Pinnacle fair over prob; game-clustered SE; 90% lower bound
- ROI at best same-point soft price AND at Pinnacle's own price
- Q1: possessions vs prior-10 (game-clustered, one-sided p < 0.10)
- Q2: top-5 minutes vs prior-20
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results" / "confirm_nb10"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

from research.corrcause.build_tables import (
    american_to_implied, american_to_decimal, v_american_to_implied,
    nba_full_to_abbrev, _nba_season_str, SOFT_BOOKS
)


def main():
    print("=== NB10 CONFIRM: April 2024-25 regular-season OVER ===")
    t0 = time.time()

    # ===============================================================
    # 1. Load lines_hourly for season=2024 (covers 2024-25 season)
    # ===============================================================
    print("  Loading lines_hourly season=2024...")
    lh_path = Path.home() / "mlb-model/data/odds_archive/nba/history/lines_hourly/season=2024"
    files = sorted(lh_path.glob("*.parquet"))
    assert len(files) > 0, "No lines_hourly files for season=2024"
    lh = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    lh["snap"] = pd.to_datetime(lh["snapshot_utc"])
    lh["ct"] = pd.to_datetime(lh["commence_time"])

    # SAFETY: assert ALL commence_times are in the 2024-25 season
    lh_months = lh["ct"].dt.month
    lh_years = lh["ct"].dt.year
    assert ((lh_years == 2024) & (lh_months >= 10) | (lh_years == 2025) & (lh_months <= 6)).all(), \
        "lines_hourly contains data outside the 2024-25 season"
    print(f"  {len(lh):,} rows, {lh['event_id'].nunique()} events")

    # Filter to pre-tip
    lh = lh[lh["snap"] < lh["ct"]].copy()

    # Filter to April 2025 only
    april_mask = (lh["ct"].dt.month == 4) & (lh["ct"].dt.year == 2025)
    lh_april = lh[april_mask].copy()
    assert len(lh_april) > 0, "No April 2025 data in lines_hourly"
    # SAFETY: assert all are April 2025
    assert (lh_april["ct"].dt.month == 4).all(), "Non-April data in April filter"
    assert (lh_april["ct"].dt.year == 2025).all(), "Non-2025 data in April filter"

    # Regular-season finale: 2025-04-13
    RS_FINALE = pd.Timestamp("2025-04-13", tz="US/Eastern")
    lh_april["ct_et"] = lh_april["ct"].dt.tz_convert("US/Eastern")
    lh_rs = lh_april[lh_april["ct_et"].dt.date <= RS_FINALE.date()].copy()
    print(f"  April 2025 regular-season pre-tip rows: {len(lh_rs):,}, "
          f"events: {lh_rs['event_id'].nunique()}")

    # ===============================================================
    # 2. Extract Pinnacle closes and soft book closes
    # ===============================================================
    events = lh_rs[["event_id", "ct", "home_team", "away_team"]].drop_duplicates("event_id")

    all_books = ["pinnacle"] + SOFT_BOOKS
    # Extract closes per event per book
    tape = lh_rs.sort_values("snap")
    idx = tape.groupby(["event_id", "bookmaker", "market", "outcome_name"])["snap"].idxmax()
    last = tape.loc[idx].copy()
    last["is_over"] = last["outcome_name"] == "Over"

    rows = {}
    for eid, grp in last.groupby("event_id"):
        r = {"event_id": eid}
        ct = events.loc[events["event_id"] == eid, "ct"]
        if len(ct) > 0:
            r["commence_time"] = ct.iloc[0]

        for book in all_books:
            bk = grp[grp["bookmaker"] == book]
            prefix = "pin" if book == "pinnacle" else f"soft_{book}"

            tot = bk[bk["market"] == "totals"]
            over = tot[tot["is_over"]]
            under = tot[~tot["is_over"]]
            if len(over) > 0:
                r[f"{prefix}_close_total"] = over["point"].iloc[0]
                r[f"{prefix}_close_over_price"] = over["price"].iloc[0]
            if len(under) > 0:
                r[f"{prefix}_close_under_price"] = under["price"].iloc[0]

        rows[eid] = r

    close_df = pd.DataFrame(rows.values())
    print(f"  Close rows: {len(close_df)}")

    # De-vig Pinnacle
    if "pin_close_over_price" in close_df.columns:
        imp_o = v_american_to_implied(close_df["pin_close_over_price"].values)
        imp_u = v_american_to_implied(close_df["pin_close_under_price"].values)
        total = imp_o + imp_u
        mask = total > 0
        close_df["pin_fair_over"] = np.where(mask, imp_o / total, np.nan)
        close_df["pin_fair_under"] = np.where(mask, imp_u / total, np.nan)

    # Require Pinnacle total close
    close_df = close_df[close_df["pin_close_total"].notna() & close_df["pin_fair_over"].notna()].copy()
    print(f"  With Pinnacle total close: {len(close_df)}")

    # ===============================================================
    # 3. Match outcomes from games.parquet
    # ===============================================================
    print("  Matching outcomes...")
    nba_games = pd.read_parquet(Path.home() / "mlb-model/nba/data/games.parquet")
    nba_games["date_dt"] = pd.to_datetime(nba_games["date"])

    # SAFETY: only use 2024-25 season
    nba_2425 = nba_games[nba_games["season"] == "2024-25"].copy()
    assert len(nba_2425) > 0, "No 2024-25 games"
    # Only April
    nba_april = nba_2425[(nba_2425["date_dt"].dt.month == 4) & (nba_2425["date_dt"].dt.year == 2025)]
    assert (nba_april["date_dt"].dt.month == 4).all(), "Non-April games in filter"
    print(f"  April 2025 games with outcomes: {len(nba_april)}")

    # Merge
    events_m = events.copy()
    events_m["game_date"] = events_m["ct"].dt.tz_convert("US/Eastern").dt.date.astype(str)
    events_m["h_abbrev"] = events_m["home_team"].map(nba_full_to_abbrev)
    events_m["a_abbrev"] = events_m["away_team"].map(nba_full_to_abbrev)

    nba_april_m = nba_april.copy()
    nba_april_m["date_str"] = nba_april_m["date_dt"].dt.date.astype(str)

    merged = close_df.merge(events_m[["event_id", "game_date", "h_abbrev", "a_abbrev",
                                       "home_team", "away_team"]], on="event_id")
    merged = merged.merge(
        nba_april_m[["date_str", "home_team", "away_team", "actual_total"]],
        left_on=["game_date", "h_abbrev", "a_abbrev"],
        right_on=["date_str", "home_team", "away_team"],
        how="inner",
        suffixes=("", "_g")
    )
    print(f"  Matched: {len(merged)}")

    # Over grading (pushes excluded)
    merged["over"] = np.where(
        merged["actual_total"] > merged["pin_close_total"], 1.0,
        np.where(merged["actual_total"] < merged["pin_close_total"], 0.0, np.nan)
    )
    merged = merged[merged["over"].notna()].copy()
    print(f"  After excluding pushes: {len(merged)}")

    # SAFETY: assert all data is April 2025
    ct_check = pd.to_datetime(merged["commence_time"])
    assert (ct_check.dt.month == 4).all(), "Non-April commence_time in final data"
    assert (ct_check.dt.year == 2025).all(), "Non-2025 commence_time in final data"

    # ===============================================================
    # 4. Compute residuals (OVER side)
    # ===============================================================
    merged["residual"] = merged["over"] - merged["pin_fair_over"]
    n = len(merged)
    mean_r = merged["residual"].mean()
    se = merged["residual"].std(ddof=1) / np.sqrt(n)
    t_stat = mean_r / se if se > 0 else 0
    # 90% lower bound (one-sided)
    t_crit_90 = stats.t.ppf(0.10, df=n - 1)
    lb_90 = mean_r + t_crit_90 * se  # lower bound (t_crit is negative)

    p_one = 1 - stats.t.cdf(t_stat, df=n - 1) if se > 0 else 0.5

    print(f"\n=== NB10 CONFIRM RESULT ===")
    print(f"  n = {n}")
    print(f"  r = {mean_r:+.4f}")
    print(f"  SE = {se:.4f}")
    print(f"  t = {t_stat:.3f}")
    print(f"  p (one-sided) = {p_one:.4f}")
    print(f"  90% lower bound = {lb_90:+.4f}")
    print(f"  CRITERION 1 (r > 0 and 90% LB > 0): {'PASS' if mean_r > 0 and lb_90 > 0 else 'FAIL'}")

    # ===============================================================
    # 5. ROI at best same-point soft price
    # ===============================================================
    n_priced = 0
    pnl_soft = []
    pnl_pin = []
    for _, row in merged.iterrows():
        won = bool(row["over"])
        pin_point = row["pin_close_total"]

        # Best soft price
        best_dec = None
        for book in SOFT_BOOKS:
            pt_col = f"soft_{book}_close_total"
            price_col = f"soft_{book}_close_over_price"
            if pt_col not in row.index or pd.isna(row.get(pt_col)):
                continue
            if row[pt_col] != pin_point:
                continue  # same-point matching
            if price_col not in row.index or pd.isna(row.get(price_col)):
                continue
            dec = american_to_decimal(row[price_col])
            if pd.isna(dec):
                continue
            if best_dec is None or dec > best_dec:
                best_dec = dec

        if best_dec is not None:
            n_priced += 1
            pnl_soft.append((best_dec - 1) if won else -1.0)

        # Pinnacle price
        pin_price = row.get("pin_close_over_price")
        if not pd.isna(pin_price):
            dec_pin = american_to_decimal(pin_price)
            if not pd.isna(dec_pin):
                pnl_pin.append((dec_pin - 1) if won else -1.0)

    roi_soft = np.mean(pnl_soft) if pnl_soft else np.nan
    roi_soft_se = np.std(pnl_soft, ddof=1) / np.sqrt(len(pnl_soft)) if len(pnl_soft) > 1 else np.nan
    roi_pin = np.mean(pnl_pin) if pnl_pin else np.nan

    print(f"\n  ROI at best soft price: {roi_soft:+.4f} (n_priced={n_priced}, SE={roi_soft_se:.4f})")
    print(f"  ROI at Pinnacle: {roi_pin:+.4f}")
    print(f"  CRITERION 2 (ROI soft > 0): {'PASS' if roi_soft > 0 else 'FAIL'}")

    # ===============================================================
    # 6. Q1: possessions vs prior-10
    # ===============================================================
    print("\n  Computing Q1 (possessions)...")
    box = pd.read_parquet(Path.home() / "mlb-model/nba/data/box_stats.parquet")
    box["date_dt"] = pd.to_datetime(box["date"])

    # SAFETY: only use 2024-25 box stats
    box_2425 = box[box["season"] == "2024-25"].copy()
    assert len(box_2425) > 0, "No 2024-25 box stats"
    # Assert: only use box stats BEFORE each game date (point-in-time)
    # This is the ONE other 2024-25 read allowed (box stats for the Q)

    poss_diffs = []
    for _, row in merged.iterrows():
        game_date = pd.to_datetime(row["commence_time"]).tz_convert("US/Eastern").date()
        ht = row["h_abbrev"]
        at = row["a_abbrev"]

        # Game-day possessions
        game_box = box_2425[
            (box_2425["date_dt"].dt.date == game_date) &
            ((box_2425["team"] == ht) | (box_2425["team"] == at))
        ]
        if len(game_box) == 0:
            continue

        game_poss = game_box["poss"].sum()  # total possessions for both teams

        # Prior-10 average for each team (point-in-time: strictly before game_date)
        prior_poss = []
        for team in [ht, at]:
            prior = box_2425[
                (box_2425["team"] == team) & (box_2425["date_dt"].dt.date < game_date)
            ].sort_values("date_dt").tail(10)
            if len(prior) >= 5:
                prior_poss.append(prior["poss"].mean())

        if len(prior_poss) == 2:
            expected_poss = sum(prior_poss)  # sum of both teams' prior-10 averages
            poss_diffs.append(game_poss - expected_poss)

    if poss_diffs:
        poss_arr = np.array(poss_diffs)
        mean_diff = poss_arr.mean()
        se_diff = poss_arr.std(ddof=1) / np.sqrt(len(poss_arr))
        # One-sided test: diff > 1.0
        t_q1 = (mean_diff - 1.0) / se_diff if se_diff > 0 else 0
        p_q1 = 1 - stats.t.cdf(t_q1, df=len(poss_arr) - 1) if se_diff > 0 else 0.5
        print(f"  Q1 possessions: n={len(poss_arr)}, mean diff={mean_diff:+.1f}, "
              f"SE={se_diff:.1f}, t(vs +1.0)={t_q1:.2f}, p={p_q1:.3f}")
        print(f"  CRITERION Q1 (diff >= +1.0, p < 0.10): {'PASS' if p_q1 < 0.10 else 'FAIL'}")
    else:
        print("  Q1: no data")
        p_q1 = 1.0

    # ===============================================================
    # 7. Q2: top-5-minutes vs prior-20
    # ===============================================================
    print("\n  Computing Q2 (top-5 minutes)...")
    plogs_path = Path.home() / "mlb-model/nba/model_c/player_game_logs.parquet"
    if plogs_path.exists():
        plogs = pd.read_parquet(plogs_path)
        plogs["GAME_DATE_DT"] = pd.to_datetime(plogs["GAME_DATE"])

        # Only 2024-25 season
        plogs_2425 = plogs[plogs["SEASON_ID"] == "22024"].copy() if "SEASON_ID" in plogs.columns else plogs.copy()
        if "SEASON_ID" not in plogs.columns:
            # Filter by date range
            plogs_2425 = plogs[
                (plogs["GAME_DATE_DT"] >= "2024-10-01") & (plogs["GAME_DATE_DT"] <= "2025-06-30")
            ].copy()

        min_diffs = []
        for _, row in merged.iterrows():
            game_date = pd.to_datetime(row["commence_time"]).tz_convert("US/Eastern").date()
            for team in [row["h_abbrev"], row["a_abbrev"]]:
                # Game-day top-5 minutes
                game_logs = plogs_2425[
                    (plogs_2425["GAME_DATE_DT"].dt.date == game_date) &
                    (plogs_2425["TEAM_ABBREVIATION"] == team)
                ]
                if len(game_logs) == 0:
                    continue

                # Find top-5 players by season minutes
                team_season = plogs_2425[plogs_2425["TEAM_ABBREVIATION"] == team]
                season_min = team_season.groupby("PLAYER_ID")["MIN"].sum().nlargest(5)
                top5_ids = season_min.index.tolist()

                # Their minutes in this game
                game_top5 = game_logs[game_logs["PLAYER_ID"].isin(top5_ids)]
                if len(game_top5) == 0:
                    continue
                game_avg = game_top5["MIN"].mean()

                # Prior-20 average
                prior_logs = plogs_2425[
                    (plogs_2425["TEAM_ABBREVIATION"] == team) &
                    (plogs_2425["GAME_DATE_DT"].dt.date < game_date) &
                    (plogs_2425["PLAYER_ID"].isin(top5_ids))
                ]
                if len(prior_logs) < 20:
                    continue
                # Group by game date, take mean of top-5's minutes per game
                prior_by_game = prior_logs.groupby("GAME_DATE_DT")["MIN"].mean()
                prior_avg = prior_by_game.tail(20).mean()

                min_diffs.append(game_avg - prior_avg)

        if min_diffs:
            min_arr = np.array(min_diffs)
            mean_min = min_arr.mean()
            se_min = min_arr.std(ddof=1) / np.sqrt(len(min_arr))
            # One-sided test: diff <= -2.0
            t_q2 = (mean_min - (-2.0)) / se_min if se_min > 0 else 0
            p_q2 = stats.t.cdf(t_q2, df=len(min_arr) - 1) if se_min > 0 else 0.5
            print(f"  Q2 top-5 minutes: n={len(min_arr)}, mean diff={mean_min:+.1f}, "
                  f"SE={se_min:.1f}, t(vs -2.0)={t_q2:.2f}, p={p_q2:.3f}")
            print(f"  CRITERION Q2 (diff <= -2.0, p < 0.10): {'PASS' if p_q2 < 0.10 else 'FAIL'}")
        else:
            print("  Q2: no data")
            p_q2 = 1.0
    else:
        print("  Q2: player_game_logs not found")
        p_q2 = 1.0

    # ===============================================================
    # 8. Final verdict
    # ===============================================================
    c1 = mean_r > 0 and lb_90 > 0
    c2 = roi_soft > 0
    c_q1 = p_q1 < 0.10 if poss_diffs else False
    overall = c1 and c2 and c_q1

    print(f"\n{'='*50}")
    print(f"NB10 CONFIRM VERDICT: {'PASS' if overall else 'FAIL'}")
    print(f"  Criterion 1 (r > 0, 90% LB > 0): {'PASS' if c1 else 'FAIL'}")
    print(f"  Criterion 2 (ROI soft > 0): {'PASS' if c2 else 'FAIL'}")
    print(f"  Q1 (possessions +1.0, p < 0.10): {'PASS' if c_q1 else 'FAIL'}")
    print(f"  Q2 (top-5 minutes -2.0, secondary): reported above")
    if overall:
        print("  STATUS: CANDIDATE for forward shadow in April 2027 — nothing else.")
    else:
        print("  STATUS: NB10 is DEAD with its id.")
    print(f"{'='*50}")

    # Save fired parquet
    save_cols = ["event_id", "commence_time", "home_team", "away_team",
                 "h_abbrev", "a_abbrev", "pin_close_total", "pin_fair_over",
                 "actual_total", "over", "residual"]
    out_cols = [c for c in save_cols if c in merged.columns]
    merged[out_cols].to_parquet(RESULTS_DIR / "nb10_fired.parquet", index=False)
    print(f"\n  Wrote {RESULTS_DIR / 'nb10_fired.parquet'} ({len(merged)} rows)")
    print(f"  Elapsed: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
