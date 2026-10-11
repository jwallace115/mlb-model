#!/usr/bin/env python3
"""
Pull nflverse post-game data for season 2026 and archive append-only.

Feeds:
  a) PBP — one slice per FINAL game (all columns).
     Final = the game's last play desc contains "END GAME".
     data/results_archive/nfl/pbp/season=2026/pbp_<game_id>_<UTC>.parquet
     A changed slice (stat correction) writes a NEW file; never overwrite.
  b) Snap counts — data/results_archive/nfl/snap_counts_2026_<UTC>.parquet
  c) FTN charting — data/results_archive/nfl/ftn_charting_2026_<UTC>.parquet
     If FTN unavailable, logs and continues.
  d) Log — data/results_archive/nfl/_postgame_pulls.jsonl

Hash-skip: sha256 of the parquet bytes; if the newest existing file for a
game/feed matches, nothing is written.

HALT on: empty PBP, no week >= 1, missing required builder columns,
any single game slice > 2 MB.

PM-1 Item 1, P48.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (ROOT / "data" / "results_archive"))

# Columns the item-2 builder (build_postgame.py) uses from PBP.
# HALT if any of these are missing from the nflverse PBP frame.
BUILDER_COLUMNS = [
    "game_id", "home_team", "away_team", "week", "season",
    "play_id", "play_type", "desc", "qtr",
    "score_differential", "home_score", "away_score",
    "posteam", "defteam",
    "pass_attempt", "rush_attempt", "sack", "complete_pass",
    "yards_gained", "passing_yards", "receiving_yards", "rushing_yards",
    "interception", "fumble", "fumble_lost", "touchdown",
    "passer_player_id", "passer_player_name",
    "receiver_player_id", "receiver_player_name",
    "rusher_player_id", "rusher_player_name",
    "yardline_100", "result",
]

MAX_SLICE_BYTES = 2 * 1024 * 1024  # 2 MB


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _log_entry(log_path, **kw):
    with open(log_path, "a") as f:
        f.write(json.dumps(kw, default=str) + "\n")


def _newest_hash(directory, prefix):
    """Return sha256 of the newest file matching prefix in directory, or None."""
    if not directory.exists():
        return None
    files = sorted(directory.glob(f"{prefix}*.parquet"))
    if not files:
        return None
    return _sha256(files[-1].read_bytes())


def _is_final(game_pbp):
    """A game is final if its last play desc contains 'END GAME'."""
    if game_pbp.empty:
        return False
    last_plays = game_pbp.sort_values("play_id")
    last_desc = str(last_plays.iloc[-1].get("desc", ""))
    return "END GAME" in last_desc.upper()


def pull(season=2026):
    """Pull all feeds for the season. Returns summary dict."""
    t0 = time.time()
    now_utc = datetime.now(timezone.utc)
    ts = now_utc.strftime("%Y%m%dT%H%M%S") + f"{now_utc.microsecond // 1000:03d}Z"

    results_dir = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or RESULTS_DIR)
    nfl_dir = results_dir / "nfl"
    pbp_dir = nfl_dir / "pbp" / f"season={season}"
    pbp_dir.mkdir(parents=True, exist_ok=True)
    nfl_dir.mkdir(parents=True, exist_ok=True)
    log_path = nfl_dir / "_postgame_pulls.jsonl"

    # ── PBP ──
    raw = nflreadpy.load_pbp([season])
    if hasattr(raw, "to_pandas"):
        raw = raw.to_pandas()
    pbp = raw

    if pbp.empty:
        print("HALT: nflverse PBP returned empty", file=sys.stderr)
        sys.exit(1)
    if not (pbp["week"] >= 1).any():
        print("HALT: no PBP row with week >= 1", file=sys.stderr)
        sys.exit(1)

    missing_cols = [c for c in BUILDER_COLUMNS if c not in pbp.columns]
    if missing_cols:
        print(f"HALT: PBP missing required builder columns: {missing_cols}", file=sys.stderr)
        sys.exit(1)

    # Per-game slices for FINAL games only
    pbp_written = 0
    pbp_unchanged = 0
    games_by_week = {}
    sizes = []

    for game_id, game_pbp in pbp.groupby("game_id"):
        if not _is_final(game_pbp):
            continue

        week = int(game_pbp["week"].iloc[0])
        games_by_week[week] = games_by_week.get(week, 0) + 1

        # Serialize to parquet bytes in memory for hash comparison
        buf = game_pbp.to_parquet(index=False)
        if isinstance(buf, pd.DataFrame):
            # to_parquet returns None when writing to file; use BytesIO
            import io
            bio = io.BytesIO()
            game_pbp.to_parquet(bio, index=False)
            buf = bio.getvalue()

        new_hash = _sha256(buf)
        slice_size = len(buf)
        sizes.append((game_id, slice_size))

        if slice_size > MAX_SLICE_BYTES:
            print(f"HALT: PBP slice for {game_id} is {slice_size:,} bytes (> 2 MB)", file=sys.stderr)
            sys.exit(1)

        # Check if newest existing file for this game has the same hash
        existing = sorted(pbp_dir.glob(f"pbp_{game_id}_*.parquet"))
        if existing:
            existing_hash = _sha256(existing[-1].read_bytes())
            if existing_hash == new_hash:
                pbp_unchanged += 1
                _log_entry(log_path, utc=ts, feed="pbp", game_id=game_id,
                           rows=len(game_pbp), sha256=new_hash, status="unchanged")
                continue

        # Write new file
        out_path = pbp_dir / f"pbp_{game_id}_{ts}.parquet"
        out_path.write_bytes(buf)
        pbp_written += 1
        _log_entry(log_path, utc=ts, feed="pbp", game_id=game_id,
                   rows=len(game_pbp), sha256=new_hash, status="written")

    # ── Snap counts ──
    snap_written = 0
    try:
        raw_sc = nflreadpy.load_snap_counts([season])
        if hasattr(raw_sc, "to_pandas"):
            raw_sc = raw_sc.to_pandas()
        if not raw_sc.empty:
            import io
            bio = io.BytesIO()
            raw_sc.to_parquet(bio, index=False)
            sc_bytes = bio.getvalue()
            sc_hash = _sha256(sc_bytes)

            existing_hash = _newest_hash(nfl_dir, f"snap_counts_{season}_")
            if existing_hash != sc_hash:
                out = nfl_dir / f"snap_counts_{season}_{ts}.parquet"
                out.write_bytes(sc_bytes)
                snap_written = 1
                _log_entry(log_path, utc=ts, feed="snap_counts", game_id=None,
                           rows=len(raw_sc), sha256=sc_hash, status="written")
            else:
                _log_entry(log_path, utc=ts, feed="snap_counts", game_id=None,
                           rows=len(raw_sc), sha256=sc_hash, status="unchanged")
        else:
            _log_entry(log_path, utc=ts, feed="snap_counts", game_id=None,
                       rows=0, sha256=None, status="unavailable")
    except Exception as e:
        _log_entry(log_path, utc=ts, feed="snap_counts", game_id=None,
                   rows=0, sha256=None, status=f"unavailable: {e}")

    # ── FTN charting ──
    ftn_written = 0
    try:
        raw_ftn = nflreadpy.load_ftn_charting([season])
        if hasattr(raw_ftn, "to_pandas"):
            raw_ftn = raw_ftn.to_pandas()
        if not raw_ftn.empty:
            import io
            bio = io.BytesIO()
            raw_ftn.to_parquet(bio, index=False)
            ftn_bytes = bio.getvalue()
            ftn_hash = _sha256(ftn_bytes)

            existing_hash = _newest_hash(nfl_dir, f"ftn_charting_{season}_")
            if existing_hash != ftn_hash:
                out = nfl_dir / f"ftn_charting_{season}_{ts}.parquet"
                out.write_bytes(ftn_bytes)
                ftn_written = 1
                _log_entry(log_path, utc=ts, feed="ftn_charting", game_id=None,
                           rows=len(raw_ftn), sha256=ftn_hash, status="written")
            else:
                _log_entry(log_path, utc=ts, feed="ftn_charting", game_id=None,
                           rows=len(raw_ftn), sha256=ftn_hash, status="unchanged")
        else:
            print("ftn unavailable: empty dataframe")
            _log_entry(log_path, utc=ts, feed="ftn_charting", game_id=None,
                       rows=0, sha256=None, status="unavailable")
    except Exception as e:
        print(f"ftn unavailable: {e}")
        _log_entry(log_path, utc=ts, feed="ftn_charting", game_id=None,
                   rows=0, sha256=None, status=f"unavailable: {e}")

    elapsed = time.time() - t0
    total_games = pbp_written + pbp_unchanged
    total_mb = sum(s for _, s in sizes) / 1024 / 1024

    print(f"PBP: {pbp_written} written, {pbp_unchanged} unchanged, {total_games} final games")
    print(f"Games per week: {dict(sorted(games_by_week.items()))}")
    print(f"Snap counts: {'written' if snap_written else 'unchanged'}")
    print(f"FTN charting: {'written' if ftn_written else 'unchanged/unavailable'}")
    print(f"Total MB: {total_mb:.1f}")
    print(f"Wall time: {elapsed:.1f}s")

    return {
        "pbp_written": pbp_written,
        "pbp_unchanged": pbp_unchanged,
        "snap_written": snap_written,
        "ftn_written": ftn_written,
        "games_by_week": games_by_week,
        "total_mb": total_mb,
        "elapsed": elapsed,
    }


if __name__ == "__main__":
    pull()
