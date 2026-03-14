"""
Phase 2 — Box score stats fetcher.

Pulls LeagueGameLog (one row per team per game) from NBA Stats API,
computes estimated possessions, ORtg, DRtg, and pace per team per game.

Possession formula (Oliver, universally standard):
    poss = FGA - OREB + TOV + 0.44 × FTA

Pace = possessions per 48 minutes (inferred from team MIN column in box log).

Results cached to data/cache/boxlog_{season}_{type}.json so re-runs
never re-pull data already on hand.
"""

import json
import logging
import os
import time
from typing import Optional

import pandas as pd

from nba.config import (
    BOX_STATS_PATH,
    CACHE_DIR,
    NBA_API_TIMEOUT,
    SEASON_TYPE_REGULAR,
    ALL_HISTORICAL_SEASONS,
)
from nba.modules.fetch_games import _call_with_retry, _norm_team

logger = logging.getLogger(__name__)

_OLIVER_CONSTANT = 0.44   # free-throw possession weight


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(season: str, season_type: str) -> str:
    slug = season_type.lower().replace(" ", "_")
    return os.path.join(CACHE_DIR, f"boxlog_{season}_{slug}.json")


def _load_cache(season: str, season_type: str) -> Optional[list]:
    path = _cache_path(season, season_type)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Box stats cache read failed for {season}: {e}")
        return None


def _save_cache(season: str, season_type: str, rows: list) -> None:
    path = _cache_path(season, season_type)
    try:
        with open(path, "w") as f:
            json.dump(rows, f)
        logger.info(f"Cached {len(rows)} box log rows → {path}")
    except Exception as e:
        logger.warning(f"Box stats cache write failed: {e}")


# ── Core fetch ────────────────────────────────────────────────────────────────

def _fetch_season_raw(season: str, season_type: str = SEASON_TYPE_REGULAR) -> list[dict]:
    """Pull LeagueGameLog for *season*, cache raw rows."""
    cached = _load_cache(season, season_type)
    if cached is not None:
        logger.info(f"Using cached box log for {season} ({len(cached)} rows)")
        return cached

    logger.info(f"Fetching box log (LeagueGameLog) for {season} {season_type} …")
    from nba_api.stats.endpoints import leaguegamelog

    log = _call_with_retry(
        leaguegamelog.LeagueGameLog,
        season=season,
        season_type_all_star=season_type,
        league_id="00",
        timeout=NBA_API_TIMEOUT,
    )
    time.sleep(1)

    df  = log.get_data_frames()[0]
    rows = df.to_dict("records")
    _save_cache(season, season_type, rows)
    logger.info(f"Fetched {len(rows)} box log rows for {season}")
    return rows


# ── Possession and efficiency helpers ─────────────────────────────────────────

def _poss(fga, oreb, tov, fta) -> float:
    """Oliver possession estimate. Returns at least 1 to avoid division by zero."""
    return max(1.0, float(fga or 0) - float(oreb or 0)
               + float(tov or 0) + _OLIVER_CONSTANT * float(fta or 0))


def _game_minutes(team_min_str) -> float:
    """
    Convert the team-minutes string from LeagueGameLog to game minutes.
    Regulation = 240 team-minutes (5 players × 48 min); divide by 5.
    OT periods add 25 team-minutes each.
    Falls back to 48.0 if MIN is missing or unparseable.
    """
    try:
        mins = float(str(team_min_str).replace(":", "."))
        return max(48.0, mins / 5.0)
    except (TypeError, ValueError):
        return 48.0


# ── Pair rows into per-team game records ──────────────────────────────────────

def _build_team_game_records(raw: list[dict], season: str) -> list[dict]:
    """
    From raw LeagueGameLog rows (one per team per game) produce a canonical
    record per (team, game) with computed efficiency stats.
    """
    # Group by game_id
    by_game: dict[str, list] = {}
    for row in raw:
        gid = str(row.get("GAME_ID", ""))
        by_game.setdefault(gid, []).append(row)

    records = []
    skipped = 0

    for gid, pair in by_game.items():
        if len(pair) != 2:
            skipped += 1
            continue

        # Identify home / away (mirrors fetch_games._pair_game_rows logic)
        home_row = away_row = None
        for r in pair:
            matchup = str(r.get("MATCHUP", ""))
            if "vs." in matchup:
                home_row = r
            elif "@" in matchup:
                away_row = r

        if home_row is None:
            # Both rows share the same MATCHUP string — infer from team after "@"
            matchup = str(pair[0].get("MATCHUP", ""))
            if "@" in matchup:
                home_abbr = matchup.split("@")[-1].strip().upper()
                for r in pair:
                    if r.get("TEAM_ABBREVIATION", "").upper() == home_abbr:
                        home_row = r
                    else:
                        away_row = r

        if home_row is None or away_row is None:
            skipped += 1
            continue

        # Skip if score is missing (shouldn't happen for completed games)
        if home_row.get("PTS") is None or away_row.get("PTS") is None:
            skipped += 1
            continue

        # Use average of both teams' MIN for game minutes (most accurate)
        gm = (_game_minutes(home_row.get("MIN")) + _game_minutes(away_row.get("MIN"))) / 2.0
        went_ot = gm > 48.5

        home_poss = _poss(home_row.get("FGA"), home_row.get("OREB"),
                          home_row.get("TOV"),  home_row.get("FTA"))
        away_poss = _poss(away_row.get("FGA"), away_row.get("OREB"),
                          away_row.get("TOV"),  away_row.get("FTA"))
        game_poss = (home_poss + away_poss) / 2.0

        home_pts = float(home_row.get("PTS", 0))
        away_pts = float(away_row.get("PTS", 0))

        # pace = possessions per 48 minutes
        pace = round(game_poss * 48.0 / gm, 2)

        for team_row, opp_row, loc, t_poss in [
            (home_row, away_row, "H", home_poss),
            (away_row, home_row, "A", away_poss),
        ]:
            t_pts   = float(team_row.get("PTS", 0))
            opp_pts = float(opp_row.get("PTS", 0))

            records.append({
                "game_id":  gid,
                "date":     team_row.get("GAME_DATE"),
                "season":   season,
                "team":     _norm_team(team_row.get("TEAM_ABBREVIATION", "")),
                "opponent": _norm_team(opp_row.get("TEAM_ABBREVIATION", "")),
                "location": loc,          # "H" = home, "A" = away
                "pts":      t_pts,
                "opp_pts":  opp_pts,
                "poss":     round(t_poss, 2),
                "ortg":     round(t_pts / t_poss * 100, 2),
                "drtg":     round(opp_pts / opp_poss * 100, 2)
                            if (opp_poss := _poss(opp_row.get("FGA"), opp_row.get("OREB"),
                                                  opp_row.get("TOV"), opp_row.get("FTA"))) > 0
                            else None,
                "pace":     pace,
                "went_ot":  went_ot,
            })

    if skipped:
        logger.warning(f"Box stats: skipped {skipped} unpair-able games in {season}")

    return records


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_box_stats(
    season: str,
    season_type: str = SEASON_TYPE_REGULAR,
) -> pd.DataFrame:
    """Return per-team-per-game efficiency stats for one season."""
    raw     = _fetch_season_raw(season, season_type)
    records = _build_team_game_records(raw, season)
    df      = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["team", "date"]).reset_index(drop=True)
    return df


def build_box_stats_table(
    seasons: list[str] = None,
    season_type: str = SEASON_TYPE_REGULAR,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Build (or incrementally extend) the box stats parquet table.
    Skips seasons already present unless force_refresh=True.
    """
    if seasons is None:
        seasons = ALL_HISTORICAL_SEASONS

    if force_refresh and os.path.exists(BOX_STATS_PATH):
        os.remove(BOX_STATS_PATH)

    existing: pd.DataFrame = pd.DataFrame()
    if os.path.exists(BOX_STATS_PATH):
        try:
            existing = pd.read_parquet(BOX_STATS_PATH)
            logger.info(f"Loaded existing box stats: {len(existing)} rows")
        except Exception as e:
            logger.warning(f"Could not load existing box stats: {e}")

    fetched_seasons = (
        set(existing["season"].unique()) if not existing.empty else set()
    )

    new_frames = []
    for season in seasons:
        if season in fetched_seasons and not force_refresh:
            logger.info(f"Box stats for {season} already present — skipping")
            continue
        df = fetch_box_stats(season, season_type)
        if not df.empty:
            new_frames.append(df)

    if new_frames:
        combined = pd.concat([existing] + new_frames, ignore_index=True)
        combined = (
            combined
            .drop_duplicates(subset=["game_id", "team"])
            .sort_values(["team", "date"])
            .reset_index(drop=True)
        )
        combined["date"] = pd.to_datetime(combined["date"])
        combined.to_parquet(BOX_STATS_PATH, index=False)
        logger.info(f"Box stats saved: {len(combined)} rows → {BOX_STATS_PATH}")
    else:
        combined = existing

    return combined
