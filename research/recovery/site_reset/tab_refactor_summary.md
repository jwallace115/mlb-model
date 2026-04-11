# Dashboard Modular Refactor — Tab Restructure Summary

**Date:** 2026-04-11
**Files modified:** `dashboard.py` (refactored), `dashboard_components.py` (created)
**Backup:** `dashboard_original_pre_refactor.py`

## Architecture

### Before
- `dashboard.py`: 6,166 lines, monolithic
- 11 tabs: Home, MLB, NBA, NHL, Soccer, NFL, Golf, WNBA, NCAAF, Reviews, Tracker
- All rendering functions, data loaders, and shared primitives in one file

### After
- `dashboard.py`: 1,047 lines
- `dashboard_components.py`: ~210 lines (shared rendering primitives)
- 9 tabs: Home, MLB, NBA, NHL, Soccer, NFL, Golf, WNBA, NCAAF
- Reviews and Tracker tabs removed

## Functions Extracted to dashboard_components.py
- `_pipeline_freshness(*keys)` — pipeline timestamp display
- `_global_freshness()` — most-recent-across-all-pipelines freshness
- `_last_run_label(data)` — ET-formatted timestamp
- `_load_last_updated()` — reads shared/last_updated.json
- `_PIPELINE_LABELS` — pipeline key → display name mapping
- `_render_game_card_universal(...)` — universal game card renderer
- `_universal_pill(label, color, bg)` — signal pill HTML
- `_render_signal_status_row(active, shadow)` — active/shadow pill rows
- `load_golf_results()` — golf data loader (cached)
- `load_nba_results()` — NBA data loader
- `load_nhl_results()` — NHL data loader
- `load_soccer_results()` — soccer data loader

## Tabs Removed
- **Reviews** (`_render_reviews_tab`) — checkpoint/weekly digest viewer
- **Tracker** (`_render_tracker_tab`) — cross-sport performance tracker (~420 lines)

## Tabs Stubbed (body replaced with placeholder)
- MLB: `st.markdown("**System reset — rebuilding.**")`
- NBA: same
- Soccer: same
- NFL: same
- WNBA: same
- NCAAF: same
- NHL: `pass` (clean design session pending)

## Tabs Preserved Exactly
- **Golf** — all 384 lines of `_render_golf_tab()` preserved byte-for-byte (verified via diff)
- **Home** — `_render_home_tab()` preserved (150 lines), uses shared loaders from dashboard_components

## Dead Code Removed
The following were removed by virtue of not being included in the new file:
- ~50 MLB-specific rendering functions (_render_card, _lean_badge, _conf_badge, etc.)
- ~20 NBA-specific rendering functions (_nba_lean_badge, etc.)
- ~15 NHL-specific rendering functions (_render_nhl_signal_card, etc.)
- ~15 Soccer-specific rendering functions (_soccer_league_label, etc.)
- ~15 NFL-specific rendering functions
- ~30 WNBA archetype functions and constants (_ARCH_SHORT, etc.)
- ~20 NCAAF rendering functions
- All MLB shadow/HR override logic
- All parlay rendering logic
- All analytics/season header rendering
- All tracker cross-sport aggregation logic

## Imports Cleaned
Retained only: `json`, `os`, `datetime`, `pandas`, `streamlit`, `dashboard_components`
Removed implicit dependencies on: `math`, `zoneinfo`, `re` (now only used within preserved tabs as needed)

## Verification
- `py_compile.compile('dashboard.py')`: PASS
- `py_compile.compile('dashboard_components.py')`: PASS
- `streamlit run dashboard.py --server.headless true`: starts cleanly, no errors
- Golf tab diff (before vs after): zero differences
- Streamlit process restarted on production server (PID verified)

## Rollback
If needed: `cp dashboard_original_pre_refactor.py dashboard.py` and restart streamlit.
