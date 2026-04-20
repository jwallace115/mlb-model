# MLB BOUNDED DISCOVERY PASS 02 — REPORT

**Original Pass Date:** 2026-04-18
**Reconstruction Date:** 2026-04-19
**Mechanism Family:** CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,430 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This was the first post-rebuild MLB bounded discovery pass through the corrected engine stack. It generated 2 candidate hypotheses within the CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION family.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | confirmed |
| Orchestration layer | confirmed |
| Runtime object | MLB_RUNTIME_OBJECT_V1 — confirmed |
| Outside-package files | NONE |

---

## 3. PROVENANCE NOTE

**This is a reconstruction from verified session records.** The original discovery pass 02 artifact files were created on 2026-04-18 but were not durable at their canonical path. They were lost between sessions. This reconstruction preserves the documented outcomes exactly as they occurred. No new analysis was run. The provenance type is RECONSTRUCTED_FROM_VERIFIED_SESSION_RECORDS.

---

## 4. MECHANISM FAMILY ENFORCED

CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION — how batted-ball/contact profile may interact with run environment to create a state more specific than generic offense quality or generic environment inflation.

---

## 5. CANDIDATES ADVANCED

### MLB_E01 — Barrel Rate x Park HR Factor

| Field | Value |
|---|---|
| candidate_id | MLB_E01 |
| mechanism_family | CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION |
| interaction_form | AND rule |
| required_runtime_fields | contact_barrel_rate_last_10, park_factor_hr |
| proposed_threshold | contact_barrel_rate_last_10 >= 0.08 AND park_factor_hr >= 1.10 |

**Core claim:** Market may underreact when elevated barrel-type contact potential interacts with home-run-amplifying park context, producing a run-environment expansion state more specific than generic offense quality or generic hitter-park inflation.

**Final disposition:** CLOSED — E01A component dominance check found park_factor_hr >= 1.10 was vacuous (flagged 100% of rows in every stage). Full formulation collapsed entirely to barrel rate alone. E01 is not a real interaction. The threshold was below the minimum value in the data.

### MLB_E02 — Launch Angle x Wind-Out

| Field | Value |
|---|---|
| candidate_id | MLB_E02 |
| mechanism_family | CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION |
| interaction_form | AND rule (intended) |
| required_runtime_fields | contact_la_last_10, wind_direction, wind_speed |

**Core claim:** Market may underreact when air-ball / elevated-contact-shape state interacts with outward wind, creating a run-environment expansion state more specific than generic wind-out conditions or generic offense quality.

**Final disposition:** HARD_STOP — Park orientation data not available in frozen foundation package. Honest outward-wind definition requires park-specific center-field bearing which does not exist in the runtime object. Generic degree-range approximation explicitly forbidden by test discipline rules. E02 is DATA_GAP_RESOLVABLE if park orientation data becomes available in a future V2 foundation package.

---

## 6. CANDIDATES REJECTED

| Name | Reason |
|---|---|
| High xwOBA x High Park Factor | Generic quality x generic environment. No contact-shape mechanism. xwOBA is comprehensive contact quality, not contact shape. Market prices both directly. |

---

## 7. E-FAMILY FINAL DISPOSITION

| Branch | Verdict |
|---|---|
| E01 | CLOSED — component-dominated (vacuous park threshold) |
| E02 | HARD_STOP — DATA_GAP_RESOLVABLE (missing park orientation semantics) |
| E-family | CLOSED under current frozen stack |

Lessons documented:
- Vacuous thresholds are structural failure (E01)
- Semantically unsupported mechanisms must hard stop (E02)
- No salvage of failed interactions by quiet reinterpretation

---

## 8. FINAL RECOMMENDATION

Pass 02 completed honestly. No surviving candidate under current infrastructure. Active research attention moved to WORKLOAD / DEPTH / HANDOFF ASYMMETRY family (Pass 03).

---

*Reconstructed: 2026-04-19 from verified session records*
