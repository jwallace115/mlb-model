#!/usr/bin/env python3
"""Targeted repull of West Coast K prop games with corrected snapshot time."""

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("kprop_west")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT_PATH = PROJECT / "research" / "kprop" / "data" / "kprop_lines_historical.parquet"

with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
BASE = "https://api.the-odds-api.com/v4"

# Feature table for commence times
ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)

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
    logger.info("STEP 1 — IDENTIFY MISSING WEST COAST GAMES")
    logger.info("=" * 60)

    df = pd.read_parquet(OUT_PATH)
    no_mkt = df[df["pull_status"].isin(["no_market", "no_market_confirmed"])].drop_duplicates("game_id")
    logger.info(f"Total no_market games: {len(no_mkt)}")

    # Get commence hour (UTC) for each missing game
    group_a = []  # East/Central — genuinely no market
    group_b = []  # West Coast — needs later snapshot

    for _, row in no_mkt.iterrows():
        gid = str(row["game_id"])
        gdate = str(row["date"])
        eid = row["odds_api_event_id"]
        home = row["home_team"]
        away = row["away_team"]

        gft = ft[ft["game_pk"] == gid]
        if len(gft) > 0:
            hour_utc = int(gft.iloc[0].get("game_hour_utc", 20))
        else:
            hour_utc = 20  # default assumption

        if hour_utc >= 24 or hour_utc < 6:
            # After midnight UTC = West Coast game
            group_b.append({
                "game_id": gid, "event_id": eid, "date": gdate,
                "home_team": home, "away_team": away, "hour_utc": hour_utc,
            })
        else:
            group_a.append({
                "game_id": gid, "event_id": eid, "date": gdate,
                "home_team": home, "away_team": away, "hour_utc": hour_utc,
            })

    logger.info(f"Group A (East/Central, skip): {len(group_a)}")
    logger.info(f"Group B (West Coast, repull): {len(group_b)}")

    if not group_b:
        logger.info("No West Coast games to repull.")
        return

    # Filter out any already recovered (status=ok) from a prior run
    ok_gids = set(df[df["pull_status"] == "ok"]["game_id"].astype(str).unique())
    group_b = [g for g in group_b if g["game_id"] not in ok_gids]
    logger.info(f"Group B after excluding already-ok: {len(group_b)}")

    # STEP 2
    logger.info("\nSTEP 2 — REPULL GROUP B WITH T+03:00Z SNAPSHOT")
    logger.info("=" * 60)

    recovered = 0
    confirmed_no_mkt = 0
    errors = 0

    for i, g in enumerate(group_b):
        gid = g["game_id"]
        eid = g["event_id"]
        gdate = g["date"]
        home = g["home_team"]
        away = g["away_team"]

        # Next day at 03:00 UTC (~8 PM PT previous evening)
        next_day = (datetime.strptime(gdate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        snap = f"{next_day}T03:00:00Z"

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

                    # Remove old no_market rows for this game
                    df = df[~((df["game_id"].astype(str) == gid) &
                              df["pull_status"].isin(["no_market", "no_market_confirmed"]))]

                    if bks:
                        rows = _extract_kprop(bks, gid, gdate, home, away, eid, timestamp)
                        if rows:
                            df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
                            recovered += 1
                        else:
                            df = pd.concat([df, pd.DataFrame([{
                                "game_id": gid, "odds_api_event_id": eid,
                                "date": gdate, "home_team": home, "away_team": away,
                                "pitcher_name": None, "pitcher_id": None,
                                "k_line": None, "over_price": None, "under_price": None,
                                "primary_book": None, "books_count": 0, "canonical_line": 0,
                                "snapshot_timestamp": timestamp,
                                "pull_status": "no_market_confirmed", "actual_k": None,
                            }])], ignore_index=True)
                            confirmed_no_mkt += 1
                    else:
                        df = pd.concat([df, pd.DataFrame([{
                            "game_id": gid, "odds_api_event_id": eid,
                            "date": gdate, "home_team": home, "away_team": away,
                            "pitcher_name": None, "pitcher_id": None,
                            "k_line": None, "over_price": None, "under_price": None,
                            "primary_book": None, "books_count": 0, "canonical_line": 0,
                            "snapshot_timestamp": timestamp,
                            "pull_status": "no_market_confirmed", "actual_k": None,
                        }])], ignore_index=True)
                        confirmed_no_mkt += 1
                    success = True
                    break
                elif r.status_code == 422:
                    df = df[~((df["game_id"].astype(str) == gid) &
                              df["pull_status"].isin(["no_market", "no_market_confirmed"]))]
                    df = pd.concat([df, pd.DataFrame([{
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": gdate, "home_team": home, "away_team": away,
                        "pitcher_name": None, "pitcher_id": None,
                        "k_line": None, "over_price": None, "under_price": None,
                        "primary_book": None, "books_count": 0, "canonical_line": 0,
                        "snapshot_timestamp": "",
                        "pull_status": "no_market_confirmed", "actual_k": None,
                    }])], ignore_index=True)
                    confirmed_no_mkt += 1
                    success = True
                    break
                elif r.status_code == 429:
                    logger.warning("429 — waiting 65s")
                    time.sleep(65)
                else:
                    time.sleep(2)
            except Exception as e:
                logger.debug(f"Attempt {attempt+1} failed: {e}")
                time.sleep(2)

        if not success:
            # Mark as west coast error
            mask = ((df["game_id"].astype(str) == gid) &
                    df["pull_status"].isin(["no_market", "no_market_confirmed"]))
            df.loc[mask, "pull_status"] = "api_error_west"
            errors += 1

        if (i + 1) % 100 == 0 or (i + 1) == len(group_b):
            credits = r.headers.get("x-requests-remaining", "?") if r else "?"
            logger.info(f"  Progress: {i+1}/{len(group_b)} | "
                        f"recovered={recovered} no_mkt={confirmed_no_mkt} err={errors} | "
                        f"credits={credits}")
            df.to_parquet(OUT_PATH, index=False)

        time.sleep(0.5)

    df.to_parquet(OUT_PATH, index=False)
    logger.info(f"\nRepull complete: recovered={recovered}, confirmed_no_market={confirmed_no_mkt}, "
                f"errors={errors}")

    # STEP 4
    logger.info("\nSTEP 4 — FINAL COVERAGE REPORT")
    logger.info("=" * 60)

    total_ok = df[df["pull_status"] == "ok"]["game_id"].nunique()
    total_nm = df[df["pull_status"].isin(["no_market", "no_market_confirmed"])]["game_id"].nunique()
    total_err = df[df["pull_status"].str.startswith("api_error", na=False)]["game_id"].nunique()
    total_games = total_ok + total_nm + total_err

    logger.info(f"  OK: {total_ok} | no_market: {total_nm} | errors: {total_err}")
    logger.info(f"  Overall coverage: {total_ok}/{total_games} ({total_ok/total_games*100:.1f}%)")

    for year, note in [(2023, " (May+)"), (2024, ""), (2025, "")]:
        if year == 2023:
            total_ft = len(ft[(ft["season"] == 2023) & (ft["date"].astype(str) >= "2023-05-03")])
        else:
            total_ft = len(ft[ft["season"] == year])
        year_ok = df[(df["pull_status"] == "ok") & (df["date"].str[:4] == str(year))]["game_id"].nunique()
        pct = year_ok / total_ft * 100 if total_ft > 0 else 0
        flag = "" if pct >= 75 else " *** LOW"
        logger.info(f"  {year}{note}: {year_ok}/{total_ft} ({pct:.1f}%){flag}")

    logger.info(f"\n  West Coast recovered: {recovered}")
    logger.info(f"  Still missing after repull: {total_nm + total_err}")

    # STEP 5
    logger.info("\nSTEP 5 — UPDATED MISSING DIAGNOSTICS")
    logger.info("=" * 60)

    still_missing = df[~df["pull_status"].isin(["ok"])].drop_duplicates("game_id")
    if len(still_missing) > 0:
        home_counts = still_missing["home_team"].value_counts()
        away_counts = still_missing["away_team"].value_counts()
        team_total = (home_counts.add(away_counts, fill_value=0)).sort_values(ascending=False)
        logger.info("  Top 10 teams still missing:")
        for t, n in team_total.head(10).items():
            logger.info(f"    {t}: {int(n)}")

        # Month distribution
        months = still_missing["date"].astype(str).str[:7]
        logger.info("\n  Still missing by month:")
        for m, n in months.value_counts().sort_index().items():
            logger.info(f"    {m}: {n}")

        # Check if West Coast still dominates
        west_coast = {"LAA", "LAD", "SFG", "SDP", "SEA", "OAK", "ARI", "COL"}
        wc_missing = still_missing[
            still_missing["home_team"].isin(west_coast) | still_missing["away_team"].isin(west_coast)
        ]
        logger.info(f"\n  West Coast involvement in remaining missing: "
                    f"{len(wc_missing)}/{len(still_missing)} ({len(wc_missing)/len(still_missing)*100:.0f}%)")
    else:
        logger.info("  No missing games remaining!")


if __name__ == "__main__":
    main()
