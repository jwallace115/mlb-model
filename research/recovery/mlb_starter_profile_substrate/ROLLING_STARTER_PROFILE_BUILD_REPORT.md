# ROLLING STARTER PROFILE — BUILD REPORT

**Generated:** 2026-04-15 09:28:44 UTC
**Output file:** research/recovery/mlb_starter_profile_substrate/rolling_starter_profile.parquet

---

## PURPOSE

This substrate provides lagged rolling window features for every starting pitcher appearance
in the MLB game universe (2022–2026). All rolling windows are strictly PIT-safe: each row
contains only information that was available BEFORE the start began (shift(1) applied before
rolling). This file is intended as a downstream input for model feature engineering,
signal validation, and live-game projection pipelines.

---

## INPUT AUDIT

| Field | Status | Null % |
|-------|--------|--------|
| game_pk | PRESENT | 0.0% |
| game_date | PRESENT | 0.0% |
| season | PRESENT | 0.0% |
| player_id | PRESENT | 0.0% |
| player_name | PRESENT | 0.0% |
| team | PRESENT | 0.0% |
| opponent | PRESENT | 0.0% |
| pitcher_hand | PRESENT | 0.0% |
| home_away | PRESENT | 0.0% |
| starter_flag | PRESENT | 0.0% |
| game_number | MERGED from game_table.parquet | 0.0% |

**game_number distribution:** {1: 19,590, 2: 324}  (324 doubleheader game-2 starts)

### Box-score fields (all present, 0.0% null)
innings_pitched, batters_faced, pitches, strikeouts, walks, hits_allowed,
earned_runs, home_runs_allowed, ground_outs, fly_outs, air_outs

### Statcast fields (all present, ~7.7% null overall)
hard_hit_rate, barrel_rate, whiff_rate, chase_rate, zone_rate,
zone_contact_rate, avg_exit_velo, avg_launch_angle

### Statcast enrichment by season

| Season | SC Enrichment | Rows |
|--------|--------------|------|
| 2022 | 93.2% | 4,860 |
| 2023 | 89.3% | 4,860 |
| 2024 | 94.3% | 4,854 |
| 2025 | 91.8% | 4,856 |
| 2026 | 97.3% | 484 |

### Missing Statcast fields (not in source substrate)
balls_in_zone, contacts_in_zone — absent from input; zone_contact_rate used as proxy.

---

## PRE-ROLLING START LAYER

Six derived rate metrics computed before rolling (no leakage — derived from same-row counts):

| Derived Column | Formula | Mean | Null % |
|----------------|---------|------|--------|
| k_rate | strikeouts / batters_faced | 0.2193 | 0.0% |
| bb_rate | walks / batters_faced | 0.0801 | 0.0% |
| hr_rate | home_runs_allowed / batters_faced | 0.0331 | 0.0% |
| hits_per_bf | hits_allowed / batters_faced | 0.2258 | 0.0% |
| whip_game | (hits+walks) / innings_pitched | 1.6286 | 0.0% |
| pitches_per_bf | pitches / batters_faced | 3.9167 | 0.0% |

*Note: whip_game and k_rate, bb_rate are used only as rolling inputs — they do NOT appear
as raw columns in the output (only their rolling windows are exported, except batters_faced
and innings_pitched which are carried as-is for downstream use).*

---

## COVERAGE

| Season | Starts | Avg null (rolling) | SC enriched |
|--------|--------|--------------------|-------------|
| 2022 | 4,860 | 21.4% | 93.2% |
| 2023 | 4,860 | 23.2% | 89.3% |
| 2024 | 4,854 | 22.1% | 94.3% |
| 2025 | 4,856 | 21.8% | 91.8% |
| 2026 | 484 | 86.9% | 97.3% |

**2026 null rate is high ({:.1f}%)** — expected: early-season rosters have few prior starts in the
rolling window. This is correct behavior (not a bug).

---

## ROLLING LOGIC

- Sort order: player_id, season, game_date, game_number
- Group keys: player_id × season (resets at season boundary — no cross-season leakage)
- Shift applied: shift(1) BEFORE rolling — game N uses only games 1..N-1
- Windows: last_3 (min=2), last_5 (min=3), last_10 (min=5)
- If fewer starts than min_periods, value is NaN (no imputation in this substrate)

**PIT-safety guarantee:** The shift(1) transform ensures zero same-game leakage.
Season boundary resets ensure no cross-season carry-forward.

---

## FEATURE FAMILIES

### BATMISS (2 base metrics × 3 windows = 6 columns)
- batmiss_k_rate → _last_3, _last_5, _last_10
- batmiss_whiff_rate → _last_3, _last_5, _last_10

### COMMAND (2 base metrics × 3 windows = 6 columns)
- command_bb_rate → _last_3, _last_5, _last_10
- command_zone_rate → _last_3, _last_5, _last_10

### CONTACT (4 base metrics × 3 windows = 12 columns)
- contact_barrel_allowed → _last_3, _last_5, _last_10
- contact_ev_allowed → _last_3, _last_5, _last_10
- contact_hh_allowed → _last_3, _last_5, _last_10
- contact_la_allowed → _last_3, _last_5, _last_10

### WORKLOAD (4 base metrics × 3 windows = 12 columns)
- workload_bf → _last_3, _last_5, _last_10
- workload_ip → _last_3, _last_5, _last_10
- workload_pitches → _last_3, _last_5, _last_10
- workload_ppbf → _last_3, _last_5, _last_10

### DAMAGE (2 base metrics × 3 windows = 6 columns)
- damage_hits_per_bf → _last_3, _last_5, _last_10
- damage_hr_rate → _last_3, _last_5, _last_10

---

## FIELD DISPOSITION

| Category | Count | Fields |
|----------|-------|--------|
| Identity | 10 | game_pk, game_date, season, player_id, player_name, team, opponent, pitcher_hand, home_away, game_number |
| Approved Rolling | 42 | All _last_3, _last_5, _last_10 columns |
| Carried (not rolled) | 3 | sc_enriched, batters_faced, innings_pitched |
| Excluded from output | many | All raw counting stats, derived rates (k_rate, etc.), Statcast counts, spin/extension/release fields |

**Total output columns:** 55

---

## PIT-SAFETY

VERDICT: **PASS**

- shift(1) applied universally before any rolling mean
- Grouped by player_id × season — no cross-season leakage
- Sort verified: player_id, season, game_date, game_number (doubleheader-safe)
- No imputation or forward-fill performed on rolling columns
- Derived rates (k_rate etc.) are same-row transformations, not leakage vectors

---

## WARNINGS

1. **2026 null rates high (86.9%)**: Season is early; most pitchers have <5 prior 2026 starts.
   Downstream consumers should use cross-season career stats as fallback if needed.
2. **balls_in_zone / contacts_in_zone absent**: These Statcast counting fields were not
   present in the source substrate. zone_contact_rate is used as the proxy.
3. **SC enrichment 2023: 89.3%**: Slightly lower than other seasons. 10.7% of 2023 starts
   have null Statcast rolling features. This is a source data gap, not a bug.
4. **min_periods thresholds**: last_3 requires 2, last_5 requires 3, last_10 requires 5.
   Early-season starts will have NaN in wider windows even if narrower windows populate.

---

## STATUS

**BUILD COMPLETE — APPROVED FOR DOWNSTREAM USE**

- Output rows: 19,914
- Output cols: 55
- Rolling features: 42
- Seasons covered: [2022, 2023, 2024, 2025, 2026]
- Round-trip verified: YES
