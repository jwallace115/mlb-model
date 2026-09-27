#!/usr/bin/env python3
"""
5X Item 2: Class-by-class re-measurement on a season-stratified sample.

50 games per season (2021-24), fixed seed, N=100, with play log.
Real side from PBP with identical classes.
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
N_PER_SEASON = 50
N_SIMS = 100


def margin_bucket(m):
    a = abs(m)
    if a <= 7: return "0-7"
    if a <= 14: return "8-14"
    if a <= 21: return "15-21"
    return "22+"


def select_games():
    """50 games per season, fixed seed, sorted by game_id."""
    rng = np.random.default_rng(42)
    all_games = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        gids = sorted(df["game_id"].unique())
        chosen = rng.choice(gids, N_PER_SEASON, replace=False)
        gs = df[df["game_id"].isin(chosen)].drop_duplicates("game_id")[
            ["game_id", "home_team", "away_team", "week"]
        ].to_dict("records")
        all_games.extend([{**g, "season": s} for g in gs])
    return all_games


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")

    games = select_games()
    print(f"Selected {len(games)} games ({N_PER_SEASON} per season)")
    print(f"Game IDs (first 5 per season):")
    for s in SEASONS:
        sg = [g["game_id"] for g in games if g["season"] == s]
        print(f"  {s}: {sg[:5]} ... ({len(sg)} total)")

    # ---- Sim side ----
    print(f"Running sim (N={N_SIMS})...")
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    sim_game_rows = []
    for gi, g in enumerate(games):
        seed = stable_seed((g["home_team"], g["away_team"], g["season"], int(g["week"]), 42))
        r = simulate_game(g["home_team"], g["away_team"], g["season"], int(g["week"]),
                          n_sims=N_SIMS, seed=seed, team_r=team_r, tend=tend, sit=sit,
                          kicker=kicker, league=league, drive_log=True)
        pl = r.attrs.get("play_log")
        for si in range(N_SIMS):
            margin = int(r.iloc[si]["home_score"] - r.iloc[si]["away_score"])
            plays = int(r.iloc[si]["plays"])
            sim_game_rows.append({
                "game_id": g["game_id"], "season": g["season"], "sim_id": si,
                "margin": margin, "margin_bucket": margin_bucket(margin),
                "plays": plays,
            })
        if (gi + 1) % 25 == 0:
            print(f"  {gi+1}/{len(games)} games...")
        gc.collect()

    sim_df = pd.DataFrame(sim_game_rows)

    # ---- Real side ----
    print("Loading real data...")
    real_rows = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        game_ids = set(g["game_id"] for g in games if g["season"] == s)
        gdf = df[df["game_id"].isin(game_ids)]
        two_pt = gdf.get("two_point_attempt", pd.Series(0, index=gdf.index)).fillna(0)
        regular = gdf[(gdf["play_type"].isin(PLAY_TYPES)) & (two_pt == 0)]
        for gid, gg in regular.groupby("game_id"):
            gi = df[df["game_id"] == gid].iloc[0]
            hs = gi.get("home_score", 0) or 0
            as_ = gi.get("away_score", 0) or 0
            margin = int(hs - as_)
            real_rows.append({
                "game_id": gid, "season": s, "margin": margin,
                "margin_bucket": margin_bucket(margin), "plays": len(gg),
            })
    real_df = pd.DataFrame(real_rows)

    # ---- Report ----
    print(f"\n{'='*80}")
    print("PLAYS/GAME BY MARGIN BUCKET — season-stratified sample")
    print(f"{'='*80}")
    for bkt in ["0-7", "8-14", "15-21", "22+"]:
        sg = sim_df[sim_df["margin_bucket"] == bkt]
        rg = real_df[real_df["margin_bucket"] == bkt]
        sp = sg["plays"].mean() if len(sg) > 0 else 0
        rp = rg["plays"].mean() if len(rg) > 0 else 0
        print(f"  {bkt:>5s}: sim {sp:.1f}  real {rp:.1f}  gap {sp-rp:+.1f}  (sim n={len(sg)}, real n={len(rg)})")

    print(f"\n{'='*80}")
    print("PLAYS/GAME BY SEASON")
    print(f"{'='*80}")
    for s in SEASONS:
        sg = sim_df[sim_df["season"] == s]
        rg = real_df[real_df["season"] == s]
        sp = sg["plays"].mean() if len(sg) > 0 else 0
        rp = rg["plays"].mean() if len(rg) > 0 else 0
        print(f"  {s}: sim {sp:.1f}  real {rp:.1f}  gap {sp-rp:+.1f}")

    # Save small summary
    summary = []
    for bkt in ["0-7", "8-14", "15-21", "22+"]:
        sg = sim_df[sim_df["margin_bucket"] == bkt]
        rg = real_df[real_df["margin_bucket"] == bkt]
        summary.append({
            "margin_bucket": bkt,
            "sim_plays": sg["plays"].mean() if len(sg) > 0 else 0,
            "real_plays": rg["plays"].mean() if len(rg) > 0 else 0,
        })
    for s in SEASONS:
        sg = sim_df[sim_df["season"] == s]
        rg = real_df[real_df["season"] == s]
        summary.append({
            "margin_bucket": f"season_{s}",
            "sim_plays": sg["plays"].mean() if len(sg) > 0 else 0,
            "real_plays": rg["plays"].mean() if len(rg) > 0 else 0,
        })
    sdf = pd.DataFrame(summary)
    out = ROOT / "research" / "nfl_sim" / "phase5x_clock_class.parquet"
    sdf.to_parquet(out, index=False)
    print(f"\nSaved {out} ({out.stat().st_size} bytes)")

    total = time.time() - t0
    print(f"Total runtime: {total:.0f}s ({total/60:.1f} min)")


if __name__ == "__main__":
    main()
