#!/usr/bin/env python3
import json, pickle, os
checks = [
    ("Anchor game table", os.path.exists("wnba_anchor/data/canonical/wnba_anchor_game_table.parquet")),
    ("Anchor feature table", os.path.exists("wnba_anchor/data/canonical/wnba_anchor_feature_table.parquet")),
    ("Anchor model", os.path.exists("wnba_anchor/models/ridge_anchor_wnba.pkl")),
    ("Variance map", os.path.exists("wnba_anchor/models/residual_variance_model.json")),
    ("Signals 2024", os.path.exists("wnba_anchor/data/signals/wnba_anchor_signals_2024.json")),
]
for name, ok in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
print(f"{sum(ok for _,ok in checks)}/{len(checks)} passed")
