#!/usr/bin/env python3
"""
5T Item 2: Diagnose the tied_drives red.

Runs the 5A-9 12-game sample at N=500 with drive_log=True, isolates the
expiring drives that reached the 35-yard line while tied, and records the
mechanism of each expiration.
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.run_metric_noise_5h import SAMPLE_GAMES, _seed_5a9


def main():
    t0 = time.time()
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    ratings = {"team_r": team_r, "tend": tend, "sit": sit, "kicker": kicker, "league": league}

    # Run the 5A-9 sample
    print(f"Running 5A-9 sample: {len(SAMPLE_GAMES)} games, N=500, drive_log=True...")
    drives_list = []
    for home, away, season, week in SAMPLE_GAMES:
        s = _seed_5a9(home, away, season, week, 0)
        r = simulate_game(home, away, season, week, n_sims=500,
                          seed=s, drive_log=True, **ratings)
        if isinstance(r, tuple):
            r = r[0]
        dl = r.attrs["drive_log"]
        # Q4 drives starting with <= 300s, tied
        q4 = dl[(dl.start_quarter == 4) & (dl.start_clock <= 300)]
        tied = q4[q4.sd_start == 0]
        # Reached the 35 (broad definition)
        reached = (tied.start_yardline - tied.yards <= 35) | tied.result.isin(["TD"]) | (tied.end_yardline <= 35)
        reached_df = tied[reached].copy()
        reached_df["game"] = f"{away}@{home}_{season}_{week}"
        drives_list.append(reached_df)

    d = pd.concat(drives_list, ignore_index=True)
    n_reached = len(d)
    expired = d[d.result.isin(["end_game", "end_half"])]
    n_expired = len(expired)
    rate = n_expired / n_reached if n_reached > 0 else 0.0
    print(f"  Reached: {n_reached}, Expired: {n_expired}, Rate: {rate:.4f}")

    # Save the expired drives for analysis
    out_path = ROOT / "research" / "nfl_sim" / "phase5t_tied_expiry.parquet"
    expired.to_parquet(out_path, index=False)
    print(f"  Saved {out_path} ({len(expired)} rows)")

    # Analyze the expired drives
    print(f"\n{'='*80}")
    print(f"EXPIRED TIED DRIVES THAT REACHED THE 35 ({n_expired} drives)")
    print(f"{'='*80}")

    if n_expired > 0:
        print(f"\nEnd yardline distribution:")
        print(f"  mean={expired['end_yardline'].mean():.1f}  "
              f"median={expired['end_yardline'].median():.1f}  "
              f"p25={expired['end_yardline'].quantile(0.25):.1f}  "
              f"p75={expired['end_yardline'].quantile(0.75):.1f}")

        print(f"\nPlays per drive: mean={expired['plays'].mean():.1f}")
        print(f"Start clock: mean={expired['start_clock'].mean():.1f}s  "
              f"median={expired['start_clock'].median():.1f}s")

        # The key: how much clock was left at drive start?
        # If start_clock is low (< 60s), the drive ran out of time naturally
        # If start_clock is high (> 120s), something else happened
        print(f"\nStart clock distribution:")
        for lo, hi, label in [(0, 30, "0-30s"), (30, 60, "30-60s"), (60, 120, "60-120s"),
                               (120, 180, "120-180s"), (180, 300, "180-300s")]:
            n = ((expired["start_clock"] >= lo) & (expired["start_clock"] < hi)).sum()
            print(f"  {label}: {n} ({n/n_expired*100:.1f}%)")

        # The drive's yardline trajectory: start vs end
        print(f"\nStart yardline: mean={expired['start_yardline'].mean():.1f}")
        print(f"Yards gained: mean={expired['yards'].mean():.1f}")

        # How many were already very close (< 35) when they started?
        close_start = (expired["start_yardline"] <= 35).sum()
        print(f"\nStarted inside 35: {close_start} ({close_start/n_expired*100:.1f}%)")

    # Also check: of the NON-expired reached drives, what do they do?
    non_expired = d[~d.result.isin(["end_game", "end_half"])]
    print(f"\n{'='*80}")
    print(f"NON-EXPIRED REACHED DRIVES ({len(non_expired)} drives)")
    print(f"{'='*80}")
    result_counts = non_expired["result"].value_counts()
    for r, n in result_counts.items():
        print(f"  {r}: {n} ({n/len(non_expired)*100:.1f}%)")

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")


if __name__ == "__main__":
    main()
