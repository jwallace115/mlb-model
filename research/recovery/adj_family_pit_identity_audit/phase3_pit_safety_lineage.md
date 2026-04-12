# Phase 3 — PIT-Safety Lineage

## Feature Source
File: `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet`
- 19,430 rows, seasons 2022-2025
- Date range: 2022-04-07 to 2025-09-28
- 729 unique pitchers

## Build Script: `research/opponent_adjusted_engine_v2/build_v2.py`

### Data Sources (from source_audit.md)
| Source | Rows | Purpose |
|--------|------|---------|
| sim/data/game_table.parquet | 9715 | Game IDs, dates, teams |
| sim/data/feature_table.parquet | 9715 | SP xFIP, park factors (used for context, NOT for ADJ features) |
| sim/data/cache/boxscores/ | 9715 JSON | Team batting + pitcher per-start stats |
| opponent_adjusted_engine/pitcher_start_adjusted_metrics.parquet | 19430 | V1 per-start K/BB/IP/ER |
| statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | 17906 | Hard-hit% per start |

### PIT-Safety Analysis

**Step 1 — Offensive Expectation Table**
- Team rolling 20-game means with `shift(1)` — SAFE (no current-game data)
- `shift(1).rolling(20, min_periods=10).mean()` — proper lagged rolling

**Step 2 — Pitcher Start Performance**
- Per-start stats extracted from individual boxscores (K, BB, H, HR, R, IP)
- These are game-level actuals, not aggregated season stats — SAFE

**Step 3 — Opponent Adjustment**
- `adj_k_rate = pitcher_k_rate - team_k_rate` (team_k_rate from shifted rolling)
- `adj_contact_rate = team_contact_rate - pitcher_contact_rate`
- `adj_hard_hit_rate = league_avg_hh - pitcher_hh` (league avg computed once)
- `adj_run_suppression = expected_runs - actual_runs`
- All opponent adjustments use LAGGED team rolling means — SAFE

**Step 4 — Recent Form Rolling**
- `shift(1).rolling(w, min_periods=minp).mean()` where w=3 or 5
- Proper lagged rolling on per-start data — SAFE

### feature_table.parquet Usage
`feature_table.parquet` is imported in line 28 but is used ONLY in the source audit
print statements (line 53). It is NOT used to compute any ADJ features. The ADJ
features derive entirely from boxscore-extracted per-start pitcher stats and
shifted-rolling team offensive expectations.

### Verdict: PIT-SAFE
No lookahead contamination. All rolling features use shift(1). Team expectations
use 20-game lagged rolling means. Feature source is per-game boxscores, not
season-level aggregates.

## Staleness Issue
The parquet file ends at 2025-09-28. The live code uses `groupby("pitcher_id").last()`
to get each pitcher's most recent form. For 2026 shadow:
- 368/729 pitchers have their last row from 2025 (most current)
- 142/729 from 2024
- 219/729 from earlier (likely retired/minors)

This means 2026 signals use FROZEN end-of-2025 rolling form. The feature is not
being updated with 2026 starts. This is a known limitation that will degrade
signal quality as the 2026 season progresses.
