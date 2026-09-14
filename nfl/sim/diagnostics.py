#!/usr/bin/env python3
"""Diagnostic instrumentation for the NFL sim engine."""

import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
sys.path.insert(0, str(ROOT))


def load_actuals():
    frames = []
    for yr in [2021, 2022, 2023, 2024]:
        frames.append(pd.read_parquet(PBP_DIR / f"pbp_{yr}.parquet"))
    return pd.concat(frames, ignore_index=True).query("week <= 18")


def print_diagnostics(label, act_df, sim_df):
    passes = act_df[act_df["play_type"] == "pass"]
    rushes = act_df[act_df["play_type"] == "run"]
    scrim = act_df[act_df["play_type"].isin(["pass", "run"]) & act_df["down"].notna()]
    n_games_act = act_df["game_id"].nunique()

    s_pass = sim_df["ev_pass_plays"].sum()
    s_rush = sim_df["ev_rush_plays"].sum()
    s_total = s_pass + s_rush
    n_sim_games = sim_df["game_id"].nunique() if "game_id" in sim_df else len(sim_df)
    n_sims_total = len(sim_df)

    print(f"\n{'='*65}\n  {label}\n{'='*65}")

    # 1. Dropback outcome mix
    print(f"\n1. DROPBACK OUTCOME MIX")
    print(f"  {'':22s} {'Actual':>8s} {'Sim':>8s} {'Delta':>8s}")
    a_sack = passes["sack"].sum() / len(passes)
    a_int = passes[passes["sack"] != 1]["interception"].sum() / len(passes)
    a_inc = ((passes["sack"] != 1) & (passes["interception"] != 1) &
             (passes["complete_pass"] != 1)).sum() / len(passes)
    a_comp = ((passes["sack"] != 1) & (passes["interception"] != 1) &
              (passes["complete_pass"] == 1)).sum() / len(passes)
    s_sk = sim_df["ev_sacks"].sum() / max(s_pass, 1)
    s_int = sim_df["ev_ints"].sum() / max(s_pass, 1)
    s_inc = sim_df["ev_incomp"].sum() / max(s_pass, 1)
    s_comp = sim_df["ev_comp"].sum() / max(s_pass, 1)
    for nm, a, s in [("P(sack)", a_sack, s_sk), ("P(INT)", a_int, s_int),
                      ("P(incomplete)", a_inc, s_inc), ("P(complete)", a_comp, s_comp)]:
        print(f"  {nm:22s} {a:8.3f} {s:8.3f} {s-a:+8.3f}")

    # 2. Turnovers per play
    print(f"\n2. TURNOVERS PER PLAY")
    a_int_db = passes["interception"].sum() / len(passes)
    a_fum_pp = scrim["fumble_lost"].sum() / len(scrim)
    s_int_db = sim_df["ev_ints"].sum() / max(s_pass, 1)
    s_fum_pp = sim_df["turnovers"].sum() / max(s_total, 1) - s_int_db * s_pass / max(s_total, 1)
    print(f"  {'INT/dropback':22s} {a_int_db:8.4f} {s_int_db:8.4f}")
    print(f"  {'Fumble lost/play':22s} {a_fum_pp:8.4f}")

    # 3. First-down rates
    print(f"\n3. FIRST-DOWN RATES")
    a_fd = scrim["first_down"].mean()
    s_fd = sim_df["ev_first_downs"].sum() / max(s_total, 1)
    print(f"  {'Overall FD/play':22s} {a_fd:8.3f} {s_fd:8.3f} {s_fd-a_fd:+8.3f}")

    # 4. Drive stats
    print(f"\n4. DRIVE STATS")
    s_scrim = sim_df["ev_pass_plays"] + sim_df["ev_rush_plays"]
    s_ppd = s_scrim.mean() / sim_df["drives"].mean()
    s_dpg = sim_df["drives"].mean()
    s_ppg = s_scrim.mean()
    pts = (sim_df["home_score"].mean() + sim_df["away_score"].mean()) / 2
    s_pts_per_drive = pts * 2 / s_dpg

    drive_plays = scrim.groupby(["game_id", "fixed_drive"]).size().reset_index(name="n_plays")
    a_ppd = drive_plays["n_plays"].mean()
    a_3ao = (drive_plays["n_plays"] == 3).mean()
    a_dpg = drive_plays.groupby("game_id").size().mean()
    a_pts = (act_df.drop_duplicates("game_id")["home_score"].mean() +
             act_df.drop_duplicates("game_id")["away_score"].mean()) / 2
    a_pts_per_drive = a_pts * 2 / a_dpg

    print(f"  {'Plays/drive':22s} {a_ppd:8.2f} {s_ppd:8.2f} {s_ppd-a_ppd:+8.2f}")
    print(f"  {'Drives/game':22s} {a_dpg:8.1f} {s_dpg:8.1f} {s_dpg-a_dpg:+8.1f}")
    print(f"  {'Plays/game':22s} {'124.5':>8s} {s_ppg:8.1f}")
    print(f"  {'Pts/team':22s} {a_pts:8.1f} {pts:8.1f} {pts-a_pts:+8.1f}")
    print(f"  {'Pts/drive':22s} {a_pts_per_drive:8.2f} {s_pts_per_drive:8.2f}")
    print(f"  {'3-and-out rate':22s} {a_3ao:8.3f}")

    # Drive-ending reason mix
    print(f"\n  DRIVE-ENDING REASON MIX")
    all_dr = act_df.groupby(["game_id", "fixed_drive"]).agg(
        punt=("play_type", lambda x: (x == "punt").any()),
        fg=("play_type", lambda x: (x == "field_goal").any()),
        td=("touchdown", "max"),
        intc=("interception", "max"),
        fum=("fumble_lost", "max"),
        end=("drive_end_transition", "last"),
    ).reset_index()
    nd = len(all_dr)
    tod_n = len(scrim[(scrim["down"] == 4) & (scrim["fourth_down_failed"] == 1)])
    eoh_n = all_dr["end"].isin(["END_HALF", "END_GAME"]).sum()
    total_dr_sim = sim_df["drives"].sum()
    print(f"  {'':22s} {'Actual':>8s} {'Sim':>8s}")
    print(f"  {'Punt':22s} {all_dr['punt'].mean():8.3f} {sim_df['ev_punts'].sum()/total_dr_sim:8.3f}")
    print(f"  {'FG attempt':22s} {all_dr['fg'].mean():8.3f} {sim_df['ev_fg_att'].sum()/total_dr_sim:8.3f}")
    print(f"  {'TD':22s} {all_dr['td'].mean():8.3f}")
    print(f"  {'INT':22s} {all_dr['intc'].mean():8.3f}")
    print(f"  {'Fumble lost':22s} {all_dr['fum'].mean():8.3f}")
    print(f"  {'Turnover on downs':22s} {tod_n/nd:8.3f}")
    print(f"  {'End of half':22s} {eoh_n/nd:8.3f}")
    print(f"  {'Sim TO/drive':22s} {'':8s} {sim_df['turnovers'].sum()/total_dr_sim:8.3f}")

    # 5. 4th-down decisions
    print(f"\n5. 4TH-DOWN DECISIONS")
    fourth = act_df[(act_df["down"] == 4) & act_df["play_type"].isin(["pass", "run", "punt", "field_goal"])]
    go = fourth[fourth["play_type"].isin(["pass", "run"])]
    print(f"  {'P(go) actual':22s} {len(go)/len(fourth):8.3f} ({len(go)}/{len(fourth)})")

    # 6. Penalty stats
    print(f"\n6. PENALTY STATS")
    no_plays = act_df[act_df["play_type"] == "no_play"]
    accepted_np = no_plays[no_plays["penalty"] == 1]
    scrim_pen = scrim[scrim["penalty"] == 1]
    total_pen = len(accepted_np) + len(scrim_pen)
    total_opp = len(scrim) + len(accepted_np)
    def_np = accepted_np[accepted_np["penalty_team"] != accepted_np["posteam"]]
    print(f"  {'Total pen rate':22s} {total_pen/total_opp:8.3f}")
    print(f"  {'Sim penalty rate':22s} {'':8s} {sim_df['ev_penalties'].sum()/(s_total+sim_df['ev_penalties'].sum()):8.3f}")
    print(f"  {'Def pen yds/game':22s} {def_np['penalty_yards'].sum()/n_games_act:8.1f}")
    print(f"  {'Def pen auto-1st':22s} {def_np['first_down_penalty'].mean():8.3f}")

    # 7. Red zone
    print(f"\n7. RED ZONE / FG")
    rz_plays = scrim[scrim["yardline_100"] <= 20]
    rz_trips = rz_plays.groupby(["game_id", "fixed_drive"]).size().reset_index().groupby("game_id").size()
    fg_att = act_df[act_df["play_type"] == "field_goal"]
    fg_made = fg_att[fg_att["field_goal_result"] == "made"]
    print(f"  {'RZ trips/game':22s} {rz_trips.mean():8.1f}")
    print(f"  {'FG att/game':22s} {len(fg_att)/n_games_act:8.1f}")
    print(f"  {'FG make rate':22s} {len(fg_made)/len(fg_att):8.3f}")
    sim_fg_per_game = sim_df["ev_fg_att"].mean()
    print(f"  {'Sim FG att/game':22s} {'':8s} {sim_fg_per_game:8.1f}")

    # 8. Explosive plays
    print(f"\n8. EXPLOSIVE PLAYS")
    pass_comp = passes[(passes["sack"] != 1) & (passes["interception"] != 1) & (passes["complete_pass"] == 1)]
    a_expl_pass = (pass_comp["yards_gained"] >= 20).mean()
    a_expl_rush = (rushes["yards_gained"] >= 12).mean()
    print(f"  {'Pass explosive ≥20':22s} {a_expl_pass:8.3f}")
    print(f"  {'Rush explosive ≥12':22s} {a_expl_rush:8.3f}")

    # 9. Yards/play with percentiles
    print(f"\n9. YARDS/PLAY")
    all_yds = scrim["yards_gained"].dropna()
    print(f"  {'Mean yds/play':22s} {all_yds.mean():8.2f}")
    print(f"  {'90th percentile':22s} {all_yds.quantile(0.90):8.0f}")
    print(f"  {'95th percentile':22s} {all_yds.quantile(0.95):8.0f}")

    # 10. Sack mean yards
    print(f"\n10. SACKS")
    sack_plays = passes[passes["sack"] == 1]
    a_sack_per_db = len(sack_plays) / len(passes)
    a_sack_yds = sack_plays["yards_gained"].mean()
    s_sack_per_db = sim_df["ev_sacks"].sum() / max(s_pass, 1)
    print(f"  {'Sack rate':22s} {a_sack_per_db:8.4f} {s_sack_per_db:8.4f}")
    print(f"  {'Mean sack yds':22s} {a_sack_yds:8.1f}")

    # 11. Sim TD/drive
    if "ev_tds" in sim_df.columns:
        sim_td_per_drive = sim_df["ev_tds"].sum() / total_dr_sim
        print(f"\n  TD/drive (sim):  {sim_td_per_drive:.3f}  (actual: {all_dr['td'].mean():.3f})")
        if "ev_fg_made" in sim_df.columns:
            sim_fg_rate = sim_df["ev_fg_made"].sum() / max(sim_df["ev_fg_att"].sum(), 1)
            print(f"  FG make rate (sim): {sim_fg_rate:.3f}  (actual: {len(fg_made)/len(fg_att):.3f})")

    # Summary
    margin_sd = (sim_df["home_score"] - sim_df["away_score"]).std()
    print(f"\n  SUMMARY: pts/team={pts:.1f}  plays/drive={s_ppd:.2f}  "
          f"drives/game={s_dpg:.1f}  per-sim margin SD={margin_sd:.1f}")


if __name__ == "__main__":
    from nfl.sim.engine import simulate_game, _load_tables, _load_ratings

    print("Loading data...")
    act_df = load_actuals()
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    games = pd.read_parquet(PBP_DIR / "pbp_2023.parquet",
                             columns=["game_id", "season", "week", "home_team",
                                       "away_team", "home_score", "away_score"])
    games = games.drop_duplicates("game_id").query("week <= 18")
    rng = np.random.default_rng(42)
    sample = games.iloc[rng.choice(len(games), 50, replace=False)]

    print(f"Running 50 games x 2000 sims...")
    t0 = time.time()
    results = []
    for _, g in sample.iterrows():
        s = hash((g["game_id"], 42)) % (2**31)
        r = simulate_game(g["home_team"], g["away_team"], 2023, int(g["week"]),
                          n_sims=2000, seed=s,
                          team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)
        r["game_id"] = g["game_id"]
        results.append(r)
    sim_df = pd.concat(results, ignore_index=True)
    t1 = time.time()
    print(f"Completed in {t1-t0:.1f}s ({(t1-t0)/50:.2f}s/game)")

    print_diagnostics("POST-FIX DIAGNOSTICS", act_df, sim_df)
