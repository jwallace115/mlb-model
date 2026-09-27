#!/usr/bin/env python3
"""
5W Item 2: Decompose plays by game state — margin buckets, score state, season.

Sim: D144 sample (200 K1 games, N=100) with play_log.
Real: PBP 2021-24 REG, per scrimmage snap.
"""
import sys, time, gc
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed
from nfl.sim.calibration import engine_fingerprint
from nfl.sim.actuals_k1 import PLAY_TYPES

SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 100
N_GAMES = 200


def margin_bucket(margin):
    a = abs(margin)
    if a <= 7: return "0-7"
    if a <= 14: return "8-14"
    if a <= 21: return "15-21"
    return "22+"


def run_sim_sample():
    """Run D144 sample, return per-game summary with play count and margin."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    games_list = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        gs = df.drop_duplicates("game_id")[["game_id", "home_team", "away_team", "week"]].to_dict("records")
        games_list.extend([{**g, "season": s} for g in gs])
    games_list = sorted(games_list, key=lambda g: g["game_id"])[:N_GAMES]

    sim_game_rows = []
    for gi, g in enumerate(games_list):
        seed = stable_seed((g["home_team"], g["away_team"], g["season"], int(g["week"]), 42))
        r = simulate_game(g["home_team"], g["away_team"], g["season"], int(g["week"]),
                          n_sims=N_SIMS, seed=seed, team_r=team_r, tend=tend, sit=sit,
                          kicker=kicker, league=league, drive_log=True)
        pl = r.attrs.get("play_log")
        for si in range(N_SIMS):
            margin = int(r.iloc[si]["home_score"] - r.iloc[si]["away_score"])
            n_plays_sim = int(r.iloc[si]["plays"])
            n_snaps_log = 0
            mean_elapsed = 0
            if pl is not None:
                sp = pl[pl["sim_id"] == si]
                n_snaps_log = len(sp)
                mean_elapsed = sp["elapsed"].mean() if len(sp) > 0 else 0
            sim_game_rows.append({
                "game_id": g["game_id"], "season": g["season"], "sim_id": si,
                "margin": margin, "margin_bucket": margin_bucket(margin),
                "plays": n_plays_sim, "snaps_log": n_snaps_log,
                "mean_elapsed": mean_elapsed,
            })
        if (gi + 1) % 50 == 0:
            print(f"  {gi+1}/{N_GAMES} games...")
        gc.collect()
    return pd.DataFrame(sim_game_rows)


def load_real_games():
    """Real per-game plays and margin from PBP 2021-24 REG."""
    rows = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        two_pt = df.get("two_point_attempt", pd.Series(0, index=df.index)).fillna(0)
        regular = df[(df["play_type"].isin(PLAY_TYPES)) & (two_pt == 0)]
        for gid, gdf in regular.groupby("game_id"):
            game_info = df[df["game_id"] == gid].iloc[0]
            hs = game_info.get("home_score", 0) or 0
            as_ = game_info.get("away_score", 0) or 0
            margin = int(hs - as_)
            rows.append({
                "game_id": gid, "season": s, "margin": margin,
                "margin_bucket": margin_bucket(margin),
                "plays": len(gdf),
            })
    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")

    print("Loading real games...")
    real = load_real_games()
    print(f"  {len(real)} real games")

    print(f"Running sim sample ({N_GAMES} games, N={N_SIMS})...")
    sim = run_sim_sample()
    print(f"  {len(sim)} sim-games")

    # ---- By margin bucket ----
    print(f"\n{'='*80}")
    print("PLAYS/GAME BY FINAL MARGIN BUCKET")
    print(f"{'='*80}")
    print(f"{'bucket':>8s} {'sim_plays':>10s} {'real_plays':>11s} {'gap':>6s} {'sim_n':>6s} {'real_n':>7s}")
    for bkt in ["0-7", "8-14", "15-21", "22+"]:
        sg = sim[sim["margin_bucket"] == bkt]
        rg = real[real["margin_bucket"] == bkt]
        s_plays = sg["plays"].mean() if len(sg) > 0 else 0
        r_plays = rg["plays"].mean() if len(rg) > 0 else 0
        print(f"{bkt:>8s} {s_plays:10.1f} {r_plays:11.1f} {s_plays - r_plays:+6.1f} {len(sg):6d} {len(rg):7d}")

    # ---- By season ----
    print(f"\n{'='*80}")
    print("PLAYS/GAME BY SEASON")
    print(f"{'='*80}")
    for s in SEASONS:
        sg = sim[sim["season"] == s]
        rg = real[real["season"] == s]
        if len(sg) > 0 and len(rg) > 0:
            print(f"  {s}: sim {sg['plays'].mean():.1f}  real {rg['plays'].mean():.1f}  gap {sg['plays'].mean()-rg['plays'].mean():+.1f}")

    # Save summary (small)
    summary_rows = []
    for bkt in ["0-7", "8-14", "15-21", "22+"]:
        sg = sim[sim["margin_bucket"] == bkt]
        rg = real[real["margin_bucket"] == bkt]
        summary_rows.append({
            "margin_bucket": bkt,
            "sim_plays": sg["plays"].mean() if len(sg) > 0 else 0,
            "real_plays": rg["plays"].mean() if len(rg) > 0 else 0,
            "sim_n": len(sg), "real_n": len(rg),
        })
    sdf = pd.DataFrame(summary_rows)
    out = ROOT / "research" / "nfl_sim" / "phase5w_clock_state.parquet"
    sdf.to_parquet(out, index=False)
    print(f"\nSaved {out} ({len(sdf)} rows, {out.stat().st_size} bytes)")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")


if __name__ == "__main__":
    main()
