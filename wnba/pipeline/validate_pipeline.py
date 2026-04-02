#!/usr/bin/env python3
"""WNBA Pipeline Validator — quick sanity checks."""
import json, pickle, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
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

print("WNBA Pipeline Validation")
print("=" * 50)

check("Feature table exists", lambda: os.path.exists("wnba/data/canonical/wnba_feature_table.parquet"))

check("Model loads and predicts", lambda: (
    pickle.load(open("wnba/models/ridge_wnba.pkl", "rb")).predict([[0]*17])[0] > 0
))

check("Scaler loads", lambda: pickle.load(open("wnba/models/scaler_wnba.pkl", "rb")) is not None)

check("Feature config valid", lambda: (
    len(json.load(open("wnba/models/feature_config_wnba.json"))["feature_list"]) == 17
))

check("Signals 2025 valid JSON", lambda: isinstance(json.load(open("wnba/data/signals/wnba_signals_2025.json")), list))

check("Signals 2024 has entries", lambda: len(json.load(open("wnba/data/signals/wnba_signals_2024.json"))) > 0)

n_pass = sum(1 for _, ok in checks if ok)
print(f"\n{n_pass}/{len(checks)} passed")
sys.exit(0 if n_pass == len(checks) else 1)
