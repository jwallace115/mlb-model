#!/usr/bin/env python3
"""
5P Item 1: Why are scoring drives short?

Runs K1 sample (N=100, drive_log=True), aggregates per game inside the loop
to avoid memory issues. Compares sim drive starts, yards/play, play-count
distributions, and explosive plays against PBP 2021-24 REG.

Converts drive log start_clock to game seconds: (4 - min(qtr,4)) * 900 + start_clock
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
N_SIMS = 100  # per the order (aggregate per game)

SIM_RESULT_MAP = {
    "TD": "TD", "FG_made": "FG", "FG_missed": "FG_miss",
    "punt": "punt", "turnover_int": "turnover", "turnover_fumble": "turnover",
    "downs": "downs", "end_half": "end_half", "end_game": "end_half",
    "safety": "safety",
}

REAL_RESULT_MAP = {
    "Touchdown": "TD", "Field goal": "FG", "Missed field goal": "FG_miss",
    "Punt": "punt", "Turnover": "turnover", "Turnover on downs": "downs",
    "End of half": "end_half", "Opp touchdown": "opp_TD", "Safety": "safety",
}


def load_real_drives():
    """Drive-level stats from PBP 2021-24 REG.
    Derivation: fixed_drive groups plays into drives; fixed_drive_result is the ending.
    Start yardline = yardline_100 of the first scrimmage play (pass or run) in the drive.
    Plays = count of pass + run plays. Seconds = max - min game_seconds_remaining.
    Yards = max(ydsnet) - min(ydsnet) within the drive (net yards gained)."""
    frames = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        scrim = df[df["play_type"].isin(["pass", "run"])].copy()

        # Per-drive aggregates from scrimmage plays
        drive_agg = scrim.groupby(["game_id", "fixed_drive"]).agg(
            start_yl=("yardline_100", "first"),  # first scrimmage play's yardline_100
            n_plays=("play_id", "count"),
            yards_gained_sum=("yards_gained", "sum"),
            explosive_20=("yards_gained", lambda x: (x >= 20).sum()),
        ).reset_index()

        # Duration from all plays (including non-scrimmage)
        drive_time = df.dropna(subset=["fixed_drive"]).groupby(["game_id", "fixed_drive"]).agg(
            seconds=("game_seconds_remaining", lambda x: x.max() - x.min()),
            drive_result=("fixed_drive_result", "first"),
        ).reset_index()

        merged = drive_agg.merge(drive_time, on=["game_id", "fixed_drive"], how="inner")
        merged["season"] = s
        merged["end_type"] = merged["drive_result"].map(REAL_RESULT_MAP).fillna("other")
        frames.append(merged)

    return pd.concat(frames, ignore_index=True)


def run_sim_drives():
    """Run K1's sample, N=100, drive_log=True.
    Aggregates per game inside the loop to control memory."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    game_rows = []  # per-game x ending aggregates
    game_count = 0

    for s in SEASONS:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        df = pd.read_parquet(p)
        df = df[df["season_type"] == "REG"]
        games = df.drop_duplicates("game_id")[
            ["game_id", "home_team", "away_team", "home_score", "away_score"]
        ].dropna(subset=["home_score"])

        for _, g in games.iterrows():
            home, away = g["home_team"], g["away_team"]
            week_rows = df[df["game_id"] == g["game_id"]]
            week = int(week_rows["week"].iloc[0])
            seed = stable_seed((home, away, s, week, 42))

            r = simulate_game(home, away, s, week, n_sims=N_SIMS, seed=seed,
                              team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                              league=league, drive_log=True)
            dl = r.attrs.get("drive_log")
            if dl is None:
                game_count += 1
                continue

            dl_df = pd.DataFrame(dl) if not isinstance(dl, pd.DataFrame) else dl.copy()

            # Convert start_clock (quarter clock) to game seconds
            # (4 - min(qtr, 4)) * 900 + start_clock
            dl_df["game_seconds"] = (4 - np.minimum(dl_df["start_quarter"].values, 4)) * 900 + dl_df["start_clock"].values

            # Map result to end_type
            dl_df["end_type"] = dl_df["result"].map(SIM_RESULT_MAP).fillna("other")

            # Aggregate per ending type within this game
            for et, grp in dl_df.groupby("end_type"):
                inside_40 = (grp["start_yardline"] <= 40).sum()
                explosive = (grp["yards"] >= 20).sum()  # drives with 20+ yards total
                # For explosive PLAYS per drive: the drive log only has total yards,
                # not individual play yards. We can't compute explosive play share
                # from the drive log directly. But we CAN count "short-field" drives.
                game_rows.append({
                    "game_id": g["game_id"],
                    "season": s,
                    "end_type": et,
                    "n": len(grp) / N_SIMS,  # drives per sim
                    "plays_sum": grp["plays"].sum() / N_SIMS,
                    "yards_sum": grp["yards"].sum() / N_SIMS,
                    "seconds_sum": 0,  # compute from game_seconds diffs below
                    "start_yl_sum": grp["start_yardline"].sum() / N_SIMS,
                    "inside_40_n": inside_40 / N_SIMS,
                    "plays_1_3": ((grp["plays"] >= 1) & (grp["plays"] <= 3)).sum() / N_SIMS,
                    "plays_4_6": ((grp["plays"] >= 4) & (grp["plays"] <= 6)).sum() / N_SIMS,
                    "plays_7_9": ((grp["plays"] >= 7) & (grp["plays"] <= 9)).sum() / N_SIMS,
                    "plays_10p": (grp["plays"] >= 10).sum() / N_SIMS,
                })

            # Duration: sort by sim_id + drive_no, diff game_seconds
            dl_df = dl_df.sort_values(["sim_id", "drive_no"])
            dl_df["next_gs"] = dl_df.groupby("sim_id")["game_seconds"].shift(-1)
            dl_df["duration"] = dl_df["next_gs"] - dl_df["game_seconds"]
            # Positive duration = correct (game_seconds increases as game progresses)
            # Actually game_seconds = (4-qtr)*900 + clock. As game progresses, qtr increases
            # and clock decreases. Let me think...
            # Q1 start: (4-1)*900 + 900 = 3600
            # Q1 end: (4-1)*900 + 0 = 2700
            # Q2 start: (4-2)*900 + 900 = 2700
            # Q4 end: (4-4)*900 + 0 = 0
            # So game_seconds DECREASES as game progresses.
            # Duration of a drive = start_game_seconds - next_drive_start_game_seconds
            dl_df["duration"] = dl_df["game_seconds"] - dl_df["next_gs"]
            valid_dur = dl_df[dl_df["duration"].notna() & (dl_df["duration"] > 0)]

            for et, grp in valid_dur.groupby("end_type"):
                # Find matching row in game_rows (same game_id, end_type)
                for row in game_rows:
                    if row["game_id"] == g["game_id"] and row["end_type"] == et:
                        row["seconds_sum"] = grp["duration"].sum() / N_SIMS
                        break

            game_count += 1
            if game_count % 200 == 0:
                print(f"  {game_count} games...")
            del dl_df, dl
            gc.collect()

    return pd.DataFrame(game_rows), game_count


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")
    assert fp == "02fbcab6e6ed042e", f"WRONG fingerprint: {fp}"

    # ---- Real drives ----
    print("Loading real drives from PBP 2021-24 REG...")
    real = load_real_drives()
    n_real_games = real["game_id"].nunique()
    print(f"  {n_real_games} real games, {len(real)} drives")

    # Real drive play-count distribution for TD drives
    real_td = real[real["end_type"] == "TD"]
    real_td_plays_1_3 = ((real_td["n_plays"] >= 1) & (real_td["n_plays"] <= 3)).sum()
    real_td_plays_4_6 = ((real_td["n_plays"] >= 4) & (real_td["n_plays"] <= 6)).sum()
    real_td_plays_7_9 = ((real_td["n_plays"] >= 7) & (real_td["n_plays"] <= 9)).sum()
    real_td_plays_10p = (real_td["n_plays"] >= 10).sum()
    real_td_total = len(real_td)

    # ---- Sim drives ----
    print(f"Running sim with drive_log=True (N={N_SIMS})...")
    sim_agg, n_sim_games = run_sim_drives()
    sim_runtime = time.time() - t0
    print(f"  {n_sim_games} games in {sim_runtime:.0f}s ({sim_runtime/60:.1f} min)")

    # Save per-game parquet
    out_path = ROOT / "research" / "nfl_sim" / "phase5p_drives_by_game.parquet"
    sim_agg.to_parquet(out_path, index=False)
    print(f"  Saved {out_path} ({len(sim_agg)} rows)")

    # ---- Aggregate sim across all games ----
    endings = ["TD", "FG", "punt", "turnover", "downs", "end_half"]

    print(f"\n{'='*80}")
    print("MEAN START YARDLINE (yards to end zone) — sim vs real")
    print(f"{'='*80}")
    print(f"{'ending':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)
    for et in endings:
        r_sub = real[real["end_type"] == et]
        r_yl = r_sub["start_yl"].mean() if len(r_sub) > 0 else float("nan")

        s_sub = sim_agg[sim_agg["end_type"] == et]
        if len(s_sub) > 0:
            s_yl = s_sub["start_yl_sum"].sum() / s_sub["n"].sum()
        else:
            s_yl = float("nan")
        print(f"{et:12s} {r_yl:8.1f} {s_yl:8.1f} {s_yl - r_yl:+8.1f}")

    print(f"\n{'='*80}")
    print("YARDS PER PLAY — sim vs real")
    print(f"{'='*80}")
    print(f"{'ending':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)
    for et in endings:
        r_sub = real[real["end_type"] == et]
        r_ypp = r_sub["yards_gained_sum"].sum() / r_sub["n_plays"].sum() if r_sub["n_plays"].sum() > 0 else float("nan")

        s_sub = sim_agg[sim_agg["end_type"] == et]
        if s_sub["plays_sum"].sum() > 0:
            s_ypp = s_sub["yards_sum"].sum() / s_sub["plays_sum"].sum()
        else:
            s_ypp = float("nan")
        print(f"{et:12s} {r_ypp:8.2f} {s_ypp:8.2f} {s_ypp - r_ypp:+8.2f}")

    print(f"\n{'='*80}")
    print("TD DRIVE PLAY-COUNT DISTRIBUTION (share)")
    print(f"{'='*80}")
    sim_td = sim_agg[sim_agg["end_type"] == "TD"]
    sim_td_n = sim_td["n"].sum()
    sim_1_3 = sim_td["plays_1_3"].sum() / sim_td_n if sim_td_n > 0 else 0
    sim_4_6 = sim_td["plays_4_6"].sum() / sim_td_n if sim_td_n > 0 else 0
    sim_7_9 = sim_td["plays_7_9"].sum() / sim_td_n if sim_td_n > 0 else 0
    sim_10p = sim_td["plays_10p"].sum() / sim_td_n if sim_td_n > 0 else 0

    real_1_3 = real_td_plays_1_3 / real_td_total
    real_4_6 = real_td_plays_4_6 / real_td_total
    real_7_9 = real_td_plays_7_9 / real_td_total
    real_10p = real_td_plays_10p / real_td_total

    print(f"{'bucket':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)
    for label, rv, sv in [("1-3 plays", real_1_3, sim_1_3),
                           ("4-6 plays", real_4_6, sim_4_6),
                           ("7-9 plays", real_7_9, sim_7_9),
                           ("10+ plays", real_10p, sim_10p)]:
        print(f"{label:12s} {rv:8.3f} {sv:8.3f} {sv - rv:+8.3f}")

    print(f"\n{'='*80}")
    print("TD DRIVES STARTING INSIDE OPPONENT'S 40, PER GAME")
    print(f"{'='*80}")
    real_td_inside40 = (real_td["start_yl"] <= 40).sum() / n_real_games
    sim_td_inside40 = sim_td["inside_40_n"].sum() / n_sim_games if n_sim_games > 0 else 0
    print(f"  Real: {real_td_inside40:.2f}/game   Sim: {sim_td_inside40:.2f}/game   Diff: {sim_td_inside40 - real_td_inside40:+.2f}")

    # Real explosive plays on TD drives (20+ yards)
    real_td_explosive = real_td["explosive_20"].sum() / real_td_total
    print(f"\n{'='*80}")
    print("EXPLOSIVE PLAYS (20+ yds) PER TD DRIVE")
    print(f"{'='*80}")
    print(f"  Real: {real_td_explosive:.3f}/drive")
    print(f"  (Sim explosive play share not available from drive log — drive log has total yards only)")

    # NULL CHECK: punt drives plays per drive
    print(f"\n{'='*80}")
    print("NULL CHECK: punt drives plays per drive")
    print(f"{'='*80}")
    r_punt = real[real["end_type"] == "punt"]
    r_punt_ppd = r_punt["n_plays"].mean()
    s_punt = sim_agg[sim_agg["end_type"] == "punt"]
    s_punt_ppd = s_punt["plays_sum"].sum() / s_punt["n"].sum() if s_punt["n"].sum() > 0 else 0
    print(f"  Real: {r_punt_ppd:.2f}   Sim: {s_punt_ppd:.2f}   Diff: {s_punt_ppd - r_punt_ppd:+.2f}")
    print(f"  Null holds: {abs(s_punt_ppd - r_punt_ppd) <= 0.1}")

    # Seconds per drive
    print(f"\n{'='*80}")
    print("SECONDS PER DRIVE — sim vs real")
    print(f"{'='*80}")
    print(f"{'ending':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)
    for et in endings:
        r_sub = real[real["end_type"] == et]
        r_spd = r_sub["seconds"].mean() if len(r_sub) > 0 else float("nan")
        s_sub = sim_agg[sim_agg["end_type"] == et]
        if s_sub["n"].sum() > 0 and s_sub["seconds_sum"].sum() > 0:
            s_spd = s_sub["seconds_sum"].sum() / s_sub["n"].sum()
        else:
            s_spd = float("nan")
        print(f"{et:12s} {r_spd:8.1f} {s_spd:8.1f} {s_spd - r_spd:+8.1f}")

    # Drives per game
    print(f"\n{'='*80}")
    print("DRIVES PER GAME — sim vs real")
    print(f"{'='*80}")
    print(f"{'ending':12s} {'real':>8s} {'sim':>8s} {'diff':>8s}")
    print("-" * 40)
    for et in endings:
        r_dpg = len(real[real["end_type"] == et]) / n_real_games
        s_sub = sim_agg[sim_agg["end_type"] == et]
        s_dpg = s_sub["n"].sum() / n_sim_games
        print(f"{et:12s} {r_dpg:8.2f} {s_dpg:8.2f} {s_dpg - r_dpg:+8.2f}")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")
    print(f"Fingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
