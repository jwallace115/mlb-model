"""
MLB Odds Warehouse — Phase 1 Mainline Historical Pull
Sport-level CORE markets (h2h, spreads, totals) at 5 daily snapshots.
Checkpoint every 500 events, shard every 5000, commit every 5000.
"""
import requests
import pandas as pd
import json
import time
import hashlib
import subprocess
from pathlib import Path
from datetime import date, timedelta, datetime

# Load API key
with open('/Users/jw115/mlb-model/.env') as f:
    for line in f:
        if line.startswith('ODDS_API_KEY'):
            API_KEY = line.strip().split('=',1)[1].strip().strip('"').strip("'")
            break

BASE_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds"
MARKETS = "h2h,spreads,totals"
REGIONS = "us"
BOOKMAKERS = "draftkings,fanduel,betmgm,caesars,hard_rock,bet365,bovada,betonline_ag,mybookieag,pinnacle"
SLEEP_INTERVAL = 1.5
CHECKPOINT_INTERVAL = 500
SHARD_INTERVAL = 5000
OUTPUT_DIR = Path("/Users/jw115/mlb-model/warehouse/baseball_mlb")
MAINLINE_DIR = OUTPUT_DIR / "mainline"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
RESUME_PATH = OUTPUT_DIR / "resume_state.json"
MANIFEST_PATH = Path("/Users/jw115/mlb-model/warehouse/WAREHOUSE_MANIFEST.json")

# Build timestamp universe
seasons = {
    '2022': (date(2022,4,7), date(2022,10,5)),
    '2023': (date(2023,3,30), date(2023,10,1)),
    '2024': (date(2024,3,20), date(2024,10,1)),
    '2025': (date(2025,3,27), date(2025,9,28)),
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
completed = set(resume.get("completed_timestamps", []))
total_events = resume.get("total_events_pulled", 0)

# Get shard count from manifest
with open(MANIFEST_PATH) as f:
    manifest = json.load(f)
shard_number = len(manifest.get("shards", []))

remaining = [ts for ts in all_timestamps if ts not in completed]
print(f"Total timestamps: {len(all_timestamps)}")
print(f"Already completed: {len(completed)}")
print(f"Remaining: {len(remaining)}")

# Pull loop
records_buffer = []
checkpoint_count = 0
shard_event_count = 0
consecutive_failures = 0
last_credits = None
t0 = time.time()

checkpoint_file = CHECKPOINT_DIR / "checkpoint_running.jsonl"

for i, ts in enumerate(remaining):
    try:
        r = requests.get(BASE_URL, params={
            'apiKey': API_KEY, 'date': ts, 'regions': REGIONS,
            'markets': MARKETS, 'bookmakers': BOOKMAKERS
        }, timeout=15)

        last_credits = r.headers.get('x-requests-remaining', last_credits)

        if r.status_code == 200:
            data = r.json()
            events = data.get('data', [])

            for event in events:
                eid = event.get('id', '')
                ct = event.get('commence_time', '')
                gd = ct[:10] if ct else ''
                ht = event.get('home_team', '')
                at = event.get('away_team', '')

                for bk in event.get('bookmakers', []):
                    bk_key = bk.get('key', '')
                    for mkt in bk.get('markets', []):
                        mkt_key = mkt.get('key', '')
                        for outcome in mkt.get('outcomes', []):
                            records_buffer.append({
                                'snapshot_timestamp': ts,
                                'event_id': eid,
                                'commence_time': ct,
                                'game_date': gd,
                                'home_team': ht,
                                'away_team': at,
                                'bookmaker': bk_key,
                                'market': mkt_key,
                                'outcome_name': outcome.get('name', ''),
                                'price': outcome.get('price'),
                                'point': outcome.get('point'),
                            })

            completed.add(ts)
            new_records = len(records_buffer) - (total_events - resume.get("total_events_pulled", 0) + shard_event_count + checkpoint_count)
            consecutive_failures = 0
        else:
            with open(OUTPUT_DIR / "pull_errors.log", "a") as ef:
                ef.write(f"{ts} | status={r.status_code} | {r.text[:200]}\n")
            consecutive_failures += 1
    except Exception as e:
        with open(OUTPUT_DIR / "pull_errors.log", "a") as ef:
            ef.write(f"{ts} | {type(e).__name__}: {e}\n")
        consecutive_failures += 1

    if consecutive_failures >= 50:
        print(f"HARD STOP: 50 consecutive failures at timestamp {i}")
        break

    # Checkpoint
    if len(records_buffer) >= CHECKPOINT_INTERVAL or (i == len(remaining) - 1 and records_buffer):
        with open(checkpoint_file, 'a') as cf:
            for rec in records_buffer:
                cf.write(json.dumps(rec) + '\n')

        shard_event_count += len(records_buffer)
        total_events += len(records_buffer)
        records_buffer = []

        resume['completed_timestamps'] = list(completed)
        resume['total_events_pulled'] = total_events
        resume['last_updated'] = datetime.utcnow().isoformat() + 'Z'
        with open(RESUME_PATH, 'w') as f:
            json.dump(resume, f, indent=2)

    # Shard
    if shard_event_count >= SHARD_INTERVAL or (i == len(remaining) - 1 and shard_event_count > 0):
        # Load all checkpoint data
        if checkpoint_file.exists():
            rows = []
            with open(checkpoint_file) as cf:
                for line in cf:
                    if line.strip():
                        rows.append(json.loads(line))

            if rows:
                shard_number += 1
                shard_name = f"mlb_mainline_shard_{shard_number:04d}.parquet"
                shard_path = MAINLINE_DIR / shard_name

                df = pd.DataFrame(rows)
                df.to_parquet(shard_path, index=False)

                # Hash
                with open(shard_path, 'rb') as sf:
                    sha = hashlib.sha256(sf.read()).hexdigest()

                # Update manifest
                manifest['shards'].append({
                    'shard_id': shard_number,
                    'filename': shard_name,
                    'row_count': len(df),
                    'min_snapshot': str(df['snapshot_timestamp'].min()),
                    'max_snapshot': str(df['snapshot_timestamp'].max()),
                    'min_game_date': str(df['game_date'].min()),
                    'max_game_date': str(df['game_date'].max()),
                    'bookmakers': sorted(df['bookmaker'].unique().tolist()),
                    'sha256': sha,
                    'committed_at': None,
                })
                with open(MANIFEST_PATH, 'w') as f:
                    json.dump(manifest, f, indent=2)

                # Archive checkpoint
                archive = CHECKPOINT_DIR / f"checkpoint_shard_{shard_number:04d}_archived.jsonl"
                checkpoint_file.rename(archive)

                # Commit and push
                try:
                    subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'add', 'warehouse/'],
                                   capture_output=True, text=True, check=True)
                    subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'commit', '-m',
                                   f"warehouse: baseball_mlb mainline shard {shard_number} — {len(df)} rows, {df['game_date'].min()} to {df['game_date'].max()}"],
                                   capture_output=True, text=True, check=True)
                    push_result = subprocess.run(['git', '-C', '/Users/jw115/mlb-model', 'push', 'origin', 'warehouse'],
                                                capture_output=True, text=True, timeout=120)
                    if push_result.returncode == 0:
                        manifest['shards'][-1]['committed_at'] = datetime.utcnow().isoformat() + 'Z'
                        with open(MANIFEST_PATH, 'w') as f:
                            json.dump(manifest, f, indent=2)
                        print(f"  Shard {shard_number} pushed: {len(df)} rows")
                    else:
                        print(f"  Push failed: {push_result.stderr[:200]}")
                except Exception as e:
                    print(f"  Git error: {e}")

                shard_event_count = 0

    # Progress
    if (i+1) % 100 == 0:
        elapsed = time.time() - t0
        rate = elapsed / (i+1)
        eta = rate * (len(remaining) - i - 1)
        pct = (len(completed)) / len(all_timestamps) * 100
        print(f"Progress: {len(completed)}/{len(all_timestamps)} ({pct:.1f}%) | "
              f"Events: {total_events} | Credits: {last_credits} | ETA: {eta/60:.0f}m")

    time.sleep(SLEEP_INTERVAL)

elapsed_total = time.time() - t0
print(f"\nPull complete in {elapsed_total/60:.1f} minutes")
print(f"Total events: {total_events}")
print(f"Shards written: {shard_number}")
print(f"Timestamps completed: {len(completed)}/{len(all_timestamps)}")
print(f"Credits remaining: {last_credits}")
