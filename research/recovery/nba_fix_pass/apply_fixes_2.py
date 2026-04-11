#!/usr/bin/env python3
"""
NBA Parity Fix Pass — Part 2: Wire location splits into feat_row,
apply injury parity decision, and update playoff blend.
"""
import sys

filepath = "/root/mlb-model/nba/run_nba.py"

with open(filepath, "r") as f:
    content = f.read()

changes = []

# ══════════════════════════════════════════════════════════════════════════════
# FIX 3: Wire location-split values into Ridge feat_row
# Training uses home team's HOME location rolling for home_ortg,
# away team's AWAY location rolling for away_ortg (and same for drtg, pace).
# ══════════════════════════════════════════════════════════════════════════════

old_feat_row = '''        # Build feature vector (unchanged — playoff blending modified the state values above)
        feat_row = {
            "home_ortg":       home_state["ortg"],
            "away_ortg":       away_state["ortg"],
            "home_drtg":       home_state["drtg"],
            "away_drtg":       away_state["drtg"],
            "home_pace":       home_state["pace"],
            "away_pace":       away_state["pace"],
            "b2b_flag_away":   b2b_away,
            "home_ortg_trend": home_state["ortg_trend"],
            "away_ortg_trend": away_state["ortg_trend"],
            "home_pace_trend": home_state["pace_trend"],
            "away_pace_trend": away_state["pace_trend"],
            "home_3pa_rate":   home_state["fg3a_rate"],
            "away_3pa_rate":   away_state["fg3a_rate"],
            "home_ft_rate":    home_state["ft_rate"],
            "away_ft_rate":    away_state["ft_rate"],
        }'''

new_feat_row = '''        # Build feature vector
        # FIX 2026-04-11: Use location-split values to match training features.py
        # home_ortg = home team's ORtg from home games only (with overall fallback)
        # away_ortg = away team's ORtg from away games only (with overall fallback)
        # Injury adjustment NOT applied to Ridge features (training had injury_adj=0.0)
        feat_row = {
            "home_ortg":       home_state_raw.get("ortg_home", home_state_raw["ortg"]),
            "away_ortg":       away_state_raw.get("ortg_away", away_state_raw["ortg"]),
            "home_drtg":       home_state_raw.get("drtg_home", home_state_raw["drtg"]),
            "away_drtg":       away_state_raw.get("drtg_away", away_state_raw["drtg"]),
            "home_pace":       home_state_raw.get("pace_home", home_state_raw["pace"]),
            "away_pace":       away_state_raw.get("pace_away", away_state_raw["pace"]),
            "b2b_flag_away":   b2b_away,
            "home_ortg_trend": home_state_raw["ortg_trend"],
            "away_ortg_trend": away_state_raw["ortg_trend"],
            "home_pace_trend": home_state_raw["pace_trend"],
            "away_pace_trend": away_state_raw["pace_trend"],
            "home_3pa_rate":   home_state_raw["fg3a_rate"],
            "away_3pa_rate":   away_state_raw["fg3a_rate"],
            "home_ft_rate":    home_state_raw["ft_rate"],
            "away_ft_rate":    away_state_raw["ft_rate"],
        }'''

if old_feat_row in content:
    content = content.replace(old_feat_row, new_feat_row)
    changes.append("FIX 3: feat_row now uses location-split values from raw state (pre-injury)")
    print(changes[-1])
else:
    print("WARNING: feat_row block not found")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# FIX 4: Playoff blend parity — also blend location-split keys
# Update _blend_playoff_features to blend ortg_home/ortg_away/pace_home/pace_away
# ══════════════════════════════════════════════════════════════════════════════

old_blend = '''    blends = [
        ("ortg", f"{role}_ortg_rolling_series"),
        ("pace", f"{role}_pace_rolling_series"),
    ]
    for state_key, series_key in blends:
        series_val = series_roll.get(series_key)
        if series_val is not None and not np.isnan(series_val):
            state[state_key] = round(
                w_playoff * series_val + w_reg * state[state_key], 2
            )'''

new_blend = '''    blends = [
        ("ortg", f"{role}_ortg_rolling_series"),
        ("pace", f"{role}_pace_rolling_series"),
    ]
    for state_key, series_key in blends:
        series_val = series_roll.get(series_key)
        if series_val is not None and not np.isnan(series_val):
            state[state_key] = round(
                w_playoff * series_val + w_reg * state[state_key], 2
            )
            # FIX 2026-04-11: Also blend location-split keys so feat_row stays aligned
            for loc_suffix in ["_home", "_away"]:
                loc_key = state_key + loc_suffix
                if loc_key in state:
                    state[loc_key] = round(
                        w_playoff * series_val + w_reg * state[loc_key], 2
                    )'''

if old_blend in content:
    content = content.replace(old_blend, new_blend)
    changes.append("FIX 4: _blend_playoff_features now also blends location-split keys")
    print(changes[-1])
else:
    print("WARNING: playoff blend block not found")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# FIX 5: Ensure LOCATION_MIN_GAMES is imported
# ══════════════════════════════════════════════════════════════════════════════

# Check if LOCATION_MIN_GAMES is already imported
if "LOCATION_MIN_GAMES" not in content.split("def _build_current_team_states")[0]:
    # Find the config import block and add it
    # Look for the existing import from nba.config
    import_marker = "from nba.config import ("
    if import_marker in content:
        # Find what's imported and check
        import_block_start = content.index(import_marker)
        import_block_end = content.index(")", import_block_start) + 1
        import_block = content[import_block_start:import_block_end]
        if "LOCATION_MIN_GAMES" not in import_block:
            # Add it before the closing paren
            old_close = import_block.rstrip()
            if old_close.endswith(")"):
                # Find the last line before )
                lines = import_block.split("\n")
                # Insert before last line
                last_line = lines[-1]
                # Add LOCATION_MIN_GAMES before the closing paren
                new_import = import_block.replace(
                    "\n)",
                    "\n    LOCATION_MIN_GAMES,\n)"
                )
                content = content[:import_block_start] + new_import + content[import_block_end:]
                changes.append("FIX 5: Added LOCATION_MIN_GAMES to config imports")
                print(changes[-1])
            else:
                print("WARNING: Unexpected import block format")
        else:
            print("LOCATION_MIN_GAMES already imported")
    else:
        print("WARNING: Config import block not found")
else:
    print("LOCATION_MIN_GAMES already available")

with open(filepath, "w") as f:
    f.write(content)

print(f"\n{len(changes)} additional fixes applied to {filepath}")
