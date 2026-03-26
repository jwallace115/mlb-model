#!/usr/bin/env python3
"""
F5 Run Line Signal Generator — Signal B (xFIP mismatch >= 1.0, home side).
Independent from V1, F5 totals, and all other engines.
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger("f5_runline")

BASE = Path(__file__).resolve().parent.parent
PROJECT = BASE.parent
LOGS = BASE / "logs"
PIPELINE = BASE / "pipeline"

SIGNALS_PATH = LOGS / "f5_runline_2026.parquet"
STATUS_PATH = PIPELINE / "f5_runline_status.json"
LINES_PATH = LOGS / "f5_runline_lines_2026.parquet"
PERF_PATH = LOGS / "f5_runline_performance_2026.json"

XFIP_GAP_THRESHOLD = 1.0
STAKE = 0.5
WIN_UNIT = 100 / 110  # fallback

SIGNAL_COLS = [
    "date", "game_id", "home_team", "away_team",
    "home_sp_name", "away_sp_name",
    "home_sp_xfip", "away_sp_xfip", "xfip_gap",
    "home_f5_line", "away_f5_line", "home_f5_price", "away_f5_price",
    "bet_side", "bet_line", "bet_price", "stake_units",
    "line_at_signal_time", "f5_line_closing", "f5_clv",
    "home_f5_score", "away_f5_score", "f5_margin",
    "result", "net_units", "resolved",
]

LINES_COLS = [
    "date", "game_id", "home_team", "away_team",
    "pull_timestamp", "pull_type",
    "home_line", "away_line", "home_price", "away_price",
    "primary_book", "books_count",
]


# ── File I/O ─────────────────────────────────────────────────────────────────

def _load_signals():
    if SIGNALS_PATH.exists():
        return pd.read_parquet(SIGNALS_PATH)
    return pd.DataFrame(columns=SIGNAL_COLS)


def _save_signals(df):
    LOGS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SIGNALS_PATH, index=False)
    try:
        df.to_json(SIGNALS_PATH.with_suffix(".json"), orient="records", indent=2)
    except Exception:
        pass


def _load_status():
    if STATUS_PATH.exists():
        with open(STATUS_PATH) as f:
            return json.load(f)
    return None


def _save_status(status):
    PIPELINE.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(status, f, indent=2)


def _load_lines():
    if LINES_PATH.exists():
        return pd.read_parquet(LINES_PATH)
    return pd.DataFrame(columns=LINES_COLS)


def _save_lines(df):
    LOGS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(LINES_PATH, index=False)


def _bootstrap():
    created = []
    if not SIGNALS_PATH.exists():
        _save_signals(pd.DataFrame(columns=SIGNAL_COLS))
        created.append("f5_runline_2026.parquet")
    if not STATUS_PATH.exists():
        _save_status({
            "status": "ACTIVE",
            "last_updated": date.today().isoformat(),
            "pause_reason": None,
            "pause_triggered_at_n": None,
            "pause_triggered_at_roi": None,
            "resume_authorized_by": None,
            "resume_date": None,
            "deployment_note": "Signal B live launch with conservative 0.5u stake",
        })
        created.append("f5_runline_status.json")
    if not LINES_PATH.exists():
        _save_lines(pd.DataFrame(columns=LINES_COLS))
        created.append("f5_runline_lines_2026.parquet")
    if created:
        logger.info(f"F5 run line: initialized {', '.join(created)}")


# ── Part 6: F5 Spread Collection ─────────────────────────────────────────────

def pull_f5_spreads(game_date_str, schedule=None):
    """Pull F5 run line (spreads_1st_5_innings) for today's games."""
    if schedule is None:
        return

    try:
        from modules.odds import ODDS_API_TEAM_MAP
        from config import ODDS_API_KEY, ODDS_API_BASE
    except ImportError:
        logger.warning("Cannot import odds config — skipping F5 spread pull")
        return

    df = _load_lines()
    now_utc = datetime.now(timezone.utc).isoformat()
    pulled = 0

    # Use standard odds endpoint for spreads (not event-level)
    url = f"{ODDS_API_BASE}/sports/baseball_mlb/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads_1st_5_innings",
        "oddsFormat": "american",
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            logger.warning(f"F5 spread fetch: HTTP {r.status_code}")
            return
        api_games = r.json()
    except Exception as e:
        logger.warning(f"F5 spread fetch failed: {e}")
        return

    ABB_MAP = {v: k for k, v in ODDS_API_TEAM_MAP.items()}  # full name → abb

    for game in schedule:
        gid = str(game.get("game_pk", ""))
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        # Find this game in API response
        home_full = next((k for k, v in ODDS_API_TEAM_MAP.items() if v == home), None)
        away_full = next((k for k, v in ODDS_API_TEAM_MAP.items() if v == away), None)

        matched_game = None
        for ag in api_games:
            if ag.get("home_team") == home_full and ag.get("away_team") == away_full:
                matched_game = ag
                break

        if not matched_game:
            continue

        # Extract valid -0.5/+0.5 spread
        best = None
        n_books = 0
        for bk in matched_game.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt["key"] != "spreads_1st_5_innings":
                    continue
                outcomes = mkt.get("outcomes", [])
                if len(outcomes) != 2:
                    continue
                o1, o2 = outcomes[0], outcomes[1]
                pts = {o1.get("point"), o2.get("point")}
                if pts != {0.5, -0.5}:
                    continue
                if o1.get("price") is None or o2.get("price") is None:
                    continue
                n_books += 1

                # Prefer FanDuel
                if best is None or bk["key"] == "fanduel":
                    # Map to home/away
                    if o1.get("name") == home_full:
                        h_line, h_price = o1["point"], o1["price"]
                        a_line, a_price = o2["point"], o2["price"]
                    elif o2.get("name") == home_full:
                        h_line, h_price = o2["point"], o2["price"]
                        a_line, a_price = o1["point"], o1["price"]
                    else:
                        continue
                    best = {
                        "home_line": h_line, "away_line": a_line,
                        "home_price": h_price, "away_price": a_price,
                        "book": bk["key"],
                    }

        if best is None:
            continue

        # Upsert
        mask = (df["game_id"].astype(str) == gid) & (df["date"] == game_date_str)
        row = {
            "date": game_date_str, "game_id": gid,
            "home_team": home, "away_team": away,
            "pull_timestamp": now_utc, "pull_type": "daily",
            "home_line": best["home_line"], "away_line": best["away_line"],
            "home_price": best["home_price"], "away_price": best["away_price"],
            "primary_book": best["book"], "books_count": n_books,
        }

        if mask.any():
            idx = df[mask].index[0]
            for k, v in row.items():
                df.at[idx, k] = v
        else:
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        pulled += 1

    _save_lines(df)
    if pulled:
        logger.info(f"F5 spreads: {pulled} games pulled for {game_date_str}")


# ── Step 1: Resolve ──────────────────────────────────────────────────────────

def resolve_signals(game_date_str):
    """Grade pending F5 run line signals."""
    sigs = _load_signals()
    pending = sigs[sigs["resolved"] == 0]
    if len(pending) == 0:
        return 0

    # Load F5 scores from MLB Stats API linescore
    resolved = 0
    for idx in pending.index:
        gid = str(sigs.at[idx, "game_id"])
        try:
            r = requests.get(f"https://statsapi.mlb.com/api/v1/game/{gid}/linescore", timeout=15)
            if r.status_code != 200:
                continue
            innings = r.json().get("innings", [])
            if len(innings) < 5:
                continue
            h5 = sum((inn.get("home", {}).get("runs", 0) or 0) for inn in innings[:5])
            a5 = sum((inn.get("away", {}).get("runs", 0) or 0) for inn in innings[:5])
        except Exception:
            continue

        margin = h5 - a5
        bet_line = sigs.at[idx, "bet_line"]
        stake = sigs.at[idx, "stake_units"]

        sigs.at[idx, "home_f5_score"] = h5
        sigs.at[idx, "away_f5_score"] = a5
        sigs.at[idx, "f5_margin"] = margin

        # Grade: home covers if margin > abs(bet_line) when bet_line is -0.5
        # bet_line for home is typically -0.5
        # WIN if margin > 0 (home leads), LOSS if margin < 0, PUSH if margin == 0
        if margin > 0:
            result = "WIN"
            net = stake * _price_to_win(sigs.at[idx, "bet_price"])
        elif margin < 0:
            result = "LOSS"
            net = -stake
        else:
            result = "PUSH"
            net = 0.0

        sigs.at[idx, "result"] = result
        sigs.at[idx, "net_units"] = net
        sigs.at[idx, "resolved"] = 1
        resolved += 1

    if resolved:
        _save_signals(sigs)
        logger.info(f"F5 run line: resolved {resolved} signals")
    return resolved


def _price_to_win(price):
    if pd.isna(price):
        return WIN_UNIT
    p = float(price)
    return 100 / abs(p) if p < 0 else p / 100


# ── Step 5: Generate ─────────────────────────────────────────────────────────

def generate_signals(game_date_str, schedule, pitcher_db):
    """Generate F5 run line signals for today."""
    from modules.pitchers import get_pitcher_metrics

    sigs = _load_signals()
    lines_df = _load_lines()
    new_signals = []
    display = []

    for game in schedule:
        gid = str(game.get("game_pk", ""))
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        # Duplicate check
        if len(sigs) > 0 and ((sigs["game_id"].astype(str) == gid) & (sigs["date"] == game_date_str)).any():
            continue

        # Get xFIP for both starters
        hsp_info = game.get("home_probable_pitcher", {})
        asp_info = game.get("away_probable_pitcher", {})
        hsp = get_pitcher_metrics(hsp_info, pitcher_db)
        asp = get_pitcher_metrics(asp_info, pitcher_db)

        if hsp is None or asp is None:
            continue
        h_xfip = hsp.get("xfip")
        a_xfip = asp.get("xfip")
        if h_xfip is None or a_xfip is None:
            continue

        xfip_gap = a_xfip - h_xfip
        if xfip_gap < XFIP_GAP_THRESHOLD:
            continue

        # Get F5 spread
        today_lines = lines_df[
            (lines_df["game_id"].astype(str) == gid) &
            (lines_df["date"] == game_date_str)
        ]
        if len(today_lines) == 0:
            continue

        line_row = today_lines.iloc[-1]  # latest pull
        h_line = line_row.get("home_line")
        a_line = line_row.get("away_line")
        h_price = line_row.get("home_price")
        a_price = line_row.get("away_price")

        if pd.isna(h_line) or pd.isna(h_price):
            continue
        if {h_line, a_line} != {0.5, -0.5}:
            continue

        sig = {
            "date": game_date_str,
            "game_id": gid,
            "home_team": home,
            "away_team": away,
            "home_sp_name": hsp_info.get("name", "TBD"),
            "away_sp_name": asp_info.get("name", "TBD"),
            "home_sp_xfip": round(h_xfip, 3),
            "away_sp_xfip": round(a_xfip, 3),
            "xfip_gap": round(xfip_gap, 3),
            "home_f5_line": h_line,
            "away_f5_line": a_line,
            "home_f5_price": h_price,
            "away_f5_price": a_price,
            "bet_side": "HOME",
            "bet_line": h_line,
            "bet_price": h_price,
            "stake_units": STAKE,
            "line_at_signal_time": h_line,
            "f5_line_closing": None,
            "f5_clv": None,
            "home_f5_score": None,
            "away_f5_score": None,
            "f5_margin": None,
            "result": None,
            "net_units": None,
            "resolved": 0,
        }
        new_signals.append(sig)
        display.append({
            **sig,
            "game_time_et": game.get("game_time_et", ""),
        })

        logger.info(f"  F5 RL: {away}@{home} HOME {h_line} @ {h_price} | "
                     f"gap={xfip_gap:.2f} ({hsp_info.get('name','?')} vs {asp_info.get('name','?')})")

    if new_signals:
        new_df = pd.DataFrame(new_signals, columns=SIGNAL_COLS)
        sigs = pd.concat([sigs, new_df], ignore_index=True)
        _save_signals(sigs)
        logger.info(f"F5 run line: {len(new_signals)} signals for {game_date_str}")

    return display


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_daily(game_date_str, schedule=None, pitcher_db=None):
    """Full daily F5 run line pipeline."""
    _bootstrap()

    # Step 1
    resolve_signals(game_date_str)

    # Step 2+3
    from mlb_sim.pipeline.f5_runline_tracker import compute_performance, check_hard_stop
    perf = compute_performance()
    if check_hard_stop(perf):
        logger.warning("F5 run line HARD STOP triggered")
        return []

    # Step 4
    status = _load_status()
    if status and status.get("status") == "PAUSED":
        logger.info(f"F5 run line PAUSED: {status.get('pause_reason')}")
        return []

    # Step 5
    if schedule is None or pitcher_db is None:
        return []

    # Pull F5 spreads first
    pull_f5_spreads(game_date_str, schedule)

    return generate_signals(game_date_str, schedule, pitcher_db)
