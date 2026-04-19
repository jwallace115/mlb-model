# MLB E-FAMILY PASS 02 — CLOSEOUT MEMO

**Closeout Date:** 2026-04-18
**Family Name:** MLB_E_FAMILY_PASS_02
**Family Scope:** CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION
**Family Disposition:** CLOSED FOR NOW UNDER CURRENT STACK
**Surviving Candidates:** NONE

---

## 1. PURPOSE

This memo closes the E-family work produced by MLB Bounded Discovery Pass 02. The pass completed honestly and tested both candidates through the rebuilt engine stack. Neither candidate survived structural validation. The family is closed for now under the current frozen engine stack.

---

## 2. SOURCE PROVENANCE

- This closeout was built from local persisted artifacts only
- No new testing was run
- No outside-package inputs were introduced
- This is a documentation closeout, not a new research result
- All branch verdicts are preserved exactly as recorded in the existing artifacts

---

## 3. PASS 02 DISCOVERY SUMMARY

| Field | Value |
|---|---|
| Pass | MLB_BOUNDED_DISCOVERY_PASS_02 |
| Verdict | DISCOVERY_PASS_COMPLETE |
| Mechanism family | CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION |
| Candidates advanced | MLB_E01, MLB_E02 |
| Engine stack | MLB_ENGINE_V1_FOUNDATION + ORCHESTRATION_V1 + RUNTIME_OBJECT_V1 |

Pass 02 was the first post-rebuild bounded discovery pass. It produced 2 provisional candidates inside a single mechanism family. The discovery pass itself completed correctly under the rebuilt governance rules.

---

## 4. E01 SUMMARY

**MLB_E01 — Barrel Rate x Park HR Factor**

| Field | Value |
|---|---|
| Parent test verdict | ADVANCE with broad-flag-rate structural caveat |
| Discovery | +0.109 gap, 43.8% flagged |
| Validation | +0.202 gap |
| OOS | +0.230 gap |
| Child check (E01A) verdict | **COMPONENT_DOMINATED** |

E01 initially showed a clean monotonic staged profile. However, the E01A component-dominance check revealed that `park_factor_hr >= 1.10` flags 100% of rows in every stage — the threshold is below the field minimum in the data. The "interaction" is entirely barrel rate alone. Component B (park HR factor) is vacuous.

**E01 must not be salvaged as a barrel-rate-alone continuation.** The candidate was framed as a contact-shape x environment interaction. Once the interaction is shown to not exist, the candidate fails as formulated. A standalone barrel-rate signal is a different candidate that would need to be proposed, anti-duplicated, and tested independently — not silently inherited from E01's structural failure.

---

## 5. E01A SUMMARY

**MLB_E01A — Component Dominance Check**

| Field | Value |
|---|---|
| Verdict | COMPONENT_DOMINATED |
| Component A (barrel rate >= 0.08 alone) | Identical to full formulation in every stage |
| Component B (park_factor_hr >= 1.10 alone) | Degenerate — flags 100% of rows, no unflagged group |
| Full formulation | = Component A exactly |

The decomposition is definitive: the park HR factor threshold is vacuous. The "interaction" was barrel rate alone wearing a decorative park-factor label.

---

## 6. E02 SUMMARY

**MLB_E02 — Launch Angle x Wind-Out**

| Field | Value |
|---|---|
| Verdict | **HARD_STOP** |
| Staged results | None computed |
| Reason | Cannot construct an honest park-specific wind-out definition from available fields |

E02 was not falsified on staged evidence. It was blocked because the frozen foundation package and runtime object do not contain park-orientation data (center-field bearing) required to map `wind_direction` degrees to "blowing out" at each venue. A generic degree-range approximation was explicitly forbidden by the test discipline rules.

**E02 is preserved as a future candidate** if park-orientation data is added to a future foundation package (V2). The mechanism (elevated launch angle x wind blowing out) is physically plausible but untestable with the current stack.

---

## 7. FINAL FAMILY CONCLUSIONS

1. **Pass 02 completed honestly and did not produce a surviving candidate.** Both candidates were tested (or attempted) under correct governance and failed for legitimate structural reasons.

2. **E01 initially looked promising directionally but failed structural integrity testing.** The component-dominance check showed the interaction does not exist — the park factor threshold is vacuous.

3. **E01 must not be silently reinterpreted as a barrel-rate-alone continuation.** The candidate was proposed as an interaction. It failed as an interaction. Barrel rate alone is a different hypothesis.

4. **E02 was not falsified on staged evidence; it was blocked because the frozen stack cannot express "wind out" honestly.** This is a data-boundary limitation, not a signal failure.

5. **The CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION family is closed for now under the current frozen engine stack.** The two candidates tested both environmental components available in the runtime object (park_factor_hr and wind_direction) and both failed structurally.

6. **Reopening this family requires either:**
   - A newly approved park-orientation / wind-semantics data layer that enables honest environmental definitions
   - Or a distinct candidate design that does not rely on the failed/vacuous structures already observed

7. **The rebuilt engine workflow behaved correctly.** It killed E01 for the right reason (component dominance via vacuous threshold) and hard-stopped E02 for the right reason (missing semantic support for honest wind-out definition). This is exactly what the governance layer is supposed to do.

---

## 8. OPERATIONAL DISPOSITION

### Do NOT:
- Advance E01
- Advance E02
- Reinterpret E01 as a surviving barrel-rate object
- Continue pass-02 child branching
- Claim pass 02 found a deployable or structurally valid candidate

### Do:
- Preserve pass 02 as completed research history
- Move active research attention to a different mechanism family
- Preserve the E02 hard-stop lesson as a stack-boundary rule: future candidates requiring park-relative wind semantics must wait for park-orientation data
- Preserve the E01 lesson as a threshold-discipline rule: environmental thresholds must actually create selectivity in the data

---

## 9. WHAT WOULD BE REQUIRED TO REOPEN THIS FAMILY

To reopen the CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION family, at least one of these must be true:

1. **Park orientation data approved:** A new data layer containing park center-field bearing / orientation angles is added to a future foundation package (V2). This would enable honest wind-out definitions and allow E02 (or a similar candidate) to be tested.

2. **A materially different candidate design:** A new candidate within this family that does not depend on park_factor_hr thresholds (which are vacuous at ≥1.10) or wind-direction semantics (which require park orientation). The new candidate must be anti-duplicated against E01 and E02 and must demonstrate that its environmental component is not vacuous.

Without one of these, reopening is not justified.

---

## 10. NEXT RESEARCH DIRECTION

Active research attention should move to a **new bounded discovery pass in a different mechanism family.** Pass 02 exhausted the testable contact-shape x environment candidates available under the current stack.

The next pass should:
- Choose a mechanism family where the runtime object's approved fields can honestly express both components of the interaction
- Verify environmental/contextual field sufficiency BEFORE candidate generation
- Apply the threshold-discipline lessons from E01 (check that thresholds create real selectivity) and E02 (check that semantic definitions are supportable)

---

## 11. FINAL CLOSEOUT VERDICT

**NO_SURVIVING_CANDIDATE — FAMILY CLOSED FOR NOW UNDER CURRENT STACK**

Pass 02 is complete. Both candidates failed for legitimate structural reasons. The rebuilt engine governance worked correctly. No surviving candidate advances. The family is preserved as documented research history.

---

*Closeout generated: 2026-04-18*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
