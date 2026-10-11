#!/usr/bin/env python3
"""
GL1 Item 2: Run unanchored engine on 2021-23 at N=5,000 (chunk_size 2,500).

Modelled on run_fit.py's per-game checkpointed runner. Runs each game ONCE with
dh = da = 0 (no Newton steps). Writes per-game checkpoints + combined output.

Output: nfl/data/sim/outputs/gl1/unanchored_2021_23.parquet

Usage: python3 nfl/sim/run_gameline_gl1.py
"""

import gc, json, os, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = Path(os.environ.get("NFL_PBP_DIR", str(ROOT / "nfl" / "data" / "pbp")))
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"

N_SIMS = 5000
CHUNK_SIZE = 2500
ALLOWED_SEASONS = [2021, 2022, 2023]

# Set from --out-dir or default
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs" / "gl1"
GAMES_DIR = OUT_DIR / "games"


def _worker_init():
    """Initialize engine tables once per worker process."""
    from nfl.sim.engine import _load_tables, _load_ratings
    global _WORKER_KW
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    _WORKER_KW = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)


def _run_one_game(args):
    """Run unanchored sim for one game. Returns row dict."""
    game_id, home, away, season, week, spread, total_line, actual_m, actual_t, games_dir = args

    games_dir = Path(games_dir)
    checkpoint = games_dir / f"{game_id}.parquet"
    if checkpoint.exists():
        return None  # skip

    from nfl.sim.anchor import _run_chunks
    from nfl.sim.seed_util import stable_seed

    base_seed = stable_seed((home, away, season, week, 42))
    n_chunks = N_SIMS // CHUNK_SIZE

    t0 = time.time()
    td, _, m, t, se_m, se_t = _run_chunks(
        home, away, season, week, CHUNK_SIZE, n_chunks, base_seed,
        0.0, 0.0, **_WORKER_KW)
    dt = time.time() - t0

    margin = (td["home_score"] - td["away_score"]).values.astype(float)
    total_arr = (td["home_score"] + td["away_score"]).values.astype(float)

    sd_m = margin.std()
    sd_t = total_arr.std()
    p_hw = (margin > 0).mean()
    p_m3 = (np.abs(margin) == 3).mean()
    p_m7 = (np.abs(margin) == 7).mean()

    # Save checkpoint
    cp = pd.DataFrame({
        "sim_id": np.arange(len(td)),
        "margin": margin.astype(np.float32),
        "total": total_arr.astype(np.float32),
    })
    cp.to_parquet(checkpoint, index=False)

    del td
    gc.collect()

    return {
        "game_id": game_id, "season": season, "week": week,
        "raw_m": m, "raw_t": t,
        "sd_m": sd_m, "sd_t": sd_t,
        "p_home_win": p_hw,
        "p_m3": p_m3, "p_m7": p_m7,
        "mkt_m": spread, "mkt_t": total_line,
        "actual_m": actual_m, "actual_t": actual_t,
        "N": N_SIMS, "seed_key": f"({home},{away},{season},{week},42)",
        "wall_time": dt,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="gl1",
                        help="Output subdirectory under nfl/data/sim/outputs/")
    parser.add_argument("--out-name", default="unanchored_2021_23.parquet",
                        help="Output parquet filename")
    args = parser.parse_args()

    global OUT_DIR, GAMES_DIR
    OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs" / args.out_dir
    GAMES_DIR = OUT_DIR / "games"

    GAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Engine fingerprint
    from nfl.sim.calibration import engine_fingerprint
    eng_fp = engine_fingerprint()
    print(f"Engine fingerprint: {eng_fp}")

    # Load game list
    all_games = []
    for s in ALLOWED_SEASONS:
        pbp_path = PBP_DIR / f"pbp_{s}.parquet"
        if not pbp_path.exists():
            print(f"ERROR: {pbp_path} not found", file=sys.stderr)
            sys.exit(1)
        df = pd.read_parquet(pbp_path,
            columns=["game_id", "season", "week", "home_team", "away_team",
                     "home_score", "away_score", "spread_line", "total_line"])
        g = df.drop_duplicates("game_id")
        g = g[(g["week"] <= 18) & g["spread_line"].notna() & g["total_line"].notna()]
        for _, row in g.iterrows():
            assert int(row["season"]) in ALLOWED_SEASONS, f"Season {row['season']} not allowed"
            all_games.append((
                row["game_id"], row["home_team"], row["away_team"],
                int(row["season"]), int(row["week"]),
                float(row["spread_line"]), float(row["total_line"]),
                float(row["home_score"] - row["away_score"]),
                float(row["home_score"] + row["away_score"]),
                str(GAMES_DIR),
            ))

    done = sum(1 for g in all_games if (Path(g[-1]) / f"{g[0]}.parquet").exists())
    todo = len(all_games) - done
    print(f"Games: {len(all_games)} total, {done} done, {todo} to run")

    if todo == 0:
        print("All games already checkpointed.")
    else:
        import psutil
        cores = psutil.cpu_count(logical=False)
        avail_mem = psutil.virtual_memory().available
        peak_rss_mb = 321
        workers_by_mem = int(0.7 * avail_mem / (peak_rss_mb * 1024 * 1024))
        workers = min(cores - 1, workers_by_mem)
        workers = max(1, workers)
        print(f"Workers: {workers} (cores={cores}, avail_mem={avail_mem/1e9:.1f}GB)")

        t_start = time.time()
        completed = 0
        rows = []
        try:
            with Pool(workers, initializer=_worker_init) as pool:
                for result in pool.imap_unordered(_run_one_game, all_games):
                    if result is None:
                        continue
                    rows.append(result)
                    completed += 1
                    if completed % 25 == 0:
                        elapsed = time.time() - t_start
                        print(f"  [{completed}/{todo}] {elapsed:.0f}s "
                              f"({elapsed/completed:.1f}s/game)", flush=True)
        except Exception as e:
            print(f"\nFATAL: {e}", file=sys.stderr)
            sys.exit(1)

        total_time = time.time() - t_start
        print(f"\nComplete: {completed} games in {total_time:.0f}s "
              f"({total_time/completed:.1f}s/game)")

    # Build combined output from all checkpoints + game list
    rows = []
    for gid, home, away, season, week, spread, total_line, actual_m, actual_t, gdir in all_games:
        cp = Path(gdir) / f"{gid}.parquet"
        if not cp.exists():
            continue
        sim_df = pd.read_parquet(cp)
        margin = sim_df["margin"].values.astype(float)
        total_arr = sim_df["total"].values.astype(float)
        rows.append({
            "game_id": gid, "season": season, "week": week,
            "raw_m": margin.mean(), "raw_t": total_arr.mean(),
            "sd_m": margin.std(), "sd_t": total_arr.std(),
            "p_home_win": (margin > 0).mean(),
            "p_m3": (np.abs(margin) == 3).mean(),
            "p_m7": (np.abs(margin) == 7).mean(),
            "mkt_m": spread, "mkt_t": total_line,
            "actual_m": actual_m, "actual_t": actual_t,
            "engine_fingerprint": eng_fp,
            "N": len(sim_df),
            "seed_key": f"({home},{away},{season},{week},42)",
        })

    result_df = pd.DataFrame(rows)

    # Sanity: season membership
    bad_seasons = set(result_df["season"].unique()) - set(ALLOWED_SEASONS)
    assert not bad_seasons, f"Disallowed seasons: {bad_seasons}"

    out_path = OUT_DIR / args.out_name
    result_df.to_parquet(out_path, index=False)
    print(f"\nOutput: {out_path} ({len(result_df)} games)")
    print(f"Engine fingerprint: {eng_fp}")
    print(f"Raw margin mean: {result_df['raw_m'].mean():.2f}")
    print(f"Raw total mean: {result_df['raw_t'].mean():.2f}")
    print(f"Market margin mean: {result_df['mkt_m'].mean():.2f}")
    print(f"Market total mean: {result_df['mkt_t'].mean():.2f}")
    print(f"corr(raw_m, mkt_m): {np.corrcoef(result_df['raw_m'], result_df['mkt_m'])[0,1]:.3f}")
    print(f"corr(raw_m, actual_m): {np.corrcoef(result_df['raw_m'], result_df['actual_m'])[0,1]:.3f}")
    print(f"P(|m|=3) mean: {result_df['p_m3'].mean()*100:.1f}%")
    print(f"P(|m|=7) mean: {result_df['p_m7'].mean()*100:.1f}%")


if __name__ == "__main__":
    main()
