#!/usr/bin/env python3
"""
F5 Historical Line Backfill (2023-2025)
========================================
Pulls F5 (first-5-innings) closing lines from Odds API historical endpoint.

Uses event-level endpoint since the bulk endpoint rejects totals_1st_5_innings.
Flow: historical/events → get event IDs → historical/events/{id}/odds per game.

Output matches f5_lines_2026.parquet schema.
"""

import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import ODDS_API_KEY

LOG_DIR = Path("/root/logs") if os.path.exists("/root/logs") else PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "f5_backfill.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("f5_backfill")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_BASE = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb"
QUERY_HOUR = "18:00:00Z"  # 2 PM ET — pre-game, catches closing lines

BOOK_PRIORITY = [
    "pinnacle", "draftkings", "fanduel", "bovada", "betonlineag",
    "betmgm", "betus", "williamhill_us", "lowvig", "mybookieag",
]

TEAM_NAME_MAP = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Cleveland Indians": "CLE",       # pre-2022 name
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP",
    "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSN",
}

SEASON_RANGES = {
    2023: (date(2023, 3, 30), date(2023, 10, 2)),
    2024: (date(2024, 3, 28), date(2024, 9, 30)),
    2025: (date(2025, 3, 27), date(2025, 9, 29)),
}

OUTPUT_PATH = PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_lines_historical.parquet"
COMBINED_PATH = PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_lines_combined.parquet"
CHECKPOINT_PATH = PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_backfill_progress.json"
GAME_TABLE_PATH = PROJECT_ROOT / "sim" / "data" / "game_table.parquet"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"completed_dates": [], "credits_used": 0, "total_games": 0}


def save_checkpoint(ckpt: dict):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(ckpt, f, indent=2)


def load_game_table() -> pd.DataFrame:
    if not GAME_TABLE_PATH.exists():
        logger.warning("game_table.parquet not found — game_pk join will be skipped")
        return pd.DataFrame()
    gt = pd.read_parquet(GAME_TABLE_PATH)
    gt["date"] = gt["date"].astype(str)
    return gt


def get_events_for_date(dt_str: str) -> list[dict]:
    """Get list of MLB events for a given date via historical events endpoint."""
    r = requests.get(f"{API_BASE}/events", params={
        "apiKey": ODDS_API_KEY,
        "date": dt_str,
    }, timeout=20)
    if r.status_code != 200:
        logger.warning(f"Events endpoint HTTP {r.status_code} for {dt_str}: {r.text[:100]}")
        return []
    data = r.json()
    return data.get("data", [])


def get_f5_odds_for_event(event_id: str, dt_str: str) -> dict | None:
    """Get F5 odds for a single event via event-level historical endpoint."""
    r = requests.get(f"{API_BASE}/events/{event_id}/odds", params={
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "totals_1st_5_innings",
        "oddsFormat": "american",
        "date": dt_str,
    }, timeout=20)
    remaining = r.headers.get("x-requests-remaining", "?")
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("data", {}), remaining


def pick_canonical_book(bookmakers: list[dict]) -> dict | None:
    """Select best book by priority order. Returns {book_key, f5_total, over_price, under_price}."""
    # Build lookup by book key
    by_key = {}
    for b in bookmakers:
        for m in b.get("markets", []):
            if m["key"] == "totals_1st_5_innings":
                outcomes = m.get("outcomes", [])
                over = next((o for o in outcomes if o["name"] == "Over"), None)
                under = next((o for o in outcomes if o["name"] == "Under"), None)
                if over and "point" in over:
                    by_key[b["key"]] = {
                        "book_key": b["key"],
                        "f5_total": over["point"],
                        "f5_over_price": over.get("price"),
                        "f5_under_price": under.get("price") if under else None,
                    }
    if not by_key:
        return None
    # Pick by priority
    for bk in BOOK_PRIORITY:
        if bk in by_key:
            return by_key[bk]
    # Fallback: first available
    return next(iter(by_key.values()))


def resolve_game_pk(game_table: pd.DataFrame, game_date: str,
                    home_abbr: str, away_abbr: str) -> tuple[str | None, float | None]:
    """Look up game_pk and actual_f5_total from game_table."""
    if game_table.empty:
        return None, None
    mask = (
        (game_table["date"] == game_date) &
        (game_table["home_team"] == home_abbr) &
        (game_table["away_team"] == away_abbr)
    )
    matches = game_table[mask]
    if len(matches) == 1:
        row = matches.iloc[0]
        gpk = str(row["game_pk"])
        af5 = row.get("actual_f5_total")
        return gpk, af5
    if len(matches) > 1:
        # Doubleheader — take first
        row = matches.iloc[0]
        return str(row["game_pk"]), row.get("actual_f5_total")
    return None, None


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------

def backfill(seasons: list[int] | None = None, dry_run_dates: list[str] | None = None):
    """
    Main backfill loop.

    Args:
        seasons: which seasons to backfill (default all)
        dry_run_dates: if provided, only process these specific date strings
    """
    ckpt = load_checkpoint()
    completed = set(ckpt["completed_dates"])
    game_table = load_game_table()
    rows = []

    # Load existing output if resuming
    if OUTPUT_PATH.exists():
        existing = pd.read_parquet(OUTPUT_PATH)
        rows = existing.to_dict("records")
        logger.info(f"Resuming with {len(rows)} existing rows")

    if seasons is None:
        seasons = [2023, 2024, 2025]

    # Build date list
    if dry_run_dates:
        dates_to_process = [(d, int(d[:4])) for d in dry_run_dates]
    else:
        dates_to_process = []
        for season in seasons:
            start, end = SEASON_RANGES[season]
            d = start
            while d <= end:
                ds = d.isoformat()
                if ds not in completed:
                    dates_to_process.append((ds, season))
                d += timedelta(days=1)

    logger.info(f"Dates to process: {len(dates_to_process)} (skipping {len(completed)} already done)")
    total_credits_session = 0
    total_games_session = 0

    for idx, (dt, season) in enumerate(dates_to_process):
        dt_query = f"{dt}T{QUERY_HOUR}"
        events = get_events_for_date(dt_query)
        if not events:
            logger.info(f"{dt}: 0 events (off-day or all-star break)")
            completed.add(dt)
            ckpt["completed_dates"] = sorted(completed)
            save_checkpoint(ckpt)
            time.sleep(0.3)
            continue

        date_games = 0
        date_f5 = 0
        date_joined = 0

        for ev in events:
            event_id = ev["id"]
            home_full = ev["home_team"]
            away_full = ev["away_team"]
            commence = ev.get("commence_time", "")

            home_abbr = TEAM_NAME_MAP.get(home_full)
            away_abbr = TEAM_NAME_MAP.get(away_full)
            if not home_abbr or not away_abbr:
                logger.warning(f"Unknown team: {home_full} or {away_full}")
                continue

            # Get F5 odds
            result = get_f5_odds_for_event(event_id, dt_query)
            total_credits_session += 1
            time.sleep(0.5)

            if result is None:
                date_games += 1
                continue

            game_data, remaining = result
            bookmakers = game_data.get("bookmakers", [])
            canonical = pick_canonical_book(bookmakers)

            # Resolve game_pk
            game_pk, actual_f5 = resolve_game_pk(game_table, dt, home_abbr, away_abbr)

            row = {
                "date": dt,
                "game_id": game_pk or "",
                "home_team": home_abbr,
                "away_team": away_abbr,
                "game_time": commence[11:16] + " UTC" if len(commence) > 16 else "",
                "pull_timestamp": dt_query,
                "pull_type": "historical_backfill",
                "book_key": canonical["book_key"] if canonical else "",
                "f5_total": canonical["f5_total"] if canonical else None,
                "f5_over_price": canonical["f5_over_price"] if canonical else None,
                "f5_under_price": canonical["f5_under_price"] if canonical else None,
                "f5_moneyline_home": None,
                "f5_moneyline_away": None,
                "actual_f5_total": actual_f5,
                "is_canonical": True,
            }
            rows.append(row)
            date_games += 1
            if canonical:
                date_f5 += 1
            if game_pk:
                date_joined += 1

        total_games_session += date_games
        logger.info(
            f"{dt}: {date_games} games, {date_f5} with F5 lines, "
            f"{date_joined} joined to game_pk | credits_session={total_credits_session}"
        )

        # Checkpoint after each date
        completed.add(dt)
        ckpt["completed_dates"] = sorted(completed)
        ckpt["credits_used"] = ckpt.get("credits_used", 0) + date_games + 1  # +1 for events call
        ckpt["total_games"] = ckpt.get("total_games", 0) + date_games
        save_checkpoint(ckpt)

        # Save parquet periodically (every date)
        df = pd.DataFrame(rows)
        df.to_parquet(OUTPUT_PATH, index=False)

        if total_games_session % 50 == 0 and total_games_session > 0:
            logger.info(f"Progress: {total_games_session} games processed, {len(completed)} dates done")

        time.sleep(2)

    # Final save
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_parquet(OUTPUT_PATH, index=False)
        logger.info(f"Saved {len(df)} rows to {OUTPUT_PATH}")

        # Build combined file with 2026 live data
        build_combined(df)
    else:
        logger.info("No rows collected")

    logger.info(
        f"Backfill complete: {total_games_session} games, "
        f"{total_credits_session} API calls this session"
    )


def build_combined(historical_df: pd.DataFrame | None = None):
    """Combine historical backfill with 2026 live F5 lines."""
    live_path = PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_lines_2026.parquet"
    frames = []
    if historical_df is not None:
        frames.append(historical_df)
    elif OUTPUT_PATH.exists():
        frames.append(pd.read_parquet(OUTPUT_PATH))

    if live_path.exists():
        frames.append(pd.read_parquet(live_path))

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined.to_parquet(COMBINED_PATH, index=False)
        logger.info(f"Combined file: {len(combined)} rows saved to {COMBINED_PATH}")


def validate_sample():
    """Run 3-day validation sample and print results."""
    logger.info("=== VALIDATION RUN: April 15-17, 2024 ===")
    dry_dates = ["2024-04-15", "2024-04-16", "2024-04-17"]

    # Clear any previous validation output
    if OUTPUT_PATH.exists():
        os.rename(OUTPUT_PATH, str(OUTPUT_PATH) + ".bak")
    if CHECKPOINT_PATH.exists():
        os.remove(CHECKPOINT_PATH)

    backfill(seasons=[2024], dry_run_dates=dry_dates)

    if not OUTPUT_PATH.exists():
        logger.error("No output produced")
        return

    df = pd.read_parquet(OUTPUT_PATH)
    logger.info(f"\n{'='*60}")
    logger.info(f"VALIDATION RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total rows: {len(df)}")
    logger.info(f"Dates: {sorted(df['date'].unique())}")
    logger.info(f"Games with F5 lines: {df['f5_total'].notna().sum()}")
    logger.info(f"Games with game_pk: {(df['game_id'] != '').sum()}")
    logger.info(f"Book distribution: {df['book_key'].value_counts().to_dict()}")
    logger.info(f"F5 total range: {df['f5_total'].min()} - {df['f5_total'].max()}")

    # Schema check vs f5_lines_2026
    live_path = PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_lines_2026.parquet"
    if live_path.exists():
        live = pd.read_parquet(live_path)
        logger.info(f"\nSchema comparison:")
        logger.info(f"  Historical columns: {sorted(df.columns)}")
        logger.info(f"  Live 2026 columns:  {sorted(live.columns)}")
        missing = set(live.columns) - set(df.columns)
        extra = set(df.columns) - set(live.columns)
        if missing:
            logger.warning(f"  Missing columns: {missing}")
        if extra:
            logger.warning(f"  Extra columns: {extra}")
        if not missing and not extra:
            logger.info(f"  ✓ Schema matches perfectly")

    # Print sample
    logger.info(f"\nSample output (5 games):")
    sample = df[df["f5_total"].notna()].head(5)
    for _, r in sample.iterrows():
        logger.info(
            f"  {r['date']} {r['away_team']}@{r['home_team']} "
            f"F5={r['f5_total']} O{r['f5_over_price']}/U{r['f5_under_price']} "
            f"[{r['book_key']}] gpk={r['game_id']} actual={r['actual_f5_total']}"
        )

    # Restore backup if exists
    bak = str(OUTPUT_PATH) + ".bak"
    if os.path.exists(bak):
        os.rename(bak, OUTPUT_PATH)

    # Credit estimate
    ckpt = load_checkpoint()
    api_calls = ckpt.get("credits_used", 0)
    games_per_date = len(df) / len(dry_dates) if dry_dates else 0
    total_dates = sum(
        (SEASON_RANGES[s][1] - SEASON_RANGES[s][0]).days + 1 for s in [2023, 2024, 2025]
    )
    est_games = games_per_date * total_dates
    est_calls = est_games + total_dates  # +1 events call per date
    logger.info(f"\nCredit estimate:")
    logger.info(f"  Avg games/date: {games_per_date:.1f}")
    logger.info(f"  Total dates (3 seasons): {total_dates}")
    logger.info(f"  Estimated API calls: {est_calls:.0f}")
    logger.info(f"  Estimated credits: {est_calls * 10:.0f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="F5 Historical Line Backfill")
    parser.add_argument("--validate", action="store_true", help="Run 3-day validation sample")
    parser.add_argument("--full", action="store_true", help="Run full 2023-2025 backfill")
    parser.add_argument("--seasons", nargs="+", type=int, default=None,
                        help="Specific seasons to backfill (e.g. --seasons 2024 2025)")
    parser.add_argument("--combine-only", action="store_true",
                        help="Just rebuild the combined output file")
    args = parser.parse_args()

    if args.combine_only:
        build_combined()
    elif args.validate:
        validate_sample()
    elif args.full or args.seasons:
        seasons = args.seasons or [2023, 2024, 2025]
        logger.info(f"Starting full backfill for seasons: {seasons}")
        backfill(seasons=seasons)
    else:
        parser.print_help()
