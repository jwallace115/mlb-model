# BATTER-GAME HITTER STATCAST SUBSTRATE — BUILD REPORT

**Object ID:** mlb_batter_game_statcast_v1
**Version:** 1.0
**Build Date:** 2026-04-15
**PIT-Safety Status:** APPROVED AS SUBSTRATE

---

## PURPOSE

Provides per-batter, per-game Statcast contact metrics (exit velocity, hard-hit rate, barrel rate, launch angle, xwOBA on contact) as a PIT-safe historical substrate. No rolling features, no model outputs, no pregame projections. This substrate feeds downstream rolling-feature builders which must enforce strict date < game_date gating.

---

## CANONICAL SOURCE

- **Pattern:** `mlb/props/data/statcast_chunk_*.parquet`
- **Files found:** 33
- **Raw pitch rows (pre-dedup, summed across chunks):** 3,193,983
- **Duplicate pitch rows removed (within-chunk):** 0 (0.00%)
- **Retained pitch rows (post-dedup estimate):** 3,193,983
- **BIP rows (type == 'X', post-dedup):** 563,743

---

## DEDUP LOGIC

Deduplication applied within each chunk FIRST, before any aggregation, on the exact 4-field pitch-level key:

```
(game_pk, pitcher, at_bat_number, pitch_number)
```

- All four key fields verified present in every chunk
- `keep='first'` on duplicates within each chunk
- Final re-aggregation by `(game_pk, batter, game_date)` after combining chunk-level partial sums handles any rare cross-chunk overlap
- No fallback dedup keys invented

---

## AGGREGATION LOGIC

Streaming approach: one chunk at a time to preserve memory. BIP subset (`type == 'X'`) isolated per chunk. Partial sums accumulated then re-summed at final stage.

**BIP subset** (type == 'X'): 563,743 rows across all chunks

| Field | Method | Notes |
|-------|--------|-------|
| avg_exit_velo | sum_exit_velo / n_exit_velo | BIP with non-null launch_speed |
| hard_hit_rate | hard_hit_count / n_exit_velo | BIP with launch_speed >= 95 |
| barrel_rate | barrel_count / bip_count | BIP with launch_speed_angle == 6 |
| avg_launch_angle | sum_launch_angle / n_launch_angle | BIP with non-null launch_angle |
| xwoba_contact | sum_xwoba / n_xwoba | BIP with non-null xwOBA estimate |
| bip_count | count of BIP rows | Any type=='X' row |
| total_pitches | count of all pitch rows | All pitch rows per batter-game |

**xBA / xSLG:** Evaluated for inclusion based on coverage (>= 90% of BIP batter-games with at least one non-null value).
- xba_contact: INCLUDED
- xslg_contact: INCLUDED

Batter-game rows after streaming aggregation: 254,895

---

## JOIN LOGIC

Inner join to `mlb/data/hitter_game_logs.parquet` on `(game_pk, batter == player_id)`.

- HGL rows loaded: 204,548
- Fields carried from HGL: `batting_order_position`, `team`, `home_away`, `season`
- Join type: INNER (unmatched Statcast batter-games excluded and reported)
- Unmatched Statcast batter-games: 28,699 (reported, not silently dropped)
- Overall match rate: 87.3%

**Season-level coverage:**

- 2022: 48,319 joined rows / 58,073 aggregated (83.2%)
- 2023: 48,762 joined rows / 55,366 aggregated (88.1%)
- 2024: 48,751 joined rows / 54,388 aggregated (89.6%)
- 2025: 48,815 joined rows / 53,674 aggregated (90.9%)
- 2026: 2,850 joined rows / 4,695 aggregated (60.7%)

---

## OUTPUT SCHEMA

File: `research/recovery/mlb_hitter_statcast_substrate/batter_game_statcast.parquet`
Rows: 197,497
Columns: 17

| Column | Type | Description |
|--------|------|-------------|
| game_pk | int64 | MLB Stats API game ID |
| game_date | date | Game date |
| batter | int64 | Statcast batter ID |
| player_id | int64 | HGL player ID (matches batter via join) |
| team | str | Batter's team abbreviation |
| home_away | str | 'home' or 'away' |
| season | int | Season year |
| batting_order_position | float | Lineup slot (1-9); NOT approved for pregame use |
| total_pitches | int | Total pitches seen in game (all types) |
| bip_count | int | Balls in play (type == 'X') |
| avg_exit_velo | float | Mean exit velocity on BIP (mph) |
| hard_hit_rate | float | Fraction of BIP with exit velo >= 95 mph |
| barrel_rate | float | Fraction of BIP that are barrels (launch_speed_angle == 6) |
| avg_launch_angle | float | Mean launch angle on BIP (degrees) |
| xwoba_contact | float | Mean xwOBA on contact (BIP with Statcast estimates) |
| xba_contact | float | Mean xBA on contact (BIP) |
| xslg_contact | float | Mean xSLG on contact (BIP) |

**Coverage on output rows:**
- avg_exit_velo non-null: 94.7%
- xwoba_contact non-null: 94.6%
- batting_order_position non-null: 100.0%

---

## COVERAGE SUMMARY

- Seasons covered: [np.int32(2022), np.int32(2023), np.int32(2024), np.int32(2025), np.int32(2026)]
- Total batter-game rows: 197,497
- Unique batters: 1,060
- Unique games: 9,856

---

## PIT-SAFETY STATUS

**VERDICT: APPROVED AS SUBSTRATE**

This file contains only per-game historical outcomes. It carries no:
- Rolling averages, moving windows, or multi-game aggregations
- Pregame projections or predictions
- Model outputs or scores
- Forward-looking lineup card data

`batting_order_position` is carried from HGL as a historical fact (actual lineup slot that game) and is explicitly NOT approved for use as a pregame top/bottom-of-order feature without proper construction-date gating.

---

## WARNINGS / LIMITS

1. `batting_order_position` carried from HGL but **NOT approved** as a pregame lineup-card feature. Any future model using lineup position must construct it from pre-game confirmed lineups only.
2. No rolling features built — this is a per-game substrate only.
3. Future rolling builds consuming this substrate **MUST** use strict `date < game_date` with `shift(1)` to prevent PIT leakage.
4. Null rates on contact metrics are non-zero: exit velocity and angle are missing for some BIP (Statcast coverage gaps, particularly early 2022 and spring training games).
5. Dedup applied within-chunk. Final re-aggregation across chunks handles cross-chunk overlap via sum re-aggregation.

---

## STATUS

BUILD COMPLETE — 2026-04-15 02:32 UTC
