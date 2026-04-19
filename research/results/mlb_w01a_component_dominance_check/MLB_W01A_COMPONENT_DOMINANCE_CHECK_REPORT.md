# MLB W01A — COMPONENT DOMINANCE CHECK REPORT

**Test Date:** 2026-04-19
**Branch Name:** MLB_W01A_COMPONENT_DOMINANCE_CHECK
**Parent Branch:** MLB_W01_MANUAL_HISTORICAL_TEST
**Candidate ID:** MLB_W01
**Advancement Type:** MANUAL_CHILD_CHECK
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,804 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This child branch tests whether W01's signal requires its full 2-field conjunction (short-outing starter AND depleted bullpen), or whether one component carries the signal while the other adds little.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | confirmed |
| Orchestration layer | confirmed |
| Runtime object | MLB_RUNTIME_OBJECT_V1 — confirmed |
| Outside-package files | **NONE** |

---

## 3. MANUAL CHILD CHECK STATUS

This is a manual child check of MLB_W01. Not a new discovery, not autonomous promotion. Parent rule inherited exactly.

---

## 4. EXACT PARENT RULE CONFIRMED

| Element | Value |
|---|---|
| Field 1 | `opp_sp_workload_ip_last_3` (opposing starter) |
| Field 2 | `opp_bullpen_pitches_last_3` (opposing bullpen, via self-join) |
| Form | AND rule |
| Thresholds | IP <= 4.67 AND bullpen pitches >= 200 |
| Side | Batting team perspective |
| Direction | Flagged > unflagged |

No mutation.

---

## 5. FROZEN COMPARISON GROUPS

| Group | Definition | What It Tests |
|---|---|---|
| COMPONENT_A_ONLY | `opp_sp_workload_ip_last_3 <= 4.67` | Short-outing starter alone |
| COMPONENT_B_ONLY | `opp_bullpen_pitches_last_3 >= 200` | Depleted bullpen alone |
| W01_FULL_FORMULATION | Both conditions simultaneously | Exact parent rule |

---

## 6. NESTING / OVERLAP STRUCTURE

The three groups overlap but are NOT nested — each component flags a distinct subset beyond the full formulation:

| Stage | Comp A | Comp B | Full (A&B) | A_not_B | B_not_A |
|---|---|---|---|---|---|
| Discovery | 2,079 (24.9%) | 2,869 (34.3%) | 745 (8.9%) | 1,334 | 2,124 |
| Validation | 913 (21.9%) | 1,312 (31.5%) | 288 (6.9%) | 625 | 1,024 |
| OOS | 950 (22.7%) | 1,377 (32.9%) | 314 (7.5%) | 636 | 1,063 |

Both components flag substantially more rows than the full formulation. Neither is vacuous. Neither subsumes the other. The full formulation is the intersection — a properly smaller, more selective subset. This is structurally healthy for a conjunction test.

---

## 7. STAGE RESULTS

| Stage | Comp A Gap | Comp B Gap | Full Gap | Strongest |
|---|---|---|---|---|
| Discovery | +0.247 | +0.011 | **+0.323** | Full |
| Validation | +0.008 | +0.198 | +0.019 | Comp B |
| OOS | +0.297 | +0.015 | **+0.363** | Full |

### Discovery
- Component A (starter alone): +0.247 — substantial standalone signal
- Component B (bullpen alone): +0.011 — near-zero, essentially no signal
- Full formulation: +0.323 — strongest, exceeds Component A by +0.076

### Validation
- Component A: +0.008 — collapses almost entirely
- Component B: +0.198 — surprisingly the strongest validation signal
- Full formulation: +0.019 — also collapses

### OOS
- Component A: +0.297 — rebounds strongly
- Component B: +0.015 — near-zero again
- Full formulation: +0.363 — strongest, exceeds Component A by +0.066

---

## 8. INTERPRETATION

### Structural Assessment

**The full formulation consistently produces the largest gap in discovery and OOS.** In both non-validation stages, the full conjunction (+0.323, +0.363) exceeds Component A alone (+0.247, +0.297) by approximately +0.07. This suggests the bullpen-depletion component DOES add something to the starter-alone signal — the conjunction amplifies the effect by approximately 25-30% over the starter component alone.

However, **Component A (starter alone) carries the majority of the signal.** It produces +0.247 and +0.297 in discovery and OOS respectively — accounting for ~75% of the full formulation's gap. Component B alone (bullpen only) is essentially zero in discovery (+0.011) and OOS (+0.015).

**Validation is anomalous for all groups.** All three groups collapse in validation, but Component B briefly shows the only meaningful validation signal (+0.198). This is difficult to interpret — it may be noise, or 2024 may have had bullpen-related structural differences that temporarily elevated the bullpen component while suppressing the starter component.

### Does the Full Formulation Add Value?

**Partially yes.** The full formulation consistently produces a larger gap than Component A alone in both discovery and OOS. The amplification (~+0.07 per stage) is modest but direction-consistent. This is not the clean dominance pattern of E01A (where one component was vacuous). Both components contribute, but asymmetrically — starter carries ~75%, bullpen adds ~25%.

### Is This INTERACTION_REAL?

**Not cleanly.** INTERACTION_REAL requires the full formulation to show "stronger structural integrity than either component alone." The full formulation shows the largest magnitude, but Component A alone shows strong signal too. The interaction is better described as "Component A amplified by Component B" rather than "a genuinely interaction-dependent signal that neither component can capture."

### Verdict Reasoning

This is **MIXED_INCONCLUSIVE** because:
- The full formulation is NOT cleanly dominated by one component (unlike E01A where the park factor was vacuous)
- The full formulation IS partially dependent on Component A doing most of the work
- Component B adds consistent but modest amplification in non-validation stages
- Validation is anomalous for all groups
- The pattern is "Component A primary + Component B as amplifier" rather than "genuine interaction" or "clean single-component dominance"

---

## 9. FINAL VERDICT

**MIXED_INCONCLUSIVE**

The W01 decomposition shows a real but asymmetric structure: Component A (short-outing starter) carries approximately 75% of the signal, Component B (depleted bullpen) adds modest amplification (~25%). The full conjunction consistently exceeds either component alone in discovery and OOS, but the interaction is not strong enough to call INTERACTION_REAL, and Component A is too strong standalone to call COMPONENT_DOMINATED. Validation is anomalous for all groups. The formulation's structural integrity is partially confirmed but not decisively so.

---

## 10. WHAT THIS RESULT DOES NOT CLAIM

- This does not say W01 is deployment-ready
- This does not say the interaction is useless — Component B adds modest value
- This does not justify converting W01 into a starter-alone signal (that would be a different candidate)
- This does not close the W-family — the formulation is inconclusive, not dead

---

*Report generated: 2026-04-19*
