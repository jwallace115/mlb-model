# Phase 0: Signal B Locked Specification

## Identity
- **Full name:** F5 Run Line Signal B (Home)
- **File:** `mlb_sim/pipeline/f5_runline_signal_generator.py`
- **Tracker:** `mlb_sim/pipeline/f5_runline_tracker.py`
- **Signal log:** `mlb_sim/logs/f5_runline_2026.parquet` + `.json`
- **Status file:** `mlb_sim/pipeline/f5_runline_status.json`
- **Lines log:** `mlb_sim/logs/f5_runline_lines_2026.parquet`
- **Perf log:** `mlb_sim/logs/f5_runline_performance_2026.json`

## Signal Definition
- **Trigger:** `away_sp_xfip - home_sp_xfip >= XFIP_GAP_THRESHOLD`
- **Current threshold in code:** 1.0 (NEEDS CHANGE TO 1.5)
- **Bet side:** HOME only (away killed in reset audit, D4 CLEAN KILL)
- **Bet line:** Home -0.5 F5 run line (spreads_1st_5_innings market)
- **Stake:** 0.5 units per signal
- **Grading:** Home F5 margin > 0 = WIN, < 0 = LOSS, == 0 = PUSH (push counts as loss in tracker)

## Feature Source
- **xFIP source:** `modules/pitchers.get_pitcher_metrics()` -> FanGraphs API (live, daily-fresh)
- **Fallback chain:** FanGraphs API -> Savant xERA -> league average
- **NO dependency on:** V1, S12, P09, feature_table, historical xFIP, PIT FIP, sim model
- **Clean for live use:** YES — all inputs are real-time API calls

## Threshold History
- **Original deployment:** 1.0 (commit 32c687d9, never changed in code)
- **Reset audit directive (2026-04-11):** Change to 1.5
  - State map (02_state_map.md): "NEW tracker, threshold changed to 1.5"
  - Tracker reset plan (03_tracker_reset_plan.md): "Threshold changed to 1.5; old signals under 1.0 threshold are not comparable"
- **Actual code as of 2026-04-12:** STILL 1.0 (directive not implemented)

## Why 1.5?
From V1 dependency revalidation (object2_f5_runline.md), PIT FIP gap analysis:
- gap >= 1.0: under rate 50.3% (2024), 53.1% (2025) — borderline
- gap >= 1.5: under rate 59.4% (2024), 60.0% (2025) — strong, stable
The 1.0 threshold was likely a round-number heuristic. The 1.5 threshold is the
PIT-safe level that shows consistent edge in clean (non-contaminated) data.

## Historical Performance (from reset audit, at 1.0 threshold)
- Pooled ROI: +27.9% (N=335, 2024-2025)
- **Caveat:** This was measured with season-final xFIP (contaminated lookahead).
  True live-forward performance at 1.0 threshold may be lower.

## Operational Integration
- Called from `run_model.py` line 1338: `f5rl_daily(game_date, schedule=games, pitcher_db=pitcher_db)`
- JSON pushed to GitHub via `push_results.py` (line 411)
- Dashboard: referenced in `dashboard_original_pre_refactor.py` as "Signal B (F5 RL)"
- Hard stop: ROI < -10% at N >= 40 triggers automatic pause

## Key Finding: THRESHOLD NOT UPDATED
The live code still fires at gap >= 1.0. The reset audit directed 1.5.
This means:
1. The tracker has 7 entries, 6 at gap < 1.5 (contaminated era signals at old threshold)
2. Only 1 entry (2026-04-05, gap=1.503) would qualify under the 1.5 threshold
3. Code must be updated to 1.5 before reactivation
