# Point-in-Time Feature Rebuild — Methodology

## Purpose

The original MLB Side Engine features (SP xFIP, bullpen xFIP, offense wRC+) were
contaminated with end-of-season FanGraphs aggregates. This rebuild reconstructs all
three feature families using only data available **before** each game, eliminating
future-data leakage.

## Source Files

| Source | Path | Rows | Description |
|--------|------|------|-------------|
| Pitcher game logs | `mlb/data/pitcher_game_logs.parquet` | 84,669 | Per-pitcher per-game stats, 2022-2026 |
| Game table | `sim/data/game_table.parquet` | 9,902 | Canonical game-level reference |

## Team Name Harmonization

Pitcher game logs use FanGraphs abbreviations; game_table uses MLB Stats API convention.
Applied mapping before all joins:

```
AZ -> ARI, CWS -> CHW, KC -> KCR, SD -> SDP, SF -> SFG, TB -> TBR, WSH -> WSN, ATH -> OAK
```

## Home/Away Identification

The `home_away` column in pitcher_game_logs is **unreliable** (all starters labeled "A").
Instead, home/away is determined by matching the pitcher's `team` column to the game_table's
`home_team` / `away_team` columns (after team name harmonization). This resolved 2,480
previously-missing home starters.

## Feature Definitions

### SP FIP (Point-in-Time)

**Formula:** `FIP = ((13 * HR + 3 * BB - 2 * K) / IP) + 3.10`

- Uses standard FIP constant of 3.10 (not league-year-adjusted, to avoid lookahead)
- For each game on date D, computes season-to-date FIP from all **prior starts** (game_date < D)
- Uses `groupby(player_id, season) + shift(1) + expanding().sum()` — vectorized, no row loops
- Requires >= 3 prior starts for a valid value; otherwise `NaN` with thin flag

**Why FIP instead of xFIP:** xFIP requires league-wide fly ball / HR/FB rate for the season,
which would require lookahead data. FIP uses only the pitcher's own stats and is fully
reconstructable from game logs.

**Output columns:** `home_sp_fip_pit`, `away_sp_fip_pit`, `home_sp_era_pit`, `away_sp_era_pit`

### Bullpen FIP (Point-in-Time)

**Formula:** Same FIP formula, applied to team aggregate reliever stats.

- Filters pitcher_game_logs to `starter_flag == 0`
- Aggregates per (team, game_pk): sums IP, ER, K, BB, HR across all relievers in that game
- Computes season-to-date cumulative with `shift(1) + expanding().sum()`
- Requires >= 20 cumulative IP for valid value
- Joined to game_table by (team, game_pk) for home and away sides

**Output columns:** `home_bp_fip_pit`, `away_bp_fip_pit`, `bp_fip_diff_pit`

### Offense RPG (Point-in-Time)

**Formula:** Rolling 20-game mean of runs scored, shifted by 1 game.

- Built from game_table's `home_score` / `away_score` columns
- Each team's games stacked into a single timeline, sorted by date
- `groupby(team, season) + shift(1) + rolling(20, min_periods=5).mean()`
- Requires >= 5 prior games for valid value
- This is explicitly labeled as `offense_rpg_pit` (runs per game, point-in-time) —
  it is NOT wRC+ and makes no pretense of being park/league-adjusted

**Output columns:** `home_offense_rpg_pit`, `away_offense_rpg_pit`

## Minimum Sample Rules

| Feature | Minimum | Thin flag when violated |
|---------|---------|----------------------|
| SP FIP | 3 prior starts in current season | `sp_sample_thin = True` |
| Bullpen FIP | 20 cumulative reliever IP in current season | `bp_sample_thin = True` |
| Offense RPG | 5 prior team games in current season | `offense_sample_thin = True` |

Composite thin flags are set if **either** home or away side is thin.
`*_thin_reason` columns provide human-readable explanation.

## Deduplication

- **SP:** If multiple pitchers flagged as starters in the same (game_pk, side), the one with
  the most IP in that game is kept (the "true" starter, not an opener).
- **BP:** Grouped by (team, game_pk) in aggregation, so inherently unique.
- **Final output:** Safety `drop_duplicates(subset=["game_pk"])` with assertion.

## Coverage Report

### By Season
| Season | Games | SP FIP (home) | BP FIP (home) | Offense RPG (home) |
|--------|-------|--------------|--------------|-------------------|
| 2022 | 2,430 | 81% | 96% | 97% |
| 2023 | 2,430 | 80% | 95% | 97% |
| 2024 | 2,427 | 81% | 96% | 97% |
| 2025 | 2,428 | 80% | 95% | 97% |
| 2026 | 187 | 0% | 47% | 60% |

2026 has 0% SP FIP because all starters have < 3 prior starts in the young season.

### By Month (SP FIP fill rate, both sides)
| Month | Games | SP FIP Fill |
|-------|-------|------------|
| March | 215 | 0% |
| April | 1,622 | 38% |
| May | 1,655 | 85% |
| June | 1,592 | 88% |
| July | 1,495 | 90% |
| Aug | 1,665 | 91% |
| Sept | 1,565 | 91% |
| Oct | 93 | 90% |

### Non-Null Rates (Overall)
| Column | Rate |
|--------|------|
| home_sp_fip_pit | 78.8% |
| away_sp_fip_pit | 78.5% |
| home_bp_fip_pit | 94.6% |
| away_bp_fip_pit | 94.6% |
| home_offense_rpg_pit | 96.3% |
| away_offense_rpg_pit | 96.2% |

## Validation Checks

### Check 1: Spot Check (5 Random Mid-2024 Games)
For each sampled game, manually recomputed SP FIP by filtering all prior starts, summing
raw stats, and applying the FIP formula. All 5 matched the vectorized output exactly
(delta = 0.000000).

### Check 2: Early Season Thin Flags
April 7-15, 2024: 121 games, 113 (93%) have `sp_sample_thin = True`.
Expected: nearly all games should be thin in the first 2 weeks. **PASS.**

### Check 3: Late Season vs Season-Final Divergence
- Aaron Nola: Sept 1 PIT FIP = 3.832 vs season-final FIP = 3.849 (delta = 0.017). **Different.**
- Seth Lugo: Sept 1 PIT FIP = 3.196 vs season-final FIP = 3.051 (delta = 0.146). **Different.**
This confirms PIT values are NOT contaminated with end-of-season aggregates.

### Check 4: Idempotency
Re-ran manual FIP computation for 3 games and compared to saved parquet values.
All matched exactly. **PASS.**

## Feature Summary Statistics

| Feature | Mean | Std | Min | 25% | 50% | 75% | Max |
|---------|------|-----|-----|-----|-----|-----|-----|
| home_sp_fip_pit | 3.957 | 1.074 | -0.071 | 3.250 | 3.879 | 4.577 | 11.225 |
| away_sp_fip_pit | 3.936 | 1.065 | -0.448 | 3.232 | 3.859 | 4.543 | 13.100 |
| home_bp_fip_pit | 3.866 | 0.578 | 1.243 | 3.527 | 3.824 | 4.172 | 7.785 |
| away_bp_fip_pit | 3.853 | 0.579 | 1.468 | 3.528 | 3.819 | 4.154 | 7.797 |
| home_offense_rpg_pit | 4.446 | 0.851 | 1.667 | 3.850 | 4.400 | 4.950 | 8.800 |
| away_offense_rpg_pit | 4.452 | 0.877 | 1.500 | 3.850 | 4.400 | 5.000 | 9.000 |

## Output Schema

File: `research/mlb_side_engine/clean_features/baseball_features_pit.parquet`

| Column | Type | Description |
|--------|------|-------------|
| game_pk | int | MLB Stats API game primary key |
| date | datetime | Game date |
| home_team | str | Home team abbreviation (MLB Stats API) |
| away_team | str | Away team abbreviation (MLB Stats API) |
| home_sp_fip_pit | float | Home SP season-to-date FIP (pre-game) |
| away_sp_fip_pit | float | Away SP season-to-date FIP (pre-game) |
| home_sp_era_pit | float | Home SP season-to-date ERA (pre-game) |
| away_sp_era_pit | float | Away SP season-to-date ERA (pre-game) |
| home_bp_fip_pit | float | Home bullpen season-to-date FIP (pre-game) |
| away_bp_fip_pit | float | Away bullpen season-to-date FIP (pre-game) |
| bp_fip_diff_pit | float | home_bp_fip_pit - away_bp_fip_pit |
| home_offense_rpg_pit | float | Home team rolling 20-game RPG (pre-game) |
| away_offense_rpg_pit | float | Away team rolling 20-game RPG (pre-game) |
| sp_sample_thin | bool | True if either SP has < 3 prior starts |
| bp_sample_thin | bool | True if either bullpen has < 20 IP |
| offense_sample_thin | bool | True if either team has < 5 prior games |
| sp_sample_thin_reason | str | Human-readable thin explanation |
| bp_sample_thin_reason | str | Human-readable thin explanation |
| offense_sample_thin_reason | str | Human-readable thin explanation |

## Comparison: Old (Contaminated) vs Clean (PIT)

| Aspect | Old Features | Clean Features |
|--------|-------------|----------------|
| SP metric | FanGraphs season-final xFIP | Game-log FIP, season-to-date |
| Date filter | None (end-of-year aggregate) | Strict game_date < D |
| Bullpen metric | FanGraphs season-final xFIP | Game-log FIP, cumulative |
| Offense metric | FanGraphs season-final wRC+ | Rolling 20-game RPG |
| Thin flags | None | Per-feature, with reasons |
| Lookahead risk | HIGH — uses full season stats | NONE — strictly pre-game |
