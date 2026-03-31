#!/usr/bin/env python3
"""
NFL Phase 1: Build canonical game table from nflreadpy.

Includes: scores, QBs, rest, closing lines, weather, dome/roof status.
Weather pulled from Open-Meteo for outdoor games only.
Closing lines from nflreadpy schedule data (100% coverage 2019-2024).

Output: nfl/data/nfl_canonical.parquet
"""

import json
import logging
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NFL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(NFL_DIR, "data")
CANONICAL_PATH = os.path.join(DATA_DIR, "nfl_canonical.parquet")
STADIUM_PATH = os.path.join(DATA_DIR, "stadium_info.json")


def load_stadium_info() -> dict:
    with open(STADIUM_PATH) as f:
        return json.load(f)


def fetch_weather(lat: float, lon: float, date: str, hour: int = 17) -> dict:
    """Fetch historical weather from Open-Meteo. Returns temp_f, wind_mph, precip_mm."""
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat, "longitude": lon,
                "start_date": date, "end_date": date,
                "hourly": "temperature_2m,wind_speed_10m,precipitation",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
            timeout=15,
        )
        r.raise_for_status()
        h = r.json().get("hourly", {})
        idx = min(hour, len(h.get("temperature_2m", [])) - 1)
        if idx < 0:
            return {}
        return {
            "temperature": h["temperature_2m"][idx],
            "wind_speed": h["wind_speed_10m"][idx],
            "precipitation": h["precipitation"][idx],
        }
    except Exception as e:
        logger.debug(f"Weather fetch failed for {date} ({lat},{lon}): {e}")
        return {}


def build_canonical(seasons=None, fetch_wx=True):
    import nflreadpy

    if seasons is None:
        seasons = list(range(2019, 2025))

    stadiums = load_stadium_info()

    logger.info(f"Loading schedules for {seasons}...")
    sched = nflreadpy.load_schedules(seasons).to_pandas()
    logger.info(f"Loaded {len(sched)} games")

    # Standardize game_type
    game_type_map = {"REG": "regular", "WC": "playoff", "DIV": "playoff",
                     "CON": "playoff", "SB": "playoff"}
    sched["game_type_std"] = sched["game_type"].map(game_type_map).fillna("regular")

    # Neutral site
    sched["neutral_site"] = sched["location"] == "Neutral"

    # Dome / roof
    sched["is_dome"] = sched["roof"].isin(["dome", "closed"])
    sched["has_retractable_roof"] = False
    sched["roof_closed"] = None

    # Apply stadium info for retractable roof
    for _, row in sched.iterrows():
        home = row["home_team"]
        info = stadiums.get(home, {})
        if info.get("has_retractable_roof"):
            sched.loc[sched["game_id"] == row["game_id"], "has_retractable_roof"] = True

    # Roof closed: use nflreadpy's roof field
    sched.loc[sched["roof"] == "closed", "roof_closed"] = True
    sched.loc[sched["roof"] == "open", "roof_closed"] = False

    # Weather: use nflreadpy temp/wind where available, backfill with Open-Meteo for outdoor
    sched["temperature"] = sched["temp"].astype(float, errors="ignore")
    sched["wind_speed_val"] = sched["wind"].astype(float, errors="ignore")
    sched["precipitation"] = None

    # Null out weather for dome/closed roof
    dome_mask = sched["is_dome"] | (sched["roof_closed"] == True)
    sched.loc[dome_mask, "temperature"] = None
    sched.loc[dome_mask, "wind_speed_val"] = None
    sched.loc[dome_mask, "precipitation"] = None

    # Backfill missing outdoor weather from Open-Meteo
    if fetch_wx:
        outdoor_missing = sched[~dome_mask & sched["temperature"].isna()].copy()
        logger.info(f"Backfilling weather for {len(outdoor_missing)} outdoor games...")
        wx_count = 0
        for idx, row in outdoor_missing.iterrows():
            home = row["home_team"]
            info = stadiums.get(home, {})
            lat = info.get("lat")
            lon = info.get("lon")
            if lat is None:
                continue
            date = str(row["gameday"])[:10]
            wx = fetch_weather(lat, lon, date)
            if wx:
                sched.loc[idx, "temperature"] = wx.get("temperature")
                sched.loc[idx, "wind_speed_val"] = wx.get("wind_speed")
                sched.loc[idx, "precipitation"] = wx.get("precipitation")
                wx_count += 1
            if wx_count % 50 == 0 and wx_count > 0:
                logger.info(f"  {wx_count} weather records fetched...")
            time.sleep(0.15)
        logger.info(f"Weather backfill complete: {wx_count} records")

    # Closing line: use total_line from nflreadpy
    sched["closing_total_line"] = sched["total_line"].astype(float, errors="ignore")
    sched["line_source"] = "nflreadpy"
    sched.loc[sched["closing_total_line"].isna(), "line_source"] = "unavailable"

    # Over/under odds for vig removal
    sched["over_price"] = sched["over_odds"].astype(float, errors="ignore")
    sched["under_price"] = sched["under_odds"].astype(float, errors="ignore")

    # Total points
    sched["total_points"] = sched["home_score"].astype(float) + sched["away_score"].astype(float)

    # Rest days
    sched["home_rest_days"] = sched["home_rest"].astype(float, errors="ignore")
    sched["away_rest_days"] = sched["away_rest"].astype(float, errors="ignore")

    # Build canonical
    canon = pd.DataFrame({
        "game_id": sched["game_id"],
        "date": sched["gameday"].astype(str),
        "season": sched["season"].astype(int),
        "week": sched["week"].astype(int),
        "game_type": sched["game_type_std"],
        "home_team": sched["home_team"],
        "away_team": sched["away_team"],
        "home_score": sched["home_score"].astype(float),
        "away_score": sched["away_score"].astype(float),
        "total_points": sched["total_points"],
        "neutral_site": sched["neutral_site"],
        "home_qb": sched["home_qb_name"],
        "away_qb": sched["away_qb_name"],
        "is_dome": sched["is_dome"],
        "has_retractable_roof": sched["has_retractable_roof"],
        "roof_closed": sched["roof_closed"],
        "temperature": sched["temperature"],
        "wind_speed": sched["wind_speed_val"],
        "precipitation": sched["precipitation"],
        "home_rest_days": sched["home_rest_days"],
        "away_rest_days": sched["away_rest_days"],
        "closing_total_line": sched["closing_total_line"],
        "over_price": sched["over_price"],
        "under_price": sched["under_price"],
        "line_source": sched["line_source"],
        "market_snapshot_status": "historical",
    })

    canon = canon.sort_values(["season", "week", "date"]).reset_index(drop=True)

    # Audit
    print(f"\n{'='*60}")
    print(f"  NFL CANONICAL TABLE AUDIT")
    print(f"{'='*60}")
    print(f"  Total rows: {len(canon)}")
    for s in sorted(canon["season"].unique()):
        sub = canon[canon["season"] == s]
        reg = sub[sub["game_type"] == "regular"]
        po = sub[sub["game_type"] == "playoff"]
        line_cov = sub["closing_total_line"].notna().mean()
        wx_cov = sub[~sub["is_dome"]]["temperature"].notna().mean() if (~sub["is_dome"]).sum() > 0 else 1.0
        neut = sub["neutral_site"].sum()
        print(f"  {s}: {len(reg)} reg + {len(po)} playoff = {len(sub)}"
              f" | lines={line_cov:.0%} | wx(outdoor)={wx_cov:.0%} | neutral={neut}")

    null_pts = canon["total_points"].isna().sum()
    print(f"\n  total_points nulls: {null_pts} {'✅' if null_pts == 0 else '❌'}")
    dup_ids = canon["game_id"].duplicated().sum()
    print(f"  duplicate game_ids: {dup_ids} {'✅' if dup_ids == 0 else '❌'}")
    print()

    os.makedirs(DATA_DIR, exist_ok=True)
    canon.to_parquet(CANONICAL_PATH, index=False)
    logger.info(f"Saved canonical: {CANONICAL_PATH} ({len(canon)} rows)")
    return canon


if __name__ == "__main__":
    build_canonical()
