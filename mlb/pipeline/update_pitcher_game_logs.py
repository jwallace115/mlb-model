#!/usr/bin/env python3
"""
Incremental Pitcher Game Logs Updater
======================================
Fetches boxscores for recent completed games and appends new pitcher
appearances to mlb/data/pitcher_game_logs.parquet.

Runs daily before the MLB confirm pass so CS028 / CS013 / CS004 have fresh
reliever data. Idempotent — safe to run multiple times.

Usage:
  python3 mlb/pipeline/update_pitcher_game_logs.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

PGL_PATH = PROJECT_ROOT / "mlb" / "data" / "pitcher_game_logs.parquet"
BOXSCORE_CACHE = PROJECT_ROOT / "sim" / "data" / "cache" / "boxscores"
HANDEDNESS_CACHE = PROJECT_ROOT / "mlb" / "data" / "player_handedness_cache.json"
MLB_API = "https://statsapi.mlb.com/api/v1"

BOXSCORE_CACHE.mkdir(parents=True, exist_ok=True)


def load_handedness():
    if HANDEDNESS_CACHE.exists():
        with open(HANDEDNESS_CACHE) as f:
            return json.load(f)
    return {}


def fetch_boxscore(game_pk):
    """Fetch and cache a boxscore from MLB Stats API."""
    cache_file = BOXSCORE_CACHE / f"{game_pk}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    try:
        r = requests.get(f"{MLB_API}/game/{game_pk}/boxscore", timeout=15)
        if r.status_code == 200:
            data = r.json()
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return data
    except Exception:
        pass
    return None


def parse_pitchers(game_pk, boxscore, handedness, game_date, season,
                   home_team, away_team):
    """Parse pitcher rows from a boxscore. Returns list of dicts."""
    rows = []
    teams_data = boxscore.get("teams", {})

    for side in ["home", "away"]:
        team_data = teams_data.get(side, {})
        team_abbr = team_data.get("team", {}).get("abbreviation", "")
        opponent = away_team if side == "home" else home_team
        home_away = "H" if side == "home" else "A"
        players = team_data.get("players", {})
        pitchers_list = team_data.get("pitchers", [])

        for i, pid in enumerate(pitchers_list):
            pid_str = str(pid)
            player = players.get(f"ID{pid_str}", {})
            person = player.get("person", {})
            pitching = player.get("stats", {}).get("pitching", {})
            if not pitching:
                continue

            hand = handedness.get(pid_str, {})
            pitch_hand = hand.get("pitch_hand",
                                  person.get("pitchHand", {}).get("code", ""))

            ip_str = str(pitching.get("inningsPitched", "0"))
            try:
                ip = float(ip_str)
            except ValueError:
                ip = 0.0

            rows.append({
                "game_pk": game_pk,
                "game_date": game_date,
                "season": season,
                "player_id": int(pid),
                "player_name": person.get("fullName", ""),
                "team": team_abbr,
                "opponent": opponent,
                "home_away": home_away,
                "starter_flag": 1 if i == 0 else 0,
                "pitcher_hand": pitch_hand,
                "innings_pitched": ip,
                "batters_faced": int(pitching.get("battersFaced", 0) or 0),
                "pitches": int(pitching.get("numberOfPitches", 0) or 0),
                "hits_allowed": int(pitching.get("hits", 0) or 0),
                "runs_allowed": int(pitching.get("runs", 0) or 0),
                "earned_runs": int(pitching.get("earnedRuns", 0) or 0),
                "walks": int(pitching.get("baseOnBalls", 0) or 0),
                "strikeouts": int(pitching.get("strikeOuts", 0) or 0),
                "home_runs_allowed": int(pitching.get("homeRuns", 0) or 0),
                "ground_outs": int(pitching.get("groundOuts", 0) or 0),
                "fly_outs": int(pitching.get("flyOuts", 0) or 0),
                "air_outs": int(pitching.get("airOuts", 0) or 0),
            })
    return rows


def main():
    print(f"Pitcher Game Logs Updater — {datetime.now(timezone.utc).isoformat()}")

    # Load existing
    if PGL_PATH.exists():
        pgl = pd.read_parquet(PGL_PATH)
        max_date = pgl["game_date"].max()
        existing_pks = set(pgl["game_pk"].unique())
        print(f"  Existing: {len(pgl)} rows, max date={max_date}")
    else:
        pgl = pd.DataFrame()
        max_date = "2026-01-01"
        existing_pks = set()
        print("  No existing file — starting fresh")

    # Determine date range to scan (max_date through yesterday)
    scan_start = datetime.strptime(max_date, "%Y-%m-%d").date() - timedelta(days=1)
    scan_end = date.today() - timedelta(days=1)

    if scan_start > scan_end:
        print(f"  Already up to date (max={max_date}, yesterday={scan_end})")
        return

    print(f"  Scanning {scan_start} to {scan_end}...")

    handedness = load_handedness()

    # Fetch completed games from MLB schedule API
    new_rows = []
    games_processed = 0
    games_skipped = 0

    d = scan_start
    while d <= scan_end:
        ds = d.isoformat()
        try:
            r = requests.get(f"{MLB_API}/schedule",
                             params={"sportId": 1, "date": ds}, timeout=10)
            for db in r.json().get("dates", []):
                for g in db.get("games", []):
                    pk = g["gamePk"]
                    if pk in existing_pks:
                        games_skipped += 1
                        continue
                    if g.get("gameType") != "R":
                        continue
                    if g.get("status", {}).get("abstractGameState") != "Final":
                        continue

                    home = g["teams"]["home"]["team"].get("abbreviation", "")
                    away = g["teams"]["away"]["team"].get("abbreviation", "")

                    # Determine season from game date
                    season = d.year

                    boxscore = fetch_boxscore(pk)
                    if boxscore:
                        rows = parse_pitchers(pk, boxscore, handedness, ds,
                                              season, home, away)
                        new_rows.extend(rows)
                        games_processed += 1

                    time.sleep(0.1)
        except Exception as e:
            print(f"  Error on {ds}: {e}")

        d += timedelta(days=1)

    print(f"  Games processed: {games_processed}, skipped (existing): {games_skipped}")
    print(f"  New pitcher rows: {len(new_rows)}")

    if not new_rows:
        print("  No new data to append.")
        return

    # Append
    new_df = pd.DataFrame(new_rows)

    # Match dtypes to existing
    if not pgl.empty:
        for col in pgl.columns:
            if col in new_df.columns:
                try:
                    new_df[col] = new_df[col].astype(pgl[col].dtype)
                except (ValueError, TypeError):
                    pass

    updated = pd.concat([pgl, new_df], ignore_index=True)
    updated = updated.drop_duplicates(subset=["game_pk", "player_id"], keep="last")
    updated = updated.sort_values(["game_date", "game_pk", "team"]).reset_index(drop=True)

    updated.to_parquet(PGL_PATH, index=False)

    new_max = updated["game_date"].max()
    n_2026 = len(updated[updated["season"] == 2026])
    relievers_2026 = len(updated[(updated["season"] == 2026) & (updated["starter_flag"] == 0)])
    print(f"  Updated: {len(updated)} total rows, max date={new_max}")
    print(f"  2026: {n_2026} rows ({relievers_2026} reliever appearances)")

    # Auto-push
    subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
                     "Pitcher game logs incremental update"],
                   capture_output=True)


if __name__ == "__main__":
    main()
