#!/usr/bin/env python3
"""
nhl_refresh_canonical.py — Daily canonical table refresh.

Fetches any completed NHL regular-season games not yet in nhl_games_canonical.csv,
appends new rows in the canonical schema, then incrementally appends new feature
rows to nhl_feature_table.parquet (reads full history for rolling context, but
only writes rows for newly added games).

Called from push_results.py at 7am before nhl_daily_pipeline.py runs.

Usage:
    python3 nhl/nhl_refresh_canonical.py
    python3 nhl/nhl_refresh_canonical.py --no-odds   # skip Odds API
    python3 nhl/nhl_refresh_canonical.py --dry-run   # audit only, no writes
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
NHL_DIR       = Path(__file__).resolve().parent
PROJECT       = NHL_DIR.parent
CANONICAL     = NHL_DIR / "nhl_games_canonical.csv"
FEATURE_TABLE = NHL_DIR / "nhl_feature_table.parquet"
CACHE_DIR     = NHL_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Current season detection
# ---------------------------------------------------------------------------
def current_season_year() -> int:
    """
    Return the start year of the active NHL season.
    Convention: season_year=2025 means 2025-26.
    NHL seasons start in early October; use Sep 15 as the cutover.
    """
    today = date.today()
    if today.month >= 9 and today.day >= 15:
        return today.year
    return today.year - 1

def season_start(season_year: int) -> str:
    """Approximate season start date (Oct 1 of season_year)."""
    return f"{season_year}-10-01"

# ---------------------------------------------------------------------------
# Column order
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
# Team name → abbreviation
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
# HTTP helpers
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

def _cached_get(key: str, url: str, params: dict | None = None,
                force: bool = False) -> dict | list | None:
    """Cache GET. force=True bypasses cache (for schedule pages that update daily)."""
    cp = _cache_path(key)
    if cp.exists() and not force:
        return json.loads(cp.read_text())
    data = _get(url, params=params)
    if data is not None:
        cp.write_text(json.dumps(data))
    return data

# ---------------------------------------------------------------------------
# 1. Schedule — new games for current season
# ---------------------------------------------------------------------------
NHL_WEB_API = "https://api-web.nhle.com/v1"

def fetch_new_games(season_year: int, existing_ids: set[str]) -> list[dict]:
    """
    Walk the current season schedule from season_start to yesterday.
    Returns only regular-season games (gameType=2) not in existing_ids.
    Schedule pages are NOT cached (force=True) so today's newly completed
    games are always picked up.
    """
    start = season_start(season_year)
    end   = (date.today() - timedelta(days=1)).isoformat()   # completed games only

    d   = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date()

    games: list[dict] = []
    seen:  set[str]   = set()

    while d <= end_d:
        ds = d.strftime("%Y-%m-%d")
        # Force-refresh schedule pages; boxscores remain cached
        data = _cached_get(f"schedule_{ds}", f"{NHL_WEB_API}/schedule/{ds}", force=True)
        if data and "gameWeek" in data:
            for week in data["gameWeek"]:
                for g in week.get("games", []):
                    if g.get("gameType") != 2:
                        continue
                    gid       = str(g["id"])
                    game_date = week["date"]
                    if game_date > end:
                        continue
                    if gid in seen or gid in existing_ids:
                        continue
                    seen.add(gid)
                    games.append({
                        "game_id":     gid,
                        "game_date":   game_date,
                        "home_team":   g.get("homeTeam", {}).get("abbrev", ""),
                        "away_team":   g.get("awayTeam", {}).get("abbrev", ""),
                        "season_year": season_year,
                    })
        d += timedelta(days=7)
        time.sleep(0.10)

    return games

# ---------------------------------------------------------------------------
# 2. Boxscore
# ---------------------------------------------------------------------------
def fetch_boxscore(game_id: str) -> dict | None:
    data = _cached_get(f"boxscore_{game_id}", f"{NHL_WEB_API}/gamecenter/{game_id}/boxscore")
    if not data:
        return None

    home_score = data.get("homeTeam", {}).get("score")
    away_score = data.get("awayTeam", {}).get("score")
    if home_score is None or away_score is None:
        return None

    outcome     = data.get("gameOutcome", {})
    period_type = outcome.get("lastPeriodType", "REG")
    went_to_ot  = period_type in ("OT", "SO")
    went_to_so  = period_type == "SO"

    if period_type == "REG":
        home_goals_reg = home_score
        away_goals_reg = away_score
        ot_goals = 0
    elif period_type == "OT":
        if home_score > away_score:
            home_goals_reg, away_goals_reg = home_score - 1, away_score
        else:
            home_goals_reg, away_goals_reg = home_score, away_score - 1
        ot_goals = 1
    else:  # SO
        if home_score > away_score:
            home_goals_reg, away_goals_reg = home_score - 1, away_score
        else:
            home_goals_reg, away_goals_reg = home_score, away_score - 1
        ot_goals = 0

    pbg         = data.get("playerByGameStats", {})
    home_goalie = _extract_goalie(pbg.get("homeTeam", {}).get("goalies", []))
    away_goalie = _extract_goalie(pbg.get("awayTeam", {}).get("goalies", []))

    return {
        "home_score": home_score, "away_score": away_score,
        "went_to_ot": went_to_ot, "went_to_so": went_to_so, "ot_goals": ot_goals,
        "home_goals_reg": home_goals_reg, "away_goals_reg": away_goals_reg,
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
            try:
                m, s = g.get("toi", "00:00").split(":")
                return int(m) * 60 + int(s)
            except Exception:
                return 0
        starter = max(goalies, key=_toi_sec) if goalies else {}
    g = starter
    sa = g.get("shotsAgainst") or g.get("powerPlayShotsAgainst")
    return {
        "id":      g.get("playerId"),
        "name":    g.get("name", {}).get("default") if isinstance(g.get("name"), dict)
                   else g.get("name"),
        "starter": g.get("starter", False),
        "sa":      sa,
        "ga":      g.get("goalsAgainst"),
        "toi":     g.get("toi"),
    }

# ---------------------------------------------------------------------------
# 3. PP stats
# ---------------------------------------------------------------------------
NHL_STATS_REST = "https://api.nhle.com/stats/rest/en"

def fetch_pp_stats(game_id: str, home_team: str, away_team: str) -> dict:
    null_result = {
        "home_pp_opportunities": None, "home_pp_goals": None,
        "home_pk_goals_against": None, "away_pp_opportunities": None,
        "away_pp_goals": None, "away_pk_goals_against": None,
        "home_pp_pct": None, "away_pp_pct": None,
        "home_pk_pct": None, "away_pk_pct": None,
    }
    cp = _cache_path(f"pp_{game_id}")
    if cp.exists():
        return json.loads(cp.read_text())

    data = _get(f"{NHL_STATS_REST}/team/powerplay", params={
        "isAggregate": "false", "isGame": "true",
        "cayenneExp":  f"gameId={game_id}",
    })

    if not data or "data" not in data or not data["data"]:
        cp.write_text(json.dumps(null_result))
        return null_result

    rows     = data["data"]
    home_row = next((r for r in rows if r.get("homeRoad") == "H"), None)
    away_row = next((r for r in rows if r.get("homeRoad") == "R"), None)
    if home_row is None or away_row is None:
        for r in rows:
            abb = r.get("teamAbbrev", "") or r.get("teamCode", "")
            if abb == home_team:
                home_row = r
            elif abb == away_team:
                away_row = r

    def _parse(row: dict | None, prefix: str) -> tuple[dict, int]:
        if row is None:
            return {}, 0
        opp   = row.get("ppOpportunities", 0) or 0
        goals = row.get("powerPlayGoalsFor", 0) or 0
        sh_ga = row.get("shGoalsAgainst", 0) or 0
        pp_pct = round(goals / opp, 4) if opp > 0 else None
        return {
            f"{prefix}_pp_opportunities": opp,
            f"{prefix}_pp_goals":         goals,
            f"{prefix}_pk_goals_against": sh_ga,
            f"{prefix}_pp_pct":           pp_pct,
        }, opp

    h_parsed, h_opp = _parse(home_row, "home")
    a_parsed, a_opp = _parse(away_row, "away")

    h_sh_ga = h_parsed.get("home_pk_goals_against", 0) or 0
    a_sh_ga = a_parsed.get("away_pk_goals_against", 0) or 0
    result  = {**null_result, **h_parsed, **a_parsed}
    result["home_pk_pct"] = round(1.0 - h_sh_ga / a_opp, 4) if a_opp > 0 else None
    result["away_pk_pct"] = round(1.0 - a_sh_ga / h_opp, 4) if h_opp > 0 else None

    cp.write_text(json.dumps(result))
    return result

# ---------------------------------------------------------------------------
# 4. MoneyPuck
# ---------------------------------------------------------------------------
MP_URL   = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
MP_CACHE = CACHE_DIR / "moneypuck_all_teams.csv"

def _mp_season_prefix(season_year: int) -> str:
    return str(season_year)  # game IDs start with season_year (e.g. "2025...")

def load_moneypuck_for_season(season_year: int) -> dict[str, dict] | None:
    """
    Load MoneyPuck index for a specific season.
    Returns {f"{game_id}_{home_or_away}": row} or None if no data for that season.
    Does NOT re-download if cache exists; caller should manage freshness separately.
    """
    if not MP_CACHE.exists():
        return None

    prefix = _mp_season_prefix(season_year)
    index: dict[str, dict] = {}
    with open(MP_CACHE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("situation") != "all":
                continue
            gid = row.get("gameId", "")
            if not str(gid).startswith(prefix):
                continue
            ha = row.get("home_or_away", "").lower()
            index[f"{gid}_{ha}"] = row

    return index if index else None

def extract_mp_fields(row: dict | None, prefix: str) -> dict:
    def _f(key: str) -> float | None:
        v = row.get(key) if row else None
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
# 5. Odds API
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
    cache_key = f"odds_nhl_{game_date}"
    cp = _cache_path(cache_key)
    if cp.exists():
        return json.loads(cp.read_text())

    data = _get(
        f"{ODDS_API_BASE}/historical/sports/icehockey_nhl/odds/",
        params={
            "apiKey": api_key,
            "date":   snapshot.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "regions": "us", "markets": "totals", "oddsFormat": "american",
            "bookmakers": "draftkings,fanduel,betmgm,williamhill_us",
        },
        timeout=60,
    )
    if not data or "data" not in data:
        cp.write_text(json.dumps([]))
        return []

    results: list[dict] = []
    for game in data.get("data", []):
        home_abb = NHL_TEAM_NAME_MAP.get(game.get("home_team", ""))
        away_abb = NHL_TEAM_NAME_MAP.get(game.get("away_team", ""))
        if not home_abb or not away_abb:
            continue
        for book in game.get("bookmakers", []):
            bname = book.get("key", "")
            if bname not in BOOK_PRIORITY:
                continue
            for market in book.get("markets", []):
                if market.get("key") != "totals":
                    continue
                over_price = under_price = total_line = None
                for o in market.get("outcomes", []):
                    if o.get("name") == "Over":
                        over_price = o.get("price"); total_line = o.get("point")
                    elif o.get("name") == "Under":
                        under_price = o.get("price")
                if total_line is not None:
                    results.append({
                        "home_team": home_abb, "away_team": away_abb,
                        "total_line": total_line, "over_price": over_price,
                        "under_price": under_price, "book": bname,
                    })

    best: dict[tuple[str, str], dict] = {}
    for row in results:
        k = (row["home_team"], row["away_team"])
        if k not in best or BOOK_PRIORITY.get(row["book"], 99) < BOOK_PRIORITY.get(best[k]["book"], 99):
            best[k] = row

    final = list(best.values())
    cp.write_text(json.dumps(final))
    return final

# ---------------------------------------------------------------------------
# 6. Schedule enrichments (rest/B2B/games_last_7) for new games
# ---------------------------------------------------------------------------
def compute_enrichments_for_new_games(
    all_season_spines: list[dict],   # all games this season (existing + new)
    new_game_ids: set[str],
) -> dict[str, dict[str, dict]]:
    """
    Compute rest/B2B/games_last_7 for new games only.
    Uses full season context so rest_days are accurate.
    Returns {game_id: {team: {rest_days, is_b2b, games_last_7}}}
    """
    from collections import defaultdict

    team_games: dict[str, list[tuple[date, str]]] = defaultdict(list)
    for g in all_season_spines:
        gd = datetime.strptime(g["game_date"], "%Y-%m-%d").date()
        team_games[g["home_team"]].append((gd, g["game_id"]))
        team_games[g["away_team"]].append((gd, g["game_id"]))

    for key in team_games:
        team_games[key].sort()

    result: dict[str, dict[str, dict]] = {}
    for g in all_season_spines:
        gid = g["game_id"]
        if gid not in new_game_ids:
            continue  # only compute for new games

        gd  = datetime.strptime(g["game_date"], "%Y-%m-%d").date()
        result[gid] = {}
        for team in (g["home_team"], g["away_team"]):
            tgl = team_games[team]
            idx = next((i for i, (_, g2) in enumerate(tgl) if g2 == gid), None)
            if idx is None or idx == 0:
                result[gid][team] = {"rest_days": None, "is_b2b": False, "games_last_7": 0}
            else:
                prev_date = tgl[idx - 1][0]
                rest_days = (gd - prev_date).days
                cutoff    = gd - timedelta(days=7)
                result[gid][team] = {
                    "rest_days":    rest_days,
                    "is_b2b":       rest_days == 1,
                    "games_last_7": sum(1 for (d2, _) in tgl[:idx] if d2 > cutoff),
                }
    return result

# ---------------------------------------------------------------------------
# 7. Assemble canonical row
# ---------------------------------------------------------------------------
def _v(d: dict | None, key: str, default=None):
    return d.get(key, default) if d else default

def build_row(spine, bx, pp, enrich, mp_h_row, mp_a_row, odds_row) -> dict:
    home = spine["home_team"]
    away = spine["away_team"]

    home_sc  = _v(bx, "home_score")
    away_sc  = _v(bx, "away_score")
    total    = (home_sc + away_sc) if (home_sc is not None and away_sc is not None) else None
    home_reg = _v(bx, "home_goals_reg")
    away_reg = _v(bx, "away_goals_reg")
    reg_tot  = (home_reg + away_reg) if (home_reg is not None and away_reg is not None) else None

    h_enr = enrich.get(home, {})
    a_enr = enrich.get(away, {})
    mp_h  = extract_mp_fields(mp_h_row, "home")
    mp_a  = extract_mp_fields(mp_a_row, "away")

    return {
        "game_id":      spine["game_id"],
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
        "reg_total_goals": reg_tot,

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

        "total_line":  _v(odds_row, "total_line"),
        "over_price":  _v(odds_row, "over_price"),
        "under_price": _v(odds_row, "under_price"),

        "moneypuck_available": (mp_h_row is not None and mp_a_row is not None),
        "market_available":    (odds_row is not None),
        "pregame_confirmed":   None,
    }

# ---------------------------------------------------------------------------
# 8. Audit (new rows only)
# ---------------------------------------------------------------------------
def audit_new_rows(rows: list[dict]) -> bool:
    """Lightweight audit on newly built rows. Returns True if all pass."""
    ok = True

    # No duplicate game_ids
    gids  = [r["game_id"] for r in rows]
    dupes = len(gids) - len(set(gids))
    if dupes > 0:
        print(f"[nhl_refresh] AUDIT FAIL: {dupes} duplicate game_ids", flush=True)
        ok = False

    # total_goals arithmetic
    for r in rows:
        hs = r.get("home_score"); as_ = r.get("away_score"); tg = r.get("total_goals")
        if hs is not None and as_ is not None and tg is not None:
            if abs(hs + as_ - tg) > 0.001:
                print(f"[nhl_refresh] AUDIT FAIL: total_goals mismatch game_id={r['game_id']}", flush=True)
                ok = False

    # OT/SO consistency
    for r in rows:
        if r.get("went_to_so") and not r.get("went_to_ot"):
            print(f"[nhl_refresh] AUDIT FAIL: SO without OT flag game_id={r['game_id']}", flush=True)
            ok = False

    if ok:
        print(f"[nhl_refresh] Audit PASS ({len(rows)} new rows)", flush=True)
    return ok

# ---------------------------------------------------------------------------
# 9. Incremental feature table append
# ---------------------------------------------------------------------------
def append_feature_rows(new_canonical_rows: list[dict]) -> None:
    """
    Build feature rows for newly added games and append to nhl_feature_table.parquet.
    Reads FULL canonical for rolling context (correct rest/rolling windows),
    but only writes feature rows for the new game_ids.
    Does not retrain or modify models.
    """
    print("[nhl_refresh] Rebuilding feature rows for new games …", flush=True)
    try:
        import pandas as pd
        sys.path.insert(0, str(NHL_DIR))
        import phase3_build_features_and_ridge as p3

        new_ids = {r["game_id"] for r in new_canonical_rows}

        # Full canonical → correct rolling features
        df = p3.load_canonical()
        ft_full = p3.build_feature_table(df)

        # Filter to only new game_ids
        ft_new = ft_full[ft_full["game_id"].astype(str).isin(new_ids)].copy()

        if ft_new.empty:
            print("[nhl_refresh] No new feature rows to append.", flush=True)
            return

        # Append to existing feature table
        if FEATURE_TABLE.exists():
            ft_existing = pd.read_parquet(FEATURE_TABLE)
            # Drop any rows for these game_ids (idempotent)
            ft_existing = ft_existing[~ft_existing["game_id"].astype(str).isin(new_ids)]
            ft_combined = pd.concat([ft_existing, ft_new], ignore_index=True)
        else:
            ft_combined = ft_new

        ft_combined.to_parquet(FEATURE_TABLE, index=False)
        print(f"[nhl_refresh] Feature table: appended {len(ft_new)} new rows "
              f"(total={len(ft_combined)})", flush=True)

    except Exception as e:
        print(f"[nhl_refresh] Feature table append failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-odds",  action="store_true", help="Skip Odds API")
    parser.add_argument("--dry-run",  action="store_true", help="Fetch but do not write")
    args = parser.parse_args()

    season_year = current_season_year()
    today       = date.today().isoformat()

    print(f"[nhl_refresh] Starting canonical refresh  "
          f"season={season_year}-{season_year+1}  date={today}", flush=True)

    # ── Load existing canonical ──────────────────────────────────────────────
    existing_rows: list[dict] = []
    existing_ids:  set[str]   = set()
    with open(CANONICAL, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_rows.append(row)
            existing_ids.add(row["game_id"])

    existing_this_season = sum(
        1 for r in existing_rows if str(r.get("season_year")) == str(season_year)
    )
    print(f"[nhl_refresh] Canonical: {len(existing_rows)} total rows, "
          f"{existing_this_season} already this season", flush=True)

    # ── Fetch new game list ──────────────────────────────────────────────────
    print(f"[nhl_refresh] Scanning schedule for new completed games …", flush=True)
    new_spines = fetch_new_games(season_year, existing_ids)

    if not new_spines:
        print(f"[nhl_refresh] Added 0 new games. "
              f"{existing_this_season} games already current.", flush=True)
        return

    print(f"[nhl_refresh] Found {len(new_spines)} new games to process", flush=True)

    # ── MoneyPuck ────────────────────────────────────────────────────────────
    mp_index = load_moneypuck_for_season(season_year)
    if mp_index:
        print(f"[nhl_refresh] MoneyPuck: {len(mp_index)//2} games available for {season_year}-{season_year+1}",
              flush=True)
    else:
        print(f"[nhl_refresh] MoneyPuck: no {season_year}-{season_year+1} data — "
              f"moneypuck_available=0 for new rows", flush=True)

    # ── Odds API key ─────────────────────────────────────────────────────────
    odds_key = "" if args.no_odds else _odds_api_key()

    # ── Odds for new dates only ───────────────────────────────────────────────
    unique_dates = sorted(set(g["game_date"] for g in new_spines))
    odds_by_date: dict[str, list[dict]] = {}
    if odds_key:
        print(f"[nhl_refresh] Fetching Odds API for {len(unique_dates)} date(s) …", flush=True)
        for gd in unique_dates:
            odds_by_date[gd] = fetch_odds_for_date(gd, odds_key)
            time.sleep(0.15)
    else:
        for gd in unique_dates:
            odds_by_date[gd] = []

    # ── Schedule enrichments ──────────────────────────────────────────────────
    # Build full season spine (existing + new) for correct rest_days context
    existing_season_spines = [
        {"game_id": r["game_id"], "game_date": r["game_date"],
         "home_team": r["home_team"], "away_team": r["away_team"],
         "season_year": season_year}
        for r in existing_rows if str(r.get("season_year")) == str(season_year)
    ]
    all_season_spines = existing_season_spines + new_spines
    new_ids_set       = {g["game_id"] for g in new_spines}
    enrichments       = compute_enrichments_for_new_games(all_season_spines, new_ids_set)

    # ── Fetch boxscores + PP + assemble rows ─────────────────────────────────
    new_rows: list[dict] = []
    skipped = 0

    for spine in new_spines:
        gid   = spine["game_id"]
        gdate = spine["game_date"]
        home  = spine["home_team"]
        away  = spine["away_team"]

        bx = fetch_boxscore(gid)
        if bx is None:
            skipped += 1
            continue  # game not yet complete

        pp = fetch_pp_stats(gid, home, away)

        game_enrich = enrichments.get(gid, {})

        mp_h_row = mp_a_row = None
        if mp_index:
            mp_h_row = mp_index.get(f"{gid}_home")
            mp_a_row = mp_index.get(f"{gid}_away")

        day_odds = odds_by_date.get(gdate, [])
        odds_row = next((o for o in day_odds
                         if o["home_team"] == home and o["away_team"] == away), None)

        new_rows.append(build_row(spine, bx, pp, game_enrich, mp_h_row, mp_a_row, odds_row))
        time.sleep(0.05)

    if skipped:
        print(f"[nhl_refresh] Skipped {skipped} incomplete (in-progress) game(s)", flush=True)

    if not new_rows:
        print(f"[nhl_refresh] Added 0 new games. "
              f"{existing_this_season} games already current.", flush=True)
        return

    # ── Audit ─────────────────────────────────────────────────────────────────
    audit_ok = audit_new_rows(new_rows)

    if not audit_ok:
        print("[nhl_refresh] Audit failed — aborting write.", flush=True)
        sys.exit(1)

    if args.dry_run:
        mkt = sum(1 for r in new_rows if r.get("market_available"))
        mp  = sum(1 for r in new_rows if r.get("moneypuck_available"))
        n   = len(new_rows)
        print(f"[nhl_refresh] --dry-run: would add {n} rows  "
              f"odds={mkt}/{n}  moneypuck={mp}/{n}", flush=True)
        return

    # ── Append to canonical CSV ───────────────────────────────────────────────
    with open(CANONICAL, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        for row in new_rows:
            writer.writerow(row)

    mkt = sum(1 for r in new_rows if r.get("market_available"))
    mp  = sum(1 for r in new_rows if r.get("moneypuck_available"))
    n   = len(new_rows)

    print(
        f"[nhl_refresh] Added {n} new games. "
        f"{existing_this_season} games already current.  "
        f"odds={mkt}/{n}  moneypuck={mp}/{n}",
        flush=True,
    )

    # ── Incremental feature table append ──────────────────────────────────────
    append_feature_rows(new_rows)

    print("[nhl_refresh] Done.", flush=True)


if __name__ == "__main__":
    main()
