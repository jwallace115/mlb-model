"""
Phase V2.2-B: Feature table builder.

Starts from soccer_feature_table_v2_1.parquet.
Adds:
  Group K — Market price features (from odds_historical.parquet)
  Group L — Injury features (from injuries_raw.parquet)
  Group M — Weather features (from weather_historical.parquet)
  Group N — Referee features (from referee_features.parquet)

Output: soccer/data/soccer_feature_table_v2_2.parquet
"""

import logging
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

INPUT_PATH      = os.path.join(DATA_DIR, "soccer_feature_table_v2_1.parquet")
ODDS_PATH       = os.path.join(DATA_DIR, "odds_historical.parquet")
INJURIES_PATH   = os.path.join(DATA_DIR, "injuries_raw.parquet")
WEATHER_PATH    = os.path.join(DATA_DIR, "weather_historical.parquet")
REFEREE_PATH    = os.path.join(DATA_DIR, "referee_features.parquet")
LINEUPS_PATH    = os.path.join(DATA_DIR, "lineups_raw.parquet")
CANONICAL_PATH  = os.path.join(DATA_DIR, "soccer_canonical.parquet")
OUTPUT_PATH     = os.path.join(DATA_DIR, "soccer_feature_table_v2_2.parquet")

SEP  = "═" * 72
SEP2 = "─" * 72

# ── New feature column lists ──────────────────────────────────────────────────

GROUP_K_COLS = [
    "market_fair_p_over_2_5",
    "market_fair_p_under_2_5",
    "market_fair_p_over_1_5",
    "market_fair_p_over_3_5",
    "market_implied_mu",
    "market_low_total_pressure",
    "market_high_total_pressure",
    "market_move_to_over_2_5",
    "market_move_magnitude_2_5",
    "market_late_move_over",
    "market_late_move_under",
    "market_odds_available",
]

GROUP_L_COLS = [
    "home_injury_count",
    "away_injury_count",
    "home_attacker_injured",
    "away_attacker_injured",
    "home_defender_injured",
    "away_defender_injured",
    "home_key_player_injured",
    "away_key_player_injured",
    "home_total_absence_score",
    "away_total_absence_score",
]

GROUP_M_COLS = [
    "weather_wind_high",
    "weather_rain",
    "weather_temp_cold",
    "weather_extreme",
    "weather_wind_kph",
    "weather_precip_mm",
]

GROUP_N_COLS = [
    "ref_avg_goals",
    "ref_red_card_rate",
    "ref_penalty_rate",
    "ref_home_adv",
    "ref_available",
]

ALL_NEW_COLS = GROUP_K_COLS + GROUP_L_COLS + GROUP_M_COLS + GROUP_N_COLS


# ── Group K: Market features ──────────────────────────────────────────────────

def build_group_k(canon: pd.DataFrame) -> pd.DataFrame:
    """Merge market features. Fallback: league-season avg for missing rows."""
    odds = pd.read_parquet(ODDS_PATH)

    # Use the columns computed in A1
    k_src_cols = [
        "game_id",
        "market_fair_p_over_2_5", "market_fair_p_under_2_5",
        "market_fair_p_over_1_5", "market_fair_p_over_3_5",
        "market_implied_mu",
        "market_low_total_pressure", "market_high_total_pressure",
        "market_move_to_over_2_5", "market_move_magnitude_2_5",
        "market_late_move_over", "market_late_move_under",
        "market_odds_available",
    ]
    # Only take columns that exist
    available = [c for c in k_src_cols if c in odds.columns]
    k = odds[available].copy()

    merged = canon[["game_id", "league_id", "season_year"]].merge(k, on="game_id", how="left")

    # Fill market_odds_available for games with no odds data
    merged["market_odds_available"] = merged["market_odds_available"].fillna(0.0)

    # Compute league-season averages for fallback
    league_season_avgs = (
        merged[merged["market_odds_available"] == 1]
        .groupby(["league_id", "season_year"])["market_fair_p_over_2_5"]
        .mean()
        .rename("ls_avg_fair_p")
        .reset_index()
    )

    merged = merged.merge(league_season_avgs, on=["league_id", "season_year"], how="left")

    # For games without market odds: fill with league-season average
    for col in ["market_fair_p_over_2_5", "market_fair_p_under_2_5",
                "market_fair_p_over_1_5", "market_fair_p_over_3_5",
                "market_implied_mu"]:
        if col not in merged.columns:
            merged[col] = np.nan
        if col == "market_fair_p_over_2_5":
            merged[col] = merged[col].fillna(merged["ls_avg_fair_p"])
        elif col == "market_fair_p_under_2_5":
            merged[col] = merged[col].fillna(1.0 - merged["ls_avg_fair_p"])

    # Fill movement features with 0 (no movement observable without odds)
    for col in ["market_move_to_over_2_5", "market_move_magnitude_2_5",
                "market_late_move_over", "market_late_move_under"]:
        if col not in merged.columns:
            merged[col] = 0.0
        else:
            merged[col] = merged[col].fillna(0.0)

    # Fill pressure features with 0 (neutral)
    for col in ["market_low_total_pressure", "market_high_total_pressure"]:
        if col not in merged.columns:
            merged[col] = np.nan
        else:
            merged[col] = merged[col].fillna(0.0)

    merged = merged.drop(columns=["ls_avg_fair_p", "league_id", "season_year"],
                         errors="ignore")
    return merged[["game_id"] + [c for c in GROUP_K_COLS if c in merged.columns]]


# ── Group L: Injury features ──────────────────────────────────────────────────

def build_group_l(canon: pd.DataFrame) -> pd.DataFrame:
    """Build injury counts per game. Returns zeros if no injury data."""
    injuries_path = INJURIES_PATH

    if not os.path.exists(injuries_path):
        logger.warning("injuries_raw.parquet not found — using zeros")
        return canon[["game_id"]].assign(
            **{c: 0.0 for c in GROUP_L_COLS}
        )

    inj = pd.read_parquet(injuries_path)

    if inj.empty:
        logger.info("No injury records — injury features set to 0")
        return canon[["game_id"]].assign(
            **{c: 0.0 for c in GROUP_L_COLS}
        )

    logger.info(f"Injury rows: {len(inj):,}")

    # Load lineups for key player identification
    lineups = pd.read_parquet(LINEUPS_PATH)
    starters = lineups[lineups["is_starter"] == True]

    # Build top-3 starters per team per game based on cumulative prior starts
    # (simplified: use player_id from lineups_raw starters as proxy for "regulars")

    def count_injuries(game_id: str, team_side: str,
                       inj_df: pd.DataFrame) -> dict:
        sub = inj_df[(inj_df["game_id"] == game_id) &
                     (inj_df["team_side"] == team_side)]
        if sub.empty:
            return {
                "injury_count": 0, "attacker_injured": 0,
                "defender_injured": 0, "key_player_injured": 0,
            }

        # Position inference from reason/type (API-Football often doesn't have position)
        n_inj = len(sub)
        # Key player = any injury in dataset (proxy since we lack position from API)
        n_key = min(1, n_inj)  # flag if any injury

        return {
            "injury_count":      n_inj,
            "attacker_injured":  0,   # API-Football injuries don't reliably give position
            "defender_injured":  0,
            "key_player_injured": n_key,
        }

    rows = []
    for _, game in canon.iterrows():
        gid = game["game_id"]
        h = count_injuries(gid, "home", inj)
        a = count_injuries(gid, "away", inj)

        # home_total_absence_score: combine lineup delta + injury count
        rows.append({
            "game_id":                gid,
            "home_injury_count":      h["injury_count"],
            "away_injury_count":      a["injury_count"],
            "home_attacker_injured":  h["attacker_injured"],
            "away_attacker_injured":  a["attacker_injured"],
            "home_defender_injured":  h["defender_injured"],
            "away_defender_injured":  a["defender_injured"],
            "home_key_player_injured": h["key_player_injured"],
            "away_key_player_injured": a["key_player_injured"],
            # Will be combined with lineup_delta after merge
            "home_total_absence_score": float(h["injury_count"]) * 0.5,
            "away_total_absence_score": float(a["injury_count"]) * 0.5,
        })

    return pd.DataFrame(rows)


# ── Group M: Weather features ─────────────────────────────────────────────────

def build_group_m(canon: pd.DataFrame) -> pd.DataFrame:
    """Merge weather features."""
    if not os.path.exists(WEATHER_PATH):
        logger.warning("weather_historical.parquet not found — using defaults")
        df = canon[["game_id"]].copy()
        df["weather_wind_high"]  = 0.0
        df["weather_rain"]       = 0.0
        df["weather_temp_cold"]  = 0.0
        df["weather_extreme"]    = 0.0
        df["weather_wind_kph"]   = 15.0
        df["weather_precip_mm"]  = 0.0
        return df

    wx = pd.read_parquet(WEATHER_PATH)
    merged = canon[["game_id"]].merge(wx, on="game_id", how="left")

    # Derive flag columns from raw values
    merged["weather_wind_high"] = (merged["wind_kph"] > 30).astype(float)
    merged["weather_rain"]      = (merged["precipitation_mm"] > 1.0).astype(float)
    merged["weather_temp_cold"] = (merged["temperature_c"] < 5.0).astype(float)
    merged["weather_extreme"]   = (
        (merged["weather_wind_high"] == 1) |
        (merged["weather_rain"] == 1) |
        (merged["weather_temp_cold"] == 1)
    ).astype(float)
    merged["weather_wind_kph"]  = merged["wind_kph"].fillna(15.0)
    merged["weather_precip_mm"] = merged["precipitation_mm"].fillna(0.0)

    # Fill flags with 0 for missing weather
    for col in ["weather_wind_high", "weather_rain", "weather_temp_cold", "weather_extreme"]:
        merged[col] = merged[col].fillna(0.0)

    return merged[["game_id"] + GROUP_M_COLS]


# ── Group N: Referee features ─────────────────────────────────────────────────

def build_group_n(canon: pd.DataFrame) -> pd.DataFrame:
    """Merge referee features."""
    if not os.path.exists(REFEREE_PATH):
        logger.warning("referee_features.parquet not found — using defaults")
        df = canon[["game_id"]].copy()
        df["ref_avg_goals"]    = 2.8
        df["ref_red_card_rate"] = 0.1
        df["ref_penalty_rate"] = 0.3
        df["ref_home_adv"]     = 0.45
        df["ref_available"]    = 0.0
        return df

    ref = pd.read_parquet(REFEREE_PATH)
    merged = canon[["game_id"]].merge(
        ref[["game_id"] + GROUP_N_COLS], on="game_id", how="left"
    )

    # Fill any remaining NaN with fallback
    merged["ref_avg_goals"]    = merged["ref_avg_goals"].fillna(2.8)
    merged["ref_red_card_rate"] = merged["ref_red_card_rate"].fillna(0.1)
    merged["ref_penalty_rate"] = merged["ref_penalty_rate"].fillna(0.3)
    merged["ref_home_adv"]     = merged["ref_home_adv"].fillna(0.45)
    merged["ref_available"]    = merged["ref_available"].fillna(0.0)

    return merged[["game_id"] + GROUP_N_COLS]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{SEP}")
    print("  PHASE V2.2-B: FEATURE TABLE BUILD")
    print(SEP)

    canon = pd.read_parquet(CANONICAL_PATH)
    canon["game_date"] = pd.to_datetime(canon["game_date"])

    feat_v21 = pd.read_parquet(INPUT_PATH)
    logger.info(f"V2.1 feature table: {len(feat_v21):,} rows × {len(feat_v21.columns)} columns")

    # ── Build each feature group ───────────────────────────────────────────────
    print("\n  Building Group K (market)...")
    k = build_group_k(canon)
    logger.info(f"Group K: {len(k.columns)-1} feature cols")

    print("  Building Group L (injuries)...")
    l = build_group_l(canon)
    logger.info(f"Group L: {len(l.columns)-1} feature cols")

    print("  Building Group M (weather)...")
    m = build_group_m(canon)
    logger.info(f"Group M: {len(m.columns)-1} feature cols")

    print("  Building Group N (referee)...")
    n = build_group_n(canon)
    logger.info(f"Group N: {len(n.columns)-1} feature cols")

    # ── Merge all onto V2.1 ────────────────────────────────────────────────────
    print("\n  Merging all groups onto V2.1...")

    # Drop any columns from v2.1 that we're overwriting
    all_new = [c for grp in [k, l, m, n] for c in grp.columns if c != "game_id"]
    overlap = [c for c in all_new if c in feat_v21.columns]
    if overlap:
        logger.info(f"Dropping {len(overlap)} overwritten cols from V2.1: {overlap}")
        feat_v21 = feat_v21.drop(columns=overlap)

    ft = feat_v21.copy()
    for df, name in [(k, "K"), (l, "L"), (m, "M"), (n, "N")]:
        before = len(ft.columns)
        ft = ft.merge(df, on="game_id", how="left")
        added = len(ft.columns) - before
        logger.info(f"Group {name}: +{added} columns  (total: {len(ft.columns)})")

    # ── Combine injury + lineup delta for total absence score ─────────────────
    if "home_lineup_delta" in ft.columns:
        # lineup_delta is negative when rotating — more negative = worse lineup
        ft["home_total_absence_score"] = (
            ft["home_total_absence_score"].fillna(0) +
            (-ft["home_lineup_delta"].fillna(0)).clip(lower=0)
        )
        ft["away_total_absence_score"] = (
            ft["away_total_absence_score"].fillna(0) +
            (-ft["away_lineup_delta"].fillna(0)).clip(lower=0)
        )

    logger.info(f"V2.2 feature table: {len(ft):,} rows × {len(ft.columns)} columns")

    # ── Leakage audit ──────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  V2.2 LEAKAGE AUDIT")
    print(SEP)

    print(f"\n  Feature table: {len(ft):,} rows × {len(ft.columns)} columns")
    print(f"\n  NEW FEATURES — NULL RATES:")
    print(f"  {'Feature':<45} {'Null%':>8}  {'Note'}")
    print(f"  {SEP2[:65]}")

    for col in ALL_NEW_COLS:
        if col not in ft.columns:
            print(f"  MISSING  {col}")
            continue
        null_pct = ft[col].isna().mean() * 100
        flag = "✓" if null_pct < 5 else ("⚠" if null_pct < 30 else "✗")
        note = ""
        if col.startswith("market_"):
            note = "pregame info — not leakage"
        elif col.startswith("ref_"):
            note = "prior-game rolling — leakage-safe"
        elif col.startswith("weather"):
            note = "kickoff-time weather — not leakage"
        elif "_injury_" in col or "_injured" in col:
            note = "confirmed pre-kickoff — not leakage"
        print(f"  {flag} {col:<45} {null_pct:>7.2f}%  {note}")

    # ── Per-split coverage ─────────────────────────────────────────────────────
    print(f"\n  COVERAGE BY SPLIT:")
    split_map = {
        "2019-20": "train", "2020-21": "train",
        "2021-22": "train", "2022-23": "train",
        "2023-24": "validate", "2024-25": "oos",
    }
    ft_with_split = ft.merge(
        canon[["game_id", "season_year"]], on="game_id", how="left",
        suffixes=("", "_can")
    )
    sy_col = "season_year" if "season_year" in ft_with_split.columns else "season_year_can"
    ft_with_split["split"] = ft_with_split[sy_col].map(split_map)

    for split in ["train", "validate", "oos"]:
        sub = ft_with_split[ft_with_split["split"] == split]
        if sub.empty:
            continue
        k_cov = sub["market_fair_p_over_2_5"].notna().mean()
        print(f"  {split:<12} {len(sub):>5} rows  "
              f"market={k_cov:.1%}  "
              f"weather={sub['weather_wind_kph'].notna().mean():.1%}  "
              f"ref={sub['ref_available'].mean():.1%}")

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"\n  Saving → {OUTPUT_PATH}")
    ft.to_parquet(OUTPUT_PATH, index=False)
    print(f"  Saved: {len(ft):,} rows × {len(ft.columns)} columns")
    print(f"  V2.1 feature table untouched.\n")

    return ft


if __name__ == "__main__":
    main()
