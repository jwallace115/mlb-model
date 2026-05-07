#!/usr/bin/env python3
"""
Rebuild Statcast Aggregates from Daily Pitch-Level Chunks
==========================================================
Reads mlb/props/data/statcast_chunk_*.parquet, rebuilds:
  1) pitcher_statcast_per_start.parquet  (pitcher × game grain)
  2) batter_game_statcast.parquet        (batter × game grain)

Replicates existing aggregation logic from run_enrichment.py (pitcher)
and batter_game_statcast BUILD_REGISTRY (batter). Backs up existing
files before overwriting. Idempotent, safe to run daily.

Usage:
  python3 mlb/pipeline/rebuild_statcast_aggregates.py
"""

import os
import shutil
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

CHUNK_DIR = PROJECT_ROOT / "mlb" / "props" / "data"
PITCHER_OUT = PROJECT_ROOT / "research" / "statcast_enrichment" / "pitcher_statcast_per_start.parquet"
BATTER_OUT = PROJECT_ROOT / "research" / "recovery" / "mlb_hitter_statcast_substrate" / "batter_game_statcast.parquet"
HGL_PATH = PROJECT_ROOT / "mlb" / "data" / "hitter_game_logs.parquet"


def _backup(path):
    if path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.with_suffix(f".parquet.bak_{ts}")
        shutil.copy2(path, bak)
        print(f"  Backup: {bak}")


def _load_chunks():
    """Load all statcast_chunk_*.parquet files."""
    files = sorted(CHUNK_DIR.glob("statcast_chunk_*.parquet"))
    if not files:
        print("ERROR: No statcast_chunk_*.parquet files found")
        sys.exit(1)

    dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            # Filter to regular season
            if "game_type" in df.columns:
                df = df[df["game_type"] == "R"]
            if "game_date" in df.columns:
                df["game_date"] = pd.to_datetime(df["game_date"])
            dfs.append(df)
            gd = df["game_date"] if "game_date" in df.columns else None
            mn = gd.min().date() if gd is not None and len(gd) > 0 else "?"
            mx = gd.max().date() if gd is not None and len(gd) > 0 else "?"
            print(f"  {f.name}: {len(df):>7,} rows  {mn} → {mx}")
        except Exception as e:
            print(f"  WARNING: skipping {f.name}: {e}")

    raw = pd.concat(dfs, ignore_index=True)
    # Dedup at pitch level
    dedup_cols = ["game_pk", "pitcher", "at_bat_number", "pitch_number"]
    avail = [c for c in dedup_cols if c in raw.columns]
    if avail:
        before = len(raw)
        raw = raw.drop_duplicates(subset=avail, keep="last")
        duped = before - len(raw)
        if duped > 0:
            print(f"  Deduped: {duped:,} duplicate pitches removed")
    print(f"  Total pitches: {len(raw):,}")
    return raw


# ═══════════════════════════════════════════════════════
# PITCHER AGGREGATE — exact replica of _aggregate_pitcher_start
# ═══════════════════════════════════════════════════════

def _build_pitcher_aggregate(raw):
    """Replicate run_enrichment._aggregate_pitcher_start on full dataset."""
    print("\n" + "=" * 60)
    print("PITCHER AGGREGATE")
    print("=" * 60)

    df = raw.copy()

    required = ["pitcher", "game_pk", "game_date", "player_name"]
    for c in required:
        if c not in df.columns:
            print(f"ERROR: missing required column {c}")
            sys.exit(1)

    # BIP
    df["is_bip"] = df["description"].isin([
        "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"
    ]).astype(int)

    if "launch_speed" in df.columns:
        df["is_hard_hit"] = (
            (df["launch_speed"].fillna(0) >= 95) & (df["is_bip"] == 1)
        ).astype(int)
    else:
        df["is_hard_hit"] = 0

    # Barrel (EV-dependent angle range)
    if "launch_speed" in df.columns and "launch_angle" in df.columns:
        ev = df["launch_speed"].fillna(0).clip(upper=116)
        la = df["launch_angle"].fillna(-999)
        bonus = (ev - 98).clip(lower=0)
        df["is_barrel"] = (
            (df["launch_speed"].fillna(0) >= 98)
            & (la >= (26 - bonus).clip(lower=0))
            & (la <= (30 + bonus).clip(upper=50))
            & (df["is_bip"] == 1)
        ).astype(int)
    else:
        df["is_barrel"] = 0

    # Zone / chase
    if "zone" in df.columns:
        zone_nn = df["zone"].fillna(0)
        df["is_in_zone"] = zone_nn.between(1, 9).astype(int)
        df["is_outside_zone"] = ((zone_nn > 0) & ~zone_nn.between(1, 9)).astype(int)
    else:
        df["is_in_zone"] = np.nan
        df["is_outside_zone"] = np.nan

    df["is_swing"] = df["description"].isin([
        "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
        "foul_bunt", "missed_bunt", "hit_into_play", "hit_into_play_no_out",
        "hit_into_play_score"
    ]).astype(int)
    df["is_whiff"] = df["description"].isin([
        "swinging_strike", "swinging_strike_blocked"
    ]).astype(int)
    df["is_contact"] = ((df["is_swing"] == 1) & (df["is_whiff"] == 0)).astype(int)
    df["is_chase"] = ((df["is_outside_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_swing"] = ((df["is_in_zone"] == 1) & (df["is_swing"] == 1)).astype(int)
    df["is_zone_contact"] = ((df["is_zone_swing"] == 1) & (df["is_contact"] == 1)).astype(int)

    # Spin by pitch type
    if "release_spin_rate" in df.columns and "pitch_type" in df.columns:
        df["spin_ff"] = np.where(df["pitch_type"].isin(["FF", "SI"]),
                                 df["release_spin_rate"], np.nan)
        df["spin_sl"] = np.where(df["pitch_type"].isin(["SL", "ST", "SV"]),
                                 df["release_spin_rate"], np.nan)
    else:
        df["spin_ff"] = np.nan
        df["spin_sl"] = np.nan

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

    # Rates
    agg["hard_hit_rate"] = agg["hard_hits"] / agg["bip"].clip(lower=1)
    agg["barrel_rate"] = agg["barrels"] / agg["bip"].clip(lower=1)
    agg["chase_rate"] = agg["chases"] / agg["outside_zone"].clip(lower=1)
    agg["zone_rate"] = agg["in_zone"] / agg["total_pitches"].clip(lower=1)
    agg["zone_contact_rate"] = agg["zone_contacts"] / agg["zone_swings"].clip(lower=1)
    agg["whiff_rate"] = agg["whiffs"] / agg["swings"].clip(lower=1)

    # Filter to meaningful starts (>= 30 pitches)
    agg = agg[agg["total_pitches"] >= 30].copy()

    # ── 2-strike secondary pitch mix (for YRFI signals S2/S4) ──
    PRIMARY_FB = {"FF", "SI", "FC", "FA"}
    if "pitch_type" in df.columns and "strikes" in df.columns:
        df["is_secondary"] = (~df["pitch_type"].isin(PRIMARY_FB)).astype(int)
        df["is_two_strike"] = (df["strikes"].fillna(-1) == 2).astype(int)
        df["is_two_strike_secondary"] = (
            (df["is_two_strike"] == 1) & (df["is_secondary"] == 1)
        ).astype(int)

        pitch_mix = df.groupby(["pitcher", "game_date", "game_pk"]).agg(
            two_strike_pitch_count=("is_two_strike", "sum"),
            two_strike_secondary_count=("is_two_strike_secondary", "sum"),
            secondary_pitch_count=("is_secondary", "sum"),
        ).reset_index().rename(columns={"pitcher": "pitcher_id"})

        pitch_mix["two_strike_secondary_pct"] = np.where(
            pitch_mix["two_strike_pitch_count"] > 0,
            pitch_mix["two_strike_secondary_count"] / pitch_mix["two_strike_pitch_count"],
            np.nan,
        )
        pitch_mix["secondary_pitch_pct"] = np.where(
            True,  # total_pitches always > 0 at this point
            pitch_mix["secondary_pitch_count"],  # will divide after merge
            np.nan,
        )

        agg = agg.merge(
            pitch_mix[["pitcher_id", "game_date", "game_pk",
                        "two_strike_secondary_pct", "two_strike_pitch_count",
                        "two_strike_secondary_count", "secondary_pitch_count"]],
            on=["pitcher_id", "game_date", "game_pk"], how="left",
        )
        agg["secondary_pitch_pct"] = agg["secondary_pitch_count"] / agg["total_pitches"].clip(lower=1)
        agg = agg.drop(columns=["two_strike_pitch_count", "two_strike_secondary_count",
                                  "secondary_pitch_count"])

        nn_2s = agg["two_strike_secondary_pct"].notna().sum()
        nn_sp = agg["secondary_pitch_pct"].notna().sum()
        print(f"  two_strike_secondary_pct non-null: {nn_2s:,}")
        print(f"  secondary_pitch_pct non-null: {nn_sp:,}")
    else:
        agg["two_strike_secondary_pct"] = np.nan
        agg["secondary_pitch_pct"] = np.nan
        print("  WARNING: pitch_type or strikes column missing — 2-strike features null")

    print(f"  Rows: {len(agg):,}")
    print(f"  Date range: {agg['game_date'].min()} to {agg['game_date'].max()}")
    print(f"  Columns: {agg.columns.tolist()}")
    return agg


# ═══════════════════════════════════════════════════════
# BATTER AGGREGATE — replica of batter_game_statcast build
# ═══════════════════════════════════════════════════════

def _build_batter_aggregate(raw):
    """Replicate batter_game_statcast build from BUILD_REGISTRY."""
    print("\n" + "=" * 60)
    print("BATTER AGGREGATE")
    print("=" * 60)

    df = raw.copy()

    required = ["batter", "game_pk", "game_date"]
    for c in required:
        if c not in df.columns:
            print(f"ERROR: missing required column {c}")
            sys.exit(1)

    # BIP subset: type == 'X'
    if "type" not in df.columns:
        print("ERROR: missing 'type' column for BIP identification")
        sys.exit(1)

    bip = df[df["type"] == "X"].copy()
    print(f"  BIP rows: {len(bip):,}")

    # Hard hit
    if "launch_speed" in bip.columns:
        bip["is_hard_hit"] = (bip["launch_speed"].fillna(0) >= 95).astype(int)
    else:
        bip["is_hard_hit"] = 0

    # Barrel via launch_speed_angle == 6 (Statcast barrel classification)
    if "launch_speed_angle" in bip.columns:
        bip["is_barrel"] = (bip["launch_speed_angle"].fillna(-1) == 6).astype(int)
    else:
        bip["is_barrel"] = 0

    # Partial sums per batter-game for weighted means
    for col, flag in [
        ("launch_speed", "has_ev"),
        ("launch_angle", "has_la"),
        ("estimated_woba_using_speedangle", "has_xwoba"),
        ("estimated_ba_using_speedangle", "has_xba"),
        ("estimated_slg_using_speedangle", "has_xslg"),
    ]:
        if col in bip.columns:
            bip[flag] = bip[col].notna().astype(int)
            bip[f"sum_{col}"] = bip[col].fillna(0) * bip[flag]
        else:
            bip[flag] = 0
            bip[f"sum_{col}"] = 0

    # Aggregate BIP per batter-game
    batter_bip = bip.groupby(["game_pk", "batter", "game_date"]).agg(
        bip_count=("batter", "count"),
        hard_hit_count=("is_hard_hit", "sum"),
        barrel_count=("is_barrel", "sum"),
        n_ev=("has_ev", "sum"),
        sum_ev=("sum_launch_speed", "sum"),
        n_la=("has_la", "sum"),
        sum_la=("sum_launch_angle", "sum"),
        n_xwoba=("has_xwoba", "sum"),
        sum_xwoba=("sum_estimated_woba_using_speedangle", "sum"),
        n_xba=("has_xba", "sum"),
        sum_xba=("sum_estimated_ba_using_speedangle", "sum"),
        n_xslg=("has_xslg", "sum"),
        sum_xslg=("sum_estimated_slg_using_speedangle", "sum"),
    ).reset_index()

    # Total pitches per batter-game (all pitches, not just BIP)
    all_pitches = df.groupby(["game_pk", "batter", "game_date"]).agg(
        total_pitches=("batter", "count"),
    ).reset_index()

    batter_agg = batter_bip.merge(all_pitches, on=["game_pk", "batter", "game_date"], how="left")

    # Compute means
    batter_agg["avg_exit_velo"] = np.where(
        batter_agg["n_ev"] > 0,
        batter_agg["sum_ev"] / batter_agg["n_ev"],
        np.nan
    )
    batter_agg["hard_hit_rate"] = np.where(
        batter_agg["n_ev"] > 0,
        batter_agg["hard_hit_count"] / batter_agg["n_ev"],
        np.nan
    )
    batter_agg["barrel_rate"] = np.where(
        batter_agg["bip_count"] > 0,
        batter_agg["barrel_count"] / batter_agg["bip_count"],
        np.nan
    )
    batter_agg["avg_launch_angle"] = np.where(
        batter_agg["n_la"] > 0,
        batter_agg["sum_la"] / batter_agg["n_la"],
        np.nan
    )
    batter_agg["xwoba_contact"] = np.where(
        batter_agg["n_xwoba"] > 0,
        batter_agg["sum_xwoba"] / batter_agg["n_xwoba"],
        np.nan
    )
    batter_agg["xba_contact"] = np.where(
        batter_agg["n_xba"] > 0,
        batter_agg["sum_xba"] / batter_agg["n_xba"],
        np.nan
    )
    batter_agg["xslg_contact"] = np.where(
        batter_agg["n_xslg"] > 0,
        batter_agg["sum_xslg"] / batter_agg["n_xslg"],
        np.nan
    )

    # Drop intermediate columns
    batter_agg = batter_agg.drop(columns=[
        "hard_hit_count", "barrel_count",
        "n_ev", "sum_ev", "n_la", "sum_la",
        "n_xwoba", "sum_xwoba", "n_xba", "sum_xba", "n_xslg", "sum_xslg",
    ])

    # Join to hitter_game_logs for team/season/position context (LEFT join to keep all rows)
    if HGL_PATH.exists():
        hgl = pd.read_parquet(HGL_PATH)
        hgl_cols = hgl[["game_pk", "player_id", "team", "home_away", "season",
                         "batting_order_position"]].drop_duplicates(
                             subset=["game_pk", "player_id"])
        before = len(batter_agg)
        batter_agg = batter_agg.merge(
            hgl_cols, left_on=["game_pk", "batter"],
            right_on=["game_pk", "player_id"], how="left"
        )
        matched = batter_agg["player_id"].notna().sum()
        print(f"  HGL join (left): {before:,} rows, {matched:,} matched ({matched/before*100:.1f}%)")
        # Fill missing context for unmatched rows
        batter_agg["player_id"] = batter_agg["player_id"].fillna(batter_agg["batter"])
        batter_agg["season"] = batter_agg["season"].fillna(
            pd.to_datetime(batter_agg["game_date"]).dt.year)
    else:
        print("  WARNING: hitter_game_logs.parquet not found — no team/season context")
        batter_agg["player_id"] = batter_agg["batter"]
        batter_agg["team"] = None
        batter_agg["home_away"] = None
        batter_agg["season"] = pd.to_datetime(batter_agg["game_date"]).dt.year
        batter_agg["batting_order_position"] = None

    # Final column order to match existing schema
    final_cols = [
        "game_pk", "game_date", "batter", "player_id", "team", "home_away",
        "season", "batting_order_position", "total_pitches", "bip_count",
        "avg_exit_velo", "hard_hit_rate", "barrel_rate", "avg_launch_angle",
        "xwoba_contact", "xba_contact", "xslg_contact",
    ]
    for c in final_cols:
        if c not in batter_agg.columns:
            batter_agg[c] = np.nan
    batter_agg = batter_agg[final_cols]

    print(f"  Rows: {len(batter_agg):,}")
    print(f"  Date range: {batter_agg['game_date'].min()} to {batter_agg['game_date'].max()}")
    print(f"  Columns: {batter_agg.columns.tolist()}")
    return batter_agg


def main():
    print(f"Statcast Aggregate Rebuild — {datetime.now().isoformat()}")
    print("=" * 60)
    print("Loading chunks from", CHUNK_DIR)

    raw = _load_chunks()

    pitcher = _build_pitcher_aggregate(raw)
    batter = _build_batter_aggregate(raw)

    # Backup and write
    print("\n" + "=" * 60)
    print("WRITING OUTPUTS")
    print("=" * 60)

    PITCHER_OUT.parent.mkdir(parents=True, exist_ok=True)
    BATTER_OUT.parent.mkdir(parents=True, exist_ok=True)

    _backup(PITCHER_OUT)
    pitcher.to_parquet(PITCHER_OUT, index=False)
    print(f"  Pitcher: {PITCHER_OUT} ({len(pitcher):,} rows)")

    _backup(BATTER_OUT)
    batter.to_parquet(BATTER_OUT, index=False)
    print(f"  Batter:  {BATTER_OUT} ({len(batter):,} rows)")

    print("\nDone.")


if __name__ == "__main__":
    main()
