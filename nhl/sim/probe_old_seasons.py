#!/usr/bin/env python3
"""D1 probe: check NHL API data availability for 2010-2020 seasons.

Tests 6 games for PBP field presence (situationCode, shot coords, etc.)
and counts regular-season games per season from the schedule endpoint.

Usage:
  python3 nhl/sim/probe_old_seasons.py
"""
import json, sys, time
from pathlib import Path

import requests

PROBE_GAMES = [
    "2010020001",  # 2010-11
    "2012020001",  # 2012-13 lockout
    "2013020001",  # 2013-14
    "2016020001",  # 2016-17
    "2019020001",  # 2019-20
    "2020020001",  # 2020-21
]

NHL_API = "https://api-web.nhle.com/v1"


def probe_pbp(game_id):
    """Fetch PBP and report field availability."""
    url = f"{NHL_API}/gamecenter/{game_id}/play-by-play"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return {"game_id": game_id, "http": r.status_code, "error": "non-200"}
    data = r.json()
    state = data.get("gameState", "")
    plays = data.get("plays", [])
    n_plays = len(plays)

    # Field presence
    has_typeDescKey = sum(1 for p in plays if p.get("typeDescKey"))
    has_situationCode = sum(1 for p in plays if p.get("situationCode"))
    has_periodNum = sum(1 for p in plays if p.get("periodDescriptor", {}).get("number") is not None)
    has_timeInPeriod = sum(1 for p in plays if p.get("timeInPeriod"))

    # Shot-type plays with coordinates
    shot_types = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
    shot_plays = [p for p in plays if p.get("typeDescKey") in shot_types]
    n_shots = len(shot_plays)
    shots_with_xy = sum(1 for p in shot_plays
                        if p.get("details", {}).get("xCoord") is not None
                        and p.get("details", {}).get("yCoord") is not None)

    # shootingPlayerId / goalieInNetId
    has_shooter = sum(1 for p in shot_plays if p.get("details", {}).get("shootingPlayerId") is not None)
    has_goalie = sum(1 for p in shot_plays if p.get("details", {}).get("goalieInNetId") is not None)

    return {
        "game_id": game_id,
        "season": f"{game_id[:4]}-{int(game_id[:4])+1}",
        "http": 200,
        "gameState": state,
        "n_plays": n_plays,
        "typeDescKey": f"{has_typeDescKey}/{n_plays}",
        "situationCode": f"{has_situationCode}/{n_plays}",
        "periodNum": f"{has_periodNum}/{n_plays}",
        "timeInPeriod": f"{has_timeInPeriod}/{n_plays}",
        "shot_plays": n_shots,
        "shots_with_xy": f"{shots_with_xy}/{n_shots}" if n_shots else "0/0",
        "shootingPlayerId": f"{has_shooter}/{n_shots}" if n_shots else "0/0",
        "goalieInNetId": f"{has_goalie}/{n_shots}" if n_shots else "0/0",
    }


def probe_boxscore(game_id):
    """Fetch boxscore and report key fields."""
    url = f"{NHL_API}/gamecenter/{game_id}/boxscore"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return {"game_id": game_id, "http": r.status_code}
    data = r.json()
    result = {
        "game_id": game_id,
        "http": 200,
        "gameState": data.get("gameState", ""),
        "gameDate": data.get("gameDate", ""),
        "home_abbrev": data.get("homeTeam", {}).get("abbrev", ""),
        "away_abbrev": data.get("awayTeam", {}).get("abbrev", ""),
    }
    # Check goalie stats
    for side in ("homeTeam", "awayTeam"):
        stats = data.get("playerByGameStats", {}).get(side, {})
        goalies = stats.get("goalies", [])
        result[f"{side}_goalies"] = len(goalies)
        if goalies:
            g0 = goalies[0]
            result[f"{side}_goalie0_name"] = g0.get("name", {}).get("default", "")
            result[f"{side}_goalie0_starter"] = g0.get("starter", "MISSING")
            result[f"{side}_goalie0_toi"] = g0.get("toi", "MISSING")
    return result


def count_season_games(season_start):
    """Count regular-season games from the NHL schedule endpoint."""
    # Use the schedule endpoint: iterate through weeks of the season
    url = f"{NHL_API}/schedule/{season_start}-10-01"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"

    # The schedule response covers one week at a time.
    # To get the full season we need a different approach.
    # Use the standings endpoint to get the season info, then count from schedule.
    # Actually, use the club-schedule-season endpoint for one team to verify,
    # or just iterate through all game IDs and count which ones exist.

    # Most reliable: try game IDs and see which ones return 200 with OFF/FINAL
    # But that's too many requests. Instead, use the season schedule endpoint.
    # api-web.nhle.com/v1/schedule-calendar/{season_start+1}-01-01 has regularSeasonEndDate
    # Let's use the score endpoint per date range.

    # Best approach: use the schedule endpoint which returns totalRegularSeasonGames or
    # try the standings endpoint.
    standings_url = f"{NHL_API}/standings/{season_start + 1}-04-15"
    sr = requests.get(standings_url, timeout=30)
    if sr.status_code == 200:
        sdata = sr.json()
        standings = sdata.get("standings", [])
        if standings:
            total_gp = sum(t.get("gamesPlayed", 0) for t in standings)
            # Each game is played by 2 teams, so total games = total_gp / 2
            n_games = total_gp // 2
            n_teams = len(standings)
            return n_games, f"{n_teams} teams, {total_gp} total GP, {n_games} games"

    return None, "standings unavailable"


def main():
    print("=" * 70)
    print("D1 PROBE: NHL API field availability for 2010-2020 seasons")
    print("=" * 70)

    # 1. PBP probes
    print("\n--- Play-by-play probes ---")
    pbp_results = []
    for gid in PROBE_GAMES:
        print(f"  Fetching PBP {gid}...", end=" ", flush=True)
        r = probe_pbp(gid)
        pbp_results.append(r)
        print(f"state={r.get('gameState','')} plays={r.get('n_plays',0)} "
              f"sitCode={r.get('situationCode','')} shots_xy={r.get('shots_with_xy','')}")
        time.sleep(0.5)

    # 2. Boxscore probes
    print("\n--- Boxscore probes ---")
    box_results = []
    for gid in PROBE_GAMES:
        print(f"  Fetching boxscore {gid}...", end=" ", flush=True)
        r = probe_boxscore(gid)
        box_results.append(r)
        starter = r.get("homeTeam_goalie0_starter", "?")
        print(f"{r.get('away_abbrev','')}@{r.get('home_abbrev','')} "
              f"goalies_h={r.get('homeTeam_goalies',0)} starter={starter}")
        time.sleep(0.5)

    # 3. Game counts per season
    print("\n--- Regular-season game counts (from standings) ---")
    game_counts = {}
    for s in range(2010, 2021):
        n, note = count_season_games(s)
        game_counts[s] = n
        print(f"  {s}-{s+1}: {n} games ({note})")
        time.sleep(0.5)

    # Summary table
    print("\n" + "=" * 70)
    print("PROBE SUMMARY TABLE")
    print("=" * 70)
    print(f"\n{'Game':>12s} {'Season':>8s} {'State':>6s} {'Plays':>6s} "
          f"{'sitCode':>10s} {'Shots':>6s} {'XY':>10s} {'Shooter':>10s} {'Goalie':>10s}")
    print("-" * 90)
    for r in pbp_results:
        print(f"{r['game_id']:>12s} {r.get('season',''):>8s} {r.get('gameState',''):>6s} "
              f"{r.get('n_plays',0):>6d} {r.get('situationCode',''):>10s} "
              f"{r.get('shot_plays',0):>6d} {r.get('shots_with_xy',''):>10s} "
              f"{r.get('shootingPlayerId',''):>10s} {r.get('goalieInNetId',''):>10s}")

    print(f"\n{'Game':>12s} {'Home':>4s} {'Away':>4s} {'Date':>12s} "
          f"{'H_goalies':>10s} {'Starter':>10s} {'TOI':>10s}")
    print("-" * 75)
    for r in box_results:
        print(f"{r['game_id']:>12s} {r.get('home_abbrev',''):>4s} {r.get('away_abbrev',''):>4s} "
              f"{r.get('gameDate',''):>12s} {r.get('homeTeam_goalies',0):>10d} "
              f"{str(r.get('homeTeam_goalie0_starter','')):>10s} "
              f"{str(r.get('homeTeam_goalie0_toi','')):>10s}")

    # Gate check
    print("\n--- GATE CHECK ---")
    gate_pass = True
    for r in pbp_results:
        sc = r.get("situationCode", "0/0")
        sc_num, sc_den = sc.split("/")
        if int(sc_den) > 0 and int(sc_num) == 0:
            print(f"  FAIL: {r['game_id']} ({r.get('season','')}) has NO situationCode")
            gate_pass = False
        xy = r.get("shots_with_xy", "0/0")
        xy_num, xy_den = xy.split("/")
        if int(xy_den) > 0 and int(xy_num) == 0:
            print(f"  FAIL: {r['game_id']} ({r.get('season','')}) has NO shot coordinates")
            gate_pass = False

    if gate_pass:
        print("  ALL PROBED GAMES PASS: situationCode and shot coordinates present everywhere.")
    else:
        print("  GATE FAILED: STOP after Item 1. Do not pull 12,000 games onto missing fields.")

    return gate_pass


if __name__ == "__main__":
    passed = main()
    sys.exit(0 if passed else 1)
