# NRFI Phase 5 — Small Engine Build vs Frozen Selector

**Date:** 2026-04-11
**Scope:** Logistic regression engines (A-D) vs frozen V1 selector
**Split:** Train=2023, Val=2024, OOS=2025

---

## Verdict: **SELECTOR REMAINS BEST**

No engine beat the frozen V1 selector on validation. Selector remains recommended.

---

## Temporal Split

| Split | Season | Games | NRFI Rate |
|-------|--------|-------|-----------|
| Train | 2023 | 1920 | 50.2% |
| Val | 2024 | 2366 | 53.1% |
| OOS | 2025 | 2349 | 49.6% |

**Note:** F5 data starts 2023 (2022 has 0% coverage). 2026 excluded (in-season).

## Engine Definitions

| Engine | Type | Features |
|--------|------|----------|
| A_market | LogReg(C=1) | f5_total_best, total_line |
| B_market_day | LogReg(C=1) | f5_total_best, total_line, is_day_game |
| C_full | LogReg(C=1) | f5_total_best, total_line, is_day_game, temperature, wind_speed, park_factor_runs, umpire_over_rate, both_sp_1st_nrfi_rate |
| D_rules | Fixed-weight | F5*10, day=-1, cold=-0.5, low_total=-0.5, high_park=+0.5, under_ump=-0.3 |
| +DQ variants | Same + disqualify night@F5=4.0 | (applied as filter) |

## Top-3 Card Results

| Method | Train Leg% | Train Card% | Val Leg% | Val Card% | OOS Leg% | OOS Card% |
|--------|-----------|------------|---------|----------|---------|----------|
| Frozen_V1 | 68.7% | 39.4% | 69.3% | 34.1% | 69.5% | 33.8% |
| Engine_A_market | 62.6% | 29.2% | 68.2% | 33.7% | 71.3% | 37.5% |
| Engine_B_market_day | 62.6% | 29.2% | 67.8% | 32.6% | 70.8% | 36.1% |
| Engine_C_full | 62.0% | 28.1% | 67.6% | 30.0% | 65.4% | 30.2% |
| Engine_D_rules | 62.6% | 29.2% | 65.2% | 28.1% | 68.5% | 31.9% |
| Engine_A_market+DQ | 69.7% | 42.4% | 68.6% | 34.1% | 71.4% | 38.0% |
| Engine_B_market_day+DQ | 69.7% | 42.4% | 68.2% | 33.0% | 70.9% | 36.6% |
| Engine_C_full+DQ | 65.4% | 34.6% | 68.1% | 30.4% | 65.4% | 30.8% |
| Engine_D_rules+DQ | 67.7% | 36.4% | 65.9% | 28.4% | 68.5% | 32.4% |

## Validation Selection

**Chosen engine:** Frozen_V1
**Reason:** Best card rate on validation

## OOS Comparison

| Method | Leg% | Card% | Slates |
|--------|------|-------|--------|
| Frozen V1 | 69.5% | 33.8% | 71 |
| Frozen_V1 | 69.5% | 33.8% | 71 |

**Delta card rate:** +0.0%
**Delta leg rate:** +0.0%

## Diagnostic: Top-3 Overlap (OOS)

Mean overlap with frozen selector: 3.00 / 3 legs

| Overlap | Pct of Slates |
|---------|---------------|
| 0/3 | 0.0% |
| 1/3 | 0.0% |
| 2/3 | 0.0% |
| 3/3 | 100.0% |

## Coefficients (chosen engine)

Frozen V1 has no coefficients — pure F5 sort.

---

## Decision: **SELECTOR REMAINS BEST**

No engine beat the frozen V1 selector on validation. Selector remains recommended.

## Files Produced

| File | Description |
|------|-------------|
| `nrfi_phase5_engine.py` | Full analysis script |
| `NRFI_PHASE5_FINAL_TABLE.csv` | All methods x splits comparison |
| `NRFI_PHASE5_EXEC_SUMMARY.md` | This file |