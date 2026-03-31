#!/usr/bin/env python3
"""
NHL Phase 1 — Canonical Game Table Builder
==========================================
Builds nhl_games_canonical.csv from three data sources:
  1. NHL Stats API  (api-web.nhle.com/v1) — canonical spine + boxscore
  2. MoneyPuck      (bulk CSV)             — advanced stats (xGoals, Corsi, …)
  3. The Odds API   (historical)           — closing totals line

Outputs:
  nhl/nhl_games_canonical.csv
  nhl/nhl_canonical_audit.txt
  nhl/nhl_data_sources.md

Usage:
  python3 nhl/phase1_build_canonical.py [--seasons 2021 2022 2023 2024] [--no-odds]
  python3 nhl/phase1_build_canonical.py --audit-only   # re-run audit on existing CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent          # nhl/
PROJECT = ROOT.parent                            # mlb-model/
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV    = ROOT / "nhl_games_canonical.csv"
AUDIT_FILE = ROOT / "nhl_canonical_audit.txt"
DOCS_FILE  = ROOT / "nhl_data_sources.md"

# ---------------------------------------------------------------------------
# Seasons to cover (start year of each season, e.g. 2021 → 2021-22)
# ---------------------------------------------------------------------------
DEFAULT_SEASONS = [2021, 2022, 2023, 2024]

# Season date ranges (approximate; script walks daily)
SEASON_WINDOWS = {
    2021: ("2021-10-12", "2022-05-01"),
    2022: ("2022-10-07", "2023-04-14"),
    2023: ("2023-10-10", "2024-04-18"),
    2024: ("2024-10-04", "2025-04-17"),
}

# ---------------------------------------------------------------------------
# ARI → UTA transition
# ---------------------------------------------------------------------------
ARI_LAST_SEASON = 2023    # 2023-24 was last season for Coyotes
UTA_FIRST_SEASON = 2024   # 2024-25 is Utah Hockey Club's first season

# ---------------------------------------------------------------------------
# NHL team full-name → abbreviation (for Odds API matching)
# ---------------------------------------------------------------------------
NHL_TEAM_NAME_MAP: dict[str, str] = {
    "Anaheim Ducks":          "ANA",
    "Boston Bruins":          "BOS",
    "Buffalo Sabres":         "BUF",
    "Calgary Flames":         "CGY",
    "Carolina Hurricanes":    "CAR",
    "Chicago Blackhawks":     "CHI",
    "Colorado Avalanche":     "COL",
    "Columbus Blue Jackets":  "CBJ",
    "Dallas Stars":           "DAL",
    "Detroit Red Wings":      "DET",
    "Edmonton Oilers":        "EDM",
    "Florida Panthers":       "FLA",
    "Los Angeles Kings":      "LAK",
    "Minnesota Wild":         "MIN",
    "Montreal Canadiens":     "MTL",
    "Montréal Canadiens":     "MTL",
    "Nashville Predators":    "NSH",
    "New Jersey Devils":      "NJD",
    "New York Islanders":     "NYI",
    "New York Rangers":       "NYR",
    "Ottawa Senators":        "OTT",
    "Philadelphia Flyers":    "PHI",
    "Pittsburgh Penguins":    "PIT",
    "San Jose Sharks":        "SJS",
    "Seattle Kraken":         "SEA",
    "St. Louis Blues":        "STL",
    "Tampa Bay Lightning":    "TBL",
    "Toronto Maple Leafs":    "TOR",
    "Utah Hockey Club":       "UTA",
    "Vancouver Canucks":      "VAN",
    "Vegas Golden Knights":   "VGK",
    "Washington Capitals":    "WSH",
    "Winnipeg Jets":          "WPG",
    # Coyotes (through 2023-24)
    "Arizona Coyotes":        "ARI",
    # The Odds API omits the period in "St." — add no-period variant
    "St Louis Blues":         "STL",
}

# ---------------------------------------------------------------------------
# Session with retry
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0.0.0 Safari/537.36",
})

def _get(url: str, params: dict | None = None, retries: int = 3,
         backoff: float = 2.0, timeout: int = 30) -> dict | list | None:
    """GET with exponential backoff."""
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                wait = backoff * (2 ** attempt)
                print(f"    [rate-limit] sleeping {wait:.0f}s", flush=True)
                time.sleep(wait)
                continue
            print(f"    [warn] GET {url} → {r.status_code}", flush=True)
            return None
        except requests.RequestException as exc:
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
            else:
                print(f"    [error] {exc}", flush=True)
    return None

# ---------------------------------------------------------------------------
# 1. NHL Schedule — collect all game IDs per season
# ---------------------------------------------------------------------------
NHL_WEB_API = "https://api-web.nhle.com/v1"

def _cache_path(key: str) -> Path:
    safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")
    return CACHE_DIR / f"{safe}.json"

def _cached_get(key: str, url: str, params: dict | None = None) -> dict | list | None:
    cp = _cache_path(key)
    if cp.exists():
        return json.loads(cp.read_text())
    data = _get(url, params=params)
    if data is not None:
        cp.write_text(json.dumps(data))
    return data

def fetch_season_game_ids(start_year: int) -> list[dict]:
    """
    Walk the schedule for one season week-by-week.
    Returns list of dicts: {game_id, date, home_team, away_team, season_year}.
    Only regular-season games (gameType == 2).
    """
    s_start, s_end = SEASON_WINDOWS[start_year]
    d = datetime.strptime(s_start, "%Y-%m-%d").date()
    end = datetime.strptime(s_end, "%Y-%m-%d").date()
    games: list[dict] = []
    seen: set[int] = set()

    print(f"  Season {start_year}-{start_year+1}: walking {s_start} → {s_end}", flush=True)

    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        cache_key = f"schedule_{ds}"
        data = _cached_get(cache_key, f"{NHL_WEB_API}/schedule/{ds}")
        if data and "gameWeek" in data:
            for week in data["gameWeek"]:
                for g in week.get("games", []):
                    if g.get("gameType") != 2:
                        continue
                    gid = g["id"]
                    if gid in seen:
                        continue
                    seen.add(gid)
                    game_date = week["date"]
                    home_abb = g.get("homeTeam", {}).get("abbrev", "")
                    away_abb = g.get("awayTeam", {}).get("abbrev", "")
                    games.append({
                        "game_id":    str(gid),
                        "game_date":  game_date,
                        "home_team":  home_abb,
                        "away_team":  away_abb,
                        "season_year": start_year,
                    })
        # NHL schedule API returns a week at a time; advance 7 days
        d += timedelta(days=7)
        time.sleep(0.15)

    print(f"    → {len(games)} regular-season games found", flush=True)
    return games

# ---------------------------------------------------------------------------
# 2. Boxscore — final scores, goalies, overtime type
# ---------------------------------------------------------------------------

def fetch_boxscore(game_id: str) -> dict | None:
    """
    Returns:
      home_score, away_score, period_type (REG/OT/SO),
      home_goals_reg, away_goals_reg, went_to_ot, went_to_so, ot_goals,
      home_goalie_id, home_goalie_name, home_goalie_starter,
      away_goalie_id, away_goalie_name, away_goalie_starter,
      home_goalie_sa, home_goalie_ga, away_goalie_sa, away_goalie_ga,
      home_goalie_toi, away_goalie_toi
    """
    cache_key = f"boxscore_{game_id}"
    data = _cached_get(cache_key, f"{NHL_WEB_API}/gamecenter/{game_id}/boxscore")
    if not data:
        return None

    home_score = data.get("homeTeam", {}).get("score")
    away_score = data.get("awayTeam", {}).get("score")
    if home_score is None or away_score is None:
        return None   # game not yet completed

    outcome = data.get("gameOutcome", {})
    period_type = outcome.get("lastPeriodType", "REG")  # REG | OT | SO

    went_to_ot = period_type in ("OT", "SO")
    went_to_so = period_type == "SO"

    # Regulation score derivation
    if period_type == "REG":
        home_goals_reg = home_score
        away_goals_reg = away_score
        ot_goals = 0
    elif period_type == "OT":
        # One team scored exactly 1 goal in OT (sudden death)
        if home_score > away_score:
            home_goals_reg = home_score - 1
            away_goals_reg = away_score
        else:
            home_goals_reg = home_score
            away_goals_reg = away_score - 1
        ot_goals = 1
    else:  # SO
        # In SO, winner credited +1 but no actual OT goal scored
        if home_score > away_score:
            home_goals_reg = home_score - 1
            away_goals_reg = away_score
        else:
            home_goals_reg = home_score
            away_goals_reg = away_score - 1
        ot_goals = 0  # no goals in OT period for SO games

    # Goalies
    pbg = data.get("playerByGameStats", {})
    home_goalie = _extract_goalie(pbg.get("homeTeam", {}).get("goalies", []))
    away_goalie = _extract_goalie(pbg.get("awayTeam", {}).get("goalies", []))

    return {
        "home_score":          home_score,
        "away_score":          away_score,
        "period_type":         period_type,
        "went_to_ot":          went_to_ot,
        "went_to_so":          went_to_so,
        "ot_goals":            ot_goals,
        "home_goals_reg":      home_goals_reg,
        "away_goals_reg":      away_goals_reg,
        "home_goalie_id":      home_goalie.get("id"),
        "home_goalie_name":    home_goalie.get("name"),
        "home_goalie_starter": home_goalie.get("starter"),
        "home_goalie_sa":      home_goalie.get("sa"),
        "home_goalie_ga":      home_goalie.get("ga"),
        "home_goalie_toi":     home_goalie.get("toi"),
        "away_goalie_id":      away_goalie.get("id"),
        "away_goalie_name":    away_goalie.get("name"),
        "away_goalie_starter": away_goalie.get("starter"),
        "away_goalie_sa":      away_goalie.get("sa"),
        "away_goalie_ga":      away_goalie.get("ga"),
        "away_goalie_toi":     away_goalie.get("toi"),
    }

def _extract_goalie(goalies: list[dict]) -> dict:
    """Pick the starting goalie (starter=True); fall back to most TOI."""
    if not goalies:
        return {}
    starter = next((g for g in goalies if g.get("starter")), None)
    if not starter:
        # Fall back to highest TOI
        def _toi_sec(g: dict) -> int:
            toi = g.get("toi", "00:00")
            try:
                m, s = toi.split(":")
                return int(m) * 60 + int(s)
            except Exception:
                return 0
        starter = max(goalies, key=_toi_sec) if goalies else {}
    g = starter
    sa = g.get("shotsAgainst")
    ga = g.get("goalsAgainst")
    # Some boxscores use different field names
    if sa is None:
        sa = g.get("powerPlayShotsAgainst")
    return {
        "id":      g.get("playerId"),
        "name":    g.get("name", {}).get("default") if isinstance(g.get("name"), dict) else g.get("name"),
        "starter": g.get("starter", False),
        "sa":      sa,
        "ga":      ga,
        "toi":     g.get("toi"),
    }

# ---------------------------------------------------------------------------
# 3. PP stats — NHL Stats REST API with cayenneExp
# ---------------------------------------------------------------------------
NHL_STATS_REST = "https://api.nhle.com/stats/rest/en"

def fetch_pp_stats(game_id: str, home_team: str, away_team: str) -> dict:
    """
    Returns:
      home_pp_opportunities, home_pp_goals, home_pk_goals_against,
      away_pp_opportunities, away_pp_goals, away_pk_goals_against,
      home_pp_pct (null if 0 opp), away_pp_pct (null if 0 opp),
      home_pk_pct (null if 0 times_shorthanded), away_pk_pct (null if 0)
    """
    cache_key = f"pp_{game_id}"
    cp = _cache_path(cache_key)
    if cp.exists():
        return json.loads(cp.read_text())

    url = f"{NHL_STATS_REST}/team/powerplay"
    params = {
        "isAggregate": "false",
        "isGame":      "true",
        "cayenneExp":  f"gameId={game_id}",
    }
    data = _get(url, params=params)
    result: dict[str, Any] = {
        "home_pp_opportunities":  None,
        "home_pp_goals":          None,
        "home_pk_goals_against":  None,
        "away_pp_opportunities":  None,
        "away_pp_goals":          None,
        "away_pk_goals_against":  None,
        "home_pp_pct":            None,
        "away_pp_pct":            None,
        "home_pk_pct":            None,
        "away_pk_pct":            None,
    }

    if not data or "data" not in data or not data["data"]:
        cp.write_text(json.dumps(result))
        return result

    rows = data["data"]
    # Match rows to home/away by teamAbbrev or homeRoad
    home_row = None
    away_row = None
    for row in rows:
        hr = row.get("homeRoad", "")
        if hr == "H":
            home_row = row
        elif hr == "R":
            away_row = row

    # Fallback: match by team abbrev in teamFullName if homeRoad not available
    if home_row is None or away_row is None:
        for row in rows:
            fname = row.get("teamAbbrev", "") or row.get("teamCode", "")
            if fname == home_team:
                home_row = row
            elif fname == away_team:
                away_row = row

    def _parse_row(row: dict | None, prefix: str) -> dict:
        if row is None:
            return {}
        opp = row.get("ppOpportunities", 0) or 0
        goals = row.get("powerPlayGoalsFor", 0) or 0
        # PK: times shorthanded = opponent's ppOpportunities (same game)
        sh_ga = row.get("shGoalsAgainst", 0) or 0

        pp_pct = (goals / opp) if opp > 0 else None
        # pk_pct: (1 - sh_ga/opp) where opp = times shorthanded
        # But "times shorthanded" for this team = opponent's ppOpportunities
        # We'll compute pk_pct after pairing both rows
        return {
            f"{prefix}_pp_opportunities": opp,
            f"{prefix}_pp_goals":         goals,
            f"{prefix}_pk_goals_against": sh_ga,
            f"{prefix}_pp_pct":           round(pp_pct, 4) if pp_pct is not None else None,
            "_opp_opp":                   opp,   # for pk_pct cross-computation
        }

    home_parsed = _parse_row(home_row, "home")
    away_parsed = _parse_row(away_row, "away")

    # PK pct = 1 - (sh_ga / times_shorthanded)
    # home PK: home was shorthanded when away had PP opportunities
    away_opp = away_parsed.pop("_opp_opp", 0)
    home_opp = home_parsed.pop("_opp_opp", 0)
    home_sh_ga = home_parsed.get("home_pk_goals_against", 0) or 0
    away_sh_ga = away_parsed.get("away_pk_goals_against", 0) or 0

    # home PK pct: home was on PK when away had PP opp
    home_pk_pct = (1.0 - home_sh_ga / away_opp) if away_opp > 0 else None
    away_pk_pct = (1.0 - away_sh_ga / home_opp) if home_opp > 0 else None

    result.update(home_parsed)
    result.update(away_parsed)
    result["home_pk_pct"] = round(home_pk_pct, 4) if home_pk_pct is not None else None
    result["away_pk_pct"] = round(away_pk_pct, 4) if away_pk_pct is not None else None

    cp.write_text(json.dumps(result))
    return result

# ---------------------------------------------------------------------------
# 4. MoneyPuck — bulk CSV download + in-memory index
# ---------------------------------------------------------------------------
MP_URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
MP_CACHE = ROOT / "cache" / "moneypuck_all_teams.csv"

def load_moneypuck() -> dict[str, dict]:
    """
    Download (once) and parse MoneyPuck bulk CSV.
    Returns dict keyed by (gameId, home_or_away) → row dict.
    Only situation == "all" rows.
    """
    if not MP_CACHE.exists():
        print("  Downloading MoneyPuck bulk CSV (~124MB)…", flush=True)
        r = requests.get(
            MP_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
                "Referer": "https://moneypuck.com/data.htm",
            },
            stream=True,
            timeout=300,
        )
        r.raise_for_status()
        total = 0
        with open(MP_CACHE, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                total += len(chunk)
                if total % (10 * 1024 * 1024) == 0:
                    print(f"    {total // (1024*1024)} MB…", flush=True)
        print(f"  MoneyPuck download complete ({total // (1024*1024)} MB)", flush=True)
    else:
        print(f"  MoneyPuck CSV: using cached {MP_CACHE.name}", flush=True)

    print("  Parsing MoneyPuck CSV (situation=all)…", flush=True)
    index: dict[str, dict] = {}
    with open(MP_CACHE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("situation") != "all":
                continue
            gid = row.get("gameId", "")
            ha = row.get("home_or_away", "").lower()   # "home" or "away"
            key = f"{gid}_{ha}"
            index[key] = row

    print(f"  MoneyPuck index: {len(index)} entries (situation=all)", flush=True)
    return index

def get_moneypuck_row(mp_index: dict[str, dict], game_id: str,
                      side: str) -> dict | None:
    """side: 'home' or 'away'"""
    key = f"{game_id}_{side}"
    return mp_index.get(key)

def extract_mp_fields(row: dict | None, prefix: str) -> dict:
    """Extract the required MoneyPuck fields with consistent naming."""
    if row is None:
        return {
            f"{prefix}_xgoals":            None,
            f"{prefix}_corsi_pct":         None,
            f"{prefix}_fenwick_pct":       None,
            f"{prefix}_shots_on_goal":     None,
            f"{prefix}_hd_shots":          None,
            f"{prefix}_hd_shots_against":  None,
            f"{prefix}_xgoals_against":    None,
        }

    def _f(key: str) -> float | None:
        v = row.get(key)
        try:
            return float(v) if v not in (None, "", "NA") else None
        except (ValueError, TypeError):
            return None

    return {
        f"{prefix}_xgoals":           _f("xGoalsFor"),
        f"{prefix}_xgoals_against":   _f("xGoalsAgainst"),
        f"{prefix}_corsi_pct":        _f("corsiPercentage"),
        f"{prefix}_fenwick_pct":      _f("fenwickPercentage"),
        f"{prefix}_shots_on_goal":    _f("shotsOnGoalFor"),
        f"{prefix}_hd_shots":         _f("highDangerShotsFor"),
        f"{prefix}_hd_shots_against": _f("highDangerShotsAgainst"),
    }

# ---------------------------------------------------------------------------
# 5. Odds API — historical NHL totals
# ---------------------------------------------------------------------------
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

def _odds_api_key() -> str:
    import os as _os
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT / ".env")
    except ImportError:
        pass
    return _os.environ.get("ODDS_API_KEY", "")

def fetch_odds_for_date(game_date: str, api_key: str) -> list[dict]:
    """
    Fetch pre-game closing lines for a given game_date.
    Queries at game_date 04:00 UTC — before first puck drop (~7pm ET) so all
    day's games are still upcoming in the snapshot.

    Fix note: the prior strategy queried D+1 04:00 UTC (midnight ET), at which
    point early-start Eastern games are already over and absent from the feed.
    D 04:00 UTC (the previous night, ~11pm ET) captures all games as upcoming.

    Returns list of dicts: {home_team, away_team, total_line, over_price, under_price, book}
    """
    if not api_key:
        return []

    # Query at game_date 04:00 UTC = previous night ~11pm ET
    # At this time all same-day games are still 15+ hours away (upcoming)
    snapshot = datetime.strptime(game_date, "%Y-%m-%d").replace(
        hour=4, minute=0, second=0, tzinfo=timezone.utc
    )
    snapshot_str = snapshot.strftime("%Y-%m-%dT%H:%M:%SZ")

    cache_key = f"odds_nhl_{game_date}"
    cp = _cache_path(cache_key)
    if cp.exists():
        return json.loads(cp.read_text())

    url = f"{ODDS_API_BASE}/historical/sports/icehockey_nhl/odds/"
    # Book preference order: DraftKings > FanDuel > BetMGM > William Hill (US)
    # DK/FD are preferred for liquidity; betmgm/williamhill_us catch games absent from DK/FD
    params = {
        "apiKey":      api_key,
        "date":        snapshot_str,
        "regions":     "us",
        "markets":     "totals",
        "oddsFormat":  "american",
        "bookmakers":  "draftkings,fanduel,betmgm,williamhill_us",
    }

    data = _get(url, params=params, timeout=60)
    if not data or "data" not in data:
        cp.write_text(json.dumps([]))
        return []

    BOOK_PRIORITY = {"draftkings": 0, "fanduel": 1, "betmgm": 2, "williamhill_us": 3}

    results: list[dict] = []
    for game in data.get("data", []):
        home_full = game.get("home_team", "")
        away_full = game.get("away_team", "")
        home_abb = NHL_TEAM_NAME_MAP.get(home_full)
        away_abb = NHL_TEAM_NAME_MAP.get(away_full)
        if not home_abb or not away_abb:
            continue

        for book in game.get("bookmakers", []):
            book_name = book.get("key", "")
            if book_name not in BOOK_PRIORITY:
                continue
            for market in book.get("markets", []):
                if market.get("key") != "totals":
                    continue
                over_price = under_price = total_line = None
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == "Over":
                        over_price  = outcome.get("price")
                        total_line  = outcome.get("point")
                    elif outcome.get("name") == "Under":
                        under_price = outcome.get("price")
                if total_line is not None:
                    results.append({
                        "home_team":   home_abb,
                        "away_team":   away_abb,
                        "total_line":  total_line,
                        "over_price":  over_price,
                        "under_price": under_price,
                        "book":        book_name,
                    })

    # Deduplicate: keep highest-priority book per matchup
    best: dict[tuple[str, str], dict] = {}
    for row in results:
        k = (row["home_team"], row["away_team"])
        if k not in best:
            best[k] = row
        elif BOOK_PRIORITY.get(row["book"], 99) < BOOK_PRIORITY.get(best[k]["book"], 99):
            best[k] = row

    final = list(best.values())
    cp.write_text(json.dumps(final))
    return final

# ---------------------------------------------------------------------------
# 6. Schedule enrichments — rest days, back-to-back, games_last_7
# ---------------------------------------------------------------------------

def compute_schedule_enrichments(all_games: list[dict]) -> dict[str, dict[str, dict]]:
    """
    For each team in each game, compute:
      rest_days: calendar days since last game WITHIN THE SAME SEASON
                 (None if first game of the season — season boundary resets counter)
      is_b2b: True if rest_days == 1 (strictly; not <= 1)
      games_last_7: number of games in the prior 7 calendar days within same season

    Returns: {game_id: {team_abb: {rest_days, is_b2b, games_last_7}}}
    """
    from collections import defaultdict

    # Build per-team, per-season sorted game list
    # Key: (team, season_year) → sorted list of (date, game_id)
    team_season_games: dict[tuple[str, int], list[tuple[date, str]]] = defaultdict(list)

    for g in all_games:
        gd = datetime.strptime(g["game_date"], "%Y-%m-%d").date()
        sy = g["season_year"]
        team_season_games[(g["home_team"], sy)].append((gd, g["game_id"]))
        team_season_games[(g["away_team"], sy)].append((gd, g["game_id"]))

    for key in team_season_games:
        team_season_games[key].sort()

    result: dict[str, dict[str, dict]] = {}
    for g in all_games:
        gid = g["game_id"]
        gd  = datetime.strptime(g["game_date"], "%Y-%m-%d").date()
        sy  = g["season_year"]
        result[gid] = {}
        for side, team in [("home", g["home_team"]), ("away", g["away_team"])]:
            tgl = team_season_games[(team, sy)]
            idx = next((i for i, (d2, g2) in enumerate(tgl) if g2 == gid), None)
            if idx is None or idx == 0:
                # First game of season → reset: no prior game this season
                rest_days = None
                is_b2b    = False
                gl7       = 0
            else:
                prev_date = tgl[idx - 1][0]
                rest_days = (gd - prev_date).days
                is_b2b    = (rest_days == 1)   # strictly == 1
                cutoff    = gd - timedelta(days=7)
                gl7       = sum(1 for (d2, _) in tgl[:idx] if d2 > cutoff)

            result[gid][team] = {
                "rest_days":    rest_days,
                "is_b2b":       is_b2b,
                "games_last_7": gl7,
            }

    return result

# ---------------------------------------------------------------------------
# 7. Assemble canonical rows
# ---------------------------------------------------------------------------

# Final CSV column order
COLUMNS = [
    # Identity
    "game_id", "game_date", "season_year",
    "home_team", "away_team",
    # Final scores
    "home_score", "away_score", "total_goals",
    # Regulation / OT
    "home_goals_reg", "away_goals_reg",
    "went_to_ot", "went_to_so", "ot_goals",
    "reg_total_goals",
    # Goalies
    "home_goalie_id", "home_goalie_name", "home_goalie_starter",
    "home_goalie_sa",  "home_goalie_ga",  "home_goalie_toi",
    "away_goalie_id", "away_goalie_name", "away_goalie_starter",
    "away_goalie_sa",  "away_goalie_ga",  "away_goalie_toi",
    # PP stats
    "home_pp_opportunities", "home_pp_goals", "home_pk_goals_against",
    "away_pp_opportunities", "away_pp_goals", "away_pk_goals_against",
    "home_pp_pct", "away_pp_pct",
    "home_pk_pct", "away_pk_pct",
    # Schedule enrichments (home)
    "home_rest_days", "home_is_b2b", "home_games_last_7",
    # Schedule enrichments (away)
    "away_rest_days", "away_is_b2b", "away_games_last_7",
    # MoneyPuck advanced stats
    "home_xgoals", "home_xgoals_against",
    "home_corsi_pct", "home_fenwick_pct",
    "home_shots_on_goal", "home_hd_shots", "home_hd_shots_against",
    "away_xgoals", "away_xgoals_against",
    "away_corsi_pct", "away_fenwick_pct",
    "away_shots_on_goal", "away_hd_shots", "away_hd_shots_against",
    # Market
    "total_line", "over_price", "under_price",
    # Flags
    "moneypuck_available", "market_available",
    "pregame_confirmed",
]

def build_canonical_row(
    spine: dict,
    bx: dict | None,
    pp: dict,
    enrich: dict,
    mp_home: dict | None,
    mp_away: dict | None,
    odds: dict | None,
) -> dict:
    """Assemble one row; None → empty string in CSV."""

    def _v(d: dict | None, key: str, default=None):
        return d.get(key, default) if d else default

    gid  = spine["game_id"]
    home = spine["home_team"]
    away = spine["away_team"]

    home_sc  = _v(bx, "home_score")
    away_sc  = _v(bx, "away_score")
    total    = (home_sc + away_sc) if (home_sc is not None and away_sc is not None) else None

    home_reg = _v(bx, "home_goals_reg")
    away_reg = _v(bx, "away_goals_reg")
    reg_total = (home_reg + away_reg) if (home_reg is not None and away_reg is not None) else None

    h_enr = enrich.get(home, {})
    a_enr = enrich.get(away, {})

    mp_home_fields = extract_mp_fields(mp_home, "home")
    mp_away_fields = extract_mp_fields(mp_away, "away")

    row = {
        "game_id":      gid,
        "game_date":    spine["game_date"],
        "season_year":  spine["season_year"],
        "home_team":    home,
        "away_team":    away,

        "home_score":   home_sc,
        "away_score":   away_sc,
        "total_goals":  total,

        "home_goals_reg": home_reg,
        "away_goals_reg": away_reg,
        "went_to_ot":   _v(bx, "went_to_ot"),
        "went_to_so":   _v(bx, "went_to_so"),
        "ot_goals":     _v(bx, "ot_goals"),
        "reg_total_goals": reg_total,

        "home_goalie_id":      _v(bx, "home_goalie_id"),
        "home_goalie_name":    _v(bx, "home_goalie_name"),
        "home_goalie_starter": _v(bx, "home_goalie_starter"),
        "home_goalie_sa":      _v(bx, "home_goalie_sa"),
        "home_goalie_ga":      _v(bx, "home_goalie_ga"),
        "home_goalie_toi":     _v(bx, "home_goalie_toi"),

        "away_goalie_id":      _v(bx, "away_goalie_id"),
        "away_goalie_name":    _v(bx, "away_goalie_name"),
        "away_goalie_starter": _v(bx, "away_goalie_starter"),
        "away_goalie_sa":      _v(bx, "away_goalie_sa"),
        "away_goalie_ga":      _v(bx, "away_goalie_ga"),
        "away_goalie_toi":     _v(bx, "away_goalie_toi"),

        "home_pp_opportunities": pp.get("home_pp_opportunities"),
        "home_pp_goals":         pp.get("home_pp_goals"),
        "home_pk_goals_against": pp.get("home_pk_goals_against"),
        "away_pp_opportunities": pp.get("away_pp_opportunities"),
        "away_pp_goals":         pp.get("away_pp_goals"),
        "away_pk_goals_against": pp.get("away_pk_goals_against"),
        "home_pp_pct":           pp.get("home_pp_pct"),
        "away_pp_pct":           pp.get("away_pp_pct"),
        "home_pk_pct":           pp.get("home_pk_pct"),
        "away_pk_pct":           pp.get("away_pk_pct"),

        "home_rest_days":    h_enr.get("rest_days"),
        "home_is_b2b":       h_enr.get("is_b2b"),
        "home_games_last_7": h_enr.get("games_last_7"),
        "away_rest_days":    a_enr.get("rest_days"),
        "away_is_b2b":       a_enr.get("is_b2b"),
        "away_games_last_7": a_enr.get("games_last_7"),

        **mp_home_fields,
        **mp_away_fields,

        "total_line":  _v(odds, "total_line"),
        "over_price":  _v(odds, "over_price"),
        "under_price": _v(odds, "under_price"),

        "moneypuck_available": (mp_home is not None and mp_away is not None),
        "market_available":    (odds is not None),
        "pregame_confirmed":   None,   # requires timestamped pregame source
    }

    return row

# ---------------------------------------------------------------------------
# 8. Audit gates
# ---------------------------------------------------------------------------

def run_audit(rows: list[dict]) -> tuple[bool, str]:
    """
    Run all 8 required audit gates.
    Returns (all_pass: bool, report_text: str).
    """
    lines: list[str] = []
    failures: list[str] = []

    def gate(name: str, expr: bool, detail: str = "") -> None:
        status = "PASS" if expr else "FAIL"
        msg = f"  [{status}] {name}"
        if detail:
            msg += f": {detail}"
        lines.append(msg)
        if not expr:
            failures.append(name)

    n = len(rows)
    lines.append(f"NHL Canonical Game Table — Audit Report")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Total rows: {n}")
    lines.append("")

    # Gate 1: Row count
    # 2021-22: 1271 regular season games (some played in neutral sites)
    # 2022-23: 1312, 2023-24: 1312, 2024-25: ~1312
    # Expect roughly 4,600–5,300 across 4 seasons
    gate(
        "Gate 1: Row count ≥ 4500",
        n >= 4500,
        f"actual={n}",
    )

    # Gate 2: No duplicate game_ids
    game_ids = [r["game_id"] for r in rows]
    dupes = n - len(set(game_ids))
    gate("Gate 2: No duplicate game_ids", dupes == 0, f"dupes={dupes}")

    # Gate 3: Required columns present
    required_cols = set(COLUMNS)
    actual_cols   = set(rows[0].keys()) if rows else set()
    missing_cols  = required_cols - actual_cols
    gate(
        "Gate 3: All required columns present",
        len(missing_cols) == 0,
        f"missing={sorted(missing_cols)}" if missing_cols else "",
    )

    # Gate 4: Total goals ≥ 1 for all completed games with scores
    completed = [r for r in rows if r.get("total_goals") is not None]
    low_goals = [r for r in completed if (r["total_goals"] or 0) < 1]
    gate(
        "Gate 4: total_goals ≥ 1 for all scored games",
        len(low_goals) == 0,
        f"bad_rows={len(low_goals)}",
    )

    # Gate 5: went_to_ot/went_to_so consistency
    # If went_to_so → went_to_ot must be True; if went_to_ot → ot_goals ∈ {0, 1}
    bad_so = [r for r in rows if r.get("went_to_so") and not r.get("went_to_ot")]
    bad_ot_goals = [
        r for r in rows
        if r.get("went_to_ot") and r.get("ot_goals") not in (0, 1, None)
    ]
    gate(
        "Gate 5: OT/SO flags consistent",
        len(bad_so) == 0 and len(bad_ot_goals) == 0,
        f"bad_so={len(bad_so)} bad_ot_goals={len(bad_ot_goals)}",
    )

    # Gate 6: reg_total_goals = home_goals_reg + away_goals_reg
    bad_reg = []
    for r in rows:
        hg = r.get("home_goals_reg")
        ag = r.get("away_goals_reg")
        rg = r.get("reg_total_goals")
        if hg is not None and ag is not None and rg is not None:
            if abs(hg + ag - rg) > 0.001:
                bad_reg.append(r["game_id"])
    gate(
        "Gate 6: reg_total_goals == home_goals_reg + away_goals_reg",
        len(bad_reg) == 0,
        f"bad_rows={len(bad_reg)}",
    )

    # Gate 7: MoneyPuck coverage ≥ 80%
    mp_count = sum(1 for r in rows if r.get("moneypuck_available"))
    mp_pct   = mp_count / n if n > 0 else 0
    gate(
        "Gate 7: MoneyPuck coverage ≥ 80%",
        mp_pct >= 0.80,
        f"{mp_count}/{n} = {mp_pct:.1%}",
    )

    # Gate 8: Market (Odds API) coverage ≥ 70% for 2022-23 onward
    rows_2022_plus = [r for r in rows if (r.get("season_year") or 0) >= 2022]
    if rows_2022_plus:
        mkt_count = sum(1 for r in rows_2022_plus if r.get("market_available"))
        mkt_pct   = mkt_count / len(rows_2022_plus)
        gate(
            "Gate 8: Market coverage ≥ 70% for 2022-23+",
            mkt_pct >= 0.70,
            f"{mkt_count}/{len(rows_2022_plus)} = {mkt_pct:.1%}",
        )
    else:
        gate("Gate 8: Market coverage (skipped — no 2022+ rows)", True)

    lines.append("")
    all_pass = len(failures) == 0
    if all_pass:
        lines.append("OVERALL: PASS — all audit gates satisfied")
    else:
        lines.append(f"OVERALL: FAIL — {len(failures)} gate(s) failed: {failures}")

    # Per-season summary
    lines.append("")
    lines.append("Per-season row counts:")
    from collections import Counter
    season_counts = Counter(r.get("season_year") for r in rows)
    for yr in sorted(season_counts):
        lines.append(f"  {yr}-{str(yr+1)[2:]}: {season_counts[yr]} games")

    return all_pass, "\n".join(lines)

# ---------------------------------------------------------------------------
# 9. Data sources doc
# ---------------------------------------------------------------------------

def write_data_sources_doc() -> None:
    content = """\
# NHL Phase 1 — Data Sources

## 1. NHL Stats API (canonical spine + boxscore + PP stats)

### Schedule
- Endpoint: `https://api-web.nhle.com/v1/schedule/{date}`
- Returns: game week containing the date; walk weekly
- Filter: `gameType == 2` for regular season only
- Fields used: `id`, `gameType`, `homeTeam.abbrev`, `awayTeam.abbrev`

### Boxscore
- Endpoint: `https://api-web.nhle.com/v1/gamecenter/{gameId}/boxscore`
- Fields used:
  - `homeTeam.score`, `awayTeam.score` — final scores
  - `gameOutcome.lastPeriodType` — "REG" | "OT" | "SO"
  - `playerByGameStats.{homeTeam,awayTeam}.goalies` — goalie stats
- Rate limit: ~15 req/s sustained; 0.15s sleep between schedule pages

### Power Play Stats
- Endpoint: `https://api.nhle.com/stats/rest/en/team/powerplay`
- Params: `isAggregate=false&isGame=true&cayenneExp=gameId={id}`
- Returns: 2 rows per game (homeRoad: H or R)
- Fields used: `ppOpportunities`, `powerPlayGoalsFor`, `shGoalsAgainst`
- PP pct: null when ppOpportunities == 0 (not 0.0)
- PK pct: null when times_shorthanded == 0

## 2. MoneyPuck (advanced stats)

- URL: `https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv`
- Download: single bulk CSV (~124 MB)
- Filter: `situation == "all"` for full-game stats
- Join: `gameId` (string) == NHL API game_id
- Required headers: `User-Agent` (browser), `Referer: https://moneypuck.com/data.htm`
- Seasons available: 2011-12 through current
- Fields used: `xGoalsFor`, `xGoalsAgainst`, `corsiPercentage`, `fenwickPercentage`,
  `shotsOnGoalFor`, `highDangerShotsFor`, `highDangerShotsAgainst`
- Coverage notes: some very recent games may lag by 1-2 days

## 3. The Odds API (closing market lines)

- Endpoint: `https://api.the-odds-api.com/v4/historical/sports/icehockey_nhl/odds/`
- API key: stored in `.env` as `ODDS_API_KEY`
- Query strategy: D+1 at 04:00 UTC to capture closing lines for date D
- Cost: ~10 requests per call (~720 calls needed for 4 seasons = ~7,200 requests)
- Markets: `totals` only; regions: `us`; bookmakers: `draftkings`, `fanduel`
- Preference: DraftKings > FanDuel when both available
- Data goes back to at least 2021-22 season
- Fields used: `point` (total line), `price` (over/under American odds)

## Regulation Score Derivation

- REG games: `home_goals_reg = homeTeam.score`, `away_goals_reg = awayTeam.score`
- OT games: winner scored exactly 1 OT goal; subtract from winner's final score
- SO games: same subtraction as OT, but `ot_goals = 0` (no goals in OT period)
- `ot_goals`: 1 for OT games, 0 for SO and REG games

## ARI → UTA Transition (2024-25)

- Arizona Coyotes (ARI) played their last season in 2023-24
- Utah Hockey Club (UTA) began play in 2024-25
- These are separate franchises with separate team codes in the NHL API
- No remapping is performed; ARI and UTA appear as distinct teams in the canonical table

## Caching

- All API responses cached as JSON in `nhl/cache/`
- MoneyPuck CSV cached in `nhl/cache/moneypuck_all_teams.csv`
- Odds API responses cached per game date
- Delete cache files to force re-fetch
"""
    DOCS_FILE.write_text(content)
    print(f"  Data sources doc written → {DOCS_FILE.name}", flush=True)

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="NHL Phase 1 — Build canonical game table")
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=DEFAULT_SEASONS,
        help="Start years of seasons (e.g. 2021 2022 2023 2024)",
    )
    parser.add_argument(
        "--no-odds", action="store_true",
        help="Skip Odds API (saves quota, market_available will be False for all rows)",
    )
    parser.add_argument(
        "--audit-only", action="store_true",
        help="Re-run audit on existing nhl_games_canonical.csv without re-fetching",
    )
    args = parser.parse_args()

    if args.audit_only:
        if not OUT_CSV.exists():
            print("ERROR: nhl_games_canonical.csv not found; run without --audit-only first.")
            sys.exit(1)
        rows = _read_csv(OUT_CSV)
        all_pass, report = run_audit(rows)
        AUDIT_FILE.write_text(report)
        print(report)
        sys.exit(0 if all_pass else 1)

    # ── Step 1: Collect all game IDs across seasons ───────────────────────
    print("\n=== Step 1: Collecting game schedules ===", flush=True)
    all_games: list[dict] = []
    for season in args.seasons:
        games = fetch_season_game_ids(season)
        all_games.extend(games)

    print(f"\nTotal games to process: {len(all_games)}", flush=True)

    # ── Step 2: Compute schedule enrichments (no API needed) ─────────────
    print("\n=== Step 2: Computing schedule enrichments ===", flush=True)
    enrichments = compute_schedule_enrichments(all_games)

    # ── Step 3: Load MoneyPuck ────────────────────────────────────────────
    print("\n=== Step 3: Loading MoneyPuck ===", flush=True)
    mp_index = load_moneypuck()

    # ── Step 4: Load Odds API keys ────────────────────────────────────────
    api_key = "" if args.no_odds else _odds_api_key()
    if args.no_odds:
        print("\n  Skipping Odds API (--no-odds)", flush=True)
    elif not api_key:
        print("\n  [warn] ODDS_API_KEY not set — skipping market data", flush=True)

    # ── Step 5: Per-game data fetch ───────────────────────────────────────
    print(f"\n=== Step 5: Fetching per-game data ({len(all_games)} games) ===", flush=True)

    # Build odds index by date → list of game odds
    odds_by_date: dict[str, list[dict]] = {}
    # We'll fetch odds lazily per date as we iterate games

    rows: list[dict] = []
    n_total = len(all_games)

    for i, spine in enumerate(all_games, 1):
        gid  = spine["game_id"]
        gdate = spine["game_date"]
        home = spine["home_team"]
        away = spine["away_team"]

        if i % 50 == 0 or i == n_total:
            print(f"  [{i}/{n_total}] {gdate} {away}@{home}", flush=True)

        # Boxscore
        bx = fetch_boxscore(gid)
        if bx is None:
            # Game not completed or API error — skip but don't abort
            print(f"    [skip] No boxscore for game {gid}", flush=True)
            continue

        # PP stats
        pp = fetch_pp_stats(gid, home, away)
        time.sleep(0.05)

        # MoneyPuck
        mp_home_row = get_moneypuck_row(mp_index, gid, "home")
        mp_away_row = get_moneypuck_row(mp_index, gid, "away")

        # Odds (fetch per date, cache in memory)
        odds_for_game: dict | None = None
        if api_key:
            if gdate not in odds_by_date:
                odds_by_date[gdate] = fetch_odds_for_date(gdate, api_key)
                time.sleep(0.2)
            game_odds_list = odds_by_date.get(gdate, [])
            for o in game_odds_list:
                if o["home_team"] == home and o["away_team"] == away:
                    odds_for_game = o
                    break

        # Enrichments
        game_enrich = enrichments.get(gid, {})

        row = build_canonical_row(
            spine   = spine,
            bx      = bx,
            pp      = pp,
            enrich  = game_enrich,
            mp_home = mp_home_row,
            mp_away = mp_away_row,
            odds    = odds_for_game,
        )
        rows.append(row)

    print(f"\n  Built {len(rows)} canonical rows", flush=True)

    # ── Step 6: Write CSV ─────────────────────────────────────────────────
    print("\n=== Step 6: Writing CSV ===", flush=True)
    _write_csv(rows, OUT_CSV)
    print(f"  Written → {OUT_CSV.name} ({len(rows)} rows)", flush=True)

    # ── Step 7: Audit ─────────────────────────────────────────────────────
    print("\n=== Step 7: Running audit ===", flush=True)
    all_pass, report = run_audit(rows)
    AUDIT_FILE.write_text(report)
    print(report, flush=True)
    print(f"\n  Audit written → {AUDIT_FILE.name}", flush=True)

    # ── Step 8: Data sources doc ──────────────────────────────────────────
    print("\n=== Step 8: Writing data sources doc ===", flush=True)
    write_data_sources_doc()

    if not all_pass:
        print("\nWARNING: One or more audit gates FAILED. See nhl_canonical_audit.txt.", flush=True)
        sys.exit(1)
    else:
        print("\nPhase 1 complete — nhl_games_canonical.csv is ready.", flush=True)

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Normalize booleans and None to clean CSV values
            cleaned = {}
            for col in COLUMNS:
                v = row.get(col)
                if v is True:
                    cleaned[col] = "True"
                elif v is False:
                    cleaned[col] = "False"
                elif v is None:
                    cleaned[col] = ""
                else:
                    cleaned[col] = v
            writer.writerow(cleaned)

def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    # Re-parse numeric fields
    int_cols  = {"season_year", "home_score", "away_score", "total_goals",
                 "home_goals_reg", "away_goals_reg", "ot_goals", "reg_total_goals",
                 "home_pp_opportunities", "home_pp_goals", "home_pk_goals_against",
                 "away_pp_opportunities", "away_pp_goals", "away_pk_goals_against",
                 "home_rest_days", "home_games_last_7",
                 "away_rest_days", "away_games_last_7",
                 "home_goalie_sa", "home_goalie_ga",
                 "away_goalie_sa", "away_goalie_ga"}
    float_cols = {"home_pp_pct", "away_pp_pct", "home_pk_pct", "away_pk_pct",
                  "total_line", "over_price", "under_price",
                  "home_xgoals", "home_xgoals_against", "home_corsi_pct",
                  "home_fenwick_pct", "home_shots_on_goal", "home_hd_shots",
                  "home_hd_shots_against", "away_xgoals", "away_xgoals_against",
                  "away_corsi_pct", "away_fenwick_pct", "away_shots_on_goal",
                  "away_hd_shots", "away_hd_shots_against"}
    bool_cols  = {"went_to_ot", "went_to_so", "home_is_b2b", "away_is_b2b",
                  "home_goalie_starter", "away_goalie_starter",
                  "moneypuck_available", "market_available"}

    for row in rows:
        for col in int_cols:
            if row.get(col) not in ("", None):
                try:
                    row[col] = int(float(row[col]))
                except (ValueError, TypeError):
                    row[col] = None
            else:
                row[col] = None
        for col in float_cols:
            if row.get(col) not in ("", None):
                try:
                    row[col] = float(row[col])
                except (ValueError, TypeError):
                    row[col] = None
            else:
                row[col] = None
        for col in bool_cols:
            v = row.get(col, "")
            if v == "True":
                row[col] = True
            elif v == "False":
                row[col] = False
            else:
                row[col] = None
    return rows


if __name__ == "__main__":
    main()
