#!/usr/bin/env python3
"""
Phase 5A-5 STEP 2+3: Non-offensive scoring audit.
Actual (PBP 2021-2024) and sim (K1) comparison.
"""
import json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]


def load_pbp():
    frames = []
    for s in SEASONS:
        frames.append(pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet"))
    df = pd.concat(frames, ignore_index=True)
    return df[df["week"] <= 18].copy()


def step2_actual(df):
    """Non-offensive scoring from PBP."""
    n_games = df["game_id"].nunique()
    n_tg = n_games * 2
    print(f"\n{'='*70}")
    print(f"STEP 2: ACTUAL NON-OFFENSIVE SCORING (2021-2024)")
    print(f"Games: {n_games}")
    print(f"{'='*70}")

    # --- Interception return TDs ---
    # return_touchdown == 1 on interception plays
    ints = df[df["interception"] == 1]
    int_ret_tds = ints[ints["return_touchdown"] == 1] if "return_touchdown" in ints.columns else pd.DataFrame()
    print(f"\nInterception return TDs: {len(int_ret_tds)}")
    print(f"  Per game: {len(int_ret_tds)/n_games:.4f}")
    print(f"  P(pick-six | INT): {len(int_ret_tds)/len(ints)*100:.2f}%")

    # INT return yards
    int_ret_yds = ints["return_yards"].fillna(0)
    print(f"  INT return yards: mean={int_ret_yds.mean():.1f} p50={int_ret_yds.median():.0f} p90={int_ret_yds.quantile(0.9):.0f}")

    # --- Fumble return TDs ---
    fums = df[df["fumble_lost"] == 1]
    fum_ret_tds = fums[fums["return_touchdown"] == 1] if "return_touchdown" in fums.columns else pd.DataFrame()
    print(f"\nFumble return TDs: {len(fum_ret_tds)}")
    print(f"  Per game: {len(fum_ret_tds)/n_games:.4f}")
    print(f"  P(scoop-six | fumble): {len(fum_ret_tds)/max(len(fums),1)*100:.2f}%")

    fum_ret_yds = fums["return_yards"].fillna(0)
    print(f"  Fumble return yards: mean={fum_ret_yds.mean():.1f} p50={fum_ret_yds.median():.0f} p90={fum_ret_yds.quantile(0.9):.0f}")

    # --- Punt return TDs ---
    punts = df[df["play_type"] == "punt"]
    punt_ret_tds = punts[punts["return_touchdown"] == 1] if "return_touchdown" in punts.columns else pd.DataFrame()
    print(f"\nPunt return TDs: {len(punt_ret_tds)}")
    print(f"  Per game: {len(punt_ret_tds)/n_games:.4f}")
    print(f"  P(ret TD | punt): {len(punt_ret_tds)/max(len(punts),1)*100:.3f}%")

    # --- Kickoff return TDs ---
    kos = df[df["play_type"] == "kickoff"]
    ko_ret_tds = kos[kos["return_touchdown"] == 1] if "return_touchdown" in kos.columns else pd.DataFrame()
    print(f"\nKickoff return TDs: {len(ko_ret_tds)}")
    print(f"  Per game: {len(ko_ret_tds)/n_games:.4f}")
    print(f"  P(ret TD | KO): {len(ko_ret_tds)/max(len(kos),1)*100:.3f}%")

    # --- Blocked kick return TDs ---
    # Blocked FG/punt are in play_type == "field_goal" or "punt" with blocked
    # nflverse doesn't have a clean "blocked" flag, approximate with
    # field_goal_result == "blocked" or punt_blocked == 1
    blocked_fg = df[df.get("field_goal_result", pd.Series(dtype=str)) == "blocked"] if "field_goal_result" in df.columns else pd.DataFrame()
    blocked_punt = df[df.get("punt_blocked", pd.Series(dtype=int)) == 1] if "punt_blocked" in df.columns else pd.DataFrame()
    blocked = pd.concat([blocked_fg, blocked_punt])
    blocked_ret_tds = blocked[blocked["return_touchdown"] == 1] if "return_touchdown" in blocked.columns and len(blocked) > 0 else pd.DataFrame()
    print(f"\nBlocked kick/punt return TDs: {len(blocked_ret_tds)}")
    print(f"  Per game: {len(blocked_ret_tds)/n_games:.4f}")
    print(f"  Blocked FGs: {len(blocked_fg)}, blocked punts: {len(blocked_punt)}")

    # --- Defensive 2-point conversions ---
    # two_point_attempt == 1 and the defense scores
    twopt = df[df["two_point_attempt"] == 1]
    # Defensive 2pt: the PAT attempt was returned by the defense for 2 points
    # nflverse: defensive_two_point_conv == 1 or two_point_conv_result == "failure" with return
    def_2pt = twopt[twopt.get("defensive_two_point_conv", pd.Series(dtype=int)) == 1] if "defensive_two_point_conv" in twopt.columns else pd.DataFrame()
    print(f"\nDefensive 2-point conversions: {len(def_2pt)}")
    print(f"  Per game: {len(def_2pt)/n_games:.4f}")

    # --- Safeties (already counted in 5A-4) ---
    safeties = df[df["safety"] == 1]
    print(f"\nSafeties: {len(safeties)}")
    print(f"  Per game: {len(safeties)/n_games:.4f}")

    # --- Total non-offensive points ---
    # Each category worth:
    # INT/fumble/punt/KO/blocked return TD: 6 pts + PAT (~0.95 XP rate) = ~6.95
    # Defensive 2pt: 2 pts
    # Safety: 2 pts
    xp_rate = 0.948
    ret_td_pts = (len(int_ret_tds) + len(fum_ret_tds) + len(punt_ret_tds) +
                  len(ko_ret_tds) + len(blocked_ret_tds)) * (6 + xp_rate)
    def_2pt_pts = len(def_2pt) * 2
    safety_pts = len(safeties) * 2
    total_nonoff_pts = ret_td_pts + def_2pt_pts + safety_pts
    print(f"\n--- Total non-offensive points ---")
    print(f"  Return TD points: {ret_td_pts:.0f} ({ret_td_pts/n_tg:.2f}/team/game)")
    print(f"  Defensive 2pt points: {def_2pt_pts:.0f} ({def_2pt_pts/n_tg:.2f}/team/game)")
    print(f"  Safety points: {safety_pts:.0f} ({safety_pts/n_tg:.2f}/team/game)")
    print(f"  TOTAL: {total_nonoff_pts:.0f} ({total_nonoff_pts/n_tg:.2f}/team/game)")

    # By season
    print(f"\n--- By season ---")
    for s in SEASONS:
        sdf = df[df["season"] == s]
        ng = sdf["game_id"].nunique()
        ntg = ng * 2
        s_int_td = len(sdf[(sdf["interception"] == 1) & (sdf["return_touchdown"] == 1)])
        s_fum_td = len(sdf[(sdf["fumble_lost"] == 1) & (sdf["return_touchdown"] == 1)])
        s_punt_td = len(sdf[(sdf["play_type"] == "punt") & (sdf["return_touchdown"] == 1)])
        s_ko_td = len(sdf[(sdf["play_type"] == "kickoff") & (sdf["return_touchdown"] == 1)])
        s_safety = sdf["safety"].sum()
        s_total_tds = s_int_td + s_fum_td + s_punt_td + s_ko_td
        s_pts = s_total_tds * (6 + xp_rate) + s_safety * 2
        print(f"  {s}: INT_TD={s_int_td} FUM_TD={s_fum_td} PUNT_TD={s_punt_td} "
              f"KO_TD={s_ko_td} SAF={int(s_safety)} total_pts/tg={s_pts/ntg:.2f} games={ng}")

    return {
        "n_games": n_games,
        "int_ret_td": len(int_ret_tds),
        "fum_ret_td": len(fum_ret_tds),
        "punt_ret_td": len(punt_ret_tds),
        "ko_ret_td": len(ko_ret_tds),
        "blocked_ret_td": len(blocked_ret_tds),
        "def_2pt": len(def_2pt),
        "safeties": len(safeties),
        "total_nonoff_pts_per_tg": total_nonoff_pts / n_tg,
        "p_pick6_given_int": len(int_ret_tds) / max(len(ints), 1),
        "p_scoop6_given_fum": len(fum_ret_tds) / max(len(fums), 1),
        "int_ret_yds_mean": float(int_ret_yds.mean()),
        "fum_ret_yds_mean": float(fum_ret_yds.mean()),
    }


if __name__ == "__main__":
    print("Loading PBP data...")
    df = load_pbp()
    print(f"Loaded {len(df):,} plays")
    actual = step2_actual(df)
