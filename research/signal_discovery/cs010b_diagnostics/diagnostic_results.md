# CS010B Diagnostics — Dynamic Park Environment UNDER

**Date:** 2026-03-27
**Signal:** CS010B — pitcher-friendly game environment (bottom 20% env_score)
**Batch 2 result:** PASS (91.6th permutation percentile)
**Frozen threshold:** env_score <= 1.0647 (bottom 20%, 2022-2023)

---

## Summary Table

| Diagnostic | Question | Answer |
|:-----------|:---------|:-------|
| A. Quintile monotonicity | Monotonic toward UNDER? | **No** — Q2 (not Q1) has highest under rate |
| B. Segmentation | Broad-based? | **Partial** — 2023 and 2025 are below 50.9%; 2022 and 2024 are strong |
| C. Decay | Trend? | **INCONSISTENT** — +4.6, -2.5, +7.5, -1.5pp lift by year |
| D. V1 interaction | Adds value to V1 UNDER? | **Yes** — CS010B+V1 shows 56.7% under rate vs 56.2% V1 alone |
| E. CS004 conflict | What happens when both fire? | **CS004_DOMINANT** — overlap goes 51.1% OVER, not UNDER |

**Overall verdict: NEEDS_MORE_DATA**

---

## Diagnostic A — Quintile Monotonicity

### Full Dataset (2022-2025, N=6,471 open-roof)

| Quintile | Env Score Range | N | Under Rate | Residual |
|:---------|:----------------|---:|---:|---:|
| Q1 (most pitcher-friendly) | 0.715-1.050 | 1,295 | 52.43% | +0.249 |
| Q2 | 1.050-1.127 | 1,294 | **54.40%** | +0.255 |
| Q3 | 1.127-1.196 | 1,294 | 50.46% | +0.482 |
| Q4 | 1.196-1.276 | 1,294 | 50.93% | +0.508 |
| Q5 (most hitter-friendly) | 1.276-1.825 | 1,294 | 48.61% | +0.676 |

**Assessment: NOT MONOTONIC.** Q2 has the highest under rate (54.4%), not Q1 (52.4%). However, the general trend Q1-Q5 does slope from higher under toward lower under, and Q5 is clearly the lowest. The non-monotonicity is at the extreme — the most pitcher-friendly bucket (Q1) underperforms the second bucket (Q2).

The 2025-only pattern is worse: completely non-monotonic with Q1 at the *lowest* under rate (48.6%).

**Flag: MECHANISM_UNCLEAR for extreme quintile**

---

## Diagnostic B — Segmentation

### By Park Type

| Park Type | N | Under Rate | Residual |
|:----------|---:|---:|---:|
| Pitcher-friendly (PF < 98) | 791 | 52.21% | +0.326 |
| Neutral (98-102) | 424 | 54.01% | +0.130 |
| Hitter-friendly (PF > 102) | 282 | 53.19% | +0.306 |

Broadly consistent — the signal works across all park types when the game-specific environment is pitcher-friendly.

### By Season

| Season | N | Under Rate | Residual |
|:-------|---:|---:|---:|
| 2022 | 273 | **54.95%** | +0.191 |
| 2023 | 303 | 48.84% | +0.533 |
| 2024 | 413 | **57.38%** | +0.027 |
| 2025 | 508 | 50.59% | +0.344 |

**NOT BROAD-BASED.** 2023 (48.8%) and 2025 (50.6%) are weak. The strong results are concentrated in 2022 and 2024. This alternating pattern (strong-weak-strong-weak) is concerning — it suggests the signal may be capturing noise rather than a stable mechanism.

### By Closing Total

| Bucket | N | Under Rate | Residual |
|:-------|---:|---:|---:|
| < 7.5 | 561 | 52.41% | +0.513 |
| 7.5-8.5 | 660 | 52.58% | +0.172 |
| > 8.5 | 276 | 54.71% | -0.009 |

Consistent across closing totals. Higher totals actually show the best under rate, suggesting the signal identifies environments where the market sets the total too high.

---

## Diagnostic C — Signal Decay

| Season | N | Under Rate | Base Rate | Lift | Perm %ile |
|:-------|---:|---:|---:|---:|---:|
| 2022 | 273 | 54.95% | 50.31% | **+4.6pp** | 83.5% |
| 2023 | 303 | 48.84% | 51.36% | **-2.5pp** | 43.0% |
| 2024 | 413 | 57.38% | 49.89% | **+7.5pp** | 99.0% |
| 2025 | 508 | 50.59% | 52.13% | **-1.5pp** | 74.5% |

**Assessment: INCONSISTENT.** The signal alternates between strong positive (2022: +4.6pp, 2024: +7.5pp) and negative (2023: -2.5pp, 2025: -1.5pp). The 2024 season alone would be one of the strongest signals in the entire discovery project (99th permutation percentile), but it doesn't replicate in adjacent years.

This alternating pattern is the most concerning finding in these diagnostics. A real mechanism should not flip sign every other year.

---

## Diagnostic D — V1 UNDER Interaction

| Segment | N | Under Rate | Residual |
|:--------|---:|---:|---:|
| CS010B + V1 UNDER | 312 | **56.73%** | +0.111 |
| CS010B only | 1,185 | 51.90% | +0.308 |
| V1 UNDER only | 591 | 56.18% | -0.140 |
| Neither | 4,383 | 50.19% | +0.569 |

**Modest positive interaction.** When CS010B and V1 UNDER coincide, the under rate is 56.7% — slightly better than V1 UNDER alone (56.2%). The +0.6pp lift is small but directionally correct.

However, CS010B without V1 support shows only 51.9% under rate — barely above baseline. The signal does not function strongly on its own; it needs V1 UNDER as a base to add marginal value.

---

## Diagnostic E — CS004 Conflict Check

| Segment | N | Under Rate | Over Rate | Residual |
|:--------|---:|---:|---:|---:|
| CS010B only | 1,088 | **54.41%** | 45.59% | +0.102 |
| CS004 only | 1,459 | 50.24% | 49.76% | +0.554 |
| **Both fire** | **409** | **48.90%** | **51.10%** | **+0.705** |
| Neither | 3,515 | 51.18% | 48.82% | +0.456 |

**Classification: CS004_DOMINANT.** When both CS004 (OVER-side bullpen tail risk) and CS010B (UNDER-side park environment) fire simultaneously, the result leans OVER (51.1% over rate, +0.71 residual). CS004's bullpen blowup mechanism overrides CS010B's pitcher-friendly environment effect.

This is the second conflict finding involving CS004 (the first was CS004 vs ST02 in the interaction study). CS004 consistently dominates when in conflict with UNDER-side signals.

---

## Overall Verdict: NEEDS_MORE_DATA

### Why not SHADOW_READY:

1. **INCONSISTENT year-by-year trend** — the signal flips between strong positive (2022, 2024) and negative (2023, 2025) lifts. This alternating pattern is a red flag.
2. **Non-monotonic quintiles** — Q1 (most pitcher-friendly) is not the strongest bucket.
3. **2025 validation is weak** — only +0.6pp lift with 50.6% under rate in the binding OOS year.
4. **Does not function independently** — only 51.9% under rate without V1 UNDER support.
5. **Dominated by CS004 in conflict** — when both fire, the OVER side wins.

### What would change the verdict:

- If 2026 shows a positive lift (breaking the alternating pattern), the signal becomes more credible
- If the quintile relationship improves with more data, the mechanism strengthens
- The V1 interaction result (+0.6pp on top of V1 UNDER) is the most promising aspect — worth monitoring as a potential secondary UNDER overlay

### Comparison to CS004:

| Metric | CS004 | CS010B |
|:-------|:------|:-------|
| Batch permutation | 89.8% | 91.6% |
| Year-by-year trend | STRENGTHENING | **INCONSISTENT** |
| Quintile monotonicity | Partial (blowup freq is monotonic) | No |
| Standalone effect | Small but consistent | Weak without V1 |
| Diagnostic verdict | **SHADOW_READY** | **NEEDS_MORE_DATA** |

CS010B passed the batch test but fails the deeper diagnostic. This is exactly why multi-layer validation exists — a single permutation test is not sufficient.
