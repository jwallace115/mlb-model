#!/usr/bin/env python3
"""
NBA Parity Fix Pass — Part 3: Ensure playoff blend also applies to raw state
(used by feat_row for Ridge predictions).
"""
import sys

filepath = "/root/mlb-model/nba/run_nba.py"

with open(filepath, "r") as f:
    content = f.read()

# Add playoff blend to home_state_raw as well
old_playoff_blend = '''                # Blend regular-season rolling with series rolling
                home_state = _blend_playoff_features(home_state, series_roll, "home", w_p)
                away_state = _blend_playoff_features(away_state, series_roll, "away", w_p)'''

new_playoff_blend = '''                # Blend regular-season rolling with series rolling
                home_state = _blend_playoff_features(home_state, series_roll, "home", w_p)
                away_state = _blend_playoff_features(away_state, series_roll, "away", w_p)
                # FIX 2026-04-11: Also blend raw state so Ridge feat_row gets playoff data
                home_state_raw = _blend_playoff_features(home_state_raw, series_roll, "home", w_p)
                away_state_raw = _blend_playoff_features(away_state_raw, series_roll, "away", w_p)'''

if old_playoff_blend in content:
    content = content.replace(old_playoff_blend, new_playoff_blend)
    print("FIX 6: Playoff blend now also applied to raw state for Ridge feat_row")
else:
    print("WARNING: Playoff blend block not found")
    sys.exit(1)

with open(filepath, "w") as f:
    f.write(content)

print("Fix applied.")
