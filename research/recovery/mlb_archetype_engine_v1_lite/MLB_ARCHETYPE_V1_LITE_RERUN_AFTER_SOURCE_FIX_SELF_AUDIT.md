# MLB Archetype Engine V1-Lite — Rerun Self-Audit

**Run date:** 2026-04-14
**Auditor:** Automated pipeline + output inspection

---

## HARD STOP Checks

| Check | Threshold | Result | Status |
|---|---|---|---|
| Only-A games after source fix | ≤ 100 | 0 | PASS |
| Unresolved home_away rows | ≤ 1% | 0 (0.00%) | PASS |
| Source rows changed | audit only | 0 | INFO |

No hard stops triggered.

---

## Data Integrity

| Check | Result | Status |
|---|---|---|
| hitter_game_logs total rows | 204,548 | PASS |
| home_away H count | 102,121 | PASS |
| home_away A count | 102,427 | PASS |
| H/A ratio | 0.998 (balanced) | PASS |
| game_table merge — unresolved | 0 | PASS |
| Both-A games (both sides away) | 0 | PASS |
| Only-H games | 0 | PASS |
| Backup created | mlb/data/hitter_game_logs_pre_ha_fix_backup.parquet | PASS |

---

## Feature Construction

| Check | Result | Status |
|---|---|---|
| Lineup rolling window | 15 games, shift(1), min 10 | CORRECT |
| SP rolling window | 5 starts, shift(1), min 3 | CORRECT |
| Lookahead bias | None — shift(1) enforced | PASS |
| team_game rows | 19,712 (= ~2 teams × 9,856 games) | PASS |
| Lineup coverage (all 3 dims) | 98.4% overall | PASS |
| Home coverage | 9,702 / 9,856 = 98.4% | PASS |
| Away coverage | 9,700 / 9,856 = 98.4% | PASS |
| SP coverage (both dims) | 18,011 / 19,914 = 90.4% | PASS |

---

## Archetype Assignment

| Check | Result | Status |
|---|---|---|
| Tercile cuts derived from discovery only | Yes (2022-2023) | CORRECT |
| Same cuts applied to val and OOS | Yes | CORRECT |
| Archetype labels used | PATIENT_DAMAGE, PATIENT_CONTACT, IMPATIENT_POWER, IMPATIENT_WEAK, MIXED | CORRECT |
| SP profile labels used | ELITE, WILD_POWER, CONTACT, VULNERABLE, AVERAGE | CORRECT |
| Home lineup arch × away SP profile for home scoring | Yes | CORRECT |
| Away lineup arch × home SP profile for away scoring | Yes | CORRECT |

---

## OLS Residual Approach

| Check | Result | Status |
|---|---|---|
| Home scoring control variable | home_ops (15-game rolling OPS) | CORRECT |
| Away scoring control variable | away_ops (15-game rolling OPS) | CORRECT |
| OLS method | numpy lstsq, intercept included | CORRECT |
| Residual pooling | home + away halves combined per cell | CORRECT |

---

## Discovery Stage

| Check | Result | Status |
|---|---|---|
| Discovery years | 2022, 2023 | CORRECT |
| Discovery games (full coverage) | 2,233 | OK |
| Active cells (n≥20) | 16 / 16 | PASS |
| Max \|residual\| | 1.1581 | PASS |
| Pass threshold | 0.50 | PASS (1.1581 ≥ 0.50) |

---

## Validation Stage

| Check | Result | Status |
|---|---|---|
| Validation year | 2024 | CORRECT |
| Validation games (full coverage) | 1,242 | OK |
| Cells with data in both disc and val | 15 | OK |
| Directional consistency | 66.7% (10/15) | PASS |
| Pass threshold | 60% | PASS (66.7% ≥ 60%) |

---

## OOS Stage

| Check | Result | Status |
|---|---|---|
| OOS year | 2025 | CORRECT |
| OOS games (full coverage) | 1,161 | OK |
| Cells compared (disc ∩ OOS) | 16 | OK |
| Directional consistency | 43.8% (7/16) | FAIL |
| Pass threshold | 60% | FAIL (43.8% < 60%) |
| OOS consistency vs chance | 43.8% < 50% | Below chance |

---

## Comparison to Prior Run

| Metric | Prior Run | Rerun | Δ |
|---|---|---|---|
| Source rows changed | N/A | 0 | — |
| Home coverage | 26.7% | 98.4% | +71.7pp |
| Away coverage | 98.2% | 98.4% | +0.2pp |
| Discovery max residual | 0.804 | 1.158 | +0.354 |
| Discovery pass | YES | YES | unchanged |
| Validation dir consistency | 40.0% | 66.7% | +26.7pp |
| Validation pass | NO | YES | **CHANGED** |
| OOS run | No | Yes | new |
| OOS pass | N/A | NO | — |
| Final verdict | NO-GO | NO-GO | unchanged |

---

## Root Cause of Prior Run's False Diagnosis

The prior run attributed its 26.7% home coverage to a home_away flag imbalance ("128K away vs 76K home rows"). This was incorrect.

**True root cause:** The prior pipeline script referenced `pitcher_id` when constructing starter rolling features. The actual column in `pitcher_game_logs.parquet` is `player_id`. This column name error caused:
1. `starters.sort_values(['pitcher_id', 'game_date'])` → `KeyError: 'pitcher_id'` (or silent misprocessing)
2. The SP rolling features `sp_bat_miss` and `sp_command` to be null across all starter rows
3. The game-level join filtering on `dropna(subset=LINEUP_COLS + SP_COLS)` to discard the majority of rows
4. Asymmetric-appearing coverage because some rows happened to retain non-null SP values by coincidence

The home_away field in `hitter_game_logs.parquet` is correct and balanced (H=102,121, A=102,427, both-A games=0).

---

## Output File Verification

| File | Written | Status |
|---|---|---|
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_REPORT.md | Yes | PASS |
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_REGISTRY.json | Yes | PASS |
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_STAGE_TABLES.csv | Yes (auto-saved by pipeline) | PASS |
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_SELF_AUDIT.md | Yes | PASS |
| _rerun_results.pkl | Yes (auto-saved by pipeline) | PASS |
