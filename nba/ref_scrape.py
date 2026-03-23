#!/usr/bin/env python3
"""
NBA Referee Crew Scraper — Board 5.

Primary source: official.nba.com/referee-assignments (posted ~9am ET daily)
Fallback: NBA Stats API BoxScoreSummaryV2 (available closer to tip-off)

Classifies each game by crew_high_count (number of top-quartile scoring refs)
and writes results to nba/data/nba_ref_assignments.csv.

Schedule:
    9:30 AM — primary scrape (com.mlbmodel.nba.refs.morning)
    6:30 PM — backup/refresh (com.mlbmodel.nba.refs.evening)

Usage:
    python nba/ref_scrape.py                # today
    python nba/ref_scrape.py 2026-03-23     # specific date
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

NBA_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(NBA_DIR, "data", "nba_ref_assignments.csv")

# ── Top-quartile referee list ─────────────────────────────────────────────────
# From research/ref_crew_aggregates.csv: refs with >= 30 prior games whose
# avg_total_points_per_game is in the top 25%.
# Threshold: >= 230.4 pts avg (computed from 2022-25 historical data).
# This list is static for the 2025-26 season and updated between seasons.

TOP_QUARTILE_REFS = {
    "Bill Kennedy",
    "CJ Washington",
    "Jason Goldenberg",
    "JD Ralls",
    "Lauren Holtkamp",
    "Mark Lindsay",
    "Matt Kallio",
    "Matt Myers",
    "Mitchell Ervin",
    "Phenizee Ransom",
    "Robert Hussey",
    "Scott Foster",
    "Scott Twardoski",
    "Sean Corbin",
    "Sean Wright",
    "Sha'Rae Mitchell",
    "Simone Jelks",
    "Tony Brothers",
    "Zach Zarba",
}

# ── Team name mapping (official.nba.com → 3-letter abbreviation) ──────────────
_TEAM_NAME_TO_ABB = {
    "Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "Charlotte": "CHA",
    "Chicago": "CHI", "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN",
    "Detroit": "DET", "Golden State": "GSW", "Houston": "HOU", "Indiana": "IND",
    "L.A. Clippers": "LAC", "LA Clippers": "LAC", "L.A. Lakers": "LAL",
    "LA Lakers": "LAL", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis": "MEM", "Miami": "MIA", "Milwaukee": "MIL", "Minnesota": "MIN",
    "New Orleans": "NOP", "New York": "NYK", "Oklahoma City": "OKC",
    "Orlando": "ORL", "Philadelphia": "PHI", "Phoenix": "PHX", "Portland": "POR",
    "Sacramento": "SAC", "San Antonio": "SAS", "Toronto": "TOR", "Utah": "UTA",
    "Washington": "WAS",
}


def _parse_ref_name(cell_text: str) -> str | None:
    """Extract referee name from table cell text like 'Scott Foster (#48)'."""
    text = cell_text.strip()
    if not text:
        return None
    # Remove jersey number: "Scott Foster (#48)" → "Scott Foster"
    name = re.sub(r"\s*\(#\d+\)\s*", "", text).strip()
    return name if name else None


def _match_team(name_str: str) -> str | None:
    """Match a team city/name string to abbreviation."""
    name_str = name_str.strip()
    for city, abb in _TEAM_NAME_TO_ABB.items():
        if city in name_str:
            return abb
    return None


# ── Primary source: official.nba.com ──────────────────────────────────────────

def _scrape_official_nba() -> list[dict]:
    """
    Scrape today's referee assignments from official.nba.com/referee-assignments.
    Returns list of dicts: {away, home, crew_chief, referee, umpire}.
    """
    url = "https://official.nba.com/referee-assignments/"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"official.nba.com fetch failed: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Find the NBA refs table (not G League)
    nba_div = soup.find("div", class_="nba-refs-content")
    if not nba_div:
        logger.warning("Could not find nba-refs-content div")
        return []

    table = nba_div.find("table")
    if not table:
        logger.warning("Could not find table in nba-refs-content")
        return []

    tbody = table.find("tbody")
    if not tbody:
        logger.warning("Could not find tbody")
        return []

    games = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        matchup = cells[0].get_text(strip=True)  # e.g. "Memphis @ Atlanta"
        crew_chief = _parse_ref_name(cells[1].get_text())
        referee = _parse_ref_name(cells[2].get_text())
        umpire = _parse_ref_name(cells[3].get_text())

        # Parse away @ home
        parts = re.split(r"\s*@\s*", matchup, maxsplit=1)
        if len(parts) != 2:
            logger.warning(f"Could not parse matchup: '{matchup}'")
            continue

        away_abb = _match_team(parts[0])
        home_abb = _match_team(parts[1])
        if not away_abb or not home_abb:
            logger.warning(f"Could not match teams: '{parts[0]}' @ '{parts[1]}'")
            continue

        games.append({
            "away": away_abb,
            "home": home_abb,
            "crew_chief": crew_chief,
            "referee": referee,
            "umpire": umpire,
        })

    return games


# ── Fallback: NBA Stats API ──────────────────────────────────────────────────

def _fetch_api_refs(game_id: str) -> list[str]:
    """Fetch referee names for a single game via BoxScoreSummaryV2. Returns list of names."""
    try:
        from nba.modules.fetch_games import _call_with_retry
        from nba_api.stats.endpoints import BoxScoreSummaryV2

        bs = _call_with_retry(BoxScoreSummaryV2, game_id=game_id, timeout=15)
        dfs = bs.get_data_frames()
        if len(dfs) > 2 and len(dfs[2]) > 0:
            refs = []
            for _, row in dfs[2].iterrows():
                first = row.get("FIRST_NAME", "")
                last = row.get("LAST_NAME", "")
                if first and last:
                    refs.append(f"{first} {last}")
            return refs
    except Exception as e:
        logger.debug(f"API fallback failed for {game_id}: {e}")
    return []


# ── Main logic ────────────────────────────────────────────────────────────────

def fetch_ref_assignments(game_date: str) -> list[dict]:
    """Fetch referee assignments for all games on game_date."""
    from nba.modules.fetch_nba_schedule import fetch_today_schedule

    schedule = fetch_today_schedule(game_date)
    if not schedule:
        logger.warning(f"No NBA games scheduled for {game_date}")
        return []

    logger.info(f"Fetching referee data for {len(schedule)} games on {game_date}")

    # Try primary source first
    nba_official = _scrape_official_nba()
    official_lookup = {}
    for g in nba_official:
        key = (g["away"], g["home"])
        official_lookup[key] = g

    # Also build unordered lookup (team pair → ref data)
    # Website away/home may not match schedule away/home exactly
    pair_lookup = {}
    for g in nba_official:
        pair_key = tuple(sorted([g["away"], g["home"]]))
        pair_lookup[pair_key] = g

    if nba_official:
        logger.info(f"  official.nba.com: {len(nba_official)} games parsed")
    else:
        logger.warning("  official.nba.com: no data — falling back to NBA Stats API")

    results = []
    for sched in schedule:
        gid = sched["game_id"]
        home = sched["home_team"]
        away = sched["away_team"]

        # Try official.nba.com — exact match first, then unordered pair
        official = official_lookup.get((away, home))
        if not official:
            official = pair_lookup.get(tuple(sorted([away, home])))
        if official:
            all_refs = [official["crew_chief"], official["referee"], official["umpire"]]
            all_refs = [r for r in all_refs if r]
            source = "official.nba.com"
        else:
            # Fallback to API
            all_refs = _fetch_api_refs(gid)
            source = "nba_api" if all_refs else "none"
            if not all_refs:
                logger.warning(f"  No ref data for {away}@{home} from either source")
            time.sleep(0.7)

        # Sort alphabetically, pad to 3
        all_refs = sorted(all_refs)[:3]
        while len(all_refs) < 3:
            all_refs.append(None)

        # Classify
        if all_refs[0] is None:
            crew_high = None
            ref_signal = "UNKNOWN"
        else:
            crew_high = sum(1 for r in all_refs if r and r in TOP_QUARTILE_REFS)
            if crew_high >= 2:
                ref_signal = "REF_OVER"
            elif crew_high == 0:
                ref_signal = "REF_UNDER"
            else:
                ref_signal = "NONE"

        results.append({
            "game_id": gid,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "ref_1": all_refs[0],
            "ref_2": all_refs[1],
            "ref_3": all_refs[2],
            "crew_high_count": crew_high,
            "crew_high_exact": crew_high,
            "ref_signal": ref_signal,
        })

        ch_str = f"✓ {crew_high} high" if crew_high is not None else "? unknown"
        logger.info(f"  {away}@{home} [{source}] — {all_refs[0] or '?'}, {all_refs[1] or '?'}, {all_refs[2] or '?'} → {ch_str}")

    return results


def run(game_date: str = None) -> str:
    """Main entry point. Returns path to output CSV."""
    if game_date is None:
        game_date = date.today().isoformat()

    results = fetch_ref_assignments(game_date)

    if not results:
        logger.info(f"No games to process for {game_date}")
        return OUT_PATH

    # Write CSV (overwrite — one day at a time)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "game_id", "game_date", "home_team", "away_team",
            "ref_1", "ref_2", "ref_3",
            "crew_high_count", "crew_high_exact", "ref_signal",
        ])
        writer.writeheader()
        writer.writerows(results)

    # Summary
    n_with = sum(1 for r in results if r["ref_signal"] != "UNKNOWN")
    n_missing = sum(1 for r in results if r["ref_signal"] == "UNKNOWN")
    over = [r for r in results if r["ref_signal"] == "REF_OVER"]
    under = [r for r in results if r["ref_signal"] == "REF_UNDER"]

    print(f"\n[ref_scrape] {game_date} — {len(results)} games")
    print(f"  Ref data available: {n_with}")
    print(f"  Ref data missing:   {n_missing}")
    print(f"  REF_OVER signals:   {len(over)}", end="")
    if over:
        print(f" — {', '.join(r['game_id'] for r in over)}")
    else:
        print()
    print(f"  REF_UNDER signals:  {len(under)}", end="")
    if under:
        print(f" — {', '.join(r['game_id'] for r in under)}")
    else:
        print()
    print(f"  Output: {OUT_PATH}")

    return OUT_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA Referee Crew Scraper")
    parser.add_argument("date", nargs="?", default=None, help="Game date (YYYY-MM-DD)")
    args = parser.parse_args()
    run(args.date)
