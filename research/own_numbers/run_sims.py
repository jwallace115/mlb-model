#!/usr/bin/env python3
"""
Standalone sim runner — saves cache then exits.
Must be run as __main__ for multiprocessing to work on macOS.
"""
import os, sys, json, time
import numpy as np
import pandas as pd

os.environ["SSL_CERT_FILE"] = __import__("certifi").where()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

ROOT = os.path.join(os.path.dirname(__file__), "../..")
SIM_CACHE = os.path.join(ROOT, "nfl/data/own/_sim_cache_2021_23.parquet")

if os.path.exists(SIM_CACHE):
    print(f"Cache exists: {SIM_CACHE}")
    sys.exit(0)

from nfl.sim.engine import simulate_game
import nflreadpy as nfl

with open(os.path.join(ROOT, "nfl/sim/hfa_v1.json")) as f:
    H = json.load(f)["h"]

sched = nfl.load_schedules([2021, 2022, 2023]).to_pandas()
games = sched[sched["game_type"] == "REG"]
print(f"Games: {len(games)}, H={H}")

N_CHUNKS = 2
CHUNK_SIZE = 2500

def sim_one_game(game_id, home, away, season, week):
    chunk_margins = []
    chunk_totals = []
    for ci in range(N_CHUNKS):
        seed = hash((game_id, ci)) % (2**31)
        result = simulate_game(home, away, season, week,
                                n_sims=CHUNK_SIZE, seed=seed,
                                epa_home_offset=H, epa_away_offset=-H)
        margins = (result["home_score"] - result["away_score"]).values
        totals = (result["home_score"] + result["away_score"]).values
        chunk_margins.append(margins.mean())
        chunk_totals.append(totals.mean())
    ours_m = np.mean(chunk_margins)
    ours_t = np.mean(chunk_totals)
    mc_se_m = np.std(chunk_margins, ddof=1) / np.sqrt(N_CHUNKS)
    mc_se_t = np.std(chunk_totals, ddof=1) / np.sqrt(N_CHUNKS)
    return {
        "game_id": game_id, "ours_m": ours_m, "ours_t": ours_t,
        "mc_se_m": mc_se_m, "mc_se_t": mc_se_t,
        "n_games_home": max(week - 1, 0),
        "n_games_away": max(week - 1, 0),
    }

if __name__ == "__main__":
    from multiprocessing import freeze_support, Pool
    freeze_support()

    game_args = [(r["game_id"], r["home_team"], r["away_team"], r["season"], r["week"])
                 for _, r in games.iterrows()]

    t0 = time.time()
    results = []
    n_workers = min(8, os.cpu_count() or 4)
    print(f"Workers: {n_workers}")

    with Pool(n_workers) as pool:
        for i, res in enumerate(pool.starmap(sim_one_game, game_args)):
            results.append(res)
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                print(f"  {i+1}/{len(game_args)} ({elapsed:.0f}s)")

    t1 = time.time()
    print(f"Done: {t1-t0:.0f}s ({(t1-t0)/60:.1f}m)")

    os.makedirs(os.path.dirname(SIM_CACHE), exist_ok=True)
    pd.DataFrame(results).to_parquet(SIM_CACHE, index=False)
    print(f"Saved: {SIM_CACHE}")
