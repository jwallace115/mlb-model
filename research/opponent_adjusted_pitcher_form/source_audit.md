# Source Audit — Opponent-Adjusted Pitcher Form

## Files Used

| # | File | Rows | Purpose |
|---|------|------|---------|
| 1 | sim/data/game_table.parquet | 9715 | Game-level canonical table |
| 2 | sim/data/feature_table.parquet | 9715 | SP xFIP, K%, BB%, park factors |
| 3 | sim/data/bullpen_usage.parquet | 83042 (19430 starters) | Starter IP, pitches, K |
| 4 | research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | 17906 | HH%, barrel%, whiff%, chase% |
| 5 | sim/data/bet_results.parquet | 4855 | Closing lines, results (2024-2025) |
| 6 | sim/data/cache/boxscores/ | 9715 JSON files | Team batting K/BB/AB per game |

## Key Decisions
- CSW proxy: strikes / total_pitches from boxscores (called+swinging strikes as proportion)
  This is strike% not true CSW, but is the best available proxy without pitch-level data per game.
- Team offense rolling: K_rate, BB_rate, runs/game from boxscore team batting lines
- Hard-hit, barrel, whiff from Statcast per-start (coverage varies by season)
- Evaluation: 2024+2025 games with closing lines (4,855 games from bet_results)
