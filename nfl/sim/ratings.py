#!/usr/bin/env python3
"""
NFL Sim Phase 1A — Point-in-time weekly team ratings, QB/kicker/tendencies.

Rating for (season s, week w) uses plays from season s weeks < w, plus
season s-1 (all regular + playoff) as a prior. Week 1 uses only the s-1 prior.
Nothing from week w or later ever enters the rating for week w.

SHRINK TARGETS are always the PRIOR SEASON's league mean (s-1), never the
current season's. This is what makes the 2026 path identical to the historical
path (Check 3): 2026 week 3 shrinks toward 2025, not toward a 2-game 2026.

Parameters from nfl/sim/params_v1.json (tuned on 2021-2024 only).
"""

import json, subprocess, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"
REPORT_DIR = ROOT / "research" / "nfl_sim"
SEASONS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
TUNE_SEASONS = [2021, 2022, 2023, 2024]
OUTPUT_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]  # 2020 is prior only


def _shrink(x, n, k, mu):
    return (n * x + k * mu) / (n + k)


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD + FILTER
# ═══════════════════════════════════════════════════════════════════════════════

def load_all_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True)


def filter_scrimmage(df):
    """Keep pass + run plays (scrimmage). Excludes no-plays, kneels, spikes."""
    return df[df["play_type"].isin(["pass", "run"])].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# PER-GAME AGGREGATES (computed once)
# ═══════════════════════════════════════════════════════════════════════════════

def build_game_aggs(plays):
    """Precompute per-team-per-game stats for pass and rush, offense and defense."""
    db = plays[plays["play_type"] == "pass"].copy()
    ru = plays[plays["play_type"] == "run"].copy()

    def _pass_agg(df, team_col):
        return df.groupby(["season", "week", "game_id", team_col]).apply(
            lambda g: pd.Series({
                "pass_epa_sum": g["epa"].sum(), "pass_n": len(g),
                "pass_success_sum": g["success"].sum(),
                "pass_explosive_sum": (g["yards_gained"] >= 20).sum(),
                "pass_sack_sum": g["sack"].sum(),
                "pass_int_sum": g["interception"].sum(),
            }), include_groups=False
        ).reset_index().rename(columns={team_col: "team"})

    def _rush_agg(df, team_col):
        return df.groupby(["season", "week", "game_id", team_col]).apply(
            lambda g: pd.Series({
                "rush_epa_sum": g["epa"].sum(), "rush_n": len(g),
                "rush_success_sum": g["success"].sum(),
                "rush_explosive_sum": (g["yards_gained"] >= 12).sum(),
                "rush_stuff_sum": (g["yards_gained"] <= 0).sum(),
            }), include_groups=False
        ).reset_index().rename(columns={team_col: "team"})

    return {
        "pass_off": _pass_agg(db, "posteam"), "pass_def": _pass_agg(db, "defteam"),
        "rush_off": _rush_agg(ru, "posteam"), "rush_def": _rush_agg(ru, "defteam"),
    }


def compute_league_means(plays):
    """League means per season. Written to league_baselines.parquet for every
    season but used as shrink targets ONLY for the FOLLOWING season."""
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


def get_shrink_target(league_means, season):
    """Shrink target for season s is ALWAYS the s-1 league mean (FIX 2)."""
    if season - 1 in league_means:
        return league_means[season - 1]
    earliest = min(league_means.keys())
    return league_means[earliest]


def get_universe(game_aggs_or_plays, season, team_col="team"):
    """Return (teams, weeks) for the 32-team universe.
    teams = 32 teams from s-1 plus any new abbreviation in s.
    weeks = 1 through min(22, last observed week in s + 1).
    Accepts either a dict of agg DataFrames or a single DataFrame."""
    all_teams = set()
    last_week = 0

    if isinstance(game_aggs_or_plays, dict):
        for label, agg in game_aggs_or_plays.items():
            prior = agg[agg["season"] == season - 1]
            curr = agg[agg["season"] == season]
            all_teams.update(prior[team_col].unique())
            all_teams.update(curr[team_col].unique())
            if not curr.empty:
                last_week = max(last_week, int(curr["week"].max()))
    else:
        df = game_aggs_or_plays
        for col in [team_col, "home_team", "away_team"]:
            if col in df.columns:
                prior = df[df["season"] == season - 1]
                curr = df[df["season"] == season]
                all_teams.update(prior[col].dropna().unique())
                all_teams.update(curr[col].dropna().unique())
        curr = df[df["season"] == season]
        if not curr.empty:
            last_week = int(curr["week"].max())

    if last_week == 0:
        last_week = 1
    weeks = list(range(1, min(22, last_week + 1) + 1))
    return sorted(all_teams), weeks


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM RATINGS (fast, vectorized on per-game aggregates)
# ═══════════════════════════════════════════════════════════════════════════════

def build_team_ratings_fast(game_aggs, league_means, params, output_seasons=None):
    hl = params["half_life"]
    pw = params["prior_weight"]
    k = params["k"]
    prior_reg = params.get("prior_regression", 0.5)

    rows = []
    for unit_label, agg_df in game_aggs.items():
        prefix = unit_label.split("_")[0]
        stat_cols = {"epa": f"{prefix}_epa_sum", "success": f"{prefix}_success_sum",
                     "explosive": f"{prefix}_explosive_sum"}
        n_col = f"{prefix}_n"
        if prefix == "pass":
            stat_cols["sack_rate"] = "pass_sack_sum"
            stat_cols["int_rate"] = "pass_int_sum"
        else:
            stat_cols["stuff_rate"] = "rush_stuff_sum"

        seasons = output_seasons or sorted(set(agg_df["season"].unique()) & set(OUTPUT_SEASONS))
        for season in seasons:
            s_agg = agg_df[agg_df["season"] == season]
            prior_agg = agg_df[agg_df["season"] == season - 1] if season - 1 in agg_df["season"].values else None

            lg = get_shrink_target(league_means, season)

            # Universe fix: 32 teams from s-1, weeks 1..last+1
            teams, weeks = get_universe(game_aggs, season)

            for team in teams:
                tg = s_agg[s_agg["team"] == team].sort_values("week")
                for w in weeks:
                    available = tg[tg["week"] < w]
                    row = {"season": season, "week": w, "team": team, "unit": unit_label}

                    for stat_name, sum_col in stat_cols.items():
                        lg_key = f"{prefix}_{stat_name}"
                        lg_val = lg.get(lg_key, 0.0)

                        # Current-season component
                        if not available.empty:
                            n_arr = available[n_col].values
                            rates = available[sum_col].values / np.maximum(n_arr, 1)
                            n_games = len(available)
                            games_ago = np.arange(n_games - 1, -1, -1, dtype=float)
                            w_arr = 0.5 ** (games_ago / hl) if hl and hl != float("inf") and hl > 0 else np.ones(n_games)
                            weighted_n = (n_arr * w_arr).sum()
                            wm = np.average(rates, weights=w_arr * n_arr)
                            shrunk = _shrink(wm, weighted_n, k, lg_val)
                        else:
                            shrunk = lg_val
                            weighted_n = 0.0

                        # Prior-season component
                        if prior_agg is not None and not prior_agg.empty:
                            pt = prior_agg[prior_agg["team"] == team]
                            if not pt.empty:
                                prior_rate = pt[sum_col].sum() / max(pt[n_col].sum(), 1)
                            else:
                                prior_rate = lg_val
                        else:
                            prior_rate = lg_val
                        regressed_prior = prior_reg * prior_rate + (1 - prior_reg) * lg_val

                        if weighted_n > 0:
                            blended = (1 - pw) * shrunk + pw * regressed_prior
                        else:
                            blended = regressed_prior

                        row[stat_name] = blended
                    row["n_plays"] = weighted_n if not available.empty else 0
                    rows.append(row)

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# QB RATINGS
# ═══════════════════════════════════════════════════════════════════════════════

def build_qb_ratings(plays, params, league_means):
    hl = params["half_life"]
    k_qb = params.get("k_qb", params["k"])
    db = plays[plays["play_type"] == "pass"].copy()

    qb_game = db.groupby(["season", "week", "game_id", "passer_player_id", "posteam"]).apply(
        lambda g: pd.Series({"epa_sum": g["epa"].sum(), "n": len(g),
                              "success_sum": g["success"].sum()}),
        include_groups=False
    ).reset_index().rename(columns={"posteam": "team"})

    # Primary QB stats for caveat
    primary_qb_stats = []
    for (gid, team), grp in qb_game.groupby(["game_id", "team"]):
        total = grp["n"].sum()
        top = grp.sort_values("n", ascending=False).iloc[0]
        primary_frac = top["n"] / total if total > 0 else 1.0
        primary_qb_stats.append({
            "game_id": gid, "team": team, "season": top["season"],
            "primary_qb": top["passer_player_id"],
            "primary_frac": primary_frac,
            "n_passers": len(grp),
        })
    pq_df = pd.DataFrame(primary_qb_stats)
    shared_any = (pq_df["n_passers"] > 1).sum()
    shared_lt80 = (pq_df["primary_frac"] < 0.80).sum()
    total_tg = len(pq_df)

    rows = []
    for season in OUTPUT_SEASONS:
        if season not in qb_game["season"].values:
            continue
        sq = qb_game[qb_game["season"] == season]
        lg = get_shrink_target(league_means, season)
        lg_epa = lg.get("pass_epa", 0.0)
        lg_succ = lg.get("pass_success", 0.5)
        for w in sorted(sq["week"].unique()):
            avail = sq[sq["week"] < w]
            if avail.empty:
                continue
            for qb_id in avail["passer_player_id"].unique():
                qp = avail[avail["passer_player_id"] == qb_id].sort_values("week")
                n_games = len(qp)
                games_ago = np.arange(n_games - 1, -1, -1, dtype=float)
                w_arr = 0.5 ** (games_ago / hl) if hl and hl != float("inf") and hl > 0 else np.ones(n_games)
                n_arr = qp["n"].values
                weighted_n = (n_arr * w_arr).sum()
                epa_wm = np.average(qp["epa_sum"].values / np.maximum(n_arr, 1), weights=w_arr * n_arr)
                succ_wm = np.average(qp["success_sum"].values / np.maximum(n_arr, 1), weights=w_arr * n_arr)
                rows.append({
                    "season": season, "week": w, "passer_player_id": qb_id,
                    "team": qp.iloc[-1]["team"],
                    "qb_epa": _shrink(epa_wm, weighted_n, k_qb, lg_epa),
                    "qb_success": _shrink(succ_wm, weighted_n, k_qb, lg_succ),
                    "n_dropbacks": weighted_n,
                })
    return pd.DataFrame(rows), shared_any, shared_lt80, total_tg


# ═══════════════════════════════════════════════════════════════════════════════
# KICKER RATINGS
# ═══════════════════════════════════════════════════════════════════════════════

def build_kicker_ratings(plays, params, league_means):
    k_kick = params.get("k_kicker", 50)
    fg = plays[plays["play_type"] == "field_goal"].copy()
    xp = plays[plays["play_type"] == "extra_point"].copy()
    fg["dist_bucket"] = pd.cut(fg["kick_distance"].fillna(0), bins=[0, 30, 40, 50, 80],
                                labels=["<30", "30-39", "40-49", "50+"], right=False)
    fg["made"] = (fg["field_goal_result"] == "made").astype(float)
    kicker_col = "kicker_player_id" if "kicker_player_id" in fg.columns else "posteam"

    rows = []
    for season in OUTPUT_SEASONS:
        sf = fg[fg["season"] == season]
        sx = xp[xp["season"] == season]
        if sf.empty:
            continue
        # FIX 2: shrink target = prior season league rates
        prior_fg = fg[fg["season"] == season - 1]
        prior_xp = xp[xp["season"] == season - 1]
        lg_rates = {}
        for b in ["<30", "30-39", "40-49", "50+"]:
            pb = prior_fg[prior_fg["dist_bucket"] == b] if not prior_fg.empty else pd.DataFrame()
            lg_rates[b] = pb["made"].mean() if len(pb) else 0.85
        lg_xp = (prior_xp["extra_point_result"] == "good").mean() if len(prior_xp) else 0.94

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


# ═══════════════════════════════════════════════════════════════════════════════
# TENDENCIES (FIX 1: 4th-down from unfiltered; FIX 4: situational PROE)
# ═══════════════════════════════════════════════════════════════════════════════

def build_tendencies(scrimmage_plays, all_plays, params, league_means,
                     fourth_down_table=None):
    """Overall PROE, pace, 4th-down GOE.
    FIX 1: 4th-down computed from ALL plays (incl. punts/FGs in denominator).
    FIX 2: shrink target = prior season.
    5A-3: fourth_down_go_rate replaced by fourth_down_goe — GOE (go-over-
    expected) measures observed go decisions minus the fourth_down table's
    expected go probability, summed over each team's own situations. Applied
    logit-additively in the engine, exactly like PROE."""
    hl = params["half_life"]
    k_t = params.get("k_tendency", 200)

    # Build lookup from the fourth_down decision table for GOE computation
    fd_lookup = {}
    if fourth_down_table is not None:
        for _, r in fourth_down_table.iterrows():
            fd_lookup[(r["ydstogo_b"], r["yl_b"], r["score_b"], r["qtr_b"])] = r["p_go"]

    def _4th_down_expected_go(row):
        """Look up the table's expected P(go) for one 4th-down play.
        Uses the same 4-level fallback as the engine."""
        yd = row["ydstogo"]
        y = row["yardline_100"]
        sd = row["score_differential"]
        qt = row["qtr"]
        gsr = row.get("game_seconds_remaining", 900)

        yd_b = "1-2" if yd <= 2 else ("3-5" if yd <= 5 else ("6-10" if yd <= 10 else "11+"))
        if y <= 10: yl_b = "opp1-10"
        elif y <= 20: yl_b = "opp11-20"
        elif y <= 30: yl_b = "opp21-30"
        elif y <= 40: yl_b = "opp31-40"
        elif y <= 50: yl_b = "opp41-50"
        elif y <= 60: yl_b = "own41-50"
        elif y <= 70: yl_b = "own31-40"
        elif y <= 80: yl_b = "own21-30"
        elif y <= 90: yl_b = "own11-20"
        else: yl_b = "own1-10"

        if sd < -8: sc_fine = "trail9+"
        elif sd < -3: sc_fine = "trail4-8"
        elif sd < 0: sc_fine = "trail1-3"
        elif sd == 0: sc_fine = "tied"
        elif sd <= 3: sc_fine = "lead1-3"
        elif sd <= 8: sc_fine = "lead4-8"
        else: sc_fine = "lead9+"

        if qt <= 3: qt_fine = "Q1-3"
        elif gsr > 300: qt_fine = "Q4>5"
        elif gsr > 120: qt_fine = "Q4_2-5"
        else: qt_fine = "Q4<2"

        sc_coarse = "trail9" if sd < -8 else ("within8" if sd <= 8 else "lead9")
        qt_coarse = "Q1-3" if qt <= 3 else "Q4"
        if y <= 10: yl_coarse = "rz"
        elif y <= 40: yl_coarse = "opp40"
        elif y <= 65: yl_coarse = "midfield"
        else: yl_coarse = "own35"

        p = fd_lookup.get((yd_b, yl_b, sc_fine, qt_fine))
        if p is None:
            p = fd_lookup.get((yd_b, yl_b, f"c_{sc_coarse}", qt_fine))
        if p is None:
            p = fd_lookup.get((yd_b, f"z_{yl_coarse}", sc_fine, qt_fine))
        if p is None:
            p = fd_lookup.get((yd_b, f"zc_{yl_coarse}", f"zc_{sc_coarse}", qt_coarse))
        if p is None:
            p = 0.15  # conservative fallback
        return p

    k_pace = params.get("k_pace", 200)

    # 5R: Pre-compute prior-season full-season values for each (season, team).
    # The prior for week 1 is the team's own prior-season full-season pace/PROE.
    # League mean is the fallback when the team has no prior season data.
    prior_season_vals = {}  # (season, team) -> (proe, pace)
    league_prior = {}       # season -> (lg_proe, lg_pace)
    for season in OUTPUT_SEASONS:
        prior_s = scrimmage_plays[scrimmage_plays["season"] == season - 1]
        if prior_s.empty:
            league_prior[season] = (0.0, 34.0)
            continue
        team_paces = []
        team_proes = []
        for team in prior_s["posteam"].unique():
            tp = prior_s[prior_s["posteam"] == team]
            # PROE: mean pass_oe
            vp = tp[tp["pass_oe"].notna()]
            t_proe = vp["pass_oe"].mean() if len(vp) else 0.0
            # Pace: same neutral-score definition as the weekly builder
            neutral = tp[(tp["score_differential"].abs() <= 8) &
                         (tp["qtr"].isin([1, 2, 3]))]
            t_pace = 34.0  # fallback
            if len(neutral) > 10 and "game_seconds_remaining" in neutral.columns:
                diffs = neutral.sort_values(["game_id", "game_seconds_remaining"],
                                            ascending=[True, False]).groupby(
                    "game_id")["game_seconds_remaining"].diff().abs()
                vd = diffs[(diffs > 5) & (diffs < 60)]
                if len(vd):
                    t_pace = vd.mean()
            prior_season_vals[(season, team)] = (t_proe, t_pace)
            team_paces.append(t_pace)
            team_proes.append(t_proe)
        league_prior[season] = (np.mean(team_proes), np.mean(team_paces))

    rows = []
    for season in OUTPUT_SEASONS:
        ss = scrimmage_plays[scrimmage_plays["season"] == season]
        all_s = all_plays[all_plays["season"] == season]
        lg = get_shrink_target(league_means, season)
        teams, weeks = get_universe(scrimmage_plays, season, team_col="posteam")

        # Legacy lg_4th_go kept for backward compat (unused in engine after 5A-3)
        fourth_all = all_s[
            (all_s["down"] == 4) & (all_s["ydstogo"] <= 2) &
            (all_s["yardline_100"] >= 40) & (all_s["yardline_100"] <= 60) &
            all_s["play_type"].isin(["pass", "run", "punt", "field_goal"])
        ]
        lg_4th_go = fourth_all["play_type"].isin(["pass", "run"]).mean() if len(fourth_all) else 0.5

        lg_proe_prior, lg_pace_prior = league_prior.get(season, (0.0, 34.0))

        for team in teams:
            tp_scrim = ss[ss["posteam"] == team]
            # 5R: team's prior-season values (league mean if no prior season)
            prior_proe, prior_pace = prior_season_vals.get(
                (season, team), (lg_proe_prior, lg_pace_prior))

            for w in weeks:
                avail = tp_scrim[tp_scrim["week"] < w]
                if avail.empty:
                    # 5R: week 1 uses the prior-season value, not hardcoded defaults
                    rows.append({"season": season, "week": w, "team": team,
                                  "proe": prior_proe, "pace_sec": prior_pace,
                                  "fourth_down_go_rate": lg_4th_go,
                                  "fourth_down_goe": 0.0, "n_plays": 0})
                    continue

                # Overall PROE — 5R: shrink toward prior-season PROE (was 0.0)
                valid = avail[avail["pass_oe"].notna()]
                proe = _shrink(valid["pass_oe"].mean(), len(valid), k_t, prior_proe) if len(valid) else prior_proe

                # Pace — 5R: shrink toward prior-season pace (was unshrunk)
                neutral = avail[(avail["score_differential"].abs() <= 8) &
                                (avail["qtr"].isin([1, 2, 3]))]
                if len(neutral) > 10 and "game_seconds_remaining" in neutral.columns:
                    diffs = neutral.sort_values(["game_id", "game_seconds_remaining"],
                                                ascending=[True, False]).groupby(
                        "game_id")["game_seconds_remaining"].diff().abs()
                    vd = diffs[(diffs > 5) & (diffs < 60)]
                    pace = _shrink(vd.mean(), len(vd), k_pace, prior_pace) if len(vd) else prior_pace
                else:
                    pace = prior_pace

                # Legacy fourth_down_go_rate (narrow definition)
                avail_all = all_s[(all_s["week"] < w) & (all_s["posteam"] == team)]
                f4_narrow = avail_all[
                    (avail_all["down"] == 4) & (avail_all["ydstogo"] <= 2) &
                    (avail_all["yardline_100"] >= 40) & (avail_all["yardline_100"] <= 60) &
                    avail_all["play_type"].isin(["pass", "run", "punt", "field_goal"])
                ]
                if len(f4_narrow) >= 2:
                    go_narrow = f4_narrow["play_type"].isin(["pass", "run"]).mean()
                    go_narrow = _shrink(go_narrow, len(f4_narrow), k_t, lg_4th_go)
                else:
                    go_narrow = lg_4th_go

                # 5A-3: Fourth-down GOE over ALL situations
                # For each of the team's 4th-down plays, compute
                # (observed_go - table_expected_go), then average and shrink.
                goe = 0.0
                if fourth_down_table is not None:
                    f4_all = avail_all[
                        (avail_all["down"] == 4) &
                        avail_all["play_type"].isin(["pass", "run", "punt", "field_goal"])
                    ]
                    if len(f4_all) >= 2:
                        observed = f4_all["play_type"].isin(["pass", "run"]).astype(float).values
                        expected = f4_all.apply(_4th_down_expected_go, axis=1).values
                        # GOE in percentage points (like PROE)
                        raw_goe = (observed - expected).mean() * 100.0
                        goe = _shrink(raw_goe, len(f4_all), k_t, 0.0)

                rows.append({"season": season, "week": w, "team": team,
                              "proe": proe, "pace_sec": pace,
                              "fourth_down_go_rate": go_narrow,
                              "fourth_down_goe": goe, "n_plays": len(avail)})
    return pd.DataFrame(rows)


def build_situational_proe(scrimmage_plays, params, league_means):
    """FIX 4: By-bucket PROE. One row per (season, week, team, bucket).
    pass_oe is in nflverse units: percentage points above league expected pass rate."""
    k_t = params.get("k_tendency", 200)
    scrim = scrimmage_plays[scrimmage_plays["down"].notna()].copy()
    scrim["down_b"] = scrim["down"].astype(int).astype(str)
    scrim["dist_b"] = pd.cut(scrim["ydstogo"], bins=[0, 3, 7, 100],
                              labels=["short", "med", "long"], right=True)
    scrim["score_b"] = pd.cut(scrim["score_differential"], bins=[-100, -9, 8, 100],
                               labels=["trail9", "within8", "lead9"])
    scrim["clock_b"] = np.where(scrim["qtr"].isin([1, 2, 3]), "Q1-3", "Q4")
    scrim["bucket"] = (scrim["down_b"] + "_" + scrim["dist_b"].astype(str) + "_" +
                        scrim["score_b"].astype(str) + "_" + scrim["clock_b"])

    rows = []
    for season in OUTPUT_SEASONS:
        ss = scrim[scrim["season"] == season]
        if ss.empty:
            continue
        # FIX 2: shrink target = prior season league PROE by bucket
        prior = scrim[scrim["season"] == season - 1]
        if not prior.empty:
            lg_proe = prior.groupby("bucket")["pass_oe"].mean().to_dict()
        else:
            lg_proe = {}

        teams, weeks = get_universe(scrim, season, team_col="posteam")
        for team in teams:
            tp = ss[ss["posteam"] == team]
            for w in weeks:
                avail = tp[tp["week"] < w]
                if avail.empty:
                    # Prior-only: emit rows for each bucket in the prior
                    for bucket, lg_val in lg_proe.items():
                        rows.append({"season": season, "week": w, "team": team,
                                      "bucket": bucket, "proe": lg_val, "n_plays": 0})
                    continue
                for bucket in avail["bucket"].dropna().unique():
                    bp = avail[(avail["bucket"] == bucket) & avail["pass_oe"].notna()]
                    if bp.empty:
                        continue
                    lg_val = lg_proe.get(bucket, 0.0)
                    val = _shrink(bp["pass_oe"].mean(), len(bp), k_t, lg_val)
                    rows.append({"season": season, "week": w, "team": team,
                                  "bucket": bucket, "proe": val, "n_plays": len(bp)})
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# PIT ASSERTION (FIX 5: real comparison test)
# ═══════════════════════════════════════════════════════════════════════════════

def pit_assertion(game_aggs, all_plays, league_means, params):
    """FIX 5: Build ratings from full data and from truncated data, compare.
    The truncated frame deletes everything from 2024+ and 2023 week >= 10.
    We compare WEEK 9 ratings (which use weeks < 9 = weeks 1-8 from 2023).
    Both the full and truncated builders see identical data for weeks 1-8,
    so the week-9 rating must match exactly. Must match to 1e-9."""
    print("  Running real PIT assertion (FIX 5)...")
    test_season, test_week, test_team = 2023, 9, "KC"

    # Full ratings
    full_ratings = build_team_ratings_fast(game_aggs, league_means, params,
                                           output_seasons=OUTPUT_SEASONS)

    # Truncated: delete season > 2023 and season == 2023 week >= 10
    trunc_plays = all_plays[
        ~((all_plays["season"] > 2023) |
          ((all_plays["season"] == 2023) & (all_plays["week"] >= 10)))
    ].copy()
    trunc_scrimmage = filter_scrimmage(trunc_plays)
    trunc_aggs = build_game_aggs(trunc_scrimmage)
    trunc_league = compute_league_means(trunc_scrimmage)
    trunc_ratings = build_team_ratings_fast(trunc_aggs, trunc_league, params,
                                             output_seasons=[2023])

    # Compare team rating
    full_row = full_ratings[(full_ratings["season"] == test_season) &
                             (full_ratings["week"] == test_week) &
                             (full_ratings["team"] == test_team) &
                             (full_ratings["unit"] == "pass_off")]
    trunc_row = trunc_ratings[(trunc_ratings["season"] == test_season) &
                               (trunc_ratings["week"] == test_week) &
                               (trunc_ratings["team"] == test_team) &
                               (trunc_ratings["unit"] == "pass_off")]
    assert not full_row.empty, f"PIT FAIL: no full row for {test_team} {test_season} wk{test_week} pass_off"
    assert not trunc_row.empty, f"PIT FAIL: no trunc row for {test_team} {test_season} wk{test_week} pass_off"
    for col in ["epa", "success", "explosive", "sack_rate", "int_rate", "n_plays"]:
        if col in full_row.columns:
            fv = float(full_row.iloc[0][col])
            tv = float(trunc_row.iloc[0][col])
            assert abs(fv - tv) < 1e-9, f"PIT FAIL team {col}: full={fv} trunc={tv}"
    print(f"    PASS: team ({test_team} {test_season} wk{test_week} pass_off)")

    # QB
    full_qb, _, _, _ = build_qb_ratings(filter_scrimmage(all_plays), params, league_means)
    trunc_qb, _, _, _ = build_qb_ratings(trunc_scrimmage, params, trunc_league)
    kc_qbs = full_qb[(full_qb["season"] == test_season) & (full_qb["week"] == test_week) &
                       (full_qb["team"] == test_team)]
    if not kc_qbs.empty:
        qb_id = kc_qbs.iloc[0]["passer_player_id"]
        fq = kc_qbs.iloc[0]
        tq = trunc_qb[(trunc_qb["season"] == test_season) & (trunc_qb["week"] == test_week) &
                        (trunc_qb["passer_player_id"] == qb_id)]
        if not tq.empty:
            for col in ["qb_epa", "qb_success", "n_dropbacks"]:
                assert abs(float(fq[col]) - float(tq.iloc[0][col])) < 1e-9, f"PIT FAIL QB {col}"
            print(f"    PASS: QB ({qb_id})")

    # Kicker
    all_typed = all_plays[all_plays["play_type"].isin(
        ["pass", "run", "field_goal", "extra_point", "punt", "kickoff",
         "two_point_attempt", "penalty"])]
    trunc_typed = trunc_plays[trunc_plays["play_type"].isin(
        ["pass", "run", "field_goal", "extra_point", "punt", "kickoff",
         "two_point_attempt", "penalty"])]
    full_kick = build_kicker_ratings(all_typed, params, league_means)
    trunc_kick = build_kicker_ratings(trunc_typed, params, trunc_league)
    fk = full_kick[(full_kick["season"] == test_season) & (full_kick["week"] == test_week)]
    if not fk.empty:
        kid = fk.iloc[0]["kicker_id"]
        fk_row = fk.iloc[0]
        tk = trunc_kick[(trunc_kick["season"] == test_season) & (trunc_kick["week"] == test_week) &
                          (trunc_kick["kicker_id"] == kid)]
        if not tk.empty:
            for col in ["fg_<30", "fg_30-39", "fg_40-49", "fg_50+", "xp_rate"]:
                if col in fk_row.index:
                    assert abs(float(fk_row[col]) - float(tk.iloc[0][col])) < 1e-9, f"PIT FAIL kicker {col}"
            print(f"    PASS: kicker ({kid})")

    # Situational PROE
    full_sit = build_situational_proe(filter_scrimmage(all_plays), params, league_means)
    trunc_sit = build_situational_proe(trunc_scrimmage, params, trunc_league)
    fs = full_sit[(full_sit["season"] == test_season) & (full_sit["week"] == test_week) &
                   (full_sit["team"] == test_team)]
    if not fs.empty:
        bucket = fs.iloc[0]["bucket"]
        fs_row = fs[fs["bucket"] == bucket].iloc[0]
        ts = trunc_sit[(trunc_sit["season"] == test_season) & (trunc_sit["week"] == test_week) &
                         (trunc_sit["team"] == test_team) & (trunc_sit["bucket"] == bucket)]
        if not ts.empty:
            assert abs(float(fs_row["proe"]) - float(ts.iloc[0]["proe"])) < 1e-9, "PIT FAIL sit PROE"
            print(f"    PASS: situational PROE ({test_team} wk{test_week} bucket={bucket})")

    # Also test week 10 (at the truncation boundary)
    full_row10 = full_ratings[(full_ratings["season"] == 2023) & (full_ratings["week"] == 10) &
                               (full_ratings["team"] == "KC") & (full_ratings["unit"] == "pass_off")]
    trunc_ratings10 = build_team_ratings_fast(trunc_aggs, trunc_league, params,
                                              output_seasons=[2023])
    trunc_row10 = trunc_ratings10[(trunc_ratings10["season"] == 2023) & (trunc_ratings10["week"] == 10) &
                                   (trunc_ratings10["team"] == "KC") & (trunc_ratings10["unit"] == "pass_off")]
    if not full_row10.empty and not trunc_row10.empty:
        for col in ["epa", "success", "explosive", "sack_rate", "int_rate", "n_plays"]:
            if col in full_row10.columns:
                fv = float(full_row10.iloc[0][col])
                tv = float(trunc_row10.iloc[0][col])
                assert abs(fv - tv) < 1e-9, f"PIT FAIL team wk10 {col}: full={fv} trunc={tv}"
        print(f"    PASS: team (KC 2023 wk10 pass_off — at truncation boundary)")
    else:
        print(f"    SKIP: wk10 not in output (full_empty={full_row10.empty}, trunc_empty={trunc_row10.empty})")

    print("  PIT ASSERTION: ALL PASSED")


# ═══════════════════════════════════════════════════════════════════════════════
# TUNING (2021-2024 ONLY)
# ═══════════════════════════════════════════════════════════════════════════════

def tune_parameters(game_aggs, league_means, all_plays):
    """Rolling-origin evaluation: each week-w rating predicts that week's
    actual EPA/play using only prior data. 2021-2024 only."""
    for label, df in game_aggs.items():
        if (df["season"] >= 2025).any():
            raise RuntimeError(f"FATAL: {label} has rows with season >= 2025 in tuning")

    db = all_plays[(all_plays["play_type"] == "pass") & (all_plays["season"].isin(TUNE_SEASONS))]
    ru = all_plays[(all_plays["play_type"] == "run") & (all_plays["season"].isin(TUNE_SEASONS))]
    actual_pass = db.groupby(["season", "week", "game_id", "posteam"]).agg(
        actual_epa=("epa", "mean")).reset_index().rename(columns={"posteam": "team"})
    actual_rush = ru.groupby(["season", "week", "game_id", "posteam"]).agg(
        actual_epa=("epa", "mean")).reset_index().rename(columns={"posteam": "team"})

    # Need aggs including 2020 (as prior for 2021) but only evaluate 2021-2024
    tune_aggs = {k: v[v["season"] <= 2024].copy() for k, v in game_aggs.items()}

    grid = []
    for hl in [4, 6, 8, 12, float("inf")]:
        for pw in [0.3, 0.5, 0.7]:
            for kv in [100, 200, 400]:
                params = {"half_life": hl, "prior_weight": pw, "k": kv, "prior_regression": 0.5}
                ratings = build_team_ratings_fast(tune_aggs, league_means, params,
                                                  output_seasons=TUNE_SEASONS)
                pass_r = ratings[ratings["unit"] == "pass_off"][["season", "week", "team", "epa"]]
                rush_r = ratings[ratings["unit"] == "rush_off"][["season", "week", "team", "epa"]]
                pe = pass_r.merge(actual_pass, on=["season", "week", "team"], how="inner")
                re = rush_r.merge(actual_rush, on=["season", "week", "team"], how="inner")
                rmse_pass = np.sqrt(((pe["epa"] - pe["actual_epa"]) ** 2).mean())
                rmse_rush = np.sqrt(((re["epa"] - re["actual_epa"]) ** 2).mean())
                mean_rmse = (rmse_pass + rmse_rush) / 2

                by_season = {}
                for s in TUNE_SEASONS:
                    sp = pe[pe["season"] == s]
                    sr = re[re["season"] == s]
                    by_season[s] = {
                        "pass": np.sqrt(((sp["epa"] - sp["actual_epa"]) ** 2).mean()) if len(sp) else float("inf"),
                        "rush": np.sqrt(((sr["epa"] - sr["actual_epa"]) ** 2).mean()) if len(sr) else float("inf"),
                    }
                    by_season[s]["mean"] = (by_season[s]["pass"] + by_season[s]["rush"]) / 2

                early = pe[pe["week"] <= 4]
                late = pe[pe["week"] > 4]
                grid.append({
                    "half_life": hl, "prior_weight": pw, "k": kv,
                    "mean_rmse": mean_rmse, "rmse_pass": rmse_pass, "rmse_rush": rmse_rush,
                    "by_season": by_season,
                    "rmse_wk1_4": np.sqrt(((early["epa"] - early["actual_epa"]) ** 2).mean()) if len(early) else float("inf"),
                    "rmse_wk5_18": np.sqrt(((late["epa"] - late["actual_epa"]) ** 2).mean()) if len(late) else float("inf"),
                })
                hl_s = "inf" if hl == float("inf") else str(hl)
                print(f"  hl={hl_s:>3s} pw={pw:.1f} k={kv:>3d}  RMSE={mean_rmse:.4f}")

    grid.sort(key=lambda x: x["mean_rmse"])
    best = grid[0]
    # Check if there's an exact tie
    ties = [g for g in grid if abs(g["mean_rmse"] - best["mean_rmse"]) < 1e-6]
    if len(ties) > 1:
        best = sorted(ties, key=lambda x: (-x["k"], -x["prior_weight"]))[0]
        print(f"\nExact tie among {len(ties)} combos; broke toward k={best['k']} pw={best['prior_weight']}")
    print(f"\nBest: hl={best['half_life']} pw={best['prior_weight']} k={best['k']}  "
          f"RMSE={best['mean_rmse']:.4f}")
    return best, grid


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT (FIX 6)
# ═══════════════════════════════════════════════════════════════════════════════

def write_report(params, grid, team_ratings, best, shared_any, shared_lt80, total_tg,
                 actual_pass_sd, rating_sd):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    L = []

    L.append("# Phase 1A: PIT Team Ratings Report\n\n")
    L.append("## PIT Definition\n\n")
    L.append("Rating for (season s, week w) uses plays from season s, weeks < w,\n")
    L.append("plus season s−1 all weeks as a regressed prior. Week 1 = prior only.\n")
    L.append("Shrink target is ALWAYS the s−1 league mean, never the current season's.\n")
    L.append("2020 is the prior for 2021; 2020 ratings are not written or evaluated.\n\n")
    L.append("Assertion test (FIX 5): ratings built from full data vs a frame truncated\n")
    L.append("at 2023 wk 10 match to 1e-9 for team, QB, kicker, and situational PROE.\n\n")

    L.append("## Chosen Parameters\n\n")
    L.append(f"- half_life: {params['half_life']} games\n")
    L.append(f"- prior_weight: {params['prior_weight']}\n")
    L.append(f"- k (shrinkage): {params['k']} plays\n")
    L.append(f"- prior_regression: {params['prior_regression']}\n")
    L.append(f"- Tuned on: 2021–2024 ONLY. No row from 2025 or 2026 touched the tuning.\n\n")

    # RMSE surface description (FIX 6e)
    rmses = [g["mean_rmse"] for g in grid]
    L.append("## Tuning Surface\n\n")
    L.append(f"Rolling-origin evaluation: each week-w rating predicts that week's actual\n")
    L.append(f"EPA/play using only prior data. Same 45-point pre-registered grid.\n\n")
    L.append(f"The RMSE surface is flat (range {min(rmses):.4f}–{max(rmses):.4f}) because\n")
    L.append(f"single-game EPA/play is noise-dominated: SD of actual game pass EPA/play =\n")
    L.append(f"{actual_pass_sd:.3f}, while SD of week-18 pass_off ratings = {rating_sd:.3f}.\n")
    L.append(f"The signal-to-noise ratio is ~{rating_sd/actual_pass_sd:.2f}. The chosen\n")
    L.append(f"parameters are kept as frozen. No row from 2025 or 2026 touched the tuning.\n\n")

    L.append("## Grid Results (sorted by RMSE)\n\n")
    L.append("| half_life | prior_wt | k | mean_RMSE | pass_RMSE | rush_RMSE |\n")
    L.append("|---|---|---|---|---|---|\n")
    for g in sorted(grid, key=lambda x: x["mean_rmse"])[:15]:
        hl = "inf" if g["half_life"] == float("inf") else str(g["half_life"])
        L.append(f"| {hl} | {g['prior_weight']} | {g['k']} | {g['mean_rmse']:.4f} | "
                  f"{g['rmse_pass']:.4f} | {g['rmse_rush']:.4f} |\n")
    L.append("(showing top 15 of 45)\n\n")

    L.append("## RMSE by Season (Check 5)\n\n")
    L.append("| Season | Pass RMSE | Rush RMSE | Mean |\n|---|---|---|---|\n")
    for s, v in sorted(best["by_season"].items()):
        L.append(f"| {s} | {v['pass']:.4f} | {v['rush']:.4f} | {v['mean']:.4f} |\n")
    L.append(f"\nWeeks 1–4 pass RMSE: {best['rmse_wk1_4']:.4f}\n")
    L.append(f"Weeks 5–18 pass RMSE: {best['rmse_wk5_18']:.4f}\n\n")

    # QB caveat (FIX 6b)
    L.append("## Check 1b: QB Caveat\n\n")
    L.append(f"- Team-games with any second passer: {shared_any} / {total_tg} ({shared_any/total_tg*100:.1f}%)\n")
    L.append(f"- Starter changed or shared (primary passer < 80% of dropbacks): {shared_lt80} / {total_tg} ({shared_lt80/total_tg*100:.1f}%)\n\n")

    # FIX 4: situational PROE units
    L.append("## Situational PROE\n\n")
    L.append("pass_oe is in nflverse units: percentage points above league expected pass rate.\n")
    L.append("Buckets: down (1/2/3/4) × distance (short ≤3, med 4–7, long 8+) × score state\n")
    L.append("(trail9+ / within8 / lead9+) × clock (Q1-3 / Q4). Written to\n")
    L.append("`nfl/data/sim/ratings/tendencies_situational_weekly.parquet`.\n\n")

    # Face validity at WEEK 18 (FIX 6c)
    L.append("## Face Validity: Week 18 Ratings (2021–2024)\n\n")
    for season in [2021, 2022, 2023, 2024]:
        sr = team_ratings[(team_ratings["season"] == season) & (team_ratings["week"] == 18)]
        if sr.empty:
            sr = team_ratings[(team_ratings["season"] == season) &
                               (team_ratings["week"] == team_ratings[team_ratings["season"] == season]["week"].max())]
        for unit in ["pass_off", "rush_off", "pass_def", "rush_def"]:
            ur = sr[sr["unit"] == unit].sort_values("epa", ascending=False)
            if ur.empty:
                continue
            if "def" in unit:
                # Defense: lowest EPA = best
                best_label = "Best 5 (lowest EPA allowed)"
                worst_label = "Worst 5 (highest EPA allowed)"
                best5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.tail(5).iloc[::-1].iterrows())
                worst5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.head(5).iterrows())
            else:
                best_label = "Best 5"
                worst_label = "Worst 5"
                best5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.head(5).iterrows())
                worst5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.tail(5).iterrows())
            L.append(f"**{season} {unit} (wk 18):**\n")
            L.append(f"- {best_label}: {best5}\n")
            L.append(f"- {worst_label}: {worst5}\n\n")

    # Distribution
    L.append("## Rating Distributions (week 18)\n\n")
    L.append("| Season | Unit | Mean | SD | Min | Max |\n|---|---|---|---|---|---|\n")
    for season in [2021, 2022, 2023, 2024]:
        sr = team_ratings[(team_ratings["season"] == season) & (team_ratings["week"] == 18)]
        if sr.empty:
            continue
        for unit in ["pass_off", "rush_off", "pass_def", "rush_def"]:
            ur = sr[sr["unit"] == unit]
            if ur.empty:
                continue
            L.append(f"| {season} | {unit} | {ur['epa'].mean():.3f} | {ur['epa'].std():.3f} | "
                      f"{ur['epa'].min():.3f} | {ur['epa'].max():.3f} |\n")

    (REPORT_DIR / "phase1a_ratings_report.md").write_text("".join(L))
    print(f"  Report: {REPORT_DIR / 'phase1a_ratings_report.md'}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("NFL Sim Phase 1A-FIX: Team Ratings")
    print("=" * 60)

    print("\nLoading PBP (2020–2026)...")
    all_plays = load_all_pbp()
    scrimmage = filter_scrimmage(all_plays)
    print(f"  {len(all_plays):,} total plays, {len(scrimmage):,} scrimmage")

    print("\nBuilding per-game aggregates...")
    game_aggs = build_game_aggs(scrimmage)
    for k, v in game_aggs.items():
        print(f"  {k}: {len(v):,} team-game rows")

    print("\nComputing league baselines...")
    league_means = compute_league_means(scrimmage)
    for s, m in sorted(league_means.items()):
        print(f"  {s}: pass_epa={m.get('pass_epa',0):.3f} rush_epa={m.get('rush_epa',0):.3f}")

    # Tune on 2021-2024
    print("\nTuning (2021-2024, 45 grid points, shrink targets = s-1 league mean)...")
    tune_aggs = {k: v[v["season"] <= 2024].copy() for k, v in game_aggs.items()}
    best, grid = tune_parameters(tune_aggs, league_means, scrimmage)

    # Get git sha
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                       text=True).strip()
    except Exception:
        sha = "unknown"

    params = {
        "half_life": best["half_life"],
        "prior_weight": best["prior_weight"],
        "k": best["k"],
        "prior_regression": 0.5,
        "k_qb": best["k"],
        "k_kicker": 50,
        "k_tendency": 200,
        "k_pace": 200,
        "tuned_on": "2021-2024",
        "holdout": "2025",
        "built_at_parent_commit": sha,
        "grid_results": [{
            "half_life": g["half_life"], "prior_weight": g["prior_weight"],
            "k": g["k"], "mean_rmse": g["mean_rmse"],
            "rmse_pass": g["rmse_pass"], "rmse_rush": g["rmse_rush"],
        } for g in sorted(grid, key=lambda x: x["mean_rmse"])],
    }
    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARAMS_PATH, "w") as f:
        json.dump(params, f, indent=2, default=str)
    print(f"\nParams: {PARAMS_PATH}")

    # PIT assertion (FIX 5)
    print("\nPIT assertion (FIX 5)...")
    pit_assertion(game_aggs, all_plays, league_means, params)

    # Build all ratings
    print("\nBuilding team ratings (2021–2026)...")
    team_ratings = build_team_ratings_fast(game_aggs, league_means, params,
                                           output_seasons=OUTPUT_SEASONS)
    print(f"  {len(team_ratings):,} rows")

    # Universe assertions
    for s in OUTPUT_SEASONS:
        sr = team_ratings[team_ratings["season"] == s]
        n_teams = sr["team"].nunique()
        assert n_teams == 32, f"FAIL: {s} has {n_teams} teams, expected 32"
    s26 = team_ratings[team_ratings["season"] == 2026]
    assert 1 in s26["week"].values and 2 in s26["week"].values, "FAIL: 2026 missing wk1 or wk2"
    print(f"  Universe assertions: all seasons 32 teams, 2026 has wk1+wk2 ✓")
    for s in OUTPUT_SEASONS:
        sr = team_ratings[team_ratings["season"] == s]
        wks = sorted(sr["week"].unique())
        print(f"    {s}: {sr['team'].nunique()} teams × {len(wks)} weeks ({min(wks)}-{max(wks)})")

    # Identity check against old ratings
    old_path = Path("/tmp/team_ratings_old.parquet")
    if old_path.exists():
        old = pd.read_parquet(old_path)
        # Compare rows that exist in both (same season, week, team, unit)
        merge_cols = ["season", "week", "team", "unit"]
        num_cols = [c for c in old.columns if c not in merge_cols]
        merged = old.merge(team_ratings, on=merge_cols, suffixes=("_old", "_new"), how="inner")
        n_compared = len(merged)
        mismatches = 0
        for col in num_cols:
            old_col = f"{col}_old"
            new_col = f"{col}_new"
            if old_col in merged.columns and new_col in merged.columns:
                diff = (merged[old_col] - merged[new_col]).abs()
                bad = diff[diff > 1e-9]
                if len(bad) > 0:
                    mismatches += len(bad)
                    print(f"  IDENTITY MISMATCH: {col} has {len(bad)} rows differing > 1e-9")
        if mismatches > 0:
            print(f"  FAIL: {mismatches} total mismatches against old ratings")
            sys.exit(1)
        print(f"  Identity check: {n_compared} old rows match new to 1e-9 ✓")
    else:
        print(f"  Identity check: SKIP (no old file at /tmp/team_ratings_old.parquet)")

    # FIX 3: verify 2021 wk1 pass_off ratings are NOT all identical
    wk1_2021 = team_ratings[(team_ratings["season"] == 2021) & (team_ratings["week"] == 1) &
                             (team_ratings["unit"] == "pass_off")]
    assert wk1_2021["epa"].std() > 0, "FAIL: 2021 week-1 pass_off ratings are all identical (no 2020 prior)"
    print(f"  FIX 3 check: 2021 wk1 pass_off sd={wk1_2021['epa'].std():.4f} > 0 ✓")

    print("\nBuilding QB ratings...")
    qb_ratings, shared_any, shared_lt80, total_tg = build_qb_ratings(scrimmage, params, league_means)
    print(f"  {len(qb_ratings):,} rows")
    print(f"  Any second passer: {shared_any}/{total_tg} ({shared_any/total_tg*100:.1f}%)")
    print(f"  Primary < 80% dropbacks: {shared_lt80}/{total_tg} ({shared_lt80/total_tg*100:.1f}%)")

    print("\nBuilding kicker ratings...")
    all_with_types = all_plays[all_plays["play_type"].isin(
        ["pass", "run", "field_goal", "extra_point", "punt", "kickoff",
         "two_point_attempt", "penalty"])]
    kicker = build_kicker_ratings(all_with_types, params, league_means)
    print(f"  {len(kicker):,} rows")

    # 5A-3: load fourth_down table for GOE computation
    fd_tbl_path = ROOT / "nfl" / "data" / "sim" / "tables" / "fourth_down.parquet"
    fd_tbl = pd.read_parquet(fd_tbl_path) if fd_tbl_path.exists() else None
    print(f"\nBuilding tendencies (GOE from {len(fd_tbl) if fd_tbl is not None else 0} 4th-down table rows)...")
    tend = build_tendencies(scrimmage, all_plays, params, league_means,
                            fourth_down_table=fd_tbl)
    print(f"  {len(tend):,} rows")

    # FIX 1 assertion: 4th-down go rate
    go_rates = tend[tend["season"].isin([2021, 2022, 2023, 2024]) & (tend["week"] == 18)]
    go_std = go_rates["fourth_down_go_rate"].std()
    go_mean = go_rates["fourth_down_go_rate"].mean()
    print(f"  FIX 1 check: 4th-down go rate wk18 2021-24: mean={go_mean:.3f} sd={go_std:.3f}")
    assert go_std > 0, "FAIL: fourth_down_go_rate sd == 0 (still all identical)"
    assert 0.30 <= go_mean <= 0.90, f"FAIL: fourth_down_go_rate mean {go_mean} outside [0.30, 0.90]"
    print(f"    Assertions passed: sd > 0, mean in [0.30, 0.90] ✓")

    print("\nBuilding situational PROE (FIX 4)...")
    sit_proe = build_situational_proe(scrimmage, params, league_means)
    print(f"  {len(sit_proe):,} rows")

    # Save all
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    team_ratings.to_parquet(OUT_DIR / "team_ratings_weekly.parquet", index=False)
    qb_ratings.to_parquet(OUT_DIR / "qb_ratings_weekly.parquet", index=False)
    if not kicker.empty:
        kicker.to_parquet(OUT_DIR / "kicker_weekly.parquet", index=False)
    tend.to_parquet(OUT_DIR / "tendencies_weekly.parquet", index=False)
    sit_proe.to_parquet(OUT_DIR / "tendencies_situational_weekly.parquet", index=False)
    lg_df = pd.DataFrame([{"season": s, **m} for s, m in league_means.items()])
    lg_df.to_parquet(OUT_DIR / "league_baselines.parquet", index=False)
    print(f"\nOutputs: {OUT_DIR}/")

    # Compute stats for report
    actual_game_epa = scrimmage[scrimmage["season"].isin(TUNE_SEASONS)].groupby(
        ["season", "week", "game_id", "posteam"])["epa"].mean()
    actual_pass_sd = actual_game_epa.std()
    wk18_pass = team_ratings[(team_ratings["week"] == 18) &
                              (team_ratings["season"].isin(TUNE_SEASONS)) &
                              (team_ratings["unit"] == "pass_off")]
    rating_sd = wk18_pass["epa"].std()

    # Face validity
    print("\n" + "=" * 60)
    print("FACE VALIDITY (2024, week 18)")
    print("=" * 60)
    sr = team_ratings[(team_ratings["season"] == 2024) & (team_ratings["week"] == 18)]
    for unit in ["pass_off", "pass_def", "rush_off", "rush_def"]:
        ur = sr[sr["unit"] == unit].sort_values("epa", ascending=False)
        if ur.empty:
            continue
        if "def" in unit:
            best5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.tail(5).iloc[::-1].iterrows())
            worst5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.head(5).iterrows())
            print(f"  {unit}:")
            print(f"    Best 5 (lowest EPA allowed): {best5}")
            print(f"    Worst 5 (highest EPA allowed): {worst5}")
        else:
            top5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.head(5).iterrows())
            bot5 = ", ".join(f"{r['team']} ({r['epa']:.3f})" for _, r in ur.tail(5).iterrows())
            print(f"  {unit}:")
            print(f"    Best 5: {top5}")
            print(f"    Worst 5: {bot5}")

    write_report(params, grid, team_ratings, best, shared_any, shared_lt80, total_tg,
                 actual_pass_sd, rating_sd)
    print("\nPhase 1A-FIX complete.")


if __name__ == "__main__":
    main()
