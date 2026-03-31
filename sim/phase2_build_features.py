"""
phase2_build_features.py — build feature_table.parquet from game_table.parquet.

Joins per-game features onto every row:
  • Starting pitcher stats (xFIP, SIERA, K%, BB%, GB%, avg_IP, TTO flag)
    Bayesian-shrunk BEFORE merge — league-average priors applied in fg_historical.py.
  • Team offense wRC+ matched to opposing SP's throwing hand
    (Savant platoon splits → overall FG wRC+ → league avg, in that order).
  • Bullpen quality × projected innings interaction term
    (team bullpen avg xFIP ratio × 9 − SP avg IP).
  • Directional wind factor (positive = blowing out toward CF).

Fallback levels are tracked for every feature so Phase 3 can optionally
weight or filter observations by data quality.

Output: sim/data/feature_table.parquet
        sim/data/phase2_feature_report.txt   (distributions + fallback counts)

Usage:
    python sim/phase2_build_features.py               # build all 3 seasons
    python sim/phase2_build_features.py --force        # ignore caches
    python sim/phase2_build_features.py --no-api       # load from cache only
"""

import argparse
import logging
import math
import os
import sys
from typing import Optional

import numpy as np
import pandas as pd

# -- path setup so we can import sim.modules from project root
SIM_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SIM_DIR)
sys.path.insert(0, PROJECT_DIR)

from sim.modules.game_starters import load_season_starters
from sim.modules.fg_historical import (
    build_pitcher_db_historical,
    build_offense_db_historical,
    build_bullpen_db_historical,
    lookup_pitcher,
    get_team_wrc,
)

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("phase2")

GAME_TABLE_PATH   = os.path.join(SIM_DIR, "data", "game_table.parquet")
FEATURE_TABLE_PATH= os.path.join(SIM_DIR, "data", "feature_table.parquet")
REPORT_PATH       = os.path.join(SIM_DIR, "data", "phase2_feature_report.txt")

SEASONS = [2022, 2023, 2024, 2025]

# League-average fallbacks
_LG_XFIP    = 4.25
_LG_WRC     = 100.0
_DEFAULT_AVG_IP = 5.5
_TTO_THRESHOLD  = 5.5   # avg IP >= this → SP likely faces lineup 3rd time

# Bullpen: projected full-game reliever innings assuming SP pitches avg_ip
# For F5 model bullpen weight = 0, so this only affects full-game features.
def _proj_bullpen_innings(avg_ip: float) -> float:
    return max(0.0, round(9.0 - avg_ip, 2))


# ---------------------------------------------------------------------------
# Wind factor
# ---------------------------------------------------------------------------

def _wind_factor(wind_speed: float, wind_dir_deg: float,
                 cf_bearing_deg: float) -> float:
    """
    Signed wind impact scalar (runs-neutral units).

    Positive  = wind blowing OUT toward CF  (offense-friendly)
    Negative  = wind blowing IN from CF     (pitcher-friendly)
    Zero      = crosswind

    Formula: -cos(wind_dir - cf_bearing) × wind_speed
      wind_dir is the direction the wind is COMING FROM (meteorological)
      cf_bearing is the compass bearing from home plate TO center field
      When wind comes from behind home plate (= opposite of CF bearing),
      it blows toward CF → that is "out" → positive.
    """
    if wind_speed <= 0:
        return 0.0
    angle_rad = math.radians(wind_dir_deg - cf_bearing_deg)
    return round(-math.cos(angle_rad) * wind_speed, 2)


# ---------------------------------------------------------------------------
# Per-row feature builder
# ---------------------------------------------------------------------------

def _build_sp_features(sp_id: Optional[int], sp_name: str,
                        sp_throws: str, pitcher_db: dict,
                        team_abb: str, prefix: str) -> dict:
    """
    Look up pitcher in DB and return feature dict with given prefix.
    All ERA-type stats already Bayesian-shrunk at build time.
    """
    entry, fallback = lookup_pitcher(sp_id, sp_name, pitcher_db, team_abb)

    avg_ip = entry.get("avg_ip_per_start") or _DEFAULT_AVG_IP
    tto    = 1 if avg_ip >= _TTO_THRESHOLD else 0

    return {
        f"{prefix}_sp_id":       sp_id,
        f"{prefix}_sp_name":     sp_name,
        f"{prefix}_sp_throws":   sp_throws,
        f"{prefix}_sp_xfip":     entry.get("xfip",  _LG_XFIP),
        f"{prefix}_sp_siera":    entry.get("siera", _LG_XFIP),
        f"{prefix}_sp_k_pct":    entry.get("k_pct", 0.224),
        f"{prefix}_sp_bb_pct":   entry.get("bb_pct", 0.085),
        f"{prefix}_sp_gb_pct":   entry.get("gb_pct"),   # may be None
        f"{prefix}_sp_avg_ip":   avg_ip,
        f"{prefix}_sp_tto_flag": tto,
        f"{prefix}_sp_fallback": fallback,
    }


def _build_offense_features(team_abb: str, offense_db: dict,
                              opp_throws: str, prefix: str) -> dict:
    """Return wRC+ matched to opposing SP handedness."""
    wrc, fallback = get_team_wrc(team_abb, offense_db, opp_throws)
    return {
        f"{prefix}_wrc_plus":    wrc,
        f"{prefix}_wrc_fallback": fallback,
    }


def _build_bullpen_features(team_abb: str, bullpen_db: dict,
                              sp_avg_ip: float, prefix: str) -> dict:
    """
    Bullpen as interaction term: (bp_xfip / league_avg) × proj_innings.
    Higher value = more innings projected + worse bullpen = more runs allowed.
    """
    entry    = bullpen_db.get(team_abb.upper(), {})
    bp_xfip  = entry.get("avg_xfip", _LG_XFIP)
    fallback = 0 if entry else 1

    proj_inn    = _proj_bullpen_innings(sp_avg_ip)
    interaction = round((bp_xfip / _LG_XFIP) * proj_inn, 3)

    return {
        f"{prefix}_bp_xfip":        bp_xfip,
        f"{prefix}_bp_proj_inn":    proj_inn,
        f"{prefix}_bp_interaction": interaction,
        f"{prefix}_bp_fallback":    fallback,
    }


# ---------------------------------------------------------------------------
# Season builder
# ---------------------------------------------------------------------------

def build_season_features(
    season_df: pd.DataFrame,
    year: int,
    force_api: bool = False,
) -> pd.DataFrame:
    """
    Build all Phase 2 features for a single season's game rows.
    Returns DataFrame with all original game_table columns + new feature columns.
    """
    game_pks = season_df["game_pk"].tolist()

    # --- Load data sources ---
    logger.info(f"=== Season {year}: {len(game_pks)} games ===")

    logger.info(f"[{year}] Loading starting pitchers...")
    starters = load_season_starters(year, game_pks)

    logger.info(f"[{year}] Loading pitcher DB (FanGraphs)...")
    pitcher_db = build_pitcher_db_historical(year, force_refresh=force_api)

    logger.info(f"[{year}] Loading offense DB (FanGraphs + Savant)...")
    offense_db = build_offense_db_historical(year, force_refresh=force_api)

    logger.info(f"[{year}] Building bullpen DB from pitcher DB...")
    bullpen_db = build_bullpen_db_historical(pitcher_db)

    # --- Load CF bearings from config ---
    try:
        from config import STADIUMS
        cf_bearings: dict = {k: v.get("cf_bearing", 0)
                             for k, v in STADIUMS.items()}
    except ImportError:
        logger.warning("config.STADIUMS not available — wind factors will be 0")
        cf_bearings = {}

    # --- Build features row by row ---
    rows_out = []
    no_starter_count = 0

    for _, game_row in season_df.iterrows():
        pk         = int(game_row["game_pk"])
        home_team  = game_row["home_team"]
        away_team  = game_row["away_team"]

        starter_data = starters.get(pk)
        if not starter_data:
            no_starter_count += 1
            # Skip games with no starter data — will be dropped from feature table
            continue

        home_sp_raw = starter_data["home"]
        away_sp_raw = starter_data["away"]

        home_sp_id     = home_sp_raw.get("id")
        home_sp_name   = home_sp_raw.get("name", "")
        home_sp_throws = home_sp_raw.get("throws", "R")
        away_sp_id     = away_sp_raw.get("id")
        away_sp_name   = away_sp_raw.get("name", "")
        away_sp_throws = away_sp_raw.get("throws", "R")

        # SP features
        home_sp_feats = _build_sp_features(
            home_sp_id, home_sp_name, home_sp_throws,
            pitcher_db, home_team, "home"
        )
        away_sp_feats = _build_sp_features(
            away_sp_id, away_sp_name, away_sp_throws,
            pitcher_db, away_team, "away"
        )

        # Offense features (wRC+ matched to OPPOSING SP's hand)
        home_off_feats = _build_offense_features(
            home_team, offense_db, away_sp_throws, "home"
        )
        away_off_feats = _build_offense_features(
            away_team, offense_db, home_sp_throws, "away"
        )

        # Bullpen features (interaction term)
        home_sp_avg_ip = home_sp_feats["home_sp_avg_ip"]
        away_sp_avg_ip = away_sp_feats["away_sp_avg_ip"]
        home_bp_feats  = _build_bullpen_features(home_team, bullpen_db, home_sp_avg_ip, "home")
        away_bp_feats  = _build_bullpen_features(away_team, bullpen_db, away_sp_avg_ip, "away")

        # Wind factor
        wind_spd = float(game_row.get("wind_speed", 0) or 0)
        wind_dir = float(game_row.get("wind_direction", 0) or 0)
        cf_bear  = float(cf_bearings.get(home_team, 0))
        wf       = _wind_factor(wind_spd, wind_dir, cf_bear)

        # Combine all features
        feat_row = dict(game_row)
        feat_row.update(home_sp_feats)
        feat_row.update(away_sp_feats)
        feat_row.update(home_off_feats)
        feat_row.update(away_off_feats)
        feat_row.update(home_bp_feats)
        feat_row.update(away_bp_feats)
        feat_row["wind_factor_effective"] = wf

        rows_out.append(feat_row)

    logger.info(f"[{year}] Built {len(rows_out)} rows; "
                f"{no_starter_count} dropped (no starter data)")

    return pd.DataFrame(rows_out)


# ---------------------------------------------------------------------------
# Audit / report
# ---------------------------------------------------------------------------

def _print_distributions(df: pd.DataFrame, report_lines: list[str]) -> None:
    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    num_cols = [
        "home_sp_xfip", "away_sp_xfip",
        "home_sp_siera", "away_sp_siera",
        "home_sp_k_pct", "away_sp_k_pct",
        "home_sp_bb_pct", "away_sp_bb_pct",
        "home_sp_avg_ip", "away_sp_avg_ip",
        "home_wrc_plus", "away_wrc_plus",
        "home_bp_interaction", "away_bp_interaction",
        "wind_factor_effective",
    ]

    line()
    line("─" * 70)
    line("FEATURE DISTRIBUTIONS")
    line("─" * 70)
    line(f"{'Feature':<30}  {'Mean':>7}  {'Std':>7}  {'Min':>7}  {'Max':>7}  {'Null%':>6}")
    line(f"{'─'*30}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*6}")

    for col in num_cols:
        if col not in df.columns:
            line(f"{col:<30}  {'MISSING'}")
            continue
        s   = df[col].dropna()
        null_pct = (df[col].isna().sum() / len(df)) * 100
        line(f"{col:<30}  {s.mean():>7.3f}  {s.std():>7.3f}  "
             f"{s.min():>7.3f}  {s.max():>7.3f}  {null_pct:>5.1f}%")


def _print_fallbacks(df: pd.DataFrame, report_lines: list[str]) -> None:
    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    fallback_cols = {
        "home_sp_fallback": {0: "FG ID", 1: "FG name", 2: "last-name", 3: "team avg", 4: "league avg"},
        "away_sp_fallback": {0: "FG ID", 1: "FG name", 2: "last-name", 3: "team avg", 4: "league avg"},
        "home_wrc_fallback": {0: "platoon split", 1: "overall wRC+", 2: "league avg"},
        "away_wrc_fallback": {0: "platoon split", 1: "overall wRC+", 2: "league avg"},
        "home_bp_fallback":  {0: "FG bullpen", 1: "league avg"},
        "away_bp_fallback":  {0: "FG bullpen", 1: "league avg"},
    }

    line()
    line("─" * 70)
    line("FALLBACK USAGE COUNTS")
    line("─" * 70)
    total = len(df)

    for col, level_names in fallback_cols.items():
        if col not in df.columns:
            continue
        line(f"  {col}:")
        counts = df[col].value_counts().to_dict()
        for lvl in sorted(level_names):
            n   = counts.get(lvl, 0)
            pct = n / total * 100
            line(f"    Level {lvl} ({level_names[lvl]}): {n:,} ({pct:.1f}%)")


def _print_collinearity(df: pd.DataFrame, report_lines: list[str]) -> None:
    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    feature_cols = [
        "home_sp_xfip", "home_sp_siera", "home_sp_k_pct", "home_sp_bb_pct",
        "home_sp_avg_ip", "home_wrc_plus", "home_bp_interaction",
        "away_sp_xfip", "away_sp_siera", "away_sp_k_pct", "away_sp_bb_pct",
        "away_sp_avg_ip", "away_wrc_plus", "away_bp_interaction",
        "wind_factor_effective", "temperature", "park_factor_runs",
        "umpire_over_rate",
    ]

    available = [c for c in feature_cols if c in df.columns]
    corr = df[available].corr().abs()

    line()
    line("─" * 70)
    line("HIGH COLLINEARITY PAIRS  (|r| > 0.70)")
    line("─" * 70)

    found_any = False
    cols = list(corr.columns)
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            r = corr.loc[c1, c2]
            if r > 0.70:
                line(f"  |r| = {r:.3f}  {c1}  ↔  {c2}")
                found_any = True

    if not found_any:
        line("  None above 0.70  ✓")

    line()
    line("Moderate collinearity pairs  (0.50 < |r| ≤ 0.70)")
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            r = corr.loc[c1, c2]
            if 0.50 < r <= 0.70:
                line(f"  |r| = {r:.3f}  {c1}  ↔  {c2}")


def print_full_report(df: pd.DataFrame) -> None:
    report_lines: list[str] = []

    def line(s: str = ""):
        print(s)
        report_lines.append(s)

    line("=" * 70)
    line("PHASE 2 FEATURE TABLE — AUDIT REPORT")
    line("=" * 70)
    line(f"  Rows: {len(df):,}")
    line(f"  Columns: {len(df.columns)}")
    line(f"  Seasons: {sorted(df['season'].unique())}")
    for yr, grp in df.groupby("season"):
        line(f"    {yr}: {len(grp):,} games")
    line()
    line(f"  Target: actual_total")
    line(f"    mean={df['actual_total'].mean():.2f}, "
         f"std={df['actual_total'].std():.2f}, "
         f"min={df['actual_total'].min()}, "
         f"max={df['actual_total'].max()}")

    _print_distributions(df, report_lines)
    _print_fallbacks(df, report_lines)
    _print_collinearity(df, report_lines)

    line()
    line("=" * 70)

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))
    logger.info(f"Report saved: {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Phase 2: Build feature table")
    parser.add_argument("--force",  action="store_true",
                        help="Force re-fetch FanGraphs data (ignore season cache)")
    parser.add_argument("--no-api", action="store_true",
                        help="Skip API calls — use cached data only")
    args = parser.parse_args()

    force_api = args.force and not args.no_api

    # Load game table
    if not os.path.exists(GAME_TABLE_PATH):
        logger.error(f"game_table.parquet not found at {GAME_TABLE_PATH}")
        logger.error("Run phase1_build_game_table.py first.")
        sys.exit(1)

    logger.info("Loading game_table.parquet...")
    game_df = pd.read_parquet(GAME_TABLE_PATH)
    logger.info(f"Loaded {len(game_df):,} rows × {len(game_df.columns)} cols")

    # Build features per season
    season_dfs = []
    for year in SEASONS:
        season_df = game_df[game_df["season"] == year].copy()
        if season_df.empty:
            logger.warning(f"No rows for season {year} in game_table")
            continue
        feat_df = build_season_features(season_df, year, force_api=force_api)
        season_dfs.append(feat_df)

    if not season_dfs:
        logger.error("No feature data built — exiting")
        sys.exit(1)

    # Combine and save
    full_df = pd.concat(season_dfs, ignore_index=True)
    full_df.sort_values(["date", "game_pk"], inplace=True)
    full_df.reset_index(drop=True, inplace=True)

    logger.info(f"Writing feature_table.parquet ({len(full_df):,} rows × "
                f"{len(full_df.columns)} cols)...")
    full_df.to_parquet(FEATURE_TABLE_PATH, index=False)
    logger.info(f"Saved: {FEATURE_TABLE_PATH}")

    # Print and save full audit report
    print_full_report(full_df)


if __name__ == "__main__":
    main()
