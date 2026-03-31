# CS004 × UNDER Interaction Report

**Date:** 2026-03-27
**Signal:** CS004 — Bullpen collapse tail risk (OVER direction)
**Study:** Interaction with UNDER signal stack
**Dataset:** 1,135 historical UNDER plays (2024-2025), 1,091 non-push

---

## Summary Table

| Question | Answer |
|:---------|:-------|
| 1. Does CS004 broadly hurt UNDER plays? | **Mildly.** -1.4pp under win rate, +0.34 residual. Below the 2pp caution threshold. |
| 2. Which context most affected? | **V1+ST02** — the largest effect (-4.2pp under WR when CS004 active) |
| 3. Does CS004 conflict with ST02? | **Yes.** ST02+CS004 overlap: 51.3% under WR vs 58.2% ST02-alone. -6.9pp delta. |
| 4. Does excluding CS004 improve UNDER? | **Marginally overall (+0.4pp).** More meaningful for V1+ST02 (+1.0pp). |
| 5. Best operational role? | **CONTEXT_SPECIFIC_CAUTION_FLAG** — display on ST02 UNDER plays specifically |

---

## Step 2 — Pooled UNDER Test

| Group | N | Under Win Rate | Mean Residual | Median Residual |
|:------|---:|---:|---:|---:|
| CS004 = TRUE | 297 | 54.88% | +0.224 | — |
| CS004 = FALSE | 794 | 56.30% | -0.112 | — |
| **Delta** | — | **-1.42pp** | **+0.336** | — |

**Assessment: NO_BROAD_EFFECT.** The delta (-1.4pp) is below the 2pp threshold for CAUTION_BROAD. CS004 does push residuals higher (+0.34 runs in flagged games), but the effect is not large enough to warrant a blanket UNDER caution flag.

---

## Step 3 — By-Context Test

| Context | CS004 | N | Under WR | Residual | Flag |
|:--------|:------|---:|---:|---:|:-----|
| V1_ONLY | TRUE | 195 | 55.38% | +0.118 | |
| V1_ONLY | FALSE | 470 | 57.02% | -0.051 | |
| V1_S12 | TRUE | 9 | 66.67% | -0.333 | THIN |
| V1_S12 | FALSE | 38 | 57.89% | -0.961 | |
| **V1_ST02** | **TRUE** | **69** | **52.17%** | **+0.645** | |
| **V1_ST02** | **FALSE** | **211** | **56.40%** | **-0.187** | |
| V1_CSE | TRUE | 17 | 58.82% | +0.147 | THIN |
| V1_CSE | FALSE | 61 | 42.62% | +0.656 | |

### Key Finding: V1+ST02 is the most affected context

When CS004 is active on a V1+ST02 UNDER play:
- Under win rate drops from 56.4% to 52.2% (**-4.2pp**)
- Market residual jumps from -0.19 to +0.65 (**+0.83 runs**)

This makes structural sense: ST02 is a road-fatigue UNDER signal, but CS004 flags bullpen tail risk — which means the away team's bullpen (already fatigued from the road trip) is also at elevated blowup risk. The two mechanisms conflict: road fatigue suppresses scoring early, but a fatigued bullpen can blow up late.

V1_ONLY shows a smaller delta (-1.6pp) — the effect is present but modest.

V1_S12 is thin-sample (N=9 with CS004) and cannot be evaluated.

V1_CSE is counterintuitive — CS004 TRUE actually *helps* the under (58.8% vs 42.6%) — but N=17 is far too thin to be reliable.

---

## Step 4 — Key Combinations

| Combination | N | Under WR | Residual | Flag |
|:------------|---:|---:|---:|:-----|
| **ST02 + CS004** | **76** | **51.32%** | **+0.579** | |
| ST02 alone | 225 | 58.22% | -0.304 | |
| S12 + CS004 | 16 | 56.25% | -0.219 | THIN |
| S12 alone | 52 | 65.38% | -1.260 | |
| CSE + CS004 | 30 | 53.33% | +0.033 | |
| CSE alone | 98 | 42.86% | +0.612 | |

### ST02 × CS004 Conflict Confirmed

| Metric | ST02 alone | ST02 + CS004 | Delta |
|:-------|---:|---:|---:|
| N | 225 | 76 | |
| Under WR | 58.22% | 51.32% | **-6.9pp** |
| Residual | -0.304 | +0.579 | **+0.88 runs** |

**This is the strongest interaction in the study.** When both ST02 (road fatigue UNDER) and CS004 (bullpen collapse OVER) are active, the UNDER win rate collapses from 58.2% to 51.3%. The residual swings from -0.30 (games going under) to +0.58 (games going over).

**Mechanism:** The road-fatigued away team's bullpen is simultaneously in a high-variance state. The road fatigue that ST02 detects suppresses early scoring, but the bullpen tail risk detected by CS004 means late-game blowups are more likely — partially or fully negating the UNDER edge.

---

## Step 5 — Defensive Filter Value

| Segment | N All | N Removed | Old Under WR | New Under WR | Improvement |
|:--------|---:|---:|---:|---:|---:|
| ALL_UNDER | 1,091 | 297 | 55.91% | 56.30% | **+0.39pp** |
| V1_ONLY | 665 | 195 | 56.54% | 57.02% | +0.48pp |
| V1_S12 | 47 | 9 | 59.57% | 57.89% | -1.68pp |
| **V1_ST02** | **280** | **69** | **55.36%** | **56.40%** | **+1.04pp** |
| V1_CSE | 78 | 17 | 46.15% | 42.62% | -3.53pp |

**Assessment: WEAK_DEFENSIVE_FILTER overall (+0.4pp), but meaningful for V1+ST02 (+1.0pp).**

Removing CS004-flagged games from the V1+ST02 cohort improves UNDER win rate by 1.0pp and shifts the residual from +0.02 to -0.19. This is a modest but structurally sound improvement.

For V1_S12 and V1_CSE, removing CS004 actually *hurts* — but these are thin-sample effects that should not be trusted.

---

## Step 7 — Season Stability

| Season | CS004=T Under WR | CS004=F Under WR | Delta |
|:-------|---:|---:|---:|
| 2024 | 59.75% | 57.72% | **+2.0pp** (CS004 helps UNDER) |
| 2025 | 49.28% | 54.89% | **-5.6pp** (CS004 hurts UNDER) |

**Assessment: INCONSISTENT.**

In 2024, CS004-flagged UNDER plays actually *won more* (+2.0pp). In 2025, CS004-flagged plays *lost significantly* (-5.6pp). The caution effect is concentrated entirely in 2025.

This instability means the defensive filter recommendation should be cautious. The 2025 effect may be real (consistent with CS004's strengthening trend in the diagnostics), or it may be noise in a single season.

---

## Overall Assessment

### Classification: CONTEXT_SPECIFIC_CAUTION_FLAG

CS004 is **not** a general UNDER caution flag. The pooled effect (-1.4pp) is too small and seasonally unstable (+2.0pp in 2024, -5.6pp in 2025) to warrant blanket application.

However, CS004 **does specifically conflict with ST02**:
- ST02+CS004: 51.3% under WR, +0.58 residual (N=76)
- ST02 alone: 58.2% under WR, -0.30 residual (N=225)
- Delta: **-6.9pp**, the largest interaction effect in the study

This conflict is mechanistically coherent: road fatigue (ST02) and bullpen blowup risk (CS004) pull in opposite directions on late-game scoring.

### Recommended Operational Interpretation

**Display CS004 as a visual caution indicator on V1+ST02 UNDER plays.**

Specifically:
- When ST02 is active AND CS004 is flagged: show a caution note ("bullpen tail risk present — road fatigue UNDER edge may be reduced")
- Do NOT use CS004 as a blanket UNDER filter or sizing reduction
- Do NOT apply to V1_ONLY or V1_S12 contexts (no meaningful interaction)
- Continue shadow-monitoring CS004 as an independent OVER-side signal

### What NOT to do

- Do not block ST02 entirely when CS004 is active (the 51.3% under WR is still above 50%)
- Do not use CS004 for UNDER stake reduction (effect is too small and unstable)
- Do not treat the 2025-only effect as confirmed — one season is insufficient
