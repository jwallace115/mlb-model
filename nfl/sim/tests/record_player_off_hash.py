#!/usr/bin/env python3
"""Record the player-OFF score hash for the current engine fingerprint."""
import sys, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed
from nfl.sim.calibration import engine_fingerprint

HASH_FILE = Path(__file__).resolve().parent / "fixtures" / "player_off_hash.json"

_load_tables()
team_r, tend, sit, kicker, league = _load_ratings()
seed = stable_seed(("T4_test", 42))
r = simulate_game("DAL", "PHI", 2023, 9, n_sims=4000, seed=seed,
                   team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)
h = hashlib.sha256(
    r["home_score"].values.tobytes() + r["away_score"].values.tobytes()
).hexdigest()[:16]

fp = engine_fingerprint()
data = json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}
data[fp] = h
HASH_FILE.write_text(json.dumps(data, indent=2) + "\n")
print(f"Recorded {fp} -> {h} in {HASH_FILE}")
