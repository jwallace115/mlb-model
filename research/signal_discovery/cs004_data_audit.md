# CS004 Data Audit — Bullpen Collapse Tail Risk

**Date:** 2026-03-27
**Status:** Data fully available — no gaps

---

## Data Required for CS004

| Field | Description | Required For |
|:------|:------------|:-------------|
| pitcher_id | Reliever identifier | Per-appearance tracking |
| game_pk | Game identifier | Join to game outcomes |
| game_date | Date | Rolling window ordering |
| team | Team abbreviation | Team-level aggregation |
| innings_pitched | IP per appearance | Activity tracking |
| runs_allowed | Runs per appearance | Variance + max computation |
| starter_flag | 0 = reliever | Filtering starters out |

---

## Available Sources

### Primary: `mlb/data/pitcher_game_logs.parquet`

**Status: COMPLETE — contains everything CS004 needs.**

| Metric | Value |
|:-------|:------|
| Total rows | 83,042 |
| Reliever rows (starter_flag=0) | 63,612 |
| Seasons | 2022, 2023, 2024, 2025 |
| runs_allowed coverage | 100% |
| innings_pitched coverage | 100% |
| Game table match rate (2023-2024) | 4,855 / 4,857 (99.96%) |

**Reliever appearances by season:**

| Season | Appearances | Unique Pitchers |
|:-------|---:|---:|
| 2022 | 16,023 | 707 |
| 2023 | 15,774 | 711 |
| 2024 | 15,822 | 668 |
| 2025 | 15,993 | 713 |

**Rolling window feasibility:**
- Mean reliever appearances per team-game: 3.3
- 99.6% of team-games meet the "8 appearances in last 10 games" minimum window requirement
- Rolling 10-game variance and max are computable for virtually all games

### Secondary Sources (not needed but available)

| Source | Grain | Use |
|:-------|:------|:----|
| `sim/data/bullpen_usage.parquet` (83,042 rows) | pitcher × game | Has pitches_thrown, games_finished; redundant with pitcher_game_logs |
| `sim/data/bullpen_features.parquet` (19,302 rows) | team × game | Pre-computed bullpen workload features; does not have per-reliever runs_allowed |
| `research/data_pulls/reliever_role_tracking.parquet` (9,715 rows) | game | Closer/setup availability flags; useful supplement but not core |

### Sources That Do NOT Have Reliever Data

| Source | Issue |
|:-------|:------|
| `research/statcast_enrichment/pitcher_statcast_per_start.parquet` | Contains 279 pitchers who also relieved, but file is structured around starts, not relief appearances |
| `data/mlb_model.db` (SQLite) | Has `home_bullpen_innings` / `away_bullpen_innings` in graded_results but only 210 games (2026 season) — aggregated, not per-reliever |
| `sim/data/game_table.parquet` | Has `actual_f5_total` which allows late-inning run derivation, but no bullpen-specific breakdown |

---

## Gap Analysis

### What exists and is sufficient

`mlb/data/pitcher_game_logs.parquet` has complete per-reliever, per-appearance run data for all four seasons. This is the exact dataset the batch 1 CS004 test used. No additional data is needed.

### What is missing

**Nothing.** The CS004 computation chain is fully supported:

1. Filter to `starter_flag == 0` → 63,612 reliever appearances
2. Group by `(game_pk, team)` → team-game bullpen summaries
3. Sort by `(team, game_date)` → temporal ordering
4. Rolling 10-game window with `shift(1)` → pregame-safe features
5. Compute `var(runs_allowed)` and `max(runs_allowed)` per window
6. Combine into `tail_score`, apply frozen threshold → signal flag
7. Merge to `game_table.parquet` via `game_pk` for closing totals and outcomes

### External pull required

**None.** No pybaseball, MLB Stats API, or Statcast pull is needed. The data is entirely local and complete.

### Can the data be reconstructed from other sources?

Not applicable — the primary source already exists. However, if `pitcher_game_logs.parquet` were unavailable, the identical data could be reconstructed from `sim/data/bullpen_usage.parquet` (which has the same 83,042 rows including `innings_pitched`) by joining back to `pitcher_game_logs` for `runs_allowed` — but this is unnecessary since the primary file is complete.

---

## Summary

| Question | Answer |
|:---------|:-------|
| Is data sufficient for CS004 backtesting? | **Yes — fully available** |
| Seasons covered | 2022, 2023, 2024, 2025 |
| Coverage for 2023-2024 specifically | 99.96% game match rate |
| External pull needed | **No** |
| Reconstruction needed | **No** |
| Best source | `mlb/data/pitcher_game_logs.parquet` (starter_flag=0) |
