"""
MLB Odds Warehouse — Phase 2 Derivatives Pull
Event-level: team_totals + alternate_totals, 2024-2025
Two-pass: (A) fetch event list per timestamp, (B) fetch event odds
Checkpoint every 100 events, shard every 1000, commit+push every 1000.
"""
import requests
import pandas as pd
import json
import time
import hashlib
import subprocess
from pathlib import Path
from datetime import date, timedelta, datetime, timezone

# Load API key
with open('/Users/jw115/mlb-model/.env') as f:
    for line in f:
        if line.startswith('ODDS_API_KEY'):
            API_KEY = line.strip().split('=',1)[1].strip().strip('"').strip("'")
            break

EVENTS_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events"
EVENT_ODDS_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events/{event_id}/odds"
MARKETS = "team_totals,alternate_totals"
REGIONS = "us"
BOOKMAKERS = "draftkings,fanduel,betmgm,caesars,hard_rock,bet365,bovada,betonline_ag,mybookieag,pinnacle"
SLEEP_EVENT_LIST = 0.5
SLEEP_EVENT_ODDS = 1.5
CHECKPOINT_INTERVAL = 100
SHARD_INTERVAL = 1000

BASE = Path("/Users/jw115/mlb-model/warehouse/baseball_mlb/derivatives")
CHECKPOINT_DIR = BASE / "checkpoints"
RESUME_PATH = BASE / "resume_state.json"
MANIFEST_PATH = Path("/Users/jw115/mlb-model/warehouse/WAREHOUSE_MANIFEST.json")

# Build timestamp universe
seasons = {
    '2024': (date(2024, 3, 20), date(2024, 10, 1)),
    '2025': (date(2025, 3, 27), date(2025, 9, 28)),
}
hours = [11, 14, 17, 20, 23]

all_timestamps = []
for season, (start, end) in seasons.items():
    d = start
    while d <= end:
        for h in hours:
            all_timestamps.append(f"{d}T{h:02d}:00:00Z")
        d += timedelta(days=1)

# Load resume state
with open(RESUME_PATH) as f:
    resume = json.load(f)
completed_set = set(resume.get("completed_event_timestamps", []))
total_events = resume.get("total_events_pulled", 0)

# Load manifest for shard numbering
with open(MANIFEST_PATH) as f:
    manifest = json.load(f)
# Find max derivative shard number
deriv_shards = [s for s in manifest.get("shards", []) if "team_totals" in s.get("filename", "") or "alt_totals" in s.get("filename", "")]
shard_number = max([s.get("shard_id", 0) for s in deriv_shards], default=0)

remaining_ts = [ts for ts in all_timestamps]
print(f"Total timestamps: {len(all_timestamps)}")
print(f"Already completed event-timestamps: {len(completed_set)}")
print(f"Starting shard number: {shard_number}")

# Runtime estimate
est_events = len(all_timestamps) * 15
est_runtime = est_events * 1.5 + len(all_timestamps) * 0.5
print(f"Estimated events: ~{est_events:,}")
print(f"Estimated runtime: ~{est_runtime/3600:.1f} hours")
print(f"Estimated credits: ~{est_events * 10 + len(all_timestamps) * 2:,}")

records_buffer = []
events_since_checkpoint = 0
events_since_shard = 0
consecutive_failures = 0
last_credits = None
t0 = time.time()
checkpoint_file = CHECKPOINT_DIR / "checkpoint_running.jsonl"

for ts_idx, ts in enumerate(remaining_ts):
    # PASS A — Fetch event list
    try:
        r_events = requests.get(EVENTS_URL, params={
            'apiKey': API_KEY, 'date': ts
        }, timeout=15)
        last_credits = r_events.headers.get('x-requests-remaining', last_credits)

        if r_events.status_code != 200:
            with open(BASE / "pull_errors.log", "a") as ef:
                ef.write(f"EVENTS {ts} | status={r_events.status_code}\n")
            time.sleep(SLEEP_EVENT_LIST)
            continue

        events_data = r_events.json()
        event_list = events_data.get('data', [])
    except Exception as e:
        with open(BASE / "pull_errors.log", "a") as ef:
            ef.write(f"EVENTS {ts} | {type(e).__name__}: {e}\n")
        time.sleep(SLEEP_EVENT_LIST)
        continue

    time.sleep(SLEEP_EVENT_LIST)

    # PASS B — Fetch odds for each event
    for event in event_list:
        event_id = event.get('id', '')
        commence = event.get('commence_time', '')
        game_date = commence[:10] if commence else ''
        home = event.get('home_team', '')
        away = event.get('away_team', '')

        composite_key = f"{event_id}|{ts}"
        if composite_key in completed_set:
            continue

        try:
            r_odds = requests.get(EVENT_ODDS_URL.format(event_id=event_id), params={
                'apiKey': API_KEY, 'date': ts, 'regions': REGIONS,
                'markets': MARKETS, 'bookmakers': BOOKMAKERS
            }, timeout=15)
            last_credits = r_odds.headers.get('x-requests-remaining', last_credits)

            if r_odds.status_code == 200:
                odds_data = r_odds.json()
                event_detail = odds_data.get('data', {})

                for bk in event_detail.get('bookmakers', []):
                    bk_key = bk.get('key', '')
                    for mkt in bk.get('markets', []):
                        mkt_key = mkt.get('key', '')
                        outcomes = mkt.get('outcomes', [])

                        if mkt_key == 'team_totals':
                            # Parse pairs: Over/Under per team
                            teams = {}
                            for o in outcomes:
                                team_name = o.get('description', '')
                                direction = o.get('name', '')  # Over or Under
                                price = o.get('price')
                                point = o.get('point')
                                if team_name not in teams:
                                    teams[team_name] = {}
                                if direction == 'Over':
                                    teams[team_name]['over_price'] = price
                                    teams[team_name]['total_line'] = point
                                elif direction == 'Under':
                                    teams[team_name]['under_price'] = price
                                    if 'total_line' not in teams[team_name]:
                                        teams[team_name]['total_line'] = point

                            for team_name, vals in teams.items():
                                if vals.get('over_price') is not None or vals.get('under_price') is not None:
                                    records_buffer.append({
                                        'snapshot_timestamp': ts,
                                        'event_id': event_id,
                                        'commence_time': commence,
                                        'game_date': game_date,
                                        'home_team': home,
                                        'away_team': away,
                                        'bookmaker': bk_key,
                                        'market': 'team_totals',
                                        'team': team_name,
                                        'total_line': vals.get('total_line'),
                                        'over_price': vals.get('over_price'),
                                        'under_price': vals.get('under_price'),
                                        'alt_line': None,
                                        'ladder_distance': None,
                                    })

                        elif mkt_key == 'alternate_totals':
                            # Each distinct line value
                            lines = {}
                            for o in outcomes:
                                point = o.get('point')
                                direction = o.get('name', '')
                                price = o.get('price')
                                if point not in lines:
                                    lines[point] = {}
                                if direction == 'Over':
                                    lines[point]['over_price'] = price
                                elif direction == 'Under':
                                    lines[point]['under_price'] = price

                            for line_val, vals in lines.items():
                                if vals.get('over_price') is not None or vals.get('under_price') is not None:
                                    records_buffer.append({
                                        'snapshot_timestamp': ts,
                                        'event_id': event_id,
                                        'commence_time': commence,
                                        'game_date': game_date,
                                        'home_team': home,
                                        'away_team': away,
                                        'bookmaker': bk_key,
                                        'market': 'alternate_totals',
                                        'team': None,
                                        'total_line': None,
                                        'over_price': vals.get('over_price'),
                                        'under_price': vals.get('under_price'),
                                        'alt_line': line_val,
                                        'ladder_distance': None,
                                    })

                completed_set.add(composite_key)
                events_since_checkpoint += 1
                events_since_shard += 1
                total_events += 1
                consecutive_failures = 0
            else:
                with open(BASE / "pull_errors.log", "a") as ef:
                    ef.write(f"ODDS {event_id} {ts} | status={r_odds.status_code}\n")
                consecutive_failures += 1
        except Exception as e:
            with open(BASE / "pull_errors.log", "a") as ef:
                ef.write(f"ODDS {event_id} {ts} | {type(e).__name__}: {e}\n")
            consecutive_failures += 1

        if consecutive_failures >= 50:
            print(f"HARD STOP: 50 consecutive failures")
            break

        time.sleep(SLEEP_EVENT_ODDS)

        # Checkpoint
        if events_since_checkpoint >= CHECKPOINT_INTERVAL:
            with open(checkpoint_file, 'a') as cf:
                for rec in records_buffer:
                    cf.write(json.dumps(rec) + '\n')
            records_buffer = []

            resume['completed_event_timestamps'] = list(completed_set)
            resume['total_events_pulled'] = total_events
            resume['last_updated'] = datetime.now(timezone.utc).isoformat()
            with open(RESUME_PATH, 'w') as f:
                json.dump(resume, f, indent=2)
            events_since_checkpoint = 0

        # Shard
        if events_since_shard >= SHARD_INTERVAL:
            # Flush remaining buffer first
            if records_buffer:
                with open(checkpoint_file, 'a') as cf:
                    for rec in records_buffer:
                        cf.write(json.dumps(rec) + '\n')
                records_buffer = []

            if checkpoint_file.exists():
                rows = []
                with open(checkpoint_file) as cf:
                    for line in cf:
                        if line.strip():
                            rows.append(json.loads(line))

                if rows:
                    shard_number += 1
                    df_all = pd.DataFrame(rows)

                    # Split team_totals and alt_totals
                    tt = df_all[df_all['market'] == 'team_totals']
                    at = df_all[df_all['market'] == 'alternate_totals']

                    for sub_df, prefix in [(tt, 'team_totals'), (at, 'alt_totals')]:
                        if len(sub_df) == 0:
                            continue
                        fname = f"mlb_{prefix}_shard_{shard_number:04d}.parquet"
                        fpath = BASE / fname
                        sub_df.to_parquet(fpath, index=False)

                        with open(fpath, 'rb') as sf:
                            sha = hashlib.sha256(sf.read()).hexdigest()

                        manifest['shards'].append({
                            'shard_id': shard_number,
                            'filename': fname,
                            'row_count': len(sub_df),
                            'min_snapshot': str(sub_df['snapshot_timestamp'].min()),
                            'max_snapshot': str(sub_df['snapshot_timestamp'].max()),
                            'min_game_date': str(sub_df['game_date'].min()),
                            'max_game_date': str(sub_df['game_date'].max()),
                            'bookmakers': sorted(sub_df['bookmaker'].unique().tolist()),
                            'sha256': sha,
                            'committed_at': None,
                        })

                    with open(MANIFEST_PATH, 'w') as f:
                        json.dump(manifest, f, indent=2)

                    # Archive checkpoint
                    archive = CHECKPOINT_DIR / f"checkpoint_deriv_shard_{shard_number:04d}_archived.jsonl"
                    checkpoint_file.rename(archive)

                    # Update resume
                    resume['completed_event_timestamps'] = list(completed_set)
                    resume['total_events_pulled'] = total_events
                    resume['last_updated'] = datetime.now(timezone.utc).isoformat()
                    with open(RESUME_PATH, 'w') as f:
                        json.dump(resume, f, indent=2)

                    # Commit and push
                    try:
                        subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'add', 'warehouse/'],
                                       capture_output=True, text=True, check=True)
                        subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'commit', '-m',
                                       f"warehouse: mlb derivatives shard {shard_number} — {len(rows)} rows, {df_all['game_date'].min()} to {df_all['game_date'].max()}"],
                                       capture_output=True, text=True, check=True)
                        push_r = subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'push', 'origin', 'warehouse'],
                                               capture_output=True, text=True, timeout=120)
                        if push_r.returncode == 0:
                            for s in manifest['shards']:
                                if s.get('committed_at') is None and s['shard_id'] == shard_number:
                                    s['committed_at'] = datetime.now(timezone.utc).isoformat()
                            with open(MANIFEST_PATH, 'w') as f:
                                json.dump(manifest, f, indent=2)
                            print(f"  Shard {shard_number} pushed: {len(rows)} rows")
                        else:
                            print(f"  Push failed: {push_r.stderr[:200]}")
                    except Exception as e:
                        print(f"  Git error: {e}")

                    events_since_shard = 0

    if consecutive_failures >= 50:
        break

    # Progress
    if (ts_idx + 1) % 20 == 0:
        elapsed = time.time() - t0
        rate = elapsed / max(ts_idx + 1, 1)
        eta = rate * (len(remaining_ts) - ts_idx - 1)
        print(f"Progress: ts={ts_idx+1}/{len(remaining_ts)} | events={total_events:,} | "
              f"credits={last_credits} | elapsed={elapsed/3600:.1f}h | ETA={eta/3600:.1f}h")

# Flush final buffer
if records_buffer:
    with open(checkpoint_file, 'a') as cf:
        for rec in records_buffer:
            cf.write(json.dumps(rec) + '\n')
    records_buffer = []

# Final shard if any remaining
if checkpoint_file.exists() and checkpoint_file.stat().st_size > 0:
    rows = []
    with open(checkpoint_file) as cf:
        for line in cf:
            if line.strip():
                rows.append(json.loads(line))
    if rows:
        shard_number += 1
        df_all = pd.DataFrame(rows)
        tt = df_all[df_all['market'] == 'team_totals']
        at = df_all[df_all['market'] == 'alternate_totals']
        for sub_df, prefix in [(tt, 'team_totals'), (at, 'alt_totals')]:
            if len(sub_df) == 0: continue
            fname = f"mlb_{prefix}_shard_{shard_number:04d}.parquet"
            fpath = BASE / fname
            sub_df.to_parquet(fpath, index=False)
            with open(fpath, 'rb') as sf:
                sha = hashlib.sha256(sf.read()).hexdigest()
            manifest['shards'].append({
                'shard_id': shard_number, 'filename': fname,
                'row_count': len(sub_df),
                'min_snapshot': str(sub_df['snapshot_timestamp'].min()),
                'max_snapshot': str(sub_df['snapshot_timestamp'].max()),
                'min_game_date': str(sub_df['game_date'].min()),
                'max_game_date': str(sub_df['game_date'].max()),
                'bookmakers': sorted(sub_df['bookmaker'].unique().tolist()),
                'sha256': sha, 'committed_at': None,
            })
        with open(MANIFEST_PATH, 'w') as f:
            json.dump(manifest, f, indent=2)
        archive = CHECKPOINT_DIR / f"checkpoint_deriv_shard_{shard_number:04d}_archived.jsonl"
        checkpoint_file.rename(archive)
        try:
            subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'add', 'warehouse/'],
                           capture_output=True, text=True, check=True)
            subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'commit', '-m',
                           f"warehouse: mlb derivatives final shard {shard_number}"],
                           capture_output=True, text=True, check=True)
            subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'push', 'origin', 'warehouse'],
                           capture_output=True, text=True, timeout=120)
            print(f"  Final shard {shard_number} pushed: {len(rows)} rows")
        except Exception as e:
            print(f"  Final git error: {e}")

# Final resume save
resume['completed_event_timestamps'] = list(completed_set)
resume['total_events_pulled'] = total_events
resume['last_updated'] = datetime.now(timezone.utc).isoformat()
with open(RESUME_PATH, 'w') as f:
    json.dump(resume, f, indent=2)

elapsed_total = time.time() - t0
print(f"\nPull complete in {elapsed_total/3600:.1f} hours")
print(f"Total events pulled: {total_events:,}")
print(f"Shards written: {shard_number}")
print(f"Credits remaining: {last_credits}")
