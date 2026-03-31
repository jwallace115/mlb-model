#!/usr/bin/env python3
"""
F5 Moneyline historical backfill: h2h_1st_5_innings.
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
logger = logging.getLogger("f5ml")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "f5_ml" / "data"
LINES_PATH = OUT / "f5_ml_lines_historical.parquet"
EMAP_PATH = PROJECT / "research" / "team_totals" / "data" / "event_id_map.parquet"

with open(PROJECT / ".env") as f:
    for line in f:
        if line.strip().startswith("ODDS_API_KEY"):
            API_KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
ODDS_BASE = "https://api.the-odds-api.com/v4"

emap = pd.read_parquet(EMAP_PATH)
emap["game_id"] = emap["game_id"].astype(str)

ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
ft["game_pk"] = ft["game_pk"].astype(str)

from config import ODDS_API_TEAM_MAP

COLS = [
    "game_id", "odds_api_event_id", "date", "home_team", "away_team",
    "commence_time", "home_ml_price", "away_ml_price",
    "primary_book", "books_count", "snapshot_timestamp", "pull_status",
]

LADDER = [360, 240, 120, 60, 30]


def _load():
    if LINES_PATH.exists():
        return pd.read_parquet(LINES_PATH)
    return pd.DataFrame(columns=COLS)


def _save(df):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(LINES_PATH, index=False)


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
            "game_id": gid, "event_id": em["odds_api_event_id"],
            "date": gdate,
            "home_team": gft.iloc[0].get("home_team", ""),
            "away_team": gft.iloc[0].get("away_team", ""),
        })
    return targets


def _extract_f5_ml(bookmakers, home_team):
    """Extract valid two-way F5 ML from bookmakers."""
    home_full = next((k for k, v in ODDS_API_TEAM_MAP.items() if v == home_team), None)
    valid = []

    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mkt in bk.get("markets", []):
            if mkt["key"] != "h2h_1st_5_innings":
                continue
            outcomes = mkt.get("outcomes", [])
            if len(outcomes) != 2:
                continue
            o1, o2 = outcomes[0], outcomes[1]
            if o1.get("price") is None or o2.get("price") is None:
                continue

            # Map to home/away
            if home_full and o1.get("name") == home_full:
                h_price, a_price = o1["price"], o2["price"]
            elif home_full and o2.get("name") == home_full:
                h_price, a_price = o2["price"], o1["price"]
            else:
                continue

            valid.append({"book": bk_key, "home": h_price, "away": a_price})

    return valid


def _call_api(eid, snap_ts):
    url = f"{ODDS_BASE}/historical/sports/baseball_mlb/events/{eid}/odds"
    params = {
        "apiKey": API_KEY, "regions": "us",
        "markets": "h2h_1st_5_innings",
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


def pull_lines():
    logger.info("PART 1 — F5 MONEYLINE BACKFILL")
    logger.info("=" * 60)

    targets = _build_targets()
    logger.info(f"Target games: {len(targets)}")

    df = _load()
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

        if gid in ok_gids:
            continue

        ct_utc = _get_commence_utc(gid, gdate)
        if ct_utc is None:
            df = pd.concat([df, pd.DataFrame([{
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": "", "home_ml_price": None, "away_ml_price": None,
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

            valid = _extract_f5_ml(bks, home)
            if not valid:
                time.sleep(0.3)
                continue

            # Canonical: prefer FanDuel
            fd = [v for v in valid if v["book"] == "fanduel"]
            chosen = fd[0] if fd else valid[0]

            row = {
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": ct_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home_ml_price": chosen["home"], "away_ml_price": chosen["away"],
                "primary_book": chosen["book"], "books_count": len(valid),
                "snapshot_timestamp": ts, "pull_status": "ok",
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            ok += 1
            ok_gids.add(gid)
            found = True
            break

        if not found:
            status = "no_market"
            if last_r is None or (last_r and last_r.status_code != 200):
                status = "api_error"
                err += 1
            else:
                no_mkt += 1

            df = pd.concat([df, pd.DataFrame([{
                "game_id": gid, "odds_api_event_id": eid,
                "date": gdate, "home_team": home, "away_team": away,
                "commence_time": ct_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if ct_utc else "",
                "home_ml_price": None, "away_ml_price": None,
                "primary_book": None, "books_count": 0,
                "snapshot_timestamp": "", "pull_status": status,
            }])], ignore_index=True)

        if (i + 1) % 200 == 0 or (i + 1) == len(remaining):
            credits = last_r.headers.get("x-requests-remaining", "?") if last_r else "?"
            logger.info(f"  Lines: {i+1}/{len(remaining)} | ok={ok} no_mkt={no_mkt} "
                        f"err={err} invalid={invalid} | credits={credits}")
            _save(df)

        time.sleep(0.3)

    _save(df)
    logger.info(f"Lines complete: ok={ok} no_mkt={no_mkt} err={err} invalid={invalid}")


def validate():
    logger.info("\nPART 3 — VALIDATION")
    logger.info("=" * 60)

    df = pd.read_parquet(LINES_PATH)

    # V1 — Uniqueness
    dups = df["game_id"].duplicated().sum()
    logger.info(f"V1 — Uniqueness: {dups} duplicates")

    # V2 — Line sanity
    ok_df = df[df["pull_status"] == "ok"]
    null_h = ok_df["home_ml_price"].isna().sum()
    null_a = ok_df["away_ml_price"].isna().sum()
    logger.info(f"V2 — Null home_ml_price: {null_h}, null away_ml_price: {null_a}")

    # V3 — Season coverage
    logger.info(f"V3 — Season coverage:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_ok = len(ok_df[ok_df["date"].str[:4] == str(year)])
        pct = n_ok / total * 100
        flag = "" if pct >= 75 else " *** LOW"
        logger.info(f"  {year}: {n_ok}/{total} ({pct:.1f}%){flag}")
    total_all = len(ft[ft["season"].isin([2024, 2025])])
    overall_ok = len(ok_df)
    logger.info(f"  Overall: {overall_ok}/{total_all} ({overall_ok/total_all*100:.1f}%)")

    # V4 — Join coverage
    scores = pd.read_parquet(PROJECT / "research" / "f5_runline" / "data" / "f5_scores.parquet")
    scores = scores[scores["score_status"] == "ok"].copy()
    scores["game_id"] = scores["game_id"].astype(str)
    joined = ok_df.merge(scores, on="game_id", how="inner", suffixes=("_l", "_s"))

    logger.info(f"V4 — Join coverage:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_j = len(joined[joined["date_l"].str[:4] == str(year)])
        logger.info(f"  {year}: {n_j}/{total} ({n_j/total*100:.1f}%)")
    logger.info(f"  Overall: {len(joined)}/{total_all} ({len(joined)/total_all*100:.1f}%)")

    # V5 — Push rate and book quality
    logger.info(f"V5 — Push rate and book quality:")
    push_rate = (joined["f5_margin"] == 0).mean() * 100
    avg_books = ok_df["books_count"].mean()
    med_h = ok_df["home_ml_price"].median()
    med_a = ok_df["away_ml_price"].median()
    fd_pct = (ok_df["primary_book"] == "fanduel").mean() * 100
    logger.info(f"  Push rate: {push_rate:.1f}%")
    logger.info(f"  Avg books: {avg_books:.1f}")
    logger.info(f"  Median home ML: {med_h:.0f}")
    logger.info(f"  Median away ML: {med_a:.0f}")
    logger.info(f"  FanDuel primary: {fd_pct:.0f}%")

    # Coverage gate
    logger.info(f"\nCOVERAGE GATE:")
    for year in [2024, 2025]:
        total = len(ft[ft["season"] == year])
        n_ok = len(ok_df[ok_df["date"].str[:4] == str(year)])
        pct = n_ok / total * 100
        status = "READY" if pct >= 75 else "PARTIAL" if pct >= 50 else "FAIL"
        logger.info(f"  {year} lines: {status} ({pct:.1f}%)")
    j_pct = len(joined) / total_all * 100
    j_status = "READY" if j_pct >= 70 else "PARTIAL" if j_pct >= 50 else "FAIL"
    logger.info(f"  Joined: {j_status} ({j_pct:.1f}%)")

    # Part 4 — Signal B margin distribution
    logger.info(f"\nPART 4 — SIGNAL B MARGIN DISTRIBUTION")
    logger.info("=" * 60)

    si24 = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_historical_2022_2024.parquet")
    si24 = si24[si24["season"] == 2024]
    si25 = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_2025.parquet")
    si = pd.concat([si24, si25], ignore_index=True)
    si["game_id"] = si["game_pk"].astype(str)

    si_home = si[si["is_home"] == 1][["game_id", "sp_xfip"]].rename(columns={"sp_xfip": "home_xfip"})
    si_away = si[si["is_home"] == 0][["game_id", "sp_xfip"]].rename(columns={"sp_xfip": "away_xfip"})

    jj = joined.merge(si_home, on="game_id", how="left")
    jj = jj.merge(si_away, on="game_id", how="left")
    jj["xfip_gap"] = jj["away_xfip"] - jj["home_xfip"]

    sig_b = jj[jj["xfip_gap"] >= 1.0]
    logger.info(f"  Signal B games (xfip_gap >= 1.0): {len(sig_b)}")

    if len(sig_b) > 0:
        margin = sig_b["f5_margin"]
        total = len(sig_b)
        logger.info(f"  F5 margin = +1 (home wins by 1): {(margin == 1).sum()} ({(margin == 1).mean()*100:.1f}%)")
        logger.info(f"  F5 margin = +2:                  {(margin == 2).sum()} ({(margin == 2).mean()*100:.1f}%)")
        logger.info(f"  F5 margin = +3+:                 {(margin >= 3).sum()} ({(margin >= 3).mean()*100:.1f}%)")
        logger.info(f"  F5 margin = 0 (push):            {(margin == 0).sum()} ({(margin == 0).mean()*100:.1f}%)")
        logger.info(f"  F5 margin < 0 (loss):            {(margin < 0).sum()} ({(margin < 0).mean()*100:.1f}%)")

        # Compare ML vs RL value
        wins_any = (margin > 0).sum()
        wins_1plus = (margin >= 1).sum()  # same as wins_any for integers
        logger.info(f"\n  Home wins (any margin): {wins_any} ({wins_any/total*100:.1f}%)")
        logger.info(f"  Pushes:                 {(margin == 0).sum()} ({(margin == 0).mean()*100:.1f}%)")
        logger.info(f"  Losses:                 {(margin < 0).sum()} ({(margin < 0).mean()*100:.1f}%)")
        logger.info(f"\n  ML win rate (pushes excluded): {wins_any/(wins_any+(margin<0).sum())*100:.1f}%")
        logger.info(f"  RL win rate (pushes excluded): {wins_any/(wins_any+(margin<0).sum())*100:.1f}% (same — spread is -0.5)")
        logger.info(f"\n  KEY: ML and RL have identical win rates for -0.5 spread.")
        logger.info(f"  The difference is in pricing structure only.")

        # Show typical ML prices for Signal B
        sig_b_ml = sig_b[["home_ml_price", "away_ml_price", "f5_margin"]].copy()
        logger.info(f"\n  Signal B ML prices:")
        logger.info(f"    Median home ML: {sig_b_ml['home_ml_price'].median():.0f}")
        logger.info(f"    Median away ML: {sig_b_ml['away_ml_price'].median():.0f}")
        logger.info(f"    Mean home ML:   {sig_b_ml['home_ml_price'].mean():.0f}")


if __name__ == "__main__":
    pull_lines()
    validate()
