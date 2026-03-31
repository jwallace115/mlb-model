# Source Audit — Walk-Forward Backtest

## Files
- V1 sim: sim/data/phase5_sim_results.parquet (4855 rows)
- Engine: research/opponent_adjusted_engine/game_level_engine_dataset.parquet (4855 rows)
- Closing lines: sim/data/bet_results.parquet (4855 rows)

## Join
- Key: game_pk (unique game identifier)
- Pre-join: 4855 V1 games
- Post-join: 4855 games (with closing lines)
- adj_k_rate_last3 available: 4468 (92.0%)

## Fields
- date: pd.Timestamp from phase5_sim_results
- game_pk: integer game identifier
- p_under: V1 simulation under probability
- close_total: closing market total from bet_results
- actual_total: final game total from phase5_sim_results

## Push handling
- Pushes (actual_total == close_total) excluded from win rate and ROI
- Pushes included in signal counts and availability stats
