#!/usr/bin/env python3
"""NHL outcomes loader: finals and player stats from api-web.nhle.com boxscores.

Cache to nhl/cache/boxscore_<id>.json ONLY when gameState is OFF/FINAL.
Team map built from the API's own placeName + commonName.
Match = unordered team pair + nearest start within 12 h (N41 lesson).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "nhl" / "cache"

# Odds API full name -> NHL API abbreviation, built from boxscore placeName + commonName.
# "St Louis Blues" (Odds API, no period) vs "St. Louis Blues" (NHL API, with period).
# "Montréal Canadiens" (accent) matches in both.
_ODDS_TO_NHL = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR", "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL", "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM", "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN",
    "Montréal Canadiens": "MTL", "Montreal Canadiens": "MTL",
    "Nashville Predators": "NSH", "New Jersey Devils": "NJD",
    "New York Islanders": "NYI", "New York Rangers": "NYR",
    "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St Louis Blues": "STL", "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR",
    "Utah Mammoth": "UTA", "Utah Hockey Club": "UTA",
    "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH", "Winnipeg Jets": "WPG",
}


def odds_to_nhl(name):
    """Map Odds API full team name to NHL abbreviation. Raises on unmapped."""
    abbr = _ODDS_TO_NHL.get(name)
    if abbr is None:
        raise SystemExit(f"HALT: unmapped NHL team name '{name}' — add to _ODDS_TO_NHL")
    return abbr


def load_boxscore(game_id):
    """Load a cached boxscore. Returns None if not cached."""
    p = CACHE_DIR / f"boxscore_{game_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def game_result(box):
    """Extract final score, OT/SO flags from a boxscore dict.
    Returns dict with home_abbr, away_abbr, home_score, away_score, went_to_ot, went_to_so,
    home_goals_reg, away_goals_reg, game_date, start_utc, game_id.
    """
    state = box.get("gameState", "")
    if state not in ("OFF", "FINAL"):
        return None
    home = box["homeTeam"]
    away = box["awayTeam"]
    outcome = box.get("gameOutcome", {})
    last_period = outcome.get("lastPeriodType", "REG")
    went_to_ot = last_period in ("OT", "SO")
    went_to_so = last_period == "SO"
    home_score = int(home["score"])
    away_score = int(away["score"])
    # Regulation scores: for SO games, the loser's score is one less than final
    # (the SO winner got +1). For OT, final includes OT goal.
    # We derive reg scores from summary periods if available, else approximate.
    home_reg = home_score
    away_reg = away_score
    if went_to_so:
        # The winner's score includes the SO +1; regulation was tied
        if home_score > away_score:
            home_reg = home_score - 1
        else:
            away_reg = away_score - 1
    elif went_to_ot:
        # OT: the winner scored in OT; regulation was tied
        if home_score > away_score:
            home_reg = home_score - 1
        else:
            away_reg = away_score - 1
    return {
        "game_id": box["id"],
        "home_abbr": home["abbrev"],
        "away_abbr": away["abbrev"],
        "home_score": home_score,
        "away_score": away_score,
        "home_goals_reg": home_reg,
        "away_goals_reg": away_reg,
        "went_to_ot": went_to_ot,
        "went_to_so": went_to_so,
        "game_date": box.get("gameDate", ""),
        "start_utc": box.get("startTimeUTC", ""),
    }


def settle_game_markets(result, market_key, line):
    """Settle h2h, spreads, totals using the final score (OT+SO included).
    Returns 1 if first side won, 0 if second side, None for push."""
    h, a = result["home_score"], result["away_score"]
    if market_key == "h2h":
        if h > a:
            return 1
        elif h < a:
            return 0
        return None  # tie (shouldn't happen with OT/SO)
    elif market_key == "spreads":
        m = h + float(line) - a
        if m == 0:
            return None
        return int(m > 0)
    elif market_key == "totals":
        t = h + a
        if t == float(line):
            return None
        return int(t > float(line))
    return None


def player_stats(box, side="homeTeam"):
    """Extract skater and goalie stats from boxscore.
    Shootout excluded by construction (boxscore stats don't count SO).
    Returns list of dicts with playerId, name, position, and stat fields."""
    stats = box.get("playerByGameStats", {}).get(side, {})
    players = []
    for pos in ("forwards", "defense"):
        for p in stats.get(pos, []):
            players.append({
                "playerId": p["playerId"],
                "name": p["name"].get("default", ""),
                "position": p["position"],
                "goals": p.get("goals", 0),
                "assists": p.get("assists", 0),
                "points": p.get("points", 0),
                "sog": p.get("sog", 0),
                "blockedShots": p.get("blockedShots", 0),
                "powerPlayGoals": p.get("powerPlayGoals", 0),
            })
    for p in stats.get("goalies", []):
        players.append({
            "playerId": p["playerId"],
            "name": p["name"].get("default", ""),
            "position": "G",
            "saves": p.get("saves", 0),
            "starter": p.get("starter", False),
        })
    return players


def match_game(home_odds, away_odds, commence_time, cached_results):
    """Match an Odds API event to a cached boxscore result.
    Match = unordered team pair + nearest start within 12 h."""
    h = odds_to_nhl(home_odds)
    a = odds_to_nhl(away_odds)
    pair = frozenset((h, a))
    ct = parse_utc(commence_time)
    best = None
    best_dt = 12 * 3600 + 1
    for r in cached_results:
        rp = frozenset((r["home_abbr"], r["away_abbr"]))
        if rp != pair:
            continue
        try:
            rt = parse_utc(r["start_utc"])
        except Exception:
            continue
        dt = abs((rt - ct).total_seconds())
        if dt < best_dt:
            best_dt = dt
            best = r
    return best


def load_all_results(season_year=2025):
    """Load all cached boxscore results for a season.
    season_year = start year of the season (2025 = 2025-26)."""
    results = []
    for p in sorted(CACHE_DIR.glob("boxscore_*.json")):
        gid_str = p.stem.replace("boxscore_", "")
        # Filter by season: game IDs are like 2025020001 where first 4 digits = season
        if not gid_str.startswith(str(season_year)):
            continue
        # Regular season only: game type 02
        if len(gid_str) >= 8 and gid_str[4:6] != "02":
            continue
        box = json.loads(p.read_text())
        r = game_result(box)
        if r:
            results.append(r)
    return results


def agreement_check(season_year=2025):
    """Check loader results against nhl_games_canonical.csv.
    Returns (n_checked, mismatches) where mismatches is a list of dicts."""
    import pandas as pd
    canonical = pd.read_csv(ROOT / "nhl" / "nhl_games_canonical.csv")
    canon = canonical[canonical["season_year"] == season_year].copy()
    results = load_all_results(season_year)
    result_map = {r["game_id"]: r for r in results}
    mismatches = []
    n_checked = 0
    for _, row in canon.iterrows():
        gid = row["game_id"]
        r = result_map.get(gid)
        if r is None:
            mismatches.append({"game_id": gid, "issue": "not in cache"})
            continue
        n_checked += 1
        issues = []
        if r["home_score"] != row["home_score"]:
            issues.append(f"home_score: loader={r['home_score']} canon={row['home_score']}")
        if r["away_score"] != row["away_score"]:
            issues.append(f"away_score: loader={r['away_score']} canon={row['away_score']}")
        if r["went_to_ot"] != bool(row["went_to_ot"]):
            issues.append(f"went_to_ot: loader={r['went_to_ot']} canon={row['went_to_ot']}")
        if r["went_to_so"] != bool(row["went_to_so"]):
            issues.append(f"went_to_so: loader={r['went_to_so']} canon={row['went_to_so']}")
        if issues:
            mismatches.append({"game_id": gid, "issue": "; ".join(issues)})
    return n_checked, mismatches
