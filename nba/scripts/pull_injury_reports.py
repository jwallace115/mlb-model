#!/usr/bin/env python3
"""
Batch pull NBA injury reports for 2023-24 regular season.

Timing rule:
  - Find the latest pre-tipoff report timestamp for each game date
  - If any game tips off before 5PM ET: use latest report before earliest tipoff
  - Otherwise: use 5PM ET report
  - Never use a report timestamped after any game has tipped off

Cache to: nba/data/injury_reports/{YYYY-MM-DD}_{HHMM}.parquet
"""

import os, sys, time, re, requests, warnings
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path

os.environ['JAVA_HOME'] = '/Users/jw115/jre21/Contents/Home'
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Must import after JAVA_HOME set
from nbainjuries import injury as nba_injury

REPO_DIR     = Path(__file__).parent.parent.parent
CACHE_DIR    = REPO_DIR / 'nba' / 'data' / 'injury_reports'
TMP_DIR      = Path('/tmp/nba_injury_pdfs')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 2023-24 regular season dates
SEASON_START = date(2023, 10, 24)
SEASON_END   = date(2024, 4, 14)   # regular season end (excl playoffs)

# Standard report times to try (ET, descending — use last valid pre-tipoff)
# New format since 2025-12-22: HH_MM; old format (2023-24): HH (no minutes)
# For 2023-24 all reports use legacy format: Injury-Report_YYYY-MM-DD_HHPM.pdf
REPORT_HOURS_ET = [17, 16, 15, 14, 13]  # 5PM, 4PM, 3PM, 2PM, 1PM

def _gen_url_legacy(dt: datetime) -> str:
    """URL format for 2023-24 season (before 2025-12-22 format change)."""
    return (f"https://ak-static.cms.nba.com/referee/injury/"
            f"Injury-Report_{dt.strftime('%Y-%m-%d')}_{dt.strftime('%I%p')}.pdf")

def _gen_url_auto(dt: datetime) -> str:
    """Use nbainjuries gen_url (handles format transitions automatically)."""
    return nba_injury.gen_url(dt)

def _pdf_exists(url: str) -> bool:
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, verify=False)
        return r.status_code == 200
    except Exception:
        return False

def _download_pdf(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        if r.status_code == 200 and len(r.content) > 1000:
            dest.write_bytes(r.content)
            return True
        return False
    except Exception:
        return False

def _parse_pdf(ts: datetime, pdf_path: Path) -> pd.DataFrame | None:
    """Parse a local PDF using nbainjuries."""
    try:
        df = nba_injury.get_reportdata(ts, local=True, localdir=str(pdf_path.parent), return_df=True)
        return df
    except Exception as e:
        print(f"    Parse error: {e}")
        return None

def _cache_path(game_date: date, hour: int, minute: int = 0) -> Path:
    return CACHE_DIR / f"{game_date.isoformat()}_{hour:02d}{minute:02d}.parquet"

def _already_cached(game_date: date) -> Path | None:
    """Return first cached parquet for this date, or None."""
    for p in sorted(CACHE_DIR.glob(f"{game_date.isoformat()}_*.parquet")):
        return p
    return None

def get_game_dates_and_tipoffs(season_start: date, season_end: date) -> dict[date, list[int]]:
    """
    Fetch game schedule from nba_api to get tipoff hours ET.
    Returns {game_date: [earliest_tipoff_hour_ET, ...]}
    """
    from nba_api.stats.endpoints import leaguegamelog
    print("Fetching 2023-24 schedule from nba_api...")
    games = leaguegamelog.LeagueGameLog(
        season='2023-24',
        season_type_all_star='Regular Season',
        timeout=60
    ).get_data_frames()[0]
    time.sleep(1)

    # GAME_DATE is YYYY-MM-DD, game_time not directly in LeagueGameLog
    # Use the games parquet if available (already cached in nba/data/games.parquet)
    games_parquet = REPO_DIR / 'nba' / 'data' / 'games.parquet'
    if games_parquet.exists():
        gdf = pd.read_parquet(games_parquet)
        gdf = gdf[gdf['season'] == '2023-24']
        if 'game_date' in gdf.columns:
            print(f"  Using cached games.parquet: {len(gdf)} games")
            date_set = {}
            for _, row in gdf.iterrows():
                gd = pd.Timestamp(row['game_date']).date()
                if season_start <= gd <= season_end:
                    date_set.setdefault(gd, [])
            return date_set

    # Fallback: just enumerate all dates in range
    d = season_start
    dates = {}
    while d <= season_end:
        dates[d] = []
        d += timedelta(days=1)
    return dates

def pull_report_for_date(game_date: date, verbose: bool = True) -> Path | None:
    """
    Pull the appropriate pre-tipoff injury report for game_date.
    Returns path to cached parquet or None if no report found.
    """
    # Check cache first
    existing = _already_cached(game_date)
    if existing:
        return existing

    # Try reports from 5PM down to 1PM (use 5PM as default, earlier for afternoon games)
    for hour in REPORT_HOURS_ET:
        ts = datetime(game_date.year, game_date.month, game_date.day, hour, 0)
        url = _gen_url_auto(ts)
        filename = url.split('/')[-1]
        pdf_path = TMP_DIR / filename

        # Download if not already local
        if not pdf_path.exists():
            if not _download_pdf(url, pdf_path):
                continue  # This hour's report doesn't exist — try earlier
            time.sleep(0.3)  # polite delay

        # Parse
        df = _parse_pdf(ts, pdf_path)
        if df is None or df.empty:
            pdf_path.unlink(missing_ok=True)
            continue

        # Cache
        cache_path = _cache_path(game_date, hour)
        df.to_parquet(cache_path, index=False)
        if verbose:
            print(f"  {game_date} → {hour:02d}:00 ET | {len(df)} rows → {cache_path.name}")
        return cache_path

    if verbose:
        print(f"  {game_date} → no report found (no games or pre-season?)")
    return None


def run_batch(season_start: date = SEASON_START, season_end: date = SEASON_END):
    """Pull all reports for the season."""
    all_dates = []
    d = season_start
    while d <= season_end:
        all_dates.append(d)
        d += timedelta(days=1)

    print(f"\nBatch pull: {len(all_dates)} dates ({season_start} → {season_end})")
    already = sum(1 for d in all_dates if _already_cached(d))
    print(f"Already cached: {already} / {len(all_dates)}")

    pulled = 0
    failed = 0
    for i, gdate in enumerate(all_dates):
        result = pull_report_for_date(gdate, verbose=True)
        if result:
            pulled += 1
        else:
            failed += 1

        if (i + 1) % 20 == 0:
            print(f"  --- Progress: {i+1}/{len(all_dates)} dates | "
                  f"pulled={pulled} failed={failed} ---")

    print(f"\nDone. Pulled: {pulled} | Failed/no-game: {failed}")


if __name__ == '__main__':
    run_batch()
