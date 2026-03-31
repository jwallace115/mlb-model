"""
football-data.co.uk fetcher — Phase 1.

Downloads historical and current-season CSV files for EPL and Bundesliga.
Parses into a standardised DataFrame with the canonical schema columns
that are available from this source.

Columns extracted:
  - game_date, home_team, away_team
  - home_score (FTHG), away_score (FTAG)
  - home_shots (HS), away_shots (AS)
  - home_shots_on_target (HST), away_shots_on_target (AST)
  - closing_total_line → derived from B365>2.5 / B365<2.5 (see note below)
  - over_price  (B365>2.5)
  - under_price (B365<2.5)

Note on closing_total_line:
  football-data.co.uk provides B365 over/under prices for the 2.5 goals line
  only — not a floating line. We record closing_total_line = 2.5 when
  B365>2.5 and B365<2.5 are both present, and set market_available = True.
  This is sufficient for Phase 1 audit and Phase 2 ROI back-testing against
  a fixed 2.5-goal market.

xG fields (home_xg_raw, away_xg_raw, xg_source):
  Not available from football-data.co.uk. All three fields are set to None/NaN.
  xG_source = None is documented as PENDING in audit gate 4.

went_to_et / went_to_penalties:
  Not tracked for EPL/BUN regular-season league matches (no knockout ET).
  Both fields are set to False.

official_bet_total:
  For EPL and BUN regular-season matches, equal to regulation_total_90
  (no overtime scoring affects the bet total).
"""

import io
import logging
import os
import time

import pandas as pd
import requests

from soccer.config import (
    CACHE_DIR,
    FD_BASE_URL,
    LEAGUES,
    SEASON_LABELS,
)

logger = logging.getLogger(__name__)

# Request headers that football-data.co.uk accepts
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

_REQUEST_DELAY = 1.2   # seconds between requests (polite crawling)


def _cache_path(league_id: str, season: str) -> str:
    return os.path.join(CACHE_DIR, f"fd_{league_id}_{season}.csv")


def _fetch_csv(league_id: str, season: str, force_refresh: bool = False) -> str | None:
    """
    Fetch raw CSV text for one league + season.
    Returns raw CSV string or None on failure.
    Caches to disk.
    """
    cache = _cache_path(league_id, season)
    if not force_refresh and os.path.exists(cache):
        with open(cache, encoding="utf-8", errors="replace") as f:
            logger.debug(f"Loaded from cache: {league_id} {season}")
            return f.read()

    fd_code = LEAGUES[league_id]["fd_code"]
    url = FD_BASE_URL.format(season=season, code=fd_code)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        text = resp.content.decode("utf-8", errors="replace")
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Fetched {league_id} {season}: {len(text):,} chars → {cache}")
        time.sleep(_REQUEST_DELAY)
        return text
    except requests.HTTPError as e:
        logger.warning(f"HTTP error fetching {league_id} {season}: {e}")
    except Exception as e:
        logger.warning(f"Failed fetching {league_id} {season}: {e}")
    return None


def _parse_csv(text: str, league_id: str, season: str) -> pd.DataFrame:
    """
    Parse raw CSV text into a standardised DataFrame.
    Returns empty DataFrame on parse failure.
    """
    try:
        df = pd.read_csv(io.StringIO(text), encoding_errors="replace")
    except Exception as e:
        logger.warning(f"CSV parse error for {league_id} {season}: {e}")
        return pd.DataFrame()

    # Drop completely empty rows (trailing blank lines common in FD CSVs)
    df = df.dropna(how="all")

    # ── Core columns ──────────────────────────────────────────────────────────
    required = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.warning(f"{league_id} {season}: missing required columns {missing}")
        return pd.DataFrame()

    out = pd.DataFrame()

    # game_date — football-data uses DD/MM/YY or DD/MM/YYYY
    out["game_date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce").dt.date.astype(str)
    out["season_year"] = SEASON_LABELS.get(season, season)
    out["league_id"]   = league_id
    out["home_team"]   = df["HomeTeam"].str.strip()
    out["away_team"]   = df["AwayTeam"].str.strip()

    out["home_score"] = pd.to_numeric(df["FTHG"], errors="coerce")
    out["away_score"] = pd.to_numeric(df["FTAG"], errors="coerce")

    # regulation_total_90: sum of 90-min goals (no ET for league matches)
    out["regulation_total_90"] = out["home_score"] + out["away_score"]
    out["official_bet_total"]  = out["regulation_total_90"]

    # ET / penalties — not applicable for regular-season league matches
    out["went_to_et"]         = False
    out["went_to_penalties"]  = False

    # ── xG fields — not available from football-data.co.uk ───────────────────
    out["home_xg_raw"] = None
    out["away_xg_raw"] = None
    out["xg_source"]   = None

    # ── Shots ─────────────────────────────────────────────────────────────────
    out["home_shots"]            = pd.to_numeric(df.get("HS"),  errors="coerce") if "HS"  in df.columns else None
    out["away_shots"]            = pd.to_numeric(df.get("AS"),  errors="coerce") if "AS"  in df.columns else None
    out["home_shots_on_target"]  = pd.to_numeric(df.get("HST"), errors="coerce") if "HST" in df.columns else None
    out["away_shots_on_target"]  = pd.to_numeric(df.get("AST"), errors="coerce") if "AST" in df.columns else None

    # ── Market — B365 over/under 2.5 ─────────────────────────────────────────
    has_over  = "B365>2.5" in df.columns
    has_under = "B365<2.5" in df.columns

    if has_over and has_under:
        over_p  = pd.to_numeric(df["B365>2.5"], errors="coerce")
        under_p = pd.to_numeric(df["B365<2.5"], errors="coerce")
        out["closing_total_line"] = 2.5
        out["over_price"]         = over_p
        out["under_price"]        = under_p
        out["market_available"]   = (over_p.notna() & under_p.notna())
    else:
        out["closing_total_line"] = None
        out["over_price"]         = None
        out["under_price"]        = None
        out["market_available"]   = False

    # ── game_id: deterministic composite key ─────────────────────────────────
    # Format: {league_id}_{season}_{YYYY-MM-DD}_{home}_{away}  (spaces → underscores)
    def _make_gid(row):
        h = str(row["home_team"]).replace(" ", "_")
        a = str(row["away_team"]).replace(" ", "_")
        return f"{league_id}_{season}_{row['game_date']}_{h}_{a}"

    out["game_id"] = out.apply(_make_gid, axis=1)

    # Drop rows where game_date parse failed (genuine nulls, not empty rows)
    out = out[out["game_date"] != "NaT"].copy()

    logger.info(f"Parsed {league_id} {season}: {len(out)} rows")
    return out


def fetch_season(league_id: str, season: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch and parse one league × season. Returns canonical-schema DataFrame
    (subset of columns — game_id through market_available).
    Returns empty DataFrame on failure.
    """
    text = _fetch_csv(league_id, season, force_refresh=force_refresh)
    if text is None:
        return pd.DataFrame()
    return _parse_csv(text, league_id, season)


def fetch_all_seasons(
    league_ids: list[str] | None = None,
    seasons:    list[str] | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch all combinations of league × season.
    Defaults to all configured leagues and all seasons (train + validate + OOS).

    Args:
        league_ids:    list of league IDs to fetch (default: all in LEAGUES)
        seasons:       list of season codes to fetch (default: all in ALL_SEASONS from config)
        force_refresh: re-download even if cached

    Returns:
        Concatenated DataFrame across all league/season combos, sorted by
        league_id, season_year, game_date.
    """
    from soccer.config import ALL_SEASONS

    if league_ids is None:
        league_ids = list(LEAGUES.keys())
    if seasons is None:
        seasons = ALL_SEASONS

    frames = []
    for lid in league_ids:
        for s in seasons:
            df = fetch_season(lid, s, force_refresh=force_refresh)
            if not df.empty:
                frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["league_id", "season_year", "game_date"]).reset_index(drop=True)
    return combined
