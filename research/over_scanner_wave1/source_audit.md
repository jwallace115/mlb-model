# Source Audit — OVER Scanner Wave 1

| File | Rows | Key |
|------|------|-----|
| feature_table.parquet | 9715 | SP xFIP/K%/BB%, BP xFIP, park, weather |
| bet_results.parquet | 4855 | Closing lines, outcomes |
| phase5_sim_results.parquet | 4855 | V1 p_under |
| pitcher_start_adjusted_metrics.parquet | 19430 | Per-start K/BB/IP/ER/pitches |
| bullpen_features.parquet | 19302 | BP pitches last 1/3 games, high_lev_avail |
| bullpen_usage.parquet | 83042 | Per-reliever IP per game |
| game_table.parquet | 9715 | innings_played for extra-innings |
| pitcher_statcast_per_start_starters_only.parquet | 17906 | hard_hit_rate per start |
| offense_expectation_table.parquet (V2) | 19430 | Team contact/BB rolling |

## Notes
- OV043: high_leverage_available is binary; using bullpen_pitches_last_3_games as workload proxy
- OV051: bullpen ERA not available; using bullpen ER from boxscores via pitcher starts
- OV050: prev_game_innings derived from game_table innings_played
