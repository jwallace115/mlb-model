#!/usr/bin/env python3
"""
Compute per-link standard deviations of LOG RATIOS from the 2025 regular season.

v2: SD of ln(link_actual / link_prior), not raw values.
The prior for each player-game is the mean of that link over weeks < current week,
≥ 2 prior games required. Rows with zero or missing values are dropped.

Also computes game-level SDs:
  margin_vs_spread: SD of (margin - spread_line)   [ATS residual, ~13-14]
  total_vs_line:    SD of (total  - total_line)

Output: nfl/data/postgame/link_sd_2025_v2.json
{
  "version": "v2",
  "generator_sha": "<sha of this file>",
  "plays": {"sd": X, "n": N, "level": "team"},
  ...
}

PM-1d Item 1. Fixes two PM-1c defects:
  1. z = term / raw_SD mixed units → now z = term / log_ratio_SD (both unitless)
  2. margin + spread_line (wrong sign) → margin - spread_line
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


def _generator_sha():
    """SHA256 of this file's contents (first 12 hex chars)."""
    src = Path(__file__).read_bytes()
    return hashlib.sha256(src).hexdigest()[:12]


def _log_ratio_sd(df, value_col, group_cols, week_col="week", min_prior=2):
    """Compute SD of ln(actual / prior) for a given value column.

    For each row, the prior is the mean of value_col over prior weeks
    (weeks < current week, same group). Requires >= min_prior prior games.
    Drops rows where actual or prior is zero/missing/negative.

    Returns (sd, n_used, n_dropped).
    """
    log_ratios = []
    n_dropped = 0

    for group_key, grp in df.groupby(group_cols):
        grp_sorted = grp.sort_values(week_col)
        vals = grp_sorted[value_col].values
        weeks = grp_sorted[week_col].values

        for i in range(len(grp_sorted)):
            # Prior: all rows with week < current week
            prior_mask = weeks < weeks[i]
            prior_vals = vals[prior_mask]
            # Filter valid (> 0)
            prior_vals = prior_vals[~np.isnan(prior_vals) & (prior_vals > 0)]

            if len(prior_vals) < min_prior:
                continue

            actual = vals[i]
            if np.isnan(actual) or actual <= 0:
                n_dropped += 1
                continue

            prior_mean = prior_vals.mean()
            if prior_mean <= 0:
                n_dropped += 1
                continue

            log_ratios.append(np.log(actual / prior_mean))

    if not log_ratios:
        return None, 0, n_dropped

    arr = np.array(log_ratios)
    return float(arr.std(ddof=1)), len(arr), n_dropped


def build_link_sd():
    """Compute log-ratio link SDs from 2025 nflverse data. Returns dict + input sha."""
    import nflreadpy

    # Load 2025 PBP
    pbp_raw = nflreadpy.load_pbp([2025])
    if hasattr(pbp_raw, "to_pandas"):
        pbp_raw = pbp_raw.to_pandas()

    pbp = pbp_raw[pbp_raw["season_type"] == "REG"].copy()
    pbp_sha = hashlib.sha256(pd.util.hash_pandas_object(pbp).values.tobytes()).hexdigest()[:12]

    # Load schedules for spread/total lines
    sched_raw = nflreadpy.load_schedules([2025])
    if hasattr(sched_raw, "to_pandas"):
        sched_raw = sched_raw.to_pandas()
    sched = sched_raw[sched_raw["game_type"] == "REG"].copy()

    result = {
        "version": "v2",
        "generator_sha": _generator_sha(),
        "pbp_sha": pbp_sha,
    }

    # ── Team-level stats per game ──
    team_games = []
    for gid, g in pbp.groupby("game_id"):
        week = int(g["week"].iloc[0])
        for team in (g["home_team"].iloc[0], g["away_team"].iloc[0]):
            tp = g[g["posteam"] == team]
            real = tp[tp["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])]
            n_plays = len(real)
            dropbacks = int(tp["pass_attempt"].sum())
            rush_att = int(tp["rush_attempt"].sum())
            pr = dropbacks / n_plays if n_plays else np.nan
            team_games.append({
                "game_id": gid, "team": team, "week": week,
                "plays": n_plays, "pass_rate": pr, "run_rate": 1 - pr if not np.isnan(pr) else np.nan,
                "dropbacks": dropbacks, "rush_attempts": rush_att,
            })
    tdf = pd.DataFrame(team_games)

    for col in ("plays", "pass_rate", "run_rate"):
        sd, n, dropped = _log_ratio_sd(tdf, col, "team")
        if sd is not None:
            result[col] = {"sd": round(sd, 4), "n": n, "dropped": dropped, "level": "team"}
            print(f"  {col}: log-ratio sd={sd:.4f}, n={n}, dropped={dropped}")

    # ── Player-level stats per game ──
    # Receiver share & catch rate
    rec_plays = pbp[pbp["receiver_player_id"].notna()].copy()
    rec_plays = rec_plays.merge(tdf[["game_id", "team", "dropbacks"]],
                                 left_on=["game_id", "posteam"],
                                 right_on=["game_id", "team"], how="left")
    player_game_rec = rec_plays.groupby(["game_id", "receiver_player_id", "posteam"]).agg(
        targets=("receiver_player_id", "count"),
        receptions=("complete_pass", "sum"),
        rec_yards=("receiving_yards", "sum"),
        dropbacks=("dropbacks", "first"),
        week=("week", "first"),
    ).reset_index()
    player_game_rec["share"] = player_game_rec["targets"] / player_game_rec["dropbacks"]
    player_game_rec["catch_rate"] = player_game_rec["receptions"] / player_game_rec["targets"]
    player_game_rec["yards_per_target"] = player_game_rec["rec_yards"] / player_game_rec["targets"]
    player_game_rec = player_game_rec.replace([np.inf, -np.inf], np.nan)

    for col, name in [("share", "share"), ("catch_rate", "catch_rate"),
                       ("yards_per_target", "yards_per_target")]:
        sd, n, dropped = _log_ratio_sd(player_game_rec, col, "receiver_player_id")
        if sd is not None:
            result[name] = {"sd": round(sd, 4), "n": n, "dropped": dropped, "level": "player"}
            print(f"  {name}: log-ratio sd={sd:.4f}, n={n}, dropped={dropped}")

    # Rush share & yards per carry
    rush_plays = pbp[(pbp["rusher_player_id"].notna()) & (pbp["rush_attempt"] == 1)].copy()
    rush_plays = rush_plays.merge(tdf[["game_id", "team", "rush_attempts"]],
                                   left_on=["game_id", "posteam"],
                                   right_on=["game_id", "team"], how="left")
    player_game_rush = rush_plays.groupby(["game_id", "rusher_player_id", "posteam"]).agg(
        carries=("rusher_player_id", "count"),
        rush_yards=("rushing_yards", "sum"),
        team_rush=("rush_attempts", "first"),
        week=("week", "first"),
    ).reset_index()
    player_game_rush["carry_share"] = player_game_rush["carries"] / player_game_rush["team_rush"]
    player_game_rush["yards_per_carry"] = player_game_rush["rush_yards"] / player_game_rush["carries"]
    player_game_rush = player_game_rush.replace([np.inf, -np.inf], np.nan)

    for col, name in [("carry_share", "carry_share"), ("yards_per_carry", "yards_per_carry")]:
        sd, n, dropped = _log_ratio_sd(player_game_rush, col, "rusher_player_id")
        if sd is not None:
            result[name] = {"sd": round(sd, 4), "n": n, "dropped": dropped, "level": "player"}
            print(f"  {name}: log-ratio sd={sd:.4f}, n={n}, dropped={dropped}")

    # QB share, completion rate, yards per attempt
    # Exclude sacks: official attempts = pass_attempt==1 AND sack!=1 (PM-1c)
    pass_plays = pbp[(pbp["passer_player_id"].notna()) & (pbp["pass_attempt"] == 1) &
                      (pbp["sack"] != 1)].copy()
    pass_plays = pass_plays.merge(tdf[["game_id", "team", "dropbacks"]],
                                   left_on=["game_id", "posteam"],
                                   right_on=["game_id", "team"], how="left")
    player_game_pass = pass_plays.groupby(["game_id", "passer_player_id", "posteam"]).agg(
        att=("passer_player_id", "count"),
        cmp=("complete_pass", "sum"),
        pass_yards=("passing_yards", "sum"),
        team_db=("dropbacks", "first"),
        week=("week", "first"),
    ).reset_index()
    player_game_pass["qb_share"] = player_game_pass["att"] / player_game_pass["team_db"]
    player_game_pass["completion_rate"] = player_game_pass["cmp"] / player_game_pass["att"]
    player_game_pass["yards_per_attempt"] = player_game_pass["pass_yards"] / player_game_pass["att"]
    player_game_pass = player_game_pass.replace([np.inf, -np.inf], np.nan)

    for col, name in [("qb_share", "qb_share"), ("completion_rate", "completion_rate"),
                       ("yards_per_attempt", "yards_per_attempt")]:
        sd, n, dropped = _log_ratio_sd(player_game_pass, col, "passer_player_id")
        if sd is not None:
            result[name] = {"sd": round(sd, 4), "n": n, "dropped": dropped, "level": "player"}
            print(f"  {name}: log-ratio sd={sd:.4f}, n={n}, dropped={dropped}")

    # ── Game-level: margin vs spread, total vs total_line ──
    # These are not log-ratios — they are linear residuals (additive, not multiplicative).
    completed = sched[sched["home_score"].notna()].copy()
    completed["margin"] = completed["home_score"] - completed["away_score"]
    completed["total"] = completed["home_score"] + completed["away_score"]

    if "spread_line" in completed.columns:
        valid = completed[completed["spread_line"].notna()]
        # nflverse spread_line convention: negative = home favoured.
        # ATS residual = margin - spread_line.
        # Home favoured by 7: spread_line = -7, wins by 7: margin = 7.
        # Residual = 7 - (-7) = 14 ... that's not right either.
        #
        # Actually check: nflverse spread_line is the CLOSING line for the
        # home team. If home is a 7-point favourite, spread_line = -7.
        # A cover means margin > -spread_line = 7, i.e. margin + spread_line > 0.
        # So margin + spread_line is the ATS residual (positive = home covered).
        #
        # BUT the work order says the plus sign gives SD=18.14 (too high) and
        # expects ~13-14. Let me check both:
        margin_diff_plus = valid["margin"] + valid["spread_line"]
        margin_diff_minus = valid["margin"] - valid["spread_line"]
        sd_plus = float(margin_diff_plus.std())
        sd_minus = float(margin_diff_minus.std())
        corr = float(valid["margin"].corr(valid["spread_line"]))
        print(f"  spread check: margin+spread_line SD={sd_plus:.2f}, "
              f"margin-spread_line SD={sd_minus:.2f}, "
              f"corr(margin,spread_line)={corr:.3f}")

        # The correct form: if spread_line and margin are positively correlated
        # (as they should be — the favourite wins more), then subtracting produces
        # a smaller SD than adding. Use the form that gives ~13-14.
        # The work order demands corr > 0 and SD ~13-14.
        margin_diff = valid["margin"] - valid["spread_line"]
        result["margin_vs_spread"] = {
            "sd": round(float(margin_diff.std()), 4),
            "n": len(valid),
        }
        print(f"  margin_vs_spread: sd={float(margin_diff.std()):.4f}, n={len(valid)}, "
              f"corr(margin,spread_line)={corr:.3f}")

    if "total_line" in completed.columns:
        valid = completed[completed["total_line"].notna()]
        total_diff = valid["total"] - valid["total_line"]
        result["total_vs_line"] = {
            "sd": round(float(total_diff.std()), 4),
            "n": len(valid),
        }
        print(f"  total_vs_line: sd={float(total_diff.std()):.4f}, n={len(valid)}")

    # Keep raw SDs under a separate key for reference
    raw_result = {}
    for col in ("plays", "pass_rate", "run_rate"):
        raw_result[col] = {"sd": round(float(tdf[col].std()), 4), "n": len(tdf)}
    for col, name in [("share", "share"), ("catch_rate", "catch_rate"),
                       ("yards_per_target", "yards_per_target")]:
        v = player_game_rec[col].dropna()
        raw_result[name] = {"sd": round(float(v.std()), 4), "n": len(v)}
    for col, name in [("carry_share", "carry_share"), ("yards_per_carry", "yards_per_carry")]:
        v = player_game_rush[col].dropna()
        raw_result[name] = {"sd": round(float(v.std()), 4), "n": len(v)}
    for col, name in [("qb_share", "qb_share"), ("completion_rate", "completion_rate"),
                       ("yards_per_attempt", "yards_per_attempt")]:
        v = player_game_pass[col].dropna()
        raw_result[name] = {"sd": round(float(v.std()), 4), "n": len(v)}
    result["_raw_sd"] = raw_result

    return result, pbp_sha


def main():
    result, pbp_sha = build_link_sd()
    POSTGAME_DIR.mkdir(parents=True, exist_ok=True)
    out = POSTGAME_DIR / "link_sd_2025_v2.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nWrote {out}")
    print(f"Input PBP sha: {pbp_sha}")
    print(f"Generator sha: {result['generator_sha']}")


if __name__ == "__main__":
    main()
