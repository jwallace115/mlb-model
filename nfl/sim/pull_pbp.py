#!/usr/bin/env python3
"""
NFL Sim Phase 0 — pull nflverse play-by-play and run a schema audit.

Writes per-season parquets to nfl/data/pbp/pbp_<season>.parquet.
Fails loudly if a season download fails; no partial files left behind.
"""

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
PBP_DIR.mkdir(parents=True, exist_ok=True)

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

REQUIRED_COLUMNS = [
    "game_id", "season", "week", "home_team", "away_team",
    "posteam", "defteam", "down", "ydstogo", "yardline_100",
    "qtr", "game_seconds_remaining", "score_differential",
    "play_type", "yards_gained", "epa", "success",
    "xpass", "pass_oe", "complete_pass", "sack", "interception",
    "fumble_lost", "penalty", "field_goal_result", "kick_distance",
    "passer_player_id", "rusher_player_id", "receiver_player_id",
    "td_team", "two_point_attempt", "extra_point_result",
]


def pull_season(season: int) -> pd.DataFrame:
    """Pull one season of PBP via nflreadpy. Fail loudly on error."""
    import nflreadpy
    try:
        df = nflreadpy.load_pbp([season]).to_pandas()
    except Exception as e:
        print(f"FATAL: failed to load PBP for {season}: {type(e).__name__}: {e}")
        sys.exit(1)
    if df.empty:
        print(f"FATAL: PBP for {season} returned 0 rows")
        sys.exit(1)
    return df


def write_safe(df: pd.DataFrame, path: Path):
    """Write to parquet atomically — no partial file on failure."""
    tmp = path.with_suffix(".tmp")
    try:
        df.to_parquet(tmp, index=False)
        tmp.rename(path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def schema_audit(dfs: dict[int, pd.DataFrame]):
    """Print schema audit for all seasons."""
    print("\n" + "=" * 80)
    print("SCHEMA AUDIT")
    print("=" * 80)

    all_missing = {}
    for season in sorted(dfs.keys()):
        df = dfs[season]
        n_rows = len(df)
        n_games = df["game_id"].nunique()
        min_week = df["week"].min()
        max_week = df["week"].max()

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        all_missing[season] = missing

        status = "OK" if not missing else f"MISSING: {missing}"
        print(f"  {season}  rows={n_rows:>7,}  games={n_games:>4}  "
              f"weeks={int(min_week):>2}–{int(max_week):>2}  {status}")

    print()
    any_missing = any(v for v in all_missing.values())
    if any_missing:
        print("  *** MISSING COLUMNS ***")
        for season, cols in all_missing.items():
            if cols:
                print(f"    {season}: {cols}")
    else:
        print("  All 32 required columns present in every season.")


def sanity_checks(dfs: dict[int, pd.DataFrame]):
    """Print sanity checks: plays/game and post-kickoff field position."""
    print("\n" + "=" * 80)
    print("SANITY CHECKS")
    print("=" * 80)

    # Plays per game (REG only, including no-plays)
    print("\n  Plays per game (REG, all play_type including no-plays):")
    for season in sorted(dfs.keys()):
        df = dfs[season]
        reg = df[df["season_type"] == "REG"] if "season_type" in df.columns else df
        if reg.empty:
            print(f"    {season}: no REG games")
            continue
        ppg = reg.groupby("game_id").size()
        print(f"    {season}  mean={ppg.mean():.1f}  median={ppg.median():.0f}  "
              f"min={ppg.min()}  max={ppg.max()}  games={len(ppg)}")

    # Post-kickoff starting field position (2024-2025, dynamic kickoff rules)
    print("\n  Post-kickoff starting yardline (first scrimmage play after kickoff, REG):")
    for season in [2024, 2025]:
        if season not in dfs:
            continue
        df = dfs[season]
        reg = df[df["season_type"] == "REG"] if "season_type" in df.columns else df

        # Identify kickoffs and the next scrimmage play
        reg = reg.sort_values(["game_id", "play_id"]).reset_index(drop=True)
        kickoff_mask = reg["play_type"] == "kickoff"
        # The play after a kickoff that is a scrimmage play
        next_idx = kickoff_mask[kickoff_mask].index + 1
        next_idx = next_idx[next_idx < len(reg)]
        next_plays = reg.loc[next_idx]
        scrimmage = next_plays[next_plays["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])]

        if scrimmage.empty or "yardline_100" not in scrimmage.columns:
            print(f"    {season}: insufficient data")
            continue

        yl = scrimmage["yardline_100"].dropna()
        print(f"    {season}  mean={yl.mean():.1f}  median={yl.median():.0f}  "
              f"n={len(yl)}  (lower = closer to opponent end zone)")


def main():
    print("NFL Sim Phase 0: nflverse PBP pull")
    print(f"Seasons: {SEASONS}")
    print(f"Output:  {PBP_DIR}/")
    print()

    dfs = {}
    for season in SEASONS:
        print(f"  Pulling {season}...", end=" ", flush=True)
        df = pull_season(season)
        out = PBP_DIR / f"pbp_{season}.parquet"
        write_safe(df, out)
        size_mb = out.stat().st_size / 1_048_576
        print(f"{len(df):>7,} rows  {df['game_id'].nunique():>4} games  "
              f"{size_mb:.1f} MB  -> {out.name}")
        dfs[season] = df

    schema_audit(dfs)
    sanity_checks(dfs)

    print("\nPhase 0 complete.")


if __name__ == "__main__":
    main()
