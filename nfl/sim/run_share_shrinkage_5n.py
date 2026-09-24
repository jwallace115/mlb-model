#!/usr/bin/env python3
"""
5O Item 1 (replaces 5N's leaky script): Share shrinkage measured honestly.
w picked on POOLED 2021-24, applied ONCE to 2025. Same-team / changed-team split.
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

        tgt = scrim[scrim["pass_attempt"] == 1].groupby(
            ["season", "week", "posteam", "receiver_player_id"]
        ).size().reset_index(name="count")
        tgt.rename(columns={"receiver_player_id": "player_id"}, inplace=True)
        tgt["share_type"] = "target"

        team_tgt = scrim[scrim["pass_attempt"] == 1].groupby(
            ["season", "week", "posteam"]
        ).size().reset_index(name="team_total")
        tgt = tgt.merge(team_tgt, on=["season", "week", "posteam"])
        tgt["share"] = tgt["count"] / tgt["team_total"].clip(lower=1)

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


def build_player_rows(all_df, season_shares, seasons, share_type, pos, k):
    """Build merged player rows for the given seasons, pos, share_type, k."""
    sdf = all_df[(all_df["share_type"] == share_type) &
                 (all_df["position"] == pos) &
                 (all_df["season"].isin(seasons))]
    wk_in = sdf[sdf["week"].between(1, k)]
    wk_out = sdf[sdf["week"].between(k + 1, 8)]
    if wk_in.empty or wk_out.empty:
        return pd.DataFrame()

    player_in = wk_in.groupby(["season", "player_id"]).agg(
        count_in=("count", "sum"), team_in=("team_total", "sum"),
        team=("posteam", "first")
    ).reset_index()
    player_in["s_k"] = player_in["count_in"] / player_in["team_in"].clip(lower=1)

    player_out = wk_out.groupby(["season", "player_id"]).agg(
        count_out=("count", "sum"), team_out=("team_total", "sum"),
        n_weeks_out=("week", "nunique")
    ).reset_index()
    player_out["s_out"] = player_out["count_out"] / player_out["team_out"].clip(lower=1)

    merged = player_in.merge(player_out, on=["season", "player_id"])
    if merged.empty:
        return pd.DataFrame()

    # Add prior season full share
    rows = []
    for s in seasons:
        prior = season_shares[(season_shares["season"] == s - 1) &
                              (season_shares["share_type"] == share_type)]
        sub = merged[merged["season"] == s].merge(
            prior[["player_id", "full_share", "posteam"]].rename(
                columns={"full_share": "s0", "posteam": "prior_team"}),
            on="player_id", how="left"
        )
        rows.append(sub)
    merged = pd.concat(rows, ignore_index=True)
    merged["same_team"] = merged["team"] == merged["prior_team"]
    merged["has_s0"] = merged["s0"].notna()
    return merged


def grid_search_w(has_s0):
    """Pick best w on the given rows. Returns (w, mae_at_w, mae_at_0)."""
    best_w, best_mae = None, float("inf")
    wt = has_s0["n_weeks_out"]
    for w10 in range(11):
        w = w10 / 10.0
        p_w = w * has_s0["s0"] + (1 - w) * has_s0["s_k"]
        mae = ((p_w - has_s0["s_out"]).abs() * wt).sum() / wt.sum()
        if mae < best_mae:
            best_w, best_mae = w, mae
    mae_w0 = ((has_s0["s_k"] - has_s0["s_out"]).abs() * wt).sum() / wt.sum()
    return best_w, best_mae, mae_w0


def main():
    print("Building shares from PBP...")
    all_df = build_shares()
    season_shares = compute_prior_season_share(all_df)

    print(f"\n{'pos':3s} {'share':6s} {'k':2s} | {'w':4s} {'n_disc':>6s} {'disc_red':>8s} | "
          f"{'n_hold':>6s} {'hold_red':>8s} | {'same_n':>6s} {'same_%':>6s} {'chg_n':>5s} {'chg_%':>6s}")
    print("-" * 90)

    for share_type in ["target", "carry"]:
        for pos in ["WR", "TE", "RB"]:
            for k in [1, 2, 3, 4]:
                # Discovery: pooled 2021-24
                disc = build_player_rows(all_df, season_shares, DISCOVERY, share_type, pos, k)
                if disc.empty:
                    continue
                disc_s0 = disc[disc["has_s0"]]
                if len(disc_s0) < 10:
                    continue
                disc_w, disc_mae, disc_mae0 = grid_search_w(disc_s0)
                disc_red = 1 - disc_mae / disc_mae0 if disc_mae0 > 0 else 0

                # Holdout: 2025, apply disc_w
                hold = build_player_rows(all_df, season_shares, HOLDOUT, share_type, pos, k)
                hold_red_str = ""
                same_str = ""
                chg_str = ""
                n_hold = 0
                if not hold.empty:
                    hold_s0 = hold[hold["has_s0"]]
                    n_hold = len(hold_s0)
                    if n_hold >= 5:
                        wt = hold_s0["n_weeks_out"]
                        p_w = disc_w * hold_s0["s0"] + (1 - disc_w) * hold_s0["s_k"]
                        h_mae = ((p_w - hold_s0["s_out"]).abs() * wt).sum() / wt.sum()
                        h_mae0 = ((hold_s0["s_k"] - hold_s0["s_out"]).abs() * wt).sum() / wt.sum()
                        h_red = 1 - h_mae / h_mae0 if h_mae0 > 0 else 0
                        hold_red_str = f"{h_red*100:7.1f}%"

                        # Same-team / changed-team split
                        same = hold_s0[hold_s0["same_team"]]
                        chg = hold_s0[~hold_s0["same_team"]]
                        if len(same) >= 3:
                            wt_s = same["n_weeks_out"]
                            p_s = disc_w * same["s0"] + (1 - disc_w) * same["s_k"]
                            s_mae = ((p_s - same["s_out"]).abs() * wt_s).sum() / wt_s.sum()
                            s_mae0 = ((same["s_k"] - same["s_out"]).abs() * wt_s).sum() / wt_s.sum()
                            s_red = 1 - s_mae / s_mae0 if s_mae0 > 0 else 0
                            same_str = f"{len(same):6d} {s_red*100:5.1f}%"
                        if len(chg) >= 3:
                            wt_c = chg["n_weeks_out"]
                            p_c = disc_w * chg["s0"] + (1 - disc_w) * chg["s_k"]
                            c_mae = ((p_c - chg["s_out"]).abs() * wt_c).sum() / wt_c.sum()
                            c_mae0 = ((chg["s_k"] - chg["s_out"]).abs() * wt_c).sum() / wt_c.sum()
                            c_red = 1 - c_mae / c_mae0 if c_mae0 > 0 else 0
                            chg_str = f"{len(chg):5d} {c_red*100:5.1f}%"

                print(f"{pos:3s} {share_type:6s} {k:2d} | {disc_w:.1f} {len(disc_s0):6d} {disc_red*100:7.1f}% | "
                      f"{n_hold:6d} {hold_red_str:>8s} | {same_str:>13s} {chg_str:>12s}")


if __name__ == "__main__":
    main()
