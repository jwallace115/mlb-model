#!/usr/bin/env python3
"""H6: probe free structured sources for NHL starting-goalie information.

Sources probed:
  1. api-web.nhle.com/v1/gamecenter/{id}/landing  — NHL API landing page
  2. api-web.nhle.com/v1/gamecenter/{id}/boxscore  — NHL API boxscore
  3. site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={espn_id}

Candidates NOT scraped here (HTML): DailyFaceoff, LeftWingLock, MoneyPuck.

Usage:
  python3 nhl/pipeline/probe_goalie_sources.py --date 2026-09-30 [--post-game]
"""
import argparse
import gzip
import json
import sys
import time
from datetime import datetime, timezone, date as _date
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
ET = ZoneInfo("America/New_York")
OUT_DIR = ROOT / "data" / "news_archive" / "nhl" / "goalies"


def _nhl_schedule(date_str):
    """Get NHL games for a date from the NHL API."""
    url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    games = []
    for week in data.get("gameWeek", []):
        for g in week.get("games", []):
            start_utc = g.get("startTimeUTC", "")
            if start_utc:
                et_date = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(ET).date()
                if et_date == _date.fromisoformat(date_str):
                    games.append(g)
    return games


def _espn_event_id(home_abbr, away_abbr, game_date):
    """Find ESPN event ID by searching the NHL scoreboard for a date."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={game_date.replace('-', '')}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        for ev in data.get("events", []):
            teams = [c.get("team", {}).get("abbreviation", "") for c in ev.get("competitions", [{}])[0].get("competitors", [])]
            if home_abbr in teams and away_abbr in teams:
                return ev["id"]
    except Exception:
        pass
    return None


def probe_nhl_landing(game_id):
    """Probe NHL API landing page for goalie info."""
    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/landing"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    results = []
    for side_key, side_label in [("homeTeam", "home"), ("awayTeam", "away")]:
        team = data.get(side_key, {})
        abbrev = team.get("abbrev", "")
        # Check for goalie info in various fields
        goalie_name = None
        status = None
        # matchup.goalieComparison or similar
        matchup = data.get("matchup", {})
        gc = matchup.get("goalieComparison", {})
        if gc:
            side_gc = gc.get(side_key, {})
            if side_gc:
                name = side_gc.get("name", {}).get("default")
                if name:
                    goalie_name = name
                    status = "goalieComparison"
        # Also check summary.gameInfo
        summary = data.get("summary", {})
        game_info = summary.get("gameInfo", {})
        gi_side = game_info.get(side_key, {})
        if gi_side:
            starter = gi_side.get("startingGoalie")
            if starter:
                name = starter.get("name", {}).get("default")
                if name:
                    goalie_name = name
                    status = "summary.gameInfo.startingGoalie"
        results.append({
            "team": abbrev,
            "source": "nhl_landing",
            "goalie_name": goalie_name,
            "status_as_given": status,
        })
    return data, results


def probe_nhl_boxscore(game_id):
    """Probe NHL API boxscore for goalie info."""
    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    results = []
    for side_key, side_label in [("homeTeam", "home"), ("awayTeam", "away")]:
        team = data.get(side_key, {})
        abbrev = team.get("abbrev", "")
        goalie_name = None
        status = None
        # Check playerByGameStats for starter flag
        stats = data.get("playerByGameStats", {}).get(side_key, {})
        goalies = stats.get("goalies", [])
        for g in goalies:
            if g.get("starter"):
                goalie_name = g.get("name", {}).get("default")
                status = "boxscore.starter=true"
                break
        if not goalie_name and goalies:
            # No starter flag — report first goalie listed
            goalie_name = goalies[0].get("name", {}).get("default")
            status = "boxscore.first_goalie_listed"
        results.append({
            "team": abbrev,
            "source": "nhl_boxscore",
            "goalie_name": goalie_name,
            "status_as_given": status,
        })
    return data, results


def probe_espn(espn_id):
    """Probe ESPN summary for goalie info."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={espn_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    results = []
    # ESPN puts goalie data in boxscore.players[].statistics[name='goalies'].athletes[]
    bp = data.get("boxscore", {}).get("players", [])
    for team_entry in bp:
        team_info = team_entry.get("team", {})
        abbrev = team_info.get("abbreviation", "")
        goalie_name = None
        status = None
        for sg in team_entry.get("statistics", []):
            if sg.get("name", "").lower() == "goalies":
                athletes = sg.get("athletes", [])
                if athletes:
                    ath = athletes[0].get("athlete", {})
                    goalie_name = ath.get("displayName")
                    starter_flag = athletes[0].get("starter")
                    if starter_flag:
                        status = "boxscore.players.goalies.starter=true"
                    else:
                        status = "boxscore.players.goalies.first_listed"
                break
        # Fallback: check rosters (pre-game, if available)
        if not goalie_name:
            for side in data.get("rosters", []):
                side_team = side.get("team", {}).get("abbreviation", "")
                if side_team == abbrev:
                    for entry in side.get("roster", []):
                        if entry.get("position", {}).get("abbreviation") == "G":
                            goalie_name = entry.get("athlete", {}).get("displayName")
                            starter_flag = entry.get("starter")
                            status = f"rosters.G{'.starter=true' if starter_flag else '.first_listed'}"
                            break
                    break
        results.append({
            "team": abbrev,
            "source": "espn_summary",
            "goalie_name": goalie_name,
            "status_as_given": status,
        })
    return data, results


def probe_date(date_str, post_game=False):
    """Probe all sources for a date's games."""
    games = _nhl_schedule(date_str)
    if not games:
        print(f"No games found on {date_str} (ET)")
        return
    print(f"Found {len(games)} games on {date_str}")

    date_dir = OUT_DIR / f"date={date_str}"
    date_dir.mkdir(parents=True, exist_ok=True)
    pulls_file = date_dir / "_pulls.jsonl"
    all_results = []

    for g in games:
        game_id = g["id"]
        home = g.get("homeTeam", {})
        away = g.get("awayTeam", {})
        home_abbr = home.get("abbrev", "")
        away_abbr = away.get("abbrev", "")
        game_state = g.get("gameState", "")
        start_utc = g.get("startTimeUTC", "")
        print(f"\n  {away_abbr} @ {home_abbr} (id={game_id}, state={game_state}, start={start_utc})")

        retrieved_utc = datetime.now(timezone.utc).isoformat()

        # 1. NHL landing
        try:
            landing_raw, landing_results = probe_nhl_landing(game_id)
            # Save raw
            raw_path = date_dir / f"{game_id}_landing.json.gz"
            with gzip.open(raw_path, "wt") as f:
                json.dump(landing_raw, f)
            for r in landing_results:
                r["game_id"] = game_id
                r["game"] = f"{away_abbr}@{home_abbr}"
                r["retrieved_utc"] = retrieved_utc
                r["feed"] = "nhl_landing"
                all_results.append(r)
                print(f"    NHL landing {r['team']}: goalie={r['goalie_name']}, status={r['status_as_given']}")
        except Exception as e:
            print(f"    NHL landing: ERROR {e}")
        time.sleep(0.5)

        # 2. NHL boxscore
        try:
            box_raw, box_results = probe_nhl_boxscore(game_id)
            raw_path = date_dir / f"{game_id}_boxscore.json.gz"
            with gzip.open(raw_path, "wt") as f:
                json.dump(box_raw, f)
            for r in box_results:
                r["game_id"] = game_id
                r["game"] = f"{away_abbr}@{home_abbr}"
                r["retrieved_utc"] = retrieved_utc
                r["feed"] = "nhl_boxscore"
                all_results.append(r)
                print(f"    NHL boxscore {r['team']}: goalie={r['goalie_name']}, status={r['status_as_given']}")
        except Exception as e:
            print(f"    NHL boxscore: ERROR {e}")
        time.sleep(0.5)

        # 3. ESPN
        try:
            espn_id = _espn_event_id(home_abbr, away_abbr, date_str)
            if espn_id:
                espn_raw, espn_results = probe_espn(espn_id)
                raw_path = date_dir / f"{game_id}_espn.json.gz"
                with gzip.open(raw_path, "wt") as f:
                    json.dump(espn_raw, f)
                for r in espn_results:
                    r["game_id"] = game_id
                    r["game"] = f"{away_abbr}@{home_abbr}"
                    r["retrieved_utc"] = retrieved_utc
                    r["feed"] = "espn_summary"
                    all_results.append(r)
                    print(f"    ESPN {r['team']}: goalie={r['goalie_name']}, status={r['status_as_given']}")
            else:
                print(f"    ESPN: no event found for {away_abbr}@{home_abbr}")
        except Exception as e:
            print(f"    ESPN: ERROR {e}")
        time.sleep(0.5)

    # Write pulls JSONL
    with open(pulls_file, "a") as f:
        for r in all_results:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote {len(all_results)} probe results to {pulls_file}")

    # Post-game mode: compare pre-puck names with boxscore starter
    if post_game:
        print("\n=== POST-GAME MODE ===")
        for g in games:
            game_id = g["id"]
            game_state = g.get("gameState", "")
            if game_state not in ("OFF", "FINAL"):
                print(f"  {game_id}: state={game_state}, skipping (not finished)")
                continue
            home_abbr = g.get("homeTeam", {}).get("abbrev", "")
            away_abbr = g.get("awayTeam", {}).get("abbrev", "")
            start_utc = g.get("startTimeUTC", "")
            # Find actual starters from boxscore
            cache_path = ROOT / "nhl" / "cache" / f"boxscore_{game_id}.json"
            if not cache_path.exists():
                # Fetch and cache
                try:
                    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
                    r = requests.get(url, timeout=10)
                    r.raise_for_status()
                    box = r.json()
                    if box.get("gameState") in ("OFF", "FINAL"):
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_text(json.dumps(box))
                except Exception as e:
                    print(f"  {game_id}: could not fetch boxscore: {e}")
                    continue
            else:
                box = json.loads(cache_path.read_text())
            actual_starters = {}
            for side_key in ("homeTeam", "awayTeam"):
                stats = box.get("playerByGameStats", {}).get(side_key, {})
                for goalie in stats.get("goalies", []):
                    if goalie.get("starter"):
                        abbr = box[side_key]["abbrev"]
                        actual_starters[abbr] = goalie.get("name", {}).get("default", "")
            print(f"\n  {away_abbr}@{home_abbr} (actual starters: {actual_starters})")
            # Compare each source's last pre-puck name
            game_probes = [r for r in all_results if r["game_id"] == game_id]
            start_t = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
            for team_abbr in (home_abbr, away_abbr):
                actual = actual_starters.get(team_abbr, "UNKNOWN")
                team_probes = [p for p in game_probes if p["team"] == team_abbr]
                for p in team_probes:
                    probe_t = datetime.fromisoformat(p["retrieved_utc"])
                    lead_min = (start_t - probe_t).total_seconds() / 60
                    correct = (p["goalie_name"] == actual) if p["goalie_name"] else False
                    print(f"    {p['source']:15s} {team_abbr}: predicted={p['goalie_name'] or 'None':20s} "
                          f"actual={actual:20s} {'CORRECT' if correct else 'WRONG/MISSING':8s} "
                          f"lead={lead_min:.0f}min")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (ET)")
    ap.add_argument("--post-game", action="store_true", help="compare with actual starters")
    a = ap.parse_args()
    probe_date(a.date, a.post_game)


if __name__ == "__main__":
    main()
