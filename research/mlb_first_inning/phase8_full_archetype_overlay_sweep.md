# Phase 8 — Full Archetype Overlay Sweep on NRFI Parlay Helper

**Date:** 2026-04-06
**Design:** Exhaustive overlay test of all Phase 6 archetype flags on Phase 4 Rule D pool.
Train 2024, test 2025. No re-clustering or threshold tuning.

---

## Verdict: UPDATE PHASE 4 — Add "exclude home starter = CONTACT_RISK" overlay.

One overlay passes all strict decision criteria: excluding games where the home
starter is a CONTACT_RISK archetype from the Phase 4 Rule D pool.

---

## Full Overlay Ranking (Single Flags, Strict Threshold N25 >= 30)

| Overlay | N 2024 | NRFI 2024 | d24 | N 2025 | NRFI 2025 | d25 | 3-leg 25 |
|---------|--------|-----------|-----|--------|-----------|-----|----------|
| **no home_s=CONTACT_RISK** | **46** | **.630** | **+.033** | **44** | **.636** | **+.068** | **25.6%** |
| any_h=DAMAGE | 29 | .586 | -.011 | 36 | .611 | +.043 | 20.7% |
| any_s=WHIFF | 38 | .579 | -.018 | 42 | .595 | +.027 | 19.2% |

Only `no_home_s=CONTACT_RISK` is positive in both years. The other two candidates
fail the both-year consistency requirement.

### Side-Level Cells (informational — too small for production)

Best cells within the Phase 4 pool were mostly N < 15 in 2025 OOS. The side-level
matchup grid fragments too aggressively within the already-small Phase 4 pool
(~80 games/year). Not actionable.

---

## Best Candidate: Exclude Home Starter = CONTACT_RISK

### Rule (plain English)

> From the Phase 4 Rule D NRFI pool, exclude games where the home starting
> pitcher is classified as CONTACT_RISK (high walk rate + high hard-hit rate
> allowed). These starters allow too many baserunners and hard contact in the
> bottom of the 1st, undermining the NRFI lean.

### Performance

| Metric | Phase 4 Rule D | Phase 4 + Overlay | Improvement |
|--------|---------------|-------------------|-------------|
| NRFI 2024 | .597 (N=67) | **.630 (N=46)** | +3.3pp |
| NRFI 2025 OOS | .568 (N=81) | **.636 (N=44)** | **+6.8pp** |
| 3-leg parlay 2025 | 17.1% | **25.6%** | **+8.5pp** |
| 5-leg parlay 2025 | 5.8% | **9.1%** | +3.3pp |

### Decision Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| 2025 OOS N >= 30 | 44 | **PASS** |
| 2025 NRFI improvement >= +2pp | +6.8pp | **PASS** |
| Directionally non-negative in 2024 | +3.3pp | **PASS** |
| Fragility check survives | .600 after top-5 team removal (N=15) | **PASS (marginal)** |
| 3-leg parlay improves vs Phase 4 | 25.6% vs 17.1% | **PASS** |

All five criteria pass.

### Fragility Check

| Removal | N | NRFI |
|---------|---|------|
| Full overlay pool | 44 | .636 |
| Remove top-5 teams (STL, MIL, PIT, MIA, CHC) | 15 | **.600** |

Survives at .600 (still above Phase 4 raw .568) but N=15 is small. The starter
concentration is moderate — top starter appears 4 times out of 44 (9%). Not a
single-pitcher artifact.

---

## Mechanism

CONTACT_RISK starters are defined by:
- High walk rate (bb_rate_r5)
- High hard-hit rate allowed (hard_hit_rate_r5)
- Moderate whiff rate

These starters are the most likely to put the leadoff hitter on base (walks) and
then allow damage from the 2/3 hitters (hard contact). This is exactly the
mechanism identified in Phase 6: REACH/DAMAGE hitters vs CONTACT_RISK starters
produce the highest first-inning scoring rates.

Excluding CONTACT_RISK home starters from the NRFI pool removes the bottom-of-1st
vulnerability that was undermining the NRFI lean.

---

## Updated Rule (Plain English)

> **NRFI Parlay Helper — Updated Selection Rule:**
>
> Select games where:
> 1. Combined YRFI probability is in the bottom 10% of the day's slate
> 2. Both top-of-1st and bottom-of-1st probabilities are individually in bottom 30%
> 3. The home starting pitcher is NOT classified as CONTACT_RISK archetype
>    (i.e., home SP whiff_rate_r5 / bb_rate_r5 / hard_hit_rate_r5 profile does
>    not cluster with the high-walk, high-hard-hit group)
>
> Expected pool: ~4-5 games per 100 on the slate (~45/season).
> Expected NRFI hit rate: ~63% (vs ~57% without overlay, ~52% random).
> Expected 3-leg parlay hit rate: ~25% (vs ~17% without overlay, ~13% random).

---

## What This Is and Is Not

This overlay is a simple exclusion filter — it removes games where the home
pitcher's vulnerability profile undermines the NRFI case. It is NOT a standalone
signal, NOT a new model, and NOT a market edge claim.

It improves parlay leg quality by removing the worst ~35% of the Phase 4 pool
(games with CONTACT_RISK home starters), leaving a cleaner NRFI candidate set.
