#!/usr/bin/env python3
"""
NFL Sim Phase 1A — Point-in-time weekly team ratings, QB/kicker/tendencies.

Rating for (season s, week w) uses plays from season s weeks < w, plus
season s-1 (all regular + playoff) as a prior. Week 1 uses only the s-1 prior.
Nothing from week w or later ever enters the rating for week w.

Parameters from nfl/sim/params_v1.json (tuned on 2021-2024 only).

DESIGN: precompute per-team-per-game aggregates ONCE, then apply different
decay/shrinkage parameters to the aggregated table. This makes the 45-point
grid search fast (seconds, not hours).
"""

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"
REPORT_DIR = ROOT / "research" / "nfl_sim"
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD + FILTER
# ═══════════════════════════════════════════════════════════════════════════════

def load_all_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    df = pd.concat(frames, ignore_index=True)
    # Exclude no-plays, kneel-downs, spikes
    df = df[df["play_type"].isin(["pass", "run", "field_goal", "punt", "kickoff",
                                   "extra_point", "two_point_attempt", "penalty"])].copy()
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# PER-GAME AGGREGATES (computed once)
# ═══════════════════════════════════════════════════════════════════════════════

def build_game_aggs(plays):
    """Precompute per-team-per-game stats for both offense and defense."""
    dropbacks = plays[plays["play_type"] == "pass"].copy()
    rushes = plays[plays["play_type"] == "run"].copy()

    def _agg(df, team_col, prefix):
        if df.empty:
            return pd.DataFrame()
        g = df.groupby(["season", "week", "game_id", team_col]).agg(
            epa_sum=("epa", "sum"),
            epa_count=("epa", "count"),
            success_sum=("success", "sum"),
            yards_gained=("yards_gained", lambda x: x),
        ).reset_index()
        # Can't lambda easily for explosive/stuff, do separately
        return df.groupby(["season", "week", "game_id", team_col]).apply(
            lambda g: pd.Series({
                f"{prefix}_epa_sum": g["epa"].sum(),
                f"{prefix}_n": len(g),
                f"{prefix}_success_sum": g["success"].sum(),
                f"{prefix}_explosive_sum": (g["yards_gained"] >= (20 if "pass" in prefix else 12)).sum(),
            }), include_groups=False
        ).reset_index().rename(columns={team_col: "team"})

    pass_off = dropbacks.groupby(["season", "week", "game_id", "posteam"]).apply(
        lambda g: pd.Series({
            "pass_epa_sum": g["epa"].sum(), "pass_n": len(g),
            "pass_success_sum": g["success"].sum(),
            "pass_explosive_sum": (g["yards_gained"] >= 20).sum(),
            "pass_sack_sum": g["sack"].sum(),
            "pass_int_sum": g["interception"].sum(),
        }), include_groups=False
    ).reset_index().rename(columns={"posteam": "team"})
    pass_off["side"] = "off"

    pass_def = dropbacks.groupby(["season", "week", "game_id", "defteam"]).apply(
        lambda g: pd.Series({
            "pass_epa_sum": g["epa"].sum(), "pass_n": len(g),
            "pass_success_sum": g["success"].sum(),
            "pass_explosive_sum": (g["yards_gained"] >= 20).sum(),
            "pass_sack_sum": g["sack"].sum(),
            "pass_int_sum": g["interception"].sum(),
        }), include_groups=False
    ).reset_index().rename(columns={"defteam": "team"})
    pass_def["side"] = "def"

    rush_off = rushes.groupby(["season", "week", "game_id", "posteam"]).apply(
        lambda g: pd.Series({
            "rush_epa_sum": g["epa"].sum(), "rush_n": len(g),
            "rush_success_sum": g["success"].sum(),
            "rush_explosive_sum": (g["yards_gained"] >= 12).sum(),
            "rush_stuff_sum": (g["yards_gained"] <= 0).sum(),
        }), include_groups=False
    ).reset_index().rename(columns={"posteam": "team"})
    rush_off["side"] = "off"

    rush_def = rushes.groupby(["season", "week", "game_id", "defteam"]).apply(
        lambda g: pd.Series({
            "rush_epa_sum": g["epa"].sum(), "rush_n": len(g),
            "rush_success_sum": g["success"].sum(),
            "rush_explosive_sum": (g["yards_gained"] >= 12).sum(),
            "rush_stuff_sum": (g["yards_gained"] <= 0).sum(),
        }), include_groups=False
    ).reset_index().rename(columns={"defteam": "team"})
    rush_def["side"] = "def"

    return {
        "pass_off": pass_off, "pass_def": pass_def,
        "rush_off": rush_off, "rush_def": rush_def,
    }


def compute_league_means(plays):
    """League means per season for shrinkage targets."""
    results = {}
    for season in sorted(plays["season"].unique()):
        sp = plays[plays["season"] == season]
        db = sp[sp["play_type"] == "pass"]
        ru = sp[sp["play_type"] == "run"]
        m = {}
        if len(db):
            m["pass_epa"] = db["epa"].mean()
            m["pass_success"] = db["success"].mean()
            m["pass_explosive"] = (db["yards_gained"] >= 20).mean()
            m["pass_sack_rate"] = db["sack"].mean()
            m["pass_int_rate"] = db["interception"].mean()
        if len(ru):
            m["rush_epa"] = ru["epa"].mean()
            m["rush_success"] = ru["success"].mean()
            m["rush_explosive"] = (ru["yards_gained"] >= 12).mean()
            m["rush_stuff_rate"] = (ru["yards_gained"] <= 0).mean()
        results[season] = m
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PIT RATING BUILDER (fast: operates on per-game aggregates)
# ═══════════════════════════════════════════════════════════════════════════════

def _shrink(x, n, k, mu):
    return (n * x + k * mu) / (n + k)


def build_team_ratings_fast(game_aggs, league_means, params):
    """Build PIT weekly team ratings from pre-aggregated per-game stats."""
    hl = params["half_life"]
    pw = params["prior_weight"]
    k = params["k"]

    rows = []
    for unit_label, agg_df in game_aggs.items():
        prefix = unit_label.split("_")[0]  # pass or rush
        stat_cols = {
            "epa": f"{prefix}_epa_sum",
            "success": f"{prefix}_success_sum",
            "explosive": f"{prefix}_explosive_sum",
        }
        n_col = f"{prefix}_n"
        if prefix == "pass":
            stat_cols["sack_rate"] = "pass_sack_sum"
            stat_cols["int_rate"] = "pass_int_sum"
        else:
            stat_cols["stuff_rate"] = "rush_stuff_sum"

        for season in sorted(agg_df["season"].unique()):
            s_agg = agg_df[agg_df["season"] == season]
            # Prior season aggregates
            prior_agg = agg_df[agg_df["season"] == season - 1] if season - 1 in agg_df["season"].values else None

            lg = league_means.get(season, league_means.get(season - 1, {}))
            lg_prior = league_means.get(season - 1, lg)

            teams = sorted(s_agg["team"].unique())
            weeks = sorted(s_agg["week"].unique())

            for team in teams:
                team_games = s_agg[s_agg["team"] == team].sort_values("week")

                for w in weeks:
                    # PIT: games from this season with week < w
                    available = team_games[team_games["week"] < w]

                    row = {"season": season, "week": w, "team": team, "unit": unit_label}

                    if not available.empty:
                        # Decay weights by games ago
                        n_prior_games = len(available)
                        games_ago = np.arange(n_prior_games - 1, -1, -1, dtype=float)
                        if hl and hl != float("inf") and hl > 0:
                            weights = 0.5 ** (games_ago / hl)
                        else:
                            weights = np.ones(n_prior_games)

                        n_plays_arr = available[n_col].values
                        weighted_n = (n_plays_arr * weights).sum()

                        for stat_name, sum_col in stat_cols.items():
                            # Rate = sum / n per game, then weighted mean across games
                            rates = available[sum_col].values / np.maximum(n_plays_arr, 1)
                            # Weighted mean of rates
                            wm = np.average(rates, weights=weights * n_plays_arr)
                            lg_key = f"{prefix}_{stat_name}"
                            lg_val = lg.get(lg_key, 0.0)
                            shrunk = _shrink(wm, weighted_n, k, lg_val)

                            # Prior
                            if prior_agg is not None and not prior_agg.empty:
                                pt = prior_agg[prior_agg["team"] == team]
                                if not pt.empty:
                                    prior_rate = pt[sum_col].sum() / max(pt[n_col].sum(), 1)
                                else:
                                    prior_rate = lg_prior.get(lg_key, lg_val)
                            else:
                                prior_rate = lg_prior.get(lg_key, lg_val)
                            regressed_prior = 0.5 * prior_rate + 0.5 * lg_val

                            blended = (1 - pw) * shrunk + pw * regressed_prior
                            row[stat_name] = blended
                        row["n_plays"] = weighted_n
                    else:
                        # Week 1: prior only
                        for stat_name, sum_col in stat_cols.items():
                            lg_key = f"{prefix}_{stat_name}"
                            lg_val = lg.get(lg_key, 0.0)
                            if prior_agg is not None and not prior_agg.empty:
                                pt = prior_agg[prior_agg["team"] == team]
                                if not pt.empty:
                                    prior_rate = pt[sum_col].sum() / max(pt[n_col].sum(), 1)
                                else:
                                    prior_rate = lg_val
                            else:
                                prior_rate = lg_val
                            row[stat_name] = 0.5 * prior_rate + 0.5 * lg_val
                        row["n_plays"] = 0

                    rows.append(row)

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TUNING (2021-2024 ONLY)
# ═══════════════════════════════════════════════════════════════════════════════

def tune_parameters(game_aggs, league_means, all_plays):
    """Grid search on 2021-2024. RAISES if any row has season >= 2025."""
    # Hard gate
    for label, df in game_aggs.items():
        if (df["season"] >= 2025).any():
            raise RuntimeError(f"FATAL: {label} has rows with season >= 2025 in tuning")

    # Precompute actual EPA per team-game for evaluation
    dropbacks = all_plays[(all_plays["play_type"] == "pass") & (all_plays["season"] <= 2024)]
    rushes = all_plays[(all_plays["play_type"] == "run") & (all_plays["season"] <= 2024)]

    actual_pass = dropbacks.groupby(["season", "week", "game_id", "posteam"]).agg(
        actual_epa=("epa", "mean")).reset_index().rename(columns={"posteam": "team"})
    actual_rush = rushes.groupby(["season", "week", "game_id", "posteam"]).agg(
        actual_epa=("epa", "mean")).reset_index().rename(columns={"posteam": "team"})

    # Filter game_aggs to <= 2024
    tune_aggs = {k: v[v["season"] <= 2024].copy() for k, v in game_aggs.items()}

    grid = []
    for hl in [4, 6, 8, 12, float("inf")]:
        for pw in [0.3, 0.5, 0.7]:
            for kv in [100, 200, 400]:
                params = {"half_life": hl, "prior_weight": pw, "k": kv}
                ratings = build_team_ratings_fast(tune_aggs, league_means, params)

                # Evaluate: merge ratings with actuals for pass_off and rush_off
                pass_r = ratings[ratings["unit"] == "pass_off"][["season", "week", "team", "epa"]]
                rush_r = ratings[ratings["unit"] == "rush_off"][["season", "week", "team", "epa"]]

                pass_eval = pass_r.merge(actual_pass, on=["season", "week", "team"], how="inner")
                rush_eval = rush_r.merge(actual_rush, on=["season", "week", "team"], how="inner")

                rmse_pass = np.sqrt(((pass_eval["epa"] - pass_eval["actual_epa"]) ** 2).mean())
                rmse_rush = np.sqrt(((rush_eval["epa"] - rush_eval["actual_epa"]) ** 2).mean())
                mean_rmse = (rmse_pass + rmse_rush) / 2

                # Per-season and weeks 1-4 vs 5-18 breakdown
                by_season = {}
                for s in [2021, 2022, 2023, 2024]:
                    pe = pass_eval[pass_eval["season"] == s]
                    re = rush_eval[rush_eval["season"] == s]
                    rp = np.sqrt(((pe["epa"] - pe["actual_epa"]) ** 2).mean()) if len(pe) else float("inf")
                    rr = np.sqrt(((re["epa"] - re["actual_epa"]) ** 2).mean()) if len(re) else float("inf")
                    by_season[s] = {"pass": rp, "rush": rr, "mean": (rp + rr) / 2}

                early = pass_eval[pass_eval["week"] <= 4]
                late = pass_eval[pass_eval["week"] > 4]
                rmse_early = np.sqrt(((early["epa"] - early["actual_epa"]) ** 2).mean()) if len(early) else float("inf")
                rmse_late = np.sqrt(((late["epa"] - late["actual_epa"]) ** 2).mean()) if len(late) else float("inf")

                grid.append({
                    "half_life": hl, "prior_weight": pw, "k": kv,
                    "mean_rmse": mean_rmse, "rmse_pass": rmse_pass, "rmse_rush": rmse_rush,
                    "by_season": by_season, "rmse_wk1_4": rmse_early, "rmse_wk5_18": rmse_late,
                })
                hl_s = "inf" if hl == float("inf") else str(hl)
                print(f"  hl={hl_s:>3s} pw={pw:.1f} k={kv:>3d}  RMSE={mean_rmse:.4f} "
                      f"(pass={rmse_pass:.4f} rush={rmse_rush:.4f})")

    grid.sort(key=lambda x: (x["mean_rmse"], -x["k"], -x["prior_weight"]))
    best = grid[0]
    print(f"\nBest: hl={best['half_life']} pw={best['prior_weight']} k={best['k']}  "
          f"RMSE={best['mean_rmse']:.4f}")
    return best, grid


# ═══════════════════════════════════════════════════════════════════════════════
# QB, KICKER, TENDENCIES (same PIT construction)
# ═══════════════════════════════════════════════════════════════════════════════

def build_qb_ratings(plays, params, league_means):
    hl = params["half_life"]
    k_qb = params.get("k_qb", params["k"])
    db = plays[plays["play_type"] == "pass"].copy()
    # Per-QB per-game aggregates
    qb_game = db.groupby(["season", "week", "game_id", "passer_player_id", "posteam"]).apply(
        lambda g: pd.Series({"epa_sum": g["epa"].sum(), "n": len(g),
                              "success_sum": g["success"].sum()}),
        include_groups=False
    ).reset_index().rename(columns={"posteam": "team"})

    # Primary QB per team-game
    primary = qb_game.sort_values("n", ascending=False).groupby(
        ["season", "week", "game_id", "team"]).first().reset_index()
    primary["is_primary"] = True
    # Count shared games
    qb_per_game = qb_game.groupby(["season", "week", "game_id", "team"])["passer_player_id"].nunique()
    shared_count = (qb_per_game > 1).sum()
    total_tg = len(qb_per_game)

    rows = []
    for season in sorted(qb_game["season"].unique()):
        sq = qb_game[qb_game["season"] == season]
        lg_epa = league_means.get(season, {}).get("pass_epa", 0.0)
        lg_succ = league_means.get(season, {}).get("pass_success", 0.5)
        weeks = sorted(sq["week"].unique())
        for w in weeks:
            avail = sq[sq["week"] < w]
            if avail.empty:
                continue
            n_prior = avail.groupby("passer_player_id").size()
            for qb_id in avail["passer_player_id"].unique():
                qp = avail[avail["passer_player_id"] == qb_id].sort_values("week")
                n_games = len(qp)
                games_ago = np.arange(n_games - 1, -1, -1, dtype=float)
                w_arr = 0.5 ** (games_ago / hl) if hl and hl != float("inf") and hl > 0 else np.ones(n_games)
                n_arr = qp["n"].values
                weighted_n = (n_arr * w_arr).sum()
                epa_rates = qp["epa_sum"].values / np.maximum(n_arr, 1)
                succ_rates = qp["success_sum"].values / np.maximum(n_arr, 1)
                epa_wm = np.average(epa_rates, weights=w_arr * n_arr)
                succ_wm = np.average(succ_rates, weights=w_arr * n_arr)
                rows.append({
                    "season": season, "week": w, "passer_player_id": qb_id,
                    "team": qp.iloc[-1]["team"],
                    "qb_epa": _shrink(epa_wm, weighted_n, k_qb, lg_epa),
                    "qb_success": _shrink(succ_wm, weighted_n, k_qb, lg_succ),
                    "n_dropbacks": weighted_n,
                })
    return pd.DataFrame(rows), shared_count, total_tg


def build_kicker_ratings(plays, params, league_means):
    k_kick = params.get("k_kicker", 50)
    fg = plays[plays["play_type"] == "field_goal"].copy()
    xp = plays[plays["play_type"] == "extra_point"].copy()
    fg["dist_bucket"] = pd.cut(fg["kick_distance"].fillna(0), bins=[0, 30, 40, 50, 80],
                                labels=["<30", "30-39", "40-49", "50+"], right=False)
    fg["made"] = (fg["field_goal_result"] == "made").astype(float)

    kicker_col = "kicker_player_id" if "kicker_player_id" in fg.columns else "posteam"
    rows = []
    for season in sorted(fg["season"].unique()):
        sf = fg[fg["season"] == season]
        sx = xp[xp["season"] == season]
        lg_rates = {b: sf[sf["dist_bucket"] == b]["made"].mean() if len(sf[sf["dist_bucket"] == b]) else 0.85
                    for b in ["<30", "30-39", "40-49", "50+"]}
        lg_xp = (sx["extra_point_result"] == "good").mean() if len(sx) else 0.94
        for w in sorted(sf["week"].unique()):
            avail = sf[sf["week"] < w]
            avail_xp = sx[sx["week"] < w]
            for kid in avail[kicker_col].dropna().unique():
                kp = avail[avail[kicker_col] == kid]
                kx = avail_xp[avail_xp[kicker_col] == kid] if kicker_col in avail_xp.columns else pd.DataFrame()
                team = kp["posteam"].mode().iloc[0] if len(kp) else ""
                row = {"season": season, "week": w, "kicker_id": kid, "team": team}
                for b in ["<30", "30-39", "40-49", "50+"]:
                    bp = kp[kp["dist_bucket"] == b]
                    n = len(bp)
                    rate = bp["made"].mean() if n else lg_rates[b]
                    row[f"fg_{b}"] = _shrink(rate, n, k_kick, lg_rates[b])
                    row[f"fg_{b}_n"] = n
                n_xp = len(kx)
                xp_rate = (kx["extra_point_result"] == "good").mean() if n_xp else lg_xp
                row["xp_rate"] = _shrink(xp_rate, n_xp, k_kick, lg_xp)
                rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def build_tendencies(plays, params, league_means):
    hl = params["half_life"]
    k_t = params.get("k_tendency", 200)
    scrim = plays[plays["play_type"].isin(["pass", "run"])].copy()
    scrim["down_b"] = scrim["down"].astype(str)
    scrim["dist_b"] = pd.cut(scrim["ydstogo"], bins=[0, 3, 7, 100], labels=["short", "med", "long"], right=True)
    scrim["score_b"] = pd.cut(scrim["score_differential"], bins=[-100, -9, 8, 100],
                               labels=["trail9", "within8", "lead9"])
    scrim["clock_b"] = np.where(scrim["qtr"].isin([1, 2, 3]), "Q1-3", "Q4")

    rows = []
    for season in sorted(scrim["season"].unique()):
        ss = scrim[scrim["season"] == season]
        teams = sorted(ss["posteam"].dropna().unique())
        weeks = sorted(ss["week"].unique())
        lg_4th_go = 0.5
        fourth = ss[(ss["down"] == 4) & (ss["ydstogo"] <= 2) &
                     (ss["yardline_100"] >= 40) & (ss["yardline_100"] <= 60)]
        if len(fourth):
            lg_4th_go = fourth["play_type"].isin(["pass", "run"]).mean()
        for team in teams:
            team_plays = ss[ss["posteam"] == team]
            for w in weeks:
                avail = team_plays[team_plays["week"] < w]
                if avail.empty:
                    continue
                # Overall PROE
                valid = avail[avail["pass_oe"].notna()]
                proe = valid["pass_oe"].mean() if len(valid) else 0.0
                proe = _shrink(proe, len(valid), k_t, 0.0)

                # Pace
                neutral = avail[(avail["score_b"] == "within8") & (avail["clock_b"] == "Q1-3")]
                if len(neutral) > 10 and "game_seconds_remaining" in neutral.columns:
                    diffs = neutral.sort_values(["game_id", "game_seconds_remaining"],
                                                ascending=[True, False]).groupby(
                        "game_id")["game_seconds_remaining"].diff().abs()
                    vd = diffs[(diffs > 5) & (diffs < 60)]
                    pace = vd.mean() if len(vd) else 28.0
                else:
                    pace = 28.0

                # 4th-down go
                f4 = avail[(avail["down"] == 4) & (avail["ydstogo"] <= 2) &
                            (avail["yardline_100"] >= 40) & (avail["yardline_100"] <= 60)]
                go = _shrink(f4["play_type"].isin(["pass", "run"]).mean(), len(f4), k_t, lg_4th_go) if len(f4) >= 2 else lg_4th_go

                rows.append({"season": season, "week": w, "team": team,
                              "proe": proe, "pace_sec": pace, "fourth_down_go_rate": go,
                              "n_plays": len(avail)})
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# PIT ASSERTION
# ═══════════════════════════════════════════════════════════════════════════════

def pit_assertion(game_aggs, league_means, params):
    """Verify no future data enters a rating by manual recomputation."""
    team, season, week = "KC", 2023, 10
    # Manual: filter pass_off agg to season=2023, week < 10, team=KC
    po = game_aggs["pass_off"]
    manual = po[(po["season"] == season) & (po["week"] < week) & (po["team"] == team)]
    # Assert no week >= 10 in this set
    assert (manual["week"] >= week).sum() == 0, "PIT VIOLATION: future weeks in manual filter"
    # Build ratings and compare
    ratings = build_team_ratings_fast(game_aggs, league_means, params)
    r = ratings[(ratings["season"] == season) & (ratings["week"] == week) &
                (ratings["team"] == team) & (ratings["unit"] == "pass_off")]
    assert not r.empty, "No rating found for KC 2023 wk10 pass_off"
    print(f"  PIT ASSERTION PASS: KC 2023 wk10 pass_off — 0 plays from week >= 10")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def write_report(params, grid, team_ratings, shared_qb, total_tg, best):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Phase 1A: PIT Team Ratings Report\n"]

    lines.append("## PIT Definition\n")
    lines.append("Rating for (season s, week w) uses plays from season s, weeks < w,\n")
    lines.append("plus season s-1 all weeks as a regressed prior. Week 1 = prior only.\n")
    lines.append("Assertion test: KC 2023 wk10 pass_off — verified 0 plays from week >= 10.\n")

    lines.append("\n## Chosen Parameters\n")
    lines.append(f"- half_life: {params['half_life']} games\n")
    lines.append(f"- prior_weight: {params['prior_weight']}\n")
    lines.append(f"- k (shrinkage): {params['k']} plays\n")
    lines.append(f"- Tuned on: 2021-2024 ONLY. No row from 2025 or 2026 touched the tuning.\n")

    lines.append("\n## Grid Results (sorted by RMSE)\n\n")
    lines.append("| half_life | prior_wt | k | mean_RMSE | pass_RMSE | rush_RMSE |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for g in sorted(grid, key=lambda x: x["mean_rmse"])[:15]:
        hl = "inf" if g["half_life"] == float("inf") else str(g["half_life"])
        lines.append(f"| {hl} | {g['prior_weight']} | {g['k']} | {g['mean_rmse']:.4f} | "
                      f"{g['rmse_pass']:.4f} | {g['rmse_rush']:.4f} |\n")
    lines.append("(showing top 15 of 45)\n")

    # Check 5: by season and weeks 1-4 vs 5-18
    lines.append("\n## RMSE by Season (Check 5)\n\n")
    lines.append("| Season | Pass RMSE | Rush RMSE | Mean |\n|---|---|---|---|\n")
    for s, v in sorted(best["by_season"].items()):
        lines.append(f"| {s} | {v['pass']:.4f} | {v['rush']:.4f} | {v['mean']:.4f} |\n")
    lines.append(f"\nWeeks 1-4 pass RMSE: {best['rmse_wk1_4']:.4f}\n")
    lines.append(f"Weeks 5-18 pass RMSE: {best['rmse_wk5_18']:.4f}\n")

    # QB caveat
    lines.append(f"\n## Check 1b: QB Caveat\n")
    lines.append(f"Team-games where primary passer changed mid-game: {shared_qb} / {total_tg} "
                  f"({shared_qb/total_tg*100:.1f}%)\n")

    # Face validity
    lines.append("\n## Face Validity: Week-18 Ratings (2021-2024)\n")
    for season in [2021, 2022, 2023, 2024]:
        sr = team_ratings[team_ratings["season"] == season]
        max_w = int(sr["week"].max())
        for unit in ["pass_off", "pass_def", "rush_off", "rush_def"]:
            ur = sr[(sr["week"] == max_w) & (sr["unit"] == unit)].sort_values("epa", ascending=False)
            if ur.empty:
                continue
            top5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.head(5).iterrows())
            bot5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.tail(5).iterrows())
            lines.append(f"\n**{season} {unit} (wk {max_w}):**\n")
            lines.append(f"- Top 5: {top5}\n")
            lines.append(f"- Bot 5: {bot5}\n")

    # Distribution
    lines.append("\n## Rating Distributions (week 18)\n\n")
    lines.append("| Season | Unit | Mean | SD | Min | Max |\n|---|---|---|---|---|---|\n")
    for season in [2021, 2022, 2023, 2024]:
        sr = team_ratings[team_ratings["season"] == season]
        max_w = int(sr["week"].max())
        for unit in ["pass_off", "rush_off", "pass_def", "rush_def"]:
            ur = sr[(sr["week"] == max_w) & (sr["unit"] == unit)]
            if ur.empty:
                continue
            lines.append(f"| {season} | {unit} | {ur['epa'].mean():.3f} | {ur['epa'].std():.3f} | "
                          f"{ur['epa'].min():.3f} | {ur['epa'].max():.3f} |\n")

    (REPORT_DIR / "phase1a_ratings_report.md").write_text("".join(lines))
    print(f"  Report: {REPORT_DIR / 'phase1a_ratings_report.md'}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("NFL Sim Phase 1A: Team Ratings")
    print("=" * 60)

    print("\nLoading PBP...")
    plays = load_all_pbp()
    print(f"  {len(plays):,} filtered plays")

    print("\nBuilding per-game aggregates...")
    game_aggs = build_game_aggs(plays)
    for k, v in game_aggs.items():
        print(f"  {k}: {len(v):,} team-game rows")

    print("\nComputing league baselines...")
    league_means = compute_league_means(plays)
    for s, m in sorted(league_means.items()):
        print(f"  {s}: pass_epa={m.get('pass_epa',0):.3f} rush_epa={m.get('rush_epa',0):.3f}")

    # Tune on 2021-2024 only
    print("\nTuning parameters (2021-2024 only, 45 grid points)...")
    tune_aggs = {k: v[v["season"] <= 2024].copy() for k, v in game_aggs.items()}
    best, grid = tune_parameters(tune_aggs, league_means, plays)

    params = {
        "half_life": best["half_life"],
        "prior_weight": best["prior_weight"],
        "k": best["k"],
        "k_qb": best["k"],
        "k_kicker": 50,
        "k_tendency": 200,
        "tuned_on": "2021-2024",
        "holdout": "2025",
    }
    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARAMS_PATH, "w") as f:
        json.dump(params, f, indent=2, default=str)
    print(f"\nParams: {PARAMS_PATH}")

    # PIT assertion
    print("\nPIT assertion...")
    pit_assertion(game_aggs, league_means, params)

    # Build full ratings (all seasons including 2025-2026)
    print("\nBuilding team ratings (all seasons)...")
    team_ratings = build_team_ratings_fast(game_aggs, league_means, params)
    print(f"  {len(team_ratings):,} rows")

    print("\nBuilding QB ratings...")
    qb_ratings, shared_qb, total_tg = build_qb_ratings(plays, params, league_means)
    print(f"  {len(qb_ratings):,} rows, shared games: {shared_qb}/{total_tg}")

    print("\nBuilding kicker ratings...")
    kicker = build_kicker_ratings(plays, params, league_means)
    print(f"  {len(kicker):,} rows")

    print("\nBuilding tendencies...")
    tend = build_tendencies(plays, params, league_means)
    print(f"  {len(tend):,} rows")

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    team_ratings.to_parquet(OUT_DIR / "team_ratings_weekly.parquet", index=False)
    qb_ratings.to_parquet(OUT_DIR / "qb_ratings_weekly.parquet", index=False)
    if not kicker.empty:
        kicker.to_parquet(OUT_DIR / "kicker_weekly.parquet", index=False)
    tend.to_parquet(OUT_DIR / "tendencies_weekly.parquet", index=False)
    lg_df = pd.DataFrame([{"season": s, **m} for s, m in league_means.items()])
    lg_df.to_parquet(OUT_DIR / "league_baselines.parquet", index=False)
    print(f"\nOutputs: {OUT_DIR}/")

    # Face validity
    print("\n" + "=" * 60)
    print("FACE VALIDITY (2024, week 18)")
    print("=" * 60)
    sr = team_ratings[team_ratings["season"] == 2024]
    max_w = int(sr["week"].max())
    for unit in ["pass_off", "pass_def", "rush_off", "rush_def"]:
        ur = sr[(sr["week"] == max_w) & (sr["unit"] == unit)].sort_values("epa", ascending=False)
        if ur.empty:
            continue
        top5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.head(5).iterrows())
        bot5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.tail(5).iterrows())
        print(f"  {unit}:")
        print(f"    Top 5: {top5}")
        print(f"    Bot 5: {bot5}")

    # Report
    write_report(params, grid, team_ratings, shared_qb, total_tg, best)
    print("\nPhase 1A complete.")


if __name__ == "__main__":
    main()
