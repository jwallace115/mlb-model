#!/usr/bin/env python3
"""
5Q Item 1: Drive starts by the event that preceded them.

Classifies each drive start by what ended the PREVIOUS drive (kickoff, punt,
INT, fumble, downs, missed FG, safety). Reports start yardline, inside-40/20
shares, and INT/fumble return yard distributions, sim vs real.

K1 sample, N=100, drive_log=True, aggregated per game.
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

# Map sim drive result to preceding-event category for the NEXT drive
SIM_PREV_MAP = {
    "TD": "kickoff_score",       # next drive starts with kickoff
    "FG_made": "kickoff_score",  # next drive starts with kickoff
    "punt": "punt",
    "turnover_int": "interception",
    "turnover_fumble": "fumble",
    "downs": "downs",
    "FG_missed": "missed_fg",
    "end_half": "half_open",     # next drive is a half-opening kickoff
    "end_game": "game_end",      # no next drive
    "safety": "safety",
}


def run_sim_drives():
    """Run K1 sample with drive_log=True, classify each drive's start by
    the previous drive's result. Aggregate per game."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    game_rows = []
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
            dl_df = dl_df.sort_values(["sim_id", "drive_no"]).reset_index(drop=True)

            # For each drive, look at previous drive's result to classify start
            dl_df["prev_result"] = dl_df.groupby("sim_id")["result"].shift(1)
            # First drive of each sim has no predecessor -> "half_open" (opening kickoff)
            dl_df["prev_result"] = dl_df["prev_result"].fillna("_opening")

            # Map to preceding-event category
            def classify_start(prev_res):
                if prev_res == "_opening":
                    return "half_open"
                return SIM_PREV_MAP.get(prev_res, "other")

            dl_df["start_type"] = dl_df["prev_result"].apply(classify_start)

            # Aggregate per start_type within this game
            for st, grp in dl_df.groupby("start_type"):
                inside_40 = (grp["start_yardline"] <= 40).sum()
                inside_20 = (grp["start_yardline"] <= 20).sum()
                game_rows.append({
                    "game_id": g["game_id"],
                    "season": s,
                    "start_type": st,
                    "n": len(grp) / N_SIMS,
                    "start_yl_sum": grp["start_yardline"].sum() / N_SIMS,
                    "inside_40_n": inside_40 / N_SIMS,
                    "inside_20_n": inside_20 / N_SIMS,
                })

            game_count += 1
            if game_count % 200 == 0:
                print(f"  {game_count} games...")
            del dl_df, dl
            gc.collect()

    return pd.DataFrame(game_rows), game_count


def load_real_drive_starts():
    """Classify real PBP drive starts by the preceding drive's result.

    Derivation: PBP 2021-24 REG. Group by (game_id, fixed_drive). For each
    drive, the preceding drive's fixed_drive_result determines how this drive
    started. Start yardline = yardline_100 of the drive's first scrimmage play.
    """
    frames = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]

        # Get drive-level info
        scrim = df[df["play_type"].isin(["pass", "run"])]
        drive_start = scrim.groupby(["game_id", "fixed_drive"]).agg(
            start_yl=("yardline_100", "first"),
        ).reset_index()

        drive_result = df.dropna(subset=["fixed_drive"]).groupby(
            ["game_id", "fixed_drive"]
        ).agg(
            drive_result=("fixed_drive_result", "first"),
        ).reset_index()

        drives = drive_start.merge(drive_result, on=["game_id", "fixed_drive"], how="inner")
        drives = drives.sort_values(["game_id", "fixed_drive"]).reset_index(drop=True)
        drives["prev_result"] = drives.groupby("game_id")["drive_result"].shift(1)
        drives["prev_result"] = drives["prev_result"].fillna("_opening")

        # Classify
        real_map = {
            "_opening": "half_open",
            "Touchdown": "kickoff_score",
            "Field goal": "kickoff_score",
            "Punt": "punt",
            "Turnover": "turnover",     # PBP lumps INT+fumble
            "Turnover on downs": "downs",
            "Missed field goal": "missed_fg",
            "End of half": "half_open",
            "Safety": "safety",
            "Opp touchdown": "kickoff_score",  # defensive/ST TD -> kickoff
        }
        drives["start_type"] = drives["prev_result"].map(real_map).fillna("other")
        drives["season"] = s
        frames.append(drives)

    return pd.concat(frames, ignore_index=True)


def load_real_return_yards():
    """INT and fumble return yards from PBP 2021-24 REG.

    Derivation: interception plays (interception == 1), return_yards column.
    Fumble recoveries (fumble_lost == 1), return_yards column.
    """
    int_yards = []
    fum_yards = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[df["season_type"] == "REG"]
        ints = df[df["interception"] == 1]["return_yards"].dropna()
        fums = df[df["fumble_lost"] == 1]["return_yards"].dropna()
        int_yards.extend(ints.tolist())
        fum_yards.extend(fums.tolist())
    return np.array(int_yards), np.array(fum_yards)


def main():
    t0 = time.time()
    fp = engine_fingerprint()
    print(f"engine_fingerprint: {fp}")
    assert fp == "02fbcab6e6ed042e", f"WRONG fingerprint: {fp}"

    # ---- Real drives ----
    print("Loading real drive starts from PBP 2021-24 REG...")
    real = load_real_drive_starts()
    n_real_games = real["game_id"].nunique()
    print(f"  {n_real_games} real games, {len(real)} drives")

    # ---- Sim drives ----
    print(f"Running sim with drive_log=True (N={N_SIMS})...")
    sim_agg, n_sim_games = run_sim_drives()
    sim_runtime = time.time() - t0
    print(f"  {n_sim_games} games in {sim_runtime:.0f}s ({sim_runtime/60:.1f} min)")

    # Save per-game parquet
    out_path = ROOT / "research" / "nfl_sim" / "phase5q_drive_starts_by_game.parquet"
    sim_agg.to_parquet(out_path, index=False)
    print(f"  Saved {out_path}")

    # ---- Real return yards ----
    print("Loading real return yards...")
    real_int_yds, real_fum_yds = load_real_return_yards()
    print(f"  INT returns: {len(real_int_yds)}, fumble returns: {len(real_fum_yds)}")

    # ---- Sim return quantiles (from turnover_returns.json) ----
    import json
    with open(ROOT / "nfl" / "data" / "sim" / "tables" / "turnover_returns.json") as f:
        to_ret = json.load(f)
    sim_int_q = np.array(to_ret["int_return_yds_q"])
    sim_fum_q = np.array(to_ret["fum_return_yds_q"])

    # ---- Report ----
    start_types = ["kickoff_score", "half_open", "punt", "interception", "fumble",
                   "downs", "missed_fg", "safety"]
    # Note: real PBP lumps INT+fumble as "turnover"; sim separates them
    real_types = ["kickoff_score", "half_open", "punt", "turnover",
                  "downs", "missed_fg", "safety"]

    print(f"\n{'='*90}")
    print("DRIVE STARTS BY PRECEDING EVENT — sim vs real")
    print(f"{'='*90}")
    print(f"{'event':18s} {'dpg_sim':>8s} {'dpg_real':>8s} {'start_yl_sim':>12s} "
          f"{'start_yl_real':>12s} {'in40_sim':>8s} {'in40_real':>8s} {'in20_sim':>8s} {'in20_real':>8s}")
    print("-" * 100)

    for st in ["kickoff_score", "half_open", "punt", "interception", "fumble",
               "downs", "missed_fg", "safety"]:
        s_sub = sim_agg[sim_agg["start_type"] == st]
        s_dpg = s_sub["n"].sum() / n_sim_games if n_sim_games > 0 else 0
        s_yl = s_sub["start_yl_sum"].sum() / s_sub["n"].sum() if s_sub["n"].sum() > 0 else 0
        s_in40 = s_sub["inside_40_n"].sum() / s_sub["n"].sum() if s_sub["n"].sum() > 0 else 0
        s_in20 = s_sub["inside_20_n"].sum() / s_sub["n"].sum() if s_sub["n"].sum() > 0 else 0

        # Real: map sim types to real types
        if st in ("interception", "fumble"):
            r_st = "turnover"
        else:
            r_st = st
        r_sub = real[real["start_type"] == r_st]
        r_dpg = len(r_sub) / n_real_games if n_real_games > 0 else 0
        r_yl = r_sub["start_yl"].mean() if len(r_sub) > 0 else 0
        r_in40 = (r_sub["start_yl"] <= 40).mean() if len(r_sub) > 0 else 0
        r_in20 = (r_sub["start_yl"] <= 20).mean() if len(r_sub) > 0 else 0

        # For combined turnover row, only print real once
        if st == "fumble":
            r_str = "(see turnover above)"
            print(f"{st:18s} {s_dpg:8.2f} {'':>8s} {s_yl:12.1f} {'':>12s} "
                  f"{s_in40:8.3f} {'':>8s} {s_in20:8.3f} {'':>8s}")
        elif st == "interception":
            print(f"{'turnover (real)':18s} {'':>8s} {r_dpg:8.2f} {'':>12s} {r_yl:12.1f} "
                  f"{'':>8s} {r_in40:8.3f} {'':>8s} {r_in20:8.3f}")
            print(f"{st + ' (sim)':18s} {s_dpg:8.2f} {'':>8s} {s_yl:12.1f} {'':>12s} "
                  f"{s_in40:8.3f} {'':>8s} {s_in20:8.3f} {'':>8s}")
        else:
            print(f"{st:18s} {s_dpg:8.2f} {r_dpg:8.2f} {s_yl:12.1f} {r_yl:12.1f} "
                  f"{s_in40:8.3f} {r_in40:8.3f} {s_in20:8.3f} {r_in20:8.3f}")

    # Combined turnover row for sim
    s_to = sim_agg[sim_agg["start_type"].isin(["interception", "fumble"])]
    s_to_dpg = s_to["n"].sum() / n_sim_games
    s_to_yl = s_to["start_yl_sum"].sum() / s_to["n"].sum() if s_to["n"].sum() > 0 else 0
    s_to_in40 = s_to["inside_40_n"].sum() / s_to["n"].sum() if s_to["n"].sum() > 0 else 0
    r_to = real[real["start_type"] == "turnover"]
    r_to_dpg = len(r_to) / n_real_games
    r_to_yl = r_to["start_yl"].mean()
    r_to_in40 = (r_to["start_yl"] <= 40).mean()
    print(f"\n{'turnover combined':18s} sim {s_to_dpg:.2f}/g  real {r_to_dpg:.2f}/g  "
          f"sim yl {s_to_yl:.1f}  real yl {r_to_yl:.1f}  "
          f"sim in40 {s_to_in40:.3f}  real in40 {r_to_in40:.3f}")

    # Inside-40 per game by start type
    print(f"\n{'='*90}")
    print("INSIDE-40 STARTS PER GAME by start type")
    print(f"{'='*90}")
    total_sim_in40 = 0
    total_real_in40 = 0
    for st in ["kickoff_score", "half_open", "punt", "interception", "fumble",
               "downs", "missed_fg", "safety"]:
        s_sub = sim_agg[sim_agg["start_type"] == st]
        s_in40_pg = s_sub["inside_40_n"].sum() / n_sim_games
        total_sim_in40 += s_in40_pg

        if st in ("interception", "fumble"):
            r_st = "turnover"
        else:
            r_st = st
        r_sub = real[real["start_type"] == r_st]
        r_in40_pg = (r_sub["start_yl"] <= 40).sum() / n_real_games
        if st == "interception":
            # Only count real turnover once
            total_real_in40 += r_in40_pg

        if st != "fumble":
            print(f"  {st:18s}  sim {s_in40_pg:.3f}  real {r_in40_pg:.3f}  diff {s_in40_pg - r_in40_pg:+.3f}")
        else:
            print(f"  {st:18s}  sim {s_in40_pg:.3f}")
            total_real_in40 += 0  # already counted in interception

    print(f"  {'TOTAL':18s}  sim {total_sim_in40:.3f}")

    # ---- Return yard quantiles ----
    print(f"\n{'='*90}")
    print("INT RETURN YARDS — sim quantiles vs real PBP")
    print(f"{'='*90}")
    pcts = [10, 25, 50, 75, 90, 95]
    print(f"{'pct':>5s} {'sim':>8s} {'real':>8s} {'diff':>8s}")
    for p in pcts:
        sim_v = np.percentile(sim_int_q, p)  # sim table quantile
        real_v = np.percentile(real_int_yds, p)
        print(f"{p:5d} {sim_v:8.1f} {real_v:8.1f} {sim_v - real_v:+8.1f}")

    print(f"\n{'='*90}")
    print("FUMBLE RETURN YARDS — sim quantiles vs real PBP")
    print(f"{'='*90}")
    print(f"{'pct':>5s} {'sim':>8s} {'real':>8s} {'diff':>8s}")
    for p in pcts:
        sim_v = np.percentile(sim_fum_q, p)
        real_v = np.percentile(real_fum_yds, p)
        print(f"{p:5d} {sim_v:8.1f} {real_v:8.1f} {sim_v - real_v:+8.1f}")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")
    print(f"Fingerprint at end: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
