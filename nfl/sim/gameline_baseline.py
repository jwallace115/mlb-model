#!/usr/bin/env python3
"""
NFL game-line statistical baseline — ridge regression on EPA/success ratings + QB.

Uses ONLY the per-game team aggregates that ratings.build_game_aggs already produces
(pass/rush EPA and success, offence and defence) plus the QB rating from
build_qb_ratings. No new features.

For a game in season s, week w, every feature uses games with
(season < s) or (season == s and week < w) — week-level as-of.

Prior-season carry-in uses the existing prior_regression / prior_weight mechanism
from ratings.py. One exponential decay parameter `hl_games` is the ONLY structural
choice, chosen on 2021-23 by leave-one-season-out log-loss on the margin model.

Model: ridge regression of actual margin on
  (home_off − away_def, away_off − home_def) pass/rush terms + QB diff + home field;
totals model on the sums.

Decision: G2 (structure + hl_games value + why).
"""

import json, os, sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from scipy.special import expit  # for log-loss

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = Path(os.environ.get("NFL_PBP_DIR", str(ROOT / "nfl" / "data" / "pbp")))
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"

ALLOWED_SEASONS = [2021, 2022, 2023]  # GL1 standing rule


def _load_params():
    with open(PARAMS_PATH) as f:
        return json.load(f)


def _shrink(x, n, k, mu):
    return (n * x + k * mu) / (n + k)


def _load_pbp(seasons):
    """Load PBP and game schedule for the requested seasons + prior season.

    HALTs (raises FileNotFoundError) if any required PBP file is missing.
    """
    all_seasons = sorted(set([s - 1 for s in seasons] + list(seasons)))
    frames = []
    for s in all_seasons:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if not p.exists():
            raise FileNotFoundError(
                f"HALT: required PBP file missing: {p}\n"
                f"Set NFL_PBP_DIR env var or ensure the file exists."
            )
        frames.append(pd.read_parquet(p))
    plays = pd.concat(frames, ignore_index=True)
    return plays


def _build_game_aggs(plays):
    """Replicate ratings.build_game_aggs — per-team-per-game stats."""
    db = plays[plays["play_type"] == "pass"].copy()
    ru = plays[plays["play_type"] == "run"].copy()

    def _pass_agg(df, team_col):
        return df.groupby(["season", "week", "game_id", team_col]).apply(
            lambda g: pd.Series({
                "pass_epa_sum": g["epa"].sum(), "pass_n": len(g),
                "pass_success_sum": g["success"].sum(),
            }), include_groups=False
        ).reset_index().rename(columns={team_col: "team"})

    def _rush_agg(df, team_col):
        return df.groupby(["season", "week", "game_id", team_col]).apply(
            lambda g: pd.Series({
                "rush_epa_sum": g["epa"].sum(), "rush_n": len(g),
                "rush_success_sum": g["success"].sum(),
            }), include_groups=False
        ).reset_index().rename(columns={team_col: "team"})

    return {
        "pass_off": _pass_agg(db, "posteam"), "pass_def": _pass_agg(db, "defteam"),
        "rush_off": _rush_agg(ru, "posteam"), "rush_def": _rush_agg(ru, "defteam"),
    }


def _build_qb_game_aggs(plays):
    """Per-game QB EPA aggregates."""
    db = plays[plays["play_type"] == "pass"].copy()
    return db.groupby(["season", "week", "game_id", "passer_player_id", "posteam"]).apply(
        lambda g: pd.Series({"epa_sum": g["epa"].sum(), "n": len(g),
                              "success_sum": g["success"].sum()}),
        include_groups=False
    ).reset_index().rename(columns={"posteam": "team"})


def _compute_league_means(plays):
    """League means per season for shrink targets (prior season's means)."""
    results = {}
    for season in sorted(plays["season"].unique()):
        sp = plays[plays["season"] == season]
        db = sp[sp["play_type"] == "pass"]
        ru = sp[sp["play_type"] == "run"]
        m = {}
        if len(db):
            m["pass_epa"] = db["epa"].mean()
            m["pass_success"] = db["success"].mean()
        if len(ru):
            m["rush_epa"] = ru["epa"].mean()
            m["rush_success"] = ru["success"].mean()
        results[season] = m
    return results


def _get_shrink_target(league_means, season):
    if season - 1 in league_means:
        return league_means[season - 1]
    earliest = min(league_means.keys())
    return league_means[earliest]


def _build_team_rating_as_of(game_aggs, league_means, season, week, team,
                              hl_games, k, prior_weight, prior_regression):
    """Build point-in-time team rating for (season, week, team).

    Returns dict with keys: pass_off_epa, pass_off_success, pass_def_epa, pass_def_success,
                            rush_off_epa, rush_off_success, rush_def_epa, rush_def_success
    """
    lg = _get_shrink_target(league_means, season)
    result = {}

    for unit_label, agg_df in game_aggs.items():
        side = unit_label.split("_")[1]  # "off" or "def"
        prefix = unit_label.split("_")[0]  # "pass" or "rush"

        # Current-season games before this week
        curr = agg_df[(agg_df["season"] == season) & (agg_df["week"] < week) &
                      (agg_df["team"] == team)].sort_values("week")

        for stat_name, sum_col, rate_name in [
            ("epa", f"{prefix}_epa_sum", f"{prefix}_epa"),
            ("success", f"{prefix}_success_sum", f"{prefix}_success"),
        ]:
            n_col = f"{prefix}_n"
            lg_val = lg.get(rate_name, 0.0)

            if not curr.empty:
                n_arr = curr[n_col].values
                rates = curr[sum_col].values / np.maximum(n_arr, 1)
                n_games = len(curr)
                games_ago = np.arange(n_games - 1, -1, -1, dtype=float)
                if hl_games and hl_games != float("inf") and hl_games > 0:
                    w_arr = 0.5 ** (games_ago / hl_games)
                else:
                    w_arr = np.ones(n_games)
                weighted_n = (n_arr * w_arr).sum()
                wm = np.average(rates, weights=w_arr * n_arr)
                shrunk = _shrink(wm, weighted_n, k, lg_val)
            else:
                shrunk = lg_val
                weighted_n = 0.0

            # Prior-season component
            prior_agg = agg_df[(agg_df["season"] == season - 1) & (agg_df["team"] == team)]
            if not prior_agg.empty:
                prior_rate = prior_agg[sum_col].sum() / max(prior_agg[n_col].sum(), 1)
            else:
                prior_rate = lg_val
            regressed_prior = prior_regression * prior_rate + (1 - prior_regression) * lg_val

            if weighted_n > 0:
                blended = (1 - prior_weight) * shrunk + prior_weight * regressed_prior
            else:
                blended = regressed_prior

            result[f"{prefix}_{side}_{stat_name}"] = blended

    return result


def _build_qb_rating_as_of(qb_aggs, league_means, season, week, team,
                            hl_games, k_qb):
    """Build point-in-time QB rating for the primary QB of (season, week, team).

    Returns qb_epa (float). Uses the QB with the most dropbacks on this team
    in games before this week in this season (or prior season if week 1).
    """
    lg = _get_shrink_target(league_means, season)
    lg_epa = lg.get("pass_epa", 0.0)

    # Current-season QB data for this team before this week
    curr = qb_aggs[(qb_aggs["season"] == season) & (qb_aggs["week"] < week) &
                   (qb_aggs["team"] == team)]

    if curr.empty:
        # Fall back to prior season
        curr = qb_aggs[(qb_aggs["season"] == season - 1) & (qb_aggs["team"] == team)]

    if curr.empty:
        return lg_epa

    # Primary QB = most dropbacks
    qb_totals = curr.groupby("passer_player_id")["n"].sum()
    primary_qb = qb_totals.idxmax()
    qp = curr[curr["passer_player_id"] == primary_qb].sort_values("week")

    if qp.empty:
        return lg_epa

    n_arr = qp["n"].values
    rates = qp["epa_sum"].values / np.maximum(n_arr, 1)
    n_games = len(qp)
    games_ago = np.arange(n_games - 1, -1, -1, dtype=float)
    if hl_games and hl_games != float("inf") and hl_games > 0:
        w_arr = 0.5 ** (games_ago / hl_games)
    else:
        w_arr = np.ones(n_games)
    weighted_n = (n_arr * w_arr).sum()
    wm = np.average(rates, weights=w_arr * n_arr)
    return _shrink(wm, weighted_n, k_qb, lg_epa)


def build_feature_row(game_aggs, qb_aggs, league_means, season, week,
                      home_team, away_team, hl_games, k, k_qb,
                      prior_weight, prior_regression):
    """Build one feature row for a game.

    Features (margin model):
      home_pass_off_epa - away_pass_def_epa    (home passing advantage)
      away_pass_off_epa - home_pass_def_epa    (away passing advantage)
      home_rush_off_epa - away_rush_def_epa    (home rushing advantage)
      away_rush_off_epa - home_rush_def_epa    (away rushing advantage)
      same for success rate
      qb_diff = home_qb_epa - away_qb_epa
      home_field = 1.0

    Features (total model): sums instead of differences, no home field.
    """
    home_r = _build_team_rating_as_of(game_aggs, league_means, season, week,
                                       home_team, hl_games, k, prior_weight, prior_regression)
    away_r = _build_team_rating_as_of(game_aggs, league_means, season, week,
                                       away_team, hl_games, k, prior_weight, prior_regression)
    home_qb = _build_qb_rating_as_of(qb_aggs, league_means, season, week,
                                      home_team, hl_games, k_qb)
    away_qb = _build_qb_rating_as_of(qb_aggs, league_means, season, week,
                                      away_team, hl_games, k_qb)

    # Margin features: (home_off - away_def) and (away_off - home_def)
    margin_features = {
        "pass_epa_home_adv": home_r["pass_off_epa"] - away_r["pass_def_epa"],
        "pass_epa_away_adv": away_r["pass_off_epa"] - home_r["pass_def_epa"],
        "rush_epa_home_adv": home_r["rush_off_epa"] - away_r["rush_def_epa"],
        "rush_epa_away_adv": away_r["rush_off_epa"] - home_r["rush_def_epa"],
        "pass_success_home_adv": home_r["pass_off_success"] - away_r["pass_def_success"],
        "pass_success_away_adv": away_r["pass_off_success"] - home_r["pass_def_success"],
        "rush_success_home_adv": home_r["rush_off_success"] - away_r["rush_def_success"],
        "rush_success_away_adv": away_r["rush_off_success"] - home_r["rush_def_success"],
        "qb_diff": home_qb - away_qb,
        "home_field": 1.0,
    }

    # Total features: sums
    total_features = {
        "pass_epa_sum": (home_r["pass_off_epa"] - away_r["pass_def_epa"]) +
                        (away_r["pass_off_epa"] - home_r["pass_def_epa"]),
        "rush_epa_sum": (home_r["rush_off_epa"] - away_r["rush_def_epa"]) +
                        (away_r["rush_off_epa"] - home_r["rush_def_epa"]),
        "pass_success_sum": (home_r["pass_off_success"] - away_r["pass_def_success"]) +
                            (away_r["pass_off_success"] - home_r["pass_def_success"]),
        "rush_success_sum": (home_r["rush_off_success"] - away_r["rush_def_success"]) +
                            (away_r["rush_off_success"] - home_r["rush_def_success"]),
        "qb_sum": home_qb + away_qb,
    }

    return margin_features, total_features


def build_dataset(seasons, hl_games, pbp_dir=None):
    """Build the full feature matrix + targets for the given seasons.

    Returns (df, margin_cols, total_cols) where df has columns:
      game_id, season, week, home_team, away_team,
      actual_m, actual_t, mkt_m, mkt_t,
      <margin_features>, <total_features>
    """
    if pbp_dir is not None:
        global PBP_DIR
        PBP_DIR = Path(pbp_dir)

    params = _load_params()
    k = params["k"]
    k_qb = params.get("k_qb", k)
    prior_weight = params["prior_weight"]
    prior_regression = params.get("prior_regression", 0.5)

    plays = _load_pbp(seasons)
    game_aggs = _build_game_aggs(plays)
    qb_aggs = _build_qb_game_aggs(plays)
    league_means = _compute_league_means(plays)

    # Game schedule
    rows = []
    for s in seasons:
        pbp_path = PBP_DIR / f"pbp_{s}.parquet"
        df = pd.read_parquet(pbp_path,
            columns=["game_id", "season", "week", "home_team", "away_team",
                     "home_score", "away_score", "spread_line", "total_line"])
        g = df.drop_duplicates("game_id")
        g = g[(g["week"] <= 18) & g["spread_line"].notna() & g["total_line"].notna()]

        for _, row in g.iterrows():
            mf, tf = build_feature_row(
                game_aggs, qb_aggs, league_means,
                int(row["season"]), int(row["week"]),
                row["home_team"], row["away_team"],
                hl_games, k, k_qb, prior_weight, prior_regression)
            r = {
                "game_id": row["game_id"],
                "season": int(row["season"]),
                "week": int(row["week"]),
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "actual_m": float(row["home_score"] - row["away_score"]),
                "actual_t": float(row["home_score"] + row["away_score"]),
                "mkt_m": float(row["spread_line"]),
                "mkt_t": float(row["total_line"]),
            }
            r.update({f"m_{fk}": v for fk, v in mf.items()})
            r.update({f"t_{fk}": v for fk, v in tf.items()})
            rows.append(r)

    df = pd.DataFrame(rows)

    margin_cols = [c for c in df.columns if c.startswith("m_")]
    total_cols = [c for c in df.columns if c.startswith("t_")]

    return df, margin_cols, total_cols


def fit_baseline(seasons, hl_games, alpha=1.0, pbp_dir=None):
    """Fit ridge regression baseline on the given seasons.

    Returns (margin_model, total_model, df, margin_cols, total_cols, residual_sd_m, residual_sd_t)
    """
    df, margin_cols, total_cols = build_dataset(seasons, hl_games, pbp_dir=pbp_dir)

    X_m = df[margin_cols].values
    y_m = df["actual_m"].values
    margin_model = Ridge(alpha=alpha, fit_intercept=True)
    margin_model.fit(X_m, y_m)

    X_t = df[total_cols].values
    y_t = df["actual_t"].values
    total_model = Ridge(alpha=alpha, fit_intercept=True)
    total_model.fit(X_t, y_t)

    resid_m = y_m - margin_model.predict(X_m)
    resid_t = y_t - total_model.predict(X_t)

    return (margin_model, total_model, df, margin_cols, total_cols,
            resid_m.std(), resid_t.std())


def predict_baseline(df_row, margin_model, total_model, margin_cols, total_cols):
    """Predict margin and total for a single game row.

    Returns (mean_margin, mean_total, residual_sd_margin, residual_sd_total).
    Note: residual SDs are from the training fit; per-game SD is not estimated here.
    """
    X_m = df_row[margin_cols].values.reshape(1, -1)
    X_t = df_row[total_cols].values.reshape(1, -1)
    return float(margin_model.predict(X_m)[0]), float(total_model.predict(X_t)[0])


def log_loss_binary(p, y):
    """Binary log-loss, clipped to avoid infinities."""
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


def loo_season_cv(seasons, hl_values, alpha=1.0, pbp_dir=None):
    """Leave-one-season-out cross-validation on margin log-loss.

    For each hl_games value, for each held-out season, fit on the remaining
    seasons and score on the held-out season.

    Returns list of (hl_games, mean_log_loss, per_season_log_losses).
    """
    results = []
    for hl in hl_values:
        full_df, m_cols, t_cols = build_dataset(seasons, hl, pbp_dir=pbp_dir)
        season_losses = []
        for hold_s in seasons:
            train_df = full_df[full_df["season"] != hold_s]
            hold_df = full_df[full_df["season"] == hold_s]

            X_train = train_df[m_cols].values
            y_train = train_df["actual_m"].values
            mm_cv = Ridge(alpha=alpha, fit_intercept=True)
            mm_cv.fit(X_train, y_train)

            X_hold = hold_df[m_cols].values
            y_hold = hold_df["actual_m"].values
            pred = mm_cv.predict(X_hold)
            sd = (y_train - mm_cv.predict(X_train)).std()

            actual_hw = (y_hold > 0).astype(float)
            p_hw = expit(pred / sd)
            ll = log_loss_binary(p_hw, actual_hw)
            season_losses.append(ll)

        results.append((hl, np.mean(season_losses), season_losses))
    return results


if __name__ == "__main__":
    # Search for optimal hl_games on 2021-23
    hl_values = [4, 8, 12, 16, 24, 32, 48, 64, 128, float("inf")]
    print("Leave-one-season-out CV for hl_games on 2021-23:")
    print(f"{'hl':>6}  {'mean_ll':>10}  {'2021':>8}  {'2022':>8}  {'2023':>8}")
    results = loo_season_cv([2021, 2022, 2023], hl_values, alpha=1.0)
    for hl, mean_ll, per_s in results:
        hl_str = f"{hl:.0f}" if hl != float("inf") else "inf"
        print(f"{hl_str:>6}  {mean_ll:>10.5f}  {per_s[0]:>8.5f}  {per_s[1]:>8.5f}  {per_s[2]:>8.5f}")

    best_hl, best_ll, _ = min(results, key=lambda x: x[1])
    print(f"\nBest hl_games = {best_hl}, log-loss = {best_ll:.5f}")
