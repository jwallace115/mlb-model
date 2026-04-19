# MLB E01A — COMPONENT DOMINANCE CHECK REPORT

**Test Date:** 2026-04-18
**Branch Name:** MLB_E01A_COMPONENT_DOMINANCE_CHECK
**Parent Branch:** MLB_E01_MANUAL_HISTORICAL_TEST
**Candidate ID:** MLB_E01
**Advancement Type:** MANUAL_CHILD_CHECK
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,804 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This child branch tests whether E01's signal requires its full 2-field interaction formulation (barrel rate AND park HR factor), or whether the result is explained by one component alone while the other acts as a vacuous filter.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | confirmed |
| Orchestration layer | confirmed (default_deny=true) |
| Runtime object | MLB_RUNTIME_OBJECT_V1 — confirmed |
| Outside-package files | **NONE** |

---

## 3. MANUAL CHILD-CHECK STATUS

This is a manual child check of MLB_E01. It is not a new discovery pass, not autonomous promotion, and not a new candidate. The parent was manually advanced from Bounded Discovery Pass 02.

---

## 4. PARENT OBJECT CONFIRMATION

Parent E01 frozen formulation inherited exactly:

| Element | Value |
|---|---|
| Field 1 | `contact_barrel_rate_last_10` |
| Field 2 | `park_factor_hr` |
| Interaction form | AND rule |
| Rule | barrel_rate >= 0.08 AND park_factor_hr >= 1.10 |
| Direction | Flagged > unflagged on actual_total |

No modification.

---

## 5. FROZEN COMPARISON GROUPS

| Group | Definition |
|---|---|
| COMPONENT_A_ONLY | `contact_barrel_rate_last_10 >= 0.08` |
| COMPONENT_B_ONLY | `park_factor_hr >= 1.10` |
| E01_FULL_FORMULATION | `contact_barrel_rate_last_10 >= 0.08 AND park_factor_hr >= 1.10` |

---

## 6. NESTING / COMPARISON STRUCTURE

**Critical structural finding:** The three groups are nested, and the nesting is completely degenerate.

| Stage | Comp A flagged | Comp B flagged | Full flagged | A_not_B | B_not_A |
|---|---|---|---|---|---|
| Discovery | 4,071 | 9,300 | 4,071 | 0 | 5,229 |
| Validation | 1,978 | 4,644 | 1,978 | 0 | 2,666 |
| OOS | 2,637 | 4,646 | 2,637 | 0 | 2,009 |

**Component B (park_factor_hr >= 1.10) flags 100% of rows in every stage.** Every game in the usable dataset (rows with non-null barrel rate, 2022-2025) has a park HR factor of 1.10 or higher. The threshold is below the minimum value in the data.

This means:
- **A_not_B = 0** in every stage — there are no rows where barrel rate meets threshold but park factor does not
- **E01_FULL_FORMULATION = COMPONENT_A_ONLY exactly** — the full interaction is identical to barrel rate alone
- **Component B is a vacuous filter** — it adds zero selectivity

The "interaction" claimed by E01 does not exist in the data. The park_factor_hr >= 1.10 threshold never excludes any game, so the AND rule collapses entirely to barrel rate alone.

---

## 7. STAGE RESULTS

| Stage | Group | N Flagged | Flag % | Gap | Note |
|---|---|---|---|---|---|
| Discovery | COMPONENT_A | 4,071 | 43.8% | +0.109 | Barrel rate alone |
| Discovery | COMPONENT_B | 9,300 | 100.0% | N/A | DEGENERATE — no unflagged |
| Discovery | FULL | 4,071 | 43.8% | +0.109 | Identical to Comp A |
| Validation | COMPONENT_A | 1,978 | 42.6% | +0.202 | Barrel rate alone |
| Validation | COMPONENT_B | 4,644 | 100.0% | N/A | DEGENERATE |
| Validation | FULL | 1,978 | 42.6% | +0.202 | Identical to Comp A |
| OOS | COMPONENT_A | 2,637 | 56.8% | +0.230 | Barrel rate alone |
| OOS | COMPONENT_B | 4,646 | 100.0% | N/A | DEGENERATE |
| OOS | FULL | 2,637 | 56.8% | +0.230 | Identical to Comp A |

---

## 8. INTERPRETATION

### The Interaction Does Not Exist

E01 was framed as a contact-shape × run-environment interaction: barrel rate AND park HR factor. The decomposition reveals that the park HR factor component contributes nothing because the frozen threshold (>= 1.10) is below the minimum park_factor_hr value in the dataset. Every game passes the park threshold. The "interaction" is entirely barrel rate alone.

This means:
- **The parent E01 test actually tested barrel rate alone, not an interaction**
- The monotonic staged profile (+0.109 → +0.202 → +0.230) is a property of barrel rate >= 0.08 as a standalone flag, not of any interaction
- The mechanism claim (barrels amplified by HR-friendly parks) was never actually tested because the park filter never excluded anything

### Is Barrel Rate Alone Interesting?

Component A (barrel rate >= 0.08 alone) shows the same clean monotonic profile that E01 showed. Teams with above-average barrel rates produce slightly more runs. This is not surprising — it is a direct consequence of barrel rate being a good offensive quality metric. The signal may be real but it is **not a contact-shape × environment interaction.** It is generic contact quality.

This collapses E01 into exactly what the anti-duplication check was supposed to prevent: a single-factor contact-quality signal masquerading as an interaction because the second factor was vacuous.

### Why the Threshold Failed

The park_factor_hr >= 1.10 threshold was set from domain knowledge assuming that 1.10 represents "above-average HR park." However, park_factor_hr in the runtime object (from game_table) may use a different scaling than assumed. If park factors in the data are all >= 1.10 (or if the field represents something other than a simple ratio centered on 1.0), the threshold fails to create any selectivity.

This is a lesson about threshold discipline: even domain-grounded thresholds can be vacuous if the field's actual value range does not match the assumed scale. The discovery pass correctly prohibited data inspection to set thresholds, but this meant the threshold could not be validated against the field's actual range.

---

## 9. FINAL VERDICT

**COMPONENT_DOMINATED**

The E01 "interaction" does not exist. Component B (park_factor_hr >= 1.10) is a vacuous filter that excludes zero rows. The full formulation is identical to Component A (barrel rate alone). The claimed contact-shape × environment interaction collapses to a single-factor contact-quality signal.

E01 as currently formulated is not a real interaction. It is barrel rate alone with a decorative park threshold that does nothing.

---

## 10. WHAT THIS RESULT DOES NOT CLAIM

- This does not say barrel rate is useless as a signal — it may have value as a standalone feature
- This does not say contact-shape × environment interactions are impossible — only that this specific formulation failed
- This is not deployment approval or profitability proof
- This does not close the E-family — a reformulated interaction with a meaningful park threshold could be tested separately

---

*Report generated: 2026-04-18*
