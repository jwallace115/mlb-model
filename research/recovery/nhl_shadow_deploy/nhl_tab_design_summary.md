# NHL Tab Build -- Design Summary

## Date: April 11, 2026

## Files Modified
- dashboard_components.py -- added render_status_header() reusable component
- dashboard.py -- replaced _render_nhl_tab() stub with full implementation

## render_status_header() Component
Reusable status header for any rebuilt sport tab. Accepts:
- object_name: display name with optional emoji
- object_id: machine-readable tracker ID
- status: one of LIVE / SHADOW / INACTIVE / ARCHIVED (badge color-coded)
- tracker_start: human-readable start date
- current_threshold: edge threshold (shown for LIVE/SHADOW/INACTIVE)
- replaces: prior system being replaced (shown in muted text)
- last_updated: pipeline timestamp string

Badge colors: green (LIVE), yellow (SHADOW), gray (INACTIVE), red (ARCHIVED).

## NHL Tab Sections
1. Status header -- SHADOW badge, object ID nhl_shadow_aligned_20260411, threshold edge >= 0.12
2. Signal status pills -- shows which tiers (HIGH/MEDIUM/LOW) have fired, red pills
3. Shadow ruleset block -- displays drift=0, tier thresholds, disabled legacy features
4. Today's signals -- game cards for current date from nhl_shadow_aligned_2026.json
5. Shadow tracker summary -- W-L-P record, hit rate, ROI (flat -110), resolved/pending counts
6. Signal table -- pandas dataframe with Date/Matchup/Dir/Total/Edge/Tier/Result
7. Legacy disclosure -- archived system notice, excludes 12-7 legacy record from current metrics

## Data Source
- nhl/logs/nhl_shadow_aligned_2026.json
- Structure: {model_version, object_id, start_date, signals: [...]}
- Signal fields: game_id, game_date, home_team, away_team, signal_side, edge, tier, closing_total, lambda_total, drift_applied
- Tier values: SHADOW_HIGH, SHADOW_MEDIUM, SHADOW_LOW (prefix stripped for display)

## Verification
- Both files compile cleanly (py_compile)
- Golf tab unchanged (1 definition)
- MLB/NBA/Soccer tabs remain stubbed
- Streamlit service restarted and serving on port 8501
- No other files modified
