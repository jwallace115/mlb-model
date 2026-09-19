#!/usr/bin/env python3
"""
Derive engine test target statistics from play-by-play data (2021-2024).

Used by D86 to verify whether the hardcoded actuals in test_engine_5a3.py,
test_engine_5a4.py, and test_engine_5a9.py match the current fit window.

Run: python3 nfl/sim/tests/derive_engine_targets.py
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"

SEASONS = [2021, 2022, 2023, 2024]


def load_pbp(seasons):
    frames = []
    for s in seasons:
        path = PBP_DIR / f"pbp_{s}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def derive_fourth_down_go_rate(pbp):
    """4th-down go rate: fraction of 4th-down decisions that are 'go' (run or pass)
    vs punt or FG attempt."""
    # Filter to 4th down plays (regular season only, weeks 1-18)
    fourth = pbp[(pbp["down"] == 4) & (pbp["week"] <= 18)].copy()

    # Exclude special teams plays that aren't decisions: kickoffs, etc.
    # A 4th-down "decision" is: run, pass, punt, or field_goal
    decision_types = {"run", "pass", "punt", "field_goal"}
    decisions = fourth[fourth["play_type"].isin(decision_types)]

    go_types = {"run", "pass"}
    n_go = decisions[decisions["play_type"].isin(go_types)].shape[0]
    n_total = decisions.shape[0]

    go_rate = n_go / n_total if n_total > 0 else 0.0
    return go_rate, n_go, n_total


def derive_offense_penalties_per_game(pbp):
    """Offense no-play penalties per game.

    The 5A-4 test comment says: 5993/1087 = 5.51.
    No-play penalties: penalty == 1 AND play_type == 'no_play'.
    Offense penalties: penalty_team == posteam (the team that committed the
    penalty is the team on offense).
    """
    reg = pbp[pbp["week"] <= 18].copy()

    # Count games
    n_games = reg["game_id"].nunique()

    # No-play penalties where the penalty team is the offense
    no_play = reg[(reg["play_type"] == "no_play") & (reg["penalty"] == 1)]
    off_pen = no_play[no_play["penalty_team"] == no_play["posteam"]]
    n_off_pen = len(off_pen)

    off_per_game = n_off_pen / n_games if n_games > 0 else 0.0
    return off_per_game, n_off_pen, n_games


def derive_tied_drive_expiry(pbp):
    """Fraction of tied drives that reach the opponent's 35 and expire without
    a kick (end_of_game or end_of_half result).

    This measures whether the sim correctly models the FG-setup situation for
    tied games in the 4th quarter.

    Definition: drives starting in Q4 with score_differential == 0, that at
    some point reach yardline_100 <= 35 (opponent's 35), where the drive result
    is not a score or kick.
    """
    reg = pbp[pbp["week"] <= 18].copy()

    # Need drive-level data. Group by game_id and drive
    # A drive reaches the 35 if any play has yardline_100 <= 35
    # The drive expires if the last play is end_of_game or end_of_half
    # without a scoring event

    q4 = reg[reg["qtr"] == 4].copy()
    tied = q4[q4["score_differential"] == 0].copy()

    if tied.empty:
        return 0.0, 0, 0

    # Group by game_id, drive
    drives = []
    for (gid, drv), grp in tied.groupby(["game_id", "drive"]):
        reached_35 = (grp["yardline_100"] <= 35).any()
        if not reached_35:
            continue

        # Check drive result: last play
        last_play = grp.iloc[-1]
        # "Expired" = game ended without a kick or score from inside the 35
        # We look at the drive's fixed_drive_result if available
        drive_result = last_play.get("fixed_drive_result", last_play.get("drive_result", ""))
        is_expired = drive_result in ("End of Half", "End of Game")
        # But also check if there was a TD or FG on the drive
        had_td = (grp["touchdown"] == 1).any() if "touchdown" in grp.columns else False
        had_fg = (grp["play_type"] == "field_goal").any()
        if had_td or had_fg:
            is_expired = False

        drives.append({
            "game_id": gid,
            "drive": drv,
            "reached_35": True,
            "expired": is_expired,
        })

    if not drives:
        return 0.0, 0, 0

    drive_df = pd.DataFrame(drives)
    n_reached = len(drive_df)
    n_expired = drive_df["expired"].sum()
    rate = n_expired / n_reached if n_reached > 0 else 0.0
    return rate, int(n_expired), n_reached


def main():
    print(f"Loading PBP for seasons {SEASONS}...")
    pbp = load_pbp(SEASONS)
    print(f"Loaded {len(pbp)} plays from {pbp['game_id'].nunique()} games")
    print()

    # 1. 4th-down go rate
    go_rate, n_go, n_total = derive_fourth_down_go_rate(pbp)
    print(f"=== 4TH-DOWN GO RATE ===")
    print(f"  Go attempts: {n_go}")
    print(f"  Total 4th-down decisions: {n_total}")
    print(f"  Go rate: {go_rate:.4f}")
    print(f"  Hardcoded in test_engine_5a3.py: 0.198")
    print(f"  Delta: {go_rate - 0.198:+.4f}")
    print()

    # 2. Offense penalties per game
    off_pg, n_off, n_games = derive_offense_penalties_per_game(pbp)
    print(f"=== OFFENSE PENALTIES PER GAME ===")
    print(f"  Offense no-play penalties: {n_off}")
    print(f"  Games: {n_games}")
    print(f"  Per game: {off_pg:.3f}")
    print(f"  Hardcoded in test_engine_5a4.py: 5.51 (from 5993/1087)")
    print(f"  Delta: {off_pg - 5.51:+.3f}")
    print()

    # 3. Tied drives reaching 35 that expire
    expire_rate, n_expired, n_reached = derive_tied_drive_expiry(pbp)
    print(f"=== TIED DRIVES REACHING 35 THAT EXPIRE ===")
    print(f"  Tied Q4 drives reaching opp 35: {n_reached}")
    print(f"  Expired without kick: {n_expired}")
    print(f"  Rate: {expire_rate:.4f}")
    print(f"  Hardcoded in test_engine_5a9.py: 0.0 (ACT_TIED_REACHED_EXPIRE)")
    print(f"  Note: test asserts sim <= {expire_rate} + 0.05 = {expire_rate + 0.05:.4f}")
    print()


if __name__ == "__main__":
    main()
