# Source Audit — Lineup Protection Study

## Data Availability

| Source | Rows | Grain | Available |
|--------|------|-------|-----------|
| historical_lineups_long.parquet | 174870 | batter × game | YES |
| game_table.parquet | 9715 | game | YES |
| Statcast pitch-level | — | pitch | **NO** (only pitcher-aggregate per start) |
| PA-level logs | — | plate appearance | **NO** (only batter-game totals) |

## Key Limitation
No plate-appearance-level or pitch-level data exists locally.
Study uses BATTER-GAME-LEVEL outcomes (K rate, BB rate, ISO per game).
Cannot test: zone rate, first-pitch strike, fastball rate, per-PA sequencing.

## Fields Available Per Batter-Game
AB, H, 2B, 3B, HR, K, BB, HBP, PA, total_bases, batting_order_slot
Player ID, team, opponent, home/away, position
