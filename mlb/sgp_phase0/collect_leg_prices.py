#!/usr/bin/env python3
"""
SGP Phase 0 — Collect individual leg prices for hits O0.5 + TB O1.5/O2.5 pairs.
Same-book pairing enforced. STRUCTURAL_CONTAINMENT method.
"""
import json
import logging
import os
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("sgp_collect")

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

OUT_DIR = Path(__file__).resolve().parent / "leg_prices"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.the-odds-api.com/v4"
BOOK_PRIORITY = ["draftkings", "fanatics", "fanduel", "bovada", "betonlineag"]

try:
    from config import ODDS_API_KEY
except ImportError:
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")


def normalize_name(name):
    """Strip accents, Jr/Sr/III suffixes, normalize spacing."""
    if not name:
        return ""
    # Strip accents
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    # Strip suffixes
    for suffix in [" Jr.", " Sr.", " III", " II", " IV", " Jr", " Sr"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()


def american_to_implied(price):
    """Convert American odds to implied probability."""
    if price > 0:
        return 100 / (price + 100)
    elif price < 0:
        return abs(price) / (abs(price) + 100)
    return 0.5


def collect(game_date=None):
    """Collect leg prices for today's games."""
    if not ODDS_API_KEY:
        logger.error("No ODDS_API_KEY found")
        return pd.DataFrame()

    # Get events
    r = requests.get(f"{BASE_URL}/sports/baseball_mlb/events",
                     params={"apiKey": ODDS_API_KEY})
    if r.status_code != 200:
        logger.error(f"Events endpoint: HTTP {r.status_code}")
        return pd.DataFrame()

    events = r.json()
    if not events:
        logger.warning("No MLB events found")
        return pd.DataFrame()

    # Filter to today or specified date
    if game_date:
        target = game_date
    else:
        target = datetime.utcnow().strftime("%Y-%m-%d")

    today_events = [e for e in events if e.get("commence_time", "")[:10] == target]
    if not today_events:
        # Use first available date
        dates = sorted(set(e["commence_time"][:10] for e in events))
        if dates:
            target = dates[0]
            today_events = [e for e in events if e["commence_time"][:10] == target]
            logger.info(f"No games on {game_date or 'today'}, using {target} ({len(today_events)} games)")

    logger.info(f"Processing {len(today_events)} events for {target}")

    rows = []
    books_param = ",".join(BOOK_PRIORITY)

    for event in today_events:
        eid = event["id"]
        home = event.get("home_team", "")
        away = event.get("away_team", "")

        # Pull both markets in one call
        r = requests.get(
            f"{BASE_URL}/sports/baseball_mlb/events/{eid}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "batter_hits,batter_total_bases",
                "bookmakers": books_param,
                "oddsFormat": "american",
            })

        if r.status_code != 200:
            logger.warning(f"  {away}@{home}: HTTP {r.status_code}")
            time.sleep(2)
            continue

        data = r.json()
        bookmakers = data.get("bookmakers", [])

        # Parse all outcomes by book → player → market → (line, price)
        # Structure: book_data[book][normalized_name][(market, line)] = price
        book_data = {}
        for bm in bookmakers:
            bk = bm["key"]
            book_data[bk] = {}
            for mkt in bm.get("markets", []):
                mkt_key = mkt["key"]
                for out in mkt.get("outcomes", []):
                    if out.get("name") != "Over":
                        continue
                    player = normalize_name(out.get("description", ""))
                    point = out.get("point")
                    price = out.get("price")
                    if not player or point is None or price is None:
                        continue
                    if player not in book_data[bk]:
                        book_data[bk][player] = {}
                    book_data[bk][player][(mkt_key, point)] = price

        # Build pairs: same-book, priority order
        seen_players_a = set()
        seen_players_b = set()

        for book in BOOK_PRIORITY:
            if book not in book_data:
                continue
            for player, legs in book_data[book].items():
                hits_05 = legs.get(("batter_hits", 0.5))
                tb_15 = legs.get(("batter_total_bases", 1.5))
                tb_25 = legs.get(("batter_total_bases", 2.5))

                # Pair A: hits O0.5 + TB O1.5
                if hits_05 is not None and tb_15 is not None and player not in seen_players_a:
                    rows.append({
                        "date": target,
                        "game_id": eid,
                        "home_team": home,
                        "away_team": away,
                        "player_name": player,
                        "player_team": "",  # not available from odds API
                        "pair_type": "A",
                        "leg1_market": "batter_hits",
                        "leg1_line": 0.5,
                        "leg1_price": hits_05,
                        "leg1_implied_prob": round(american_to_implied(hits_05), 4),
                        "leg2_market": "batter_total_bases",
                        "leg2_line": 1.5,
                        "leg2_price": tb_15,
                        "leg2_implied_prob": round(american_to_implied(tb_15), 4),
                        "reference_book": book,
                        "cross_book_reference": False,
                        "pulled_at": datetime.utcnow().isoformat(),
                    })
                    seen_players_a.add(player)

                # Pair B: hits O0.5 + TB O2.5
                if hits_05 is not None and tb_25 is not None and player not in seen_players_b:
                    rows.append({
                        "date": target,
                        "game_id": eid,
                        "home_team": home,
                        "away_team": away,
                        "player_name": player,
                        "player_team": "",
                        "pair_type": "B",
                        "leg1_market": "batter_hits",
                        "leg1_line": 0.5,
                        "leg1_price": hits_05,
                        "leg1_implied_prob": round(american_to_implied(hits_05), 4),
                        "leg2_market": "batter_total_bases",
                        "leg2_line": 2.5,
                        "leg2_price": tb_25,
                        "leg2_implied_prob": round(american_to_implied(tb_25), 4),
                        "reference_book": book,
                        "cross_book_reference": False,
                        "pulled_at": datetime.utcnow().isoformat(),
                    })
                    seen_players_b.add(player)

        logger.info(f"  {away}@{home}: {len([r for r in rows if r['game_id']==eid])} pairs")
        time.sleep(2)

    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("No pairs collected")
        return df

    # Save daily
    daily_path = OUT_DIR / f"leg_prices_{target.replace('-','_')}.parquet"
    df.to_parquet(daily_path, index=False)
    logger.info(f"Saved: {daily_path} ({len(df)} rows)")

    # Append to archive
    archive_path = OUT_DIR / "leg_prices_archive.parquet"
    if archive_path.exists():
        existing = pd.read_parquet(archive_path)
        existing = existing[existing["date"] != target]
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.to_parquet(archive_path, index=False)

    # Summary
    n_a = len(df[df["pair_type"] == "A"])
    n_b = len(df[df["pair_type"] == "B"])
    books = sorted(df["reference_book"].unique())
    players = df["player_name"].nunique()
    logger.info(f"Summary: {players} players, Pair A={n_a}, Pair B={n_b}, books={books}")

    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    collect(args.date)
