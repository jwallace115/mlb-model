# Phase 0: Exact Object Lock

## Source
- Classification table: research/recovery/mlb_sides_phase4_winpath/classification_table.csv
- MIXED = reason == 'MIXED' (all SP/offense/BP gaps below discovery median)
- MIXED total: 1231 games
- Discovery (2022-2023): 540
- Validation (2024): 333
- OOS (2025): 358

## Object 1: bp_adv_dog
- Definition: within MIXED, bp_era_diff > 0 (fav BP ERA > dog BP ERA)
- bp_era_diff = fav_bp_era - dog_bp_era
- Source: pitcher_game_logs.parquet, starter_flag==0, expanding cumulative ERA with shift(1)
- Counts: disc=241, val=147, oos=179

## Object 2: night_dog
- Definition: within MIXED, local_start_hour >= 17 (night game)
- Source: game_table.parquet local_start_hour field
- Counts: disc=381, val=245, oos=268