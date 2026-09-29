#!/usr/bin/env python3
"""Full K1 table generator — one committed entry point.

Usage: python3 nfl/sim/run_k1_table.py --out research/nfl_sim/<name>.txt

1,087 games x N=500, seasons 2021-24, week <= 18, seeds via stable_seed
exactly as run_k1_5a5.py. Prints every K1 line with sim, actual, diff,
tolerance and PASS/FAIL. Writes per-game means to <name>_rows.parquet.
"""

import argparse
import subprocess
import time
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _CACHE
from nfl.sim.seed_util import stable_seed
from nfl.sim.calibration import engine_fingerprint

PBP_DIR = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 500

# --- Tolerances (imported from tests, not invented) ---
# test_engine_5a3.py: go rate < 0.010, FG att < 0.15
# test_engine_5a4.py: penalties per side < 0.5, FD by penalty < 0.3
# test_engine_5a5.py: nonoff pts < 0.3
# test_engine_5a9.py: tied expiry <= 0.0 + 0.05
# test_engine_5i.py: like-for-like go rate < 0.010, 3rd-and-11+ < 0.03
TOLERANCES = {
    "go_rate": 0.010,          # test_engine_5a3.py:67 (D148: 4th-down-only denom)
    "fg_att_pg": 0.15,         # test_engine_5a3.py:77
    "off_pen_pg": 0.5,         # test_engine_5a4.py:75
    "def_pen_pg": 0.5,         # test_engine_5a4.py:77
    "fd_pen_pt": 0.3,          # test_engine_5a4.py:89
    "nonoff_pts_pt": 0.3,      # test_engine_5a5.py:84 (per team)
    "tied_expiry_broad": 0.05, # test_engine_5a9.py:143 (above 0.0)
    "3rd_11_share": 0.03,      # test_engine_5i.py:103
}


def load_actuals():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        df = pd.read_parquet(p, columns=["game_id", "season", "week", "home_team",
                                          "away_team", "home_score", "away_score"])
        frames.append(df.drop_duplicates("game_id").query("week <= 18"))
    return pd.concat(frames, ignore_index=True)


def compute_actuals_from_pbp():
    """Compute actual K1 targets from PBP."""
    frames = []
    for s in SEASONS:
        frames.append(pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet"))
    pbp = pd.concat(frames, ignore_index=True)
    pbp = pbp[pbp["week"] <= 18]
    n_games = pbp.drop_duplicates("game_id").shape[0]

    # Pts/team
    actuals = load_actuals()
    act_pts = (actuals["home_score"].mean() + actuals["away_score"].mean()) / 2

    # Go rate (down == 4, real)
    d4 = pbp[(pbp["down"] == 4) & pbp["play_type"].isin(["pass", "run", "punt", "field_goal"])]
    act_go = d4["play_type"].isin(["pass", "run"]).mean()

    # Penalties
    no_play = pbp[pbp["play_type"] == "no_play"]
    acc = no_play[no_play["penalty"] == 1]
    off_pen = acc[acc["penalty_team"] == acc["posteam"]]
    def_pen = acc[acc["penalty_team"] != acc["posteam"]]
    act_off_pen = len(off_pen) / n_games
    act_def_pen = len(def_pen) / n_games

    # FD by penalty
    fd_pen = pbp[(pbp["first_down_penalty"] == 1)]
    act_fd_pen_pt = len(fd_pen) / n_games / 2  # per team

    # 3rd-down share at 11+
    third = pbp[(pbp["down"] == 3) & pbp["play_type"].isin(["pass", "run"])]
    act_3rd_11 = (third["ydstogo"] >= 11).mean()

    # FG attempts per game
    fgs = pbp[pbp["play_type"] == "field_goal"]
    act_fg_pg = len(fgs) / n_games

    # Punts per game
    punts = pbp[pbp["play_type"] == "punt"]
    act_punts_pg = len(punts) / n_games

    return {
        "pts_team": act_pts,
        "go_rate": act_go,
        "off_pen_pg": act_off_pen,
        "def_pen_pg": act_def_pen,
        "fd_pen_pt": act_fd_pen_pt,
        "3rd_11_share": act_3rd_11,
        "fg_att_pg": act_fg_pg,
        "punts_pg": act_punts_pg,
        "n_games": n_games,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    out_path = Path(args.out)
    rows_path = out_path.parent / (out_path.stem + "_rows.parquet")

    # Header
    fp = engine_fingerprint()
    try:
        git_desc = subprocess.check_output(
            ["git", "describe", "--always", "--dirty"], text=True, cwd=str(ROOT)
        ).strip()
    except Exception:
        git_desc = "unknown"
    utc_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    lines = []
    lines.append(f"K1 Table: {fp} | {git_desc} | {utc_now}")
    lines.append(f"N={N_SIMS}, games={len(SEASONS)}*~272, seasons={SEASONS}")
    lines.append("")

    # Load and run
    _CACHE.clear()
    _load_tables()
    tr, tend, sit, kicker, league = _load_ratings()

    actuals_df = load_actuals()
    print(f"K1: {len(actuals_df)} games, N={N_SIMS}", flush=True)

    # 6E (D205): build per-game rows incrementally to avoid OOM.
    # The old code held all 1,087 game DataFrames (~543K rows) in memory,
    # then concatenated. Now we extract per-game means immediately and
    # accumulate only the sums needed for the K1 table.
    COLS = ["home_score", "away_score", "ev_4th_go", "ev_punts", "ev_fg_att",
            "ev_fg_non4th", "ev_pen_offense", "ev_pen_defense", "ev_fd_penalty",
            "ev_3rd_att", "ev_3rd_long", "ev_int_ret_td", "ev_fum_ret_td",
            "ev_punt_ret_td", "ev_ko_ret_td", "ev_safeties"]
    game_rows = []
    col_sums = {c: 0.0 for c in COLS}
    col_sums["plays"] = 0.0
    col_sums["drives"] = 0.0
    margin_vals = []  # for SD
    total_sims = 0

    t_total = time.time()
    game_idx = 0
    for s in SEASONS:
        s_games = actuals_df[actuals_df["season"] == s]
        t0 = time.time()
        for _, game in s_games.iterrows():
            seed = stable_seed((game["game_id"], 42))
            sim = simulate_game(game["home_team"], game["away_team"], s, int(game["week"]),
                                n_sims=N_SIMS, seed=seed, team_r=tr, tend=tend, sit=sit,
                                kicker=kicker, league=league, drive_log=True)
            n = len(sim)
            # Accumulate sums for K1 metrics
            for c in COLS:
                col_sums[c] += float(sim[c].sum())
            col_sums["plays"] += float(sim["plays"].sum()) if "plays" in sim else 0.0
            col_sums["drives"] += float(sim["drives"].sum()) if "drives" in sim else 0.0
            margin_vals.extend((sim["home_score"] - sim["away_score"]).tolist())
            total_sims += n
            # Build per-game row immediately and drop the frame
            game_rows.append({
                "game_id": game["game_id"],
                "season": int(s), "week": int(game["week"]),
                "sim_home": sim["home_score"].mean(),
                "sim_away": sim["away_score"].mean(),
                "actual_home": game["home_score"],
                "actual_away": game["away_score"],
                "ev_4th_go": sim["ev_4th_go"].mean(),
                "ev_punts": sim["ev_punts"].mean(),
                "ev_fg_att": sim["ev_fg_att"].mean(),
                "ev_fg_non4th": sim["ev_fg_non4th"].mean(),
                "ev_pen_offense": sim["ev_pen_offense"].mean(),
                "ev_pen_defense": sim["ev_pen_defense"].mean(),
                "ev_fd_penalty": sim["ev_fd_penalty"].mean(),
                "ev_3rd_att": sim["ev_3rd_att"].mean(),
                "ev_3rd_long": sim["ev_3rd_long"].mean(),
                "plays": sim["plays"].mean() if "plays" in sim else 0.0,
                "drives": sim["drives"].mean() if "drives" in sim else 0.0,
            })
            del sim
            game_idx += 1
            if game_idx == 100:
                t100 = time.time() - t_total
                print(f"  First 100 games: {t100:.1f}s ({t100/100:.2f}s/game)", flush=True)
        elapsed = time.time() - t0
        print(f"  Season {s}: {len(s_games)} games, {elapsed:.1f}s ({elapsed/len(s_games):.2f}s/game)", flush=True)

    total_time = time.time() - t_total
    print(f"Total: {total_time:.1f}s ({total_time/60:.1f}min)", flush=True)

    # Save per-game rows immediately
    pd.DataFrame(game_rows).to_parquet(rows_path, index=False)
    print(f"Rows written to {rows_path} ({len(game_rows)} games)", flush=True)

    # Compute actuals from PBP
    act = compute_actuals_from_pbp()

    # Sim metrics from accumulated sums
    n_games = len(actuals_df)
    sim_pts = (col_sums["home_score"] + col_sums["away_score"]) / total_sims / 2
    sim_plays = col_sums["plays"] / total_sims
    sim_drives = col_sums["drives"] / total_sims
    sim_go = col_sums["ev_4th_go"] / (col_sums["ev_4th_go"] + col_sums["ev_punts"] +
                col_sums["ev_fg_att"] - col_sums["ev_fg_non4th"])
    sim_off_pen = col_sums["ev_pen_offense"] / total_sims
    sim_def_pen = col_sums["ev_pen_defense"] / total_sims
    sim_fd_pen = col_sums["ev_fd_penalty"] / total_sims / 2
    sim_punts = col_sums["ev_punts"] / total_sims
    sim_fg = col_sums["ev_fg_att"] / total_sims
    sim_3rd_11 = col_sums["ev_3rd_long"] / col_sums["ev_3rd_att"]

    # Non-offensive scoring
    xp = 0.948
    nonoff_tds = (col_sums["ev_int_ret_td"] + col_sums["ev_fum_ret_td"] +
                  col_sums["ev_punt_ret_td"] + col_sums["ev_ko_ret_td"]) / total_sims
    nonoff_pts = nonoff_tds * (6 + xp) + col_sums["ev_safeties"] / total_sims * 2
    sim_nonoff_pt = nonoff_pts / 2

    # Margin SD
    sim_margin_sd = float(np.std(margin_vals, ddof=1))
    act_margin_sd = (actuals_df["home_score"] - actuals_df["away_score"]).std()

    # Tied-drive expiry (broad)
    from nfl.sim.run_metric_noise_5h import SAMPLE_GAMES, compute_tied_expiry
    ratings_dict = {"team_r": tr, "tend": tend, "sit": sit, "kicker": kicker, "league": league}
    tied = compute_tied_expiry(salt=0, ratings=ratings_dict)
    sim_tied_broad = tied["tied_expiry"]

    # Build table
    def row(name, sim_val, act_val, tol_key=None):
        diff = sim_val - act_val
        if tol_key and tol_key in TOLERANCES:
            tol = TOLERANCES[tol_key]
            pf = "PASS" if abs(diff) < tol else "FAIL"
            return f"  {name:25s}  sim={sim_val:8.4f}  actual={act_val:8.4f}  diff={diff:+8.4f}  tol={tol:.4f}  {pf}"
        else:
            return f"  {name:25s}  sim={sim_val:8.4f}  actual={act_val:8.4f}  diff={diff:+8.4f}  tolerance: none defined"

    def row_above(name, sim_val, act_val, tol_key):
        """For tied expiry: sim must be <= actual + tolerance."""
        diff = sim_val - act_val
        tol = TOLERANCES.get(tol_key, 0.05)
        pf = "PASS" if sim_val <= act_val + tol else "FAIL"
        return f"  {name:25s}  sim={sim_val:8.4f}  actual={act_val:8.4f}  diff={diff:+8.4f}  tol={tol:.4f}  {pf}"

    lines.append("--- K1 Table ---")
    lines.append(row("pts/team", sim_pts, act["pts_team"]))
    from nfl.sim.actuals_k1 import compute_k1_actuals
    k1_act = compute_k1_actuals()
    lines.append(f"  {'plays/game':25s}  sim={sim_plays:8.1f}  actual={k1_act['plays_pg']:.1f}     tolerance: none defined")
    lines.append(f"  {'drives/game':25s}  sim={sim_drives:8.1f}  actual={k1_act['drives_pg']:.1f}      tolerance: none defined")
    lines.append(row("go_rate", sim_go, act["go_rate"], "go_rate"))
    lines.append(row("off_pen/game", sim_off_pen, act["off_pen_pg"], "off_pen_pg"))
    lines.append(row("def_pen/game", sim_def_pen, act["def_pen_pg"], "def_pen_pg"))
    lines.append(row("fd_pen/team", sim_fd_pen, act["fd_pen_pt"], "fd_pen_pt"))
    lines.append(row("punts/game", sim_punts, act["punts_pg"]))
    lines.append(row("fg_att/game", sim_fg, act["fg_att_pg"], "fg_att_pg"))
    lines.append(row("3rd_11+_share", sim_3rd_11, act["3rd_11_share"], "3rd_11_share"))
    lines.append(f"  {'nonoff_pts/team':25s}  sim={sim_nonoff_pt:8.4f}  tolerance: none defined")
    lines.append(f"  {'margin_sd':25s}  sim={sim_margin_sd:8.2f}  actual={act_margin_sd:8.2f}  tolerance: none defined")
    lines.append(row_above("tied_expiry_broad", sim_tied_broad, 0.0, "tied_expiry_broad"))

    # Non-offensive breakdown
    lines.append("")
    lines.append("--- Non-Offensive Scoring ---")
    for c in ["ev_int_ret_td", "ev_fum_ret_td", "ev_punt_ret_td", "ev_ko_ret_td", "ev_safeties"]:
        lines.append(f"  {c}/game: {col_sums[c]/total_sims:.4f}")
    lines.append(f"  Non-off pts/game: {nonoff_pts:.2f} ({nonoff_pts/2:.2f}/team)")

    # Write
    text = "\n".join(lines)
    with open(out_path, "w") as f:
        f.write(text + "\n")
    print(f"\nTable written to {out_path}")
    print(text)


if __name__ == "__main__":
    main()
