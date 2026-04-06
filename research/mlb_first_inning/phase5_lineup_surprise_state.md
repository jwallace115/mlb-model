# Phase 5 — Lineup Finalization / Top-of-Card Surprise Test

**Date:** 2026-04-06
**Design:** 2024-2025 (4,361 games). Default baseline = prior 7 team games.

---

## Verdict: LINEUP SURPRISE DID NOT PRODUCE A MEANINGFUL FIRST-INNING STATE EDGE.

No surprise definition is directionally consistent across both years, survives
controls, AND adds practical value to the NRFI helper framework. The strongest
raw effects are small (+2-4pp), inconsistent across years, and do not help filter
NRFI parlay candidates.

---

## Surprise Definitions Tested

| ID | Definition | Formula |
|----|-----------|---------|
| S1 | Leadoff change | Final leadoff player differs from mode of prior 7 team games |
| S2 | Top-3 quality shift | Final top-3 rolling OBP mean vs rolling 7-game team default; UP = top quartile delta, DOWN = bottom quartile |
| S3 | Handedness shift | Number of LHB in final top-3 differs by >= 0.5 from default |
| S4 | Damage shape shift | Final top-3 rolling ISO mean in top quartile of positive delta |
| S5 | Reach upgrade | Top quartile of positive delta in both OBP and SLG simultaneously |

Rates: Leadoff changes occur in ~31% of games. Quality/damage shifts in ~19% (by
quartile definition). Handedness shifts in ~25%.

---

## Side-Level Results

### Most Promising Raw Effects

| Surprise | Side | Hit (surprise) | Hit (non-surprise) | Delta | 2024 | 2025 |
|----------|------|---------------|-------------------|-------|------|------|
| S5 Away reach UP | top1 | 0.305 | 0.265 | **+0.041** | 0.266 | 0.347 |
| S3 Home hand shift | bot1 | 0.326 | 0.293 | **+0.033** | 0.319 | 0.333 |
| S4 Away damage UP | top1 | 0.296 | 0.263 | **+0.032** | 0.284 | 0.308 |
| S2 Away quality UP | top1 | 0.289 | 0.265 | +0.025 | 0.263 | 0.312 |

### Year-Level Consistency

| Surprise | 2024 | 2025 | Consistent? |
|----------|------|------|-------------|
| S5 Away reach UP | 0.266 | 0.347 | **NO** — flips direction (below base in 2024) |
| S3 Home hand shift | 0.319 | 0.333 | YES — directionally consistent |
| S4 Away damage UP | 0.284 | 0.308 | YES — directionally consistent |
| S2 Away quality UP | 0.263 | 0.312 | **NO** — below base in 2024 |

S5 (reach UP) has the largest raw effect (+4.1pp) but fails 2024 (below base rate).
S3 (handedness shift) and S4 (damage UP) pass the both-year check.

---

## YRFI-Level Compound Tests

| Compound Surprise | N | YRFI rate | Non-surprise | Delta | 2024 | 2025 |
|-------------------|---|-----------|-------------|-------|------|------|
| Either damage UP | 1,451 | 0.511 | 0.471 | **+0.040** | 0.511 | 0.511 |
| Leadoff + quality UP | 607 | 0.502 | 0.482 | +0.021 | 0.508 | 0.497 |
| Either quality UP | 1,471 | 0.492 | 0.481 | +0.011 | 0.483 | 0.500 |

"Either damage UP" is the strongest compound (+4.0pp YRFI), consistent across years
(0.511 in both 2024 and 2025). But the market residual is -5.1pp — the market
already prices these games as MORE likely to score (nrfi_implied=0.540 vs
actual_nrfi=0.489). **The market over-corrects for damage upgrades.**

---

## Control Checks

| Surprise | Raw delta | After controlling for total + park + broad offense |
|----------|-----------|---------------------------------------------------|
| S2 Away quality UP → top1 | +0.018 | **+0.016** (survives) |
| S4 Away damage UP → top1 | +0.020 | **+0.018** (survives) |
| S2 Home quality UP → bot1 | +0.006 | +0.008 (negligible) |
| S1 Away leadoff change → top1 | -0.005 | -0.014 (wrong direction) |

S2 and S4 survive controls — the delta is not just low-total leakage. But the
absolute effect size (~1.6-1.8pp) is very small.

---

## Practical Use Test

Within NRFI candidate pool (market implied NRFI >= 52%):

| Surprise | Surprise NRFI | Non-surprise NRFI | Delta | 2024 | 2025 |
|----------|--------------|-------------------|-------|------|------|
| S4 any damage UP | 0.507 | 0.539 | **-0.032** | 0.512 | 0.502 |
| S1 any leadoff change | 0.522 | 0.533 | -0.011 | 0.527 | 0.517 |
| S2 any quality UP | 0.526 | 0.530 | -0.004 | 0.543 | 0.510 |
| S2 any quality DOWN | 0.530 | 0.528 | +0.002 | 0.549 | 0.510 |

**S4 damage UP hurts NRFI candidates by -3.2pp** — games where either team's top-3
gets a damage upgrade are worse NRFI legs. This is directionally useful: **exclude
damage-surprise games from NRFI parlay pools.**

But the effect degrades OOS: 2024 = -2.7pp, 2025 = -3.7pp. The 2025 direction
holds but the absolute NRFI rate (0.502) is barely above 50% — meaning even the
"clean" non-surprise pool only produces 53.9% NRFI rate. This is inside the
existing Phase 4 helper's range (56.8%) and doesn't improve it.

---

## Decision Criteria Assessment

| Criterion | Result |
|-----------|--------|
| At least one surprise directionally consistent both years | S3 (hand shift) and S4 (damage UP) pass |
| Adds distinct information beyond totals/broad context | S4 survives controls (+1.8pp residual) |
| Plausible real-world interpretation | YES — damage upgrades = more HR/XBH risk in inning 1 |
| Practical value for NRFI helper | **NO** — excluding damage-UP games doesn't improve the existing pool |

Two of three analytical criteria pass, but the practical use criterion fails. The
effect is real but too small (~2pp) to improve the existing NRFI parlay helper,
which already operates at 56.8% NRFI from its own feature set.

---

## Why This Branch Didn't Work

1. **The market already adjusts for lineup changes.** NRFI implied probabilities
   in damage-surprise games are LOWER (0.489 actual vs 0.540 implied), meaning
   the market over-adjusts for lineup upgrades. There's no timing edge — the
   market moves with the lineup.

2. **Effect sizes are too small.** Even the best surprise (S4 damage UP) only
   shifts top-of-1st scoring probability by ~2pp. First-inning outcomes are
   dominated by randomness, not lineup composition changes.

3. **The existing NRFI helper pool already captures the useful variance.**
   The micro model's ranking (which uses top-3 profiles, pitcher TTO1, and
   platoon) subsumes most of what surprise detection would add.

---

## Conclusion

Lineup-finalization surprise is a real phenomenon — damage upgrades do correlate
with +2pp top-of-1st scoring after controls. But it is not a usable first-inning
filter because:
- The market already adjusts (over-adjusts) for lineup changes
- The effect size is too small to improve existing NRFI parlay selection
- It does not create a distinct YRFI pocket worth separate tracking

**Recommended disposition:** Close this branch. The first-inning research program
has now tested five branches (broad baseline, micro baseline, top-card interaction,
parlay helper rules, lineup surprise). Only the NRFI parlay helper (Phase 4) produced
a usable result, and it is already deployed as a shadow tracker.
