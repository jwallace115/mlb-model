#!/usr/bin/env python3
"""Targeted retry for YRFI lines with corrected snapshot timing."""

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("yrfi_retry")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

LINES_PATH = PROJECT / "research" / "yrfi" / "data" / "yrfi_lines_historical.parquet"

with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
ODDS_BASE = "https://api.the-odds-api.com/v4"

ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)


def _get_commence_hour(game_id):
    gft = ft[ft["game_pk"] == str(game_id)]
    if len(gft) > 0:
        return int(gft.iloc[0].get("game_hour_utc", 20))
    return 20


def _extract_yrfi(bookmakers):
    """Extract YRFI/NRFI from bookmakers. Only 0.5 lines."""
    valid = []
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "totals_1st_1_innings":
                continue
            over_p = under_p = None
            for oc in mkt.get("outcomes", []):
                if oc.get("point") != 0.5:
                    continue
                if oc["name"] == "Over":
                    over_p = oc["price"]
                elif oc["name"] == "Under":
                    under_p = oc["price"]
            if over_p is not None and under_p is not None:
                valid.append({"book": bk_key, "over": over_p, "under": under_p})

    if not valid:
        return None, None, None, 0

    fd = [v for v in valid if v["book"] == "fanduel"]
    if fd:
        chosen = fd[0]
    else:
        med_over = int(np.median([v["over"] for v in valid]))
        med_under = int(np.median([v["under"] for v in valid]))
        chosen = min(valid, key=lambda v: abs(v["over"] - med_over) + abs(v["under"] - med_under))

    return chosen["over"], chosen["under"], chosen["book"], len(valid)


def _try_snapshot(eid, snap):
    """Single API call. Returns (bookmakers, timestamp) or (None, None)."""
    url = f"{ODDS_BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
    params = {
        "apiKey": API_KEY, "regions": "us",
        "markets": "totals_1st_1_innings",
        "oddsFormat": "american", "date": snap,
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                data = r.json()
                inner = data.get("data", data)
                return inner.get("bookmakers", []), data.get("timestamp", ""), r
            elif r.status_code == 429:
                logger.warning("429 — waiting 65s")
                time.sleep(65)
            elif r.status_code == 422:
                return [], "", r
            else:
                time.sleep(2)
        except Exception:
            time.sleep(2)
    return None, None, None


def main():
    df = pd.read_parquet(LINES_PATH)

    logger.info("YRFI RETRY — CORRECTED SNAPSHOT TIMING")
    logger.info("=" * 60)
    logger.info(f"Total rows: {len(df)}")
    logger.info(f"Status: {df['pull_status'].value_counts().to_dict()}")

    # Targets: api_error or no_market
    targets = df[df["pull_status"].isin(["api_error", "no_market"])].copy()
    logger.info(f"Retry targets: {len(targets)}")

    recovered = 0
    confirmed_no_mkt = 0
    errors_final = 0
    invalid_line = 0

    for i, (idx, row) in enumerate(targets.iterrows()):
        gid = str(row["game_id"])
        eid = row["odds_api_event_id"]
        gdate = str(row["date"])

        # Skip if already updated to ok in a prior resume
        if df.at[idx, "pull_status"] == "ok":
            continue

        hour_utc = _get_commence_hour(gid)
        is_west = hour_utc >= 24 or hour_utc < 6

        # Build snapshot candidates
        snapshots = []
        if is_west:
            # West Coast primary: next day T03:00Z
            next_day = (datetime.strptime(gdate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            snapshots.append(f"{next_day}T03:00:00Z")
        else:
            ct = datetime.strptime(gdate, "%Y-%m-%d") + timedelta(hours=hour_utc)
            # T-30min
            snapshots.append((ct - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))
            # T-15min
            snapshots.append((ct - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"))

        found = False
        last_r = None
        for snap in snapshots:
            bks, timestamp, r = _try_snapshot(eid, snap)
            last_r = r

            if bks is None:
                # Total failure
                continue

            if bks:
                over_p, under_p, book, n_books = _extract_yrfi(bks)
                if over_p is not None:
                    df.at[idx, "yrfi_over_price"] = over_p
                    df.at[idx, "nrfi_under_price"] = under_p
                    df.at[idx, "yrfi_line"] = 0.5
                    df.at[idx, "primary_book"] = book
                    df.at[idx, "books_count"] = n_books
                    df.at[idx, "snapshot_timestamp"] = timestamp
                    df.at[idx, "pull_status"] = "ok"
                    recovered += 1
                    found = True
                    break
                else:
                    # Bookmakers present but no valid 0.5 line — check for 1.5
                    has_any = False
                    for bk in bks:
                        for mkt in bk.get("markets", []):
                            if mkt["key"] == "totals_1st_1_innings":
                                for oc in mkt.get("outcomes", []):
                                    if oc.get("point") is not None:
                                        has_any = True
                    if has_any:
                        df.at[idx, "pull_status"] = "invalid_line"
                        df.at[idx, "snapshot_timestamp"] = timestamp
                        invalid_line += 1
                        found = True
                        break

            time.sleep(0.5)

        if not found:
            if last_r is None:
                df.at[idx, "pull_status"] = "api_error_final"
                errors_final += 1
            else:
                df.at[idx, "pull_status"] = "no_market_confirmed"
                confirmed_no_mkt += 1

        if (i + 1) % 100 == 0 or (i + 1) == len(targets):
            credits = last_r.headers.get("x-requests-remaining", "?") if last_r else "?"
            logger.info(f"  Progress: {i+1}/{len(targets)} | recovered={recovered} "
                        f"no_mkt={confirmed_no_mkt} err={errors_final} invalid={invalid_line} | "
                        f"credits={credits}")
            df.to_parquet(LINES_PATH, index=False)

        time.sleep(0.5)

    df.to_parquet(LINES_PATH, index=False)
    logger.info(f"\nRetry complete: recovered={recovered}, no_market_confirmed={confirmed_no_mkt}, "
                f"api_error_final={errors_final}, invalid_line={invalid_line}")

    # Coverage report
    logger.info("\n" + "=" * 60)
    logger.info("UPDATED COVERAGE")
    logger.info("=" * 60)

    status = df["pull_status"].value_counts()
    logger.info(f"Status breakdown: {status.to_dict()}")

    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_ok = len(df[(df["pull_status"] == "ok") & (df["date"].str[:4] == str(year))])
        pct = n_ok / total * 100
        flag = "" if pct >= 75 else " *** LOW"
        logger.info(f"  {year}: {n_ok}/{total} ({pct:.1f}%){flag}")

    logger.info(f"\n  Rows recovered: {recovered}")

    # Missing diagnostics if below 75%
    missing = df[~df["pull_status"].isin(["ok"])]
    if len(missing) > 0:
        logger.info(f"\n  Missing games diagnostics ({len(missing)} games):")

        # Top teams
        home_c = missing["home_team"].value_counts()
        away_c = missing["away_team"].value_counts()
        team_t = (home_c.add(away_c, fill_value=0)).sort_values(ascending=False)
        logger.info("  Top 10 teams with most missing:")
        for t, n in team_t.head(10).items():
            logger.info(f"    {t}: {int(n)}")

        # Monthly
        months = missing["date"].astype(str).str[:7]
        logger.info("\n  Missing by month:")
        for m, n in months.value_counts().sort_index().items():
            logger.info(f"    {m}: {n}")


if __name__ == "__main__":
    main()
