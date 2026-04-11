#!/usr/bin/env python3
"""
NBA Parity Fix Pass — Apply all fixes to run_nba.py
Run on the server: python3 /root/mlb-model/research/recovery/nba_fix_pass/apply_fixes.py
"""
import sys
import os

filepath = "/root/mlb-model/nba/run_nba.py"

with open(filepath, "r") as f:
    content = f.read()

changes = []

# ══════════════════════════════════════════════════════════════════════════════
# FIX 1: Kill ELITE_DEF2 signal
# ══════════════════════════════════════════════════════════════════════════════

old_elite = '        if away in _ELITE_DEF2 and home in _ELITE_DEF:'
new_elite = '        # KILLED 2026-04-11 — revalidation verdict: COLLAPSES (43% OOS, -18% ROI)\n        if False:  # was: away in _ELITE_DEF2 and home in _ELITE_DEF'

if old_elite in content:
    content = content.replace(old_elite, new_elite)
    changes.append("FIX 1: ELITE_DEF2 signal killed (if False guard)")
    print(changes[-1])
else:
    print("WARNING: ELITE_DEF2 block not found or already fixed")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# FIX 2: Location-split feature alignment in _build_current_team_states
# ══════════════════════════════════════════════════════════════════════════════

# 2a: Update docstring
old_doc = '''    """
    Compute rolling efficiency state for each team as of game_date.

    For live use (unlike training), we include the team\'s most recent completed
    game in the rolling window (no shift). Rolling window = 15 games.

    Returns dict: {team_abbr: {ortg, drtg, pace, fg3a_rate, ft_rate,
                                ortg_trend, pace_trend, games_in_season}}
    """'''

new_doc = '''    """
    Compute rolling efficiency state for each team as of game_date.

    Uses location-specific rolling for ortg/drtg/pace (home games only for
    home team features, away games only for away team features) to match
    training features.py. Falls back to overall rolling if fewer than
    LOCATION_MIN_GAMES same-location games available.
    Rolling window = 15 games.

    Returns dict: {team_abbr: {ortg, drtg, pace, fg3a_rate, ft_rate,
                                ortg_trend, pace_trend, games_in_season,
                                ortg_home, drtg_home, pace_home,
                                ortg_away, drtg_away, pace_away}}
    """'''

if old_doc in content:
    content = content.replace(old_doc, new_doc)
    changes.append("FIX 2a: Updated docstring for location splits")
    print(changes[-1])
else:
    print("WARNING: Old docstring not found")
    sys.exit(1)

# 2b: Replace rolling computation block
old_rolling = """        n = len(cur)
        recent15 = cur.tail(ROLLING_WINDOW)
        recent5  = cur.tail(5)

        ortg_roll15 = recent15["ortg"].mean()
        drtg_roll15 = recent15["drtg"].mean()
        pace_roll15 = recent15["pace"].mean()

        ortg_roll5 = recent5["ortg"].mean() if len(recent5) >= 3 else ortg_roll15
        pace_roll5 = recent5["pace"].mean() if len(recent5) >= 3 else pace_roll15

        ortg_trend = round(float(ortg_roll5 - ortg_roll15), 3)
        pace_trend = round(float(pace_roll5 - pace_roll15), 3)

        # Style features
        fg3a_rate = recent15["fg3a_rate"].mean() if "fg3a_rate" in cur.columns else 0.36
        ft_rate   = recent15["ft_rate"].mean()   if "ft_rate"   in cur.columns else 0.28

        # Prior-season blending for early season
        bl = baselines.get((team, CURRENT_SEASON), {})
        ortg = _blend(ortg_roll15, bl.get("ortg", np.nan), n)
        drtg = _blend(drtg_roll15, bl.get("drtg", np.nan), n)
        pace = _blend(pace_roll15, bl.get("pace", np.nan), n)

        states[team] = {
            "ortg":          round(float(ortg), 2),
            "drtg":          round(float(drtg), 2),
            "pace":          round(float(pace), 2),
            "fg3a_rate":     round(float(fg3a_rate), 4),
            "ft_rate":       round(float(ft_rate), 4),
            "ortg_trend":    ortg_trend,
            "pace_trend":    pace_trend,
            "games_in_season": n,
        }"""

new_rolling = """        n = len(cur)
        recent15 = cur.tail(ROLLING_WINDOW)
        recent5  = cur.tail(5)

        # Overall rolling (used for trends and fallback)
        ortg_roll15 = recent15["ortg"].mean()
        drtg_roll15 = recent15["drtg"].mean()
        pace_roll15 = recent15["pace"].mean()

        ortg_roll5 = recent5["ortg"].mean() if len(recent5) >= 3 else ortg_roll15
        pace_roll5 = recent5["pace"].mean() if len(recent5) >= 3 else pace_roll15

        ortg_trend = round(float(ortg_roll5 - ortg_roll15), 3)
        pace_trend = round(float(pace_roll5 - pace_roll15), 3)

        # Location-specific rolling (matches training features.py)
        # FIX 2026-04-11: training uses location_rolling with LOCATION_MIN_GAMES fallback
        loc_splits = {}
        for loc_label, loc_code in [("home", "H"), ("away", "A")]:
            loc_games = cur[cur["location"] == loc_code]
            loc_recent = loc_games.tail(ROLLING_WINDOW)
            if len(loc_recent) >= LOCATION_MIN_GAMES:
                loc_splits[f"ortg_{loc_label}"] = loc_recent["ortg"].mean()
                loc_splits[f"drtg_{loc_label}"] = loc_recent["drtg"].mean()
                loc_splits[f"pace_{loc_label}"] = loc_recent["pace"].mean()
            else:
                # Fallback to overall rolling (same as training features.py)
                loc_splits[f"ortg_{loc_label}"] = ortg_roll15
                loc_splits[f"drtg_{loc_label}"] = drtg_roll15
                loc_splits[f"pace_{loc_label}"] = pace_roll15

        # Style features (no location split in training)
        fg3a_rate = recent15["fg3a_rate"].mean() if "fg3a_rate" in cur.columns else 0.36
        ft_rate   = recent15["ft_rate"].mean()   if "ft_rate"   in cur.columns else 0.28

        # Prior-season blending for early season
        bl = baselines.get((team, CURRENT_SEASON), {})
        # Blend location-specific values (matches training _resolve_team_features)
        ortg_home = _blend(loc_splits["ortg_home"], bl.get("ortg", np.nan), n)
        drtg_home = _blend(loc_splits["drtg_home"], bl.get("drtg", np.nan), n)
        pace_home = _blend(loc_splits["pace_home"], bl.get("pace", np.nan), n)
        ortg_away = _blend(loc_splits["ortg_away"], bl.get("ortg", np.nan), n)
        drtg_away = _blend(loc_splits["drtg_away"], bl.get("drtg", np.nan), n)
        pace_away = _blend(loc_splits["pace_away"], bl.get("pace", np.nan), n)
        # Overall blended (for trend, style, and non-location features)
        ortg = _blend(ortg_roll15, bl.get("ortg", np.nan), n)
        drtg = _blend(drtg_roll15, bl.get("drtg", np.nan), n)
        pace = _blend(pace_roll15, bl.get("pace", np.nan), n)

        states[team] = {
            "ortg":          round(float(ortg), 2),
            "drtg":          round(float(drtg), 2),
            "pace":          round(float(pace), 2),
            # Location-split values (used by Ridge feature builder)
            "ortg_home":     round(float(ortg_home), 2),
            "drtg_home":     round(float(drtg_home), 2),
            "pace_home":     round(float(pace_home), 2),
            "ortg_away":     round(float(ortg_away), 2),
            "drtg_away":     round(float(drtg_away), 2),
            "pace_away":     round(float(pace_away), 2),
            "fg3a_rate":     round(float(fg3a_rate), 4),
            "ft_rate":       round(float(ft_rate), 4),
            "ortg_trend":    ortg_trend,
            "pace_trend":    pace_trend,
            "games_in_season": n,
        }"""

if old_rolling in content:
    content = content.replace(old_rolling, new_rolling)
    changes.append("FIX 2b: Location-split rolling added to _build_current_team_states")
    print(changes[-1])
else:
    print("WARNING: Old rolling block not found")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# FIX 3: Wire location-split values into Ridge feature row
# Need to find where feat_row is built and use home_state ortg_home / away_state ortg_away
# ══════════════════════════════════════════════════════════════════════════════

# We need to find where the feat_row dict is constructed in the main loop
# and replace ortg/drtg/pace with location-specific values

with open(filepath, "w") as f:
    f.write(content)

print(f"\n{len(changes)} fixes applied to {filepath}")
print("NOTE: FIX 3 (wiring location splits into feat_row) needs separate implementation")
