#!/usr/bin/env python3
"""WNBA Archetype Board — Pipeline Validator."""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(ROOT)

checks = []

def check(name, fn):
    try:
        ok = fn()
        checks.append((name, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    except Exception as e:
        checks.append((name, False))
        print(f"  [FAIL] {name}: {e}")

print("WNBA Archetype Board Validation")
print("=" * 50)

check("Signal registry exists", lambda: os.path.exists(
    "wnba_archetype_board/config/archetype_signal_registry.json"))

check("Registry has confidence_tier", lambda: all(
    "confidence_tier" in s for s in json.load(
        open("wnba_archetype_board/config/archetype_signal_registry.json"))))

check("Registry has 7 signals", lambda: len(json.load(
    open("wnba_archetype_board/config/archetype_signal_registry.json"))) == 7)

check("Historical performance exists", lambda: os.path.exists(
    "wnba_archetype_board/reports/historical_signal_performance.csv"))

check("Signal tracker exists", lambda: os.path.exists(
    "wnba_archetype_board/data/logs/signal_tracker.parquet"))

check("2026 signals JSON valid", lambda: isinstance(json.load(
    open("wnba_archetype_board/data/signals/wnba_archetype_signals_2026.json")), list))

check("Backfill signals exist", lambda: len(json.load(
    open("wnba_archetype_board/data/signals/wnba_archetype_signals_backfill_2022_2025.json"))) > 0)

check("Assign archetypes script exists", lambda: os.path.exists(
    "wnba_archetype_board/pipeline/assign_archetypes.py"))

n_pass = sum(1 for _, ok in checks if ok)
print(f"\n{n_pass}/{len(checks)} passed")
sys.exit(0 if n_pass == len(checks) else 1)
