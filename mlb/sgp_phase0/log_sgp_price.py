#!/usr/bin/env python3
"""
SGP Phase 0 — Manual SGP price logger.
Logs book SGP prices and computes edge vs fair (TB standalone) price.

Usage:
  python log_sgp_price.py --date 2026-03-30 --player "Bobby Witt" --pair A --book hardrock --sgp_price -145
  python log_sgp_price.py --date 2026-03-30 --player "Bobby Witt" --pair A --book hardrock --sgp_price -145 --same_book_tb -160
"""
import argparse
import json
import logging
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("sgp_log")

BASE_DIR = Path(__file__).resolve().parent
FAIR_DIR = BASE_DIR / "fair_prices"
LOG_PATH = BASE_DIR / "sgp_manual_log.json"


def normalize_name(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    for suffix in [" Jr.", " Sr.", " III", " II", " IV", " Jr", " Sr"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()


def american_to_implied(price):
    if price > 0:
        return 100 / (price + 100)
    elif price < 0:
        return abs(price) / (abs(price) + 100)
    return 0.5


def american_to_decimal(price):
    if price > 0:
        return (price / 100) + 1
    elif price < 0:
        return (100 / abs(price)) + 1
    return 2.0


def log_price(date, player, pair, book, sgp_price, same_book_tb=None):
    """Log a manually observed SGP price and compute edge."""

    fair_path = FAIR_DIR / f"fair_sgp_{date.replace('-','_')}.parquet"
    if not fair_path.exists():
        logger.error(f"No fair price file for {date}. Run fair_sgp_calculator.py first.")
        return

    df = pd.read_parquet(fair_path)
    norm_player = normalize_name(player)

    # Match player + pair
    mask = (df["player_name"].apply(normalize_name) == norm_player) & (df["pair_type"] == pair)
    matches = df[mask]

    if matches.empty:
        logger.error(f"No match for player='{norm_player}', pair={pair} on {date}")
        logger.info(f"Available players: {sorted(df['player_name'].unique())[:10]}")
        return

    idx = matches.index[0]

    # Compute SGP implied prob
    sgp_impl = round(american_to_implied(sgp_price), 4)
    decimal_odds = round(american_to_decimal(sgp_price), 4)

    # Determine fair price source
    if same_book_tb is not None:
        # Same-book comparison: fair = same book's TB standalone
        tb_impl = round(american_to_implied(same_book_tb), 4)
        fair_prob = tb_impl
        df.at[idx, "same_book_tb_price"] = same_book_tb
        df.at[idx, "same_book_tb_implied_prob"] = tb_impl
        df.at[idx, "same_book_comparison"] = True
        df.at[idx, "reference_book_mismatch"] = False
        df.at[idx, "fair_combined_prob"] = tb_impl
        df.at[idx, "fair_american_odds"] = same_book_tb
    else:
        # Use API reference book TB price
        fair_prob = df.at[idx, "fair_combined_prob"]
        df.at[idx, "same_book_comparison"] = False
        ref_book = df.at[idx, "reference_book"]
        df.at[idx, "reference_book_mismatch"] = (book.lower() != ref_book)

    edge = round(fair_prob - sgp_impl, 4)  # positive = book charges more than fair
    excess_hold = round(sgp_impl - fair_prob, 4)  # positive = book extracts hold
    ev = round(fair_prob * (decimal_odds - 1) - (1 - fair_prob), 4)

    df.at[idx, "book_sgp_price"] = sgp_price
    df.at[idx, "book_sgp_implied_prob"] = sgp_impl
    df.at[idx, "decimal_odds_book"] = decimal_odds
    df.at[idx, "edge"] = edge
    df.at[idx, "excess_hold"] = excess_hold
    df.at[idx, "ev_per_unit"] = ev

    df.to_parquet(fair_path, index=False)

    # Print result
    row = df.loc[idx]
    tb_label = f"Same-book TB: {same_book_tb} ({american_to_implied(same_book_tb)*100:.1f}%)" if same_book_tb else f"API ref TB: {row['leg2_price']} ({row['leg2_implied_prob']*100:.1f}%)"
    print(f"\n  Player: {row['player_name']}")
    print(f"  Pair: {pair} ({'Hits O0.5 + TB O1.5' if pair == 'A' else 'Hits O0.5 + TB O2.5'})")
    print(f"  {tb_label}")
    print(f"  Fair SGP price: {row['fair_american_odds']} ({fair_prob*100:.1f}%)")
    print(f"  Book SGP price: {sgp_price} ({sgp_impl*100:.1f}%)")
    print(f"  Excess hold: {excess_hold*100:+.1f}pp ({'book extracts hold' if excess_hold > 0 else 'potential value'})")
    print(f"  EV per unit: {ev:+.3f}")

    # Append to manual log
    entry = {
        "date": date,
        "player": row["player_name"],
        "pair": pair,
        "book": book,
        "book_sgp_price": sgp_price,
        "book_sgp_implied_prob": sgp_impl,
        "same_book_tb_price": same_book_tb,
        "same_book_tb_implied_prob": american_to_implied(same_book_tb) if same_book_tb else None,
        "same_book_comparison": same_book_tb is not None,
        "reference_book_mismatch": book.lower() != row["reference_book"] if same_book_tb is None else False,
        "fair_combined_prob": fair_prob,
        "fair_american_odds": int(row["fair_american_odds"]),
        "edge": edge,
        "excess_hold": excess_hold,
        "ev_per_unit": ev,
        "result": None,
        "logged_at": datetime.utcnow().isoformat(),
    }

    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except:
            log = []
    log.append(entry)
    LOG_PATH.write_text(json.dumps(log, indent=2))
    logger.info(f"Appended to {LOG_PATH}")

    # Rebuild summary tracker
    from mlb.sgp_phase0.update_summary_tracker import rebuild
    rebuild()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--pair", required=True, choices=["A", "B"])
    parser.add_argument("--book", required=True)
    parser.add_argument("--sgp_price", required=True, type=int)
    parser.add_argument("--same_book_tb", type=int, default=None)
    args = parser.parse_args()
    log_price(args.date, args.player, args.pair, args.book, args.sgp_price, args.same_book_tb)
