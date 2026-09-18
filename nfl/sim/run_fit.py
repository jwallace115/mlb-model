#!/usr/bin/env python3
"""
Phase 5C-2: Parallel anchored fit runner.

Usage: python3 nfl/sim/run_fit.py --seasons 2021 2022 2023 2024

Per game: uses anchor.run_anchored_chunked (shared solver, params from anchor block).
Checkpoints one parquet per game under nfl/data/sim/outputs/fit_5c2/games/.
Resumable: skip games whose checkpoint exists.
Worker count is MEASURED from peak RSS and available memory.
"""

import argparse, gc, json, os, subprocess, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs" / "fit_5d1"
GAMES_DIR = OUT_DIR / "games"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"


def _get_engine_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _worker_init():
    """Initialize engine tables once per worker process."""
    from nfl.sim.engine import _load_tables, _load_ratings
    global _WORKER_KW, _WORKER_PU, _WORKER_AU
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    _WORKER_PU = pd.read_parquet(
        ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    _WORKER_AU = pd.read_parquet(
        ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    _WORKER_KW = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
                      player_usage=_WORKER_PU, active_uni=_WORKER_AU)


def _run_one_game(args):
    """Process a single game. Returns (game_id, wall_time, n_iter, converged)."""
    game_id, home, away, season, week, spread, total_line, engine_commit = args
    out_path = GAMES_DIR / f"{game_id}.parquet"
    if out_path.exists():
        return (game_id, 0.0, 0, True, "skipped")

    from nfl.sim.anchor import run_anchored_chunked

    t0 = time.time()
    # D55: no except-and-continue. Any exception propagates to the pool,
    # kills it, and exits non-zero with the game_id.
    td, pdf, dh, da, n_iter, conv, raw_m, raw_t, anch_m, anch_t = \
        run_anchored_chunked(
            home, away, season, week, spread, total_line,
            **_WORKER_KW)
    dt = time.time() - t0

    # Build checkpoint
    N = len(td)
    margin = (td["home_score"] - td["away_score"]).values.astype(np.float32)
    total_arr = (td["home_score"] + td["away_score"]).values.astype(np.float32)
    se_m = margin.std() / np.sqrt(N)
    se_t = total_arr.std() / np.sqrt(N)

    rows = {
        "sim_id": np.arange(N),
        "margin": margin,
        "total": total_arr,
        "home_score": td["home_score"].values.astype(np.float32),
        "away_score": td["away_score"].values.astype(np.float32),
    }

    # Add player stats if available
    if pdf is not None and len(pdf) > 0:
        # Keep the full player DataFrame for prop map fitting
        pdf_save = pdf[["sim_id", "player_id", "player_name", "position", "team",
                        "targets", "receptions", "rec_yds", "carries", "rush_yds",
                        "pass_att", "pass_cmp", "pass_yds", "pass_td",
                        "anytime_td"]].copy()
        pdf_save.to_parquet(GAMES_DIR / f"{game_id}_players.parquet", index=False)

    # Anchoring metadata
    meta = {
        "game_id": game_id, "season": season, "week": week,
        "home": home, "away": away,
        "spread": spread, "total_line": total_line,
        "dh": dh, "da": da, "n_iter": n_iter, "converged": conv,
        "raw_m": raw_m, "raw_t": raw_t, "anch_m": anch_m, "anch_t": anch_t,
        "final_err_m": abs(spread - anch_m), "final_err_t": abs(total_line - anch_t),
        "se_m": float(se_m), "se_t": float(se_t),
        "n_sims": N, "wall_time": dt,
        "engine_commit": engine_commit,
    }

    # Save checkpoint: sim-level data + metadata as attrs
    checkpoint = pd.DataFrame(rows)
    for k, v in meta.items():
        checkpoint.attrs[k] = v
    checkpoint.to_parquet(out_path, index=False)

    del td, pdf
    gc.collect()

    return (game_id, dt, n_iter, conv, "done")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    args = parser.parse_args()

    t_start = time.time()
    GAMES_DIR.mkdir(parents=True, exist_ok=True)

    engine_commit = _get_engine_commit()
    print(f"Engine commit: {engine_commit}")

    # Load game list
    all_games = []
    for s in args.seasons:
        pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        if not pbp_path.exists():
            print(f"WARNING: pbp_{s}.parquet not found, skipping")
            continue
        df = pd.read_parquet(pbp_path,
            columns=["game_id", "season", "week", "home_team", "away_team",
                     "spread_line", "total_line"])
        g = df.drop_duplicates("game_id")
        g = g[(g["week"] <= 18) & g["spread_line"].notna() & g["total_line"].notna()]
        for _, row in g.iterrows():
            all_games.append((
                row["game_id"], row["home_team"], row["away_team"],
                int(row["season"]), int(row["week"]),
                float(row["spread_line"]), float(row["total_line"]),
                engine_commit,
            ))

    # Count already done
    done = [gid for gid, *_ in all_games if (GAMES_DIR / f"{gid}.parquet").exists()]
    todo = len(all_games) - len(done)
    print(f"Games: {len(all_games)} total, {len(done)} done, {todo} to run")

    if todo == 0:
        print("All games already checkpointed.")
        return

    # Worker count
    import psutil, resource
    cores = psutil.cpu_count(logical=False)
    avail_mem = psutil.virtual_memory().available
    peak_rss_mb = 321  # measured from single-game run
    workers_by_mem = int(0.7 * avail_mem / (peak_rss_mb * 1024 * 1024))
    workers = min(cores - 1, workers_by_mem)
    workers = max(1, workers)
    print(f"Workers: {workers} (cores={cores}, avail_mem={avail_mem/1e9:.1f}GB, "
          f"peak_rss={peak_rss_mb}MB)")

    # D55: any exception kills the pool and exits non-zero.
    completed = 0
    conv_count = 0
    try:
        with Pool(workers, initializer=_worker_init) as pool:
            for result in pool.imap_unordered(_run_one_game, all_games):
                game_id, dt, n_iter, conv, status = result
                if status == "skipped":
                    continue
                completed += 1
                if conv:
                    conv_count += 1
                flag = "" if conv else " [NOT CONVERGED]"
                print(f"  [{completed}/{todo}] {game_id}: {dt:.1f}s, {n_iter} iter{flag}",
                      flush=True)
    except Exception as e:
        print(f"\nFATAL: worker exception after {completed} games: {e}",
              file=sys.stderr)
        sys.exit(1)

    total_time = time.time() - t_start
    print(f"\nFit complete: {completed} games in {total_time:.0f}s "
          f"({total_time/60:.1f} min)")
    print(f"Converged: {conv_count}/{completed}")

    # Write census
    census_rows = []
    for gid, *_ in all_games:
        cp_path = GAMES_DIR / f"{gid}.parquet"
        if cp_path.exists():
            cp = pd.read_parquet(cp_path)
            census_rows.append({
                "game_id": gid,
                "season": cp.attrs.get("season"),
                "week": cp.attrs.get("week"),
                "converged": cp.attrs.get("converged"),
                "n_iter": cp.attrs.get("n_iter"),
                "final_err_m": cp.attrs.get("final_err_m"),
                "final_err_t": cp.attrs.get("final_err_t"),
                "se_m": cp.attrs.get("se_m"),
                "se_t": cp.attrs.get("se_t"),
                "wall_time": cp.attrs.get("wall_time"),
                "n_sims": cp.attrs.get("n_sims"),
            })
    census = pd.DataFrame(census_rows)
    census.to_parquet(OUT_DIR / "fit_census.parquet", index=False)
    print(f"Census written: {OUT_DIR / 'fit_census.parquet'}")

    # Print convergence by season
    for s in sorted(census["season"].unique()):
        sc = census[census["season"] == s]
        n_conv = sc["converged"].sum()
        print(f"  Season {s}: {n_conv}/{len(sc)} converged "
              f"({(1-n_conv/len(sc))*100:.1f}% unconverged)")


if __name__ == "__main__":
    main()
