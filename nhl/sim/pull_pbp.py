#!/usr/bin/env python3
"""
Pull NHL play-by-play and boxscores from api-web.nhle.com for regular-season games.

Saves gzipped raw JSON to nhl/cache/pbp/{gameId}.json.gz (PBP mode) or
plain JSON to nhl/cache/boxscore_{gameId}.json (boxscore mode).
Resume: existing files are skipped. Only games with gameState OFF/FINAL.
A 404 stops the current season (game ID is past the season's last game).

Usage:
  python3 nhl/sim/pull_pbp.py --seasons 2021,2022,2023,2024,2025
  python3 nhl/sim/pull_pbp.py --seasons 2010,2011,2012 --boxscore
  python3 nhl/sim/pull_pbp.py --seasons 2024 --dry-run
"""
import argparse, gzip, hashlib, json, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
PBP_CACHE = ROOT / "nhl" / "cache" / "pbp"
BOX_CACHE = ROOT / "nhl" / "cache"
NHL_API = "https://api-web.nhle.com/v1"

# Measured game counts per season (D1 probe: binary search on last valid game ID)
GAMES_PER_SEASON = {
    2010: 1230, 2011: 1230, 2012: 720,  2013: 1230, 2014: 1230,
    2015: 1230, 2016: 1230, 2017: 1271, 2018: 1271, 2019: 1082,
    2020: 868,  2021: 1312, 2022: 1312, 2023: 1312, 2024: 1312,
    2025: 1312,
}


def game_ids_for_season(season):
    n = GAMES_PER_SEASON.get(season, 1312)
    return [f"{season}02{i:04d}" for i in range(1, n + 1)]


def pull_pbp(game_id):
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


def pull_boxscore(game_id):
    """Pull boxscore for one game. Returns (data, status_code)."""
    url = f"{NHL_API}/gamecenter/{game_id}/boxscore"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return None, r.status_code
    data = r.json()
    state = data.get("gameState", "")
    if state not in ("OFF", "FINAL"):
        return None, f"state={state}"
    return data, 200


def pbp_path(gid):
    return PBP_CACHE / f"{gid}.json.gz"


def box_path(gid):
    return BOX_CACHE / f"boxscore_{gid}.json"


def main():
    ap = argparse.ArgumentParser(description="Pull NHL play-by-play / boxscores")
    ap.add_argument("--seasons", required=True, help="comma-separated start years")
    ap.add_argument("--boxscore", action="store_true", help="pull boxscores instead of PBP")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seasons = [int(s) for s in args.seasons.split(",")]
    mode = "boxscore" if args.boxscore else "pbp"
    path_fn = box_path if args.boxscore else pbp_path
    pull_fn = pull_boxscore if args.boxscore else pull_pbp
    cache_dir = BOX_CACHE if args.boxscore else PBP_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Runtime pre-check
    total_todo = 0
    for season in seasons:
        gids = game_ids_for_season(season)
        todo = sum(1 for gid in gids if not path_fn(gid).exists())
        total_todo += todo
    est_per_request = 0.55  # ~0.3s request + 0.25s sleep
    est_seconds = total_todo * est_per_request
    est_hours = est_seconds / 3600
    print(f"Runtime pre-check ({mode}):")
    print(f"  Total games to pull: {total_todo}")
    print(f"  Estimated time: {total_todo} x {est_per_request}s = {est_seconds:.0f}s = {est_hours:.1f}h")
    if est_hours > 2.5:
        print(f"  WARNING: estimated {est_hours:.1f}h exceeds 2.5h limit")

    for season in seasons:
        gids = game_ids_for_season(season)
        existing = sum(1 for gid in gids if path_fn(gid).exists())
        todo = [gid for gid in gids if not path_fn(gid).exists()]

        print(f"\nSeason {season}-{season+1} ({mode}): {len(gids)} games, "
              f"{existing} cached, {len(todo)} to pull")

        if args.dry_run or not todo:
            continue

        saved = 0
        failed_404 = 0
        skipped_state = 0
        other_errors = 0
        t0 = time.time()

        for i, gid in enumerate(todo):
            data, status = pull_fn(gid)
            if data is not None:
                p = path_fn(gid)
                if args.boxscore:
                    p.write_text(json.dumps(data))
                else:
                    with gzip.open(p, "wt") as f:
                        json.dump(data, f)
                saved += 1
            elif status == 404:
                failed_404 += 1
                if failed_404 >= 3:
                    print(f"  3 consecutive-range 404s at {gid} — season {season} ends here")
                    break
            elif isinstance(status, str) and "state=" in status:
                skipped_state += 1
                failed_404 = 0  # reset 404 counter
            else:
                other_errors += 1
                failed_404 = 0

            if status != 404:
                failed_404 = 0  # reset consecutive 404 counter on any non-404

            if (i + 1) % 200 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"  [{i+1}/{len(todo)}] saved={saved} 404={failed_404} "
                      f"skipped={skipped_state} err={other_errors} "
                      f"{rate:.1f} req/s", flush=True)

            time.sleep(0.25)

        elapsed = time.time() - t0
        print(f"  Season {season}: saved={saved}, 404={failed_404}, "
              f"skipped_state={skipped_state}, errors={other_errors}, "
              f"time={elapsed:.0f}s")

    print(f"\nDone ({mode}).")


if __name__ == "__main__":
    main()
