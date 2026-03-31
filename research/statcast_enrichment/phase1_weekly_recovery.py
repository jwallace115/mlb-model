#!/usr/bin/env python3
"""
Statcast weekly recovery — pull in 7-day windows to stay under 25K pitch cap.
Appends new starts only. Skips existing pitcher+date combos.
"""

import calendar
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT = Path("/Users/jw115/mlb-model")
OUT = PROJECT / "research" / "statcast_enrichment"
CHUNKS = OUT / "chunks"
CKPT_PATH = OUT / "checkpoints.json"
LOG_PATH = OUT / "pull_log.txt"
MAIN_PATH = OUT / "pitcher_statcast_per_start.parquet"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, mode="a"), logging.StreamHandler()],
)
logger = logging.getLogger("weekly_recovery")

SAVANT_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv?"
    "all=true&hfPT=&hfAB=&hfGT=R%7C&hfPR=&hfZ=&hfStadium=&hfBBL=&hfNewZones=&hfPull=&hfC=&hfSea={year}%7C"
    "&hfSit=&player_type=pitcher&hfOuts=&hfOpponent=&pitcher_throws=&batter_stands="
    "&hfSA=&game_date_gt={start}&game_date_lt={end}"
    "&hfMo=&hfTeam=&home_road=&hfRO=&position=&hfInfield=&hfOutfield=&hfInn=&hfBBT=&hfFlag="
    "&metric_1=&group_by=name&min_pitches=0&min_results=0&min_pas=0&sort_col=pitches&player_event_sort=api_p_release_speed"
    "&sort_order=desc&type=details&player_id=&csv=true"
)
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _load_ckpt():
    if CKPT_PATH.exists():
        with open(CKPT_PATH) as f:
            return json.load(f)
    return {}


def _save_ckpt(ckpt):
    with open(CKPT_PATH, "w") as f:
        json.dump(ckpt, f, indent=2)


def _load_existing():
    if MAIN_PATH.exists():
        df = pd.read_parquet(MAIN_PATH)
        return df
    return pd.DataFrame()


def _pull_chunk(year, start, end):
    url = SAVANT_URL.format(year=year, start=start, end=end)
    r = requests.get(url, headers=HEADERS, timeout=120)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")
    text = r.text
    if len(text) < 200 or "pitcher" not in text[:500].lower():
        return pd.DataFrame()
    df = pd.read_csv(StringIO(text), dtype=str, low_memory=False)
    for col in ["launch_speed", "launch_angle", "release_spin_rate",
                 "release_extension", "release_pos_x", "release_pos_z",
                 "zone", "pitcher", "game_pk"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _aggregate(df):
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if "pitcher" not in df.columns or "game_date" not in df.columns:
        return pd.DataFrame()

    bip_events = ["hit_into_play", "hit_into_play_no_out", "hit_into_play_score"]
    df["is_bip"] = df["description"].isin(bip_events).astype(int)
    df["is_hard_hit"] = ((df["launch_speed"] >= 95) & (df["is_bip"] == 1)).astype(int)

    if "launch_speed" in df.columns and "launch_angle" in df.columns:
        ev = df["launch_speed"].fillna(0)
        la = df["launch_angle"].fillna(0)
        min_la = np.maximum(26, 30 - (ev.clip(upper=116) - 98).clip(lower=0))
        max_la = np.minimum(50, 30 + (ev.clip(upper=116) - 98).clip(lower=0))
        df["is_barrel"] = ((ev >= 98) & (la >= min_la) & (la <= max_la) & (df["is_bip"] == 1)).astype(int)
    else:
        df["is_barrel"] = 0

    if "zone" in df.columns:
        df["is_in_zone"] = df["zone"].between(1, 9).astype(int)
        df["is_outside_zone"] = (~df["zone"].between(1, 9) & df["zone"].notna()).astype(int)
    else:
        df["is_in_zone"] = np.nan
        df["is_outside_zone"] = np.nan

    swing_events = ["swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
                    "foul_bunt", "missed_bunt"] + bip_events
    df["is_swing"] = df["description"].isin(swing_events).astype(int)
    df["is_whiff"] = df["description"].isin(["swinging_strike", "swinging_strike_blocked"]).astype(int)
    df["is_contact"] = ((df["is_swing"] == 1) & (df["is_whiff"] == 0)).astype(int)
    df["is_chase"] = ((df["is_outside_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_swing"] = ((df["is_in_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_contact"] = ((df["is_zone_swing"] == 1) & (df["is_contact"] == 1)).astype(int)

    if "release_spin_rate" in df.columns and "pitch_type" in df.columns:
        df["spin_ff"] = np.where(df["pitch_type"].isin(["FF", "SI"]), df["release_spin_rate"], np.nan)
        df["spin_sl"] = np.where(df["pitch_type"].isin(["SL", "ST", "SV"]), df["release_spin_rate"], np.nan)
    else:
        df["spin_ff"] = np.nan
        df["spin_sl"] = np.nan

    for col in ["release_extension", "release_pos_x", "release_pos_z"]:
        if col not in df.columns:
            df[col] = np.nan

    group_cols = ["pitcher", "game_date"]
    if "game_pk" in df.columns and df["game_pk"].notna().sum() > 0:
        group_cols.append("game_pk")

    agg = df.groupby(group_cols).agg(
        pitcher_name=("player_name", "first") if "player_name" in df.columns else ("pitcher", "first"),
        total_pitches=("pitcher", "count"),
        bip=("is_bip", "sum"), hard_hits=("is_hard_hit", "sum"), barrels=("is_barrel", "sum"),
        swings=("is_swing", "sum"), whiffs=("is_whiff", "sum"),
        in_zone=("is_in_zone", "sum"), outside_zone=("is_outside_zone", "sum"),
        chases=("is_chase", "sum"), zone_swings=("is_zone_swing", "sum"),
        zone_contacts=("is_zone_contact", "sum"),
        avg_launch_angle=("launch_angle", "mean"), avg_exit_velo=("launch_speed", "mean"),
        spin_rate_ff=("spin_ff", "mean"), spin_rate_sl=("spin_sl", "mean"),
        extension=("release_extension", "mean"),
        release_point_x=("release_pos_x", "mean"), release_point_z=("release_pos_z", "mean"),
    ).reset_index()

    agg = agg.rename(columns={"pitcher": "pitcher_id"})
    agg["hard_hit_rate"] = agg["hard_hits"] / agg["bip"].clip(lower=1)
    agg["barrel_rate"] = agg["barrels"] / agg["bip"].clip(lower=1)
    agg["chase_rate"] = agg["chases"] / agg["outside_zone"].clip(lower=1)
    agg["zone_rate"] = agg["in_zone"] / agg["total_pitches"].clip(lower=1)
    agg["zone_contact_rate"] = agg["zone_contacts"] / agg["zone_swings"].clip(lower=1)
    agg["whiff_rate"] = agg["whiffs"] / agg["swings"].clip(lower=1)
    return agg[agg["total_pitches"] >= 40]


def main():
    logger.info("=" * 60)
    logger.info("STATCAST WEEKLY RECOVERY")
    logger.info("=" * 60)

    existing = _load_existing()
    logger.info(f"  Existing starts: {len(existing)}")

    # Build existing keys for dedup
    existing_keys = set()
    if len(existing) > 0:
        for _, r in existing.iterrows():
            if pd.notna(r.get("hard_hit_rate")):
                key = (int(r["pitcher_id"]), str(r["game_date"]))
                existing_keys.add(key)
    logger.info(f"  Existing dedup keys: {len(existing_keys)}")

    ckpt = _load_ckpt()
    if "weekly_recovery" not in ckpt:
        ckpt["weekly_recovery"] = {"chunks_complete": [], "chunks_failed": []}

    # Build weekly chunks
    seasons = [2022, 2023, 2024, 2025]
    chunks = []
    for yr in seasons:
        # Regular season: late March through early October
        start = datetime(yr, 3, 20)
        end = datetime(yr, 10, 5)
        current = start
        while current < end:
            week_end = min(current + timedelta(days=6), end)
            cid = f"w_{yr}_{current.strftime('%m%d')}"
            chunks.append({
                "id": cid, "year": yr,
                "start": current.strftime("%Y-%m-%d"),
                "end": week_end.strftime("%Y-%m-%d"),
            })
            current = week_end + timedelta(days=1)

    completed = set(ckpt["weekly_recovery"]["chunks_complete"])
    remaining = [c for c in chunks if c["id"] not in completed]

    logger.info(f"  Total weekly chunks: {len(chunks)}")
    logger.info(f"  Already complete: {len(completed)}")
    logger.info(f"  Remaining: {len(remaining)}")

    new_starts_total = 0
    all_new = []

    for ci, chunk in enumerate(remaining):
        cid = chunk["id"]

        success = False
        for attempt in range(3):
            try:
                raw = _pull_chunk(chunk["year"], chunk["start"], chunk["end"])
                if raw is None or len(raw) == 0:
                    ckpt["weekly_recovery"]["chunks_complete"].append(cid)
                    _save_ckpt(ckpt)
                    success = True
                    break

                agg = _aggregate(raw)
                if len(agg) == 0:
                    ckpt["weekly_recovery"]["chunks_complete"].append(cid)
                    _save_ckpt(ckpt)
                    success = True
                    break

                # Filter out already-existing starts
                new_rows = []
                for _, r in agg.iterrows():
                    key = (int(r["pitcher_id"]), str(r["game_date"]))
                    if key not in existing_keys:
                        new_rows.append(r)
                        existing_keys.add(key)

                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    all_new.append(new_df)
                    new_starts_total += len(new_rows)

                ckpt["weekly_recovery"]["chunks_complete"].append(cid)
                _save_ckpt(ckpt)
                success = True

                if len(new_rows) > 0:
                    logger.info(f"  {cid}: {len(raw)} pitches → {len(agg)} starts, {len(new_rows)} NEW")
                break

            except Exception as e:
                wait = [30, 90, 180][attempt]
                logger.warning(f"  {cid} attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep(wait)

        if not success:
            logger.error(f"  FAILED: {cid}")
            if cid not in ckpt["weekly_recovery"]["chunks_failed"]:
                ckpt["weekly_recovery"]["chunks_failed"].append(cid)
            _save_ckpt(ckpt)

        # Pacing
        if ci < len(remaining) - 1:
            next_yr = remaining[ci + 1]["year"] if ci + 1 < len(remaining) else None
            if next_yr and next_yr != chunk["year"]:
                time.sleep(15)
            else:
                time.sleep(3)

        # Periodic save
        if (ci + 1) % 20 == 0 and all_new:
            combined = pd.concat([existing] + all_new, ignore_index=True)
            dedup_cols = ["pitcher_id", "game_date"]
            if "game_pk" in combined.columns:
                dedup_cols.append("game_pk")
            combined = combined.drop_duplicates(subset=dedup_cols)
            combined.to_parquet(MAIN_PATH, index=False)
            existing = combined
            all_new = []
            logger.info(f"  Checkpoint save: {len(existing)} total starts, +{new_starts_total} new")

    # Final merge
    if all_new:
        combined = pd.concat([existing] + all_new, ignore_index=True)
        dedup_cols = ["pitcher_id", "game_date"]
        if "game_pk" in combined.columns:
            dedup_cols.append("game_pk")
        combined = combined.drop_duplicates(subset=dedup_cols)
        combined.to_parquet(MAIN_PATH, index=False)
        existing = combined

    # Validation
    logger.info(f"\n{'='*60}")
    logger.info("COVERAGE REPORT")
    logger.info(f"{'='*60}")

    final = pd.read_parquet(MAIN_PATH) if MAIN_PATH.exists() else pd.DataFrame()
    logger.info(f"  Starts before recovery: {len(existing) - new_starts_total}")
    logger.info(f"  Starts after recovery:  {len(final)}")
    logger.info(f"  New starts added:       {new_starts_total}")

    # Coverage vs historical
    pgl = pd.read_parquet(PROJECT / "mlb" / "data" / "pitcher_game_logs.parquet")
    pgl_starters = pgl[pgl["starter_flag"] == 1]
    for yr in [2022, 2023, 2024, 2025]:
        total = len(pgl_starters[pgl_starters["season"] == yr])
        have = len(final[final["game_date"].astype(str).str[:4] == str(yr)])
        pct = have / total * 100 if total > 0 else 0
        flag = "" if pct >= 85 else " *** BELOW 85%"
        logger.info(f"  {yr}: {have}/{total} ({pct:.1f}%){flag}")

    # Null rates
    logger.info(f"\n  Field null rates:")
    for col in ["hard_hit_rate", "barrel_rate", "chase_rate", "zone_rate",
                "whiff_rate", "avg_exit_velo", "spin_rate_ff", "extension"]:
        if col in final.columns:
            null_pct = final[col].isna().mean() * 100
            logger.info(f"    {col}: {null_pct:.1f}%")

    n_complete = len(ckpt["weekly_recovery"]["chunks_complete"])
    n_failed = len(ckpt["weekly_recovery"]["chunks_failed"])
    logger.info(f"\n  Chunks: {n_complete} complete, {n_failed} failed")
    logger.info(f"  Recovery complete: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
