#!/usr/bin/env python3
"""WNBA Live Data Pull — gated behind LIVE_MODE flag."""
import sys

LIVE_MODE = True

if not LIVE_MODE:
    print("Live mode disabled. Set LIVE_MODE=True to activate 2025 season data pull.")
    sys.exit(0)

# When LIVE_MODE = True:
# 1. Pull today's WNBA games from nba_api (league_id='10')
# 2. Update player_game_logs.parquet
# 3. Call build_features.py
# 4. Call run_model.py
print("WNBA live pull would execute here.")
