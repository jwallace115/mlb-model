#!/usr/bin/env python3
"""Phase 5A-5: Run K1 (1087 games, N=500) with non-offensive scoring counters."""
import time, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _CACHE
from nfl.sim.seed_util import stable_seed

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs"
SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 500

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _load_tables()
    tr, tend, sit, kicker, league = _load_ratings()
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        df = pd.read_parquet(p, columns=["game_id","season","week","home_team","away_team","home_score","away_score"])
        frames.append(df.drop_duplicates("game_id").query("week <= 18"))
    actuals = pd.concat(frames, ignore_index=True)
    print(f"K1 5A-5: {len(actuals)} games, N={N_SIMS}", flush=True)
    results = []
    t_total = time.time()
    for s in SEASONS:
        s_games = actuals[actuals["season"] == s]
        t0 = time.time()
        for _, game in s_games.iterrows():
            seed = stable_seed((game["game_id"], 42))
            sim = simulate_game(game["home_team"], game["away_team"], s, int(game["week"]),
                                n_sims=N_SIMS, seed=seed, team_r=tr, tend=tend, sit=sit,
                                kicker=kicker, league=league, drive_log=True)
            sim["game_id"] = game["game_id"]
            sim["actual_home"] = game["home_score"]
            sim["actual_away"] = game["away_score"]
            sim["season"] = s; sim["week"] = game["week"]
            results.append(sim)
        elapsed = time.time() - t0
        print(f"  Season {s}: {len(s_games)} games, {elapsed:.1f}s ({elapsed/len(s_games):.2f}s/game)", flush=True)
    all_sims = pd.concat(results, ignore_index=True)
    total_time = time.time() - t_total
    print(f"Total: {total_time:.1f}s ({total_time/60:.1f}min)", flush=True)
    out_path = OUT_DIR / "k1_5a5.parquet"
    all_sims.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(all_sims)} rows)", flush=True)

    # Summary
    xp = 0.948
    print(f"\n--- Non-Offensive Scoring ---", flush=True)
    for c in ["ev_int_ret_td","ev_fum_ret_td","ev_punt_ret_td","ev_ko_ret_td","ev_safeties"]:
        print(f"  {c}/game: {all_sims[c].mean():.4f}", flush=True)
    nonoff_tds = (all_sims["ev_int_ret_td"]+all_sims["ev_fum_ret_td"]+all_sims["ev_punt_ret_td"]+all_sims["ev_ko_ret_td"]).mean()
    nonoff_pts = nonoff_tds * (6 + xp) + all_sims["ev_safeties"].mean() * 2
    print(f"  Non-off pts/game: {nonoff_pts:.2f} ({nonoff_pts/2:.2f}/team)", flush=True)
    print(f"  Pts/team: {(all_sims['home_score'].mean() + all_sims['away_score'].mean())/2:.1f}", flush=True)

if __name__ == "__main__":
    main()
