"""
5V: Derive real plays/game and drives/game from PBP to match the engine's n_plays definition.

The engine increments n_plays once per: pass (incl sacks), run, qb_kneel, qb_spike,
pre-snap safety. This matches PBP play_type in {pass, run, qb_kneel, qb_spike},
EXCLUDING two-point attempts (engine handles 2pt via the PAT branch, not n_plays).

Drives: PBP fixed_drive with >= 1 play of the above types (matching the plays >= 1
filter from D153).
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]

# The engine's n_plays events (from engine.py: 14 sites, all on these play types)
PLAY_TYPES = {"pass", "run", "qb_kneel", "qb_spike"}


def compute_k1_actuals():
    """Derive plays/game and drives/game from PBP 2021-24 REG.

    Returns dict with 'plays_pg', 'drives_pg', 'n_games', and the per-type breakdown.
    """
    frames = []
    for s in SEASONS:
        df = pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        frames.append(df)
    pbp = pd.concat(frames, ignore_index=True)
    n_games = pbp["game_id"].nunique()

    # Exclude two-point attempts (engine doesn't count them in n_plays)
    two_pt = pbp.get("two_point_attempt", pd.Series(0, index=pbp.index)).fillna(0)
    regular = pbp[two_pt == 0]

    # Count plays by type
    counts = {}
    total = 0
    for pt in PLAY_TYPES:
        n = len(regular[regular["play_type"] == pt])
        counts[pt] = n
        total += n

    plays_pg = total / n_games

    # Drives with >= 1 play (matching D153 plays>=1 filter)
    # 5W: explicit dropna=True on fixed_drive to ensure cross-platform reproducibility
    plays_in_drives = regular[regular["play_type"].isin(PLAY_TYPES)].dropna(subset=["fixed_drive"])
    drive_plays = plays_in_drives.groupby(["game_id", "fixed_drive"], dropna=True).size().reset_index(name="n")
    drives_with_plays = drive_plays[drive_plays["n"] >= 1]
    n_drives_total = len(drives_with_plays)
    drives_pg = n_drives_total / n_games

    return {
        "plays_pg": round(plays_pg, 2),
        "drives_pg": round(drives_pg, 2),
        "n_games": n_games,
        "n_plays_total": total,
        "n_drives_total": n_drives_total,
        "per_type": {pt: round(counts[pt] / n_games, 2) for pt in sorted(PLAY_TYPES)},
    }


if __name__ == "__main__":
    act = compute_k1_actuals()
    print(f"Plays/game: {act['plays_pg']} ({act['n_games']} games)")
    print(f"  Breakdown: {act['per_type']}")
    print(f"Drives/game: {act['drives_pg']}")
