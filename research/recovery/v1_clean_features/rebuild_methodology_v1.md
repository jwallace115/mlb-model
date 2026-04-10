# PIT V1 Feature Rebuild — Methodology

## Contamination Source
The original V1 feature table (`sim/data/feature_table.parquet`) uses FanGraphs end-of-season aggregates for all pitcher and offense features. A game on April 5 uses the same xFIP/K%/BB%/IP/wRC+ value that includes performance through September. This is lookahead contamination.

## Rebuild Approach

### Starter Features (xFIP proxy, K%, BB%, avg IP)
- Source: `mlb/data/pitcher_game_logs.parquet` (84,669 rows, 2022-2026)
- Filter: `starter_flag == 1`
- Method: Per-pitcher expanding cumulative stats with `shift(1)` (strict date < game_date)
- xFIP proxy: FIP formula `(13*HR + 3*BB - 2*K)/IP + 3.10` applied to cumulative stats
- Bayesian shrinkage: `(stat * BF + league_avg * 300) / (BF + 300)` — matches V1 prior weight
- Clamping: xFIP [2.0, 7.5], K% [0.05, 0.50], BB% [0.02, 0.25], avg_ip [3.0, 7.5]
- First start of career: receives league-average values (shrinkage fully active at BF < 30)

### Offense (wRC+ proxy)
- Source: `sim/data/game_table.parquet` team scores
- Method: Rolling 20-game runs/game with `shift(1)`, scaled to wRC+ units: `(rpg / 4.5) * 100`
- First games of season: expanding mean until 20 games accumulated
- Clamped to [60, 140]

### Bullpen FIP
- Source: `mlb/data/pitcher_game_logs.parquet`, `starter_flag == 0`
- Method: Team-level aggregate K/BB/HR/IP per game, expanding cumulative with `shift(1)`
- FIP formula applied to cumulative totals, then Bayesian-shrunk
- Used to compute `bullpen_delta = bp_fip - sp_fip` and `bp_delta_exposure = delta * (9 - avg_ip)`

### Flyball Interaction
- Source: PGL `fly_outs / (fly_outs + ground_outs)` as FB% proxy
- Method: Per-pitcher expanding with `shift(1)`, default 0.35 (league avg)
- `flyball_wind_interaction = (home_fb + away_fb) * wind_out_flag`
- `wind_out_flag = (roof_status == "open") & (wind_factor_effective > 3)`

### Clean Features Reused As-Is
- `park_factor_runs`, `park_factor_hr`: Static from config.STADIUMS
- `temperature`, `wind_factor_effective`: Game-day weather from game_table/feature_table
- `umpire_over_rate`: Static umpire lookup table
- `home_rest_days`, `away_rest_days`: Chronological computation from game_table
- `doubleheader_flag`: MLB schedule metadata
- `home/away_high_leverage_avail`: Phase 8 bullpen features (already uses shift(1))

## Validation Results
- 6/6 gates passed
- 9,715 games (matches original feature table exactly)
- Gerrit Cole 2022 xFIP: 15 unique values (was 1 in contaminated V1)
- Feature correlations with actual_total are weaker than contaminated V1 (expected — point-in-time has less information than full-season)
