#!/usr/bin/env python3
"""
Historical backfill: team_totals + totals_1st_5_innings
=======================================================
Pulls closing-line snapshots from The Odds API historical endpoint
for all 2023-2025 regular season MLB games.

Resumable: skips games already pulled with pull_status="ok".
Rate limited: 0.5s between calls, 10s backoff on 429.

Outputs:
  research/team_totals/data/team_totals_historical.parquet
  research/team_totals/data/f5_lines_historical.parquet
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("backfill")

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

# Load correct API key from .env
from config import ODDS_API_KEY, ODDS_API_BASE, ODDS_API_TEAM_MAP

API_KEY = ODDS_API_KEY
BASE = ODDS_API_BASE

OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TT_PATH = OUT_DIR / "team_totals_historical.parquet"
F5_PATH = OUT_DIR / "f5_lines_historical.parquet"
EVENT_MAP_PATH = OUT_DIR / "event_id_map.parquet"

# Reverse mapping: abbreviation → Odds API full name
ABB_TO_FULL = {v: k for k, v in ODDS_API_TEAM_MAP.items()}

TT_COLS = ["game_id", "odds_api_event_id", "date", "home_team", "away_team",
           "commence_time", "snapshot_timestamp", "home_tt_line", "away_tt_line",
           "home_over_price", "home_under_price", "away_over_price", "away_under_price",
           "primary_book", "books_count", "thin_coverage", "raw_bookmaker_json", "pull_status"]

F5_COLS = ["game_id", "odds_api_event_id", "date", "home_team", "away_team",
           "commence_time", "snapshot_timestamp", "f5_line", "f5_over_price",
           "f5_under_price", "primary_book", "books_count", "raw_bookmaker_json",
           "pull_status"]


def _load_or_create(path, cols):
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=cols)


def _save(df, path):
    df.to_parquet(path, index=False)


def _api_call(url, params, retries=1):
    """Make API call with retry on 429."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                logger.warning("429 rate limit — backing off 10s")
                time.sleep(10)
                continue
            return r
        except Exception as e:
            logger.warning(f"API error: {e}")
            if attempt < retries:
                time.sleep(5)
    return None


# ═══════════════════════════════════════════════════════════
# STEP 1 — BUILD GAME LIST
# ═══════════════════════════════════════════════════════════

def build_game_list():
    """Get all regular season games from feature_table."""
    ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
    games = ft[ft["season"].isin([2023, 2024, 2025])][
        ["game_pk", "date", "season", "home_team", "away_team", "game_hour_utc"]
    ].copy()
    games = games.rename(columns={"game_pk": "game_id"})
    games["game_id"] = games["game_id"].astype(str)

    # Build approximate commence_time UTC
    games["date_dt"] = pd.to_datetime(games["date"])
    games["commence_time"] = games.apply(
        lambda r: (r["date_dt"] + timedelta(hours=int(r["game_hour_utc"]))).isoformat() + "Z"
        if pd.notna(r["game_hour_utc"]) else r["date"] + "T23:00:00Z", axis=1)

    logger.info(f"Game list: {len(games)} games across {games['season'].unique()}")
    return games


# ═══════════════════════════════════════════════════════════
# STEP 2 — MAP TO ODDS API EVENT IDs
# ═══════════════════════════════════════════════════════════

def map_event_ids(games):
    """Map pipeline game_ids to Odds API event IDs."""
    if EVENT_MAP_PATH.exists():
        existing = pd.read_parquet(EVENT_MAP_PATH)
        mapped = set(existing["game_id"].astype(str))
        unmapped_games = games[~games["game_id"].isin(mapped)]
        logger.info(f"Event map: {len(existing)} already mapped, {len(unmapped_games)} remaining")
    else:
        existing = pd.DataFrame(columns=["game_id", "date", "odds_api_event_id",
                                          "home_full", "away_full"])
        unmapped_games = games

    if unmapped_games.empty:
        return existing

    # Get unique dates
    dates = sorted(unmapped_games["date"].unique())
    logger.info(f"Fetching events for {len(dates)} dates...")

    new_rows = []
    for i, dt in enumerate(dates):
        date_games = unmapped_games[unmapped_games["date"] == dt]
        date_param = dt + "T20:00:00Z"

        r = _api_call(f"{BASE}/historical/sports/baseball_mlb/events",
                      {"apiKey": API_KEY, "date": date_param})
        if r is None or r.status_code != 200:
            logger.warning(f"Events fetch failed for {dt}: {r.status_code if r else 'timeout'}")
            time.sleep(0.5)
            continue

        data = r.json()
        events = data.get("data", data)
        if isinstance(events, dict):
            events = events.get("data", [])

        # Match events to pipeline games
        for _, game in date_games.iterrows():
            home_full = ABB_TO_FULL.get(game["home_team"], "")
            away_full = ABB_TO_FULL.get(game["away_team"], "")

            matched_eid = None
            for evt in events:
                if (evt.get("home_team") == home_full and evt.get("away_team") == away_full):
                    matched_eid = evt["id"]
                    break

            if matched_eid:
                new_rows.append({
                    "game_id": game["game_id"],
                    "date": game["date"],
                    "odds_api_event_id": matched_eid,
                    "home_full": home_full,
                    "away_full": away_full,
                })

        if (i + 1) % 20 == 0:
            logger.info(f"  Events: {i+1}/{len(dates)} dates, {len(new_rows)} mapped")
            # Save incrementally
            if new_rows:
                combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
                combined = combined.drop_duplicates(subset="game_id", keep="first")
                _save(combined, EVENT_MAP_PATH)
                existing = combined
                new_rows = []

        time.sleep(0.3)

    # Final save
    if new_rows:
        combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
        combined = combined.drop_duplicates(subset="game_id", keep="first")
        _save(combined, EVENT_MAP_PATH)
        existing = combined

    return existing


# ═══════════════════════════════════════════════════════════
# STEP 3 — PULL CLOSING LINES
# ═══════════════════════════════════════════════════════════

def _extract_team_totals(bookmakers, home_full, away_full):
    """Extract consensus team total lines from bookmaker response."""
    home_lines = []
    away_lines = []
    primary_book = None

    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "team_totals":
                continue
            for oc in mkt.get("outcomes", []):
                desc = oc.get("description", "")
                point = oc.get("point")
                price = oc.get("price")
                name = oc.get("name", "")

                if desc == home_full and name == "Over" and point is not None:
                    home_lines.append({"book": bk_key, "point": point,
                                       "over_price": price,
                                       "under_price": None})
                elif desc == home_full and name == "Under" and point is not None:
                    # Update matching entry
                    for hl in home_lines:
                        if hl["book"] == bk_key and hl["point"] == point:
                            hl["under_price"] = price
                elif desc == away_full and name == "Over" and point is not None:
                    away_lines.append({"book": bk_key, "point": point,
                                       "over_price": price,
                                       "under_price": None})
                elif desc == away_full and name == "Under" and point is not None:
                    for al in away_lines:
                        if al["book"] == bk_key and al["point"] == point:
                            al["under_price"] = price

    # Consensus: FanDuel primary, else modal
    home_line = away_line = None
    home_op = home_up = away_op = away_up = None

    for lines, side in [(home_lines, "home"), (away_lines, "away")]:
        fd = [l for l in lines if l["book"] == "fanduel"]
        if fd:
            chosen = fd[0]
        elif lines:
            # Modal point
            from collections import Counter
            pts = Counter(l["point"] for l in lines)
            modal_pt = pts.most_common(1)[0][0]
            chosen = [l for l in lines if l["point"] == modal_pt][0]
        else:
            chosen = None

        if chosen:
            if side == "home":
                home_line = chosen["point"]
                home_op = chosen["over_price"]
                home_up = chosen["under_price"]
                primary_book = chosen["book"]
            else:
                away_line = chosen["point"]
                away_op = chosen["over_price"]
                away_up = chosen["under_price"]

    return home_line, away_line, home_op, home_up, away_op, away_up, primary_book


def _extract_f5(bookmakers):
    """Extract consensus F5 line from bookmaker response."""
    lines = []
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "totals_1st_5_innings":
                continue
            over_pt = over_pr = under_pr = None
            for oc in mkt.get("outcomes", []):
                if oc["name"] == "Over":
                    over_pt = oc.get("point")
                    over_pr = oc.get("price")
                elif oc["name"] == "Under":
                    under_pr = oc.get("price")
            if over_pt is not None:
                lines.append({"book": bk_key, "point": over_pt,
                              "over_price": over_pr, "under_price": under_pr})

    fd = [l for l in lines if l["book"] == "fanduel"]
    if fd:
        chosen = fd[0]
    elif lines:
        from collections import Counter
        pts = Counter(l["point"] for l in lines)
        modal_pt = pts.most_common(1)[0][0]
        chosen = [l for l in lines if l["point"] == modal_pt][0]
    else:
        return None, None, None, None

    return chosen["point"], chosen["over_price"], chosen["under_price"], chosen["book"]


def pull_lines(games, event_map):
    """Pull team_totals and F5 lines for all mapped games."""
    tt_df = _load_or_create(TT_PATH, TT_COLS)
    f5_df = _load_or_create(F5_PATH, F5_COLS)

    # Already completed — skip ok pulls AND no_market from pre-cutoff dates
    tt_done = set(tt_df[tt_df["pull_status"].isin(["ok"])]["game_id"].astype(str))
    f5_done = set(f5_df[f5_df["pull_status"].isin(["ok"])]["game_id"].astype(str))

    # Also skip games already marked no_market from before the cutoff dates
    # (these were correctly identified as unavailable — no need to re-pull)
    tt_pre_cutoff_skip = set(
        tt_df[(tt_df["pull_status"] == "no_market") & (tt_df["date"] < "2023-08-01")]["game_id"].astype(str))
    f5_pre_cutoff_skip = set(
        f5_df[(f5_df["pull_status"] == "no_market") & (f5_df["date"] < "2023-06-01")]["game_id"].astype(str))
    tt_done |= tt_pre_cutoff_skip
    f5_done |= f5_pre_cutoff_skip

    # Date range filters:
    #   team_totals: skip games before 2023-08-01 (market didn't exist)
    #   F5: skip games before 2023-06-01 (market didn't exist)
    TT_MIN_DATE = "2023-08-01"
    F5_MIN_DATE = "2023-06-01"

    # Merge games with event map
    emap = event_map[["game_id", "odds_api_event_id", "home_full", "away_full"]].copy()
    emap["game_id"] = emap["game_id"].astype(str)
    merged = games.merge(emap, on="game_id", how="inner")

    total = len(merged)
    success_tt = success_f5 = errors = skipped = 0
    no_market_tt = no_market_f5 = 0
    thin_tt = 0

    logger.info(f"Pulling lines for {total} games (TT from {TT_MIN_DATE}, F5 from {F5_MIN_DATE})...")

    for i, (_, game) in enumerate(merged.iterrows()):
        gid = str(game["game_id"])
        eid = game["odds_api_event_id"]
        home_full = game["home_full"]
        away_full = game["away_full"]
        game_date = game["date"]

        # Compute snapshot time: T-1 hour before commence
        try:
            ct = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
            snap_time = (ct - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except:
            snap_time = game["date"] + "T21:00:00Z"

        url = f"{BASE}/historical/sports/baseball_mlb/events/{eid}/odds"

        # ── Team totals (skip before 2023-08-01) ──
        if gid not in tt_done and game_date >= TT_MIN_DATE:
            r = _api_call(url, {"apiKey": API_KEY, "regions": "us",
                                "markets": "team_totals", "oddsFormat": "american",
                                "date": snap_time})
            if r and r.status_code == 200:
                data = r.json()
                inner = data.get("data", data)
                bks = inner.get("bookmakers", [])
                ts = data.get("timestamp", "")

                if bks:
                    hl, al, hop, hup, aop, aup, pb = _extract_team_totals(bks, home_full, away_full)
                    n_tt_books = sum(1 for bk in bks if any(m["key"] == "team_totals" for m in bk.get("markets", [])))
                    tt_row = {
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": game["date"], "home_team": game["home_team"],
                        "away_team": game["away_team"], "commence_time": game["commence_time"],
                        "snapshot_timestamp": ts, "home_tt_line": hl, "away_tt_line": al,
                        "home_over_price": hop, "home_under_price": hup,
                        "away_over_price": aop, "away_under_price": aup,
                        "primary_book": pb, "books_count": n_tt_books,
                        "thin_coverage": 1 if n_tt_books == 1 else 0,
                        "raw_bookmaker_json": json.dumps(bks),
                        "pull_status": "ok" if hl is not None else "no_market",
                    }
                    if hl is not None:
                        success_tt += 1
                        if n_tt_books == 1:
                            thin_tt += 1
                    else:
                        no_market_tt += 1
                else:
                    tt_row = {"game_id": gid, "odds_api_event_id": eid,
                              "date": game["date"], "home_team": game["home_team"],
                              "away_team": game["away_team"], "pull_status": "no_market",
                              "commence_time": game["commence_time"], "snapshot_timestamp": ts}
                    no_market_tt += 1

                tt_df = pd.concat([tt_df, pd.DataFrame([tt_row])], ignore_index=True)
            elif r:
                tt_df = pd.concat([tt_df, pd.DataFrame([{
                    "game_id": gid, "date": game["date"],
                    "home_team": game["home_team"], "away_team": game["away_team"],
                    "pull_status": f"api_error_{r.status_code}"}])], ignore_index=True)
                errors += 1
            else:
                errors += 1

            time.sleep(0.5)
        else:
            skipped += 1

        # ── F5 (skip before 2023-06-01) ──
        if gid not in f5_done and game_date >= F5_MIN_DATE:
            r2 = _api_call(url, {"apiKey": API_KEY, "regions": "us",
                                 "markets": "totals_1st_5_innings", "oddsFormat": "american",
                                 "date": snap_time})
            if r2 and r2.status_code == 200:
                data2 = r2.json()
                inner2 = data2.get("data", data2)
                bks2 = inner2.get("bookmakers", [])
                ts2 = data2.get("timestamp", "")

                if bks2:
                    f5l, f5op, f5up, f5bk = _extract_f5(bks2)
                    f5_row = {
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": game["date"], "home_team": game["home_team"],
                        "away_team": game["away_team"], "commence_time": game["commence_time"],
                        "snapshot_timestamp": ts2, "f5_line": f5l,
                        "f5_over_price": f5op, "f5_under_price": f5up,
                        "primary_book": f5bk, "books_count": len(bks2),
                        "raw_bookmaker_json": json.dumps(bks2),
                        "pull_status": "ok" if f5l is not None else "no_market",
                    }
                    if f5l is not None:
                        success_f5 += 1
                    else:
                        no_market_f5 += 1
                else:
                    f5_row = {"game_id": gid, "date": game["date"],
                              "home_team": game["home_team"], "away_team": game["away_team"],
                              "pull_status": "no_market", "commence_time": game["commence_time"],
                              "snapshot_timestamp": ts2}
                    no_market_f5 += 1

                f5_df = pd.concat([f5_df, pd.DataFrame([f5_row])], ignore_index=True)
            elif r2:
                f5_df = pd.concat([f5_df, pd.DataFrame([{
                    "game_id": gid, "date": game["date"],
                    "home_team": game["home_team"], "away_team": game["away_team"],
                    "pull_status": f"api_error_{r2.status_code}"}])], ignore_index=True)
            time.sleep(0.5)

        # Progress
        if (i + 1) % 100 == 0:
            _save(tt_df, TT_PATH)
            _save(f5_df, F5_PATH)
            remaining = "?"
            try:
                remaining = (r or r2).headers.get("x-requests-remaining", "?")
            except:
                pass
            logger.info(f"  Progress: {i+1}/{total} | TT ok={success_tt} thin={thin_tt} noMkt={no_market_tt} | "
                        f"F5 ok={success_f5} noMkt={no_market_f5} | err={errors} skip={skipped} | "
                        f"credits={remaining}")

    # Final save
    _save(tt_df, TT_PATH)
    _save(f5_df, F5_PATH)

    logger.info(f"\n{'='*60}")
    logger.info(f"BACKFILL COMPLETE")
    logger.info(f"  Total games: {total}")
    logger.info(f"  team_totals: {success_tt} ok, {no_market_tt} no_market, {errors} errors")
    logger.info(f"  F5: {success_f5} ok, {no_market_f5} no_market")


def print_coverage():
    """Print coverage gate results with thin_coverage breakdown."""
    tt = _load_or_create(TT_PATH, TT_COLS)
    f5 = _load_or_create(F5_PATH, F5_COLS)
    ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")

    print(f"\n{'='*60}")
    print("COVERAGE GATE")
    print("="*60)

    # Team totals by season with thin_coverage
    print(f"\n  team_totals:")
    tt_ok = tt[tt["pull_status"] == "ok"]
    for s, note in [(2023, " (Aug-Oct only)"), (2024, ""), (2025, "")]:
        total = len(ft[ft["season"] == s])
        covered = tt_ok[tt_ok["date"].str[:4] == str(s)]
        n = len(covered)
        pct = n / total * 100 if total > 0 else 0
        thin = covered["thin_coverage"].sum() if "thin_coverage" in covered.columns else 0
        flag = " *** LOW" if pct < 80 and s >= 2024 else ""
        print(f"    {s}{note}: {n}/{total} ({pct:.1f}%) | thin_coverage={int(thin)}{flag}")

    # F5 by season
    print(f"\n  F5:")
    f5_ok = f5[f5["pull_status"] == "ok"]
    for s, note in [(2023, " (Jun-Oct only)"), (2024, ""), (2025, "")]:
        total = len(ft[ft["season"] == s])
        covered = f5_ok[f5_ok["date"].str[:4] == str(s)]
        n = len(covered)
        pct = n / total * 100 if total > 0 else 0
        flag = " *** LOW" if pct < 80 and s >= 2024 else ""
        print(f"    {s}{note}: {n}/{total} ({pct:.1f}%){flag}")

    # Credits summary
    print(f"\n  Credits used: check x-requests-remaining header")
    print(f"  TT total ok: {len(tt_ok)}, F5 total ok: {len(f5_ok)}")


if __name__ == "__main__":
    print(f"API key: {API_KEY[:10]}...")

    # Step 1
    games = build_game_list()

    # Step 2
    event_map = map_event_ids(games)

    # Mapping gate
    total_games = len(games)
    mapped = len(event_map)
    unmapped = total_games - mapped
    match_rate = mapped / total_games * 100
    print(f"\nMAPPING GATE:")
    print(f"  Total pipeline games: {total_games}")
    print(f"  Mapped to event ID: {mapped}")
    print(f"  Unmapped: {unmapped}")
    print(f"  Match rate: {match_rate:.1f}%")

    if match_rate < 85:
        print(f"\n*** MAPPING GATE FAILED ({match_rate:.1f}% < 85%) — stopping ***")
        # Show unmapped examples
        mapped_ids = set(event_map["game_id"].astype(str))
        unmapped_games = games[~games["game_id"].isin(mapped_ids)]
        print(f"First 10 unmapped:")
        for _, g in unmapped_games.head(10).iterrows():
            print(f"  {g['date']} {g['away_team']}@{g['home_team']} (id={g['game_id']})")
        sys.exit(1)

    print(f"  PASS ✓")

    # Step 3
    pull_lines(games, event_map)

    # Coverage gate
    print_coverage()
