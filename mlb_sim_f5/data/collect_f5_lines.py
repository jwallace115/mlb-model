#!/usr/bin/env python3
"""
F5 Data Collection Pipeline — 2026
===================================
Captures F5 (first 5 innings) market data for every MLB game.
Pure data collection infrastructure — no modeling, no signals.

Pull schedule (maps to existing launchd times):
  7:00 AM  → pull_type = "open"
  11:00 AM → pull_type = "midday"
  5:00 PM  → pull_type = "close"
             NOTE: "close" is the latest scheduled pregame pull,
             not a guaranteed official market close. Late games
             (9PM+) may still have lines moving after this pull.

  signal_time → written only when V1 under engine fires a signal

Uniqueness: one row per game_id + date + pull_type.
Update in place, never append duplicates.
"""

import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("f5_collect")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
F5_DATA = Path(__file__).resolve().parent
F5_LINES_PATH = F5_DATA / "f5_lines_2026.parquet"
F5_COVERAGE_PATH = F5_DATA / "f5_coverage_2026.json"
SIGNALS_PATH = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.parquet"

F5_COLS = [
    "date", "game_id", "home_team", "away_team", "game_time",
    "pull_timestamp", "pull_type", "book_key",
    "f5_total", "f5_over_price", "f5_under_price",
    "f5_moneyline_home", "f5_moneyline_away",
    "actual_f5_total", "is_canonical",
]


def _select_canonical_line(f5_data):
    """
    Select the canonical F5 total line from multi-book data.

    Canonical = the line where abs(over_price - under_price) is minimized
    (most balanced prices). Tiebreaker: prefer the lower line.

    Args:
        f5_data: dict from _build_game_lines, containing per-book entries
                 like {"draftkings": {"line": 4.5, "over": -115, "under": -115}, ...}
                 plus "consensus", "best_over", "best_under" keys.

    Returns:
        (f5_total, over_price, under_price, book_key) or (None, None, None, None)
    """
    if not f5_data:
        return None, None, None, None

    # Collect all book lines with prices
    candidates = []
    skip_keys = {"consensus", "best_over", "best_under", "home_team", "away_team",
                 "book", "source", "over_price", "under_price"}
    for key, val in f5_data.items():
        if key in skip_keys or not isinstance(val, dict):
            continue
        line = val.get("line")
        over = val.get("over")
        under = val.get("under")
        if line is not None and over is not None and under is not None:
            candidates.append({
                "book": key,
                "line": float(line),
                "over": int(over),
                "under": int(under),
                "balance": abs(int(over) - int(under)),
            })

    if not candidates:
        # No book-level data with prices — fall back to consensus
        total = f5_data.get("consensus")
        if total is not None:
            return total, None, None, None
        return None, None, None, None

    # Sort: most balanced first (lowest abs diff), then lowest line as tiebreaker
    candidates.sort(key=lambda c: (c["balance"], c["line"]))
    best = candidates[0]
    return best["line"], best["over"], best["under"], best["book"]


def _load_f5_lines():
    """Load existing F5 lines or create empty DataFrame."""
    if F5_LINES_PATH.exists():
        df = pd.read_parquet(F5_LINES_PATH)
        # Add is_canonical column if missing (backward compat)
        if "is_canonical" not in df.columns:
            df["is_canonical"] = True  # treat legacy rows as canonical
        return df
    logger.info("First run — initializing F5 data files")
    return pd.DataFrame(columns=F5_COLS)


def _save_f5_lines(df):
    F5_DATA.mkdir(parents=True, exist_ok=True)
    df.to_parquet(F5_LINES_PATH, index=False)


def _ensure_signals_f5_column():
    """Add f5_line_at_signal_time column to signals_2026.parquet if missing."""
    if not SIGNALS_PATH.exists():
        return
    sigs = pd.read_parquet(SIGNALS_PATH)
    if "f5_line_at_signal_time" not in sigs.columns:
        sigs["f5_line_at_signal_time"] = None
        sigs.to_parquet(SIGNALS_PATH, index=False)
        logger.info("Added f5_line_at_signal_time column to signals_2026.parquet")


def pull_f5_lines(game_date_str, pull_type, schedule=None):
    """
    Pull F5 lines for all games on game_date.

    Args:
        game_date_str: "YYYY-MM-DD"
        pull_type: "open" | "midday" | "close" | "signal_time"
        schedule: list of game dicts from modules/schedule.py
            Each needs: game_pk, home_team, away_team, game_time (optional)
    """
    if schedule is None:
        logger.info("No schedule provided — skipping F5 pull")
        return

    # Fetch F5 odds via per-event endpoint (bulk endpoint doesn't carry F5)
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from modules.odds import ODDS_API_TEAM_MAP
        from config import ODDS_API_KEY, ODDS_API_BASE
    except ImportError as e:
        logger.warning(f"Cannot import odds config: {e}")
        return

    import requests as _req

    # Get event IDs from bulk endpoint
    try:
        _r = _req.get(f"{ODDS_API_BASE}/sports/baseball_mlb/odds/",
                      params={"apiKey": ODDS_API_KEY, "regions": "us",
                              "markets": "totals", "oddsFormat": "american"}, timeout=30)
        _bulk = _r.json() if _r.status_code == 200 else []
    except Exception:
        _bulk = []

    _eid_map = {}
    for _bg in _bulk:
        _h = ODDS_API_TEAM_MAP.get(_bg.get("home_team", ""))
        _a = ODDS_API_TEAM_MAP.get(_bg.get("away_team", ""))
        if _h and _a:
            _eid_map[(_h, _a)] = _bg["id"]

    df = _load_f5_lines()
    now_utc = datetime.now(timezone.utc).isoformat()
    updated_count = 0
    inserted_count = 0

    for game in schedule:
        gid = str(game.get("game_pk", ""))
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        gtime = game.get("game_time_et") or game.get("game_time") or None

        # Per-event F5 totals call
        _eid = _eid_map.get((home, away))
        f5_data = {}
        if _eid:
            try:
                _r2 = _req.get(f"{ODDS_API_BASE}/sports/baseball_mlb/events/{_eid}/odds",
                               params={"apiKey": ODDS_API_KEY, "regions": "us",
                                       "markets": "totals_1st_5_innings",
                                       "oddsFormat": "american"}, timeout=15)
                if _r2.status_code == 200:
                    _bks = _r2.json().get("bookmakers", [])
                    # Build f5_data in same format as _build_game_lines output
                    for _bk in _bks:
                        f5_data[_bk["key"]] = {"line": None, "over": None, "under": None}
                        for _m in _bk.get("markets", []):
                            if _m["key"] == "totals_1st_5_innings":
                                for _oc in _m.get("outcomes", []):
                                    if _oc["name"] == "Over":
                                        f5_data[_bk["key"]]["line"] = _oc.get("point")
                                        f5_data[_bk["key"]]["over"] = _oc.get("price")
                                    elif _oc["name"] == "Under":
                                        f5_data[_bk["key"]]["under"] = _oc.get("price")
            except Exception:
                pass

        f5_total, f5_over_price, f5_under_price, book_key = _select_canonical_line(f5_data)

        # F5 moneylines (capture if available)
        f5_ml_home = f5_data.get("home_ml")
        f5_ml_away = f5_data.get("away_ml")

        # Check for existing row (uniqueness: game_id + date + pull_type)
        mask = ((df["game_id"].astype(str) == gid) &
                (df["date"] == game_date_str) &
                (df["pull_type"] == pull_type))
        existing = df[mask]

        row_data = {
            "date": game_date_str,
            "game_id": gid,
            "home_team": home,
            "away_team": away,
            "game_time": gtime,
            "pull_timestamp": now_utc,
            "pull_type": pull_type,
            "book_key": book_key,
            "f5_total": f5_total,
            "f5_over_price": f5_over_price,
            "f5_under_price": f5_under_price,
            "f5_moneyline_home": f5_ml_home,
            "f5_moneyline_away": f5_ml_away,
            "actual_f5_total": None,
            "is_canonical": True if f5_total is not None else False,
        }

        if len(existing) > 0:
            # Update in place
            idx = existing.index[0]
            for col, val in row_data.items():
                if col != "actual_f5_total":  # don't overwrite actual if already filled
                    if col == "actual_f5_total" and pd.notna(df.at[idx, col]):
                        continue
                    df.at[idx, col] = val
            updated_count += 1
            logger.debug(f"  F5 updated: {away}@{home} ({pull_type}) line={f5_total}")
        else:
            # Insert new row
            new_row = pd.DataFrame([row_data], columns=F5_COLS)
            df = pd.concat([df, new_row], ignore_index=True)
            inserted_count += 1

    _save_f5_lines(df)
    total_with_line = df[(df["date"] == game_date_str) & (df["pull_type"] == pull_type) & df["f5_total"].notna()]
    logger.info(f"F5 {pull_type}: {inserted_count} new, {updated_count} updated, "
                f"{len(total_with_line)} with lines for {game_date_str}")


def pull_f5_for_signal(game_date_str, game_id, home_team, away_team):
    """
    Pull F5 line at signal time for a specific game.
    Called by V1 under engine when a signal fires.

    Updates:
      1. f5_lines_2026.parquet with pull_type="signal_time" row
      2. signals_2026.parquet f5_line_at_signal_time column
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from modules.odds import fetch_all_lines, get_game_lines
    except ImportError:
        return None

    f5_data = {}
    try:
        all_lines = fetch_all_lines(game_date_str)
        game_lines = get_game_lines(home_team, away_team, all_lines)
        f5_data = game_lines.get("f5") or {}
        f5_total, f5_over_price, f5_under_price, book_key = _select_canonical_line(f5_data)
    except Exception as e:
        logger.warning(f"F5 signal-time pull failed: {e}")
        f5_total = f5_over_price = f5_under_price = book_key = None

    # Write to f5_lines_2026.parquet
    df = _load_f5_lines()
    now_utc = datetime.now(timezone.utc).isoformat()
    gid = str(game_id)

    mask = ((df["game_id"].astype(str) == gid) &
            (df["date"] == game_date_str) &
            (df["pull_type"] == "signal_time"))

    row_data = {
        "date": game_date_str,
        "game_id": gid,
        "home_team": home_team,
        "away_team": away_team,
        "game_time": None,
        "pull_timestamp": now_utc,
        "pull_type": "signal_time",
        "book_key": book_key,
        "f5_total": f5_total,
        "f5_over_price": f5_over_price,
        "f5_under_price": f5_under_price,
        "f5_moneyline_home": None,
        "f5_moneyline_away": None,
        "actual_f5_total": None,
        "is_canonical": True if f5_total is not None else False,
    }

    if len(df[mask]) > 0:
        idx = df[mask].index[0]
        for col, val in row_data.items():
            if col != "actual_f5_total" or pd.isna(df.at[idx, col]):
                df.at[idx, col] = val
    else:
        df = pd.concat([df, pd.DataFrame([row_data], columns=F5_COLS)], ignore_index=True)

    _save_f5_lines(df)

    # Update signals_2026.parquet — f5_line_at_signal_time column only
    if SIGNALS_PATH.exists():
        sigs = pd.read_parquet(SIGNALS_PATH)
        if "f5_line_at_signal_time" not in sigs.columns:
            sigs["f5_line_at_signal_time"] = None
        sig_mask = ((sigs["game_id"].astype(str) == gid) & (sigs["date"] == game_date_str))
        if sig_mask.any():
            sigs.loc[sig_mask, "f5_line_at_signal_time"] = f5_total
            sigs.to_parquet(SIGNALS_PATH, index=False)
            logger.info(f"  F5 signal-time: {away_team}@{home_team} f5_line={f5_total}")

    return f5_total


def fill_actual_f5_scores(game_date_str):
    """
    Fill actual_f5_total for completed games.
    Uses feature_table.parquet as the source of truth.
    Idempotent: does not overwrite already-populated values.
    """
    if not F5_LINES_PATH.exists():
        return

    df = _load_f5_lines()
    pending = df[df["actual_f5_total"].isna()]
    if pending.empty:
        return

    # Load actual F5 scores from feature_table
    ft_path = PROJECT_ROOT / "sim" / "data" / "feature_table.parquet"
    if not ft_path.exists():
        return
    ft = pd.read_parquet(ft_path)
    ft["game_pk"] = ft["game_pk"].astype(str)

    scores = ft[ft["actual_f5_total"].notna()][["game_pk", "actual_f5_total"]].copy()
    score_map = dict(zip(scores["game_pk"], scores["actual_f5_total"]))

    updated = 0
    for idx, row in df.iterrows():
        if pd.notna(row["actual_f5_total"]):
            continue  # idempotent — don't overwrite
        gid = str(row["game_id"])
        if gid in score_map:
            df.at[idx, "actual_f5_total"] = score_map[gid]
            updated += 1

    if updated > 0:
        _save_f5_lines(df)
        logger.info(f"F5 actuals filled: {updated} rows")


def update_coverage():
    """Update f5_coverage_2026.json."""
    if not F5_LINES_PATH.exists():
        cov = {
            "last_updated": date.today().isoformat(),
            "total_games_played": 0, "total_games_with_f5_close": 0,
            "games_missing_f5_close": 0, "coverage_pct": 0,
            "total_v1_signals": 0, "total_v1_signals_no_f5": 0,
        }
        with open(F5_COVERAGE_PATH, "w") as f:
            json.dump(cov, f, indent=2)
        return cov

    df = _load_f5_lines()

    # Games with actual results (denominator)
    games_played = df[df["actual_f5_total"].notna()]["game_id"].nunique()

    # Games with close pull and F5 line
    close_rows = df[(df["pull_type"] == "close") & df["f5_total"].notna()]
    close_with_actual = close_rows[close_rows["actual_f5_total"].notna()]
    games_with_f5_close = close_with_actual["game_id"].nunique()

    missing = max(0, games_played - games_with_f5_close)
    coverage = games_with_f5_close / games_played * 100 if games_played > 0 else 0

    # V1 signal alignment
    v1_signals = 0
    v1_no_f5 = 0
    if SIGNALS_PATH.exists():
        sigs = pd.read_parquet(SIGNALS_PATH)
        if "f5_line_at_signal_time" in sigs.columns:
            resolved = sigs[sigs["resolved"] == 1]
            v1_signals = resolved["f5_line_at_signal_time"].notna().sum()
            v1_no_f5 = resolved["f5_line_at_signal_time"].isna().sum()

    cov = {
        "last_updated": date.today().isoformat(),
        "total_games_played": int(games_played),
        "total_games_with_f5_close": int(games_with_f5_close),
        "games_missing_f5_close": int(missing),
        "coverage_pct": round(coverage, 1),
        "total_v1_signals": int(v1_signals),
        "total_v1_signals_no_f5": int(v1_no_f5),
    }

    F5_DATA.mkdir(parents=True, exist_ok=True)
    with open(F5_COVERAGE_PATH, "w") as f:
        json.dump(cov, f, indent=2)
    logger.info(f"F5 coverage: {games_with_f5_close}/{games_played} ({coverage:.0f}%)")
    return cov


def run_daily(game_date_str, pull_type, schedule=None):
    """
    Full daily F5 collection run.
    Call from the main pipeline at each launchd trigger time.
    """
    logger.info(f"F5 collection: {pull_type} pull for {game_date_str}")

    # Ensure signals file has f5 column
    _ensure_signals_f5_column()

    # Fill actual scores for completed games
    fill_actual_f5_scores(game_date_str)

    # Pull F5 lines for today's games
    pull_f5_lines(game_date_str, pull_type, schedule)

    # Update coverage tracking
    update_coverage()
