#!/usr/bin/env python3
"""
Phase 5A-4 STEP 6: K1 before/after comparison.
Reads pre-5a4 (k1_5a4.parquet) and post-5a4 (k1_5a4_after.parquet) results.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs"
PBP_DIR = ROOT / "nfl" / "data" / "pbp"


def load_actuals():
    frames = []
    for s in [2021, 2022, 2023, 2024]:
        p = PBP_DIR / f"pbp_{s}.parquet"
        df = pd.read_parquet(p, columns=["game_id", "season", "week", "home_team",
                                          "away_team", "home_score", "away_score"])
        games = df.drop_duplicates("game_id").query("week <= 18")
        frames.append(games)
    return pd.concat(frames, ignore_index=True)


def report(label, sims, actuals):
    """Print K1 metrics for a sim set."""
    n_games = actuals.shape[0]
    act_pts = (actuals["home_score"].mean() + actuals["away_score"].mean()) / 2
    sim_pts = (sims["home_score"].mean() + sims["away_score"].mean()) / 2
    sim_plays = sims["plays"].mean()
    sim_drives = sims["drives"].mean()
    sim_h_pass = sims["home_pass_yds"].mean()
    sim_h_rush = sims["home_rush_yds"].mean()
    sim_a_pass = sims["away_pass_yds"].mean()
    sim_a_rush = sims["away_rush_yds"].mean()
    sim_pass = (sim_h_pass + sim_a_pass) / 2
    sim_rush = (sim_h_rush + sim_a_rush) / 2

    # Margin stats
    sims = sims.copy()
    sims["margin"] = sims["home_score"] - sims["away_score"]
    act_margins = actuals["home_score"] - actuals["away_score"]
    sim_margin_sd = sims["margin"].std()
    act_margin_sd = act_margins.std()

    # Drive-related
    total_4th = sims["ev_4th_go"].sum() + sims["ev_punts"].sum() + sims["ev_fg_att"].sum()
    go_rate = sims["ev_4th_go"].sum() / max(total_4th, 1)
    fg_pg = sims["ev_fg_att"].mean()

    # Penalty stats (5A-4)
    pen_pg = sims["ev_penalties"].mean() if "ev_penalties" in sims.columns else 0
    off_pen_pg = sims["ev_pen_offense"].mean() if "ev_pen_offense" in sims.columns else 0
    def_pen_pg = sims["ev_pen_defense"].mean() if "ev_pen_defense" in sims.columns else 0
    off_pen_yds_pg = sims["ev_pen_off_yds"].mean() if "ev_pen_off_yds" in sims.columns else 0
    def_pen_yds_pg = sims["ev_pen_def_yds"].mean() if "ev_pen_def_yds" in sims.columns else 0
    fd_rush_pg = sims["ev_fd_rush"].mean() if "ev_fd_rush" in sims.columns else 0
    fd_pass_pg = sims["ev_fd_pass"].mean() if "ev_fd_pass" in sims.columns else 0
    fd_pen_pg = sims["ev_fd_penalty"].mean() if "ev_fd_penalty" in sims.columns else 0
    fd_total = sims["ev_first_downs"].mean()
    safety_pg = sims["ev_safeties"].mean() if "ev_safeties" in sims.columns else 0

    # P(|margin|=k)
    margin_probs = {}
    for k in range(1, 15):
        sim_p = (sims["margin"].abs() == k).mean()
        act_p = (act_margins.abs() == k).mean()
        margin_probs[k] = (sim_p, act_p)

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Mean pts/team:    {sim_pts:.1f}  (actual: {act_pts:.1f})")
    print(f"  Plays/game:       {sim_plays:.1f}  (actual: 124.5)")
    print(f"  Drives/game:      {sim_drives:.1f}  (actual: 21.9)")
    print(f"  SD margin:        {sim_margin_sd:.2f}  (actual: {act_margin_sd:.2f})")
    print(f"  Pass yds/team:    {sim_pass:.1f}  (actual: 221.0)")
    print(f"  Rush yds/team:    {sim_rush:.1f}  (actual: 118.2)")
    print(f"  4th-down go rate: {go_rate:.3f}  (actual: 0.198)")
    print(f"  FG att/game:      {fg_pg:.2f}  (actual: 3.92)")
    print(f"\n  Penalties/game:   {pen_pg:.2f}  (actual: 8.96)")
    print(f"  Off pen/game:     {off_pen_pg:.2f}  (actual: 5.51)")
    print(f"  Def pen/game:     {def_pen_pg:.2f}  (actual: 3.45)")
    print(f"  Off pen yds/game: {off_pen_yds_pg:.1f}  (actual: 50.2)")
    print(f"  Def pen yds/game: {def_pen_yds_pg:.1f}  (actual: 47.9)")
    print(f"  Net pen yds/game: {(def_pen_yds_pg-off_pen_yds_pg):.1f}  (actual: -2.3)")
    print(f"\n  FD total/game:    {fd_total:.1f}  (actual: 39.1)")
    print(f"  FD rush/game:     {fd_rush_pg:.1f}  (actual: 13.3)")
    print(f"  FD pass/game:     {fd_pass_pg:.1f}  (actual: 22.7)")
    print(f"  FD penalty/game:  {fd_pen_pg:.2f}  (actual: 3.45)")
    print(f"\n  Safeties/game:    {safety_pg:.4f}  (actual: 0.0488)")

    print(f"\n  P(|margin|=k):")
    print(f"  {'k':>3s}  {'Sim':>7s}  {'Actual':>7s}")
    for k in range(1, 15):
        sp, ap = margin_probs[k]
        print(f"  {k:3d}  {sp:7.4f}  {ap:7.4f}")

    # By season
    if "season" in sims.columns:
        print(f"\n  By Season:")
        for s in [2021, 2022, 2023, 2024]:
            ss = sims[sims["season"] == s]
            sa = actuals[actuals["season"] == s]
            sp = (ss["home_score"].mean() + ss["away_score"].mean()) / 2
            ap = (sa["home_score"].mean() + sa["away_score"].mean()) / 2
            print(f"  {s}: sim={sp:.1f} actual={ap:.1f}")

    return {
        "pts_team": sim_pts,
        "plays": sim_plays,
        "drives": sim_drives,
        "pass_yds": sim_pass,
        "rush_yds": sim_rush,
        "go_rate": go_rate,
        "fg_pg": fg_pg,
        "pen_pg": pen_pg,
        "off_pen_pg": off_pen_pg,
        "def_pen_pg": def_pen_pg,
        "fd_total": fd_total,
        "fd_pen_pg": fd_pen_pg,
        "safety_pg": safety_pg,
        "margin_probs": margin_probs,
    }


def main():
    actuals = load_actuals()
    print(f"Actuals: {len(actuals)} games")

    before_path = OUT_DIR / "k1_5a4_before.parquet"
    after_path = OUT_DIR / "k1_5a4_after.parquet"

    if before_path.exists():
        before = pd.read_parquet(before_path)
        b = report("BEFORE (pre-5A-4 penalty model)", before, actuals)
    else:
        print("Before file not found")
        b = None

    if after_path.exists():
        after = pd.read_parquet(after_path)
        a = report("AFTER (5A-4 penalty + safety fixes)", after, actuals)
    else:
        print("After file not found yet")
        a = None

    if b and a:
        print(f"\n{'='*60}")
        print(f"  COMPARISON")
        print(f"{'='*60}")
        print(f"  {'Metric':25s} {'Before':>8s} {'After':>8s} {'Actual':>8s} {'Delta':>8s}")
        for metric in ["pts_team", "plays", "drives", "pass_yds", "rush_yds",
                        "go_rate", "fg_pg", "pen_pg", "off_pen_pg", "def_pen_pg",
                        "fd_total", "fd_pen_pg", "safety_pg"]:
            bv = b[metric]
            av = a[metric]
            actual_vals = {
                "pts_team": 22.4, "plays": 124.5, "drives": 21.9,
                "pass_yds": 221.0, "rush_yds": 118.2, "go_rate": 0.198,
                "fg_pg": 3.92, "pen_pg": 8.96, "off_pen_pg": 5.51,
                "def_pen_pg": 3.45, "fd_total": 39.1, "fd_pen_pg": 3.45,
                "safety_pg": 0.049,
            }
            act = actual_vals.get(metric, 0)
            fmt = ".3f" if metric in ("go_rate", "safety_pg") else ".1f" if metric == "pts_team" else ".2f"
            print(f"  {metric:25s} {bv:{fmt}} {av:{fmt}} {act:{fmt}} {av-bv:+{fmt}}")


if __name__ == "__main__":
    main()
