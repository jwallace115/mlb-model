"""
Phase 1 — Historical game fetcher.

Pulls regular-season game results from the NBA Stats API using
LeagueGameFinder, one season at a time.  Raw API responses are cached
to disk as JSON so re-runs never re-pull data already on hand.

Output: canonical DataFrame with one row per game:
    game_id, date, home_team, away_team,
    home_score, away_score, actual_total,
    season, season_type
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
    NBA_API_BACKOFF,
    NBA_API_RETRIES,
    NBA_API_TIMEOUT,
    SEASON_TYPE_REGULAR,
)

logger = logging.getLogger(__name__)

# ── NBA team abbreviation normalisation ──────────────────────────────────────
# nba_api uses official abbreviations but a handful have changed over the years.
_TEAM_NORM = {
    "NOP": "NOP",  # New Orleans Pelicans (sometimes "NOH" in old data)
    "NOH": "NOP",
    "NJN": "BKN",  # New Jersey Nets → Brooklyn
    "SEA": "OKC",  # Seattle → OKC
    "VAN": "MEM",  # Vancouver → Memphis
    "CHA": "CHA",  # Charlotte (keep — both CHA and CHO appear)
    "CHO": "CHA",
    "GSW": "GSW",
    "PHX": "PHX",
    "UTA": "UTA",
}


def _norm_team(abbr: str) -> str:
    return _TEAM_NORM.get(abbr.upper().strip(), abbr.upper().strip())


# ── Retry wrapper ─────────────────────────────────────────────────────────────

def _call_with_retry(fn, *args, **kwargs):
    """
    Call *fn* with exponential back-off retry.
    NBA Stats API frequently times out or returns 429s.
    """
    last_exc = None
    for attempt in range(NBA_API_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            wait = NBA_API_BACKOFF[min(attempt, len(NBA_API_BACKOFF) - 1)]
            logger.warning(
                f"NBA API call failed (attempt {attempt + 1}/{NBA_API_RETRIES}): "
                f"{exc!r} — retrying in {wait}s"
            )
            time.sleep(wait)
    raise RuntimeError(
        f"NBA API call failed after {NBA_API_RETRIES} retries"
    ) from last_exc


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(season: str, season_type: str) -> str:
    slug = season_type.lower().replace(" ", "_")
    return os.path.join(CACHE_DIR, f"games_{season}_{slug}.json")


def _load_cache(season: str, season_type: str) -> Optional[list]:
    path = _cache_path(season, season_type)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Cache read failed for {season}/{season_type}: {e}")
        return None


def _save_cache(season: str, season_type: str, rows: list) -> None:
    path = _cache_path(season, season_type)
    try:
        with open(path, "w") as f:
            json.dump(rows, f)
        logger.info(f"Cached {len(rows)} game rows → {path}")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


# ── Core fetch ────────────────────────────────────────────────────────────────

def _fetch_season_raw(season: str, season_type: str = SEASON_TYPE_REGULAR) -> list[dict]:
    """
    Pull LeagueGameFinder for *season* / *season_type*.
    Returns a list of row dicts (one row per team per game — pairs later).
    Results are cached to disk.
    """
    cached = _load_cache(season, season_type)
    if cached is not None:
        logger.info(f"Using cached data for {season} {season_type} ({len(cached)} rows)")
        return cached

    logger.info(f"Fetching {season} {season_type} from NBA Stats API …")

    from nba_api.stats.endpoints import leaguegamefinder
    finder = _call_with_retry(
        leaguegamefinder.LeagueGameFinder,
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable="00",   # NBA
        timeout=NBA_API_TIMEOUT,
    )
    time.sleep(1)  # polite delay — NBA API rate-limits aggressively

    df = finder.get_data_frames()[0]
    rows = df.to_dict("records")

    _save_cache(season, season_type, rows)
    logger.info(f"Fetched {len(rows)} team-game rows for {season} {season_type}")
    return rows


# ── Pair home / away rows into one game row ───────────────────────────────────

def _pair_game_rows(rows: list[dict], season: str, season_type: str) -> list[dict]:
    """
    LeagueGameFinder returns one row per *team* per game.
    The MATCHUP column distinguishes home ("vs.") from away ("@").

    We pair rows by GAME_ID and build one canonical game record.
    """
    # Group by game_id
    by_game: dict[str, list] = {}
    for row in rows:
        gid = str(row.get("GAME_ID", ""))
        by_game.setdefault(gid, []).append(row)

    games = []
    skipped = 0
    for gid, pair in by_game.items():
        if len(pair) != 2:
            # Some rows are corrupted or double-headers; skip
            skipped += 1
            continue

        # Identify home / away from MATCHUP string.
        # Normal case: home row shows "XXX vs. YYY", away row shows "YYY @ XXX".
        # Edge case: both rows share the same string (e.g. both say "IND @ SAS").
        # In that case infer home from the team listed AFTER "@" in the shared string.
        home_row = away_row = None
        for r in pair:
            matchup = str(r.get("MATCHUP", ""))
            if "vs." in matchup:
                home_row = r
            elif "@" in matchup:
                away_row = r

        if home_row is None:
            # Both rows matched "@" (same MATCHUP string) — parse home from it
            matchup = str(pair[0].get("MATCHUP", ""))
            if "@" in matchup:
                # Format: "AWAY_ABBR @ HOME_ABBR"
                home_abbr = matchup.split("@")[-1].strip().upper()
                for r in pair:
                    if r.get("TEAM_ABBREVIATION", "").upper() == home_abbr:
                        home_row = r
                    else:
                        away_row = r

        if home_row is None or away_row is None:
            skipped += 1
            continue

        home_score = home_row.get("PTS")
        away_score = away_row.get("PTS")
        if home_score is None or away_score is None:
            skipped += 1
            continue

        games.append({
            "game_id":     gid,
            "date":        home_row.get("GAME_DATE", ""),
            "home_team":   _norm_team(home_row.get("TEAM_ABBREVIATION", "")),
            "away_team":   _norm_team(away_row.get("TEAM_ABBREVIATION", "")),
            "home_score":  int(home_score),
            "away_score":  int(away_score),
            "actual_total": int(home_score) + int(away_score),
            "season":      season,
            "season_type": season_type,
        })

    if skipped:
        logger.warning(f"Skipped {skipped} unpair-able game_ids in {season}")

    return games


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_season(season: str, season_type: str = SEASON_TYPE_REGULAR) -> pd.DataFrame:
    """Return a cleaned DataFrame for one season."""
    raw  = _fetch_season_raw(season, season_type)
    rows = _pair_game_rows(raw, season, season_type)
    df   = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def build_game_table(
    seasons: list[str] = None,
    season_type: str = SEASON_TYPE_REGULAR,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Build (or load from cache) the canonical game table.

    Parameters
    ----------
    seasons       : list of season strings e.g. ["2022-23", "2023-24"]
    season_type   : SEASON_TYPE_REGULAR or SEASON_TYPE_PLAYOFF
    force_refresh : if True, ignore disk cache and re-pull from API

    Returns
    -------
    pd.DataFrame with canonical schema
    """
    from nba.config import ALL_HISTORICAL_SEASONS
    if seasons is None:
        seasons = ALL_HISTORICAL_SEASONS

    if force_refresh and os.path.exists(GAMES_PATH):
        os.remove(GAMES_PATH)

    # Load existing parquet if present so we can skip already-fetched seasons
    existing: pd.DataFrame = pd.DataFrame()
    if os.path.exists(GAMES_PATH):
        try:
            existing = pd.read_parquet(GAMES_PATH)
            logger.info(f"Loaded existing game table: {len(existing)} rows")
        except Exception as e:
            logger.warning(f"Could not load existing game table: {e}")

    fetched_seasons = (
        set(existing["season"].unique()) if not existing.empty else set()
    )

    new_frames = []
    for season in seasons:
        if season in fetched_seasons and not force_refresh:
            logger.info(f"Season {season} already in game table — skipping")
            continue
        df = fetch_season(season, season_type)
        if not df.empty:
            new_frames.append(df)

    if new_frames:
        combined = pd.concat([existing] + new_frames, ignore_index=True)
        combined = (
            combined
            .drop_duplicates(subset=["game_id"])
            .sort_values(["date", "game_id"])
            .reset_index(drop=True)
        )
        combined.to_parquet(GAMES_PATH, index=False)
        logger.info(f"Game table saved: {len(combined)} rows → {GAMES_PATH}")
    else:
        combined = existing

    return combined


# ── Data quality audit ────────────────────────────────────────────────────────

def audit_game_table(df: pd.DataFrame) -> dict:
    """
    Run a data quality audit on the canonical game table.

    Returns a dict of audit findings; also prints a human-readable report.
    """
    print("\n" + "═" * 60)
    print("  NBA GAME TABLE — DATA QUALITY AUDIT")
    print("═" * 60)

    findings = {}

    # 1. Row counts by season
    counts = df.groupby("season").size().to_dict()
    findings["rows_by_season"] = counts
    print("\n📊 Row counts by season:")
    for s, n in sorted(counts.items()):
        expected = 1230  # 30 teams × 82 games / 2
        flag = "  ✓" if abs(n - expected) <= 30 else f"  ⚠ (expected ~{expected})"
        print(f"   {s}: {n:>5} games{flag}")

    # 2. Missing values
    nulls = df.isnull().sum()
    null_cols = nulls[nulls > 0]
    findings["missing_values"] = null_cols.to_dict()
    if null_cols.empty:
        print("\n✅ Missing values: none")
    else:
        print(f"\n⚠  Missing values found:")
        for col, n in null_cols.items():
            print(f"   {col}: {n} ({n/len(df)*100:.1f}%)")

    # 3. Duplicate game_ids
    dup_count = df.duplicated(subset=["game_id"]).sum()
    findings["duplicate_game_ids"] = int(dup_count)
    if dup_count == 0:
        print("\n✅ Duplicate game_ids: none")
    else:
        print(f"\n⚠  Duplicate game_ids: {dup_count}")

    # 4. Score sanity checks
    # Lower bound: <150 impossible in regulation; upper bound: >320 would require
    # an implausible number of OT periods (a 4OT game (LAC/SAC 2023) scored 351).
    low_total  = (df["actual_total"] < 150).sum()
    high_total = (df["actual_total"] > 320).sum()
    findings["totals_below_150"] = int(low_total)
    findings["totals_above_320"] = int(high_total)
    if low_total or high_total:
        print(f"\n⚠  Implausible totals: {low_total} below 150, {high_total} above 320")
        if low_total:
            print(df[df["actual_total"] < 150][["date","home_team","away_team","home_score","away_score","actual_total"]].to_string(index=False))
        if high_total:
            print(df[df["actual_total"] > 320][["date","home_team","away_team","home_score","away_score","actual_total"]].to_string(index=False))
    else:
        print(f"\n✅ Total score range: {df['actual_total'].min()}–{df['actual_total'].max()} (all plausible; OT games included)")

    # 5. Negative or zero scores
    bad_scores = ((df["home_score"] <= 0) | (df["away_score"] <= 0)).sum()
    findings["zero_or_negative_scores"] = int(bad_scores)
    if bad_scores:
        print(f"\n⚠  Zero/negative team scores: {bad_scores}")
    else:
        print(f"\n✅ Team score range: {df['home_score'].min()}–{df['home_score'].max()} home, "
              f"{df['away_score'].min()}–{df['away_score'].max()} away")

    # 6. Team naming consistency
    all_teams = set(df["home_team"].unique()) | set(df["away_team"].unique())
    findings["unique_teams"] = sorted(all_teams)
    print(f"\n📋 Unique team abbreviations ({len(all_teams)}): {', '.join(sorted(all_teams))}")
    # Flag anything unexpected (should be 30 teams)
    if len(all_teams) > 32:
        print(f"   ⚠  More than 32 unique team codes — possible naming inconsistency")
    else:
        print(f"   ✓  Team count looks normal")

    # 7. Total distribution
    print(f"\n📈 Actual total distribution:")
    print(f"   mean={df['actual_total'].mean():.1f}  "
          f"std={df['actual_total'].std():.1f}  "
          f"p10={df['actual_total'].quantile(0.10):.0f}  "
          f"p25={df['actual_total'].quantile(0.25):.0f}  "
          f"p50={df['actual_total'].quantile(0.50):.0f}  "
          f"p75={df['actual_total'].quantile(0.75):.0f}  "
          f"p90={df['actual_total'].quantile(0.90):.0f}")
    findings["total_stats"] = {
        "mean": round(df["actual_total"].mean(), 1),
        "std":  round(df["actual_total"].std(), 1),
        "min":  int(df["actual_total"].min()),
        "max":  int(df["actual_total"].max()),
    }

    # 8. Date range check
    print(f"\n📅 Date range: {df['date'].min().date()} → {df['date'].max().date()}")
    findings["date_range"] = {
        "min": str(df["date"].min().date()),
        "max": str(df["date"].max().date()),
    }

    # 9. Season overlap check
    for season in df["season"].unique():
        sub = df[df["season"] == season]
        print(f"   {season}: {sub['date'].min().date()} → {sub['date'].max().date()}")

    # 10. Sample rows
    print("\n📝 Sample rows (5 random games):")
    sample = df.sample(min(5, len(df)), random_state=42)[
        ["game_id","date","home_team","away_team","home_score","away_score","actual_total","season"]
    ].sort_values("date")
    print(sample.to_string(index=False))

    print("\n" + "═" * 60)
    total_issues = (
        len(null_cols) + dup_count + low_total + high_total + bad_scores
        + max(0, len(all_teams) - 32)
    )
    # Note: >280 but <=320 totals are OT games (real data, not errors)
    if total_issues == 0:
        print("  ✅  AUDIT PASSED — no issues found")
    else:
        print(f"  ⚠   AUDIT: {total_issues} issue category/ies flagged above")
    print("═" * 60 + "\n")

    findings["total_issues"] = total_issues
    return findings
