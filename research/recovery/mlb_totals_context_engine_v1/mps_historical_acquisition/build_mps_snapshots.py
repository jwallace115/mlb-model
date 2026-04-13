#!/usr/bin/env python3
"""
MPS Historical Snapshot Acquisition Script
MLB Totals Context Engine V1

BUILD ONLY — MPS REMAINS BLOCKED

Acquires open and close totals snapshots for 9,715 games (2022-2025)
from The Odds API historical endpoint.

Output: research/recovery/mlb_totals_context_engine_v1/mps_historical_acquisition/
"""

import os
import sys
import json
import time
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

print("BUILD ONLY — MPS REMAINS BLOCKED")
print("=" * 60)

# ── Config ──────────────────────────────────────────────────────
BASE_DIR = Path("/root/mlb-model")
OUT_DIR  = BASE_DIR / "research/recovery/mlb_totals_context_engine_v1/mps_historical_acquisition"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_FILE = OUT_DIR / "acquisition_checkpoint.json"
MANIFEST_FILE   = OUT_DIR / "mps_source_game_manifest_2022_2025.csv"
FINAL_PARQUET   = OUT_DIR / "mps_historical_snapshots_2022_2025.parquet"

CHECKPOINT_EVERY = 100
SLEEP_BETWEEN    = 0.4   # seconds between API calls

# ── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUT_DIR / "acquisition.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ── API Key ──────────────────────────────────────────────────────
def get_api_key():
    key = os.environ.get("ODDS_API_KEY")
    if key:
        return key
    try:
        with open(BASE_DIR / ".env") as f:
            for line in f:
                if "ODDS_API_KEY" in line:
                    return line.split("=", 1)[1].strip().strip("'\"")
    except Exception:
        pass
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", BASE_DIR / "config.py")
        cfg  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        return getattr(cfg, "ODDS_API_KEY", None)
    except Exception:
        pass
    return None

API_KEY = get_api_key()
if not API_KEY:
    log.error("No API key found — aborting")
    sys.exit(1)
log.info(f"API key loaded: {API_KEY[:8]}...")

# ── Team normalization map ────────────────────────────────────────
TEAM_NAME_MAP = {
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",
    "CHW": "Chicago White Sox",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Oakland Athletics",
    "ATH": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDP": "San Diego Padres",
    "SD":  "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SFG": "San Francisco Giants",
    "SF":  "San Francisco Giants",
    "STL": "St. Louis Cardinals",
    "TBR": "Tampa Bay Rays",
    "TB":  "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WSN": "Washington Nationals",
    "WSH": "Washington Nationals",
}

# ── STEP 1: Build game manifest ───────────────────────────────────
def classify_day_game(game_hour_utc, local_start_hour):
    """
    Day game = starts before ~5pm ET (17:00 ET = 21:00 UTC in EDT).
    UTC hours 14-21 cover 10am-5pm ET (EDT).
    UTC hours 0,1,2,22,23 are evening games (6pm-10pm ET).
    Tokyo series (UTC 10) counted as day games.
    Use local_start_hour < 17 as primary where available.
    """
    if pd.notna(local_start_hour):
        return float(local_start_hour) < 17
    h = int(game_hour_utc) if pd.notna(game_hour_utc) else -1
    return 10 <= h <= 21

def build_manifest():
    log.info("Building game manifest...")
    df = pd.read_parquet(BASE_DIR / "research/recovery/mlb_totals_context_engine_v1/context_engine_raw_table.parquet")
    log.info(f"Loaded context table: {len(df)} games, seasons {sorted(df['season'].unique().tolist())}")

    df["game_date"] = pd.to_datetime(df["date"]).dt.date.astype(str)

    # Build commence_time_utc from game_date + game_hour_utc
    # game_hour_utc is the UTC hour of game start on game_date
    # For hours 0,1,2 (next-day UTC), game_date is still the ET game date
    # We construct UTC datetime using game_date as date and game_hour_utc as hour
    def build_utc(row):
        try:
            hour = int(row["game_hour_utc"])
            dt   = datetime.strptime(row["game_date"], "%Y-%m-%d").replace(
                       hour=hour, minute=0, second=0, tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            return None

    df["commence_time_utc"] = df.apply(build_utc, axis=1)
    df["is_day_game"]       = df.apply(
        lambda r: classify_day_game(r["game_hour_utc"], r.get("local_start_hour")), axis=1
    )

    manifest = df[[
        "game_pk", "game_date", "home_team", "away_team",
        "season", "commence_time_utc", "is_day_game", "game_hour_utc"
    ]].copy()
    manifest.columns = [
        "game_id", "game_date", "home_team", "away_team",
        "season", "commence_time_utc", "is_day_game", "game_hour_utc"
    ]
    manifest = manifest.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    manifest.to_csv(MANIFEST_FILE, index=False)
    log.info(f"Manifest saved: {len(manifest)} games → {MANIFEST_FILE}")
    print(f"\nManifest summary:")
    print(f"  Total games: {len(manifest)}")
    print(f"  By season: {manifest.groupby('season').size().to_dict()}")
    print(f"  Day games: {manifest['is_day_game'].sum()} ({manifest['is_day_game'].mean()*100:.1f}%)")
    print(f"  Evening games: {(~manifest['is_day_game']).sum()} ({(~manifest['is_day_game']).mean()*100:.1f}%)")
    return manifest

# ── Probe timestamp computation ───────────────────────────────────
def compute_probes(row):
    """
    Returns (open_probe_utc_str, close_probe_utc_str, close_rule)

    OPEN:  game_date + 04:01:00 UTC  (= 00:01 ET in EDT)
    CLOSE:
      Day games  → commence_time_utc - 60 min
      Evening    → game_date + 22:00:00 UTC  (= 18:00 ET in EDT)
      If commence_time missing → 22:00 UTC, flag CLOSE_RULE_UNRESOLVED
    """
    game_date_str = row["game_date"]
    game_date     = datetime.strptime(game_date_str, "%Y-%m-%d")

    # Open probe: midnight ET open = 04:01 UTC
    open_probe     = game_date.replace(hour=4, minute=1, second=0, tzinfo=timezone.utc)
    open_probe_str = open_probe.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Close probe
    close_rule = "UNKNOWN"
    close_probe = None

    if pd.notna(row.get("commence_time_utc")) and row["commence_time_utc"]:
        try:
            ct = datetime.fromisoformat(str(row["commence_time_utc"]))
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=timezone.utc)
            if row["is_day_game"]:
                close_probe = ct - timedelta(minutes=60)
                close_rule  = "DAY_TMINUS60"
            else:
                close_probe = game_date.replace(hour=22, minute=0, second=0, tzinfo=timezone.utc)
                close_rule  = "EVENING_1800ET"
        except Exception:
            close_probe = game_date.replace(hour=22, minute=0, second=0, tzinfo=timezone.utc)
            close_rule  = "CLOSE_RULE_UNRESOLVED"
    else:
        close_probe = game_date.replace(hour=22, minute=0, second=0, tzinfo=timezone.utc)
        close_rule  = "CLOSE_RULE_UNRESOLVED"

    close_probe_str = close_probe.strftime("%Y-%m-%dT%H:%M:%SZ")
    return open_probe_str, close_probe_str, close_rule

# ── API call ──────────────────────────────────────────────────────
API_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds"
TARGET_BOOKS = {"fanduel", "draftkings"}

def fetch_snapshot(probe_utc: str) -> dict:
    """
    Fetch one historical snapshot.
    Returns dict with: raw_events, snapshot_timestamp, credits_remaining, error, status_code
    """
    params = {
        "apiKey":     API_KEY,
        "regions":    "us",
        "markets":    "totals",
        "oddsFormat": "american",
        "date":       probe_utc,
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        credits_remaining = resp.headers.get("x-requests-remaining", None)

        if resp.status_code == 429:
            return {
                "raw_events": None, "credits_remaining": credits_remaining,
                "error": "RATE_LIMITED_429", "status_code": 429
            }
        if resp.status_code != 200:
            return {
                "raw_events": None, "credits_remaining": credits_remaining,
                "error": f"HTTP_{resp.status_code}", "status_code": resp.status_code
            }

        data = resp.json()
        # Historical endpoint: {"timestamp":..., "previous_timestamp":..., "next_timestamp":..., "data":[...]}
        if isinstance(data, dict) and "data" in data:
            events      = data["data"]
            snapshot_ts = data.get("timestamp", probe_utc)
        elif isinstance(data, list):
            events      = data
            snapshot_ts = probe_utc
        else:
            return {
                "raw_events": None, "credits_remaining": credits_remaining,
                "error": "MALFORMED_RESPONSE", "status_code": resp.status_code
            }

        return {
            "raw_events":         events,
            "snapshot_timestamp": snapshot_ts,
            "credits_remaining":  credits_remaining,
            "error":              None,
            "status_code":        resp.status_code,
        }
    except requests.exceptions.Timeout:
        return {"raw_events": None, "credits_remaining": None, "error": "TIMEOUT", "status_code": None}
    except Exception as e:
        return {"raw_events": None, "credits_remaining": None, "error": str(e), "status_code": None}

# ── Event matching ────────────────────────────────────────────────
def match_event(events, home_abbr, away_abbr):
    """
    Match an event from API response using both home and away team names.
    Returns matched event dict or None.
    """
    if not events:
        return None
    home_name = TEAM_NAME_MAP.get(home_abbr, "").lower()
    away_name = TEAM_NAME_MAP.get(away_abbr, "").lower()
    if not home_name or not away_name:
        return None
    for ev in events:
        ev_home = ev.get("home_team", "").lower()
        ev_away = ev.get("away_team", "").lower()
        if ev_home == home_name and ev_away == away_name:
            return ev
    return None

# ── Extract totals data ───────────────────────────────────────────
def extract_totals(event, snapshot_ts, probe_utc):
    """
    From a matched event, extract FanDuel and DraftKings totals.
    """
    result = {
        "fanduel_available":      False,
        "fanduel_line":           None,
        "fanduel_over_price":     None,
        "fanduel_under_price":    None,
        "draftkings_available":   False,
        "draftkings_line":        None,
        "draftkings_over_price":  None,
        "draftkings_under_price": None,
        "snapshot_timestamp":     snapshot_ts,
    }
    if not event:
        return result

    for bk in event.get("bookmakers", []):
        bk_key = bk.get("key", "").lower()
        if bk_key not in TARGET_BOOKS:
            continue
        for mkt in bk.get("markets", []):
            if mkt.get("key") != "totals":
                continue
            outcomes    = mkt.get("outcomes", [])
            line        = None
            over_price  = None
            under_price = None
            for oc in outcomes:
                name  = oc.get("name", "").lower()
                point = oc.get("point")
                price = oc.get("price")
                if point is not None:
                    line = point
                if name == "over":
                    over_price = price
                elif name == "under":
                    under_price = price
            if bk_key == "fanduel":
                result["fanduel_available"]   = True
                result["fanduel_line"]        = line
                result["fanduel_over_price"]  = over_price
                result["fanduel_under_price"] = under_price
            elif bk_key == "draftkings":
                result["draftkings_available"]   = True
                result["draftkings_line"]        = line
                result["draftkings_over_price"]  = over_price
                result["draftkings_under_price"] = under_price

    return result

# ── Book selection ────────────────────────────────────────────────
def select_book(totals_data, prefix):
    """
    FanDuel primary, DraftKings fallback.
    prefix = "open" or "close"
    """
    fd_avail = totals_data["fanduel_available"]
    dk_avail = totals_data["draftkings_available"]

    def quality_flag(avail, line, over, under):
        if not avail:
            return "MISSING"
        if line is None or over is None or under is None:
            return "INCOMPLETE"
        return "OK"

    if fd_avail and totals_data["fanduel_line"] is not None:
        sb    = "fanduel"
        sl    = totals_data["fanduel_line"]
        so    = totals_data["fanduel_over_price"]
        su    = totals_data["fanduel_under_price"]
        fb    = False
        q     = quality_flag(fd_avail, sl, so, su)
    elif dk_avail and totals_data["draftkings_line"] is not None:
        sb    = "draftkings"
        sl    = totals_data["draftkings_line"]
        so    = totals_data["draftkings_over_price"]
        su    = totals_data["draftkings_under_price"]
        fb    = True
        q     = quality_flag(dk_avail, sl, so, su)
    else:
        sb, sl, so, su, fb = None, None, None, None, False
        q = "MISSING"

    snap_ts = totals_data.get("snapshot_timestamp")

    return {
        f"{prefix}_selected_book":               sb,
        f"{prefix}_selected_line":               sl,
        f"{prefix}_selected_over_price":         so,
        f"{prefix}_selected_under_price":        su,
        f"{prefix}_selected_snapshot_timestamp": snap_ts,
        f"{prefix}_fallback_used":               fb,
        f"{prefix}_selected_quality_flag":       q,
        f"{prefix}_fanduel_available":           fd_avail,
        f"{prefix}_fanduel_line":                totals_data["fanduel_line"],
        f"{prefix}_fanduel_over_price":          totals_data["fanduel_over_price"],
        f"{prefix}_fanduel_under_price":         totals_data["fanduel_under_price"],
        f"{prefix}_draftkings_available":        dk_avail,
        f"{prefix}_draftkings_line":             totals_data["draftkings_line"],
        f"{prefix}_draftkings_over_price":       totals_data["draftkings_over_price"],
        f"{prefix}_draftkings_under_price":      totals_data["draftkings_under_price"],
    }

def compute_ts_delta(probe_utc_str, snapshot_ts_str):
    """Compute |probe - snapshot| in minutes."""
    try:
        if not probe_utc_str or not snapshot_ts_str:
            return None
        probe    = datetime.strptime(probe_utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        snap_str = str(snapshot_ts_str).replace("Z", "+00:00")
        snap     = datetime.fromisoformat(snap_str)
        if snap.tzinfo is None:
            snap = snap.replace(tzinfo=timezone.utc)
        delta = abs((snap - probe).total_seconds() / 60)
        return round(delta, 1)
    except Exception:
        return None

# ── Checkpoint management ─────────────────────────────────────────
def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            cp = json.load(f)
        completed = set(cp.get("completed_game_ids", []))
        log.info(f"Checkpoint loaded: {len(completed)} games completed")
        return cp, completed
    return {"completed_game_ids": [], "results": [], "credits_log": [], "error_log": []}, set()

def save_checkpoint(cp, completed_ids, results, credits_log, error_log):
    cp["completed_game_ids"] = list(completed_ids)
    cp["results"]            = results
    cp["credits_log"]        = credits_log
    cp["error_log"]          = error_log
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(cp, f)

# ── Main acquisition loop ─────────────────────────────────────────
def run_acquisition(manifest):
    cp, completed_ids = load_checkpoint()
    results     = cp.get("results", [])
    credits_log = cp.get("credits_log", [])
    error_log   = cp.get("error_log", [])

    remaining = manifest[~manifest["game_id"].isin(completed_ids)].copy()
    log.info(f"Games remaining: {len(remaining)} / {len(manifest)}")

    if len(remaining) == 0:
        log.info("All games already completed — skipping acquisition loop")
        last_credits = credits_log[-1]["credits"] if credits_log else None
        return results, last_credits

    calls_made   = 0
    last_credits = None
    loop_start   = time.time()

    for idx, (_, row) in enumerate(remaining.iterrows()):
        game_id   = int(row["game_id"])
        game_date = str(row["game_date"])
        home_team = str(row["home_team"])
        away_team = str(row["away_team"])
        season    = int(row["season"])

        open_probe, close_probe, close_rule = compute_probes(row)

        # ── Open snapshot ────────────────────────────────────────
        time.sleep(SLEEP_BETWEEN)
        open_resp  = fetch_snapshot(open_probe)
        calls_made += 1

        if open_resp.get("error") == "RATE_LIMITED_429":
            log.error("HARD STOP: 429 Rate Limited on OPEN call — saving checkpoint")
            save_checkpoint(cp, completed_ids, results, credits_log, error_log)
            sys.exit(2)

        if open_resp.get("credits_remaining"):
            last_credits = open_resp["credits_remaining"]
            credits_log.append({"ts": datetime.utcnow().isoformat(),
                                 "credits": last_credits, "call": "open",
                                 "game_id": game_id})

        if open_resp.get("error"):
            error_log.append({"game_id": game_id, "probe": "open",
                               "probe_ts": open_probe, "error": open_resp["error"]})
            log.warning(f"  Game {game_id} [{game_date}] OPEN error: {open_resp['error']}")

        open_event    = match_event(open_resp.get("raw_events"), home_team, away_team)
        open_totals   = extract_totals(open_event, open_resp.get("snapshot_timestamp", open_probe), open_probe)
        open_sel      = select_book(open_totals, "open")
        open_ts_delta = compute_ts_delta(open_probe, open_totals.get("snapshot_timestamp"))
        open_sel["open_selected_timestamp_delta_min"] = open_ts_delta
        open_sel["open_api_error"]                    = open_resp.get("error")

        # ── Close snapshot ───────────────────────────────────────
        time.sleep(SLEEP_BETWEEN)
        close_resp  = fetch_snapshot(close_probe)
        calls_made += 1

        if close_resp.get("error") == "RATE_LIMITED_429":
            log.error("HARD STOP: 429 Rate Limited on CLOSE call — saving checkpoint")
            save_checkpoint(cp, completed_ids, results, credits_log, error_log)
            sys.exit(2)

        if close_resp.get("credits_remaining"):
            last_credits = close_resp["credits_remaining"]
            credits_log.append({"ts": datetime.utcnow().isoformat(),
                                 "credits": last_credits, "call": "close",
                                 "game_id": game_id})

        if close_resp.get("error"):
            error_log.append({"game_id": game_id, "probe": "close",
                               "probe_ts": close_probe, "error": close_resp["error"]})
            log.warning(f"  Game {game_id} [{game_date}] CLOSE error: {close_resp['error']}")

        close_event    = match_event(close_resp.get("raw_events"), home_team, away_team)
        close_totals   = extract_totals(close_event, close_resp.get("snapshot_timestamp", close_probe), close_probe)
        close_sel      = select_book(close_totals, "close")
        close_ts_delta = compute_ts_delta(close_probe, close_totals.get("snapshot_timestamp"))
        close_sel["close_selected_timestamp_delta_min"] = close_ts_delta
        close_sel["close_rule_used"]                    = close_rule
        close_sel["close_api_error"]                    = close_resp.get("error")

        # ── Pair quality ─────────────────────────────────────────
        ob = open_sel.get("open_selected_book")
        cb = close_sel.get("close_selected_book")
        oq = open_sel.get("open_selected_quality_flag")
        cq = close_sel.get("close_selected_quality_flag")

        if ob and cb and oq == "OK" and cq == "OK":
            same_book = (ob == cb)
            pair_book = ob if same_book else f"{ob}|{cb}"
            pair_flag = f"SAME_{ob.upper()}" if same_book else "CROSS_BOOK"
        elif ob or cb:
            same_book = False
            pair_book = ob or cb
            pair_flag = "INCOMPLETE"
        else:
            same_book = False
            pair_book = None
            pair_flag = "BOTH_MISSING"

        # ── Assemble record ──────────────────────────────────────
        record = {
            "game_id":             game_id,
            "season":              season,
            "game_date":           game_date,
            "home_team":           home_team,
            "away_team":           away_team,
            "commence_time_utc":   str(row["commence_time_utc"]) if pd.notna(row.get("commence_time_utc")) else None,
            "is_day_game":         bool(row["is_day_game"]),
            "requested_open_probe_utc":  open_probe,
            "requested_close_probe_utc": close_probe,
            "same_book_pair":      same_book,
            "pair_book":           pair_book,
            "pair_quality_flag":   pair_flag,
            **open_sel,
            **close_sel,
        }
        results.append(record)
        completed_ids.add(game_id)

        # Progress log every 25 games
        n_done = idx + 1
        if n_done % 25 == 0 or n_done == len(remaining):
            elapsed = time.time() - loop_start
            rate    = calls_made / elapsed if elapsed > 0 else 0
            eta_s   = (len(remaining) - n_done) * 2 / rate if rate > 0 else 0
            log.info(
                f"  Progress: {n_done}/{len(remaining)} games | "
                f"calls={calls_made} | credits_remaining={last_credits} | "
                f"rate={rate:.2f} calls/s | ETA={eta_s/60:.0f}min"
            )

        # Checkpoint every N games
        if n_done % CHECKPOINT_EVERY == 0:
            save_checkpoint(cp, completed_ids, results, credits_log, error_log)
            log.info(f"  Checkpoint saved at {n_done} games")

    # Final checkpoint
    save_checkpoint(cp, completed_ids, results, credits_log, error_log)
    log.info(f"Acquisition complete: {len(results)} game records, {calls_made} API calls total")
    return results, last_credits

# ── STEP 4: Build final parquet ────────────────────────────────────
COLUMN_ORDER = [
    # Identity
    "game_id", "season", "game_date", "home_team", "away_team", "commence_time_utc",
    # Open
    "requested_open_probe_utc",
    "open_selected_book", "open_selected_line",
    "open_selected_over_price", "open_selected_under_price",
    "open_selected_snapshot_timestamp", "open_selected_timestamp_delta_min",
    "open_fallback_used", "open_selected_quality_flag",
    "open_fanduel_available", "open_fanduel_line",
    "open_fanduel_over_price", "open_fanduel_under_price",
    "open_draftkings_available", "open_draftkings_line",
    "open_draftkings_over_price", "open_draftkings_under_price",
    # Close
    "requested_close_probe_utc", "close_rule_used",
    "close_selected_book", "close_selected_line",
    "close_selected_over_price", "close_selected_under_price",
    "close_selected_snapshot_timestamp", "close_selected_timestamp_delta_min",
    "close_fallback_used", "close_selected_quality_flag",
    "close_fanduel_available", "close_fanduel_line",
    "close_fanduel_over_price", "close_fanduel_under_price",
    "close_draftkings_available", "close_draftkings_line",
    "close_draftkings_over_price", "close_draftkings_under_price",
    # Pair
    "same_book_pair", "pair_book", "pair_quality_flag",
]

def build_final_table(results):
    log.info("Building final parquet table...")
    df = pd.DataFrame(results)
    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMN_ORDER]
    df.to_parquet(FINAL_PARQUET, index=False)
    log.info(f"Final table saved: {len(df)} rows → {FINAL_PARQUET}")
    return df

# ── STEP 5: QA & Coverage summary ────────────────────────────────
def print_qa(df, last_credits):
    print("\n" + "=" * 60)
    print("QA & COVERAGE SUMMARY")
    print("=" * 60)
    total_n = len(df)

    print(f"\nBy Season:")
    print(f"{'Season':<8} {'N':>6} {'Open OK':>9} {'Close OK':>9} {'Both OK':>9} {'Both%':>7}")
    for season in sorted(df["season"].unique()):
        s = df[df["season"] == season]
        n = len(s)
        o = (s["open_selected_quality_flag"]  == "OK").sum()
        c = (s["close_selected_quality_flag"] == "OK").sum()
        b = ((s["open_selected_quality_flag"] == "OK") &
             (s["close_selected_quality_flag"] == "OK")).sum()
        print(f"{season:<8} {n:>6} {o:>9} {c:>9} {b:>9} {b/n*100:>6.0f}%")
    total_o = (df["open_selected_quality_flag"]  == "OK").sum()
    total_c = (df["close_selected_quality_flag"] == "OK").sum()
    total_b = ((df["open_selected_quality_flag"] == "OK") &
               (df["close_selected_quality_flag"] == "OK")).sum()
    print(f"{'TOTAL':<8} {total_n:>6} {total_o:>9} {total_c:>9} {total_b:>9} {total_b/total_n*100:>6.0f}%")

    print("\nBook Selection:")
    for probe in ["open", "close"]:
        col   = f"{probe}_selected_book"
        books = df[col].value_counts(dropna=False)
        print(f"  {probe.upper()}:")
        for b, c in books.items():
            print(f"    {b}: {c} ({c/total_n*100:.1f}%)")

    print("\nPair Quality:")
    pair_q = df["pair_quality_flag"].value_counts(dropna=False)
    for q, c in pair_q.items():
        print(f"  {q}: {c} ({c/total_n*100:.1f}%)")

    print("\nTimestamp Quality:")
    for prefix in ["open", "close"]:
        col  = f"{prefix}_selected_timestamp_delta_min"
        vals = df[col].dropna()
        if len(vals) > 0:
            print(f"  {prefix.upper()} delta — "
                  f"median: {vals.median():.0f}min | "
                  f"P90: {vals.quantile(0.9):.0f}min | "
                  f"max: {vals.max():.0f}min")
        else:
            print(f"  {prefix.upper()} delta — no data")

    print(f"\nAPI credits remaining: {last_credits}")
    return total_n, total_o, total_c, total_b

# ── STEP 6: Reports ───────────────────────────────────────────────
def write_reports(df, last_credits, total_n, total_o, total_c, total_b):
    season_stats = {}
    for season in sorted(df["season"].unique()):
        s  = df[df["season"] == season]
        n  = int(len(s))
        o  = int((s["open_selected_quality_flag"] == "OK").sum())
        c  = int((s["close_selected_quality_flag"] == "OK").sum())
        b  = int(((s["open_selected_quality_flag"] == "OK") &
                  (s["close_selected_quality_flag"] == "OK")).sum())
        season_stats[str(season)] = {"n": n, "open_ok": o, "close_ok": c, "both_ok": b}

    pair_q    = df["pair_quality_flag"].value_counts(dropna=False).to_dict()
    open_bks  = df["open_selected_book"].value_counts(dropna=False).to_dict()
    close_bks = df["close_selected_book"].value_counts(dropna=False).to_dict()

    open_d_vals  = df["open_selected_timestamp_delta_min"].dropna()
    close_d_vals = df["close_selected_timestamp_delta_min"].dropna()
    open_delta   = {
        "median": round(float(open_d_vals.median()), 1)      if len(open_d_vals) else None,
        "p90":    round(float(open_d_vals.quantile(0.9)), 1) if len(open_d_vals) else None,
    }
    close_delta  = {
        "median": round(float(close_d_vals.median()), 1)      if len(close_d_vals) else None,
        "p90":    round(float(close_d_vals.quantile(0.9)), 1) if len(close_d_vals) else None,
    }

    if total_b >= total_n * 0.80:
        verdict = "SNAPSHOT SUBSTRATE BUILT CLEANLY"
    elif total_b >= total_n * 0.60:
        verdict = "SNAPSHOT SUBSTRATE BUILT WITH GAPS"
    else:
        verdict = "SNAPSHOT SUBSTRATE INCOMPLETE"

    # JSON summary
    raw_json = {
        "build_type":      "MPS_HISTORICAL_ACQUISITION",
        "mps_status":      "RESERVED — MPS REMAINS BLOCKED — DATA ONLY",
        "generated_at":    datetime.utcnow().isoformat(),
        "source_universe": {"total_games": int(total_n), "seasons": season_stats},
        "acquisition":     {
            "open_usable":              int(total_o),
            "close_usable":             int(total_c),
            "both_usable":              int(total_b),
            "both_pct":                 round(total_b / total_n * 100, 1),
            "credits_remaining_final":  str(last_credits) if last_credits else "unknown",
        },
        "book_selection":  {
            "open":  {str(k): int(v) for k, v in open_bks.items()},
            "close": {str(k): int(v) for k, v in close_bks.items()},
        },
        "pair_quality":    {str(k): int(v) for k, v in pair_q.items()},
        "timestamp_quality": {"open": open_delta, "close": close_delta},
        "verdict":         verdict,
        "output_files":    {
            "manifest":      str(MANIFEST_FILE),
            "final_parquet": str(FINAL_PARQUET),
            "build_report":  str(OUT_DIR / "MPS_HISTORICAL_ACQUISITION_BUILD.md"),
            "raw_json":      str(OUT_DIR / "MPS_HISTORICAL_ACQUISITION_RAW.json"),
        },
    }
    with open(OUT_DIR / "MPS_HISTORICAL_ACQUISITION_RAW.json", "w") as f:
        json.dump(raw_json, f, indent=2)

    # Markdown
    o_fd = int(open_bks.get("fanduel",   open_bks.get(None, 0)) or 0)
    o_dk = int(open_bks.get("draftkings", 0) or 0)
    o_na = int(open_bks.get(None, open_bks.get("None", 0)) or 0)
    c_fd = int(close_bks.get("fanduel",   0) or 0)
    c_dk = int(close_bks.get("draftkings", 0) or 0)
    c_na = int(close_bks.get(None, close_bks.get("None", 0)) or 0)

    lines = [
        "# MPS Historical Snapshot Acquisition Build",
        "",
        "> **BUILD ONLY — MPS REMAINS BLOCKED**",
        f"> Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## 1. Build Scope",
        "Historical open/close totals snapshot acquisition for MLB Totals Context Engine V1.",
        "This is a **data acquisition build only**. MPS is NOT activated, NOT computed,",
        "and NOT in any path state.",
        "",
        "## 2. Source Game Universe",
        f"- Source: `context_engine_raw_table.parquet`",
        f"- Total games: **{total_n}**",
        f"- Seasons: 2022–2025",
        "",
        "| Season | N Games |",
        "|--------|---------|",
    ]
    for s, st in season_stats.items():
        lines.append(f"| {s} | {st['n']} |")

    lines += [
        "",
        "## 3. Frozen Protocol",
        "| Parameter | Rule |",
        "|-----------|------|",
        "| OPEN probe | `game_date 04:01:00 UTC` (= 00:01 ET) |",
        "| CLOSE probe — day games (start < 17:00 local / UTC 14-21) | `commence_time_utc − 60 minutes` |",
        "| CLOSE probe — evening games | `game_date 22:00:00 UTC` (= 18:00 ET) |",
        "| CLOSE fallback | `game_date 22:00:00 UTC`, flagged `CLOSE_RULE_UNRESOLVED` |",
        "| Book selection | FanDuel primary, DraftKings fallback |",
        "| Sleep between calls | 0.4 seconds |",
        "| Checkpoint | Every 100 games |",
        "",
        "## 4. Acquisition Results",
        "",
        "| Season | N | Open OK | Close OK | Both OK | Both% |",
        "|--------|---|---------|----------|---------|-------|",
    ]
    for s, st in season_stats.items():
        n = st["n"]
        lines.append(
            f"| {s} | {n} | {st['open_ok']} ({st['open_ok']/n*100:.0f}%) | "
            f"{st['close_ok']} ({st['close_ok']/n*100:.0f}%) | "
            f"{st['both_ok']} ({st['both_ok']/n*100:.0f}%) | "
            f"{st['both_ok']/n*100:.0f}% |"
        )
    lines.append(
        f"| **TOTAL** | **{total_n}** | **{total_o}** ({total_o/total_n*100:.0f}%) | "
        f"**{total_c}** ({total_c/total_n*100:.0f}%) | **{total_b}** ({total_b/total_n*100:.0f}%) | "
        f"**{total_b/total_n*100:.0f}%** |"
    )

    lines += [
        "",
        "## 5. Failure / Missingness Analysis",
        "",
        "**Open probe quality flags:**",
    ]
    for flag, cnt in df["open_selected_quality_flag"].value_counts(dropna=False).items():
        lines.append(f"- {flag}: {cnt} ({cnt/total_n*100:.1f}%)")
    lines += ["", "**Close probe quality flags:**"]
    for flag, cnt in df["close_selected_quality_flag"].value_counts(dropna=False).items():
        lines.append(f"- {flag}: {cnt} ({cnt/total_n*100:.1f}%)")

    lines += [
        "",
        "## 6. Final Table Spec",
        f"- File: `mps_historical_snapshots_2022_2025.parquet`",
        f"- Rows: {total_n}",
        "- Column groups: IDENTITY (6), OPEN (18), CLOSE (19), PAIR (3)",
        "",
        "## 7. Book Selection",
        "",
        "| Probe | FanDuel | DraftKings | Missing |",
        "|-------|---------|------------|---------|",
        f"| Open  | {o_fd} ({o_fd/total_n*100:.0f}%) | {o_dk} ({o_dk/total_n*100:.0f}%) | {o_na} ({o_na/total_n*100:.0f}%) |",
        f"| Close | {c_fd} ({c_fd/total_n*100:.0f}%) | {c_dk} ({c_dk/total_n*100:.0f}%) | {c_na} ({c_na/total_n*100:.0f}%) |",
        "",
        "## 8. Pair Quality",
        "",
        "| Pair Flag | Count | % |",
        "|-----------|-------|---|",
    ]
    for q, cnt in sorted(pair_q.items(), key=lambda x: -x[1]):
        lines.append(f"| {q} | {cnt} | {cnt/total_n*100:.1f}% |")

    lines += [
        "",
        "## 9. Timestamp Quality",
        f"- OPEN  — median: {open_delta['median']} min | P90: {open_delta['p90']} min",
        f"- CLOSE — median: {close_delta['median']} min | P90: {close_delta['p90']} min",
        "",
        f"## 10. Readiness: {verdict}",
        "",
        "## 11. MPS Status",
        "",
        "> **MPS remains RESERVED / DATA-BLOCKED.**",
        "> The snapshot substrate has been acquired. MPS computation, path states,",
        "> and activation are NOT part of this build and remain blocked pending",
        "> explicit future authorization.",
    ]

    with open(OUT_DIR / "MPS_HISTORICAL_ACQUISITION_BUILD.md", "w") as f:
        f.write("\n".join(lines))
    log.info("Reports written")
    return raw_json

# ── Main ─────────────────────────────────────────────────────────
def main():
    print("BUILD ONLY — MPS REMAINS BLOCKED")

    # Step 1: Manifest
    if MANIFEST_FILE.exists():
        log.info(f"Loading existing manifest: {MANIFEST_FILE}")
        manifest = pd.read_csv(MANIFEST_FILE)
        log.info(f"Manifest: {len(manifest)} games")
    else:
        manifest = build_manifest()

    log.info(f"Game universe: {len(manifest)} games, seasons {sorted(manifest['season'].unique().tolist())}")

    # Step 3: Acquisition
    results, last_credits = run_acquisition(manifest)

    # Step 4: Final table
    df = build_final_table(results)

    # Step 5: QA
    total_n, total_o, total_c, total_b = print_qa(df, last_credits)

    # Step 6: Reports
    raw_json = write_reports(df, last_credits, total_n, total_o, total_c, total_b)

    # Final summary
    open_bks  = df["open_selected_book"].value_counts(dropna=False).to_dict()
    close_bks = df["close_selected_book"].value_counts(dropna=False).to_dict()
    pair_q    = df["pair_quality_flag"].value_counts(dropna=False).to_dict()
    open_d    = df["open_selected_timestamp_delta_min"].dropna()
    close_d   = df["close_selected_timestamp_delta_min"].dropna()

    print("\n" + "=" * 60)
    print("BUILD ONLY — MPS REMAINS BLOCKED")
    print("=" * 60)
    print(f"1. Source universe: 2022–2025, {total_n} games")
    print(f"2. API acquisition: open_usable={total_o} ({total_o/total_n*100:.0f}%), "
          f"close_usable={total_c} ({total_c/total_n*100:.0f}%), "
          f"both_usable={total_b} ({total_b/total_n*100:.0f}%)")
    print(f"   Credits remaining: {last_credits}")
    print(f"3. Book selection (open):  FD={open_bks.get('fanduel',0)} "
          f"DK={open_bks.get('draftkings',0)}")
    print(f"   Book selection (close): FD={close_bks.get('fanduel',0)} "
          f"DK={close_bks.get('draftkings',0)}")
    print(f"4. Pair quality: {dict(pair_q)}")
    if len(open_d):
        print(f"5. Timestamp quality — OPEN  median={open_d.median():.0f}min P90={open_d.quantile(0.9):.0f}min")
    if len(close_d):
        print(f"   Timestamp quality — CLOSE median={close_d.median():.0f}min P90={close_d.quantile(0.9):.0f}min")
    print(f"6. Build verdict: {raw_json['verdict']}")
    print(f"7. Files written:")
    for k, v in raw_json["output_files"].items():
        print(f"   {k}: {v}")
    print(f"8. MPS STATUS: RESERVED / DATA-BLOCKED — no change")

if __name__ == "__main__":
    main()
