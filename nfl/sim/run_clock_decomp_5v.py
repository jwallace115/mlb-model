#!/usr/bin/env python3
"""
5V Item 3: Decompose the seconds-per-snap gap between sim and real.

Sim: D144 sample (200 K1 games, N=100) with play_log.
Real: PBP 2021-24 REG, elapsed = diff in game_seconds_remaining between
consecutive snaps in the same half.
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

SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 100
N_GAMES = 200


def load_real_snaps():
    """Real per-snap elapsed from PBP 2021-24 REG.

    elapsed = diff in game_seconds_remaining between consecutive snaps in the
    same half. Classified by play outcome for mix decomposition.
    """
    frames = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        # Only scrimmage-like plays (match the engine's n_plays events)
        play_mask = df["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])
        # Exclude 2pt attempts
        two_pt = df.get("two_point_attempt", pd.Series(0, index=df.index)).fillna(0)
        scrim = df[play_mask & (two_pt == 0)].copy()

        # Compute elapsed as diff in game_seconds_remaining within game+half
        scrim = scrim.sort_values(["game_id", "game_seconds_remaining"], ascending=[True, False])
        scrim["elapsed"] = -scrim.groupby(["game_id", "game_half"])["game_seconds_remaining"].diff()
        # First play of each half has NaN elapsed
        scrim = scrim[scrim["elapsed"].notna() & (scrim["elapsed"] > 0) & (scrim["elapsed"] < 120)]

        # Score differential from offense's perspective
        scrim["off_sd"] = scrim["score_differential"]

        scrim["season"] = s
        frames.append(scrim[["game_id", "season", "qtr", "elapsed", "play_type",
                              "off_sd", "incomplete_pass", "sack",
                              "game_seconds_remaining"]])
    return pd.concat(frames, ignore_index=True)


def run_sim_play_log():
    """Run D144 sample with play_log."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    games = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        gs = df.drop_duplicates("game_id")[["game_id", "home_team", "away_team", "week"]].to_dict("records")
        games.extend([{**g, "season": s} for g in gs])
    games = sorted(games, key=lambda g: g["game_id"])[:N_GAMES]

    all_play_rows = []
    for gi, g in enumerate(games):
        seed = stable_seed((g["home_team"], g["away_team"], g["season"], int(g["week"]), 42))
        r = simulate_game(g["home_team"], g["away_team"], g["season"], int(g["week"]),
                          n_sims=N_SIMS, seed=seed, team_r=team_r, tend=tend, sit=sit,
                          kicker=kicker, league=league, drive_log=True)
        pl = r.attrs.get("play_log")
        if pl is not None and len(pl) > 0:
            pl = pl.copy()
            pl["game_id"] = g["game_id"]
            all_play_rows.append(pl)
        if (gi + 1) % 50 == 0:
            print(f"  {gi+1}/{N_GAMES} games...")
        gc.collect()

    return pd.concat(all_play_rows, ignore_index=True)


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")

    # Real side
    print("Loading real snaps from PBP 2021-24 REG...")
    real = load_real_snaps()
    n_real_games = real["game_id"].nunique()
    print(f"  {len(real)} snaps from {n_real_games} games")

    # Sim side
    print(f"Running sim: {N_GAMES} games, N={N_SIMS}, drive_log=True...")
    sim = run_sim_play_log()
    print(f"  {len(sim)} sim snaps")

    # Save
    out_path = ROOT / "research" / "nfl_sim" / "phase5v_clock_decomp.parquet"
    sim.to_parquet(out_path, index=False)
    print(f"  Saved {out_path}")

    # ---- Report ----
    # Per-game totals
    sim_snaps_pg = len(sim) / (N_GAMES * N_SIMS)
    real_snaps_pg = len(real) / n_real_games
    sim_elapsed_pg = sim["elapsed"].sum() / (N_GAMES * N_SIMS)
    real_elapsed_pg = real["elapsed"].sum() / n_real_games

    print(f"\n{'='*80}")
    print("OVERALL")
    print(f"{'='*80}")
    print(f"  Sim snaps/game: {sim_snaps_pg:.1f}")
    print(f"  Real snaps/game: {real_snaps_pg:.1f} (excl first snap of each half)")
    print(f"  Sim total clock/game: {sim_elapsed_pg:.1f}")
    print(f"  Real total clock/game: {real_elapsed_pg:.1f}")
    print(f"  Sim mean elapsed/snap: {sim['elapsed'].mean():.2f}")
    print(f"  Real mean elapsed/snap: {real['elapsed'].mean():.2f}")
    print(f"  Diff: {sim['elapsed'].mean() - real['elapsed'].mean():+.2f}")

    # By quarter
    print(f"\n{'='*80}")
    print("BY QUARTER")
    print(f"{'='*80}")
    print(f"{'qtr':>4s} {'sim_mean':>10s} {'real_mean':>10s} {'diff':>8s} {'sim_n/g':>8s} {'real_n/g':>8s}")
    for q in [1, 2, 3, 4]:
        sq = sim[sim["qtr"] == q]
        rq = real[real["qtr"] == q]
        s_mean = sq["elapsed"].mean() if len(sq) > 0 else 0
        r_mean = rq["elapsed"].mean() if len(rq) > 0 else 0
        s_ng = len(sq) / (N_GAMES * N_SIMS)
        r_ng = len(rq) / n_real_games
        print(f"{q:4d} {s_mean:10.2f} {r_mean:10.2f} {s_mean - r_mean:+8.2f} {s_ng:8.1f} {r_ng:8.1f}")

    # By score state
    print(f"\n{'='*80}")
    print("BY SCORE STATE")
    print(f"{'='*80}")
    for label, lo, hi in [("trail 9+", -999, -9), ("within 8", -8, 8), ("lead 9+", 9, 999)]:
        sq = sim[(sim["score_diff"] >= lo) & (sim["score_diff"] <= hi)]
        rq = real[(real["off_sd"] >= lo) & (real["off_sd"] <= hi)]
        if len(sq) > 0 and len(rq) > 0:
            print(f"  {label:12s}: sim {sq['elapsed'].mean():.2f}s ({len(sq)/(N_GAMES*N_SIMS):.1f}/g) "
                  f" real {rq['elapsed'].mean():.2f}s ({len(rq)/n_real_games:.1f}/g) "
                  f" diff {sq['elapsed'].mean()-rq['elapsed'].mean():+.2f}")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")
    print(f"Fingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
