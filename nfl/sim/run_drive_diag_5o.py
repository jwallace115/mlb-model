#!/usr/bin/env python3
"""
5O Item 3: Drive decomposition using drive_log=True.

Runs K1's sample and N with drive_log=True, aggregates the returned drive logs.
Sim vs real drives per game by ending type, plays per drive by ending,
seconds consumed per drive by ending, drives started in final 2:00 of each half.
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

SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 500  # Same as K1


def load_real_drives():
    """Drive-level stats from PBP 2021-24. Derivation: each row in PBP with a
    non-null `drive` column belongs to one drive; `fixed_drive_result` gives the
    ending type; scrimmage plays = play_type in {pass, run}."""
    frames = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        drives = df.dropna(subset=["drive"]).groupby(["game_id", "drive"]).agg(
            n_plays=("play_id", "count"),
            first_qtr=("qtr", "first"),
            drive_result=("fixed_drive_result", "first"),
            start_time=("game_seconds_remaining", "max"),
            end_time=("game_seconds_remaining", "min"),
        ).reset_index()
        drives["season"] = s
        drives["clock_consumed"] = drives["start_time"] - drives["end_time"]

        scrim = df[df["play_type"].isin(["pass", "run"])]
        scrim_per_drive = scrim.groupby(["game_id", "drive"]).agg(
            scrim_plays=("play_id", "count"),
        ).reset_index()
        drives = drives.merge(scrim_per_drive, on=["game_id", "drive"], how="left")
        drives["scrim_plays"] = drives["scrim_plays"].fillna(0).astype(int)
        frames.append(drives)
    return pd.concat(frames, ignore_index=True)


def run_sim_drives():
    """Run K1's sample with drive_log=True, return aggregated drive logs."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    all_drives = []
    game_count = 0
    for s in SEASONS:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        df = pd.read_parquet(p)
        games = df.drop_duplicates("game_id")[["game_id", "home_team", "away_team",
                                                "home_score", "away_score"]].dropna(subset=["home_score"])
        for _, g in games.iterrows():
            home = g["home_team"]
            away = g["away_team"]
            week_rows = df[df["game_id"] == g["game_id"]]
            week = int(week_rows["week"].iloc[0])
            seed = stable_seed((home, away, s, week, 42))

            r = simulate_game(home, away, s, week, n_sims=N_SIMS, seed=seed,
                              team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                              league=league, drive_log=True)
            dl = r.attrs.get("drive_log")
            if dl is not None and len(dl) > 0:
                dl_df = pd.DataFrame(dl) if not isinstance(dl, pd.DataFrame) else dl
                dl_df["game_id"] = g["game_id"]
                dl_df["season"] = s
                all_drives.append(dl_df)
            game_count += 1
            if game_count % 100 == 0:
                print(f"  {game_count} games...")

    return pd.concat(all_drives, ignore_index=True), game_count


def main():
    t0 = time.time()
    print(f"engine_fingerprint: {engine_fingerprint()}")

    # Real drives
    print("Loading real drives from PBP...")
    real = load_real_drives()
    n_real_games = real["game_id"].nunique()
    ending_map = {"Punt": "punt", "Touchdown": "TD", "Field goal": "FG",
                  "Turnover": "turnover", "Turnover on downs": "downs",
                  "End of half": "end_half", "Safety": "safety",
                  "Opp touchdown": "opp_TD"}
    real["end_type"] = real["drive_result"].map(ending_map).fillna("other")

    # Sim drives
    print(f"Running sim with drive_log=True ({N_SIMS} sims/game)...")
    sim_dl, n_sim_games = run_sim_drives()
    sim_runtime = time.time() - t0

    # Map sim result names to categories matching real
    sim_result_map = {"TD": "TD", "FG_made": "FG", "FG_missed": "FG_miss",
                      "punt": "punt", "turnover_int": "turnover",
                      "turnover_fumble": "turnover", "downs": "downs",
                      "end_half": "end_half", "end_game": "end_half",
                      "safety": "safety"}
    sim_dl["end_type"] = sim_dl["result"].map(sim_result_map).fillna("other")

    # Per-game means (sim: divide by n_sim_games * N_SIMS)
    sim_total_sims = n_sim_games * N_SIMS

    print(f"\n{'='*70}")
    print(f"DRIVES PER GAME BY ENDING TYPE")
    print(f"{'='*70}")
    print(f"{'end_type':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)

    real_dpg = real.groupby("end_type").size() / n_real_games
    sim_dpg = sim_dl.groupby("end_type").size() / sim_total_sims

    for et in ["punt", "TD", "FG", "turnover", "downs", "end_half", "safety"]:
        r_val = real_dpg.get(et, 0)
        s_val = sim_dpg.get(et, 0)
        if et == "FG":
            # Sim: FG_made + FG_miss
            s_val = sim_dpg.get("FG", 0) + sim_dpg.get("FG_miss", 0)
        print(f"{et:12s} {r_val:8.2f} {s_val:8.2f} {s_val - r_val:+8.2f}")

    real_total = real_dpg.sum()
    sim_total = sim_dl.shape[0] / sim_total_sims
    print(f"{'TOTAL':12s} {real_total:8.2f} {sim_total:8.2f} {sim_total - real_total:+8.2f}")

    # Plays per drive by ending
    print(f"\n{'='*70}")
    print(f"PLAYS PER DRIVE BY ENDING TYPE (scrimmage plays for real; drive_log plays for sim)")
    print(f"{'='*70}")
    print(f"{'end_type':12s} {'real':>8s} {'sim':>8s} {'diff':>8s} {'n_real':>8s} {'n_sim':>8s}")
    print("-" * 55)

    for et in ["punt", "TD", "FG", "turnover", "downs"]:
        r_sub = real[real["end_type"] == et]
        if et == "FG":
            s_sub = sim_dl[sim_dl["end_type"].isin(["FG", "FG_miss"])]
        else:
            s_sub = sim_dl[sim_dl["end_type"] == et]
        r_ppd = r_sub["scrim_plays"].mean() if len(r_sub) > 0 else 0
        s_ppd = s_sub["plays"].mean() if len(s_sub) > 0 else 0
        print(f"{et:12s} {r_ppd:8.2f} {s_ppd:8.2f} {s_ppd - r_ppd:+8.2f} "
              f"{len(r_sub):8d} {len(s_sub):8d}")

    # Seconds consumed per drive by ending
    print(f"\n{'='*70}")
    print(f"SECONDS CONSUMED PER DRIVE BY ENDING TYPE")
    print(f"{'='*70}")
    # Sim: clock consumed = start_clock of this drive - start_clock of next drive (same sim)
    # Approximate: sort by (game_id, sim_id, drive_no), compute diff
    sim_dl_sorted = sim_dl.sort_values(["game_id", "sim_id", "drive_no"])
    sim_dl_sorted["next_start"] = sim_dl_sorted.groupby(["game_id", "sim_id"])["start_clock"].shift(-1)
    sim_dl_sorted["clock_consumed"] = sim_dl_sorted["start_clock"] - sim_dl_sorted["next_start"]
    # Drop last drive per sim (no next drive)
    sim_with_clock = sim_dl_sorted[sim_dl_sorted["clock_consumed"].notna()]

    print(f"{'end_type':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)
    for et in ["punt", "TD", "FG", "turnover"]:
        r_sub = real[real["end_type"] == et]
        if et == "FG":
            s_sub = sim_with_clock[sim_with_clock["end_type"].isin(["FG", "FG_miss"])]
        else:
            s_sub = sim_with_clock[sim_with_clock["end_type"] == et]
        r_sec = r_sub["clock_consumed"].mean() if len(r_sub) > 0 else 0
        s_sec = s_sub["clock_consumed"].mean() if len(s_sub) > 0 else 0
        print(f"{et:12s} {r_sec:8.1f} {s_sec:8.1f} {s_sec - r_sec:+8.1f}")

    # Drives started in final 2:00 of each half
    print(f"\n{'='*70}")
    print(f"DRIVES STARTED IN FINAL 2:00 OF EACH HALF")
    print(f"{'='*70}")
    # Real: start_time <= 120 in Q2 (half_seconds) or Q4 (game_seconds)
    r_late_q2 = real[(real["first_qtr"] == 2) & (real["start_time"] <= 120)]
    r_late_q4 = real[(real["first_qtr"] == 4) & (real["start_time"] <= 120)]
    # Sim: start_clock <= 120 and start_quarter in {2, 4}
    s_late_q2 = sim_dl[(sim_dl["start_quarter"] == 2) & (sim_dl["start_clock"] <= 120)]
    s_late_q4 = sim_dl[(sim_dl["start_quarter"] == 4) & (sim_dl["start_clock"] <= 120)]
    print(f"  Q2 last 2:00: real {len(r_late_q2)/n_real_games:.2f}/game, sim {len(s_late_q2)/sim_total_sims:.2f}/game")
    print(f"  Q4 last 2:00: real {len(r_late_q4)/n_real_games:.2f}/game, sim {len(s_late_q4)/sim_total_sims:.2f}/game")

    total_runtime = time.time() - t0
    print(f"\nRuntime: {total_runtime:.0f}s ({total_runtime/60:.1f} min)")
    print(f"Games: {n_sim_games}, sims/game: {N_SIMS}")


if __name__ == "__main__":
    main()
