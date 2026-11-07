#!/usr/bin/env python3
"""
CC-1b run_screen.py — Run the DEV screen with corrected residuals and ROI.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results" / "screen_v1b"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

from research.corrcause.build_tables import (
    american_to_implied, american_to_decimal, SOFT_BOOKS
)
from research.corrcause.cells import (
    load_config, NHL_TIER1, NBA_TIER1,
    generate_tier2_nhl, generate_tier2_nba, _devig_spread
)


def compute_stats(fired, min_per_season=60):
    """Compute cell statistics with game-clustered SE (one row per event_id)."""
    if len(fired) == 0 or "residual" not in fired.columns:
        return None

    # Game-cluster: one row per event_id (keep first if duplicates)
    clustered = fired.drop_duplicates("event_id", keep="first")
    r = clustered["residual"].dropna()
    if len(r) < 10:
        return None

    n = len(r)
    mean_r = r.mean()
    se = r.std(ddof=1) / np.sqrt(n)
    t_stat = mean_r / se if se > 0 else 0
    p_one = 1 - stats.t.cdf(t_stat, df=n - 1) if se > 0 else 0.5

    # Per season
    if "season" not in clustered.columns and "commence_time" in clustered.columns:
        clustered = clustered.copy()
        clustered["season"] = pd.to_datetime(clustered["commence_time"]).apply(
            lambda x: x.year if x.month >= 10 else x.year - 1
        )

    per_season = {}
    if "season" in clustered.columns:
        for s, grp in clustered.groupby("season"):
            sr = grp["residual"].dropna()
            per_season[int(s)] = {
                "n": len(sr),
                "mean_r": sr.mean(),
                "se": sr.std(ddof=1) / np.sqrt(len(sr)) if len(sr) > 1 else np.nan,
            }

    season_pass = all(v["n"] >= min_per_season for v in per_season.values()) if per_season else False
    signs = [v["mean_r"] > 0 for v in per_season.values()]
    same_sign = len(set(signs)) == 1 if len(signs) >= 2 else False

    return {
        "n": n, "mean_r": mean_r, "se": se, "p_one": p_one,
        "season_pass": season_pass, "same_sign": same_sign,
        "per_season": per_season,
    }


def compute_roi(fired, games):
    """ROI at best soft price with same-point matching. No default price."""
    if len(fired) == 0 or "cell_side" not in fired.columns:
        return None

    clustered = fired.drop_duplicates("event_id", keep="first")
    side = clustered["cell_side"].iloc[0]

    n_priced = 0
    n_excluded = 0
    pnl = []

    for _, row in clustered.iterrows():
        eid = row["event_id"]
        g_rows = games[games["event_id"] == eid]
        if len(g_rows) == 0:
            n_excluded += 1
            continue
        g = g_rows.iloc[0]

        # Determine outcome
        if "over" in side:
            won = row.get("over", g.get("over"))
            if pd.isna(won): n_excluded += 1; continue
            won = bool(won)
            pin_point = g.get("pin_close_total")
            price_col_template = "soft_{}_close_over_price"
            point_col_template = "soft_{}_close_total"
        elif "under" in side:
            won = g.get("over")
            if pd.isna(won): n_excluded += 1; continue
            won = not bool(won)
            pin_point = g.get("pin_close_total")
            price_col_template = "soft_{}_close_under_price"
            point_col_template = "soft_{}_close_total"
        elif "home_ml" in side:
            won = g.get("home_win")
            if pd.isna(won): n_excluded += 1; continue
            won = bool(won)
            pin_point = None  # ML has no point
            price_col_template = "soft_{}_close_ml_h"
            point_col_template = None
        elif "away_ml" in side:
            won = g.get("home_win")
            if pd.isna(won): n_excluded += 1; continue
            won = not bool(won)
            pin_point = None
            price_col_template = "soft_{}_close_ml_a"
            point_col_template = None
        elif "home_ats" in side:
            won = g.get("home_covers")
            if pd.isna(won): n_excluded += 1; continue
            won = bool(won)
            pin_point = g.get("pin_close_spread_h")
            price_col_template = "soft_{}_close_spread_h_price"
            point_col_template = "soft_{}_close_spread_h"
        elif "away_ats" in side:
            won = g.get("home_covers")
            if pd.isna(won): n_excluded += 1; continue
            won = not bool(won)
            pin_point = g.get("pin_close_spread_h")
            # Away spread = -home spread; match on home spread point
            price_col_template = "soft_{}_close_spread_a_price"
            point_col_template = "soft_{}_close_spread_h"
        else:
            n_excluded += 1
            continue

        # Find best soft price with same-point matching
        best_dec = None
        for book in SOFT_BOOKS:
            price_col = price_col_template.format(book)
            if price_col not in g.index or pd.isna(g[price_col]):
                continue

            # Point matching (totals and spreads only)
            if point_col_template is not None:
                pt_col = point_col_template.format(book)
                if pt_col not in g.index or pd.isna(g[pt_col]):
                    continue
                if pd.isna(pin_point) or g[pt_col] != pin_point:
                    continue

            dec = american_to_decimal(g[price_col])
            if pd.isna(dec):
                continue
            if best_dec is None or dec > best_dec:
                best_dec = dec

        if best_dec is None:
            n_excluded += 1
            continue

        n_priced += 1
        pnl.append((best_dec - 1) if won else -1.0)

    if n_priced == 0:
        return {"n_priced": 0, "n_excluded": n_excluded, "roi": np.nan, "roi_se": np.nan}

    roi = np.mean(pnl)
    roi_se = np.std(pnl, ddof=1) / np.sqrt(n_priced)

    # Also compute ROI at Pinnacle's own close
    pin_pnl = []
    for _, row in clustered.iterrows():
        eid = row["event_id"]
        g_rows = games[games["event_id"] == eid]
        if len(g_rows) == 0: continue
        g = g_rows.iloc[0]

        if "over" in side:
            won = bool(row.get("over", g.get("over")))
            price = g.get("pin_close_over_price")
        elif "under" in side:
            won = not bool(g.get("over"))
            price = g.get("pin_close_under_price")
        elif "home_ml" in side:
            won = bool(g.get("home_win"))
            price = g.get("pin_close_ml_h")
        elif "away_ml" in side:
            won = not bool(g.get("home_win"))
            price = g.get("pin_close_ml_a")
        elif "home_ats" in side:
            won = bool(g.get("home_covers"))
            price = g.get("pin_close_spread_h_price")
        elif "away_ats" in side:
            won = not bool(g.get("home_covers"))
            price = g.get("pin_close_spread_a_price")
        else:
            continue

        if pd.isna(price): continue
        dec = american_to_decimal(price)
        if pd.isna(dec): continue
        pin_pnl.append((dec - 1) if won else -1.0)

    pin_roi = np.mean(pin_pnl) if pin_pnl else np.nan

    return {
        "n_priced": n_priced, "n_excluded": n_excluded,
        "roi": roi, "roi_se": roi_se, "pin_roi": pin_roi,
    }


def compute_breakdowns(fired, games):
    """CHECK 5 breakdowns: season, month, fav/dog or O/U, line band, sample-depth tercile."""
    if len(fired) == 0:
        return []

    clustered = fired.drop_duplicates("event_id", keep="first").copy()
    if "season" not in clustered.columns and "commence_time" in clustered.columns:
        clustered["season"] = pd.to_datetime(clustered["commence_time"]).apply(
            lambda x: x.year if x.month >= 10 else x.year - 1
        )
    clustered["month"] = pd.to_datetime(clustered["commence_time"]).dt.month

    rows = []
    r = clustered["residual"].dropna()
    pooled_sum = r.sum()

    # By season
    for key, grp in clustered.groupby("season"):
        sr = grp["residual"].dropna()
        if len(sr) == 0: continue
        rows.append({"breakdown": "season", "value": str(int(key)),
                     "n": len(sr), "mean_r": sr.mean(),
                     "se": sr.std(ddof=1) / np.sqrt(len(sr)) if len(sr) > 1 else np.nan})

    # By month
    for key, grp in clustered.groupby("month"):
        sr = grp["residual"].dropna()
        if len(sr) == 0: continue
        rows.append({"breakdown": "month", "value": str(int(key)),
                     "n": len(sr), "mean_r": sr.mean(),
                     "se": sr.std(ddof=1) / np.sqrt(len(sr)) if len(sr) > 1 else np.nan})

    # Share of largest season-month
    clustered["season_month"] = clustered["season"].astype(str) + "_" + clustered["month"].astype(str)
    sm_sums = clustered.groupby("season_month")["residual"].sum()
    if len(sm_sums) > 0 and pooled_sum != 0:
        largest_share = sm_sums.abs().max() / abs(pooled_sum)
    else:
        largest_share = np.nan

    return rows, largest_share


def bh_correction(pvalues, alpha=0.10):
    pv = np.array(pvalues)
    n = len(pv)
    if n == 0: return 0, np.array([], dtype=bool)
    sorted_idx = np.argsort(pv)
    sorted_pv = pv[sorted_idx]
    thresholds = alpha * np.arange(1, n + 1) / n
    mask = sorted_pv <= thresholds
    if mask.any():
        k = np.max(np.where(mask)) + 1
        bh_thresh = thresholds[k - 1]
    else:
        k = 0
        bh_thresh = 0
    survivors = np.zeros(n, dtype=bool)
    survivors[sorted_idx[:k]] = True
    return bh_thresh, survivors


def null_control(games):
    """Null: home team ML fires every game."""
    mask = games["home_win"].notna() & games["pin_close_fair_h"].notna()
    r = games.loc[mask, "home_win"].astype(float) - games.loc[mask, "pin_close_fair_h"]
    mean_r = r.mean()
    se = r.std(ddof=1) / np.sqrt(len(r))
    print(f"  NULL CONTROL: n={len(r)}, r={mean_r:+.4f}, SE={se:.4f}, "
          f"|r|<0.01: {'PASS' if abs(mean_r) < 0.01 else 'FAIL'}")
    return mean_r


def run_all(sport, games, features, config, tier_list, market_features=None):
    """Run Tier 1 + Tier 2 cells, return results list."""
    results = []

    if 1 in tier_list:
        cells = NHL_TIER1 if sport == "nhl" else NBA_TIER1
        print(f"\n--- {sport.upper()} Tier 1 ---")
        for cell_id, func in cells.items():
            print(f"  {cell_id}...", end=" ", flush=True)
            fired = func(games, features, config)
            if len(fired) == 0:
                print("0 fires")
                results.append({"cell_id": cell_id, "tier": 1, "sport": sport,
                               "n_fired": 0, "status": "NO_FIRES"})
                continue

            # Add season
            if "season" not in fired.columns and "commence_time" in fired.columns:
                fired["season"] = pd.to_datetime(fired["commence_time"]).apply(
                    lambda x: x.year if x.month >= 10 else x.year - 1
                )

            st = compute_stats(fired)
            roi = compute_roi(fired, games)
            bd, share = compute_breakdowns(fired, games) if st else ([], np.nan)

            if st is None:
                print(f"{len(fired)} raw fires, too few after clustering")
                results.append({"cell_id": cell_id, "tier": 1, "sport": sport,
                               "n_fired": len(fired), "status": "TOO_FEW"})
                continue

            r = {
                "cell_id": cell_id, "tier": 1, "sport": sport,
                "n_fired": st["n"], "mean_r": st["mean_r"], "se": st["se"],
                "p_one": st["p_one"], "season_pass": st["season_pass"],
                "same_sign": st["same_sign"], "share_largest_sm": share,
            }
            for s_key, s_val in st["per_season"].items():
                r[f"n_s{s_key}"] = s_val["n"]
                r[f"r_s{s_key}"] = s_val["mean_r"]

            if roi:
                r.update({f"roi_{k}": v for k, v in roi.items()})

            sign = "+" if st["mean_r"] > 0 else "−"
            roi_str = f"ROI={roi['roi']:+.3f} ({roi['n_priced']}p/{roi['n_excluded']}x)" if roi and roi["n_priced"] > 0 else "no priced"
            print(f"n={st['n']}, r={st['mean_r']:+.4f}, p={st['p_one']:.4f}, "
                  f"sign={'same' if st['same_sign'] else 'flip'}, {roi_str}")

            # Save fired rows
            fired_out = RESULTS_DIR / "fired"
            fired_out.mkdir(exist_ok=True)
            save_cols = ["event_id", "season", "cell_side", "residual",
                         "pin_close_total", "pin_close_ml_h", "pin_close_ml_a",
                         "pin_close_spread_h", "pin_close_spread_h_price",
                         "pin_close_spread_a_price", "over", "home_win", "home_covers",
                         "home_team", "away_team", "commence_time"]
            out_cols = [c for c in save_cols if c in fired.columns]
            fired[out_cols].to_parquet(fired_out / f"{cell_id}.parquet", index=False)

            results.append(r)

    if 2 in tier_list:
        print(f"\n--- {sport.upper()} Tier 2 ---")
        if sport == "nhl":
            t2_cells = generate_tier2_nhl(games, features, config, market_features=market_features)
        else:
            t2_cells = generate_tier2_nba(games, features, config, market_features=market_features)

        print(f"  Generated {len(t2_cells)} cells")
        for cell in t2_cells:
            fired = cell["data"]
            if "season" not in fired.columns and "commence_time" in fired.columns:
                fired = fired.copy()
                fired["season"] = pd.to_datetime(fired["commence_time"]).apply(
                    lambda x: x.year if x.month >= 10 else x.year - 1
                )

            st = compute_stats(fired, min_per_season=60)
            r = {
                "cell_id": cell["cell_id"], "tier": 2, "sport": sport,
                "feature": cell["feature"], "level": cell["level"], "side": cell["side"],
                "n_fired": cell["n_fired"],
                "not_bettable": cell.get("not_bettable", False),
            }
            if st:
                r.update({"mean_r": st["mean_r"], "se": st["se"], "p_one": st["p_one"],
                          "season_pass": st["season_pass"], "same_sign": st["same_sign"]})
                for s_key, s_val in st["per_season"].items():
                    r[f"n_s{s_key}"] = s_val["n"]
                    r[f"r_s{s_key}"] = s_val["mean_r"]

                # Save fired if ≥ 20 fires
                if st["n"] >= 20:
                    fired_out = RESULTS_DIR / "fired"
                    fired_out.mkdir(exist_ok=True)
                    save_cols = ["event_id", "season", "cell_side", "residual",
                                 "commence_time", "home_team", "away_team", "over",
                                 "home_win", "home_covers"]
                    out_cols = [c for c in save_cols if c in fired.columns]
                    fired[out_cols].to_parquet(
                        fired_out / f"{cell['cell_id']}.parquet", index=False)

            results.append(r)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--sport", nargs="+", default=["nhl", "nba"])
    parser.add_argument("--v2", action="store_true", help="Use screen_v2 results dir with market features")
    args = parser.parse_args()

    if args.v2:
        global RESULTS_DIR
        RESULTS_DIR = ROOT / "results" / "screen_v2"
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    config = load_config()
    all_results = []

    for sport in args.sport:
        print(f"\n{'='*60}\n  {sport.upper()} SCREEN\n{'='*60}")
        games = pd.read_parquet(DATA_DIR / f"games_{sport}.parquet")
        features = pd.read_parquet(DATA_DIR / f"features_{sport}.parquet")

        # Load v2 market features if available
        mf_path = DATA_DIR / f"market_features_{sport}.parquet"
        market_features = pd.read_parquet(mf_path) if mf_path.exists() else None
        if market_features is not None:
            print(f"  Loaded market features: {len(market_features)} rows, "
                  f"{len([c for c in market_features.columns if c != 'event_id'])} features")

        null_control(games)
        results = run_all(sport, games, features, config, args.tier, market_features=market_features)
        all_results.extend(results)

    # Save
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(RESULTS_DIR / "all_cells.csv", index=False)
    print(f"\nSaved {len(results_df)} cells to {RESULTS_DIR / 'all_cells.csv'}")

    # BH — two families per addendum §A
    print(f"\n--- BH CORRECTION (α=0.10) ---")
    family_path = Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/hunt_2026-09-30/family.csv"
    ledger = pd.read_csv(family_path)

    # Tier 1 family (confirmatory, 16 pre-registered cells)
    t1_mask = (results_df["tier"] == 1) & results_df["p_one"].notna()
    t1_pv = results_df.loc[t1_mask, "p_one"].values
    t1_ids = results_df.loc[t1_mask, "cell_id"].values
    if len(t1_pv) > 0:
        bh_thresh_t1, survivors_t1 = bh_correction(t1_pv, alpha=0.10)
        print(f"  Tier 1 family: {len(t1_pv)}, BH threshold: {bh_thresh_t1:.6f}, "
              f"Survivors: {survivors_t1.sum()}")
        if survivors_t1.sum() > 0:
            for sid, sp in sorted(zip(t1_ids[survivors_t1], t1_pv[survivors_t1]), key=lambda x: x[1]):
                print(f"    {sid}: p={sp:.6f}")
    else:
        bh_thresh_t1 = 0
        survivors_t1 = np.array([], dtype=bool)

    # Tier 2 + ledger family (exploratory)
    # Exclude f4 (NOT-BETTABLE) from BH
    t2_mask = (results_df["tier"] == 2) & results_df["p_one"].notna()
    if "not_bettable" in results_df.columns:
        t2_mask = t2_mask & ~results_df["not_bettable"].fillna(False)
    t2_pv = results_df.loc[t2_mask, "p_one"].values
    t2_ids = results_df.loc[t2_mask, "cell_id"].values

    all_pv = np.concatenate([t2_pv, ledger["p"].values])
    all_ids = np.concatenate([t2_ids, ledger["id"].values])

    bh_thresh, survivors = bh_correction(all_pv, alpha=0.10)
    print(f"  Tier 2 + ledger family: {len(all_pv)}, BH threshold: {bh_thresh:.6f}, "
          f"Survivors: {survivors.sum()}")
    if survivors.sum() > 0:
        for sid, sp in sorted(zip(all_ids[survivors], all_pv[survivors]), key=lambda x: x[1]):
            print(f"    {sid}: p={sp:.6f}")

    family_out = pd.DataFrame({"cell_id": all_ids, "p": all_pv, "bh_survivor": survivors})
    family_out.to_csv(RESULTS_DIR / "family.csv", index=False)

    # Also save Tier 1 family
    t1_family = pd.DataFrame({"cell_id": t1_ids, "p": t1_pv,
                               "bh_survivor": survivors_t1 if len(survivors_t1) > 0 else []})
    t1_family.to_csv(RESULTS_DIR / "family_tier1.csv", index=False)

    # f4 NOT-BETTABLE cells reported separately
    if "not_bettable" in results_df.columns:
        nb = results_df[results_df["not_bettable"].fillna(False)]
        if len(nb) > 0:
            print(f"\n  NOT-BETTABLE (f4 in-play reset, excluded from BH): {len(nb)} cells")
            for _, r in nb[nb["p_one"].notna()].sort_values("p_one").head(5).iterrows():
                print(f"    {r['cell_id']}: n={r['n_fired']}, r={r.get('mean_r', np.nan):+.4f}, "
                      f"p={r['p_one']:.4f}")

    # Power table
    print(f"\n--- POWER ---")
    power_rows = []
    for _, r in results_df[results_df["se"].notna()].iterrows():
        n = r["n_fired"]
        se = r["se"]
        mde_05 = stats.t.ppf(0.95, df=max(n - 1, 1)) * se if n > 1 else np.nan
        if bh_thresh > 0:
            z_bh = stats.norm.ppf(1 - bh_thresh)
            mde_bh = z_bh * se
        else:
            mde_bh = np.nan
        power_rows.append({
            "cell_id": r["cell_id"], "n": n, "se": se,
            "mde_p05": mde_05, "mde_bh": mde_bh,
        })
    power_df = pd.DataFrame(power_rows)
    power_df.to_csv(RESULTS_DIR / "power.csv", index=False)

    if len(power_df) > 0:
        se_120 = 0.5 / np.sqrt(120)
        mde_120_05 = stats.t.ppf(0.95, df=119) * se_120
        se_240 = 0.5 / np.sqrt(240)
        mde_240_05 = stats.t.ppf(0.95, df=239) * se_240
        print(f"  At 120 fires (60/season): MDE p<0.05 = {mde_120_05:.3f}")
        print(f"  At 240 fires: MDE p<0.05 = {mde_240_05:.3f}")
        if bh_thresh > 0:
            z_bh = stats.norm.ppf(1 - bh_thresh)
            print(f"  At 120 fires: MDE BH = {z_bh * se_120:.3f}")
            print(f"  At 240 fires: MDE BH = {z_bh * se_240:.3f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
