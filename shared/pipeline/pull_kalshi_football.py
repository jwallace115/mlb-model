#!/usr/bin/env python3
"""
WO10 Item 3: Pull Kalshi NFL or NCAAF game markets (moneyline, spread, total).

Public market data, NO authentication required.
Base: https://api.elections.kalshi.com/trade-api/v2

Output (parquet, append-only):
  data/odds_archive/kalshi/nfl/season=2026/snap_<UTC>.parquet
  data/odds_archive/kalshi/ncaaf/season=2026/snap_<UTC>.parquet

Price scale: DOLLARS (0.00-1.00), matching the API field names (*_dollars).
"""

import argparse, sys, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

SERIES = {
    "nfl": ["KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL"],
    "ncaaf": ["KXNCAAFGAME", "KXNCAAFSPREAD", "KXNCAAFTOTAL"],
}

KEEP_FIELDS = [
    "ticker", "event_ticker", "title", "yes_sub_title", "no_sub_title",
    "yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars",
    "last_price_dollars", "previous_price_dollars",
    "volume_fp", "volume_24h_fp", "open_interest_fp", "liquidity_dollars",
    "open_time", "close_time", "expected_expiration_time",
    "occurrence_datetime", "status", "market_type",
]


def pull_series(series_ticker):
    """Pull all open markets for a series, following cursor pagination."""
    all_markets = []
    cursor = None
    page = 0

    while True:
        params = {
            "series_ticker": series_ticker,
            "status": "open",
            "limit": 1000,
        }
        if cursor:
            params["cursor"] = cursor

        try:
            r = requests.get(f"{KALSHI_BASE}/markets", params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  HALT: request error for {series_ticker}: {e}")
            sys.exit(1)

        if r.status_code != 200:
            print(f"  HALT: {series_ticker} HTTP {r.status_code}: {r.text[:120]}")
            sys.exit(1)

        data = r.json()
        markets = data.get("markets", [])

        if not markets and page == 0:
            print(f"  {series_ticker}: 0 markets (empty)")
            return []

        all_markets.extend(markets)
        page += 1

        next_cursor = data.get("cursor", "")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.25)

    print(f"  {series_ticker}: {len(all_markets)} markets, {page} page(s)")
    return all_markets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", required=True, choices=["nfl", "ncaaf"])
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    ts_label = now.strftime("%Y%m%dT%H%MZ")
    print(f"pull_kalshi_football --sport {args.sport} ts={ts_label}")

    t0 = time.time()
    all_rows = []

    for series_ticker in SERIES[args.sport]:
        markets = pull_series(series_ticker)
        for m in markets:
            row = {"pull_timestamp": now.isoformat(), "series_ticker": series_ticker}
            for field in KEEP_FIELDS:
                row[field] = m.get(field)
            all_rows.append(row)

    elapsed = time.time() - t0

    if not all_rows:
        print(f"HALT: no markets found for {args.sport}")
        sys.exit(1)

    df = pd.DataFrame(all_rows)

    # Report zero-volume share
    vol = pd.to_numeric(df["volume_fp"], errors="coerce").fillna(0)
    zero_vol = (vol == 0).sum()
    print(f"  total rows: {len(df)}, zero volume: {zero_vol} ({zero_vol/len(df)*100:.0f}%)")

    # Save
    out_dir = (ROOT / "data" / "odds_archive" / "kalshi" / args.sport
               / f"season={args.season}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"snap_{ts_label}.parquet"

    df.to_parquet(out_path, index=False)
    size_kb = out_path.stat().st_size / 1024
    print(f"  saved to {out_path} ({size_kb:.0f} KB)")
    print(f"  elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
