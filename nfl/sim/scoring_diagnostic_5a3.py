#!/usr/bin/env python3
"""
Phase 5A-3: K1 before/after comparison.

Step 1: Corrected actual drives (includes qb_kneel, qb_spike).
Step 5: K1 after fixes, compared to pre-5a3 baseline.
"""

import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs"
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _CACHE
from nfl.sim.seed_util import stable_seed

SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 500

# Play types the engine counts as plays
SIM_PLAY_TYPES = ["pass", "run", "qb_kneel", "qb_spike"]


def build_corrected_drives():
    """Step 1: Actual drives including qb_kneel and qb_spike."""
    frames = []
    for s in SEASONS:
        frames.append(pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet"))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["week"] <= 18].copy()

    plays = df[df["play_type"].isin(SIM_PLAY_TYPES)].copy()

    drive_rows = []
    for (gid, drv), grp in plays.groupby(["game_id", "fixed_drive"]):
        all_in_drive = df[(df["game_id"] == gid) & (df["fixed_drive"] == drv)]
        first = all_in_drive.iloc[0]
        season = first["season"]
        start_yl = grp["yardline_100"].iloc[0] if "yardline_100" in grp.columns and grp["yardline_100"].notna().any() else 75
        start_qtr = int(grp["qtr"].iloc[0])

        n_plays = len(grp)
        total_yards = grp["yards_gained"].fillna(0).sum()

        drive_result_raw = first.get("fixed_drive_result", "")
        det = str(first.get("drive_end_transition", ""))

        if drive_result_raw == "Touchdown":
            result = "TD"
        elif drive_result_raw == "Opp touchdown":
            result = "turnover_int" if "INTERCEPTION" in det else "turnover_fumble"
        elif drive_result_raw == "Field goal":
            result = "FG_made"
        elif drive_result_raw == "Missed field goal":
            result = "FG_missed"
        elif drive_result_raw == "Punt":
            result = "punt"
        elif drive_result_raw == "Turnover":
            result = "turnover_int" if "INTERCEPTION" in det else "turnover_fumble"
        elif drive_result_raw == "Turnover on downs":
            result = "downs"
        elif drive_result_raw == "End of half":
            result = "end_half"
        elif drive_result_raw == "Safety":
            result = "safety"
        else:
            result = "end_game"

        if result == "TD":
            pts = 6
            pat = all_in_drive[all_in_drive["play_type"] == "extra_point"]
            twopt = all_in_drive[all_in_drive["two_point_attempt"] == 1]
            if len(pat) and (pat["extra_point_result"] == "good").any():
                pts += 1
            elif len(twopt) and (twopt["two_point_conv_result"] == "success").any():
                pts += 2
        elif result == "FG_made":
            pts = 3
        elif result == "safety":
            pts = -2
        else:
            pts = 0

        min_yl = grp["yardline_100"].min() if grp["yardline_100"].notna().any() else 75
        drive_rows.append({
            "game_id": gid, "season": season, "drive_no": drv,
            "start_yardline": start_yl, "start_quarter": start_qtr,
            "plays": n_plays, "yards": total_yards,
            "result": result, "points": pts,
            "reached_rz": min_yl <= 20, "reached_gl": min_yl <= 5,
        })

    return pd.DataFrame(drive_rows), df


def run_k1():
    """Run K1 backtest with drive log."""
    _CACHE.clear()
    _load_tables()
    tr, tend, sit, kicker, league = _load_ratings()

    all_results = []
    all_drives = []

    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        gdf = pd.read_parquet(p, columns=[
            "game_id", "season", "week", "home_team", "away_team",
            "home_score", "away_score"
        ])
        games = gdf.drop_duplicates("game_id").query("week <= 18")
        t0 = time.time()

        for _, g in games.iterrows():
            seed = stable_seed((g["game_id"], 42))
            r = simulate_game(
                g["home_team"], g["away_team"], s, int(g["week"]),
                n_sims=N_SIMS, seed=seed,
                team_r=tr, tend=tend, sit=sit, kicker=kicker, league=league,
                drive_log=True
            )
            dl = r.attrs.get("drive_log")
            if dl is not None and len(dl):
                dl = dl.copy()
                dl["game_id"] = g["game_id"]
                dl["season"] = s
                all_drives.append(dl)

            r["game_id"] = g["game_id"]
            r["actual_home"] = g["home_score"]
            r["actual_away"] = g["away_score"]
            r["season"] = s
            all_results.append(r)

        elapsed = time.time() - t0
        print(f"  Season {s}: {len(games)} games, {elapsed:.1f}s ({elapsed/len(games):.2f}s/game)")

    sim_df = pd.concat(all_results, ignore_index=True)
    drive_df = pd.concat(all_drives, ignore_index=True) if all_drives else pd.DataFrame()
    return sim_df, drive_df


def report(sim_df, sim_drives, act_drives, act_df, label=""):
    """Print key metrics."""
    n_games = act_df["game_id"].nunique()
    act_games = act_df.drop_duplicates("game_id")

    act_pts = (act_games["home_score"].mean() + act_games["away_score"].mean()) / 2
    sim_pts = (sim_df["home_score"].mean() + sim_df["away_score"].mean()) / 2

    # Drive result distribution
    act_rc = act_drives["result"].value_counts(normalize=True)
    sim_rc = sim_drives["result"].value_counts(normalize=True)

    all_results_list = sorted(set(act_rc.index) | set(sim_rc.index))

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    # K1 table
    margin_sd = (sim_df["home_score"] - sim_df["away_score"]).std()
    act_margin = (act_games["home_score"] - act_games["away_score"]).abs()
    sim_margin = (sim_df["home_score"] - sim_df["away_score"]).abs()

    total_4th = sim_df["ev_4th_go"].sum() + sim_df["ev_punts"].sum() + sim_df["ev_fg_att"].sum()
    go_rate = sim_df["ev_4th_go"].sum() / max(total_4th, 1)

    print(f"pts/team: sim={sim_pts:.1f} actual={act_pts:.1f}")
    print(f"plays/game: {sim_df['plays'].mean():.1f}")
    print(f"drives/game: {sim_df['drives'].mean():.1f}")
    print(f"SD margin (pooled): {margin_sd:.2f}")
    print(f"pass yds/team: {(sim_df['home_pass_yds'].mean()+sim_df['away_pass_yds'].mean())/2:.1f}")
    print(f"rush yds/team: {(sim_df['home_rush_yds'].mean()+sim_df['away_rush_yds'].mean())/2:.1f}")
    print(f"FG att/game: {sim_df['ev_fg_att'].mean():.2f}")
    print(f"FG make rate: {sim_df['ev_fg_made'].sum()/max(sim_df['ev_fg_att'].sum(),1):.3f}")
    print(f"4th-down go rate: {go_rate:.3f}")
    if "ev_explosive_pass" in sim_df.columns:
        print(f"Explosive pass (20+)/game: {sim_df['ev_explosive_pass'].mean():.2f}")
        print(f"Explosive rush (10+)/game: {sim_df['ev_explosive_rush'].mean():.2f}")

    # Margin distribution
    print(f"\nP(|margin|=k):")
    for k in [3, 6, 7, 10, 14]:
        a = (act_margin == k).mean()
        s = (sim_margin == k).mean()
        print(f"  k={k}: actual={a:.4f} sim={s:.4f} delta={s-a:+.4f}")

    # Drive result table
    print(f"\nDrive result distribution:")
    for r in all_results_list:
        a = act_rc.get(r, 0)
        s = sim_rc.get(r, 0)
        print(f"  {r:20s}: actual={a:.4f} sim={s:.4f} delta={s-a:+.4f}")

    # By season
    print(f"\nBy season:")
    for yr in SEASONS:
        ag = act_games[act_games["season"] == yr]
        sd = sim_df[sim_df["season"] == yr]
        sdr = sim_drives[sim_drives["season"] == yr]
        ad = act_drives[act_drives["season"] == yr]
        a_pts = (ag["home_score"].mean() + ag["away_score"].mean()) / 2
        s_pts = (sd["home_score"].mean() + sd["away_score"].mean()) / 2
        a_td = (ad["result"] == "TD").mean()
        s_td = (sdr["result"] == "TD").mean() if len(sdr) else 0
        a_fg = (ad["result"] == "FG_made").mean()
        s_fg = (sdr["result"] == "FG_made").mean() if len(sdr) else 0
        print(f"  {yr}: pts act={a_pts:.1f} sim={s_pts:.1f} | "
              f"TD/drv act={a_td:.3f} sim={s_td:.3f} | "
              f"FG/drv act={a_fg:.3f} sim={s_fg:.3f}")


if __name__ == "__main__":
    t_start = time.time()

    print("STEP 1: Corrected actual drives (includes qb_kneel, qb_spike)...")
    t0 = time.time()
    act_drives, act_df = build_corrected_drives()
    print(f"  {len(act_drives)} drives (was 22,870 in 5A-2), "
          f"{act_df['game_id'].nunique()} games ({time.time()-t0:.1f}s)")
    act_drives.to_parquet(OUT_DIR / "actual_drives_2021_2024_v2.parquet", index=False)

    # Re-state 5A-2 §4a with corrected denominator
    print("\nCorrected drive-result distribution (vs 5A-2):")
    rc = act_drives["result"].value_counts(normalize=True)
    for r in sorted(rc.index):
        print(f"  {r:20s}: {rc[r]:.4f}")
    print(f"  end_half+end_game total: {rc.get('end_half',0)+rc.get('end_game',0):.4f}")
    print(f"  Total drives: {len(act_drives)}")

    print(f"\nSTEP 5: K1 after 5A-3 fixes (N={N_SIMS}, 1087 games)...")
    t0 = time.time()
    sim_df, sim_drives = run_k1()
    k1_runtime = time.time() - t0
    print(f"  K1 runtime: {k1_runtime:.1f}s ({k1_runtime/1087:.2f}s/game)")

    report(sim_df, sim_drives, act_drives, act_df, "K1 AFTER 5A-3")

    total_runtime = time.time() - t_start
    print(f"\nTotal runtime: {total_runtime:.1f}s ({total_runtime/60:.1f}m)")
