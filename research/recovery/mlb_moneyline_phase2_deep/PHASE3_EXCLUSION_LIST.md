# Excluded/Contaminated Sources
## Permanently Excluded
1. Lineup features — unreliable pre-game
2. FanGraphs aggregate tables — contaminated in V1
3. V1/sim model outputs — circular
4. wRC+ / xFIP / SIERA pre-computed — not PIT-safe from available tables

## Sources Used (clean)
1. pitcher_game_logs.parquet — individual pitcher box stats
2. game_table.parquet — final scores + schedule
3. mlb_odds_closing_canonical.parquet — actual DK closing lines
