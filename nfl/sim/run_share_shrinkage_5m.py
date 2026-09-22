#!/usr/bin/env python3
"""
5M Item 4: Measure the week-1 share shrinkage hypothesis.

Per player-season with >= 8 games: target/carry share in week 1 (s1),
prior season (s0, if >= 8 games), and realised over weeks 2-8 (s_out).
Discovery on 2021-24. Holdout 2025.
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
    """Build per-player per-season target/carry shares from PBP."""
    frames = []
    for s in DISCOVERY + HOLDOUT:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        scrim = df[df["play_type"].isin(["pass", "run"])].copy()
        # Targets: receiver_player_id where pass_attempt == 1
        tgt = scrim[scrim["pass_attempt"] == 1].groupby(
            ["season", "week", "posteam", "receiver_player_id"]
        ).size().reset_index(name="targets")
        tgt.rename(columns={"receiver_player_id": "player_id"}, inplace=True)
        # Carries: rusher_player_id where rush_attempt == 1 and qb_scramble != 1
        rush = scrim[(scrim["rush_attempt"] == 1)]
        if "qb_scramble" in rush.columns:
            rush = rush[rush["qb_scramble"] != 1]
        car = rush.groupby(
            ["season", "week", "posteam", "rusher_player_id"]
        ).size().reset_index(name="carries")
        car.rename(columns={"rusher_player_id": "player_id"}, inplace=True)
        frames.append({"tgt": tgt, "car": car})

    tgt_all = pd.concat([f["tgt"] for f in frames], ignore_index=True)
    car_all = pd.concat([f["car"] for f in frames], ignore_index=True)

    results = []
    for share_type, df, count_col in [("target", tgt_all, "targets"), ("carry", car_all, "carries")]:
        # Team totals per week
        team_tot = df.groupby(["season", "week", "posteam"])[count_col].sum().reset_index(name="team_total")
        merged = df.merge(team_tot, on=["season", "week", "posteam"])
        merged["share"] = merged[count_col] / merged["team_total"].clip(lower=1)

        for (s, pid), grp in merged.groupby(["season", "player_id"]):
            n_games = grp["week"].nunique()
            if n_games < 8:
                continue
            wk1 = grp[grp["week"] == 1]
            wk28 = grp[(grp["week"] >= 2) & (grp["week"] <= 8)]
            if len(wk1) == 0 or len(wk28) == 0:
                continue
            s1 = wk1["share"].mean()
            s_out = wk28["share"].mean()
            results.append({
                "season": s, "player_id": pid, "share_type": share_type,
                "s1": s1, "s_out": s_out, "n_games": n_games,
                "team": grp["posteam"].iloc[0],
            })

    rdf = pd.DataFrame(results)

    # Add prior-season share (s0)
    rdf["s0"] = np.nan
    for i, row in rdf.iterrows():
        prior = rdf[(rdf["player_id"] == row["player_id"]) &
                    (rdf["season"] == row["season"] - 1) &
                    (rdf["share_type"] == row["share_type"])]
        if len(prior) > 0:
            rdf.at[i, "s0"] = prior.iloc[0]["s_out"]  # Use wk2-8 of prior season

    # Add position from usage table
    pu_path = ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet"
    if pu_path.exists():
        pu = pd.read_parquet(pu_path, columns=["player_id", "position"]).drop_duplicates("player_id")
        rdf = rdf.merge(pu, on="player_id", how="left")

    return rdf


def main():
    print("Building shares from PBP...")
    rdf = build_shares()
    print(f"Total: {len(rdf)} player-seasons")

    disc = rdf[rdf["season"].isin(DISCOVERY)]
    hold = rdf[rdf["season"].isin(HOLDOUT)]
    print(f"Discovery: {len(disc)}, Holdout: {len(hold)}")

    for share_type in ["target", "carry"]:
        for pos in ["WR", "TE", "RB"]:
            subset = disc[(disc["share_type"] == share_type) & (disc["position"] == pos)]
            has_s0 = subset[subset["s0"].notna()]
            no_s0 = subset[subset["s0"].isna()]
            if len(has_s0) < 10:
                continue

            print(f"\n=== {pos} {share_type} share (discovery, n={len(has_s0)} with s0, {len(no_s0)} without) ===")

            # Grid search for optimal w
            best_w, best_mae = None, float("inf")
            for w10 in range(11):
                w = w10 / 10.0
                p_w = w * has_s0["s0"] + (1 - w) * has_s0["s1"]
                mae = (p_w - has_s0["s_out"]).abs().mean()
                if mae < best_mae:
                    best_w, best_mae = w, mae
            mae_w0 = (has_s0["s1"] - has_s0["s_out"]).abs().mean()
            mae_w1 = (has_s0["s0"] - has_s0["s_out"]).abs().mean()
            print(f"  Discovery best w={best_w:.1f}, MAE={best_mae:.5f}")
            print(f"  w=0 (raw wk1): MAE={mae_w0:.5f}")
            print(f"  w=1 (prior):   MAE={mae_w1:.5f}")
            reduction = 1 - best_mae / mae_w0
            print(f"  Reduction vs raw wk1: {reduction*100:.1f}%")

            # Holdout
            h_sub = hold[(hold["share_type"] == share_type) & (hold["position"] == pos)]
            h_s0 = h_sub[h_sub["s0"].notna()]
            if len(h_s0) >= 5:
                p_w_h = best_w * h_s0["s0"] + (1 - best_w) * h_s0["s1"]
                mae_h = (p_w_h - h_s0["s_out"]).abs().mean()
                mae_h_w0 = (h_s0["s1"] - h_s0["s_out"]).abs().mean()
                mae_h_w1 = (h_s0["s0"] - h_s0["s_out"]).abs().mean()
                red_h = 1 - mae_h / mae_h_w0
                print(f"  Holdout 2025 (n={len(h_s0)}): w={best_w:.1f} MAE={mae_h:.5f}, "
                      f"w=0 MAE={mae_h_w0:.5f}, w=1 MAE={mae_h_w1:.5f}")
                print(f"  Holdout reduction vs raw wk1: {red_h*100:.1f}%")

    # Week 2 2026 board: fraction of priced players with no s0
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    wk2_2026 = pu[(pu["season"] == 2026) & (pu["week"] == 2)]
    n_wk2 = len(wk2_2026)
    # Check which have prior-season data
    prior_ids = set(pu[pu["season"] == 2025]["player_id"].unique())
    n_with = wk2_2026["player_id"].isin(prior_ids).sum()
    n_without = n_wk2 - n_with
    print(f"\nWeek 2 2026: {n_wk2} players, {n_with} ({n_with/max(n_wk2,1)*100:.0f}%) with 2025 data, "
          f"{n_without} ({n_without/max(n_wk2,1)*100:.0f}%) without")


if __name__ == "__main__":
    main()
