#!/usr/bin/env python3
"""
Pull NHL play-by-play from api-web.nhle.com for regular-season games.

Saves gzipped raw JSON to nhl/cache/pbp/{gameId}.json.gz.
Resume: existing files are skipped. Only games with gameState OFF/FINAL.

Usage:
  python3 nhl/sim/pull_pbp.py --seasons 2021,2022,2023,2024,2025
  python3 nhl/sim/pull_pbp.py --seasons 2024 --dry-run
"""
import argparse, gzip, json, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "nhl" / "cache" / "pbp"
NHL_API = "https://api-web.nhle.com/v1"

# Regular season game IDs: {season_start_year}02{0001..1312}
# The season with start year S has game IDs S020001 .. S021312 (82 games x 32 teams / 2)
GAMES_PER_SEASON = 1312


def get_schedule_game_ids(season_start):
    """Get all regular-season game IDs from the NHL schedule API."""
    game_ids = []
    # The schedule endpoint returns games by date; we can also construct IDs directly
    # Regular season IDs are {season}02{seq:04d} where season = start_year
    # But we should verify against the schedule to get actual completed games

    # Try the schedule endpoint for the full season
    start_date = f"{season_start}-10-01"
    end_date = f"{season_start + 1}-06-30"

    # Use the standings endpoint to verify season exists, then construct IDs
    # The game IDs are deterministic: {season}020001 through {season}021312
    for i in range(1, GAMES_PER_SEASON + 1):
        game_ids.append(f"{season_start}02{i:04d}")
    return game_ids


def pull_game(game_id):
    """Pull play-by-play for one game. Returns (data, status_code)."""
    url = f"{NHL_API}/gamecenter/{game_id}/play-by-play"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return None, r.status_code
    data = r.json()
    state = data.get("gameState", "")
    if state not in ("OFF", "FINAL"):
        return None, f"state={state}"
    return data, 200


def main():
    ap = argparse.ArgumentParser(description="Pull NHL play-by-play")
    ap.add_argument("--seasons", required=True, help="comma-separated start years")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seasons = [int(s) for s in args.seasons.split(",")]
    CACHE.mkdir(parents=True, exist_ok=True)

    for season in seasons:
        game_ids = get_schedule_game_ids(season)
        existing = sum(1 for gid in game_ids if (CACHE / f"{gid}.json.gz").exists())
        todo = [gid for gid in game_ids if not (CACHE / f"{gid}.json.gz").exists()]

        print(f"Season {season}-{season+1}: {len(game_ids)} games, {existing} cached, {len(todo)} to pull")

        if args.dry_run:
            continue

        saved = 0
        failed = 0
        skipped_state = 0

        for i, gid in enumerate(todo):
            data, status = pull_game(gid)
            if data is not None:
                path = CACHE / f"{gid}.json.gz"
                with gzip.open(path, "wt") as f:
                    json.dump(data, f)
                saved += 1
            elif status == 200:
                pass  # shouldn't happen
            elif isinstance(status, str) and "state=" in status:
                skipped_state += 1
            else:
                failed += 1

            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{len(todo)}] saved={saved} failed={failed} skipped_state={skipped_state}")

            time.sleep(0.25)

        print(f"  Season {season}: saved={saved}, failed={failed}, skipped_state={skipped_state}")

    # Report play typeDescKey vocabulary for the last season pulled
    if not args.dry_run and seasons:
        last_season = seasons[-1]
        type_counts = {}
        sample_count = 0
        for gid in get_schedule_game_ids(last_season):
            path = CACHE / f"{gid}.json.gz"
            if not path.exists():
                continue
            with gzip.open(path, "rt") as f:
                data = json.load(f)
            for play in data.get("plays", []):
                tk = play.get("typeDescKey", "unknown")
                type_counts[tk] = type_counts.get(tk, 0) + 1
            sample_count += 1
            if sample_count >= 100:
                break
        if type_counts:
            print(f"\nPlay typeDescKey vocabulary (season {last_season}, {sample_count} games):")
            for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
                print(f"  {k}: {v}")

        # Check situationCode presence
        has_sc = 0
        total_plays = 0
        for gid in get_schedule_game_ids(last_season)[:50]:
            path = CACHE / f"{gid}.json.gz"
            if not path.exists():
                continue
            with gzip.open(path, "rt") as f:
                data = json.load(f)
            for play in data.get("plays", []):
                total_plays += 1
                if play.get("situationCode"):
                    has_sc += 1
        if total_plays:
            print(f"\nsituationCode present: {has_sc}/{total_plays} plays ({has_sc/total_plays:.1%})")


if __name__ == "__main__":
    main()
