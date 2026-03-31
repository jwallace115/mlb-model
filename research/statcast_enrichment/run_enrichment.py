#!/usr/bin/env python3
"""
Statcast Enrichment — Overnight data acquisition.
Resumable, incremental, fault-tolerant.
All output in research/statcast_enrichment/.
"""

import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT = PROJECT / "research" / "statcast_enrichment"
CHUNKS = OUT / "chunks"
CKPT_PATH = OUT / "checkpoints.json"
LOG_PATH = OUT / "pull_log.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("enrichment")


def _load_ckpt():
    if CKPT_PATH.exists():
        with open(CKPT_PATH) as f:
            return json.load(f)
    return {}


def _save_ckpt(ckpt):
    with open(CKPT_PATH, "w") as f:
        json.dump(ckpt, f, indent=2)


# ═══════════════════════════════════════════════
# PHASE 0 — PRECHECKS
# ═══════════════════════════════════════════════

def phase0():
    logger.info("=" * 60)
    logger.info("PHASE 0 — PRECHECKS")
    logger.info("=" * 60)

    logger.info(f"  Python: {sys.version}")
    logger.info(f"  Output: {OUT}")
    logger.info(f"  Timestamp: {datetime.now().isoformat()}")

    try:
        from pybaseball import statcast
        import pybaseball
        v = getattr(pybaseball, "__version__", "unknown")
        logger.info(f"  pybaseball: {v}")
    except ImportError:
        logger.error("  pybaseball NOT AVAILABLE — cannot proceed")
        return False

    # Test write access
    test_file = OUT / "_test_write"
    try:
        test_file.write_text("ok")
        test_file.unlink()
        logger.info("  Disk write: OK")
    except Exception as e:
        logger.error(f"  Disk write FAILED: {e}")
        return False

    # Init checkpoint
    ckpt = _load_ckpt()
    if "phase0" not in ckpt:
        ckpt["phase0"] = {"status": "complete", "timestamp": datetime.now().isoformat()}
        _save_ckpt(ckpt)

    logger.info("  Prechecks: PASS")
    return True


# ═══════════════════════════════════════════════
# PHASE 1 — STATCAST PITCH-LEVEL ENRICHMENT
# ═══════════════════════════════════════════════

def _aggregate_pitcher_start(chunk_df):
    """Aggregate pitch-level data to pitcher-start level."""
    if chunk_df is None or len(chunk_df) == 0:
        return pd.DataFrame()

    df = chunk_df.copy()

    # Ensure required columns exist
    required = ["pitcher", "game_pk", "game_date", "player_name"]
    for c in required:
        if c not in df.columns:
            return pd.DataFrame()

    # BIP = balls in play (hit_into_play events)
    df["is_bip"] = df["description"].isin([
        "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"
    ]).astype(int)

    df["is_hard_hit"] = ((df["launch_speed"] >= 95) & (df["is_bip"] == 1)).astype(int) if "launch_speed" in df.columns else 0

    # Barrel: launch_speed >= 98 AND launch_angle between 26-30 (simplified)
    if "launch_speed" in df.columns and "launch_angle" in df.columns:
        df["is_barrel"] = (
            (df["launch_speed"] >= 98) &
            (df["launch_angle"] >= 26) & (df["launch_angle"] <= 30) &
            (df["is_bip"] == 1)
        ).astype(int)
        # Broader barrel: EV-dependent angle range (Statcast definition)
        df["is_barrel"] = (
            (df["launch_speed"] >= 98) &
            (df["launch_angle"] >= max(26, 30 - (df["launch_speed"].clip(upper=116) - 98).clip(lower=0))) &
            (df["launch_angle"] <= min(50, 30 + (df["launch_speed"].clip(upper=116) - 98).clip(lower=0))) &
            (df["is_bip"] == 1)
        ).astype(int)
    else:
        df["is_barrel"] = 0

    # Zone/chase
    df["is_in_zone"] = (df["zone"].between(1, 9)).astype(int) if "zone" in df.columns else np.nan
    df["is_outside_zone"] = (~df["zone"].between(1, 9)).astype(int) if "zone" in df.columns else np.nan
    df["is_swing"] = df["description"].isin([
        "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
        "foul_bunt", "missed_bunt", "hit_into_play", "hit_into_play_no_out",
        "hit_into_play_score"
    ]).astype(int)
    df["is_whiff"] = df["description"].isin(["swinging_strike", "swinging_strike_blocked"]).astype(int)
    df["is_contact"] = (df["is_swing"] == 1) & (df["is_whiff"] == 0)

    # Chase = swing on pitch outside zone
    df["is_chase"] = ((df["is_outside_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_swing"] = ((df["is_in_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_contact"] = ((df["is_zone_swing"] == 1) & (df["is_contact"] == 1)).astype(int)

    # Spin rate by pitch type
    if "release_spin_rate" in df.columns and "pitch_type" in df.columns:
        df["spin_ff"] = np.where(df["pitch_type"].isin(["FF", "SI"]), df["release_spin_rate"], np.nan)
        df["spin_sl"] = np.where(df["pitch_type"].isin(["SL", "ST", "SV"]), df["release_spin_rate"], np.nan)
    else:
        df["spin_ff"] = np.nan
        df["spin_sl"] = np.nan

    # Extension and release point
    for col in ["release_extension", "release_pos_x", "release_pos_z"]:
        if col not in df.columns:
            df[col] = np.nan

    # Aggregate by pitcher + game
    agg = df.groupby(["pitcher", "game_date", "game_pk"]).agg(
        pitcher_name=("player_name", "first"),
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

    # Compute rates
    agg["hard_hit_rate"] = (agg["hard_hits"] / agg["bip"].clip(lower=1))
    agg["barrel_rate"] = (agg["barrels"] / agg["bip"].clip(lower=1))
    agg["chase_rate"] = (agg["chases"] / agg["outside_zone"].clip(lower=1))
    agg["zone_rate"] = (agg["in_zone"] / agg["total_pitches"].clip(lower=1))
    agg["zone_contact_rate"] = (agg["zone_contacts"] / agg["zone_swings"].clip(lower=1))
    agg["whiff_rate"] = (agg["whiffs"] / agg["swings"].clip(lower=1))

    # Keep only meaningful starts (>= 30 pitches)
    agg = agg[agg["total_pitches"] >= 30]

    return agg


def phase1():
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1 — STATCAST PITCH-LEVEL ENRICHMENT")
    logger.info("=" * 60)

    from pybaseball import statcast

    ckpt = _load_ckpt()
    if "phase1" not in ckpt:
        ckpt["phase1"] = {"chunks_complete": [], "chunks_failed": []}

    seasons = [2022, 2023, 2024, 2025]
    months = list(range(3, 11))  # March through October

    # Build chunk list
    chunks = []
    for yr in seasons:
        for mo in months:
            if mo == 3:
                start = f"{yr}-03-20"
            else:
                start = f"{yr}-{mo:02d}-01"
            if mo == 10:
                end = f"{yr}-10-05"
            else:
                import calendar
                last_day = calendar.monthrange(yr, mo)[1]
                end = f"{yr}-{mo:02d}-{last_day}"
            chunk_id = f"{yr}_{mo:02d}"
            chunks.append({"id": chunk_id, "start": start, "end": end, "season": yr})

    completed = set(ckpt["phase1"]["chunks_complete"])
    failed_set = set(ckpt["phase1"]["chunks_failed"])
    remaining = [c for c in chunks if c["id"] not in completed]

    logger.info(f"  Total chunks: {len(chunks)}")
    logger.info(f"  Already complete: {len(completed)}")
    logger.info(f"  Remaining: {len(remaining)}")

    for ci, chunk in enumerate(remaining):
        cid = chunk["id"]
        logger.info(f"\n  Pulling chunk {cid} ({chunk['start']} to {chunk['end']})...")

        success = False
        for attempt in range(3):
            try:
                data = statcast(start_dt=chunk["start"], end_dt=chunk["end"])
                if data is None or len(data) == 0:
                    logger.info(f"    No data for {cid}")
                    ckpt["phase1"]["chunks_complete"].append(cid)
                    _save_ckpt(ckpt)
                    success = True
                    break

                agg = _aggregate_pitcher_start(data)
                if len(agg) > 0:
                    chunk_path = CHUNKS / f"pitcher_statcast_{cid}.parquet"
                    agg.to_parquet(chunk_path, index=False)
                    logger.info(f"    {cid}: {len(agg)} pitcher-starts saved")

                ckpt["phase1"]["chunks_complete"].append(cid)
                _save_ckpt(ckpt)
                success = True
                break

            except Exception as e:
                wait = [30, 90, 180][attempt]
                logger.warning(f"    Attempt {attempt+1} failed for {cid}: {e}")
                if attempt < 2:
                    logger.info(f"    Retrying in {wait}s...")
                    time.sleep(wait)

        if not success:
            logger.error(f"    FAILED after 3 attempts: {cid}")
            ckpt["phase1"]["chunks_failed"].append(cid)
            _save_ckpt(ckpt)

        # Pacing
        if ci < len(remaining) - 1:
            next_season = remaining[ci + 1]["season"] if ci + 1 < len(remaining) else None
            if next_season and next_season != chunk["season"]:
                logger.info("    Season boundary — sleeping 20s")
                time.sleep(20)
            else:
                time.sleep(5)

    # Merge all chunks
    logger.info("\n  Merging chunks...")
    all_chunks = []
    for p in sorted(CHUNKS.glob("pitcher_statcast_*.parquet")):
        try:
            all_chunks.append(pd.read_parquet(p))
        except Exception as e:
            logger.warning(f"  Failed to read {p}: {e}")

    if all_chunks:
        merged = pd.concat(all_chunks, ignore_index=True)
        merged = merged.drop_duplicates(subset=["pitcher_id", "game_date", "game_pk"])
        merged.to_parquet(OUT / "pitcher_statcast_per_start.parquet", index=False)
        logger.info(f"  Merged: {len(merged)} pitcher-starts")

        # Validation
        logger.info("\n  Phase 1 Validation:")
        for yr in seasons:
            yr_data = merged[merged["game_date"].astype(str).str[:4] == str(yr)]
            logger.info(f"    {yr}: {len(yr_data)} starts, {yr_data['pitcher_id'].nunique()} pitchers")
            for col in ["hard_hit_rate", "barrel_rate", "chase_rate", "zone_rate",
                        "whiff_rate", "avg_exit_velo", "spin_rate_ff", "extension"]:
                if col in yr_data.columns:
                    null_pct = yr_data[col].isna().mean() * 100
                    if null_pct > 5:
                        logger.info(f"      {col}: {null_pct:.1f}% null")
    else:
        logger.warning("  No chunks to merge!")

    ckpt["phase1"]["status"] = "complete"
    ckpt["phase1"]["timestamp"] = datetime.now().isoformat()
    _save_ckpt(ckpt)


# ═══════════════════════════════════════════════
# PHASES 2-5 — DOWNSTREAM ENRICHMENT
# ═══════════════════════════════════════════════

def phase2():
    """Lineup composition — team rolling averages as fallback."""
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2 — LINEUP COMPOSITION")
    logger.info("=" * 60)

    ckpt = _load_ckpt()
    if ckpt.get("phase2", {}).get("status") == "complete":
        logger.info("  Already complete — skipping")
        return

    try:
        ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
        ft["game_id"] = ft["game_pk"].astype(str)
        ft_2425 = ft[ft["season"].isin([2024, 2025])].copy()

        # Use wRC+ as lineup quality proxy (team rolling)
        lineup = []
        for _, r in ft_2425.iterrows():
            for side, team_col, wrc_col in [("home", "home_team", "home_wrc_plus"),
                                             ("away", "away_team", "away_wrc_plus")]:
                lineup.append({
                    "game_id": r["game_id"], "date": r["date"], "team": r[team_col],
                    "lineup_avg_wrc_plus": r[wrc_col],
                    "lineup_pct_left_handed": np.nan,  # not available without lineup data
                    "lineup_avg_hard_hit_rate": np.nan,
                    "lineup_avg_barrel_rate": np.nan,
                })

        lineup_df = pd.DataFrame(lineup)
        lineup_df.to_parquet(OUT / "lineup_composition.parquet", index=False)
        logger.info(f"  Saved: {len(lineup_df)} rows (FALLBACK_USED — team wRC+ only)")

        ckpt["phase2"] = {"status": "complete", "approach": "fallback_wrc_plus",
                          "timestamp": datetime.now().isoformat()}
        _save_ckpt(ckpt)

    except Exception as e:
        logger.error(f"  Phase 2 failed: {e}")
        ckpt["phase2"] = {"status": "failed", "error": str(e)}
        _save_ckpt(ckpt)


def phase3():
    """Team defense — from FanGraphs or Statcast if available."""
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 3 — TEAM DEFENSE")
    logger.info("=" * 60)

    ckpt = _load_ckpt()
    if ckpt.get("phase3", {}).get("status") == "complete":
        logger.info("  Already complete — skipping")
        return

    try:
        # Try FanGraphs team fielding
        import requests
        from io import StringIO

        rows = []
        for yr in [2022, 2023, 2024, 2025]:
            url = (f"https://www.fangraphs.com/api/leaders/major-league/data"
                   f"?age=0&pos=all&stats=fld&lg=all&qual=0&season={yr}&season1={yr}"
                   f"&ind=0&team=0,ts&pageitems=50&pagenum=1&type=1")
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    for team in data:
                        rows.append({
                            "season": yr,
                            "team_name": team.get("TeamName", ""),
                            "defensive_runs_saved": team.get("DRS", np.nan),
                            "outs_above_average_total": np.nan,  # FanGraphs doesn't have OAA
                        })
                    logger.info(f"    {yr}: {len(data)} teams from FanGraphs")
                else:
                    logger.warning(f"    {yr}: FanGraphs HTTP {r.status_code}")
            except Exception as e:
                logger.warning(f"    {yr}: FanGraphs failed — {e}")
            time.sleep(2)

        if rows:
            defense_df = pd.DataFrame(rows)
            defense_df.to_parquet(OUT / "team_defense.parquet", index=False)
            logger.info(f"  Saved: {len(defense_df)} rows")
            ckpt["phase3"] = {"status": "complete", "timestamp": datetime.now().isoformat()}
        else:
            logger.warning("  No defense data retrieved")
            ckpt["phase3"] = {"status": "partial", "note": "FanGraphs blocked or unavailable"}

        _save_ckpt(ckpt)

    except Exception as e:
        logger.error(f"  Phase 3 failed: {e}")
        ckpt["phase3"] = {"status": "failed", "error": str(e)}
        _save_ckpt(ckpt)


def phase4():
    """Team baserunning."""
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 4 — TEAM BASERUNNING")
    logger.info("=" * 60)

    ckpt = _load_ckpt()
    if ckpt.get("phase4", {}).get("status") == "complete":
        logger.info("  Already complete — skipping")
        return

    try:
        import requests

        rows = []
        for yr in [2022, 2023, 2024, 2025]:
            url = (f"https://www.fangraphs.com/api/leaders/major-league/data"
                   f"?age=0&pos=all&stats=bat&lg=all&qual=0&season={yr}&season1={yr}"
                   f"&ind=0&team=0,ts&pageitems=50&pagenum=1&type=8")
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    for team in data:
                        rows.append({
                            "season": yr,
                            "team_name": team.get("TeamName", ""),
                            "stolen_bases": team.get("SB", np.nan),
                            "caught_stealing": team.get("CS", np.nan),
                            "bsr": team.get("BsR", np.nan),  # baserunning runs
                        })
                    logger.info(f"    {yr}: {len(data)} teams from FanGraphs")
                else:
                    logger.warning(f"    {yr}: FanGraphs HTTP {r.status_code}")
            except Exception as e:
                logger.warning(f"    {yr}: FanGraphs failed — {e}")
            time.sleep(2)

        if rows:
            br_df = pd.DataFrame(rows)
            br_df["sb_success_rate"] = br_df["stolen_bases"] / (br_df["stolen_bases"] + br_df["caught_stealing"]).clip(lower=1)
            br_df.to_parquet(OUT / "team_baserunning.parquet", index=False)
            logger.info(f"  Saved: {len(br_df)} rows")
            ckpt["phase4"] = {"status": "complete", "timestamp": datetime.now().isoformat()}
        else:
            ckpt["phase4"] = {"status": "partial"}

        _save_ckpt(ckpt)

    except Exception as e:
        logger.error(f"  Phase 4 failed: {e}")
        ckpt["phase4"] = {"status": "failed", "error": str(e)}
        _save_ckpt(ckpt)


def phase5():
    """Catcher framing — availability check."""
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 5 — CATCHER FRAMING")
    logger.info("=" * 60)

    ckpt = _load_ckpt()
    if ckpt.get("phase5", {}).get("status") == "complete":
        logger.info("  Already complete — skipping")
        return

    try:
        import requests
        from io import StringIO

        rows = []
        for yr in [2022, 2023, 2024, 2025]:
            url = (f"https://baseballsavant.mlb.com/leaderboard/catcher-framing"
                   f"?year={yr}&team=&min=100&type=&csv=true")
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if r.status_code == 200 and len(r.text) > 100:
                    df = pd.read_csv(StringIO(r.text))
                    df["season"] = yr
                    rows.append(df)
                    logger.info(f"    {yr}: {len(df)} catchers from Savant")
                else:
                    logger.warning(f"    {yr}: Savant framing HTTP {r.status_code}")
            except Exception as e:
                logger.warning(f"    {yr}: Savant framing failed — {e}")
            time.sleep(3)

        if rows:
            framing = pd.concat(rows, ignore_index=True)
            framing.to_parquet(OUT / "catcher_framing.parquet", index=False)
            logger.info(f"  Saved: {len(framing)} rows")
            ckpt["phase5"] = {"status": "complete", "timestamp": datetime.now().isoformat()}
        else:
            status = {"status": "unavailable", "note": "Savant framing endpoint returned no data",
                      "timestamp": datetime.now().isoformat()}
            with open(OUT / "catcher_framing_status.json", "w") as f:
                json.dump(status, f, indent=2)
            ckpt["phase5"] = {"status": "unavailable"}

        _save_ckpt(ckpt)

    except Exception as e:
        logger.error(f"  Phase 5 failed: {e}")
        ckpt["phase5"] = {"status": "failed", "error": str(e)}
        _save_ckpt(ckpt)


# ═══════════════════════════════════════════════
# FINAL VALIDATION
# ═══════════════════════════════════════════════

def final_validation():
    logger.info("\n" + "=" * 60)
    logger.info("FINAL VALIDATION REPORT")
    logger.info("=" * 60)

    ckpt = _load_ckpt()

    outputs = [
        ("Phase 1", "pitcher_statcast_per_start.parquet"),
        ("Phase 2", "lineup_composition.parquet"),
        ("Phase 3", "team_defense.parquet"),
        ("Phase 4", "team_baserunning.parquet"),
        ("Phase 5", "catcher_framing.parquet"),
    ]

    logger.info(f"\n  {'Phase':>8s} | {'File':>40s} | {'Rows':>6s} | {'Seasons':>12s} | {'Status':>10s}")
    logger.info(f"  {'-'*8} | {'-'*40} | {'-'*6} | {'-'*12} | {'-'*10}")

    for phase, fname in outputs:
        fpath = OUT / fname
        if fpath.exists():
            try:
                df = pd.read_parquet(fpath)
                rows = len(df)
                if "season" in df.columns:
                    seasons = sorted(df["season"].unique())
                elif "game_date" in df.columns:
                    seasons = sorted(df["game_date"].astype(str).str[:4].unique())
                else:
                    seasons = ["?"]
                s_str = ",".join(str(s) for s in seasons)
                logger.info(f"  {phase:>8s} | {fname:>40s} | {rows:>6d} | {s_str:>12s} | {'OK':>10s}")
            except Exception as e:
                logger.info(f"  {phase:>8s} | {fname:>40s} | {'ERR':>6s} | {'':>12s} | {'READ_ERR':>10s}")
        else:
            phase_key = phase.lower().replace(" ", "")
            status = ckpt.get(phase_key, {}).get("status", "missing")
            logger.info(f"  {phase:>8s} | {fname:>40s} | {'0':>6s} | {'':>12s} | {status:>10s}")

    # Failed chunks
    p1 = ckpt.get("phase1", {})
    failed = p1.get("chunks_failed", [])
    if failed:
        logger.info(f"\n  Failed chunks: {failed}")
    else:
        logger.info(f"\n  Failed chunks: none")

    logger.info(f"\n  Enrichment run complete: {datetime.now().isoformat()}")


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    if not phase0():
        sys.exit(1)

    # Phase 1 is the priority
    try:
        phase1()
    except Exception as e:
        logger.error(f"Phase 1 crashed: {e}\n{traceback.format_exc()}")

    # Phases 2-5 are best-effort
    for phase_fn in [phase2, phase3, phase4, phase5]:
        try:
            phase_fn()
        except Exception as e:
            logger.error(f"{phase_fn.__name__} crashed: {e}")

    final_validation()
