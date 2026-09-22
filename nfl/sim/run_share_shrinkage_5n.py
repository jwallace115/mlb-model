#!/usr/bin/env python3
"""
5N Item 2: Share shrinkage re-measured without survivorship, at weeks 1..k,
by prior-team status. No engine or usage change.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DISCOVERY = [2021, 2022, 2023, 2024]
HOLDOUT = [2025]


def build_shares():
    """Build per-player per-season per-week target/carry shares from PBP."""
    frames = []
    for s in DISCOVERY + HOLDOUT:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        scrim = df[df["play_type"].isin(["pass", "run"])].copy()

        # Targets per player per week
        tgt = scrim[scrim["pass_attempt"] == 1].groupby(
            ["season", "week", "posteam", "receiver_player_id"]
        ).size().reset_index(name="count")
        tgt.rename(columns={"receiver_player_id": "player_id"}, inplace=True)
        tgt["share_type"] = "target"

        # Team totals per week for targets
        team_tgt = scrim[scrim["pass_attempt"] == 1].groupby(
            ["season", "week", "posteam"]
        ).size().reset_index(name="team_total")
        tgt = tgt.merge(team_tgt, on=["season", "week", "posteam"])
        tgt["share"] = tgt["count"] / tgt["team_total"].clip(lower=1)

        # Carries per player per week
        rush = scrim[scrim["rush_attempt"] == 1]
        if "qb_scramble" in rush.columns:
            rush = rush[rush["qb_scramble"] != 1]
        car = rush.groupby(
            ["season", "week", "posteam", "rusher_player_id"]
        ).size().reset_index(name="count")
        car.rename(columns={"rusher_player_id": "player_id"}, inplace=True)
        car["share_type"] = "carry"

        team_car = rush.groupby(
            ["season", "week", "posteam"]
        ).size().reset_index(name="team_total")
        car = car.merge(team_car, on=["season", "week", "posteam"])
        car["share"] = car["count"] / car["team_total"].clip(lower=1)

        frames.append(pd.concat([tgt, car], ignore_index=True))

    all_df = pd.concat(frames, ignore_index=True)

    # Add position from usage table
    pu_path = ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet"
    if pu_path.exists():
        pu = pd.read_parquet(pu_path, columns=["player_id", "position"]).drop_duplicates("player_id")
        all_df = all_df.merge(pu, on="player_id", how="left")

    return all_df


def compute_prior_season_share(all_df):
    """Full-season share (weeks 1-18) for each player-season."""
    season_shares = (
        all_df.groupby(["season", "player_id", "share_type", "posteam"])
        .agg(total_count=("count", "sum"), total_team=("team_total", "sum"))
        .reset_index()
    )
    season_shares["full_share"] = season_shares["total_count"] / season_shares["total_team"].clip(lower=1)
    return season_shares


def main():
    print("Building shares from PBP...")
    all_df = build_shares()
    season_shares = compute_prior_season_share(all_df)

    results = []
    for share_type in ["target", "carry"]:
        for pos in ["WR", "TE", "RB"]:
            for k in [1, 2, 3, 4]:
                for split in DISCOVERY + HOLDOUT:
                    sdf = all_df[(all_df["share_type"] == share_type) &
                                 (all_df["position"] == pos) &
                                 (all_df["season"] == split)]

                    # s_k: cumulative share over weeks 1..k
                    wk_in = sdf[sdf["week"].between(1, k)]
                    wk_out = sdf[sdf["week"].between(k + 1, 8)]

                    if wk_in.empty or wk_out.empty:
                        continue

                    # Per-player cumulative share
                    player_in = wk_in.groupby("player_id").agg(
                        count_in=("count", "sum"), team_in=("team_total", "sum"),
                        team=("posteam", "first")
                    ).reset_index()
                    player_in["s_k"] = player_in["count_in"] / player_in["team_in"].clip(lower=1)

                    player_out = wk_out.groupby("player_id").agg(
                        count_out=("count", "sum"), team_out=("team_total", "sum"),
                        n_weeks_out=("week", "nunique")
                    ).reset_index()
                    player_out["s_out"] = player_out["count_out"] / player_out["team_out"].clip(lower=1)

                    # Must have at least one week in 2-8
                    merged = player_in.merge(player_out, on="player_id")
                    if merged.empty:
                        continue

                    # Add prior season full share
                    prior = season_shares[(season_shares["season"] == split - 1) &
                                          (season_shares["share_type"] == share_type)]
                    merged = merged.merge(
                        prior[["player_id", "full_share", "posteam"]].rename(
                            columns={"full_share": "s0", "posteam": "prior_team"}),
                        on="player_id", how="left"
                    )
                    merged["same_team"] = merged["team"] == merged["prior_team"]
                    merged["has_s0"] = merged["s0"].notna()

                    has_s0 = merged[merged["has_s0"]]
                    no_s0 = merged[~merged["has_s0"]]

                    if len(has_s0) < 5:
                        continue

                    # Grid search for optimal w
                    best_w, best_mae = None, float("inf")
                    for w10 in range(11):
                        w = w10 / 10.0
                        p_w = w * has_s0["s0"] + (1 - w) * has_s0["s_k"]
                        mae = ((p_w - has_s0["s_out"]).abs() * has_s0["n_weeks_out"]).sum() / has_s0["n_weeks_out"].sum()
                        if mae < best_mae:
                            best_w, best_mae = w, mae
                    mae_w0 = ((has_s0["s_k"] - has_s0["s_out"]).abs() * has_s0["n_weeks_out"]).sum() / has_s0["n_weeks_out"].sum()
                    mae_w0_uw = (has_s0["s_k"] - has_s0["s_out"]).abs().mean()
                    best_mae_uw = best_mae  # simplified

                    results.append({
                        "share_type": share_type, "pos": pos, "k": k,
                        "season_group": "discovery" if split in DISCOVERY else "holdout",
                        "season": split, "n_with_s0": len(has_s0), "n_without_s0": len(no_s0),
                        "best_w": best_w, "best_mae": best_mae, "mae_w0": mae_w0,
                        "reduction": 1 - best_mae / mae_w0 if mae_w0 > 0 else 0,
                        "n_same_team": has_s0["same_team"].sum(),
                        "n_changed_team": (~has_s0["same_team"]).sum(),
                    })

    rdf = pd.DataFrame(results)

    # Aggregate across seasons for discovery and holdout
    for group in ["discovery", "holdout"]:
        gdf = rdf[rdf["season_group"] == group]
        if gdf.empty:
            continue
        print(f"\n{'='*70}")
        print(f"{group.upper()}")
        print(f"{'='*70}")
        agg = gdf.groupby(["share_type", "pos", "k"]).agg(
            n=("n_with_s0", "sum"),
            best_w=("best_w", "mean"),
            reduction=("reduction", "mean"),
        ).reset_index()
        for st in ["target", "carry"]:
            for pos in ["WR", "TE", "RB"]:
                sub = agg[(agg["share_type"] == st) & (agg["pos"] == pos)]
                if sub.empty:
                    continue
                print(f"\n{pos} {st} share:")
                for _, r in sub.iterrows():
                    print(f"  k={int(r['k'])}: n={int(r['n']):4d}, w={r['best_w']:.1f}, reduction={r['reduction']*100:.1f}%")

    # Week 3 2026: fraction without prior season
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    wk3 = pu[(pu["season"] == 2026) & (pu["week"] <= 3)]
    n_players = wk3["player_id"].nunique()
    prior_ids = set(pu[pu["season"] == 2025]["player_id"].unique())
    wk3_pids = set(wk3["player_id"].unique())
    n_with = len(wk3_pids & prior_ids)
    n_without = len(wk3_pids - prior_ids)
    print(f"\nWeek 3 2026 board: {n_players} players, "
          f"{n_with} ({n_with/max(n_players,1)*100:.0f}%) with prior season, "
          f"{n_without} ({n_without/max(n_players,1)*100:.0f}%) without")


if __name__ == "__main__":
    main()
