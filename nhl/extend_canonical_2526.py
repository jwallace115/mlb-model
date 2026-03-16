#!/usr/bin/env python3
"""
extend_canonical_2526.py — Extend nhl_games_canonical.csv with 2025-26 season data.

Fetches all completed 2025-26 regular-season games (Oct 2025 → yesterday) and
appends them to the canonical CSV in the same 62-column format.

MoneyPuck: expected unavailable for 2025-26 → moneypuck_available=0, fields null.
Odds API:  historical query per date; null if not found.

Usage:
    python3 nhl/extend_canonical_2526.py [--no-odds] [--dry-run]
    python3 nhl/extend_canonical_2526.py --rebuild-features-only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
NHL_DIR      = Path(__file__).resolve().parent
PROJECT      = NHL_DIR.parent
CANONICAL    = NHL_DIR / "nhl_games_canonical.csv"
FEATURE_TABLE = NHL_DIR / "nhl_feature_table.parquet"
CACHE_DIR    = NHL_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 2025-26 season window
# ---------------------------------------------------------------------------
SEASON_YEAR   = 2025
SEASON_START  = "2025-10-04"
# End = yesterday (all completed games through 2026-03-15)
SEASON_END    = (date.today() - timedelta(days=1)).isoformat()

# ---------------------------------------------------------------------------
# Column order (must match phase1 COLUMNS exactly)
# ---------------------------------------------------------------------------
COLUMNS = [
    "game_id", "game_date", "season_year",
    "home_team", "away_team",
    "home_score", "away_score", "total_goals",
    "home_goals_reg", "away_goals_reg",
    "went_to_ot", "went_to_so", "ot_goals",
    "reg_total_goals",
    "home_goalie_id", "home_goalie_name", "home_goalie_starter",
    "home_goalie_sa",  "home_goalie_ga",  "home_goalie_toi",
    "away_goalie_id", "away_goalie_name", "away_goalie_starter",
    "away_goalie_sa",  "away_goalie_ga",  "away_goalie_toi",
    "home_pp_opportunities", "home_pp_goals", "home_pk_goals_against",
    "away_pp_opportunities", "away_pp_goals", "away_pk_goals_against",
    "home_pp_pct", "away_pp_pct",
    "home_pk_pct", "away_pk_pct",
    "home_rest_days", "home_is_b2b", "home_games_last_7",
    "away_rest_days", "away_is_b2b", "away_games_last_7",
    "home_xgoals", "home_xgoals_against",
    "home_corsi_pct", "home_fenwick_pct",
    "home_shots_on_goal", "home_hd_shots", "home_hd_shots_against",
    "away_xgoals", "away_xgoals_against",
    "away_corsi_pct", "away_fenwick_pct",
    "away_shots_on_goal", "away_hd_shots", "away_hd_shots_against",
    "total_line", "over_price", "under_price",
    "moneypuck_available", "market_available",
    "pregame_confirmed",
]

# ---------------------------------------------------------------------------
# NHL team name → abbreviation (for Odds API)
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
    "St Louis Blues":         "STL",
    "Tampa Bay Lightning":    "TBL",
    "Toronto Maple Leafs":    "TOR",
    "Utah Hockey Club":       "UTA",
    "Vancouver Canucks":      "VAN",
    "Vegas Golden Knights":   "VGK",
    "Washington Capitals":    "WSH",
    "Winnipeg Jets":          "WPG",
    "Arizona Coyotes":        "ARI",
}

# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0.0.0 Safari/537.36",
})

def _get(url: str, params: dict | None = None, retries: int = 3,
         backoff: float = 2.0, timeout: int = 30) -> dict | list | None:
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

# ---------------------------------------------------------------------------
# 1. Fetch 2025-26 schedule
# ---------------------------------------------------------------------------
NHL_WEB_API = "https://api-web.nhle.com/v1"

def fetch_2526_game_ids(existing_ids: set[str]) -> list[dict]:
    """
    Walk 2025-26 schedule weekly from SEASON_START to SEASON_END.
    Returns only regular-season games (gameType=2) not already in existing_ids.
    """
    d     = datetime.strptime(SEASON_START, "%Y-%m-%d").date()
    end   = datetime.strptime(SEASON_END,   "%Y-%m-%d").date()
    games: list[dict] = []
    seen:  set[str]   = set()

    print(f"  Walking 2025-26 schedule: {SEASON_START} → {SEASON_END}", flush=True)

    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        cache_key = f"schedule_{ds}"
        data = _cached_get(cache_key, f"{NHL_WEB_API}/schedule/{ds}")
        if data and "gameWeek" in data:
            for week in data["gameWeek"]:
                for g in week.get("games", []):
                    if g.get("gameType") != 2:
                        continue
                    gid = str(g["id"])
                    if gid in seen or gid in existing_ids:
                        continue
                    # Only include games on or before SEASON_END
                    game_date = week["date"]
                    if game_date > SEASON_END:
                        continue
                    seen.add(gid)
                    home_abb = g.get("homeTeam", {}).get("abbrev", "")
                    away_abb = g.get("awayTeam", {}).get("abbrev", "")
                    games.append({
                        "game_id":     gid,
                        "game_date":   game_date,
                        "home_team":   home_abb,
                        "away_team":   away_abb,
                        "season_year": SEASON_YEAR,
                    })
        d += timedelta(days=7)
        time.sleep(0.15)

    print(f"    → {len(games)} new 2025-26 games", flush=True)
    return games

# ---------------------------------------------------------------------------
# 2. Boxscore
# ---------------------------------------------------------------------------
def fetch_boxscore(game_id: str) -> dict | None:
    cache_key = f"boxscore_{game_id}"
    data = _cached_get(cache_key, f"{NHL_WEB_API}/gamecenter/{game_id}/boxscore")
    if not data:
        return None

    home_score = data.get("homeTeam", {}).get("score")
    away_score = data.get("awayTeam", {}).get("score")
    if home_score is None or away_score is None:
        return None  # not yet complete

    outcome     = data.get("gameOutcome", {})
    period_type = outcome.get("lastPeriodType", "REG")

    went_to_ot = period_type in ("OT", "SO")
    went_to_so = period_type == "SO"

    if period_type == "REG":
        home_goals_reg = home_score
        away_goals_reg = away_score
        ot_goals = 0
    elif period_type == "OT":
        if home_score > away_score:
            home_goals_reg = home_score - 1
            away_goals_reg = away_score
        else:
            home_goals_reg = home_score
            away_goals_reg = away_score - 1
        ot_goals = 1
    else:  # SO
        if home_score > away_score:
            home_goals_reg = home_score - 1
            away_goals_reg = away_score
        else:
            home_goals_reg = home_score
            away_goals_reg = away_score - 1
        ot_goals = 0

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
    if not goalies:
        return {}
    starter = next((g for g in goalies if g.get("starter")), None)
    if not starter:
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
# 3. PP stats
# ---------------------------------------------------------------------------
NHL_STATS_REST = "https://api.nhle.com/stats/rest/en"

def fetch_pp_stats(game_id: str, home_team: str, away_team: str) -> dict:
    cache_key = f"pp_{game_id}"
    cp = _cache_path(cache_key)
    if cp.exists():
        return json.loads(cp.read_text())

    url    = f"{NHL_STATS_REST}/team/powerplay"
    params = {
        "isAggregate": "false",
        "isGame":      "true",
        "cayenneExp":  f"gameId={game_id}",
    }
    data = _get(url, params=params)
    result: dict = {
        "home_pp_opportunities": None, "home_pp_goals": None,
        "home_pk_goals_against": None, "away_pp_opportunities": None,
        "away_pp_goals": None, "away_pk_goals_against": None,
        "home_pp_pct": None, "away_pp_pct": None,
        "home_pk_pct": None, "away_pk_pct": None,
    }

    if not data or "data" not in data or not data["data"]:
        cp.write_text(json.dumps(result))
        return result

    rows = data["data"]
    home_row = away_row = None
    for row in rows:
        hr = row.get("homeRoad", "")
        if hr == "H":
            home_row = row
        elif hr == "R":
            away_row = row

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
        opp   = row.get("ppOpportunities", 0) or 0
        goals = row.get("powerPlayGoalsFor", 0) or 0
        sh_ga = row.get("shGoalsAgainst", 0) or 0
        pp_pct = (goals / opp) if opp > 0 else None
        return {
            f"{prefix}_pp_opportunities": opp,
            f"{prefix}_pp_goals":         goals,
            f"{prefix}_pk_goals_against": sh_ga,
            f"{prefix}_pp_pct":           round(pp_pct, 4) if pp_pct is not None else None,
            "_own_opp":                   opp,
        }

    home_parsed = _parse_row(home_row, "home")
    away_parsed = _parse_row(away_row, "away")

    away_opp  = away_parsed.pop("_own_opp", 0)
    home_opp  = home_parsed.pop("_own_opp", 0)
    home_sh_ga = home_parsed.get("home_pk_goals_against", 0) or 0
    away_sh_ga = away_parsed.get("away_pk_goals_against", 0) or 0

    home_pk_pct = (1.0 - home_sh_ga / away_opp) if away_opp > 0 else None
    away_pk_pct = (1.0 - away_sh_ga / home_opp) if home_opp > 0 else None

    result.update(home_parsed)
    result.update(away_parsed)
    result["home_pk_pct"] = round(home_pk_pct, 4) if home_pk_pct is not None else None
    result["away_pk_pct"] = round(away_pk_pct, 4) if away_pk_pct is not None else None

    cp.write_text(json.dumps(result))
    return result

# ---------------------------------------------------------------------------
# 4. MoneyPuck — check 2025-26 availability
# ---------------------------------------------------------------------------
MP_URL   = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
MP_CACHE = CACHE_DIR / "moneypuck_all_teams.csv"

def check_moneypuck_2526() -> dict[str, dict] | None:
    """
    Try to load MoneyPuck and check if any 2025-26 games are present.
    Returns index keyed by f"{game_id}_{home_or_away}" if available, else None.
    """
    if not MP_CACHE.exists():
        print("  MoneyPuck CSV not cached — skipping (moneypuck_available=0 for 2025-26)", flush=True)
        return None

    print("  Checking MoneyPuck cache for 2025-26 data …", flush=True)
    index: dict[str, dict] = {}
    count_2526 = 0
    with open(MP_CACHE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("situation") != "all":
                continue
            gid  = row.get("gameId", "")
            ha   = row.get("home_or_away", "").lower()
            # 2025-26 game IDs start with 2025 (e.g. 2025020001)
            if str(gid).startswith("2025"):
                count_2526 += 1
                index[f"{gid}_{ha}"] = row

    if count_2526 == 0:
        print(f"  MoneyPuck: 0 games for 2025-26 → moneypuck_available=0", flush=True)
        return None

    print(f"  MoneyPuck: {count_2526 // 2} games for 2025-26 found (refreshing CSV first…)", flush=True)
    # If we have 2025-26 data, try to update the cache
    try:
        print("  Refreshing MoneyPuck CSV for updated 2025-26 data …", flush=True)
        r = requests.get(
            MP_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
                "Referer": "https://moneypuck.com/data.htm",
            },
            stream=True, timeout=300,
        )
        if r.status_code == 200:
            with open(MP_CACHE, "wb") as f2:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f2.write(chunk)
            print("  MoneyPuck refreshed.", flush=True)
            # Reload
            index.clear()
            with open(MP_CACHE, newline="", encoding="utf-8") as f2:
                reader = csv.DictReader(f2)
                for row in reader:
                    if row.get("situation") != "all":
                        continue
                    gid = row.get("gameId", "")
                    ha  = row.get("home_or_away", "").lower()
                    if str(gid).startswith("2025"):
                        index[f"{gid}_{ha}"] = row
        else:
            print(f"  MoneyPuck refresh failed: {r.status_code}", flush=True)
    except Exception as e:
        print(f"  MoneyPuck refresh error: {e}", flush=True)

    return index if index else None

def null_mp_fields(prefix: str) -> dict:
    return {
        f"{prefix}_xgoals":           None,
        f"{prefix}_xgoals_against":   None,
        f"{prefix}_corsi_pct":        None,
        f"{prefix}_fenwick_pct":      None,
        f"{prefix}_shots_on_goal":    None,
        f"{prefix}_hd_shots":         None,
        f"{prefix}_hd_shots_against": None,
    }

def extract_mp_fields(row: dict | None, prefix: str) -> dict:
    if row is None:
        return null_mp_fields(prefix)

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
BOOK_PRIORITY = {"draftkings": 0, "fanduel": 1, "betmgm": 2, "williamhill_us": 3}

def _odds_api_key() -> str:
    import os as _os
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT / ".env")
    except ImportError:
        pass
    key = _os.environ.get("ODDS_API_KEY", "")
    if not key:
        # Try config.py
        try:
            sys.path.insert(0, str(PROJECT))
            import config as _cfg
            key = getattr(_cfg, "ODDS_API_KEY", "")
        except Exception:
            pass
    return key

def fetch_odds_for_date(game_date: str, api_key: str) -> list[dict]:
    if not api_key:
        return []

    snapshot = datetime.strptime(game_date, "%Y-%m-%d").replace(
        hour=4, minute=0, second=0, tzinfo=timezone.utc
    )
    snapshot_str = snapshot.strftime("%Y-%m-%dT%H:%M:%SZ")

    cache_key = f"odds_nhl_{game_date}"
    cp = _cache_path(cache_key)
    if cp.exists():
        return json.loads(cp.read_text())

    url    = f"{ODDS_API_BASE}/historical/sports/icehockey_nhl/odds/"
    params = {
        "apiKey":     api_key,
        "date":       snapshot_str,
        "regions":    "us",
        "markets":    "totals",
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel,betmgm,williamhill_us",
    }

    data = _get(url, params=params, timeout=60)
    if not data or "data" not in data:
        cp.write_text(json.dumps([]))
        return []

    results: list[dict] = []
    for game in data.get("data", []):
        home_full = game.get("home_team", "")
        away_full = game.get("away_team", "")
        home_abb  = NHL_TEAM_NAME_MAP.get(home_full)
        away_abb  = NHL_TEAM_NAME_MAP.get(away_full)
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
                        over_price = outcome.get("price")
                        total_line = outcome.get("point")
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
# 6. Schedule enrichments — rest days, B2B, games_last_7
# ---------------------------------------------------------------------------
def compute_schedule_enrichments(all_games: list[dict]) -> dict[str, dict[str, dict]]:
    """
    Compute rest/B2B/games_last_7 for 2025-26 games only (season boundary reset).
    all_games: list of {game_id, game_date, home_team, away_team, season_year}
    """
    from collections import defaultdict
    from datetime import datetime

    team_games: dict[str, list[tuple[date, str]]] = defaultdict(list)
    for g in all_games:
        gd = datetime.strptime(g["game_date"], "%Y-%m-%d").date()
        team_games[g["home_team"]].append((gd, g["game_id"]))
        team_games[g["away_team"]].append((gd, g["game_id"]))

    for key in team_games:
        team_games[key].sort()

    result: dict[str, dict[str, dict]] = {}
    for g in all_games:
        gid = g["game_id"]
        gd  = datetime.strptime(g["game_date"], "%Y-%m-%d").date()
        result[gid] = {}
        for side, team in [("home", g["home_team"]), ("away", g["away_team"])]:
            tgl = team_games[team]
            idx = next((i for i, (d2, g2) in enumerate(tgl) if g2 == gid), None)
            if idx is None or idx == 0:
                rest_days = None
                is_b2b    = False
                gl7       = 0
            else:
                prev_date = tgl[idx - 1][0]
                rest_days = (gd - prev_date).days
                is_b2b    = (rest_days == 1)
                cutoff    = gd - timedelta(days=7)
                gl7       = sum(1 for (d2, _) in tgl[:idx] if d2 > cutoff)

            result[gid][team] = {
                "rest_days":    rest_days,
                "is_b2b":       is_b2b,
                "games_last_7": gl7,
            }
    return result

# ---------------------------------------------------------------------------
# 7. Assemble and write new rows
# ---------------------------------------------------------------------------

def _v(d: dict | None, key: str, default=None):
    return d.get(key, default) if d else default

def build_row(spine, bx, pp, enrich, mp_home, mp_away, odds) -> dict:
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

    mp_h = extract_mp_fields(mp_home, "home")
    mp_a = extract_mp_fields(mp_away, "away")
    mp_avail = (mp_home is not None and mp_away is not None)

    row = {
        "game_id":      gid,
        "game_date":    spine["game_date"],
        "season_year":  spine["season_year"],
        "home_team":    home,
        "away_team":    away,

        "home_score":   home_sc,
        "away_score":   away_sc,
        "total_goals":  total,

        "home_goals_reg":  home_reg,
        "away_goals_reg":  away_reg,
        "went_to_ot":      _v(bx, "went_to_ot"),
        "went_to_so":      _v(bx, "went_to_so"),
        "ot_goals":        _v(bx, "ot_goals"),
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

        **mp_h,
        **mp_a,

        "total_line":  _v(odds, "total_line"),
        "over_price":  _v(odds, "over_price"),
        "under_price": _v(odds, "under_price"),

        "moneypuck_available": mp_avail,
        "market_available":    (odds is not None),
        "pregame_confirmed":   None,
    }
    return row

# ---------------------------------------------------------------------------
# 8. Rebuild feature table
# ---------------------------------------------------------------------------

def rebuild_feature_table() -> None:
    """
    Rebuild nhl_feature_table.parquet from updated canonical CSV.
    Imports phase3 functions directly — does NOT retrain ridge models.
    """
    print("\n[rebuild] Rebuilding nhl_feature_table.parquet (features only, no model retraining) …",
          flush=True)
    try:
        sys.path.insert(0, str(NHL_DIR))
        import phase3_build_features_and_ridge as p3

        df = p3.load_canonical()
        ft = p3.build_feature_table(df)

        ft.to_parquet(FEATURE_TABLE, index=False)
        print(f"[rebuild] Saved {len(ft):,} rows, {len(ft.columns)} columns → {FEATURE_TABLE}",
              flush=True)
    except Exception as e:
        print(f"[rebuild] ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()

# ---------------------------------------------------------------------------
# 9. Calibration diagnostic for 2025-26
# ---------------------------------------------------------------------------

def run_calibration_diagnostic() -> None:
    """
    Apply existing ridge models to 2025-26 feature rows and report
    mean(lambda_total_calibrated) vs mean(total_goals).
    """
    print("\n[calibration] Running 2025-26 calibration diagnostic …", flush=True)
    try:
        import pickle
        import numpy as np
        import pandas as pd

        ft = pd.read_parquet(FEATURE_TABLE)
        rows_2526 = ft[ft["season_year"] == SEASON_YEAR].copy()
        if rows_2526.empty:
            print("[calibration] No 2025-26 rows in feature table — skipping.", flush=True)
            return

        # Load calibration from phase45
        cal_path = NHL_DIR / "phase45_calibration.parquet"
        if not cal_path.exists():
            print("[calibration] phase45_calibration.parquet not found — skipping.", flush=True)
            return

        # Load lambda_total_calibrated if it exists in the feature table
        if "lambda_total_calibrated" in rows_2526.columns and "total_goals" in rows_2526.columns:
            valid = rows_2526[
                rows_2526["lambda_total_calibrated"].notna() &
                rows_2526["total_goals"].notna()
            ]
            if valid.empty:
                print("[calibration] No valid rows with lambda + total_goals.", flush=True)
                return

            mean_lambda = valid["lambda_total_calibrated"].mean()
            mean_actual = valid["total_goals"].mean()
            diff        = mean_lambda - mean_actual
            n           = len(valid)
            print(f"[calibration] 2025-26 (n={n} games with lines):")
            print(f"  mean(lambda_total_calibrated) = {mean_lambda:.3f}")
            print(f"  mean(total_goals)              = {mean_actual:.3f}")
            print(f"  diff (lambda - actual)         = {diff:+.3f}")
            if abs(diff) > 0.5:
                print(f"  [WARNING] Drift > 0.5 goals — consider recalibrating.")
            else:
                print(f"  [OK] Drift within acceptable range (< 0.5 goals).")
        else:
            print("[calibration] lambda_total_calibrated not in feature table — "
                  "run nhl_daily_pipeline.py to generate live signals with calibration.", flush=True)

    except Exception as e:
        print(f"[calibration] Error: {e}", flush=True)

# ---------------------------------------------------------------------------
# 10. Audit gates (2025-26 specific)
# ---------------------------------------------------------------------------

def run_2526_audit(new_rows: list[dict]) -> None:
    print("\n[audit] Running 2025-26 audit gates …", flush=True)
    n = len(new_rows)
    failures: list[str] = []

    def gate(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        msg = f"  [{status}] {name}"
        if detail:
            msg += f": {detail}"
        print(msg, flush=True)
        if not ok:
            failures.append(name)

    # Gate 1: Row count reasonable (2025-26 regular season ~1312 games total;
    # through Mar 15 expect ~900-1100)
    gate("Gate 1: Row count ≥ 500", n >= 500, f"actual={n}")

    # Gate 2: No duplicate game_ids
    gids  = [r["game_id"] for r in new_rows]
    dupes = n - len(set(gids))
    gate("Gate 2: No duplicate game_ids", dupes == 0, f"dupes={dupes}")

    # Gate 3: All required columns present
    actual_cols   = set(new_rows[0].keys()) if new_rows else set()
    required_cols = set(COLUMNS)
    missing       = required_cols - actual_cols
    gate("Gate 3: All required columns present",
         len(missing) == 0,
         f"missing={sorted(missing)}" if missing else "")

    # Gate 4: total_goals ≥ 1 for all scored rows
    scored  = [r for r in new_rows if r.get("total_goals") is not None]
    bad_tg  = [r for r in scored if (r["total_goals"] or 0) < 1]
    gate("Gate 4: total_goals ≥ 1 for all scored games",
         len(bad_tg) == 0, f"bad_rows={len(bad_tg)}")

    # Gate 5: OT/SO consistency
    bad_so = [r for r in new_rows if r.get("went_to_so") and not r.get("went_to_ot")]
    gate("Gate 5: OT/SO flags consistent",
         len(bad_so) == 0, f"bad_so={len(bad_so)}")

    # Gate 6: reg_total_goals consistency
    bad_reg = []
    for r in new_rows:
        hg = r.get("home_goals_reg")
        ag = r.get("away_goals_reg")
        rg = r.get("reg_total_goals")
        if hg is not None and ag is not None and rg is not None:
            if abs(hg + ag - rg) > 0.001:
                bad_reg.append(r["game_id"])
    gate("Gate 6: reg_total_goals arithmetic",
         len(bad_reg) == 0, f"bad_rows={len(bad_reg)}")

    # Gate 7: MoneyPuck coverage (expected 0% for 2025-26 — WARN not FAIL)
    mp_count = sum(1 for r in new_rows if r.get("moneypuck_available"))
    mp_pct   = mp_count / n if n > 0 else 0
    print(f"  [INFO] MoneyPuck coverage: {mp_count}/{n} = {mp_pct:.1%} "
          f"(expected ~0% for 2025-26)", flush=True)

    # Gate 8: Odds API coverage — report only
    mkt_count = sum(1 for r in new_rows if r.get("market_available"))
    mkt_pct   = mkt_count / n if n > 0 else 0
    gate("Gate 8: Market coverage ≥ 50% (historical Odds API)",
         mkt_pct >= 0.50,
         f"{mkt_count}/{n} = {mkt_pct:.1%}")

    print(flush=True)
    if failures:
        print(f"[audit] OVERALL: FAIL — {len(failures)} gate(s) failed: {failures}", flush=True)
    else:
        print("[audit] OVERALL: PASS — all gates satisfied", flush=True)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-odds",              action="store_true",
                        help="Skip Odds API queries")
    parser.add_argument("--dry-run",              action="store_true",
                        help="Fetch data but do not write to canonical CSV")
    parser.add_argument("--rebuild-features-only", action="store_true",
                        help="Skip data fetch; just rebuild feature table")
    args = parser.parse_args()

    if args.rebuild_features_only:
        rebuild_feature_table()
        run_calibration_diagnostic()
        return

    # ── Load existing canonical CSV ──────────────────────────────────────────
    print(f"[extend] Loading existing canonical CSV …", flush=True)
    existing_rows: list[dict] = []
    existing_ids:  set[str]   = set()
    with open(CANONICAL, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_rows.append(row)
            existing_ids.add(row["game_id"])

    existing_2526 = [r for r in existing_rows if str(r.get("season_year")) == "2025"]
    print(f"  Existing rows: {len(existing_rows)} total, "
          f"{len(existing_2526)} already 2025-26", flush=True)

    # ── Fetch 2025-26 game list ───────────────────────────────────────────────
    print(f"\n[extend] Fetching 2025-26 schedule …", flush=True)
    new_spines = fetch_2526_game_ids(existing_ids)

    if not new_spines:
        print("[extend] No new 2025-26 games to add.", flush=True)
    else:
        # ── MoneyPuck check ───────────────────────────────────────────────────
        print(f"\n[extend] Checking MoneyPuck for 2025-26 …", flush=True)
        mp_index = check_moneypuck_2526()  # None if unavailable

        # ── Odds API key ──────────────────────────────────────────────────────
        odds_api_key = "" if args.no_odds else _odds_api_key()
        if odds_api_key:
            print(f"  Odds API: key found, will query historical lines", flush=True)
        else:
            print(f"  Odds API: no key or --no-odds — market fields will be null", flush=True)

        # ── Compute schedule enrichments for ALL 2025-26 games ───────────────
        # Include existing 2025-26 rows for correct rest computation
        all_2526 = [
            {"game_id": r["game_id"], "game_date": r["game_date"],
             "home_team": r["home_team"], "away_team": r["away_team"],
             "season_year": 2025}
            for r in existing_2526
        ] + new_spines

        print(f"\n[extend] Computing schedule enrichments for {len(all_2526)} 2025-26 games …",
              flush=True)
        enrichments = compute_schedule_enrichments(all_2526)

        # ── Fetch odds for each unique date ───────────────────────────────────
        unique_dates = sorted(set(g["game_date"] for g in new_spines))
        odds_by_date: dict[str, list[dict]] = {}
        if odds_api_key:
            print(f"\n[extend] Fetching Odds API for {len(unique_dates)} dates …", flush=True)
            for i, gd in enumerate(unique_dates, 1):
                print(f"  [{i}/{len(unique_dates)}] {gd}", end=" ", flush=True)
                odds_list = fetch_odds_for_date(gd, odds_api_key)
                odds_by_date[gd] = odds_list
                cached = "cached" if _cache_path(f"odds_nhl_{gd}").exists() else "fetched"
                print(f"({len(odds_list)} games, {cached})", flush=True)
                time.sleep(0.2)
        else:
            for gd in unique_dates:
                odds_by_date[gd] = []

        # ── Fetch boxscores and PP stats ──────────────────────────────────────
        print(f"\n[extend] Fetching boxscores and PP stats for {len(new_spines)} games …",
              flush=True)
        new_rows: list[dict] = []
        skipped = 0

        for i, spine in enumerate(new_spines, 1):
            gid       = spine["game_id"]
            gdate     = spine["game_date"]
            home_team = spine["home_team"]
            away_team = spine["away_team"]

            if i % 50 == 0 or i == len(new_spines):
                print(f"  Progress: {i}/{len(new_spines)}", flush=True)

            # Boxscore
            bx = fetch_boxscore(gid)
            if bx is None:
                # Game not yet completed — skip (don't add to canonical)
                skipped += 1
                continue

            # PP stats
            pp = fetch_pp_stats(gid, home_team, away_team)

            # Enrichments
            game_enrich = enrichments.get(gid, {})

            # MoneyPuck
            if mp_index is not None:
                mp_home_row = mp_index.get(f"{gid}_home")
                mp_away_row = mp_index.get(f"{gid}_away")
            else:
                mp_home_row = mp_away_row = None

            # Odds
            day_odds = odds_by_date.get(gdate, [])
            odds_row = None
            for o in day_odds:
                if o["home_team"] == home_team and o["away_team"] == away_team:
                    odds_row = o
                    break

            row = build_row(spine, bx, pp, game_enrich, mp_home_row, mp_away_row, odds_row)
            new_rows.append(row)

            time.sleep(0.05)

        print(f"\n[extend] Built {len(new_rows)} new rows "
              f"(skipped {skipped} incomplete games)", flush=True)

        if new_rows:
            # ── Audit ─────────────────────────────────────────────────────────
            run_2526_audit(new_rows)

            if not args.dry_run:
                # ── Append to CSV ─────────────────────────────────────────────
                print(f"\n[extend] Appending {len(new_rows)} rows to {CANONICAL} …", flush=True)
                with open(CANONICAL, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                    for row in new_rows:
                        writer.writerow(row)

                total_after = len(existing_rows) + len(new_rows)
                print(f"[extend] CSV updated: {total_after} total rows "
                      f"({len(existing_rows)} existing + {len(new_rows)} new 2025-26)", flush=True)

                # ── Summary stats ─────────────────────────────────────────────
                mp_count  = sum(1 for r in new_rows if r.get("moneypuck_available"))
                mkt_count = sum(1 for r in new_rows if r.get("market_available"))
                n         = len(new_rows)
                print(f"\n[extend] 2025-26 summary:")
                print(f"  Games added:           {n}")
                print(f"  MoneyPuck coverage:    {mp_count}/{n} = {mp_count/n:.1%}")
                print(f"  Odds API coverage:     {mkt_count}/{n} = {mkt_count/n:.1%}")
            else:
                print(f"\n[extend] --dry-run: CSV not modified.", flush=True)
                # Still print summary
                mp_count  = sum(1 for r in new_rows if r.get("moneypuck_available"))
                mkt_count = sum(1 for r in new_rows if r.get("market_available"))
                n         = len(new_rows)
                print(f"\n[extend] 2025-26 preview (dry-run):")
                print(f"  Games found:           {n}")
                print(f"  MoneyPuck coverage:    {mp_count}/{n} = {mp_count/n:.1%}")
                print(f"  Odds API coverage:     {mkt_count}/{n} = {mkt_count/n:.1%}")

    # ── Rebuild feature table ─────────────────────────────────────────────────
    if not args.dry_run and new_spines:
        rebuild_feature_table()

    # ── Calibration diagnostic ────────────────────────────────────────────────
    if not args.dry_run:
        run_calibration_diagnostic()

    print("\n[extend] Done.", flush=True)


if __name__ == "__main__":
    main()
