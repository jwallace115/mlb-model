#!/usr/bin/env python3
"""Targeted retry pass on failed team_totals and F5 pulls."""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("retry")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT_DIR = PROJECT / "research" / "team_totals" / "data"
TT_PATH = OUT_DIR / "team_totals_historical.parquet"
F5_PATH = OUT_DIR / "f5_lines_historical.parquet"
EMAP_PATH = OUT_DIR / "event_id_map.parquet"

# Load correct key from .env
with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
BASE = "https://api.the-odds-api.com/v4"

# Load event map and feature table for commence times
emap = pd.read_parquet(EMAP_PATH)
emap["game_id"] = emap["game_id"].astype(str)
ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)

from config import ODDS_API_TEAM_MAP
ABB_TO_FULL = {v: k for k, v in ODDS_API_TEAM_MAP.items()}


def _get_commence(game_id, game_date):
    gft = ft[ft["game_pk"] == str(game_id)]
    if len(gft) > 0:
        h = int(gft.iloc[0]["game_hour_utc"])
        return datetime.strptime(game_date, "%Y-%m-%d") + timedelta(hours=h)
    return datetime.strptime(game_date, "%Y-%m-%d") + timedelta(hours=23)


def _api_call(url, params):
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429:
            logger.warning("429 — waiting 65s")
            time.sleep(65)
            r = requests.get(url, params=params, timeout=30)
        return r
    except Exception as e:
        logger.warning(f"API error: {e}")
        return None


def _extract_team_totals(bookmakers, home_full, away_full):
    from collections import Counter
    home_lines = []; away_lines = []
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "team_totals": continue
            for oc in mkt.get("outcomes", []):
                desc = oc.get("description", ""); pt = oc.get("point"); pr = oc.get("price"); nm = oc.get("name", "")
                if desc == home_full and nm == "Over" and pt is not None:
                    home_lines.append({"book": bk_key, "point": pt, "over_price": pr, "under_price": None})
                elif desc == home_full and nm == "Under" and pt is not None:
                    for hl in home_lines:
                        if hl["book"] == bk_key and hl["point"] == pt: hl["under_price"] = pr
                elif desc == away_full and nm == "Over" and pt is not None:
                    away_lines.append({"book": bk_key, "point": pt, "over_price": pr, "under_price": None})
                elif desc == away_full and nm == "Under" and pt is not None:
                    for al in away_lines:
                        if al["book"] == bk_key and al["point"] == pt: al["under_price"] = pr

    for lines, side_out in [(home_lines, "home"), (away_lines, "away")]:
        fd = [l for l in lines if l["book"] == "fanduel"]
        if fd: chosen = fd[0]
        elif lines:
            pts = Counter(l["point"] for l in lines)
            chosen = [l for l in lines if l["point"] == pts.most_common(1)[0][0]][0]
        else: chosen = None
        if side_out == "home":
            hl = chosen["point"] if chosen else None; hop = chosen["over_price"] if chosen else None; hup = chosen["under_price"] if chosen else None; pb = chosen["book"] if chosen else None
        else:
            al = chosen["point"] if chosen else None; aop = chosen["over_price"] if chosen else None; aup = chosen["under_price"] if chosen else None

    n_tt = sum(1 for bk in bookmakers if any(m["key"] == "team_totals" for m in bk.get("markets", [])))
    return hl, al, hop, hup, aop, aup, pb, n_tt


def retry_tt():
    logger.info("=== TEAM TOTALS RETRY ===")
    tt = pd.read_parquet(TT_PATH)
    # Target: api_error or no_market rows from 2023-08-01+
    targets = tt[(tt["pull_status"].isin(["no_market"]) | tt["pull_status"].str.startswith("api_error", na=False))
                 & (tt["date"] >= "2023-08-01")]
    logger.info(f"TT retry targets: {len(targets)} rows")
    if targets.empty:
        return 0

    recovered = 0
    for idx in targets.index:
        row = tt.loc[idx]
        gid = str(row["game_id"])
        game_date = row["date"]
        status = row["pull_status"]

        # Get event ID
        em = emap[emap["game_id"] == gid]
        if em.empty: continue
        eid = em.iloc[0]["odds_api_event_id"]
        home_full = em.iloc[0].get("home_full", ABB_TO_FULL.get(row.get("home_team", ""), ""))
        away_full = em.iloc[0].get("away_full", ABB_TO_FULL.get(row.get("away_team", ""), ""))

        ct = _get_commence(gid, game_date)
        url = f"{BASE}/historical/sports/baseball_mlb/events/{eid}/odds"

        # Determine retry snapshots
        if str(status).startswith("api_error"):
            snaps = [(ct - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")]
        else:  # no_market
            snaps = [
                (ct - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                (ct - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ]

        for snap in snaps:
            r = _api_call(url, {"apiKey": API_KEY, "regions": "us", "markets": "team_totals",
                                "oddsFormat": "american", "date": snap})
            if r and r.status_code == 200:
                data = r.json()
                inner = data.get("data", data)
                bks = inner.get("bookmakers", [])
                if bks:
                    hl, al, hop, hup, aop, aup, pb, n_tt = _extract_team_totals(bks, home_full, away_full)
                    if hl is not None:
                        tt.at[idx, "home_tt_line"] = hl
                        tt.at[idx, "away_tt_line"] = al
                        tt.at[idx, "home_over_price"] = hop
                        tt.at[idx, "home_under_price"] = hup
                        tt.at[idx, "away_over_price"] = aop
                        tt.at[idx, "away_under_price"] = aup
                        tt.at[idx, "primary_book"] = pb
                        tt.at[idx, "books_count"] = n_tt
                        tt.at[idx, "thin_coverage"] = 1 if n_tt == 1 else 0
                        tt.at[idx, "snapshot_timestamp"] = data.get("timestamp", "")
                        tt.at[idx, "raw_bookmaker_json"] = json.dumps(bks)
                        tt.at[idx, "pull_status"] = "ok"
                        recovered += 1
                        break
            time.sleep(1.5)

        if (recovered) % 25 == 0 and recovered > 0:
            tt.to_parquet(TT_PATH, index=False)
            logger.info(f"  TT recovered: {recovered} so far")

    tt.to_parquet(TT_PATH, index=False)
    logger.info(f"TT retry complete: {recovered} recovered")
    return recovered


def retry_f5():
    logger.info("\n=== F5 RETRY ===")
    f5 = pd.read_parquet(F5_PATH)
    targets = f5[(f5["pull_status"].isin(["no_market"]) | f5["pull_status"].str.startswith("api_error", na=False))
                 & (f5["date"] >= "2023-06-01")]
    logger.info(f"F5 retry targets: {len(targets)} rows")
    if targets.empty:
        return 0

    recovered = 0
    for idx in targets.index:
        row = f5.loc[idx]
        gid = str(row["game_id"])
        game_date = row["date"]

        em = emap[emap["game_id"] == gid]
        if em.empty: continue
        eid = em.iloc[0]["odds_api_event_id"]

        ct = _get_commence(gid, game_date)
        snap = (ct - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{BASE}/historical/sports/baseball_mlb/events/{eid}/odds"

        r = _api_call(url, {"apiKey": API_KEY, "regions": "us", "markets": "totals_1st_5_innings",
                            "oddsFormat": "american", "date": snap})
        if r and r.status_code == 200:
            data = r.json()
            inner = data.get("data", data)
            bks = inner.get("bookmakers", [])
            for bk in bks:
                for m in bk.get("markets", []):
                    if m["key"] == "totals_1st_5_innings":
                        over_pt = over_pr = under_pr = None
                        for oc in m.get("outcomes", []):
                            if oc["name"] == "Over": over_pt = oc.get("point"); over_pr = oc.get("price")
                            elif oc["name"] == "Under": under_pr = oc.get("price")
                        if over_pt is not None:
                            f5.at[idx, "f5_line"] = over_pt
                            f5.at[idx, "f5_over_price"] = over_pr
                            f5.at[idx, "f5_under_price"] = under_pr
                            f5.at[idx, "primary_book"] = bk["key"]
                            f5.at[idx, "books_count"] = len(bks)
                            f5.at[idx, "snapshot_timestamp"] = data.get("timestamp", "")
                            f5.at[idx, "raw_bookmaker_json"] = json.dumps(bks)
                            f5.at[idx, "pull_status"] = "ok"
                            recovered += 1
                            break
                if f5.at[idx, "pull_status"] == "ok": break
        time.sleep(1.5)

        if recovered % 25 == 0 and recovered > 0:
            f5.to_parquet(F5_PATH, index=False)
            logger.info(f"  F5 recovered: {recovered} so far")

    f5.to_parquet(F5_PATH, index=False)
    logger.info(f"F5 retry complete: {recovered} recovered")
    return recovered


def print_coverage():
    tt = pd.read_parquet(TT_PATH)
    f5 = pd.read_parquet(F5_PATH)

    print(f"\n{'='*60}")
    print("UPDATED COVERAGE AFTER RETRY")
    print("="*60)

    tt_ok = tt[tt["pull_status"] == "ok"]
    print(f"\n  team_totals:")
    for s, note in [(2023, " (Aug-Oct)"), (2024, ""), (2025, "")]:
        total = len(ft[ft["season"] == s])
        covered = tt_ok[tt_ok["date"].str[:4] == str(s)]
        n = len(covered)
        pct = n / total * 100
        thin = int(covered["thin_coverage"].sum()) if "thin_coverage" in covered.columns else 0
        flag = " *** LOW" if pct < 80 and s >= 2024 else " ✓" if pct >= 80 and s >= 2024 else ""
        print(f"    {s}{note}: {n}/{total} ({pct:.1f}%) thin={thin}{flag}")

    f5_ok = f5[f5["pull_status"] == "ok"]
    print(f"\n  F5:")
    for s, note in [(2023, " (Jun-Oct)"), (2024, ""), (2025, "")]:
        total = len(ft[ft["season"] == s])
        covered = f5_ok[f5_ok["date"].str[:4] == str(s)]
        n = len(covered)
        pct = n / total * 100
        flag = " *** LOW" if pct < 80 and s >= 2024 else " ✓" if pct >= 80 and s >= 2024 else ""
        print(f"    {s}{note}: {n}/{total} ({pct:.1f}%){flag}")


if __name__ == "__main__":
    print(f"API key: {API_KEY[:10]}...")
    r_tt = retry_tt()
    r_f5 = retry_f5()
    print(f"\nRows recovered: TT={r_tt}, F5={r_f5}")
    print_coverage()
