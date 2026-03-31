"""
Phase V2.2-A4: Referee feature extraction.

Reads football-data.co.uk CSVs (EPL only — BUN has no referee column).
Builds leakage-safe rolling referee statistics using prior matches only.

Output: soccer/data/referee_features.parquet
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

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

CANONICAL_PATH = os.path.join(DATA_DIR, "soccer_canonical.parquet")
OUTPUT_PATH    = os.path.join(DATA_DIR, "referee_features.parquet")

SEASON_CSV_MAP = {
    "2019-20": "1920",
    "2020-21": "2021",
    "2021-22": "2122",
    "2022-23": "2223",
    "2023-24": "2324",
    "2024-25": "2425",
}

SEP = "═" * 72


def parse_csv_referee(league: str, season_suffix: str) -> pd.DataFrame:
    """Parse CSV for referee and match stats."""
    path = os.path.join(CACHE_DIR, f"fd_{league}_{season_suffix}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()

    df = pd.read_csv(path, on_bad_lines="skip")
    if "Referee" not in df.columns:
        return pd.DataFrame()

    df["game_date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["game_date", "HomeTeam", "AwayTeam", "Referee"])

    # Parse match stats needed for rolling features
    # Red cards: HR (home reds) + AR (away reds)
    # Yellow cards: HY + AY (not used but available)
    # Fouls: HF + AF
    # Goals: FTHG + FTAG
    # Home win: FTR == 'H'
    for col in ["HR", "AR", "HF", "AF", "FTHG", "FTAG", "FTR"]:
        if col not in df.columns:
            df[col] = np.nan
        else:
            if col != "FTR":
                df[col] = pd.to_numeric(df[col], errors="coerce")

    df["total_goals"]    = df["FTHG"].fillna(0) + df["FTAG"].fillna(0)
    df["total_reds"]     = df["HR"].fillna(0)   + df["AR"].fillna(0)
    df["total_fouls"]    = df["HF"].fillna(0)   + df["AF"].fillna(0)
    df["home_win"]       = (df["FTR"] == "H").astype(float)
    df["had_penalty"]    = ((df["total_fouls"] > 18) |
                            (df["total_goals"] >= 4)).astype(float)  # proxy

    df["league_id"]   = league
    df["season_year"] = None  # filled below via year inference

    return df[[
        "game_date", "HomeTeam", "AwayTeam", "Referee",
        "total_goals", "total_reds", "total_fouls", "home_win",
        "league_id",
    ]].rename(columns={"HomeTeam": "home_team", "AwayTeam": "away_team",
                        "Referee": "referee"}).copy()


def main():
    print(f"\n{SEP}")
    print("  PHASE V2.2-A4: REFEREE FEATURES")
    print(SEP)

    canon = pd.read_parquet(CANONICAL_PATH)
    canon["game_date"] = pd.to_datetime(canon["game_date"])

    # ── Load all EPL referee data ─────────────────────────────────────────────
    frames = []
    for season_year, suffix in SEASON_CSV_MAP.items():
        df = parse_csv_referee("EPL", suffix)
        if df.empty:
            continue
        df["season_year"] = season_year
        frames.append(df)

    if not frames:
        logger.error("No EPL referee data found")
        return

    ref_data = pd.concat(frames, ignore_index=True)
    ref_data["game_date"] = pd.to_datetime(ref_data["game_date"])
    ref_data = ref_data.sort_values("game_date").reset_index(drop=True)
    logger.info(f"Referee match data: {len(ref_data):,} rows from EPL CSVs")

    # ── Build leakage-safe rolling referee stats ──────────────────────────────
    # Sort by game_date globally (all seasons together — referees span seasons)
    # For each match: compute stats from ALL prior matches by this referee
    ref_data = ref_data.sort_values("game_date").reset_index(drop=True)

    # Group by referee, sorted by date
    # Prior stats use shift(1) + expanding

    ref_data["ref_games_prior"]    = ref_data.groupby("referee")["game_date"].transform(
        lambda x: x.expanding().count().shift(1).fillna(0)
    )
    ref_data["ref_avg_goals"]      = ref_data.groupby("referee")["total_goals"].transform(
        lambda x: x.expanding().mean().shift(1)
    )
    ref_data["ref_red_card_rate"]  = ref_data.groupby("referee")["total_reds"].transform(
        lambda x: x.expanding().mean().shift(1)
    )
    ref_data["ref_foul_rate"]      = ref_data.groupby("referee")["total_fouls"].transform(
        lambda x: x.expanding().mean().shift(1)
    )
    ref_data["ref_home_adv"]       = ref_data.groupby("referee")["home_win"].transform(
        lambda x: x.expanding().mean().shift(1)
    )

    # Proxy penalty rate: flag games with many fouls or high goal counts
    # Better proxy: use total_fouls > 18 as "busy game" rate
    ref_data["busy_game"] = (ref_data["total_fouls"] > 18).astype(float)
    ref_data["ref_penalty_rate"]   = ref_data.groupby("referee")["busy_game"].transform(
        lambda x: x.expanding().mean().shift(1)
    )

    # Apply shrinkage for refs with few prior games
    MIN_GAMES = 5
    w = ref_data["ref_games_prior"].clip(upper=MIN_GAMES) / MIN_GAMES

    # League-wide averages (will fill NaN for first appearances)
    league_avg_goals   = ref_data["total_goals"].mean()
    league_avg_reds    = ref_data["total_reds"].mean()
    league_avg_fouls   = ref_data["total_fouls"].mean()
    league_avg_home_win = ref_data["home_win"].mean()
    league_avg_busy    = ref_data["busy_game"].mean()

    def shrink(col: str, avg: float):
        return w * ref_data[col].fillna(avg) + (1 - w) * avg

    ref_data["ref_avg_goals_shrunk"]    = shrink("ref_avg_goals",    league_avg_goals)
    ref_data["ref_red_card_rate_shrunk"]= shrink("ref_red_card_rate",league_avg_reds)
    ref_data["ref_penalty_rate_shrunk"] = shrink("ref_penalty_rate", league_avg_busy)
    ref_data["ref_home_adv_shrunk"]     = shrink("ref_home_adv",     league_avg_home_win)

    # ── Match ref data to canonical ───────────────────────────────────────────
    logger.info("Matching referee data to canonical game IDs...")

    epl_canon = canon[canon["league_id"] == "EPL"].copy()

    ref_match = epl_canon.merge(
        ref_data[[
            "game_date", "home_team", "away_team", "referee",
            "ref_games_prior",
            "ref_avg_goals_shrunk", "ref_red_card_rate_shrunk",
            "ref_penalty_rate_shrunk", "ref_home_adv_shrunk",
        ]],
        on=["game_date", "home_team", "away_team"],
        how="left",
    )

    match_rate = ref_match["referee"].notna().mean()
    logger.info(f"EPL referee match rate: {match_rate:.1%}")

    # ── Build output (all games — BUN gets zeros + flag) ─────────────────────
    # League averages for shrinkage fallback
    avg_goals    = ref_data["ref_avg_goals_shrunk"].mean()
    avg_reds     = ref_data["ref_red_card_rate_shrunk"].mean()
    avg_penalty  = ref_data["ref_penalty_rate_shrunk"].mean()
    avg_home_adv = ref_data["ref_home_adv_shrunk"].mean()

    all_rows = []
    for _, row in canon.iterrows():
        gid    = row["game_id"]
        league = row["league_id"]

        if league == "EPL":
            r = ref_match[ref_match["game_id"] == gid]
            if r.empty or r.iloc[0]["referee"] != r.iloc[0]["referee"]:  # NaN check
                all_rows.append({
                    "game_id":             gid,
                    "referee":             None,
                    "ref_games_prior":     0,
                    "ref_avg_goals":       avg_goals,
                    "ref_red_card_rate":   avg_reds,
                    "ref_penalty_rate":    avg_penalty,
                    "ref_home_adv":        avg_home_adv,
                    "ref_available":       0,
                })
            else:
                rv = r.iloc[0]
                all_rows.append({
                    "game_id":             gid,
                    "referee":             rv["referee"],
                    "ref_games_prior":     rv["ref_games_prior"],
                    "ref_avg_goals":       rv["ref_avg_goals_shrunk"],
                    "ref_red_card_rate":   rv["ref_red_card_rate_shrunk"],
                    "ref_penalty_rate":    rv["ref_penalty_rate_shrunk"],
                    "ref_home_adv":        rv["ref_home_adv_shrunk"],
                    "ref_available":       1,
                })
        else:
            # BUN: no referee data
            all_rows.append({
                "game_id":           gid,
                "referee":           None,
                "ref_games_prior":   0,
                "ref_avg_goals":     avg_goals,
                "ref_red_card_rate": avg_reds,
                "ref_penalty_rate":  avg_penalty,
                "ref_home_adv":      avg_home_adv,
                "ref_available":     0,
            })

    out = pd.DataFrame(all_rows)
    out.to_parquet(OUTPUT_PATH, index=False)
    logger.info(f"Saved: {OUTPUT_PATH}  ({len(out):,} rows)")

    print(f"\n  AUDIT")
    print(f"  {'League':<8} {'N':>5} {'ref_available':>15}")
    for lg in ["EPL", "BUN"]:
        sub = out.merge(canon[["game_id","league_id"]], on="game_id")
        sub = sub[sub["league_id"] == lg]
        print(f"  {lg:<8} {len(sub):>5} {sub['ref_available'].mean():>15.1%}")

    print(f"\n  ref_avg_goals mean (EPL available): "
          f"{out[out['ref_available']==1]['ref_avg_goals'].mean():.3f}")
    print(f"  ref_red_card_rate mean:             "
          f"{out[out['ref_available']==1]['ref_red_card_rate'].mean():.3f}")
    print(f"\n  Saved → {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
