# ST02 Live Deployment Report

**Date:** 2026-03-27
**Signal:** ST02 — road_trip_game_6plus (UNDER overlay)
**Status:** ACTIVE (conditional, tag-only)

---

## Task 1 — Game Table Refresh

`sim/data/game_table.parquet` already contained 2026 data (11 games from 2026-03-26) from a prior refresh. No additional completed March 27 games were available at time of run (today's games still in progress).

| Season | Games |
|:-------|------:|
| 2022 | 2,430 |
| 2023 | 2,430 |
| 2024 | 2,427 |
| 2025 | 2,428 |
| 2026 | 11 |
| **Total** | **9,726** |

ST02 computes non-null road_trip_game_num for all 11 2026 games. All show road_trip=1 (first away game of the season), which is correct.

---

## Task 2 — ST02 Live Conditional Overlay

### Activation Rules

All three must be true:

| # | Condition | Implementation |
|:--|:----------|:---------------|
| 1 | V1 direction = UNDER | Guaranteed by signal generator: ST02 block only runs inside the V1 UNDER signal path (after `p_under > 0.57` gate) |
| 2 | ST02 favorable zone = TRUE | `road_trip_game_num_away >= 6` from game_table lookup |
| 3 | P09 is NOT active | `evaluate_st02_overlay(st02_val, p09_active=True)` blocks activation and logs the block |

### Sizing

**Tag-only.** ST02 does not modify stake_units. The `apply_combined_overlay()` function in p09_overlay.py handles S12+P09 sizing exactly as before — ST02 is not passed to it.

### Files Changed

| File | Change | Lines |
|:-----|:-------|:------|
| `mlb_sim/pipeline/st02_overlay.py` | **New file.** ST02 computation, evaluation, P09 block logic. | 141 lines |
| `mlb_sim/pipeline/st02_overlay_config.json` | **New file.** Frozen config: threshold=6, status=ACTIVE. | 5 lines |
| `mlb_sim/pipeline/daily_signal_generator.py` | Added ST02 block after P09, before combined stake. Added ST02 cols to SIGNAL_COLS. Added ST02 to tag logging. | ~15 lines inserted |
| `dashboard.py` | Added `st02_active` to signal info dict. Added ST02 boost narrative text. | ~10 lines |

### Files NOT Changed

| File | Reason |
|:-----|:-------|
| `run_model.py` | Shadow logger already captures ST02 for all games via `shadow_signals.py` — no change needed |
| `mlb_sim/pipeline/s12_overlay.py` | Not touched |
| `mlb_sim/pipeline/p09_overlay.py` | Not touched — `apply_combined_overlay()` unchanged |
| `modules/` | No production modules modified |

### Signal Log Schema

New columns added to `mlb_sim/logs/signals_2026.parquet`:

| Column | Type | Description |
|:-------|:-----|:------------|
| `st02_overlay_active` | int (0/1) | 1 if ST02 fired on this signal |
| `st02_value` | int or null | Road trip game number for the away team |
| `st02_favorable_zone` | int (0/1) | 1 if road_trip >= 6 |
| `st02_blocked_by_p09` | int (0/1) | 1 if ST02 was favorable but blocked by P09 |

### Dashboard Rendering

ST02 active games show a blue narrative line:

> Road fatigue — away team on extended road trip

If both S12 and ST02 are active:

> Boosted — elite pitching environment + road fatigue

ST02 never displays when P09 is active (blocked).

---

## Validation Results

| Test | Result |
|:-----|:-------|
| ST02 activates on road_trip >= 6, P09 inactive | **PASS** |
| ST02 blocked when P09 is active | **PASS** (st02_overlay_active=0, st02_blocked_by_p09=1) |
| ST02 inactive on road_trip < 6 | **PASS** |
| ST02 handles null game_pk gracefully | **PASS** |
| 2026 games have non-null ST02 values | **PASS** (11/11) |
| S12 compute/evaluate unchanged | **PASS** |
| P09 compute/evaluate unchanged | **PASS** |
| apply_combined_overlay unchanged | **PASS** (BOTH=1.5u, S12_ONLY=1.25u) |
| SIGNAL_COLS includes all ST02 fields | **PASS** |

---

## Expected Behavior in Production

- **~25% of games** have road_trip >= 6 (historically ~600/season)
- Of those, only V1 UNDER signals are eligible (~40-50% of slate)
- Of those, games where P09 is also active are blocked (~40% of V1 UNDER signals)
- **Net:** ST02 should tag roughly **3-5 games per week** during the regular season
- **Sizing impact:** None — tag-only, no stake modification
- **Risk:** Zero additional risk — ST02 cannot create bets or change sizes
