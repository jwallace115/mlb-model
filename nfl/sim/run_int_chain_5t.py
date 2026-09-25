#!/usr/bin/env python3
"""
5T Item 1: Instrument the INT chain and place the 3.3-yard residual.

200 K1 games (first by game_id, seed 42), N=100, drive_log=True.
Real side from PBP 2021-24 REG with identical definitions.
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


def load_real_int_chain():
    """Real INT chain from PBP 2021-24 REG.
    six = touchdown==1 & td_team==defteam; ez = (yardline_100 - clip(air_yards,0)) <= 0 & ~six;
    next start = yardline_100 of the first scrimmage play of the next fixed_drive."""
    rows = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        ints = df[df["interception"] == 1].copy()
        scrim = df[df["play_type"].isin(["pass", "run"])]
        for _, ir in ints.iterrows():
            gid = ir["game_id"]
            los = ir.get("yardline_100", np.nan)
            air = max(ir.get("air_yards", 0) or 0, 0)
            ret = ir.get("return_yards", 0) or 0
            catch_yl = los - air if pd.notna(los) else np.nan
            td_flag = ir.get("touchdown", 0) == 1
            td_team = ir.get("td_team", "")
            defteam = ir.get("defteam", "")
            six = td_flag and td_team == defteam
            ez = (catch_yl is not None and not np.isnan(catch_yl) and catch_yl <= 0) and not six
            # Next drive start
            drv = ir.get("fixed_drive")
            next_start = np.nan
            if pd.notna(drv):
                game_scrim = scrim[scrim["game_id"] == gid]
                nxt = game_scrim[game_scrim["fixed_drive"] > drv]
                if len(nxt) > 0:
                    next_start = nxt.iloc[0]["yardline_100"]
            rows.append({
                "los": los, "air": air, "catch_yl": catch_yl,
                "ez": ez, "ret": ret, "six": six, "next_start": next_start,
            })
    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")

    # ---- Real side ----
    print("Loading real INT chain from PBP 2021-24 REG...")
    real = load_real_int_chain()
    print(f"  {len(real)} INT events")

    # ---- Sim side ----
    print(f"Running sim: {N_GAMES} games, N={N_SIMS}, drive_log=True...")
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    games = []
    for s in SEASONS:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        df = pd.read_parquet(p)
        df = df[df["season_type"] == "REG"]
        gs = df.drop_duplicates("game_id")[["game_id", "home_team", "away_team", "week"]].to_dict("records")
        games.extend([{**g, "season": s} for g in gs])
    games = sorted(games, key=lambda g: g["game_id"])[:N_GAMES]

    sim_int_rows = []
    for gi, g in enumerate(games):
        seed = stable_seed((g["home_team"], g["away_team"], g["season"], int(g["week"]), 42))
        r = simulate_game(g["home_team"], g["away_team"], g["season"], int(g["week"]),
                          n_sims=N_SIMS, seed=seed, team_r=team_r, tend=tend, sit=sit,
                          kicker=kicker, league=league, drive_log=True)
        icl = r.attrs.get("int_chain_log")
        if icl is not None and len(icl) > 0:
            for _, row in icl.iterrows():
                sim_int_rows.append(dict(row))
        if (gi + 1) % 50 == 0:
            print(f"  {gi+1}/{N_GAMES} games...")
        gc.collect()

    sim = pd.DataFrame(sim_int_rows)
    sim_runtime = time.time() - t0
    print(f"  {len(sim)} sim INT events in {sim_runtime:.0f}s")

    # Save
    out_path = ROOT / "research" / "nfl_sim" / "phase5t_int_chain.parquet"
    sim.to_parquet(out_path, index=False)
    print(f"  Saved {out_path}")

    # ---- Report ----
    # Classify into three cells: six, ez, other
    real_valid = real.dropna(subset=["next_start"])
    for df_name, df_data in [("REAL", real_valid), ("SIM", sim)]:
        print(f"\n{'='*80}")
        print(f"{df_name} INT CHAIN ({len(df_data)} events)")
        print(f"{'='*80}")

        six_mask = df_data["six"] == True
        ez_mask = (df_data["ez"] == True) & ~six_mask
        other_mask = ~six_mask & ~ez_mask

        for label, mask in [("six", six_mask), ("ez", ez_mask), ("other", other_mask)]:
            sub = df_data[mask]
            share = len(sub) / len(df_data) * 100
            if label == "six":
                # Pick-six: next_start is kickoff
                ns = sub["next_start"].dropna()
                mean_ns = ns.mean() if len(ns) > 0 else float("nan")
            else:
                ns = sub["next_start"].dropna()
                mean_ns = ns.mean() if len(ns) > 0 else float("nan")
            print(f"  {label:6s}: {share:5.1f}%  n={len(sub):5d}  mean next_start={mean_ns:.1f}")

        # LOS distribution
        los = df_data["los"].dropna()
        pcts = [10, 25, 50, 75, 90]
        print(f"\n  LOS: ", end="")
        for p in pcts:
            print(f"p{p}={np.percentile(los, p):.1f} ", end="")
        print(f"mean={los.mean():.1f}")

        # Air distribution
        air = df_data["air"].dropna()
        if len(air) > 0:
            print(f"  Air: ", end="")
            for p in pcts:
                print(f"p{p}={np.percentile(air, p):.1f} ", end="")
            print(f"mean={air.mean():.1f}")

        # Return distribution
        ret = df_data["ret"].dropna()
        if len(ret) > 0:
            print(f"  Ret: ", end="")
            for p in pcts:
                print(f"p{p}={np.percentile(ret, p):.1f} ", end="")
            print(f"mean={ret.mean():.1f}")

    # Overall next_start comparison
    print(f"\n{'='*80}")
    print("OVERALL NEXT START COMPARISON")
    print(f"{'='*80}")
    sim_ns = sim[~sim["six"]]["next_start"].dropna()
    real_ns = real_valid[~real_valid["six"]]["next_start"].dropna()
    print(f"  Sim (excl six): mean={sim_ns.mean():.1f}  n={len(sim_ns)}")
    print(f"  Real (excl six): mean={real_ns.mean():.1f}  n={len(real_ns)}")
    print(f"  Diff: {sim_ns.mean() - real_ns.mean():+.1f}")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")
    print(f"Fingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
