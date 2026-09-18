#!/usr/bin/env python3
"""
NFL Sim — Actual player-game stats from PBP.

Single source of truth for grading, calibration scoring, and backtest.
All call sites (grade_week, calibration, run_cal_players) import from here.
"""

import numpy as np
import pandas as pd


def actual_player_game_stats(game_pbp):
    """Compute actual player-game stats from PBP for a single game.

    Uses td_player_id (nflfastR canonical scorer) for anytime TD,
    NOT rusher/receiver on TD plays (which misses return TDs and
    mis-attributes some scoring plays).

    Returns:
      rec_stats:  DataFrame(player_id, actual_rec, actual_rec_yds)
      rush_stats: DataFrame(player_id, actual_rush_yds, actual_carries)
      td_stats:   DataFrame(player_id, actual_atd)  -- 1 if scored any TD
      pass_stats: DataFrame(player_id, actual_completions, actual_pass_att,
                            actual_pass_yds, actual_pass_td)
    """
    # --- Receiving ---
    passes = game_pbp[
        (game_pbp["play_type"] == "pass")
        & game_pbp["down"].notna()
        & (game_pbp.get("sack", pd.Series(0, index=game_pbp.index)) != 1)
    ]
    rec_rows = passes[passes["receiver_player_id"].notna()]
    if len(rec_rows) > 0:
        completions = rec_rows[rec_rows["complete_pass"] == 1]
        rec_stats = rec_rows.groupby("receiver_player_id").agg(
            actual_rec=("complete_pass", "sum"),
        ).reset_index().rename(columns={"receiver_player_id": "player_id"})
        # Receiving yards: sum yards_gained on completed passes only
        if len(completions) > 0:
            rec_yds = completions.groupby("receiver_player_id")["yards_gained"].sum(
            ).reset_index().rename(
                columns={"receiver_player_id": "player_id", "yards_gained": "actual_rec_yds"})
            rec_stats = rec_stats.merge(rec_yds, on="player_id", how="left")
            rec_stats["actual_rec_yds"] = rec_stats["actual_rec_yds"].fillna(0).astype(int)
        else:
            rec_stats["actual_rec_yds"] = 0
    else:
        rec_stats = pd.DataFrame(columns=["player_id", "actual_rec", "actual_rec_yds"])

    # --- Rushing (D62: official definitions) ---
    # Attempt universe: play_type in {run, qb_kneel}, rusher_player_id not null,
    # two_point_attempt != 1. Kneels carry negative yardage — keep it.
    _two_pt = game_pbp.get("two_point_attempt", pd.Series(0, index=game_pbp.index))
    rushes = game_pbp[
        game_pbp["play_type"].isin({"run", "qb_kneel"})
        & game_pbp["rusher_player_id"].notna()
        & (_two_pt != 1)
    ]
    if len(rushes) > 0:
        rush_stats = rushes.groupby("rusher_player_id").agg(
            actual_rush_yds=("yards_gained", "sum"),
            actual_carries=("play_id", "count"),
        ).reset_index().rename(columns={"rusher_player_id": "player_id"})
    else:
        rush_stats = pd.DataFrame(columns=["player_id", "actual_rush_yds", "actual_carries"])

    # --- Anytime TD (from td_player_id) ---
    if "td_player_id" in game_pbp.columns:
        td_pids = game_pbp[game_pbp["td_player_id"].notna()]["td_player_id"].unique()
    else:
        # Fallback for PBP without td_player_id
        td_pids = set()
        td_plays = game_pbp[game_pbp.get("touchdown", pd.Series(0, index=game_pbp.index)) == 1]
        for col in ["rusher_player_id", "receiver_player_id"]:
            if col in td_plays.columns:
                td_pids.update(td_plays[col].dropna().unique())
        td_pids = list(td_pids)

    td_stats = pd.DataFrame({
        "player_id": list(td_pids),
        "actual_atd": 1,
    }) if len(td_pids) > 0 else pd.DataFrame(columns=["player_id", "actual_atd"])

    # --- Passing (D62: official definitions) ---
    # Attempt universe: play_type in {pass, qb_spike}, down not null (excludes
    # two-point), sack != 1, passer_player_id not null.
    # Spikes are attempts with 0 yards and no completion.
    pass_universe = game_pbp[
        game_pbp["play_type"].isin({"pass", "qb_spike"})
        & game_pbp["down"].notna()
        & (game_pbp.get("sack", pd.Series(0, index=game_pbp.index)) != 1)
    ]
    if len(pass_universe) > 0 and "passer_player_id" in pass_universe.columns:
        passer_passes = pass_universe[pass_universe["passer_player_id"].notna()]
        if len(passer_passes) > 0:
            pass_stats = passer_passes.groupby("passer_player_id").agg(
                actual_completions=("complete_pass", "sum"),
                actual_pass_att=("play_id", "count"),
                actual_pass_yds=("yards_gained", "sum"),
            ).reset_index().rename(columns={"passer_player_id": "player_id"})
            # Passing TDs
            pass_tds = passer_passes[passer_passes.get("pass_touchdown",
                        pd.Series(0, index=passer_passes.index)) == 1]
            if len(pass_tds) > 0:
                ptd = pass_tds.groupby("passer_player_id").size().reset_index(
                    name="actual_pass_td").rename(columns={"passer_player_id": "player_id"})
                pass_stats = pass_stats.merge(ptd, on="player_id", how="left")
                pass_stats["actual_pass_td"] = pass_stats["actual_pass_td"].fillna(0).astype(int)
            else:
                pass_stats["actual_pass_td"] = 0
        else:
            pass_stats = pd.DataFrame(columns=[
                "player_id", "actual_completions", "actual_pass_att",
                "actual_pass_yds", "actual_pass_td"])
    else:
        pass_stats = pd.DataFrame(columns=[
            "player_id", "actual_completions", "actual_pass_att",
            "actual_pass_yds", "actual_pass_td"])

    return rec_stats, rush_stats, td_stats, pass_stats
