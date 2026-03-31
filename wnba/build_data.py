#!/usr/bin/env python3
"""
WNBA Data Infrastructure — Phase 1 Builder
Builds canonical player and game data asset covering 2020-2025.
"""

import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

DATA_DIR = Path("wnba/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]
LEAGUE_ID = "10"  # WNBA
API_SLEEP = 1.0
RATE_LIMIT_SLEEP = 60

# Custom headers to avoid NBA.com blocking
CUSTOM_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}

# nba_api imports
from nba_api.stats.endpoints import (
    CommonAllPlayers,
    LeagueGameLog,
    BoxScoreTraditionalV3,
    TeamGameLog,
)


def api_call(endpoint_class, max_retries=2, **kwargs):
    """Call nba_api endpoint with rate limiting and retry. Non-recursive."""
    for attempt in range(max_retries + 1):
        time.sleep(API_SLEEP)
        try:
            result = endpoint_class(headers=CUSTOM_HEADERS, timeout=60, **kwargs)
            return result
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(w in err_str for w in ["rate", "429", "timeout", "timed out", "connection"])
            if is_transient and attempt < max_retries:
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                print(f"    Transient error (attempt {attempt+1}/{max_retries+1}), sleeping {wait}s: {e}", flush=True)
                time.sleep(wait)
                continue
            print(f"    API error (final): {e}", flush=True)
            return None


def minutes_to_decimal(min_str):
    """Convert 'MM:SS' or 'M:SS' to decimal minutes."""
    if pd.isna(min_str) or min_str is None or str(min_str).strip() == "":
        return 0.0
    s = str(min_str).strip()
    if ":" in s:
        parts = s.split(":")
        try:
            return int(parts[0]) + int(parts[1]) / 60.0
        except (ValueError, IndexError):
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# ===================================================================
# STEP 1 — PLAYER IDENTITY TABLE
# ===================================================================
def step1_player_identity():
    print("=" * 60, flush=True)
    print("STEP 1 — PLAYER IDENTITY TABLE", flush=True)
    print("=" * 60, flush=True)

    all_rows = []
    api_calls = 0

    for year in SEASONS:
        season_str = str(year)
        print(f"  Pulling players for {season_str}...", flush=True)
        result = api_call(
            CommonAllPlayers,
            league_id=LEAGUE_ID,
            season=season_str,
            is_only_current_season=0,
        )
        api_calls += 1

        if result is None:
            print(f"    FAILED for {season_str}", flush=True)
            continue

        df = result.get_data_frames()[0]
        print(f"    Raw rows: {len(df)}", flush=True)

        # Filter to WNBA players — they should have WNBA team info
        # The endpoint returns all players; filter by those with team info
        df = df[df["TEAM_ID"] != 0].copy() if "TEAM_ID" in df.columns else df

        df["season"] = year
        all_rows.append(df)

    if not all_rows:
        print("  ERROR: No player data retrieved", flush=True)
        return 0

    raw = pd.concat(all_rows, ignore_index=True)
    print(f"\n  Raw combined rows: {len(raw)}", flush=True)
    print(f"  Columns: {list(raw.columns)}", flush=True)

    # Standardize column names
    col_map = {}
    for c in raw.columns:
        cl = c.lower()
        if "person_id" in cl or c == "PERSON_ID":
            col_map[c] = "player_id"
        elif "display_first_last" in cl:
            col_map[c] = "player_name"
        elif c == "TEAM_ID":
            col_map[c] = "team_id"
        elif c == "TEAM_NAME":
            col_map[c] = "team_name"
        elif c == "TEAM_ABBREVIATION":
            col_map[c] = "team_abbreviation"
        elif c == "IS_ACTIVE":
            col_map[c] = "is_active"

    raw = raw.rename(columns=col_map)

    keep_cols = ["player_id", "player_name", "team_id", "team_name",
                 "team_abbreviation", "season", "is_active"]
    keep_cols = [c for c in keep_cols if c in raw.columns]
    identity = raw[keep_cols].drop_duplicates()

    identity.to_parquet(DATA_DIR / "player_identity.parquet", index=False)

    # Report
    n_unique = identity["player_id"].nunique()
    print(f"\n  Unique players: {n_unique}", flush=True)
    print(f"  Players per season:", flush=True)
    for y in SEASONS:
        sub = identity[identity["season"] == y]
        print(f"    {y}: {sub['player_id'].nunique()}", flush=True)

    multi = identity.groupby("player_id")["season"].nunique()
    multi_season = (multi > 1).sum()
    print(f"  Players in multiple seasons: {multi_season}", flush=True)
    print(f"  Saved: {DATA_DIR / 'player_identity.parquet'}", flush=True)
    print(f"  API calls: {api_calls}", flush=True)
    return api_calls


# ===================================================================
# STEP 2 — GAME INDEX
# ===================================================================
def step2_game_index():
    print("\n" + "=" * 60, flush=True)
    print("STEP 2 — GAME INDEX", flush=True)
    print("=" * 60, flush=True)

    all_rows = []
    api_calls = 0

    for year in SEASONS:
        season_str = str(year)
        for stype in ["Regular Season", "Playoffs"]:
            print(f"  Pulling {stype} {season_str}...", flush=True)
            result = api_call(
                LeagueGameLog,
                league_id=LEAGUE_ID,
                season=season_str,
                season_type_all_star=stype,
            )
            api_calls += 1

            if result is None:
                print(f"    FAILED", flush=True)
                continue

            df = result.get_data_frames()[0]
            if len(df) == 0:
                print(f"    No games", flush=True)
                continue

            df["season"] = year
            df["season_type"] = stype
            all_rows.append(df)
            print(f"    Rows: {len(df)}", flush=True)

    if not all_rows:
        print("  ERROR: No game data retrieved", flush=True)
        return 0

    raw = pd.concat(all_rows, ignore_index=True)
    print(f"\n  Raw combined rows: {len(raw)}", flush=True)
    print(f"  Columns: {list(raw.columns)}", flush=True)

    # LeagueGameLog returns one row per team per game
    # We need to pair them into home/away
    raw["GAME_DATE"] = pd.to_datetime(raw["GAME_DATE"])

    # Determine home/away from MATCHUP field (contains "vs." for home, "@" for away)
    raw["is_home"] = raw["MATCHUP"].str.contains("vs.", regex=False)

    home = raw[raw["is_home"] == True].copy()
    away = raw[raw["is_home"] == False].copy()

    games = home.merge(
        away[["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "PTS"]],
        on="GAME_ID",
        suffixes=("_home", "_away"),
    )

    game_index = pd.DataFrame({
        "game_id": games["GAME_ID"],
        "game_date": games["GAME_DATE"],
        "home_team_id": games["TEAM_ID_home"],
        "home_team_abbreviation": games["TEAM_ABBREVIATION_home"],
        "away_team_id": games["TEAM_ID_away"],
        "away_team_abbreviation": games["TEAM_ABBREVIATION_away"],
        "home_score": games["PTS_home"],
        "away_score": games["PTS_away"],
        "season": games["season"],
        "season_type": games["season_type"],
    })

    game_index = game_index.drop_duplicates(subset=["game_id"]).sort_values(
        ["season", "game_date", "game_id"]
    ).reset_index(drop=True)

    # Compute rest days per team
    # Build team appearance timeline
    team_games = []
    for _, row in game_index.iterrows():
        team_games.append({"team_id": row["home_team_id"], "game_date": row["game_date"],
                           "game_id": row["game_id"], "season": row["season"]})
        team_games.append({"team_id": row["away_team_id"], "game_date": row["game_date"],
                           "game_id": row["game_id"], "season": row["season"]})

    tg = pd.DataFrame(team_games).sort_values(["team_id", "season", "game_date"])
    tg["prev_game_date"] = tg.groupby(["team_id", "season"])["game_date"].shift(1)
    tg["rest_days"] = (tg["game_date"] - tg["prev_game_date"]).dt.days
    tg["back_to_back"] = tg["rest_days"] == 1

    rest_lookup = tg.set_index(["game_id", "team_id"])[["rest_days", "back_to_back"]]

    # Add rest for home and away
    game_index = game_index.merge(
        rest_lookup.rename(columns={"rest_days": "home_rest_days", "back_to_back": "home_b2b"}),
        left_on=["game_id", "home_team_id"], right_index=True, how="left",
    )
    game_index = game_index.merge(
        rest_lookup.rename(columns={"rest_days": "away_rest_days", "back_to_back": "away_b2b"}),
        left_on=["game_id", "away_team_id"], right_index=True, how="left",
    )

    game_index.to_parquet(DATA_DIR / "game_index.parquet", index=False)

    # Report
    print(f"\n  Total games: {len(game_index)}", flush=True)
    print(f"  Games per season:", flush=True)
    for y in SEASONS:
        sub = game_index[game_index["season"] == y]
        reg = sub[sub["season_type"] == "Regular Season"]
        po = sub[sub["season_type"] == "Playoffs"]
        print(f"    {y}: {len(reg)} regular + {len(po)} playoff = {len(sub)}", flush=True)

    b2b = tg["back_to_back"].sum()
    total_tg = len(tg[tg["rest_days"].notna()])
    print(f"  Back-to-back frequency: {b2b}/{total_tg} ({b2b/total_tg*100:.1f}%)", flush=True)
    print(f"  Saved: {DATA_DIR / 'game_index.parquet'}", flush=True)
    print(f"  API calls: {api_calls}", flush=True)
    return api_calls


# ===================================================================
# STEP 3 — PLAYER GAME LOGS (BOX SCORES)
# ===================================================================
def step3_player_game_logs():
    print("\n" + "=" * 60, flush=True)
    print("STEP 3 — PLAYER GAME LOGS (BOX SCORES)", flush=True)
    print("=" * 60, flush=True)

    game_index = pd.read_parquet(DATA_DIR / "game_index.parquet")
    identity = pd.read_parquet(DATA_DIR / "player_identity.parquet")

    # Resume: load existing processed data if available
    existing_file = DATA_DIR / "player_game_logs.parquet"
    existing_processed = None
    if existing_file.exists():
        existing_processed = pd.read_parquet(existing_file)
        completed_games = set(existing_processed["game_id"].unique())
        print(f"  Resuming: {len(existing_processed)} existing rows, {len(completed_games)} games done", flush=True)
    else:
        completed_games = set()

    api_calls = 0
    failed_games = []
    new_raw_rows = []

    for year in SEASONS:
        season_games = game_index[game_index["season"] == year]
        all_game_ids = season_games["game_id"].unique()
        game_ids = [g for g in all_game_ids if g not in completed_games]

        if len(game_ids) == 0:
            print(f"\n  Season {year}: already complete ({len(all_game_ids)} games)", flush=True)
            continue

        print(f"\n  Season {year}: {len(game_ids)} games to pull ({len(all_game_ids) - len(game_ids)} already done)", flush=True)

        season_rows = []
        for i, gid in enumerate(game_ids):
            if (i + 1) % 25 == 0 or i == 0:
                print(f"    Game {i+1}/{len(game_ids)} ({gid})...", flush=True)

            result = api_call(BoxScoreTraditionalV3, game_id=gid)
            api_calls += 1

            if result is None:
                failed_games.append({"game_id": gid, "season": year, "error": "api_failure"})
                continue

            dfs = result.get_data_frames()
            if len(dfs) == 0 or len(dfs[0]) == 0:
                failed_games.append({"game_id": gid, "season": year, "error": "empty_response"})
                continue

            player_df = dfs[0]  # PlayerStats is first result set
            player_df["season"] = year

            # Get game info
            game_row = season_games[season_games["game_id"] == gid].iloc[0]
            player_df["game_date"] = game_row["game_date"]
            player_df["season_type"] = game_row["season_type"]

            season_rows.append(player_df)

        if season_rows:
            season_df = pd.concat(season_rows, ignore_index=True)
            new_raw_rows.append(season_df)
            n_new = sum(len(r) for r in new_raw_rows)
            print(f"    Season {year}: {len(season_df)} player-game rows from {len(season_rows)} games", flush=True)

            # Process new raw data and merge with existing
            new_combined = pd.concat(new_raw_rows, ignore_index=True)
            new_processed = _save_player_game_logs(new_combined, game_index, identity, save=False)
            if existing_processed is not None:
                full = pd.concat([existing_processed, new_processed], ignore_index=True)
            else:
                full = new_processed
            full.to_parquet(DATA_DIR / "player_game_logs.parquet", index=False)
            print(f"    Incremental save: {len(full)} total rows", flush=True)

    if not new_raw_rows and existing_processed is None:
        print("  ERROR: No box score data retrieved", flush=True)
        return 0

    # Final save
    if new_raw_rows:
        new_combined = pd.concat(new_raw_rows, ignore_index=True)
        new_processed = _save_player_game_logs(new_combined, game_index, identity, save=False)
        if existing_processed is not None:
            final = pd.concat([existing_processed, new_processed], ignore_index=True)
        else:
            final = new_processed
        final = final.sort_values(["season", "game_date", "game_id", "team_id", "player_id"]).reset_index(drop=True)
        final.to_parquet(DATA_DIR / "player_game_logs.parquet", index=False)
    else:
        final = existing_processed

    if failed_games:
        print(f"\n  Failed games: {len(failed_games)}", flush=True)
        for fg in failed_games[:10]:
            print(f"    {fg}", flush=True)

    print(f"  API calls: {api_calls}", flush=True)
    return api_calls


def _save_player_game_logs(raw, game_index, identity, save=True):
    """Clean and save player game logs."""
    # Standardize columns — supports both V2 (uppercase) and V3 (camelCase) formats
    col_map = {
        # V2 format
        "PLAYER_ID": "player_id", "PLAYER_NAME": "player_name",
        "TEAM_ID": "team_id", "TEAM_ABBREVIATION": "team_abbreviation",
        "GAME_ID": "game_id",
        "MIN": "minutes_raw", "START_POSITION": "start_position",
        "PTS": "points", "REB": "rebounds_total",
        "OREB": "rebounds_offensive", "DREB": "rebounds_defensive",
        "AST": "assists", "STL": "steals", "BLK": "blocks",
        "TO": "turnovers", "PF": "personal_fouls", "PLUS_MINUS": "plus_minus",
        "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
        "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
        "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
        # V3 format (camelCase)
        "personId": "player_id", "teamId": "team_id", "teamTricode": "team_abbreviation",
        "gameId": "game_id",
        "minutes": "minutes_raw", "position": "start_position",
        "points": "points", "reboundsTotal": "rebounds_total",
        "reboundsOffensive": "rebounds_offensive", "reboundsDefensive": "rebounds_defensive",
        "assists": "assists", "steals": "steals", "blocks": "blocks",
        "turnovers": "turnovers", "foulsPersonal": "personal_fouls",
        "plusMinusPoints": "plus_minus",
        "fieldGoalsMade": "fgm", "fieldGoalsAttempted": "fga",
        "fieldGoalsPercentage": "fg_pct",
        "threePointersMade": "fg3m", "threePointersAttempted": "fg3a",
        "threePointersPercentage": "fg3_pct",
        "freeThrowsMade": "ftm", "freeThrowsAttempted": "fta",
        "freeThrowsPercentage": "ft_pct",
    }
    # Build player_name from V3 firstName + familyName if needed
    if "firstName" in raw.columns and "familyName" in raw.columns:
        raw["player_name_v3"] = raw["firstName"].fillna("") + " " + raw["familyName"].fillna("")
        col_map["player_name_v3"] = "player_name"

    available = {k: v for k, v in col_map.items() if k in raw.columns}
    df = raw.rename(columns=available).copy()

    # Carry through non-mapped columns
    for keep_col in ["game_date", "season", "season_type"]:
        if keep_col in raw.columns and keep_col not in df.columns:
            df[keep_col] = raw[keep_col].values

    # Convert minutes
    if "minutes_raw" in df.columns:
        df["minutes"] = df["minutes_raw"].apply(minutes_to_decimal)
    else:
        df["minutes"] = 0.0

    # Started flag: V3 uses 'position' field (non-empty = starter)
    if "start_position" in df.columns:
        df["started"] = df["start_position"].notna() & (df["start_position"] != "")
    else:
        df["started"] = np.nan

    df["starter_proxy_minutes20"] = df["minutes"] >= 20

    # Derived combo stats
    for col in ["points", "rebounds_total", "assists"]:
        if col not in df.columns:
            df[col] = 0
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).astype(int)
    df["rebounds_total"] = pd.to_numeric(df["rebounds_total"], errors="coerce").fillna(0).astype(int)
    df["assists"] = pd.to_numeric(df["assists"], errors="coerce").fillna(0).astype(int)

    df["pra"] = df["points"] + df["rebounds_total"] + df["assists"]
    df["pr"] = df["points"] + df["rebounds_total"]
    df["pa"] = df["points"] + df["assists"]
    df["ra"] = df["rebounds_total"] + df["assists"]

    # DNP flags
    df["dnp"] = df["minutes"] == 0
    df["dnp_reconstructed"] = False

    # Join context from game_index
    gi = game_index[["game_id", "home_team_id", "away_team_id",
                      "home_team_abbreviation", "away_team_abbreviation",
                      "home_rest_days", "away_rest_days",
                      "home_b2b", "away_b2b"]].copy()

    df = df.merge(gi, on="game_id", how="left")

    # Determine home/away and opponent
    df["home_away"] = np.where(
        df["team_id"] == df["home_team_id"], "HOME", "AWAY"
    )
    df["opponent_team_id"] = np.where(
        df["home_away"] == "HOME", df["away_team_id"], df["home_team_id"]
    )
    df["opponent_team_abbreviation"] = np.where(
        df["home_away"] == "HOME", df["away_team_abbreviation"], df["home_team_abbreviation"]
    )
    df["rest_days"] = np.where(
        df["home_away"] == "HOME", df["home_rest_days"], df["away_rest_days"]
    )
    df["back_to_back"] = np.where(
        df["home_away"] == "HOME", df["home_b2b"], df["away_b2b"]
    )

    # Drop merge helper columns
    drop_cols = ["home_team_id", "away_team_id", "home_team_abbreviation",
                 "away_team_abbreviation", "home_rest_days", "away_rest_days",
                 "home_b2b", "away_b2b", "minutes_raw", "start_position"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    df = df.sort_values(["season", "game_date", "game_id", "team_id", "player_id"]).reset_index(drop=True)

    if save:
        df.to_parquet(DATA_DIR / "player_game_logs.parquet", index=False)
    return df


# ===================================================================
# STEP 4 — TEAM GAME LOGS
# ===================================================================
def step4_team_game_logs():
    print("\n" + "=" * 60, flush=True)
    print("STEP 4 — TEAM GAME LOGS", flush=True)
    print("=" * 60, flush=True)

    game_index = pd.read_parquet(DATA_DIR / "game_index.parquet")

    # Get unique teams per season
    teams = set()
    for _, row in game_index.iterrows():
        teams.add((row["home_team_id"], row["season"]))
        teams.add((row["away_team_id"], row["season"]))

    teams_by_season = {}
    for tid, season in teams:
        teams_by_season.setdefault(season, set()).add(tid)

    all_rows = []
    api_calls = 0

    for year in SEASONS:
        season_teams = teams_by_season.get(year, set())
        print(f"  Season {year}: {len(season_teams)} teams", flush=True)

        for tid in sorted(season_teams):
            for stype in ["Regular Season", "Playoffs"]:
                result = api_call(
                    TeamGameLog,
                    team_id=int(tid),
                    league_id=LEAGUE_ID,
                    season=str(year),
                    season_type_all_star=stype,
                )
                api_calls += 1

                if result is None:
                    continue

                df = result.get_data_frames()[0]
                if len(df) == 0:
                    continue

                df["season"] = year
                df["season_type"] = stype
                all_rows.append(df)

    if not all_rows:
        print("  ERROR: No team game log data", flush=True)
        return 0

    raw = pd.concat(all_rows, ignore_index=True)
    print(f"  Raw rows: {len(raw)}", flush=True)
    print(f"  Columns: {list(raw.columns)}", flush=True)

    # Standardize
    col_map = {
        "Team_ID": "team_id",
        "TEAM_ID": "team_id",
        "TEAM_ABBREVIATION": "team_abbreviation",
        "Game_ID": "game_id",
        "GAME_ID": "game_id",
        "GAME_DATE": "game_date",
        "MATCHUP": "matchup",
        "WL": "win_loss",
        "PTS": "points_scored",
    }
    available = {k: v for k, v in col_map.items() if k in raw.columns}
    tgl = raw.rename(columns=available).copy()

    tgl["game_date"] = pd.to_datetime(tgl["game_date"])

    # Home/away from matchup
    if "matchup" in tgl.columns:
        tgl["home_away"] = np.where(
            tgl["matchup"].str.contains("vs.", regex=False), "HOME", "AWAY"
        )

    # Join opponent points and rest from game_index
    gi = game_index[["game_id", "home_team_id", "away_team_id",
                      "home_score", "away_score",
                      "home_rest_days", "away_rest_days",
                      "home_b2b", "away_b2b"]].copy()

    tgl = tgl.merge(gi, on="game_id", how="left")

    tgl["points_allowed"] = np.where(
        tgl["team_id"] == tgl["home_team_id"],
        tgl["away_score"], tgl["home_score"]
    )
    tgl["rest_days"] = np.where(
        tgl["team_id"] == tgl["home_team_id"],
        tgl["home_rest_days"], tgl["away_rest_days"]
    )
    tgl["back_to_back"] = np.where(
        tgl["team_id"] == tgl["home_team_id"],
        tgl["home_b2b"], tgl["away_b2b"]
    )

    # Season record
    tgl = tgl.sort_values(["team_id", "season", "game_date"]).reset_index(drop=True)
    tgl["win_flag"] = (tgl["win_loss"] == "W").astype(int)
    tgl["season_wins"] = tgl.groupby(["team_id", "season"])["win_flag"].cumsum()
    tgl["season_game_num"] = tgl.groupby(["team_id", "season"]).cumcount() + 1
    tgl["season_losses"] = tgl["season_game_num"] - tgl["season_wins"]
    tgl["season_record"] = tgl["season_wins"].astype(str) + "-" + tgl["season_losses"].astype(str)

    drop_cols = ["home_team_id", "away_team_id", "home_score", "away_score",
                 "home_rest_days", "away_rest_days", "home_b2b", "away_b2b", "win_flag"]
    tgl = tgl.drop(columns=[c for c in drop_cols if c in tgl.columns])

    tgl.to_parquet(DATA_DIR / "team_game_logs.parquet", index=False)

    print(f"  Saved: {len(tgl)} team-game rows", flush=True)
    print(f"  API calls: {api_calls}", flush=True)
    return api_calls


# ===================================================================
# STEP 5 — ENRICHED PLAYER GAME LOGS
# ===================================================================
def step5_enriched():
    print("\n" + "=" * 60, flush=True)
    print("STEP 5 — ENRICHED PLAYER GAME LOGS", flush=True)
    print("=" * 60, flush=True)

    pgl = pd.read_parquet(DATA_DIR / "player_game_logs.parquet")
    tgl = pd.read_parquet(DATA_DIR / "team_game_logs.parquet")

    # Join team context
    team_cols = tgl[["game_id", "team_id", "points_scored", "points_allowed", "win_loss"]].copy()
    team_cols = team_cols.rename(columns={
        "points_scored": "team_points_scored",
        "points_allowed": "team_points_allowed",
        "win_loss": "team_win_loss",
    })

    enriched = pgl.merge(team_cols, on=["game_id", "team_id"], how="left")

    # Opponent points
    opp_cols = tgl[["game_id", "team_id", "points_scored", "points_allowed"]].copy()
    opp_cols = opp_cols.rename(columns={
        "team_id": "opponent_team_id",
        "points_scored": "opponent_points_scored",
        "points_allowed": "opponent_points_allowed",
    })
    # opponent_team_id might be float from np.where, cast to match
    enriched["opponent_team_id"] = enriched["opponent_team_id"].astype(float)
    opp_cols["opponent_team_id"] = opp_cols["opponent_team_id"].astype(float)

    enriched = enriched.merge(opp_cols, on=["game_id", "opponent_team_id"], how="left")

    enriched.to_parquet(DATA_DIR / "player_game_logs_enriched.parquet", index=False)
    print(f"  Saved: {len(enriched)} enriched rows", flush=True)
    print(f"  Columns: {len(enriched.columns)}", flush=True)
    return 0


# ===================================================================
# STEP 6 — SEASON AGGREGATES
# ===================================================================
def step6_season_aggregates():
    print("\n" + "=" * 60, flush=True)
    print("STEP 6 — SEASON AGGREGATES", flush=True)
    print("=" * 60, flush=True)

    df = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")

    # Separate played vs DNP
    played = df[df["minutes"] > 0].copy()
    dnp = df[df["minutes"] == 0].copy()

    agg = played.groupby(["player_id", "player_name", "season"]).agg(
        games_played=("game_id", "count"),
        total_minutes=("minutes", "sum"),
        minutes_per_game=("minutes", "mean"),
        points_per_game=("points", "mean"),
        rebounds_per_game=("rebounds_total", "mean"),
        assists_per_game=("assists", "mean"),
        pra_per_game=("pra", "mean"),
        fg_pct=("fg_pct", "mean"),
        fg3_pct=("fg3_pct", "mean"),
        ft_pct=("ft_pct", "mean"),
        points_std=("points", "std"),
        points_mean=("points", "mean"),
        starter_proxy_count=("starter_proxy_minutes20", "sum"),
    ).reset_index()

    # DNP count
    dnp_count = dnp.groupby(["player_id", "season"])["game_id"].count().reset_index()
    dnp_count.columns = ["player_id", "season", "games_dnp"]
    agg = agg.merge(dnp_count, on=["player_id", "season"], how="left")
    agg["games_dnp"] = agg["games_dnp"].fillna(0).astype(int)

    # Derived
    agg["starter_proxy_rate"] = agg["starter_proxy_count"] / agg["games_played"]
    agg["consistency_score"] = agg["points_std"] / agg["points_mean"].replace(0, np.nan)

    # Round
    for c in ["minutes_per_game", "points_per_game", "rebounds_per_game",
              "assists_per_game", "pra_per_game", "fg_pct", "fg3_pct", "ft_pct",
              "consistency_score", "starter_proxy_rate"]:
        if c in agg.columns:
            agg[c] = agg[c].round(3)

    agg = agg.drop(columns=["points_std", "points_mean", "starter_proxy_count"], errors="ignore")

    agg.to_parquet(DATA_DIR / "season_aggregates.parquet", index=False)
    print(f"  Saved: {len(agg)} player-season rows", flush=True)
    print(f"  Players with 20+ games per season:", flush=True)
    for y in SEASONS:
        sub = agg[agg["season"] == y]
        n20 = (sub["games_played"] >= 20).sum()
        n30 = (sub["games_played"] >= 30).sum()
        print(f"    {y}: {n20} with 20+ GP, {n30} with 30+ GP (of {len(sub)} total)", flush=True)
    return 0


# ===================================================================
# STEP 7 — ROLLING FORM PROFILES
# ===================================================================
def step7_rolling_form():
    print("\n" + "=" * 60, flush=True)
    print("STEP 7 — ROLLING FORM PROFILES", flush=True)
    print("=" * 60, flush=True)

    df = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")

    # Only played games for rolling windows
    played = df[df["minutes"] > 0].copy()
    played = played.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)

    roll_cols = ["points", "rebounds_total", "assists", "pra", "minutes", "fg3m"]
    roll_cols = [c for c in roll_cols if c in played.columns]

    results = []

    for (pid, season), group in played.groupby(["player_id", "season"]):
        group = group.sort_values("game_date").reset_index(drop=True)
        n = len(group)

        for i in range(n):
            row = {"player_id": pid, "season": season,
                   "game_id": group.loc[i, "game_id"],
                   "game_date": group.loc[i, "game_date"]}

            # L5 window: games i-5 to i-1 (pregame only)
            l5_start = max(0, i - 5)
            l5_window = group.iloc[l5_start:i]
            l5_n = len(l5_window)

            row["rolling_5_games_played"] = l5_n
            row["l5_window_complete"] = l5_n >= 5

            if l5_n > 0:
                for c in roll_cols:
                    row[f"rolling_5_{c}"] = l5_window[c].sum()
                    row[f"{c.replace('rebounds_total','rebounds').replace('fg3m','fg3m')}_per_game_L5"] = l5_window[c].mean()
                row["points_std_L5"] = l5_window["points"].std() if l5_n > 1 else 0.0

                # Form trend: last 2 vs prior 3
                if l5_n >= 5:
                    last2_avg = l5_window.iloc[-2:]["points"].mean()
                    prior3_avg = l5_window.iloc[:3]["points"].mean()
                    diff = last2_avg - prior3_avg
                    if diff > 2:
                        row["form_trend"] = "UP"
                    elif diff < -2:
                        row["form_trend"] = "DOWN"
                    else:
                        row["form_trend"] = "FLAT"
                else:
                    row["form_trend"] = np.nan

            # L10 window: games i-10 to i-1
            l10_start = max(0, i - 10)
            l10_window = group.iloc[l10_start:i]
            l10_n = len(l10_window)

            row["rolling_10_games_played"] = l10_n
            row["l10_window_complete"] = l10_n >= 10

            if l10_n > 0:
                for c in roll_cols:
                    row[f"rolling_10_{c}"] = l10_window[c].sum()
                    col_name = c.replace("rebounds_total", "rebounds").replace("fg3m", "fg3m")
                    row[f"{col_name}_per_game_L10"] = l10_window[c].mean()
                row["points_std_L10"] = l10_window["points"].std() if l10_n > 1 else 0.0

            results.append(row)

    rolling = pd.DataFrame(results)

    # Rename column keys for consistency
    rename_map = {}
    for c in rolling.columns:
        if "rebounds_total" in c:
            rename_map[c] = c.replace("rebounds_total", "rebounds")
    rolling = rolling.rename(columns=rename_map)

    rolling.to_parquet(DATA_DIR / "rolling_form.parquet", index=False)

    # Report
    total = len(rolling)
    l5_complete = rolling["l5_window_complete"].sum()
    l10_complete = rolling["l10_window_complete"].sum()
    l5_partial = ((rolling["rolling_5_games_played"] > 0) & (~rolling["l5_window_complete"])).sum()
    l10_partial = ((rolling["rolling_10_games_played"] > 0) & (~rolling["l10_window_complete"])).sum()
    no_window = (rolling["rolling_5_games_played"] == 0).sum()

    print(f"  Total rows: {total}", flush=True)
    print(f"  L5 complete: {l5_complete} ({l5_complete/total*100:.1f}%)", flush=True)
    print(f"  L5 partial: {l5_partial} ({l5_partial/total*100:.1f}%)", flush=True)
    print(f"  L10 complete: {l10_complete} ({l10_complete/total*100:.1f}%)", flush=True)
    print(f"  L10 partial: {l10_partial} ({l10_partial/total*100:.1f}%)", flush=True)
    print(f"  No window (first game): {no_window} ({no_window/total*100:.1f}%)", flush=True)
    return 0


# ===================================================================
# STEP 8 — COVERAGE REPORT
# ===================================================================
def step8_coverage_report():
    print("\n" + "=" * 60, flush=True)
    print("STEP 8 — COVERAGE REPORT", flush=True)
    print("=" * 60, flush=True)

    pgl = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")
    rolling = pd.read_parquet(DATA_DIR / "rolling_form.parquet")
    agg = pd.read_parquet(DATA_DIR / "season_aggregates.parquet")

    lines = []
    lines.append("WNBA DATA INFRASTRUCTURE — COVERAGE REPORT")
    lines.append("=" * 60)

    # SECTION A — Volume
    lines.append("\nSECTION A — Volume")
    lines.append("-" * 40)
    played = pgl[pgl["minutes"] > 0]
    dnp = pgl[pgl["minutes"] == 0]
    lines.append(f"  Total player-game records: {len(pgl)}")
    lines.append(f"  Played rows (minutes > 0): {len(played)}")
    lines.append(f"  DNP rows (minutes == 0): {len(dnp)}")
    lines.append(f"  DNP reconstructed: {pgl['dnp_reconstructed'].sum()}")
    lines.append(f"  Unique players: {pgl['player_id'].nunique()}")
    lines.append(f"  Games per season:")
    for y in SEASONS:
        sub = pgl[pgl["season"] == y]
        lines.append(f"    {y}: {sub['game_id'].nunique()} games, {len(sub)} player-game rows")

    # SECTION B — Field Coverage
    lines.append("\nSECTION B — Field Coverage (% non-null)")
    lines.append("-" * 40)
    key_fields = ["minutes", "points", "rebounds_total", "assists", "steals",
                  "blocks", "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct",
                  "ftm", "fta", "ft_pct", "plus_minus", "started"]
    for f in key_fields:
        if f in pgl.columns:
            pct = pgl[f].notna().mean() * 100
            lines.append(f"  {f:30s}: {pct:.1f}%")
        else:
            lines.append(f"  {f:30s}: MISSING")

    # SECTION C — Player Depth
    lines.append("\nSECTION C — Player Depth (games played per player per season)")
    lines.append("-" * 40)
    gp = played.groupby(["player_id", "season"])["game_id"].count()
    for pct_label, pct_val in [("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90)]:
        lines.append(f"  {pct_label}: {gp.quantile(pct_val/100):.0f}")
    n20 = (gp >= 20).sum()
    n30 = (gp >= 30).sum()
    lines.append(f"  Players with 20+ games: {n20} ({n20/len(gp)*100:.1f}%)")
    lines.append(f"  Players with 30+ games: {n30} ({n30/len(gp)*100:.1f}%)")

    # SECTION D — Rolling Form Coverage
    lines.append("\nSECTION D — Rolling Form Coverage")
    lines.append("-" * 40)
    total_r = len(rolling)
    l5c = rolling["l5_window_complete"].sum()
    l10c = rolling["l10_window_complete"].sum()
    l5p = ((rolling["rolling_5_games_played"] > 0) & (~rolling["l5_window_complete"])).sum()
    l10p = ((rolling["rolling_10_games_played"] > 0) & (~rolling["l10_window_complete"])).sum()
    no_w = (rolling["rolling_5_games_played"] == 0).sum()
    lines.append(f"  Total rows: {total_r}")
    lines.append(f"  L5 complete: {l5c} ({l5c/total_r*100:.1f}%)")
    lines.append(f"  L5 partial: {l5p} ({l5p/total_r*100:.1f}%)")
    lines.append(f"  L10 complete: {l10c} ({l10c/total_r*100:.1f}%)")
    lines.append(f"  L10 partial: {l10p} ({l10p/total_r*100:.1f}%)")
    lines.append(f"  No window (first game): {no_w} ({no_w/total_r*100:.1f}%)")

    # SECTION E — Known Gaps
    lines.append("\nSECTION E — Known Gaps")
    lines.append("-" * 40)
    lines.append("  - Usage proxy: SKIPPED in v1 (team possessions not available)")
    lines.append("  - DNP reconstruction: skipped where roster data insufficient")
    lines.append(f"  - Started flag actual coverage: {pgl['started'].notna().mean()*100:.1f}%")

    report = "\n".join(lines)
    print(report, flush=True)

    with open(DATA_DIR / "wnba_data_summary.txt", "w") as f:
        f.write(report)

    print(f"\n  Saved: {DATA_DIR / 'wnba_data_summary.txt'}", flush=True)


# ===================================================================
# MAIN
# ===================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-step", type=int, default=1, help="Start from step N")
    args = parser.parse_args()
    start = args.from_step

    total_api_calls = 0

    if start <= 1:
        if not (DATA_DIR / "player_identity.parquet").exists():
            total_api_calls += step1_player_identity()
        else:
            print("Step 1: player_identity.parquet exists, skipping", flush=True)

    if start <= 2:
        if not (DATA_DIR / "game_index.parquet").exists():
            total_api_calls += step2_game_index()
        else:
            print("Step 2: game_index.parquet exists, skipping", flush=True)

    if start <= 3:
        total_api_calls += step3_player_game_logs()  # has built-in resume

    if start <= 4:
        if not (DATA_DIR / "team_game_logs.parquet").exists():
            total_api_calls += step4_team_game_logs()
        else:
            print("Step 4: team_game_logs.parquet exists, skipping", flush=True)

    if start <= 5:
        step5_enriched()
    if start <= 6:
        step6_season_aggregates()
    if start <= 7:
        step7_rolling_form()
    if start <= 8:
        step8_coverage_report()

    print(f"\n{'='*60}", flush=True)
    print(f"COMPLETE — Total API calls: {total_api_calls}", flush=True)
    print(f"{'='*60}", flush=True)
