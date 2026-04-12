# Phase 4: Operational Path Check

## Daily Execution Chain

### 1. Signal Generation
- `run_model.py` line 1338 calls `f5rl_daily(game_date, schedule=games, pitcher_db=pitcher_db)`
- `run_daily()` in signal generator:
  1. Bootstraps tracker files if missing
  2. Resolves pending signals (grades yesterday results)
  3. Computes performance stats
  4. Checks hard stop (ROI < -10% at N >= 40)
  5. Checks status file (blocks only if PAUSED)
  6. Pulls F5 spreads from Odds API (spreads_1st_5_innings market)
  7. Generates new signals where gap >= 1.5

### 2. Data Push
- `push_results.py` line 411 includes `mlb_sim/logs/f5_runline_2026.json` in dashboard push
- JSON is auto-generated alongside parquet by `_save_signals()`

### 3. Dashboard Display
- `dashboard_original_pre_refactor.py` references:
  - Green pill "Signal B (F5 RL)" when status is ACTIVE (lines 1234, 3235)
  - Tracker tab loads `f5_runline_2026.json` (lines 3326, 3576, 5930)
  - Computes W-L-P record and ROI for signal board (line 5969)
- **Current status is SHADOW** -- dashboard should not show green pill
  - Dashboard checks status file: only shows green pill when status == ACTIVE
  - With SHADOW status, pill will not appear (correct behavior)

### 4. F5 Spread Collection
- Uses per-event Odds API endpoint for `spreads_1st_5_innings`
- Prefers FanDuel book, validates -0.5/+0.5 spread format
- Lines stored in `f5_runline_lines_2026.parquet`
- Lines must be available for signal to fire (no line = no signal)

### 5. Grading
- MLB Stats API linescore endpoint for F5 scores
- Same-day resolution when game data available
- Auto-grades on next day run via resolve_signals()

## Path Status: OPERATIONAL
All components are wired and functional. The threshold fix is the only
code change needed. No rewiring, no new integrations required.
