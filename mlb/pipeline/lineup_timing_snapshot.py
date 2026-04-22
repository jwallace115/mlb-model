#!/usr/bin/env python3
"""
lineup_timing_snapshot.py

Hits MLB Stats API lineup endpoint and logs
what lineups are available at the time of the call.
Run 4x daily via cron to build timing dataset.
"""

import requests
import json
import os
from datetime import datetime, timezone
import pytz

ET = pytz.timezone("America/New_York")

def get_todays_lineup_coverage():
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)
    today_str = now_et.strftime("%Y-%m-%d")
    snapshot_time_et = now_et.strftime("%H:%M")
    snapshot_label = now_et.strftime("%Y-%m-%d_%H%M_ET")

    url = (
        "https://statsapi.mlb.com/api/v1/schedule"
        f"?sportId=1&date={today_str}&hydrate=lineups"
    )

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        return None

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            game_pk = game.get("gamePk")
            status = game.get("status", {}).get(
                "detailedState", "Unknown"
            )

            game_time_utc = game.get("gameDate", "")
            if game_time_utc:
                try:
                    gt = datetime.fromisoformat(
                        game_time_utc.replace("Z", "+00:00")
                    )
                    gt_et = gt.astimezone(ET)
                    first_pitch_et = gt_et.strftime("%H:%M")
                    hours_to_pitch = round(
                        (gt - now_utc).total_seconds() / 3600, 2
                    )
                except:
                    first_pitch_et = "unknown"
                    hours_to_pitch = None
            else:
                first_pitch_et = "unknown"
                hours_to_pitch = None

            lineups = game.get("lineups", {})
            home_lineup = lineups.get("homePlayers", [])
            away_lineup = lineups.get("awayPlayers", [])
            lineup_confirmed = (
                len(home_lineup) == 9 and
                len(away_lineup) == 9
            )

            games.append({
                "game_pk": game_pk,
                "game_date": today_str,
                "snapshot_time_et": snapshot_time_et,
                "first_pitch_et": first_pitch_et,
                "hours_to_first_pitch": hours_to_pitch,
                "status": status,
                "home_lineup_count": len(home_lineup),
                "away_lineup_count": len(away_lineup),
                "lineup_confirmed": lineup_confirmed,
            })

    total = len(games)
    confirmed = sum(1 for g in games if g["lineup_confirmed"])
    coverage_pct = round(
        confirmed / total * 100, 1
    ) if total > 0 else 0

    result = {
        "snapshot_label": snapshot_label,
        "snapshot_time_et": snapshot_time_et,
        "date": today_str,
        "total_games": total,
        "lineups_confirmed": confirmed,
        "coverage_pct": coverage_pct,
        "games": games,
    }

    out_dir = (
        "/root/mlb-model/mlb/data/lineups/snapshots_2026"
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir, f"lineup_snapshot_{snapshot_label}.json"
    )
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    log_path = os.path.join(
        out_dir, "lineup_timing_log_2026.jsonl"
    )
    summary = {
        "snapshot_label": snapshot_label,
        "snapshot_time_et": snapshot_time_et,
        "date": today_str,
        "total_games": total,
        "lineups_confirmed": confirmed,
        "coverage_pct": coverage_pct,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(summary) + "\n")

    print(
        f"[{snapshot_label}] "
        f"{confirmed}/{total} games with lineups "
        f"({coverage_pct}%)"
    )
    return result

if __name__ == "__main__":
    get_todays_lineup_coverage()
