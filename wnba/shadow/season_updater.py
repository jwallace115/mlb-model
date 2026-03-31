#!/usr/bin/env python3
"""WNBA Shadow — Season Updater (Component 5). Runs 10:00 AM ET nightly."""
import os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

DATA_DIR = Path("wnba/data")
SHADOW_DIR = Path("wnba/shadow")
RUN_MODE = os.environ.get("RUN_MODE", "test")

ROLE_ORDER = {"Deep Bench": 1, "Bench": 2, "Rotation": 3, "Starter": 4, "Starter-Heavy": 5}

HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.nba.com/",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def assign_role(start_rate, avg_minutes, gp=99):
    if gp < 5: return "Deep Bench"
    if start_rate >= 0.80 and avg_minutes >= 28: return "Starter-Heavy"
    if start_rate >= 0.50 and avg_minutes >= 22: return "Starter"
    if start_rate < 0.50 and avg_minutes >= 14: return "Rotation"
    if avg_minutes >= 7: return "Bench"
    return "Deep Bench"


def minutes_to_decimal(min_str):
    if pd.isna(min_str) or min_str is None or str(min_str).strip() == "":
        return 0.0
    s = str(min_str).strip()
    if ":" in s:
        parts = s.split(":")
        try: return int(parts[0]) + int(parts[1]) / 60.0
        except: return 0.0
    try: return float(s)
    except: return 0.0


def run(update_date=None):
    """Update data for games played on update_date (yesterday by default)."""
    if update_date is None:
        update_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print("WNBA Season Updater | %s | mode=%s" % (update_date, RUN_MODE), flush=True)

    enr = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")
    enr["game_date"] = pd.to_datetime(enr["game_date"])
    gi = pd.read_parquet(DATA_DIR / "game_index.parquet")

    # Check if update_date already in data
    existing_dates = enr["game_date"].dt.strftime("%Y-%m-%d").unique()
    if update_date in existing_dates:
        print("Data for %s already exists. Skipping fetch." % update_date, flush=True)
    else:
        if RUN_MODE == "test":
            print("TEST MODE: data for %s should already exist in enriched file." % update_date, flush=True)
        else:
            # Fetch box scores for yesterday's games
            from nba_api.stats.endpoints import BoxScoreTraditionalV3, LeagueGameLog
            print("Fetching games for %s..." % update_date, flush=True)
            # Get game IDs
            time.sleep(1)
            lg = LeagueGameLog(league_id="10", season=str(datetime.now().year),
                               season_type_all_star="Regular Season", headers=HEADERS, timeout=60)
            games_df = lg.get_data_frames()[0]
            games_df["GAME_DATE"] = pd.to_datetime(games_df["GAME_DATE"])
            today_games = games_df[games_df["GAME_DATE"].dt.strftime("%Y-%m-%d") == update_date]
            game_ids = today_games["GAME_ID"].unique()
            print("Found %d games" % len(game_ids), flush=True)

            for gid in game_ids:
                time.sleep(1)
                try:
                    result = BoxScoreTraditionalV3(game_id=gid, headers=HEADERS, timeout=60)
                    # Process and append... (simplified for now)
                    print("  Fetched %s" % gid, flush=True)
                except Exception as e:
                    print("  Failed %s: %s" % (gid, e), flush=True)

    # Recompute rolling features for players who played on update_date
    played = enr[(enr["game_date"].dt.strftime("%Y-%m-%d") == update_date) & (enr["minutes"] > 0)]
    affected_players = played["player_id"].unique()
    print("Affected players: %d" % len(affected_players), flush=True)

    if len(affected_players) == 0:
        print("No players to update. Exiting.", flush=True)
        return

    # Recompute rolling features
    all_played = enr[enr["minutes"] > 0].copy()
    all_played = all_played.sort_values(["player_id", "game_date"])

    update_count = 0
    for pid in affected_players:
        pp = all_played[all_played["player_id"] == pid].sort_values("game_date")
        if len(pp) < 3:
            continue
        # Update L5, L8 for last row
        last_idx = pp.index[-1]
        l5 = pp.tail(6).head(5)["minutes"].mean() if len(pp) >= 6 else pp.iloc[:-1]["minutes"].mean()
        l8 = pp.tail(9).head(8)["minutes"].mean() if len(pp) >= 9 else pp.iloc[:-1]["minutes"].mean()
        sr5 = pp.tail(6).head(5)["started"].mean() if len(pp) >= 6 else pp.iloc[:-1]["started"].mean()
        sr8 = pp.tail(9).head(8)["started"].mean() if len(pp) >= 9 else pp.iloc[:-1]["started"].mean()

        enr.loc[last_idx, "rolling_avg_min_L5"] = round(l5, 2)
        enr.loc[last_idx, "rolling_avg_min_L8"] = round(l8, 2)
        enr.loc[last_idx, "rolling_role_L5"] = assign_role(sr5, l5)
        enr.loc[last_idx, "rolling_role_L8"] = assign_role(sr8, l8)
        update_count += 1

    enr.to_parquet(DATA_DIR / "player_game_logs_enriched.parquet", index=False)
    print("Updated rolling features for %d players" % update_count, flush=True)

    # Log
    with open(SHADOW_DIR / "p6_shadow_log.txt", "a") as f:
        f.write("%s | season_updater | %s | %d players updated\n" % (
            datetime.now().isoformat(), update_date, update_count))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(update_date=args.date)
