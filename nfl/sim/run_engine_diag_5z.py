#!/usr/bin/env python3
"""
5Z: Run the shared sample (200 games, 50/season, seed 42, N=100) with play_log + drive_log.
Produces all data needed for Items 0-2.
"""
import sys, time, gc, json
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


def select_games():
    """50 games per season, seed 42 — the 5X/5Y sample."""
    rng = np.random.default_rng(42)
    all_games = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        gids = sorted(df["game_id"].unique())
        chosen = sorted(rng.choice(gids, N_PER_SEASON, replace=False))
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
    print(f"Selected {len(games)} games")

    # Save sample game IDs
    with open(ROOT / "research" / "nfl_sim" / "phase5z_sample.txt", "w") as f:
        for g in games:
            f.write(f"{g['game_id']}\n")
    print(f"Saved phase5z_sample.txt")

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    # Run ONE pass with play_log + drive_log
    all_team_dfs = []
    all_play_logs = []
    all_drive_logs = []
    all_int_chains = []

    for gi, g in enumerate(games):
        seed = stable_seed((g["home_team"], g["away_team"], g["season"], int(g["week"]), 42))
        r = simulate_game(g["home_team"], g["away_team"], g["season"], int(g["week"]),
                          n_sims=N_SIMS, seed=seed, team_r=team_r, tend=tend, sit=sit,
                          kicker=kicker, league=league, drive_log=True)

        r["game_id"] = g["game_id"]
        r["season"] = g["season"]
        all_team_dfs.append(r[["game_id", "season", "home_score", "away_score", "plays", "drives",
                                "ev_safeties", "ev_punts", "ev_fg_att", "ev_tds",
                                "ev_clock_used", "ot_flag"]].copy())

        pl = r.attrs.get("play_log")
        if pl is not None and len(pl) > 0:
            pl = pl.copy()
            pl["game_id"] = g["game_id"]
            pl["season"] = g["season"]
            all_play_logs.append(pl)

        dl = r.attrs.get("drive_log")
        if dl is not None:
            dldf = pd.DataFrame(dl) if not isinstance(dl, pd.DataFrame) else dl.copy()
            dldf["game_id"] = g["game_id"]
            dldf["season"] = g["season"]
            all_drive_logs.append(dldf)

        if (gi + 1) % 25 == 0:
            elapsed = time.time() - t0
            print(f"  {gi+1}/{len(games)} games ({elapsed:.0f}s)")
        gc.collect()

    # Concatenate
    team_df = pd.concat(all_team_dfs, ignore_index=True)
    play_log = pd.concat(all_play_logs, ignore_index=True) if all_play_logs else pd.DataFrame()
    drive_log = pd.concat(all_drive_logs, ignore_index=True) if all_drive_logs else pd.DataFrame()

    total = time.time() - t0
    print(f"\nSim complete: {total:.0f}s ({total/60:.1f} min)")
    print(f"  team_df: {len(team_df)} rows")
    print(f"  play_log: {len(play_log)} rows")
    print(f"  drive_log: {len(drive_log)} rows")

    # Summary stats
    n_total_sims = len(games) * N_SIMS
    print(f"\n=== SUMMARY ===")
    print(f"  plays/game: {team_df['plays'].mean():.1f}")
    print(f"  drives/game: {team_df['drives'].mean():.1f}")
    print(f"  safeties/game: {team_df['ev_safeties'].mean():.3f}")
    print(f"  pts/team: {(team_df['home_score'].mean() + team_df['away_score'].mean())/2:.2f}")

    # Save summary (small)
    summary = {
        "n_games": len(games), "n_sims": N_SIMS, "n_total": n_total_sims,
        "plays_pg": float(team_df["plays"].mean()),
        "drives_pg": float(team_df["drives"].mean()),
        "safeties_pg": float(team_df["ev_safeties"].mean()),
        "pts_team": float((team_df["home_score"].mean() + team_df["away_score"].mean()) / 2),
    }
    with open(ROOT / "research" / "nfl_sim" / "phase5z_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return team_df, play_log, drive_log, games


if __name__ == "__main__":
    team_df, play_log, drive_log, games = main()
