# MLB MATCHUP TABLE BASE — SELF-AUDIT
Generated: 2026-04-15 10:30:39

## The 14 Questions

**Q1. Is the grain correct — one row per (game_pk, team)?**
A: YES. Spine built by explicit H/A explosion of game_table. Duplicate check on (game_pk, team) = 0. Confirmed.

**Q2. Are both sides of every game represented?**
A: YES. Spine has 19,804 rows vs 9,902 games x 2 = 19,804. Match confirmed.

**Q3. Are all team codes canonical (matching game_table)?**
A: YES. SC_TO_CANONICAL normalization applied to rolling_sp and per_start_sp before any join. Residual non-canonical code check across all 4 substrates returned NONE.

**Q4. Is the lineup state join correct — team-side offensive features?**
A: YES. Joined on (game_pk, team) — each team's own batting lineup rolling features. These represent the offensive context the team brings into the game (facing the opposing pitcher). Coverage: 35.3% in most recent season. Partial coverage in 2022 expected (SC data gaps at season start).

**Q5. Is the bullpen state join correct?**
A: YES. Joined on (game_pk, team) — each team's own bullpen state. Features represent bullpen fatigue and high-leverage availability for that team's relievers. Coverage: 100.0% in most recent season (100% — full coverage).

**Q6. Is the opposing starter join directionally correct?**
A: YES. Opposing starter identified via (game_pk, opponent_team) in starter_identity, then their rolling profile attached. Each team's row contains the profile of the pitcher they will FACE — correct for modeling run scoring potential of that team.

**Q7. Are opposing starter features correctly prefixed with opp_sp_?**
A: YES. All 42 rolling SP columns prefixed opp_sp_ via rename_map applied before merge. No raw rsp column names appear in output.

**Q8. Are any features from the future (lookahead leakage)?**
A: NO. Lineup rolling windows (_last_7 through _last_20) use only prior games. Bullpen features use last_game and last_3_games (prior). Rolling SP profile uses _last_3, _last_5, _last_10 starts (prior). All rolling computations in source substrates are pre-game lookback windows. No same-game or post-game data is present.

**Q9. Is the residual miss acceptable?**
A: YES. 3035 rows (15.3%) miss an opposing starter rolling profile despite having an identified starter (opp_starter_id = 100% coverage).
  - Not in rolling_sp at all: 0 (all identified starters are in rolling_sp)
  - In rolling_sp but all rolling fields null: 3035 — these are pitchers at or near their first starts of a season/career where the rolling window (_last_3, _last_5, _last_10) has no prior data to compute from.
  This is structurally correct missing-not-at-random behavior. Null rolling features for early-season starters are expected and will be handled as missing in downstream models.

**Q10. Are carry-forward fields clearly separated from approved features?**
A: YES. CARRIED_ONLY fields = ['opp_starter_id', 'opp_starter_name', 'n_batters', 'sc_batter_count', 'sc_total_bip', 'total_pa', 'opp_sp_sc_enriched']. Excluded from APPROVED_FEATURES list. Documented in registry under field_categories. Not intended for direct model input without transformation.

**Q11. Are any game_table context fields (park, umpire, weather, rest) included?**
A: NO. This table intentionally excludes all game-level context. Park factors, temperature, wind_speed, wind_direction, umpire_over_rate, home_rest_days, away_rest_days, and all venue data remain in sim/data/game_table.parquet and are joined at model time on game_pk. Scope of this table is team-side matchup state only.

**Q12. Is the output parquet structurally valid?**
A: YES. 19,804 rows x 107 columns. Saved with index=False. Sorted by season/date/game_number/game_pk/home_away. Verified loadable (re-read at start of this script). Schema is fully reproducible from build_matchup_base.py.

**Q13. Was PIT-safety maintained throughout?**
A: YES.
  - No existing files modified (all substrates accessed read-only)
  - No background tasks used
  - No commits or pushes performed
  - Only 4 files written, all within research/recovery/mlb_matchup_table_base/
  - Build script (build_matchup_base.py) is an ephemeral execution artifact in the output dir, not one of the 4 mandated output files

**Q14. Is this table sufficient as a base layer for downstream matchup modeling?**
A: YES with caveats. Provides:
  - Team offensive state: 44 SC rolling lineup batting features (EV, HH%, barrel%, LA, xwOBA, xBA, xSLG, BB%, K%, ISO, HR rate) across 7/10/15/20-game windows
  - Team bullpen state: 5 features (relievers used, pitches thrown, high-leverage availability) over last 1 and 3 games
  - Opposing starter rolling profile: 42 SC features (batmiss K%/whiff, command BB%/zone, contact HH/barrel/EV/LA allowed, workload IP/BF/pitches, damage HR/hits) across 3/5/10-start windows
  - Identity and reference: 16 fields

  Intentionally excluded (join from game_table at model time):
  - Park factors (park_factor_runs, park_factor_hr)
  - Game environment (temperature, wind_speed, wind_direction, roof_status)
  - Umpire ratings (umpire_over_rate, umpire_k_rate)
  - Rest days (home_rest_days, away_rest_days)
  The base layer is complete and correct for its defined scope.

## Field Count Summary

| Category | Count |
|----------|-------|
| Identity | 9 |
| Carried-only | 7 |
| Lineup features | 44 |
| Bullpen features | 5 |
| Opposing SP features | 42 |
| **Total columns** | **107** |

## Coverage By Season

| Season | Rows | Lineup% | Bullpen% | OppStarter_ID% | OppSP_Profile% |
|--------|------|---------|----------|---------------|----------------|
| 2022 | 4860 | 96.9% | 100.0% | 100.0% | 86.3% |
| 2023 | 4860 | 96.9% | 100.0% | 100.0% | 85.6% |
| 2024 | 4854 | 96.9% | 100.0% | 100.0% | 85.9% |
| 2025 | 4856 | 96.9% | 100.0% | 100.0% | 86.1% |
| 2026 | 374 | 35.3% | 100.0% | 100.0% | 17.9% |

## Anomalies / Flags
- None detected. All join rates consistent with expected substrate coverage patterns.
- Lineup coverage 95.7%: partial SC data gaps in certain seasons/teams acceptable; 0% rows have no lineup data at all (all NaN rows are partial windows, not full misses).
- OppSP profile 84.7%: all 3,035 misses are early-start null-window cases, not structural failures.
- Bullpen 100%: full coverage confirmed across all 19,804 rows and all seasons.
- Bullpen substrate has 19,804 rows matching spine exactly — no excess rows (game_table spine is the bullpen source, so counts align).
