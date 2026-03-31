#!/usr/bin/env python3
"""
Phase V2 Backfill — API-Football data pull.

Steps:
  1. crosswalk — map canonical game_ids → API-Football fixture_ids
  2. lineups   — pull starting XI for each matched fixture
  3. odds      — pull 1.5 / 2.5 / 3.5 over/under for each matched fixture
  4. audit     — coverage report by league/season

Usage:
    python3 -m soccer.phase_v2_backfill --step crosswalk
    python3 -m soccer.phase_v2_backfill --step lineups
    python3 -m soccer.phase_v2_backfill --step odds
    python3 -m soccer.phase_v2_backfill --step audit
    python3 -m soccer.phase_v2_backfill --step all
"""

import argparse
import json
import logging
import os
import sys
import time
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import pandas as pd
import requests

from soccer.config import CANONICAL_PATH, DATA_DIR, SEASON_LABELS

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

CACHE_DIR      = os.path.join(DATA_DIR, "cache", "api_football")
CROSSWALK_PATH = os.path.join(DATA_DIR, "api_football_crosswalk.parquet")
LINEUPS_PATH   = os.path.join(DATA_DIR, "lineups_raw.parquet")
ODDS_PATH      = os.path.join(DATA_DIR, "odds_raw.parquet")

os.makedirs(CACHE_DIR, exist_ok=True)

# ── API constants ─────────────────────────────────────────────────────────────

BASE_URL       = "https://v3.football.api-sports.io"
REQUEST_DELAY  = 0.5           # seconds between calls (2 req/sec, safe for 75k quota)
DAILY_CALL_CAP = 70_000        # stop at 70k to leave buffer on 75k quota

API_LEAGUE_IDS = {"EPL": 39, "BUN": 78}

# fd_season code → API-Football season year (season start year)
def fd_season_to_api_year(fd_season: str) -> int:
    return 2000 + int(fd_season[:2])

# Reverse: season_year label → season start year
_LABEL_TO_YEAR = {v: fd_season_to_api_year(k) for k, v in SEASON_LABELS.items()}

SEP  = "═" * 72
SEP2 = "─" * 72

# ── .env reader ───────────────────────────────────────────────────────────────

def read_api_key() -> str:
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env_path):
        raise FileNotFoundError(f".env not found at {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("API_FOOTBALL_KEY="):
                return line.split("=", 1)[1].strip()
    raise ValueError("API_FOOTBALL_KEY not found in .env")


# ── API client ────────────────────────────────────────────────────────────────

class APIFootballClient:
    """
    Thin client for API-Football v3.
    - Caches every response to CACHE_DIR/{endpoint_slug}_{params_hash}.json
    - Enforces REQUEST_DELAY between live calls
    - Tracks call count; raises StopIteration when DAILY_CALL_CAP reached
    """

    def __init__(self, api_key: str):
        self.api_key   = api_key
        self.session   = requests.Session()
        self.session.headers.update({
            "x-apisports-key": api_key,
            "Accept": "application/json",
        })
        self.calls_this_session = 0
        self.quota_remaining    = None

    def _cache_path(self, endpoint: str, params: dict) -> str:
        slug   = endpoint.strip("/").replace("/", "_")
        params_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
        return os.path.join(CACHE_DIR, f"{slug}_{params_str}.json")

    def get(self, endpoint: str, params: dict, force_refresh: bool = False) -> dict:
        cache = self._cache_path(endpoint, params)

        if not force_refresh and os.path.exists(cache):
            with open(cache) as f:
                return json.load(f)

        if self.calls_this_session >= DAILY_CALL_CAP:
            logger.warning(f"Daily call cap ({DAILY_CALL_CAP}) reached — stopping.")
            raise StopIteration("Daily API call cap reached")

        url = f"{BASE_URL}/{endpoint.lstrip('/')}"

        # Retry up to 3 times on transient server errors (5xx, 429)
        last_exc = None
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=20)
                if resp.status_code in (429, 503, 502, 504):
                    wait = 10 * (attempt + 1)
                    logger.warning(f"HTTP {resp.status_code} on attempt {attempt+1} "
                                   f"for {endpoint} {params} — retrying in {wait}s")
                    time.sleep(wait)
                    last_exc = requests.exceptions.HTTPError(
                        f"{resp.status_code}", response=resp
                    )
                    continue
                resp.raise_for_status()
                break
            except requests.exceptions.ConnectionError as e:
                wait = 10 * (attempt + 1)
                logger.warning(f"ConnectionError attempt {attempt+1}: {e} — retrying in {wait}s")
                time.sleep(wait)
                last_exc = e
        else:
            # All retries exhausted — log and return empty response (don't crash)
            logger.error(f"All retries failed for {endpoint} {params}: {last_exc}")
            return {"response": [], "errors": [str(last_exc)], "results": 0}

        self.calls_this_session += 1
        remaining = resp.headers.get("x-ratelimit-requests-remaining")
        if remaining is not None:
            self.quota_remaining = int(remaining)

        data = resp.json()
        with open(cache, "w") as f:
            json.dump(data, f)

        time.sleep(REQUEST_DELAY)
        return data

    def status(self) -> str:
        q = f"{self.quota_remaining} remaining" if self.quota_remaining is not None else "unknown"
        return f"calls_this_session={self.calls_this_session}  quota={q}"


# ── Team name normalisation for fuzzy matching ────────────────────────────────

_STRIP_WORDS = {"fc", "afc", "sc", "cf", "ac", "as", "ss", "bsc", "1.", "sv",
                "fk", "sk", "nk", "rk", "hfc", "vfb", "vfl", "rb"}

def _normalise(name: str) -> str:
    import re
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    words = [w for w in name.split() if w not in _STRIP_WORDS]
    return " ".join(words).strip()


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()


def _best_name_match(our_name: str, candidates: list[str], threshold: float = 0.70) -> str | None:
    best_ratio, best_name = 0.0, None
    for c in candidates:
        r = _name_similarity(our_name, c)
        if r > best_ratio:
            best_ratio, best_name = r, c
    return best_name if best_ratio >= threshold else None


# ── STEP 1: Crosswalk ─────────────────────────────────────────────────────────

def build_crosswalk(client: APIFootballClient) -> pd.DataFrame:
    """
    For each (league_id, season_year) combo, fetch all API-Football fixtures
    in one call, then match to canonical games by (date, score) primary and
    (team name) secondary.

    Returns crosswalk DataFrame:
        game_id, fixture_id, match_method, api_home_team, api_away_team
    """
    canonical = pd.read_parquet(CANONICAL_PATH)
    logger.info(f"Canonical: {len(canonical):,} rows")

    combos = canonical.groupby(["league_id", "season_year"]).size().reset_index()
    logger.info(f"League×season combos: {len(combos)}")

    rows = []

    for _, combo_row in combos.iterrows():
        lid      = combo_row["league_id"]
        sy_label = combo_row["season_year"]   # e.g. "2023-24"
        api_lid  = API_LEAGUE_IDS[lid]
        api_year = _LABEL_TO_YEAR.get(sy_label)
        if api_year is None:
            logger.warning(f"No API year mapping for {sy_label}")
            continue

        logger.info(f"Fetching fixtures: {lid} {sy_label} (API league={api_lid} season={api_year})")

        try:
            data = client.get("/fixtures", {"league": api_lid, "season": api_year})
        except StopIteration:
            logger.warning("Call cap hit during crosswalk — saving partial results")
            break

        fixtures = data.get("response", [])
        logger.info(f"  → {len(fixtures)} API fixtures returned  [{client.status()}]")

        # Build lookup: (date_str, home_goals, away_goals) → fixture record
        score_lookup: dict[tuple, list] = {}
        for fx in fixtures:
            status = fx.get("fixture", {}).get("status", {}).get("short", "")
            if status not in ("FT", "AET", "PEN"):
                continue   # skip unfinished / cancelled
            date_str  = fx["fixture"]["date"][:10]
            gh        = fx["goals"].get("home")
            ga        = fx["goals"].get("away")
            if gh is None or ga is None:
                continue
            key = (date_str, int(gh), int(ga))
            score_lookup.setdefault(key, []).append(fx)

        # Also build name lookup: (date_str) → list of fixtures
        date_lookup: dict[str, list] = {}
        for fx in fixtures:
            d = fx["fixture"]["date"][:10]
            date_lookup.setdefault(d, []).append(fx)

        # Match canonical games in this league-season
        sub = canonical[(canonical["league_id"] == lid) & (canonical["season_year"] == sy_label)]

        for _, game in sub.iterrows():
            gid   = game["game_id"]
            gdate = str(game["game_date"])[:10]
            gh    = int(game["home_score"])
            ga    = int(game["away_score"])

            # Primary: score match
            candidates = score_lookup.get((gdate, gh, ga), [])
            matched_fx = None
            method     = "unmatched"

            if len(candidates) == 1:
                matched_fx = candidates[0]
                method = "score_match"
            elif len(candidates) > 1:
                # Multiple games with same score on same date (rare) — use name match
                our_home = game["home_team"]
                our_away = game["away_team"]
                for fx in candidates:
                    api_home = fx["teams"]["home"]["name"]
                    api_away = fx["teams"]["away"]["name"]
                    if (_name_similarity(our_home, api_home) >= 0.65 and
                            _name_similarity(our_away, api_away) >= 0.65):
                        matched_fx = fx
                        method = "score+name_match"
                        break
                if matched_fx is None and candidates:
                    matched_fx = candidates[0]
                    method = "score_match_ambiguous"

            # Fallback: name match on same date
            if matched_fx is None:
                day_fixtures = date_lookup.get(gdate, [])
                our_home = game["home_team"]
                our_away = game["away_team"]
                best_score = 0.0
                for fx in day_fixtures:
                    api_home = fx["teams"]["home"]["name"]
                    api_away = fx["teams"]["away"]["name"]
                    s = (_name_similarity(our_home, api_home) +
                         _name_similarity(our_away, api_away)) / 2.0
                    if s > best_score:
                        best_score, matched_fx = s, fx
                if matched_fx is not None and best_score >= 0.70:
                    method = f"name_match_{best_score:.2f}"
                else:
                    matched_fx = None
                    method = "unmatched"

            if matched_fx is not None:
                rows.append({
                    "game_id":       gid,
                    "fixture_id":    matched_fx["fixture"]["id"],
                    "match_method":  method,
                    "api_home_team": matched_fx["teams"]["home"]["name"],
                    "api_away_team": matched_fx["teams"]["away"]["name"],
                    "league_id":     lid,
                    "season_year":   sy_label,
                })
            else:
                rows.append({
                    "game_id":       gid,
                    "fixture_id":    None,
                    "match_method":  "unmatched",
                    "api_home_team": None,
                    "api_away_team": None,
                    "league_id":     lid,
                    "season_year":   sy_label,
                })

    cw = pd.DataFrame(rows)
    cw.to_parquet(CROSSWALK_PATH, index=False)
    logger.info(f"Crosswalk saved: {len(cw):,} rows → {CROSSWALK_PATH}")

    # ── Coverage report ───────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  CROSSWALK RESULTS")
    print(SEP)
    n_total   = len(cw)
    n_matched = cw["fixture_id"].notna().sum()
    rate      = n_matched / n_total if n_total else 0
    print(f"\n  Total canonical games:  {n_total:,}")
    print(f"  Matched to API-Football: {n_matched:,}  ({rate:.1%})")
    print()
    print(f"  {'Method':<30} {'N':>6}")
    print(f"  {SEP2[:40]}")
    for method, cnt in cw["match_method"].value_counts().items():
        print(f"  {method:<30} {cnt:>6}")

    print(f"\n  By league × season:")
    print(f"  {SEP2[:60]}")
    print(f"  {'League':<8} {'Season':<12} {'Total':>6} {'Matched':>8} {'Rate':>8}")
    print(f"  {SEP2[:46]}")
    for (lid, sy), grp in cw.groupby(["league_id", "season_year"]):
        n   = len(grp)
        nm  = grp["fixture_id"].notna().sum()
        r   = nm / n if n else 0
        ok  = "✓" if r >= 0.90 else "✗"
        print(f"  {ok} {lid:<8} {sy:<12} {n:>6} {nm:>8} {r:>7.1%}")

    print()
    if rate < 0.90:
        print(f"  ⚠  BELOW 90% MATCH RATE — unmatched games:")
        unmatched = cw[cw["fixture_id"].isna()][
            ["game_id", "league_id", "season_year"]
        ]
        print(unmatched.to_string(index=False))
    else:
        print(f"  ✓ Match rate {rate:.1%} ≥ 90% — proceeding with lineups/odds pull")
    print()

    return cw


# ── STEP 2: Lineups ───────────────────────────────────────────────────────────

def pull_lineups(client: APIFootballClient) -> pd.DataFrame:
    """
    For each matched fixture_id, pull /fixtures/lineups and extract starting XI.
    Returns lineups_raw DataFrame.
    """
    if not os.path.exists(CROSSWALK_PATH):
        raise FileNotFoundError("Crosswalk not found — run --step crosswalk first")

    cw = pd.read_parquet(CROSSWALK_PATH)
    matched = cw[cw["fixture_id"].notna()].copy()
    matched["fixture_id"] = matched["fixture_id"].astype(int)
    logger.info(f"Pulling lineups for {len(matched):,} matched fixtures")

    # Load existing lineups to resume
    if os.path.exists(LINEUPS_PATH):
        existing = pd.read_parquet(LINEUPS_PATH)
        done_ids = set(existing["fixture_id"].unique())
        logger.info(f"  Resuming — {len(done_ids):,} already done")
    else:
        existing = pd.DataFrame()
        done_ids = set()

    new_rows = []
    n_processed = 0
    n_skipped   = 0
    n_empty     = 0

    for i, (_, row) in enumerate(matched.iterrows()):
        fid    = int(row["fixture_id"])
        gid    = row["game_id"]
        lid    = row["league_id"]
        sy     = row["season_year"]

        if fid in done_ids:
            n_skipped += 1
            continue

        try:
            data = client.get("/fixtures/lineups", {"fixture": fid})
        except StopIteration:
            logger.warning(f"Call cap hit at fixture {fid} — saving partial lineups")
            break

        lineup_data = data.get("response", [])
        n_processed += 1

        if not lineup_data:
            n_empty += 1
        else:
            for team_entry in lineup_data:
                team_name = team_entry.get("team", {}).get("name", "")
                team_id   = team_entry.get("team", {}).get("id")

                # Determine side (home/away) using crosswalk api team names
                api_home = row.get("api_home_team", "")
                if _name_similarity(team_name, str(api_home)) > 0.7:
                    side = "home"
                else:
                    side = "away"

                for player in team_entry.get("startXI", []):
                    p = player.get("player", {})
                    new_rows.append({
                        "game_id":      gid,
                        "fixture_id":   fid,
                        "league_id":    lid,
                        "season_year":  sy,
                        "team_side":    side,
                        "team_name":    team_name,
                        "team_id":      team_id,
                        "player_id":    p.get("id"),
                        "player_name":  p.get("name"),
                        "position":     p.get("pos"),
                        "jersey_number": p.get("number"),
                        "is_starter":   True,
                    })
                for player in team_entry.get("substitutes", []):
                    p = player.get("player", {})
                    new_rows.append({
                        "game_id":      gid,
                        "fixture_id":   fid,
                        "league_id":    lid,
                        "season_year":  sy,
                        "team_side":    side,
                        "team_name":    team_name,
                        "team_id":      team_id,
                        "player_id":    p.get("id"),
                        "player_name":  p.get("name"),
                        "position":     p.get("pos"),
                        "jersey_number": p.get("number"),
                        "is_starter":   False,
                    })

        if n_processed % 100 == 0:
            logger.info(f"  Lineups: {n_processed} processed, {n_skipped} cached, "
                        f"{n_empty} empty  [{client.status()}]")

    # Merge with existing
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if not existing.empty:
            lineups_df = pd.concat([existing, new_df], ignore_index=True)
        else:
            lineups_df = new_df
    else:
        lineups_df = existing

    lineups_df.to_parquet(LINEUPS_PATH, index=False)
    logger.info(f"Lineups saved: {len(lineups_df):,} player rows → {LINEUPS_PATH}")

    starters = lineups_df[lineups_df["is_starter"] == True]
    n_games  = starters["game_id"].nunique()
    print(f"\n  Lineup pull complete:")
    print(f"  Total player rows:  {len(lineups_df):,}")
    print(f"  Games with starters: {n_games:,}")
    print(f"  New fetched:        {n_processed}")
    print(f"  Skipped (cached):   {n_skipped}")
    print(f"  Empty responses:    {n_empty}")
    print()

    return lineups_df


# ── STEP 3: Odds ─────────────────────────────────────────────────────────────

_OVER_UNDER_MARKETS = {
    "Goals Over/Under 1.5",
    "Goals Over/Under 2.5",
    "Goals Over/Under 3.5",
    # API-Football sometimes uses these names:
    "Goals Over/Under",
}

_LINE_FROM_MARKET = {
    "Goals Over/Under 1.5": "1.5",
    "Goals Over/Under 2.5": "2.5",
    "Goals Over/Under 3.5": "3.5",
}


def _parse_odds_response(data: dict, gid: str, fid: int) -> list[dict]:
    """
    Parse /odds response for one fixture.
    Extracts over/under prices for 1.5, 2.5, 3.5 lines.
    Takes closest-to-kickoff snapshot (last in list) and earliest (first).
    Returns list of row dicts.
    """
    rows = []
    response = data.get("response", [])
    if not response:
        return rows

    for entry in response:
        bookmakers = entry.get("bookmakers", [])
        for bm in bookmakers:
            for bet in bm.get("bets", []):
                bet_name = bet.get("name", "")

                # Match known market names
                line = None
                if bet_name in _LINE_FROM_MARKET:
                    line = _LINE_FROM_MARKET[bet_name]
                elif bet_name == "Goals Over/Under":
                    # Values contain the line: "Over 2.5", "Under 2.5"
                    values = bet.get("values", [])
                    for v in values:
                        val_str = v.get("value", "")
                        if val_str.startswith("Over ") or val_str.startswith("Under "):
                            try:
                                parts = val_str.split()
                                line_candidate = parts[1] if len(parts) >= 2 else None
                                if line_candidate in ("1.5", "2.5", "3.5"):
                                    line = line_candidate
                                    break
                            except Exception:
                                pass

                if line is None:
                    continue

                values = bet.get("values", [])
                # Build (value_name → price) dict
                price_map: dict[str, list[str]] = {}
                for v in values:
                    val_str  = v.get("value", "")
                    odd_str  = v.get("odd", "")
                    price_map.setdefault(val_str, []).append(odd_str)

                # Find over/under odds for this line
                over_key  = f"Over {line}"
                under_key = f"Under {line}"

                def _get_price(key: str, idx: int) -> float | None:
                    prices = price_map.get(key, [])
                    if not prices:
                        return None
                    try:
                        return float(prices[idx] if idx < len(prices) else prices[-1])
                    except (ValueError, IndexError):
                        return None

                # Closing (last snapshot = closest to kickoff)
                over_close  = _get_price(over_key,  -1)
                under_close = _get_price(under_key, -1)
                # Opening (first snapshot)
                over_open   = _get_price(over_key,   0)
                under_open  = _get_price(under_key,  0)

                if over_close is None or under_close is None:
                    continue

                rows.append({
                    "game_id":           gid,
                    "fixture_id":        fid,
                    "market":            line,
                    "over_price_decimal":  over_close,
                    "under_price_decimal": under_close,
                    "open_over_price":     over_open,
                    "open_under_price":    under_open,
                    "bookmaker_id":        bm.get("id"),
                    "bookmaker_name":      bm.get("name"),
                })

    return rows


def pull_odds(client: APIFootballClient) -> pd.DataFrame:
    """
    For each matched fixture_id, pull /odds?fixture={id}&bookmaker=6
    and extract 1.5 / 2.5 / 3.5 over/under prices.
    """
    if not os.path.exists(CROSSWALK_PATH):
        raise FileNotFoundError("Crosswalk not found — run --step crosswalk first")

    cw = pd.read_parquet(CROSSWALK_PATH)
    matched = cw[cw["fixture_id"].notna()].copy()
    matched["fixture_id"] = matched["fixture_id"].astype(int)
    logger.info(f"Pulling odds for {len(matched):,} matched fixtures")

    if os.path.exists(ODDS_PATH):
        existing = pd.read_parquet(ODDS_PATH)
        done_ids = set(existing["fixture_id"].unique())
        logger.info(f"  Resuming — {len(done_ids):,} fixture_ids already done")
    else:
        existing = pd.DataFrame()
        done_ids = set()

    new_rows   = []
    n_processed = 0
    n_skipped   = 0
    n_empty     = 0

    for _, row in matched.iterrows():
        fid = int(row["fixture_id"])
        gid = row["game_id"]

        if fid in done_ids:
            n_skipped += 1
            continue

        try:
            data = client.get("/odds", {"fixture": fid, "bookmaker": 6})
        except StopIteration:
            logger.warning(f"Call cap hit at fixture {fid} — saving partial odds")
            break

        parsed = _parse_odds_response(data, gid, fid)
        n_processed += 1

        if not parsed:
            n_empty += 1
        else:
            new_rows.extend(parsed)

        if n_processed % 100 == 0:
            logger.info(f"  Odds: {n_processed} processed, {n_skipped} cached, "
                        f"{n_empty} empty  [{client.status()}]")

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if not existing.empty:
            odds_df = pd.concat([existing, new_df], ignore_index=True)
        else:
            odds_df = new_df
    else:
        odds_df = existing

    if not odds_df.empty:
        odds_df = odds_df.drop_duplicates(subset=["game_id", "fixture_id", "market", "bookmaker_id"])
        odds_df.to_parquet(ODDS_PATH, index=False)

    logger.info(f"Odds saved: {len(odds_df):,} rows → {ODDS_PATH}")
    print(f"\n  Odds pull complete:")
    print(f"  Total rows:        {len(odds_df):,}")
    n_games_25 = odds_df[odds_df["market"] == "2.5"]["game_id"].nunique() if not odds_df.empty else 0
    print(f"  Games with 2.5 line: {n_games_25:,}")
    print(f"  New fetched:        {n_processed}")
    print(f"  Skipped (cached):   {n_skipped}")
    print(f"  Empty responses:    {n_empty}")
    print()

    return odds_df


# ── STEP 4: Audit ─────────────────────────────────────────────────────────────

def run_audit():
    """
    Print coverage report by league / season.
    Hard-stop gates:
      Lineup coverage < 70% overall
      Odds coverage (2.5) < 70% for seasons 2021-22 onward
    """
    print(f"\n{SEP}")
    print("  PHASE V2 BACKFILL AUDIT")
    print(SEP)

    if not os.path.exists(CROSSWALK_PATH):
        print("  ✗ Crosswalk not found")
        return False

    cw = pd.read_parquet(CROSSWALK_PATH)
    n_canonical = len(cw)
    n_matched   = cw["fixture_id"].notna().sum()
    xw_rate     = n_matched / n_canonical if n_canonical else 0

    print(f"\n  Crosswalk:  {n_matched:,} / {n_canonical:,} matched  ({xw_rate:.1%})")

    # Load lineups and odds
    lineups_df = pd.read_parquet(LINEUPS_PATH) if os.path.exists(LINEUPS_PATH) else pd.DataFrame()
    odds_df    = pd.read_parquet(ODDS_PATH)    if os.path.exists(ODDS_PATH)    else pd.DataFrame()

    # Games with at least one starter
    if not lineups_df.empty:
        games_with_lineups = set(lineups_df[lineups_df["is_starter"] == True]["game_id"].unique())
    else:
        games_with_lineups = set()

    # Games with 2.5 odds
    if not odds_df.empty:
        games_with_odds_25 = set(odds_df[odds_df["market"] == "2.5"]["game_id"].unique())
    else:
        games_with_odds_25 = set()

    matched_games = cw[cw["fixture_id"].notna()]["game_id"].tolist()
    n_lu   = sum(1 for g in matched_games if g in games_with_lineups)
    n_od25 = sum(1 for g in matched_games if g in games_with_odds_25)

    lu_rate   = n_lu   / n_matched if n_matched else 0
    od25_rate = n_od25 / n_matched if n_matched else 0

    print(f"  Lineups:    {n_lu:,} / {n_matched:,} matched games ({lu_rate:.1%})")
    print(f"  Odds (2.5): {n_od25:,} / {n_matched:,} matched games ({od25_rate:.1%})")

    # By league × season
    print(f"\n  {SEP2}")
    print(f"  {'League':<8} {'Season':<12} {'Matched':>8} {'Lineups':>8} {'LU%':>6}  {'Odds2.5':>8} {'OD%':>6}")
    print(f"  {SEP2}")

    gate_pass = True
    MODERN_SEASONS = {"2021-22", "2022-23", "2023-24", "2024-25"}

    for (lid, sy), grp in cw.groupby(["league_id", "season_year"]):
        nm     = grp["fixture_id"].notna().sum()
        gids   = grp[grp["fixture_id"].notna()]["game_id"].tolist()
        n_lu_g = sum(1 for g in gids if g in games_with_lineups)
        n_od_g = sum(1 for g in gids if g in games_with_odds_25)
        lu_r   = n_lu_g / nm if nm else 0
        od_r   = n_od_g / nm if nm else 0

        lu_ok = "✓" if lu_r >= 0.70 else "✗"
        od_ok = "✓" if (od_r >= 0.70 or sy not in MODERN_SEASONS) else "✗"
        print(f"  {lid:<8} {sy:<12} {nm:>8} {n_lu_g:>8} {lu_r:>5.1%}  {n_od_g:>8} {od_r:>5.1%}")

        if lu_r < 0.70:
            gate_pass = False
        if od_r < 0.70 and sy in MODERN_SEASONS:
            gate_pass = False

    print(f"  {SEP2}")
    print(f"  {'OVERALL':<8} {'':12} {n_matched:>8} {n_lu:>8} {lu_rate:>5.1%}  {n_od25:>8} {od25_rate:>5.1%}")

    print()
    if lu_rate < 0.70:
        print(f"  ✗ GATE FAIL: Lineup coverage {lu_rate:.1%} < 70%")
        gate_pass = False
    else:
        print(f"  ✓ Lineup coverage {lu_rate:.1%} ≥ 70%")

    if od25_rate < 0.70:
        print(f"  ✗ GATE FAIL: Odds (2.5) coverage {od25_rate:.1%} < 70% overall")
        # Only hard fail if modern seasons are below threshold
        modern_gids  = cw[(cw["fixture_id"].notna()) & (cw["season_year"].isin(MODERN_SEASONS))]["game_id"].tolist()
        n_od_modern  = sum(1 for g in modern_gids if g in games_with_odds_25)
        od_mod_rate  = n_od_modern / len(modern_gids) if modern_gids else 0
        print(f"     Modern seasons (2021-22+): {od_mod_rate:.1%}")
        if od_mod_rate < 0.70:
            gate_pass = False
    else:
        print(f"  ✓ Odds (2.5) coverage {od25_rate:.1%} ≥ 70%")

    print()
    if gate_pass:
        print(f"  ✓ ALL GATES PASSED — ready for feature engineering")
    else:
        print(f"  ✗ ONE OR MORE GATES FAILED — do not proceed to feature engineering")

    print(f"\n  API calls this session: {_client_ref.calls_this_session if _client_ref else 'N/A'}")
    print()
    return gate_pass


# ── Main ──────────────────────────────────────────────────────────────────────

_client_ref = None   # module-level ref so audit can report session calls


def main():
    global _client_ref

    parser = argparse.ArgumentParser(description="Phase V2: API-Football backfill")
    parser.add_argument(
        "--step",
        choices=["crosswalk", "lineups", "odds", "audit", "all"],
        default="audit",
        help="Which step to run",
    )
    args = parser.parse_args()

    api_key = read_api_key()
    client  = APIFootballClient(api_key)
    _client_ref = client

    print(f"\n{SEP}")
    print("  PHASE V2 BACKFILL — API-Football")
    print(SEP)
    print(f"  Step: {args.step}")
    print(f"  Daily cap: {DAILY_CALL_CAP:,} calls")
    print()

    try:
        if args.step in ("crosswalk", "all"):
            build_crosswalk(client)
            print(f"  [{client.status()}]")

        if args.step in ("lineups", "all"):
            pull_lineups(client)
            print(f"  [{client.status()}]")

        if args.step in ("odds", "all"):
            pull_odds(client)
            print(f"  [{client.status()}]")

        if args.step in ("audit", "all"):
            run_audit()

    except StopIteration:
        print(f"\n  ⚠  Daily call cap reached. Resume tomorrow with same --step.")
        print(f"  All cached responses preserved — no re-fetching needed.")
        run_audit()
        sys.exit(0)

    print(f"  Total API calls this session: {client.calls_this_session}")
    if client.quota_remaining is not None:
        print(f"  Quota remaining: {client.quota_remaining:,}")
    print()


if __name__ == "__main__":
    main()
