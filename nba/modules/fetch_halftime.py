"""
Phase 6 — First-half score fetcher.

The existing LeagueGameLog cache (boxlog_*.json) contains full-game stats only
— no quarter breakdown. This module fetches Q1+Q2 scores via ScoreboardV2,
one call per unique game date (~160-165 per season vs ~1230 per-game).

H1 score = PTS_QTR1 + PTS_QTR2 per team.
Results cached to data/cache/halftime_{season}_{type}.json so subsequent runs
never re-fetch data already on hand.
"""

import json
import logging
import os
import time
from typing import Optional

import pandas as pd

from nba.config import (
    CACHE_DIR,
    GAMES_PATH,
    NBA_API_TIMEOUT,
    SEASON_TYPE_REGULAR,
    ALL_HISTORICAL_SEASONS,
    CURRENT_SEASON,
)
from nba.modules.fetch_games import _call_with_retry, _norm_team

logger = logging.getLogger(__name__)


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_path(season: str, season_type: str) -> str:
    slug = season_type.lower().replace(" ", "_")
    return os.path.join(CACHE_DIR, f"halftime_{season}_{slug}.json")


def _load_cache(season: str, season_type: str) -> Optional[list]:
    path = _cache_path(season, season_type)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"H1 cache read failed for {season}: {e}")
        return None


def _save_cache(season: str, season_type: str, rows: list) -> None:
    path = _cache_path(season, season_type)
    try:
        with open(path, "w") as f:
            json.dump(rows, f)
        logger.info(f"Cached {len(rows)} H1 game rows → {path}")
    except Exception as e:
        logger.warning(f"H1 cache write failed: {e}")


# ── Core fetch ─────────────────────────────────────────────────────────────────

def _fetch_season_raw(
    season: str,
    season_type: str = SEASON_TYPE_REGULAR,
    games_df: pd.DataFrame = None,
) -> list[dict]:
    """
    Pull H1 scores for all games in season via ScoreboardV2 by date.
    Returns list of {game_id, home_team, away_team, home_h1, away_h1, actual_h1_total}.

    games_df : Optional pre-built games DataFrame (e.g. from phase4b.build_2526_features).
               When provided, bypasses GAMES_PATH for seasons not yet in the historical parquet.
    """
    cached = _load_cache(season, season_type)
    if cached is not None:
        logger.info(f"Using cached H1 data for {season} ({len(cached)} games)")
        return cached

    if games_df is not None:
        sg = games_df.copy()
    else:
        if not os.path.exists(GAMES_PATH):
            raise FileNotFoundError(f"games.parquet not found — run build_games_table first.")
        games = pd.read_parquet(GAMES_PATH)
        sg = games[games["season"] == season].copy()

    if sg.empty:
        logger.warning(f"No games found for {season}")
        return []

    sg["date"] = pd.to_datetime(sg["date"])
    valid_gids = set(sg["game_id"].astype(str))
    unique_dates = sorted(sg["date"].dt.date.unique())
    home_map = sg.set_index("game_id")[["home_team", "away_team"]].to_dict("index")

    logger.info(
        f"Fetching H1 scores for {season}: {len(unique_dates)} game dates, "
        f"{len(valid_gids)} games …"
    )

    from nba_api.stats.endpoints import scoreboardv2

    # game_id → {team_abbr: h1_score}
    h1_map: dict[str, dict] = {}
    errors = 0

    for i, date in enumerate(unique_dates):
        date_str = pd.Timestamp(date).strftime("%m/%d/%Y")
        try:
            board = _call_with_retry(
                scoreboardv2.ScoreboardV2,
                game_date=date_str,
                day_offset=0,
                league_id="00",
                timeout=NBA_API_TIMEOUT,
            )
            time.sleep(0.6)

            # ScoreboardV2 LineScore is index 1 in most nba_api versions;
            # use named accessor if available, fall back to index.
            try:
                ls = board.line_score.get_data_frame()
            except AttributeError:
                ls = board.get_data_frames()[1]

            for _, row in ls.iterrows():
                gid = str(row.get("GAME_ID", "")).strip()
                if gid not in valid_gids:
                    continue
                q1 = float(row.get("PTS_QTR1") or 0)
                q2 = float(row.get("PTS_QTR2") or 0)
                team = _norm_team(str(row.get("TEAM_ABBREVIATION", "")))
                h1_map.setdefault(gid, {})[team] = q1 + q2

        except Exception as e:
            logger.warning(f"ScoreboardV2 failed for {date_str}: {e}")
            errors += 1
            continue

        if (i + 1) % 40 == 0:
            logger.info(f"  {i+1}/{len(unique_dates)} dates processed …")

    if errors:
        logger.warning(f"  {errors} date(s) failed — those games will be missing from H1 data")

    # Pair home/away H1 scores
    rows = []
    skipped = 0
    for gid, teams in h1_map.items():
        info = home_map.get(gid, {})
        home = _norm_team(str(info.get("home_team", "")))
        away = _norm_team(str(info.get("away_team", "")))
        home_h1 = teams.get(home)
        away_h1 = teams.get(away)
        if home_h1 is None or away_h1 is None:
            logger.debug(f"Missing H1 team data for game {gid}: found={list(teams.keys())}")
            skipped += 1
            continue
        rows.append({
            "game_id":       gid,
            "home_team":     home,
            "away_team":     away,
            "home_h1":       home_h1,
            "away_h1":       away_h1,
            "actual_h1_total": home_h1 + away_h1,
        })

    if skipped:
        logger.warning(f"Skipped {skipped} games with incomplete H1 team data in {season}")

    _save_cache(season, season_type, rows)
    logger.info(f"H1 fetch complete: {len(rows)} games for {season} ({season_type})")
    return rows


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_halftime_season(
    season: str,
    season_type: str = SEASON_TYPE_REGULAR,
    games_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """Return H1 scores DataFrame for one season.

    games_df : Optional pre-built games DataFrame for seasons not yet in games.parquet
               (e.g. CURRENT_SEASON fetched live via fetch_season()).
    """
    rows = _fetch_season_raw(season, season_type, games_df=games_df)
    if not rows:
        return pd.DataFrame(columns=["game_id", "home_team", "away_team",
                                     "home_h1", "away_h1", "actual_h1_total"])
    return pd.DataFrame(rows)


def build_halftime_table(
    seasons: list[str] = None,
    season_type: str = SEASON_TYPE_REGULAR,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Build combined H1 scores table for all seasons."""
    if seasons is None:
        seasons = ALL_HISTORICAL_SEASONS + [CURRENT_SEASON]

    frames = []
    for season in seasons:
        if force_refresh:
            path = _cache_path(season, season_type)
            if os.path.exists(path):
                os.remove(path)
        df = fetch_halftime_season(season, season_type)
        if not df.empty:
            frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
