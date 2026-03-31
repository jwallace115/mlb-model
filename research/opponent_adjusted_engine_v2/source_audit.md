# Source Audit — Opponent-Adjusted Engine V2

## Primary Sources
| File | Rows | Seasons | Purpose |
|------|------|---------|---------|
| sim/data/game_table.parquet | 9715 | 2022-2025 | Canonical game table |
| sim/data/feature_table.parquet | 9715 | 2022-2025 | SP xFIP, park factors |
| sim/data/bet_results.parquet | 4855 | 2024-2025 | Closing lines, outcomes |
| sim/data/phase5_sim_results.parquet | 4855 | 2024-2025 | V1 p_under |
| research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | 17906 | 2022-2025 | HH%, barrel%, whiff% |
| sim/data/cache/boxscores/ | 9715 JSON | 2022-2025 | Team batting + pitcher stats |

## V1 Engine Reuse
| File | Rows | Purpose |
|------|------|---------|
| research/opponent_adjusted_engine/offense_expectation_table.parquet | 19430 | Team K/BB/runs rolling 20g |
| research/opponent_adjusted_engine/pitcher_start_adjusted_metrics.parquet | 19430 | Pitcher K/BB/IP/ER per start |

## Key Fields
- game_pk: integer game ID (join key across all tables)
- date: game date (datetime)
- pitcher_id: MLB player ID
- team/opponent: 3-letter abbreviation
- side: home/away
