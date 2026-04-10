#!/usr/bin/env python3
"""
MLB Historical Odds Backfill (2022-2025)
=========================================
One-time comprehensive pull of all MLB closing lines from Odds API historical
endpoint before downgrading API tier.

Markets per game (single API call):
  h2h, spreads, totals, alternate_totals, team_totals

Architecture mirrors backfill_f5_lines_historical.py:
  historical/events → event IDs → historical/events/{id}/odds per game

FUTURE: NHL h2h, spreads, totals 2022-2026
FUTURE: NBA h2h, spreads 2022-2026
FUTURE: NCAAF totals, spreads, h2h 2022-2025
FUTURE: Soccer h2h, totals 2022-2026
FUTURE: NFL totals, spreads, h2h 2022-2025
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
        logging.FileHandler(LOG_DIR / "odds_backfill.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("odds_backfill")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_BASE = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb"
QUERY_HOUR = "16:00:00Z"  # noon ET — pre-game, catches closing lines
MARKETS = "h2h,spreads,totals,alternate_totals,team_totals"

BOOK_PRIORITY = [
    "pinnacle", "draftkings", "fanduel", "bovada", "betonlineag",
    "betmgm", "betus", "williamhill_us", "lowvig", "mybookieag",
    "betrivers", "wynnbet", "hardrockbet",
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
    "Cleveland Indians": "CLE",
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
    2022: (date(2022, 4, 7), date(2022, 10, 5)),
    2023: (date(2023, 3, 30), date(2023, 10, 2)),
    2024: (date(2024, 3, 28), date(2024, 9, 30)),
    2025: (date(2025, 3, 27), date(2025, 9, 29)),
}

CANONICAL_PATH = PROJECT_ROOT / "mlb_sim" / "data" / "mlb_odds_closing_canonical.parquet"
ALT_TOTALS_PATH = PROJECT_ROOT / "mlb_sim" / "data" / "mlb_alt_totals_historical.parquet"
CHECKPOINT_PATH = PROJECT_ROOT / "mlb_sim" / "data" / "odds_backfill_progress.json"
GAME_TABLE_PATH = PROJECT_ROOT / "sim" / "data" / "game_table.parquet"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"completed_dates": [], "credits_used": 0, "games_processed": 0,
            "last_updated": ""}


def save_checkpoint(ckpt: dict):
    ckpt["last_updated"] = pd.Timestamp.now().isoformat()
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(ckpt, f, indent=2)


def load_game_table() -> pd.DataFrame:
    if not GAME_TABLE_PATH.exists():
        logger.warning("game_table.parquet not found — game_pk join skipped")
        return pd.DataFrame()
    gt = pd.read_parquet(GAME_TABLE_PATH)
    gt["date"] = gt["date"].astype(str)
    gt["game_pk"] = gt["game_pk"].astype(str)
    return gt


def resolve_game_pk(game_table: pd.DataFrame, game_date: str,
                    home_abbr: str, away_abbr: str) -> str | None:
    if game_table.empty:
        return None
    mask = (
        (game_table["date"] == game_date) &
        (game_table["home_team"] == home_abbr) &
        (game_table["away_team"] == away_abbr)
    )
    matches = game_table[mask]
    if len(matches) >= 1:
        return str(matches.iloc[0]["game_pk"])
    return None


def get_events_for_date(dt_str: str) -> list[dict]:
    r = requests.get(f"{API_BASE}/events", params={
        "apiKey": ODDS_API_KEY,
        "date": dt_str,
    }, timeout=20)
    if r.status_code != 200:
        logger.warning(f"Events HTTP {r.status_code} for {dt_str}: {r.text[:100]}")
        return []
    return r.json().get("data", [])


def get_odds_for_event(event_id: str, dt_str: str) -> tuple[dict, str] | None:
    r = requests.get(f"{API_BASE}/events/{event_id}/odds", params={
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": MARKETS,
        "oddsFormat": "american",
        "date": dt_str,
    }, timeout=20)
    remaining = r.headers.get("x-requests-remaining", "?")
    if r.status_code != 200:
        return None
    return r.json().get("data", {}), remaining


def american_to_implied(price: float) -> float:
    """Convert American odds to raw implied probability."""
    if price is None:
        return None
    if price > 0:
        return 100.0 / (price + 100.0)
    else:
        return abs(price) / (abs(price) + 100.0)


def devig_pair(price_a: float, price_b: float) -> tuple[float, float]:
    """De-vig two American prices into fair probabilities."""
    raw_a = american_to_implied(price_a)
    raw_b = american_to_implied(price_b)
    if raw_a is None or raw_b is None:
        return None, None
    total = raw_a + raw_b
    if total == 0:
        return None, None
    return raw_a / total, raw_b / total


# ---------------------------------------------------------------------------
# Market extraction
# ---------------------------------------------------------------------------

def _find_market(bookmaker: dict, market_key: str) -> dict | None:
    for m in bookmaker.get("markets", []):
        if m["key"] == market_key:
            return m
    return None


def _outcome_by_name(market: dict, name: str) -> dict | None:
    for o in market.get("outcomes", []):
        if o["name"] == name:
            return o
    return None


def extract_canonical(bookmakers: list[dict], home_full: str, away_full: str) -> dict | None:
    """Extract canonical row from best-priority book with h2h data."""
    for bk in BOOK_PRIORITY:
        book = next((b for b in bookmakers if b["key"] == bk), None)
        if book is None:
            continue

        # Must have at least h2h
        h2h = _find_market(book, "h2h")
        if h2h is None:
            continue

        home_ml_o = _outcome_by_name(h2h, home_full)
        away_ml_o = _outcome_by_name(h2h, away_full)
        if home_ml_o is None or away_ml_o is None:
            continue

        ml_home = home_ml_o.get("price")
        ml_away = away_ml_o.get("price")
        ml_home_imp, ml_away_imp = devig_pair(ml_home, ml_away)

        # Spreads (run-line)
        spreads = _find_market(book, "spreads")
        rl_home_line = rl_home_price = rl_away_line = rl_away_price = None
        if spreads:
            home_sp = _outcome_by_name(spreads, home_full)
            away_sp = _outcome_by_name(spreads, away_full)
            if home_sp:
                rl_home_line = home_sp.get("point")
                rl_home_price = home_sp.get("price")
            if away_sp:
                rl_away_line = away_sp.get("point")
                rl_away_price = away_sp.get("price")

        # Totals
        totals = _find_market(book, "totals")
        total_line = total_over = total_under = None
        if totals:
            over_o = _outcome_by_name(totals, "Over")
            under_o = _outcome_by_name(totals, "Under")
            if over_o:
                total_line = over_o.get("point")
                total_over = over_o.get("price")
            if under_o:
                total_under = under_o.get("price")

        # Team totals
        tt = _find_market(book, "team_totals")
        ht_line = ht_over = ht_under = None
        at_line = at_over = at_under = None
        if tt:
            for o in tt.get("outcomes", []):
                desc = o.get("description", "")
                if desc == home_full:
                    if o["name"] == "Over":
                        ht_line = o.get("point")
                        ht_over = o.get("price")
                    elif o["name"] == "Under":
                        ht_under = o.get("price")
                elif desc == away_full:
                    if o["name"] == "Over":
                        at_line = o.get("point")
                        at_over = o.get("price")
                    elif o["name"] == "Under":
                        at_under = o.get("price")

        return {
            "book_key": bk,
            "ml_home_price": ml_home,
            "ml_away_price": ml_away,
            "ml_home_implied": ml_home_imp,
            "ml_away_implied": ml_away_imp,
            "rl_home_line": rl_home_line,
            "rl_home_price": rl_home_price,
            "rl_away_line": rl_away_line,
            "rl_away_price": rl_away_price,
            "total_line": total_line,
            "total_over_price": total_over,
            "total_under_price": total_under,
            "home_total_line": ht_line,
            "home_total_over_price": ht_over,
            "home_total_under_price": ht_under,
            "away_total_line": at_line,
            "away_total_over_price": at_over,
            "away_total_under_price": at_under,
        }

    return None


def extract_alt_totals(bookmakers: list[dict], total_line: float | None) -> list[dict]:
    """Extract alt-total ladder points from all books."""
    rows = []
    for book in bookmakers:
        at = _find_market(book, "alternate_totals")
        if at is None:
            continue
        # Group outcomes by point value to pair over/under
        by_point = {}
        for o in at.get("outcomes", []):
            pt = o.get("point")
            if pt is None:
                continue
            if pt not in by_point:
                by_point[pt] = {}
            by_point[pt][o["name"]] = o.get("price")

        for pt, prices in sorted(by_point.items()):
            rows.append({
                "book_key": book["key"],
                "line_value": pt,
                "over_price": prices.get("Over"),
                "under_price": prices.get("Under"),
                "ladder_distance": round(pt - total_line, 1) if total_line else None,
            })
    return rows


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------

def backfill(seasons: list[int] | None = None,
             dry_run_dates: list[str] | None = None):
    ckpt = load_checkpoint()
    completed = set(ckpt["completed_dates"])
    game_table = load_game_table()

    canonical_rows = []
    alt_rows = []

    # Load existing if resuming
    if not dry_run_dates and CANONICAL_PATH.exists():
        existing = pd.read_parquet(CANONICAL_PATH)
        canonical_rows = existing.to_dict("records")
        logger.info(f"Resuming with {len(canonical_rows)} existing canonical rows")
    if not dry_run_dates and ALT_TOTALS_PATH.exists():
        existing_alt = pd.read_parquet(ALT_TOTALS_PATH)
        alt_rows = existing_alt.to_dict("records")
        logger.info(f"Resuming with {len(alt_rows)} existing alt-total rows")

    if seasons is None:
        seasons = [2022, 2023, 2024, 2025]

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

    logger.info(f"Dates to process: {len(dates_to_process)} "
                f"(skipping {len(completed)} already done)")
    total_api_calls = 0
    total_games = 0

    for idx, (dt, season) in enumerate(dates_to_process):
        dt_query = f"{dt}T{QUERY_HOUR}"
        events = get_events_for_date(dt_query)
        total_api_calls += 1

        if not events:
            logger.info(f"{dt}: 0 events")
            completed.add(dt)
            ckpt["completed_dates"] = sorted(completed)
            save_checkpoint(ckpt)
            time.sleep(0.3)
            continue

        date_canonical = 0
        date_alt = 0
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

            result = get_odds_for_event(event_id, dt_query)
            total_api_calls += 1
            time.sleep(0.3)

            if result is None:
                total_games += 1
                continue

            game_data, remaining = result
            bookmakers = game_data.get("bookmakers", [])

            canonical = extract_canonical(bookmakers, home_full, away_full)
            if canonical is None:
                total_games += 1
                continue

            game_pk = resolve_game_pk(game_table, dt, home_abbr, away_abbr)

            row = {
                "date": dt,
                "season": season,
                "game_pk": game_pk or "",
                "home_team": home_abbr,
                "away_team": away_abbr,
                "pull_timestamp": dt_query,
                **canonical,
            }
            canonical_rows.append(row)
            date_canonical += 1
            if game_pk:
                date_joined += 1

            # Alt totals
            alt_points = extract_alt_totals(bookmakers, canonical.get("total_line"))
            for ap in alt_points:
                alt_rows.append({
                    "date": dt,
                    "season": season,
                    "game_pk": game_pk or "",
                    "home_team": home_abbr,
                    "away_team": away_abbr,
                    **ap,
                })
            if alt_points:
                date_alt += 1

            total_games += 1

        logger.info(
            f"{dt}: {len(events)} events, {date_canonical} canonical, "
            f"{date_alt} with alt-totals, {date_joined} joined | "
            f"api_calls={total_api_calls}"
        )

        # Checkpoint
        completed.add(dt)
        ckpt["completed_dates"] = sorted(completed)
        ckpt["credits_used"] = ckpt.get("credits_used", 0) + len(events) + 1
        ckpt["games_processed"] = ckpt.get("games_processed", 0) + date_canonical
        save_checkpoint(ckpt)

        # Save every 5 dates
        if len(completed) % 5 == 0:
            if canonical_rows:
                pd.DataFrame(canonical_rows).to_parquet(CANONICAL_PATH, index=False)
            if alt_rows:
                pd.DataFrame(alt_rows).to_parquet(ALT_TOTALS_PATH, index=False)

        if total_games % 100 == 0 and total_games > 0:
            logger.info(f"Progress: {total_games} games, {len(completed)} dates, "
                        f"{len(canonical_rows)} canonical, {len(alt_rows)} alt rows")

        time.sleep(1.0)

    # Final save
    if canonical_rows:
        df = pd.DataFrame(canonical_rows)
        df.to_parquet(CANONICAL_PATH, index=False)
        logger.info(f"Saved {len(df)} canonical rows to {CANONICAL_PATH}")
    if alt_rows:
        df_alt = pd.DataFrame(alt_rows)
        df_alt.to_parquet(ALT_TOTALS_PATH, index=False)
        logger.info(f"Saved {len(df_alt)} alt-total rows to {ALT_TOTALS_PATH}")

    logger.info(f"Backfill complete: {total_games} games, {total_api_calls} API calls")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_sample():
    logger.info("=== VALIDATION RUN: June 15-17, 2024 ===")
    dry_dates = ["2024-06-15", "2024-06-16", "2024-06-17"]

    # Stash existing outputs
    for p in [CANONICAL_PATH, ALT_TOTALS_PATH, CHECKPOINT_PATH]:
        if p.exists():
            os.rename(p, str(p) + ".bak")

    backfill(seasons=[2024], dry_run_dates=dry_dates)

    if not CANONICAL_PATH.exists():
        logger.error("No output produced")
        return

    df = pd.read_parquet(CANONICAL_PATH)
    logger.info(f"\n{'='*60}")
    logger.info("VALIDATION RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Canonical rows: {len(df)}")
    logger.info(f"Dates: {sorted(df['date'].unique())}")

    # Market coverage
    has_ml = df["ml_home_price"].notna().sum()
    has_rl = df["rl_home_line"].notna().sum()
    has_tot = df["total_line"].notna().sum()
    has_ht = df["home_total_line"].notna().sum()
    has_gpk = (df["game_pk"] != "").sum()
    logger.info(f"Market coverage:")
    logger.info(f"  h2h (ML):      {has_ml}/{len(df)} ({100*has_ml/len(df):.0f}%)")
    logger.info(f"  spreads (RL):  {has_rl}/{len(df)} ({100*has_rl/len(df):.0f}%)")
    logger.info(f"  totals:        {has_tot}/{len(df)} ({100*has_tot/len(df):.0f}%)")
    logger.info(f"  team_totals:   {has_ht}/{len(df)} ({100*has_ht/len(df):.0f}%)")
    logger.info(f"  game_pk join:  {has_gpk}/{len(df)} ({100*has_gpk/len(df):.0f}%)")
    logger.info(f"Book distribution: {df['book_key'].value_counts().to_dict()}")

    # Alt totals
    if ALT_TOTALS_PATH.exists():
        alt = pd.read_parquet(ALT_TOTALS_PATH)
        games_with_alt = alt["game_pk"].nunique() if "game_pk" in alt.columns else alt.groupby(["date", "home_team"]).ngroups
        logger.info(f"Alt-total rows: {len(alt)}")
        logger.info(f"  Games with alt-totals: {games_with_alt}")
        logger.info(f"  Avg ladder points/game: {len(alt)/games_with_alt:.1f}" if games_with_alt > 0 else "")
        logger.info(f"  Books: {alt['book_key'].nunique()}")
        logger.info(f"  Line range: {alt['line_value'].min()} - {alt['line_value'].max()}")

    # Sample output
    logger.info(f"\nSample output (3 games, all markets):")
    for _, r in df.head(3).iterrows():
        logger.info(
            f"  {r['date']} {r['away_team']}@{r['home_team']} [{r['book_key']}] "
            f"gpk={r['game_pk']}"
        )
        logger.info(
            f"    ML: home={r['ml_home_price']} away={r['ml_away_price']} "
            f"(impl: {r['ml_home_implied']:.3f}/{r['ml_away_implied']:.3f})"
        )
        logger.info(
            f"    RL: home {r['rl_home_line']}@{r['rl_home_price']} / "
            f"away {r['rl_away_line']}@{r['rl_away_price']}"
        )
        logger.info(
            f"    Total: {r['total_line']} O{r['total_over_price']}/U{r['total_under_price']}"
        )
        logger.info(
            f"    TT: home {r['home_total_line']} O{r['home_total_over_price']}"
            f"/U{r['home_total_under_price']} | "
            f"away {r['away_total_line']} O{r['away_total_over_price']}"
            f"/U{r['away_total_under_price']}"
        )

    # Schema
    logger.info(f"\nSchema ({len(df.columns)} columns):")
    logger.info(f"  {sorted(df.columns)}")

    # Credit estimate
    games_per_date = len(df) / len(dry_dates)
    total_dates = sum(
        (SEASON_RANGES[s][1] - SEASON_RANGES[s][0]).days + 1
        for s in [2022, 2023, 2024, 2025]
    )
    est_calls = games_per_date * total_dates + total_dates  # games + events calls
    logger.info(f"\nCredit estimate (full 4-season run):")
    logger.info(f"  Avg games/date: {games_per_date:.1f}")
    logger.info(f"  Total dates: {total_dates}")
    logger.info(f"  Estimated API calls: {est_calls:.0f}")
    logger.info(f"  Estimated credits (~10/call): {est_calls * 10:.0f}")

    # Restore backups
    for p in [CANONICAL_PATH, ALT_TOTALS_PATH, CHECKPOINT_PATH]:
        bak = str(p) + ".bak"
        if os.path.exists(bak):
            if p.exists():
                os.remove(p)
            os.rename(bak, p)
        elif p.exists():
            os.remove(p)


def combine():
    """Merge historical canonical with any existing partial data."""
    if not CANONICAL_PATH.exists():
        logger.error(f"{CANONICAL_PATH} not found")
        return
    df = pd.read_parquet(CANONICAL_PATH)
    logger.info(f"Canonical: {len(df)} rows, seasons {sorted(df['season'].unique())}")

    # Merge with existing market_snapshots totals (2024-2025)
    ms_path = PROJECT_ROOT / "sim" / "data" / "market_snapshots.parquet"
    if ms_path.exists():
        ms = pd.read_parquet(ms_path)
        logger.info(f"Existing market_snapshots: {len(ms)} rows "
                    f"({ms['date'].min()} - {ms['date'].max()})")
    logger.info("Combined output ready — no merge needed (separate schemas)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MLB Historical Odds Backfill")
    parser.add_argument("--validate", action="store_true",
                        help="3-day validation (Jun 15-17, 2024)")
    parser.add_argument("--full", action="store_true",
                        help="Full 2022-2025 backfill")
    parser.add_argument("--season", type=int, default=None,
                        help="Single season (e.g. --season 2024)")
    parser.add_argument("--combine", action="store_true",
                        help="Merge partial data")
    args = parser.parse_args()

    if args.validate:
        validate_sample()
    elif args.full:
        backfill(seasons=[2022, 2023, 2024, 2025])
    elif args.season:
        backfill(seasons=[args.season])
    elif args.combine:
        combine()
    else:
        parser.print_help()
