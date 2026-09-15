#!/usr/bin/env python3
"""
Phase 5A-2: Scoring-Conversion Diagnostic.

Compares sim vs actual drive-level, red-zone, FG, turnover, 3rd-down,
explosive, PAT, quarter scoring, and margin distributions.

Steps 2-5 of the Phase 5A-2 spec.
"""

import sys, time, json
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs"
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed

SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 500


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Actual per-drive table from nflverse PBP
# ═══════════════════════════════════════════════════════════════════════════════

def build_actual_drives():
    """Build per-drive table from nflverse PBP 2021-2024."""
    frames = []
    for s in SEASONS:
        frames.append(pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet"))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["week"] <= 18].copy()

    # Scrimmage plays
    scrim = df[df["play_type"].isin(["pass", "run"]) & df["down"].notna()].copy()

    # Build per-drive summary
    drive_rows = []
    for (gid, drv), grp in scrim.groupby(["game_id", "fixed_drive"]):
        all_plays_in_drive = df[(df["game_id"] == gid) & (df["fixed_drive"] == drv)]
        first_play = all_plays_in_drive.iloc[0]
        season = first_play["season"]

        start_yl = grp["yardline_100"].iloc[0]
        start_qtr = int(grp["qtr"].iloc[0])

        n_plays = len(grp)
        total_yards = grp["yards_gained"].sum()

        # Drive result
        drive_result_raw = first_play.get("fixed_drive_result", "")
        det = first_play.get("drive_end_transition", "")

        # Map to our categories
        if drive_result_raw == "Touchdown":
            result = "TD"
        elif drive_result_raw == "Opp touchdown":
            # Defensive/ST TD — the offense's drive ended in a turnover
            if "INTERCEPTION" in str(det):
                result = "turnover_int"
            elif "FUMBLE" in str(det):
                result = "turnover_fumble"
            else:
                result = "turnover_fumble"  # default for def TD
        elif drive_result_raw == "Field goal":
            result = "FG_made"
        elif drive_result_raw == "Missed field goal":
            result = "FG_missed"
        elif drive_result_raw == "Punt":
            result = "punt"
        elif drive_result_raw == "Turnover":
            if "INTERCEPTION" in str(det):
                result = "turnover_int"
            elif "FUMBLE" in str(det):
                result = "turnover_fumble"
            else:
                result = "turnover_int"  # default
        elif drive_result_raw == "Turnover on downs":
            result = "downs"
        elif drive_result_raw == "End of half":
            result = "end_half"
        elif drive_result_raw == "Safety":
            result = "safety"
        else:
            result = "end_game"

        # Points: count TDs, FGs
        has_td = grp["touchdown"].max() == 1
        fg_plays = all_plays_in_drive[all_plays_in_drive["play_type"] == "field_goal"]
        fg_made = (fg_plays["field_goal_result"] == "made").any() if len(fg_plays) else False

        # For offensive TD drives, compute actual points scored
        if result == "TD":
            pts = 6
            # Check PAT
            pat = all_plays_in_drive[all_plays_in_drive["play_type"] == "extra_point"]
            twopt = all_plays_in_drive[all_plays_in_drive["two_point_attempt"] == 1]
            if len(pat) and (pat["extra_point_result"] == "good").any():
                pts += 1
            elif len(twopt) and (twopt["two_point_conv_result"] == "success").any():
                pts += 2
        elif result == "FG_made":
            pts = 3
        elif result == "safety":
            pts = -2  # offensive team gives up 2 points
        else:
            pts = 0

        # Red zone / goal line
        min_yl = grp["yardline_100"].min()
        reached_rz = min_yl <= 20
        reached_gl = min_yl <= 5

        drive_rows.append({
            "game_id": gid, "season": season, "drive_no": drv,
            "start_yardline": start_yl, "start_quarter": start_qtr,
            "plays": n_plays, "yards": total_yards,
            "result": result, "points": pts,
            "reached_rz": reached_rz, "reached_gl": reached_gl,
        })

    drives_df = pd.DataFrame(drive_rows)
    return drives_df, df


def build_actual_game_stats(df):
    """Build per-game actual stats for comparison."""
    games = df.drop_duplicates("game_id")[["game_id", "season", "home_score", "away_score"]].copy()
    scrim = df[df["play_type"].isin(["pass", "run"]) & df["down"].notna()]

    # 3rd down
    third = scrim[scrim["down"] == 3]
    third_conv = third[third["first_down"] == 1]
    g3 = third.groupby("game_id").size().rename("third_att")
    g3c = third_conv.groupby("game_id").size().rename("third_conv")

    # 4th down go
    fourth = df[(df["down"] == 4) & df["play_type"].isin(["pass", "run"])]
    fourth_conv = fourth[fourth["first_down"] == 1]
    g4 = fourth.groupby("game_id").size().rename("fourth_go")
    g4c = fourth_conv.groupby("game_id").size().rename("fourth_conv")

    # FG
    fg = df[df["play_type"] == "field_goal"]
    fg_made = fg[fg["field_goal_result"] == "made"]
    fg_att_g = fg.groupby("game_id").size().rename("fg_att")
    fg_made_g = fg_made.groupby("game_id").size().rename("fg_made")
    fg_dist_g = fg.groupby("game_id")["kick_distance"].sum().rename("fg_dist_sum")

    # Explosive
    passes = df[(df["play_type"] == "pass") & df["down"].notna()]
    comp = passes[(passes["sack"] != 1) & (passes["interception"] != 1) & (passes["complete_pass"] == 1)]
    explosive_pass = comp[comp["yards_gained"] >= 20].groupby("game_id").size().rename("expl_pass")
    rushes = df[(df["play_type"] == "run") & df["down"].notna()]
    explosive_rush = rushes[rushes["yards_gained"] >= 10].groupby("game_id").size().rename("expl_rush")

    # Turnovers
    ints_g = passes[passes["interception"] == 1].groupby("game_id").size().rename("ints")
    fum_g = scrim[scrim["fumble_lost"] == 1].groupby("game_id").size().rename("fumbles")

    result = games.set_index("game_id")
    for s in [g3, g3c, g4, g4c, fg_att_g, fg_made_g, fg_dist_g,
              explosive_pass, explosive_rush, ints_g, fum_g]:
        result = result.join(s, how="left")
    result = result.fillna(0).reset_index()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Run K1 with drive log
# ═══════════════════════════════════════════════════════════════════════════════

def run_k1_with_drives():
    """Run K1 backtest (1,087 games, N=500) with drive_log=True."""
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

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
                team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
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
        print(f"  Season {s}: {len(games)} games, {elapsed:.1f}s "
              f"({elapsed/len(games):.2f}s/game)")

    sim_df = pd.concat(all_results, ignore_index=True)
    drive_df = pd.concat(all_drives, ignore_index=True) if all_drives else pd.DataFrame()
    return sim_df, drive_df


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Compare sim vs actual
# ═══════════════════════════════════════════════════════════════════════════════

def field_pos_bucket(yl):
    """Map yardline_100 to 5 buckets for comparison."""
    if yl <= 20:
        return "opp1-20"
    elif yl <= 40:
        return "opp21-40"
    elif yl <= 60:
        return "41-60"
    elif yl <= 80:
        return "own21-40"
    else:
        return "own1-20"


def compute_between_season_sd(series_by_season, stat_func):
    """Compute between-season SD of a statistic."""
    vals = [stat_func(series_by_season[s]) for s in SEASONS if s in series_by_season]
    return np.std(vals, ddof=1) if len(vals) > 1 else 0.0


def compare_all(sim_df, sim_drives, act_drives, act_df, act_game_stats):
    """Run all Step 4 comparisons. Returns tables dict."""
    tables = {}
    n_games = act_df["game_id"].nunique()
    n_sims_total = len(sim_df)

    # ── 4a: Drive result distribution ──
    print("\n" + "="*70)
    print("  4a. DRIVE RESULT DISTRIBUTION")
    print("="*70)

    act_result_counts = act_drives["result"].value_counts(normalize=True)
    sim_result_counts = sim_drives["result"].value_counts(normalize=True)

    all_results = sorted(set(act_result_counts.index) | set(sim_result_counts.index))
    rows_4a = []
    for r in all_results:
        a = act_result_counts.get(r, 0)
        s = sim_result_counts.get(r, 0)
        # Between-season SD
        season_vals = []
        for yr in SEASONS:
            ad = act_drives[act_drives["season"] == yr]
            season_vals.append((ad["result"] == r).mean())
        bsd = np.std(season_vals, ddof=1)
        flag = "MATERIAL" if abs(s - a) > 2 * bsd and bsd > 0 else ""
        rows_4a.append({"result": r, "actual": a, "sim": s, "delta": s-a,
                        "season_SD": bsd, "flag": flag,
                        "N_act": (act_drives["result"]==r).sum(),
                        "N_sim": (sim_drives["result"]==r).sum()})
    tbl_4a = pd.DataFrame(rows_4a)
    print(tbl_4a.to_string(index=False, float_format="%.4f"))
    tables["4a"] = tbl_4a

    # Points per drive
    act_ppd = act_drives[act_drives["points"] > 0]["points"].sum() / len(act_drives)
    sim_ppd = sim_drives[sim_drives["points"] > 0]["points"].sum() / len(sim_drives)
    print(f"\nPoints per drive: actual={act_ppd:.3f}  sim={sim_ppd:.3f}  delta={sim_ppd-act_ppd:+.3f}")

    # ── 4b: Points per drive by starting field position ──
    print("\n" + "="*70)
    print("  4b. TD RATE & POINTS/DRIVE BY STARTING FIELD POSITION")
    print("="*70)

    act_drives["fp_bucket"] = act_drives["start_yardline"].apply(field_pos_bucket)
    sim_drives["fp_bucket"] = sim_drives["start_yardline"].apply(field_pos_bucket)

    buckets = ["own1-20", "own21-40", "41-60", "opp21-40", "opp1-20"]
    rows_4b = []
    for b in buckets:
        ad = act_drives[act_drives["fp_bucket"] == b]
        sd = sim_drives[sim_drives["fp_bucket"] == b]
        a_td = (ad["result"] == "TD").mean() if len(ad) else 0
        s_td = (sd["result"] == "TD").mean() if len(sd) else 0
        a_ppd = ad["points"].clip(lower=0).sum() / max(len(ad), 1)
        s_ppd = sd["points"].clip(lower=0).sum() / max(len(sd), 1)
        # Between-season SD for TD rate
        svs = []
        for yr in SEASONS:
            ady = act_drives[(act_drives["season"]==yr)&(act_drives["fp_bucket"]==b)]
            svs.append((ady["result"]=="TD").mean() if len(ady) else 0)
        bsd = np.std(svs, ddof=1)
        flag = "MATERIAL" if abs(s_td - a_td) > 2 * bsd and bsd > 0 else ""
        rows_4b.append({"bucket": b, "act_TD_rate": a_td, "sim_TD_rate": s_td,
                        "act_ppd": a_ppd, "sim_ppd": s_ppd,
                        "N_act": len(ad), "N_sim": len(sd),
                        "season_SD": bsd, "flag": flag})
    tbl_4b = pd.DataFrame(rows_4b)
    print(tbl_4b.to_string(index=False, float_format="%.4f"))
    tables["4b"] = tbl_4b

    # ── 4c: Red zone ──
    print("\n" + "="*70)
    print("  4c. RED ZONE")
    print("="*70)

    act_rz = act_drives[act_drives["reached_rz"]]
    sim_rz = sim_drives[sim_drives["reached_rz"]]
    act_rz_per_game = len(act_rz) / n_games
    sim_rz_per_game = len(sim_rz) / (n_sims_total / 2)  # /2 for per-team

    act_rz_td = (act_rz["result"] == "TD").mean()
    sim_rz_td = (sim_rz["result"] == "TD").mean()
    act_rz_fg = (act_rz["result"] == "FG_made").mean()
    sim_rz_fg = (sim_rz["result"] == "FG_made").mean()
    act_rz_to = act_rz["result"].isin(["turnover_int", "turnover_fumble"]).mean()
    sim_rz_to = sim_rz["result"].isin(["turnover_int", "turnover_fumble"]).mean()

    rz_rows = [
        {"metric": "RZ drives/game", "actual": act_rz_per_game,
         "sim": sim_rz_per_game * 2},  # *2 for both teams
        {"metric": "TD rate|RZ", "actual": act_rz_td, "sim": sim_rz_td},
        {"metric": "FG rate|RZ", "actual": act_rz_fg, "sim": sim_rz_fg},
        {"metric": "TO rate|RZ", "actual": act_rz_to, "sim": sim_rz_to},
        {"metric": "Plays/RZ drive", "actual": act_rz["plays"].mean(),
         "sim": sim_rz["plays"].mean()},
    ]
    tbl_4c = pd.DataFrame(rz_rows)
    tbl_4c["delta"] = tbl_4c["sim"] - tbl_4c["actual"]
    print(tbl_4c.to_string(index=False, float_format="%.4f"))

    # Yards/play inside RZ vs outside
    act_scrim = act_df[act_df["play_type"].isin(["pass", "run"]) & act_df["down"].notna()]
    act_rz_ypp = act_scrim[act_scrim["yardline_100"] <= 20]["yards_gained"].mean()
    act_nrz_ypp = act_scrim[act_scrim["yardline_100"] > 20]["yards_gained"].mean()
    print(f"\nActual yds/play: RZ={act_rz_ypp:.2f}  non-RZ={act_nrz_ypp:.2f}")
    tables["4c"] = tbl_4c

    # ── 4d: Field goals ──
    print("\n" + "="*70)
    print("  4d. FIELD GOALS")
    print("="*70)

    fg_actual = act_df[act_df["play_type"] == "field_goal"]
    fg_made_actual = fg_actual[fg_actual["field_goal_result"] == "made"]
    act_fg_per_game = len(fg_actual) / n_games
    sim_fg_per_game = sim_df["ev_fg_att"].mean()
    act_fg_make = len(fg_made_actual) / max(len(fg_actual), 1)
    sim_fg_make = sim_df["ev_fg_made"].sum() / max(sim_df["ev_fg_att"].sum(), 1)

    # Distance distribution
    act_fg_dist = fg_actual["kick_distance"].describe()
    sim_avg_fg_dist = sim_df["ev_fg_dist_sum"].sum() / max(sim_df["ev_fg_att"].sum(), 1)

    print(f"FG att/game:  actual={act_fg_per_game:.2f}  sim={sim_fg_per_game:.2f}")
    print(f"FG make rate: actual={act_fg_make:.3f}  sim={sim_fg_make:.3f}")
    print(f"Avg FG dist:  actual={fg_actual['kick_distance'].mean():.1f}  sim={sim_avg_fg_dist:.1f}")

    # FG make rate by distance bucket
    fg_actual_c = fg_actual.copy()
    fg_actual_c["dist_b"] = pd.cut(fg_actual_c["kick_distance"],
                                    bins=[0, 30, 40, 50, 70],
                                    labels=["<30", "30-39", "40-49", "50+"])
    fg_dist_tbl = fg_actual_c.groupby("dist_b", observed=True).agg(
        n=("field_goal_result", "size"),
        made=("field_goal_result", lambda x: (x == "made").sum())
    )
    fg_dist_tbl["make_rate"] = fg_dist_tbl["made"] / fg_dist_tbl["n"]
    print(f"\nActual FG make rate by distance:")
    print(fg_dist_tbl.to_string())

    # 4th-down decisions
    fourth = act_df[(act_df["down"] == 4) & act_df["play_type"].isin(["pass", "run", "punt", "field_goal"])]
    go = fourth[fourth["play_type"].isin(["pass", "run"])]
    punt = fourth[fourth["play_type"] == "punt"]
    fg_4th = fourth[fourth["play_type"] == "field_goal"]
    print(f"\n4th-down decisions: go={len(go)/len(fourth):.3f} punt={len(punt)/len(fourth):.3f} "
          f"fg={len(fg_4th)/len(fourth):.3f} (N={len(fourth)})")
    sim_4th_go_rate = sim_df["ev_4th_go"].sum() / max(
        sim_df["ev_4th_go"].sum() + sim_df["ev_punts"].sum() + sim_df["ev_fg_att"].sum(), 1)
    print(f"Sim 4th-go rate: {sim_4th_go_rate:.3f}")

    tables["4d_fg"] = {"act_fg_pg": act_fg_per_game, "sim_fg_pg": sim_fg_per_game,
                       "act_make": act_fg_make, "sim_make": sim_fg_make}

    # ── 4e: Turnovers ──
    print("\n" + "="*70)
    print("  4e. TURNOVERS")
    print("="*70)

    act_ints = act_game_stats["ints"].mean()
    act_fums = act_game_stats["fumbles"].mean()
    sim_ints = sim_df["ev_ints"].mean()
    # sim fumbles = total turnovers minus INTs (per sim)
    sim_fums = (sim_df["turnovers"] - sim_df["ev_ints"]).mean()
    print(f"INTs/game:    actual={act_ints:.2f}  sim={sim_ints:.2f}")
    print(f"Fumbles/game: actual={act_fums:.2f}  sim={sim_fums:.2f}")
    print(f"Total TO/game: actual={act_ints+act_fums:.2f}  sim={sim_df['turnovers'].mean():.2f}")

    # Points off turnovers
    act_to_drives = act_drives[act_drives["result"].isin(["turnover_int", "turnover_fumble"])]
    sim_to_drives = sim_drives[sim_drives["result"].isin(["turnover_int", "turnover_fumble"])]
    # These are the offense's drives that ended in TO; points off = next drive's points
    # Hard to compute from drive data alone; skip and note

    tables["4e"] = {"act_ints": act_ints, "sim_ints": sim_ints,
                    "act_fums": act_fums, "sim_fums": sim_fums}

    # ── 4f: Third-down conversion rate ──
    print("\n" + "="*70)
    print("  4f. THIRD-DOWN CONVERSION")
    print("="*70)

    third = act_df[(act_df["play_type"].isin(["pass", "run"])) & (act_df["down"] == 3)]
    third_conv = third[third["first_down"] == 1]
    act_3rd_rate = len(third_conv) / len(third)
    sim_3rd_rate = sim_df["ev_3rd_conv"].sum() / max(sim_df["ev_3rd_att"].sum(), 1)
    print(f"3rd-down conv rate: actual={act_3rd_rate:.3f}  sim={sim_3rd_rate:.3f}")

    # By distance bucket
    third_c = third.copy()
    third_c["dist_b"] = pd.cut(third_c["ydstogo"], bins=[0, 3, 7, 100],
                                labels=["short(1-3)", "med(4-7)", "long(8+)"])
    for db, grp in third_c.groupby("dist_b", observed=True):
        conv = (grp["first_down"] == 1).mean()
        print(f"  {db}: {conv:.3f} (N={len(grp)})")

    # 4th-down conversion
    act_4th = act_df[(act_df["play_type"].isin(["pass", "run"])) & (act_df["down"] == 4)]
    act_4th_conv = (act_4th["first_down"] == 1).mean()
    sim_4th_conv = sim_df["ev_4th_conv"].sum() / max(sim_df["ev_4th_go"].sum(), 1)
    print(f"\n4th-down conv rate: actual={act_4th_conv:.3f}  sim={sim_4th_conv:.3f}")

    tables["4f"] = {"act_3rd": act_3rd_rate, "sim_3rd": sim_3rd_rate,
                    "act_4th": act_4th_conv, "sim_4th": sim_4th_conv}

    # ── 4g: Explosive plays ──
    print("\n" + "="*70)
    print("  4g. EXPLOSIVE PLAYS")
    print("="*70)

    act_expl_pass = act_game_stats["expl_pass"].mean()
    act_expl_rush = act_game_stats["expl_rush"].mean()
    print(f"Explosive pass (20+)/game: actual={act_expl_pass:.2f}")
    print(f"Explosive rush (10+)/game: actual={act_expl_rush:.2f}")
    # Sim explosive counts not tracked yet — report actual only and note

    # ── 4h: Two-point and XP ──
    print("\n" + "="*70)
    print("  4h. PAT: XP AND 2PT")
    print("="*70)

    xp = act_df[act_df["play_type"] == "extra_point"]
    xp_good = (xp["extra_point_result"] == "good").sum()
    twopt = act_df[act_df["two_point_attempt"] == 1]
    twopt_good = (twopt["two_point_conv_result"] == "success").sum()
    act_xp_rate = xp_good / max(len(xp), 1)
    act_2pt_rate = twopt_good / max(len(twopt), 1)
    act_2pt_attempt_rate = len(twopt) / max(len(xp) + len(twopt), 1)

    # Sim: compute from sim TD drives
    sim_td_drives = sim_drives[sim_drives["result"] == "TD"]
    sim_pts_vals = sim_td_drives["points"].value_counts().sort_index()
    sim_xp_rate_approx = (sim_td_drives["points"] == 7).sum() / max(len(sim_td_drives), 1)
    sim_2pt_rate_approx = (sim_td_drives["points"] == 8).sum() / max(len(sim_td_drives), 1)

    print(f"XP make rate:       actual={act_xp_rate:.3f}")
    print(f"2pt conv rate:      actual={act_2pt_rate:.3f}")
    print(f"2pt attempt rate:   actual={act_2pt_attempt_rate:.3f}")
    print(f"\nSim TD drive points distribution:")
    for pts, cnt in sim_pts_vals.items():
        print(f"  {pts} pts: {cnt} ({cnt/len(sim_td_drives)*100:.1f}%)")

    tables["4h"] = {"act_xp_rate": act_xp_rate, "act_2pt_rate": act_2pt_rate}

    # ── 4i: Scoring by quarter ──
    print("\n" + "="*70)
    print("  4i. SCORING BY QUARTER")
    print("="*70)

    # Actual: compute from PBP touchdown/FG events by quarter
    scoring_plays = act_df[act_df["play_type"].isin(["field_goal", "extra_point"]) |
                           (act_df["touchdown"] == 1)]
    act_pts_by_q = {}
    for q in [1, 2, 3, 4]:
        q_plays = scoring_plays[scoring_plays["qtr"] == q]
        tds = (q_plays["touchdown"] == 1).sum()
        fgs = ((q_plays["play_type"] == "field_goal") & (q_plays["field_goal_result"] == "made")).sum()
        xps = ((q_plays["play_type"] == "extra_point") & (q_plays["extra_point_result"] == "good")).sum()
        twpts = ((q_plays["two_point_attempt"] == 1) & (q_plays["two_point_conv_result"] == "success")).sum()
        pts = tds * 6 + fgs * 3 + xps + twpts * 2
        act_pts_by_q[q] = pts / n_games

    # Last 2:00 of each half
    act_last2_h1 = scoring_plays[(scoring_plays["qtr"] == 2) &
                                  (scoring_plays["game_seconds_remaining"] <= 1920)  # ~Q2 last 2 min
                                  ]
    print("Actual pts/game by quarter:")
    for q in [1, 2, 3, 4]:
        print(f"  Q{q}: {act_pts_by_q[q]:.2f}")

    # Sim: can compute from drive log by quarter
    sim_pts_by_q = {}
    for q in [1, 2, 3, 4]:
        qd = sim_drives[sim_drives["start_quarter"] == q]
        pts = qd["points"].clip(lower=0).sum()
        sim_pts_by_q[q] = pts / n_sims_total * 2  # per game
    print("Sim pts/game by quarter:")
    for q in [1, 2, 3, 4]:
        print(f"  Q{q}: {sim_pts_by_q.get(q, 0):.2f}")

    tables["4i"] = {"actual": act_pts_by_q, "sim": sim_pts_by_q}

    # ── 4j: Margin distribution ──
    print("\n" + "="*70)
    print("  4j. MARGIN DISTRIBUTION")
    print("="*70)

    act_games = act_df.drop_duplicates("game_id")
    act_margin = (act_games["home_score"] - act_games["away_score"]).abs()
    sim_margin = (sim_df["home_score"] - sim_df["away_score"]).abs()

    rows_4j = []
    for k in range(1, 15):
        a = (act_margin == k).mean()
        s = (sim_margin == k).mean()
        svs = []
        for yr in SEASONS:
            ag = act_games[act_games["season"] == yr] if "season" in act_games.columns else act_games
            am = (ag["home_score"] - ag["away_score"]).abs()
            svs.append((am == k).mean())
        bsd = np.std(svs, ddof=1)
        flag = "MATERIAL" if abs(s - a) > 2 * bsd and bsd > 0 else ""
        rows_4j.append({"margin": k, "actual": a, "sim": s, "delta": s-a,
                        "season_SD": bsd, "flag": flag,
                        "N_act": (act_margin == k).sum()})
    tbl_4j = pd.DataFrame(rows_4j)
    print(tbl_4j.to_string(index=False, float_format="%.4f"))

    # FG-decided share
    act_fg_decided = act_drives.groupby("game_id").apply(
        lambda x: x.iloc[-1]["result"] in ["FG_made"] if len(x) else False
    )
    # Simplified: games decided by 3 are FG-likely
    act_margin3 = (act_margin == 3).sum()
    sim_margin3 = (sim_margin == 3).sum()
    print(f"\nP(|margin|=3): actual={act_margin3/len(act_games):.4f}  "
          f"sim={sim_margin3/len(sim_df):.4f}")
    print(f"FG-decided games fraction: sim FG_made drives per game = "
          f"{sim_df['ev_fg_made'].mean():.2f}")

    tables["4j"] = tbl_4j

    return tables


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Attribution
# ═══════════════════════════════════════════════════════════════════════════════

def attribution(tables, sim_df, sim_drives, act_drives, act_df):
    """Step 5: Identify mechanisms for the scoring deficit."""
    print("\n" + "="*70)
    print("  STEP 5: ATTRIBUTION")
    print("="*70)

    act_games = act_df.drop_duplicates("game_id")
    act_pts = (act_games["home_score"].mean() + act_games["away_score"].mean()) / 2
    sim_pts = (sim_df["home_score"].mean() + sim_df["away_score"].mean()) / 2

    print(f"\nScoring deficit: sim {sim_pts:.1f} vs actual {act_pts:.1f} = {sim_pts-act_pts:+.1f} pts/team")

    # TD rate
    act_td_rate = (act_drives["result"] == "TD").mean()
    sim_td_rate = (sim_drives["result"] == "TD").mean()
    print(f"TD/drive: actual={act_td_rate:.4f} sim={sim_td_rate:.4f} delta={sim_td_rate-act_td_rate:+.4f}")

    # FG rate
    act_fg_rate = (act_drives["result"] == "FG_made").mean()
    sim_fg_rate = (sim_drives["result"] == "FG_made").mean()
    print(f"FG/drive: actual={act_fg_rate:.4f} sim={sim_fg_rate:.4f} delta={sim_fg_rate-act_fg_rate:+.4f}")

    # Decompose scoring deficit
    act_dpg = len(act_drives) / act_df["game_id"].nunique()
    sim_dpg = sim_df["drives"].mean()
    act_td_pts = act_td_rate * act_dpg / 2 * 6.5  # avg TD worth ~6.5 with PAT
    sim_td_pts = sim_td_rate * sim_dpg / 2 * 6.5
    act_fg_pts = act_fg_rate * act_dpg / 2 * 3
    sim_fg_pts = sim_fg_rate * sim_dpg / 2 * 3

    print(f"\nScoring decomposition (pts/team):")
    print(f"  TD contribution: actual={act_td_pts:.1f} sim={sim_td_pts:.1f} delta={sim_td_pts-act_td_pts:+.1f}")
    print(f"  FG contribution: actual={act_fg_pts:.1f} sim={sim_fg_pts:.1f} delta={sim_fg_pts-act_fg_pts:+.1f}")

    # Red zone analysis
    act_rz = act_drives[act_drives["reached_rz"]]
    sim_rz = sim_drives[sim_drives["reached_rz"]]
    act_rz_td = (act_rz["result"] == "TD").mean()
    sim_rz_td = (sim_rz["result"] == "TD").mean()
    print(f"\nRed zone TD rate: actual={act_rz_td:.3f} sim={sim_rz_td:.3f}")

    # 3rd-down impact
    act_3rd = tables["4f"]["act_3rd"]
    sim_3rd = tables["4f"]["sim_3rd"]
    print(f"3rd-down conv:    actual={act_3rd:.3f} sim={sim_3rd:.3f}")

    # Key-number analysis
    tbl_4j = tables["4j"]
    m3 = tbl_4j[tbl_4j["margin"] == 3].iloc[0]
    m6 = tbl_4j[tbl_4j["margin"] == 6].iloc[0]
    m7 = tbl_4j[tbl_4j["margin"] == 7].iloc[0]
    print(f"\nKey-number mass:")
    print(f"  |margin|=3: actual={m3['actual']:.4f} sim={m3['sim']:.4f} ({m3['flag']})")
    print(f"  |margin|=6: actual={m6['actual']:.4f} sim={m6['sim']:.4f} ({m6['flag']})")
    print(f"  |margin|=7: actual={m7['actual']:.4f} sim={m7['sim']:.4f} ({m7['flag']})")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 by-season breakdown
# ═══════════════════════════════════════════════════════════════════════════════

def by_season_tables(sim_df, sim_drives, act_drives, act_df):
    """Run key comparisons by season."""
    print("\n" + "="*70)
    print("  BY-SEASON BREAKDOWN")
    print("="*70)

    act_games = act_df.drop_duplicates("game_id")

    for yr in SEASONS:
        ag = act_games[act_games["season"] == yr]
        sd = sim_df[sim_df["season"] == yr]
        ad = act_drives[act_drives["season"] == yr]
        sdr = sim_drives[sim_drives["season"] == yr]

        act_pts = (ag["home_score"].mean() + ag["away_score"].mean()) / 2
        sim_pts = (sd["home_score"].mean() + sd["away_score"].mean()) / 2

        act_td_rate = (ad["result"] == "TD").mean()
        sim_td_rate = (sdr["result"] == "TD").mean() if len(sdr) else 0
        act_fg_rate = (ad["result"] == "FG_made").mean()
        sim_fg_rate = (sdr["result"] == "FG_made").mean() if len(sdr) else 0

        act_rz = ad[ad["reached_rz"]]
        sim_rz = sdr[sdr["reached_rz"]]
        act_rz_td = (act_rz["result"] == "TD").mean() if len(act_rz) else 0
        sim_rz_td = (sim_rz["result"] == "TD").mean() if len(sim_rz) else 0

        print(f"\n{yr}: pts/team act={act_pts:.1f} sim={sim_pts:.1f} | "
              f"TD/drv act={act_td_rate:.3f} sim={sim_td_rate:.3f} | "
              f"FG/drv act={act_fg_rate:.3f} sim={sim_fg_rate:.3f} | "
              f"RZ_TD act={act_rz_td:.3f} sim={sim_rz_td:.3f}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    t_start = time.time()

    print("STEP 2: Building actual drive table from PBP 2021-2024...")
    t0 = time.time()
    act_drives, act_df = build_actual_drives()
    act_game_stats = build_actual_game_stats(act_df)
    print(f"  {len(act_drives)} drives, {act_df['game_id'].nunique()} games ({time.time()-t0:.1f}s)")

    # Add season to act_df games
    act_games = act_df.drop_duplicates("game_id")[["game_id", "season"]].copy()

    print(f"\nSTEP 3: Running K1 backtest (N={N_SIMS}, 1087 games) with drive log...")
    t0 = time.time()
    sim_df, sim_drives = run_k1_with_drives()
    k1_runtime = time.time() - t0
    print(f"  K1 runtime: {k1_runtime:.1f}s ({k1_runtime/1087:.2f}s/game)")
    print(f"  {len(sim_drives)} sim drive rows, {len(sim_df)} sim rows")

    # Save outputs
    sim_drives.to_parquet(OUT_DIR / "k1_drives_5a2.parquet", index=False)
    act_drives.to_parquet(OUT_DIR / "actual_drives_2021_2024.parquet", index=False)
    print(f"  Saved to {OUT_DIR}/k1_drives_5a2.parquet and actual_drives_2021_2024.parquet")

    print(f"\nSTEP 4: Comparing sim vs actual...")
    tables = compare_all(sim_df, sim_drives, act_drives, act_df, act_game_stats)

    by_season_tables(sim_df, sim_drives, act_drives, act_df)

    print(f"\nSTEP 5: Attribution...")
    attribution(tables, sim_df, sim_drives, act_drives, act_df)

    total_runtime = time.time() - t_start
    print(f"\nTotal runtime: {total_runtime:.1f}s ({total_runtime/60:.1f}m)")
