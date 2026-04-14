# SURVIVAL_THRESHOLD_PATH — Execution V1

**Executed:** 2026-04-14
**Executor:** Claude (claude-sonnet-4-6)
**Output directory:** execution_v1/
**Status:** COMPLETE — all stages executed

---

## STEP 0 — PLAN CONFIRMATION

Frozen plan files read:
- SURVIVAL_THRESHOLD_PATH_TEST_PLAN.md — confirmed
- SURVIVAL_THRESHOLD_PATH_HARDENING_MEMO.md — confirmed

Frozen threshold: 3.0 IP (starter exits before completing 3 innings = BREAK)
Frozen tercile cuts: ESP HIGH > 48.5482; SS FRAGILE <= 45.9406
Discovery/Validation/OOS: 2022-2023 / 2024 / 2025

---

## STEP 1 — INPUT AUDIT (STAGE 0)

**CE V1 output table:** 9,715 rows (2022: 2430, 2023: 2430, 2024: 2427, 2025: 2428)
**ESP and SS columns present:** esp, ss, esp_label, ss_label — all present, continuous scores
**actual_total present in CE V1 table:** YES — no game_table join required

**Universe construction (frozen tercile cuts applied):**
- ESP=HIGH x SS=FRAGILE: **1,743 games**
- By season: 2022=356, 2023=518, 2024=422, 2025=447
- Boundary check: 132 games fell in HIGH/AVERAGE straddling zone; 1,611 are cleanly HIGH/FRAGILE

**Pitcher game logs:** 85,142 rows; starter_flag present; innings_pitched column confirmed
- Starter rows: 19,914
- IP range: 0.0 – 9.0
- Games with starter IP: 9,957

**Starter IP join to universe:** 1,743 / 1,743 (zero nulls)

**Path split (3.0 IP threshold applied):**
- BREAK (min_starter_ip < 3.0): 263 games (15.1%)
- SURVIVAL (min_starter_ip >= 3.0): 1,480 games (84.9%)

**Temporal splits:**
| Split | Years | Total | BREAK | SURVIVAL |
|-------|-------|-------|-------|----------|
| Discovery | 2022-2023 | 874 | 143 | 731 |
| Validation | 2024 | 422 | 63 | 359 |
| OOS | 2025 | 447 | 57 | 390 |

All splits exceed minimum thresholds (>20 per label). HARD STOP condition NOT triggered.

---

## STEP 2 — STAGE A: DISCOVERY (2022-2023)

**Discovery rows with actual total:** 874

| Path | n | Mean Total | Median | Std |
|------|---|-----------|--------|-----|
| BREAK | 143 | 10.81 | 10.0 | 5.86 |
| SURVIVAL | 731 | 9.05 | 9.0 | 4.41 |

**BREAK - SURVIVAL gap: +1.76 runs**
**Advancement criterion (gap >= 1.5): PASS**

### By season within discovery:
| Year | Path | n | Mean |
|------|------|---|------|
| 2022 | BREAK | 41 | 10.90 |
| 2022 | SURVIVAL | 315 | 8.41 |
| 2022 gap | — | — | +2.49 |
| 2023 | BREAK | 102 | 10.77 |
| 2023 | SURVIVAL | 416 | 9.54 |
| 2023 gap | — | — | +1.24 |

Both discovery seasons show positive gaps. No single-season concentration concern.
2023 gap (+1.24) is below 1.5 threshold individually, but discovery criterion applies to combined 2022-2023.

### By month (discovery):
| Month | BREAK n | BREAK mean | SURVIVAL n | SURVIVAL mean |
|-------|---------|-----------|------------|---------------|
| 04 | 16 | 12.00 | 98 | 8.52 |
| 05 | 24 | 13.25 | 142 | 9.42 |
| 06 | 22 | 9.27 | 118 | 9.55 |
| 07 | 20 | 10.95 | 111 | 8.66 |
| 08 | 17 | 9.71 | 124 | 9.25 |
| 09 | 40 | 10.48 | 125 | 8.94 |
| 10 | 4 | 7.25 | 12 | 6.42 |

Note: June (month 06) shows near-zero gap (BREAK 9.27 vs SURVIVAL 9.55, -0.28). Pattern strongest in April-May and September. No single month accounts for >40% of the pattern.

---

## STEP 3 — STAGE A: VALIDATION (2024) AND OOS (2025)

### Validation (2024):
| Path | n | Mean Total | Median | Std |
|------|---|-----------|--------|-----|
| BREAK | 63 | 11.46 | 11.0 | 5.26 |
| SURVIVAL | 359 | 8.64 | 8.0 | 3.83 |

**Validation gap: +2.82 runs — SAME DIRECTION as discovery: YES**
**Validation advancement criterion (>= 1.5): PASS**

### OOS (2025):
| Path | n | Mean Total | Median | Std |
|------|---|-----------|--------|-----|
| BREAK | 57 | 12.67 | 11.0 | 5.53 |
| SURVIVAL | 390 | 9.04 | 8.0 | 4.61 |

**OOS gap: +3.63 runs**

### Gap trend across all 4 seasons:
| Year | BREAK n | BREAK mean | SURVIVAL n | SURVIVAL mean | Gap |
|------|---------|-----------|------------|---------------|-----|
| 2022 | 41 | 10.90 | 315 | 8.41 | +2.49 |
| 2023 | 102 | 10.77 | 416 | 9.54 | +1.24 |
| 2024 | 63 | 11.46 | 359 | 8.64 | +2.82 |
| 2025 | 57 | 12.67 | 390 | 9.04 | +3.63 |

**Seasons with positive gap: 4 / 4 (criterion >= 3: PASS)**

Stage A overall: PASS (discovery +1.76, validation +2.82, OOS +3.63, 4/4 seasons positive)

---

## STEP 4 — STAGE B: UNIQUENESS CHECK

Adjacent universes declared BEFORE computing results:
- ADJ1: ESP=HIGH x SS=MODERATE (high pressure, moderate starters)
- ADJ2: ESP=MID x SS=FRAGILE (moderate pressure, fragile starters)
- BOARD: ALL MLB games

### Overall gaps (all seasons, all games with IP data):
| Universe | BREAK n | BREAK mean | SURVIVAL n | SURVIVAL mean | Gap |
|----------|---------|-----------|------------|---------------|-----|
| TARGET_HIGH_FRAG | 263 | 11.37 | 1,480 | 8.95 | **+2.42** |
| ADJ1_HIGH_MOD | 153 | 10.96 | 824 | 9.07 | +1.89 |
| ADJ2_MID_FRAG | 158 | 10.82 | 899 | 8.73 | +2.09 |
| BOARD | 1,240 | 11.05 | 8,475 | 8.55 | **+2.50** |

### Kill rule evaluation:
- Target gap: +2.42
- Board-wide gap: +2.50
- Board / Target ratio: 1.033 (103.3%)
- Kill condition (board >= 80% of target): **TRIGGERED — KILL**

The board-wide BREAK-SURVIVAL gap (+2.50) **exceeds** the target universe gap (+2.42).
The bifurcation pattern is not unique to ESP=HIGH x SS=FRAGILE. It exists generically across all MLB games and is, if anything, slightly larger in the full board.

### By season (board vs target):
| Year | Target gap | Board gap |
|------|-----------|----------|
| 2022 | +2.49 | +2.92 |
| 2023 | +1.24 | +1.78 |
| 2024 | +2.82 | +2.27 |
| 2025 | +3.63 | +3.14 |

2024-2025 show target slightly exceeding board, but the aggregate measure triggers the kill rule.

**Stage B result: KILL — pattern is generic**

---

## STEP 5 — STAGE C: PREGAME PROXY SCREEN

**Note:** Stage B triggered the kill rule. Stage C is executed for completeness but does NOT change the final verdict. Results are documented but cannot advance to a new object.

Executed on discovery data only (2022-2023). Discovery universe: 874 games.

**Candidate proxy: min_rolling_avg_ip** (per-starter expanding mean of innings_pitched, shift(1))

| Path | n | Mean rolling avg IP | Std |
|------|---|-------------------|-----|
| BREAK | 143 | 3.45 | 1.51 |
| SURVIVAL | 731 | 4.39 | 0.69 |

- Rolling IP difference (SURVIVAL - BREAK): +0.94 innings
- Direction (SURVIVAL starters historically pitched more): YES
- Cohen's d: 0.80 (large effect)
- t-test: t=7.29, p < 0.0001

**Result: Proxy separates paths with large effect.** Survival-path starters have historically pitched ~0.94 more innings per start on average. The proxy is mechanically expected — starters who historically throw fewer innings are more likely to exit early — rather than novel insight.

**Critical note:** This proxy is expected by construction, not a novel finding. A starter who routinely pitches only 3 innings on average will obviously more often exit before 3 IP. The proxy is not independent evidence of a tradable pregame signal. Under Stage B kill conditions, this cannot constitute a new research object without first establishing that the BREAK/SURVIVAL pattern itself is universe-specific.

---

## STEP 6 — STAGE D: FINAL VERDICT

**VERDICT: NO-GO — CLOSE NOW**

Reason: Stage B kill rule triggered. The BREAK-SURVIVAL scoring gap is generic across all MLB games (+2.50 board-wide vs +2.42 universe-specific). The ESP=HIGH x SS=FRAGILE filter does not add explanatory power above and beyond simply observing early starter exits in any game context. The pattern is real (Stage A passed cleanly) but not unique to the target universe.

The bifurcation effect is a board-level observation: whenever a starter exits before 3 IP in any MLB game, the full-game total is approximately 2.5 runs higher than when the starter completes 3+ IP. This is not a CE V1 universe-specific insight.

**Branch status: CLOSED**

---

## APPENDIX: STAGE C PRESERVATION NOTE

Despite the NO-GO verdict, the Stage C finding (rolling avg IP as predictor of early exit probability, Cohen's d = 0.80) is noted for completeness. If a future research effort revisits board-level early-exit prediction as a live object, the proxy finding would need:
1. Its own independent discovery/validation/OOS chain
2. Verification that it provides edge above market pricing of totals (not just correlation with outcome)
3. A new research object identity (not inherited from this branch)

This note is informational only and does not authorize any testing or live object creation.
