#!/usr/bin/env python3
"""
NFL Feature table builder (Phase 1 + Phase 3 features).

Phase 1: Rolling points scored/allowed, weather, rest, dome, neutral site
Phase 3: Pace (plays per game), SOS (opponent quality), market residual

All rolling windows: season-bounded, shift(1) to prevent leakage.
Training uses regular season only.

Output: nfl/data/nfl_feature_table.parquet
"""

import json
import logging
import os
import pickle

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NFL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(NFL_DIR, "data")
MODELS_DIR = os.path.join(NFL_DIR, "models")
CANONICAL_PATH = os.path.join(DATA_DIR, "nfl_canonical.parquet")
PLAYS_PATH = os.path.join(DATA_DIR, "plays_per_game.parquet")
FEATURE_PATH = os.path.join(DATA_DIR, "nfl_feature_table.parquet")

ROLLING_WINDOW = 6


def compute_rolling(df: pd.DataFrame, team_col: str, score_col: str,
                    opp_score_col: str, prefix: str) -> pd.DataFrame:
    """Compute rolling stats per team per season, shifted by 1 to prevent leakage."""
    frames = []
    for (season,), group in df.groupby(["season"]):
        team_games = group.sort_values("date")
        for team in team_games[team_col].unique():
            mask = team_games[team_col] == team
            tg = team_games[mask].copy()
            tg[f"{prefix}_pts_scored_rolling"] = (
                tg[score_col].shift(1)
                .rolling(ROLLING_WINDOW, min_periods=1).mean()
            )
            tg[f"{prefix}_pts_allowed_rolling"] = (
                tg[opp_score_col].shift(1)
                .rolling(ROLLING_WINDOW, min_periods=1).mean()
            )
            frames.append(tg[["game_id", f"{prefix}_pts_scored_rolling",
                              f"{prefix}_pts_allowed_rolling"]])
    return pd.concat(frames, ignore_index=True)


def compute_pace_rolling(canon: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling plays-per-game from PBP data (Phase 3 feature)."""
    if not os.path.exists(PLAYS_PATH):
        logger.warning("plays_per_game.parquet not found — pace features skipped")
        return pd.DataFrame()

    ppg = pd.read_parquet(PLAYS_PATH)

    # Build a team-game lookup: for each game_id + team, get plays
    # Need to map to canonical's home_team/away_team
    frames = []
    for side, team_col in [("home", "home_team"), ("away", "away_team")]:
        merged = canon[["game_id", "season", "date", team_col]].merge(
            ppg.rename(columns={"posteam": team_col}),
            on=["game_id", team_col, "season"],
            how="left",
        )
        # Rolling pace per team per season, shifted
        result_frames = []
        for (season,), group in merged.groupby(["season"]):
            for team in group[team_col].unique():
                mask = group[team_col] == team
                tg = group[mask].sort_values("date").copy()
                tg[f"{side}_plays_rolling"] = (
                    tg["plays"].shift(1)
                    .rolling(ROLLING_WINDOW, min_periods=1).mean()
                )
                result_frames.append(tg[["game_id", f"{side}_plays_rolling"]])
        frames.append(pd.concat(result_frames, ignore_index=True))

    home_pace = frames[0]
    away_pace = frames[1]
    return home_pace, away_pace


def compute_sos_rolling(canon: pd.DataFrame) -> pd.DataFrame:
    """Compute strength-of-schedule: avg pts_allowed of recent opponents (Phase 3)."""
    # For each team-game, find the opponents they faced in their last 6 games,
    # then average those opponents' pts_allowed_rolling

    # First build a lookup: team → season-ordered list of (game_id, opponent, opp_pts_allowed)
    # We need each team's opponents and those opponents' defensive quality

    # Build per-team game log
    home_log = canon[["game_id", "date", "season", "home_team", "away_team", "away_score"]].rename(
        columns={"home_team": "team", "away_team": "opponent", "away_score": "opp_score_for"}
    )
    # For home team, opponent's "pts allowed" in that game = home_score (what home scored against them)
    home_log["pts_scored_vs_opp"] = canon["home_score"]

    away_log = canon[["game_id", "date", "season", "away_team", "home_team", "home_score"]].rename(
        columns={"away_team": "team", "home_team": "opponent", "home_score": "opp_score_for"}
    )
    away_log["pts_scored_vs_opp"] = canon["away_score"]

    team_log = pd.concat([home_log, away_log], ignore_index=True).sort_values(["season", "date"])

    # For each team, compute rolling avg of opponents' season-average pts allowed
    # Step 1: For each team-season, compute their season-average pts allowed so far
    # (this is the "opponent quality" metric)
    team_log_with_def = team_log.copy()

    # Build opponent defensive quality: for each opponent in each season,
    # what's their avg pts allowed per game up to that point?
    opp_def = []
    for (season,), group in team_log.groupby(["season"]):
        for team in group["team"].unique():
            mask = group["team"] == team
            tg = group[mask].sort_values("date").copy()
            # pts the opponent scored against this team = opp_score_for
            # But we want: how many pts does this team's defense allow on average?
            # That's opp_score_for for games where this team is the one playing
            tg["team_def_avg"] = tg["opp_score_for"].shift(1).expanding().mean()
            opp_def.append(tg[["game_id", "team", "team_def_avg"]])

    opp_def_df = pd.concat(opp_def, ignore_index=True)

    # Now for each game, get the opponent's defensive quality
    # and compute rolling avg of opponent defensive quality
    frames = []
    for side, team_col, opp_col in [("home", "home_team", "away_team"),
                                     ("away", "away_team", "home_team")]:
        # For each game, the opponent is opp_col
        # Get opponent's defensive avg (how many pts they allow)
        game_opp = canon[["game_id", "season", "date", team_col, opp_col]].copy()
        game_opp = game_opp.merge(
            opp_def_df.rename(columns={"team": opp_col, "team_def_avg": "opp_def_quality"}),
            on=["game_id", opp_col],
            how="left",
        )

        # Rolling avg of opp_def_quality per team per season
        result_frames = []
        for (season,), group in game_opp.groupby(["season"]):
            for team in group[team_col].unique():
                mask = group[team_col] == team
                tg = group[mask].sort_values("date").copy()
                tg[f"{side}_opp_def_quality_rolling"] = (
                    tg["opp_def_quality"].shift(1)
                    .rolling(ROLLING_WINDOW, min_periods=1).mean()
                )
                result_frames.append(tg[["game_id", f"{side}_opp_def_quality_rolling"]])
        frames.append(pd.concat(result_frames, ignore_index=True))

    return frames[0], frames[1]


def compute_market_residual(ft: pd.DataFrame) -> pd.DataFrame:
    """Compute market residual = closing_line - Phase1 model projection (Phase 3)."""
    # Load Phase 1 model to get projections
    ridge_path = os.path.join(MODELS_DIR, "ridge_model.pkl")
    scaler_path = os.path.join(MODELS_DIR, "scaler.pkl")
    impute_path = os.path.join(MODELS_DIR, "impute_vals.json")

    if not all(os.path.exists(p) for p in [ridge_path, scaler_path, impute_path]):
        logger.warning("Phase 1 model files not found — market residual skipped")
        return ft

    with open(ridge_path, "rb") as f:
        ridge = pickle.load(f)
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
    with open(impute_path) as f:
        impute_vals = json.load(f)

    PHASE1_FEATURES = [
        "home_pts_scored_rolling", "home_pts_allowed_rolling",
        "away_pts_scored_rolling", "away_pts_allowed_rolling",
        "is_dome_f", "wind_for_feature", "temp_for_feature",
        "wind_bucket", "neutral_site_f",
        "home_rest_days", "away_rest_days", "rest_advantage",
        "is_short_week_home", "is_short_week_away",
    ]

    # Impute
    df = ft.copy()
    for col, v in impute_vals.items():
        if col in df.columns:
            df[col] = df[col].fillna(v)

    # Predict with Phase 1 model
    X = df[PHASE1_FEATURES].fillna(0).values
    X_s = scaler.transform(X)
    df["phase1_projection"] = ridge.predict(X_s)

    # Market residual = closing line - model projection
    df["market_residual"] = df["closing_total_line"] - df["phase1_projection"]

    return df


def build_features():
    canon = pd.read_parquet(CANONICAL_PATH)
    logger.info(f"Canonical: {len(canon)} rows")

    # ── Phase 1 features ──────────────────────────────────────────────
    home_roll = compute_rolling(canon, "home_team", "home_score", "away_score", "home")
    away_roll = compute_rolling(canon, "away_team", "away_score", "home_score", "away")

    ft = canon.merge(home_roll, on="game_id", how="left")
    ft = ft.merge(away_roll, on="game_id", how="left")

    ft["wind_for_feature"] = ft["wind_speed"].fillna(0)
    ft.loc[ft["is_dome"], "wind_for_feature"] = 0
    ft["wind_bucket"] = pd.cut(
        ft["wind_for_feature"], bins=[-1, 5, 15, 100], labels=[0, 1, 2],
    ).astype(float)
    ft["temp_for_feature"] = ft["temperature"].fillna(70)
    ft.loc[ft["is_dome"], "temp_for_feature"] = 70
    ft["rest_advantage"] = ft["home_rest_days"] - ft["away_rest_days"]
    ft["is_short_week_home"] = (ft["home_rest_days"] <= 6).astype(float)
    ft["is_short_week_away"] = (ft["away_rest_days"] <= 6).astype(float)
    ft["neutral_site_f"] = ft["neutral_site"].astype(float)
    ft["is_dome_f"] = ft["is_dome"].astype(float)

    # ── Phase 3 Feature 1: Pace ───────────────────────────────────────
    logger.info("Building pace features...")
    try:
        home_pace, away_pace = compute_pace_rolling(canon)
        ft = ft.merge(home_pace, on="game_id", how="left")
        ft = ft.merge(away_pace, on="game_id", how="left")
        ft["combined_pace"] = ft["home_plays_rolling"].fillna(0) + ft["away_plays_rolling"].fillna(0)
        pace_added = True
        logger.info(f"  Pace: coverage={ft['home_plays_rolling'].notna().mean():.1%}")
    except Exception as e:
        logger.warning(f"  Pace feature failed: {e}")
        pace_added = False

    # ── Phase 3 Feature 2: SOS ────────────────────────────────────────
    logger.info("Building SOS features...")
    try:
        home_sos, away_sos = compute_sos_rolling(canon)
        ft = ft.merge(home_sos, on="game_id", how="left")
        ft = ft.merge(away_sos, on="game_id", how="left")
        sos_added = True
        logger.info(f"  SOS: coverage={ft['home_opp_def_quality_rolling'].notna().mean():.1%}")
    except Exception as e:
        logger.warning(f"  SOS feature failed: {e}")
        sos_added = False

    # ── Phase 3 Feature 3: Market residual ────────────────────────────
    logger.info("Building market residual...")
    ft = compute_market_residual(ft)
    mkt_res_added = "market_residual" in ft.columns and ft["market_residual"].notna().any()
    if mkt_res_added:
        logger.info(f"  Market residual: coverage={ft['market_residual'].notna().mean():.1%}")

    # ── Feature summary ───────────────────────────────────────────────
    FEATURE_COLS = [
        "home_pts_scored_rolling", "home_pts_allowed_rolling",
        "away_pts_scored_rolling", "away_pts_allowed_rolling",
        "is_dome_f", "wind_for_feature", "temp_for_feature",
        "wind_bucket", "neutral_site_f",
        "home_rest_days", "away_rest_days", "rest_advantage",
        "is_short_week_home", "is_short_week_away",
    ]
    if pace_added:
        FEATURE_COLS += ["home_plays_rolling", "away_plays_rolling", "combined_pace"]
    if sos_added:
        FEATURE_COLS += ["home_opp_def_quality_rolling", "away_opp_def_quality_rolling"]
    if mkt_res_added:
        FEATURE_COLS.append("market_residual")

    print(f"\n{'='*60}")
    print(f"  NFL FEATURE TABLE (Phase 1 + Phase 3)")
    print(f"{'='*60}")
    print(f"  Rows: {len(ft)}")
    print(f"  Features: {len(FEATURE_COLS)}")
    print(f"  Pace: {'✅ added' if pace_added else '❌ skipped'}")
    print(f"  SOS: {'✅ added' if sos_added else '❌ skipped'}")
    print(f"  Market residual: {'✅ added' if mkt_res_added else '❌ skipped'}")
    print()

    reg = ft[ft["game_type"] == "regular"]
    print(f"  Feature distributions (regular season only):")
    for col in FEATURE_COLS:
        if col in ft.columns:
            vals = reg[col].dropna()
            null_pct = reg[col].isna().mean() * 100
            flag = " ⚠️" if null_pct > 5 else ""
            corr = reg[[col, "total_points"]].dropna().corr().iloc[0, 1]
            print(f"    {col:<40} mean={vals.mean():>7.2f}  null={null_pct:.1f}%{flag}  corr={corr:+.3f}")

    # Multicollinearity check for SOS
    if sos_added:
        print(f"\n  SOS multicollinearity check:")
        corr_sos_pts = reg[["home_opp_def_quality_rolling", "home_pts_scored_rolling"]].dropna().corr().iloc[0, 1]
        print(f"    corr(home_opp_def_quality, home_pts_scored): {corr_sos_pts:+.3f}")
        if abs(corr_sos_pts) > 0.8:
            print(f"    ⚠️ HIGH multicollinearity — consider dropping SOS")
        else:
            print(f"    ✅ Acceptable multicollinearity")

    ft.to_parquet(FEATURE_PATH, index=False)
    logger.info(f"Saved: {FEATURE_PATH}")
    return ft


if __name__ == "__main__":
    build_features()
