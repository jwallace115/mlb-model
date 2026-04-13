# Phase 4 - Raw PIT-Safe Canonical Table Build (REVISED)
## MLB Totals Context Engine V1

### Build Summary
Source files joined in sequence. All pitcher and offense features use shift(1) rolling windows to enforce point-in-time safety. Team abbreviation normalization applied to resolve pitcher_game_logs vs game_table naming mismatches (TB=TBR, WSH=WSN, CWS=CHW, SD=SDP, SF=SFG, AZ=ARI, KC=KCR, ATH=OAK).

**Output:** research/recovery/mlb_totals_context_engine_v1/context_engine_raw_table.parquet
**Rows:** 9,715 (2022-2025 games, one row per game, no duplicates)
**Columns:** 72

---

### Build Steps

**Step 1: Starter Features (PIT-Safe)**
- Source: mlb/data/pitcher_game_logs.parquet
- Filter: starter_flag == True
- Dedup: for opener/tandem games, take highest innings_pitched starter per team per game
- Rolling window: 5 starts, min 2, shift(1) applied before rolling
- Features: avg_ip_r5, k_rate_r5, bb_rate_r5, hr_rate_r5, er_per9_r5, ip_std_r5, short_exit_r5

**Step 2: Starter Game-Level Join**
- Team abbreviation normalization applied: TB->TBR, WSH->WSN, CWS->CHW, SD->SDP, SF->SFG, AZ->ARI, KC->KCR, ATH->OAK
- Joined via game_pk + team_norm matching game_table home_norm / away_norm
- Result: 9715 home starters matched, 9715 away starters matched

**Step 3: Offense Features (PIT-Safe)**
- Source: mlb/data/hitter_game_logs.parquet (starter_flag == True)
- Aggregated to team-game level: OBP, SLG, ISO, HR count
- Rolling window: 10 games, min 3, shift(1) applied before rolling
- Same team normalization applied

**Step 4: Bullpen Features**
- Source: sim/data/bullpen_features.parquet
- Already computed as last_game / last_3_games lookback (PIT-safe by design)
- Opening-day nulls filled with 0
- Same team normalization applied

**Step 5: Market Lines**
- hist_lines (2022-2023) + market_snapshots (2024-2025) combined
- Deduplicated on game_pk (first book only)
- CLV available 2024-2025 only; open total unavailable all seasons

**Step 6: Environment (from game_table)**
- temperature, wind_speed, wind_direction, roof_status: 100% coverage
- park_factor_runs, park_factor_hr: 100% coverage  
- umpire_over_rate, umpire_k_rate: 100% coverage
- is_dome_or_closed flag derived from roof_status

---

### Coverage by Key Feature

| Feature | Coverage | Notes |
|---------|----------|-------|
| home_sp_avg_ip_r5 | 9072/9715 (93.4%) | Missing: fewer than 2 prior starts |
| away_sp_avg_ip_r5 | 9024/9715 (92.9%) | Same |
| home_obp_r10 | 9670/9715 (99.5%) | Missing: fewer than 3 prior games |
| away_obp_r10 | 9670/9715 (99.5%) | Same |
| home_bp_rel_last3 | 9650/9715 (99.3%) | |
| away_bp_rel_last3 | 9652/9715 (99.4%) | |
| market_close_total | 8766/9715 (90.2%) | ~78% 2022, ~82% 2023, 100% 2024-2025 |
| temperature | 9715/9715 (100.0%) | |
| park_factor_runs | 9715/9715 (100.0%) | |
| umpire_over_rate | 9715/9715 (100.0%) | |

---

### PIT Safety Verification
- Starter rolling features: VERIFIED (shift(1) before rolling)
- Offense rolling features: VERIFIED (shift(1) before rolling at team-date level)
- Bullpen features: VERIFIED (last_game, last_3_games by source design)
- Park factors: VERIFIED (static structural inputs)
- Weather: VERIFIED (physical measurement, not statistical aggregate)
- Market closing total: CONTEXTUAL - not a predictor, used as market geometry reference

---

### Temporal Splits
- DISCOVERY: season in (2022, 2023) - 4,860 games
- VALIDATION: season == 2024 - 2,427 games
- OOS: season == 2025 - 2,428 games

---

Built: 2026-04-12
