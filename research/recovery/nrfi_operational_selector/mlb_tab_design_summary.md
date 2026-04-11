# MLB Tab Design Summary — NRFI Selector Display

**Date:** 2026-04-11
**File modified:** `dashboard.py` (`_render_mlb_tab()` only)
**Status:** SHADOW

## What was built

Replaced the `_render_mlb_tab()` stub ("System reset — rebuilding.") with a full
NRFI Daily Selector display. No other functions or files were modified.

## Layout (top to bottom)

1. **Status header** — Uses shared `render_status_header()` component.
   Object ID: `mlb_nrfi_selector_v1_20260411`, status badge: SHADOW.

2. **Signal status row** — Uses shared `_render_signal_status_row()`.
   No active signals; one shadow signal ("NRFI Selector").

3. **Frozen selector ruleset** — Static HTML block displaying the four rules:
   qualify (F5 <= 4.0), disqualify (night + F5 = 4.0), rank (ascending), card (top 3).

4. **Today's NRFI card** — Reads `mlb/logs/nrfi_selector_v1_2026.json`, filters
   to today's `run_date` + `selected_top3`. Renders each selection as a game card
   via shared `_render_game_card_universal()` with rank pill, NRFI pill, F5 total,
   and game time converted to ET. Falls back to "No selections today" if empty.

5. **Shadow tracker** — Aggregate record (W-L), leg hit %, card hit % (all legs
   won on a slate), resolved/pending counts. Rendered as a styled summary bar.

6. **Tracker table** — `st.dataframe` of all resolved selections: Date, Rank,
   Matchup, F5, Result (NRFI/YRFI), W/L. Sorted by date + rank.

## Data source

Single JSON file: `mlb/logs/nrfi_selector_v1_2026.json`
- Keyed on `selections` array
- Deduped by `game_pk` at render time
- Filtered to `selected_top3 == true` for display

## Verification

- `py_compile` passed (syntax OK)
- Other tab functions unchanged (golf, nba, nhl all present)
- `streamlit-dashboard` service restarted and running
