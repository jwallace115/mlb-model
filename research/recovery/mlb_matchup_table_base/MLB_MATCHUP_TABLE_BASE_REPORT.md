# MLB MATCHUP TABLE BASE — BUILD REPORT
Generated: 2026-04-15 10:29:13

## Summary
- **Output rows**: 19804 (2 team-sides per game from 9902 games)
- **Output columns**: 107
- **Seasons covered**: [np.int64(2022), np.int64(2023), np.int64(2024), np.int64(2025), np.int64(2026)]
- **Duplicates on (game_pk, team)**: 0

## Input Substrates

| Substrate | File | Rows |
|-----------|------|------|
| Game table | sim/data/game_table.parquet | 9902 |
| Lineup state | research/recovery/mlb_lineup_state_substrate/team_game_lineup_state.parquet | 19712 |
| Bullpen features | sim/data/bullpen_features.parquet | 19804 |
| Rolling starter profile | research/recovery/mlb_starter_profile_substrate/rolling_starter_profile.parquet | 19914 |
| Per-start starter | research/recovery/mlb_starting_pitcher_substrate/per_start_starter_substrate.parquet | 19914 |

## Normalization
- Statcast-style team codes in rolling_sp and per_start_sp mapped to canonical via SC_TO_CANONICAL.
- lineup_state and bullpen_features already use canonical codes.
- Residual non-canonical check across all 4 substrates: NONE

## Team-Side Spine
- Built by exploding each game into 2 rows (H/A)
- Join key: (game_pk, team)
- Season row counts: {2022: 4860, 2023: 4860, 2024: 4854, 2025: 4856, 2026: 374}

## Join Coverage

| Season | Rows | Lineup% | Bullpen% | OppStarter_ID% | OppSP_Profile% |
|--------|------|---------|----------|---------------|----------------|
| 2022 | 4860 | 96.9% | 100.0% | 100.0% | 86.3% |
| 2023 | 4860 | 96.9% | 100.0% | 100.0% | 85.6% |
| 2024 | 4854 | 96.9% | 100.0% | 100.0% | 85.9% |
| 2025 | 4856 | 96.9% | 100.0% | 100.0% | 86.1% |
| 2026 | 374 | 35.3% | 100.0% | 100.0% | 17.9% |

## Residual Miss Diagnostic

- Rows with opposing starter ID: **19804**
- Rows with opposing starter profile: **16769**
- Missing profile despite having ID: **3035**

### Cause Classification
- Not in rolling_sp at all: 0
- In rolling_sp but all-null rolling fields: 3035

### Interpretation
- "Not in rolling_sp" cases: pitchers who appear in per_start_starter_substrate (starter_flag=1) but have no matching row in rolling_starter_profile. Expected for pitchers whose first start has no prior window to compute over.
- "In rolling_sp but all-null" cases: pitchers in rolling_sp whose rolling window covers insufficient prior starts (early-season or debut appearances).
- Both categories are acceptable. Rolling features will be null for those rows, treated as missing in downstream models.

## Field Disposition

### Identity Fields (9)
['game_pk', 'date', 'season', 'game_number', 'team', 'opponent_team', 'home_away', 'home_team', 'away_team']

### Carried-Only Fields (7)
(Not approved features — reference/metadata only)
['opp_starter_id', 'opp_starter_name', 'n_batters', 'sc_batter_count', 'sc_total_bip', 'total_pa', 'opp_sp_sc_enriched']

### Approved Feature Fields (91)

#### Lineup State Features (44)
Rolling SC-derived batting metrics over 7/10/15/20 game windows (contact_ev, contact_hh_rate, contact_barrel_rate, contact_la, contact_xwoba, contact_xba, contact_xslg, plate_bb_rate, plate_k_rate, damage_iso, damage_hr_rate).

#### Bullpen State Features (5)
Relievers used and pitch counts over last 1 and 3 games; high-leverage availability flag.

#### Opposing Starter Profile Features (42)
Rolling SC-derived pitching metrics (batmiss K%, whiff, command BB%/zone, contact HH/barrel/EV/LA, workload IP/BF/pitches, damage HR/hits) over 3/5/10 start windows, prefixed opp_sp_.

## Carry-Forward Caveats
1. SC-derived lineup and SP rolling features may be partial-window averages at season start — null where insufficient history.
2. Bullpen features accepted despite retroactive build from boxscores — data is structurally correct.
3. Opposing starter profile miss (3035 rows): 0 not in rolling_sp (no prior starts), 3035 in rolling_sp with all-null windows.
4. No game-level context features (park, umpire, weather, rest) included — intentionally excluded from this matchup base layer. Those join from game_table at model time.

## PIT-Safety Verdict
- No existing files modified
- No background tasks used
- No commits or pushes performed
- Output directory: research/recovery/mlb_matchup_table_base/
- Exactly 4 files written (parquet + 3 docs)
