#!/usr/bin/env python3
"""
MLB INTRADAY DECISION PANEL V1 — build_intraday_panel.py
BUILD ONLY — no signal testing, no modeling, no activation.

Acquires 3 new intraday time probes (07:00 ET, 10:00 ET, 12:00 ET)
for all 9,715 games 2022-2025, then merges with existing OPEN and
FINAL CLOSE from the MPS substrate to build a 5-state panel.

MPS remains RESERVED / DATA-BLOCKED.
"""

import os
import sys
import json
import time
import logging
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Paths ─────────────────────────────────────────────────────────
BASE_DIR      = Path("/root/mlb-model")
MPS_PARQUET   = BASE_DIR / "research/recovery/mlb_totals_context_engine_v1/mps_historical_acquisition/mps_historical_snapshots_2022_2025.parquet"
OUT_DIR       = BASE_DIR / "research/recovery/mlb_totals_context_engine_v1/intraday_decision_panel_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_FILE = OUT_DIR / "intraday_checkpoint.json"
RAW_RECORDS_FILE = OUT_DIR / "intraday_raw_records.parquet"
LOG_FILE        = OUT_DIR / "intraday_acquisition.log"

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

log.info("=" * 60)
log.info("BUILD ONLY — INTRADAY DECISION PANEL V1")
log.info("=" * 60)

# ── API setup ─────────────────────────────────────────────────────
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

API_URL     = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds"
TARGET_BOOKS = {"fanduel", "draftkings"}
SLEEP_SEC   = 0.35
CHECKPOINT_EVERY = 100

# ── Probe definitions (ET → UTC offset, EDT = UTC-4) ─────────────
# 07:00 ET = 11:00 UTC,  10:00 ET = 14:00 UTC,  12:00 ET = 16:00 UTC
PROBES = [
    ("DT_0700", 11),   # 07:00 ET = 11:00 UTC
    ("DT_1000", 14),   # 10:00 ET = 14:00 UTC
    ("DT_1200", 16),   # 12:00 ET = 16:00 UTC
]

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

# ── API fetch ─────────────────────────────────────────────────────
def fetch_snapshot(probe_utc: str) -> dict:
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
            return {"raw_events": None, "snapshot_timestamp": None,
                    "credits_remaining": credits_remaining,
                    "error": "RATE_LIMITED_429", "status_code": 429}
        if resp.status_code != 200:
            return {"raw_events": None, "snapshot_timestamp": None,
                    "credits_remaining": credits_remaining,
                    "error": f"HTTP_{resp.status_code}", "status_code": resp.status_code}

        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            events      = data["data"]
            snapshot_ts = data.get("timestamp", probe_utc)
        elif isinstance(data, list):
            events      = data
            snapshot_ts = probe_utc
        else:
            return {"raw_events": None, "snapshot_timestamp": None,
                    "credits_remaining": credits_remaining,
                    "error": "MALFORMED_RESPONSE", "status_code": resp.status_code}

        return {"raw_events": events, "snapshot_timestamp": snapshot_ts,
                "credits_remaining": credits_remaining,
                "error": None, "status_code": resp.status_code}
    except requests.exceptions.Timeout:
        return {"raw_events": None, "snapshot_timestamp": None,
                "credits_remaining": None, "error": "TIMEOUT", "status_code": None}
    except Exception as e:
        return {"raw_events": None, "snapshot_timestamp": None,
                "credits_remaining": None, "error": str(e), "status_code": None}

# ── Event matching ────────────────────────────────────────────────
def match_event(events, home_abbr, away_abbr):
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

# ── Extract totals ────────────────────────────────────────────────
def extract_totals(event, snapshot_ts):
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

# ── Select book (FD primary, DK fallback) ─────────────────────────
def select_book(totals_data, probe_utc_str, probe_label):
    def quality_flag(avail, line, over, under):
        if not avail:
            return "MISSING"
        if line is None or over is None or under is None:
            return "INCOMPLETE"
        return "OK"

    fd_avail = totals_data["fanduel_available"]
    dk_avail = totals_data["draftkings_available"]

    if fd_avail and totals_data["fanduel_line"] is not None:
        sb = "fanduel"; sl = totals_data["fanduel_line"]
        so = totals_data["fanduel_over_price"]; su = totals_data["fanduel_under_price"]
        fb = False
        q  = quality_flag(fd_avail, sl, so, su)
    elif dk_avail and totals_data["draftkings_line"] is not None:
        sb = "draftkings"; sl = totals_data["draftkings_line"]
        so = totals_data["draftkings_over_price"]; su = totals_data["draftkings_under_price"]
        fb = True
        q  = quality_flag(dk_avail, sl, so, su)
    else:
        sb, sl, so, su, fb = None, None, None, None, False
        q = "MISSING"

    snap_ts = totals_data.get("snapshot_timestamp")

    # Compute timestamp delta
    delta_min = None
    try:
        if probe_utc_str and snap_ts:
            probe_dt = datetime.strptime(probe_utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            snap_str = str(snap_ts).replace("Z", "+00:00")
            snap_dt  = datetime.fromisoformat(snap_str)
            if snap_dt.tzinfo is None:
                snap_dt = snap_dt.replace(tzinfo=timezone.utc)
            delta_min = round(abs((snap_dt - probe_dt).total_seconds() / 60), 1)
    except Exception:
        pass

    pfx = probe_label.lower()
    return {
        f"{pfx}_selected_book":               sb,
        f"{pfx}_selected_line":               sl,
        f"{pfx}_selected_over_price":         so,
        f"{pfx}_selected_under_price":        su,
        f"{pfx}_selected_snapshot_timestamp": snap_ts,
        f"{pfx}_selected_timestamp_delta_min": delta_min,
        f"{pfx}_fallback_used":               fb,
        f"{pfx}_selected_quality_flag":       q,
        f"{pfx}_fanduel_available":           fd_avail,
        f"{pfx}_fanduel_line":                totals_data["fanduel_line"],
        f"{pfx}_fanduel_over_price":          totals_data["fanduel_over_price"],
        f"{pfx}_fanduel_under_price":         totals_data["fanduel_under_price"],
        f"{pfx}_draftkings_available":        dk_avail,
        f"{pfx}_draftkings_line":             totals_data["draftkings_line"],
        f"{pfx}_draftkings_over_price":       totals_data["draftkings_over_price"],
        f"{pfx}_draftkings_under_price":      totals_data["draftkings_under_price"],
    }

# ── Checkpoint management ─────────────────────────────────────────
def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            cp = json.load(f)
        completed = set(cp.get("completed_game_ids", []))
        log.info(f"Checkpoint loaded: {len(completed)} games completed")
        return cp, completed
    return {"completed_game_ids": [], "records": [], "credits_remaining": None,
            "calls_made": 0, "last_updated": None}, set()

def save_checkpoint(cp, completed, records_df=None):
    cp["last_updated"] = datetime.utcnow().isoformat()
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(cp, f)
    if records_df is not None and len(records_df) > 0:
        records_df.to_parquet(RAW_RECORDS_FILE, index=False)

# ── STEP 1: Load substrate ────────────────────────────────────────
log.info("STEP 1: Loading MPS substrate...")
snap = pd.read_parquet(MPS_PARQUET)
log.info(f"Substrate: {len(snap)} games, {len(snap.columns)} cols")
log.info(f"Seasons: {dict(snap['season'].value_counts().sort_index())}")

# ── STEP 2: Build manifest of games to probe ──────────────────────
log.info("STEP 2: Building game manifest...")
manifest = snap[["game_id","season","game_date","home_team","away_team","commence_time_utc"]].copy()
manifest["game_date"] = manifest["game_date"].astype(str).str[:10]
log.info(f"Manifest: {len(manifest)} games")

# Save source manifest
manifest_path = OUT_DIR / "mlb_intraday_decision_panel_v1_source_manifest.csv"
manifest.to_csv(manifest_path, index=False)
log.info(f"Manifest saved: {manifest_path}")

# ── STEP 3: Acquisition loop ──────────────────────────────────────
log.info("STEP 3: Starting intraday probe acquisition...")
cp, completed = load_checkpoint()
calls_made    = cp.get("calls_made", 0)
credits_rem   = cp.get("credits_remaining", None)

# Load existing raw records if any
existing_records = []
if RAW_RECORDS_FILE.exists():
    existing_df = pd.read_parquet(RAW_RECORDS_FILE)
    existing_records = existing_df.to_dict("records")
    log.info(f"Existing raw records loaded: {len(existing_records)}")

new_records = []
games_list  = manifest.to_dict("records")

# Group games by date to reuse API responses efficiently
# Each probe timestamp is the same for all games on that date,
# so we batch by (date, probe) to make one API call per unique (date, probe)
from collections import defaultdict

date_groups = defaultdict(list)
for g in games_list:
    date_groups[g["game_date"]].append(g)

sorted_dates = sorted(date_groups.keys())
log.info(f"Unique game dates: {len(sorted_dates)}")
log.info(f"Total probe calls needed: {len(sorted_dates) * 3} (3 probes × {len(sorted_dates)} dates)")

# Use a per-(game_id, probe_label) key for completion tracking
completed_keys = set(cp.get("completed_keys", []))
log.info(f"Already completed (game×probe) keys: {len(completed_keys)}")

HARD_STOP = False

for date_idx, game_date in enumerate(sorted_dates):
    games_on_date = date_groups[game_date]
    game_ids_on_date = [g["game_id"] for g in games_on_date]

    for probe_label, probe_hour_utc in PROBES:
        if HARD_STOP:
            break

        probe_utc_str = f"{game_date}T{probe_hour_utc:02d}:00:00Z"

        # Check if ALL games on this date for this probe are done
        all_done = all(
            f"{gid}_{probe_label}" in completed_keys
            for gid in game_ids_on_date
        )
        if all_done:
            continue

        # Make ONE API call for this (date, probe)
        time.sleep(SLEEP_SEC)
        result = fetch_snapshot(probe_utc_str)
        calls_made += 1
        cp["calls_made"] = calls_made

        if result.get("credits_remaining"):
            credits_rem = result["credits_remaining"]
            cp["credits_remaining"] = credits_rem

        # HARD STOP conditions
        if result["error"] == "RATE_LIMITED_429":
            log.error(f"HARD STOP: 429 rate limit at {probe_utc_str}")
            HARD_STOP = True
            break
        if result["error"] == "MALFORMED_RESPONSE":
            log.error(f"HARD STOP: malformed response at {probe_utc_str}")
            HARD_STOP = True
            break

        raw_events    = result.get("raw_events") or []
        snapshot_ts   = result.get("snapshot_timestamp")
        api_error     = result.get("error")

        # For each game on this date, extract and record
        for g in games_on_date:
            gid        = g["game_id"]
            key        = f"{gid}_{probe_label}"
            if key in completed_keys:
                continue

            event      = match_event(raw_events, g["home_team"], g["away_team"])
            totals     = extract_totals(event, snapshot_ts)
            sel        = select_book(totals, probe_utc_str, probe_label)

            rec = {
                "game_id":          gid,
                "season":           g["season"],
                "game_date":        game_date,
                "home_team":        g["home_team"],
                "away_team":        g["away_team"],
                "commence_time_utc": g["commence_time_utc"],
                "probe_label":      probe_label,
                "probe_utc":        probe_utc_str,
                "api_error":        api_error,
                **sel,
            }
            new_records.append(rec)
            completed_keys.add(key)

        cp["completed_keys"] = list(completed_keys)

        # Log progress
        if calls_made % 50 == 0:
            log.info(f"  Calls: {calls_made} | Date: {game_date} | Probe: {probe_label} | Credits: {credits_rem}")

        # Checkpoint every N calls
        if calls_made % CHECKPOINT_EVERY == 0:
            all_records = existing_records + new_records
            df_cp = pd.DataFrame(all_records)
            save_checkpoint(cp, set(), df_cp)
            log.info(f"  Checkpoint saved at call {calls_made}")

    if HARD_STOP:
        break

# Final save
log.info(f"Acquisition complete. Total calls: {calls_made}, Credits remaining: {credits_rem}")
all_records = existing_records + new_records
df_raw = pd.DataFrame(all_records)
df_raw.to_parquet(RAW_RECORDS_FILE, index=False)
log.info(f"Raw records saved: {len(df_raw)} rows → {RAW_RECORDS_FILE}")

if HARD_STOP:
    log.error("BUILD STOPPED EARLY due to HARD STOP condition")
    sys.exit(2)

# ── STEP 4: Build final panel ─────────────────────────────────────
log.info("STEP 4: Building final panel table...")

# Reload full raw records
df_raw = pd.read_parquet(RAW_RECORDS_FILE)
log.info(f"Raw records: {len(df_raw)} rows, probes: {df_raw['probe_label'].value_counts().to_dict()}")

# Pivot: one row per game, columns per probe
def build_state_cols(df, probe_label):
    """Extract probe-specific columns and rename to state prefix."""
    pfx    = probe_label.lower()
    # Map the new probe label to canonical state name
    state_map = {
        "dt_0700": "DT_0700",
        "dt_1000": "DT_1000",
        "dt_1200": "DT_1200",
    }
    state = state_map.get(pfx, pfx.upper())
    spfx  = state.lower()

    sub = df[df["probe_label"] == probe_label].copy()
    id_cols = ["game_id"]
    data_cols = [c for c in sub.columns if c.startswith(pfx + "_")]
    sub = sub[id_cols + data_cols].copy()

    # Rename: pfx_ → state_
    rename = {c: c.replace(pfx + "_", spfx + "_", 1) for c in data_cols}
    sub = sub.rename(columns=rename)

    # Add probe_utc as the "requested" timestamp column
    probe_utc_col = df[df["probe_label"] == probe_label][["game_id","probe_utc"]].drop_duplicates("game_id")
    probe_utc_col = probe_utc_col.rename(columns={"probe_utc": f"{spfx}_requested_probe_utc"})
    sub = sub.merge(probe_utc_col, on="game_id", how="left")

    return sub

# Build per-probe frames
frames = {}
for probe_label, _ in PROBES:
    frames[probe_label] = build_state_cols(df_raw, probe_label)

# Start with substrate (open + close)
panel = snap.copy()

# Rename substrate columns to use canonical state names
open_rename  = {c: c.replace("open_", "open_0001_", 1) if c.startswith("open_") else c for c in panel.columns}
close_rename = {c: c.replace("close_", "final_close_", 1) if c.startswith("close_") else c for c in panel.columns}
rename_map   = {**open_rename, **close_rename}
# Handle open_0001_0001_ double-replace issue
panel = panel.rename(columns={
    c: c.replace("open_", "open_0001_", 1) if c.startswith("open_") else
       (c.replace("close_", "final_close_", 1) if c.startswith("close_") else c)
    for c in panel.columns
})

# Rename substrate's existing pairing columns
if "same_book_pair" in panel.columns:
    panel = panel.rename(columns={
        "same_book_pair": "open_close_same_book",
        "pair_book":       "open_close_pair_book",
        "pair_quality_flag": "open_close_pair_quality_flag",
    })

# Rename requested probe columns
if "requested_open_probe_utc" in panel.columns:
    panel = panel.rename(columns={
        "requested_open_probe_utc":  "open_0001_requested_probe_utc",
        "requested_close_probe_utc": "final_close_requested_probe_utc",
    })
if "close_rule_used" in panel.columns:
    panel = panel.rename(columns={"close_rule_used": "final_close_rule_used"})

# Merge intraday probe frames
for probe_label, _ in PROBES:
    pfr = frames[probe_label]
    panel = panel.merge(pfr, on="game_id", how="left")
    log.info(f"  Merged {probe_label}: {len(pfr)} records")

# ── Add day_evening_class ─────────────────────────────────────────
def classify_game(row):
    try:
        ct = str(row["commence_time_utc"])
        dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        h  = dt.hour
        # Day game: 10:00–20:59 UTC (roughly 6am–4:59pm ET in EDT)
        return "DAY" if 10 <= h <= 20 else "EVENING"
    except Exception:
        return "UNKNOWN"

panel["day_evening_class"] = panel.apply(classify_game, axis=1)

# ── Integrity flags ───────────────────────────────────────────────
def parse_utc(s):
    try:
        if not s or (isinstance(s, float) and np.isnan(s)):
            return None
        s = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

# open_late_flag: open snapshot >= 10:00 UTC (06:00 ET)
def open_late_flag(row):
    ts = parse_utc(row.get("open_0001_selected_snapshot_timestamp"))
    if ts is None:
        return None
    return ts.hour >= 10

# dt0700_near_open_flag: DT_0700 snapshot within 30 min of open snapshot
def dt0700_near_open_flag(row):
    ts_open = parse_utc(row.get("open_0001_selected_snapshot_timestamp"))
    ts_dt   = parse_utc(row.get("dt_0700_selected_snapshot_timestamp"))
    if ts_open is None or ts_dt is None:
        return None
    delta = abs((ts_dt - ts_open).total_seconds() / 60)
    return delta <= 30

# final_close_post_first_pitch_flag: close snapshot >= commence_time
def close_post_first_pitch_flag(row):
    ts_close   = parse_utc(row.get("final_close_selected_snapshot_timestamp"))
    ts_commence = parse_utc(row.get("commence_time_utc"))
    if ts_close is None or ts_commence is None:
        return None
    return ts_close >= ts_commence

panel["open_late_flag"]                   = panel.apply(open_late_flag, axis=1)
panel["dt0700_near_open_flag"]            = panel.apply(dt0700_near_open_flag, axis=1)
panel["final_close_post_first_pitch_flag"] = panel.apply(close_post_first_pitch_flag, axis=1)

# ── Continuity pairs ──────────────────────────────────────────────
STATE_PAIRS = [
    ("open_0001", "dt_0700",       "open_0700"),
    ("open_0001", "dt_1000",       "open_1000"),
    ("open_0001", "dt_1200",       "open_1200"),
    ("dt_0700",   "final_close",   "dt0700_close"),
    ("dt_1000",   "final_close",   "dt1000_close"),
    ("dt_1200",   "final_close",   "dt1200_close"),
    ("open_0001", "final_close",   "open_close"),
]

def build_pair_cols(panel, s1, s2, pair_name):
    book1 = panel.get(f"{s1}_selected_book")
    book2 = panel.get(f"{s2}_selected_book")
    if book1 is None or book2 is None:
        panel[f"{pair_name}_same_book"]        = None
        panel[f"{pair_name}_pair_book"]        = None
        panel[f"{pair_name}_pair_quality_flag"] = "MISSING_STATE"
        return panel

    same = book1 == book2
    pb   = book1.where(same, other=book1 + "→" + book2.fillna("NONE"))

    def qflag(row):
        b1 = row.get(f"{s1}_selected_book")
        b2 = row.get(f"{s2}_selected_book")
        q1 = row.get(f"{s1}_selected_quality_flag", "MISSING")
        q2 = row.get(f"{s2}_selected_quality_flag", "MISSING")
        if q1 == "MISSING" or q2 == "MISSING":
            return "MISSING_ONE"
        if q1 == "OK" and q2 == "OK" and b1 == b2:
            return f"SAME_{b1.upper()}" if b1 else "SAME_UNKNOWN"
        if q1 == "OK" and q2 == "OK":
            return "CROSS_BOOK"
        return "INCOMPLETE"

    panel[f"{pair_name}_same_book"]        = same
    panel[f"{pair_name}_pair_book"]        = pb
    panel[f"{pair_name}_pair_quality_flag"] = panel.apply(qflag, axis=1)
    return panel

for s1, s2, pair_name in STATE_PAIRS:
    panel = build_pair_cols(panel, s1, s2, pair_name)
    log.info(f"  Pair built: {pair_name}")

# ── Save panel ────────────────────────────────────────────────────
panel_path = OUT_DIR / "mlb_intraday_decision_panel_v1_2022_2025.parquet"
panel.to_parquet(panel_path, index=False)
log.info(f"Panel saved: {len(panel)} rows × {len(panel.columns)} cols → {panel_path}")

# ── STEP 5: QA tables ─────────────────────────────────────────────
log.info("STEP 5: Computing QA tables...")

STATES = ["open_0001", "dt_0700", "dt_1000", "dt_1200", "final_close"]

# TABLE A: Usable data by state × season
log.info("\n=== TABLE A: Usable data (quality_flag==OK) by state × season ===")
table_a = {}
for state in STATES:
    qcol = f"{state}_selected_quality_flag"
    if qcol in panel.columns:
        ok_by_season = panel.groupby("season").apply(
            lambda df: (df[qcol] == "OK").sum()
        )
        total_by_season = panel.groupby("season").size()
        table_a[state] = (ok_by_season / total_by_season * 100).round(1)
        for yr, pct in table_a[state].items():
            log.info(f"  {state:15s}  {yr}  {ok_by_season[yr]:4d}/{total_by_season[yr]:4d}  ({pct}%)")
    else:
        log.info(f"  {state}: column not found")

# TABLE B: Book selection by state × season
log.info("\n=== TABLE B: Book selection by state × season ===")
for state in STATES:
    bcol = f"{state}_selected_book"
    if bcol in panel.columns:
        dist = panel.groupby(["season", bcol]).size().unstack(fill_value=0)
        log.info(f"\n  {state}:\n{dist.to_string()}")

# TABLE C: Continuity/pair quality
log.info("\n=== TABLE C: Continuity pair quality ===")
for _, _, pair_name in STATE_PAIRS:
    pcol = f"{pair_name}_pair_quality_flag"
    if pcol in panel.columns:
        dist = panel.groupby("season")[pcol].value_counts().unstack(fill_value=0)
        log.info(f"\n  Pair {pair_name}:\n{dist.to_string()}")

# TABLE D: Timestamp quality
log.info("\n=== TABLE D: Timestamp delta (median min) by state × season ===")
for state in STATES:
    dcol = f"{state}_selected_timestamp_delta_min"
    if dcol in panel.columns:
        med = panel.groupby("season")[dcol].median().round(1)
        log.info(f"  {state:15s}: {med.to_dict()}")

# Integrity flags
log.info("\n=== Integrity flags by season ===")
for flag_col in ["open_late_flag","dt0700_near_open_flag","final_close_post_first_pitch_flag"]:
    if flag_col in panel.columns:
        cnts = panel.groupby("season")[flag_col].sum()
        log.info(f"  {flag_col}: {cnts.to_dict()}")

# Monthly coverage check
log.info("\n=== Monthly coverage check (any state × month below 80%) ===")
panel["year_month"] = panel["game_date"].astype(str).str[:7]
low_coverage = []
for state in STATES:
    qcol = f"{state}_selected_quality_flag"
    if qcol not in panel.columns:
        continue
    monthly = panel.groupby("year_month").apply(
        lambda df: (df[qcol] == "OK").sum() / len(df) * 100
    ).round(1)
    below = monthly[monthly < 80.0]
    for ym, pct in below.items():
        low_coverage.append((state, ym, pct))
        log.info(f"  LOW COVERAGE: {state} @ {ym} = {pct}%")

if not low_coverage:
    log.info("  No month×state below 80% — all clean")

# ── STEP 6: Build reports ─────────────────────────────────────────
log.info("STEP 6: Writing reports...")

# Determine build verdict
ok_rates = []
for state in ["dt_0700","dt_1000","dt_1200"]:
    qcol = f"{state}_selected_quality_flag"
    if qcol in panel.columns:
        r = (panel[qcol] == "OK").mean() * 100
        ok_rates.append(r)

avg_ok = sum(ok_rates) / len(ok_rates) if ok_rates else 0
material_low_months = len([x for x in low_coverage if x[2] < 70.0])

if HARD_STOP:
    verdict = "BUILD INCOMPLETE"
elif avg_ok >= 80.0 and material_low_months == 0:
    verdict = "PANEL BUILT CLEANLY"
elif avg_ok >= 60.0:
    verdict = "PANEL BUILT WITH MATERIAL GAPS"
else:
    verdict = "BUILD INCOMPLETE"

log.info(f"\nBuild verdict: {verdict}")
log.info(f"  avg usable rate (DT probes): {avg_ok:.1f}%")
log.info(f"  material low months (<70%): {material_low_months}")

# Summary dict for JSON
summary = {
    "build_type":          "INTRADAY DECISION PANEL V1",
    "build_note":          "MPS remains RESERVED / DATA-BLOCKED. This build creates the historical intraday decision panel only. No signals have been tested, no decision filters have been defined, and no changes to the canonical spec have been made.",
    "generated_at":        datetime.utcnow().isoformat() + "Z",
    "mps_status":          "RESERVED / DATA-BLOCKED",
    "source_universe": {
        "seasons":          [2022, 2023, 2024, 2025],
        "total_games":      len(panel),
        "by_season":        dict(snap["season"].value_counts().sort_index()),
    },
    "acquisition": {
        "new_probe_calls_made":    calls_made,
        "credits_remaining":       credits_rem,
        "probes":                  [p[0] for p in PROBES],
        "sleep_sec":               SLEEP_SEC,
        "hard_stop":               HARD_STOP,
    },
    "usable_rates_pct": {
        state: round((panel[f"{state}_selected_quality_flag"] == "OK").mean() * 100, 1)
        if f"{state}_selected_quality_flag" in panel.columns else None
        for state in STATES
    },
    "integrity_flags": {
        "open_late_flag_count":       int(panel["open_late_flag"].sum()) if "open_late_flag" in panel.columns else None,
        "dt0700_near_open_count":     int(panel["dt0700_near_open_flag"].sum()) if "dt0700_near_open_flag" in panel.columns else None,
        "close_post_first_pitch_count": int(panel["final_close_post_first_pitch_flag"].sum()) if "final_close_post_first_pitch_flag" in panel.columns else None,
    },
    "low_coverage_months":     low_coverage,
    "verdict":                 verdict,
    "output_files": {
        "panel_parquet":        str(panel_path),
        "source_manifest_csv":  str(manifest_path),
        "raw_records_parquet":  str(RAW_RECORDS_FILE),
        "build_report_md":      str(OUT_DIR / "MLB_INTRADAY_DECISION_PANEL_V1_BUILD.md"),
        "raw_json":             str(OUT_DIR / "MLB_INTRADAY_DECISION_PANEL_V1_RAW.json"),
        "log":                  str(LOG_FILE),
    },
}

# Write RAW JSON
with open(OUT_DIR / "MLB_INTRADAY_DECISION_PANEL_V1_RAW.json", "w") as f:
    json.dump(summary, f, indent=2)
log.info("RAW JSON written")

# Build report markdown
md_lines = [
    "# MLB INTRADAY DECISION PANEL V1 — BUILD REPORT",
    "",
    "> **BUILD ONLY — INTRADAY DECISION PANEL V1**",
    "> MPS remains RESERVED / DATA-BLOCKED. This build creates the historical intraday decision panel only. No signals have been tested, no decision filters have been defined, and no changes to the canonical spec have been made.",
    "",
    f"**Generated:** {summary['generated_at']}",
    f"**Verdict:** {verdict}",
    "",
    "## 1. Source Universe",
    f"- Seasons: 2022–2025",
    f"- Total games: {len(panel):,}",
    f"- By season: {dict(snap['season'].value_counts().sort_index())}",
    "",
    "## 2. Acquisition",
    f"- New probe timestamps: 07:00 ET (11:00 UTC), 10:00 ET (14:00 UTC), 12:00 ET (16:00 UTC)",
    f"- Unique (date, probe) API calls made: {calls_made:,}",
    f"- Credits remaining: {credits_rem}",
    f"- Sleep: {SLEEP_SEC}s between calls",
    f"- OPEN + FINAL CLOSE reused from MPS substrate (no new API calls)",
    f"- Hard stop triggered: {HARD_STOP}",
    "",
    "## 3. Panel Structure",
    f"- Rows: {len(panel):,} (one per game)",
    f"- Columns: {len(panel.columns)}",
    "- States: OPEN_0001, DT_0700, DT_1000, DT_1200, FINAL_CLOSE",
    "- Per state: selected_book, selected_line, over_price, under_price, snapshot_timestamp, timestamp_delta_min, fallback_used, quality_flag, fanduel/draftkings raw",
    "",
    "## 4. Usable Data Rates",
]
for state in STATES:
    qcol = f"{state}_selected_quality_flag"
    if qcol in panel.columns:
        r = (panel[qcol] == "OK").mean() * 100
        md_lines.append(f"- {state}: {r:.1f}%")

md_lines += [
    "",
    "## 5. Integrity Flags",
    f"- open_late_flag (open ≥ 06:00 ET): {int(panel['open_late_flag'].sum()) if 'open_late_flag' in panel.columns else 'N/A'}",
    f"- dt0700_near_open_flag (within 30min): {int(panel['dt0700_near_open_flag'].sum()) if 'dt0700_near_open_flag' in panel.columns else 'N/A'}",
    f"- final_close_post_first_pitch_flag: {int(panel['final_close_post_first_pitch_flag'].sum()) if 'final_close_post_first_pitch_flag' in panel.columns else 'N/A'}",
    "",
    "## 6. Continuity Pairs",
    "States: open→0700, open→1000, open→1200, 0700→close, 1000→close, 1200→close, open→close",
]
for _, _, pair_name in STATE_PAIRS:
    pcol = f"{pair_name}_pair_quality_flag"
    if pcol in panel.columns:
        dist = panel[pcol].value_counts().to_dict()
        md_lines.append(f"- {pair_name}: {dist}")

md_lines += [
    "",
    "## 7. Low Coverage Months",
]
if low_coverage:
    for state, ym, pct in low_coverage:
        md_lines.append(f"- {state} @ {ym}: {pct}%")
else:
    md_lines.append("- None below 80%")

md_lines += [
    "",
    "## 8. Output Files",
    f"- Panel parquet: `mlb_intraday_decision_panel_v1_2022_2025.parquet`",
    f"- Source manifest: `mlb_intraday_decision_panel_v1_source_manifest.csv`",
    f"- Raw records: `intraday_raw_records.parquet`",
    f"- Raw JSON: `MLB_INTRADAY_DECISION_PANEL_V1_RAW.json`",
    f"- Log: `intraday_acquisition.log`",
    "",
    "## 9. MPS Status",
    "**MPS STATUS: RESERVED / DATA-BLOCKED**",
    "",
    f"## Build Verdict: {verdict}",
]

with open(OUT_DIR / "MLB_INTRADAY_DECISION_PANEL_V1_BUILD.md", "w") as f:
    f.write("\n".join(md_lines))
log.info("Build report written")

# ── Final print ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BUILD ONLY — INTRADAY DECISION PANEL V1")
print("=" * 60)
print(f"\n1. SOURCE UNIVERSE")
print(f"   Seasons: 2022–2025 | Total games: {len(panel):,}")
print(f"   By season: {dict(snap['season'].value_counts().sort_index())}")
print(f"\n2. API ACQUISITION")
print(f"   New (date×probe) calls made: {calls_made:,}")
print(f"   Credits remaining: {credits_rem}")
for state in STATES:
    qcol = f"{state}_selected_quality_flag"
    if qcol in panel.columns:
        r = (panel[qcol] == "OK").mean() * 100
        print(f"   {state:15s}: {r:.1f}% usable")
print(f"\n3. INTEGRITY FLAGS")
print(f"   open_late_flag:                    {int(panel['open_late_flag'].sum()) if 'open_late_flag' in panel.columns else 'N/A'}")
print(f"   dt0700_near_open_flag:             {int(panel['dt0700_near_open_flag'].sum()) if 'dt0700_near_open_flag' in panel.columns else 'N/A'}")
print(f"   final_close_post_first_pitch_flag: {int(panel['final_close_post_first_pitch_flag'].sum()) if 'final_close_post_first_pitch_flag' in panel.columns else 'N/A'}")
print(f"\n4. BOOK SELECTION (all states)")
for state in STATES:
    bcol = f"{state}_selected_book"
    if bcol in panel.columns:
        dist = panel[bcol].value_counts().to_dict()
        print(f"   {state:15s}: {dist}")
print(f"\n5. CONTINUITY RATES")
for _, _, pair_name in STATE_PAIRS:
    pcol = f"{pair_name}_pair_quality_flag"
    if pcol in panel.columns:
        same = panel[pcol].str.startswith("SAME").mean() * 100
        print(f"   {pair_name:18s}: {same:.1f}% same-book")
print(f"\n6. TIMESTAMP QUALITY (median delta min)")
for state in STATES:
    dcol = f"{state}_selected_timestamp_delta_min"
    if dcol in panel.columns:
        med = panel[dcol].median()
        print(f"   {state:15s}: {med:.1f} min median delta")
print(f"\n7. BUILD VERDICT: {verdict}")
print(f"\n8. FILES WRITTEN")
for k, v in summary["output_files"].items():
    print(f"   {k}: {v}")
print(f"\n9. MPS STATUS: RESERVED / DATA-BLOCKED")
print("=" * 60)
