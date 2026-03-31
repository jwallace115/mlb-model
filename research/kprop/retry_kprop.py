#!/usr/bin/env python3
"""Targeted retry pass on api_error rows in K prop backfill."""

import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("kprop_retry")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT_PATH = PROJECT / "research" / "kprop" / "data" / "kprop_lines_historical.parquet"

with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
BASE = "https://api.the-odds-api.com/v4"

# Pitcher name→ID lookup
pgl = pd.read_parquet(PROJECT / "mlb" / "data" / "pitcher_game_logs.parquet")
_name_to_id = {}
for _, r in pgl[pgl["starter_flag"] == 1].drop_duplicates("player_id").iterrows():
    name = str(r.get("player_name", "")).strip()
    pid = int(r["player_id"])
    if name:
        _name_to_id[name.lower()] = pid
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            _name_to_id[f"{parts[1]} {parts[0]}".lower()] = pid


def _match_pitcher_id(name):
    if not name:
        return None
    key = name.strip().lower()
    if key in _name_to_id:
        return _name_to_id[key]
    parts = key.split()
    if len(parts) >= 2:
        last = parts[-1]
        matches = [v for k, v in _name_to_id.items() if k.endswith(last)]
        if len(matches) == 1:
            return matches[0]
    return None


def _extract_kprop(bookmakers, game_id, game_date, home_team, away_team, eid, timestamp):
    pitcher_data = {}
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "pitcher_strikeouts":
                continue
            for oc in mkt.get("outcomes", []):
                name = oc.get("description", "")
                side = oc.get("name", "")
                pt = oc.get("point")
                pr = oc.get("price")
                if not name or pt is None:
                    continue
                if name not in pitcher_data:
                    pitcher_data[name] = {}
                if bk_key not in pitcher_data[name]:
                    pitcher_data[name][bk_key] = {}
                entry = pitcher_data[name][bk_key]
                entry["line"] = pt
                if side == "Over":
                    entry["over"] = pr
                elif side == "Under":
                    entry["under"] = pr

    rows = []
    for pitcher_name, books in pitcher_data.items():
        candidates = []
        for bk_key, data in books.items():
            if "over" in data and "under" in data and data.get("line") is not None:
                candidates.append({
                    "book": bk_key, "line": data["line"],
                    "over": data["over"], "under": data["under"],
                    "balance": abs(data["over"] - data["under"]),
                })
        if not candidates:
            continue
        candidates.sort(key=lambda c: (c["balance"], c["line"]))
        canonical = candidates[0]
        fd = [c for c in candidates if c["book"] == "fanduel"]
        primary = fd[0] if fd else canonical
        pid = _match_pitcher_id(pitcher_name)

        rows.append({
            "game_id": game_id, "odds_api_event_id": eid,
            "date": game_date, "home_team": home_team, "away_team": away_team,
            "pitcher_name": pitcher_name, "pitcher_id": pid,
            "k_line": primary["line"], "over_price": primary["over"],
            "under_price": primary["under"], "primary_book": primary["book"],
            "books_count": len(candidates),
            "canonical_line": 1 if (primary["line"] == canonical["line"] and primary["book"] == canonical["book"]) else 0,
            "snapshot_timestamp": timestamp, "pull_status": "ok", "actual_k": None,
        })
        if primary["book"] != canonical["book"] or primary["line"] != canonical["line"]:
            rows[-1]["canonical_line"] = 0
            rows.append({
                "game_id": game_id, "odds_api_event_id": eid,
                "date": game_date, "home_team": home_team, "away_team": away_team,
                "pitcher_name": pitcher_name, "pitcher_id": pid,
                "k_line": canonical["line"], "over_price": canonical["over"],
                "under_price": canonical["under"], "primary_book": canonical["book"],
                "books_count": len(candidates), "canonical_line": 1,
                "snapshot_timestamp": timestamp, "pull_status": "ok", "actual_k": None,
            })
    return rows


def main():
    # STEP 1
    logger.info("STEP 1 — LOAD AND VERIFY")
    df = pd.read_parquet(OUT_PATH)
    status_counts = df["pull_status"].value_counts().to_dict()
    ok_games = df[df["pull_status"] == "ok"]["game_id"].nunique()
    logger.info(f"  Total rows: {len(df)}")
    logger.info(f"  Status counts: {status_counts}")
    logger.info(f"  OK unique games: {ok_games}")

    # STEP 2
    logger.info("\nSTEP 2 — IDENTIFY RETRY TARGETS")
    errors = df[df["pull_status"].str.startswith("api_error", na=False)]
    targets = errors.drop_duplicates("game_id")[
        ["game_id", "odds_api_event_id", "date", "home_team", "away_team"]
    ].to_dict("records")
    logger.info(f"  Unique events to retry: {len(targets)}")

    # STEP 3+4
    logger.info("\nSTEP 3 — RETRY API CALLS")
    recovered = 0
    still_failed = 0
    now_no_market = 0

    for i, t in enumerate(targets):
        gid = t["game_id"]
        eid = t["odds_api_event_id"]
        gdate = t["date"]
        home = t["home_team"]
        away = t["away_team"]

        snap = f"{gdate}T20:00:00Z"
        url = f"{BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
        params = {
            "apiKey": API_KEY, "regions": "us",
            "markets": "pitcher_strikeouts", "oddsFormat": "american",
            "date": snap,
        }

        success = False
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    inner = data.get("data", data)
                    bks = inner.get("bookmakers", [])
                    timestamp = data.get("timestamp", "")

                    # Remove old error rows for this game
                    df = df[~((df["game_id"] == gid) & df["pull_status"].str.startswith("api_error", na=False))]

                    if bks:
                        rows = _extract_kprop(bks, gid, gdate, home, away, eid, timestamp)
                        if rows:
                            new_df = pd.DataFrame(rows)
                            df = pd.concat([df, new_df], ignore_index=True)
                            recovered += 1
                        else:
                            df = pd.concat([df, pd.DataFrame([{
                                "game_id": gid, "odds_api_event_id": eid,
                                "date": gdate, "home_team": home, "away_team": away,
                                "pitcher_name": None, "pitcher_id": None,
                                "k_line": None, "over_price": None, "under_price": None,
                                "primary_book": None, "books_count": 0, "canonical_line": 0,
                                "snapshot_timestamp": timestamp,
                                "pull_status": "no_market", "actual_k": None,
                            }])], ignore_index=True)
                            now_no_market += 1
                    else:
                        df = pd.concat([df, pd.DataFrame([{
                            "game_id": gid, "odds_api_event_id": eid,
                            "date": gdate, "home_team": home, "away_team": away,
                            "pitcher_name": None, "pitcher_id": None,
                            "k_line": None, "over_price": None, "under_price": None,
                            "primary_book": None, "books_count": 0, "canonical_line": 0,
                            "snapshot_timestamp": timestamp,
                            "pull_status": "no_market", "actual_k": None,
                        }])], ignore_index=True)
                        now_no_market += 1
                    success = True
                    break
                elif r.status_code == 429:
                    logger.warning("429 — waiting 65s")
                    time.sleep(65)
                    continue
                elif r.status_code == 422:
                    df = df[~((df["game_id"] == gid) & df["pull_status"].str.startswith("api_error", na=False))]
                    df = pd.concat([df, pd.DataFrame([{
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": gdate, "home_team": home, "away_team": away,
                        "pitcher_name": None, "pitcher_id": None,
                        "k_line": None, "over_price": None, "under_price": None,
                        "primary_book": None, "books_count": 0, "canonical_line": 0,
                        "snapshot_timestamp": "",
                        "pull_status": "no_market", "actual_k": None,
                    }])], ignore_index=True)
                    now_no_market += 1
                    success = True
                    break
                else:
                    time.sleep(2)
            except Exception as e:
                logger.debug(f"Attempt {attempt+1} failed: {e}")
                time.sleep(2)

        if not success:
            # Update status to retry_failed
            mask = (df["game_id"] == gid) & df["pull_status"].str.startswith("api_error", na=False)
            df.loc[mask, "pull_status"] = "api_error_retry_failed"
            still_failed += 1

        if (i + 1) % 50 == 0 or (i + 1) == len(targets):
            credits = r.headers.get("x-requests-remaining", "?") if r else "?"
            logger.info(f"  Progress: {i+1}/{len(targets)} | "
                        f"recovered={recovered} no_market={now_no_market} failed={still_failed} | "
                        f"credits={credits}")
            df.to_parquet(OUT_PATH, index=False)

        time.sleep(0.5)

    df.to_parquet(OUT_PATH, index=False)
    logger.info(f"\nRetry complete: recovered={recovered}, now_no_market={now_no_market}, "
                f"still_failed={still_failed}")

    # STEP 5
    logger.info("\nSTEP 5 — UPDATED COVERAGE")
    logger.info("=" * 60)
    ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
    ft["game_pk"] = ft["game_pk"].astype(str)

    total_ok = df[df["pull_status"] == "ok"]["game_id"].nunique()
    total_nm = df[df["pull_status"] == "no_market"]["game_id"].nunique()
    total_fail = df[df["pull_status"] == "api_error_retry_failed"]["game_id"].nunique()
    total_games = total_ok + total_nm + total_fail
    logger.info(f"  OK: {total_ok} | no_market: {total_nm} | retry_failed: {total_fail}")
    logger.info(f"  Overall coverage: {total_ok}/{total_games} ({total_ok/total_games*100:.1f}%)")

    for year, note in [(2023, " (May+)"), (2024, ""), (2025, "")]:
        if year == 2023:
            total_ft = len(ft[(ft["season"] == 2023) & (ft["date"].astype(str) >= "2023-05-03")])
        else:
            total_ft = len(ft[ft["season"] == year])
        year_ok = df[(df["pull_status"] == "ok") & (df["date"].str[:4] == str(year))]["game_id"].nunique()
        pct = year_ok / total_ft * 100 if total_ft > 0 else 0
        flag = " *** LOW" if pct < 75 else ""
        logger.info(f"  {year}{note}: {year_ok}/{total_ft} ({pct:.1f}%){flag}")

    # STEP 6
    logger.info("\nSTEP 6 — MISSING DATA DIAGNOSTICS")
    logger.info("=" * 60)
    missing = df[df["pull_status"] != "ok"].drop_duplicates("game_id")

    # By month
    missing_dates = missing["date"].astype(str)
    months = missing_dates.str[:7]
    logger.info("  Missing by month:")
    for m, n in months.value_counts().sort_index().items():
        logger.info(f"    {m}: {n}")

    # Top teams
    home_counts = missing["home_team"].value_counts()
    away_counts = missing["away_team"].value_counts()
    team_total = (home_counts.add(away_counts, fill_value=0)).sort_values(ascending=False)
    logger.info("\n  Top 10 teams with most missing:")
    for t, n in team_total.head(10).items():
        logger.info(f"    {t}: {int(n)}")

    # Join to game logs for IP
    pgl_starters = pgl[pgl["starter_flag"] == 1].copy()
    pgl_starters["game_pk"] = pgl_starters["game_pk"].astype(str)
    missing_gids = set(missing["game_id"].astype(str))
    missing_starts = pgl_starters[pgl_starters["game_pk"].isin(missing_gids)]
    ok_gids = set(df[df["pull_status"] == "ok"]["game_id"].astype(str).unique())
    ok_starts = pgl_starters[pgl_starters["game_pk"].isin(ok_gids)]

    if len(missing_starts) > 0:
        logger.info(f"\n  Avg IP in missing games: {missing_starts['innings_pitched'].mean():.2f}")
        logger.info(f"  Avg IP in OK games:      {ok_starts['innings_pitched'].mean():.2f}")
        logger.info(f"  Missing starts < 3 IP:   {(missing_starts['innings_pitched'] < 3).sum()}/{len(missing_starts)}")
        logger.info(f"  OK starts < 3 IP:        {(ok_starts['innings_pitched'] < 3).sum()}/{len(ok_starts)}")

    # STEP 7
    logger.info("\nSTEP 7 — FINAL SUMMARY")
    logger.info("=" * 60)
    ok_rows = df[df["pull_status"] == "ok"]
    canon = ok_rows[ok_rows["canonical_line"] == 1]
    logger.info(f"  Total pitcher-game rows (ok): {len(ok_rows)}")
    logger.info(f"  Canonical rows: {len(canon)}")
    logger.info(f"  Average books per pitcher: {ok_rows['books_count'].mean():.1f}")
    logger.info(f"  Pitcher ID match rate: {ok_rows['pitcher_id'].notna().sum()}/{len(ok_rows)} "
                f"({ok_rows['pitcher_id'].notna().mean()*100:.1f}%)")

    logger.info("\n  K line distribution (canonical):")
    for line, n in canon["k_line"].value_counts().sort_index().items():
        logger.info(f"    {line}: {n} ({n/len(canon)*100:.1f}%)")


if __name__ == "__main__":
    main()
