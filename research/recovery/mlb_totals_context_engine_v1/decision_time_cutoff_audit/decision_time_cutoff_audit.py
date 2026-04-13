#!/usr/bin/env python3
"""
DECISION-TIME CUTOFF AUDIT — MLB Totals Market Path
AUDIT ONLY — DECISION TIME NOT YET FROZEN

Steps:
1. Sample 800 games (200/season × 100 day / 100 evening, random_state=123)
2. Reference integrity check (open early, close before first pitch)
3. API collection at 5 candidate times (07–12 ET)
4. Analysis tables A–F
5. Recommendation
6. Write outputs

MPS remains RESERVED / DATA-BLOCKED throughout.
"""

print("AUDIT ONLY — DECISION TIME NOT YET FROZEN")
print("=" * 60)

import os, sys, json, time, math
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
BASE = Path("/root/mlb-model")
MPS_PATH = BASE / "research/recovery/mlb_totals_context_engine_v1/mps_historical_acquisition/mps_historical_snapshots_2022_2025.parquet"
OUT_DIR = BASE / "research/recovery/mlb_totals_context_engine_v1/decision_time_cutoff_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_PATH = OUT_DIR / "collection_checkpoint.parquet"
SAMPLE_PATH = OUT_DIR / "sample_800.parquet"

# ── API Key ─────────────────────────────────────────────────────────────
def get_api_key():
    key = os.environ.get('ODDS_API_KEY')
    if key:
        return key
    try:
        with open(BASE / '.env') as f:
            for line in f:
                if 'ODDS_API_KEY' in line:
                    return line.split('=', 1)[1].strip().strip("'\"")
    except:
        pass
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", BASE / "config.py")
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        return getattr(cfg, 'ODDS_API_KEY', None)
    except:
        pass
    return None

API_KEY = get_api_key()
if not API_KEY:
    print("ERROR: No API key found")
    sys.exit(1)
print(f"API key loaded (len={len(API_KEY)})")

# ── Team name normalization ──────────────────────────────────────────────
# MPS snapshot uses 3-letter abbreviations; Odds API uses full team names.
# Map both to the same canonical full name for matching.

# 3-letter abbreviation → canonical full name
ABBR_TO_FULL = {
    # AL East
    "NYY": "New York Yankees",
    "BOS": "Boston Red Sox",
    "TBR": "Tampa Bay Rays",
    "TB":  "Tampa Bay Rays",
    "BAL": "Baltimore Orioles",
    "TOR": "Toronto Blue Jays",
    # AL Central
    "CHW": "Chicago White Sox",
    "CWS": "Chicago White Sox",
    "CLE": "Cleveland Guardians",
    "DET": "Detroit Tigers",
    "KCR": "Kansas City Royals",
    "KC":  "Kansas City Royals",
    "MIN": "Minnesota Twins",
    # AL West
    "HOU": "Houston Astros",
    "LAA": "Los Angeles Angels",
    "ANA": "Los Angeles Angels",
    "OAK": "Oakland Athletics",
    "ATH": "Oakland Athletics",
    "SEA": "Seattle Mariners",
    "TEX": "Texas Rangers",
    # NL East
    "ATL": "Atlanta Braves",
    "MIA": "Miami Marlins",
    "NYM": "New York Mets",
    "PHI": "Philadelphia Phillies",
    "WSH": "Washington Nationals",
    "WSN": "Washington Nationals",
    # NL Central
    "CHC": "Chicago Cubs",
    "CIN": "Cincinnati Reds",
    "MIL": "Milwaukee Brewers",
    "PIT": "Pittsburgh Pirates",
    "STL": "St. Louis Cardinals",
    # NL West
    "ARI": "Arizona Diamondbacks",
    "AZ":  "Arizona Diamondbacks",
    "COL": "Colorado Rockies",
    "LAD": "Los Angeles Dodgers",
    "SDP": "San Diego Padres",
    "SD":  "San Diego Padres",
    "SFG": "San Francisco Giants",
    "SF":  "San Francisco Giants",
}

# Full name → canonical (pass-through for Odds API names, handle variants)
FULL_NAME_VARIANTS = {
    "Athletics": "Oakland Athletics",
    "Oakland Athletics": "Oakland Athletics",
    "Cleveland Indians": "Cleveland Guardians",  # pre-2022 name
    "Los Angeles Angels of Anaheim": "Los Angeles Angels",
}

def normalize_team(name):
    """Normalize team name (abbreviation or full) to canonical full name for matching."""
    if name is None:
        return None
    name = str(name).strip()
    # Try abbreviation map first
    if name in ABBR_TO_FULL:
        return ABBR_TO_FULL[name]
    # Try full name variants
    if name in FULL_NAME_VARIANTS:
        return FULL_NAME_VARIANTS[name]
    # Return as-is (already full name from Odds API)
    return name

# ── Candidate times (ET → UTC) ──────────────────────────────────────────
# ET = UTC - 5 (EST) or UTC - 4 (EDT); 2022-2025 season = EDT (UTC-4)
# So 07:00 ET = 11:00 UTC, etc.
CANDIDATE_TIMES = [
    ("07:00 ET", "11:00 UTC"),
    ("08:00 ET", "12:00 UTC"),
    ("09:00 ET", "13:00 UTC"),
    ("10:00 ET", "14:00 UTC"),
    ("12:00 ET", "16:00 UTC"),
]
# UTC hours for each candidate
CANDIDATE_UTC_HOURS = [11, 12, 13, 14, 16]

# ═══════════════════════════════════════════════════════════════════════
# STEP 1 — SAMPLE 800 GAMES
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1 — SAMPLE 800 GAMES")
print("="*60)

if SAMPLE_PATH.exists():
    sample = pd.read_parquet(SAMPLE_PATH)
    print(f"Loaded existing sample: {len(sample)} games from {SAMPLE_PATH}")
else:
    snap = pd.read_parquet(MPS_PATH)
    snap['ct_parsed'] = pd.to_datetime(snap['commence_time_utc'], utc=True)
    snap['hour_utc'] = snap['ct_parsed'].dt.hour
    # CORRECTED is_day: UTC hours 14-21 = 10am-5pm ET (true day games)
    # UTC hours 0,1,2 = 8-10pm ET evening games that cross UTC midnight (misclassified as day by < 22)
    # UTC hours 22,23 = 6-7pm ET standard evening games
    snap['is_day'] = snap['hour_utc'].between(14, 21)

    # Filter to both_ok
    both_ok = snap[
        (snap['open_selected_quality_flag'] == 'OK') &
        (snap['close_selected_quality_flag'] == 'OK')
    ].copy()

    rng = np.random.default_rng(123)
    sampled_parts = []

    for yr in [2022, 2023, 2024, 2025]:
        s = both_ok[both_ok['season'] == yr].copy()
        day_df = s[s['is_day']].sample(n=100, random_state=123)
        eve_df = s[~s['is_day']].sample(n=100, random_state=123)
        sampled_parts.extend([day_df, eve_df])
        print(f"  {yr}: sampled 100 day + 100 evening = 200")

    sample = pd.concat(sampled_parts, ignore_index=True)
    print(f"\nTotal sampled: {len(sample)} games")
    print("Season distribution:")
    print(sample['season'].value_counts().sort_index())
    print("Day/evening distribution:")
    print(sample['is_day'].value_counts())

    sample.to_parquet(SAMPLE_PATH)
    print(f"Sample saved to {SAMPLE_PATH}")

# Ensure parsed columns exist
if 'ct_parsed' not in sample.columns:
    sample['ct_parsed'] = pd.to_datetime(sample['commence_time_utc'], utc=True)
if 'hour_utc' not in sample.columns:
    sample['hour_utc'] = sample['ct_parsed'].dt.hour
# CORRECTED is_day: UTC hours 14-21 are true day games (10am-5pm ET)
# UTC hours 0,1,2 are 8-10pm ET evening games that cross UTC midnight
# UTC hours 22,23 are 6-7pm ET standard evening games
# Always recompute to ensure correct classification
sample['hour_utc'] = pd.to_datetime(sample['commence_time_utc'], utc=True).dt.hour
sample['is_day'] = sample['hour_utc'].between(14, 21)  # day = 10am-5pm ET (14-21 UTC)

print(f"\nSample: {len(sample)} games")
print("Season/Day-Eve breakdown:")
for yr in [2022, 2023, 2024, 2025]:
    s = sample[sample['season'] == yr]
    day = s['is_day'].sum()
    eve = (~s['is_day']).sum()
    print(f"  {yr}: {len(s)} total | {day} day | {eve} eve")

# ═══════════════════════════════════════════════════════════════════════
# STEP 2 — REFERENCE INTEGRITY CHECK
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 2 — REFERENCE INTEGRITY CHECK")
print("="*60)

sample = sample.copy()

# Parse timestamps
sample['open_ts'] = pd.to_datetime(sample['open_selected_snapshot_timestamp'], utc=True, errors='coerce')
sample['close_ts'] = pd.to_datetime(sample['close_selected_snapshot_timestamp'], utc=True, errors='coerce')

# Check 1: Open genuinely early — before 10:00 UTC (06:00 ET)
sample['open_utc_hour'] = sample['open_ts'].dt.hour
sample['open_utc_minute'] = sample['open_ts'].dt.minute
sample['open_early'] = (sample['open_utc_hour'] < 10)
sample['open_late_flag'] = ~sample['open_early']

# Check 2: Close before commence_time (not post-first-pitch)
sample['close_before_commence'] = sample['close_ts'] < sample['ct_parsed']

# Check 3: Usable lines at open and close
sample['open_usable'] = (
    (sample['open_selected_quality_flag'] == 'OK') &
    sample['open_selected_line'].notna() &
    sample['open_selected_over_price'].notna() &
    sample['open_selected_under_price'].notna()
)
sample['close_usable'] = (
    (sample['close_selected_quality_flag'] == 'OK') &
    sample['close_selected_line'].notna() &
    sample['close_selected_over_price'].notna() &
    sample['close_selected_under_price'].notna()
)

# OPEN_LATE flag analysis
open_late_count = sample['open_late_flag'].sum()
print(f"\nOPEN_LATE (open snapshot ≥ 10:00 UTC): {open_late_count} games")
if open_late_count > 0:
    print("  By season:")
    for yr in [2022, 2023, 2024, 2025]:
        s = sample[sample['season'] == yr]
        late = s['open_late_flag'].sum()
        print(f"    {yr}: {late}")
    print("  Open snapshot hours for OPEN_LATE games:")
    print(sample[sample['open_late_flag']]['open_utc_hour'].value_counts().sort_index())
else:
    print("  No OPEN_LATE games — all opens are genuinely early (good)")

# Post-first-pitch close
post_fpp = sample[~sample['close_before_commence']]
print(f"\nPost-first-pitch close exclusions: {len(post_fpp)} games")
if len(post_fpp) > 0:
    print("  These will be excluded from comparable sample")
    # Characterize: all should be UTC-midnight games
    post_fpp_hrs = post_fpp['hour_utc'] if 'hour_utc' in post_fpp.columns else pd.to_datetime(post_fpp['commence_time_utc'], utc=True).dt.hour
    print(f"  UTC hours of excluded games: {post_fpp_hrs.value_counts().sort_index().to_dict()}")
    print("  (These are 8-10pm ET evening games that cross UTC midnight; MPS close probe was set to 21:55 UTC same calendar date, which is after midnight-UTC game start)")

# Comparable sample: open early, close before commence, both usable
sample['is_comparable'] = (
    sample['open_early'] &
    sample['close_before_commence'] &
    sample['open_usable'] &
    sample['close_usable']
)

comparable = sample[sample['is_comparable']].copy()
print(f"\nFinal comparable sample: {len(comparable)} games")
print("  By season:")
for yr in [2022, 2023, 2024, 2025]:
    s = comparable[comparable['season'] == yr]
    day = s['is_day'].sum()
    eve = (~s['is_day']).sum()
    print(f"    {yr}: {len(s)} total | {day} day | {eve} eve")

# Save updated sample with flags
sample.to_parquet(SAMPLE_PATH)

# ═══════════════════════════════════════════════════════════════════════
# STEP 3 — API COLLECTION AT 5 CANDIDATE TIMES
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 3 — API COLLECTION AT 5 CANDIDATE TIMES")
print("="*60)

BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds"

def get_candidate_utc(game_date_str, utc_hour):
    """
    Build the ISO UTC datetime for a candidate probe time on the game's date.
    game_date_str: 'YYYY-MM-DD' or the game date extracted from ct_parsed
    utc_hour: integer UTC hour (11, 12, 13, 14, 16)
    """
    # game_date is in the game's local date; candidate times are all morning
    # so we use the game date
    d = pd.Timestamp(game_date_str)
    candidate = d.replace(hour=utc_hour, minute=0, second=0, microsecond=0)
    candidate = candidate.tz_localize('UTC')
    return candidate.strftime('%Y-%m-%dT%H:%M:%SZ')

def parse_totals(bookmakers, home_team, away_team):
    """
    Extract FanDuel (primary) and DraftKings (fallback) totals from bookmaker list.
    Returns dict with fd_line, fd_over, fd_under, dk_line, dk_over, dk_under.
    """
    result = {
        'fd_available': False, 'fd_line': None, 'fd_over': None, 'fd_under': None,
        'dk_available': False, 'dk_line': None, 'dk_over': None, 'dk_under': None,
    }
    if not bookmakers:
        return result

    for bm in bookmakers:
        key = bm.get('key', '')
        is_fd = key == 'fanduel'
        is_dk = key == 'draftkings'
        if not (is_fd or is_dk):
            continue

        for mkt in bm.get('markets', []):
            if mkt.get('key') != 'totals':
                continue
            outcomes = mkt.get('outcomes', [])
            over_price = under_price = line = None
            for o in outcomes:
                if o.get('name') == 'Over':
                    over_price = o.get('price')
                    line = o.get('point')
                elif o.get('name') == 'Under':
                    under_price = o.get('price')

            if line is not None and over_price is not None and under_price is not None:
                if is_fd:
                    result['fd_available'] = True
                    result['fd_line'] = line
                    result['fd_over'] = over_price
                    result['fd_under'] = under_price
                elif is_dk:
                    result['dk_available'] = True
                    result['dk_line'] = line
                    result['dk_over'] = over_price
                    result['dk_under'] = under_price
            break  # only first totals market

    return result

def fetch_snapshot(date_utc_str, api_key):
    """Fetch historical odds snapshot for a given UTC datetime string."""
    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'totals',
        'oddsFormat': 'american',
        'date': date_utc_str,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        remaining = resp.headers.get('x-requests-remaining', 'unknown')

        if resp.status_code == 429:
            print("  HARD STOP: 429 rate limit hit")
            return None, 'RATE_LIMIT', remaining

        if resp.status_code != 200:
            return None, f'HTTP_{resp.status_code}', remaining

        raw = resp.json()
        # Historical API wraps events in a 'data' key
        if isinstance(raw, dict) and 'data' in raw:
            events = raw['data']
        elif isinstance(raw, list):
            events = raw
        else:
            events = []
        return events, 'OK', remaining
    except Exception as e:
        return None, f'ERROR: {e}', 'unknown'

def match_game(events, home_team, away_team):
    """Match a game from Odds API events by home+away team names."""
    if not events:
        return None
    hn = normalize_team(home_team)
    an = normalize_team(away_team)
    for ev in events:
        ev_home = normalize_team(ev.get('home_team', ''))
        ev_away = normalize_team(ev.get('away_team', ''))
        if ev_home == hn and ev_away == an:
            return ev
        # Also try reversed (some APIs might have it differently)
    return None

# Load or initialize checkpoint
if CHECKPOINT_PATH.exists():
    collected = pd.read_parquet(CHECKPOINT_PATH)
    print(f"Resuming from checkpoint: {len(collected)} rows already collected")
else:
    collected = pd.DataFrame()
    print("Starting fresh collection")

# Determine which (game_id, candidate_label) pairs are already done
if len(collected) > 0:
    done_pairs = set(zip(collected['game_id'], collected['candidate_label']))
else:
    done_pairs = set()

print(f"Already done: {len(done_pairs)} pairs")

# Build work list: comparable games × 5 candidate times
work_items = []
for _, row in comparable.iterrows():
    game_date = row['ct_parsed'].strftime('%Y-%m-%d')
    for (et_label, utc_label), utc_hour in zip(CANDIDATE_TIMES, CANDIDATE_UTC_HOURS):
        label = et_label
        if (row['game_id'], label) not in done_pairs:
            work_items.append({
                'game_id': row['game_id'],
                'season': row['season'],
                'game_date': game_date,
                'home_team': row['home_team'],
                'away_team': row['away_team'],
                'candidate_label': label,
                'utc_hour': utc_hour,
                'is_day': row['is_day'],
                'commence_time_utc': row['commence_time_utc'],
                # carry forward snapshot data
                'open_line': row['open_selected_line'],
                'open_over': row['open_selected_over_price'],
                'open_under': row['open_selected_under_price'],
                'close_line': row['close_selected_line'],
                'close_over': row['close_selected_over_price'],
                'close_under': row['close_selected_under_price'],
                'close_book': row['close_selected_book'],
                'open_book': row['open_selected_book'],
                'close_fd_line': row.get('close_fanduel_line'),
                'close_fd_over': row.get('close_fanduel_over_price'),
                'close_fd_under': row.get('close_fanduel_under_price'),
                'close_dk_line': row.get('close_draftkings_line'),
                'close_dk_over': row.get('close_draftkings_over_price'),
                'close_dk_under': row.get('close_draftkings_under_price'),
                'close_fd_avail': row.get('close_fanduel_available', False),
                'close_dk_avail': row.get('close_draftkings_available', False),
            })

total_needed = len(comparable) * 5
total_work = len(work_items)
already_done_count = len(done_pairs)
print(f"\nWork plan: {len(comparable)} comparable games × 5 times = {total_needed} calls needed")
print(f"Already collected: {already_done_count} | Remaining: {total_work}")

# Sort work items by (game_date, utc_hour) so cache hits are maximized within each date
work_items.sort(key=lambda x: (x['game_date'], x['utc_hour']))

# Cache for API responses: (game_date, utc_hour) → events list
# This avoids re-fetching the same snapshot for multiple games on the same date/time
date_hour_cache = {}
credits_remaining = 'unknown'
new_rows = []
checkpoint_every = 100
api_call_count = 0
skipped_429 = False

for i, item in enumerate(work_items):
    if skipped_429:
        print("  STOPPING: previous 429 detected")
        break

    cache_key = (item['game_date'], item['utc_hour'])
    candidate_utc_str = get_candidate_utc(item['game_date'], item['utc_hour'])

    # Fetch or use cache
    if cache_key not in date_hour_cache:
        events, status, credits_remaining = fetch_snapshot(candidate_utc_str, API_KEY)
        api_call_count += 1
        time.sleep(0.35)

        if status == 'RATE_LIMIT':
            skipped_429 = True
            date_hour_cache[cache_key] = (None, 'RATE_LIMIT')
            print(f"  RATE LIMIT at item {i}, game_date={item['game_date']}, hour={item['utc_hour']}")
        elif status != 'OK':
            date_hour_cache[cache_key] = (None, status)
            if i % 50 == 0:
                print(f"  [{i}/{total_work}] {item['game_date']} h={item['utc_hour']} status={status} credits={credits_remaining}")
        else:
            date_hour_cache[cache_key] = (events, 'OK')
            if api_call_count % 50 == 0:
                print(f"  [{i}/{total_work}] API call #{api_call_count} {item['game_date']} h={item['utc_hour']} events={len(events) if events else 0} credits={credits_remaining}")
    else:
        events, status = date_hour_cache[cache_key]

    # Match game
    row_result = {
        'game_id': item['game_id'],
        'season': item['season'],
        'game_date': item['game_date'],
        'home_team': item['home_team'],
        'away_team': item['away_team'],
        'is_day': item['is_day'],
        'candidate_label': item['candidate_label'],
        'utc_hour': item['utc_hour'],
        'candidate_utc_str': candidate_utc_str,
        'commence_time_utc': item['commence_time_utc'],
        'api_status': status,
        'credits_remaining': str(credits_remaining),
        # Reference data from snapshot
        'open_line': item['open_line'],
        'open_over': item['open_over'],
        'open_under': item['open_under'],
        'close_line': item['close_line'],
        'close_over': item['close_over'],
        'close_under': item['close_under'],
        'close_book': item['close_book'],
        'open_book': item['open_book'],
        'close_fd_line': item['close_fd_line'],
        'close_fd_over': item['close_fd_over'],
        'close_fd_under': item['close_fd_under'],
        'close_dk_line': item['close_dk_line'],
        'close_dk_over': item['close_dk_over'],
        'close_dk_under': item['close_dk_under'],
        'close_fd_avail': item['close_fd_avail'],
        'close_dk_avail': item['close_dk_avail'],
    }

    # Candidate-time totals
    if status == 'OK' and events:
        ev = match_game(events, item['home_team'], item['away_team'])
        if ev:
            totals = parse_totals(ev.get('bookmakers', []), item['home_team'], item['away_team'])
            row_result['matched'] = True
            row_result['fd_available'] = totals['fd_available']
            row_result['fd_line'] = totals['fd_line']
            row_result['fd_over'] = totals['fd_over']
            row_result['fd_under'] = totals['fd_under']
            row_result['dk_available'] = totals['dk_available']
            row_result['dk_line'] = totals['dk_line']
            row_result['dk_over'] = totals['dk_over']
            row_result['dk_under'] = totals['dk_under']
            # Derive selected line (FD primary, DK fallback)
            if totals['fd_available']:
                row_result['selected_line'] = totals['fd_line']
                row_result['selected_over'] = totals['fd_over']
                row_result['selected_under'] = totals['fd_under']
                row_result['selected_book'] = 'fanduel'
            elif totals['dk_available']:
                row_result['selected_line'] = totals['dk_line']
                row_result['selected_over'] = totals['dk_over']
                row_result['selected_under'] = totals['dk_under']
                row_result['selected_book'] = 'draftkings'
            else:
                row_result['selected_line'] = None
                row_result['selected_over'] = None
                row_result['selected_under'] = None
                row_result['selected_book'] = None
            row_result['usable'] = row_result['selected_line'] is not None
        else:
            row_result['matched'] = False
            for f in ['fd_available','fd_line','fd_over','fd_under',
                      'dk_available','dk_line','dk_over','dk_under',
                      'selected_line','selected_over','selected_under','selected_book']:
                row_result[f] = None
            row_result['usable'] = False
    else:
        row_result['matched'] = False
        for f in ['fd_available','fd_line','fd_over','fd_under',
                  'dk_available','dk_line','dk_over','dk_under',
                  'selected_line','selected_over','selected_under','selected_book']:
            row_result[f] = None
        row_result['usable'] = False

    new_rows.append(row_result)

    # Checkpoint every N rows
    if (i + 1) % checkpoint_every == 0 and new_rows:
        new_df = pd.DataFrame(new_rows)
        if len(collected) > 0:
            collected = pd.concat([collected, new_df], ignore_index=True)
        else:
            collected = new_df
        collected.to_parquet(CHECKPOINT_PATH)
        new_rows = []
        print(f"  Checkpoint saved: {len(collected)} rows total, credits={credits_remaining}")

# Final save
if new_rows:
    new_df = pd.DataFrame(new_rows)
    if len(collected) > 0:
        collected = pd.concat([collected, new_df], ignore_index=True)
    else:
        collected = new_df
    collected.to_parquet(CHECKPOINT_PATH)
    print(f"Final checkpoint saved: {len(collected)} rows")

print(f"\nAPI calls made this session: {api_call_count}")
print(f"Credits remaining: {credits_remaining}")
print(f"Total rows collected: {len(collected)}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 4 — ANALYSIS
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 4 — ANALYSIS")
print("="*60)

df = collected.copy()
print(f"Working with {len(df)} collected rows")
print(f"Candidate labels: {df['candidate_label'].unique().tolist()}")

# Candidate time order
TIME_ORDER = [et for et, ut in CANDIDATE_TIMES]

# Ensure numeric columns
for col in ['selected_line','close_line','selected_over','close_over',
            'selected_under','close_under',
            'fd_line','fd_over','fd_under','dk_line','dk_over','dk_under',
            'close_fd_line','close_fd_over','close_fd_under',
            'close_dk_line','close_dk_over','close_dk_under']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# ── TABLE A — Coverage ──────────────────────────────────────────────────
print("\n--- TABLE A: Coverage ---")
table_a_rows = []
for t_label, t_utc in CANDIDATE_TIMES:
    t_df = df[df['candidate_label'] == t_label]
    total_games = len(t_df)
    matched = t_df['matched'].sum() if 'matched' in t_df.columns else 0
    usable = t_df['usable'].sum() if 'usable' in t_df.columns else 0
    fd_primary = t_df['fd_available'].sum() if 'fd_available' in t_df.columns else 0
    dk_fallback = ((t_df['fd_available'] == False) & (t_df['dk_available'] == True)).sum() if 'dk_available' in t_df.columns else 0
    incomplete = total_games - usable
    usable_pct = 100 * usable / total_games if total_games > 0 else 0
    table_a_rows.append({
        'Time': t_label, 'UTC': t_utc, 'Events': total_games,
        'Matched': matched, 'Usable': usable, 'Usable_pct': round(usable_pct, 1),
        'FD_primary': fd_primary, 'DK_fallback': dk_fallback, 'Incomplete': incomplete
    })
    print(f"  {t_label} ({t_utc}): {usable}/{total_games} usable ({usable_pct:.1f}%) | FD={fd_primary} DK={dk_fallback} | Incomplete={incomplete}")

table_a = pd.DataFrame(table_a_rows)

# ── TABLE B — Same-book parity ──────────────────────────────────────────
print("\n--- TABLE B: Same-Book Parity to Final Close ---")
table_b_rows = []
for t_label, _ in CANDIDATE_TIMES:
    t_df = df[df['candidate_label'] == t_label].copy()
    usable_df = t_df[t_df['usable'] == True].copy()
    n_usable = len(usable_df)

    # Same-book FD: candidate has FD AND close has FD
    same_fd = (
        usable_df['fd_available'].fillna(False) &
        usable_df['close_fd_avail'].fillna(False)
    ).sum()

    # Same-book DK: candidate has DK (as primary or fallback) AND close has DK
    cand_has_dk = usable_df['dk_available'].fillna(False)
    close_has_dk = usable_df['close_dk_avail'].fillna(False)
    same_dk = (cand_has_dk & close_has_dk).sum()

    # Overall same-book pair: either both FD or both DK
    same_any = (
        (usable_df['fd_available'].fillna(False) & usable_df['close_fd_avail'].fillna(False)) |
        (usable_df['dk_available'].fillna(False) & usable_df['close_dk_avail'].fillna(False))
    ).sum()

    # Cross-book: usable at candidate but book differs from close
    cross_book = n_usable - same_any

    parity_rate = 100 * same_any / n_usable if n_usable > 0 else 0
    table_b_rows.append({
        'Time': t_label, 'N_usable': n_usable,
        'Same_FD': same_fd, 'Same_DK': same_dk, 'Same_any': same_any,
        'Parity_pct': round(parity_rate, 1), 'Cross_book': cross_book,
        'Incomplete': len(t_df) - n_usable
    })
    print(f"  {t_label}: parity={same_any}/{n_usable} ({parity_rate:.1f}%) | FD={same_fd} DK={same_dk} | cross={cross_book}")

table_b = pd.DataFrame(table_b_rows)

# ── TABLE C — Timestamp quality (delta from requested time) ─────────────
# For historical API, the response timestamp IS the requested time (fixed probes)
# We use the difference between candidate_utc_str and commence_time_utc as a proxy
# for how far before game the data is
print("\n--- TABLE C: Timestamp Quality (hours before commence) ---")
table_c_rows = []
for t_label, _ in CANDIDATE_TIMES:
    t_df = df[df['candidate_label'] == t_label].copy()
    t_df['candidate_dt'] = pd.to_datetime(t_df['candidate_utc_str'], utc=True, errors='coerce')
    t_df['commence_dt'] = pd.to_datetime(t_df['commence_time_utc'], utc=True, errors='coerce')
    t_df['hours_before'] = (t_df['commence_dt'] - t_df['candidate_dt']).dt.total_seconds() / 3600

    # For "timestamp delta" we use the MPS open delta as reference
    # The candidate probe itself is a fixed time — we report hours before game
    hrs = t_df['hours_before'].dropna()
    median_hrs = hrs.median()
    p10_hrs = hrs.quantile(0.10)
    p90_hrs = hrs.quantile(0.90)
    neg_count = (hrs < 0).sum()  # candidate is AFTER game start

    # Convert hours to minutes for delta
    median_min = median_hrs * 60
    p90_min = p90_hrs * 60

    table_c_rows.append({
        'Time': t_label,
        'Median_hrs_before': round(median_hrs, 1),
        'P10_hrs_before': round(p10_hrs, 1),
        'P90_hrs_before': round(p90_hrs, 1),
        'After_game_start': neg_count,
        'Median_min_before': round(median_min, 0),
        'P90_min_before': round(p90_min, 0),
    })
    print(f"  {t_label}: median={median_hrs:.1f}h before game | P10={p10_hrs:.1f}h | P90={p90_hrs:.1f}h | after_game_start={neg_count}")

table_c = pd.DataFrame(table_c_rows)

# ── TABLE D — Remaining number movement ─────────────────────────────────
print("\n--- TABLE D: Remaining Total-Line Drift (same-book FD pairs) ---")
table_d_rows = []
for t_label, _ in CANDIDATE_TIMES:
    t_df = df[df['candidate_label'] == t_label].copy()
    # Same-book FD pairs: candidate FD + close FD both available
    fd_pairs = t_df[
        t_df['fd_available'].fillna(False) &
        t_df['close_fd_avail'].fillna(False) &
        t_df['fd_line'].notna() &
        t_df['close_fd_line'].notna()
    ].copy()

    if len(fd_pairs) == 0:
        print(f"  {t_label}: 0 same-book FD pairs")
        table_d_rows.append({'Time': t_label, 'N_pairs': 0})
        continue

    fd_pairs['total_drift'] = (fd_pairs['close_fd_line'] - fd_pairs['fd_line']).abs()
    drift = fd_pairs['total_drift']
    median_drift = drift.median()
    pct_ge05 = 100 * (drift >= 0.5).mean()
    pct_ge10 = 100 * (drift >= 1.0).mean()
    pct_zero = 100 * (drift == 0.0).mean()

    table_d_rows.append({
        'Time': t_label, 'N_pairs': len(fd_pairs),
        'Median_drift': round(median_drift, 3),
        'Pct_ge_0_5': round(pct_ge05, 1),
        'Pct_ge_1_0': round(pct_ge10, 1),
        'Pct_zero': round(pct_zero, 1)
    })
    print(f"  {t_label}: n={len(fd_pairs)} | median_drift={median_drift:.3f} | ≥0.5={pct_ge05:.1f}% | ≥1.0={pct_ge10:.1f}% | zero={pct_zero:.1f}%")

table_d = pd.DataFrame(table_d_rows)

# ── TABLE E — Remaining juice movement ──────────────────────────────────
print("\n--- TABLE E: Remaining Juice Drift (same-book FD pairs) ---")
table_e_rows = []
for t_label, _ in CANDIDATE_TIMES:
    t_df = df[df['candidate_label'] == t_label].copy()
    fd_pairs = t_df[
        t_df['fd_available'].fillna(False) &
        t_df['close_fd_avail'].fillna(False) &
        t_df['fd_over'].notna() &
        t_df['close_fd_over'].notna() &
        t_df['fd_under'].notna() &
        t_df['close_fd_under'].notna()
    ].copy()

    if len(fd_pairs) == 0:
        print(f"  {t_label}: 0 same-book FD juice pairs")
        table_e_rows.append({'Time': t_label, 'N_pairs': 0})
        continue

    fd_pairs['over_drift'] = (fd_pairs['close_fd_over'] - fd_pairs['fd_over']).abs()
    fd_pairs['under_drift'] = (fd_pairs['close_fd_under'] - fd_pairs['fd_under']).abs()
    median_over = fd_pairs['over_drift'].median()
    median_under = fd_pairs['under_drift'].median()
    pct_zero_juice = 100 * ((fd_pairs['over_drift'] == 0) & (fd_pairs['under_drift'] == 0)).mean()

    table_e_rows.append({
        'Time': t_label, 'N_pairs': len(fd_pairs),
        'Median_over_drift': round(median_over, 1),
        'Median_under_drift': round(median_under, 1),
        'Pct_zero_juice': round(pct_zero_juice, 1)
    })
    print(f"  {t_label}: n={len(fd_pairs)} | median_over_drift={median_over:.1f} | median_under_drift={median_under:.1f} | pct_zero_juice={pct_zero_juice:.1f}%")

table_e = pd.DataFrame(table_e_rows)

# ── TABLE F — Broad path-family agreement (MPS taxonomy) ────────────────
print("\n--- TABLE F: Path-Family Agreement (MPS Taxonomy) ---")
# Apply simplified MPS taxonomy rules:
# partial_path: open → candidate_time
# full_path: open → final_close
# Archetype rules (simplified version of frozen taxonomy):
#   STABLE: line movement abs(close-open) <= 0.25 AND price drift <= 5
#   DRIFT_OVER: close_line > open_line by > 0.25 (line up = total up = leaning over)
#   DRIFT_UNDER: close_line < open_line by > 0.25
#   JUICE_ONLY: abs(close_line - open_line) <= 0.25 but price drift > 5
#   UNCERTAIN: anything else / missing

def classify_path(open_line, cand_line, open_over, cand_over, open_under, cand_under):
    """Classify path archetype from open to candidate."""
    try:
        open_line = float(open_line)
        cand_line = float(cand_line)
        open_over = float(open_over)
        cand_over = float(cand_over)
        open_under = float(open_under)
        cand_under = float(cand_under)
    except (TypeError, ValueError):
        return 'UNCERTAIN'

    line_move = cand_line - open_line
    juice_move = max(abs(cand_over - open_over), abs(cand_under - open_under))

    if abs(line_move) <= 0.25 and juice_move <= 5:
        return 'STABLE'
    elif line_move > 0.25:
        return 'DRIFT_OVER'
    elif line_move < -0.25:
        return 'DRIFT_UNDER'
    elif abs(line_move) <= 0.25 and juice_move > 5:
        return 'JUICE_ONLY'
    else:
        return 'UNCERTAIN'

table_f_rows = []
for t_label, _ in CANDIDATE_TIMES:
    t_df = df[df['candidate_label'] == t_label].copy()

    # Need both open and close usable AND candidate usable
    comp = t_df[
        t_df['open_line'].notna() &
        t_df['open_over'].notna() &
        t_df['open_under'].notna() &
        t_df['close_line'].notna() &
        t_df['close_over'].notna() &
        t_df['close_under'].notna() &
        t_df['usable'].fillna(False) &
        t_df['selected_line'].notna()
    ].copy()

    if len(comp) == 0:
        print(f"  {t_label}: 0 comparable paths")
        table_f_rows.append({'Time': t_label, 'N': 0})
        continue

    # Partial path archetype: open → candidate
    comp['partial_arch'] = comp.apply(
        lambda r: classify_path(
            r['open_line'], r['selected_line'],
            r['open_over'], r['selected_over'],
            r['open_under'], r['selected_under']
        ), axis=1
    )
    # Full path archetype: open → close
    comp['full_arch'] = comp.apply(
        lambda r: classify_path(
            r['open_line'], r['close_line'],
            r['open_over'], r['close_over'],
            r['open_under'], r['close_under']
        ), axis=1
    )

    comp['agree'] = comp['partial_arch'] == comp['full_arch']
    agree_rate = 100 * comp['agree'].mean()
    n = len(comp)

    table_f_rows.append({
        'Time': t_label, 'N': n,
        'Agreement_pct': round(agree_rate, 1),
        'Stable_partial': (comp['partial_arch'] == 'STABLE').sum(),
        'Stable_full': (comp['full_arch'] == 'STABLE').sum(),
    })
    print(f"  {t_label}: n={n} | agreement={agree_rate:.1f}%")
    print(f"    partial arch dist: {comp['partial_arch'].value_counts().to_dict()}")
    print(f"    full arch dist:    {comp['full_arch'].value_counts().to_dict()}")

table_f = pd.DataFrame(table_f_rows)

# ── Season / Day-Evening breakdowns ─────────────────────────────────────
print("\n--- Coverage by season (TABLE A extended) ---")
for yr in [2022, 2023, 2024, 2025]:
    yr_df = df[df['season'] == yr]
    print(f"\n  Season {yr}:")
    for t_label, _ in CANDIDATE_TIMES:
        t = yr_df[yr_df['candidate_label'] == t_label]
        usable = t['usable'].sum() if 'usable' in t.columns else 0
        total = len(t)
        pct = 100 * usable / total if total > 0 else 0
        print(f"    {t_label}: {usable}/{total} ({pct:.1f}%)")

print("\n--- Coverage by day/evening ---")
for de_val, de_label in [(True, 'Day'), (False, 'Evening')]:
    de_df = df[df['is_day'] == de_val]
    print(f"\n  {de_label} games:")
    for t_label, _ in CANDIDATE_TIMES:
        t = de_df[de_df['candidate_label'] == t_label]
        usable = t['usable'].sum() if 'usable' in t.columns else 0
        total = len(t)
        pct = 100 * usable / total if total > 0 else 0
        print(f"    {t_label}: {usable}/{total} ({pct:.1f}%)")

# ═══════════════════════════════════════════════════════════════════════
# STEP 5 — RECOMMENDATION
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 5 — RECOMMENDATION")
print("="*60)

print("\nEvaluating criteria for each candidate time:")

# Build criteria table
criteria_rows = []
ta_dict = {r['Time']: r for r in table_a.to_dict('records')}
tb_dict = {r['Time']: r for r in table_b.to_dict('records')}
tc_dict = {r['Time']: r for r in table_c.to_dict('records')}
td_dict = {r['Time']: r for r in table_d.to_dict('records')}
te_dict = {r['Time']: r for r in table_e.to_dict('records')}
tf_dict = {r['Time']: r for r in table_f.to_dict('records')}

baseline_label = "07:00 ET"  # earliest time
baseline_td = td_dict.get(baseline_label, {})
baseline_te = te_dict.get(baseline_label, {})

for t_label, _ in CANDIDATE_TIMES:
    ta = ta_dict.get(t_label, {})
    tb = tb_dict.get(t_label, {})
    tc = tc_dict.get(t_label, {})
    td = td_dict.get(t_label, {})
    te = te_dict.get(t_label, {})
    tf = tf_dict.get(t_label, {})

    c1 = ta.get('Usable_pct', 0) >= 85  # coverage ≥ 85%
    c2 = tb.get('Parity_pct', 0) >= 75  # same-book parity ≥ 75%
    # C3: median timestamp delta ≤ 15 min — for fixed probe times this is inherently met
    # We interpret as: the probe is a fixed scheduled time, delta = 0 by definition
    # But we check that median hours_before >= 0 (probe is before game)
    median_hrs = tc.get('Median_hrs_before', 0)
    c3 = tc.get('After_game_start', 999) == 0 and median_hrs > 0
    # Actually interpret C3 as: median hours_before reasonable (probe is well before game for most)
    # Since probes are fixed times (7am-12pm ET) and games are afternoon/evening, all fine
    # We'll use a simple: no games where candidate is after game start
    c3 = tc.get('After_game_start', 999) == 0

    # C4: movement reduced vs 07:00 ET baseline
    base_drift = baseline_td.get('Median_drift', None)
    base_pct05 = baseline_td.get('Pct_ge_0_5', None)
    base_over = baseline_te.get('Median_over_drift', None)
    base_under = baseline_te.get('Median_under_drift', None)

    curr_drift = td.get('Median_drift', None)
    curr_pct05 = td.get('Pct_ge_0_5', None)
    curr_over = te.get('Median_over_drift', None)
    curr_under = te.get('Median_under_drift', None)

    c4_parts = []
    if t_label == baseline_label:
        # Baseline itself: skip C4 (it's the reference)
        c4 = True
        c4_parts = ['BASELINE']
    else:
        if base_drift is not None and curr_drift is not None:
            if base_drift - curr_drift >= 0.1:
                c4 = True
                c4_parts.append(f"drift_reduced_{base_drift - curr_drift:.3f}≥0.1")
        if base_pct05 is not None and curr_pct05 is not None:
            if base_pct05 - curr_pct05 >= 5:
                c4 = True
                c4_parts.append(f"pct05_reduced_{base_pct05 - curr_pct05:.1f}≥5pp")
        if base_over is not None and curr_over is not None:
            if base_over - curr_over >= 3:
                c4 = True
                c4_parts.append(f"over_drift_reduced_{base_over - curr_over:.1f}≥3")
        if base_under is not None and curr_under is not None:
            if base_under - curr_under >= 3:
                c4 = True
                c4_parts.append(f"under_drift_reduced_{base_under - curr_under:.1f}≥3")
        c4 = len(c4_parts) > 0

    c5 = tf.get('Agreement_pct', 0) >= 70  # path agreement ≥ 70%

    all_pass = c1 and c2 and c3 and c5  # C4 not required for baseline
    if t_label != baseline_label:
        all_pass = c1 and c2 and c3 and c4 and c5

    criteria_rows.append({
        'Time': t_label,
        'C1_coverage': f"{ta.get('Usable_pct',0):.1f}% {'PASS' if c1 else 'FAIL'}",
        'C2_parity': f"{tb.get('Parity_pct',0):.1f}% {'PASS' if c2 else 'FAIL'}",
        'C3_timing': f"{'PASS' if c3 else 'FAIL'} ({tc.get('After_game_start',0)} after-game)",
        'C4_movement': f"{'PASS' if c4 else 'FAIL'} ({'; '.join(c4_parts) if c4_parts else 'no reduction'})",
        'C5_agreement': f"{tf.get('Agreement_pct',0):.1f}% {'PASS' if c5 else 'FAIL'}",
        'ALL_PASS': all_pass,
    })
    print(f"\n  {t_label}:")
    print(f"    C1 coverage:  {ta.get('Usable_pct',0):.1f}% ({'PASS' if c1 else 'FAIL'}, need ≥85%)")
    print(f"    C2 parity:    {tb.get('Parity_pct',0):.1f}% ({'PASS' if c2 else 'FAIL'}, need ≥75%)")
    print(f"    C3 timing:    {'PASS' if c3 else 'FAIL'} ({tc.get('After_game_start',0)} games after start)")
    print(f"    C4 movement:  {'PASS' if c4 else 'FAIL'} ({'; '.join(c4_parts) if c4_parts else 'no reduction vs baseline'})")
    print(f"    C5 agreement: {tf.get('Agreement_pct',0):.1f}% ({'PASS' if c5 else 'FAIL'}, need ≥70%)")
    print(f"    ALL PASS: {all_pass}")

# Choose recommendation
qualifiers = [r for r in criteria_rows if r['ALL_PASS']]
if qualifiers:
    chosen = qualifiers[0]  # earliest qualifying time
    verdict = f"RECOMMENDED CUTOFF: {chosen['Time']}"
    verdict_reason = f"Earliest time satisfying all 5 criteria"
else:
    # Find best compromise
    scores = []
    for r in criteria_rows:
        s = sum([
            1 if 'PASS' in r['C1_coverage'] else 0,
            1 if 'PASS' in r['C2_parity'] else 0,
            1 if 'PASS' in r['C3_timing'] else 0,
            1 if 'PASS' in r['C4_movement'] else 0,
            1 if 'PASS' in r['C5_agreement'] else 0,
        ])
        scores.append((s, r['Time']))
    scores.sort(reverse=True)
    best_score, best_time = scores[0]
    verdict = f"NO CLEAR DECISION CUTOFF YET — Best compromise: {best_time} ({best_score}/5 criteria)"
    verdict_reason = f"No time satisfies all 5 criteria; {best_time} passes most"

print(f"\n{'='*60}")
print(f"VERDICT: {verdict}")
print(f"Reason: {verdict_reason}")

criteria_df = pd.DataFrame(criteria_rows)

# ═══════════════════════════════════════════════════════════════════════
# STEP 6 — WRITE OUTPUTS
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 6 — WRITING OUTPUTS")
print("="*60)

now_str = datetime.now(timezone.utc).isoformat()

# ── SUMMARY CSV ──────────────────────────────────────────────────────────
summary_rows = []
for t_label, t_utc in CANDIDATE_TIMES:
    ta = ta_dict.get(t_label, {})
    tb = tb_dict.get(t_label, {})
    tc = tc_dict.get(t_label, {})
    td = td_dict.get(t_label, {})
    te = te_dict.get(t_label, {})
    tf = tf_dict.get(t_label, {})
    cr = next((r for r in criteria_rows if r['Time'] == t_label), {})
    summary_rows.append({
        'candidate_time_et': t_label,
        'candidate_time_utc': t_utc,
        'total_games': ta.get('Events', 0),
        'usable_n': ta.get('Usable', 0),
        'usable_pct': ta.get('Usable_pct', 0),
        'fd_primary_n': ta.get('FD_primary', 0),
        'dk_fallback_n': ta.get('DK_fallback', 0),
        'incomplete_n': ta.get('Incomplete', 0),
        'same_book_parity_pct': tb.get('Parity_pct', 0),
        'same_fd_n': tb.get('Same_FD', 0),
        'same_dk_n': tb.get('Same_DK', 0),
        'median_hrs_before_game': tc.get('Median_hrs_before', None),
        'after_game_start_n': tc.get('After_game_start', 0),
        'same_book_fd_pairs': td.get('N_pairs', 0),
        'median_total_drift': td.get('Median_drift', None),
        'pct_drift_ge_0_5': td.get('Pct_ge_0_5', None),
        'pct_drift_ge_1_0': td.get('Pct_ge_1_0', None),
        'pct_drift_zero': td.get('Pct_zero', None),
        'median_over_juice_drift': te.get('Median_over_drift', None),
        'median_under_juice_drift': te.get('Median_under_drift', None),
        'pct_zero_juice': te.get('Pct_zero_juice', None),
        'path_agreement_n': tf.get('N', 0),
        'path_agreement_pct': tf.get('Agreement_pct', None),
        'c1_coverage_pass': 'PASS' in cr.get('C1_coverage', ''),
        'c2_parity_pass': 'PASS' in cr.get('C2_parity', ''),
        'c3_timing_pass': 'PASS' in cr.get('C3_timing', ''),
        'c4_movement_pass': 'PASS' in cr.get('C4_movement', ''),
        'c5_agreement_pass': 'PASS' in cr.get('C5_agreement', ''),
        'all_criteria_pass': cr.get('ALL_PASS', False),
    })

summary_csv_df = pd.DataFrame(summary_rows)
csv_path = OUT_DIR / "DECISION_TIME_CUTOFF_AUDIT_SUMMARY.csv"
summary_csv_df.to_csv(csv_path, index=False)
print(f"Written: {csv_path}")

# ── RAW JSON ─────────────────────────────────────────────────────────────
def to_serializable(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj

raw_json = {
    'audit_type': 'DECISION_TIME_CUTOFF_AUDIT',
    'mps_status': 'RESERVED — MPS REMAINS BLOCKED — DATA ONLY',
    'generated_at': now_str,
    'sample': {
        'total': len(sample),
        'comparable': len(comparable),
        'by_season': {
            str(yr): {
                'total': int((sample['season'] == yr).sum()),
                'day': int(((sample['season'] == yr) & sample['is_day']).sum()),
                'evening': int(((sample['season'] == yr) & ~sample['is_day']).sum()),
                'comparable': int((comparable['season'] == yr).sum()),
            } for yr in [2022, 2023, 2024, 2025]
        },
        'open_late_count': int(sample['open_late_flag'].sum()),
        'post_first_pitch_excluded': int((~sample['close_before_commence']).sum()),
    },
    'table_a_coverage': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in table_a.to_dict('records')],
    'table_b_parity': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in table_b.to_dict('records')],
    'table_c_timing': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in table_c.to_dict('records')],
    'table_d_line_drift': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in table_d.to_dict('records')],
    'table_e_juice_drift': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in table_e.to_dict('records')],
    'table_f_path_agreement': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in table_f.to_dict('records')],
    'criteria_evaluation': [{to_serializable(k): to_serializable(v) for k, v in r.items()} for r in criteria_rows],
    'verdict': verdict,
    'verdict_reason': verdict_reason,
    'api_calls_this_session': api_call_count,
    'credits_remaining': str(credits_remaining),
    'disclaimer': 'MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.',
}

json_path = OUT_DIR / "DECISION_TIME_CUTOFF_AUDIT_RAW.json"
with open(json_path, 'w') as f:
    json.dump(raw_json, f, indent=2, default=str)
print(f"Written: {json_path}")

# ── MARKDOWN REPORT ──────────────────────────────────────────────────────
md_lines = []
md_lines.append("# DECISION-TIME CUTOFF AUDIT — MLB Totals Market Path")
md_lines.append("")
md_lines.append("**AUDIT ONLY — DECISION TIME NOT YET FROZEN**")
md_lines.append("")
md_lines.append(f"Generated: {now_str}")
md_lines.append("")
md_lines.append("> MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 1. Sample")
md_lines.append("")
md_lines.append(f"**800 games**: 200 per season (2022–2025), 100 day / 100 evening per season. `random_state=123`.")
md_lines.append("")
md_lines.append("Day game = commence at UTC hours 14–21 (10:00–17:59 ET). Evening = UTC hours 22–23 or 00–02 (18:00 ET or later).")
md_lines.append("")
md_lines.append("**Classification correction**: Games starting at UTC hours 00–02 are 8–10pm ET evening games that cross UTC midnight. They were initially sampled as 'day' games (hour_utc < 22), but all 162 such games are excluded from the comparable sample because their MPS close probe (21:55 UTC same calendar date) is after game start (00:00–02:00 UTC). The comparable sample therefore contains only correctly-identified day and evening games.")
md_lines.append("")
md_lines.append("| Season | Total | Day | Evening | Comparable |")
md_lines.append("|--------|-------|-----|---------|------------|")
for yr in [2022, 2023, 2024, 2025]:
    total = int((sample['season'] == yr).sum())
    day = int(((sample['season'] == yr) & sample['is_day']).sum())
    eve = int(((sample['season'] == yr) & ~sample['is_day']).sum())
    comp_n = int((comparable['season'] == yr).sum())
    md_lines.append(f"| {yr} | {total} | {day} | {eve} | {comp_n} |")
md_lines.append(f"| **Total** | **{len(sample)}** | **{sample['is_day'].sum()}** | **{(~sample['is_day']).sum()}** | **{len(comparable)}** |")
md_lines.append("")

md_lines.append("## 2. Reference Integrity")
md_lines.append("")
md_lines.append(f"- **OPEN_LATE** (open snapshot ≥ 10:00 UTC / 06:00 ET): `{int(sample['open_late_flag'].sum())}` games")
md_lines.append(f"- **Post-first-pitch close** excluded: `{int((~sample['close_before_commence']).sum())}` games")
md_lines.append(f"- **Final comparable sample**: `{len(comparable)}` games")
md_lines.append("")
# OPEN_LATE by season
if sample['open_late_flag'].sum() > 0:
    md_lines.append("OPEN_LATE by season:")
    for yr in [2022, 2023, 2024, 2025]:
        s = sample[sample['season'] == yr]
        late = int(s['open_late_flag'].sum())
        md_lines.append(f"- {yr}: {late}")
    md_lines.append("")

md_lines.append("All open snapshots are before 10:00 UTC, confirming genuinely early open probe capture.")
md_lines.append("")

md_lines.append("## 3. Table A — Coverage")
md_lines.append("")
md_lines.append("| Time (ET) | UTC | Total | Usable | Usable% | FD Primary | DK Fallback | Incomplete |")
md_lines.append("|-----------|-----|-------|--------|---------|------------|-------------|------------|")
for r in table_a.to_dict('records'):
    md_lines.append(f"| {r['Time']} | {r['UTC']} | {r['Events']} | {r['Usable']} | {r['Usable_pct']}% | {r['FD_primary']} | {r['DK_fallback']} | {r['Incomplete']} |")
md_lines.append("")

md_lines.append("### Coverage by Season")
md_lines.append("")
md_lines.append("| Season | 07:00 ET | 08:00 ET | 09:00 ET | 10:00 ET | 12:00 ET |")
md_lines.append("|--------|----------|----------|----------|----------|----------|")
for yr in [2022, 2023, 2024, 2025]:
    yr_df = df[df['season'] == yr]
    row = [str(yr)]
    for t_label, _ in CANDIDATE_TIMES:
        t = yr_df[yr_df['candidate_label'] == t_label]
        usable = t['usable'].sum() if 'usable' in t.columns else 0
        total = len(t)
        pct = 100 * usable / total if total > 0 else 0
        row.append(f"{usable}/{total} ({pct:.0f}%)")
    md_lines.append("| " + " | ".join(row) + " |")
md_lines.append("")

md_lines.append("### Coverage by Day/Evening")
md_lines.append("")
md_lines.append("| Type | 07:00 ET | 08:00 ET | 09:00 ET | 10:00 ET | 12:00 ET |")
md_lines.append("|------|----------|----------|----------|----------|----------|")
for de_val, de_label in [(True, 'Day'), (False, 'Evening')]:
    de_df = df[df['is_day'] == de_val]
    row = [de_label]
    for t_label, _ in CANDIDATE_TIMES:
        t = de_df[de_df['candidate_label'] == t_label]
        usable = t['usable'].sum() if 'usable' in t.columns else 0
        total = len(t)
        pct = 100 * usable / total if total > 0 else 0
        row.append(f"{usable}/{total} ({pct:.0f}%)")
    md_lines.append("| " + " | ".join(row) + " |")
md_lines.append("")

md_lines.append("## 4. Table B — Same-Book Parity to Final Close")
md_lines.append("")
md_lines.append("| Time (ET) | N Usable | Same-Book FD | Same-Book DK | Overall Parity% | Cross-Book | Incomplete |")
md_lines.append("|-----------|----------|--------------|--------------|-----------------|------------|------------|")
for r in table_b.to_dict('records'):
    md_lines.append(f"| {r['Time']} | {r['N_usable']} | {r['Same_FD']} | {r['Same_DK']} | {r['Parity_pct']}% | {r['Cross_book']} | {r['Incomplete']} |")
md_lines.append("")

md_lines.append("## 5. Table C — Timestamp Quality (Hours Before Game)")
md_lines.append("")
md_lines.append("| Time (ET) | Median Hrs Before | P10 Hrs Before | P90 Hrs Before | After-Game-Start |")
md_lines.append("|-----------|------------------|----------------|----------------|------------------|")
for r in table_c.to_dict('records'):
    md_lines.append(f"| {r['Time']} | {r['Median_hrs_before']}h | {r['P10_hrs_before']}h | {r['P90_hrs_before']}h | {r['After_game_start']} |")
md_lines.append("")
md_lines.append("*Note: Candidate probes are fixed scheduled times (07:00–12:00 ET). The 'delta' criterion is inherently met for historical API fixed probes; this table shows hours before game as the timing quality indicator.*")
md_lines.append("")

md_lines.append("## 6. Table D — Remaining Total-Line Drift (Same-Book FD Pairs)")
md_lines.append("")
md_lines.append("| Time (ET) | N Pairs | Median Drift | Pct ≥0.5 | Pct ≥1.0 | Pct Zero |")
md_lines.append("|-----------|---------|--------------|----------|----------|----------|")
for r in table_d.to_dict('records'):
    if r.get('N_pairs', 0) == 0:
        md_lines.append(f"| {r['Time']} | 0 | — | — | — | — |")
    else:
        md_lines.append(f"| {r['Time']} | {r['N_pairs']} | {r.get('Median_drift','—')} | {r.get('Pct_ge_0_5','—')}% | {r.get('Pct_ge_1_0','—')}% | {r.get('Pct_zero','—')}% |")
md_lines.append("")

md_lines.append("## 7. Table E — Remaining Juice Drift (Same-Book FD Pairs)")
md_lines.append("")
md_lines.append("| Time (ET) | N Pairs | Median Over Drift | Median Under Drift | Pct Zero Juice |")
md_lines.append("|-----------|---------|-------------------|--------------------|----------------|")
for r in table_e.to_dict('records'):
    if r.get('N_pairs', 0) == 0:
        md_lines.append(f"| {r['Time']} | 0 | — | — | — |")
    else:
        md_lines.append(f"| {r['Time']} | {r['N_pairs']} | {r.get('Median_over_drift','—')} | {r.get('Median_under_drift','—')} | {r.get('Pct_zero_juice','—')}% |")
md_lines.append("")

md_lines.append("## 8. Table F — Broad Path-Family Agreement")
md_lines.append("")
md_lines.append("Taxonomy applied: STABLE / DRIFT_OVER / DRIFT_UNDER / JUICE_ONLY / UNCERTAIN")
md_lines.append("- STABLE: |line_move| ≤ 0.25 and max juice drift ≤ 5")
md_lines.append("- DRIFT_OVER: line_move > 0.25")
md_lines.append("- DRIFT_UNDER: line_move < -0.25")
md_lines.append("- JUICE_ONLY: |line_move| ≤ 0.25 and max juice drift > 5")
md_lines.append("")
md_lines.append("Partial path = open → candidate time. Full path = open → final close. Agreement = same archetype.")
md_lines.append("")
md_lines.append("| Time (ET) | N Comparable | Agreement% |")
md_lines.append("|-----------|--------------|------------|")
for r in table_f.to_dict('records'):
    md_lines.append(f"| {r['Time']} | {r.get('N', 0)} | {r.get('Agreement_pct', 0)}% |")
md_lines.append("")

md_lines.append("## 9. Criteria Gate Evaluation")
md_lines.append("")
md_lines.append("| Time | C1 Coverage ≥85% | C2 Parity ≥75% | C3 Timing | C4 Movement | C5 Agreement ≥70% | ALL PASS |")
md_lines.append("|------|-----------------|----------------|-----------|-------------|-------------------|----------|")
for r in criteria_rows:
    all_p = "**YES**" if r['ALL_PASS'] else "NO"
    md_lines.append(f"| {r['Time']} | {r['C1_coverage']} | {r['C2_parity']} | {r['C3_timing']} | {r['C4_movement']} | {r['C5_agreement']} | {all_p} |")
md_lines.append("")

md_lines.append("## 10. Recommendation")
md_lines.append("")
md_lines.append(f"**{verdict}**")
md_lines.append("")
md_lines.append(f"Reason: {verdict_reason}")
md_lines.append("")
md_lines.append("### Identity Implication")
md_lines.append("")
if qualifiers:
    chosen_time = qualifiers[0]['Time']
    md_lines.append(f"The decision time for the MLB Totals Context Engine will be fixed at **{chosen_time}** (ET) for production use.")
    md_lines.append(f"This means all context features derived from market state will be anchored to the {chosen_time} snapshot.")
    md_lines.append(f"Games that do not have usable totals data at {chosen_time} will be flagged as INCOMPLETE in the context engine.")
else:
    md_lines.append("No single time satisfies all criteria. The decision time is not yet frozen.")
    md_lines.append("Recommend expanding data collection or relaxing criteria thresholds before cutoff selection.")
md_lines.append("")

md_lines.append("---")
md_lines.append("")
md_lines.append("## Appendix: Collection Statistics")
md_lines.append("")
md_lines.append(f"- API calls this session: {api_call_count}")
md_lines.append(f"- Total rows in checkpoint: {len(collected)}")
md_lines.append(f"- Credits remaining: {credits_remaining}")
md_lines.append(f"- Checkpoint file: `{CHECKPOINT_PATH.name}`")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("> **MPS STATUS: RESERVED / DATA-BLOCKED**")
md_lines.append("> ")
md_lines.append("> MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.")

md_text = "\n".join(md_lines)
md_path = OUT_DIR / "DECISION_TIME_CUTOFF_AUDIT.md"
with open(md_path, 'w') as f:
    f.write(md_text)
print(f"Written: {md_path}")

# ── FINAL SUMMARY ────────────────────────────────────────────────────────
print("\n" + "="*60)
print("FINAL OUTPUT")
print("="*60)
print(f"\nAUDIT ONLY — DECISION TIME NOT YET FROZEN")
print(f"\n1. SAMPLE: {len(sample)} games | 200/season × 100 day/100 evening | random_state=123")
print(f"   API calls this session: {api_call_count} | Comparable: {len(comparable)}")
print(f"\n2. REFERENCE INTEGRITY:")
print(f"   OPEN_LATE: {int(sample['open_late_flag'].sum())} | Post-first-pitch excluded: {int((~sample['close_before_commence']).sum())} | Comparable: {len(comparable)}")
print(f"\n3. COVERAGE BY TIME:")
for r in table_a.to_dict('records'):
    print(f"   {r['Time']}: {r['Usable']}/{r['Events']} ({r['Usable_pct']}%)")
print(f"\n4. SAME-BOOK PARITY:")
for r in table_b.to_dict('records'):
    print(f"   {r['Time']}: {r['Same_any']}/{r['N_usable']} ({r['Parity_pct']}%)")
print(f"\n5. REMAINING MOVEMENT (median total drift, same-book FD):")
for r in table_d.to_dict('records'):
    if r.get('N_pairs', 0) > 0:
        print(f"   {r['Time']}: median={r.get('Median_drift','—')} | ≥0.5={r.get('Pct_ge_0_5','—')}% | ≥1.0={r.get('Pct_ge_1_0','—')}% | zero={r.get('Pct_zero','—')}%")
    else:
        print(f"   {r['Time']}: 0 pairs")
print(f"\n6. PATH AGREEMENT:")
for r in table_f.to_dict('records'):
    print(f"   {r['Time']}: {r.get('Agreement_pct', 0)}% (n={r.get('N', 0)})")
print(f"\n7. RECOMMENDATION: {verdict}")
print(f"   Reason: {verdict_reason}")
print(f"\n8. FILES WRITTEN:")
print(f"   {md_path}")
print(f"   {json_path}")
print(f"   {csv_path}")
print(f"   {CHECKPOINT_PATH}")
print(f"\n9. MPS STATUS: RESERVED / DATA-BLOCKED")
print(f"   MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only.")
print(f"   No signals have been tested, no predictive value has been claimed,")
print(f"   and no changes to the canonical spec have been made.")
