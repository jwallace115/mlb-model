#!/usr/bin/env python3
"""
YRFI/NRFI historical backfill: lines + first-inning actuals.
2024-2025 regular season only.
Output: research/yrfi/data/
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("yrfi")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "yrfi" / "data"
LINES_PATH = OUT / "yrfi_lines_historical.parquet"
ACTUALS_PATH = OUT / "yrfi_actuals.parquet"
EMAP_PATH = PROJECT / "research" / "team_totals" / "data" / "event_id_map.parquet"

with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
ODDS_BASE = "https://api.the-odds-api.com/v4"
MLB_BASE = "https://statsapi.mlb.com/api/v1"

emap = pd.read_parquet(EMAP_PATH)
emap["game_id"] = emap["game_id"].astype(str)

ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)

LINES_COLS = [
    "game_id", "odds_api_event_id", "date", "home_team", "away_team",
    "commence_time", "yrfi_over_price", "nrfi_under_price", "yrfi_line",
    "primary_book", "books_count", "snapshot_timestamp", "pull_status",
]

ACTUALS_COLS = [
    "game_id", "date", "home_team", "away_team",
    "first_inning_runs_home", "first_inning_runs_away",
    "first_inning_total", "yrfi_result", "actuals_status",
]


def _load_lines():
    if LINES_PATH.exists():
        return pd.read_parquet(LINES_PATH)
    return pd.DataFrame(columns=LINES_COLS)


def _save_lines(df):
    df.to_parquet(LINES_PATH, index=False)


def _load_actuals():
    if ACTUALS_PATH.exists():
        return pd.read_parquet(ACTUALS_PATH)
    return pd.DataFrame(columns=ACTUALS_COLS)


def _save_actuals(df):
    df.to_parquet(ACTUALS_PATH, index=False)


def _get_commence_hour(game_id):
    gft = ft[ft["game_pk"] == str(game_id)]
    if len(gft) > 0:
        return int(gft.iloc[0].get("game_hour_utc", 20))
    return 20


def _build_targets():
    """Build target game list: 2024-2025 regular season."""
    targets = []
    for _, em in emap.iterrows():
        gid = str(em["game_id"])
        gdate = str(em["date"])
        year = int(gdate[:4])
        if year not in (2024, 2025):
            continue
        gft = ft[ft["game_pk"] == gid]
        if len(gft) == 0:
            continue
        home = gft.iloc[0].get("home_team", "")
        away = gft.iloc[0].get("away_team", "")
        targets.append({
            "game_id": gid,
            "event_id": em["odds_api_event_id"],
            "date": gdate,
            "home_team": home,
            "away_team": away,
        })
    return targets


def _extract_yrfi(bookmakers, timestamp):
    """Extract YRFI/NRFI prices from bookmakers. Only 0.5 lines."""
    valid = []
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "totals_1st_1_innings":
                continue
            over_p = under_p = line_pt = None
            for oc in mkt.get("outcomes", []):
                pt = oc.get("point")
                if pt != 0.5:
                    continue
                if oc["name"] == "Over":
                    over_p = oc["price"]
                    line_pt = pt
                elif oc["name"] == "Under":
                    under_p = oc["price"]
                    line_pt = pt
            if over_p is not None and under_p is not None and line_pt == 0.5:
                valid.append({
                    "book": bk_key, "over": over_p, "under": under_p,
                })

    if not valid:
        return None, None, None, None, 0

    # Prefer FanDuel
    fd = [v for v in valid if v["book"] == "fanduel"]
    if fd:
        chosen = fd[0]
    else:
        # Median price among valid books
        med_over = int(np.median([v["over"] for v in valid]))
        med_under = int(np.median([v["under"] for v in valid]))
        # Pick the book closest to median
        best = min(valid, key=lambda v: abs(v["over"] - med_over) + abs(v["under"] - med_under))
        chosen = best

    return chosen["over"], chosen["under"], 0.5, chosen["book"], len(valid)


# ═══════════════════════════════════════════════
# PART 1 — YRFI/NRFI LINES
# ═══════════════════════════════════════════════

def pull_lines():
    logger.info("PART 1 — YRFI/NRFI LINES BACKFILL")
    logger.info("=" * 60)

    targets = _build_targets()
    logger.info(f"Target games: {len(targets)}")

    df = _load_lines()
    ok_gids = set(df[df["pull_status"] == "ok"]["game_id"].astype(str))
    remaining = [t for t in targets if t["game_id"] not in ok_gids]
    logger.info(f"Already ok: {len(ok_gids)}, remaining: {len(remaining)}")

    ok = no_mkt = err = invalid = 0

    for i, t in enumerate(remaining):
        gid = t["game_id"]
        eid = t["event_id"]
        gdate = t["date"]
        home = t["home_team"]
        away = t["away_team"]

        hour_utc = _get_commence_hour(gid)
        if hour_utc >= 24 or hour_utc < 6:
            # West Coast: next day T03:00Z
            next_day = (datetime.strptime(gdate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            snap = f"{next_day}T03:00:00Z"
        else:
            ct = datetime.strptime(gdate, "%Y-%m-%d") + timedelta(hours=hour_utc)
            snap = (ct - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{ODDS_BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
        params = {
            "apiKey": API_KEY, "regions": "us",
            "markets": "totals_1st_1_innings",
            "oddsFormat": "american", "date": snap,
        }

        # Remove old non-ok row if exists
        df = df[~((df["game_id"].astype(str) == gid) &
                   ~df["pull_status"].isin(["ok"]))]

        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                logger.warning("429 — waiting 65s")
                time.sleep(65)
                r = requests.get(url, params=params, timeout=30)
        except Exception as e:
            r = None

        if r and r.status_code == 200:
            data = r.json()
            inner = data.get("data", data)
            bks = inner.get("bookmakers", [])
            timestamp = data.get("timestamp", "")

            if bks:
                over_p, under_p, line, book, n_books = _extract_yrfi(bks, timestamp)
                if over_p is not None:
                    row = {
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": gdate, "home_team": home, "away_team": away,
                        "commence_time": snap,
                        "yrfi_over_price": over_p, "nrfi_under_price": under_p,
                        "yrfi_line": line, "primary_book": book,
                        "books_count": n_books, "snapshot_timestamp": timestamp,
                        "pull_status": "ok",
                    }
                    ok += 1
                else:
                    row = {
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": gdate, "home_team": home, "away_team": away,
                        "commence_time": snap,
                        "yrfi_over_price": None, "nrfi_under_price": None,
                        "yrfi_line": None, "primary_book": None,
                        "books_count": 0, "snapshot_timestamp": timestamp,
                        "pull_status": "invalid_line",
                    }
                    invalid += 1
            else:
                row = {
                    "game_id": gid, "odds_api_event_id": eid,
                    "date": gdate, "home_team": home, "away_team": away,
                    "commence_time": snap,
                    "yrfi_over_price": None, "nrfi_under_price": None,
                    "yrfi_line": None, "primary_book": None,
                    "books_count": 0, "snapshot_timestamp": timestamp,
                    "pull_status": "no_market",
                }
                no_mkt += 1
        elif r and r.status_code == 422:
            row = {
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": snap,
                "yrfi_over_price": None, "nrfi_under_price": None,
                "yrfi_line": None, "primary_book": None,
                "books_count": 0, "snapshot_timestamp": "",
                "pull_status": "no_market",
            }
            no_mkt += 1
        else:
            sc = r.status_code if r else "timeout"
            row = {
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": snap,
                "yrfi_over_price": None, "nrfi_under_price": None,
                "yrfi_line": None, "primary_book": None,
                "books_count": 0, "snapshot_timestamp": "",
                "pull_status": f"api_error",
            }
            err += 1

        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        if (i + 1) % 200 == 0 or (i + 1) == len(remaining):
            credits = r.headers.get("x-requests-remaining", "?") if r else "?"
            logger.info(f"  Lines: {i+1}/{len(remaining)} | ok={ok} no_mkt={no_mkt} "
                        f"err={err} invalid={invalid} | credits={credits}")
            _save_lines(df)

        time.sleep(0.5)

    _save_lines(df)
    logger.info(f"Lines complete: ok={ok} no_mkt={no_mkt} err={err} invalid={invalid}")


# ═══════════════════════════════════════════════
# PART 2 — FIRST INNING ACTUALS
# ═══════════════════════════════════════════════

def pull_actuals():
    logger.info("\nPART 2 — FIRST INNING ACTUALS")
    logger.info("=" * 60)

    targets = _build_targets()
    logger.info(f"Target games: {len(targets)}")

    df = _load_actuals()
    ok_gids = set(df[df["actuals_status"] == "ok"]["game_id"].astype(str))
    remaining = [t for t in targets if t["game_id"] not in ok_gids]
    logger.info(f"Already ok: {len(ok_gids)}, remaining: {len(remaining)}")

    ok = err = 0

    for i, t in enumerate(remaining):
        gid = t["game_id"]
        gdate = t["date"]
        home = t["home_team"]
        away = t["away_team"]

        # Remove old error row
        df = df[~((df["game_id"].astype(str) == gid) & (df["actuals_status"] != "ok"))]

        try:
            r = requests.get(f"{MLB_BASE}/game/{gid}/linescore", timeout=15)
            if r.status_code == 200:
                ls = r.json()
                innings = ls.get("innings", [])
                if innings and len(innings) > 0:
                    inn1 = innings[0]
                    h_runs = inn1.get("home", {}).get("runs", 0) or 0
                    a_runs = inn1.get("away", {}).get("runs", 0) or 0
                    total = h_runs + a_runs
                    row = {
                        "game_id": gid, "date": gdate,
                        "home_team": home, "away_team": away,
                        "first_inning_runs_home": h_runs,
                        "first_inning_runs_away": a_runs,
                        "first_inning_total": total,
                        "yrfi_result": 1 if total > 0 else 0,
                        "actuals_status": "ok",
                    }
                    ok += 1
                else:
                    row = {
                        "game_id": gid, "date": gdate,
                        "home_team": home, "away_team": away,
                        "first_inning_runs_home": None,
                        "first_inning_runs_away": None,
                        "first_inning_total": None,
                        "yrfi_result": None,
                        "actuals_status": "api_error",
                    }
                    err += 1
            else:
                row = {
                    "game_id": gid, "date": gdate,
                    "home_team": home, "away_team": away,
                    "first_inning_runs_home": None,
                    "first_inning_runs_away": None,
                    "first_inning_total": None,
                    "yrfi_result": None,
                    "actuals_status": "api_error",
                }
                err += 1
        except Exception:
            row = {
                "game_id": gid, "date": gdate,
                "home_team": home, "away_team": away,
                "first_inning_runs_home": None,
                "first_inning_runs_away": None,
                "first_inning_total": None,
                "yrfi_result": None,
                "actuals_status": "api_error",
            }
            err += 1

        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        if (i + 1) % 500 == 0 or (i + 1) == len(remaining):
            logger.info(f"  Actuals: {i+1}/{len(remaining)} | ok={ok} err={err}")
            _save_actuals(df)

        # MLB Stats API is free — lighter rate limit
        if (i + 1) % 50 == 0:
            time.sleep(1)

    _save_actuals(df)
    logger.info(f"Actuals complete: ok={ok} err={err}")


# ═══════════════════════════════════════════════
# PART 3 — VALIDATION
# ═══════════════════════════════════════════════

def validate():
    logger.info("\nPART 3 — VALIDATION")
    logger.info("=" * 60)

    lines = pd.read_parquet(LINES_PATH)
    actuals = pd.read_parquet(ACTUALS_PATH)

    # V1 — Uniqueness
    lines_dup = lines["game_id"].duplicated().sum()
    actuals_dup = actuals["game_id"].duplicated().sum()
    logger.info(f"V1 — Uniqueness:")
    logger.info(f"  Lines duplicates: {lines_dup}")
    logger.info(f"  Actuals duplicates: {actuals_dup}")

    # V2 — Line sanity
    ok_lines = lines[lines["pull_status"] == "ok"]
    bad_line = ok_lines[ok_lines["yrfi_line"] != 0.5]
    null_prices = ok_lines[ok_lines["yrfi_over_price"].isna() | ok_lines["nrfi_under_price"].isna()]
    logger.info(f"\nV2 — Line sanity (ok rows):")
    logger.info(f"  Non-0.5 lines: {len(bad_line)}")
    logger.info(f"  Null prices: {len(null_prices)}")

    # V3 — Season coverage
    logger.info(f"\nV3 — Season coverage:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_ok = len(lines[(lines["pull_status"] == "ok") & (lines["date"].str[:4] == str(year))])
        pct = n_ok / total * 100
        flag = "" if pct >= 75 else " *** LOW"
        logger.info(f"  Lines {year}: {n_ok}/{total} ({pct:.1f}%){flag}")

        a_ok = len(actuals[(actuals["actuals_status"] == "ok") & (actuals["date"].str[:4] == str(year))])
        a_pct = a_ok / total * 100
        logger.info(f"  Actuals {year}: {a_ok}/{total} ({a_pct:.1f}%)")

    # V4 — Join coverage
    logger.info(f"\nV4 — Join coverage:")
    joined = ok_lines.merge(
        actuals[actuals["actuals_status"] == "ok"],
        on="game_id", how="inner", suffixes=("_l", "_a")
    )
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_j = len(joined[joined["date_l"].str[:4] == str(year)])
        pct = n_j / total * 100
        logger.info(f"  {year}: {n_j}/{total} ({pct:.1f}%)")
    logger.info(f"  Total: {len(joined)}/{len(ft[ft['season'].isin([2024,2025])])} "
                f"({len(joined)/len(ft[ft['season'].isin([2024,2025])])*100:.1f}%)")

    # V5 — Book quality
    logger.info(f"\nV5 — Book quality:")
    for year in [2024, 2025]:
        yr_ok = ok_lines[ok_lines["date"].str[:4] == str(year)]
        if len(yr_ok) == 0:
            continue
        avg_books = yr_ok["books_count"].mean()
        med_yrfi = yr_ok["yrfi_over_price"].median()
        med_nrfi = yr_ok["nrfi_under_price"].median()
        fd_pct = (yr_ok["primary_book"] == "fanduel").mean() * 100
        logger.info(f"  {year}: avg_books={avg_books:.1f}, med_YRFI={med_yrfi:.0f}, "
                    f"med_NRFI={med_nrfi:.0f}, FD_primary={fd_pct:.0f}%")

    # YRFI base rate
    act_ok = actuals[actuals["actuals_status"] == "ok"]
    for year in [2024, 2025]:
        yr = act_ok[act_ok["date"].str[:4] == str(year)]
        if len(yr) > 0:
            yrfi_rate = yr["yrfi_result"].mean() * 100
            logger.info(f"  {year} YRFI base rate: {yrfi_rate:.1f}%")

    # Coverage gate
    logger.info(f"\n{'='*60}")
    logger.info("COVERAGE GATE")
    logger.info("=" * 60)

    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        l_ok = len(ok_lines[ok_lines["date"].str[:4] == str(year)])
        a_ok = len(act_ok[act_ok["date"].str[:4] == str(year)])
        l_pct = l_ok / total * 100
        a_pct = a_ok / total * 100

        l_status = "READY" if l_pct >= 75 else "PARTIAL" if l_pct >= 50 else "FAIL"
        a_status = "READY" if a_pct >= 95 else "PARTIAL" if a_pct >= 75 else "FAIL"
        logger.info(f"  lines_{year}_status = {l_status} ({l_pct:.1f}%)")
        logger.info(f"  actuals_{year}_status = {a_status} ({a_pct:.1f}%)")

    # Joined status
    j_total = len(ft[ft["season"].isin([2024, 2025])])
    j_pct = len(joined) / j_total * 100
    j_status = "READY" if j_pct >= 70 else "PARTIAL" if j_pct >= 50 else "FAIL"
    logger.info(f"  joined_dataset_status = {j_status} ({j_pct:.1f}%)")


if __name__ == "__main__":
    pull_lines()
    pull_actuals()
    validate()
