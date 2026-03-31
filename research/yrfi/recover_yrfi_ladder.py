#!/usr/bin/env python3
"""
YRFI recovery: timestamp ladder search around actual commence_time.
Derives all timestamps from UTC commence_time, not date assumptions.
"""

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("yrfi_ladder")

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

# Ladder offsets (minutes before commence_time)
LADDER = [360, 240, 180, 120, 90, 60, 45, 30, 15]


def _get_commence_utc(game_id, game_date):
    """Reconstruct UTC commence_time from game_hour_utc."""
    gft = ft[ft["game_pk"] == str(game_id)]
    if len(gft) == 0:
        return None
    hour = int(gft.iloc[0].get("game_hour_utc", 20))
    base = datetime.strptime(game_date, "%Y-%m-%d")
    if hour >= 24:
        return base + timedelta(hours=hour)
    elif hour < 6:
        # After midnight UTC = next calendar day
        return base + timedelta(days=1, hours=hour)
    else:
        return base + timedelta(hours=hour)


def _extract_yrfi(bookmakers):
    """Extract valid 0.5 YRFI/NRFI lines."""
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
        med_o = int(np.median([v["over"] for v in valid]))
        med_u = int(np.median([v["under"] for v in valid]))
        chosen = min(valid, key=lambda v: abs(v["over"] - med_o) + abs(v["under"] - med_u))
    return chosen["over"], chosen["under"], chosen["book"], len(valid)


def _call_api(eid, snap_ts):
    """Single API call. Returns (response, bookmakers) or (None, None)."""
    url = f"{ODDS_BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
    params = {
        "apiKey": API_KEY, "regions": "us",
        "markets": "totals_1st_1_innings",
        "oddsFormat": "american",
        "date": snap_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429:
            logger.warning("429 — waiting 65s")
            time.sleep(65)
            r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            data = r.json()
            inner = data.get("data", data)
            return r, inner.get("bookmakers", []), data.get("timestamp", "")
        return r, [], ""
    except Exception:
        return None, None, ""


def main():
    df = pd.read_parquet(LINES_PATH)

    targets_mask = df["pull_status"].isin(
        ["no_market", "no_market_confirmed", "api_error", "api_error_final"]
    )
    target_indices = df[targets_mask].index.tolist()

    logger.info("YRFI RECOVERY — TIMESTAMP LADDER")
    logger.info("=" * 60)
    logger.info(f"Targets: {len(target_indices)}")
    logger.info(f"Status breakdown: {df.loc[target_indices, 'pull_status'].value_counts().to_dict()}")

    # ── STEP 3: Debug first 25 games ──
    logger.info("\nSTEP 3 — DEBUG FIRST 25 GAMES")
    logger.info("=" * 60)

    debug_count = min(25, len(target_indices))
    for di in range(debug_count):
        idx = target_indices[di]
        row = df.loc[idx]
        gid = str(row["game_id"])
        eid = row["odds_api_event_id"]
        gdate = str(row["date"])

        ct_utc = _get_commence_utc(gid, gdate)
        if ct_utc is None:
            logger.info(f"  Game {gid}: NO COMMENCE TIME")
            continue

        logger.info(f"\n  Game {gid}: {row['away_team']}@{row['home_team']} "
                    f"commence={ct_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}")

        for offset_min in LADDER:
            snap_ts = ct_utc - timedelta(minutes=offset_min)
            r, bks, ts = _call_api(eid, snap_ts)
            if bks is None:
                logger.info(f"    T-{offset_min:3d}m ({snap_ts.strftime('%H:%M')}Z): FAILED")
                time.sleep(0.5)
                continue

            http_code = r.status_code if r else "?"
            n_bks = len(bks)

            # Check for market
            has_market = False
            has_05 = False
            points_seen = set()
            bk_names = []
            for bk in bks[:2]:
                bk_names.append(bk["key"])
                for mkt in bk.get("markets", []):
                    if mkt["key"] == "totals_1st_1_innings":
                        has_market = True
                        for oc in mkt.get("outcomes", []):
                            pt = oc.get("point")
                            if pt is not None:
                                points_seen.add(pt)
                                if pt == 0.5:
                                    has_05 = True

            pts_str = ",".join(str(p) for p in sorted(points_seen)) if points_seen else "none"
            bks_str = ",".join(bk_names[:2]) if bk_names else "none"
            marker = " <<<< FOUND 0.5" if has_05 else ""
            logger.info(f"    T-{offset_min:3d}m ({snap_ts.strftime('%H:%M')}Z): "
                        f"HTTP={http_code} bks={n_bks} market={has_market} "
                        f"pts=[{pts_str}] books=[{bks_str}]{marker}")

            if has_05:
                break  # Found it, stop ladder for this debug game
            time.sleep(0.5)

    # ── STEP 4: Full recovery pass ──
    logger.info("\n" + "=" * 60)
    logger.info("STEP 4 — FULL RECOVERY PASS")
    logger.info("=" * 60)

    recovered = 0
    no_mkt_conf = 0
    invalid_conf = 0
    err_final = 0
    wc_recovered = 0
    ec_recovered = 0
    last_r = None

    for i, idx in enumerate(target_indices):
        row = df.loc[idx]
        gid = str(row["game_id"])
        eid = row["odds_api_event_id"]
        gdate = str(row["date"])
        home = row["home_team"]
        away = row["away_team"]

        # Skip if already ok (from debug pass or prior resume)
        if df.at[idx, "pull_status"] == "ok":
            continue

        ct_utc = _get_commence_utc(gid, gdate)
        if ct_utc is None:
            df.at[idx, "pull_status"] = "api_error_retry_failed"
            err_final += 1
            continue

        is_west = ct_utc.hour < 6 or ct_utc.hour >= 24

        found = False
        saw_non05 = False
        all_failed = True

        for offset_min in LADDER:
            snap_ts = ct_utc - timedelta(minutes=offset_min)
            r, bks, ts = _call_api(eid, snap_ts)
            last_r = r

            if bks is None:
                time.sleep(0.5)
                continue

            all_failed = False

            if not bks:
                time.sleep(0.3)
                continue

            # Check for valid 0.5 line
            over_p, under_p, book, n_books = _extract_yrfi(bks)
            if over_p is not None:
                df.at[idx, "yrfi_over_price"] = over_p
                df.at[idx, "nrfi_under_price"] = under_p
                df.at[idx, "yrfi_line"] = 0.5
                df.at[idx, "primary_book"] = book
                df.at[idx, "books_count"] = n_books
                df.at[idx, "snapshot_timestamp"] = ts
                df.at[idx, "pull_status"] = "ok"
                recovered += 1
                if is_west:
                    wc_recovered += 1
                else:
                    ec_recovered += 1
                found = True
                break

            # Check if non-0.5 lines exist
            for bk in bks:
                for mkt in bk.get("markets", []):
                    if mkt["key"] == "totals_1st_1_innings":
                        for oc in mkt.get("outcomes", []):
                            if oc.get("point") is not None and oc.get("point") != 0.5:
                                saw_non05 = True

            time.sleep(0.3)

        if not found:
            if all_failed:
                df.at[idx, "pull_status"] = "api_error_retry_failed"
                err_final += 1
            elif saw_non05:
                df.at[idx, "pull_status"] = "invalid_line_confirmed"
                invalid_conf += 1
            else:
                df.at[idx, "pull_status"] = "no_market_confirmed"
                no_mkt_conf += 1

        if (i + 1) % 50 == 0 or (i + 1) == len(target_indices):
            credits = last_r.headers.get("x-requests-remaining", "?") if last_r else "?"
            logger.info(f"  Progress: {i+1}/{len(target_indices)} | recovered={recovered} "
                        f"no_mkt={no_mkt_conf} invalid={invalid_conf} err={err_final} | "
                        f"credits={credits}")
            df.to_parquet(LINES_PATH, index=False)

        time.sleep(0.3)

    df.to_parquet(LINES_PATH, index=False)
    logger.info(f"\nRecovery complete: recovered={recovered}, no_market_confirmed={no_mkt_conf}, "
                f"invalid_line_confirmed={invalid_conf}, api_error_retry_failed={err_final}")

    # ── STEP 5: Final report ──
    logger.info("\n" + "=" * 60)
    logger.info("STEP 5 — FINAL REPORT")
    logger.info("=" * 60)

    logger.info(f"\n1. Target rows: {len(target_indices)}")
    logger.info(f"2. Recovered to ok: {recovered}")
    logger.info(f"3. Remaining by status:")
    remaining = df[~df["pull_status"].isin(["ok", "invalid_line"])]
    for s, n in remaining["pull_status"].value_counts().items():
        logger.info(f"     {s}: {n}")

    logger.info(f"\n4. Coverage by season:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_ok = len(df[(df["pull_status"] == "ok") & (df["date"].str[:4] == str(year))])
        pct = n_ok / total * 100
        flag = "" if pct >= 75 else " *** LOW"
        logger.info(f"   {year}: {n_ok}/{total} ({pct:.1f}%){flag}")

    logger.info(f"\n5. Recovery split:")
    logger.info(f"   West Coast recoveries: {wc_recovered}")
    logger.info(f"   East/Central recoveries: {ec_recovered}")

    logger.info(f"\n6. Unrecovered concentration:")
    unrec = df[~df["pull_status"].isin(["ok", "invalid_line"])]
    if len(unrec) > 0:
        home_c = unrec["home_team"].value_counts()
        away_c = unrec["away_team"].value_counts()
        team_t = (home_c.add(away_c, fill_value=0)).sort_values(ascending=False)
        logger.info("   Top 10 teams:")
        for t, n in team_t.head(10).items():
            logger.info(f"     {t}: {int(n)}")

    # Full status summary
    logger.info(f"\n   Full status summary: {df['pull_status'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
