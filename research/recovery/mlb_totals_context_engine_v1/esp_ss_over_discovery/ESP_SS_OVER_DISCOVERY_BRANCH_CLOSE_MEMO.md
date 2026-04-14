# ESP × SS Over-Side Discovery — Branch Close Memo

**Closed:** 2026-04-14  
**Branch:** ESP=HIGH × SS=FRAGILE over-side mechanism discovery  
**Status:** CLOSED — no surviving object

---

## 1. PURPOSE

This memo closes the ESP × SS over-side discovery branch. It preserves both research conclusions and process caveats. It is not a betting memo. The branch produced no surviving object.

## 2. WHY THIS BRANCH EXISTED

The Context × MPS Crosswalk V1 identified ESP=HIGH × SS=FRAGILE as the only structural cell where OVERWARD_NUMBER led among market-path response families. This made it the strongest descriptive search universe for over-side mechanism research. The branch existed to test whether a real, exploitable mechanism could be found inside that descriptive universe. The crosswalk finding was descriptive — it described how the market tends to move, not where the market is wrong. This branch tested whether any mechanism underneath that tendency could survive disciplined execution.

## 3. MECHANISMS TESTED

1. **SURVIVAL_THRESHOLD_PATH** — Claimed that games bifurcate into survival vs break subpaths depending on whether the fragile starter survives the early stress window, producing a mixture distribution for full-game totals.

2. **FRONT_LOADED_DISTRIBUTION_SHAPE** — Claimed that run mass is disproportionately concentrated in innings 1–3 in this universe compared to the board baseline, representing a structural scoring-shape difference.

3. **LINEUP_AMPLIFIER_UNDERPRICING** — Claimed that specific lineup traits (patience, contact quality) amplify damage against fragile starters beyond what generic lineup strength explains, and the market underprices this interaction.

## 4. WHY EACH MECHANISM FAILED

**SURVIVAL_THRESHOLD_PATH:** The early-break / early-survival bifurcation is real and consistent (discovery gap +1.76 runs, all 4 seasons positive). But the board-wide MLB gap (+2.50) exceeds the target universe gap (+2.42). The effect is generic baseball, not specific to this structural universe. Stage B kill rule triggered.

**FRONT_LOADED_DISTRIBUTION_SHAPE:** The observed innings 1–3 run share in the universe was 35.1% versus a 33.9% board baseline — a +1.1pp gap against a pre-registered +7pp threshold. The median gap was exactly 0pp. There is no meaningful front-loading effect. Stage A kill rule triggered.

**LINEUP_AMPLIFIER_UNDERPRICING:** Patience (BB%) and contact quality (ISO) showed near-zero partial correlations with actual totals after controlling for generic lineup strength (r = −0.010 and +0.025). Both traits reversed direction across the two discovery seasons. No residual interaction exists beyond what generic lineup quality already captures. Stage A kill rule triggered.

## 5. WHAT THE BRANCH CLOSURE MEANS

The ESP=HIGH × SS=FRAGILE universe was useful as descriptive infrastructure — it correctly identified the structural cell with the strongest overward market-response tendency. But that descriptive finding did not translate into a surviving over-side mechanism from this branch. All three candidate mechanisms were tested with pre-registered kill rules, and all three failed cleanly. The crosswalk remains valid as a map of market behavior. The mechanisms built from it did not survive.

## 6. PROCESS CAVEATS TO PRESERVE

- **SURVIVAL_THRESHOLD_PATH:** Execution is treated as substantively clean. Self-audit passed with no warnings. Adjacent universes were declared before results. No threshold tuning occurred.

- **FRONT_LOADED_DISTRIBUTION_SHAPE:** Substantively closed (effect too small to matter). Process was noncompliant: an unauthorized cache file (`inning_cache.json`) was created during execution, and background tasks were spawned. These did not affect the substantive kill-rule conclusion (+1.1pp vs +7pp is unambiguous), but the execution was not pristine.

- **LINEUP_AMPLIFIER_UNDERPRICING:** Substantively closed (near-zero residuals, seasonal reversals). Process had one identified substitution: OPS was used as generic lineup control instead of the preferred wRC+ because wRC+ was not available in the source data. The self-audit correctly identified this. The kill-rule conclusion is robust to this substitution given the magnitude of the failure.

These caveats do not reopen the branch. They are preserved so future readers do not misremember the execution quality.

## 7. WHAT SHOULD REMAIN TRUE GOING FORWARD

- The crosswalk should still be treated as descriptive market-behavior infrastructure — it correctly maps structural states to market-path tendencies
- Descriptive overward leadership in a structural cell is not enough by itself to justify an object — all three mechanisms derived from the strongest such cell failed
- Future over-side work should not casually reuse ESP × SS as if this branch succeeded
- Reopening would require a genuinely new mechanism hypothesis, not a recycled version of the three failed branches
- Process discipline remains important — self-audits that miss violations erode trust in the full research chain

## 8. STATUS

ESP × SS over-side discovery is CLOSED. The descriptive universe remains valid, but the tested mechanism branch did not produce a surviving object. No live or shadow object behavior has been changed.

This memo is frozen as the branch-close record. Future work may reference it, but should not reopen this branch without a genuinely new mechanism hypothesis.
