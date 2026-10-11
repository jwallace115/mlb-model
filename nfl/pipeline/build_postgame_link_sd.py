#!/usr/bin/env python3
"""
Compute per-link standard deviations from the 2025 regular season.

Output: nfl/data/postgame/link_sd_2025.json
{
  "plays": {"sd": X, "n": N, "level": "team"},
  "pass_rate": {"sd": X, "n": N, "level": "team"},
  "share": {"sd": X, "n": N, "level": "player"},
  ...
  "margin_vs_spread": {"sd": X, "n": N},
  "total_vs_line": {"sd": X, "n": N}
}

Also computes game-level SDs for margin−close and total−close from
nflverse schedules spread_line / total_line.

PM-1 Item 2, P49. Generator committed; input sha + n per link printed.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
POSTGAME_DIR = Path(os.environ.get("POSTGAME_OUT_DIR") or (ROOT / "nfl" / "data" / "postgame"))


def build_link_sd():
    """Compute link SDs from 2025 nflverse data. Returns dict + input sha."""
    import nflreadpy

    # Load 2025 PBP
    pbp_raw = nflreadpy.load_pbp([2025])
    if hasattr(pbp_raw, "to_pandas"):
        pbp_raw = pbp_raw.to_pandas()

    # Only regular season, completed games
    pbp = pbp_raw[pbp_raw["season_type"] == "REG"].copy()
    pbp_sha = hashlib.sha256(pd.util.hash_pandas_object(pbp).values.tobytes()).hexdigest()[:12]

    # Load schedules for spread/total lines
    sched_raw = nflreadpy.load_schedules([2025])
    if hasattr(sched_raw, "to_pandas"):
        sched_raw = sched_raw.to_pandas()
    sched = sched_raw[sched_raw["game_type"] == "REG"].copy()

    result = {}

    # ── Team-level stats per game ──
    team_games = []
    for gid, g in pbp.groupby("game_id"):
        for team in (g["home_team"].iloc[0], g["away_team"].iloc[0]):
            tp = g[g["posteam"] == team]
            real = tp[tp["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])]
            n_plays = len(real)
            dropbacks = int(tp["pass_attempt"].sum())
            rush_att = int(tp["rush_attempt"].sum())
            pr = dropbacks / n_plays if n_plays else 0
            team_games.append({
                "game_id": gid, "team": team,
                "plays": n_plays, "pass_rate": pr, "run_rate": 1 - pr,
                "dropbacks": dropbacks, "rush_attempts": rush_att,
            })
    tdf = pd.DataFrame(team_games)

    for col in ("plays", "pass_rate", "run_rate"):
        result[col] = {"sd": round(float(tdf[col].std()), 4),
                        "n": len(tdf), "level": "team"}

    # ── Player-level stats per game ──
    # Receiver share & catch rate
    rec_plays = pbp[pbp["receiver_player_id"].notna()].copy()
    # Merge team dropbacks
    rec_plays = rec_plays.merge(tdf[["game_id", "team", "dropbacks"]],
                                 left_on=["game_id", "posteam"],
                                 right_on=["game_id", "team"], how="left")
    player_game_rec = rec_plays.groupby(["game_id", "receiver_player_id", "posteam"]).agg(
        targets=("receiver_player_id", "count"),
        receptions=("complete_pass", "sum"),
        rec_yards=("receiving_yards", "sum"),
        dropbacks=("dropbacks", "first"),
    ).reset_index()
    player_game_rec["share"] = player_game_rec["targets"] / player_game_rec["dropbacks"]
    player_game_rec["catch_rate"] = player_game_rec["receptions"] / player_game_rec["targets"]
    player_game_rec["yards_per_target"] = player_game_rec["rec_yards"] / player_game_rec["targets"]
    player_game_rec = player_game_rec.replace([np.inf, -np.inf], np.nan)

    for col, name in [("share", "share"), ("catch_rate", "catch_rate"),
                       ("yards_per_target", "yards_per_target")]:
        valid = player_game_rec[col].dropna()
        result[name] = {"sd": round(float(valid.std()), 4),
                         "n": len(valid), "level": "player"}

    # Rush share & yards per carry
    rush_plays = pbp[(pbp["rusher_player_id"].notna()) & (pbp["rush_attempt"] == 1)].copy()
    rush_plays = rush_plays.merge(tdf[["game_id", "team", "rush_attempts"]],
                                   left_on=["game_id", "posteam"],
                                   right_on=["game_id", "team"], how="left")
    player_game_rush = rush_plays.groupby(["game_id", "rusher_player_id", "posteam"]).agg(
        carries=("rusher_player_id", "count"),
        rush_yards=("rushing_yards", "sum"),
        team_rush=("rush_attempts", "first"),
    ).reset_index()
    player_game_rush["carry_share"] = player_game_rush["carries"] / player_game_rush["team_rush"]
    player_game_rush["yards_per_carry"] = player_game_rush["rush_yards"] / player_game_rush["carries"]
    player_game_rush = player_game_rush.replace([np.inf, -np.inf], np.nan)

    for col, name in [("carry_share", "carry_share"), ("yards_per_carry", "yards_per_carry")]:
        valid = player_game_rush[col].dropna()
        result[name] = {"sd": round(float(valid.std()), 4),
                         "n": len(valid), "level": "player"}

    # QB share, completion rate, yards per attempt
    pass_plays = pbp[(pbp["passer_player_id"].notna()) & (pbp["pass_attempt"] == 1)].copy()
    pass_plays = pass_plays.merge(tdf[["game_id", "team", "dropbacks"]],
                                   left_on=["game_id", "posteam"],
                                   right_on=["game_id", "team"], how="left")
    player_game_pass = pass_plays.groupby(["game_id", "passer_player_id", "posteam"]).agg(
        att=("passer_player_id", "count"),
        cmp=("complete_pass", "sum"),
        pass_yards=("passing_yards", "sum"),
        team_db=("dropbacks", "first"),
    ).reset_index()
    player_game_pass["qb_share"] = player_game_pass["att"] / player_game_pass["team_db"]
    player_game_pass["completion_rate"] = player_game_pass["cmp"] / player_game_pass["att"]
    player_game_pass["yards_per_attempt"] = player_game_pass["pass_yards"] / player_game_pass["att"]
    player_game_pass = player_game_pass.replace([np.inf, -np.inf], np.nan)

    for col, name in [("qb_share", "qb_share"), ("completion_rate", "completion_rate"),
                       ("yards_per_attempt", "yards_per_attempt")]:
        valid = player_game_pass[col].dropna()
        result[name] = {"sd": round(float(valid.std()), 4),
                         "n": len(valid), "level": "player"}

    # ── Game-level: margin vs spread, total vs total_line ──
    completed = sched[sched["home_score"].notna()].copy()
    completed["margin"] = completed["home_score"] - completed["away_score"]
    completed["total"] = completed["home_score"] + completed["away_score"]

    if "spread_line" in completed.columns:
        valid = completed[completed["spread_line"].notna()]
        margin_diff = valid["margin"] + valid["spread_line"]  # spread_line is from home perspective
        result["margin_vs_spread"] = {
            "sd": round(float(margin_diff.std()), 4),
            "n": len(valid),
        }

    if "total_line" in completed.columns:
        valid = completed[completed["total_line"].notna()]
        total_diff = valid["total"] - valid["total_line"]
        result["total_vs_line"] = {
            "sd": round(float(total_diff.std()), 4),
            "n": len(valid),
        }

    return result, pbp_sha


def main():
    result, pbp_sha = build_link_sd()
    POSTGAME_DIR.mkdir(parents=True, exist_ok=True)
    out = POSTGAME_DIR / "link_sd_2025.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {out}")
    print(f"Input PBP sha: {pbp_sha}")
    for k, v in result.items():
        n = v.get("n", "?")
        sd = v.get("sd", "?")
        level = v.get("level", "game")
        print(f"  {k}: sd={sd}, n={n}, level={level}")


if __name__ == "__main__":
    main()
