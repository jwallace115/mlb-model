"""
MLB Scoring Path Data Pull — Inning-by-inning scoring from MLB Stats API
Resumable with checkpoint every 500 games.
"""
import requests
import pandas as pd
import json
import time
import os
from pathlib import Path

BASE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore"
SLEEP_INTERVAL = 0.5
OUTPUT_DIR = Path("/Users/jw115/mlb-model/mlb/data/scoring_paths")
OUTPUT_FILE = OUTPUT_DIR / "mlb_inning_scoring_2022_2025.parquet"
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

t0 = time.time()
consecutive_failures = 0

for i, gpk in enumerate(remaining):
    url = BASE_URL.format(game_pk=int(gpk))
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            innings = data.get("innings", [])
            for inn in innings:
                inning_num = inn.get("num", 0)
                home_runs = inn.get("home", {}).get("runs", 0)
                away_runs = inn.get("away", {}).get("runs", 0)
                if home_runs is None:
                    home_runs = 0
                if away_runs is None:
                    away_runs = 0
                records.append({
                    "game_pk": int(gpk),
                    "inning_num": int(inning_num),
                    "home_runs": int(home_runs),
                    "away_runs": int(away_runs),
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

    # Checkpoint
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
df["game_pk"] = df["game_pk"].astype(int)
df["inning_num"] = df["inning_num"].astype(int)
df["home_runs"] = df["home_runs"].astype(int)
df["away_runs"] = df["away_runs"].astype(int)
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
print(f"Total innings: {len(df)}")
print(f"Inning range: {df['inning_num'].min()} to {df['inning_num'].max()}")
