#!/usr/bin/env python3
"""
Phase 1 Repair — Statcast pitch-level enrichment via direct Savant CSV.
Bypasses pybaseball entirely. Custom NA-safe parsing.
"""

import json
import logging
import sys
import time
from datetime import datetime
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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, mode="a"), logging.StreamHandler()],
)
logger = logging.getLogger("phase1_repair")

SAVANT_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv?"
    "all=true&hfPT=&hfAB=&hfGT=R%7C&hfPR=&hfZ=&hfStadium=&hfBBL=&hfNewZones=&hfPull=&hfC=&hfSea={year}%7C"
    "&hfSit=&player_type=pitcher&hfOuts=&hfOpponent=&pitcher_throws=&batter_stands="
    "&hfSA=&game_date_gt={start}&game_date_lt={end}"
    "&hfMo=&hfTeam=&home_road=&hfRO=&position=&hfInfield=&hfOutfield=&hfInn=&hfBBT=&hfFlag="
    "&metric_1=&group_by=name&min_pitches=0&min_results=0&min_pas=0&sort_col=pitches&player_event_sort=api_p_release_speed"
    "&sort_order=desc&type=details&player_id=&csv=true"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def _load_ckpt():
    if CKPT_PATH.exists():
        with open(CKPT_PATH) as f:
            return json.load(f)
    return {}


def _save_ckpt(ckpt):
    with open(CKPT_PATH, "w") as f:
        json.dump(ckpt, f, indent=2)


def _pull_chunk(year, start, end):
    """Pull raw pitch-level CSV from Savant. Returns DataFrame or None."""
    url = SAVANT_URL.format(year=year, start=start, end=end)
    logger.info(f"    URL: ...game_date_gt={start}&game_date_lt={end}")

    r = requests.get(url, headers=HEADERS, timeout=120)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")

    text = r.text
    if len(text) < 200 or "pitcher" not in text[:500].lower():
        logger.info(f"    Empty or invalid response ({len(text)} bytes)")
        return pd.DataFrame()

    # Parse with all-string dtypes to avoid NA integer casting
    df = pd.read_csv(StringIO(text), dtype=str, low_memory=False)

    if len(df) == 0:
        return df

    # Convert numeric columns safely
    numeric_cols = [
        "launch_speed", "launch_angle", "release_spin_rate",
        "release_extension", "release_pos_x", "release_pos_z",
        "zone", "pitcher", "game_pk",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _aggregate_pitcher_start(df):
    """Aggregate pitch-level to pitcher-per-start. Only starters (>= 40 pitches)."""
    if df is None or len(df) == 0:
        return pd.DataFrame()

    required = ["pitcher", "game_date"]
    for c in required:
        if c not in df.columns:
            logger.warning(f"    Missing column: {c}")
            return pd.DataFrame()

    # game_pk may be float after coercion
    if "game_pk" in df.columns:
        df["game_pk"] = pd.to_numeric(df["game_pk"], errors="coerce")

    # BIP
    bip_events = ["hit_into_play", "hit_into_play_no_out", "hit_into_play_score"]
    df["is_bip"] = df["description"].isin(bip_events).astype(int)
    df["is_hard_hit"] = ((df["launch_speed"] >= 95) & (df["is_bip"] == 1)).astype(int)

    # Barrel (simplified: EV >= 98 and LA 26-30, broadened per Statcast)
    if "launch_speed" in df.columns and "launch_angle" in df.columns:
        ev = df["launch_speed"].fillna(0)
        la = df["launch_angle"].fillna(0)
        # Statcast barrel: EV >= 98, angle range widens with EV
        min_la = np.maximum(26, 30 - (ev.clip(upper=116) - 98).clip(lower=0))
        max_la = np.minimum(50, 30 + (ev.clip(upper=116) - 98).clip(lower=0))
        df["is_barrel"] = ((ev >= 98) & (la >= min_la) & (la <= max_la) & (df["is_bip"] == 1)).astype(int)
    else:
        df["is_barrel"] = 0

    # Zone
    if "zone" in df.columns:
        df["is_in_zone"] = df["zone"].between(1, 9).astype(int)
        df["is_outside_zone"] = (~df["zone"].between(1, 9) & df["zone"].notna()).astype(int)
    else:
        df["is_in_zone"] = np.nan
        df["is_outside_zone"] = np.nan

    # Swings and whiffs
    swing_events = ["swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
                    "foul_bunt", "missed_bunt"] + bip_events
    df["is_swing"] = df["description"].isin(swing_events).astype(int)
    df["is_whiff"] = df["description"].isin(["swinging_strike", "swinging_strike_blocked"]).astype(int)
    df["is_contact"] = ((df["is_swing"] == 1) & (df["is_whiff"] == 0)).astype(int)
    df["is_chase"] = ((df["is_outside_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_swing"] = ((df["is_in_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_contact"] = ((df["is_zone_swing"] == 1) & (df["is_contact"] == 1)).astype(int)

    # Spin by pitch type
    if "release_spin_rate" in df.columns and "pitch_type" in df.columns:
        df["spin_ff"] = np.where(df["pitch_type"].isin(["FF", "SI"]), df["release_spin_rate"], np.nan)
        df["spin_sl"] = np.where(df["pitch_type"].isin(["SL", "ST", "SV"]), df["release_spin_rate"], np.nan)
    else:
        df["spin_ff"] = np.nan
        df["spin_sl"] = np.nan

    for col in ["release_extension", "release_pos_x", "release_pos_z"]:
        if col not in df.columns:
            df[col] = np.nan

    # Group key
    group_cols = ["pitcher", "game_date"]
    if "game_pk" in df.columns and df["game_pk"].notna().sum() > 0:
        group_cols.append("game_pk")

    agg = df.groupby(group_cols).agg(
        pitcher_name=("player_name", "first") if "player_name" in df.columns else ("pitcher", "first"),
        total_pitches=("pitcher", "count"),
        bip=("is_bip", "sum"),
        hard_hits=("is_hard_hit", "sum"),
        barrels=("is_barrel", "sum"),
        swings=("is_swing", "sum"),
        whiffs=("is_whiff", "sum"),
        in_zone=("is_in_zone", "sum"),
        outside_zone=("is_outside_zone", "sum"),
        chases=("is_chase", "sum"),
        zone_swings=("is_zone_swing", "sum"),
        zone_contacts=("is_zone_contact", "sum"),
        avg_launch_angle=("launch_angle", "mean"),
        avg_exit_velo=("launch_speed", "mean"),
        spin_rate_ff=("spin_ff", "mean"),
        spin_rate_sl=("spin_sl", "mean"),
        extension=("release_extension", "mean"),
        release_point_x=("release_pos_x", "mean"),
        release_point_z=("release_pos_z", "mean"),
    ).reset_index()

    agg = agg.rename(columns={"pitcher": "pitcher_id"})

    # Rates
    agg["hard_hit_rate"] = agg["hard_hits"] / agg["bip"].clip(lower=1)
    agg["barrel_rate"] = agg["barrels"] / agg["bip"].clip(lower=1)
    agg["chase_rate"] = agg["chases"] / agg["outside_zone"].clip(lower=1)
    agg["zone_rate"] = agg["in_zone"] / agg["total_pitches"].clip(lower=1)
    agg["zone_contact_rate"] = agg["zone_contacts"] / agg["zone_swings"].clip(lower=1)
    agg["whiff_rate"] = agg["whiffs"] / agg["swings"].clip(lower=1)

    # Only starters (>= 40 pitches)
    agg = agg[agg["total_pitches"] >= 40]

    return agg


def main():
    logger.info("=" * 60)
    logger.info("PHASE 1 REPAIR — Direct Savant CSV pull")
    logger.info("=" * 60)

    ckpt = _load_ckpt()
    if "phase1_repair" not in ckpt:
        ckpt["phase1_repair"] = {"chunks_complete": [], "chunks_failed": []}

    import calendar
    seasons = [2022, 2023, 2024, 2025]
    months = list(range(3, 11))

    chunks = []
    for yr in seasons:
        for mo in months:
            start = f"{yr}-03-20" if mo == 3 else f"{yr}-{mo:02d}-01"
            end = f"{yr}-10-05" if mo == 10 else f"{yr}-{mo:02d}-{calendar.monthrange(yr, mo)[1]}"
            chunks.append({"id": f"{yr}_{mo:02d}", "start": start, "end": end, "year": yr})

    completed = set(ckpt["phase1_repair"]["chunks_complete"])
    remaining = [c for c in chunks if c["id"] not in completed]

    logger.info(f"  Total chunks: {len(chunks)}")
    logger.info(f"  Complete: {len(completed)}")
    logger.info(f"  Remaining: {len(remaining)}")

    for ci, chunk in enumerate(remaining):
        cid = chunk["id"]
        logger.info(f"\n  Chunk {cid} ({chunk['start']} to {chunk['end']})...")

        success = False
        for attempt in range(3):
            try:
                raw = _pull_chunk(chunk["year"], chunk["start"], chunk["end"])
                if raw is None or len(raw) == 0:
                    logger.info(f"    {cid}: no data (empty response)")
                    ckpt["phase1_repair"]["chunks_complete"].append(cid)
                    _save_ckpt(ckpt)
                    success = True
                    break

                logger.info(f"    {cid}: {len(raw)} pitches pulled")
                agg = _aggregate_pitcher_start(raw)

                if len(agg) > 0:
                    path = CHUNKS / f"pitcher_statcast_{cid}.parquet"
                    agg.to_parquet(path, index=False)
                    logger.info(f"    {cid}: {len(agg)} pitcher-starts saved")

                ckpt["phase1_repair"]["chunks_complete"].append(cid)
                _save_ckpt(ckpt)
                success = True
                break

            except Exception as e:
                wait = [30, 90, 180][attempt]
                logger.warning(f"    Attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep(wait)

        if not success:
            logger.error(f"    FAILED: {cid}")
            if cid not in ckpt["phase1_repair"]["chunks_failed"]:
                ckpt["phase1_repair"]["chunks_failed"].append(cid)
            _save_ckpt(ckpt)

        # Pacing
        if ci < len(remaining) - 1:
            next_yr = remaining[ci + 1]["year"] if ci + 1 < len(remaining) else None
            if next_yr and next_yr != chunk["year"]:
                logger.info("    Season boundary — sleeping 15s")
                time.sleep(15)
            else:
                time.sleep(3)

    # Merge
    logger.info("\n  Merging chunks...")
    all_chunks = []
    for p in sorted(CHUNKS.glob("pitcher_statcast_*.parquet")):
        try:
            all_chunks.append(pd.read_parquet(p))
        except Exception as e:
            logger.warning(f"  Failed to read {p.name}: {e}")

    if all_chunks:
        merged = pd.concat(all_chunks, ignore_index=True)
        dedup_cols = ["pitcher_id", "game_date"]
        if "game_pk" in merged.columns:
            dedup_cols.append("game_pk")
        merged = merged.drop_duplicates(subset=dedup_cols)
        merged.to_parquet(OUT / "pitcher_statcast_per_start.parquet", index=False)
        logger.info(f"  Merged: {len(merged)} pitcher-starts")

        # Validation
        logger.info("\n  VALIDATION REPORT")
        logger.info("=" * 60)
        for yr in seasons:
            yr_data = merged[merged["game_date"].astype(str).str[:4] == str(yr)]
            n_starts = len(yr_data)
            n_pitchers = yr_data["pitcher_id"].nunique()
            logger.info(f"  {yr}: {n_starts} starts, {n_pitchers} pitchers")
            for col in ["hard_hit_rate", "barrel_rate", "chase_rate", "zone_rate",
                        "whiff_rate", "avg_exit_velo", "spin_rate_ff", "extension"]:
                if col in yr_data.columns:
                    null_pct = yr_data[col].isna().mean() * 100
                    if null_pct > 0:
                        logger.info(f"    {col}: {null_pct:.1f}% null")
    else:
        logger.warning("  No chunks to merge!")

    # Summary
    n_complete = len(ckpt["phase1_repair"]["chunks_complete"])
    n_failed = len(ckpt["phase1_repair"]["chunks_failed"])
    logger.info(f"\n  Chunks: {n_complete} complete, {n_failed} failed out of {len(chunks)}")
    logger.info(f"  Phase 1 repair complete: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
