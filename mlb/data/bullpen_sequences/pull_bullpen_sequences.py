"""
MLB Bullpen Appearance Sequence Pull — Reliever order + workload from boxscore API
Resumable with checkpoint every 500 games.
"""
import requests
import pandas as pd
import json
import time
from pathlib import Path

BASE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
SLEEP_INTERVAL = 0.5
OUTPUT_DIR = Path("/Users/jw115/mlb-model/mlb/data/bullpen_sequences")
OUTPUT_FILE = OUTPUT_DIR / "mlb_bullpen_appearances_2022_2025.parquet"
CHECKPOINT_FILE = OUTPUT_DIR / "pull_checkpoint.json"
CHECKPOINT_INTERVAL = 500

# Build game_pk universe
odds = pd.read_parquet("/Users/jw115/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet", columns=["game_pk"])
v6 = pd.read_parquet("/Users/jw115/mlb-model/research/runtime_objects/mlb_runtime_object_v6/mlb_runtime_object_v6.parquet", columns=["game_pk"])
odds_pks = set(pd.to_numeric(odds["game_pk"], errors="coerce").dropna().astype(int))
v6_pks = set(pd.to_numeric(v6["game_pk"], errors="coerce").dropna().astype(int))
all_pks = sorted(odds_pks | v6_pks)
print(f"Total game_pks in universe: {len(all_pks)}")

# Load checkpoint
if CHECKPOINT_FILE.exists():
    with open(CHECKPOINT_FILE) as f:
        ckpt = json.load(f)
    completed = set(ckpt.get("completed_pks", []))
    failed = set(ckpt.get("failed_pks", []))
    records = ckpt.get("records", [])
    print(f"Resuming: {len(completed)} completed, {len(failed)} failed")
else:
    completed = set()
    failed = set()
    records = []
    print("Starting fresh")

remaining = [pk for pk in all_pks if pk not in completed]
print(f"Remaining to pull: {len(remaining)}")

def safe_int(d, key, default=0):
    v = d.get(key, default)
    return int(v) if v is not None else default

t0 = time.time()
consecutive_failures = 0

for i, gpk in enumerate(remaining):
    url = BASE_URL.format(game_pk=int(gpk))
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("teams", {})
            for side_key, side_label in [("home", "home"), ("away", "away")]:
                team_data = teams.get(side_key, {})
                pitchers = team_data.get("pitchers", [])
                players = team_data.get("players", {})
                for order_idx, pid in enumerate(pitchers):
                    player_key = f"ID{pid}"
                    player_info = players.get(player_key, {})
                    person = player_info.get("person", {})
                    stats = player_info.get("stats", {})
                    pitching = stats.get("pitching", {})
                    records.append({
                        "game_pk": int(gpk),
                        "team_side": side_label,
                        "appearance_order": order_idx + 1,
                        "is_starter": order_idx == 0,
                        "pitcher_id": int(person.get("id", 0)),
                        "pitcher_name": person.get("fullName", ""),
                        "outs_recorded": safe_int(pitching, "outs"),
                        "batters_faced": safe_int(pitching, "battersFaced"),
                        "hits_allowed": safe_int(pitching, "hits"),
                        "runs_allowed": safe_int(pitching, "runs"),
                        "inherited_runners": safe_int(pitching, "inheritedRunners"),
                        "inherited_scored": safe_int(pitching, "inheritedRunnersScored"),
                        "strikes_thrown": safe_int(pitching, "strikes"),
                        "pitches_thrown": safe_int(pitching, "numberOfPitches"),
                    })
            completed.add(int(gpk))
            consecutive_failures = 0
        else:
            failed.add(int(gpk))
            consecutive_failures += 1
            print(f"  FAIL {gpk}: status {resp.status_code}")
    except Exception as e:
        failed.add(int(gpk))
        consecutive_failures += 1
        print(f"  FAIL {gpk}: {type(e).__name__}: {e}")

    if consecutive_failures >= 10:
        print(f"  WARNING: 10 consecutive failures at game {i+1}")
        consecutive_failures = 0

    if (i + 1) % CHECKPOINT_INTERVAL == 0:
        elapsed = time.time() - t0
        rate = elapsed / (i + 1)
        eta = rate * (len(remaining) - i - 1)
        print(f"Completed {len(completed)} / {len(all_pks)} games ({len(completed)/len(all_pks)*100:.1f}%) "
              f"— elapsed {elapsed/60:.1f}m — ETA {eta/60:.1f}m")
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({"completed_pks": list(completed), "failed_pks": list(failed), "records": records}, f)

    time.sleep(SLEEP_INTERVAL)

# Final checkpoint
with open(CHECKPOINT_FILE, "w") as f:
    json.dump({"completed_pks": list(completed), "failed_pks": list(failed), "records": records}, f)

# Save parquet
df = pd.DataFrame(records)
df.to_parquet(OUTPUT_FILE, index=False)

elapsed_total = time.time() - t0
print(f"\nPull complete in {elapsed_total/60:.1f} minutes")
print(f"Shape: {df.shape}")
print(f"Unique games pulled: {df['game_pk'].nunique()}")
print(f"Failed games: {len(failed)}")
if len(failed) < 50:
    print(f"Failed list: {sorted(failed)}")
else:
    print(f"Failed count: {len(failed)}")

# Distribution of appearance_order
print(f"\nAppearance order distribution:")
print(df['appearance_order'].value_counts().sort_index().to_string())

# Sanity checks
starters = df[df['is_starter']]
relievers = df[~df['is_starter']]
print(f"\nStarters: mean outs={starters['outs_recorded'].mean():.1f}, mean pitches={starters['pitches_thrown'].mean():.1f}")
print(f"Relievers: mean outs={relievers['outs_recorded'].mean():.1f}, mean pitches={relievers['pitches_thrown'].mean():.1f}")

if starters['outs_recorded'].mean() < 6 or starters['outs_recorded'].mean() > 21:
    print("WARNING: Starter outs outside expected range (6-21)")
