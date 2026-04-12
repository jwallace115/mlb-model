# PHASE 5 — Priority Scoring and Retest Queue

**Date:** 2026-04-12

---

## Scoring Criteria (0-10 each, max 50)

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Mechanism soundness | 10 | Does the hypothesis have a plausible causal path? |
| Data cleanliness | 10 | Is a PIT-safe clean test feasible with existing data? |
| Early evidence | 10 | Shadow/preliminary results directionally positive? |
| Market fit | 10 | Is the target market liquid with manageable vig? |
| Build effort | 10 | Can a clean retest be done in <1 week? |

---

## RETEST REQUIRED Objects — Ranked

| Rank | Object | Mech | Data | Evidence | Market | Effort | Total | Priority |
|------|--------|------|------|----------|--------|--------|-------|----------|
| 1 | C2 ADJ_HH | 8 | 9 | 9 | 6 | 9 | **41** | **HIGH** |
| 2 | G1 Over Scanner (standalone) | 7 | 8 | 7 | 7 | 6 | **35** | **HIGH** |
| 3 | C3 ADJ_K_RATE | 8 | 9 | 7 | 6 | 9 | **39** | **HIGH** |
| 4 | C5 ADJ_RUN_SUPP | 7 | 9 | 7 | 6 | 9 | **38** | **HIGH** |
| 5 | C1 ADJ_CONTACT | 7 | 9 | 6 | 6 | 9 | **37** | **MEDIUM** |
| 6 | F3 F5/FG Path Mismatch | 7 | 8 | 5 | 7 | 5 | **32** | **MEDIUM** |
| 7 | C9 CS004 | 6 | 9 | 5 | 6 | 8 | **34** | **MEDIUM** |
| 8 | D5 CS025 F5 RL Overlay | 6 | 8 | 8 | 8 | 7 | **37** | **LOW** |

---

## Retest Queue — Execution Plan

### Tier 1: Let Shadow Accumulate (no build needed, just wait + add prices)

**C2 ADJ_HH** — Wait for N=100 resolved. Currently N=34 at 61.8%. Add actual closing
UNDER price logging to shadow pipeline. Review date: ~2026-05-15 at current pace.

**C3 ADJ_K_RATE** — Same. N=30 at 56.7%. Review at N=100.

**C5 ADJ_RUN_SUPP** — Same. N=34 at 55.9%. Review at N=100.

**C1 ADJ_CONTACT** — Same. N=65 at 53.8%. Almost at review threshold. If still <54%
at N=100, downgrade to CLEAN KILL.

### Tier 2: Active Retest Needed

**G1 Over Scanner** — Requires clean standalone retest WITHOUT V1 interaction gate.
The V1 gate was contaminated. Test OV043/OV016/OV001 as pure standalone signals
using only boxscore-derived features (PIT-safe) against actual closing over prices.
Estimated effort: 3-5 days.

**F3 F5/FG Path Mismatch** — Research in progress. Complete the late_implied feature
analysis with 2024-2025 data. Estimated effort: 2-3 days.

**C9 CS004** — Check current shadow fire rate. If firing at reasonable rate, add to
Tier 1 (wait for accumulation). If 0 fires like CS013/CS028/KP04, reclassify as
UNVERIFIABLE.

### Tier 3: Conditional (only if parent signal degrades)

**D5 CS025 F5 RL Overlay** — Only retest if D3 (Signal B) shows degradation in live
shadow. Currently D3 is the only surviving profitable object. The command overlay
adds no marginal edge over unfiltered Signal B.

---

## Critical Gap: Real Prices

The single most important infrastructure improvement for ALL retest objects is
**actual closing price logging**. Every surviving shadow signal assumes flat -110.
Without real prices, no promotion to live betting is possible.

**Action:** Modify shadow logging to capture actual UNDER closing line at game
resolution time for all ADJ signals. F5 RL already has price logging.
