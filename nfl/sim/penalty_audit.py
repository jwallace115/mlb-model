#!/usr/bin/env python3
"""
Phase 5A-4 STEP 1 + STEP 2: Penalty & First-Down Audit
Actual penalty/first-down tables from 2021-2024 PBP, then sim counterpart.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]


def load_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["week"] <= 18].copy()
    return df


def count_games(df):
    return df["game_id"].nunique()


def step1(df):
    """Actual penalty and first-down tables from PBP."""
    n_games = count_games(df)
    n_team_games = n_games * 2  # each game has 2 teams
    print(f"\n{'='*70}")
    print(f"STEP 1: ACTUAL PENALTY & FIRST-DOWN TABLE (2021-2024)")
    print(f"Games: {n_games}, Team-games: {n_team_games}")
    print(f"{'='*70}")

    # --- 1a. Accepted penalties per game by side and type ---
    # "penalty" == 1 means a penalty occurred and was accepted on this play
    # penalty_team tells us which team committed it
    # posteam tells us the offensive team
    pen = df[df["penalty"] == 1].copy()

    # Classify by side
    pen["side"] = np.where(
        pen["penalty_team"] == pen["posteam"], "offense", "defense"
    )
    # Some penalty_team might not match either team (special teams, etc.)
    pen = pen[pen["side"].isin(["offense", "defense"])].copy()

    pen_per_game = len(pen) / n_games
    off_pen = pen[pen["side"] == "offense"]
    def_pen = pen[pen["side"] == "defense"]

    print(f"\n--- 1a. Accepted penalties per game ---")
    print(f"Total accepted penalties/game: {pen_per_game:.2f}")
    print(f"  Offense penalties/game: {len(off_pen)/n_games:.2f}")
    print(f"  Defense penalties/game: {len(def_pen)/n_games:.2f}")
    print(f"  Offense fraction: {len(off_pen)/len(pen):.3f}")

    # Top 10 penalty types
    print(f"\n--- Top 10 penalty types ---")
    type_col = "penalty_type" if "penalty_type" in pen.columns else None
    if type_col is None:
        print("  (penalty_type column not found, using penalty_name or desc)")
        for c in ["penalty_name", "desc", "penalty"]:
            if c in pen.columns and pen[c].dtype == object:
                type_col = c
                break

    if type_col:
        top_types = pen.groupby([type_col, "side"]).agg(
            count=("penalty_yards", "size"),
            mean_yds=("penalty_yards", "mean"),
            auto_first=("first_down_penalty", "mean"),
        ).reset_index()
        top_types["per_game"] = top_types["count"] / n_games
        top_types = top_types.sort_values("count", ascending=False)
        print(top_types.head(20).to_string(index=False))
    else:
        print("  No penalty type column found")

    # Penalty yards by side
    print(f"\n  Offense penalty mean yards: {off_pen['penalty_yards'].mean():.1f}")
    print(f"  Defense penalty mean yards: {def_pen['penalty_yards'].mean():.1f}")

    # --- 1b. First downs per team per game ---
    print(f"\n--- 1b. First downs per team per game ---")
    # Use scrimmage plays (pass, run) + no_play (penalty replays)
    # first_down == 1: a first down was achieved on this play
    # first_down_penalty == 1: the first down came via penalty
    # first_down_rush == 1: first down via rush
    # first_down_pass == 1: first down via pass
    scrim_plus_nop = df[df["play_type"].isin(["pass", "run", "no_play"])].copy()

    total_fd = scrim_plus_nop["first_down"].sum()
    fd_rush = scrim_plus_nop["first_down_rush"].sum() if "first_down_rush" in scrim_plus_nop.columns else 0
    fd_pass = scrim_plus_nop["first_down_pass"].sum() if "first_down_pass" in scrim_plus_nop.columns else 0
    fd_penalty = scrim_plus_nop["first_down_penalty"].sum() if "first_down_penalty" in scrim_plus_nop.columns else 0

    print(f"  Total first downs/team/game: {total_fd/n_team_games:.2f}")
    print(f"  By rush: {fd_rush/n_team_games:.2f}")
    print(f"  By pass: {fd_pass/n_team_games:.2f}")
    print(f"  By penalty: {fd_penalty/n_team_games:.2f}")
    print(f"  Sum of types: {(fd_rush+fd_pass+fd_penalty)/n_team_games:.2f}")

    # By season
    print(f"\n  By season:")
    for s in SEASONS:
        sg = scrim_plus_nop[scrim_plus_nop["season"] == s]
        ng = df[df["season"] == s]["game_id"].nunique()
        ntg = ng * 2
        fd_s = sg["first_down"].sum()
        fd_r = sg["first_down_rush"].sum() if "first_down_rush" in sg.columns else 0
        fd_p = sg["first_down_pass"].sum() if "first_down_pass" in sg.columns else 0
        fd_pen = sg["first_down_penalty"].sum() if "first_down_penalty" in sg.columns else 0
        print(f"  {s}: total={fd_s/ntg:.2f}  rush={fd_r/ntg:.2f}  pass={fd_p/ntg:.2f}  penalty={fd_pen/ntg:.2f}  games={ng}")

    # --- 1c. 3rd/4th-down penalty first downs ---
    print(f"\n--- 1c. Penalty first downs on 3rd/4th down ---")
    third_plays = scrim_plus_nop[scrim_plus_nop["down"] == 3]
    third_fd = third_plays[third_plays["first_down"] == 1]
    third_fd_pen = third_plays[third_plays["first_down_penalty"] == 1]
    print(f"  3rd-down plays: {len(third_plays)}")
    print(f"  3rd-down first downs: {len(third_fd)} ({len(third_fd)/len(third_plays)*100:.1f}%)")
    print(f"  3rd-down FDs by penalty: {len(third_fd_pen)} ({len(third_fd_pen)/len(third_fd)*100:.1f}% of 3rd-down FDs)")

    fourth_plays = scrim_plus_nop[scrim_plus_nop["down"] == 4]
    fourth_fd = fourth_plays[fourth_plays["first_down"] == 1]
    fourth_fd_pen = fourth_plays[fourth_plays["first_down_penalty"] == 1]
    print(f"  4th-down plays: {len(fourth_plays)}")
    print(f"  4th-down first downs: {len(fourth_fd)}")
    print(f"  4th-down FDs by penalty: {len(fourth_fd_pen)} ({len(fourth_fd_pen)/max(len(fourth_fd),1)*100:.1f}% of 4th-down FDs)")

    # --- 1d. Net penalty yards per team per game ---
    print(f"\n--- 1d. Net penalty yards per team per game ---")
    # Defensive penalty yards help the offense, offensive penalty yards hurt
    off_pen_yds = off_pen["penalty_yards"].sum()
    def_pen_yds = def_pen["penalty_yards"].sum()
    net_pen_yds = def_pen_yds - off_pen_yds  # positive = net benefit to offense
    print(f"  Offensive penalty yards total: {off_pen_yds:.0f}")
    print(f"  Defensive penalty yards total: {def_pen_yds:.0f}")
    print(f"  Net penalty yards (def - off) per team per game: {net_pen_yds/n_team_games:.1f}")
    print(f"  Def penalty yards per team per game: {def_pen_yds/n_team_games:.1f}")
    print(f"  Off penalty yards per team per game: {off_pen_yds/n_team_games:.1f}")

    # By season
    for s in SEASONS:
        spen = pen[pen["season"] == s]
        ng = df[df["season"] == s]["game_id"].nunique()
        ntg = ng * 2
        s_off = spen[spen["side"] == "offense"]["penalty_yards"].sum()
        s_def = spen[spen["side"] == "defense"]["penalty_yards"].sum()
        print(f"  {s}: off={s_off/ntg:.1f} def={s_def/ntg:.1f} net={(s_def-s_off)/ntg:.1f}")

    # --- 1e. Safeties ---
    print(f"\n--- 1e. Safeties ---")
    safeties = df[df["safety"] == 1]
    print(f"  Total safeties: {len(safeties)}")
    print(f"  Safeties per game: {len(safeties)/n_games:.4f}")
    print(f"  Safeties per team per game: {len(safeties)/n_team_games:.4f}")
    if len(safeties) > 0:
        print(f"\n  Safety situations:")
        print(f"  Play types: {safeties['play_type'].value_counts().to_dict()}")
        print(f"  Mean yardline_100: {safeties['yardline_100'].mean():.1f}")
        print(f"  Yardline distribution:")
        for yl_lo, yl_hi in [(96, 100), (91, 95), (86, 90), (80, 85)]:
            ct = len(safeties[(safeties["yardline_100"] >= yl_lo) & (safeties["yardline_100"] <= yl_hi)])
            print(f"    yl100 {yl_lo}-{yl_hi}: {ct}")
        if "down" in safeties.columns:
            print(f"  Down distribution: {safeties['down'].value_counts().sort_index().to_dict()}")

    # Return key metrics for sim comparison
    return {
        "n_games": n_games,
        "n_team_games": n_team_games,
        "pen_per_game": pen_per_game,
        "off_pen_per_game": len(off_pen) / n_games,
        "def_pen_per_game": len(def_pen) / n_games,
        "off_pen_yds_mean": off_pen["penalty_yards"].mean(),
        "def_pen_yds_mean": def_pen["penalty_yards"].mean(),
        "off_pen_yds_per_tg": off_pen_yds / n_team_games,
        "def_pen_yds_per_tg": def_pen_yds / n_team_games,
        "net_pen_yds_per_tg": net_pen_yds / n_team_games,
        "fd_total_per_tg": total_fd / n_team_games,
        "fd_rush_per_tg": fd_rush / n_team_games,
        "fd_pass_per_tg": fd_pass / n_team_games,
        "fd_penalty_per_tg": fd_penalty / n_team_games,
        "safety_per_game": len(safeties) / n_games,
        "safety_per_tg": len(safeties) / n_team_games,
        "p_auto_first_def": def_pen["first_down_penalty"].mean() if "first_down_penalty" in def_pen.columns else 0.5,
        "third_fd_by_pen_share": len(third_fd_pen) / max(len(third_fd), 1),
    }


if __name__ == "__main__":
    print("Loading PBP data...")
    df = load_pbp()
    print(f"Loaded {len(df):,} plays")

    actual = step1(df)

    print(f"\n\n{'='*70}")
    print("KEY METRICS FOR SIM COMPARISON")
    print(f"{'='*70}")
    for k, v in actual.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
