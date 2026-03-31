# Source Audit — Run Volatility Model

| File | Rows | Purpose |
|------|------|---------|
| sim/data/feature_table.parquet | 9715 | SP xFIP/K%/BB%, BP xFIP, park, weather |
| sim/data/bet_results.parquet | 4855 | Closing lines, outcomes |
| sim/data/phase5_sim_results.parquet | 4855 | V1 p_under |
| research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet | 17906 | HH%, barrel%, whiff% per start |
| sim/data/bullpen_features.parquet | 19302 | BP pitches last 1/3 games |
| research/opponent_adjusted_engine_v2/offense_expectation_table.parquet | 19430 | Team contact/BB/runs rolling |
| research/opponent_adjusted_engine/pitcher_start_adjusted_metrics.parquet | 19430 | Pitcher K/BB/IP/ER per start |

## Feature availability
- SP bb_pct, k_pct, xfip: YES (feature_table)
- SP hard_hit, barrel, whiff: YES (Statcast per-start, ~92% coverage)
- BP xfip: YES (feature_table)
- BP workload: YES (bullpen_features — pitches last 3 games)
- Lineup contact_rate, bb_rate: YES (V2 offense table)
- Park factors, temperature, wind: YES (feature_table)
- SP fb_rate/gb_rate: NOT AVAILABLE (all NaN)
- Strand rate, ISO, BABIP: NOT AVAILABLE directly
- Will use proxies where feasible
