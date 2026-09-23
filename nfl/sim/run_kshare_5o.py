#!/usr/bin/env python3
"""
5O Item 4: k_share measured with the live usage formula (build_player_usage).

Discovery 2021-24, holdout 2025. Score each k_share in {20,40,80,120,160,240}
at weeks 2..9 against realised share that week.
"""
import sys, time, json, copy
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DISCOVERY = [2021, 2022, 2023, 2024]
HOLDOUT = [2025]
K_GRID = [20, 40, 80, 120, 160, 240]
WEEKS = list(range(2, 10))  # weeks 2..9
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"


def main():
    t0 = time.time()
    from nfl.sim.usage import (build_player_game_aggs, build_position_map,
                                compute_position_priors, build_active_universe,
                                load_pbp, load_roster_data, build_player_usage,
                                compute_season_share_data, derive_starting_qbs)

    params = json.load(open(PARAMS_PATH))

    # Load common data
    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()

    rosters, depth, injuries = load_roster_data()
    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    pos_map = build_position_map(rosters)
    rate_priors = compute_position_priors(rec, car, pos_map)
    roster_uni = rosters[rosters["position"].isin(["WR", "TE", "RB", "QB"])][
        ["season", "week", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(["season", "week", "player_id"])

    active = build_active_universe(rosters, injuries, depth)
    starting_qbs = derive_starting_qbs(depth, scrimmage, active_universe=active)

    depth_order_priors, player_season_shares = compute_season_share_data(
        active, rec, team_tgt, car, team_car)

    print(f"Data loaded in {time.time()-t0:.1f}s")

    # Build realised shares per player per week (from PBP)
    # target_share = n_targets_this_week / team_targets_this_week
    real_tgt = rec[["season", "week", "team", "player_id", "n_targets"]].copy()
    real_tgt = real_tgt.merge(team_tgt[["season", "week", "team", "team_targets"]],
                              on=["season", "week", "team"])
    real_tgt["real_share"] = real_tgt["n_targets"] / real_tgt["team_targets"].clip(lower=1)
    real_tgt["share_type"] = "target"

    real_car = car[["season", "week", "team", "player_id", "n_carries"]].copy()
    real_car = real_car.merge(team_car[["season", "week", "team", "team_carries"]],
                              on=["season", "week", "team"])
    real_car["real_share"] = real_car["n_carries"] / real_car["team_carries"].clip(lower=1)
    real_car["share_type"] = "carry"

    real_all = pd.concat([
        real_tgt[["season", "week", "team", "player_id", "real_share", "share_type"]],
        real_car[["season", "week", "team", "player_id", "real_share", "share_type"]],
    ], ignore_index=True)

    # Add position
    pm = pos_map[["player_id", "position"]].drop_duplicates("player_id")
    real_all = real_all.merge(pm, on="player_id", how="left")

    results = []

    for k_val in K_GRID:
        t_k = time.time()
        test_params = copy.deepcopy(params)
        test_params["usage"]["k_share"] = k_val

        # Build usage table with this k_share
        usage_df = build_player_usage(
            rec, team_tgt, car, team_car, pos_map, rate_priors, test_params,
            active_universe=active, roster_universe=roster_uni,
            depth_order_priors=depth_order_priors,
            player_season_shares=player_season_shares,
            starting_qbs=starting_qbs,
            output_seasons=DISCOVERY + HOLDOUT,
        )

        # Score: for each (season, week in 2..9), compare projected share vs realised
        for w in WEEKS:
            proj = usage_df[usage_df["week"] == w][
                ["season", "week", "team", "player_id", "target_share", "carry_share"]
            ].copy()
            if proj.empty:
                continue

            # Melt to long form
            proj_long = proj.melt(
                id_vars=["season", "week", "team", "player_id"],
                value_vars=["target_share", "carry_share"],
                var_name="share_col", value_name="proj_share"
            )
            proj_long["share_type"] = proj_long["share_col"].map({
                "target_share": "target", "carry_share": "carry"
            })

            # Join with realised
            scored = proj_long.merge(
                real_all[["season", "week", "team", "player_id", "real_share",
                          "share_type", "position"]],
                on=["season", "week", "team", "player_id", "share_type"],
                how="inner"
            )

            if scored.empty:
                continue

            for pos in ["WR", "TE", "RB"]:
                for st in ["target", "carry"]:
                    sub = scored[(scored["position"] == pos) & (scored["share_type"] == st)]
                    if len(sub) < 10:
                        continue
                    for sg, seasons in [("discovery", DISCOVERY), ("holdout", HOLDOUT)]:
                        s_sub = sub[sub["season"].isin(seasons)]
                        if len(s_sub) < 5:
                            continue
                        mae = (s_sub["proj_share"] - s_sub["real_share"]).abs().mean()
                        results.append({
                            "k_share": k_val, "week": w, "pos": pos,
                            "share_type": st, "group": sg, "mae": mae,
                            "n": len(s_sub),
                        })

        print(f"  k_share={k_val}: {time.time()-t_k:.1f}s")

    rdf = pd.DataFrame(results)

    # Pick best k_share on pooled discovery for each (pos, share_type, week)
    disc = rdf[rdf["group"] == "discovery"]
    hold = rdf[rdf["group"] == "holdout"]

    # Aggregate: for each (pos, share_type), average MAE across weeks 2-5
    # (the range where shrinkage matters most) on discovery
    disc_agg = disc[disc["week"].between(2, 5)].groupby(
        ["k_share", "pos", "share_type"]
    )["mae"].mean().reset_index()

    best_picks = {}
    for (pos, st), grp in disc_agg.groupby(["pos", "share_type"]):
        best = grp.loc[grp["mae"].idxmin()]
        best_picks[(pos, st)] = int(best["k_share"])

    # Report
    print(f"\n{'='*70}")
    print(f"DISCOVERY: best k_share (pooled 2021-24, weeks 2-5 avg)")
    print(f"{'='*70}")
    for (pos, st), k in sorted(best_picks.items()):
        print(f"  {pos} {st}: k_share = {k}")

    # Overall best (single number, all positions)
    overall_best = disc[disc["week"].between(2, 5)].groupby("k_share")["mae"].mean()
    overall_k = int(overall_best.idxmin())
    print(f"\n  OVERALL best (single number): k_share = {overall_k}")

    # Holdout at best k vs k=20
    print(f"\n{'='*70}")
    print(f"HOLDOUT (2025): MAE at k={overall_k} vs k=20")
    print(f"{'='*70}")
    print(f"{'pos':3s} {'share':6s} {'week':4s} {'k=20':>8s} {'k='+str(overall_k):>8s} {'red%':>8s}")
    print("-" * 40)

    for pos in ["WR", "TE", "RB"]:
        for st in ["target", "carry"]:
            for w in WEEKS:
                h20 = hold[(hold["k_share"] == 20) & (hold["pos"] == pos) &
                           (hold["share_type"] == st) & (hold["week"] == w)]
                hbest = hold[(hold["k_share"] == overall_k) & (hold["pos"] == pos) &
                             (hold["share_type"] == st) & (hold["week"] == w)]
                if h20.empty or hbest.empty:
                    continue
                m20 = h20["mae"].iloc[0]
                mb = hbest["mae"].iloc[0]
                red = (1 - mb / m20) * 100 if m20 > 0 else 0
                print(f"{pos:3s} {st:6s} {w:4d} {m20:8.5f} {mb:8.5f} {red:+7.1f}%")

    print(f"\nTotal runtime: {time.time()-t0:.0f}s ({(time.time()-t0)/60:.1f} min)")


if __name__ == "__main__":
    main()
