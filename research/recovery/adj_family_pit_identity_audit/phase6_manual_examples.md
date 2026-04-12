# Phase 6 — Manual Examples

## ADJ_HH Favorable Zone Examples (2026 shadow)

### Example 1: 2026-03-28 OAK@TOR
- combined ADJ_HH value: 0.1116
- closing_total: 8.0
- actual_total: 15.0
- Result: OVER (signal WRONG)
- V1 context: NONE

### Example 2: 2026-03-28 CLE@SEA
- combined ADJ_HH value: 0.0232
- closing_total: 7.0
- actual_total: 11.0
- Result: OVER (signal WRONG)
- V1 context: NONE

### Example 3: 2026-03-28 NYY@SFG
- combined ADJ_HH value: 0.0021
- closing_total: 8.5
- actual_total: 4.0
- Result: UNDER (signal CORRECT)
- V1 context: NONE

### Example 4: 2026-03-28 DET@SDP
- combined ADJ_HH value: 0.0452
- closing_total: 8.0
- actual_total: 3.0
- Result: UNDER (signal CORRECT)
- V1 context: NONE

### Example 5: 2026-03-28 CHW@MIL
- combined ADJ_HH value: 0.0117
- closing_total: 8.5
- actual_total: 7.0
- Result: UNDER (signal CORRECT)
- V1 context: NONE

## Feature Trace Notes
- All examples use frozen end-of-2025 pitcher form values
- The parquet file (pitcher_recent_adjusted_features.parquet) uses
  `groupby("pitcher_id").last()` so each pitcher gets their final 2025 rolling value
- Opening Day starters in 2026 are mapped to their September 2025 rolling form
- This is reasonable for early April but will degrade rapidly
