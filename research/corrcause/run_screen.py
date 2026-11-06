#!/usr/bin/env python3
"""
CC-1 Item 2: Run the DEV screen on Tier 1 and Tier 2 cells.

Usage:
    python3 run_screen.py --tier 1 --sport nhl
    python3 run_screen.py --tier 2 --sport nba
    python3 run_screen.py --tier 1 2 --sport nhl nba
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
RESULTS_DIR = ROOT / "results" / "screen_v1"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

from research.corrcause.build_tables import (
    american_to_implied, american_to_decimal, v_american_to_implied,
    v_american_to_decimal, SOFT_BOOKS
)
from research.corrcause.cells import (
    load_config, NHL_TIER1, NBA_TIER1,
    generate_tier2_nhl, generate_tier2_nba
)


def compute_residual_stats(fired, min_per_season=60):
    """Compute cell statistics: mean residual, SE, p-value, per-season breakdown."""
    if len(fired) == 0 or "residual" not in fired.columns:
        return None

    r = fired["residual"].dropna()
    if len(r) < 20:
        return None

    n = len(r)
    mean_r = r.mean()
    se = r.std(ddof=1) / np.sqrt(n)

    # One-sided p-value (in the registered direction = positive residual)
    if se > 0:
        t_stat = mean_r / se
        p_one = 1 - stats.t.cdf(t_stat, df=n-1)
    else:
        p_one = np.nan

    # Per season
    per_season = {}
    if "season" in fired.columns:
        for s, grp in fired.groupby("season"):
            sr = grp["residual"].dropna()
            per_season[s] = {
                "n": len(sr),
                "mean_r": sr.mean(),
                "se": sr.std(ddof=1) / np.sqrt(len(sr)) if len(sr) > 1 else np.nan,
                "sign": "+" if sr.mean() > 0 else "-",
            }

    # Check: ≥ 60 fires per DEV season
    season_pass = all(v["n"] >= min_per_season for v in per_season.values())
    # Same sign both seasons
    signs = [v["sign"] for v in per_season.values()]
    same_sign = len(set(signs)) == 1 if len(signs) >= 2 else False

    return {
        "n": n,
        "mean_r": mean_r,
        "se": se,
        "p_one": p_one,
        "per_season": per_season,
        "season_pass": season_pass,
        "same_sign": same_sign,
    }


def compute_roi(fired, games):
    """Compute ROI at the best soft price."""
    if len(fired) == 0 or "cell_side" not in fired.columns:
        return None

    side = fired["cell_side"].iloc[0]
    wins = 0.0
    losses = 0.0
    n_bets = 0

    for _, row in fired.iterrows():
        eid = row["event_id"]
        game_row = games[games["event_id"] == eid]
        if len(game_row) == 0:
            continue
        g = game_row.iloc[0]

        # Determine if we won
        if "over" in side:
            won = row.get("over", g.get("over"))
            if pd.isna(won): continue
            won = bool(won)
        elif "under" in side:
            won = not bool(row.get("over", g.get("over")))
        elif "home_ml" in side:
            won = bool(g.get("home_win"))
        elif "away_ml" in side:
            won = not bool(g.get("home_win"))
        elif "home_ats" in side:
            won = bool(g.get("home_covers"))
            if pd.isna(g.get("home_covers")): continue
        elif "away_ats" in side:
            won = not bool(g.get("home_covers"))
            if pd.isna(g.get("home_covers")): continue
        else:
            continue

        # Find best soft price
        best_dec = -999
        if "over" in side:
            for book in SOFT_BOOKS:
                col = f"soft_{book}_close_over_price"
                if col in g.index and not pd.isna(g[col]):
                    dec = american_to_decimal(g[col])
                    if not pd.isna(dec) and dec > best_dec:
                        best_dec = dec
        elif "under" in side:
            for book in SOFT_BOOKS:
                col = f"soft_{book}_close_under_price"
                if col in g.index and not pd.isna(g[col]):
                    dec = american_to_decimal(g[col])
                    if not pd.isna(dec) and dec > best_dec:
                        best_dec = dec
        elif "home_ml" in side:
            for book in SOFT_BOOKS:
                col = f"soft_{book}_close_ml_h"
                if col in g.index and not pd.isna(g[col]):
                    dec = american_to_decimal(g[col])
                    if not pd.isna(dec) and dec > best_dec:
                        best_dec = dec
        elif "away_ml" in side:
            for book in SOFT_BOOKS:
                col = f"soft_{book}_close_ml_a"
                if col in g.index and not pd.isna(g[col]):
                    dec = american_to_decimal(g[col])
                    if not pd.isna(dec) and dec > best_dec:
                        best_dec = dec
        elif "ats" in side:
            # ATS: use spread prices
            price_col = "spread_h_price" if "home" in side else "spread_a_price"
            for book in SOFT_BOOKS:
                col = f"soft_{book}_close_{price_col}"
                if col in g.index and not pd.isna(g[col]):
                    dec = american_to_decimal(g[col])
                    if not pd.isna(dec) and dec > best_dec:
                        best_dec = dec

        if best_dec <= 0:
            best_dec = 1.909  # default -110
        n_bets += 1
        if won:
            wins += (best_dec - 1)
        else:
            losses += 1

    if n_bets == 0:
        return None
    roi = (wins - losses) / n_bets
    return {"n_bets": n_bets, "roi": roi, "wins": wins, "losses": losses}


def run_tier1(sport, games, features, config):
    """Run all Tier 1 cells for a sport."""
    cells = NHL_TIER1 if sport == "nhl" else NBA_TIER1
    results = []

    for cell_id, func in cells.items():
        print(f"  {cell_id}...", end=" ")
        fired = func(games, features, config)
        if len(fired) == 0:
            print(f"SKIP (no fires or missing data)")
            results.append({"cell_id": cell_id, "tier": 1, "sport": sport, "status": "SKIP"})
            continue

        # Add season column
        if "season" not in fired.columns and "commence_time" in fired.columns:
            fired["season"] = pd.to_datetime(fired["commence_time"]).apply(
                lambda x: x.year if x.month >= 10 else x.year - 1
            )

        stats_result = compute_residual_stats(fired)
        roi_result = compute_roi(fired, games)

        if stats_result is None:
            print(f"SKIP (too few fires: {len(fired)})")
            results.append({"cell_id": cell_id, "tier": 1, "sport": sport, "status": "SKIP",
                           "n_fired": len(fired)})
            continue

        result = {
            "cell_id": cell_id,
            "tier": 1,
            "sport": sport,
            "n_fired": stats_result["n"],
            "mean_r": stats_result["mean_r"],
            "se": stats_result["se"],
            "p_one": stats_result["p_one"],
            "season_pass": stats_result["season_pass"],
            "same_sign": stats_result["same_sign"],
            "per_season": stats_result["per_season"],
        }
        if roi_result:
            result["roi"] = roi_result["roi"]
            result["n_bets"] = roi_result["n_bets"]

        sign = "+" if stats_result["mean_r"] > 0 else "-"
        print(f"n={stats_result['n']}, r={stats_result['mean_r']:+.4f}, "
              f"p={stats_result['p_one']:.4f}, same_sign={stats_result['same_sign']}, "
              f"ROI={roi_result['roi']:+.3f}" if roi_result else "")
        results.append(result)

    return results


def run_tier2(sport, games, features, config):
    """Run all Tier 2 cells for a sport."""
    if sport == "nhl":
        cells = generate_tier2_nhl(games, features, config)
    else:
        cells = generate_tier2_nba(games, features, config)

    print(f"  Generated {len(cells)} Tier 2 cells")
    results = []

    for cell in cells:
        fired = cell["data"]
        if "season" not in fired.columns and "commence_time" in fired.columns:
            fired["season"] = pd.to_datetime(fired["commence_time"]).apply(
                lambda x: x.year if x.month >= 10 else x.year - 1
            )

        stats_result = compute_residual_stats(fired, min_per_season=60)
        if stats_result is None:
            results.append({
                "cell_id": cell["cell_id"],
                "tier": 2,
                "sport": sport,
                "n_fired": len(fired),
                "status": "SKIP",
            })
            continue

        result = {
            "cell_id": cell["cell_id"],
            "tier": 2,
            "sport": sport,
            "feature": cell["feature"],
            "level": cell["level"],
            "side": cell["side"],
            "n_fired": stats_result["n"],
            "mean_r": stats_result["mean_r"],
            "se": stats_result["se"],
            "p_one": stats_result["p_one"],
            "season_pass": stats_result["season_pass"],
            "same_sign": stats_result["same_sign"],
        }
        results.append(result)

    return results


def bh_correction(pvalues, alpha=0.10):
    """Benjamini-Hochberg correction. Returns threshold and mask of survivors."""
    pv = np.array(pvalues)
    n = len(pv)
    if n == 0:
        return 0, np.array([], dtype=bool)
    sorted_idx = np.argsort(pv)
    sorted_pv = pv[sorted_idx]
    thresholds = alpha * np.arange(1, n + 1) / n
    # Find the largest k where p(k) <= threshold(k)
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


def null_control(games, features):
    """Null control: 'home team' cell — fires on every game, side home ML."""
    mask = games["home_win"].notna() & games["pin_close_fair_h"].notna()
    fired = games[mask].copy()
    fired["residual"] = fired["home_win"].astype(float) - fired["pin_close_fair_h"]
    r = fired["residual"].dropna()
    mean_r = r.mean()
    se = r.std(ddof=1) / np.sqrt(len(r))
    print(f"  NULL CONTROL (home team): n={len(r)}, mean_r={mean_r:+.4f}, "
          f"SE={se:.4f}, within ±0.01: {'PASS' if abs(mean_r) < 0.01 else 'FAIL'}")
    return mean_r, se


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--sport", nargs="+", default=["nhl", "nba"])
    args = parser.parse_args()

    config = load_config()
    all_results = []

    for sport in args.sport:
        print(f"\n{'='*60}")
        print(f"  {sport.upper()} SCREEN")
        print(f"{'='*60}")

        games = pd.read_parquet(DATA_DIR / f"games_{sport}.parquet")
        features = pd.read_parquet(DATA_DIR / f"features_{sport}.parquet")

        # Null control
        null_control(games, features)

        if 1 in args.tier:
            print(f"\n--- Tier 1 ---")
            t1_results = run_tier1(sport, games, features, config)
            all_results.extend(t1_results)

        if 2 in args.tier:
            print(f"\n--- Tier 2 ---")
            t2_results = run_tier2(sport, games, features, config)
            all_results.extend(t2_results)

    # Save results
    results_df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "per_season"}
        for r in all_results
    ])
    results_df.to_csv(RESULTS_DIR / "all_cells.csv", index=False)
    print(f"\nSaved {len(results_df)} cell results to {RESULTS_DIR / 'all_cells.csv'}")

    # BH correction across the whole family
    print(f"\n--- BH CORRECTION (family-wide, α=0.10) ---")

    # Load NHL ledger family.csv
    family_path = Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/hunt_2026-09-30/family.csv"
    ledger = pd.read_csv(family_path)
    print(f"  NHL ledger: {len(ledger)} existing p-values")

    # Combine all p-values
    cc_pvalues = results_df[results_df["p_one"].notna()]["p_one"].values
    cc_ids = results_df[results_df["p_one"].notna()]["cell_id"].values
    ledger_pvalues = ledger["p"].values
    ledger_ids = ledger["id"].values

    all_pv = np.concatenate([cc_pvalues, ledger_pvalues])
    all_ids = np.concatenate([cc_ids, ledger_ids])

    bh_thresh, survivors = bh_correction(all_pv, alpha=0.10)
    print(f"  Total family size: {len(all_pv)}")
    print(f"  BH threshold: {bh_thresh:.6f}")
    print(f"  Survivors: {survivors.sum()}")

    if survivors.sum() > 0:
        surv_ids = all_ids[survivors]
        surv_pv = all_pv[survivors]
        for sid, sp in sorted(zip(surv_ids, surv_pv), key=lambda x: x[1]):
            print(f"    {sid}: p={sp:.6f}")

    # Save family table
    family_out = pd.DataFrame({
        "cell_id": all_ids,
        "p": all_pv,
        "bh_survivor": survivors,
    })
    family_out.to_csv(RESULTS_DIR / "family.csv", index=False)
    print(f"\n  Family table saved to {RESULTS_DIR / 'family.csv'}")


if __name__ == "__main__":
    main()
