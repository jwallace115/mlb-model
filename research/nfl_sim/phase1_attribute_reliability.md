# Phase 1B Step 4: Attribute Reliability Audit (D11)

## Method

**Data:** Play-by-play from 2021-2024, regular season only (week <= 18).
Per-game aggregation uses `build_player_game_aggs` from `usage.py` (imported).
All attributes computed on RAW per-player-per-game values, NOT shrunk/decayed estimates.

**Split-half reliability:** For each player-season with >= 8 qualifying games,
games ordered by week, odd-indexed = half A, even-indexed = half B.
Each half's attribute = pooled ratio (sum numerator / sum denominator).
Pearson r between halves across all qualifying player-seasons (pooled over 4 seasons).
Spearman-Brown correction to 8-game length: r8 = 2r / (1 + r).
Threshold: r8 >= 0.50 => PASS (frozen from D11).

**Qualifying games:** A game counts for a receiver if targets >= 1,
for a rusher if carries >= 1. Carries exclude qb_scramble.

**Year-over-year:** Pearson r between full-season pooled ratio in season s
and season s+1 for players qualifying in both. Informational only, not gated.

## Reliability Table

| Attribute | Group | N | r | r8 | YoY r | YoY N | PASS/FAIL |
|---|---|---|---|---|---|---|---|
| target_share | receivers | 1105 | 0.890 | 0.942 | 0.802 | 1074 | PASS |
| rz_target_share | receivers | 1073 | 0.579 | 0.733 | 0.521 | 1065 | PASS |
| adot | receivers | 1105 | 0.848 | 0.918 | 0.759 | 1074 | PASS |
| catch_rate | receivers | 1105 | 0.375 | 0.546 | 0.219 | 1074 | PASS |
| yac_per_rec | receivers | 991 | 0.530 | 0.693 | 0.322 | 1029 | PASS |
| yards_per_target | receivers | 1105 | 0.286 | 0.445 | 0.096 | 1074 | FAIL |
| explosive_rec_rate | receivers | 1105 | 0.228 | 0.372 | 0.109 | 1074 | FAIL |
| carry_share | rushers | 438 | 0.960 | 0.980 | 0.832 | 683 | PASS |
| gl_carry_share | rushers | 245 | 0.720 | 0.837 | 0.568 | 568 | PASS |
| yards_per_carry | rushers | 438 | 0.419 | 0.590 | 0.231 | 683 | PASS |
| explosive_rush_rate | rushers | 438 | 0.312 | 0.476 | 0.151 | 683 | FAIL |

## Recent Form Analysis

Does last-3-game share add information beyond season-to-date rate
for predicting next-game share? Train 2021-2023, test 2024.
Positive delta (RMSE_std - RMSE_std+l3) means recent form improves prediction.

| Attribute | RMSE (STD only) | RMSE (STD + L3) | Delta | Sign | N_train | N_test |
|---|---|---|---|---|---|---|
| target_share (receivers) | 0.06813 | 0.06727 | 0.00086 | + | 9640 | 3127 |
| carry_share (rushers) | 0.15025 | 0.14547 | 0.00478 | + | 4330 | 1419 |

## Defense-Type Split Reliability

Is the difference in yards_per_target vs top-half vs bottom-half pass defenses
a stable player trait? Top-half = lower EPA allowed (better defense).
Split-half within each defense half (odd/even games), then reliability of the difference.
Threshold: r8 >= 0.50 => PASS.

| Attribute | Group | N | r | r8 | PASS/FAIL |
|---|---|---|---|---|---|
| ypt_defense_split | receivers | 913 | -0.046 | -0.097 | FAIL |

## ATTRIBUTES ADMITTED TO THE SIM

Threshold: r8 >= 0.50 (D11, frozen). The threshold was not moved.

**PASSED (admitted):**

- `target_share` (receivers)
- `rz_target_share` (receivers)
- `adot` (receivers)
- `catch_rate` (receivers)
- `yac_per_rec` (receivers)
- `carry_share` (rushers)
- `gl_carry_share` (rushers)
- `yards_per_carry` (rushers)

**FAILED (excluded):**

- `yards_per_target` (receivers)
- `explosive_rec_rate` (receivers)
- `explosive_rush_rate` (rushers)

Excluded attributes are not used in the player layer.
The defense-type split (ypt_defense_split) FAILED (r8=-0.097) and is excluded as a matchup adjustment.

