"""
Phase 2 — Feature engineering.

Builds the canonical feature table (one row per game) from:
  - games.parquet     : Phase 1 game table
  - box_stats.parquet : Phase 2 per-team efficiency stats

Features computed
─────────────────
Efficiency (ORtg, DRtg, pace) with four-level fallback:
  1. location_rolling  — rolling 15 prior same-location games (≥ 5 required)
  2. overall_rolling   — rolling 15 prior games (all locations)
  3. prior_season_baseline — team's full prior-season average
  4. league_average    — config constants

Season stabilisation blending (games 0–19 of a new season):
  70% prior-season baseline + 30% rolling → linearly fades to 100% rolling by game 20

Rest / schedule:
  days_rest, back-to-back flag, games played in last 7 days

Injury adjustments:
  Disabled for all historical data (no reliable pre-tip timestamps available).
  injury_adj_home = injury_adj_away = 0.0 throughout.

Naive projection (for Phase 3 calibration):
  proj_total_naive = home_exp_pts + away_exp_pts
  where exp_pts uses matchup-adjusted ORtg × pace × opponent DRtg ratio.
"""

import logging
import os

import numpy as np
import pandas as pd

from nba.config import (
    ALL_HISTORICAL_SEASONS,
    BOX_STATS_PATH,
    FEATURES_PATH,
    GAMES_PATH,
    LEAGUE_AVG_DRTG,
    LEAGUE_AVG_ORTG,
    LEAGUE_AVG_PACE,
    LOCATION_MIN_GAMES,
    PRIOR_SEASON_WEIGHT,
    ROLLING_WINDOW,
    SEASON_BLEND_END,
    SEASON_BLEND_START,
)

logger = logging.getLogger(__name__)

# ── Injury note ────────────────────────────────────────────────────────────────
_INJURY_DISABLED_MSG = (
    "Injury adjustments DISABLED for historical data — no reliable pre-tip "
    "lineup timestamps are available for backtesting. injury_adj_home and "
    "injury_adj_away are set to 0.0 for all rows. This is intentional: a "
    "clean backtest without injury adjustment is better than a contaminated one."
)


# ── Prior-season baseline ─────────────────────────────────────────────────────

def _build_prior_season_baselines(box: pd.DataFrame) -> dict:
    """
    Compute per-team per-season mean ORtg/DRtg/pace.
    Returns dict: (team, current_season) → {ortg, drtg, pace}
    Key is the CURRENT season (the one being predicted); value uses prior-season data.
    """
    seasons_sorted = sorted(box["season"].unique())
    season_means   = (
        box.groupby(["team", "season"])[["ortg", "drtg", "pace"]]
        .mean()
        .rename(columns={"ortg": "ortg_bl", "drtg": "drtg_bl", "pace": "pace_bl"})
        .reset_index()
    )

    baselines: dict = {}
    for i, current_season in enumerate(seasons_sorted):
        if i == 0:
            continue  # 2022-23 has no prior season in our data
        prior_season = seasons_sorted[i - 1]
        prior_rows   = season_means[season_means["season"] == prior_season]
        for _, row in prior_rows.iterrows():
            baselines[(row["team"], current_season)] = {
                "ortg": row["ortg_bl"],
                "drtg": row["drtg_bl"],
                "pace": row["pace_bl"],
            }

    logger.info(
        f"Prior-season baselines built for {len(baselines)} (team, season) pairs"
    )
    return baselines


# ── Rolling efficiency (no-leakage) ──────────────────────────────────────────

def _build_rolling(box: pd.DataFrame, window: int = ROLLING_WINDOW) -> pd.DataFrame:
    """
    Compute rolling mean ORtg/DRtg/pace per team, shift(1) for no-leakage.

    Returns box DataFrame with added columns:
      ortg_roll, drtg_roll, pace_roll         (overall rolling)
      ortg_loc_roll, drtg_loc_roll, pace_loc_roll  (location-specific rolling)
      loc_game_count                            (# prior same-location games)
      season_game_count                         (# prior games in current season)
    """
    box = box.sort_values(["team", "date"]).copy()

    # ── Overall rolling ────────────────────────────────────────────────────────
    for col in ["ortg", "drtg", "pace"]:
        box[f"{col}_roll"] = (
            box.groupby("team")[col]
            .transform(lambda s: s.rolling(window, min_periods=1).mean().shift(1))
        )

    # ── Season game count (# prior games this season for this team) ───────────
    box["season_game_count"] = (
        box.groupby(["team", "season"]).cumcount()   # 0-indexed prior games
    )
    # cumcount() gives 0 for the first game of the season (meaning 0 prior games)

    # ── Location-specific rolling ──────────────────────────────────────────────
    # Process home and away games separately, then join back.
    loc_frames = []
    for loc in ("H", "A"):
        loc_box = box[box["location"] == loc].copy()
        loc_box = loc_box.sort_values(["team", "date"])
        for col in ["ortg", "drtg", "pace"]:
            loc_box[f"{col}_loc_roll"] = (
                loc_box.groupby("team")[col]
                .transform(lambda s: s.rolling(window, min_periods=1).mean().shift(1))
            )
        # Track # prior same-location games
        loc_box["loc_game_count"] = loc_box.groupby("team").cumcount()
        loc_frames.append(loc_box[["game_id", "team", "ortg_loc_roll",
                                    "drtg_loc_roll", "pace_loc_roll",
                                    "loc_game_count"]])

    loc_df = pd.concat(loc_frames, ignore_index=True)
    box = box.merge(loc_df, on=["game_id", "team"], how="left")

    # Null out location split if fewer than LOCATION_MIN_GAMES prior same-location games
    for col in ["ortg_loc_roll", "drtg_loc_roll", "pace_loc_roll"]:
        box.loc[box["loc_game_count"] < LOCATION_MIN_GAMES, col] = np.nan

    return box


# ── Season blending ───────────────────────────────────────────────────────────

def _blend(current_val: float, prior_val: float, games_in_season: int) -> float:
    """
    Blend current-season rolling with prior-season baseline.
    Blend only applies during the stabilisation window (< SEASON_BLEND_END games).
    """
    if games_in_season >= SEASON_BLEND_END:
        return current_val

    if games_in_season <= SEASON_BLEND_START:
        prior_weight = PRIOR_SEASON_WEIGHT
    else:
        t = (games_in_season - SEASON_BLEND_START) / (SEASON_BLEND_END - SEASON_BLEND_START)
        prior_weight = PRIOR_SEASON_WEIGHT * (1.0 - t)

    if np.isnan(prior_val):
        return current_val
    if np.isnan(current_val):
        return prior_val
    return prior_weight * prior_val + (1.0 - prior_weight) * current_val


# ── Per-team feature resolution ───────────────────────────────────────────────

def _resolve_team_features(
    team: str,
    season: str,
    game_id: str,
    box_row: pd.Series,
    baselines: dict,
) -> dict:
    """
    Apply fallback chain and season blending for one team in one game.
    Returns resolved ORtg, DRtg, pace and the fallback level used.
    """
    bl = baselines.get((team, season), {})
    bl_ortg = bl.get("ortg", np.nan)
    bl_drtg = bl.get("drtg", np.nan)
    bl_pace = bl.get("pace", np.nan)

    games_in_season = int(box_row.get("season_game_count", 0) or 0)

    def _resolve_one(col: str, bl_val: float) -> tuple[float, str]:
        loc_val  = box_row.get(f"{col}_loc_roll", np.nan)
        roll_val = box_row.get(f"{col}_roll", np.nan)

        if not np.isnan(loc_val):
            resolved = _blend(loc_val, bl_val, games_in_season)
            level    = "location_rolling"
        elif not np.isnan(roll_val):
            resolved = _blend(roll_val, bl_val, games_in_season)
            level    = "overall_rolling"
        elif not np.isnan(bl_val):
            resolved = bl_val
            level    = "prior_season_baseline"
        else:
            resolved = {"ortg": LEAGUE_AVG_ORTG,
                        "drtg": LEAGUE_AVG_DRTG,
                        "pace": LEAGUE_AVG_PACE}[col]
            level    = "league_average"

        return resolved, level

    ortg, ortg_fb = _resolve_one("ortg", bl_ortg)
    drtg, drtg_fb = _resolve_one("drtg", bl_drtg)
    pace, pace_fb = _resolve_one("pace", bl_pace)

    return {
        "ortg": ortg, "drtg": drtg, "pace": pace,
        "ortg_fb": ortg_fb, "drtg_fb": drtg_fb, "pace_fb": pace_fb,
        "games_in_season": games_in_season,
    }


# ── Rest / schedule features ──────────────────────────────────────────────────

def _build_rest_features(games: pd.DataFrame) -> pd.DataFrame:
    """
    Compute days_rest, back-to-back flag, and games-in-last-7-days
    for each team appearance (home + away) using only the game table.

    Returns DataFrame indexed by game_id with home_ and away_ prefixed columns.
    """
    # Stack home and away appearances into a single team-game series
    home_app = games[["game_id", "date", "home_team"]].rename(
        columns={"home_team": "team", "date": "gdate"}
    ).assign(role="home")
    away_app = games[["game_id", "date", "away_team"]].rename(
        columns={"away_team": "team", "date": "gdate"}
    ).assign(role="away")

    apps = pd.concat([home_app, away_app], ignore_index=True)
    apps = apps.sort_values(["team", "gdate"]).reset_index(drop=True)

    # Previous game date per team
    apps["prev_gdate"] = apps.groupby("team")["gdate"].shift(1)

    # Days rest: (today - prev_day) - 1; cap at 7; NaN (first game) → 7
    apps["days_rest"] = (
        (apps["gdate"] - apps["prev_gdate"]).dt.days - 1
    ).clip(upper=7).fillna(7).astype(int)

    # Cross-season boundary: if gap > 30 days treat as full rest
    large_gap = (apps["gdate"] - apps["prev_gdate"]).dt.days > 30
    apps.loc[large_gap, "days_rest"] = 7

    apps["b2b_flag"] = (apps["days_rest"] == 0).astype(int)

    # Games in last 7 days (not counting this game)
    apps_indexed = apps.set_index("gdate")

    def _games_l7(grp: pd.DataFrame) -> pd.Series:
        dates = grp["gdate"].sort_values()
        result = []
        for d in dates:
            cutoff = d - pd.Timedelta(days=7)
            count  = ((dates < d) & (dates >= cutoff)).sum()
            result.append(count)
        return pd.Series(result, index=dates.index)

    apps["games_l7"] = (
        apps.groupby("team", group_keys=False)[["gdate"]]
        .apply(_games_l7)
    )

    # Pivot back to game_id level with home_ / away_ columns
    home_rest = (
        apps[apps["role"] == "home"]
        [["game_id", "days_rest", "b2b_flag", "games_l7"]]
        .rename(columns={
            "days_rest": "days_rest_home",
            "b2b_flag":  "b2b_flag_home",
            "games_l7":  "games_l7_home",
        })
    )
    away_rest = (
        apps[apps["role"] == "away"]
        [["game_id", "days_rest", "b2b_flag", "games_l7"]]
        .rename(columns={
            "days_rest": "days_rest_away",
            "b2b_flag":  "b2b_flag_away",
            "games_l7":  "games_l7_away",
        })
    )

    rest = home_rest.merge(away_rest, on="game_id", how="outer")
    return rest


# ── Main builder ──────────────────────────────────────────────────────────────

def build_features(force_refresh: bool = False) -> pd.DataFrame:
    """
    Build the full feature table from games.parquet + box_stats.parquet.
    Saves result to data/features.parquet and returns the DataFrame.
    """
    if not force_refresh and os.path.exists(FEATURES_PATH):
        logger.info("Loading existing features.parquet")
        return pd.read_parquet(FEATURES_PATH)

    logger.warning(_INJURY_DISABLED_MSG)

    # ── Load inputs ───────────────────────────────────────────────────────────
    games = pd.read_parquet(GAMES_PATH)
    box   = pd.read_parquet(BOX_STATS_PATH)
    games["date"] = pd.to_datetime(games["date"])
    box["date"]   = pd.to_datetime(box["date"])

    logger.info(f"Games: {len(games)} rows | Box stats: {len(box)} rows")

    # ── Build prior-season baselines ──────────────────────────────────────────
    baselines = _build_prior_season_baselines(box)

    # ── Add rolling columns to box stats ──────────────────────────────────────
    logger.info("Computing rolling efficiency metrics …")
    box_rolled = _build_rolling(box)

    # Index box_rolled by (game_id, team) for fast lookup
    box_idx = box_rolled.set_index(["game_id", "team"])

    # ── Build rest features ───────────────────────────────────────────────────
    logger.info("Computing rest / schedule features …")
    rest = _build_rest_features(games)

    # ── Resolve features per game ─────────────────────────────────────────────
    logger.info("Resolving features per game (fallback + blending) …")
    rows = []
    fallback_counts: dict = {}

    for _, game in games.iterrows():
        gid    = game["game_id"]
        season = game["season"]
        home   = game["home_team"]
        away   = game["away_team"]

        # Fetch rolled box row for each team in this game
        try:
            home_box = box_idx.loc[(gid, home)]
        except KeyError:
            home_box = pd.Series(dtype=float)
        try:
            away_box = box_idx.loc[(gid, away)]
        except KeyError:
            away_box = pd.Series(dtype=float)

        hf = _resolve_team_features(home, season, gid, home_box, baselines)
        af = _resolve_team_features(away, season, gid, away_box, baselines)

        # Track fallback distribution
        for fb_key in (hf["ortg_fb"], af["ortg_fb"]):
            fallback_counts[fb_key] = fallback_counts.get(fb_key, 0) + 1

        # Naive projection: matchup-adjusted expected points
        avg_pace   = (hf["pace"] + af["pace"]) / 2.0
        home_exp   = (hf["ortg"] / 100.0) * avg_pace * (af["drtg"] / LEAGUE_AVG_DRTG)
        away_exp   = (af["ortg"] / 100.0) * avg_pace * (hf["drtg"] / LEAGUE_AVG_DRTG)
        proj_naive = round(home_exp + away_exp, 2)

        rows.append({
            "game_id":     gid,
            "date":        game["date"],
            "season":      season,
            "home_team":   home,
            "away_team":   away,

            # Resolved efficiency
            "home_ortg":   round(hf["ortg"], 2),
            "home_drtg":   round(hf["drtg"], 2),
            "home_pace":   round(hf["pace"], 2),
            "away_ortg":   round(af["ortg"], 2),
            "away_drtg":   round(af["drtg"], 2),
            "away_pace":   round(af["pace"], 2),

            # Fallback levels
            "home_ortg_fb": hf["ortg_fb"],
            "home_drtg_fb": hf["drtg_fb"],
            "home_pace_fb": hf["pace_fb"],
            "away_ortg_fb": af["ortg_fb"],
            "away_drtg_fb": af["drtg_fb"],
            "away_pace_fb": af["pace_fb"],

            # Season stabilisation metadata
            "home_games_in_season": hf["games_in_season"],
            "away_games_in_season": af["games_in_season"],

            # Injury (disabled for historical)
            "injury_adj_home": 0.0,
            "injury_adj_away": 0.0,

            # Naive projection
            "proj_total_naive": proj_naive,

            # Ground truth
            "actual_total":  game["actual_total"],
            "home_score":    game["home_score"],
            "away_score":    game["away_score"],
        })

    feat = pd.DataFrame(rows)

    # ── Merge rest features ───────────────────────────────────────────────────
    feat = feat.merge(rest, on="game_id", how="left")

    # ── Save ──────────────────────────────────────────────────────────────────
    feat.to_parquet(FEATURES_PATH, index=False)
    logger.info(f"Features saved: {len(feat)} rows → {FEATURES_PATH}")

    # Log fallback distribution
    total = sum(fallback_counts.values())
    logger.info("Fallback level distribution (ORtg, per team-game):")
    for level, count in sorted(fallback_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {level:<25} {count:>5} ({count/total*100:.1f}%)")

    return feat
