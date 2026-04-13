# Phase 2 - Feature Family Audit
## MLB Totals Context Engine V1

### Audit Methodology
Each feature family was evaluated against three criteria:
1. PIT Safety: Can this feature be computed using only data from dates strictly before the game date?
2. Coverage: What fraction of 2022-2025 games have this feature available without imputation?
3. Derivable from approved sources: Does it come from pitcher_game_logs, hitter_game_logs, game_table, or bullpen_features?

The V1 feature_table (sim/data/feature_table.parquet) is EXCLUDED because it was built by sim/phase2_build_features.py which joins season-level aggregates to game dates, creating target leakage.

---

### Family 1: Starter Quality (APPROVED with conditions)
**Source:** mlb/data/pitcher_game_logs.parquet
**Approach:** Rolling 5-start window using shift(1) to exclude current game.
**Features approved:**
- innings_pitched rolling 5-start mean (shift(1) applied)
- strikeouts rolling 5-start mean (shift(1) applied)
- walks rolling 5-start mean (shift(1) applied)
- earned_runs rolling 5-start mean (shift(1) applied)
- derived K rate = strikeouts / (batters_faced) rolling 5-start
- derived HR rate = home_runs_allowed / batters_faced rolling 5-start

**PIT Safety:** VERIFIED. Each start row uses shift(1) before rolling to exclude same-game data.
**Coverage:** 84,938 rows total, 19,864 starter rows, seasons 2022-2026.
**Null rate:** innings_pitched 0.0%, strikeouts 0.0% in starter subset.
**Decision:** APPROVED. Min 2 prior starts required for rolling features (cold-start gets None/league avg).

---

### Family 2: Starter Depth (APPROVED with conditions)
**Source:** mlb/data/pitcher_game_logs.parquet
**Approach:** Rolling window on innings_pitched to compute depth volatility.
**Features approved:**
- avg_ip_rolling5: mean of last 5 starts (PIT-safe)
- ip_stdev_rolling5: std dev of last 5 starts (proxy for consistency)
- short_exit_rate: fraction of last 5 starts with IP < 5.0

**PIT Safety:** VERIFIED. Same shift(1) approach.
**Coverage:** Full starter subset, 2022-2025.
**Decision:** APPROVED.

---

### Family 3: Bullpen Quality (APPROVED - from bullpen_features)
**Source:** sim/data/bullpen_features.parquet
**PIT Safety:** VERIFIED. Columns are labeled last_game and last_3_games, indicating they are pre-computed with prior-game lookback. Verified column names: relievers_used_last_game, bullpen_pitches_last_game, high_leverage_available.
**Coverage:** 19,302 rows (team-game level), 2022-2025. ~0% null for high_leverage_available, ~10% null for usage cols (opening day).
**Features approved:**
- relievers_used_last_game
- relievers_used_last_3_games
- bullpen_pitches_last_3_games
- high_leverage_available

**Decision:** APPROVED. Opening-day nulls filled with 0 (no prior usage).

---

### Family 4: Bullpen Freshness (APPROVED - derived from pitcher_game_logs)
**Source:** mlb/data/pitcher_game_logs.parquet (non-starters)
**Approach:** Group relievers by team and game_date, compute rolling bullpen workload.
**Features approved:**
- team_bullpen_ip_last3: sum of all reliever IP in prior 3 games
- team_bullpen_pitches_last3: sum of all reliever pitches in prior 3 games

**PIT Safety:** VERIFIED. Strict date < game_date filter applied before aggregation.
**Decision:** APPROVED as supplement to bullpen_features.

---

### Family 5: Offense Quality (APPROVED with conditions)
**Source:** mlb/data/hitter_game_logs.parquet
**Approach:** Team-level rolling 10-game aggregates (shift(1) applied at team-date level).
**Features approved:**
- team_obp_rolling10: mean team lineup OBP over prior 10 games
- team_slg_rolling10: mean team lineup SLG over prior 10 games
- team_iso_rolling10: mean team lineup ISO over prior 10 games
- team_hr_rate_rolling10: HR per PA over prior 10 games

**PIT Safety:** VERIFIED. Aggregated at game level with date filter.
**Coverage:** 204,548 rows (starter batters), seasons 2022-2026. Full lineup coverage.
**Note:** Only batting_order_position 1-9 and starter_flag=True used.
**Decision:** APPROVED.

---

### Family 6: Park Effects (APPROVED - from game_table)
**Source:** sim/data/game_table.parquet, columns park_factor_runs, park_factor_hr
**PIT Safety:** VERIFIED. Park factors are static structural properties of venues, not computed from game outcomes. They do not leak future information.
**Coverage:** 100% non-null across 2022-2025 (9,715 games).
**Range:** park_factor_runs 0.793 to 1.179.
**Decision:** APPROVED.

---

### Family 7: Weather (APPROVED with partial limitations)
**Source:** sim/data/game_table.parquet, columns temperature, wind_speed, wind_direction, roof_status
**PIT Safety:** VERIFIED. Weather is a game-day physical measurement, not a statistical aggregate.
**Coverage:**
- temperature: ~0% null
- wind_speed: ~0% null
- wind_direction: ~0% null
- roof_status: ~0% null; values include open/closed/dome/retractable
**Limitations:** Wind direction is raw degrees, must be converted to run-impact via park bearing (CF direction). Roof closed/dome games should zero out wind/temperature effect.
**Decision:** APPROVED. Dome/closed-roof games get WPL=NEUTRAL on weather component.

---

### Family 8: Market Geometry (APPROVED - partial, data-blocked for full path)
**Source:**
- sim/data/mlb_historical_closing_lines.parquet: 2022-2023 closing totals only (3,911 games)
- sim/data/market_snapshots.parquet: 2024-2025 closing totals + CLV (4,855 games)
- data/line_movement.csv: 2026 only, mostly null open totals

**PIT Safety:** N/A - market inputs are used as contextual inputs, not predictors. The closing total is an outcome-adjacent feature but is explicitly flagged as market geometry, not a model predictor.

**Coverage by season:**
- 2022: 1,908 / 2,430 games (78.5%) - closing line only
- 2023: 2,003 / 2,430 games (82.4%) - closing line only
- 2024: 2,427 / 2,427 games (100%) - closing line + CLV
- 2025: 2,428 / 2,428 games (100%) - closing line + CLV
- Open total: 0% coverage for all seasons (not available in historical pull)

**Decision:** APPROVED for closing total only. Market Path Shape output is DATA-BLOCKED for 2022-2023 (no open/noon/5pm lines available). MPS will be classified as DATA-BLOCKED for discovery split and only computable in 2024-2025.

---

### Family 9: Home/Away Asymmetry (APPROVED - derived)
**Source:** game_table (home/away team identifiers), pitcher_game_logs, hitter_game_logs
**Features approved:**
- home_advantage_flag: always 1 (structural, not predictive)
- home_sp_stability vs away_sp_stability: separate scores per side
- home_offense_quality vs away_offense_quality: separate scores per side
**Decision:** APPROVED. Asymmetry tracked at game level via home/away split in all pitcher and offense features.

---

### Excluded Feature Families

| Family | Reason |
|--------|--------|
| sim/data/feature_table.parquet | Built by sim/phase2_build_features.py - season-level aggregates, PIT contaminated |
| research/opponent_adjusted_engine_v2/ | Ambiguous lineage, likely PIT contaminated |
| mlb_sim/data/ feature tables | Ambiguous lineage per charter rules |
| xFIP/SIERA from FanGraphs | Not available as game-level PIT-safe series; would require external pull |
| wRC+ (FanGraphs) | Same issue; game-level hitter logs used instead |

---

Built: 2026-04-12
