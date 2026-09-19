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

    # D94: scrimmage snaps only. Kickoff rows carry yardline_100 == 35 and belong to the
    # receiving team's drive, so without this every tied Q4 drive that began with a
    # kickoff "reached the 35" (329 drives instead of 181).
    reg = reg[reg["down"].notna()]
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
        # D94: nflverse's label is "End of half" (lower-case h; it covers end of game too).
        # The original compared against "End of Half"/"End of Game", which never match, so
        # the numerator was 0 by construction.
        is_expired = drive_result == "End of half"
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


def derive_tied_drive_expiry_matched(pbp):
    """D94: the real-side number under the SAME definition the sim test uses
    (test_engine_5a9.py::test_t3_tied_drives_that_reach_range_get_the_kick_off):
    drive STARTS in Q4 with <= 300 s left, offence tied at the first snap; "reached" =
    a snap at/inside the 35 (strict), or additionally a play that ENDS at/inside the 35 or
    a TD (broad — this is what `start_yardline - yards <= 35 | TD | end_yardline <= 35`
    measures on the sim side). Expired = fixed_drive_result == "End of half".
    Returns dict with strict/broad counts and the broad expired game_ids."""
    reg = pbp[(pbp["week"] <= 18) & pbp["drive"].notna() & pbp["posteam"].notna()]
    scr = reg[reg["down"].notna()].sort_values(["game_id", "play_id"]).copy()
    scr["yl_after"] = scr["yardline_100"] - scr["yards_gained"].fillna(0)
    g = scr.groupby(["game_id", "drive"])
    d = pd.DataFrame({"q": g["qtr"].first(), "clk": g["half_seconds_remaining"].first(),
                      "sd": g["score_differential"].first(), "min_yl": g["yardline_100"].min(),
                      "min_after": g["yl_after"].min(), "res": g["fixed_drive_result"].last(),
                      "td": g["touchdown"].max()}).reset_index()
    x = d[(d["q"] == 4) & (d["clk"] <= 300) & (d["sd"] == 0)]
    strict = x[x["min_yl"] <= 35]
    broad = x[(x["min_yl"] <= 35) | (x["min_after"] <= 35) | (x["td"] == 1)]
    be = broad[broad["res"] == "End of half"]
    return {"n_tied_late": len(x),
            "strict_reached": len(strict), "strict_expired": int((strict["res"] == "End of half").sum()),
            "broad_reached": len(broad), "broad_expired": len(be),
            "broad_expired_games": be["game_id"].tolist()}


def derive_go_rate_breakdown(pbp):
    """D94: go rate by season, and in the 50 games test_engine_5a3's k1_sample draws."""
    out = {}
    dec = pbp[(pbp["down"] == 4) & (pbp["week"] <= 18) &
              pbp["play_type"].isin(["run", "pass", "punt", "field_goal"])]
    for s, grp in dec.groupby("season"):
        out[int(s)] = (float(grp["play_type"].isin(["run", "pass"]).mean()), len(grp))
    g23 = pd.read_parquet(PBP_DIR / "pbp_2023.parquet",
                          columns=["game_id", "season", "week", "home_team", "away_team",
                                   "home_score", "away_score"]).drop_duplicates("game_id").query("week <= 18")
    rng = np.random.default_rng(42)
    samp = g23.iloc[rng.choice(len(g23), 50, replace=False)]["game_id"]
    ds = dec[dec["game_id"].isin(samp)]
    out["sample50_2023"] = (float(ds["play_type"].isin(["run", "pass"]).mean()), len(ds))
    return out


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


def main_d94():
    pbp = load_pbp(SEASONS)
    m = derive_tied_drive_expiry_matched(pbp)
    print("=== D94: TIED-DRIVE EXPIRY, MATCHED TO THE SIM TEST'S DEFINITION ===")
    print(f"  tied drives starting Q4 <= 300 s: {m['n_tied_late']}")
    print(f"  strict (a snap at/inside the 35): {m['strict_expired']}/{m['strict_reached']}")
    print(f"  broad  (sim test's definition):   {m['broad_expired']}/{m['broad_reached']}"
          f" = {m['broad_expired']/max(m['broad_reached'],1):.4f}   games: {m['broad_expired_games']}")
    print("=== D94: GO RATE BY SEASON AND IN THE TEST'S OWN 50-GAME SAMPLE ===")
    for k, (r, n) in derive_go_rate_breakdown(pbp).items():
        print(f"  {k}: {r:.4f}  (n={n}, binomial SE {np.sqrt(r*(1-r)/n):.4f})")


if __name__ == "__main__":
    main()
    main_d94()
