# Source Audit — Yesterday Rollforward Check

## Date Context
- Today: 2026-03-27
- Yesterday: 2026-03-26

## Data Files

| File | Rows | Max Date | Modified |
|------|------|----------|----------|
| sim/data/game_table.parquet | 9,715 | 2025-09-28 | 2026-03-15 |
| sim/data/feature_table.parquet | 9,715 | 2025-09-28 | 2026-03-15 |
| sim/data/bullpen_usage.parquet | 83,042 | 2025-09-28 | 2026-03-15 |
| sim/data/bullpen_features.parquet | 19,302 | 2025-09-28 | 2026-03-15 |
| sim/data/phase5_sim_results.parquet | 4,855 | 2025-09-28 | 2026-03-15 |
| sim/data/phase9_baseline_model.pkl | — | — | 2026-03-15 |
| data/mlb_model.db (results table) | — | 2026-03-26 | live |

## Key Finding
- ALL parquet files in sim/data/ have max date 2025-09-28
- They have NOT been updated since 2026-03-15
- They contain ZERO 2026 games
- The SQLite database (mlb_model.db) DOES have 2026 results through 2026-03-26
- The live simulation pipeline does NOT read from the parquet files for daily projections
