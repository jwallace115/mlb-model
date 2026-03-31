# TB Signal Discovery — Source Audit

**Date:** 2026-03-27

## Data Sources Used

### 1. TB Prop Dataset (CORE)
- **Path:** `research/mlb_props/tb_props/tb_props_dataset.parquet`
- **Rows:** 32,756
- **Seasons:** 2025
- **Key join fields:** `game_pk_out`, `player_name_out`, `name_norm`, `game_date`
- **Coverage:** 100% — all rows have actual_tb, implied_over, batting_order_slot
- **Under odds availability:** 14.6% (4,781 rows from BetMGM, DraftKings, Bovada, etc.)
- **Notes:** FanDuel (62% of data) provides Over odds only

### 2. Hitter Game Logs
- **Path:** `mlb/data/hitter_game_logs.parquet`
- **Rows:** 201,605
- **Seasons:** 2022-2025
- **Key join fields:** `player_id`, `game_pk`, `player_name`
- **Coverage:** 98.2% match rate to TB props via player_name → player_id → game_pk
- **Rolling aggregation:** Built 20-game rolling features (zero_tb_rate, ISO, SLG, K%, variance, pct_2plus_tb, pct_4plus_tb) with 1-game shift to avoid leakage
- **Key columns:** singles, doubles, triples, home_runs, at_bats, plate_appearances, strikeouts, iso, slg

### 3. Pitcher Statcast Per Start
- **Path:** `research/statcast_enrichment/pitcher_statcast_per_start.parquet`
- **Rows:** 20,662
- **Seasons:** 2022-2025
- **Key join fields:** `pitcher_id`, `game_pk`
- **Coverage:** 62.5% match rate to TB props (requires starter identification from pitcher_game_logs)
- **Rolling aggregation:** Built 5-start rolling features (barrel_rate, hard_hit_rate, whiff_rate, avg_exit_velo) with 1-start shift
- **Key columns:** hard_hit_rate, barrel_rate, whiff_rate, avg_exit_velo, avg_launch_angle

### 4. Pitcher Game Logs (Starter Identification)
- **Path:** `mlb/data/pitcher_game_logs.parquet`
- **Rows:** 83,042
- **Seasons:** 2022-2025
- **Key join fields:** `player_id`, `game_pk`, `starter_flag`
- **Usage:** Identify opposing starter for each batter via starter_flag=1 + opponent team match
- **Key columns:** innings_pitched, starter_flag, game_pk, team, opponent

### 5. Lineup Protection Dataset
- **Path:** `research/lineup_protection_study/followup_iso_mechanism/iso_mechanism_dataset.parquet`
- **Rows:** 174,870
- **Seasons:** 2022-2025
- **Key join fields:** `game_pk`, `player_id`
- **Coverage:** 97.4% match rate to TB props
- **Key columns:** ondeck_iso_last20, ondeck_woba_proxy_last20, protector_type, opp_pitcher_barrel_rate, opp_pitcher_hh_rate

### 6. Reliever Role Tracking
- **Path:** `research/data_pulls/reliever_role_tracking.parquet`
- **Rows:** 9,715 (game-level)
- **Seasons:** 2022-2025
- **Key join fields:** `game_pk`
- **Coverage:** 99.5% match rate to TB props
- **Key columns:** home/away_closer_pitched_last2days, home/away_bullpen_high_leverage_ip_last3d

### 7. Team Defense
- **Path:** `research/statcast_enrichment/team_defense.parquet`
- **Rows:** 120 (30 teams x 4 seasons)
- **Seasons:** 2022-2025
- **Key join fields:** `season`, `team_name` (mapped from opponent abbreviation)
- **Coverage:** 100% for DRS; OAA is NaN for 2025
- **Key columns:** defensive_runs_saved, outs_above_average_total (2025 has DRS only)

## Coverage Summary

| Source | Join to TB Props | Coverage |
|:-------|:-----------------|:---------|
| Hitter rolling features | player_id + game_pk | 98.2% |
| Protection features | player_id + game_pk | 97.4% |
| Team defense (DRS) | season + opponent | 100.0% |
| Reliever tracking | game_pk | 99.5% |
| Pitcher statcast rolling | game_pk + opponent | 62.5% |

## Data Gaps

1. **Pitcher statcast coverage is 62.5%** — gap is mostly early-season starts before rolling window fills, plus games where starter wasn't in the statcast dataset. This reduces sample for Families B and D.
2. **OAA unavailable for 2025** — only DRS available for defense. OAA would be preferred but DRS is an acceptable proxy.
3. **Under odds available for only 14.6% of records** — Under ROI calculations have small samples. Edge analysis uses implied_over (available for all records) as the primary metric.
4. **TB props are 2025 only** — no multi-season stability test possible. Half-season (H1 vs H2) split used as proxy.
5. **No Statcast batter contact-quality features available at the game level** — barrel rate, hard hit rate are pitcher-side only. Batter-side contact quality must be proxied via ISO/SLG from boxscores.
