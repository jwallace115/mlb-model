#!/usr/bin/env python3
"""
5R Item 2: Measure k_pace and k_tendency on 2021-24, report 2025 holdout.

For each k in {25, 50, 100, 200, 400, 800}, build the weekly tendency tables
for 2021-25 using the modified build_tendencies, and for every team-week 2..18
score the projected pace/PROE against that week's realised value.

Pick k on POOLED 2021-24, report the 2025 holdout at the pick vs k=200 (PROE)
and vs the current unshrunk rule (pace).
"""
import sys, json, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.ratings import build_tendencies, _shrink

DISCOVERY_SEASONS = [2021, 2022, 2023, 2024]
HOLDOUT_SEASON = 2025
ALL_SEASONS = DISCOVERY_SEASONS + [HOLDOUT_SEASON]
K_VALUES = [25, 50, 100, 200, 400, 800]


def load_data():
    """Load scrimmage plays and all plays for 2020-2025."""
    frames_scrim = []
    frames_all = []
    for s in range(2020, 2026):
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        df = df[df["season_type"] == "REG"]
        scrim = df[df["play_type"].isin(["pass", "run"])].copy()
        frames_scrim.append(scrim)
        frames_all.append(df)
    return pd.concat(frames_scrim, ignore_index=True), pd.concat(frames_all, ignore_index=True)


def compute_realized(scrimmage):
    """Compute realised pace and PROE for each team-week.

    Derivation: PROE = mean(pass_oe) for that team's scrimmage plays in that
    week's game. Pace = mean of play-to-play time diffs in neutral-score
    Q1-3 situations (same filter as build_tendencies), within the week's game.
    """
    rows = []
    for (season, week, team), gdf in scrimmage.groupby(["season", "week", "posteam"]):
        if week < 2 or week > 18:
            continue
        # PROE
        valid = gdf[gdf["pass_oe"].notna()]
        proe = valid["pass_oe"].mean() if len(valid) else 0.0
        # Pace
        neutral = gdf[(gdf["score_differential"].abs() <= 8) & gdf["qtr"].isin([1, 2, 3])]
        pace = np.nan
        if len(neutral) > 5 and "game_seconds_remaining" in neutral.columns:
            diffs = neutral.sort_values("game_seconds_remaining", ascending=False)[
                "game_seconds_remaining"].diff().abs()
            vd = diffs[(diffs > 5) & (diffs < 60)]
            if len(vd):
                pace = vd.mean()
        rows.append({"season": season, "week": int(week), "team": team,
                      "real_proe": proe, "real_pace": pace})
    return pd.DataFrame(rows)


def main():
    t0 = time.time()

    with open(ROOT / "nfl" / "sim" / "params_v1.json") as f:
        base_params = json.load(f)

    print("Loading PBP 2020-2025...")
    scrimmage, all_plays = load_data()
    print(f"  Scrimmage: {len(scrimmage)} plays")

    # League means (needed by build_tendencies)
    from nfl.sim.ratings import compute_league_means, OUTPUT_SEASONS as OS
    league_means = compute_league_means(scrimmage)

    # Fourth-down table (needed by build_tendencies)
    fd_path = ROOT / "nfl" / "data" / "sim" / "tables" / "fourth_down.parquet"
    fd_table = pd.read_parquet(fd_path) if fd_path.exists() else None

    # Compute realised values
    print("Computing realised pace/PROE per team-week...")
    realized = compute_realized(scrimmage)
    print(f"  {len(realized)} team-week observations")

    # Also compute the CURRENT unshrunk-pace baseline for comparison
    # (the default before 5R: pace is raw mean, not shrunk)
    # This is just the existing tendencies_weekly.parquet
    existing = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "tendencies_weekly.parquet")

    # ---- Measure k_pace and k_tendency ----
    results = []
    for k_pace in K_VALUES:
        for k_tendency in K_VALUES:
            params = base_params.copy()
            params["k_pace"] = k_pace
            params["k_tendency"] = k_tendency

            # Build tendencies with these k values
            tend = build_tendencies(scrimmage, all_plays, params, league_means,
                                     fourth_down_table=fd_table)

            # Score: for each team-week 2..18, compare projected vs realized
            merged = tend.merge(realized, on=["season", "week", "team"], how="inner")
            merged = merged[(merged["week"] >= 2) & (merged["week"] <= 18)]

            for scope, mask in [("discovery", merged["season"].isin(DISCOVERY_SEASONS)),
                                ("holdout", merged["season"] == HOLDOUT_SEASON)]:
                sub = merged[mask]
                if len(sub) == 0:
                    continue
                valid_pace = sub[sub["real_pace"].notna()]
                pace_mae = (valid_pace["pace_sec"] - valid_pace["real_pace"]).abs().mean() if len(valid_pace) else np.nan
                proe_mae = (sub["proe"] - sub["real_proe"]).abs().mean()

                results.append({
                    "k_pace": k_pace, "k_tendency": k_tendency,
                    "scope": scope, "n": len(sub),
                    "pace_mae": pace_mae, "proe_mae": proe_mae,
                })

    rdf = pd.DataFrame(results)

    # ---- Pick best k on discovery ----
    disc = rdf[rdf["scope"] == "discovery"]

    # Best k_pace: fix k_tendency at 200 (its current value), vary k_pace
    print(f"\n{'='*80}")
    print("PACE MAE by k_pace (k_tendency=200, discovery 2021-24)")
    print(f"{'='*80}")
    print(f"{'k_pace':>8s} {'MAE':>8s}")
    pace_at_200 = disc[disc["k_tendency"] == 200].sort_values("k_pace")
    for _, r in pace_at_200.iterrows():
        print(f"{int(r['k_pace']):8d} {r['pace_mae']:8.3f}")
    best_k_pace = int(pace_at_200.loc[pace_at_200["pace_mae"].idxmin(), "k_pace"])
    print(f"Best k_pace: {best_k_pace}")

    # Best k_tendency: fix k_pace at best, vary k_tendency
    print(f"\n{'='*80}")
    print(f"PROE MAE by k_tendency (k_pace={best_k_pace}, discovery 2021-24)")
    print(f"{'='*80}")
    print(f"{'k_tend':>8s} {'MAE':>8s}")
    proe_at_best = disc[disc["k_pace"] == best_k_pace].sort_values("k_tendency")
    for _, r in proe_at_best.iterrows():
        print(f"{int(r['k_tendency']):8d} {r['proe_mae']:8.3f}")
    best_k_tendency = int(proe_at_best.loc[proe_at_best["proe_mae"].idxmin(), "k_tendency"])
    print(f"Best k_tendency: {best_k_tendency}")

    # ---- Holdout comparison ----
    print(f"\n{'='*80}")
    print(f"HOLDOUT (2025) at picked k vs baselines")
    print(f"{'='*80}")
    ho = rdf[rdf["scope"] == "holdout"]
    ho_best = ho[(ho["k_pace"] == best_k_pace) & (ho["k_tendency"] == best_k_tendency)]
    ho_200 = ho[(ho["k_pace"] == 200) & (ho["k_tendency"] == 200)]

    if len(ho_best) > 0 and len(ho_200) > 0:
        print(f"  Pace MAE at k_pace={best_k_pace}: {ho_best.iloc[0]['pace_mae']:.3f}")
        print(f"  Pace MAE at k_pace=200: {ho_200.iloc[0]['pace_mae']:.3f}")

        # Current unshrunk baseline for pace
        ex_ho = existing[(existing["season"] == HOLDOUT_SEASON) &
                         (existing["week"] >= 2) & (existing["week"] <= 18)]
        ex_merged = ex_ho.merge(realized[realized["season"] == HOLDOUT_SEASON],
                                on=["season", "week", "team"], how="inner")
        valid_ex = ex_merged[ex_merged["real_pace"].notna()]
        unshrunk_pace_mae = (valid_ex["pace_sec"] - valid_ex["real_pace"]).abs().mean()
        print(f"  Pace MAE unshrunk (current): {unshrunk_pace_mae:.3f}")

        # Week-1 default baseline for pace
        default_mae = realized[(realized["season"] == HOLDOUT_SEASON) &
                                realized["real_pace"].notna()]
        default_pace_mae = (28.0 - default_mae["real_pace"]).abs().mean()
        print(f"  Pace MAE at 28.0 default (wk1 only applicable to wk1 forecast): {default_pace_mae:.3f}")

        # PROE
        print(f"\n  PROE MAE at k_tendency={best_k_tendency}: {ho_best.iloc[0]['proe_mae']:.3f}")
        print(f"  PROE MAE at k_tendency=200: {ho_200.iloc[0]['proe_mae']:.3f}")

    # Save results
    out_path = ROOT / "research" / "nfl_sim" / "phase5r_tendency_k_results.parquet"
    rdf.to_parquet(out_path, index=False)
    print(f"\nSaved {out_path}")

    total = time.time() - t0
    print(f"Runtime: {total:.0f}s ({total/60:.1f} min)")
    print(f"\nPICKED: k_pace={best_k_pace}, k_tendency={best_k_tendency}")


if __name__ == "__main__":
    main()
