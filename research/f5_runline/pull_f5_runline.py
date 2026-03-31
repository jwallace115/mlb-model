#!/usr/bin/env python3
"""
F5 Run Line historical backfill: spreads_1st_5_innings + per-team F5 scores.
2024-2025 regular season only.
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
logger = logging.getLogger("f5rl")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "f5_runline" / "data"
LINES_PATH = OUT / "f5_runline_lines_historical.parquet"
SCORES_PATH = OUT / "f5_scores.parquet"
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

from config import ODDS_API_TEAM_MAP

LINES_COLS = [
    "game_id", "odds_api_event_id", "date", "home_team", "away_team",
    "commence_time", "home_line", "away_line", "home_price", "away_price",
    "primary_book", "books_count", "snapshot_timestamp", "pull_status",
]

SCORES_COLS = [
    "game_id", "date", "home_team", "away_team",
    "home_f5_score", "away_f5_score", "f5_margin", "f5_result_home",
    "score_status",
]

LADDER = [360, 240, 120, 60, 30]  # minutes before commence


def _load_lines():
    if LINES_PATH.exists():
        return pd.read_parquet(LINES_PATH)
    return pd.DataFrame(columns=LINES_COLS)


def _save_lines(df):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(LINES_PATH, index=False)


def _load_scores():
    if SCORES_PATH.exists():
        return pd.read_parquet(SCORES_PATH)
    return pd.DataFrame(columns=SCORES_COLS)


def _save_scores(df):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SCORES_PATH, index=False)


def _get_commence_utc(game_id, game_date):
    gft = ft[ft["game_pk"] == str(game_id)]
    if len(gft) == 0:
        return None
    hour = int(gft.iloc[0].get("game_hour_utc", 20))
    base = datetime.strptime(game_date, "%Y-%m-%d")
    if hour >= 24:
        return base + timedelta(hours=hour)
    elif hour < 6:
        return base + timedelta(days=1, hours=hour)
    else:
        return base + timedelta(hours=hour)


def _build_targets():
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
        targets.append({
            "game_id": gid,
            "event_id": em["odds_api_event_id"],
            "date": gdate,
            "home_team": gft.iloc[0].get("home_team", ""),
            "away_team": gft.iloc[0].get("away_team", ""),
        })
    return targets


def _extract_f5_spread(bookmakers):
    """Extract valid standard -0.5/+0.5 F5 run line."""
    valid = []
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "spreads_1st_5_innings":
                continue
            outcomes = mkt.get("outcomes", [])
            if len(outcomes) != 2:
                continue
            o1, o2 = outcomes[0], outcomes[1]
            p1, p2 = o1.get("point"), o2.get("point")
            pr1, pr2 = o1.get("price"), o2.get("price")
            if p1 is None or p2 is None or pr1 is None or pr2 is None:
                continue
            # Check standard line: one is +0.5, other is -0.5
            if not ({p1, p2} == {0.5, -0.5}):
                continue
            # Identify home/away
            # The API uses team names; we need to figure out which is home
            valid.append({
                "book": bk_key,
                "team1": o1.get("name", ""), "point1": p1, "price1": pr1,
                "team2": o2.get("name", ""), "point2": p2, "price2": pr2,
            })
    return valid


def _call_api(eid, snap_ts):
    url = f"{ODDS_BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
    params = {
        "apiKey": API_KEY, "regions": "us",
        "markets": "spreads_1st_5_innings",
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


# ═══ PART 1: F5 RUN LINE LINES ═══

def pull_lines():
    logger.info("PART 1 — F5 RUN LINE LINES BACKFILL")
    logger.info("=" * 60)

    targets = _build_targets()
    logger.info(f"Target games: {len(targets)}")

    df = _load_lines()
    ok_gids = set(df[df["pull_status"] == "ok"]["game_id"].astype(str))
    remaining = [t for t in targets if t["game_id"] not in ok_gids]
    logger.info(f"Already ok: {len(ok_gids)}, remaining: {len(remaining)}")

    ok = no_mkt = err = invalid = 0
    last_r = None

    for i, t in enumerate(remaining):
        gid = t["game_id"]
        eid = t["event_id"]
        gdate = t["date"]
        home = t["home_team"]
        away = t["away_team"]

        # Skip if already ok from prior checkpoint
        if gid in ok_gids:
            continue

        ct_utc = _get_commence_utc(gid, gdate)
        if ct_utc is None:
            df = pd.concat([df, pd.DataFrame([{
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": "", "home_line": None, "away_line": None,
                "home_price": None, "away_price": None,
                "primary_book": None, "books_count": 0,
                "snapshot_timestamp": "", "pull_status": "api_error",
            }])], ignore_index=True)
            err += 1
            continue

        # Remove old non-ok row
        df = df[~((df["game_id"].astype(str) == gid) & (df["pull_status"] != "ok"))]

        found = False
        for offset_min in LADDER:
            snap_ts = ct_utc - timedelta(minutes=offset_min)
            r, bks, ts = _call_api(eid, snap_ts)
            last_r = r

            if bks is None:
                time.sleep(0.5)
                continue
            if not bks:
                time.sleep(0.3)
                continue

            valid = _extract_f5_spread(bks)
            if not valid:
                time.sleep(0.3)
                continue

            # Canonical: prefer FanDuel
            fd = [v for v in valid if v["book"] == "fanduel"]
            chosen = fd[0] if fd else valid[0]

            # Map team names to home/away
            home_full = None
            for full_name, abb in ODDS_API_TEAM_MAP.items():
                if abb == home:
                    home_full = full_name
                    break

            if home_full and chosen["team1"] == home_full:
                h_line, h_price = chosen["point1"], chosen["price1"]
                a_line, a_price = chosen["point2"], chosen["price2"]
            elif home_full and chosen["team2"] == home_full:
                h_line, h_price = chosen["point2"], chosen["price2"]
                a_line, a_price = chosen["point1"], chosen["price1"]
            else:
                # Fallback: -0.5 side is favorite
                if chosen["point1"] == -0.5:
                    h_line, h_price = chosen["point1"], chosen["price1"]
                    a_line, a_price = chosen["point2"], chosen["price2"]
                else:
                    h_line, h_price = chosen["point2"], chosen["price2"]
                    a_line, a_price = chosen["point1"], chosen["price1"]

            row = {
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": ct_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home_line": h_line, "away_line": a_line,
                "home_price": h_price, "away_price": a_price,
                "primary_book": chosen["book"], "books_count": len(valid),
                "snapshot_timestamp": ts, "pull_status": "ok",
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            ok += 1
            ok_gids.add(gid)
            found = True
            break

        if not found:
            # Check if any timestamp had bookmakers but no valid line
            saw_market = False
            for offset_min in LADDER:
                snap_ts = ct_utc - timedelta(minutes=offset_min)
                r2, bks2, _ = _call_api(eid, snap_ts)
                if bks2 and len(bks2) > 0:
                    for bk in bks2:
                        for m in bk.get("markets", []):
                            if m["key"] == "spreads_1st_5_innings":
                                saw_market = True
                    break
                time.sleep(0.3)

            if saw_market:
                status = "invalid_line"
                invalid += 1
            elif last_r is None or (last_r and last_r.status_code != 200):
                status = "api_error"
                err += 1
            else:
                status = "no_market"
                no_mkt += 1

            df = pd.concat([df, pd.DataFrame([{
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": ct_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home_line": None, "away_line": None,
                "home_price": None, "away_price": None,
                "primary_book": None, "books_count": 0,
                "snapshot_timestamp": "", "pull_status": status,
            }])], ignore_index=True)

        if (i + 1) % 200 == 0 or (i + 1) == len(remaining):
            credits = last_r.headers.get("x-requests-remaining", "?") if last_r else "?"
            logger.info(f"  Lines: {i+1}/{len(remaining)} | ok={ok} no_mkt={no_mkt} "
                        f"err={err} invalid={invalid} | credits={credits}")
            _save_lines(df)

        time.sleep(0.3)

    _save_lines(df)
    logger.info(f"Lines complete: ok={ok} no_mkt={no_mkt} err={err} invalid={invalid}")


# ═══ PART 2: PER-TEAM F5 SCORES ═══

def pull_scores():
    logger.info("\nPART 2 — PER-TEAM F5 SCORES")
    logger.info("=" * 60)

    targets = _build_targets()
    logger.info(f"Target games: {len(targets)}")

    df = _load_scores()
    ok_gids = set(df[df["score_status"] == "ok"]["game_id"].astype(str))
    remaining = [t for t in targets if t["game_id"] not in ok_gids]
    logger.info(f"Already ok: {len(ok_gids)}, remaining: {len(remaining)}")

    ok = err = 0

    for i, t in enumerate(remaining):
        gid = t["game_id"]
        gdate = t["date"]
        home = t["home_team"]
        away = t["away_team"]

        df = df[~((df["game_id"].astype(str) == gid) & (df["score_status"] != "ok"))]

        try:
            r = requests.get(f"{MLB_BASE}/game/{gid}/linescore", timeout=15)
            if r.status_code == 200:
                ls = r.json()
                innings = ls.get("innings", [])
                if len(innings) >= 5:
                    h5 = sum((inn.get("home", {}).get("runs", 0) or 0) for inn in innings[:5])
                    a5 = sum((inn.get("away", {}).get("runs", 0) or 0) for inn in innings[:5])
                    margin = h5 - a5
                    result = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
                    row = {
                        "game_id": gid, "date": gdate,
                        "home_team": home, "away_team": away,
                        "home_f5_score": h5, "away_f5_score": a5,
                        "f5_margin": margin, "f5_result_home": result,
                        "score_status": "ok",
                    }
                    ok += 1
                else:
                    row = {
                        "game_id": gid, "date": gdate,
                        "home_team": home, "away_team": away,
                        "home_f5_score": None, "away_f5_score": None,
                        "f5_margin": None, "f5_result_home": None,
                        "score_status": "api_error",
                    }
                    err += 1
            else:
                row = {
                    "game_id": gid, "date": gdate,
                    "home_team": home, "away_team": away,
                    "home_f5_score": None, "away_f5_score": None,
                    "f5_margin": None, "f5_result_home": None,
                    "score_status": "api_error",
                }
                err += 1
        except Exception:
            row = {
                "game_id": gid, "date": gdate,
                "home_team": home, "away_team": away,
                "home_f5_score": None, "away_f5_score": None,
                "f5_margin": None, "f5_result_home": None,
                "score_status": "api_error",
            }
            err += 1

        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        if (i + 1) % 500 == 0 or (i + 1) == len(remaining):
            logger.info(f"  Scores: {i+1}/{len(remaining)} | ok={ok} err={err}")
            _save_scores(df)

        if (i + 1) % 50 == 0:
            time.sleep(1)

    _save_scores(df)
    logger.info(f"Scores complete: ok={ok} err={err}")


# ═══ PART 3: VALIDATION ═══

def validate():
    logger.info("\nPART 3 — VALIDATION")
    logger.info("=" * 60)

    lines = pd.read_parquet(LINES_PATH)
    scores = pd.read_parquet(SCORES_PATH)

    # V1 — Uniqueness
    logger.info(f"V1 — Uniqueness:")
    logger.info(f"  Lines duplicates: {lines['game_id'].duplicated().sum()}")
    logger.info(f"  Scores duplicates: {scores['game_id'].duplicated().sum()}")

    # V2 — Line sanity
    ok_lines = lines[lines["pull_status"] == "ok"]
    bad_pair = ok_lines[ok_lines["home_line"] != -ok_lines["away_line"]]
    not_half = ok_lines[~ok_lines["home_line"].isin([-0.5, 0.5])]
    null_prices = ok_lines[ok_lines["home_price"].isna() | ok_lines["away_price"].isna()]
    logger.info(f"\nV2 — Line sanity (ok rows, N={len(ok_lines)}):")
    logger.info(f"  Non-opposite lines: {len(bad_pair)}")
    logger.info(f"  Non-standard (-0.5/+0.5): {len(not_half)}")
    logger.info(f"  Null prices: {len(null_prices)}")

    # V3 — Season coverage
    logger.info(f"\nV3 — Season coverage:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_ok = len(ok_lines[ok_lines["date"].str[:4] == str(year)])
        pct = n_ok / total * 100
        flag = "" if pct >= 75 else " *** LOW"
        logger.info(f"  Lines {year}: {n_ok}/{total} ({pct:.1f}%){flag}")

        ok_scores = scores[scores["score_status"] == "ok"]
        s_ok = len(ok_scores[ok_scores["date"].str[:4] == str(year)])
        s_pct = s_ok / total * 100
        logger.info(f"  Scores {year}: {s_ok}/{total} ({s_pct:.1f}%)")

    # V4 — Join coverage
    ok_scores = scores[scores["score_status"] == "ok"]
    joined = ok_lines.merge(ok_scores, on="game_id", how="inner", suffixes=("_l", "_s"))
    logger.info(f"\nV4 — Join coverage:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_j = len(joined[joined["date_l"].str[:4] == str(year)])
        pct = n_j / total * 100
        logger.info(f"  {year}: {n_j}/{total} ({pct:.1f}%)")
    total_all = len(ft[ft["season"].isin([2024, 2025])])
    logger.info(f"  Total: {len(joined)}/{total_all} ({len(joined)/total_all*100:.1f}%)")

    # V5 — Push rate and outcome mix
    logger.info(f"\nV5 — Push rate and outcome mix:")
    logger.info(f"  Push rate (f5_margin==0): {(joined['f5_margin']==0).mean()*100:.1f}%")
    logger.info(f"  Home wins: {(joined['f5_result_home']==1.0).mean()*100:.1f}%")
    logger.info(f"  Away wins: {(joined['f5_result_home']==0.0).mean()*100:.1f}%")
    logger.info(f"  Ties: {(joined['f5_result_home']==0.5).mean()*100:.1f}%")
    logger.info(f"  Mean f5_margin: {joined['f5_margin'].mean():+.3f}")
    logger.info(f"  Std f5_margin: {joined['f5_margin'].std():.3f}")

    # V6 — Book quality
    logger.info(f"\nV6 — Book quality:")
    for year in [2024, 2025]:
        yr_ok = ok_lines[ok_lines["date"].str[:4] == str(year)]
        if len(yr_ok) == 0:
            continue
        logger.info(f"  {year}: avg_books={yr_ok['books_count'].mean():.1f}, "
                    f"med_home_price={yr_ok['home_price'].median():.0f}, "
                    f"med_away_price={yr_ok['away_price'].median():.0f}, "
                    f"FD_primary={( yr_ok['primary_book']=='fanduel').mean()*100:.0f}%")

    # Coverage gate
    logger.info(f"\n{'='*60}")
    logger.info("COVERAGE GATE")
    logger.info("=" * 60)

    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        l_ok = len(ok_lines[ok_lines["date"].str[:4] == str(year)])
        s_ok = len(ok_scores[ok_scores["date"].str[:4] == str(year)])
        l_pct = l_ok / total * 100
        s_pct = s_ok / total * 100
        l_status = "READY" if l_pct >= 75 else "PARTIAL" if l_pct >= 50 else "FAIL"
        s_status = "READY" if s_pct >= 95 else "PARTIAL" if s_pct >= 75 else "FAIL"
        logger.info(f"  lines_{year}_status = {l_status} ({l_pct:.1f}%)")
        logger.info(f"  scores_{year}_status = {s_status} ({s_pct:.1f}%)")

    j_pct = len(joined) / total_all * 100
    j_status = "READY" if j_pct >= 70 else "PARTIAL" if j_pct >= 50 else "FAIL"
    logger.info(f"  joined_dataset_status = {j_status} ({j_pct:.1f}%)")


if __name__ == "__main__":
    pull_lines()
    pull_scores()
    validate()
