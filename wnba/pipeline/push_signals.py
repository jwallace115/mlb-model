#!/usr/bin/env python3
"""WNBA Signal Push — grades completed games and pushes to GitHub."""
import json, subprocess, sys, os
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(ROOT)

SIGNALS_PATH = ROOT / "wnba" / "data" / "signals" / "wnba_signals_2025.json"

def main():
    if not SIGNALS_PATH.exists():
        print("No signals file found.")
        return

    with open(SIGNALS_PATH) as f:
        signals = json.load(f)

    # Grade pending signals (placeholder — needs game results)
    graded = 0
    pending = sum(1 for s in signals if s.get("status") == "PRELIMINARY")

    if graded == 0:
        print(f"No changes to push. {pending} pending signals.")
        return

    with open(SIGNALS_PATH, "w") as f:
        json.dump(signals, f, indent=2)

    try:
        subprocess.run(["git", "add", "-f", str(SIGNALS_PATH)], cwd=str(ROOT), check=True)
        subprocess.run(["git", "commit", "-m", f"wnba signals: {date.today().isoformat()}"],
                       cwd=str(ROOT), check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT), check=True)
        print(f"Pushed: {graded} graded, {pending} pending")
    except Exception as e:
        print(f"Git push failed: {e}")

if __name__ == "__main__":
    main()
