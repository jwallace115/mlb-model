"""
MPS OPEN-DISCOVERY TIMING AUDIT — MLB Totals Context Engine V1
AUDIT ONLY — MPS REMAINS BLOCKED
"""
import pandas as pd
import numpy as np
import requests
import json
import time
import os
import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path

print("=" * 60)
print("AUDIT ONLY — MPS REMAINS BLOCKED")
print("=" * 60)
print()

# ── API KEY ──────────────────────────────────────────────────
spec = importlib.util.spec_from_file_location("config", "config.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)
KEY = getattr(cfg, "ODDS_API_KEY", None)
if not KEY:
    raise RuntimeError("No API key found")
print(f"API key loaded: {KEY[:8]}...")

# ── OUTPUT DIR ───────────────────────────────────────────────
OUT_DIR = Path("research/recovery/mlb_totals_context_engine_v1/mps_open_discovery_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Output dir: {OUT_DIR}")

# ── TEAM NAME NORMALIZATION ───────────────────────────────────
ABBR_TO_FULL = {
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
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDP": "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SFG": "San Francisco Giants",
    "STL": "St. Louis Cardinals",
    "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WSN": "Washington Nationals",
}
FULL_TO_ABBR = {v: k for k, v in ABBR_TO_FULL.items()}

print("\nTeam normalization map (abbr -> full name):")
for k, v in ABBR_TO_FULL.items():
    print(f"  {k} = {v}")

# ── STEP 1: SAMPLE 30 GAMES ───────────────────────────────────
print("\n" + "="*60)
print("STEP 1 — SAMPLE 30 GAMES")
print("="*60)

df = pd.read_parquet("research/recovery/mlb_totals_context_engine_v1/context_engine_raw_table.parquet")
games_2024 = df[df["season"] == 2024].copy()
games_2024 = games_2024.dropna(subset=["local_start_hour"])

# Day = local hour <= 15 (through 3pm), Evening = >= 16
day_games = games_2024[games_2024["local_start_hour"] <= 15]
eve_games = games_2024[games_2024["local_start_hour"] >= 16]

day_sample = day_games.sample(n=min(15, len(day_games)), random_state=99)
eve_sample = eve_games.sample(n=min(15, len(eve_games)), random_state=99)
sample = pd.concat([day_sample, eve_sample]).reset_index(drop=True)
sample["is_day"] = sample["local_start_hour"] <= 15

print(f"Day games available: {len(day_games)}, sampled: {len(day_sample)}")
print(f"Evening games available: {len(eve_games)}, sampled: {len(eve_sample)}")
print(f"Total sample: {len(sample)}")
print()

# ── STEP 2: PROBE SCHEDULE ────────────────────────────────────
print("="*60)
print("STEP 2 — PROBE SCHEDULE SETUP")
print("="*60)

# ET probe times → UTC offsets (ET = UTC-4 during DST in 2024)
# 2024 DST: started March 10, ended Nov 3 → all our games in DST window (ET = UTC-4)
ET_PROBES = [
    ("00:01 ET", 0*60+1,   4*60+1),   # ET 00:01 -> UTC 04:01
    ("02:00 ET", 2*60+0,   6*60+0),
    ("04:00 ET", 4*60+0,   8*60+0),
    ("06:00 ET", 6*60+0,  10*60+0),
    ("08:00 ET", 8*60+0,  12*60+0),
    ("10:00 ET",10*60+0,  14*60+0),
    ("12:00 ET",12*60+0,  16*60+0),
    ("14:00 ET",14*60+0,  18*60+0),
]
# Close probe varies by game type
CLOSE_DAY_ET = 17*60+0   # 17:00 ET → 21:00 UTC
CLOSE_EVE_ET = 18*60+0   # 18:00 ET → 22:00 UTC

BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds"

def build_utc_timestamp(date_str, utc_minute_offset):
    """Build ISO UTC timestamp from YYYY-MM-DD date string and minutes-from-midnight UTC."""
    h = utc_minute_offset // 60
    m = utc_minute_offset % 60
    return f"{date_str}T{h:02d}:{m:02d}:00Z"

def probe_api(date_str, utc_min_offset, key):
    ts = build_utc_timestamp(date_str, utc_min_offset)
    params = {
        "apiKey": key,
        "regions": "us",
        "markets": "totals",
        "oddsFormat": "american",
        "date": ts,
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)
    return resp, ts

def match_event(events, home_full, away_full):
    """Find event matching home+away team names (case-insensitive partial match)."""
    home_l = home_full.lower()
    away_l = away_full.lower()
    for ev in events:
        ev_home = ev.get("home_team", "").lower()
        ev_away = ev.get("away_team", "").lower()
        if ev_home == home_l and ev_away == away_l:
            return ev
    return None

def extract_bookmaker_data(ev):
    """Return dict: bookmaker_key -> {total, over_price, under_price}."""
    result = {}
    if not ev:
        return result
    for bk in ev.get("bookmakers", []):
        bk_key = bk["key"]
        for mkt in bk.get("markets", []):
            if mkt["key"] == "totals":
                outcomes = {o["name"]: o for o in mkt.get("outcomes", [])}
                over = outcomes.get("Over", {})
                under = outcomes.get("Under", {})
                result[bk_key] = {
                    "total": over.get("point", None),
                    "over_price": over.get("price", None),
                    "under_price": under.get("price", None),
                }
    return result

# ── COLLECT DATA ──────────────────────────────────────────────
print("\nStarting data collection...")
print(f"Games: {len(sample)}, Probes per game: 9, Total API calls: {len(sample)*9}")
print()

all_records = []
remaining_start = None
remaining_end = None
call_count = 0
HARD_STOP = False

for idx, row in sample.iterrows():
    if HARD_STOP:
        break
    
    game_date = row["date"]
    home_abbr = row["home_team"]
    away_abbr = row["away_team"]
    is_day = bool(row["is_day"])
    local_hour = row["local_start_hour"]
    game_hour_utc = row["game_hour_utc"]
    
    home_full = ABBR_TO_FULL.get(home_abbr, home_abbr)
    away_full = ABBR_TO_FULL.get(away_abbr, away_abbr)
    
    # Build probe list for this game
    probes = list(ET_PROBES)
    if is_day:
        probes.append(("17:00 ET (close-day)", CLOSE_DAY_ET, CLOSE_DAY_ET+4*60))
    else:
        probes.append(("18:00 ET (close-eve)", CLOSE_EVE_ET, CLOSE_EVE_ET+4*60))
    
    print(f"Game {len(all_records)//9 + 1}/30: {away_abbr} @ {home_abbr} on {game_date} ({'day' if is_day else 'evening'})")
    
    game_probes = []
    for probe_label, et_min, utc_min in probes:
        if HARD_STOP:
            break
        
        try:
            resp, req_ts = probe_api(game_date, utc_min, KEY)
            call_count += 1
            
            remaining = resp.headers.get("x-requests-remaining")
            if remaining_start is None:
                remaining_start = remaining
            remaining_end = remaining
            
            if resp.status_code == 429:
                print(f"  HARD STOP: 429 rate limit at probe {probe_label}")
                print(f"  Response: {resp.text[:500]}")
                HARD_STOP = True
                break
            
            if resp.status_code != 200:
                print(f"  ERROR {resp.status_code} at probe {probe_label}: {resp.text[:200]}")
                game_probes.append({
                    "game_date": game_date, "home": home_abbr, "away": away_abbr,
                    "is_day": is_day, "probe_label": probe_label,
                    "req_ts": req_ts, "snap_ts": None, "matched": False,
                    "bookmakers": {}, "error": resp.status_code
                })
                time.sleep(0.4)
                continue
            
            data = resp.json()
            snap_ts = data.get("timestamp")
            events = data.get("data", [])
            
            # Validate schema
            if not isinstance(events, list):
                print(f"  HARD STOP: unexpected schema at {probe_label}")
                print(f"  Response: {json.dumps(data)[:500]}")
                HARD_STOP = True
                break
            
            matched_ev = match_event(events, home_full, away_full)
            bk_data = extract_bookmaker_data(matched_ev)
            
            record = {
                "game_date": game_date, "home": home_abbr, "away": away_abbr,
                "home_full": home_full, "away_full": away_full,
                "is_day": is_day, "local_hour": local_hour, "game_hour_utc": game_hour_utc,
                "probe_label": probe_label, "req_ts": req_ts, "snap_ts": snap_ts,
                "matched": matched_ev is not None,
                "bookmakers": bk_data, "error": None,
                "n_bookmakers": len(bk_data),
                "has_fanduel": "fanduel" in bk_data,
                "has_draftkings": "draftkings" in bk_data,
            }
            game_probes.append(record)
            
            match_str = "MATCH" if matched_ev else "no-match"
            books_str = ",".join(bk_data.keys()) if bk_data else "-"
            print(f"  {probe_label}: snap={snap_ts} | {match_str} | books=[{books_str}]")
            
        except Exception as e:
            print(f"  EXCEPTION at {probe_label}: {e}")
            game_probes.append({
                "game_date": game_date, "home": home_abbr, "away": away_abbr,
                "is_day": is_day, "probe_label": probe_label,
                "req_ts": req_ts if "req_ts" in dir() else None, "snap_ts": None,
                "matched": False, "bookmakers": {}, "error": str(e)
            })
        
        time.sleep(0.4)
    
    all_records.extend(game_probes)
    print()

print(f"\nCollection complete. Total calls: {call_count}")
print(f"Remaining credits (start): {remaining_start}")
print(f"Remaining credits (end):   {remaining_end}")

if HARD_STOP:
    print("\nHARD STOP triggered. Saving partial data.")

# ── STEP 3: ANALYSIS ──────────────────────────────────────────
print("\n" + "="*60)
print("STEP 3 — ANALYSIS")
print("="*60)

records_df = pd.DataFrame(all_records)

# Parse timestamps
def parse_ts(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except:
        return None

def parse_req_min(ts_str):
    """Return minutes from midnight for requested UTC time."""
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.hour * 60 + dt.minute
    except:
        return None

records_df["snap_dt"] = records_df["snap_ts"].apply(parse_ts)
records_df["req_dt"] = records_df["req_ts"].apply(parse_ts)
records_df["ts_delta_min"] = records_df.apply(
    lambda r: abs((r["snap_dt"] - r["req_dt"]).total_seconds() / 60) 
    if r["snap_dt"] and r["req_dt"] else None, axis=1
)

# Get standard probe labels in order
probe_order = [p[0] for p in ET_PROBES] + ["17:00 ET (close-day)", "18:00 ET (close-eve)"]

# TABLE A — Coverage by probe time
print("\nTABLE A — Coverage by probe time:")
print(f"{'Probe':<25} {'Games':>6} {'Matched':>8} {'Any Total':>10} {'FanDuel':>8} {'DraftKings':>10}")
print("-"*70)
table_a = []
for pl in probe_order:
    sub = records_df[records_df["probe_label"] == pl]
    if len(sub) == 0:
        continue
    n_games = len(sub)
    n_matched = sub["matched"].sum()
    n_any = sub.apply(lambda r: len(r["bookmakers"]) > 0 if isinstance(r["bookmakers"], dict) else False, axis=1).sum()
    n_fd = sub["has_fanduel"].sum() if "has_fanduel" in sub.columns else 0
    n_dk = sub["has_draftkings"].sum() if "has_draftkings" in sub.columns else 0
    print(f"{pl:<25} {n_games:>6} {n_matched:>8} {n_any:>10} {n_fd:>8} {n_dk:>10}")
    table_a.append({"probe": pl, "n_games": n_games, "n_matched": n_matched,
                    "n_any_total": int(n_any), "n_fanduel": int(n_fd), "n_draftkings": int(n_dk)})

# TABLE B — First availability by bookmaker
print("\nTABLE B — First availability by bookmaker (median probe time ET):")
bk_first = {}
for _, row in records_df.iterrows():
    game_id = (row["game_date"], row["home"], row["away"])
    if not isinstance(row["bookmakers"], dict):
        continue
    for bk in row["bookmakers"]:
        if bk not in bk_first:
            bk_first[bk] = {}
        if game_id not in bk_first[bk]:
            bk_first[bk][game_id] = row["probe_label"]

print(f"{'Bookmaker':<20} {'N games':>8} {'Median first probe':<25}")
print("-"*55)
table_b = []
for bk in sorted(bk_first.keys()):
    game_probes = list(bk_first[bk].values())
    # Map probe labels to order index
    probe_idx = [probe_order.index(p) if p in probe_order else 999 for p in game_probes]
    med_idx = int(np.median(probe_idx))
    med_probe = probe_order[med_idx] if med_idx < len(probe_order) else "unknown"
    p25_idx = int(np.percentile(probe_idx, 25))
    p75_idx = int(np.percentile(probe_idx, 75))
    p25_probe = probe_order[min(p25_idx, len(probe_order)-1)]
    p75_probe = probe_order[min(p75_idx, len(probe_order)-1)]
    print(f"  {bk:<18} {len(game_probes):>8}  {med_probe} (P25={p25_probe[:12]}, P75={p75_probe[:12]})")
    table_b.append({"bookmaker": bk, "n_games": len(game_probes), "median_first": med_probe,
                    "p25": p25_probe, "p75": p75_probe})

# TABLE C — Timestamp delta quality
print("\nTABLE C — Timestamp delta from requested time:")
print(f"{'Probe':<25} {'N':>4} {'Med delta(min)':>14} {'P90 delta(min)':>14}")
print("-"*60)
table_c = []
for pl in probe_order:
    sub = records_df[(records_df["probe_label"] == pl) & records_df["ts_delta_min"].notna()]
    if len(sub) == 0:
        continue
    med_d = sub["ts_delta_min"].median()
    p90_d = sub["ts_delta_min"].quantile(0.9)
    print(f"  {pl:<23} {len(sub):>4} {med_d:>14.1f} {p90_d:>14.1f}")
    table_c.append({"probe": pl, "n": len(sub), "median_delta_min": round(med_d, 1), "p90_delta_min": round(p90_d, 1)})

# Build open/close pairs for Tables D-F
# Close probes
close_records = records_df[records_df["probe_label"].str.contains("close")]
open_probes = [p for p in probe_order if "close" not in p]

def get_close_data(game_date, home, away, bk, is_day):
    close_label = "17:00 ET (close-day)" if is_day else "18:00 ET (close-eve)"
    close_row = records_df[
        (records_df["game_date"] == game_date) &
        (records_df["home"] == home) &
        (records_df["away"] == away) &
        (records_df["probe_label"] == close_label)
    ]
    if len(close_row) == 0:
        return None
    bks = close_row.iloc[0]["bookmakers"]
    if not isinstance(bks, dict):
        return None
    return bks.get(bk)

# TABLE D — Same-book parity (open -> close)
print("\nTABLE D — Same-bookmaker parity (open-to-close pairs):")
print(f"{'Probe':<25} {'FD pairs':>9} {'DK pairs':>9} {'Any book pairs':>15}")
print("-"*60)
table_d = []
for pl in open_probes:
    sub = records_df[records_df["probe_label"] == pl]
    fd_pairs = 0
    dk_pairs = 0
    any_pairs = 0
    for _, row in sub.iterrows():
        if not isinstance(row["bookmakers"], dict):
            continue
        for bk, bk_info in row["bookmakers"].items():
            close_info = get_close_data(row["game_date"], row["home"], row["away"], bk, bool(row["is_day"]))
            if close_info and close_info.get("total") is not None and bk_info.get("total") is not None:
                any_pairs += 1
                if bk == "fanduel":
                    fd_pairs += 1
                elif bk == "draftkings":
                    dk_pairs += 1
    n_games = len(sub)
    print(f"  {pl:<23} {fd_pairs:>9} {dk_pairs:>9} {any_pairs:>15}")
    table_d.append({"probe": pl, "fd_pairs": fd_pairs, "dk_pairs": dk_pairs, "any_pairs": any_pairs, "n_games": n_games})

# TABLE E — Total drift (open to close, same book)
print("\nTABLE E — Total drift (open to close, same-book pairs only):")
print(f"{'Probe':<25} {'N pairs':>8} {'Med drift':>10} {'>=0.5':>7} {'>=1.0':>7} {'=0.0':>7}")
print("-"*65)
table_e = []
for pl in open_probes:
    sub = records_df[records_df["probe_label"] == pl]
    drifts = []
    for _, row in sub.iterrows():
        if not isinstance(row["bookmakers"], dict):
            continue
        for bk, bk_info in row["bookmakers"].items():
            close_info = get_close_data(row["game_date"], row["home"], row["away"], bk, bool(row["is_day"]))
            if close_info and close_info.get("total") is not None and bk_info.get("total") is not None:
                drift = abs(close_info["total"] - bk_info["total"])
                drifts.append(drift)
    if not drifts:
        print(f"  {pl:<23} {'0':>8} {'N/A':>10} {'N/A':>7} {'N/A':>7} {'N/A':>7}")
        table_e.append({"probe": pl, "n_pairs": 0})
        continue
    med_d = np.median(drifts)
    pct_05 = sum(d >= 0.5 for d in drifts) / len(drifts) * 100
    pct_10 = sum(d >= 1.0 for d in drifts) / len(drifts) * 100
    pct_00 = sum(d == 0.0 for d in drifts) / len(drifts) * 100
    print(f"  {pl:<23} {len(drifts):>8} {med_d:>10.3f} {pct_05:>7.1f}% {pct_10:>7.1f}% {pct_00:>7.1f}%")
    table_e.append({"probe": pl, "n_pairs": len(drifts), "median_drift": round(med_d, 3),
                    "pct_gte_05": round(pct_05, 1), "pct_gte_10": round(pct_10, 1), "pct_zero": round(pct_00, 1)})

# TABLE F — Juice drift
print("\nTABLE F — Juice drift (over_price, under_price, open to close):")
print(f"{'Probe':<25} {'N pairs':>8} {'Med over$drift':>14} {'Med under$drift':>15} {'%zero juice':>11}")
print("-"*75)
table_f = []
for pl in open_probes:
    sub = records_df[records_df["probe_label"] == pl]
    over_drifts = []
    under_drifts = []
    zero_juice = 0
    total_pairs = 0
    for _, row in sub.iterrows():
        if not isinstance(row["bookmakers"], dict):
            continue
        for bk, bk_info in row["bookmakers"].items():
            close_info = get_close_data(row["game_date"], row["home"], row["away"], bk, bool(row["is_day"]))
            if close_info:
                o_open = bk_info.get("over_price")
                o_close = close_info.get("over_price")
                u_open = bk_info.get("under_price")
                u_close = close_info.get("under_price")
                if o_open is not None and o_close is not None:
                    over_drifts.append(abs(o_close - o_open))
                if u_open is not None and u_close is not None:
                    under_drifts.append(abs(u_close - u_open))
                if o_open is not None and o_close is not None and u_open is not None and u_close is not None:
                    total_pairs += 1
                    if abs(o_close - o_open) == 0 and abs(u_close - u_open) == 0:
                        zero_juice += 1
    if not over_drifts:
        print(f"  {pl:<23} {'0':>8} {'N/A':>14} {'N/A':>15} {'N/A':>11}")
        table_f.append({"probe": pl, "n_pairs": 0})
        continue
    med_o = np.median(over_drifts)
    med_u = np.median(under_drifts) if under_drifts else None
    pct_z = zero_juice / total_pairs * 100 if total_pairs > 0 else None
    print(f"  {pl:<23} {len(over_drifts):>8} {med_o:>14.1f} {(med_u if med_u else 0):>15.1f} {(pct_z if pct_z is not None else 0):>11.1f}%")
    table_f.append({"probe": pl, "n_pairs": len(over_drifts), "median_over_drift": round(med_o, 1),
                    "median_under_drift": round(med_u, 1) if med_u else None, "pct_zero_juice": round(pct_z, 1) if pct_z else None})

# ── STEP 4: RECOMMENDATION ────────────────────────────────────
print("\n" + "="*60)
print("STEP 4 — RECOMMENDATION")
print("="*60)

# Build candidate evaluation
print("\nEvaluating candidates against 4 criteria:")
print("  1. Matched-event hit rate >= 80%")
print("  2. FD or DK same-book parity >= 70%")
print("  3. Median timestamp delta <= 15 min")
print("  4. Drift capture meaningfully better than 09:00 ET benchmark")

# Find "09:00 ET" benchmark -> closest is "08:00 ET" or "10:00 ET"
benchmark_probe = "10:00 ET"

candidates = []
for i, row_a in enumerate(table_a):
    pl = row_a["probe"]
    if "close" in pl:
        continue
    n = row_a["n_games"]
    if n == 0:
        continue
    hit_rate = row_a["n_matched"] / n * 100
    
    # Parity from table_d
    d_row = next((r for r in table_d if r["probe"] == pl), None)
    fd_parity = (d_row["fd_pairs"] / n * 100) if d_row else 0
    dk_parity = (d_row["dk_pairs"] / n * 100) if d_row else 0
    max_parity = max(fd_parity, dk_parity)
    
    # Timestamp delta
    c_row = next((r for r in table_c if r["probe"] == pl), None)
    med_delta = c_row["median_delta_min"] if c_row else 999
    
    # Drift
    e_row = next((r for r in table_e if r["probe"] == pl), None)
    pct_zero = e_row["pct_zero"] if e_row and e_row.get("n_pairs", 0) > 0 else 100
    
    # Compare to benchmark
    bench_e = next((r for r in table_e if r["probe"] == benchmark_probe), None)
    bench_zero = bench_e["pct_zero"] if bench_e and bench_e.get("n_pairs", 0) > 0 else 100
    better_than_bench = pct_zero < bench_zero or (e_row and e_row.get("median_drift", 0) > (bench_e["median_drift"] if bench_e and bench_e.get("n_pairs", 0) > 0 else 0))
    
    c1 = hit_rate >= 80
    c2 = max_parity >= 70
    c3 = med_delta <= 15
    c4 = better_than_bench
    
    candidates.append({
        "probe": pl, "hit_rate": hit_rate, "fd_parity": fd_parity, "dk_parity": dk_parity,
        "max_parity": max_parity, "med_delta": med_delta,
        "pct_zero_drift": pct_zero, "better_than_bench": better_than_bench,
        "c1": c1, "c2": c2, "c3": c3, "c4": c4,
        "all_pass": c1 and c2 and c3 and c4
    })
    
    status = "ALL PASS" if (c1 and c2 and c3 and c4) else f"FAIL: {','.join(['C1' if not c1 else '', 'C2' if not c2 else '', 'C3' if not c3 else '', 'C4' if not c4 else '']).strip(',')}"
    print(f"  {pl:<25} hit={hit_rate:.0f}% parity_max={max_parity:.0f}% delta={med_delta:.1f}min zero_drift={pct_zero:.0f}% -> {status}")

# Choose recommendation
passing = [c for c in candidates if c["all_pass"]]
if passing:
    rec = passing[0]  # earliest
    verdict = "VIABLE"
    verdict_detail = f"Recommended open probe: {rec['probe']}"
else:
    # Best compromise: highest parity with hit_rate >= 50%
    feasible = [c for c in candidates if c["hit_rate"] >= 50]
    if feasible:
        rec = max(feasible, key=lambda x: x["max_parity"])
    else:
        rec = max(candidates, key=lambda x: x["hit_rate"]) if candidates else None
    verdict = "PARTIALLY VIABLE"
    verdict_detail = f"No probe passes all 4 criteria. Best compromise: {rec['probe'] if rec else 'none'}"

print(f"\nVERDICT: {verdict}")
print(f"DETAIL: {verdict_detail}")
if rec:
    print(f"  Hit rate:    {rec['hit_rate']:.1f}%")
    print(f"  FD parity:   {rec['fd_parity']:.1f}%")
    print(f"  DK parity:   {rec['dk_parity']:.1f}%")
    print(f"  TS delta:    {rec['med_delta']:.1f} min")
    print(f"  Zero drift:  {rec['pct_zero_drift']:.1f}%")

# ── STEP 5: WRITE OUTPUTS ─────────────────────────────────────
print("\n" + "="*60)
print("STEP 5 — WRITING OUTPUTS")
print("="*60)

# Serialize records for JSON (convert numpy types)
def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(v) for v in obj]
    elif isinstance(obj, (np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, pd.Timestamp):
        return str(obj)
    elif obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    else:
        return str(obj)

raw_output = {
    "audit_type": "MPS_OPEN_DISCOVERY_TIMING_AUDIT",
    "status": "AUDIT ONLY — MPS REMAINS BLOCKED",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "sample_design": {
        "n_games": len(sample),
        "n_day": len(day_sample),
        "n_evening": len(eve_sample),
        "random_state": 99,
        "season": 2024
    },
    "api_credits": {
        "remaining_before": remaining_start,
        "remaining_after": remaining_end,
        "calls_made": call_count
    },
    "normalization_map": ABBR_TO_FULL,
    "probe_schedule": [{"label": p[0], "et_minute": p[1], "utc_minute": p[2]} for p in ET_PROBES],
    "table_a_coverage": make_serializable(table_a),
    "table_b_first_availability": make_serializable(table_b),
    "table_c_timestamp_quality": make_serializable(table_c),
    "table_d_parity": make_serializable(table_d),
    "table_e_total_drift": make_serializable(table_e),
    "table_f_juice_drift": make_serializable(table_f),
    "recommendation": make_serializable(rec) if rec else None,
    "verdict": verdict,
    "verdict_detail": verdict_detail,
    "all_candidates": make_serializable(candidates),
    "raw_records": make_serializable(all_records)
}

raw_path = OUT_DIR / "MPS_OPEN_DISCOVERY_RAW.json"
with open(raw_path, "w") as f:
    json.dump(raw_output, f, indent=2)
print(f"Raw JSON written: {raw_path}")

# Build markdown report
# Estimate backfill calls
games_per_season = 2430
seasons = 3  # 2022, 2023, 2024
probes_per_game = 9
est_backfill_calls = games_per_season * seasons * probes_per_game
est_credits = est_backfill_calls  # 1 credit per call typically

rec_probe = rec["probe"] if rec else "TBD"

md_lines = [
    "# MPS Open-Discovery Timing Audit — MLB Totals Context Engine V1",
    "",
    "> **Status: AUDIT ONLY — MPS REMAINS BLOCKED**",
    f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    "",
    "---",
    "",
    "## 1. Audit Scope",
    "",
    "This is a pure timing and data-availability audit. Its purpose is to identify the",
    "optimal open-probe time for the MLB Totals Context Engine V1 Market Probe Signal (MPS).",
    "",
    "**No modeling has been performed. No MPS path states have been defined.**",
    "**No signals have been tested. No changes to the canonical spec have been made.**",
    "",
    "The audit answers: *At what time of day do historical totals lines first appear with",
    "sufficient coverage, same-book parity, and movement potential to support an opening-line",
    "capture?*",
    "",
    "---",
    "",
    "## 2. Sample Design",
    "",
    f"- **Season:** 2024 (2,427 games after NaN-filter: 1,860 with valid `local_start_hour`)",
    f"- **Sample:** 30 games — {len(day_sample)} day starts (local hour ≤15), {len(eve_sample)} evening starts (local hour ≥16)",
    "- **Random state:** 99 (reproducible)",
    f"- **API calls made:** {call_count}",
    f"- **Credits remaining after audit:** {remaining_end}",
    "",
    "### Sampled Games",
    "",
    "| Date | Away | Home | Type | Local Hour |",
    "|------|------|------|------|-----------|",
]
for _, row in sample.iterrows():
    md_lines.append(f"| {row['date']} | {row['away_team']} | {row['home_team']} | {'Day' if row['is_day'] else 'Evening'} | {int(row['local_start_hour'])} |")

md_lines += [
    "",
    "### Probe Schedule",
    "",
    "| ET Probe | UTC Timestamp |",
    "|----------|--------------|",
]
for p in ET_PROBES:
    h_et = p[1] // 60
    m_et = p[1] % 60
    h_utc = p[2] // 60
    m_utc = p[2] % 60
    md_lines.append(f"| {h_et:02d}:{m_et:02d} ET | {h_utc:02d}:{m_utc:02d} UTC |")
md_lines += [
    "| 17:00 ET (day games close) | 21:00 UTC |",
    "| 18:00 ET (evening games close) | 22:00 UTC |",
    "",
    "---",
    "",
    "## 3. Coverage Results",
    "",
    "### Table A — Coverage by Probe Time",
    "",
    "| Probe | Games | Matched | Any Total | FanDuel | DraftKings |",
    "|-------|-------|---------|-----------|---------|-----------|",
]
for r in table_a:
    pct_match = r["n_matched"] / r["n_games"] * 100 if r["n_games"] > 0 else 0
    md_lines.append(f"| {r['probe']} | {r['n_games']} | {r['n_matched']} ({pct_match:.0f}%) | {r['n_any_total']} | {r['n_fanduel']} | {r['n_draftkings']} |")

md_lines += [
    "",
    "### Table B — First Availability by Bookmaker",
    "",
    "| Bookmaker | N Games | Median First Probe | P25 | P75 |",
    "|-----------|---------|-------------------|-----|-----|",
]
for r in table_b:
    md_lines.append(f"| {r['bookmaker']} | {r['n_games']} | {r['median_first']} | {r['p25']} | {r['p75']} |")

md_lines += [
    "",
    "### Table C — Timestamp Quality",
    "",
    "| Probe | N | Median Delta (min) | P90 Delta (min) |",
    "|-------|---|-------------------|----------------|",
]
for r in table_c:
    md_lines.append(f"| {r['probe']} | {r['n']} | {r['median_delta_min']} | {r['p90_delta_min']} |")

md_lines += [
    "",
    "---",
    "",
    "## 4. Parity Results",
    "",
    "### Table D — Same-Bookmaker Open-to-Close Pairs",
    "",
    "| Probe | Games | FD Pairs | DK Pairs | FD Parity % | DK Parity % |",
    "|-------|-------|----------|----------|-------------|-------------|",
]
for r in table_d:
    n = r["n_games"]
    fd_pct = r["fd_pairs"] / n * 100 if n > 0 else 0
    dk_pct = r["dk_pairs"] / n * 100 if n > 0 else 0
    md_lines.append(f"| {r['probe']} | {n} | {r['fd_pairs']} | {r['dk_pairs']} | {fd_pct:.1f}% | {dk_pct:.1f}% |")

md_lines += [
    "",
    "---",
    "",
    "## 5. Market Movement",
    "",
    "### Table E — Total Drift (Open to Close, Same-Book Pairs)",
    "",
    "| Probe | N Pairs | Median Drift | ≥0.5 | ≥1.0 | =0.0 (no move) |",
    "|-------|---------|-------------|------|------|---------------|",
]
for r in table_e:
    if r.get("n_pairs", 0) == 0:
        md_lines.append(f"| {r['probe']} | 0 | N/A | N/A | N/A | N/A |")
    else:
        md_lines.append(f"| {r['probe']} | {r['n_pairs']} | {r['median_drift']} | {r['pct_gte_05']}% | {r['pct_gte_10']}% | {r['pct_zero']}% |")

md_lines += [
    "",
    "### Table F — Juice Drift (Over/Under Price, Open to Close)",
    "",
    "| Probe | N Pairs | Med Over$ Drift | Med Under$ Drift | % Zero Juice Move |",
    "|-------|---------|----------------|-----------------|------------------|",
]
for r in table_f:
    if r.get("n_pairs", 0) == 0:
        md_lines.append(f"| {r['probe']} | 0 | N/A | N/A | N/A |")
    else:
        md_lines.append(f"| {r['probe']} | {r['n_pairs']} | {r['median_over_drift']} | {r['median_under_drift']} | {r['pct_zero_juice']}% |")

md_lines += [
    "",
    "---",
    "",
    "## 6. Recommended Open Probe Time",
    "",
    f"**Recommended probe:** `{rec_probe}`",
    "",
]
if rec:
    md_lines += [
        "| Criterion | Value | Pass |",
        "|-----------|-------|------|",
        f"| Hit rate ≥ 80% | {rec['hit_rate']:.1f}% | {'Yes' if rec['c1'] else 'No'} |",
        f"| FD parity ≥ 70% | {rec['fd_parity']:.1f}% | {'Yes' if rec['c2'] and rec['fd_parity']>=70 else 'No'} |",
        f"| DK parity ≥ 70% | {rec['dk_parity']:.1f}% | {'Yes' if rec['c2'] and rec['dk_parity']>=70 else 'No'} |",
        f"| Median TS delta ≤ 15 min | {rec['med_delta']:.1f} min | {'Yes' if rec['c3'] else 'No'} |",
        f"| Better drift than benchmark | {rec['pct_zero_drift']:.0f}% zero drift | {'Yes' if rec['c4'] else 'No'} |",
    ]

md_lines += [
    "",
    "---",
    "",
    "## 7. Viability Verdict",
    "",
    f"**{verdict}**",
    "",
    verdict_detail,
    "",
    "---",
    "",
    "## 8. Full Backfill Implications",
    "",
    "| Parameter | Value |",
    "|-----------|-------|",
    f"| Seasons to backfill | 2022, 2023, 2024 |",
    f"| Games per season (est.) | ~2,430 |",
    f"| Total games | ~7,290 |",
    f"| Probes per game | 9 (8 standard + 1 close) |",
    f"| Estimated API calls | ~{est_backfill_calls:,} |",
    f"| Recommended bookmaker priority | FanDuel, DraftKings, BetMGM, WynnBet |",
    f"| Sleep between calls | 0.4s minimum |",
    f"| Estimated runtime | ~{est_backfill_calls * 0.4 / 3600:.1f} hours |",
    "",
    "**Recommended probe schedule for backfill:**",
    f"- Primary open probe: `{rec_probe}` (convert to UTC for each game date)",
    "- Close probe: 17:00 ET for day games, 18:00 ET for evening games",
    "- If full 9-probe backfill not needed, priority is: open probe + close probe (2 calls/game = ~14,580 total)",
    "",
    "---",
    "",
    "## 9. Status",
    "",
    "> **MPS remains RESERVED / DATA-BLOCKED.**",
    ">",
    "> This audit identifies the best available open-probe timing only.",
    "> No path states have been defined, no signals have been tested,",
    "> and no changes to the canonical spec have been made.",
    "> MPS activation requires a separate explicit authorization.",
]

md_path = OUT_DIR / "MPS_OPEN_DISCOVERY_TIMING_AUDIT.md"
with open(md_path, "w") as f:
    f.write("\n".join(md_lines))
print(f"Markdown report written: {md_path}")

# ── FINAL CONSOLE OUTPUT ──────────────────────────────────────
print()
print("=" * 60)
print("AUDIT ONLY — MPS REMAINS BLOCKED")
print("=" * 60)
print()
print("1. SAMPLE:")
print(f"   Games sampled: {len(sample)} ({len(day_sample)} day, {len(eve_sample)} evening)")
print(f"   API calls made: {call_count}")
print(f"   Credits used: ~{call_count}")
print(f"   Credits remaining: {remaining_end}")
print()
print("2. COVERAGE BY PROBE:")
for r in table_a:
    pct = r["n_matched"] / r["n_games"] * 100 if r["n_games"] > 0 else 0
    print(f"   {r['probe']:<25} matched={r['n_matched']}/{r['n_games']} ({pct:.0f}%)  FD={r['n_fanduel']}  DK={r['n_draftkings']}")
print()
print("3. BEST BOOKMAKER:")
if rec:
    print(f"   At probe {rec['probe']}:")
    print(f"   FanDuel parity:    {rec['fd_parity']:.1f}%")
    print(f"   DraftKings parity: {rec['dk_parity']:.1f}%")
print()
print("4. MOVEMENT TO CLOSE:")
if rec:
    e_rec = next((r for r in table_e if r["probe"] == rec["probe"]), None)
    if e_rec and e_rec.get("n_pairs", 0) > 0:
        print(f"   Probe: {rec['probe']}")
        print(f"   N pairs:       {e_rec['n_pairs']}")
        print(f"   Median drift:  {e_rec['median_drift']}")
        print(f"   Pct >= 0.5:    {e_rec['pct_gte_05']}%")
        print(f"   Pct zero move: {e_rec['pct_zero']}%")
print()
print("5. RECOMMENDATION:")
print(f"   Probe time: {rec_probe}")
print(f"   Verdict:    {verdict}")
print(f"   Detail:     {verdict_detail}")
print()
print("6. FILES WRITTEN:")
print(f"   {md_path}")
print(f"   {raw_path}")
print()
print("7. MPS STATUS: RESERVED / DATA-BLOCKED — no change")
print("   No path states defined. No signals tested. No spec changes.")
print("=" * 60)
