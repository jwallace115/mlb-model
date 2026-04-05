#!/usr/bin/env python3
"""
NBA Catchup — runs when MacBook wakes/boots after being off.
Detects missed pipeline runs and catches up.
"""
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(ROOT)

SIGNAL_LOG = ROOT / "nba" / "data" / "nba_signal_log.parquet"
REF_SCRAPE = ROOT / "nba" / "ref_scrape.py"
RUN_NBA = ROOT / "nba" / "run_nba.py"
PYTHON = sys.executable


def main():
    print(f"NBA Catchup — {date.today()}")
    print("=" * 40)

    # Step 1: Check last signal date
    try:
        import pandas as pd
        sig = pd.read_parquet(SIGNAL_LOG)
        last_date = pd.to_datetime(sig["game_date"]).max().date()
        days_gap = (date.today() - last_date).days
        print(f"Last signal: {last_date} ({days_gap} days ago)")
    except Exception as e:
        print(f"Could not read signal log: {e}")
        days_gap = 999
        last_date = None

    if days_gap == 0:
        print("Signal log is current — no catchup needed.")
        return

    if days_gap >= 1:
        print(f"Gap detected: {days_gap} days since last signal log entry.")

    # Step 2: Run ref scrape for today
    print(f"\nRunning ref scrape...")
    try:
        result = subprocess.run(
            [PYTHON, str(REF_SCRAPE)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr[-500:])
    except Exception as e:
        print(f"Ref scrape failed: {e}")
        return

    # Step 3: Run main NBA pipeline
    print(f"\nRunning NBA pipeline...")
    try:
        result = subprocess.run(
            [PYTHON, str(RUN_NBA)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300
        )
        print(result.stdout[-2000:])
        if result.returncode != 0 and result.stderr:
            print(f"Stderr: {result.stderr[-500:]}")
    except Exception as e:
        print(f"NBA pipeline failed: {e}")
        return

    # Step 4: Push to git
    print(f"\nPushing to GitHub...")
    try:
        subprocess.run(["git", "add", "nba/data/nba_signal_log.parquet",
                         "nba/data/nba_daily_projections.parquet",
                         "nba/data/nba_ref_assignments.csv"],
                        cwd=str(ROOT), capture_output=True, timeout=30)
        commit = subprocess.run(
            ["git", "commit", "-m", f"NBA catchup: {date.today().isoformat()}"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30
        )
        if commit.returncode == 0:
            push = subprocess.run(["git", "push", "origin", "main"],
                                   cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            print(f"Push: {push.stdout.strip() or push.stderr.strip()}")
        else:
            print(f"Nothing to commit: {commit.stdout.strip()}")
    except Exception as e:
        print(f"Git push failed: {e}")

    # Step 5: Sync VM
    print(f"\nSyncing VM...")
    try:
        sync = subprocess.run(
            ["ssh", "root@142.93.242.4", "cd /root/mlb-model && git pull"],
            capture_output=True, text=True, timeout=30
        )
        print(f"VM: {sync.stdout.strip() or sync.stderr.strip()}")
    except Exception as e:
        print(f"VM sync failed (non-fatal): {e}")

    print(f"\nCatchup complete.")


if __name__ == "__main__":
    main()
