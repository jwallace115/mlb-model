#!/usr/bin/env python3
"""
5Q Item 2: The quoted players' share of team receptions.

Two samples:
(A) 2026 Weeks 1-2: sim with player layer, N=500, vs PBP actuals.
(B) 2024 100 seeded games (K1 list), N=500, player layer ON, vs PBP actuals.

For each team-game: team receptions sim vs real; share of team receptions
to the top-6 players by sim mean; share to everyone else. Also: how many
players per team are in active_uni vs how many actually caught a pass.

No engine, usage, table, or parameter change. Zero API credits.
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed
from nfl.sim.calibration import engine_fingerprint

N_SIMS = 500


def get_games_from_pbp(seasons, weeks=None, max_games=None):
    """Get game list from PBP. Returns list of dicts."""
    games = []
    for s in seasons:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        if weeks:
            df = df[df["week"].isin(weeks)]
        glist = df.drop_duplicates("game_id")[
            ["game_id", "home_team", "away_team", "week"]
        ].to_dict("records")
        games.extend([{**g, "season": s} for g in glist])
    if max_games:
        games = games[:max_games]
    return games


def get_real_receptions(seasons, weeks=None):
    """Per-player receptions from PBP. Returns DataFrame with
    game_id, team (posteam), player_id, receptions."""
    frames = []
    for s in seasons:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        if weeks:
            df = df[df["week"].isin(weeks)]
        comps = df[(df["play_type"] == "pass") & (df["complete_pass"] == 1)]
        rec = comps.groupby(["game_id", "posteam", "receiver_player_id"]).agg(
            receptions=("play_id", "count"),
        ).reset_index()
        rec.rename(columns={"posteam": "team", "receiver_player_id": "player_id"}, inplace=True)
        rec["season"] = s
        frames.append(rec)
    return pd.concat(frames, ignore_index=True)


def run_sample(games, label, team_r, tend, sit, kicker, league, pu, au):
    """Run sim for a list of games, return per-team-game stats."""
    team_game_rows = []
    t0 = time.time()

    for gi, g in enumerate(games):
        home, away, s, week = g["home_team"], g["away_team"], g["season"], int(g["week"])
        seed = stable_seed((home, away, s, week, 42))

        r = simulate_game(home, away, s, week, n_sims=N_SIMS, seed=seed,
                          team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                          league=league, player_usage=pu, active_uni=au)

        if not isinstance(r, tuple):
            # No player output
            continue

        team_df, player_df = r

        # Per-player mean receptions across sims
        pl_means = player_df.groupby(["player_id", "player_name", "position", "team"]).agg(
            sim_mean_rec=("receptions", "mean"),
        ).reset_index()

        for team in [home, away]:
            tm = pl_means[pl_means["team"] == team].copy()
            if len(tm) == 0:
                continue
            tm = tm.sort_values("sim_mean_rec", ascending=False).reset_index(drop=True)

            # Top-6 by sim mean
            top6 = tm.head(6)
            rest = tm.iloc[6:]

            sim_team_total = tm["sim_mean_rec"].sum()
            sim_top6_total = top6["sim_mean_rec"].sum()
            sim_top6_share = sim_top6_total / max(sim_team_total, 1e-9)
            sim_rest_share = 1 - sim_top6_share

            # Per-position breakdown for top-6
            top6_by_pos = top6.groupby("position").agg(
                n=("player_id", "count"),
                sim_mean=("sim_mean_rec", "mean"),
            ).to_dict("index")

            team_game_rows.append({
                "game_id": g["game_id"],
                "season": s,
                "week": week,
                "team": team,
                "sample": label,
                "sim_team_rec": sim_team_total,
                "sim_top6_rec": sim_top6_total,
                "sim_top6_share": sim_top6_share,
                "sim_n_players": len(tm),
                "top6_wr_n": top6_by_pos.get("WR", {}).get("n", 0),
                "top6_wr_mean": top6_by_pos.get("WR", {}).get("sim_mean", 0),
                "top6_te_n": top6_by_pos.get("TE", {}).get("n", 0),
                "top6_te_mean": top6_by_pos.get("TE", {}).get("sim_mean", 0),
                "top6_rb_n": top6_by_pos.get("RB", {}).get("n", 0),
                "top6_rb_mean": top6_by_pos.get("RB", {}).get("sim_mean", 0),
                "top6_ids": top6["player_id"].tolist(),
            })

        if (gi + 1) % 20 == 0:
            print(f"  [{label}] {gi+1}/{len(games)} games...")

    elapsed = time.time() - t0
    print(f"  [{label}] {len(games)} games in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    return pd.DataFrame(team_game_rows)


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")
    assert fp == "02fbcab6e6ed042e"

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")

    # ---- Sample A: 2026 Weeks 1-2 ----
    print("Sample A: 2026 Weeks 1-2...")
    games_a = get_games_from_pbp([2026], weeks=[1, 2])
    print(f"  {len(games_a)} games")
    sim_a = run_sample(games_a, "2026_w1w2", team_r, tend, sit, kicker, league, pu, au)

    # ---- Sample B: 2024, 100 games (K1 list, seed 42) ----
    print("Sample B: 2024, 100 K1 games...")
    games_b = get_games_from_pbp([2024])
    # K1 list: first 100 games of the season, sorted by game_id
    games_b = sorted(games_b, key=lambda g: g["game_id"])[:100]
    print(f"  {len(games_b)} games")
    sim_b = run_sample(games_b, "2024_100", team_r, tend, sit, kicker, league, pu, au)

    # ---- Real receptions ----
    print("Loading real receptions...")
    real_a = get_real_receptions([2026], weeks=[1, 2])
    real_b = get_real_receptions([2024])

    # ---- Match and compute real-side stats ----
    all_sim = pd.concat([sim_a, sim_b], ignore_index=True)

    results = []
    for _, row in all_sim.iterrows():
        gid, team, sample = row["game_id"], row["team"], row["sample"]
        real_df = real_a if "2026" in sample else real_b
        r_team = real_df[(real_df["game_id"] == gid) & (real_df["team"] == team)]

        real_team_rec = r_team["receptions"].sum()
        real_unique_rec = len(r_team)

        # Top-6 sim players: how many receptions did they get in reality?
        top6_ids = row["top6_ids"]
        r_top6 = r_team[r_team["player_id"].isin(top6_ids)]
        real_top6_rec = r_top6["receptions"].sum()
        real_top6_share = real_top6_rec / max(real_team_rec, 1) if real_team_rec > 0 else 0

        results.append({
            **{k: row[k] for k in row.index if k != "top6_ids"},
            "real_team_rec": real_team_rec,
            "real_unique_rec": real_unique_rec,
            "real_top6_rec": real_top6_rec,
            "real_top6_share": real_top6_share,
        })

    rdf = pd.DataFrame(results)

    # Save parquet
    out_path = ROOT / "research" / "nfl_sim" / "phase5q_reception_share.parquet"
    rdf.to_parquet(out_path, index=False)
    print(f"Saved {out_path} ({len(rdf)} rows)")

    # ---- Report ----
    for sample_label, sample_name in [("2026_w1w2", "Sample A (2026 W1-2)"),
                                       ("2024_100", "Sample B (2024 100 games)")]:
        sdf = rdf[rdf["sample"] == sample_label]
        print(f"\n{'='*80}")
        print(f"{sample_name}: {len(sdf)} team-games")
        print(f"{'='*80}")

        print(f"  Team receptions/game: sim {sdf['sim_team_rec'].mean():.1f}  "
              f"real {sdf['real_team_rec'].mean():.1f}  "
              f"diff {sdf['sim_team_rec'].mean() - sdf['real_team_rec'].mean():+.1f}")

        print(f"  Top-6 share: sim {sdf['sim_top6_share'].mean():.3f}  "
              f"real {sdf['real_top6_share'].mean():.3f}  "
              f"diff {sdf['sim_top6_share'].mean() - sdf['real_top6_share'].mean():+.3f}")

        print(f"  Top-6 receptions: sim {sdf['sim_top6_rec'].mean():.1f}  "
              f"real {sdf['real_top6_rec'].mean():.1f}  "
              f"diff {sdf['sim_top6_rec'].mean() - sdf['real_top6_rec'].mean():+.1f}")

        rest_sim = sdf['sim_team_rec'].mean() - sdf['sim_top6_rec'].mean()
        rest_real = sdf['real_team_rec'].mean() - sdf['real_top6_rec'].mean()
        print(f"  Rest receptions: sim {rest_sim:.1f}  real {rest_real:.1f}  diff {rest_sim - rest_real:+.1f}")

        # By position (top-6)
        for pos in ["WR", "TE", "RB"]:
            n_col = f"top6_{pos.lower()}_n"
            m_col = f"top6_{pos.lower()}_mean"
            pos_rows = sdf[sdf[n_col] > 0]
            if len(pos_rows) > 0:
                print(f"  Top-6 {pos}: sim mean/player {pos_rows[m_col].mean():.2f}, "
                      f"avg count in top-6 {pos_rows[n_col].mean():.1f}")

    # ---- Active-uni vs actual receivers ----
    print(f"\n{'='*80}")
    print("ACTIVE UNIVERSE vs ACTUAL RECEIVERS (2026 Week 2)")
    print(f"{'='*80}")

    au_w2 = au[(au["season"] == 2026) & (au["week"] == 2) & (au["active_flag"] == True)]
    # Filter to skill positions
    au_w2_skill = au_w2[au_w2["position"].isin(["WR", "TE", "RB"])]
    au_per_team = au_w2_skill.groupby("team").size()

    real_w2 = real_a[real_a["game_id"].str.contains("2026_02")]
    real_per_team = real_w2.groupby("team")["player_id"].nunique()

    # Also count how many players on the team received at least 1 target
    # (not just catches - but we only have catches from PBP)
    print(f"  Active skill (WR/TE/RB) per team: mean {au_per_team.mean():.1f}, "
          f"range {au_per_team.min()}-{au_per_team.max()}")
    print(f"  Players who caught a pass per team: mean {real_per_team.mean():.1f}, "
          f"range {real_per_team.min()}-{real_per_team.max()}")
    print(f"  Gap: {au_per_team.mean() - real_per_team.mean():.1f} more active players than actual receivers")

    # ---- Renormalization read-only ----
    print(f"\n{'='*80}")
    print("_renormalize_measured READ-ONLY ANALYSIS")
    print(f"{'='*80}")
    print("  Code at engine.py:381-435.")
    print("  Vacated shares from inactive players at position P are redistributed to")
    print("  active players using REDIST_TARGET/REDIST_CARRY proportional weights.")
    print("  Final renormalize to sum=1 across active players (line 428-433).")
    print("  This means: the fewer active players, the more share each gets.")
    print(f"  With {au_per_team.mean():.0f} active skill players and {real_per_team.mean():.0f} actual")
    print(f"  receivers, ~{au_per_team.mean() - real_per_team.mean():.0f} active players get shares but don't")
    print("  catch passes in real games. Their sim receptions come from somewhere real")
    print("  receivers don't lose — this is a depth-player inflation mechanism.")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")
    print(f"Fingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
