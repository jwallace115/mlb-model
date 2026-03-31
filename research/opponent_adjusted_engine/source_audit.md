# Source Audit — Opponent-Adjusted Engine v1

| # | File | Rows | Purpose |
|---|------|------|---------|
| 1 | sim/data/game_table.parquet | 9715 | Canonical game table (2022-2025) |
| 2 | sim/data/feature_table.parquet | 9715 | SP xFIP/K%/BB%, park factors, weather |
| 3 | sim/data/bullpen_usage.parquet | 83042 | Pitcher appearances (starter identification) |
| 4 | research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | 17906 | HH%, barrel%, whiff% per start |
| 5 | sim/data/bet_results.parquet | 4855 | Closing lines + outcomes (2024-2025) |
| 6 | sim/data/cache/boxscores/ | 9715 JSON | Team batting + pitcher K/BB/strikes per game |

## Key Decisions
- Team offense rolling: K_rate, BB_rate, runs/game from boxscore team batting lines (last 20 games)
- CSW proxy: strikes/pitches from boxscores (strike percentage; best available without pitch-level classify)
- Hard-hit/barrel: raw from Statcast per-start; adjustment uses opponent runs_per_game as quality proxy
  (no team-level hard-hit data available from boxscores)
- Evaluation: 2024+2025 with closing lines (4,855 games)
