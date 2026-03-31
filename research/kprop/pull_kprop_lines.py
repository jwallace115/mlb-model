#!/usr/bin/env python3
"""
Historical backfill: pitcher_strikeouts lines from The Odds API.
Seasons: 2023 (May 3+), 2024, 2025 regular season.
Output: research/kprop/data/kprop_lines_historical.parquet
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("kprop_backfill")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT_DIR = PROJECT / "research" / "kprop" / "data"
OUT_PATH = OUT_DIR / "kprop_lines_historical.parquet"
EMAP_PATH = PROJECT / "research" / "team_totals" / "data" / "event_id_map.parquet"

# Load API key
with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
BASE = "https://api.the-odds-api.com/v4"

# Load event map
emap = pd.read_parquet(EMAP_PATH)
emap["game_id"] = emap["game_id"].astype(str)

# Load feature table for commence times and team abbreviations
ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)

# Load pitcher game logs for name→ID matching
from config import ODDS_API_TEAM_MAP
ABB_TO_FULL = {v: k for k, v in ODDS_API_TEAM_MAP.items()}

# Build pitcher name→ID lookup from sim_inputs and pitcher_game_logs
pgl = pd.read_parquet(PROJECT / "mlb" / "data" / "pitcher_game_logs.parquet")
pgl_starters = pgl[pgl["starter_flag"] == 1].copy()
# Normalize names: "Last, First" or "First Last" → lowercase
_name_to_id = {}
for _, r in pgl_starters.drop_duplicates("player_id").iterrows():
    name = str(r.get("player_name", "")).strip()
    pid = int(r["player_id"])
    if name:
        _name_to_id[name.lower()] = pid
        # Also try "First Last" format
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            _name_to_id[f"{parts[1]} {parts[0]}".lower()] = pid

logger.info(f"Pitcher name→ID lookup: {len(_name_to_id)} entries")

COLS = [
    "game_id", "odds_api_event_id", "date", "home_team", "away_team",
    "pitcher_name", "pitcher_id", "k_line", "over_price", "under_price",
    "primary_book", "books_count", "canonical_line",
    "snapshot_timestamp", "pull_status", "actual_k",
]


def _load():
    if OUT_PATH.exists():
        return pd.read_parquet(OUT_PATH)
    return pd.DataFrame(columns=COLS)


def _save(df):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)


def _get_commence(game_id, game_date):
    gft = ft[ft["game_pk"] == str(game_id)]
    if len(gft) > 0:
        h = int(gft.iloc[0].get("game_hour_utc", 23))
        return datetime.strptime(game_date, "%Y-%m-%d") + timedelta(hours=h)
    return datetime.strptime(game_date, "%Y-%m-%d") + timedelta(hours=23)


def _match_pitcher_id(name):
    """Match API pitcher name to pipeline sp_id."""
    if not name:
        return None
    key = name.strip().lower()
    if key in _name_to_id:
        return _name_to_id[key]
    # Try last name only (risky but catches most)
    parts = key.split()
    if len(parts) >= 2:
        last = parts[-1]
        matches = [v for k, v in _name_to_id.items() if k.endswith(last)]
        if len(matches) == 1:
            return matches[0]
    return None


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


def _extract_kprop(bookmakers, game_id, game_date, home_team, away_team, eid, timestamp):
    """Extract pitcher K prop rows from bookmakers list."""
    # Collect all outcomes by pitcher
    pitcher_data = {}  # pitcher_name → {book: {line, over, under}}

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
        # Build candidates with both over and under
        candidates = []
        for bk_key, data in books.items():
            if "over" in data and "under" in data and data.get("line") is not None:
                balance = abs(data["over"] - data["under"])
                candidates.append({
                    "book": bk_key,
                    "line": data["line"],
                    "over": data["over"],
                    "under": data["under"],
                    "balance": balance,
                })

        if not candidates:
            continue

        # Canonical: most balanced, tiebreaker lower line
        candidates.sort(key=lambda c: (c["balance"], c["line"]))
        canonical = candidates[0]

        # Primary book: FanDuel if present, else canonical
        fd = [c for c in candidates if c["book"] == "fanduel"]
        primary = fd[0] if fd else canonical

        pid = _match_pitcher_id(pitcher_name)

        rows.append({
            "game_id": game_id,
            "odds_api_event_id": eid,
            "date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "pitcher_name": pitcher_name,
            "pitcher_id": pid,
            "k_line": primary["line"],
            "over_price": primary["over"],
            "under_price": primary["under"],
            "primary_book": primary["book"],
            "books_count": len(candidates),
            "canonical_line": 1 if primary["line"] == canonical["line"] and primary["book"] == canonical["book"] else 0,
            "snapshot_timestamp": timestamp,
            "pull_status": "ok",
            "actual_k": None,
        })

        # If primary != canonical, also flag canonical
        if primary["book"] != canonical["book"] or primary["line"] != canonical["line"]:
            rows[-1]["canonical_line"] = 0
            # Add canonical row
            rows.append({
                "game_id": game_id,
                "odds_api_event_id": eid,
                "date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "pitcher_name": pitcher_name,
                "pitcher_id": pid,
                "k_line": canonical["line"],
                "over_price": canonical["over"],
                "under_price": canonical["under"],
                "primary_book": canonical["book"],
                "books_count": len(candidates),
                "canonical_line": 1,
                "snapshot_timestamp": timestamp,
                "pull_status": "ok",
                "actual_k": None,
            })

    return rows


def main():
    logger.info(f"API key: {API_KEY[:10]}...")

    # Build target game list
    # Filter: regular season 2023 (May 3+), 2024, 2025
    targets = []
    for _, em in emap.iterrows():
        gid = str(em["game_id"])
        gdate = str(em["date"])

        # Season filter
        year = int(gdate[:4])
        if year == 2023 and gdate < "2023-05-03":
            continue
        if year < 2023 or year > 2025:
            continue

        # Confirm it's regular season (in feature table)
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

    logger.info(f"Target games: {len(targets)}")

    # Load existing results for resume
    df = _load()
    completed_games = set(df[df["pull_status"] == "ok"]["game_id"].astype(str).unique())
    logger.info(f"Already completed: {len(completed_games)} games")

    # Filter to remaining
    remaining = [t for t in targets if t["game_id"] not in completed_games]
    logger.info(f"Remaining to pull: {len(remaining)}")

    if not remaining:
        logger.info("All games already pulled!")
        _print_coverage(df)
        return

    ok = err = no_mkt = 0
    new_rows = []

    for i, t in enumerate(remaining):
        gid = t["game_id"]
        gdate = t["date"]
        eid = t["event_id"]
        home = t["home_team"]
        away = t["away_team"]

        ct = _get_commence(gid, gdate)
        snap = (ct - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
        r = _api_call(url, {
            "apiKey": API_KEY,
            "regions": "us",
            "markets": "pitcher_strikeouts",
            "oddsFormat": "american",
            "date": snap,
        })

        if r and r.status_code == 200:
            data = r.json()
            inner = data.get("data", data)
            bks = inner.get("bookmakers", [])
            timestamp = data.get("timestamp", "")

            if bks:
                rows = _extract_kprop(bks, gid, gdate, home, away, eid, timestamp)
                if rows:
                    new_rows.extend(rows)
                    ok += 1
                else:
                    # Bookmakers present but no pitcher_strikeouts outcomes
                    new_rows.append({
                        "game_id": gid, "odds_api_event_id": eid,
                        "date": gdate, "home_team": home, "away_team": away,
                        "pitcher_name": None, "pitcher_id": None,
                        "k_line": None, "over_price": None, "under_price": None,
                        "primary_book": None, "books_count": 0,
                        "canonical_line": 0, "snapshot_timestamp": timestamp,
                        "pull_status": "no_market", "actual_k": None,
                    })
                    no_mkt += 1
            else:
                new_rows.append({
                    "game_id": gid, "odds_api_event_id": eid,
                    "date": gdate, "home_team": home, "away_team": away,
                    "pitcher_name": None, "pitcher_id": None,
                    "k_line": None, "over_price": None, "under_price": None,
                    "primary_book": None, "books_count": 0,
                    "canonical_line": 0, "snapshot_timestamp": timestamp,
                    "pull_status": "no_market", "actual_k": None,
                })
                no_mkt += 1
        elif r and r.status_code == 422:
            new_rows.append({
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "pitcher_name": None, "pitcher_id": None,
                "k_line": None, "over_price": None, "under_price": None,
                "primary_book": None, "books_count": 0,
                "canonical_line": 0, "snapshot_timestamp": "",
                "pull_status": "no_market", "actual_k": None,
            })
            no_mkt += 1
        else:
            status_code = r.status_code if r else "timeout"
            new_rows.append({
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "pitcher_name": None, "pitcher_id": None,
                "k_line": None, "over_price": None, "under_price": None,
                "primary_book": None, "books_count": 0,
                "canonical_line": 0, "snapshot_timestamp": "",
                "pull_status": f"api_error_{status_code}", "actual_k": None,
            })
            err += 1

        # Progress + checkpoint
        total_done = i + 1
        if total_done % 200 == 0 or total_done == len(remaining):
            credits = r.headers.get("x-requests-remaining", "?") if r else "?"
            logger.info(f"  Progress: {total_done}/{len(remaining)} | "
                        f"ok={ok} no_market={no_mkt} errors={err} | "
                        f"credits remaining={credits}")
            # Checkpoint save
            if new_rows:
                new_df = pd.DataFrame(new_rows, columns=COLS)
                combined = pd.concat([df, new_df], ignore_index=True)
                _save(combined)
                df = combined
                new_rows = []

        time.sleep(0.5)

    # Final save
    if new_rows:
        new_df = pd.DataFrame(new_rows, columns=COLS)
        df = pd.concat([df, new_df], ignore_index=True)
        _save(df)

    logger.info(f"\nBackfill complete: ok={ok}, no_market={no_mkt}, errors={err}")
    _print_coverage(df)


def _print_coverage(df):
    """Print coverage summary by season."""
    logger.info("\n" + "=" * 60)
    logger.info("COVERAGE SUMMARY")
    logger.info("=" * 60)

    ok_games = df[df["pull_status"] == "ok"]["game_id"].nunique()

    for year, note in [(2023, " (May+)"), (2024, ""), (2025, "")]:
        year_str = str(year)
        total_ft = len(ft[ft["season"] == year])
        if year == 2023:
            total_ft = len(ft[(ft["season"] == 2023) & (ft["date"].astype(str) >= "2023-05-03")])

        year_ok = df[(df["pull_status"] == "ok") & (df["date"].str[:4] == year_str)]["game_id"].nunique()
        pct = year_ok / total_ft * 100 if total_ft > 0 else 0
        flag = " *** LOW" if pct < 75 else ""
        logger.info(f"  {year}{note}: {year_ok}/{total_ft} games ({pct:.1f}%){flag}")

    # Pitcher ID match rate
    ok_rows = df[df["pull_status"] == "ok"]
    matched = ok_rows["pitcher_id"].notna().sum()
    total_p = len(ok_rows)
    match_pct = matched / total_p * 100 if total_p > 0 else 0
    logger.info(f"\n  Pitcher ID match rate: {matched}/{total_p} ({match_pct:.1f}%)")
    if match_pct < 80:
        logger.warning("  *** MATCH RATE BELOW 80% — review before proceeding")

    # Line distribution
    logger.info(f"\n  K line distribution (canonical only):")
    canon = ok_rows[ok_rows["canonical_line"] == 1]
    if len(canon) > 0:
        for line, n in canon["k_line"].value_counts().sort_index().items():
            logger.info(f"    {line}: {n} ({n/len(canon)*100:.1f}%)")

    # Books distribution
    logger.info(f"\n  Average books per pitcher: {ok_rows['books_count'].mean():.1f}")


if __name__ == "__main__":
    main()
