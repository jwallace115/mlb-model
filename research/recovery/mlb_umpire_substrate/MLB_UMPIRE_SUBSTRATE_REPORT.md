# MLB UMPIRE SUBSTRATE -- BUILD REPORT
**Build date:** 2026-04-15
**Build ID:** MLB_UMPIRE_SUBSTRATE_v1
**Output:** research/recovery/mlb_umpire_substrate/mlb_umpire_substrate.parquet

---

## PURPOSE

This substrate provides a single, authoritative, game-level umpire signal table derived from
`sim/data/game_table.parquet` and the repaired `modules/umpires.py` (repair ID:
`MLB_UMPIRE_RATINGS_2026_REPAIR`). It is the canonical join key for all downstream model
pipelines that require umpire features. It is NOT a historical PIT-safe backtest table.

---

## SOURCE + SCOPE CONFIRMATION

### Game source
- File: `sim/data/game_table.parquet`
- Rows: 9,902 (one per game_pk)
- game_pk unique: True (confirmed)
- Seasons: 2022 (2,430), 2023 (2,430), 2024 (2,427), 2025 (2,428), 2026 (187)

### Ratings source
- File: `modules/umpires.py` (repaired 2026-04-15, repair ID: MLB_UMPIRE_RATINGS_2026_REPAIR)
- UMPIRE_RATINGS entries: 92 rated umpires
- Ratings derived exclusively from 2022-2025 game outcomes (season 2026 excluded)
- League-average baseline: 8.870201 runs/game (9,715 qualifying games)
- Min-games threshold: 30 (below => neutral fallback 1.000)
- Clamp range: [0.90, 1.10]

### Repair registry confirmation
- repair_id: MLB_UMPIRE_RATINGS_2026_REPAIR
- seasons_used: [2022, 2023, 2024, 2025]
- seasons_excluded: [2026]
- eligible_umpires: 92
- ineligible_umpires: 19
- coverage_before: 50.8% game coverage
- coverage_after: 97.2% game coverage
- Bugs fixed:
  1. Lance Barrett missing from UMPIRE_RATINGS (122 game_table games, rf=1.0193)
  2. Alfonso Marquez unicode mismatch (accented key, NFKD normalization added)
  3. Last-name fallback cross-collision (Lance Barrett -> Ted Barrett, -2.5pp error)

---

## FIELD INVENTORY + DISPOSITION

| Field | Type | Disposition | Notes |
|---|---|---|---|
| game_pk | int64 | IDENTITY | Primary key, unique |
| date | object/date | IDENTITY | Game date |
| season | int64 | IDENTITY | Season year |
| umpire_name | object | CARRIED_ONLY_SUPPORT_FIELD | Passed through from game_table |
| umpire_id | int64 | CARRIED_ONLY_SUPPORT_FIELD | MLB Stats API umpire ID |
| umpire_over_rate | float64 | APPROVED_UMPIRE_FEATURE | 2026-frozen scope only |
| umpire_k_rate | float64 | CARRIED_ONLY_SUPPORT_FIELD | All zeros -- not rebuildable |
| umpire_matched | bool | CARRIED_ONLY_SUPPORT_FIELD | True if non-neutral rating applied |

**APPROVED_UMPIRE_FEATURE (1):** `umpire_over_rate`
**CARRIED_ONLY_SUPPORT_FIELD (4):** `umpire_name`, `umpire_id`, `umpire_k_rate`, `umpire_matched`
**EXCLUDED (0):** None -- all fields serve a documented purpose.

---

## GRAIN CHECK

- Substrate rows: 9,902
- game_pk duplicates: 0
- Null counts: 0 in any field

---

## COVERAGE CHECKS

### Overall
- Non-neutral umpire_over_rate (matched): 9,626 / 9,902 = **97.2%**
- Neutral fallback (19 ineligible below-threshold umpires): 276 games = 2.8%

### By season
| Season | Matched | Total | Coverage |
|---|---|---|---|
| 2022 | 2,271 | 2,430 | 93.5% |
| 2023 | 2,420 | 2,430 | 99.6% |
| 2024 | 2,393 | 2,427 | 98.6% |
| 2025 | 2,359 | 2,428 | 97.2% |
| 2026 | 183 | 187 | 97.9% |

Lower 2022 coverage reflects umpires who retired mid-dataset and never reached 30-game threshold
in 2022-2025 combined.

### Key umpire spot checks
| Umpire | Games in substrate | runs_factor | Status |
|---|---|---|---|
| Lance Barrett | 125 | 1.0193 | MATCHED (bug-fixed) |
| Alfonso Marquez | 121 | 1.0700 | MATCHED (unicode fixed) |
| Ted Barrett | 29 | 1.0000 | NEUTRAL (29 games, below threshold) |
| Angel Hernandez | (present) | 1.0640 | MATCHED |
| UNKNOWN_UMP | N/A | 1.0000 | NEUTRAL (fallback) |

### umpire_k_rate
- All values: 0.000 (100% zero)
- Not rebuildable from game_table alone (pitch-level ball/strike data required)
- Status: CARRIED_ONLY -- do not promote to feature

---

## DISTRIBUTION CHECK

umpire_over_rate summary:
- count: 9,902
- mean: 1.000877
- std: 0.049102
- min: 0.900 (clamped floor)
- 25%: 0.965
- 50%: 1.000
- 75%: 1.035
- max: 1.100 (clamped ceiling)
- Clamped at floor (0.90): 7 umpires
- Clamped at ceiling (1.10): 3 umpires

---

## PIT-SAFETY + USAGE VERDICT

**VERDICT: PIT-SAFE for 2026 live model use only.**

### What this means
- `umpire_over_rate` is approved for use in the 2026 daily model pipeline.
- Ratings computed exclusively from 2022-2025 game outcomes; no 2026 outcome data used.
- For 2026 games, no future information contaminates the ratings.

### What this does NOT mean
- This substrate does NOT establish PIT-safe umpire features for 2022-2025 backtests.
- Using these ratings in a 2022-2025 backtest is a look-ahead violation: the full
  4-year window of outcomes is baked into every historical rating.
- Any future historical backtest that includes umpire features must use a separate PIT-safe
  rebuild (rolling or leave-one-season-out methodology).

---

## CARRY-FORWARD NOTES

1. **umpire_over_rate scope is 2026-frozen only.** Do not use this substrate for 2022-2025
   backtests without explicit historical PIT-safe rebuild.

2. **umpire_k_rate is all zeros.** This field exists for schema continuity but carries no
   information. Do not promote to an active feature. If strike/ball data becomes available,
   rebuild separately.

3. **19 umpires remain on neutral fallback.** These umpires had fewer than 30 qualifying
   games in 2022-2025: James Jean (29), Ted Barrett (29), Jonathan Parra (27), Jerry Meals
   (27), Jim Reynolds (21), Bill Welke (20), David Arrieta (19), Ed Hickox (18), Willie
   Traynor (17), Jose Navas (11), Marty Foster (11), Greg Gibson (10), Tom Hallion (10),
   Jen Pawol (6), Tyler Jones (5), Steven Jaschinski (5), Randy Rosenberg (4), Dexter Kelley
   (4), Lew Williams (2). They receive runs_factor=1.000.

4. **Backup exists.** The original modules/umpires.py was backed up to
   `modules/umpires.py.bak_2026` before the repair step.

5. **modules/umpires.py not modified in this step.** The substrate build is read-only
   with respect to source modules.

---

*Build completed: 2026-04-15*
*Built by: MLB Umpire Substrate Builder v1*
